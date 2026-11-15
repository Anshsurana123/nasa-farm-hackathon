"""FAO-56 / FAO-33 Daily Soil-Water & Thermal Stress Simulation. (TASK-M02, M03)

Simulates daily root-zone soil moisture depletion (TAW, RAW, Ks, deep percolation),
crop evapotranspiration (ETc and actual ETa), irrigation demand, and yield response
to both water stress and reproductive/terminal heat stress across multi-year rotations.

Key physical mechanisms modelled:
1. Saxton-Rawls soil water holding capacity (FC, WP, sand/clay percolation) with
   inter-seasonal root-zone moisture carryover.
2. Lowland rice hydrology parameterised to match Punjab Agricultural University (PAU) trials
   (Bouman & Tuong 2001; Ladha et al. 2009; Humphreys et al. 2010; Sudhir-Yadav et al. 2011):
   - Puddled transplanted rice (`rice_puddled`, `rice_short`, `basmati`):
     Mechanical puddling destroys soil aggregates and compacts a plough pan (reducing saturated
     conductivity Ksat relative to unpuddled soil). However, PTR maintains a continuous standing ponded
     head (5-10 cm) throughout vegetative and reproductive growth. This continuous positive hydrostatic
     pressure head drives steady-state downward percolation (~3.5 mm/day on alluvial loam), alongside
     a ~175 mm pre-transplanting puddling/land-soaking requirement.
   - Direct-seeded rice (`rice_dsr`) with Alternate Wetting & Drying (AWD):
     Unpuddled soil has higher saturated conductivity (Ksat) because no plough pan is formed.
     However, DSR eliminates continuous standing ponding. Under AWD, soil is kept in an unsaturated/aerobic
     state between irrigations; unsaturated hydraulic conductivity drops by several orders of magnitude as
     matric suction develops. Downward drainage occurs primarily during the transient pulse after irrigation
     until field capacity is reached. Hence, the effective seasonal time-averaged percolation flux under AWD
     averages ~2.55 mm/day on loam (vs ~3.5 mm/day continuous ponded loss in PTR), saving ~24-28% irrigation
     water when combined with the elimination of the puddling soak (75 mm rauni vs 175 mm puddling).
     On coarse sandy soils (sand > 55%), poor water retention increases percolation to ~4.2 mm/day and causes
     iron chlorosis and weed competition penalties.
3. Reproductive heat sterility and March wheat terminal heat (>32 C during grain fill,
   Asseng et al. 2011; Lobell et al. 2012; PAU 2022 heatwave records), plus Happy Seeder surface residue mulch
   evaporation reduction (-10%) and canopy cooling (-1.0 C) (Sidhu et al. 2007).
"""

from __future__ import annotations

import datetime
import functools
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from terraloop_schemas import CalendarSlotSpec, CropSpec, FarmConstraints, Rotation, SoilSummary

from terraloop_engine import crop_kb
from terraloop_engine.models import agroclimate

_ORDINAL_EPOCH_OFFSET = 719163  # datetime.date(1970, 1, 1).toordinal()

# Empirical Ky from FAO-33 Table 24
_KY_LOOKUP: dict[str, float] = {
    "wheat": 1.05,
    "wheat_winter": 1.05,
    "wheat_spring": 1.05,
    "barley": 1.00,
    "oats": 1.00,
    "triticale": 1.00,
    "maize": 1.25,
    "chickpea": 0.85,
    "mustard": 0.90,
    "rapeseed_canola": 0.90,
    "soybean": 0.85,
    "sorghum": 0.90,
    "cotton": 0.85,
    "potato": 1.10,
    "sugar_beet": 1.05,
    "sunflower": 0.95,
    "groundnut": 0.70,
    "moong": 0.85,
    "urad": 0.85,
    "field_pea": 1.05,
    "faba_bean": 1.05,
    "lupin": 0.90,
    "alfalfa": 0.95,
    "rice_upland": 1.15,
    "cassava": 0.85,
    "sweet_potato": 0.95,
}


@dataclass(slots=True)
class _WeatherArrays:
    """Contiguous NumPy arrays & epoch-day index for fast zero-DataFrame seasonal slicing."""

    days_epoch: np.ndarray
    min_year: int
    doy: np.ndarray
    precip: np.ndarray
    et0: np.ndarray
    tmax: np.ndarray
    tmin: np.ndarray
    solar: np.ndarray | None
    ref_rad_cache: dict[bytes, float]


def build_weather_arrays(w_df: pd.DataFrame) -> _WeatherArrays | None:
    """Extract monotonic midnight-daily NumPy arrays from a simulation weather DataFrame."""
    if len(w_df) == 0 or not isinstance(w_df.index, pd.DatetimeIndex) or not w_df.index.is_monotonic_increasing:
        return None
    if not all(col in w_df.columns for col in ("Precipitation", "ReferenceET", "MaxTemp", "MinTemp")):
        return None
    dt_vals = w_df.index.to_numpy()
    dt_days = dt_vals.astype("datetime64[D]")
    if not np.array_equal(dt_vals, dt_days.astype(dt_vals.dtype)):
        return None
    days_epoch = dt_days.astype(np.int64)
    solar_col = (
        "SolarRadiation"
        if "SolarRadiation" in w_df.columns
        else ("ALLSKY_SFC_SW_DWN" if "ALLSKY_SFC_SW_DWN" in w_df.columns else None)
    )
    return _WeatherArrays(
        days_epoch=days_epoch,
        min_year=int(w_df.index.year.min()),
        doy=w_df.index.dayofyear.to_numpy(dtype=np.int16),
        precip=np.asarray(w_df["Precipitation"], dtype=float),
        et0=np.asarray(w_df["ReferenceET"], dtype=float),
        tmax=np.asarray(w_df["MaxTemp"], dtype=float),
        tmin=np.asarray(w_df["MinTemp"], dtype=float),
        solar=np.asarray(w_df[solar_col], dtype=float) if solar_col is not None else None,
        ref_rad_cache={},
    )

# Standard sowing DOY defaults for Indian agro-climatic rotation slots
# season_index 0: Kharif (Jun-Oct), 1: Rabi (Nov-Apr), 2: Zaid / Summer (Apr-Jun)
_SLOT_DEFAULTS = {
    0: {"name": "kharif", "sowing_month": 6, "sowing_day": 18, "default_dur": 120},
    1: {"name": "rabi", "sowing_month": 11, "sowing_day": 8, "default_dur": 145},
    2: {"name": "zaid", "sowing_month": 4, "sowing_day": 12, "default_dur": 65},
}


