"""Heuristic agro-climatic suitability pre-filter.

Purpose: shrink the candidate crop list BEFORE expensive simulation
(build plan section 5.5). This is NOT the final recommendation logic.

Score in [0, 1] = thermal_fit * water_fit, plus per-season windows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from terraloop_schemas import CropSpec, FarmConstraints, FieldProfile

DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


@dataclass
class SuitabilityResult:
    crop_id: str
    score: float
    thermal_fit: float
    water_fit: float
    sowing_months: list[int] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def _window_months(start_month: int, duration_days: int) -> list[int]:
    months, days, m = [], 0, start_month
    while days < duration_days:
        months.append(m)
        days += DAYS_IN_MONTH[m - 1]
        m = m % 12 + 1
    return months


def score_crop(profile: FieldProfile, crop: CropSpec, constraints: FarmConstraints | None = None) -> SuitabilityResult:
    c = profile.climate
    tmean = [(tx + tn) / 2 for tx, tn in zip(c.monthly_tmax_c, c.monthly_tmin_c)]
    duration = int(sum(crop.duration_days) / 2)
    opt_lo, opt_hi = crop.optimal_temp_c
    need_lo, need_hi = crop.water_requirement_mm
    irrigation = constraints.irrigation if constraints else "limited"
    monsoon_rain = sum(c.monthly_precip_mm[m - 1] for m in (7, 8, 9))

    if "cool" in crop.season_type and "warm" not in crop.season_type:
        preferred_starts = [10, 11, 12, 1, 2]
    elif "warm" in crop.season_type and "cool" not in crop.season_type:
        preferred_starts = [4, 5, 6, 7, 8, 9]
    else:
        preferred_starts = list(range(1, 13))

    def _eval_starts(candidate_starts: list[int]) -> tuple[float, float, float, list[int], list[int]]:
        b_score, b_tfit, b_wfit, b_months, b_sowing = 0.0, 0.0, 0.0, [], []
        for start in candidate_starts:
            months = _window_months(start, duration)
            gdd = sum(max(min(tmean[m - 1], 30) - crop.base_temp_c, 0) * DAYS_IN_MONTH[m - 1] for m in months)
            if gdd < 0.85 * crop.gdd_to_maturity:
                continue
            if any(c.monthly_tmin_c[m - 1] < crop.min_temp_c for m in months):
                continue
            if any(c.monthly_tmax_c[m - 1] > crop.max_temp_c + 3 for m in months):
                continue
            in_opt = sum(1 for m in months if opt_lo <= tmean[m - 1] <= opt_hi) / len(months)
            t_fit = 0.5 + 0.5 * in_opt

            season_rain = sum(c.monthly_precip_mm[m - 1] for m in months)
            if irrigation == "full":
                w_fit = 1.0
            else:
                # Deep-rooted Rabi pulses/oilseeds (drought_tolerance >= 4) sown post-monsoon (Oct-Nov)
                # access residual root-zone soil moisture recharged by July-Sept monsoon rains
                residual_mm = (
                    0.35 * monsoon_rain
                    if ("cool" in crop.season_type and crop.drought_tolerance >= 4 and start in (10, 11))
                    else 0.0
                )
                eff_rain = season_rain + residual_mm
                rain_fit = min(eff_rain / need_lo, 1.0) if need_lo else 1.0
                bonus = 0.5 if irrigation == "limited" else 0.0
                drought_bonus = 0.1 * (crop.drought_tolerance - 3)
                w_fit = max(0.0, min(1.0, rain_fit + bonus * (1 - rain_fit) + drought_bonus))

            comb = t_fit * w_fit
            if comb > b_score + 1e-9:
                b_score, b_tfit, b_wfit, b_months, b_sowing = comb, t_fit, w_fit, months, [start]
            elif abs(comb - b_score) < 1e-9 and b_score > 0:
                b_sowing.append(start)
        return b_score, b_tfit, b_wfit, b_months, b_sowing

    best_score, best_fit, water_fit, best_months, sowing = _eval_starts(preferred_starts)
    if best_fit == 0.0 and len(preferred_starts) < 12:
        best_score, best_fit, water_fit, best_months, sowing = _eval_starts(list(range(1, 13)))

    reasons: list[str] = []
    if best_fit == 0:
        reasons.append("No sowing window satisfies temperature and heat-unit requirements.")
        return SuitabilityResult(crop.id, 0.0, 0.0, 0.0, [], reasons)

    season_rain = sum(c.monthly_precip_mm[m - 1] for m in best_months)
    reasons.append(
        f"Best window: months {best_months[0]}-{best_months[-1]}, season rain {season_rain:.0f} mm vs need {need_lo:.0f}-{need_hi:.0f} mm."
    )

    return SuitabilityResult(
        crop_id=crop.id,
        score=round(best_score, 3),
        thermal_fit=round(best_fit, 3),
        water_fit=round(water_fit, 3),
        sowing_months=sowing,
        reasons=reasons,
    )


def rank_crops(profile: FieldProfile, crops: dict[str, CropSpec], constraints: FarmConstraints | None = None) -> list[SuitabilityResult]:
    results = [score_crop(profile, crop, constraints) for crop in crops.values()]
    return sorted(results, key=lambda r: r.score, reverse=True)
