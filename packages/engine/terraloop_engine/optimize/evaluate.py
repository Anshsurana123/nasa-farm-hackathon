"""Multi-scenario rotation evaluation pipeline & Indian farmer practical metrics. (TASK-O02)

Evaluates Rotation candidates across climate ensemble members to compute:
  - Yields per crop across members (responding to soil hydraulics, drought, and terminal heat)
  - Irrigation demand distribution (P10/P50/P90)
  - Operating profit distribution & CVaR-10 downside risk (combining climate + mandi market volatility)
  - 10-year SOC accretion/depletion (steady-state calibrated RothC-lite + root C)
  - Annual RUSLE soil loss with rotation-specific cover factor C
  - Annual nitrogen balance, Urea bags saved, irrigations saved, and Kharif-Rabi turnaround days
  - Soil Health Score (0-100) based on 5 USDA-NRCS principles
"""

from __future__ import annotations

import zlib
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
from terraloop_schemas import (
    CalendarSlotSpec,
    CropSpec,
    FarmConstraints,
    FieldProfile,
    PracticalFarmerMetrics,
    Rotation,
    SeasonalOperationStep,
    SimulationResult,
)

from terraloop_engine import crop_kb, region_registry
from terraloop_engine.models import agroclimate, economics, fao56_runner, rusle, soil_health, surrogate

# Backward-compatible alias
aquacrop_runner = fao56_runner
from terraloop_engine.optimize import rotations as rot_mod


def compute_rotation_c_factor(rotation: Rotation, crops: dict) -> float:
    """Compute rotation-level RUSLE C factor based on canopy cover and practices."""
    step_c_factors = []
    for step in rotation.steps:
        if step.crop_id == "fallow":
            c_val = 0.15 if "residue_retained" in step.practices else 0.45
        else:
            c_spec = crops.get(step.crop_id)
            group = c_spec.group if c_spec else "cereal"
            if group in ("cover", "fodder"):
                c_val = 0.05
            elif group == "legume":
                c_val = 0.18
            else:
                c_val = 0.25

            if any(p in ("no_till", "zero_till", "happy_seeder") for p in step.practices):
                c_val *= 0.50
            elif "residue_retained" in step.practices:
                c_val *= 0.70
            elif soil_health.is_burning_practice(step.practices):
                c_val *= 1.45

        step_c_factors.append(c_val)

    return float(np.clip(np.mean(step_c_factors), 0.02, 0.50))


def _compute_rothc_monthly_climate(
    members: dict[str, pd.DataFrame],
    profile: FieldProfile,
) -> tuple[list[float], list[float], list[float]]:
    """Precompute 12-month (temperature, precipitation, ET0) climatology for RothC across sampled members."""
    m_temp = [
        (tmax + tmin) / 2.0
        for tmax, tmin in zip(profile.climate.monthly_tmax_c, profile.climate.monthly_tmin_c, strict=False)
    ]
    m_precip = profile.climate.monthly_precip_mm
    ann_et0 = float(profile.climate.annual_et0_mm or 1550.0)
    t_pos = [max(4.0, t) for t in (m_temp if len(m_temp) == 12 else [24.0] * 12)]
    t_pos_sum = sum(t_pos) or 1.0
    m_et0 = [round(ann_et0 * (tv / t_pos_sum), 1) for tv in t_pos]

    if not members:
        return m_temp, m_precip, m_et0

    member_vals = list(members.values())
    if len(member_vals) > 6:
        idxs = np.linspace(0, len(member_vals) - 1, 6, dtype=int)
        sampled = [member_vals[int(i)] for i in idxs]
    else:
        sampled = member_vals

    valid_dfs = [m for m in sampled if len(m) >= 365 and isinstance(m.index, pd.DatetimeIndex)]
    if not valid_dfs:
        return m_temp, m_precip, m_et0

    t_months: dict[int, list[float]] = {mo: [] for mo in range(1, 13)}
    p_months: dict[int, list[float]] = {mo: [] for mo in range(1, 13)}
    e_months: dict[int, list[float]] = {mo: [] for mo in range(1, 13)}
    for mdf in valid_dfs:
        tmax_col = "T2M_MAX" if "T2M_MAX" in mdf.columns else "MaxTemp"
        tmin_col = "T2M_MIN" if "T2M_MIN" in mdf.columns else "MinTemp"
        prec_col = "PRECTOTCORR" if "PRECTOTCORR" in mdf.columns else "Precipitation"
        tmax_s = mdf[tmax_col]
        tmin_s = mdf[tmin_col]
        tmean_s = 0.5 * (tmax_s + tmin_s)
        rs_s = mdf["ALLSKY_SFC_SW_DWN"] if "ALLSKY_SFC_SW_DWN" in mdf.columns else None
        rh_s = mdf["RH2M"] if "RH2M" in mdf.columns else None
        ws_s = mdf["WS2M"] if "WS2M" in mdf.columns else None
        if tmax_col == "MaxTemp" and "ReferenceET" in mdf.columns:
            et0_d = mdf["ReferenceET"]
        else:
            et0_d = agroclimate.et0_penman_monteith_series(
                tmax_s, tmin_s, profile.field.lat, rs_mj_m2_day=rs_s, rh_mean_pct=rh_s, wind_m_s=ws_s
            )
        for mo, val in tmean_s.groupby(tmean_s.index.month).mean().items():
            t_months[int(mo)].append(float(val))
        p_mo_ser = mdf[prec_col].resample("MS").sum()
        for mo, val in p_mo_ser.groupby(p_mo_ser.index.month).mean().items():
            p_months[int(mo)].append(float(val))
        e_mo_ser = et0_d.resample("MS").sum()
        for mo, val in e_mo_ser.groupby(e_mo_ser.index.month).mean().items():
            e_months[int(mo)].append(float(val))

    return (
        [round(float(np.mean(t_months[mo])) if t_months[mo] else 24.0, 2) for mo in range(1, 13)],
        [round(float(np.mean(p_months[mo])) if p_months[mo] else 40.0, 2) for mo in range(1, 13)],
        [round(float(np.mean(e_months[mo])) if e_months[mo] else 125.0, 2) for mo in range(1, 13)],
    )


def _build_eval_context(
    members: dict[str, pd.DataFrame],
    profile: FieldProfile,
    scenario_set_id: str,
) -> dict[str, Any]:
    """Precompute per-field invariants shared across all candidate rotations in a batch."""
    reg_cfg = region_registry.detect_region_config(profile.field.lat, profile.field.lon)
    raw_crops = crop_kb.load_crops()
    crops = {cid: crop_kb.resolve_crop_spec(spec, reg_cfg.cultivar_zone) for cid, spec in raw_crops.items()}
    calendar_slots = (
        list(profile.calendar_slots)
        if getattr(profile, "calendar_slots", None)
        else [CalendarSlotSpec(**s) for s in region_registry.get_calendar_slots(profile.field.lat, profile.field.lon)]
    )
    state_to_use = getattr(profile, "state", None) or reg_cfg.state
    econ_region = reg_cfg.economics_table or (state_to_use.lower().replace(" ", "_") if state_to_use else reg_cfg.region_id)
    econ_data = economics.load_economics(econ_region)
    econ_table = econ_data.get("crops", {})

    first_slot_id = calendar_slots[0].slot_id if calendar_slots else ""
    sim_members: dict[str, pd.DataFrame] = {}
    member_sigs: dict[str, tuple] = {}
    member_avail_yrs: dict[str, list[int]] = {}
    member_arrays: dict[str, Any] = {}
    for member_id, weather_df in members.items():
        if "ReferenceET" not in weather_df.columns:
            w_df = aquacrop_runner.to_daily_simulation_weather(weather_df, lat=profile.field.lat)
        elif not isinstance(weather_df.index, pd.DatetimeIndex):
            w_df = weather_df.copy()
            if "Date" in w_df.columns:
                w_df.index = pd.to_datetime(w_df["Date"])
            elif "date" in w_df.columns:
                w_df.index = pd.to_datetime(w_df["date"])
        else:
            w_df = weather_df
        sim_members[member_id] = w_df
        member_sigs[member_id] = aquacrop_runner.compute_weather_sig(
            w_df,
            lat=profile.field.lat,
            cultivar_zone=reg_cfg.cultivar_zone,
            first_slot_id=first_slot_id,
        )
        member_arrays[member_id] = aquacrop_runner.build_weather_arrays(w_df)
        if hasattr(w_df.index, "year") and len(w_df) > 0:
            member_avail_yrs[member_id] = sorted({int(y) for y in w_df.index.year})

    m_temp, m_precip, m_et0 = _compute_rothc_monthly_climate(sim_members, profile)

    soil = profile.soil
    r_fact = rusle.r_factor_intensity(
        profile.climate.annual_precip_mm,
        max_30m_rate_mmh=profile.hazards.max_30m_precip_rate_mmh,
        extreme_rain_days_per_yr=profile.hazards.extreme_rain_days_per_year,
    )
    soc_pct = (soil.soc_g_per_kg or 7.5) / 10.0
    k_fact = rusle.k_factor_williams(
        sand_pct=soil.sand_pct or 40.0,
        silt_pct=soil.silt_pct or 38.0,
        clay_pct=soil.clay_pct or 22.0,
        soc_pct=soc_pct,
    )
    ls_fact = rusle.ls_factor(slope_pct=soil.slope_pct or 0.8)

    has_live_mm_deficit = bool(
        scenario_set_id == "historical"
        and profile.water.soil_moisture_deficit_mm is not None
        and any(p.source.startswith("Meteomatics") and p.mode == "observed" for p in profile.water.provenance)
    )
    init_dep_mm = profile.water.soil_moisture_deficit_mm if has_live_mm_deficit else None

    return {
        "reg_cfg": reg_cfg,
        "crops": crops,
        "calendar_slots": calendar_slots,
        "econ_region": econ_region,
        "econ_data": econ_data,
        "econ_table": econ_table,
        "rothc_climate": (m_temp, m_precip, m_et0),
        "rusle_base": (r_fact, k_fact, ls_fact),
        "sim_members": sim_members,
        "member_sigs": member_sigs,
        "member_avail_yrs": member_avail_yrs,
        "member_arrays": member_arrays,
        "init_dep_mm": init_dep_mm,
    }