def to_daily_simulation_weather(power_df: pd.DataFrame, lat: float) -> pd.DataFrame:
    """Convert a NASA POWER daily frame into standard FAO-56 daily simulation weather format.

    Columns: MinTemp, MaxTemp, Precipitation, ReferenceET, Date.
    """
    df = power_df.copy()

    if not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            dates = pd.to_datetime(df["Date"])
        elif "date" in df.columns:
            dates = pd.to_datetime(df["date"])
        else:
            dates = pd.date_range("2000-01-01", periods=len(df), freq="D")
    else:
        dates = df.index

    tmax = df["T2M_MAX"] if "T2M_MAX" in df.columns else df.get("MaxTemp", 30.0)
    tmin = df["T2M_MIN"] if "T2M_MIN" in df.columns else df.get("MinTemp", 18.0)
    precip = df["PRECTOTCORR"] if "PRECTOTCORR" in df.columns else df.get("Precipitation", 0.0)

    tmax_s = pd.Series(np.asarray(tmax, dtype=float), index=dates)
    tmin_s = pd.Series(np.asarray(tmin, dtype=float), index=dates)
    precip_s = pd.Series(np.asarray(precip, dtype=float), index=dates).clip(lower=0.0)

    rs_col = "ALLSKY_SFC_SW_DWN" if "ALLSKY_SFC_SW_DWN" in df.columns else ("SolarRadiation" if "SolarRadiation" in df.columns else None)
    rs_s = pd.Series(np.asarray(df[rs_col], dtype=float), index=dates) if rs_col is not None else None
    rh_s = pd.Series(np.asarray(df["RH2M"], dtype=float), index=dates) if "RH2M" in df.columns else None
    ws_s = pd.Series(np.asarray(df["WS2M"], dtype=float), index=dates) if "WS2M" in df.columns else None

    et0_col = "ET0" if "ET0" in df.columns else ("ReferenceET" if "ReferenceET" in df.columns else None)
    use_existing_et0 = False
    if et0_col is not None:
        raw_et0 = pd.to_numeric(df[et0_col], errors="coerce")
        if raw_et0.notna().all() and (raw_et0 >= 0.0).all() and (raw_et0 <= 20.0).all():
            et0_s = pd.Series(np.asarray(raw_et0, dtype=float), index=dates)
            use_existing_et0 = True

    if not use_existing_et0:
        et0_s = agroclimate.et0_penman_monteith_series(
            tmax_s,
            tmin_s,
            lat,
            rs_mj_m2_day=rs_s,
            rh_mean_pct=rh_s,
            wind_m_s=ws_s,
        )

    out_cols: dict[str, object] = {
        "MinTemp": tmin_s.values,
        "MaxTemp": tmax_s.values,
        "Precipitation": precip_s.values,
        "ReferenceET": et0_s.values,
        "Date": dates,
    }
    if rs_s is not None:
        out_cols["SolarRadiation"] = rs_s.values

    return pd.DataFrame(out_cols, index=dates)


# Backward-compatible alias
to_aquacrop_weather = to_daily_simulation_weather


@functools.lru_cache(maxsize=256)
def _cached_stage_kc(kc_tuple: tuple[float, float, float], n_days: int) -> np.ndarray:
    if n_days <= 0:
        return np.array([0.5], dtype=float)
    kc_ini, kc_mid, kc_end = kc_tuple
    n_ini = max(1, round(0.20 * n_days))
    n_dev = max(1, round(0.25 * n_days))
    n_mid = max(1, round(0.35 * n_days))
    n_late = max(1, n_days - (n_ini + n_dev + n_mid))

    s_ini = np.full(n_ini, kc_ini, dtype=float)
    s_dev = np.linspace(kc_ini, kc_mid, n_dev, dtype=float)
    s_mid = np.full(n_mid, kc_mid, dtype=float)
    s_late = np.linspace(kc_mid, kc_end, n_late, dtype=float)
    arr = np.concatenate([s_ini, s_dev, s_mid, s_late])
    out = arr[:n_days] if len(arr) >= n_days else np.pad(arr, (0, n_days - len(arr)), mode="edge")
    out.setflags(write=False)
    return out


def _stage_kc_series(kc_tuple: tuple[float, float, float], n_days: int) -> np.ndarray:
    """Construct daily FAO-56 crop coefficient Kc curve across 4 growth stages."""
    return _cached_stage_kc(kc_tuple, n_days).copy()


def _extract_season_arrays(
    w_arr: _WeatherArrays,
    sow_date: datetime.date,
    dur_days: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray]:
    """Slice daily NumPy weather arrays for [sow_date, sow_date + dur_days - 1] with cross-year stitch."""
    sow_epoch = sow_date.toordinal() - _ORDINAL_EPOCH_OFFSET
    harv_epoch = sow_epoch + dur_days - 1
    days_epoch = w_arr.days_epoch
    i0 = int(np.searchsorted(days_epoch, sow_epoch, side="left"))
    i1 = int(np.searchsorted(days_epoch, harv_epoch, side="right"))

    def _view(s: int, e: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray]:
        return (
            w_arr.precip[s:e],
            w_arr.et0[s:e],
            w_arr.tmax[s:e],
            w_arr.tmin[s:e],
            w_arr.solar[s:e] if w_arr.solar is not None else None,
            w_arr.doy[s:e],
        )

    end_sub = min(i1, i0 + dur_days)
    if i1 - i0 >= dur_days - 5:
        return _view(i0, end_sub)

    n_sub = max(0, end_sub - i0)
    missing = dur_days - n_sub
    if n_sub > 0 and missing > 0:
        last_dt = datetime.date.fromordinal(int(days_epoch[end_sub - 1]) + _ORDINAL_EPOCH_OFFSET)
        next_dt = last_dt + datetime.timedelta(days=1)
        first_yr = w_arr.min_year
        is_leap = first_yr % 4 == 0 and (first_yr % 100 != 0 or first_yr % 400 == 0)
        tgt_day = 28 if (next_dt.month == 2 and next_dt.day == 29 and not is_leap) else next_dt.day
        tail_epoch = datetime.date(first_yr, next_dt.month, tgt_day).toordinal() - _ORDINAL_EPOCH_OFFSET
        t0 = int(np.searchsorted(days_epoch, tail_epoch, side="left"))
        t1 = min(len(days_epoch), t0 + missing)
        if t1 > t0:
            take_t = min(t1 - t0, max(0, dur_days - n_sub))
            t1 = t0 + take_t
            return (
                np.concatenate((w_arr.precip[i0:end_sub], w_arr.precip[t0:t1])),
                np.concatenate((w_arr.et0[i0:end_sub], w_arr.et0[t0:t1])),
                np.concatenate((w_arr.tmax[i0:end_sub], w_arr.tmax[t0:t1])),
                np.concatenate((w_arr.tmin[i0:end_sub], w_arr.tmin[t0:t1])),
                np.concatenate((w_arr.solar[i0:end_sub], w_arr.solar[t0:t1])) if w_arr.solar is not None else None,
                np.concatenate((w_arr.doy[i0:end_sub], w_arr.doy[t0:t1])),
            )

    first_yr = w_arr.min_year
    alt_epoch = datetime.date(first_yr, sow_date.month, min(28, sow_date.day)).toordinal() - _ORDINAL_EPOCH_OFFSET
    a0 = int(np.searchsorted(days_epoch, alt_epoch, side="left"))
    a1 = min(len(days_epoch), a0 + dur_days)
    if a1 - a0 >= 30:
        return _view(a0, a1)
    return _view(0, min(len(days_epoch), dur_days))


