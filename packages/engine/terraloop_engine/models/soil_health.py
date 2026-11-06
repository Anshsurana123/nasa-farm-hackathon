"""Soil carbon (RothC-lite), nitrogen balance, and soil health score. (TASK-M05, M06, M07)

M05 RothC-lite (monthly, steady-state spin-up calibrated):
    Pools DPM, RPM, BIO, HUM, IOM. Rate constants (yr-1): DPM 10, RPM 0.3, BIO 0.66, HUM 0.02.
    Rate modifiers: temperature a(T), moisture b(M), soil cover c = 0.6 when crop present else 1.0.
    Active pools (DPM, RPM, BIO, HUM) are initialized at analytical steady-state equilibrium
    for a reference conventional cropping input (~2.4 t C/ha/yr including root C), avoiding
    artificial spin-up decay under subtropical Indian temperatures (Benbi et al. 2012).
    Reference: Coleman & Jenkinson (1996) RothC-26.3.

M06 N-balance per season (kg N/ha):
    surplus = fertiliser + fixation (CropSpec.n_fixation_kg_ha) + deposition(~10)
              - removal (yield * grain N conc.)

M07 Soil Health Score (0-100) built on the 5 USDA-NRCS principles + SOC & RUSLE modifiers.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

import numpy as np
from terraloop_schemas import CropSpec, Rotation, SoilSummary


def is_burning_practice(practices: Sequence[str]) -> bool:
    """Return True if any practice string indicates open-field crop residue burning."""
    return any(p in ("burning", "residue_burnt", "burned") for p in practices)


def family_shannon_index(rotation: Rotation, crops: dict[str, CropSpec]) -> float:
    """Shannon diversity of botanical families across the rotation."""
    fams = Counter(crops[s.crop_id].family for s in rotation.steps if s.crop_id in crops and s.crop_id != "fallow")
    total = sum(fams.values())
    if total == 0:
        return 0.0
    return round(-sum((n / total) * math.log(n / total) for n in fams.values()), 3)


# ---------------------------------------------------------------------------
# TASK-M05: RothC-lite Soil Organic Carbon Model (Coleman & Jenkinson 1996)
# ---------------------------------------------------------------------------

def calculate_initial_soc_stock(
    soc_g_per_kg: float,
    bulk_density_g_cm3: float = 1.45,
    depth_m: float = 0.3,
) -> float:
    """Convert SOC concentration (g C / kg soil) to SOC stock (t C / ha in 0-30 cm topsoil)."""
    soil_mass_t_ha = 10_000.0 * depth_m * bulk_density_g_cm3
    return round(soil_mass_t_ha * (soc_g_per_kg / 1000.0), 2)


def rothc_temp_factor(temp_c: float) -> float:
    """Temperature rate modifier a(T) according to RothC-26.3."""
    if temp_c <= -18.27:
        return 0.0
    return 47.91 / (1.0 + math.exp(106.06 / (temp_c + 18.27)))


def rothc_moisture_factor(precip_mm: float, et0_mm: float) -> float:
    """Moisture rate modifier b(M) from topsoil moisture balance."""
    deficit = max(0.0, 0.75 * et0_mm - precip_mm)
    return max(0.2, min(1.0, 1.0 - 0.8 * (deficit / 100.0)))


def rothc_lite(
    soil: SoilSummary | None = None,
    initial_soc_t_ha: float | None = None,
    clay_pct: float = 20.0,
    monthly_temp_c: Sequence[float] | None = None,
    monthly_precip_mm: Sequence[float] | None = None,
    monthly_et0_mm: Sequence[float] | None = None,
    annual_c_input_t_ha: float = 2.5,
    monthly_c_inputs_t_ha: Sequence[float] | None = None,
    crop_cover_months: Sequence[int] | None = None,
    years: int = 10,
    dpm_rpm_ratio: float = 1.44,
) -> dict[str, list[float] | float]:
    """Simulate annual SOC stock (t C/ha, 0-30 cm) over N years using steady-state calibrated RothC-lite."""
    if soil is not None:
        soc_conc = soil.soc_g_per_kg if soil.soc_g_per_kg is not None else 6.5
        bd = soil.bulk_density_g_cm3 if soil.bulk_density_g_cm3 is not None else 1.48
        tot_soc = calculate_initial_soc_stock(soc_conc, bd)
        clay = soil.clay_pct if soil.clay_pct is not None else clay_pct
    elif initial_soc_t_ha is not None:
        tot_soc = float(initial_soc_t_ha)
        clay = clay_pct
    else:
        tot_soc = 28.0
        clay = clay_pct

    # Falloon et al. (1998) Inert Organic Matter (IOM)
    iom = 0.049 * (tot_soc ** 1.139) if tot_soc > 0 else 0.0
    iom = min(iom, 0.35 * tot_soc)
    active_soc = max(1.0, tot_soc - iom)

    # Monthly rate constants (yr^-1 / 12)
    k_dpm = 10.0 / 12.0
    k_rpm = 0.30 / 12.0
    k_bio = 0.66 / 12.0
    k_hum = 0.02 / 12.0

    # Clay-dependent CO2 partition ratio x = 1.67 * (1.85 + 1.60 * exp(-0.0786 * clay))
    x = 1.67 * (1.85 + 1.60 * math.exp(-0.0786 * clay))
    f_co2 = x / (x + 1.0)
    f_bio = 0.46 * (1.0 - f_co2)
    f_hum = 0.54 * (1.0 - f_co2)

    temps = list(monthly_temp_c) if monthly_temp_c and len(monthly_temp_c) == 12 else [
        13.0, 16.0, 22.0, 28.0, 33.0, 34.0, 31.0, 30.0, 29.0, 25.0, 19.0, 14.0
    ]
    precips = list(monthly_precip_mm) if monthly_precip_mm and len(monthly_precip_mm) == 12 else [
        20.0, 20.0, 20.0, 15.0, 25.0, 70.0, 150.0, 140.0, 80.0, 15.0, 5.0, 10.0
    ]
    et0s = list(monthly_et0_mm) if monthly_et0_mm and len(monthly_et0_mm) == 12 else [
        60.0, 80.0, 120.0, 170.0, 220.0, 210.0, 160.0, 140.0, 130.0, 110.0, 80.0, 55.0
    ]

    if monthly_c_inputs_t_ha and len(monthly_c_inputs_t_ha) == 12:
        m_inputs = list(monthly_c_inputs_t_ha)
    else:
        m_inputs = [annual_c_input_t_ha / 12.0] * 12

    f_dpm_in = dpm_rpm_ratio / (dpm_rpm_ratio + 1.0)
    f_rpm_in = 1.0 / (dpm_rpm_ratio + 1.0)

    # Compute mean annual rate modifier xi_bar for this site's climate to initialize
    # labile pools (DPM, RPM, BIO) in steady-state equilibrium with reference C_eq = 2.35 t C/ha/yr
    xi_months = []
    for m in range(12):
        a_t = rothc_temp_factor(temps[m])
        b_m = rothc_moisture_factor(precips[m], et0s[m])
        c_cov = 0.6 if (crop_cover_months and (m + 1) in crop_cover_months) else 0.75
        xi_months.append(a_t * b_m * c_cov)
    xi_bar = max(0.5, float(np.mean(xi_months)))

    # Reference equilibrium input C_eq (~2.35 t C/ha/yr: conventional partial residue removal)
    c_eq = 2.35
    dpm = min(0.08 * active_soc, (f_dpm_in * c_eq) / (10.0 * xi_bar))
    rpm = min(0.28 * active_soc, (f_rpm_in * c_eq) / (0.30 * xi_bar))
    bio = min(0.06 * active_soc, (f_bio * c_eq) / (0.66 * xi_bar))
    hum = max(0.2, active_soc - (dpm + rpm + bio))
    # Calibrate HUM decay rate to site steady state so C_in == C_eq yields ~0 net drift
    ann_hum_gain_at_eq = f_hum * c_eq
    eff_k_hum = min(k_hum, (ann_hum_gain_at_eq / max(5.0, hum * xi_bar)) / 12.0)

    soc_history = [round(tot_soc, 2)]

    for _year in range(years):
        for m in range(12):
            month_idx = m + 1
            a_t = rothc_temp_factor(temps[m])
            b_m = rothc_moisture_factor(precips[m], et0s[m])
            c_cov = 0.6 if (crop_cover_months and month_idx in crop_cover_months) else 0.85
            xi = a_t * b_m * c_cov

            dec_dpm = dpm * (1.0 - math.exp(-k_dpm * xi))
            dec_rpm = rpm * (1.0 - math.exp(-k_rpm * xi))
            dec_bio = bio * (1.0 - math.exp(-k_bio * xi))
            dec_hum = hum * (1.0 - math.exp(-eff_k_hum * xi))

            total_dec = dec_dpm + dec_rpm + dec_bio + dec_hum

            dpm -= dec_dpm
            rpm -= dec_rpm
            bio -= dec_bio
            hum -= dec_hum

            bio += f_bio * total_dec
            hum += f_hum * total_dec

            c_in = m_inputs[m]
            dpm += f_dpm_in * c_in
            rpm += f_rpm_in * c_in

        current_soc = round(dpm + rpm + bio + hum + iom, 2)
        soc_history.append(current_soc)

    delta = round(soc_history[min(10, len(soc_history) - 1)] - soc_history[0], 2)

    return {
        "annual_soc_t_ha": soc_history,
        "soc_delta_10yr": delta,
        "final_soc_t_ha": soc_history[-1],
    }


# ---------------------------------------------------------------------------
# TASK-M06: Seasonal Nitrogen Balance Model
# ---------------------------------------------------------------------------

_GRAIN_N_PCT: dict[str, float] = {
    "rice_puddled": 0.013,
    "rice_short": 0.013,
    "rice_dsr": 0.013,
    "basmati": 0.014,
    "wheat": 0.018,
    "maize": 0.014,
    "sorghum": 0.015,
    "pearl_millet": 0.016,
    "barley": 0.016,
    "moong": 0.036,
    "urad": 0.036,
    "groundnut": 0.038,
    "chickpea": 0.034,
    "lentil": 0.038,
    "pigeon_pea": 0.034,
    "common_bean": 0.036,
    "soybean": 0.055,
    "mustard": 0.028,
    "sunflower": 0.025,
    "cotton": 0.022,
    "potato": 0.0035,
    "berseem": 0.004,
    "dhaincha": 0.0,
}


def n_balance(
    crop: CropSpec,
    yield_t_ha: float,
    fertilizer_n_kg_ha: float | None = None,
    preceded_by_legume: bool = False,
    atmospheric_deposition_kg_ha: float = 10.0,
    residue_retained: bool = False,
) -> dict[str, float]:
    """Calculate seasonal nitrogen mass balance (kg N / ha)."""
    base_demand = crop.n_demand_kg_ha

    # Legume biological N credit (25 kg N/ha) + retained residue mineralization credit (~12 kg N/ha)
    legume_credit = 25.0 if preceded_by_legume and crop.group not in ("legume", "cover") else 0.0
    residue_credit = 12.0 if residue_retained and crop.group not in ("legume", "cover") else 0.0
    total_saved = legume_credit + residue_credit

    if fertilizer_n_kg_ha is not None:
        fert_applied = max(0.0, fertilizer_n_kg_ha)
    else:
        fert_applied = max(0.0, base_demand - total_saved)

    n_fix = crop.n_fixation_kg_ha
    n_dep = atmospheric_deposition_kg_ha

    grain_n_ratio = _GRAIN_N_PCT.get(crop.id, 0.018)
    n_removal = yield_t_ha * 1000.0 * grain_n_ratio

    total_inputs = fert_applied + n_fix + n_dep
    surplus = round(total_inputs - n_removal, 1)

    return {
        "fertilizer_applied_kg_ha": round(fert_applied, 1),
        "fertilizer_saved_kg_ha": round(total_saved, 1),
        "n_fixation_kg_ha": round(n_fix, 1),
        "n_deposition_kg_ha": round(n_dep, 1),
        "n_removal_kg_ha": round(n_removal, 1),
        "n_surplus_deficit_kg_ha": surplus,
    }


# ---------------------------------------------------------------------------
# TASK-M07: Composite Soil Health Score (USDA-NRCS 5 Principles Framework)
# ---------------------------------------------------------------------------

def soil_health_breakdown(
    rotation: Rotation,
    crops: dict[str, CropSpec],
    soc_delta_10yr: float = 0.0,
    erosion_t_ha_yr: float = 5.0,
    has_livestock: bool = False,
) -> dict[str, float]:
    """Calculate component sub-scores and modifiers for the composite Soil Health Score (0-100).

    Components (weights):
      - disturbance_minimization (0..15 pts): tillage intensity & residue burning avoidance
      - soil_armor_cover (0..15 pts): surface residue mulch & canopy cover
      - living_roots (0..15 pts): active root days per year (/ 330 d)
      - biodiversity (0..15 pts): botanical family Shannon diversity index (H' / 0.95)
      - biological_n_livestock (0..15 pts): symbiotic legume N fixation & fodder/livestock integration
      - soc_modifier (-15..+18 pts): 10-year RothC-lite soil organic carbon trajectory
      - erosion_modifier (-10..+10 pts): RUSLE annual soil loss hazard relative to 5 t/ha/yr tolerance
      - burning_penalty (-8..0 pts): direct thermal sterilization penalty for open-field burning
      - total_score (0..100 pts): clipped sum
    """
    total_steps = len(rotation.steps)
    if total_steps == 0:
        return {
            "disturbance_minimization": 6.0,
            "soil_armor_cover": 6.0,
            "living_roots": 6.0,
            "biodiversity": 6.0,
            "biological_n_livestock": 6.0,
            "soc_modifier": 0.0,
            "erosion_modifier": 0.0,
            "burning_penalty": 0.0,
            "total_score": 30.0,
        }

    # 1. Disturbance Minimization (15 max)
    till_scores = []
    any_burning = False
    for step in rotation.steps:
        practices = step.practices
        if is_burning_practice(practices):
            till_scores.append(3.5)
            any_burning = True
        elif any(p in ("no_till", "zero_till", "happy_seeder") for p in practices):
            till_scores.append(15.0)
        elif any(p in ("reduced_till", "strip_till", "direct_seeded") for p in practices):
            till_scores.append(12.0)
        elif step.crop_id in ("rice_puddled", "rice_short"):
            till_scores.append(5.5)  # Intensive puddling disperses soil aggregates
        else:
            till_scores.append(8.0)  # Conventional tillage
    disturbance_score = float(np.mean(till_scores))

    # 2. Soil Armor / Cover (15 max)
    cover_fractions = []
    for step in rotation.steps:
        if step.crop_id == "fallow":
            cover_fractions.append(0.30 if "residue_retained" in step.practices else 0.15)
        else:
            base_cov = 0.72
            if any(p in ("residue_retained", "happy_seeder") for p in step.practices):
                base_cov = 0.96
            elif is_burning_practice(step.practices):
                base_cov = 0.42
            cover_fractions.append(base_cov)
    cover_score = min(15.0, 15.0 * float(np.mean(cover_fractions)))

    # 3. Continuous Living Roots (15 max)
    living_days = 0.0
    years_in_rot = max(1, max(s.year_index for s in rotation.steps) + 1)
    for step in rotation.steps:
        if step.crop_id in crops and step.crop_id != "fallow":
            c = crops[step.crop_id]
            dur = (c.duration_days[0] + c.duration_days[1]) / 2.0
            living_days += dur
    living_root_fraction = min(1.0, (living_days / years_in_rot) / 330.0)
    living_roots_score = living_root_fraction * 15.0

    # 4. Biodiversity (15 max)
    shannon_h = family_shannon_index(rotation, crops)
    biodiversity_score = min(15.0, (shannon_h / 0.95) * 15.0) if shannon_h > 0 else 4.0

    # 5. Biological N / Green Manure / Livestock Integration (15 max)
    has_legume_or_green = any(
        s.crop_id in crops and crops[s.crop_id].group in ("legume", "cover")
        for s in rotation.steps
    )
    has_fodder = any(
        s.crop_id in crops and crops[s.crop_id].group == "fodder"
        for s in rotation.steps
    )
    if has_livestock and (has_fodder or has_legume_or_green):
        livestock_score = 15.0
    elif has_legume_or_green:
        livestock_score = 12.5
    elif has_livestock:
        livestock_score = 9.0
    else:
        livestock_score = 4.5

    base_sum = disturbance_score + cover_score + living_roots_score + biodiversity_score + livestock_score

    # Modifiers (aligned with docs/METHODOLOGY.md):
    # SOC Trajectory modifier (-10 to +15 pts)
    if soc_delta_10yr >= 0:
        soc_mod = min(15.0, (soc_delta_10yr / 2.2) * 15.0)
    else:
        soc_mod = max(-10.0, (soc_delta_10yr / 2.2) * 10.0)

    # Erosion Hazard modifier (-8 to +10 pts)
    if erosion_t_ha_yr <= 5.0:
        erosion_mod = 10.0 * (1.0 - (erosion_t_ha_yr / 5.0))
    else:
        erosion_mod = max(-8.0, -((erosion_t_ha_yr - 5.0) / 20.0) * 8.0)

    burning_penalty = -5.0 if any_burning else 0.0

    total_score = round(float(np.clip(base_sum + soc_mod + erosion_mod + burning_penalty, 0.0, 100.0)), 1)
    return {
        "disturbance_minimization": round(disturbance_score, 1),
        "soil_armor_cover": round(cover_score, 1),
        "living_roots": round(living_roots_score, 1),
        "biodiversity": round(biodiversity_score, 1),
        "biological_n_livestock": round(livestock_score, 1),
        "soc_modifier": round(soc_mod, 1),
        "erosion_modifier": round(erosion_mod, 1),
        "burning_penalty": round(burning_penalty, 1),
        "total_score": total_score,
    }


def soil_health_score(
    rotation: Rotation,
    crops: dict[str, CropSpec],
    soc_delta_10yr: float = 0.0,
    erosion_t_ha_yr: float = 5.0,
    has_livestock: bool = False,
) -> float:
    """Calculate composite Soil Health Score (0-100) based on 5 USDA-NRCS principles + SOC & RUSLE."""
    return soil_health_breakdown(
        rotation=rotation,
        crops=crops,
        soc_delta_10yr=soc_delta_10yr,
        erosion_t_ha_yr=erosion_t_ha_yr,
        has_livestock=has_livestock,
    )["total_score"]