def evaluate_rotation(
    rotation: Rotation,
    members: dict[str, pd.DataFrame],
    profile: FieldProfile,
    constraints: FarmConstraints,
    scenario_set_id: str = "historical",
    price_shock_pct: float = 0.0,
    fertilizer_shock_pct: float = 0.0,
    step_cache: dict | None = None,
    _precomputed: dict[str, Any] | None = None,
) -> SimulationResult:
    """Evaluate a single rotation across all climate ensemble members."""
    soil = profile.soil
    if _precomputed is not None:
        reg_cfg = _precomputed["reg_cfg"]
        crops = _precomputed["crops"]
        calendar_slots = _precomputed["calendar_slots"]
        econ_region = _precomputed["econ_region"]
        econ_data = _precomputed["econ_data"]
        econ_table = _precomputed["econ_table"]
        sim_members = _precomputed["sim_members"]
        member_sigs = _precomputed["member_sigs"]
        member_avail_yrs = _precomputed["member_avail_yrs"]
        member_arrays = _precomputed["member_arrays"]
        init_dep_mm = _precomputed["init_dep_mm"]
        copy_weather = False
        crops_pre_resolved = True
    else:
        reg_cfg = region_registry.detect_region_config(profile.field.lat, profile.field.lon)
        raw_crops = crop_kb.load_crops()
        crops = {cid: crop_kb.resolve_crop_spec(spec, reg_cfg.cultivar_zone) for cid, spec in raw_crops.items()}
        calendar_slots = (
            list(profile.calendar_slots)
            if getattr(profile, "calendar_slots", None)
            else [CalendarSlotSpec(**s) for s in region_registry.get_calendar_slots(profile.field.lat, profile.field.lon)]
        )
        state_to_use = getattr(profile, "state", None) or reg_cfg.state
        econ_region = reg_cfg.economics_table or (state_to_use.lower().replace(" ", "_") if state_to_use else reg_cfg.region_id)
        econ_data = economics.load_economics(econ_region)
        econ_table = econ_data.get("crops", {})
        sim_members = members
        member_sigs = {}
        member_avail_yrs = {}
        member_arrays = {}
        has_live_mm_deficit = bool(
            scenario_set_id == "historical"
            and profile.water.soil_moisture_deficit_mm is not None
            and any(p.source.startswith("Meteomatics") and p.mode == "observed" for p in profile.water.provenance)
        )
        init_dep_mm = profile.water.soil_moisture_deficit_mm if has_live_mm_deficit else None
        copy_weather = True
        crops_pre_resolved = False

    member_profits: list[float] = []
    member_irrigations: list[float] = []
    crop_yields: dict[str, list[float]] = {
        s.crop_id: [] for s in rotation.steps if s.crop_id != "fallow"
    }
    step_yield_samples: list[list[float]] = [[] for _ in rotation.steps]
    step_irr_samples: list[list[float]] = [[] for _ in rotation.steps]

    rotation_years = max(1, max(s.year_index for s in rotation.steps) + 1)

    for member_idx, (member_id, weather_df) in enumerate(sim_members.items()):
        if "hist_" in member_id:
            try:
                start_years = [int(member_id.split("_")[1])]
            except (IndexError, ValueError):
                start_years = [2015]
        elif member_id in member_avail_yrs:
            avail_yrs = member_avail_yrs[member_id]
            if len(avail_yrs) >= rotation_years + 6:
                mid_idx = max(1, (len(avail_yrs) - rotation_years) // 2)
                last_idx = max(1, len(avail_yrs) - rotation_years - 1)
                start_years = sorted({avail_yrs[0], avail_yrs[mid_idx], avail_yrs[last_idx]})
            else:
                start_years = [avail_yrs[0]]
        elif hasattr(weather_df.index, "year") and len(weather_df) > 0:
            avail_yrs = sorted({int(y) for y in weather_df.index.year})
            if len(avail_yrs) >= rotation_years + 6:
                # Multi-decade CMIP6 member (e.g. 2026-2045 or 2041-2060): sample early, mid, and late blocks
                mid_idx = max(1, (len(avail_yrs) - rotation_years) // 2)
                last_idx = max(1, len(avail_yrs) - rotation_years - 1)
                start_years = sorted({avail_yrs[0], avail_yrs[mid_idx], avail_yrs[last_idx]})
            else:
                start_years = [avail_yrs[0]]
        else:
            start_years = [2015]

        w_sig = member_sigs.get(member_id)
        w_arr = member_arrays.get(member_id)

        for sub_idx, start_year in enumerate(start_years):
            step_sims = aquacrop_runner.simulate_rotation(
                rotation=rotation,
                weather=weather_df,
                soil=soil,
                constraints=constraints,
                start_year=start_year,
                crops=crops,
                lat=profile.field.lat,
                step_cache=step_cache,
                initial_depletion_mm=init_dep_mm,
                cultivar_zone=reg_cfg.cultivar_zone,
                calendar_slots=calendar_slots,
                weather_sig=w_sig,
                copy_weather=copy_weather,
                weather_arrays=w_arr,
                crops_pre_resolved=crops_pre_resolved,
            )

            tot_irr = 0.0
            tot_profit = 0.0

            n_sim_steps = len(step_sims)
            for step_i, sim_step in enumerate(step_sims):
                cid = sim_step["crop_id"]
                y_val = sim_step["yield_t_ha"]
                irr_val = float(sim_step["irrigation_mm"])
                tot_irr += irr_val
                if step_i < len(step_yield_samples):
                    step_yield_samples[step_i].append(float(y_val))
                    step_irr_samples[step_i].append(irr_val)

                if cid != "fallow":
                    crop_yields[cid].append(y_val)
                    prev_cid = step_sims[step_i - 1]["crop_id"] if n_sim_steps > 1 else None
                    prec_leg = bool(prev_cid and prev_cid in crops and crops[prev_cid].group in ("legume", "cover"))
                    practices = sim_step.get("practices", [])

                    # Deterministic mandi price realization draw per weather year, procurement_type & market_risk
                    c_econ = econ_table.get(cid, {})
                    m_risk = float(c_econ.get("market_risk", 0.12))
                    proc_type = str(c_econ.get("procurement_type", "nafed_pss"))
                    seed = zlib.crc32(f"{member_id}_{cid}_{member_idx}_{sub_idx}".encode())
                    # Map seed to shock in [-0.5, +0.5]
                    u_val = ((seed % 1000) / 1000.0) - 0.5
                    if proc_type == "msp_assured":
                        # Assured FCI / state procurement at MSP floor
                        price_mult = float(np.clip(1.0 + 0.80 * m_risk * u_val, 0.95, 1.05))
                    elif proc_type == "nafed_pss":
                        # NAFED / PSS 25% procurement ceiling -> moderate mandi discount in surplus years
                        base_realization = 0.94
                        shock = (2.1 * m_risk * u_val) if u_val < 0 else (1.4 * m_risk * u_val)
                        price_mult = float(np.clip(base_realization + shock, 0.68, 1.18))
                    else:
                        # Open mandi-linked crop without assured procurement -> higher price discount & volatility
                        base_realization = 0.86
                        shock = (2.6 * m_risk * u_val) if u_val < 0 else (1.8 * m_risk * u_val)
                        price_mult = float(np.clip(base_realization + shock, 0.52, 1.25))

                    if price_shock_pct != 0.0:
                        price_mult = max(0.25, price_mult * (1.0 + price_shock_pct / 100.0))

                    econ_res = economics.profit_per_ha(
                        cid,
                        y_val,
                        practices=practices,
                        region=econ_region,
                        currency=profile.currency or "INR",
                        price_multiplier=price_mult,
                        preceded_by_legume=prec_leg,
                        irrigation=constraints.irrigation,
                    )
                    step_profit = float(econ_res["profit_per_ha"])
                    if fertilizer_shock_pct != 0.0 and cid in crops:
                        c_spec = crops[cid]
                        synth_n_kg = max(
                            0.0,
                            c_spec.n_demand_kg_ha - c_spec.n_fixation_kg_ha - (25.0 if prec_leg else 0.0),
                        )
                        cur_code = profile.currency or reg_cfg.currency or "INR"
                        usd_rt = float(econ_data.get("usd_exchange_rate", 83.5))
                        unit_n_cost = 14.0 if cur_code == "INR" else round(0.18 * (usd_rt if cur_code != "USD" else 1.0), 4)
                        step_profit -= synth_n_kg * unit_n_cost * (fertilizer_shock_pct / 100.0)
                    tot_profit += step_profit

            ann_irr = tot_irr / rotation_years
            ann_profit = tot_profit / rotation_years

            member_irrigations.append(round(ann_irr, 1))
            member_profits.append(round(ann_profit, 1))

    p_arr = np.array(member_profits) if member_profits else np.array([50000.0])
    p10 = float(np.percentile(p_arr, 10))
    p50 = float(np.percentile(p_arr, 50))
    p90 = float(np.percentile(p_arr, 90))
    worst_10 = p_arr[p_arr <= p10]
    cvar10 = float(np.mean(worst_10)) if len(worst_10) > 0 else p10
    cvar_ci_low, cvar_ci_high = economics.cvar_bootstrap_ci(member_profits, alpha=0.10)

    # Soil Carbon (RothC-lite 10-year simulation)
    # Account for both aboveground straw C (depending on burning/retention/fodder removal) and belowground root C
    ann_residue_c = 0.0
    rot_has_burning = any(soil_health.is_burning_practice(s.practices) for s in rotation.steps)
    n_rot_steps = len(rotation.steps)
    for idx, s in enumerate(rotation.steps):
        if s.crop_id in crops and s.crop_id != "fallow":
            c_spec = crops[s.crop_id]
            step_y_vals = step_yield_samples[idx] if idx < len(step_yield_samples) and step_yield_samples[idx] else crop_yields.get(s.crop_id, [c_spec.typical_yield_t_ha[0]])
            mean_y_step = float(np.mean(step_y_vals))
            typ_min = max(0.4, float(c_spec.typical_yield_t_ha[0]))
            # Scale crop straw/root biomass proportionally when severe water/heat stress depresses yield below typical_min
            yield_scale = float(np.clip(mean_y_step / typ_min, 0.25, 1.0)) if mean_y_step < typ_min else 1.0
            res_t = c_spec.residue_t_ha * yield_scale
            c_frac = 0.45

            if soil_health.is_burning_practice(s.practices) or (rot_has_burning and s.crop_id in ("rice_puddled", "wheat")):
                # Open-field burning destroys ~92% of straw C and oxidizes surface labile humus
                ann_residue_c += res_t * c_frac * 0.25
            elif c_spec.group in ("cover", "legume"):
                # Green manure / pulse haulm incorporated in-situ + N-rich microbial humification boost
                ann_residue_c += res_t * c_frac * 0.85
            elif any(p in ("residue_retained", "happy_seeder", "no_till", "zero_till", "direct_seeded") for p in s.practices):
                # In-situ straw mulch retention + intact root biomass C incorporated into 0-30cm mineral pool
                ann_residue_c += res_t * c_frac * 0.62
            else:
                # Conventional tillage where ~80% of straw is removed for fodder (turi) / fuel
                ann_residue_c += res_t * c_frac * 0.36

    ann_residue_c = max(0.3, ann_residue_c / rotation_years)

    if _precomputed is not None:
        m_temp, m_precip, m_et0 = _precomputed["rothc_climate"]
    else:
        m_temp, m_precip, m_et0 = _compute_rothc_monthly_climate(members, profile)

    covered_months_set: set[int] = set()
    for s in rotation.steps:
        has_surface_cover = (s.crop_id != "fallow") or any(
            p in ("residue_retained", "happy_seeder", "no_till", "zero_till") for p in s.practices
        )
        if not has_surface_cover:
            continue
        dur_d = int(rot_mod._step_duration_days(s.crop_id, crops)) if (s.crop_id != "fallow" and s.crop_id in crops) else 60
        sow_doy = s.sowing_doy or (165 if s.season_index == 0 else (305 if s.season_index == 1 else 100))
        if s.sowing_doy is None and reg_cfg.hemisphere == "SH":
            sow_doy = ((sow_doy + 182 - 1) % 365) + 1
        start_ts = pd.Timestamp(year=2021, month=1, day=1) + pd.Timedelta(days=int(sow_doy) - 1)
        for off in range(0, dur_d + 1, 15):
            covered_months_set.add((start_ts + pd.Timedelta(days=off)).month)

    rothc_res = soil_health.rothc_lite(
        soil=soil,
        clay_pct=soil.clay_pct or 22.0,
        monthly_temp_c=m_temp,
        monthly_precip_mm=m_precip,
        monthly_et0_mm=m_et0,
        annual_c_input_t_ha=ann_residue_c,
        crop_cover_months=sorted(covered_months_set) if covered_months_set else None,
        years=10,
        lat=profile.field.lat,
        c_eq_t_ha_yr=reg_cfg.c_eq_t_ha_yr,
    )
    soc_delta = float(rothc_res["soc_delta_10yr"])

    # RUSLE erosion calculation with rotation C factor & storm kinetic intensity
    rot_c_factor = compute_rotation_c_factor(rotation, crops)
    if _precomputed is not None:
        r_fact, k_fact, ls_fact = _precomputed["rusle_base"]
    else:
        r_fact = rusle.r_factor_intensity(
            profile.climate.annual_precip_mm,
            max_30m_rate_mmh=profile.hazards.max_30m_precip_rate_mmh,
            extreme_rain_days_per_yr=profile.hazards.extreme_rain_days_per_year,
        )
        soc_pct = (soil.soc_g_per_kg or 7.5) / 10.0
        k_fact = rusle.k_factor_williams(
            sand_pct=soil.sand_pct or 40.0,
            silt_pct=soil.silt_pct or 38.0,
            clay_pct=soil.clay_pct or 22.0,
            soc_pct=soc_pct,
        )
        ls_fact = rusle.ls_factor(slope_pct=soil.slope_pct or 0.8)
    p_fact = 1.0
    ann_erosion = float(round(rusle.soil_loss(r_fact, k_fact, ls_fact, rot_c_factor, p_fact), 2))

    # Nitrogen Balance (incorporating Soil Health Card available N mineralization credit when present)
    shc_n_credit = (
        float(np.clip((soil.nitrogen_g_kg * 2240.0 - 280.0) * 0.15, -25.0, 30.0))
        if (soil.source == "farmer_test" and soil.nitrogen_g_kg is not None)
        else 0.0
    )
    n_surpluses = []
    for idx, s in enumerate(rotation.steps):
        if s.crop_id in crops and s.crop_id != "fallow":
            c_spec = crops[s.crop_id]
            prev_step = rotation.steps[idx - 1] if n_rot_steps > 1 else None
            prev_crop_obj = crops.get(prev_step.crop_id) if prev_step else None
            prec_leg = bool(prev_crop_obj is not None and prev_crop_obj.group in ("legume", "cover"))
            ret_res = any(p in ("residue_retained", "happy_seeder") for p in s.practices)
            step_y_vals = step_yield_samples[idx] if idx < len(step_yield_samples) and step_yield_samples[idx] else crop_yields.get(s.crop_id, [2.0])
            mean_y = float(np.mean(step_y_vals))
            n_res = soil_health.n_balance(
                c_spec,
                yield_t_ha=mean_y,
                preceded_by_legume=prec_leg,
                residue_retained=ret_res,
                soil_n_credit_kg_ha=shc_n_credit,
                preceding_crop=prev_crop_obj,
            )
            n_surpluses.append(n_res["n_surplus_deficit_kg_ha"])
    ann_n_balance = float(round(sum(n_surpluses) / rotation_years, 1)) if n_surpluses else 0.0

    # Living root days percentage
    tot_living_days = 0.0
    for s in rotation.steps:
        if s.crop_id in crops and s.crop_id != "fallow":
            dur = (crops[s.crop_id].duration_days[0] + crops[s.crop_id].duration_days[1]) / 2.0
            tot_living_days += dur
    living_roots_pct = float(round(min(100.0, (tot_living_days / (rotation_years * 365.0)) * 100.0), 1))

    fam_div = float(soil_health.family_shannon_index(rotation, crops))

    sh_breakdown = soil_health.soil_health_breakdown(
        rotation=rotation,
        crops=crops,
        soc_delta_10yr=soc_delta,
        erosion_t_ha_yr=ann_erosion,
        has_livestock=constraints.has_livestock,
        soil=soil,
        soc_ref_g_kg=reg_cfg.soc_ref_g_kg,
    )
    sh_score = float(sh_breakdown["total_score"])

    step_yields_map = {
        f"{s.year_index}:{s.season_index}:{s.crop_id}": round(float(np.mean(step_yield_samples[i])), 2)
        for i, s in enumerate(rotation.steps)
        if i < len(step_yield_samples) and step_yield_samples[i]
    }
    step_irr_map = {
        f"{s.year_index}:{s.season_index}:{s.crop_id}": round(float(np.mean(step_irr_samples[i])), 1)
        for i, s in enumerate(rotation.steps)
        if i < len(step_irr_samples) and step_irr_samples[i]
    }

    return SimulationResult(
        rotation_id=rotation.id,
        scenario_set_id=scenario_set_id,
        yield_t_ha=crop_yields,
        irrigation_mm=member_irrigations,
        profit_per_ha=member_profits,
        soc_delta_t_ha_10yr=soc_delta,
        erosion_t_ha_yr=ann_erosion,
        n_balance_kg_ha_yr=ann_n_balance,
        living_root_days_pct=living_roots_pct,
        family_diversity_index=fam_div,
        soil_health_score=sh_score,
        soil_health_breakdown=sh_breakdown,
        profit_p10=round(p10, 1),
        profit_p50=round(p50, 1),
        profit_p90=round(p90, 1),
        cvar_profit_10=round(cvar10, 1),
        cvar_ci_low=cvar_ci_low,
        cvar_ci_high=cvar_ci_high,
        step_yields=step_yields_map,
        step_irrigations_mm=step_irr_map,
    )


def evaluate_candidates(
    rotations: list[Rotation],
    members: dict[str, pd.DataFrame],
    profile: FieldProfile,
    constraints: FarmConstraints,
    scenario_set_id: str = "historical",
    price_shock_pct: float = 0.0,
    fertilizer_shock_pct: float = 0.0,
    progress_cb: Callable[[int, int], None] | None = None,
) -> list[SimulationResult]:
    """Evaluate a list of candidate rotations across climate members."""
    shared_step_cache: dict = {}
    precomputed = _build_eval_context(members, profile, scenario_set_id) if rotations else None
    total = len(rotations)
    results: list[SimulationResult] = []
    for idx, rot in enumerate(rotations):
        results.append(
            evaluate_rotation(
                rotation=rot,
                members=members,
                profile=profile,
                constraints=constraints,
                scenario_set_id=scenario_set_id,
                price_shock_pct=price_shock_pct,
                fertilizer_shock_pct=fertilizer_shock_pct,
                step_cache=shared_step_cache,
                _precomputed=precomputed,
            )
        )
        if progress_cb is not None and (idx + 1 == total or (idx + 1) % 10 == 0):
            progress_cb(idx + 1, total)
    return results


def _format_doy_window(doy: int, span_lo: int = -5, span_hi: int = 10) -> str:
    base_dt = pd.Timestamp(year=2021, month=1, day=1) + pd.Timedelta(days=(int(doy) - 1) % 365)
    lo_dt = base_dt + pd.Timedelta(days=span_lo)
    hi_dt = base_dt + pd.Timedelta(days=span_hi)
    return f"{lo_dt.strftime('%b %d')} – {hi_dt.strftime('%b %d')}"


_SEASON_NAMES_I18N: dict[str, dict[str, dict[int, str]]] = {
    "cauvery": {
        "en": {0: "Kuruvai (SW Monsoon)", 1: "Samba (NE Monsoon)", 2: "Navarai / Thaladi (Summer)"},
        "hi": {0: "कुरुवई (दक्षिण-पश्चिम मानसून)", 1: "सांबा (उत्तर-पूर्व मानसून)", 2: "नवरई / थलाडी (गर्मी)"},
        "pa": {0: "ਕੁਰੂਵਈ (ਦੱਖਣ-ਪੱਛਮੀ ਮੌਨਸੂਨ)", 1: "ਸਾਂਬਾ (ਉੱਤਰ-ਪੂਰਬੀ ਮੌਨਸੂਨ)", 2: "ਨਵਰਈ / ਥਲਾਡੀ (ਗਰਮੀ)"},
        "es": {0: "Kuruvai (Monzón SO)", 1: "Samba (Monzón NE)", 2: "Navarai / Thaladi (Verano)"},
        "pt": {0: "Kuruvai (Monção SO)", 1: "Samba (Monção NE)", 2: "Navarai / Thaladi (Verão)"},
        "fr": {0: "Kuruvai (Mousson SO)", 1: "Samba (Mousson NE)", 2: "Navarai / Thaladi (Été)"},
    },
    "south": {
        "en": {0: "Warm Wet Season", 1: "Cool Winter Season", 2: "Spring Shoulder"},
        "hi": {0: "गर्म आर्द्र मौसम", 1: "ठंडा सर्दी का मौसम", 2: "वसंत मध्यवर्ती मौसम"},
        "pa": {0: "ਗਰਮ ਨਮੀ ਵਾਲਾ ਸੀਜ਼ਨ", 1: "ਠੰਢਾ ਸਰਦੀਆਂ ਦਾ ਸੀਜ਼ਨ", 2: "ਬਸੰਤ ਵਿਚਕਾਰਲਾ ਸੀਜ਼ਨ"},
        "es": {0: "Estación Cálida Húmeda", 1: "Estación Fresca de Invierno", 2: "Entretiempo Primaveral"},
        "pt": {0: "Estação Quente e Úmida", 1: "Estação Fria de Inverno", 2: "Entressafra de Primavera"},
        "fr": {0: "Saison Chaude Humide", 1: "Saison Fraîche d'Hiver", 2: "Intersaison Printanière"},
    },
    "north": {
        "en": {0: "Kharif (Monsoon)", 1: "Rabi (Winter)", 2: "Zaid (Summer)"},
        "hi": {0: "खरीफ (मानसून)", 1: "रबी (सर्दी)", 2: "जायद (गर्मी)"},
        "pa": {0: "ਖਰੀਫ਼ (ਮੌਨਸੂਨ)", 1: "ਰਬੀ (ਸਰਦੀਆਂ)", 2: "ਜ਼ੈਦ (ਗਰਮੀਆਂ)"},
        "es": {0: "Kharif (Monzón)", 1: "Rabi (Invierno)", 2: "Zaid (Verano)"},
        "pt": {0: "Kharif (Monção)", 1: "Rabi (Inverno)", 2: "Zaid (Verão)"},
        "fr": {0: "Kharif (Mousson)", 1: "Rabi (Hiver)", 2: "Zaid (Été)"},
    },
}

_SEASON_FALLBACK_I18N = {
    "en": "Season",
    "hi": "सीज़न",
    "pa": "ਸੀਜ਼ਨ",
    "es": "Temporada",
    "pt": "Safra",
    "fr": "Saison",
}

_FALLOW_TEXT_I18N = {
    "crop_name": {
        "en": "Seasonal Fallow / Residue Mulch",
        "hi": "मौसमी परती / फसल अवशेष मल्च",
        "pa": "ਮੌਸਮੀ ਖਾਲੀ ਖੇਤ / ਪਰਾਲੀ ਮਲਚ",
        "es": "Barbecho Estacional / Cobertura de Rastrojo",
        "pt": "Pousio Sazonal / Cobertura de Palhada",
        "fr": "Jachère Saisonnière / Paillis de Résidus",
    },
    "guidance": {
        "en": "Retain anchored crop stubble mulch on soil surface; avoid unnecessary tillage.",
        "hi": "मिट्टी की सतह पर खड़ी पराली/अवशेष मल्च बनाए रखें; अनावश्यक जुताई से बचें।",
        "pa": "ਮਿੱਟੀ ਦੀ ਸਤ੍ਹਾ 'ਤੇ ਖੜ੍ਹੀ ਪਰਾਲੀ ਦੀ ਮਲਚ ਰੱਖੋ; ਬੇਲੋੜੀ ਵਹਾਈ ਤੋਂ ਬਚੋ।",
        "es": "Conservar rastrojo anclado en superficie; evitar labranza innecesaria.",
        "pt": "Manter palhada na superfície do solo; evitar preparo mecânico desnecessário.",
        "fr": "Maintenir les chaumes en surface du sol ; éviter tout travail du sol superflu.",
    },
}

_MSP_LEVELS_I18N = {
    "global_proxy": {
        "en": "Global Proxy Benchmark (India Reference Market Risk)",
        "hi": "वैश्विक प्रॉक्सी बेंचमार्क (भारत संदर्भ बाज़ार जोखिम)",
        "pa": "ਗਲੋਬਲ ਪ੍ਰੌਕਸੀ ਬੈਂਚਮਾਰਕ (ਭਾਰਤ ਹਵਾਲਾ ਬਾਜ਼ਾਰ ਜੋਖਮ)",
        "es": "Referencia Global Aproximada (Riesgo de Mercado India)",
        "pt": "Referência Global Aproximada (Risco de Mercado Índia)",
        "fr": "Référence Mondiale Indicative (Risque Marché Inde)",
    },
    "regional_verified": {
        "en": "Regional Commodity Benchmark & Conservation Program Support",
        "hi": "क्षेत्रीय जिंस मूल्य मानक एवं संरक्षण कार्यक्रम सहायता",
        "pa": "ਖੇਤਰੀ ਜਿਣਸ ਮੁੱਲ ਮਾਪਦੰਡ ਅਤੇ ਸੰਭਾਲ ਪ੍ਰੋਗਰਾਮ ਸਹਾਇਤਾ",
        "es": "Referencia Regional de Mercado y Apoyos Agroambientales",
        "pt": "Referência Regional de Mercado e Programas Agrícolas",
        "fr": "Référence Régionale de Marché et Aides Agroécologiques",
    },
    "msp_assured": {
        "en": "MSP Assured (FCI / State)",
        "hi": "सुनिश्चित MSP (FCI / राज्य खरीद)",
        "pa": "ਯਕੀਨੀ MSP (FCI / ਰਾਜ ਖਰੀਦ)",
        "es": "Precio Mínimo Garantizado (MSP)",
        "pt": "Preço Mínimo Garantido (MSP)",
        "fr": "Prix Minimum Garanti (MSP)",
    },
    "mandi_linked": {
        "en": "Mandi Market-Linked",
        "hi": "मंडी बाज़ार-आधारित मूल्य",
        "pa": "ਮੰਡੀ ਬਾज़ार-ਅਧਾਰਤ ਕੀਮਤ",
        "es": "Precio Vinculado a Mercado Local",
        "pt": "Preço Vinculado ao Mercado Local",
        "fr": "Prix Indexé sur le Marché Local",
    },
    "nafed_pss": {
        "en": "NAFED / PSS Supported",
        "hi": "NAFED / PSS मूल्य समर्थन",
        "pa": "NAFED / PSS ਕੀਮਤ ਸਹਾਇਤਾ",
        "es": "Con Soporte NAFED / PSS",
        "pt": "Com Suporte NAFED / PSS",
        "fr": "Avec Soutien NAFED / PSS",
    },
}

_GUIDANCE_NOTES_I18N: dict[str, dict[str, str]] = {
    "rice_dsr": {
        "en": "Drill-seed at 20 kg/ha after 75 mm pre-sowing rauni irrigation; apply AWD wetting/drying",
        "hi": "75 मिमी बुवाई-पूर्व रौनी सिंचाई के बाद 20 किग्रा/हेक्टेयर सीधी बुवाई (DSR) करें; AWD से सिंचाई अंतराल रखें",
        "pa": "75 ਮਿ.ਮੀ. ਰੌਣੀ ਸਿੰਚਾਈ ਤੋਂ ਬਾਅਦ 20 ਕਿਲੋ/ਹੈਕਟੇਅਰ ਸਿੱਧੀ ਬਿਜਾਈ (DSR) ਕਰੋ; AWD ਤਰੀਕੇ ਨਾਲ ਪਾਣੀ ਦਿਓ",
        "es": "Siembra directa de precisión a 20 kg/ha con manejo de humedecimiento y secado alterno (AWD)",
        "pt": "Semeadura direta a 20 kg/ha com manejo intermitente de lâmina d'água (AWD)",
        "fr": "Semis direct à 20 kg/ha avec irrigation alternée mouillage-séchage (AWD)",
    },
    "rice_short": {
        "en": "Transplant 25-day short-duration seedlings; stop irrigation 14 days before harvest for early clearance",
        "hi": "25 दिन की कम अवधि की पौध रोपें; समय पर खेत खाली करने के लिए कटाई से 14 दिन पहले सिंचाई बंद करें",
        "pa": "25 ਦਿਨਾਂ ਦੀ ਘੱਟ ਸਮੇਂ ਵਾਲੀ ਪਨੀਰੀ ਲਗਾਓ; ਜਲਦੀ ਵਾਢੀ ਲਈ ਕਟਾਈ ਤੋਂ 14 ਦਿਨ ਪਹਿਲਾਂ ਪਾਣੀ ਬੰਦ ਕਰੋ",
        "es": "Usar variedad de ciclo corto y suspender el riego 14 días antes de cosecha",
        "pt": "Utilizar cultivar de ciclo curto e suspender irrigação 14 dias antes da colheita",
        "fr": "Utiliser une variété précoce et stopper l'irrigation 14 jours avant la récolte",
    },
    "rice_puddled": {
        "en": "Conventional puddled transplanted paddy (high percolation & narrow turnaround)",
        "hi": "पारंपरिक कद्दू (पडलिंग) धान रोपाई (अधिक पानी रिसाव और कम बुवाई अंतराल)",
        "pa": "ਰਵਾਇਤੀ ਕੱਦੂ ਕੀਤੇ ਝੋਨੇ ਦੀ ਲੁਆਈ (ਵੱਧ ਪਾਣੀ ਰਿਸਾਅ ਅਤੇ ਘੱਟ ਸਮਾਂ)",
        "es": "Arroz trasplantado en fangueo convencional (alta percolación y ventana estrecha)",
        "pt": "Arroz transplantado em solo encharcado (alta percolação e janela curta)",
        "fr": "Riz repiqué en sol boueux conventionnel (forte percolation et interculture courte)",
    },
    "broad_bed_furrow": {
        "en": "Plant on ICRISAT Broad-Bed & Furrow (BBF) beds to drain storm excess and store subsoil moisture",
        "hi": "तेज़ बारिश का अतिरिक्त पानी निकालने और नमी संचयन के लिए ICRISAT चौड़ी मेड़-नाली (BBF) पर बुवाई करें",
        "pa": "ਭਾਰੀ ਮੀਂਹ ਦਾ ਵਾਧੂ ਪਾਣੀ ਕੱਢਣ ਅਤੇ ਨਮੀ ਸਾਂਭਣ ਲਈ ICRISAT ਚੌੜੀ ਵੱਟ-ਖਾਲੀ (BBF) 'ਤੇ ਬਿਜਾਈ ਕਰੋ",
        "es": "Sembrar en camellones amplios con surcos para drenar excesos y almacenar humedad",
        "pt": "Plantio em camalhões largos com sulcos para drenagem de chuvas intensas e reserva hídrica",
        "fr": "Semer sur billons larges avec sillons pour drainer les excès pluviaux et préserver l'humidité",
    },
    "happy_seeder": {
        "en": "Direct-drill into standing crop mulch using Happy Seeder / zero-till disc seeder without burning",
        "hi": "पराली जलाए बिना खड़ी मल्च में PAU हैप्पी सीडर / सुपर SMS से सीधी बुवाई करें",
        "pa": "ਪਰਾਲੀ ਸਾੜੇ ਬਿਨਾਂ ਖੜ੍ਹੇ ਕਰਚਿਆਂ ਵਿੱਚ PAU ਹੈਪੀ ਸੀਡਰ / ਸੁਪਰ SMS ਨਾਲ ਸਿੱਧੀ ਬਿਜਾਈ ਕਰੋ",
        "es": "Siembra directa bajo cobertura de rastrojo sin labranza ni quema",
        "pt": "Plantio direto na palha sem revolvimento ou queima de resíduos",
        "fr": "Semis direct sous couvert de résidus sans labour ni brûlage",
    },
    "zero_till": {
        "en": "Zero-till seed-cum-fertilizer drill into anchored crop residue",
        "hi": "खड़े फसल अवशेष में ज़ीरो-टिल सीड-कम-फर्टिलाइज़र ड्रिल से बुवाई करें",
        "pa": "ਖੜ੍ਹੇ ਫ਼ਸਲੀ ਅਵਸ਼ੇਸ਼ਾਂ ਵਿੱਚ ਜ਼ੀਰੋ-ਟਿੱਲ ਸੀਡ-ਕਮ-ਖਾਦ ਡਰਿੱਲ ਨਾਲ ਬਿਜਾਈ ਕਰੋ",
        "es": "Siembra directa con sembradora de cero labranza sobre rastrojo anclado",
        "pt": "Plantio direto com semeadora-adubadora sobre palhada ancorada",
        "fr": "Semis direct sans labour avec combiné semoir-engrais dans les résidus",
    },
    "residue_retained": {
        "en": "Retain surface crop residue as organic soil armor to conserve root-zone moisture",
        "hi": "जड़-क्षेत्र की नमी बचाने के लिए सतह पर फसल अवशेष को जैविक मल्च के रूप में रखें",
        "pa": "ਜੜ੍ਹ-ਖੇਤਰ ਦੀ ਨਮੀ ਬਚਾਉਣ ਲਈ ਸਤ੍ਹਾ 'ਤੇ ਫ਼ਸਲੀ ਅਵਸ਼ੇਸ਼ਾਂ ਦੀ ਜੈਵਿਕ ਮਲਚ ਰੱਖੋ",
        "es": "Mantener el rastrojo en superficie para proteger el suelo y conservar humedad",
        "pt": "Manter a palhada na superfície para proteger o solo e conservar umidade radicular",
        "fr": "Conserver les résidus en surface pour protéger le sol et limiter l'évaporation",
    },
    "prec_leg": {
        "en": "Reduce basal nitrogen dose by ~25–45 kg N/ha using preceding legume BNF credit",
        "hi": "पिछली दलहनी फसल के नाइट्रोजन लाभ से आधार यूरिया खुराक 25 किग्रा N/हेक्टेयर (~55 किग्रा यूरिया) कम करें",
        "pa": "ਪਿਛਲੀ ਦਾਲ ਵਾਲੀ ਫ਼ਸਲ ਦੇ ਨਾਈਟ੍ਰੋਜਨ ਲਾਭ ਸਦਕਾ ਮੁੱਢਲੀ ਯੂਰੀਆ ਖੁਰਾਕ 25 ਕਿਲੋ N/ਹੈਕਟੇਅਰ (~55 ਕਿਲੋ ਯੂਰੀਆ) ਘਟਾਓ",
        "es": "Reducir el nitrógeno basal ~25–45 kg N/ha gracias al aporte simbiótico de la leguminosa previa",
        "pt": "Reduzir a adubação nitrogenada de base em ~25–45 kg N/ha pelo crédito da leguminosa anterior",
        "fr": "Réduire l'apport azoté de fond de ~25–45 kg N/ha grâce au précédent légumineuse",
    },
    "irr_none": {
        "en": "Rainfed conservation profile (ridge-furrow / moisture-conserving mulch)",
        "hi": "वर्षा आधारित नमी संरक्षण प्रणाली (मेड़-नाली / बंध निर्माण)",
        "pa": "ਬਰਸਾਤੀ ਨਮੀ ਸੰਭਾਲ ਪ੍ਰਣਾਲੀ (ਵੱਟ-ਖਾਲੀ / ਖੇਤ ਬੰਨ੍ਹ)",
        "es": "Manejo de secano con conservación de humedad y cobertura vegetal",
        "pt": "Sistema de sequeiro com conservação de umidade e palhada",
        "fr": "Conduite pluviale de conservation de l'humidité du sol",
    },
    "irr_limited": {
        "en": "Deficit irrigation only at critical flowering and grain-filling stages",
        "hi": "केवल फूल आने और दाना भरने की महत्वपूर्ण अवस्था में ही सीमित सिंचाई दें",
        "pa": "ਸਿਰਫ਼ ਫੁੱਲ ਆਉਣ ਅਤੇ ਦਾਣੇ ਭਰਨ ਦੇ ਨਾਜ਼ੁਕ ਪੜਾਵਾਂ 'ਤੇ ਹੀ ਸੀਮਤ ਪਾਣੀ ਦਿਓ",
        "es": "Riego deficitario estratégico solo en floración y llenado de grano",
        "pt": "Irrigação deficitária apenas nos estádios críticos de florescimento e enchimento",
        "fr": "Irrigation déficitaire ciblée sur la floraison et le remplissage du grain",
    },
    "default_cycle": {
        "en": "Standard regional package of practices ({dur_days}d field cycle)",
        "hi": "मानक क्षेत्रीय कृषि पद्धतियाँ ({dur_days} दिन का फसल चक्र)",
        "pa": "ਮਿਆਰੀ ਖੇਤਰੀ ਖੇਤੀਬਾੜੀ ਵਿਧੀਆਂ ({dur_days} ਦਿਨਾਂ ਦਾ ਫ਼ਸਲੀ ਚੱਕਰ)",
        "es": "Manejo agronómico regional estándar (ciclo de {dur_days} días)",
        "pt": "Manejo agronômico regional padrão (ciclo de {dur_days} dias)",
        "fr": "Itinéraire technique régional standard (cycle de {dur_days} jours)",
    },
}


def _build_step_guidance(
    crop_id: str,
    season_index: int,
    practices: list[str],
    prec_leg: bool,
    irrigation_mode: str,
    dur_days: int,
    sowing_doy: int | None = None,
    lat: float = 30.0,
    language: str = "en",
    hemisphere: str | None = None,
) -> tuple[str, str, str]:
    """Return (sowing_window, harvest_window, agronomic_guidance) for a rotation step."""
    lang = language if language in ("en", "hi", "pa", "es", "pt", "fr") else "en"
    is_sh = (hemisphere == "SH") if hemisphere is not None else (lat < 0)
    if sowing_doy is not None:
        sow_win = _format_doy_window(sowing_doy, -5, 10)
        harv_win = _format_doy_window(((sowing_doy + dur_days - 1) % 365) + 1, -7, 8)
    elif is_sh:
        sh_sow = {0: 345, 1: 126, 2: 280}.get(season_index, 345)
        sow_win = _format_doy_window(sh_sow, -5, 10)
        harv_win = _format_doy_window(((sh_sow + dur_days - 1) % 365) + 1, -7, 8)
    else:
        windows = {
            0: ("Jun 15 – Jul 05", "Oct 05 – Oct 25"),
            1: ("Nov 01 – Nov 20", "Apr 01 – Apr 18"),
            2: ("Apr 10 – Apr 22", "Jun 08 – Jun 20"),
        }
        sow_win, harv_win = windows.get(season_index, ("Jun 15", "Oct 15"))
        if crop_id == "rice_short" and season_index == 0:
            sow_win, harv_win = "Jun 20 – Jun 28", "Oct 01 – Oct 08"
        elif crop_id == "rice_dsr" and season_index == 0:
            sow_win, harv_win = "Jun 05 – Jun 18", "Oct 05 – Oct 15"
        elif crop_id == "rice_puddled" and season_index == 0:
            sow_win, harv_win = "Jun 15 – Jun 25", "Oct 22 – Nov 05"
        elif crop_id in ("rice_puddled", "rice_short") and season_index == 1:
            sow_win, harv_win = "Oct 10 – Oct 25", "Feb 12 – Feb 28"
        elif crop_id in ("mustard", "chickpea", "lentil") and season_index == 1:
            sow_win, harv_win = "Oct 18 – Nov 10", "Mar 15 – Mar 30"

    notes: list[str] = []
    if crop_id == "rice_dsr":
        notes.append(_GUIDANCE_NOTES_I18N["rice_dsr"][lang])
    elif crop_id == "rice_short":
        notes.append(_GUIDANCE_NOTES_I18N["rice_short"][lang])
    elif crop_id == "rice_puddled":
        notes.append(_GUIDANCE_NOTES_I18N["rice_puddled"][lang])
    elif "broad_bed_furrow" in practices:
        notes.append(_GUIDANCE_NOTES_I18N["broad_bed_furrow"][lang])
    elif "happy_seeder" in practices:
        notes.append(_GUIDANCE_NOTES_I18N["happy_seeder"][lang])
    elif any(p in ("zero_till", "no_till") for p in practices):
        notes.append(_GUIDANCE_NOTES_I18N["zero_till"][lang])
    elif "residue_retained" in practices:
        notes.append(_GUIDANCE_NOTES_I18N["residue_retained"][lang])

    if prec_leg:
        notes.append(_GUIDANCE_NOTES_I18N["prec_leg"][lang])
    if irrigation_mode == "none":
        notes.append(_GUIDANCE_NOTES_I18N["irr_none"][lang])
    elif irrigation_mode == "limited":
        notes.append(_GUIDANCE_NOTES_I18N["irr_limited"][lang])

    if not notes:
        notes.append(_GUIDANCE_NOTES_I18N["default_cycle"][lang].format(dur_days=dur_days))
    end_punct = "।" if lang in ("hi", "pa") else "."
    return sow_win, harv_win, "; ".join(notes) + end_punct


def compute_practical_farmer_metrics(
    rotation: Rotation,
    sim_result: SimulationResult,
    baseline_result: SimulationResult | None = None,
    crops: dict[str, CropSpec] | None = None,
    constraints: FarmConstraints | None = None,
    profile: FieldProfile | None = None,
    region_id: str | None = None,
    shc_n_credit: float | None = None,
    price_shock_pct: float = 0.0,
    fertilizer_shock_pct: float = 0.0,
    language: str = "en",
) -> PracticalFarmerMetrics:
    """Translate biophysical simulation outputs into practical farmer decision metrics."""
    lang = language if language in ("en", "hi", "pa", "es", "pt", "fr") else "en"
    reg_cfg = region_registry.detect_region_config(profile.field.lat, profile.field.lon) if profile is not None else None
    if crops is None:
        crops = crop_kb.load_crops()
    if reg_cfg is not None:
        crops = {cid: crop_kb.resolve_crop_spec(spec, reg_cfg.cultivar_zone) for cid, spec in crops.items()}
    state_to_use = None
    if region_id:
        known_states = {
            "haryana": "Haryana",
            "punjab": "Punjab",
            "uttar_pradesh": "Uttar Pradesh",
            "maharashtra": "Maharashtra",
            "tamil_nadu": "Tamil Nadu",
            "vidarbha": "Maharashtra",
            "western_maharashtra": "Maharashtra",
            "bundelkhand": "Uttar Pradesh",
            "western_up": "Uttar Pradesh",
            "cauvery": "Tamil Nadu",
            "thanjavur": "Tamil Nadu",
            "sangrur": "Punjab",
            "ludhiana": "Punjab",
            "bathinda": "Punjab",
        }
        state_to_use = known_states.get(region_id.lower())
        if not state_to_use:
            state_to_use = region_id.capitalize()
    if not state_to_use and profile is not None:
        state_to_use = getattr(profile, "state", None) or region_registry.detect_state(profile.field.lat, profile.field.lon)
    val_status = (profile.validation_status if profile is not None else None) or (
        reg_cfg.validation_status if reg_cfg else "validated_india"
    )
    hemisphere = reg_cfg.hemisphere if reg_cfg is not None else "NH"
    country_code = (profile.country_code if profile is not None else None) or (reg_cfg.country_code if reg_cfg else "IND")
    currency = (profile.currency if profile is not None else None) or (reg_cfg.currency if reg_cfg else "INR") or "INR"
    currency_symbol = (
        (profile.currency_symbol if profile is not None else None)
        or (reg_cfg.currency_symbol if reg_cfg else "₹")
        or "₹"
    )
    lat_val = profile.field.lat if profile is not None else 30.0
    econ_region = (
        (reg_cfg.economics_table if reg_cfg else None)
        or (region_id or (state_to_use.lower().replace(" ", "_") if state_to_use else (reg_cfg.region_id if reg_cfg else "punjab")))
    ).lower()
    econ_data = economics.load_economics(econ_region)
    econ_basis = str(econ_data.get("economics_basis", "local_verified"))
    usd_rt = float(econ_data.get("usd_exchange_rate", 83.5))
    econ_crops = econ_data.get("crops", {})
    raw_slots = (
        list(profile.calendar_slots)
        if (profile is not None and getattr(profile, "calendar_slots", None))
        else (region_registry.get_calendar_slots(profile.field.lat, profile.field.lon) if profile is not None else [])
    )
    slot_name_map = {
        int(s.slot_index if hasattr(s, "slot_index") else s["slot_index"]): str(
            s.name if hasattr(s, "name") else s["name"]
        )
        for s in raw_slots
    }
    slot_doy_map = {
        int(s.slot_index if hasattr(s, "slot_index") else s["slot_index"]): int(
            s.default_sowing_doy if hasattr(s, "default_sowing_doy") else s["default_sowing_doy"]
        )
        for s in raw_slots
    }
    irr_mode = constraints.irrigation if constraints is not None else "full"
    area_ha = float(constraints.area_ha) if constraints is not None and constraints.area_ha > 0 else 1.0

    if profile is not None and region_id is None:
        region_id = reg_cfg.region_id if reg_cfg else None

    # Soil Health Card available nitrogen mineralization credit (if laboratory tested)
    if shc_n_credit is None:
        shc_n_credit = 0.0
        if (
            profile is not None
            and profile.soil is not None
            and profile.soil.source == "farmer_test"
            and profile.soil.nitrogen_g_kg is not None
        ):
            shc_n_credit = float(np.clip((profile.soil.nitrogen_g_kg * 2240.0 - 280.0) * 0.15, -25.0, 30.0))

    rotation_years = max(1, max(s.year_index for s in rotation.steps) + 1)
    turnaround_days = rot_mod.compute_turnaround_days(rotation, crops)

    # 1. Irrigation events (75 mm standard flood irrigation) & 5 HP borewell pumping hours saved
    base_irr = (
        float(np.mean(baseline_result.irrigation_mm))
        if baseline_result is not None and baseline_result.irrigation_mm
        else (float(np.mean(sim_result.irrigation_mm)) if sim_result.irrigation_mm else 1350.0)
    )
    cand_irr = float(np.mean(sim_result.irrigation_mm)) if sim_result.irrigation_mm else base_irr
    water_saved_mm = max(0.0, base_irr - cand_irr)
    irrigations_saved = round(water_saved_mm / 75.0)
    # 1 mm/ha = 10 m3; standard 5 HP submersible pump delivers ~18 m3/hr -> 0.55 hr per mm/ha
    pumping_hours_saved = round(water_saved_mm * 0.55)

    # Relative water demand weights fallback if per-step irrigation wasn't persisted
    step_water_weights: list[float] = []
    for s in rotation.steps:
        if s.crop_id in crops and s.crop_id != "fallow":
            c_spec = crops[s.crop_id]
            w_mid = 0.5 * (c_spec.water_requirement_mm[0] + c_spec.water_requirement_mm[1])
            if s.crop_id == "rice_puddled":
                w_mid *= 1.25
            elif s.crop_id == "rice_dsr":
                w_mid *= 0.88
            elif s.crop_id == "rice_short":
                w_mid *= 0.92
            step_water_weights.append(max(20.0, w_mid))
        else:
            step_water_weights.append(0.0)
    total_w_weight = sum(step_water_weights) or 1.0
    total_sim_irr = cand_irr * rotation_years

    # 2. Biological N fixation + retained residue N savings -> 45-kg Urea bags saved (1 bag = 20.7 kg N)
    tot_n_saved_kg = 0.0
    tot_labor_inr = 0.0
    tot_cost_inr = 0.0
    proc_types: list[str] = []
    seasonal_ops: list[SeasonalOperationStep] = []
    if region_id == "cauvery":
        season_names = _SEASON_NAMES_I18N["cauvery"][lang]
    elif country_code != "IND" and slot_name_map:
        season_names = slot_name_map
    elif hemisphere == "SH":
        season_names = _SEASON_NAMES_I18N["south"][lang]
    else:
        season_names = _SEASON_NAMES_I18N["north"][lang]

    n_steps = len(rotation.steps)
    unit_n_cost = 14.0 if currency == "INR" else round(0.18 * (usd_rt if currency != "USD" else 1.0), 4)
    min_step_cost = 2000.0 if currency == "INR" else round(25.0 * (usd_rt if currency != "USD" else 1.0), 1)
    money_dec = 0 if currency in ("INR", "KES") else 2
    price_mult = max(0.25, 1.0 + price_shock_pct / 100.0)

    for idx, s in enumerate(rotation.steps):
        s_name = season_names.get(s.season_index, f"{_SEASON_FALLBACK_I18N[lang]} {s.season_index + 1}")
        step_key = f"{s.year_index}:{s.season_index}:{s.crop_id}"
        if s.crop_id in crops and s.crop_id != "fallow":
            c_spec = crops[s.crop_id]
            prev_cid = rotation.steps[idx - 1].crop_id if n_steps > 1 else None
            prev_crop_obj = crops.get(prev_cid) if prev_cid else None
            prec_leg = bool(prev_crop_obj is not None and prev_crop_obj.group in ("legume", "cover"))
            ret_res = any(p in ("residue_retained", "happy_seeder") for p in s.practices)
            if step_key in sim_result.step_yields:
                mean_y = float(sim_result.step_yields[step_key])
            else:
                mean_y = float(np.mean(sim_result.yield_t_ha.get(s.crop_id, [c_spec.typical_yield_t_ha[0]])))

            n_res = soil_health.n_balance(
                c_spec,
                yield_t_ha=mean_y,
                preceded_by_legume=prec_leg,
                residue_retained=ret_res,
                soil_n_credit_kg_ha=shc_n_credit,
                preceding_crop=prev_crop_obj,
            )
            step_n_saved = float(n_res["fertilizer_saved_kg_ha"] + 0.45 * c_spec.n_fixation_kg_ha)
            tot_n_saved_kg += step_n_saved

            econ_res = economics.profit_per_ha(
                s.crop_id,
                mean_y,
                practices=s.practices,
                region=econ_region,
                currency=currency,
                price_multiplier=price_mult,
                preceded_by_legume=prec_leg,
                irrigation=irr_mode,
            )
            step_labor = float(econ_res["labor_cost_per_ha"])
            step_cost = float(econ_res["cost_per_ha"])
            step_profit = float(econ_res["profit_per_ha"])
            if fertilizer_shock_pct != 0.0:
                synth_n_kg = max(
                    0.0,
                    c_spec.n_demand_kg_ha - c_spec.n_fixation_kg_ha - (25.0 if prec_leg else 0.0),
                )
                fert_delta = synth_n_kg * unit_n_cost * (fertilizer_shock_pct / 100.0)
                step_cost = max(min_step_cost, step_cost + fert_delta)
                step_profit -= fert_delta
            if shc_n_credit > 0.0:
                fert_reduction = shc_n_credit * unit_n_cost
                step_cost = max(min_step_cost, step_cost - fert_reduction)
                step_profit += fert_reduction

            tot_labor_inr += step_labor
            tot_cost_inr += step_cost
            c_proc = str(econ_crops.get(s.crop_id, {}).get("procurement_type", "nafed_pss"))
            proc_types.append(c_proc)

            if step_key in sim_result.step_irrigations_mm:
                step_irr_mm = round(float(sim_result.step_irrigations_mm[step_key]), 1)
            else:
                step_irr_mm = round(total_sim_irr * (step_water_weights[idx] / total_w_weight), 1)
            step_irr_cnt = max(0, round(step_irr_mm / 70.0)) if step_irr_mm > 20.0 else 0
            dur_d = int(rot_mod._step_duration_days(s.crop_id, crops))
            step_doy = s.sowing_doy if s.sowing_doy is not None else (
                slot_doy_map.get(s.season_index) if country_code != "IND" else None
            )
            sow_win, harv_win, guidance = _build_step_guidance(
                s.crop_id,
                s.season_index,
                s.practices,
                prec_leg,
                irr_mode,
                dur_d,
                sowing_doy=step_doy,
                lat=lat_val,
                language=lang,
                hemisphere=hemisphere,
            )
            seasonal_ops.append(
                SeasonalOperationStep(
                    year_index=s.year_index,
                    season_index=s.season_index,
                    season_name=s_name,
                    crop_id=s.crop_id,
                    crop_name=c_spec.name,
                    sowing_window=sow_win,
                    harvest_window=harv_win,
                    duration_days=dur_d,
                    practices=list(s.practices),
                    yield_t_ha=round(mean_y, 2),
                    irrigation_mm=step_irr_mm,
                    irrigations_count=step_irr_cnt,
                    currency=currency,
                    currency_symbol=currency_symbol,
                    input_cost_local_ha=round(step_cost, money_dec),
                    labor_cost_local_ha=round(step_labor, money_dec),
                    net_profit_local_ha=round(step_profit, money_dec),
                    input_cost_inr_ha=round(step_cost, 0),
                    labor_cost_inr_ha=round(step_labor, 0),
                    net_profit_inr_ha=round(step_profit, 0),
                    n_fixation_kg_ha=round(float(c_spec.n_fixation_kg_ha), 1),
                    urea_saved_kg_ha=round(step_n_saved / 0.46, 1),
                    agronomic_guidance=guidance,
                )
            )
        else:
            if s.season_index in slot_doy_map and country_code != "IND":
                f_doy = slot_doy_map[s.season_index]
                f_sow = _format_doy_window(f_doy, 0, 0).split(" – ")[0]
                f_harv = _format_doy_window((f_doy + 59) % 365 + 1, 0, 0).split(" – ")[0]
            else:
                f_sow, f_harv = ("Oct 15", "Dec 15") if hemisphere == "SH" else ("Apr 15", "Jun 15")
            seasonal_ops.append(
                SeasonalOperationStep(
                    year_index=s.year_index,
                    season_index=s.season_index,
                    season_name=s_name,
                    crop_id="fallow",
                    crop_name=_FALLOW_TEXT_I18N["crop_name"][lang],
                    sowing_window=f_sow,
                    harvest_window=f_harv,
                    duration_days=60,
                    practices=list(s.practices),
                    yield_t_ha=0.0,
                    irrigation_mm=0.0,
                    irrigations_count=0,
                    currency=currency,
                    currency_symbol=currency_symbol,
                    input_cost_local_ha=0.0,
                    labor_cost_local_ha=0.0,
                    net_profit_local_ha=0.0,
                    input_cost_inr_ha=0.0,
                    labor_cost_inr_ha=0.0,
                    net_profit_inr_ha=0.0,
                    n_fixation_kg_ha=0.0,
                    urea_saved_kg_ha=0.0,
                    agronomic_guidance=_FALLOW_TEXT_I18N["guidance"][lang],
                )
            )

    ann_n_saved_kg = tot_n_saved_kg / rotation_years
    urea_bags_saved = round(ann_n_saved_kg / 20.7, 1)  # 45 kg * 46% N = 20.7 kg N per bag

    # 3. MSP Assurance Level / Regional Benchmark / Global Proxy Disclaimer
    is_global_proxy = bool(
        val_status in ("biophysical_global", "unvalidated_global")
        or econ_basis in ("punjab_proxy", "uncalibrated_proxy")
    )
    if is_global_proxy:
        msp_level = _MSP_LEVELS_I18N["global_proxy"][lang]
    elif val_status == "validated_regional" or econ_basis == "regional_verified":
        msp_level = _MSP_LEVELS_I18N["regional_verified"][lang]
    else:
        main_proc_types = [
            str(econ_crops.get(s.crop_id, {}).get("procurement_type", "nafed_pss"))
            for s in rotation.steps
            if s.crop_id in crops and s.crop_id != "fallow" and s.season_index in (0, 1)
        ]
        if main_proc_types and all(p == "msp_assured" for p in main_proc_types) and not any(p == "mandi_linked" for p in proc_types):
            msp_level = _MSP_LEVELS_I18N["msp_assured"][lang]
        elif any(p == "mandi_linked" for p in proc_types):
            msp_level = _MSP_LEVELS_I18N["mandi_linked"][lang]
        elif any(p == "msp_assured" for p in main_proc_types):
            msp_level = _MSP_LEVELS_I18N["msp_assured"][lang]
        else:
            msp_level = _MSP_LEVELS_I18N["nafed_pss"][lang]

    # 4. Matching Regional & National Government Support Schemes (YAML-driven via scheme_kb)
    planted_ids = {s.crop_id for s in rotation.steps if s.crop_id != "fallow"}
    all_practices = {p for s in rotation.steps for p in s.practices}

    from .. import scheme_kb
    schemes = scheme_kb.get_matching_schemes(
        state=state_to_use if not is_global_proxy else None,
        planted_crops=planted_ids,
        practices=all_practices,
        urea_bags_saved=urea_bags_saved,
        region_id=region_id,
        country_code=country_code,
        validation_status=val_status,
        language=lang,
    )

    ann_labor = round(tot_labor_inr / rotation_years, money_dec)
    ann_input = round(tot_cost_inr / rotation_years, money_dec)
    return PracticalFarmerMetrics(
        turnaround_days_kharif_rabi=turnaround_days,
        turnaround_days=turnaround_days,
        urea_bags_saved_per_ha=urea_bags_saved,
        fertilizer_n_saved_kg_ha=round(ann_n_saved_kg, 1),
        irrigations_saved_per_yr=irrigations_saved,
        pumping_hours_saved_per_ha=pumping_hours_saved,
        water_saved_m3_per_ha=round(water_saved_mm * 10.0, 1),
        msp_assurance_level=msp_level,
        market_assurance_level=msp_level,
        eligible_schemes=schemes,
        currency=currency,
        currency_symbol=currency_symbol,
        labor_cost_inr_per_ha=ann_labor,
        input_cost_inr_per_ha=ann_input,
        area_ha=round(area_ha, 2),
        total_farm_profit_p50=round(sim_result.profit_p50 * area_ha, money_dec),
        total_farm_input_cost=round(ann_input * area_ha, money_dec),
        total_farm_urea_bags_saved=round(urea_bags_saved * area_ha, 1),
        total_farm_pumping_hours_saved=round(pumping_hours_saved * area_ha),
        seasonal_operations=seasonal_ops,
    )


def prescreen_rotations_with_surrogate(
    rotations: list[Rotation],
    profile: FieldProfile,
    crops: dict[str, CropSpec] | None = None,
    max_candidates: int = 85,
    rank_scores: dict[str, float] | None = None,
) -> list[Rotation]:
    """TASK-O05: Fast polynomial Ridge surrogate pre-screener for large rotation pools."""
    if len(rotations) <= max_candidates:
        return rotations
    crops = crops or crop_kb.load_crops()
    reg_cfg = region_registry.detect_region_config(profile.field.lat, profile.field.lon)
    crops = {cid: crop_kb.resolve_crop_spec(spec, reg_cfg.cultivar_zone) for cid, spec in crops.items()}
    econ_reg = reg_cfg.economics_table or (reg_cfg.state.lower().replace(" ", "_") if reg_cfg.state else reg_cfg.region_id)
    econ_data = economics.load_economics(econ_reg)
    econ_crops = econ_data.get("crops", {})
    punjab_crops = economics.load_economics("punjab").get("crops", {})
    currency = getattr(profile, "currency", None) or reg_cfg.currency or "INR"
    usd_rt = float(econ_data.get("usd_exchange_rate", 83.5))
    local_per_inr = 1.0 if currency == "INR" else (usd_rt / 83.5)
    norm_val = max(100.0, 100000.0 * local_per_inr)

    # Site-specific soil, water, and climate boundary conditions for biophysical interaction terms
    soil_obj = profile.soil
    water_obj = profile.water
    clim_obj = profile.climate
    haz_obj = profile.hazards
    soc_g_kg = float(soil_obj.soc_g_per_kg) if (soil_obj and soil_obj.soc_g_per_kg is not None) else 6.0
    clay_pct = float(soil_obj.clay_pct) if (soil_obj and soil_obj.clay_pct is not None) else 22.0
    ph_val = float(soil_obj.ph) if (soil_obj and soil_obj.ph is not None) else 7.2
    annual_p = float(clim_obj.annual_precip_mm) if clim_obj else 750.0
    annual_et0 = float(clim_obj.annual_et0_mm) if (clim_obj and clim_obj.annual_et0_mm is not None) else 1500.0
    gw_trend = (
        float(water_obj.groundwater_trend_cm_per_year)
        if (water_obj and water_obj.groundwater_trend_cm_per_year is not None)
        else -0.5
    )
    drought_freq = float(haz_obj.drought_frequency) if (haz_obj and haz_obj.drought_frequency is not None) else 0.15
    aquifer_depl = max(0.0, -gw_trend)
    low_soc_factor = max(0.0, 12.0 - soc_g_kg)
    aridity_idx = annual_et0 / max(annual_p, 250.0)

    from .. import suitability

    crop_ph_ranges = {cid: suitability._crop_ph_range(spec) for cid, spec in crops.items()}
    features: list[list[float]] = []
    targets: list[float] = []
    for rot in rotations:
        yrs = max(1, max(s.year_index for s in rot.steps) + 1)
        water_req = 0.0
        n_fix = 0.0
        dur_tot = 0.0
        val_est = 0.0
        active_cids = [s.crop_id for s in rot.steps if s.crop_id in crops and s.crop_id != "fallow"]
        for cid in active_cids:
            c = crops[cid]
            water_req += 0.5 * (c.water_requirement_mm[0] + c.water_requirement_mm[1])
            n_fix += c.n_fixation_kg_ha
            dur_tot += 0.5 * (c.duration_days[0] + c.duration_days[1])
            if cid in econ_crops:
                ce = econ_crops[cid]
                price_t = float(ce.get("price_per_tonne", 300.0 if currency != "INR" else 25000.0))
                cost_ha = float(ce.get("cost_per_ha", 400.0 if currency != "INR" else 32000.0))
            else:
                ce = punjab_crops.get(cid) or {}
                price_t = float(ce.get("price_per_tonne", 25000.0)) * local_per_inr
                cost_ha = float(ce.get("cost_per_ha", 32000.0)) * local_per_inr
            typ_y = 0.5 * (c.typical_yield_t_ha[0] + c.typical_yield_t_ha[1])
            val_est += (typ_y * price_t) - cost_ha
        mean_suit = (
            float(np.mean([rank_scores.get(cid, 0.3) for cid in active_cids]))
            if (rank_scores and active_cids)
            else 0.6
        )
        has_leg = 0.25 if any(crops[cid].n_fixation_kg_ha > 0 for cid in active_cids) else 0.0
        has_cereal_fiber = 0.20 if any(crops[cid].group in ("cereal", "fiber", "fibre") for cid in active_cids) else 0.0
        fams = len({crops[cid].family for cid in active_cids})

        water_req_yr = water_req / yrs
        n_fix_yr = n_fix / yrs
        dur_yr = dur_tot / yrs
        val_yr = val_est / yrs
        water_deficit_ratio = max(0.0, (water_req_yr - annual_p) / max(annual_p, 250.0))
        residue_steps = sum(
            1
            for s in rot.steps
            if any(p in ("happy_seeder", "residue_retained", "zero_till", "no_till") for p in s.practices)
        )
        residue_ratio = residue_steps / max(1, len(rot.steps))
        ph_mismatch = sum(
            1.0
            for cid in active_cids
            if ph_val < crop_ph_ranges[cid][0] or ph_val > crop_ph_ranges[cid][1]
        )

        x_vec = [
            water_req_yr,
            n_fix_yr,
            dur_yr,
            mean_suit * 100.0,
            float(fams),
            val_yr,
            water_deficit_ratio * 100.0,
            water_req_yr * aquifer_depl / 100.0,
            n_fix_yr * low_soc_factor,
            residue_ratio * aridity_idx,
        ]
        # Multi-pillar + site interaction composite: suitability + legume BNF + cereal anchor + diversity + margin + soil/climate interactions
        aquifer_stress_pen = 0.08 * water_deficit_ratio * (1.0 + 0.35 * aquifer_depl + 0.50 * drought_freq)
        low_soc_leg_bonus = 0.07 * (n_fix_yr / 60.0) * max(0.4, (10.0 - soc_g_kg) / 5.0)
        mulch_climate_bonus = 0.05 * residue_ratio * min(
            2.5, max(0.5, 0.4 * aridity_idx + (0.3 if clay_pct >= 25.0 or soc_g_kg < 8.0 else 0.0))
        )
        ph_pen = 0.08 * ph_mismatch
        score_proxy = (
            mean_suit
            + has_leg
            + has_cereal_fiber
            + 0.10 * fams
            + val_yr / norm_val
            - aquifer_stress_pen
            + low_soc_leg_bonus
            + mulch_climate_bonus
            - ph_pen
        )
        features.append(x_vec)
        targets.append(score_proxy)
    X_arr = np.asarray(features, dtype=float)
    y_arr = np.asarray(targets, dtype=float)
    model = surrogate.train_crop_surrogate(X_arr, y_arr, degree=2, alpha=0.5)
    preds = 0.5 * np.asarray(model.predict(X_arr), dtype=float).ravel() + 0.5 * y_arr

    # Stratified primary pair diversity: group candidates by (Kharif, Rabi) pair
    pair_to_cands: dict[tuple[str, str], list[tuple[float, int]]] = {}
    for i, r in enumerate(rotations):
        pair = (r.steps[0].crop_id if len(r.steps) > 0 else "", r.steps[1].crop_id if len(r.steps) > 1 else "")
        pair_to_cands.setdefault(pair, []).append((preds[i], i))

    selected_indices: set[int] = set()
    for r_i, r in enumerate(rotations):
        if r.is_baseline:
            selected_indices.add(r_i)

    # Include up to 2 candidates from each distinct primary pair (ordered by site-adapted score)
    sorted_groups = []
    for c_list in pair_to_cands.values():
        c_list.sort(key=lambda x: -x[0])
        sorted_groups.append(c_list)
    sorted_groups.sort(key=lambda c_list: -c_list[0][0])

    for rank_pos in range(2):
        for c_list in sorted_groups:
            if len(selected_indices) >= max_candidates:
                break
            if rank_pos < len(c_list):
                selected_indices.add(c_list[rank_pos][1])

    # Fill remaining capacity with top surrogate predictions
    order = np.argsort(-preds)
    for i in order:
        if len(selected_indices) >= max_candidates:
            break
        selected_indices.add(int(i))

    return [rotations[i] for i in sorted(selected_indices)]


def compute_resilience_and_regret(
    hist_result: SimulationResult,
    stress_result: SimulationResult | None = None,
) -> dict[str, float]:
    """TASK-O06: Compute climate resilience score (0-100) and regret metrics."""
    p_hist = hist_result.profit_p50
    irr_hist = float(np.mean(hist_result.irrigation_mm)) if hist_result.irrigation_mm else 1200.0

    if stress_result is not None:
        p_stress = stress_result.profit_p50
        irr_stress = float(np.mean(stress_result.irrigation_mm)) if stress_result.irrigation_mm else irr_hist
        profit_regret = max(0.0, p_hist - p_stress)
        irrigation_spike = max(0.0, irr_stress - irr_hist)
    else:
        profit_regret = max(0.0, p_hist - hist_result.cvar_profit_10)
        if hist_result.irrigation_mm and len(hist_result.irrigation_mm) > 1:
            irr_p90 = float(np.percentile(hist_result.irrigation_mm, 90))
            irrigation_spike = max(0.0, irr_p90 - irr_hist)
        else:
            irrigation_spike = 0.15 * irr_hist

    profit_penalty = 40.0 * min(1.0, profit_regret / max(100.0, abs(p_hist)))
    irrigation_penalty = 30.0 * min(1.0, irrigation_spike / max(150.0, irr_hist))
    soil_bonus = 30.0 * (hist_result.soil_health_score / 100.0)

    score = 100.0 - profit_penalty - irrigation_penalty + (soil_bonus - 15.0)
    resilience_score = float(np.clip(score, 10.0, 98.0))

    return {
        "climate_resilience_score": round(resilience_score, 1),
        "profit_regret": round(profit_regret, 1),
        "irrigation_spike_mm": round(irrigation_spike, 1),
    }