def _extract_season_weather(
    weather: pd.DataFrame,
    sowing_date: pd.Timestamp,
    dur_days: int,
) -> pd.DataFrame:
    """Slice `dur_days` of daily weather starting at `sowing_date`.

    If a Rabi season crosses Dec 31 past the final available year in `weather`,
    stitches the Jan-Apr tail from the earliest complete year so full seasonal
    weather is always evaluated without truncation.
    """
    harvest_date = sowing_date + pd.Timedelta(days=dur_days - 1)
    is_mono_dt = isinstance(weather.index, pd.DatetimeIndex) and weather.index.is_monotonic_increasing
    if is_mono_dt:
        i0 = int(weather.index.searchsorted(sowing_date, side="left"))
        i1 = int(weather.index.searchsorted(harvest_date, side="right"))
        sub = weather.iloc[i0 : min(i1, i0 + dur_days)]
        if i1 - i0 >= dur_days - 5:
            return sub
    else:
        sub = weather.loc[(weather.index >= sowing_date) & (weather.index <= harvest_date)]
        if len(sub) >= dur_days - 5:
            return sub.iloc[:dur_days]

    # Cross-year stitch for Rabi crops on the final year of the weather record
    missing = dur_days - len(sub)
    if len(sub) > 0 and missing > 0:
        last_dt = sub.index[-1]
        first_yr = int(weather.index.year.min())
        next_dt = last_dt + pd.Timedelta(days=1)
        tgt_day = (
            28
            if (next_dt.month == 2 and next_dt.day == 29 and not pd.Timestamp(year=first_yr, month=1, day=1).is_leap_year)
            else next_dt.day
        )
        tail_start = pd.Timestamp(year=first_yr, month=next_dt.month, day=tgt_day)
        if is_mono_dt:
            t0 = int(weather.index.searchsorted(tail_start, side="left"))
            tail = weather.iloc[t0 : t0 + missing]
        else:
            tail = weather.loc[weather.index >= tail_start].iloc[:missing]
        if len(tail) > 0:
            return pd.concat([sub, tail]).iloc[:dur_days]

    # Final fallback: slice by day-of-year matching from first available year
    first_yr = int(weather.index.year.min())
    alt_start = pd.Timestamp(year=first_yr, month=sowing_date.month, day=min(28, sowing_date.day))
    if is_mono_dt:
        a0 = int(weather.index.searchsorted(alt_start, side="left"))
        alt_sub = weather.iloc[a0 : a0 + dur_days]
    else:
        alt_sub = weather.loc[weather.index >= alt_start].iloc[:dur_days]
    if len(alt_sub) >= 30:
        return alt_sub
    return weather.iloc[:dur_days]


