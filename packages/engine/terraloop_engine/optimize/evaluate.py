"""Multi-scenario rotation evaluation pipeline. (TASK-O02)

Evaluates Rotation candidates across climate ensemble members to compute:
  - Yields per crop across members
  - Irrigation demand distribution (P10/P50/P90)
  - Operating profit distribution & CVaR-10 downside risk
  - 10-year SOC accretion/depletion (RothC-lite)
  - Annual RUSLE soil loss with rotation-specific cover factor C
  - Annual nitrogen balance and fertiliser savings
  - Soil Health Score (0-100) based on 5 USDA-NRCS principles
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from terraloop_schemas import FarmConstraints, FieldProfile, Rotation, SimulationResult

from terraloop_engine import crop_kb
from terraloop_engine.models import aquacrop_runner, economics, rusle, soil_health


def compute_rotation_c_factor(rotation: Rotation, crops: dict) -> float:
    """Compute rotation-level RUSLE C factor based on canopy cover and practices."""
    step_c_factors = []
    for step in rotation.steps:
        if step.crop_id == "fallow":
            # Bare soil fallow
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

            if "no_till" in step.practices or "zero_till" in step.practices:
                c_val *= 0.5
            elif "residue_retained" in step.practices:
                c_val *= 0.7
            elif "burning" in step.practices:
                c_val *= 1.4

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

    # Track member outputs
    member_profits: list[float] = []
    member_irrigations: list[float] = []
    crop_yields: dict[str, list[float]] = {
        s.crop_id: [] for s in rotation.steps if s.crop_id != "fallow"
    }

    # Rotation length in years
    rotation_years = max(1, max(s.year_index for s in rotation.steps) + 1)

    for member_id, weather_df in members.items():
        # Determine starting year from member if available, else 2015
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

        for sim_step in step_sims:
            cid = sim_step["crop_id"]
            y_val = sim_step["yield_t_ha"]
            tot_irr += sim_step["irrigation_mm"]

            if cid != "fallow":
                crop_yields[cid].append(y_val)
                econ_region = economics.detect_region(profile.field.lat, profile.field.lon)
                target_currency = "INR" if econ_region == "punjab" else "USD"
                practices = sim_step.get("practices", [])
                econ_res = economics.profit_per_ha(
                    cid, y_val, practices=practices, region=econ_region, currency=target_currency
                )
                tot_profit += econ_res["profit_per_ha"]

        # Annualize per-year values
        ann_irr = tot_irr / rotation_years
        ann_profit = tot_profit / rotation_years

        member_irrigations.append(round(ann_irr, 1))
        member_profits.append(round(ann_profit, 1))

    # Calculate risk statistics
    p_arr = np.array(member_profits) if member_profits else np.array([500.0])
    p10 = float(np.percentile(p_arr, 10))
    p50 = float(np.percentile(p_arr, 50))
    p90 = float(np.percentile(p_arr, 90))
    worst_10 = p_arr[p_arr <= p10]
    cvar10 = float(np.mean(worst_10)) if len(worst_10) > 0 else p10

    # Soil Carbon (RothC-lite 10-year simulation)
    # Estimate annual residue input from rotation
    ann_residue_c = 0.0
    for s in rotation.steps:
        if s.crop_id in crops and s.crop_id != "fallow":
            c_spec = crops[s.crop_id]
            res_t = c_spec.residue_t_ha
            c_frac = 0.45
            if "burning" in s.practices:
                # 90% lost to atmosphere
                ann_residue_c += res_t * c_frac * 0.10
            else:
                ann_residue_c += res_t * c_frac
    ann_residue_c = max(0.2, ann_residue_c / rotation_years)

    # Monthly temperature, precip, ET0 from climate summary
    m_temp = [
        (tmax + tmin) / 2.0
        for tmax, tmin in zip(profile.climate.monthly_tmax_c, profile.climate.monthly_tmin_c, strict=False)
    ]
    m_precip = profile.climate.monthly_precip_mm
    # Hargreaves ET0 monthly
    m_et0 = [profile.climate.annual_et0_mm / 12.0] * 12

    rothc_res = soil_health.rothc_lite(
        soil=soil,
        clay_pct=soil.clay_pct or 20.0,
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
    soc_pct = (soil.soc_g_per_kg or 8.0) / 10.0
    k_fact = rusle.k_factor_williams(
        sand_pct=soil.sand_pct or 40.0,
        silt_pct=soil.silt_pct or 40.0,
        clay_pct=soil.clay_pct or 20.0,
        soc_pct=soc_pct,
    )
    ls_fact = rusle.ls_factor(slope_pct=soil.slope_pct or 1.0)
    p_fact = 1.0  # Conservation practice factor
    ann_erosion = float(round(rusle.soil_loss(r_fact, k_fact, ls_fact, rot_c_factor, p_fact), 2))

    # Nitrogen Balance
    n_surpluses = []
    for idx, s in enumerate(rotation.steps):
        if s.crop_id in crops and s.crop_id != "fallow":
            c_spec = crops[s.crop_id]
            # Check if preceded by legume
            prev_step = rotation.steps[idx - 1]
            prec_leg = prev_step.crop_id in crops and crops[prev_step.crop_id].group == "legume"
            mean_y = float(np.mean(crop_yields.get(s.crop_id, [2.0])))
            n_res = soil_health.n_balance(c_spec, yield_t_ha=mean_y, preceded_by_legume=prec_leg)
            n_surpluses.append(n_res["n_surplus_deficit_kg_ha"])
    ann_n_balance = float(round(sum(n_surpluses) / rotation_years, 1)) if n_surpluses else 0.0

    # Living root days percentage
    tot_living_days = 0.0
    for s in rotation.steps:
        if s.crop_id in crops and s.crop_id != "fallow":
            dur = (crops[s.crop_id].duration_days[0] + crops[s.crop_id].duration_days[1]) / 2.0
            tot_living_days += dur
    living_roots_pct = float(round(min(100.0, (tot_living_days / (rotation_years * 365.0)) * 100.0), 1))

    # Botanical family Shannon diversity
    fam_div = float(soil_health.family_shannon_index(rotation, crops))

    # Soil Health Score (0-100)
    sh_score = float(
        soil_health.soil_health_score(
            rotation=rotation,
            crops=crops,
            soc_delta_10yr=soc_delta,
            erosion_t_ha_yr=ann_erosion,
            has_livestock=constraints.has_livestock,
        )
    )

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
    results: list[SimulationResult] = []
    for r in rotations:
        res = evaluate_rotation(
            rotation=r,
            members=members,
            profile=profile,
            constraints=constraints,
            scenario_set_id=scenario_set_id,
        )
        results.append(res)
    return results


def compute_resilience_and_regret(
    hist_result: SimulationResult,
    stress_result: SimulationResult | None = None,
) -> dict[str, float]:
    """TASK-O06: Compute climate resilience score (0-100) and regret metrics.

    Evaluates rotation stability between historical baseline and adverse climate stress
    (e.g. CMIP6 ssp585 warming or severe drought):
      - Profit Regret: drop in median operating profit under climate stress
      - Irrigation Spike: increase in irrigation demand under higher evaporative demand
      - Resilience Score: composite index [0, 100] reflecting downside stability and soil health.
    """
    p_hist = hist_result.profit_p50
    irr_hist = float(np.mean(hist_result.irrigation_mm)) if hist_result.irrigation_mm else 1200.0

    if stress_result is not None:
        p_stress = stress_result.profit_p50
        irr_stress = float(np.mean(stress_result.irrigation_mm)) if stress_result.irrigation_mm else irr_hist
        profit_regret = max(0.0, p_hist - p_stress)
        irrigation_spike = max(0.0, irr_stress - irr_hist)
    else:
        # Evaluate historical downside tail risk (P50 vs CVaR-10)
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

