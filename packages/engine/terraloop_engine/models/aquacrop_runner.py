"""FAO-56 / FAO-33 Daily Soil-Water & Thermal Stress Simulation. (TASK-M02, M03)

Simulates daily root-zone soil moisture depletion (TAW, RAW, Ks, deep percolation),
crop evapotranspiration (ETc and actual ETa), irrigation demand, and yield response
to both water stress and reproductive/terminal heat stress across multi-year rotations.

Key physical mechanisms modelled:
1. Saxton-Rawls soil water holding capacity (FC, WP, sand/clay percolation) with
   inter-seasonal root-zone moisture carryover.
2. Lowland rice hydrology (Bouman & Tuong 2001; Yadav et al. 2011 PAU trials):
   - Puddled transplanted rice (`rice_puddled`, `rice_short`, `basmati`) requires
     pre-transplanting puddling water (150-180 mm) and continuous ponded water head,
     creating a plough pan that reduces vertical Ksat on medium/heavy soils.
   - Direct-seeded rice (`rice_dsr`) eliminates puddling water and uses Alternate
     Wetting & Drying (AWD), saving 20-28% water on loam/clay-loam soils, but suffers
     higher deep percolation and iron/weed yield penalties on coarse sandy soils (>60% sand).
3. Reproductive heat sterility and March wheat terminal heat (>32 C during grain fill,
   Asseng et al. 2011; PAU 2022 heatwave records), plus Happy Seeder straw mulch
   evaporation reduction and canopy cooling (Sidhu et al. 2007).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from terraloop_schemas import CropSpec, FarmConstraints, Rotation, SoilSummary

from terraloop_engine import crop_kb
from terraloop_engine.models import agroclimate

# Standard sowing DOY defaults for Indian agro-climatic rotation slots
# season_index 0: Kharif (Jun-Oct), 1: Rabi (Nov-Apr), 2: Zaid / Summer (Apr-Jun)
_SLOT_DEFAULTS = {
    0: {"name": "kharif", "sowing_month": 6, "sowing_day": 18, "default_dur": 120},
    1: {"name": "rabi", "sowing_month": 11, "sowing_day": 8, "default_dur": 145},
    2: {"name": "zaid", "sowing_month": 4, "sowing_day": 12, "default_dur": 65},
}


def to_aquacrop_weather(power_df: pd.DataFrame, lat: float) -> pd.DataFrame:
    """Convert a NASA POWER daily frame into standard daily simulation weather format.

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

    et0_s = agroclimate.et0_hargreaves(tmax_s, tmin_s, lat)

    return pd.DataFrame(
        {
            "MinTemp": tmin_s.values,
            "MaxTemp": tmax_s.values,
            "Precipitation": precip_s.values,
            "ReferenceET": et0_s.values,
            "Date": dates,
        },
        index=dates,
    )