def _compute_thermal_and_waterlog_factors(
    crop: CropSpec,
    tmax_arr: np.ndarray,
    tmin_arr: np.ndarray,
    precip_arr: np.ndarray,
    clay_pct: float,
    has_mulch: bool,
    has_bbf: bool = False,
    t_base_override: float | None = None,
    t_upper_override: float | None = None,
) -> float:
    """Compute multiplicative yield modifier from heat stress, frost, GDD pacing, and waterlogging.

    Citations:
      - Asseng et al. (2011) Global Change Biology; Lobell et al. (2012) Nature Climate Change:
        wheat grain-fill terminal heat >32 C accelerates leaf senescence and shortens grain filling.
      - Sidhu et al. (2007) Field Crops Research: surface straw mulch (Happy Seeder)
        lowers canopy/topsoil max temperature by ~1.0-1.5 C during March grain fill.
    """
    n_days = len(tmax_arr)
    if n_days == 0:
        return 1.0

    # Ambient mean air temperature drives GDD accumulation; mulch cools reproductive canopy temperature
    raw_tmean = 0.5 * (tmax_arr + tmin_arr)
    eff_tmax = tmax_arr - (1.0 if has_mulch else 0.0)

    # 1. Grain-filling / reproductive heat stress (final 35% of crop duration)
    repro_start = int(0.65 * n_days)
    repro_tmax = eff_tmax[repro_start:]

    if "cool" in crop.season_type and "warm" not in crop.season_type:
        # Cool-season crops (wheat, mustard, chickpea, barley, lentil, potato, field pea, faba bean, rapeseed)
        # Sensitive to reproductive heat (>32.0 C during wheat grain filling; Asseng et al. 2011; Lobell et al. 2012)
        # Cool pulses (chickpea, lentil, pea, faba, lupin) are pod-set sensitive above 30.0 C (Gaur et al. 2015)
        crit_temp = 32.0 if crop.id in ("wheat", "wheat_winter", "wheat_spring") else (
            30.0 if crop.id in ("chickpea", "lentil", "field_pea", "faba_bean", "lupin") else min(crop.max_temp_c - 2.0, 32.0)
        )
        heat_hdd = float(np.sum(np.maximum(0.0, repro_tmax - crit_temp)))
        # Sensitivity inversely proportional to heat_tolerance (1..5)
        sens = 0.0021 * (1.35 - 0.15 * crop.heat_tolerance)
        f_heat = max(0.45, 1.0 - sens * heat_hdd)
    else:
        # Warm-season Kharif/Zaid crops: spikelet/pollen sterility above max_temp_c - 1.5
        crit_temp = crop.max_temp_c - 1.5
        heat_hdd = float(np.sum(np.maximum(0.0, repro_tmax - crit_temp)))
        sens = 0.0035 * (1.35 - 0.15 * crop.heat_tolerance)
        f_heat = max(0.55, 1.0 - sens * heat_hdd)

    # 1b. Stage-specific flowering heat stress (Rice spikelet sterility & Maize silking heat)
    # Citations: Satake & Yoshida (1978); Matsui et al. (2001); Cicchino et al. (2010)
    if "rice" in crop.id:
        anthesis_tmax = eff_tmax[int(0.65 * n_days) : int(0.82 * n_days)]
        if len(anthesis_tmax) > 0:
            sterility_load = float(np.sum(np.maximum(0.0, anthesis_tmax - 35.0)))
            f_heat = min(f_heat, max(0.40, 1.0 - 0.035 * sterility_load))
    elif crop.id == "maize":
        silking_tmax = eff_tmax[int(0.50 * n_days) : int(0.70 * n_days)]
        if len(silking_tmax) > 0:
            silking_heat = float(np.sum(np.maximum(0.0, silking_tmax - 35.0)))
            f_heat = min(f_heat, max(0.45, 1.0 - 0.030 * silking_heat))

    # 2. Vegetative extreme heat load above crop.max_temp_c (pre-reproductive to avoid double-counting)
    extreme_hdd = float(np.sum(np.maximum(0.0, eff_tmax[:repro_start] - crop.max_temp_c)))
    f_extreme_heat = max(0.55, 1.0 - 0.0010 * extreme_hdd)

    # 3. Frost stress / winterkill vs vernalization chill-days
    if crop.winter_dormancy:
        lethal_t = float(crop.lethal_frost_c) if crop.lethal_frost_c is not None else -18.0
        kill_days = int(np.sum(tmin_arr < lethal_t))
        f_frost = max(0.25, 1.0 - 0.12 * kill_days)
    elif crop.min_temp_c > 2.0:
        frost_days = int(np.sum(tmin_arr < 2.0))
        f_frost = max(0.30, 1.0 - 0.08 * frost_days)
    else:
        f_frost = 1.0

    if crop.vernalization_required and crop.vernalization_chill_days > 0:
        chill_days = float(
            np.sum((raw_tmean >= -2.0) & (raw_tmean <= 8.0))
            + 0.5 * np.sum((raw_tmean > 8.0) & (tmin_arr <= 4.0))
        )
        vern_ratio = min(1.0, chill_days / float(crop.vernalization_chill_days))
        f_vern = max(0.25, 0.30 + 0.70 * vern_ratio)
    else:
        f_vern = 1.0

    # 4. GDD accumulation factor
    t_base = float(t_base_override) if t_base_override is not None else crop.base_temp_c
    gdd_tmean = np.minimum(raw_tmean, float(t_upper_override)) if t_upper_override is not None else raw_tmean
    if crop.winter_dormancy:
        dorm_t = float(crop.dormancy_temp_c)
        active_mask = raw_tmean > dorm_t
        gdd = float(np.sum(np.where(active_mask, np.maximum(0.0, gdd_tmean - t_base), 0.0)))
    else:
        gdd = float(np.sum(np.maximum(0.0, gdd_tmean - t_base)))
    req_gdd = crop.gdd_to_maturity
    if gdd < 0.70 * req_gdd:
        f_gdd = max(0.50, gdd / (0.70 * req_gdd))
    else:
        f_gdd = 1.0

    # 5. Monsoon waterlogging penalty for sensitive upland crops (maize, pulses, cotton)
    # Citation: Rathore et al. (1998) Soil & Tillage Research; PAU Package of Practices for Kharif Crops
    if crop.waterlogging_tolerance <= 2 and clay_pct >= 20.0:
        heavy_rain_days = int(np.sum(precip_arr > 50.0))
        if has_bbf:
            f_waterlog = max(0.88, 1.0 - 0.025 * max(0, heavy_rain_days - 2))
        elif heavy_rain_days >= 2:
            f_waterlog = max(0.60, 1.0 - 0.08 * (heavy_rain_days - 1))
        else:
            f_waterlog = 1.0
    else:
        f_waterlog = 1.0

    return float(np.clip(f_heat * f_extreme_heat * f_frost * f_vern * f_gdd * f_waterlog, 0.25, 1.0))


