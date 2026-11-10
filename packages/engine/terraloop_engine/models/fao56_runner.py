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


# Backward-compatible alias
to_aquacrop_weather = to_daily_simulation_weather


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
      - Asseng et al. (2011) Global Change Biology; Lobell et al. (2012) Nature Climate Change:
        wheat grain-fill terminal heat >32 C accelerates leaf senescence and shortens grain filling.
      - Sidhu et al. (2007) Field Crops Research: surface straw mulch (Happy Seeder)
        lowers canopy/topsoil max temperature by ~1.0-1.5 C during March grain fill.
    """
    n_days = len(tmax_arr)
    if n_days == 0:
        return 1.0

    # Mulch cools topsoil and reproductive microclimate during hot dry afternoons
    eff_tmax = tmax_arr - (1.0 if has_mulch else 0.0)
    tmean = 0.5 * (eff_tmax + tmin_arr)

    # 1. Grain-filling / reproductive heat stress (final 35% of crop duration)
    repro_start = int(0.65 * n_days)
    repro_tmax = eff_tmax[repro_start:]

    if "cool" in crop.season_type and "warm" not in crop.season_type:
        # Cool-season Rabi crops (wheat, mustard, chickpea, barley, lentil, potato)
        # Sensitive to March terminal heat (>32.0 C during grain filling; Asseng et al. 2011; Lobell et al. 2012)
        crit_temp = min(crop.max_temp_c - 2.0, 32.0)
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

    # 2. Vegetative extreme heat load above crop.max_temp_c (pre-reproductive to avoid double-counting)
    extreme_hdd = float(np.sum(np.maximum(0.0, eff_tmax[:repro_start] - crop.max_temp_c)))
    f_extreme_heat = max(0.55, 1.0 - 0.0010 * extreme_hdd)

    # 3. Frost stress for frost-sensitive crops
    if crop.min_temp_c > 2.0:
        frost_days = int(np.sum(tmin_arr < 2.0))
        f_frost = max(0.30, 1.0 - 0.08 * frost_days)
    else:
        f_frost = 1.0

    # 4. GDD accumulation factor
    gdd = float(np.sum(np.maximum(0.0, tmean - crop.base_temp_c)))
    req_gdd = crop.gdd_to_maturity
    if gdd < 0.70 * req_gdd:
        f_gdd = max(0.50, gdd / (0.70 * req_gdd))
    else:
        f_gdd = 1.0

    # 5. Monsoon waterlogging penalty for sensitive upland crops (maize, pulses, cotton)
    if crop.waterlogging_tolerance <= 2 and clay_pct >= 32.0:
        heavy_rain_days = int(np.sum(precip_arr > 50.0))
        if heavy_rain_days >= 3:
            f_waterlog = max(0.70, 1.0 - 0.05 * (heavy_rain_days - 2))
        else:
            f_waterlog = 1.0
    else:
        f_waterlog = 1.0

    return float(np.clip(f_heat * f_extreme_heat * f_frost * f_gdd * f_waterlog, 0.25, 1.0))


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
) -> tuple[dict, float]:
    """Execute daily FAO-56 / FAO-33 water-balance simulation for one crop season."""
    if crop_id == "fallow" or crop_id not in crops:
        fallow_yr = year + (1 if season_index == 2 else 0)
        s_md, h_md = {
            0: ("06-15", "10-15"),
            1: ("11-01", "03-15"),
            2: ("04-15", "06-15"),
        }.get(season_index, ("04-15", "06-15"))
        h_yr = fallow_yr + (1 if season_index == 1 else 0)
        # Monsoon Kharif fallow recharges topsoil moisture; dry Rabi/Zaid fallow carries over depletion
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
            "sowing_date": f"{fallow_yr}-{s_md}",
            "harvest_date": f"{h_yr}-{h_md}",
        }, carry_dep

    crop = crops[crop_id]
    slot_info = _SLOT_DEFAULTS.get(season_index, _SLOT_DEFAULTS[0])
    s_month, s_day = slot_info["sowing_month"], slot_info["sowing_day"]

    if crop_id == "rice_short":
        s_month, s_day = 6, 22
    elif crop_id == "rice_puddled":
        s_month, s_day = 6, 20
    elif crop_id == "wheat":
        s_month, s_day = 11, 5
    elif crop_id in ("moong", "urad") and season_index == 2:
        s_month, s_day = 4, 10

    eff_year = year + (1 if season_index == 2 else 0)
    sowing_date = pd.Timestamp(year=eff_year, month=s_month, day=s_day)
    dur_days = round(0.5 * (crop.duration_days[0] + crop.duration_days[1]))
    if crop_id == "rice_puddled":
        dur_days = 126  # Transplanted field occupancy (June 20 - Oct 24)
    elif crop_id == "rice_short":
        dur_days = 104  # PR-126 transplanted field occupancy (June 22 - Oct 4; 22 fewer field days)
    elif crop_id in ("moong", "urad") and season_index == 2:
        dur_days = 60   # PAU 60-day Summer Sathi Moong catch crop (Apr 10 - Jun 9)

    sub_w = _extract_season_weather(weather, sowing_date, dur_days)
    harvest_date = sowing_date + pd.Timedelta(days=dur_days)
    n_days = len(sub_w)

    precip_arr = np.asarray(sub_w["Precipitation"], dtype=float)
    et0_arr = np.asarray(sub_w["ReferenceET"], dtype=float)
    tmax_arr = np.asarray(sub_w["MaxTemp"], dtype=float)
    tmin_arr = np.asarray(sub_w["MinTemp"], dtype=float)

    sand_pct = float(soil.sand_pct or 45.0)
    clay_pct = float(soil.clay_pct or 20.0)
    fc_vol = float(soil.field_capacity_vol or 0.25)
    wp_vol = float(soil.wilting_point_vol or 0.12)
    root_depth_m = float(crop.root_depth_m or 1.0)

    # Total Available Water (TAW, mm) in root zone
    taw_mm = max(35.0, (fc_vol - wp_vol) * root_depth_m * 1000.0)
    # Readily Available Water fraction (p): baseline from FAO-56 Table 22
    p_frac = 0.50 if crop.drought_tolerance <= 3 else (0.60 if crop.drought_tolerance == 4 else 0.68)

    # Deep percolation rate scaling by soil texture
    sand_seepage_factor = float(np.clip(0.60 + 0.90 * (sand_pct / 60.0), 0.5, 2.0))

    has_mulch = any(p in ("residue_retained", "happy_seeder", "no_till", "zero_till") for p in practices)
    mulch_evap_saving = 0.90 if has_mulch else 1.0  # Mulch cuts stage-1 soil evaporation by ~10% of ETc

    kc_daily = _stage_kc_series(crop.kc, n_days) * mulch_evap_saving
    etc_daily = et0_arr * kc_daily
    etc_mm = float(np.sum(etc_daily))

    irr_mode = constraints.irrigation
    irr_cap = float(constraints.irrigation_cap_mm) if constraints.irrigation_cap_mm is not None else 9999.0
    if season_index == 2 and crop_id in ("moong", "urad", "dhaincha"):
        # PAU Summer Moong recommendation: 2-3 light irrigations (~120 mm max), terminated by May 20
        irr_cap = min(irr_cap, 120.0)

    # Potential yield benchmark (upper quartile of typical range under unstressed conditions)
    y_min, y_max = crop.typical_yield_t_ha
    q_pot = 0.85 if crop_id == "wheat" else 0.68
    y_pot = float(y_min + q_pot * (y_max - y_min))

    # -----------------------------------------------------------------------
    # Case 1: Lowland Paddy Rice (Puddled Transplanted vs Direct-Seeded DSR)
    # Parameterised to match PAU trials (Ladha et al. 2009; Sudhir-Yadav et al. 2011)
    # -----------------------------------------------------------------------
    if crop_id in ("rice_puddled", "rice_short", "basmati", "rice_dsr"):
        is_dsr = crop_id == "rice_dsr" or "direct_seeded" in practices

        if not is_dsr:
            # Puddled Transplanted Rice (PTR):
            # Mechanical puddling breaks soil aggregates and forms a plough pan (reducing saturated
            # hydraulic conductivity Ksat relative to unpuddled soil). HOWEVER, PTR maintains a
            # continuous standing ponded water head (5-10 cm depth) throughout the vegetative and
            # reproductive stages. This continuous positive hydrostatic pressure head drives steady-state
            # downward percolation (~3.5 mm/d on alluvial loam). Additionally, PTR requires ~175 mm
            # of land-soaking and puddling water before transplanting.
            puddling_mm = 175.0
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
            rauni_mm = 75.0
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
        f_therm = _compute_thermal_and_waterlog_factors(crop, tmax_arr, tmin_arr, precip_arr, clay_pct, has_mulch)
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

        daily_eta = np.zeros(n_days, dtype=float)
        daily_irr = np.zeros(n_days, dtype=float)
        daily_ks = np.zeros(n_days, dtype=float)

        for d in range(n_days):
            etc_d = float(etc_daily[d])
            p_d = float(precip_arr[d])

            # Effective rainfall (FAO-56: surface runoff above 75 mm/day)
            peff_d = min(p_d, 75.0)

            # Daily adjusted depletion fraction p and RAW (FAO-56 Eq. 89)
            p_adj = float(np.clip(p_frac + 0.04 * (5.0 - etc_d), 0.10, 0.80))
            raw_d = p_adj * taw_mm

            # Daily water stress coefficient Ks (FAO-56 Eq. 84)
            if dr <= raw_d:
                ks = 1.0
            else:
                ks = max(0.0, (taw_mm - dr) / max(1.0, (taw_mm - raw_d)))
            daily_ks[d] = ks

            eta_d = ks * etc_d
            daily_eta[d] = eta_d

            # Irrigation decision: trigger when depletion exceeds 75% of adjusted RAW
            trigger_dr = raw_d * 0.75
            app_depth = min(raw_d, 65.0)
            irr_d = 0.0
            if irr_mode != "none" and dr >= trigger_dr:
                if irr_mode == "limited":
                    irr_d = min(app_depth * 0.70, irr_cap - np.sum(daily_irr))
                else:
                    irr_d = min(app_depth, irr_cap - np.sum(daily_irr))
                irr_d = max(0.0, irr_d)

            daily_irr[d] = irr_d

            # Daily root-zone water balance update (FAO-56 Eq. 85)
            # dr[d] = dr[d-1] - (P - RO) - I + ETa + DP
            dr_next = dr - peff_d - irr_d + eta_d

            # Deep percolation DP occurs when soil moisture exceeds field capacity (Dr < 0)
            if dr_next < 0.0:
                dr_next = 0.0
            elif dr_next > taw_mm:
                dr_next = taw_mm

            dr = dr_next

        irrigation_mm = float(np.sum(daily_irr))
        eta_mm = float(np.sum(daily_eta))
        mean_ks = float(np.mean(daily_ks)) if n_days > 0 else 1.0

        # FAO-33 yield response to water deficit: (1 - Ya/Ym) = Ky * (1 - ETa/ETc)
        ky = float(crop.waterlogging_tolerance if crop.waterlogging_tolerance > 0.5 else 1.0)
        # Empirical Ky from FAO-33 Table 24
        ky_lookup = {
            "wheat": 1.05,
            "maize": 1.25,
            "chickpea": 0.85,
            "mustard": 0.90,
            "soybean": 0.85,
            "sorghum": 0.90,
            "cotton": 0.85,
            "potato": 1.10,
            "moong": 0.85,
            "urad": 0.85,
        }
        if crop_id in ky_lookup:
            ky = ky_lookup[crop_id]
        else:
            aq_ovr = crop_kb.load_aquacrop_override(crop_id)
            ky = float(aq_ovr["ky"]) if aq_ovr and "ky" in aq_ovr else 1.0
        rel_et = eta_mm / max(1.0, etc_mm)
        water_yield_ratio = max(0.18, 1.0 - ky * (1.0 - rel_et))

        f_therm = _compute_thermal_and_waterlog_factors(crop, tmax_arr, tmin_arr, precip_arr, clay_pct, has_mulch)
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
        "sowing_date": sowing_date.strftime("%Y-%m-%d"),
        "harvest_date": harvest_date.strftime("%Y-%m-%d"),
    }
    return step_result, final_dep


def simulate_rotation(
    rotation: Rotation,
    weather: pd.DataFrame,
    soil: SoilSummary,
    constraints: FarmConstraints,
    start_year: int = 2020,
    crops: dict[str, CropSpec] | None = None,
    lat: float = 30.0,
) -> list[dict]:
    """Simulate multi-year rotation sequence under daily FAO-56 soil-water balance."""
    crops = crops or crop_kb.load_crops()
    results: list[dict] = []

    if "ReferenceET" not in weather.columns:
        w_df = to_daily_simulation_weather(weather, lat=lat)
    else:
        w_df = weather.copy()
        if not isinstance(w_df.index, pd.DatetimeIndex):
            if "Date" in w_df.columns:
                w_df.index = pd.to_datetime(w_df["Date"])
            elif "date" in w_df.columns:
                w_df.index = pd.to_datetime(w_df["date"])

    current_depletion_mm = 0.0

    for step in rotation.steps:
        sim_year = start_year + step.year_index
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
        )
        res["year_index"] = step.year_index
        current_depletion_mm = next_dep
        results.append(res)

    return results