def _stage_kc_series(kc_tuple: tuple[float, float, float], n_days: int) -> np.ndarray:
    """Construct daily FAO-56 crop coefficient Kc curve across 4 growth stages."""
    if n_days <= 0:
        return np.array([0.5])
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
    return arr[:n_days] if len(arr) >= n_days else np.pad(arr, (0, n_days - len(arr)), mode="edge")


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
    sub = weather.loc[(weather.index >= sowing_date) & (weather.index <= harvest_date)]
    if len(sub) >= dur_days - 5:
        return sub.iloc[:dur_days]

    # Cross-year stitch for Rabi crops on the final year of the weather record
    missing = dur_days - len(sub)
    if len(sub) > 0 and missing > 0:
        last_dt = sub.index[-1]
        first_yr = int(weather.index.year.min())
        tail_start = pd.Timestamp(year=first_yr, month=1, day=1) + pd.Timedelta(days=last_dt.dayofyear % 365)
        tail = weather.loc[weather.index >= tail_start].iloc[:missing]
        if len(tail) > 0:
            return pd.concat([sub, tail]).iloc[:dur_days]

    # Final fallback: slice by day-of-year matching from first available year
    first_yr = int(weather.index.year.min())
    alt_start = pd.Timestamp(year=first_yr, month=sowing_date.month, day=min(28, sowing_date.day))
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
) -> float:
    """Compute multiplicative yield modifier from heat stress, frost, GDD pacing, and waterlogging.

    Citations:
      - Asseng et al. (2011) Global Change Biology: wheat grain-fill terminal heat >32 C
        reduces grain yield by ~0.6-0.9% per degree-day above threshold.
      - Sidhu et al. (2007) Field Crops Research: surface straw mulch (Happy Seeder)
        lowers canopy/topsoil max temperature by ~1.2 C during March grain fill.
    """
    n_days = len(tmax_arr)
    if n_days == 0:
        return 1.0

    # Mulch cools topsoil and reproductive microclimate during hot dry afternoons
    eff_tmax = tmax_arr - (1.0 if has_mulch else 0.0)
    tmean = 0.5 * (eff_tmax + tmin_arr)

    # 1. Grain-filling / reproductive heat stress (final 45% of crop duration)
    repro_start = int(0.55 * n_days)
    repro_tmax = eff_tmax[repro_start:]

    if "cool" in crop.season_type and "warm" not in crop.season_type:
        # Cool-season Rabi crops (wheat, mustard, chickpea, barley, lentil, potato)
        # Sensitive to March terminal heat (>30.0 C during grain filling)
        crit_temp = min(crop.max_temp_c - 5.0, 30.0)
        heat_hdd = float(np.sum(np.maximum(0.0, repro_tmax - crit_temp)))
        # Sensitivity inversely proportional to heat_tolerance (1..5)
        sens = 0.0046 * (1.35 - 0.15 * crop.heat_tolerance)
        f_heat = max(0.45, 1.0 - sens * heat_hdd)
    else:
        # Warm-season Kharif/Zaid crops: spikelet/pollen sterility above max_temp_c - 1.5
        crit_temp = crop.max_temp_c - 1.5
        heat_hdd = float(np.sum(np.maximum(0.0, repro_tmax - crit_temp)))
        sens = 0.0035 * (1.35 - 0.15 * crop.heat_tolerance)
        f_heat = max(0.55, 1.0 - sens * heat_hdd)

    # 2. Whole-season extreme heat load above crop.max_temp_c
    extreme_hdd = float(np.sum(np.maximum(0.0, eff_tmax - crop.max_temp_c)))
    f_extreme_heat = max(0.55, 1.0 - 0.0022 * extreme_hdd)

    # 3. Frost stress for frost-sensitive crops
    if crop.min_temp_c > 2.0:
        frost_dd = float(np.sum(np.maximum(0.0, 4.0 - tmin_arr)))
        f_frost = max(0.40, 1.0 - 0.015 * frost_dd)
    else:
        severe_frost_dd = float(np.sum(np.maximum(0.0, crop.min_temp_c - tmin_arr)))
        f_frost = max(0.65, 1.0 - 0.01 * severe_frost_dd)

    # 4. Thermal optimality & GDD accumulation factor (creates natural interannual weather variation)
    opt_lo, opt_hi = crop.optimal_temp_c
    opt_mid = 0.5 * (opt_lo + opt_hi)
    season_tmean = float(np.mean(tmean))
    # Deviation from optimal temperature envelope reduces radiation-use efficiency slightly
    if season_tmean < opt_lo:
        temp_dev = opt_lo - season_tmean
    elif season_tmean > opt_hi:
        temp_dev = season_tmean - opt_hi
    else:
        temp_dev = 0.25 * abs(season_tmean - opt_mid)
    f_thermal_opt = max(0.72, 1.0 - 0.018 * temp_dev)

    # 5. Waterlogging / heavy monsoon cloudburst penalty for non-tolerant crops
    if crop.waterlogging_tolerance <= 2:
        heavy_rain_days = int(np.sum(precip_arr > 45.0))
        clay_vulnerability = max(0.6, clay_pct / 25.0)
        wl_loss = 0.025 * heavy_rain_days * clay_vulnerability * (3 - crop.waterlogging_tolerance)
        f_waterlog = max(0.65, 1.0 - wl_loss)
    else:
        f_waterlog = 1.0

    return float(np.clip(f_heat * f_extreme_heat * f_frost * f_thermal_opt * f_waterlog, 0.25, 1.08))


