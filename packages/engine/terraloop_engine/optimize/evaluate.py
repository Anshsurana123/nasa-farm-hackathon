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

import numpy as np
import pandas as pd
from terraloop_schemas import (
    CropSpec,
    FarmConstraints,
    FieldProfile,
    PracticalFarmerMetrics,
    Rotation,
    SeasonalOperationStep,
    SimulationResult,
)

from terraloop_engine import crop_kb
from terraloop_engine.models import economics, fao56_runner, rusle, soil_health, surrogate

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


def evaluate_rotation(
    rotation: Rotation,
    members: dict[str, pd.DataFrame],
    profile: FieldProfile,
    constraints: FarmConstraints,
    scenario_set_id: str = "historical",
    price_shock_pct: float = 0.0,
    fertilizer_shock_pct: float = 0.0,
) -> SimulationResult:
    """Evaluate a single rotation across all climate ensemble members."""
    crops = crop_kb.load_crops()
    soil = profile.soil
    econ_table = economics.load_economics("punjab").get("crops", {})

    member_profits: list[float] = []
    member_irrigations: list[float] = []
    crop_yields: dict[str, list[float]] = {
        s.crop_id: [] for s in rotation.steps if s.crop_id != "fallow"
    }

    rotation_years = max(1, max(s.year_index for s in rotation.steps) + 1)

    for member_idx, (member_id, weather_df) in enumerate(members.items()):
        start_year = 2015
        if "hist_" in member_id:
            try:
                start_year = int(member_id.split("_")[1])
            except (IndexError, ValueError):
                start_year = 2015

        step_sims = aquacrop_runner.simulate_rotation(
            rotation=rotation,
            weather=weather_df,
            soil=soil,
            constraints=constraints,
            start_year=start_year,
            lat=profile.field.lat,
        )

        tot_irr = 0.0
        tot_profit = 0.0

        for step_i, sim_step in enumerate(step_sims):
            cid = sim_step["crop_id"]
            y_val = sim_step["yield_t_ha"]
            tot_irr += sim_step["irrigation_mm"]

            if cid != "fallow":
                crop_yields[cid].append(y_val)
                prev_cid = step_sims[step_i - 1]["crop_id"] if step_i > 0 else step_sims[-1]["crop_id"]
                prec_leg = prev_cid in crops and crops[prev_cid].group in ("legume", "cover")
                practices = sim_step.get("practices", [])

                # Deterministic mandi price realization draw per weather year, procurement_type & market_risk
                c_econ = econ_table.get(cid, {})
                m_risk = float(c_econ.get("market_risk", 0.12))
                proc_type = str(c_econ.get("procurement_type", "nafed_pss"))
                seed = zlib.crc32(f"{member_id}_{cid}_{member_idx}".encode())
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
                    region="punjab",
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
                    unit_n_cost = 14.0 if (profile.currency or "INR") == "INR" else 0.18
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

    # Soil Carbon (RothC-lite 10-year simulation)
    # Account for both aboveground straw C (depending on burning/retention/fodder removal) and belowground root C
    ann_residue_c = 0.0
    rot_has_burning = any(soil_health.is_burning_practice(s.practices) for s in rotation.steps)
    for s in rotation.steps:
        if s.crop_id in crops and s.crop_id != "fallow":
            c_spec = crops[s.crop_id]
            res_t = c_spec.residue_t_ha
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

    m_temp = [
        (tmax + tmin) / 2.0
        for tmax, tmin in zip(profile.climate.monthly_tmax_c, profile.climate.monthly_tmin_c, strict=False)
    ]
    m_precip = profile.climate.monthly_precip_mm
    m_et0 = [(profile.climate.annual_et0_mm or 1550.0) / 12.0] * 12

    rothc_res = soil_health.rothc_lite(
        soil=soil,
        clay_pct=soil.clay_pct or 22.0,
        monthly_temp_c=m_temp,
        monthly_precip_mm=m_precip,
        monthly_et0_mm=m_et0,
        annual_c_input_t_ha=ann_residue_c,
        years=10,
    )
    soc_delta = float(rothc_res["soc_delta_10yr"])

    # RUSLE erosion calculation with rotation C factor
    rot_c_factor = compute_rotation_c_factor(rotation, crops)
    r_fact = rusle.r_factor_annual(profile.climate.annual_precip_mm)
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

    # Nitrogen Balance
    n_surpluses = []
    for idx, s in enumerate(rotation.steps):
        if s.crop_id in crops and s.crop_id != "fallow":
            c_spec = crops[s.crop_id]
            prev_step = rotation.steps[idx - 1]
            prec_leg = prev_step.crop_id in crops and crops[prev_step.crop_id].group in ("legume", "cover")
            ret_res = any(p in ("residue_retained", "happy_seeder") for p in s.practices)
            mean_y = float(np.mean(crop_yields.get(s.crop_id, [2.0])))
            n_res = soil_health.n_balance(
                c_spec, yield_t_ha=mean_y, preceded_by_legume=prec_leg, residue_retained=ret_res
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
    )
    sh_score = float(sh_breakdown["total_score"])

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
    )


