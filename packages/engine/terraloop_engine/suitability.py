"""Heuristic agro-climatic suitability pre-filter.

Purpose: shrink the candidate crop list BEFORE expensive simulation
(build plan section 5.5). This is NOT the final recommendation logic.

Score in [0, 1] = thermal_fit * water_fit, plus per-season windows.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from terraloop_schemas import CropSpec, FarmConstraints, FieldProfile

from terraloop_engine import region_registry

DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

_GROUP_PH_RANGE: dict[str, tuple[float, float]] = {
    "cereal": (5.5, 8.2),
    "legume": (5.8, 7.8),
    "oilseed": (6.0, 8.0),
    "tuber": (5.0, 6.8),
    "vegetable": (5.8, 7.5),
    "fibre": (5.8, 8.2),
    "cover": (5.5, 8.0),
    "fodder": (5.8, 8.2),
}

_CROP_PH_RANGE: dict[str, tuple[float, float]] = {
    "rice_puddled": (5.0, 8.2),
    "rice_dsr": (5.0, 8.2),
    "rice_short": (5.0, 8.2),
    "basmati": (5.0, 8.2),
    "wheat": (6.0, 8.2),
    "barley": (6.0, 8.5),
    "potato": (5.0, 6.8),
    "groundnut": (5.5, 7.5),
    "chickpea": (6.0, 8.2),
    "cotton": (5.8, 8.2),
}


def _crop_ph_range(crop: CropSpec) -> tuple[float, float]:
    explicit = getattr(crop, "ph_range", None)
    if explicit and len(explicit) == 2:
        return float(explicit[0]), float(explicit[1])
    return _CROP_PH_RANGE.get(crop.id, _GROUP_PH_RANGE.get(crop.group, (5.8, 8.0)))


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


def score_crop(
    profile: FieldProfile,
    crop: CropSpec,
    constraints: FarmConstraints | None = None,
    language: str = "en",
) -> SuitabilityResult:
    c = profile.climate
    tmean = [(tx + tn) / 2 for tx, tn in zip(c.monthly_tmax_c, c.monthly_tmin_c)]
    duration = int(sum(crop.duration_days) / 2)
    opt_lo, opt_hi = crop.optimal_temp_c
    need_lo, need_hi = crop.water_requirement_mm
    irrigation = constraints.irrigation if constraints else "limited"
    irr_cap = constraints.irrigation_cap_mm if constraints else None
    is_sh = region_registry.detect_region_config(profile.field.lat, profile.field.lon).hemisphere == "SH"
    wet_months = c.wettest_months or ([12, 1, 2, 3] if is_sh else [7, 8, 9])
    monsoon_rain = sum(c.monthly_precip_mm[m - 1] for m in wet_months)
    post_wet_starts = {wet_months[-1], (wet_months[-1] % 12) + 1, ((wet_months[-1] + 1) % 12) + 1}

    if "cool" in crop.season_type and "warm" not in crop.season_type:
        preferred_starts = [4, 5, 6, 7, 8] if is_sh else [10, 11, 12, 1, 2]
    elif "warm" in crop.season_type and "cool" not in crop.season_type:
        preferred_starts = [10, 11, 12, 1, 2, 3] if is_sh else [4, 5, 6, 7, 8, 9]
    else:
        preferred_starts = list(range(1, 13))

    smap_pcts = profile.water.root_zone_moisture_percentile
    gw_trend = profile.water.groundwater_trend_cm_per_year
    haz = profile.hazards
    soil_s = profile.soil

    def _eval_starts(candidate_starts: list[int]) -> tuple[float, float, float, list[int], list[int]]:
        b_score, b_tfit, b_wfit, b_months, b_sowing = 0.0, 0.0, 0.0, [], []
        best_raw = -1e9
        for start in candidate_starts:
            months = _window_months(start, duration)
            gdd = sum(max(min(tmean[m - 1], crop.max_temp_c) - crop.base_temp_c, 0) * DAYS_IN_MONTH[m - 1] for m in months)
            if gdd < 0.85 * crop.gdd_to_maturity:
                continue
            if any(c.monthly_tmin_c[m - 1] < crop.min_temp_c for m in months):
                continue
            if any(c.monthly_tmax_c[m - 1] > crop.max_temp_c + 4 for m in months):
                continue
            in_opt = sum(1 for m in months if opt_lo <= tmean[m - 1] <= opt_hi) / len(months)
            heat_excess = sum(max(0.0, c.monthly_tmax_c[m - 1] - crop.max_temp_c) for m in months) / len(months)
            t_fit = max(0.15, min(1.0, 0.5 + 0.5 * in_opt - 0.04 * heat_excess))

            season_rain = sum(c.monthly_precip_mm[m - 1] for m in months)
            smap_mod = 1.0
            smap_mean = None
            if smap_pcts and len(smap_pcts) == 12:
                smap_mean = sum(smap_pcts[m - 1] for m in months) / len(months)
                if smap_mean > 60.0:
                    smap_mod = 1.15

            if irrigation == "full":
                w_fit = 1.0
            else:
                # Deep-rooted post-monsoon crops access residual soil moisture recharged by wet-season rains
                residual_mm = (
                    0.35 * monsoon_rain * smap_mod
                    if (crop.drought_tolerance >= 4 and start in post_wet_starts)
                    else 0.0
                )
                eff_rain = season_rain + residual_mm
                if irr_cap is not None and irrigation == "limited":
                    eff_rain += min(float(irr_cap), max(0.0, need_lo - eff_rain))
                rain_fit = min(eff_rain / need_lo, 1.0) if need_lo else 1.0
                if irrigation == "limited":
                    lim_bonus = max(0.12, min(0.42, 0.45 - 0.00028 * need_lo))
                else:
                    lim_bonus = 0.0
                drought_bonus = 0.1 * (crop.drought_tolerance - 3)
                smap_bonus = 0.0
                if smap_mean is not None:
                    if smap_mean < 35.0 and crop.drought_tolerance >= 4:
                        smap_bonus = 0.06
                    elif smap_mean < 35.0 and crop.drought_tolerance <= 2:
                        smap_bonus = -0.08
                w_fit = max(0.0, min(1.0, rain_fit + lim_bonus * (1 - rain_fit) + drought_bonus + smap_bonus))

            # Aquifer overdraft, drought hazard, heat hazard, soil pH & rainfed telemetry adjustments
            adj = 0.0
            if gw_trend is not None and gw_trend < -1.5 and need_lo >= 750:
                adj -= min(0.18, abs(gw_trend + 1.0) * 0.045)
            if haz.drought_frequency and haz.drought_frequency > 0.25 and irrigation != "full" and crop.drought_tolerance <= 2:
                adj -= 0.06
            if haz.terminal_heat_days_per_year and haz.terminal_heat_days_per_year > 5.0 and crop.id in ("wheat", "potato", "lentil"):
                adj -= 0.03
            if profile.water.irrigation_detected is False and irrigation == "limited" and need_lo > 750:
                adj -= 0.12
            if soil_s.ph is not None:
                p_lo, p_hi = _crop_ph_range(crop)
                if soil_s.ph < p_lo:
                    adj -= min(0.30, (p_lo - soil_s.ph) * 0.14)
                elif soil_s.ph > p_hi:
                    adj -= min(0.30, (soil_s.ph - p_hi) * 0.14)
            if soil_s.available_p_kg_ha is not None and soil_s.available_p_kg_ha < 12.0 and crop.n_fixation_kg_ha > 0:
                adj += 0.02
            if soil_s.available_k_kg_ha is not None and soil_s.available_k_kg_ha < 110.0 and crop.id == "potato":
                adj -= 0.04
            # Gate instantaneous snapshot biotic/hail hazard penalties to crops whose growing window overlaps the hazard season
            cool_hazard_months = {4, 5, 6, 7, 8, 9} if is_sh else {10, 11, 12, 1, 2, 3}
            hail_hazard_months = {8, 9, 10} if is_sh else {2, 3, 4}
            has_cool_overlap = bool(set(months) & cool_hazard_months)
            has_hail_overlap = bool(set(months) & hail_hazard_months)
            if (
                has_cool_overlap
                and haz.late_blight_risk_idx is not None
                and haz.late_blight_risk_idx > 150.0
                and crop.id == "potato"
            ):
                adj -= 0.08
            if (
                has_cool_overlap
                and haz.canopy_wetness_idx is not None
                and haz.canopy_wetness_idx > 0.65
                and crop.id in ("chickpea", "mustard", "lentil")
            ):
                adj -= 0.05
            if (
                has_hail_overlap
                and haz.hail_probability_pct is not None
                and haz.hail_probability_pct > 25.0
                and "cool" in crop.season_type
            ):
                adj -= 0.04
            if haz.meteorological_drought_idx is not None and haz.meteorological_drought_idx < -1.5:
                if need_lo >= 750:
                    adj -= min(0.10, abs(haz.meteorological_drought_idx + 1.0) * 0.03)
                elif crop.drought_tolerance >= 4:
                    adj += 0.03

            raw_comb = t_fit * w_fit + adj
            comb = max(0.0, min(1.0, raw_comb))
            if raw_comb > best_raw + 1e-9:
                best_raw = raw_comb
                b_score, b_tfit, b_wfit, b_months, b_sowing = comb, t_fit, w_fit, months, [start]
            elif abs(raw_comb - best_raw) < 1e-9 and b_tfit > 0:
                b_sowing.append(start)
        return b_score, b_tfit, b_wfit, b_months, b_sowing

    best_score, best_fit, water_fit, best_months, sowing = _eval_starts(preferred_starts)
    if best_fit == 0.0 and len(preferred_starts) < 12:
        best_score, best_fit, water_fit, best_months, sowing = _eval_starts(list(range(1, 13)))

    lang = language if language in ("en", "hi", "pa") else "en"

    def _tr(en: str, hi: str, pa: str) -> str:
        return hi if lang == "hi" else pa if lang == "pa" else en

    reasons: list[str] = []
    if best_fit == 0:
        reasons.append(
            _tr(
                "No sowing window satisfies temperature and heat-unit requirements.",
                "कोई भी बुवाई अवधि तापमान और ऊष्मा-इकाई (GDD) आवश्यकताओं को पूरा नहीं करती।",
                "ਕੋਈ ਵੀ ਬਿਜਾਈ ਸਮਾਂ ਤਾਪਮਾਨ ਅਤੇ ਗਰਮੀ-ਇਕਾਈ (GDD) ਦੀਆਂ ਲੋੜਾਂ ਪੂਰੀਆਂ ਨਹੀਂ ਕਰਦਾ।",
            )
        )
        return SuitabilityResult(crop.id, 0.0, 0.0, 0.0, [], reasons)

    season_rain = sum(c.monthly_precip_mm[m - 1] for m in best_months)
    reasons.append(
        _tr(
            f"Best window: months {best_months[0]}-{best_months[-1]}, season rain {season_rain:.0f} mm vs need {need_lo:.0f}-{need_hi:.0f} mm.",
            f"सर्वोत्तम अवधि: महीने {best_months[0]}-{best_months[-1]}, मौसमी वर्षा {season_rain:.0f} मिमी (आवश्यकता {need_lo:.0f}-{need_hi:.0f} मिमी)।",
            f"ਸਭ ਤੋਂ ਵਧੀਆ ਸਮਾਂ: ਮਹੀਨੇ {best_months[0]}-{best_months[-1]}, ਮੌਸਮੀ ਮੀਂਹ {season_rain:.0f} ਮਿ.ਮੀ. (ਲੋੜ {need_lo:.0f}-{need_hi:.0f} ਮਿ.ਮੀ.)।",
        )
    )
    if gw_trend is not None and gw_trend < -1.5 and need_lo >= 750:
        reasons.append(
            _tr(
                f"NASA GRACE aquifer depletion ({gw_trend:+.2f} cm/yr) penalizes high-water crops.",
                f"नासा GRACE भूजल गिरावट ({gw_trend:+.2f} सेमी/वर्ष) अधिक पानी वाली फसलों के लिए जोखिम बढ़ाती है।",
                f"ਨਾਸਾ GRACE ਧਰਤੀ ਹੇਠਲੇ ਪਾਣੀ ਦੀ ਗਿਰਾਵਟ ({gw_trend:+.2f} ਸੈ.ਮੀ./ਸਾਲ) ਵੱਧ ਪਾਣੀ ਵਾਲੀਆਂ ਫ਼ਸਲਾਂ ਲਈ ਨੁਕਸਾਨਦੇਹ ਹੈ।",
            )
        )
    ph_lo, ph_hi = _crop_ph_range(crop)
    if soil_s.ph is not None and not (ph_lo <= soil_s.ph <= ph_hi):
        reasons.append(
            _tr(
                f"Field pH ({soil_s.ph:.1f}) falls outside optimal {ph_lo:.1f}-{ph_hi:.1f}.",
                f"खेत का मिट्टी pH ({soil_s.ph:.1f}) उपयुक्त सीमा {ph_lo:.1f}-{ph_hi:.1f} से बाहर है।",
                f"ਖੇਤ ਦਾ ਮਿੱਟੀ pH ({soil_s.ph:.1f}) ਢੁਕਵੀਂ ਹੱਦ {ph_lo:.1f}-{ph_hi:.1f} ਤੋਂ ਬਾਹਰ ਹੈ।",
            )
        )
    if profile.water.irrigation_detected is False and need_lo > 750:
        reasons.append(
            _tr(
                "Satellite observations indicate rainfed conditions; water-intensive paddy is discouraged.",
                "उपग्रह अवलोकन वर्षा-आधारित क्षेत्र दर्शाते हैं; अधिक पानी वाले धान की सिफारिश नहीं की जाती।",
                "ਸੈਟੇਲਾਈਟ ਅੰਕੜੇ ਬਰਾਨੀ ਹਾਲਾਤ ਦਰਸਾਉਂਦੇ ਹਨ; ਵੱਧ ਪਾਣੀ ਵਾਲੇ ਝੋਨੇ ਦੀ ਸਿਫ਼ਾਰਿਸ਼ ਨਹੀਂ ਕੀਤੀ ਜਾਂਦੀ।",
            )
        )
    best_cool_overlap = bool(set(best_months) & ({4, 5, 6, 7, 8, 9} if is_sh else {10, 11, 12, 1, 2, 3}))
    best_hail_overlap = bool(set(best_months) & ({8, 9, 10} if is_sh else {2, 3, 4}))
    if (
        best_cool_overlap
        and haz.late_blight_risk_idx is not None
        and haz.late_blight_risk_idx > 150.0
        and crop.id == "potato"
    ):
        reasons.append(
            _tr(
                f"Elevated Meteomatics Phytophthora late-blight index ({haz.late_blight_risk_idx:.0f} > 150) increases disease risk.",
                f"मेटियोमैटिक्स फाइटोफ्थोरा लेट-ब्लाइट सूचकांक ({haz.late_blight_risk_idx:.0f} > 150) झुलसा रोग का खतरा बढ़ाता है।",
                f"ਮੀਟੀਓਮੈਟਿਕਸ ਫਾਈਟੋਪਥੋਰਾ ਲੇਟ-ਬਲਾਈਟ ਸੂਚਕ ({haz.late_blight_risk_idx:.0f} > 150) ਝੁਲਸ ਰੋਗ ਦਾ ਖ਼ਤਰਾ ਵਧਾਉਂਦਾ ਹੈ।",
            )
        )
    if (
        best_cool_overlap
        and haz.canopy_wetness_idx is not None
        and haz.canopy_wetness_idx > 0.65
        and crop.id in ("chickpea", "mustard", "lentil")
    ):
        reasons.append(
            _tr(
                f"High canopy leaf wetness ({haz.canopy_wetness_idx:.2f}) elevates foliar fungal blight pressure.",
                f"पत्ती पर अधिक नमी ({haz.canopy_wetness_idx:.2f}) फफूंद झुलसा रोग का दबाव बढ़ाती है।",
                f"ਪੱਤਿਆਂ ਦੀ ਵੱਧ ਨਮੀ ({haz.canopy_wetness_idx:.2f}) ਉੱਲੀ ਝੁਲਸ ਰੋਗ ਦਾ ਦਬਾਅ ਵਧਾਉਂਦੀ ਹੈ।",
            )
        )
    if (
        best_hail_overlap
        and haz.hail_probability_pct is not None
        and haz.hail_probability_pct > 25.0
        and "cool" in crop.season_type
    ):
        reasons.append(
            _tr(
                f"Elevated Rabi hailstorm probability ({haz.hail_probability_pct:.0f}%) increases pre-harvest lodging risk.",
                f"कटाई-पूर्व ओलावृष्टि संभावना ({haz.hail_probability_pct:.0f}%) फसल गिरने का जोखिम बढ़ाती है।",
                f"ਵਾਢੀ ਤੋਂ ਪਹਿਲਾਂ ਗੜੇਮਾਰੀ ਦੀ ਸੰਭਾਵਨਾ ({haz.hail_probability_pct:.0f}%) ਫ਼ਸਲ ਡਿੱਗਣ ਦਾ ਖ਼ਤਰਾ ਵਧਾਉਂਦੀ ਹੈ।",
            )
        )
    if haz.meteorological_drought_idx is not None and haz.meteorological_drought_idx < -1.5:
        if need_lo >= 750:
            reasons.append(
                _tr(
                    f"Severe meteorological drought index ({haz.meteorological_drought_idx:+.1f}) stresses water-intensive crops.",
                    f"गंभीर मौसम सूखा सूचकांक ({haz.meteorological_drought_idx:+.1f}) अधिक सिंचाई वाली फसलों पर दबाव डालता है।",
                    f"ਗੰਭੀਰ ਮੌਸਮੀ ਸੋਕਾ ਸੂਚਕ ({haz.meteorological_drought_idx:+.1f}) ਵੱਧ ਪਾਣੀ ਵਾਲੀਆਂ ਫ਼ਸਲਾਂ 'ਤੇ ਦਬਾਅ ਪਾਉਂਦਾ ਹੈ।",
                )
            )
        elif crop.drought_tolerance >= 4:
            reasons.append(
                _tr(
                    f"High drought tolerance suited to dry meteorological balance ({haz.meteorological_drought_idx:+.1f} drought index).",
                    f"सूखे के प्रति उच्च सहनशीलता शुष्क मौसम संतुलन ({haz.meteorological_drought_idx:+.1f}) के लिए उपयुक्त है।",
                    f"ਸੋਕੇ ਪ੍ਰਤੀ ਉੱਚ ਸਹਿਣਸ਼ੀਲਤਾ ਖੁਸ਼ਕ ਮੌਸਮ ਸੰਤੁਲਨ ({haz.meteorological_drought_idx:+.1f}) ਲਈ ਢੁਕਵੀਂ ਹੈ।",
                )
            )

    return SuitabilityResult(
        crop_id=crop.id,
        score=round(best_score, 3),
        thermal_fit=round(best_fit, 3),
        water_fit=round(water_fit, 3),
        sowing_months=sowing,
        reasons=reasons,
    )


def rank_crops(
    profile: FieldProfile,
    crops: dict[str, CropSpec],
    constraints: FarmConstraints | None = None,
    language: str = "en",
) -> list[SuitabilityResult]:
    results = [score_crop(profile, crop, constraints, language=language) for crop in crops.values()]
    return sorted(results, key=lambda r: r.score, reverse=True)
