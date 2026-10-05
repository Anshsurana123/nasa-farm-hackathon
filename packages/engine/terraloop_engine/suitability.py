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

    best_fit, best_months, sowing = 0.0, [], []
    for start in range(1, 13):
        months = _window_months(start, duration)
        gdd = sum(max(min(tmean[m - 1], 30) - crop.base_temp_c, 0) * DAYS_IN_MONTH[m - 1] for m in months)
        if gdd < 0.85 * crop.gdd_to_maturity:
            continue
        if any(c.monthly_tmin_c[m - 1] < crop.min_temp_c for m in months):
            continue
        if any(c.monthly_tmax_c[m - 1] > crop.max_temp_c + 3 for m in months):
            continue
        in_opt = sum(1 for m in months if opt_lo <= tmean[m - 1] <= opt_hi) / len(months)
        fit = 0.5 + 0.5 * in_opt
        if fit > best_fit + 1e-9:
            best_fit, best_months, sowing = fit, months, [start]
        elif abs(fit - best_fit) < 1e-9 and best_fit > 0:
            sowing.append(start)

    reasons: list[str] = []
    if best_fit == 0:
        reasons.append("No sowing window satisfies temperature and heat-unit requirements.")
        return SuitabilityResult(crop.id, 0.0, 0.0, 0.0, [], reasons)

    season_rain = sum(c.monthly_precip_mm[m - 1] for m in best_months)
    need_lo, need_hi = crop.water_requirement_mm
    irrigation = (constraints.irrigation if constraints else "limited")
    if irrigation == "full":
        water_fit = 1.0
    else:
        rain_fit = min(season_rain / need_lo, 1.0) if need_lo else 1.0
        bonus = 0.5 if irrigation == "limited" else 0.0
        drought_bonus = 0.1 * (crop.drought_tolerance - 3)
        water_fit = max(0.0, min(1.0, rain_fit + bonus * (1 - rain_fit) + drought_bonus))
    reasons.append(f"Best window: months {best_months[0]}-{best_months[-1]}, season rain {season_rain:.0f} mm vs need {need_lo:.0f}-{need_hi:.0f} mm.")

    return SuitabilityResult(
        crop_id=crop.id,
        score=round(best_fit * water_fit, 3),
        thermal_fit=round(best_fit, 3),
        water_fit=round(water_fit, 3),
        sowing_months=sowing,
        reasons=reasons,
    )


def rank_crops(profile: FieldProfile, crops: dict[str, CropSpec], constraints: FarmConstraints | None = None) -> list[SuitabilityResult]:
    results = [score_crop(profile, crop, constraints) for crop in crops.values()]
    return sorted(results, key=lambda r: r.score, reverse=True)