def _simulate_step(
    crop_id: str,
    practices: list[str],
    season_index: int,
    year: int,
    weather: pd.DataFrame,
    soil: SoilSummary,
    constraints: FarmConstraints,
    crops: dict[str, CropSpec],
    initial_depletion_mm: float = 0.0,
    sowing_doy: int | None = None,
    lat: float = 30.0,
    prev_crop_id: str | None = None,
    cultivar_zone: str | None = None,
    calendar_slots: Sequence[CalendarSlotSpec] | None = None,
    _weather_arrays: _WeatherArrays | None = None,
    _crops_pre_resolved: bool = False,
) -> tuple[dict, float]:
    """Execute daily FAO-56 / FAO-33 water-balance simulation for one crop season."""
    norm_slots = (
        [s if isinstance(s, CalendarSlotSpec) else CalendarSlotSpec(**s) for s in calendar_slots]
        if calendar_slots
        else None
    )
    if norm_slots and 0 <= season_index < len(norm_slots):
        slot_spec = norm_slots[season_index]
        slot0_doy = norm_slots[0].default_sowing_doy
        year_offset = 1 if slot_spec.default_sowing_doy < slot0_doy else 0
        is_india_cal = slot_spec.slot_id in (
            "kharif", "rabi", "zaid", "kharif_kuruvai", "rabi_samba", "summer_navarai"
        )
    else:
        slot_spec = None
        year_offset = 1 if (season_index == 2 or (lat < 0 and season_index >= 1)) else 0
        is_india_cal = lat >= 0

    if crop_id == "fallow" or crop_id not in crops:
        fallow_yr = year + year_offset
        if slot_spec is not None and not is_india_cal:
            s_dt = datetime.date(fallow_yr, 1, 1) + datetime.timedelta(days=max(0, slot_spec.default_sowing_doy - 1))
            f_dur = min(90, max(45, slot_spec.max_duration_days // 2))
            h_dt = s_dt + datetime.timedelta(days=f_dur)
            s_str = s_dt.isoformat()
            h_str = h_dt.isoformat()
        else:
            s_md, h_md = {
                0: ("06-15", "10-15"),
                1: ("11-01", "03-15"),
                2: ("04-15", "06-15"),
            }.get(season_index, ("04-15", "06-15"))
            h_yr = fallow_yr + (1 if season_index == 1 else 0)
            s_str = f"{fallow_yr}-{s_md}"
            h_str = f"{h_yr}-{h_md}"
        # Wet-season fallow recharges topsoil moisture; dry off-season fallow carries over depletion
        carry_dep = 10.0 if season_index == 0 else float(initial_depletion_mm)
        return {
            "crop_id": crop_id,
            "season_index": season_index,
            "practices": list(practices),
            "yield_t_ha": 0.0,
            "irrigation_mm": 0.0,
            "eta_mm": 0.0,
            "etc_mm": 0.0,
            "water_productivity_kg_m3": 0.0,
            "water_stress_coefficient": 1.0,
            "thermal_factor": 1.0,
            "duration_days": 60,
            "sowing_date": s_str,
            "harvest_date": h_str,
        }, carry_dep

    raw_crop = crops[crop_id]
    crop = raw_crop if _crops_pre_resolved else crop_kb.resolve_crop_spec(raw_crop, cultivar_zone)
    slot_info = _SLOT_DEFAULTS.get(season_index, _SLOT_DEFAULTS[0])
    s_month, s_day = slot_info["sowing_month"], slot_info["sowing_day"]

    if is_india_cal:
        if crop_id == "rice_short" and season_index == 0:
            s_month, s_day = 6, 22
        elif crop_id == "rice_puddled" and season_index == 0:
            s_month, s_day = 6, 20
        elif crop_id in ("rice_short", "rice_puddled") and season_index == 1:
            s_month, s_day = 10, 15
        elif crop_id == "wheat":
            s_month, s_day = 11, 5
        elif crop_id in ("moong", "urad") and season_index == 2:
            s_month, s_day = 4, 10

    eff_year = year + year_offset
    if sowing_doy is not None:
        eff_doy = max(1, min(365, int(sowing_doy)))
        sowing_date = datetime.date(eff_year, 1, 1) + datetime.timedelta(days=eff_doy - 1)
    elif slot_spec is not None and not is_india_cal:
        eff_doy = max(1, min(365, int(slot_spec.default_sowing_doy)))
        sowing_date = datetime.date(eff_year, 1, 1) + datetime.timedelta(days=eff_doy - 1)
    else:
        sowing_date = datetime.date(eff_year, s_month, s_day)
        if calendar_slots is None and lat < 0:
            sh_doy = ((sowing_date.timetuple().tm_yday + 182 - 1) % 365) + 1
            sowing_date = datetime.date(eff_year, 1, 1) + datetime.timedelta(days=sh_doy - 1)

    has_fast_turnaround = any(p in ("happy_seeder", "zero_till", "no_till") for p in practices)
    sow_doy_num = sowing_date.timetuple().tm_yday
    if (
        crop_id == "wheat"
        and season_index == 1
        and is_india_cal
        and prev_crop_id == "rice_puddled"
        and not has_fast_turnaround
        and sow_doy_num <= 319
    ):
        # Conventional tillage clearance after long-duration Pusa-44 delays wheat sowing past Nov 15
        sowing_date = datetime.date(eff_year, 11, 22)
        sow_doy_num = sowing_date.timetuple().tm_yday

    dur_days = round(0.5 * (crop.duration_days[0] + crop.duration_days[1]))
    if crop_id == "rice_puddled":
        dur_days = 126  # Transplanted field occupancy (June 20 - Oct 24)
    elif crop_id == "rice_short":
        dur_days = 104  # PR-126 transplanted field occupancy (June 22 - Oct 4; 22 fewer field days)
    elif crop_id in ("moong", "urad") and season_index == 2:
        dur_days = 60   # PAU 60-day Summer Sathi Moong catch crop (Apr 10 - Jun 9)

    harvest_date = sowing_date + datetime.timedelta(days=dur_days)
    if _weather_arrays is not None:
        precip_arr, et0_arr, tmax_arr, tmin_arr, solar_sub, doy_sub = _extract_season_arrays(
            _weather_arrays, sowing_date, dur_days
        )
        n_days = len(precip_arr)
    else:
        sow_ts = pd.Timestamp(sowing_date)
        sub_w = _extract_season_weather(weather, sow_ts, dur_days)
        n_days = len(sub_w)
        precip_arr = np.asarray(sub_w["Precipitation"], dtype=float)
        et0_arr = np.asarray(sub_w["ReferenceET"], dtype=float)
        tmax_arr = np.asarray(sub_w["MaxTemp"], dtype=float)
        tmin_arr = np.asarray(sub_w["MinTemp"], dtype=float)
        solar_col = (
            "SolarRadiation"
            if "SolarRadiation" in sub_w.columns
            else ("ALLSKY_SFC_SW_DWN" if "ALLSKY_SFC_SW_DWN" in sub_w.columns else None)
        )
        solar_sub = np.asarray(sub_w[solar_col], dtype=float) if solar_col else None
        doy_sub = sub_w.index.dayofyear.to_numpy(dtype=np.int16) if isinstance(sub_w.index, pd.DatetimeIndex) else None

    aq_ovr = crop_kb.load_aquacrop_override(crop_id)
    sand_pct = float(soil.sand_pct or 45.0)
    clay_pct = float(soil.clay_pct or 20.0)
    fc_vol = float(soil.field_capacity_vol or 0.25)
    wp_vol = float(soil.wilting_point_vol or 0.12)
    root_depth_m = float(aq_ovr["z_max"]) if aq_ovr and "z_max" in aq_ovr else float(crop.root_depth_m or 1.0)
    t_base_ovr = float(aq_ovr["t_base"]) if aq_ovr and "t_base" in aq_ovr else None
    t_upper_ovr = float(aq_ovr["t_upper"]) if aq_ovr and "t_upper" in aq_ovr else None

    # Total Available Water (TAW, mm) in root zone
    taw_mm = max(35.0, (fc_vol - wp_vol) * root_depth_m * 1000.0)
    # Readily Available Water fraction (p): prefer crop AquaCrop override else FAO-56 Table 22
    if aq_ovr and "p_up" in aq_ovr:
        raw_pup = aq_ovr["p_up"]
        p_frac = float(np.mean(raw_pup)) if isinstance(raw_pup, (list, tuple)) else float(raw_pup)
    else:
        p_frac = 0.50 if crop.drought_tolerance <= 3 else (0.60 if crop.drought_tolerance == 4 else 0.68)

    # Deep percolation rate scaling by soil texture
    sand_seepage_factor = float(np.clip(0.60 + 0.90 * (sand_pct / 60.0), 0.5, 2.0))

    has_bbf = "broad_bed_furrow" in practices
    has_mulch = any(p in ("residue_retained", "happy_seeder", "no_till", "zero_till") for p in practices)
    mulch_evap_saving = 0.90 if has_mulch else 1.0  # Mulch cuts stage-1 soil evaporation by ~10% of ETc

    kc_daily = _cached_stage_kc(crop.kc, n_days) * mulch_evap_saving
    etc_daily = et0_arr * kc_daily
    etc_mm = float(np.sum(etc_daily))

    irr_mode = constraints.irrigation
    irr_cap = float(constraints.irrigation_cap_mm) if constraints.irrigation_cap_mm is not None else 9999.0
    if (
        season_index == 2
        and crop_id in ("moong", "urad", "dhaincha")
        and irr_mode == "limited"
        and constraints.irrigation_cap_mm is None
    ):
        # PAU Summer Moong recommendation under limited irrigation: 2-3 light irrigations (~120 mm max)
        irr_cap = min(irr_cap, 120.0)

    # Potential yield benchmark with physical sensitivity to solar radiation, sowing date, and soil texture/SOC (WS-F2)
    y_min, y_max = crop.typical_yield_t_ha
    q_pot = 0.45 if crop_id == "wheat" else 0.68
    y_pot_base = float(y_min + q_pot * (y_max - y_min))

    # 1. Solar Radiation responsiveness during grain filling (Monteith 1977; Fischer 1985)
    if solar_sub is not None and n_days > 0:
        fill_start = int(0.50 * n_days)
        mean_rad = float(np.mean(solar_sub[fill_start:]))
        if is_india_cal:
            # Benchmark radiation in North/Central India during grain fill is ~18.5 MJ/m2/day
            ref_rad = 18.5
        elif _weather_arrays is not None and doy_sub is not None and _weather_arrays.solar is not None:
            fill_doys_sub = doy_sub[fill_start:]
            cache_k = fill_doys_sub.tobytes()
            cached_ref = _weather_arrays.ref_rad_cache.get(cache_k)
            if cached_ref is None:
                fill_doys = np.unique(fill_doys_sub)
                same_vals = _weather_arrays.solar[np.isin(_weather_arrays.doy, fill_doys)]
                same_vals = same_vals[~np.isnan(same_vals)]
                cached_ref = (
                    float(np.clip(float(np.mean(same_vals)), 8.0, 26.0))
                    if len(same_vals) >= 15
                    else -1.0
                )
                _weather_arrays.ref_rad_cache[cache_k] = cached_ref
            ref_rad = cached_ref if cached_ref >= 0.0 else max(10.0, mean_rad)
        elif (
            doy_sub is not None
            and isinstance(weather.index, pd.DatetimeIndex)
            and any(c in weather.columns for c in ("SolarRadiation", "ALLSKY_SFC_SW_DWN"))
        ):
            s_col_w = "SolarRadiation" if "SolarRadiation" in weather.columns else "ALLSKY_SFC_SW_DWN"
            fill_doys = list({int(d) for d in doy_sub[fill_start:]})
            w_doys = weather.index.dayofyear.to_numpy()
            same_vals = np.asarray(weather[s_col_w], dtype=float)[np.isin(w_doys, fill_doys)]
            same_vals = same_vals[~np.isnan(same_vals)]
            ref_rad = float(np.clip(float(np.mean(same_vals)), 8.0, 26.0)) if len(same_vals) >= 15 else max(10.0, mean_rad)
        else:
            ref_rad = max(10.0, mean_rad)
        f_radiation = float(np.clip(0.90 + 0.10 * (mean_rad / ref_rad), 0.88, 1.10))
    else:
        f_radiation = 1.0

    # 2. Sowing date / late sowing penalty for Rabi wheat (PAU Package of Practices: ~0.7% / day delay after Nov 15)
    sowing_penalty = 1.0
    if crop_id == "wheat" and season_index == 1 and is_india_cal and 319 < sow_doy_num < 366:
        late_days = sow_doy_num - 319
        sowing_penalty = float(max(0.78, 1.0 - 0.007 * late_days))

    # 3. Soil texture, organic carbon & pH responsiveness (Saxton-Rawls / PAU soil fertility guide / WS-G2)
    sand_fertility_penalty = float(np.clip(1.0 - 0.18 * max(0.0, (sand_pct - 50.0) / 40.0), 0.84, 1.0))
    soc_val = float(soil.soc_g_per_kg or 5.2)
    soc_fertility_bonus = float(np.clip(0.92 + 0.12 * (soc_val / 7.0), 0.90, 1.08))
    ph_penalty = 1.0
    if soil.ph is not None:
        if soil.ph < 5.5:
            # Aluminum/Mn toxicity and phosphorus fixation in acidic soils (pH < 5.5)
            ph_penalty = float(max(0.70, 1.0 - 0.12 * (5.5 - soil.ph)))
        elif soil.ph > 8.5:
            # Micronutrient (Zn, Fe) deficiency and sodicity/osmotic stress in alkali soils (pH > 8.5)
            ph_penalty = float(max(0.72, 1.0 - 0.10 * (soil.ph - 8.5)))
    f_soil_fertility = sand_fertility_penalty * soc_fertility_bonus * ph_penalty

    y_pot = float(y_pot_base * f_radiation * sowing_penalty * f_soil_fertility)

    # -----------------------------------------------------------------------
    # Case 1: Lowland Paddy Rice (Puddled Transplanted vs Direct-Seeded DSR / AWD)
    # Parameterised to match PAU trials (Ladha et al. 2009; Sudhir-Yadav et al. 2011)
    # Aerobic upland rice (`rice_upland`) intentionally uses Case 2 below.
    # -----------------------------------------------------------------------
    if crop_id in ("rice_puddled", "rice_short", "basmati", "rice_dsr", "rice_japonica_temperate"):
        is_dsr = crop_id == "rice_dsr" or "direct_seeded" in practices or "irrigated_awd" in practices

        # Adjust pre-sowing soak demand upward when Meteomatics reports dry root-zone deficit (>35 mm)
        extra_dry_mm = max(0.0, float(initial_depletion_mm) - 35.0)

        if not is_dsr:
            # Puddled Transplanted Rice (PTR):
            # Mechanical puddling breaks soil aggregates and forms a plough pan (reducing saturated
            # hydraulic conductivity Ksat relative to unpuddled soil). HOWEVER, PTR maintains a
            # continuous standing ponded water head (5-10 cm depth) throughout the vegetative and
            # reproductive stages. This continuous positive hydrostatic pressure head drives steady-state
            # downward percolation (~3.5 mm/d on alluvial loam). Additionally, PTR requires ~175 mm
            # of land-soaking and puddling water before transplanting.
            puddling_mm = 175.0 + min(45.0, extra_dry_mm * 0.55)
            plough_pan_perc_rate = 3.5 * (0.75 + 0.25 * sand_seepage_factor)
            flooded_days = max(60, n_days - 14)
            percolation_mm = plough_pan_perc_rate * flooded_days
            # Monsoon rain effectiveness scales with field exposure window
            rain_capture = 0.68 if crop_id == "rice_short" else 0.82
            eff_rain = float(np.sum(np.minimum(precip_arr * rain_capture, 60.0)))
            gross_water_need = etc_mm + puddling_mm + percolation_mm

            if irr_mode == "none":
                irrigation_mm = 0.0
                eta_mm = min(etc_mm, eff_rain)
                water_stress = max(0.0, 1.0 - (eff_rain / max(1.0, gross_water_need * 0.85)))
            elif irr_mode == "limited":
                target_irr = max(0.0, gross_water_need - eff_rain) * 0.82
                irrigation_mm = min(irr_cap, target_irr)
                supplied = eff_rain + irrigation_mm
                water_stress = max(0.0, 1.0 - (supplied / max(1.0, gross_water_need)))
                eta_mm = etc_mm * (1.0 - 0.85 * water_stress)
            else:
                irrigation_mm = min(irr_cap, max(0.0, gross_water_need - eff_rain))
                supplied = eff_rain + irrigation_mm
                water_stress = max(0.0, 1.0 - (supplied / max(1.0, gross_water_need)))
                eta_mm = etc_mm * (1.0 - 0.85 * water_stress)

            sand_yield_penalty = 1.0
            final_dep = 15.0
        else:
            # Direct-Seeded Rice (DSR) with Alternate Wetting & Drying (AWD):
            # Unpuddled soil has higher saturated conductivity (Ksat) than puddled soil because no
            # plough pan is created. However, DSR eliminates continuous standing ponded water. Under AWD,
            # soil is kept in an unsaturated/aerobic state between irrigations; unsaturated conductivity
            # drops by orders of magnitude as soil matric suction develops. Percolation only occurs
            # during the brief transient hours following an irrigation application until field capacity is
            # reached. Consequently, the effective seasonal time-averaged percolation flux under AWD on
            # loam/clay-loam averages ~2.55 mm/d (compared to continuous ~3.5 mm/d under flooded PTR),
            # and the 175 mm puddling soak is replaced by a lighter ~75 mm pre-sowing rauni irrigation.
            # On coarse sandy soils (sand > 55%) without a plough pan, non-ponded retention is low,
            # percolation increases to ~4.2 mm/d, and iron chlorosis reduces yield.
            rauni_mm = 75.0 + min(30.0, extra_dry_mm * 0.40)
            if sand_pct <= 55.0:
                dsr_seepage_rate = 2.55 * sand_seepage_factor
                sand_yield_penalty = 0.98
            else:
                # Coarse sand without puddling loses water rapidly
                dsr_seepage_rate = 4.2 * sand_seepage_factor
                sand_yield_penalty = max(0.76, 0.98 - 0.012 * (sand_pct - 55.0))

            awd_days = max(60, n_days - 14)
            percolation_mm = dsr_seepage_rate * awd_days
            eff_rain = float(np.sum(np.minimum(precip_arr * 0.80, taw_mm * 0.65)))
            gross_water_need = etc_mm + rauni_mm + percolation_mm

            if irr_mode == "none":
                irrigation_mm = 0.0
                eta_mm = min(etc_mm, eff_rain)
                water_stress = max(0.0, 1.0 - (eff_rain / max(1.0, gross_water_need * 0.80)))
            elif irr_mode == "limited":
                target_irr = max(0.0, gross_water_need - eff_rain) * 0.85
                irrigation_mm = min(irr_cap, target_irr)
                supplied = eff_rain + irrigation_mm
                water_stress = max(0.0, 1.0 - (supplied / max(1.0, gross_water_need)))
                eta_mm = etc_mm * (1.0 - 0.85 * water_stress)
            else:
                irrigation_mm = min(irr_cap, max(0.0, gross_water_need - eff_rain))
                supplied = eff_rain + irrigation_mm
                water_stress = max(0.0, 1.0 - (supplied / max(1.0, gross_water_need)))
                eta_mm = etc_mm * (1.0 - 0.85 * water_stress)

            final_dep = 25.0

        # Thermal and vegetative factors for rice
        f_therm = _compute_thermal_and_waterlog_factors(
            crop,
            tmax_arr,
            tmin_arr,
            precip_arr,
            clay_pct,
            has_mulch,
            has_bbf=has_bbf,
            t_base_override=t_base_ovr,
            t_upper_override=t_upper_ovr,
        )
        actual_yield = y_pot * max(0.20, 1.0 - 1.25 * water_stress) * f_therm * sand_yield_penalty
        water_stress_coeff = float(np.clip(1.0 - water_stress, 0.0, 1.0))

    # -----------------------------------------------------------------------
    # Case 2: Upland / Aerobic Field Crops (Daily Root-Zone Depletion Balance)
    # -----------------------------------------------------------------------
    else:
        if irr_mode == "none" and season_index == 1 and crop.drought_tolerance >= 4:
            # Deep-rooted rainfed Rabi pulses/oilseeds (chickpea, lentil, mustard) grown on
            # post-monsoon residual profile moisture access subsoil capillary storage
            taw_mm = taw_mm * (1.42 if clay_pct >= 30.0 else 1.25)
            dr = 4.0
        else:
            dr = float(np.clip(initial_depletion_mm, 0.0, taw_mm * 0.75))
        if has_mulch:
            # Retained residue preserves pre-sowing soil moisture
            dr = max(0.0, dr - 18.0)

        peff_cap = 85.0 if has_bbf else 75.0
        peff_daily = np.minimum(precip_arr, peff_cap)
        raw_daily = np.clip(p_frac + 0.04 * (5.0 - etc_daily), 0.10, 0.80) * taw_mm
        can_irr = irr_mode != "none"
        irr_limited = irr_mode == "limited"

        irr_sum = 0.0
        eta_sum = 0.0
        ks_sum = 0.0

        for etc_d, peff_d, raw_d in zip(etc_daily.tolist(), peff_daily.tolist(), raw_daily.tolist()):
            # Daily water stress coefficient Ks (FAO-56 Eq. 84)
            if dr <= raw_d:
                ks = 1.0
            elif dr >= taw_mm:
                ks = 0.0
            else:
                denom = max(1e-6, taw_mm - raw_d)
                ks = max(0.0, (taw_mm - dr) / denom)
            ks_sum += ks

            eta_d = ks * etc_d
            eta_sum += eta_d

            # Irrigation decision: trigger when depletion exceeds 75% of adjusted RAW
            irr_d = 0.0
            if can_irr and dr >= raw_d * 0.75:
                app_depth = min(65.0, raw_d)
                rem_cap = irr_cap - irr_sum
                cand = app_depth * 0.70 if irr_limited else app_depth
                irr_d = max(0.0, min(rem_cap, cand))
                irr_sum += irr_d

            # Daily root-zone water balance update (FAO-56 Eq. 85)
            dr_next = dr - peff_d - irr_d + eta_d
            if dr_next < 0.0:
                dr = 0.0
            elif dr_next > taw_mm:
                dr = taw_mm
            else:
                dr = dr_next

        irrigation_mm = irr_sum
        eta_mm = eta_sum
        mean_ks = ks_sum / n_days if n_days > 0 else 1.0

        # FAO-33 yield response to water deficit: (1 - Ya/Ym) = Ky * (1 - ETa/ETc)
        if crop_id in _KY_LOOKUP:
            ky = _KY_LOOKUP[crop_id]
        else:
            ky = float(aq_ovr["ky"]) if aq_ovr and "ky" in aq_ovr else 1.0
        rel_et = eta_mm / max(1.0, etc_mm)
        water_yield_ratio = max(0.18, 1.0 - ky * (1.0 - rel_et))

        f_therm = _compute_thermal_and_waterlog_factors(
            crop,
            tmax_arr,
            tmin_arr,
            precip_arr,
            clay_pct,
            has_mulch,
            has_bbf=has_bbf,
            t_base_override=t_base_ovr,
            t_upper_override=t_upper_ovr,
        )
        actual_yield = y_pot * water_yield_ratio * f_therm
        water_stress_coeff = mean_ks
        final_dep = dr

    tot_water_m3 = (irrigation_mm + float(np.sum(precip_arr))) * 10.0
    wp_kg_m3 = round((actual_yield * 1000.0) / max(100.0, tot_water_m3), 2)

    step_result = {
        "crop_id": crop_id,
        "season_index": season_index,
        "practices": list(practices),
        "yield_t_ha": round(float(actual_yield), 2),
        "irrigation_mm": round(float(irrigation_mm), 1),
        "eta_mm": round(float(eta_mm), 1),
        "etc_mm": round(float(etc_mm), 1),
        "water_productivity_kg_m3": wp_kg_m3,
        "water_stress_coefficient": round(float(water_stress_coeff), 3),
        "thermal_factor": round(float(f_therm), 3),
        "duration_days": n_days,
        "sowing_date": sowing_date.isoformat(),
        "harvest_date": harvest_date.isoformat(),
    }
    return step_result, final_dep


def compute_weather_sig(
    w_df: pd.DataFrame,
    lat: float,
    cultivar_zone: str | None = None,
    first_slot_id: str = "",
) -> tuple:
    """Compute cache signature tuple for a converted daily simulation weather DataFrame."""
    if len(w_df) == 0:
        return ()
    return (
        len(w_df),
        str(w_df.index[0]),
        str(w_df.index[-1]),
        round(float(w_df["Precipitation"].sum()), 2) if "Precipitation" in w_df.columns else 0.0,
        round(float(w_df["MaxTemp"].mean()), 4) if "MaxTemp" in w_df.columns else 0.0,
        round(float(w_df["ReferenceET"].mean()), 4) if "ReferenceET" in w_df.columns else 0.0,
        round(float(lat), 3),
        cultivar_zone or "",
        first_slot_id,
    )


def simulate_rotation(
    rotation: Rotation,
    weather: pd.DataFrame,
    soil: SoilSummary,
    constraints: FarmConstraints,
    start_year: int = 2020,
    crops: dict[str, CropSpec] | None = None,
    lat: float = 30.0,
    step_cache: dict | None = None,
    initial_depletion_mm: float | None = None,
    cultivar_zone: str | None = None,
    calendar_slots: Sequence[CalendarSlotSpec] | None = None,
    weather_sig: tuple | None = None,
    copy_weather: bool = True,
    weather_arrays: _WeatherArrays | None = None,
    crops_pre_resolved: bool = False,
) -> list[dict]:
    """Simulate multi-year rotation sequence under daily FAO-56 soil-water balance."""
    crops = crops or crop_kb.load_crops()
    results: list[dict] = []

    if weather_arrays is not None:
        w_df = weather
        w_arr = weather_arrays
    else:
        if "ReferenceET" not in weather.columns:
            w_df = to_daily_simulation_weather(weather, lat=lat)
        elif not isinstance(weather.index, pd.DatetimeIndex):
            w_df = weather.copy()
            if "Date" in w_df.columns:
                w_df.index = pd.to_datetime(w_df["Date"])
            elif "date" in w_df.columns:
                w_df.index = pd.to_datetime(w_df["date"])
        else:
            w_df = weather.copy() if copy_weather else weather
        w_arr = build_weather_arrays(w_df)

    if initial_depletion_mm is not None:
        current_depletion_mm = float(np.clip(initial_depletion_mm, 0.0, 120.0))
    else:
        current_depletion_mm = 0.0
    norm_slots = (
        [s if isinstance(s, CalendarSlotSpec) else CalendarSlotSpec(**s) for s in calendar_slots]
        if calendar_slots
        else None
    )
    if step_cache is not None and len(w_df) > 0:
        if weather_sig is None:
            weather_sig = compute_weather_sig(
                w_df,
                lat=lat,
                cultivar_zone=cultivar_zone,
                first_slot_id=norm_slots[0].slot_id if norm_slots else "",
            )
    else:
        weather_sig = ()

    n_steps = len(rotation.steps)
    for step_idx, step in enumerate(rotation.steps):
        sim_year = start_year + step.year_index
        prev_cid = rotation.steps[step_idx - 1].crop_id if n_steps > 1 else None
        delay_key = prev_cid if (step.crop_id == "wheat" and prev_cid == "rice_puddled") else None
        cache_key = None
        if step_cache is not None:
            cache_key = (
                weather_sig,
                step.crop_id,
                tuple(sorted(step.practices)),
                step.season_index,
                step.sowing_doy,
                delay_key,
                sim_year,
                round(current_depletion_mm, 1),
                constraints.irrigation,
                constraints.irrigation_cap_mm,
            )
            if cache_key in step_cache:
                cached_res, next_dep = step_cache[cache_key]
                res = dict(cached_res)
                res["year_index"] = step.year_index
                current_depletion_mm = next_dep
                results.append(res)
                continue

        res, next_dep = _simulate_step(
            crop_id=step.crop_id,
            practices=step.practices,
            season_index=step.season_index,
            year=sim_year,
            weather=w_df,
            soil=soil,
            constraints=constraints,
            crops=crops,
            initial_depletion_mm=current_depletion_mm,
            sowing_doy=step.sowing_doy,
            lat=lat,
            prev_crop_id=prev_cid,
            cultivar_zone=cultivar_zone,
            calendar_slots=norm_slots,
            _weather_arrays=w_arr,
            _crops_pre_resolved=crops_pre_resolved,
        )
        if step_cache is not None and cache_key is not None:
            step_cache[cache_key] = (dict(res), next_dep)

        res["year_index"] = step.year_index
        current_depletion_mm = next_dep
        results.append(res)

    return results