def _simulate_step(
    crop_id: str,
    year: int,
    season_index: int,
    weather: pd.DataFrame,
    soil: SoilSummary,
    constraints: FarmConstraints,
    practices: list[str],
    initial_depletion_mm: float = 20.0,
) -> dict:
    """Simulate a single season step with daily FAO-56 soil-water balance and thermal response."""
    if crop_id == "fallow":
        return {
            "crop_id": "fallow",
            "yield_t_ha": 0.0,
            "irrigation_mm": 0.0,
            "et_mm": 35.0,
            "etc_mm": 45.0,
            "final_depletion_mm": max(0.0, initial_depletion_mm + 15.0),
            "sowing_date": f"{year}-04-15",
            "harvest_date": f"{year}-06-15",
            "practices": list(practices),
        }

    crops = crop_kb.load_crops()
    if crop_id not in crops:
        raise KeyError(f"Unknown crop_id '{crop_id}'")
    crop = crops[crop_id]

    slot_info = _SLOT_DEFAULTS.get(season_index, _SLOT_DEFAULTS[0])
    s_month = int(slot_info["sowing_month"])
    s_day = int(slot_info["sowing_day"])

    # Crop-specific agronomic sowing dates in India
    if crop_id == "rice_puddled":
        s_month, s_day = 6, 20  # Punjab Subsoil Water Act: transplanting after June 15-20
    elif crop_id == "rice_short":
        s_month, s_day = 6, 22  # PR-126 transplanted late June, harvested late Sept
    elif crop_id == "rice_dsr":
        s_month, s_day = 6, 5   # DSR sown early June before peak monsoon
    elif crop_id == "basmati":
        s_month, s_day = 7, 8   # Basmati transplanted in July
    elif crop_id == "cotton":
        s_month, s_day = 5, 1   # Cotton sown early May
    elif crop_id == "wheat":
        s_month, s_day = 11, 8
    elif crop_id in ("mustard", "chickpea", "lentil", "potato"):
        s_month, s_day = 10, 25
    elif crop_id in ("moong", "urad", "dhaincha") and season_index == 2:
        s_month, s_day = 4, 10

    sowing_date = pd.Timestamp(year=year, month=s_month, day=s_day)
    dur_days = round(0.5 * (crop.duration_days[0] + crop.duration_days[1]))
    if crop_id == "rice_short":
        dur_days = 105  # Field duration from June transplanting to early October harvest

    sub_w = _extract_season_weather(weather, sowing_date, dur_days)
    harvest_date = sowing_date + pd.Timedelta(days=dur_days)

    precip_arr = sub_w["Precipitation"].to_numpy(dtype=float)
    et0_arr = sub_w["ReferenceET"].to_numpy(dtype=float)
    tmax_arr = sub_w["MaxTemp"].to_numpy(dtype=float)
    tmin_arr = sub_w["MinTemp"].to_numpy(dtype=float)
    n_days = len(sub_w)

    # Soil hydraulic properties (Saxton-Rawls volumetric FC & WP + sand/clay texture)
    fc_vol = float(soil.field_capacity_vol if soil.field_capacity_vol is not None else 0.28)
    wp_vol = float(soil.wilting_point_vol if soil.wilting_point_vol is not None else 0.14)
    sand_pct = float(soil.sand_pct if soil.sand_pct is not None else 42.0)
    clay_pct = float(soil.clay_pct if soil.clay_pct is not None else 22.0)
    awc_vol = max(0.05, fc_vol - wp_vol)

    # Total Available Water (TAW) and Readily Available Water (RAW) in root zone (mm)
    taw_mm = max(35.0, 1000.0 * awc_vol * crop.root_depth_m)
    p_frac = float(np.clip(0.45 + 0.04 * (crop.drought_tolerance - 3), 0.35, 0.65))
    raw_mm = p_frac * taw_mm

    # Texture seepage multiplier: sandy soils (>50% sand) lose more water to deep percolation
    # and retain less rain per event; clay soils hold more water per irrigation
    sand_seepage_factor = float(np.clip(1.0 + 0.018 * (sand_pct - 40.0) - 0.010 * (clay_pct - 22.0), 0.65, 1.85))

    has_mulch = any(p in ("residue_retained", "happy_seeder", "no_till", "zero_till") for p in practices)
    mulch_evap_saving = 0.90 if has_mulch else 1.0  # Mulch cuts stage-1 soil evaporation by ~10% of ETc

    kc_daily = _stage_kc_series(crop.kc, n_days) * mulch_evap_saving
    etc_daily = et0_arr * kc_daily
    etc_mm = float(np.sum(etc_daily))

    irr_mode = constraints.irrigation
    irr_cap = float(constraints.irrigation_cap_mm) if constraints.irrigation_cap_mm is not None else 9999.0

    # Potential yield benchmark (upper quartile of typical range under unstressed conditions)
    y_min, y_max = crop.typical_yield_t_ha
    y_pot = float(y_min + 0.68 * (y_max - y_min))

    # -----------------------------------------------------------------------
    # Case 1: Lowland Paddy Rice (Puddled Transplanted vs Direct-Seeded DSR)
    # -----------------------------------------------------------------------
    if crop_id in ("rice_puddled", "rice_short", "basmati", "rice_dsr"):
        is_dsr = crop_id == "rice_dsr" or "direct_seeded" in practices

        if not is_dsr:
            # Puddled Transplanted Rice (PTR):
            # Puddling compacts a plough pan (reducing vertical Ksat to ~2.8 mm/d on loam),
            # BUT requires 150-165 mm land-soaking/puddling water + continuous standing water head.
            puddling_mm = 165.0 if crop_id == "rice_puddled" else 140.0
            # Plough pan reduces sensitivity to sand slightly, but coarse sand still leaks more
            plough_pan_perc_rate = (2.7 if crop_id == "rice_puddled" else 2.4) * (0.75 + 0.25 * sand_seepage_factor)
            percolation_mm = plough_pan_perc_rate * n_days
            eff_rain = float(np.sum(np.minimum(precip_arr * 0.82, 65.0)))
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
            # Direct-Seeded Rice (DSR):
            # Zero puddling water (0 mm) and Alternate Wetting & Drying (no standing ponded head).
            # On loam/clay-loam (sand <= 55%), seepage is much lower (~1.5 mm/d during wet days).
            # On coarse sandy soils (sand > 60%) without a plough pan, deep percolation spikes
            # and iron chlorosis / weed competition penalizes yield (Yadav et al. 2011; PAU).
            if sand_pct <= 55.0:
                dsr_seepage_rate = 1.45 * sand_seepage_factor
                sand_yield_penalty = 0.98
            else:
                # Coarse sand without puddling loses water rapidly
                dsr_seepage_rate = 3.6 * sand_seepage_factor
                sand_yield_penalty = max(0.76, 0.98 - 0.012 * (sand_pct - 55.0))

            percolation_mm = dsr_seepage_rate * n_days
            eff_rain = float(np.sum(np.minimum(precip_arr * 0.80, taw_mm * 0.65)))
            gross_water_need = etc_mm + percolation_mm

            if irr_mode == "none":
                irrigation_mm = 0.0
                water_stress = max(0.0, 1.0 - (eff_rain / max(1.0, gross_water_need * 0.85)))
                eta_mm = etc_mm * (1.0 - water_stress)
            elif irr_mode == "limited":
                target_irr = max(0.0, gross_water_need - eff_rain) * 0.84
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

        ky = 1.10
        f_water = max(0.15, 1.0 - ky * water_stress)
        f_env = _compute_thermal_and_waterlog_factors(crop, tmax_arr, tmin_arr, precip_arr, clay_pct, has_mulch)
        actual_yield = round(max(0.4, y_pot * sand_yield_penalty * f_water * f_env), 2)

    # -----------------------------------------------------------------------
    # Case 2: Upland / Aerobic Field Crops (Daily Root-Zone Depletion Balance)
    # -----------------------------------------------------------------------
    else:
        dr = float(np.clip(initial_depletion_mm, 0.0, taw_mm * 0.75))
        if has_mulch:
            # Retained residue preserves pre-sowing soil moisture
            dr = max(0.0, dr - 18.0)

        tot_irr = 0.0
        tot_eta = 0.0
        # Application depth per irrigation event depends on soil TAW and texture
        irr_gift_mm = max(45.0, min(75.0, raw_mm * (0.85 + 0.20 * sand_seepage_factor)))
        # Conveyance / field application efficiency (sandy soils lose more to deep percolation during flood irrigation)
        app_eff = float(np.clip(0.84 / (0.75 + 0.25 * sand_seepage_factor), 0.58, 0.88))

        for d in range(n_days):
            p_d = precip_arr[d]
            etc_d = etc_daily[d]

            # Effective rain infiltrating root zone (runoff increases on heavy storms)
            infil_rain = min(p_d * 0.88, taw_mm * 0.85)
            dr -= infil_rain

            # Deep percolation if root zone exceeds field capacity (dr < 0)
            dr = max(dr, 0.0)

            # Trigger irrigation when root-zone depletion exceeds RAW threshold
            if irr_mode != "none" and tot_irr < irr_cap:
                trigger_mm = raw_mm if irr_mode == "full" else (raw_mm + 0.35 * (taw_mm - raw_mm))
                if dr >= trigger_mm and (n_days - d) > 10:
                    needed_net = min(dr, irr_gift_mm)
                    gross_applied = min(irr_cap - tot_irr, needed_net / app_eff)
                    tot_irr += gross_applied
                    dr = max(0.0, dr - gross_applied * app_eff)

            # Root-zone water stress coefficient Ks (FAO-56 eq. 84)
            if dr <= raw_mm:
                ks = 1.0
            elif dr >= taw_mm:
                ks = 0.0
            else:
                ks = (taw_mm - dr) / max(1.0, taw_mm - raw_mm)

            eta_d = etc_d * ks
            tot_eta += eta_d
            # Daily root-zone drainage leak on very sandy soils when near field capacity
            sand_leak = 0.45 * max(0.0, (sand_pct - 50.0) / 30.0) if dr < 0.3 * raw_mm else 0.0
            dr = min(taw_mm, dr + eta_d + sand_leak)

        irrigation_mm = tot_irr
        eta_mm = tot_eta
        final_dep = dr

        # Seasonal FAO-33 water-yield response
        ky = 1.22 - 0.10 * crop.drought_tolerance
        water_stress = max(0.0, 1.0 - (eta_mm / max(1.0, etc_mm)))
        f_water = max(0.10, 1.0 - ky * water_stress)
        f_env = _compute_thermal_and_waterlog_factors(crop, tmax_arr, tmin_arr, precip_arr, clay_pct, has_mulch)

        if crop.Typical_yield_t_ha[1] == 0.0 if hasattr(crop, "Typical_yield_t_ha") else crop.typical_yield_t_ha[1] == 0.0:
            actual_yield = 0.0
        else:
            actual_yield = round(max(0.15, y_pot * f_water * f_env), 2)

    return {
        "crop_id": crop_id,
        "yield_t_ha": actual_yield,
        "irrigation_mm": round(float(irrigation_mm), 1),
        "et_mm": round(float(eta_mm), 1),
        "etc_mm": round(float(etc_mm), 1),
        "final_depletion_mm": round(float(final_dep), 1),
        "sowing_date": sowing_date.strftime("%Y-%m-%d"),
        "harvest_date": harvest_date.strftime("%Y-%m-%d"),
        "practices": list(practices),
    }