def evaluate_candidates(
    rotations: list[Rotation],
    members: dict[str, pd.DataFrame],
    profile: FieldProfile,
    constraints: FarmConstraints,
    scenario_set_id: str = "historical",
    price_shock_pct: float = 0.0,
    fertilizer_shock_pct: float = 0.0,
) -> list[SimulationResult]:
    """Evaluate a list of candidate rotations across climate members."""
    return [
        evaluate_rotation(
            rotation=r,
            members=members,
            profile=profile,
            constraints=constraints,
            scenario_set_id=scenario_set_id,
            price_shock_pct=price_shock_pct,
            fertilizer_shock_pct=fertilizer_shock_pct,
        )
        for r in rotations
    ]


def _build_step_guidance(
    crop_id: str,
    season_index: int,
    practices: list[str],
    prec_leg: bool,
    irrigation_mode: str,
    dur_days: int,
) -> tuple[str, str, str]:
    """Return (sowing_window, harvest_window, agronomic_guidance) for a rotation step."""
    windows = {
        0: ("Jun 15 – Jul 05", "Oct 05 – Oct 25"),
        1: ("Nov 01 – Nov 20", "Apr 01 – Apr 18"),
        2: ("Apr 10 – Apr 22", "Jun 08 – Jun 20"),
    }
    sow_win, harv_win = windows.get(season_index, ("Jun 15", "Oct 15"))
    if crop_id == "rice_short":
        sow_win, harv_win = "Jun 20 – Jun 28", "Oct 01 – Oct 08"
    elif crop_id == "rice_dsr":
        sow_win, harv_win = "Jun 05 – Jun 18", "Oct 05 – Oct 15"
    elif crop_id == "rice_puddled":
        sow_win, harv_win = "Jun 15 – Jun 25", "Oct 22 – Nov 05"
    elif crop_id in ("mustard", "chickpea", "lentil"):
        sow_win, harv_win = "Oct 18 – Nov 10", "Mar 15 – Mar 30"

    notes: list[str] = []
    if crop_id == "rice_dsr":
        notes.append("Drill-seed at 20 kg/ha after 75 mm pre-sowing rauni irrigation; apply AWD wetting/drying")
    elif crop_id == "rice_short":
        notes.append("Transplant 25-day PR-126 seedlings; stop irrigation 14 days before harvest for early Oct clearance")
    elif crop_id == "rice_puddled":
        notes.append("Conventional puddled transplanted paddy (high percolation & narrow Rabi turnaround)")
    elif "happy_seeder" in practices:
        notes.append("Direct-drill with PAU Happy Seeder / Super SMS into standing rice mulch without burning")
    elif any(p in ("zero_till", "no_till") for p in practices):
        notes.append("Zero-till seed-cum-fertilizer drill into anchored crop residue")
    elif "residue_retained" in practices:
        notes.append("Retain surface crop residue as organic soil armor to conserve root-zone moisture")

    if prec_leg:
        notes.append("Reduce basal Urea dose by 25 kg N/ha (~55 kg Urea/ha) using preceding legume BNF credit")
    if irrigation_mode == "none":
        notes.append("Rainfed conservation profile (ridge-furrow / compartment bunding)")
    elif irrigation_mode == "limited":
        notes.append("Deficit irrigation only at critical flowering and grain-filling stages")

    if not notes:
        notes.append(f"Standard regional package of practices ({dur_days}d field cycle)")
    return sow_win, harv_win, "; ".join(notes) + "."


