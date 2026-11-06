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
    SimulationResult,
)

from terraloop_engine import crop_kb
from terraloop_engine.models import economics, fao56_runner, rusle, soil_health

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
                tot_profit += float(econ_res["profit_per_ha"])

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
) -> list[SimulationResult]:
    """Evaluate a list of candidate rotations across climate members."""
    return [
        evaluate_rotation(
            rotation=r,
            members=members,
            profile=profile,
            constraints=constraints,
            scenario_set_id=scenario_set_id,
        )
        for r in rotations
    ]


def compute_practical_farmer_metrics(
    rotation: Rotation,
    sim_result: SimulationResult,
    baseline_result: SimulationResult | None = None,
    crops: dict[str, CropSpec] | None = None,
) -> PracticalFarmerMetrics:
    """Translate biophysical simulation outputs into practical Indian farmer decision metrics."""
    if crops is None:
        crops = crop_kb.load_crops()
    econ_crops = economics.load_economics("punjab").get("crops", {})

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

    # 2. Biological N fixation + retained residue N savings -> 45-kg Urea bags saved (1 bag = 20.7 kg N)
    tot_n_saved_kg = 0.0
    tot_labor_inr = 0.0
    tot_cost_inr = 0.0
    proc_types: list[str] = []

    for idx, s in enumerate(rotation.steps):
        if s.crop_id in crops and s.crop_id != "fallow":
            c_spec = crops[s.crop_id]
            prev_cid = rotation.steps[idx - 1].crop_id
            prec_leg = prev_cid in crops and crops[prev_cid].group in ("legume", "cover")
            ret_res = any(p in ("residue_retained", "happy_seeder") for p in s.practices)
            mean_y = float(np.mean(sim_result.yield_t_ha.get(s.crop_id, [c_spec.typical_yield_t_ha[0]])))

            n_res = soil_health.n_balance(
                c_spec, yield_t_ha=mean_y, preceded_by_legume=prec_leg, residue_retained=ret_res
            )
            # Credit both direct fertilizer reduction and 50% of legume symbiotic N fixation
            tot_n_saved_kg += n_res["fertilizer_saved_kg_ha"] + 0.45 * c_spec.n_fixation_kg_ha

            econ_res = economics.profit_per_ha(
                s.crop_id, mean_y, practices=s.practices, preceded_by_legume=prec_leg
            )
            tot_labor_inr += float(econ_res["labor_cost_per_ha"])
            tot_cost_inr += float(econ_res["cost_per_ha"])
            c_proc = str(econ_crops.get(s.crop_id, {}).get("procurement_type", "nafed_pss"))
            proc_types.append(c_proc)

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
    )


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