def simulate_rotation(
    rotation: Rotation,
    weather: pd.DataFrame,
    soil: SoilSummary,
    constraints: FarmConstraints,
    start_year: int,
    lat: float = 30.0,
) -> list[dict]:
    """Return one dict per RotationStep with daily water balance and inter-seasonal moisture carryover."""
    results: list[dict] = []

    if "ReferenceET" not in weather.columns:
        w_df = to_aquacrop_weather(weather, lat=lat)
    else:
        w_df = weather.copy()
        if not isinstance(w_df.index, pd.DatetimeIndex):
            w_df.index = pd.to_datetime(w_df["Date"])

    avail_years = sorted(int(y) for y in w_df.index.year.unique())
    if not avail_years:
        avail_years = [start_year]

    if start_year in avail_years:
        base_idx = avail_years.index(start_year)
    else:
        base_idx = 0

    carryover_depletion_mm = 22.0

    for step in rotation.steps:
        # Cyclic wrap across available weather years so multi-year rotations never reset to year 0
        sim_year = avail_years[(base_idx + step.year_index) % len(avail_years)]
        res = _simulate_step(
            crop_id=step.crop_id,
            year=sim_year,
            season_index=step.season_index,
            weather=w_df,
            soil=soil,
            constraints=constraints,
            practices=step.practices,
            initial_depletion_mm=carryover_depletion_mm,
        )
        carryover_depletion_mm = float(res.get("final_depletion_mm", 22.0))
        res["year_index"] = step.year_index
        res["season_index"] = step.season_index
        results.append(res)

    return results