def compute_practical_farmer_metrics(
    rotation: Rotation,
    sim_result: SimulationResult,
    baseline_result: SimulationResult | None = None,
    crops: dict[str, CropSpec] | None = None,
    constraints: FarmConstraints | None = None,
) -> PracticalFarmerMetrics:
    """Translate biophysical simulation outputs into practical Indian farmer decision metrics."""
    if crops is None:
        crops = crop_kb.load_crops()
    econ_crops = economics.load_economics("punjab").get("crops", {})
    irr_mode = constraints.irrigation if constraints is not None else "full"

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

    # Estimate relative water demand weights across steps so seasonal irrigation sums to total simulated irrigation
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
    season_names = {0: "Kharif (Monsoon)", 1: "Rabi (Winter)", 2: "Zaid (Summer)"}

    for idx, s in enumerate(rotation.steps):
        s_name = season_names.get(s.season_index, f"Season {s.season_index + 1}")
        if s.crop_id in crops and s.crop_id != "fallow":
            c_spec = crops[s.crop_id]
            prev_cid = rotation.steps[idx - 1].crop_id
            prec_leg = prev_cid in crops and crops[prev_cid].group in ("legume", "cover")
            ret_res = any(p in ("residue_retained", "happy_seeder") for p in s.practices)
            mean_y = float(np.mean(sim_result.yield_t_ha.get(s.crop_id, [c_spec.typical_yield_t_ha[0]])))

            n_res = soil_health.n_balance(
                c_spec, yield_t_ha=mean_y, preceded_by_legume=prec_leg, residue_retained=ret_res
            )
            step_n_saved = float(n_res["fertilizer_saved_kg_ha"] + 0.45 * c_spec.n_fixation_kg_ha)
            tot_n_saved_kg += step_n_saved

            econ_res = economics.profit_per_ha(
                s.crop_id,
                mean_y,
                practices=s.practices,
                preceded_by_legume=prec_leg,
                irrigation=irr_mode,
            )
            step_labor = float(econ_res["labor_cost_per_ha"])
            step_cost = float(econ_res["cost_per_ha"])
            step_profit = float(econ_res["profit_per_ha"])
            tot_labor_inr += step_labor
            tot_cost_inr += step_cost
            c_proc = str(econ_crops.get(s.crop_id, {}).get("procurement_type", "nafed_pss"))
            proc_types.append(c_proc)

            step_irr_mm = round(total_sim_irr * (step_water_weights[idx] / total_w_weight), 1)
            step_irr_cnt = max(0, round(step_irr_mm / 70.0)) if step_irr_mm > 20.0 else 0
            dur_d = int(rot_mod._step_duration_days(s.crop_id, crops))
            sow_win, harv_win, guidance = _build_step_guidance(
                s.crop_id, s.season_index, s.practices, prec_leg, irr_mode, dur_d
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
                    input_cost_inr_ha=round(step_cost, 0),
                    labor_cost_inr_ha=round(step_labor, 0),
                    net_profit_inr_ha=round(step_profit, 0),
                    n_fixation_kg_ha=round(float(c_spec.n_fixation_kg_ha), 1),
                    urea_saved_kg_ha=round(step_n_saved / 0.46, 1),
                    agronomic_guidance=guidance,
                )
            )
        else:
            seasonal_ops.append(
                SeasonalOperationStep(
                    year_index=s.year_index,
                    season_index=s.season_index,
                    season_name=s_name,
                    crop_id="fallow",
                    crop_name="Summer Fallow / Residue Mulch",
                    sowing_window="Apr 15",
                    harvest_window="Jun 15",
                    duration_days=60,
                    practices=list(s.practices),
                    yield_t_ha=0.0,
                    irrigation_mm=0.0,
                    irrigations_count=0,
                    input_cost_inr_ha=0.0,
                    labor_cost_inr_ha=0.0,
                    net_profit_inr_ha=0.0,
                    n_fixation_kg_ha=0.0,
                    urea_saved_kg_ha=0.0,
                    agronomic_guidance="Retain anchored wheat stubble mulch on soil surface; avoid summer deep ploughing.",
                )
            )

    ann_n_saved_kg = tot_n_saved_kg / rotation_years
    urea_bags_saved = round(ann_n_saved_kg / 20.7, 1)  # 45 kg * 46% N = 20.7 kg N per bag

    # 3. MSP Assurance Level
    main_proc_types = [
        str(econ_crops.get(s.crop_id, {}).get("procurement_type", "nafed_pss"))
        for s in rotation.steps
        if s.crop_id in crops and s.crop_id != "fallow" and s.season_index in (0, 1)
    ]
    if main_proc_types and all(p == "msp_assured" for p in main_proc_types) and not any(p == "mandi_linked" for p in proc_types):
        msp_level = "MSP Assured (FCI / State)"
    elif any(p == "mandi_linked" for p in proc_types):
        msp_level = "Mandi Market-Linked"
    elif any(p == "msp_assured" for p in main_proc_types):
        msp_level = "MSP Assured (FCI / State)"
    else:
        msp_level = "NAFED / PSS Supported"

    # 4. Matching Indian Government Schemes
    schemes: list[str] = []
    planted_ids = {s.crop_id for s in rotation.steps if s.crop_id != "fallow"}
    all_practices = {p for s in rotation.steps for p in s.practices}

    if "rice_puddled" not in planted_ids and any(
        c in planted_ids for c in ("maize", "moong", "urad", "pigeon_pea", "soybean", "groundnut", "pearl_millet", "cotton")
    ):
        schemes.append("Crop Diversification / Mera Pani Meri Virasat (₹17,500/ha state incentive)")
    if "rice_dsr" in planted_ids or "direct_seeded" in all_practices:
        schemes.append("Direct-Seeded Rice (DSR) Promotion Scheme (₹3,750/ha support)")
    if any(p in all_practices for p in ("happy_seeder", "zero_till", "residue_retained")) and not any(
        soil_health.is_burning_practice(s.practices) for s in rotation.steps
    ):
        schemes.append("CRM Sub-Mission on Crop Residue Management (50–80% Happy Seeder / CHC subsidy)")
    if any(c in planted_ids for c in ("moong", "urad", "chickpea", "lentil", "pigeon_pea")):
        schemes.append("NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement")
    if any(c in planted_ids for c in ("mustard", "groundnut", "sunflower", "soybean")):
        schemes.append("National Mission on Edible Oils (NMEO-Oilseeds) Seed & Procurement Support")

    return PracticalFarmerMetrics(
        turnaround_days_kharif_rabi=turnaround_days,
        urea_bags_saved_per_ha=urea_bags_saved,
        irrigations_saved_per_yr=irrigations_saved,
        pumping_hours_saved_per_ha=pumping_hours_saved,
        msp_assurance_level=msp_level,
        eligible_schemes=schemes,
        labor_cost_inr_per_ha=round(tot_labor_inr / rotation_years, 0),
        input_cost_inr_per_ha=round(tot_cost_inr / rotation_years, 0),
        seasonal_operations=seasonal_ops,
    )


def prescreen_rotations_with_surrogate(
    rotations: list[Rotation],
    profile: FieldProfile,
    crops: dict[str, CropSpec] | None = None,
    max_candidates: int = 32,
) -> list[Rotation]:
    """TASK-O05: Fast polynomial Ridge surrogate pre-screener for large rotation pools."""
    if len(rotations) <= max_candidates:
        return rotations
    crops = crops or crop_kb.load_crops()
    features = []
    targets = []
    for rot in rotations:
        yrs = max(1, max(s.year_index for s in rot.steps) + 1)
        water_req = 0.0
        n_fix = 0.0
        dur_tot = 0.0
        for s in rot.steps:
            if s.crop_id in crops and s.crop_id != "fallow":
                c = crops[s.crop_id]
                water_req += 0.5 * (c.water_requirement_mm[0] + c.water_requirement_mm[1])
                n_fix += c.n_fixation_kg_ha
                dur_tot += 0.5 * (c.duration_days[0] + c.duration_days[1])
        x_vec = [water_req / yrs, n_fix / yrs, dur_tot / yrs, float(profile.soil.clay_pct or 22.0)]
        score_proxy = (n_fix / yrs) * 1.5 - (water_req / yrs) * 0.08 + (dur_tot / yrs) * 0.2
        features.append(x_vec)
        targets.append(score_proxy)
    X_arr = np.asarray(features, dtype=float)
    y_arr = np.asarray(targets, dtype=float)
    model = surrogate.train_crop_surrogate(X_arr, y_arr, degree=2, alpha=0.5)
    preds = np.asarray(model.predict(X_arr), dtype=float).ravel()
    ranked_idx = np.argsort(-preds)
    selected: list[Rotation] = []
    for idx in ranked_idx:
        if rotations[int(idx)].is_baseline or len(selected) < max_candidates:
            selected.append(rotations[int(idx)])
    return selected


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
        irrigation_spike = 0.15 * irr_hist

    profit_penalty = 40.0 * min(1.0, profit_regret / max(100.0, abs(p_hist)))
    irrigation_penalty = 30.0 * min(1.0, irrigation_spike / max(100.0, irr_hist))
    soil_bonus = 30.0 * (hist_result.soil_health_score / 100.0)

    score = 100.0 - profit_penalty - irrigation_penalty + (soil_bonus - 15.0)
    resilience_score = float(np.clip(score, 10.0, 98.0))

    return {
        "climate_resilience_score": round(resilience_score, 1),
        "profit_regret": round(profit_regret, 1),
        "irrigation_spike_mm": round(irrigation_spike, 1),
    }
