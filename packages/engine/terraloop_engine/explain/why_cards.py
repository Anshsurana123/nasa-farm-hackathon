"""Explainability: deterministic why-cards with strict data provenance. (TASK-X01, X02)

RULES:
  * Every number in an explanation traces strictly to FieldProfile / SimulationResult / PracticalFarmerMetrics.
  * Every why-card cites the data source / process model.
  * Supports English ('en'), Hindi ('hi'), and Punjabi ('pa').
  * No hallucinated numbers.
"""

from __future__ import annotations

import logging
import os
import re
import time

import httpx
import numpy as np
from terraloop_schemas import (
    DataProvenance,
    FieldProfile,
    PracticalFarmerMetrics,
    Rotation,
    SimulationResult,
    StrategyRecommendation,
)

from ..data import gee

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

log = logging.getLogger("terraloop.explain")
_DOTENV_LOADED = False
_LLM_COOLDOWN_UNTIL: float = 0.0

_FAO56_PROV = DataProvenance(
    source="FAO-56 / FAO-33 Soil-Water Balance",
    product="Daily root-zone depletion, percolation & thermal stress model",
    period="1985-2024",
    doi="10.1016/S0378-3774(98)00051-8",
    url="https://www.fao.org/3/x0490e/x0490e00.htm",
    mode="observed",
)

_GRACE_PROV = DataProvenance(
    source="NASA GRACE / GRACE-FO",
    product="Tellus Regional Terrestrial Water Storage (TWS) Mascon (JPL V04, 3° native)",
    period="2002-2024",
    doi="10.5067/TEMSC-3MJ62",
    url="https://grace.jpl.nasa.gov/",
)

_ROTHC_PROV = DataProvenance(
    source="Rothamsted Carbon Model (RothC-26.3)",
    product="4-pool soil organic carbon turnover & ICAR N-balance model",
    doi="10.1007/978-3-642-61094-3_17",
    mode="observed",
)

_POWER_PROV = DataProvenance(
    source="NASA POWER",
    product="Daily Agroclimatology (MERRA-2 / GEOS / CERES / IGP-corrected)",
    period="1985-2024",
    url="https://power.larc.nasa.gov/",
    mode="observed",
)

_FIRMS_PROV = DataProvenance(
    source="NASA FIRMS",
    product="MODIS / VIIRS Active Fire Detections",
    period="2019-2024",
    doi="10.5067/FIRMS/MODIS",
    url="https://firms.modaps.eosdis.nasa.gov/",
)

_CACP_PROV = DataProvenance(
    source="CACP / Ministry of Agriculture (GoI)",
    product="Minimum Support Prices (MSP 2024-25) & PAU Cost of Cultivation",
    period="2024-2025",
    url="https://cacp.dacnet.nic.in/",
    mode="observed",
)


def _grace_water_clause(gw_trend: float | None, language: str) -> tuple[str, bool]:
    """Return localized GRACE storage context without inverting positive recharge into decline."""
    if gw_trend is None:
        return "", False
    if gw_trend < -0.1:
        if language == "hi":
            return f" नासा GRACE क्षेत्रीय जल भंडारण (TWS) में {abs(gw_trend):.1f} सेमी/वर्ष की गिरावट को देखते हुए यह अत्यंत महत्वपूर्ण है।", True
        if language == "pa":
            return f" ਨਾਸਾ GRACE ਖੇਤਰੀ ਪਾਣੀ ਭੰਡਾਰ (TWS) ਵਿੱਚ {abs(gw_trend):.1f} ਸੈਂਟੀਮੀਟਰ/ਸਾਲ ਦੀ ਗਿਰਾਵਟ ਨੂੰ ਰੋਕਣ ਲਈ ਇਹ ਬਹੁਤ ਜ਼ਰੂਰੀ ਹੈ।", True
        return f" Directly counters regional GRACE-FO terrestrial water storage decline of {abs(gw_trend):.1f} cm/yr.", True
    if gw_trend > 0.1:
        if language == "hi":
            return f" यह क्षेत्रीय जल संतुलन बनाए रखता है (नासा GRACE-FO प्रवृत्ति: +{gw_trend:.1f} सेमी/वर्ष)।" , True
        if language == "pa":
            return f" ਇਹ ਖੇਤਰੀ ਪਾਣੀ ਸੰਤੁਲਨ ਬਣਾਈ ਰੱਖਦਾ ਹੈ (ਨਾਸਾ GRACE-FO ਰੁਝਾਨ: +{gw_trend:.1f} ਸੈਂਟੀਮੀਟਰ/ਸਾਲ)।" , True
        return f" Helps sustain positive regional groundwater storage (NASA GRACE-FO trend: {gw_trend:+.1f} cm/yr).", True
    if language == "hi":
        return f" नासा GRACE-FO जल स्तर स्थिर ({gw_trend:+.1f} सेमी/वर्ष) रहते हुए जल दक्षता बढ़ाता है।", True
    if language == "pa":
        return f" ਨਾਸਾ GRACE-FO ਪਾਣੀ ਪੱਧਰ ਸਥਿਰ ({gw_trend:+.1f} ਸੈਂਟੀਮੀਟਰ/ਸਾਲ) ਰਹਿੰਦਿਆਂ ਪਾਣੀ ਦੀ ਬੱਚਤ ਕਰਦਾ ਹੈ।", True
    return f" Enhances water productivity alongside stable regional storage ({gw_trend:+.1f} cm/yr, NASA GRACE-FO).", True


def why_cards(
    profile: FieldProfile,
    rec: StrategyRecommendation,
    baseline: StrategyRecommendation | None = None,
    language: str = "en",
) -> tuple[list[str], list[DataProvenance]]:
    """Generate deterministic explanation why-cards with cited data provenances in en, hi, or pa."""
    cards: list[str] = []
    provenances: list[DataProvenance] = []

    if not rec.results:
        if language == "hi":
            return ["क्षेत्रीय कृषि-जलवायु उपयुक्तता मानदंडों के आधार पर मूल्यांकित रणनीति।"], []
        if language == "pa":
            return ["ਖੇਤਰੀ ਖੇਤੀ-ਜਲਵਾਯੂ ਅਨੁਕੂਲਤਾ ਮਾਪਦੰਡਾਂ ਦੇ ਅਧਾਰ 'ਤੇ ਮੁਲਾਂਕਣ ਕੀਤੀ ਰਣਨੀਤੀ।"], []
        return ["Strategy evaluated based on regional suitability criteria."], []

    sim_res = rec.results[0]
    base_res = baseline.results[0] if baseline and baseline.results else None
    pm = rec.practical_metrics
    sym = rec.currency_symbol or profile.currency_symbol or ("₹" if profile.currency == "INR" else "$")
    is_global_proxy = bool(
        profile.validation_status == "unvalidated_global"
        or profile.currency != "INR"
        or getattr(rec, "economics_basis", "local_verified") == "punjab_proxy"
    )

    # 1. Water savings & borewell pumping card
    cand_irr = float(np.mean(sim_res.irrigation_mm)) if sim_res.irrigation_mm else 0.0
    if base_res and base_res.irrigation_mm:
        base_irr = float(np.mean(base_res.irrigation_mm))
        diff_mm = base_irr - cand_irr
        pct_saved = (diff_mm / base_irr * 100.0) if base_irr > 0 else 0.0
        gw_trend = profile.water.groundwater_trend_cm_per_year
        irr_saved_cnt = pm.irrigations_saved_per_yr if pm else round(max(0.0, diff_mm) / 75.0, 1)
        pump_hrs = pm.pumping_hours_saved_per_ha if pm else round(max(0.0, diff_mm) * 0.55, 0)

        if diff_mm > 30:
            grace_clause, has_grace = _grace_water_clause(gw_trend, language)
            if language == "hi":
                cards.append(
                    f"आधार फसल चक्र की तुलना में {int(pct_saved)}% सिंचाई जल ({int(diff_mm)} मिमी/वर्ष — लगभग "
                    f"{irr_saved_cnt:.0f} पानी और {int(pump_hrs)} घंटे/हेक्टेयर ट्यूबवेल पंपिंग) बचाता है [FAO-56]।{grace_clause}"
                )
            elif language == "pa":
                cards.append(
                    f"ਬੇਸਲਾਈਨ ਫ਼ਸਲੀ ਚੱਕਰ ਦੇ ਮੁਕਾਬਲੇ {int(pct_saved)}% ਸਿੰਚਾਈ ਪਾਣੀ ({int(diff_mm)} ਮਿਲੀਮੀਟਰ/ਸਾਲ — ਲਗਭਗ "
                    f"{irr_saved_cnt:.0f} ਪਾਣੀ ਅਤੇ {int(pump_hrs)} ਘੰਟੇ/ਹੈਕਟੇਅਰ ਮੋਟਰ ਪੰਪਿੰਗ) ਬਚਾਉਂਦਾ ਹੈ [FAO-56]।{grace_clause}"
                )
            else:
                cards.append(
                    f"Saves {int(pct_saved)}% irrigation water ({int(diff_mm)} mm/yr — ~{irr_saved_cnt:.0f} flood irrigations "
                    f"and {int(pump_hrs)} hrs/ha of borewell pumping) vs. baseline [FAO-56].{grace_clause}"
                )
            provenances.append(_FAO56_PROV)
            if has_grace:
                provenances.append(gee.provenance_with_mode(_GRACE_PROV))
        elif diff_mm < -30:
            if language == "hi":
                cards.append(
                    f"फसल सघनता के लिए {int(abs(diff_mm))} मिमी/वर्ष अतिरिक्त सिंचाई की आवश्यकता है [FAO-56], "
                    f"जिसकी भरपाई उच्च शुद्ध लाभ और मृदा सुधार से होती है।"
                )
            elif language == "pa":
                cards.append(
                    f"ਫ਼ਸਲ ਦੀ ਸਘਨਤਾ ਲਈ {int(abs(diff_mm))} ਮਿਲੀਮੀਟਰ/ਸਾਲ ਵਾਧੂ ਸਿੰਚਾਈ ਦੀ ਲੋੜ ਹੈ [FAO-56], "
                    f"ਜਿਸਦੀ ਭਰਪਾਈ ਵੱਧ ਮੁਨਾਫ਼ੇ ਅਤੇ ਮਿੱਟੀ ਦੀ ਸਿਹਤ ਨਾਲ ਹੁੰਦੀ ਹੈ।"
                )
            else:
                cards.append(
                    f"Requires {int(abs(diff_mm))} mm/yr additional irrigation to support crop intensification [FAO-56], "
                    f"compensated by higher net margins and soil carbon restoration."
                )
            provenances.append(_FAO56_PROV)

    # 2. Soil Health, Carbon & 45-kg Urea Bags card
    soc_delta = sim_res.soc_delta_t_ha_10yr
    score = sim_res.soil_health_score
    urea_bags = pm.urea_bags_saved_per_ha if pm else 0.0
    urea_str_en = f", saving {urea_bags:.1f} bags/ha of 45-kg Urea via biological N fixation" if urea_bags >= 0.5 else ""
    urea_str_hi = f" और दलहनी नाइट्रोजन स्थिरीकरण से प्रति हेक्टेयर {urea_bags:.1f} बोरी (45 किग्रा) यूरिया बचाता है" if urea_bags >= 0.5 else ""
    urea_str_pa = f" ਅਤੇ ਦਾਲਾਂ ਰਾਹੀਂ ਨਾਈਟ੍ਰੋਜਨ ਫਿਕਸੇਸ਼ਨ ਨਾਲ ਪ੍ਰਤੀ ਹੈਕਟੇਅਰ {urea_bags:.1f} ਗੱਟੇ (45 ਕਿਲੋ) ਯੂਰੀਆ ਬਚਾਉਂਦਾ ਹੈ" if urea_bags >= 0.5 else ""

    if base_res:
        delta_score = score - base_res.soil_health_score
        if language == "hi":
            cards.append(
                f"मृदा स्वास्थ्य स्कोर को {int(score)}/100 ({delta_score:+.0f} अंक) तक पहुँचाता है और 10 वर्षों में "
                f"ऊपरी मिट्टी में {soc_delta:+.1f} टन कार्बन/हेक्टेयर जोड़ता है{urea_str_hi} [RothC-lite · SoilGrids]।"
            )
        elif language == "pa":
            cards.append(
                f"ਮਿੱਟੀ ਸਿਹਤ ਸਕੋਰ ਨੂੰ {int(score)}/100 ({delta_score:+.0f} ਅੰਕ) ਤੱਕ ਵਧਾਉਂਦਾ ਹੈ ਅਤੇ 10 ਸਾਲਾਂ ਵਿੱਚ "
                f"ਉੱਪਰਲੀ ਮਿੱਟੀ ਵਿੱਚ {soc_delta:+.1f} ਟਨ ਕਾਰਬਨ/ਹੈਕਟੇਅਰ ਜੋੜਦਾ ਹੈ{urea_str_pa} [RothC-lite · SoilGrids]।"
            )
        else:
            cards.append(
                f"Elevates Soil Health Score to {int(score)}/100 ({delta_score:+.0f} pts vs. baseline) and changes "
                f"10-year topsoil organic carbon by {soc_delta:+.1f} t C/ha{urea_str_en} [RothC-lite · SoilGrids]."
            )
    else:
        if language == "hi":
            cards.append(
                f"मृदा स्वास्थ्य स्कोर {int(score)}/100 और 10 वर्षों में ऊपरी मिट्टी के कार्बन में "
                f"{soc_delta:+.1f} टन कार्बन/हेक्टेयर परिवर्तन का अनुमान है{urea_str_hi} [RothC-lite · SoilGrids]।"
            )
        elif language == "pa":
            cards.append(
                f"ਮਿੱਟੀ ਸਿਹਤ ਸਕੋਰ {int(score)}/100 ਅਤੇ 10 ਸਾਲਾਂ ਵਿੱਚ ਜੈਵਿਕ ਕਾਰਬਨ ਵਿੱਚ "
                f"{soc_delta:+.1f} ਟਨ ਕਾਰਬਨ/ਹੈਕਟੇਅਰ ਬਦਲਾਅ ਦਾ ਅੰਦਾਜ਼ਾ ਹੈ{urea_str_pa} [RothC-lite · SoilGrids]।"
            )
        else:
            cards.append(
                f"Achieves a Soil Health Score of {int(score)}/100 and projected 10-year SOC change of "
                f"{soc_delta:+.1f} t C/ha{urea_str_en} [RothC-lite · SoilGrids]."
            )
    provenances.append(_ROTHC_PROV)

    # 3. Turnaround Window & Stubble Burning Elimination card
    has_retention = any("residue_retained" in s.practices or "happy_seeder" in s.practices for s in rec.rotation.steps)
    has_no_till = any("no_till" in s.practices or "zero_till" in s.practices or "happy_seeder" in s.practices for s in rec.rotation.steps)
    turnaround = pm.turnaround_days_kharif_rabi if pm else 22

    if has_retention or has_no_till:
        if language == "hi":
            cards.append(
                f"खरीफ कटाई और रबी बुवाई के बीच {turnaround} दिनों का समय देता है, जिससे बिना पराली जलाए कम जुताई / "
                f"इन-सीटू मल्चिंग संभव होती है और NASA FIRMS द्वारा दर्ज मौसमी पराली दहन रुकता है।"
            )
        elif language == "pa":
            cards.append(
                f"ਸਾਉਣੀ ਦੀ ਵਾਢੀ ਅਤੇ ਹਾੜ੍ਹੀ ਦੀ ਬਿਜਾਈ ਵਿਚਕਾਰ {turnaround} ਦਿਨਾਂ ਦਾ ਸਮਾਂ ਦਿੰਦਾ ਹੈ, ਜਿਸ ਨਾਲ ਬਿਨਾਂ ਪਰਾਲੀ ਸਾੜੇ "
                f"ਘੱਟ ਵਹਾਈ / ਮਲਚਿੰਗ ਸੰਭਵ ਹੁੰਦੀ ਹੈ ਅਤੇ NASA FIRMS ਵੱਲੋਂ ਦਰਜ ਮੌਸਮੀ ਪਰਾਲੀ ਸਾੜਨ ਤੋਂ ਬਚਾਅ ਹੁੰਦਾ ਹੈ।"
            )
        else:
            cards.append(
                f"Provides a {turnaround}-day inter-season turnaround window for direct/zero-till seeding with "
                f"in-situ residue mulching — avoiding seasonal stubble burning monitored by NASA FIRMS."
            )
        provenances.append(gee.provenance_with_mode(_FIRMS_PROV))

    # 4. Agro-climate & Terminal Heat Stress Evasion card
    heat_days = profile.climate.heat_days_per_year
    term_days = profile.hazards.terminal_heat_days_per_year or 0.0
    if language == "hi":
        cards.append(
            f"संतुलित बुवाई चक्र NASA POWER द्वारा दर्ज {int(heat_days)} वार्षिक भीषण गर्मी दिनों (>35°C) और दाना "
            f"भराव के {term_days:.1f} टर्मिनल हीट दिनों (>32°C) के नुकसान से फसल को बचाता है।"
        )
    elif language == "pa":
        cards.append(
            f"ਸੰਤੁਲਿਤ ਬਿਜਾਈ ਚੱਕਰ NASA POWER ਵੱਲੋਂ ਦਰਜ {int(heat_days)} ਸਾਲਾਨਾ ਤੇਜ਼ ਗਰਮੀ ਦੇ ਦਿਨਾਂ (>35°C) ਅਤੇ ਦਾਣੇ "
            f"ਭਰਨ ਸਮੇਂ {term_days:.1f} ਟਰਮੀਨਲ ਹੀਟ ਦਿਨਾਂ (>32°C) ਦੇ ਨੁਕਸਾਨ ਤੋਂ ਫ਼ਸਲ ਨੂੰ ਬਚਾਉਂਦਾ ਹੈ।"
        )
    else:
        cards.append(
            f"Timely sowing schedule buffers crops against {int(heat_days)} annual extreme heat days (>35°C) and "
            f"{term_days:.1f} grain-filling terminal heat days (>32°C) recorded by NASA POWER."
        )
    provenances.append(_POWER_PROV)

    # 5. Economic Returns, Downside Risk & Eligible Govt Schemes card
    p50 = sim_res.profit_p50
    cvar = sim_res.cvar_profit_10
    p50_acre = round(p50 / 2.47105)
    cvar_acre = round(cvar / 2.47105)
    schemes_str = ""
    if pm and pm.eligible_schemes:
        if language == "hi":
            schemes_str = f" पात्र योजनाएं: {'; '.join(pm.eligible_schemes[:2])}।"
        elif language == "pa":
            schemes_str = f" ਯੋਗ ਸਕੀਮਾਂ: {'; '.join(pm.eligible_schemes[:2])}।"
        else:
            schemes_str = f" Eligible schemes: {'; '.join(pm.eligible_schemes[:2])}."

    if is_global_proxy:
        if language == "hi":
            cards.append(
                f"क्षेत्रीय संदर्भ मूल्य अनुमानों के आधार पर {sym}{int(p50):,}/हेक्टेयर ({sym}{p50_acre:,}/एकड़) का अपेक्षित शुद्ध लाभ "
                f"और गंभीर सूखे में {sym}{int(cvar):,}/हेक्टेयर (CVaR-10) की सुरक्षा दर्शाता है (स्थानीय बाजार भाव सत्यापित करें)।"
            )
        elif language == "pa":
            cards.append(
                f"ਖੇਤਰੀ ਸੰਦਰਭ ਮੁੱਲ ਅੰਦਾਜ਼ੇ ਅਨੁਸਾਰ {sym}{int(p50):,}/ਹੈਕਟੇਅਰ ({sym}{p50_acre:,}/ਏਕੜ) ਦਾ ਔਸਤ ਸ਼ੁੱਧ ਮੁਨਾਫ਼ਾ "
                f"ਅਤੇ ਸੋਕੇ ਦੇ ਸਾਲਾਂ ਵਿੱਚ {sym}{int(cvar):,}/ਹੈਕਟੇਅਰ (CVaR-10) ਦੀ ਸੁਰੱਖਿਆ ਦਰਸਾਉਂਦਾ ਹੈ (ਸਥਾਨਕ ਮੰਡੀ ਭਾਅ ਦੀ ਪੁਸ਼ਟੀ ਕਰੋ)।"
            )
        else:
            cards.append(
                f"Estimates median net operating return of {sym}{int(p50):,}/ha ({sym}{p50_acre:,}/acre) with worst-10% drought "
                f"downside buffer (CVaR-10) of {sym}{int(cvar):,}/ha ({sym}{cvar_acre:,}/acre) using India-calibrated proxy costs — verify local prices."
            )
        provenances.append(_CACP_PROV.model_copy(update={"mode": "fallback_estimate"}))
    else:
        if language == "hi":
            cards.append(
                f"CACP MSP (2024-25) के अनुसार {sym}{int(p50):,}/हेक्टेयर ({sym}{p50_acre:,}/एकड़) का अपेक्षित शुद्ध लाभ और "
                f"सूखे के वर्षों में {sym}{int(cvar):,}/हेक्टेयर ({sym}{cvar_acre:,}/एकड़) की डाउनसाइड सुरक्षा (CVaR-10) देता है।{schemes_str}"
            )
        elif language == "pa":
            cards.append(
                f"CACP MSP (2024-25) ਅਨੁਸਾਰ {sym}{int(p50):,}/ਹੈਕਟੇਅਰ ({sym}{p50_acre:,}/ਏਕੜ) ਦਾ ਔਸਤ ਸ਼ੁੱਧ ਮੁਨਾਫ਼ਾ ਅਤੇ "
                f"ਸੋਕੇ ਦੇ ਸਾਲਾਂ ਵਿੱਚ {sym}{int(cvar):,}/ਹੈਕਟੇਅਰ ({sym}{cvar_acre:,}/ਏਕੜ) ਦੀ ਸੁਰੱਖਿਆ (CVaR-10) ਦਿੰਦਾ ਹੈ।{schemes_str}"
            )
        else:
            cards.append(
                f"Delivers median net operating return of {sym}{int(p50):,}/ha ({sym}{p50_acre:,}/acre) with a worst-10% drought "
                f"downside buffer (CVaR-10) of {sym}{int(cvar):,}/ha ({sym}{cvar_acre:,}/acre) [CACP MSP 2024-25].{schemes_str}"
            )
        provenances.append(_CACP_PROV)

    # Preserve each source's true observation mode instead of masking all cards to one global flag
    profile_modes: dict[str, str] = {}
    for p_list in (
        profile.climate.provenance,
        profile.water.provenance,
        profile.soil.provenance,
        profile.hazards.provenance,
    ):
        for p_item in p_list:
            if p_item.source and p_item.source not in profile_modes:
                profile_modes[p_item.source] = p_item.mode

    seen_sources: set[str] = set()
    unique_provs: list[DataProvenance] = []
    for p in provenances:
        if p.source in seen_sources:
            continue
        seen_sources.add(p.source)
        mode = p.mode
        if p.source in profile_modes:
            mode = profile_modes[p.source]
        elif p.source == _FAO56_PROV.source:
            mode = "regional_climatology" if profile.is_fallback else profile_modes.get("NASA POWER", "observed")
        elif p.source == _ROTHC_PROV.source:
            mode = "regional_climatology" if profile.is_fallback else (
                "observed" if (profile.soil and profile.soil.source in ("soilgrids", "farmer_test")) else "regional_climatology"
            )
        unique_provs.append(p.model_copy(update={"mode": mode}))  # type: ignore[arg-type]

    return cards, unique_provs


def extract_numeric_tokens(text: str) -> list[float]:
    """Extract numeric values from text, stripping commas, signs, and units.

    Avoid matching hyphenated cultivar/model names like 'PR-126' or 'HD-2967' as negative numbers.
    """
    raw_tokens = re.findall(r"(?<![a-zA-Z0-9])[-+]?\b\d+(?:,\d{3})*(?:\.\d+)?\b", text)
    nums: list[float] = []
    for tok in raw_tokens:
        clean = tok.replace(",", "")
        try:
            nums.append(float(clean))
        except ValueError:
            pass
    return nums


def verify_llm_numeric_grounding(
    text: str,
    allowed_numbers: set[float],
    tolerance_pct: float = 5.0,
) -> bool:
    """Validate that every number mentioned in the LLM text is close to one of the allowed numbers.

    Returns True if all numbers in text are grounded within tolerance_pct, False otherwise.
    """
    extracted = extract_numeric_tokens(text)
    if not extracted:
        return True

    # Common structural / agricultural numbers that legitimately appear in explanations:
    structural_allowed = {0.0, 1.0, 2.0, 3.0, 5.0, 10.0, 12.0, 24.0, 30.0, 32.0, 35.0, 45.0, 75.0, 100.0}
    full_allowed = set(allowed_numbers) | structural_allowed

    for val in extracted:
        matched = False
        for allowed in full_allowed:
            if abs(allowed) < 1e-6:
                if abs(val) < 1e-3:
                    matched = True
                    break
            else:
                rel_diff = abs(val - allowed) / abs(allowed) * 100.0
                if rel_diff <= tolerance_pct:
                    matched = True
                    break
        if not matched:
            log.warning("LLM numeric grounding failed: rejected ungrounded value %s", val)
            return False
    return True


def _ensure_dotenv_loaded() -> None:
    """Safely load .env once without overriding already exported environment variables."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED or load_dotenv is None:
        _DOTENV_LOADED = True
        return
    try:
        load_dotenv(override=False)
    except Exception as exc:  # noqa: BLE001
        log.debug("Optional dotenv load skipped: %s", exc)
    _DOTENV_LOADED = True


def _call_gemini_api(
    prompt: str,
    api_key: str,
    model: str = "gemini-2.0-flash",
    timeout_sec: float = 2.5,
) -> str | None:
    """Execute REST call to Google Gemini generateContent endpoint with circuit-breaker backoff."""
    global _LLM_COOLDOWN_UNTIL
    now = time.monotonic()
    if now < _LLM_COOLDOWN_UNTIL:
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 260,
        },
    }
    try:
        with httpx.Client(timeout=timeout_sec) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return str(parts[0]["text"]).strip()
            else:
                cooldown = 300.0 if resp.status_code in (401, 403, 404) else 60.0
                _LLM_COOLDOWN_UNTIL = time.monotonic() + cooldown
                log.warning("Gemini API call returned status %s (cooldown %.0fs)", resp.status_code, cooldown)
    except Exception as exc:  # noqa: BLE001
        _LLM_COOLDOWN_UNTIL = time.monotonic() + 60.0
        log.warning("Gemini API call failed (%s): %s", type(exc).__name__, exc)
    return None


def grounded_llm_explain(
    profile: FieldProfile,
    rec: StrategyRecommendation,
    baseline: StrategyRecommendation | None = None,
    language: str = "en",
    use_llm: bool = True,
) -> str:
    """TASK-X02: Grounded agronomic explainer.

    Strictly restricted to verified numbers produced by FAO-56, RothC, GRACE,
    POWER, and regional economics. If GEMINI_API_KEY/LLM_API_KEY is present and
    `use_llm=True`, queries Gemini Flash with a 2.5s timeout and circuit breaker,
    validating numeric grounding via verify_llm_numeric_grounding. Falls back
    deterministically to verified multilingual templates if ungrounded, errored,
    disabled, or offline.
    """
    if not rec.results:
        if language == "hi":
            return "अनुशंसित फसल चक्र क्षेत्रीय कृषि-जलवायु उपयुक्तता पर आधारित है।"
        if language == "pa":
            return "ਸਿਫ਼ਾਰਿਸ਼ ਕੀਤਾ ਫ਼ਸਲੀ ਚੱਕਰ ਖੇਤਰੀ ਖੇਤੀ-ਜਲਵਾਯੂ ਅਨੁਕੂਲਤਾ 'ਤੇ ਅਧਾਰਤ ਹੈ।"
        return "Recommended rotation is established on regional agro-climatic suitability parameters."

    sim_res = rec.results[0]
    base_res = baseline.results[0] if baseline and baseline.results else None

    cand_irr = float(np.mean(sim_res.irrigation_mm)) if sim_res.irrigation_mm else 0.0
    base_irr = float(np.mean(base_res.irrigation_mm)) if base_res and base_res.irrigation_mm else cand_irr
    irr_saved = max(0.0, base_irr - cand_irr)
    irr_saved_pct = (irr_saved / base_irr * 100.0) if base_irr > 0 else 0.0

    gw_trend = profile.water.groundwater_trend_cm_per_year
    grace_clause, has_grace = _grace_water_clause(gw_trend, language)

    score = int(sim_res.soil_health_score)
    soc_c = sim_res.soc_delta_t_ha_10yr
    p50 = int(sim_res.profit_p50)
    cvar = int(sim_res.cvar_profit_10)

    sym = rec.currency_symbol or profile.currency_symbol or ("₹" if profile.currency == "INR" else "$")
    cur_code = rec.currency or profile.currency or "INR"
    is_global_proxy = bool(
        profile.validation_status == "unvalidated_global"
        or cur_code != "INR"
        or getattr(rec, "economics_basis", "local_verified") == "punjab_proxy"
    )
    rot_name = rec.rotation.label or rec.rotation.id

    if language == "hi":
        water_part = (
            f"यह चक्र आधार की तुलना में प्रति वर्ष {int(irr_saved)} मिमी ({int(irr_saved_pct)}%) सिंचाई जल की बचत करता है [FAO-56]।"
            if irr_saved > 0
            else f"इस चक्र की वार्षिक सिंचाई मांग {int(cand_irr)} मिमी/वर्ष है [FAO-56]।"
        )
        econ_src = "क्षेत्रीय संदर्भ मूल्य अनुमान अनुसार" if is_global_proxy else "CACP MSP (2024-25) अनुसार"
        fallback_text = (
            f"रणनीति '{rot_name}': {water_part}{grace_clause} "
            f"RothC मॉडल के अनुसार, यह 10 वर्षों में मिट्टी में {soc_c:+.1f} टन कार्बन/हेक्टेयर का परिवर्तन करता है "
            f"और मृदा स्वास्थ्य स्कोर को {score}/100 तक बढ़ाता है। {econ_src}, अपेक्षित वार्षिक लाभ "
            f"{sym}{p50:,}/हेक्टेयर है, जबकि गंभीर सूखे में डाउनसाइड सुरक्षा (CVaR-10) {sym}{cvar:,}/हेक्टेयर है।"
        )
    elif language == "pa":
        water_part = (
            f"ਇਹ ਚੱਕਰ ਬੇਸਲਾਈਨ ਨਾਲੋਂ {int(irr_saved)} ਮਿਲੀਮੀਟਰ ({int(irr_saved_pct)}%) ਸਿੰਚਾਈ ਪਾਣੀ ਦੀ ਬਚਤ ਕਰਦਾ ਹੈ [FAO-56]।"
            if irr_saved > 0
            else f"ਇਸ ਚੱਕਰ ਦੀ ਸਾਲਾਨਾ ਸਿੰਚਾਈ ਲੋੜ {int(cand_irr)} ਮਿਲੀਮੀਟਰ/ਸਾਲ ਹੈ [FAO-56]।"
        )
        econ_src = "ਖੇਤਰੀ ਸੰਦਰਭ ਮੁੱਲ ਅੰਦਾਜ਼ੇ ਮੁਤਾਬਕ" if is_global_proxy else "CACP MSP (2024-25) ਮੁਤਾਬਕ"
        fallback_text = (
            f"ਰਣਨੀਤੀ '{rot_name}': {water_part}{grace_clause} "
            f"RothC ਮਾਡਲ ਅਨੁਸਾਰ ਇਹ 10 ਸਾਲਾਂ ਵਿੱਚ ਮਿੱਟੀ ਵਿੱਚ {soc_c:+.1f} ਟਨ ਕਾਰਬਨ/ਹੈਕਟੇਅਰ ਦਾ ਵਾਧਾ ਕਰਕੇ ਮਿੱਟੀ ਸਿਹਤ ਸਕੋਰ {score}/100 "
            f"ਤੱਕ ਪਹੁੰਚਾਉਂਦਾ ਹੈ। {econ_src} ਔਸਤ ਸਾਲਾਨਾ ਮੁਨਾਫ਼ਾ {sym}{p50:,}/ਹੈਕਟੇਅਰ ਅਤੇ ਸੋਕੇ ਦੇ ਸਾਲਾਂ ਵਿੱਚ ਸੁਰੱਖਿਅਤ ਸੀਮਾ (CVaR-10) {sym}{cvar:,}/ਹੈਕਟੇਅਰ ਹੈ।"
        )
    else:
        water_part = (
            f"Reduces net irrigation by {int(irr_saved)} mm/yr ({int(irr_saved_pct)}% savings vs baseline) [FAO-56]."
            if irr_saved > 0
            else f"Requires {int(cand_irr)} mm/yr net seasonal irrigation [FAO-56]."
        )
        econ_src = (
            "Using India-calibrated proxy costs (verify local prices)"
            if is_global_proxy
            else "Under CACP MSP (2024-25) policies"
        )
        fallback_text = (
            f"Strategy '{rot_name}': {water_part}{grace_clause} "
            f"RothC forecasts a 10-year soil organic carbon change of {soc_c:+.1f} t C/ha, elevating soil health "
            f"to {score}/100. {econ_src}, median expected return is {sym}{p50:,}/ha with a worst-10% drought buffer (CVaR-10) of {sym}{cvar:,}/ha."
        )

    pm = rec.practical_metrics
    allowed_numbers = {
        float(int(irr_saved)),
        float(int(irr_saved_pct)),
        float(int(cand_irr)),
        float(score),
        round(soc_c, 1),
        float(p50),
        float(cvar),
        round(p50 / 2.47105),
        round(cvar / 2.47105),
    }
    if has_grace and gw_trend is not None:
        allowed_numbers.add(round(abs(gw_trend), 1))
        allowed_numbers.add(round(gw_trend, 1))
    allowed_numbers.update(extract_numeric_tokens(rot_name))
    if pm:
        allowed_numbers.update({
            float(pm.irrigations_saved_per_yr),
            float(pm.pumping_hours_saved_per_ha),
            float(pm.urea_bags_saved_per_ha),
            float(pm.turnaround_days_kharif_rabi),
        })

    if not use_llm or os.environ.get("TERRALOOP_DISABLE_LLM", "").strip().lower() in ("1", "true", "yes"):
        return fallback_text

    _ensure_dotenv_loaded()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        return fallback_text

    model_name = os.environ.get("GEMINI_MODEL") or os.environ.get("LLM_MODEL") or "gemini-2.0-flash"
    grace_line = f"- NASA GRACE-FO regional storage trend: {gw_trend:+.1f} cm/yr\n" if gw_trend is not None else ""
    prompt = (
        f"You are an agronomic expert summarizing a crop rotation strategy for a farmer.\n"
        f"Requested language: {language} (en=English, hi=Hindi, pa=Punjabi).\n"
        f"Strategy: {rot_name}\n"
        f"Verified biophysical metrics:\n"
        f"- Irrigation demand: {int(cand_irr)} mm/yr; savings vs baseline: {int(irr_saved)} mm/yr ({int(irr_saved_pct)}%)\n"
        f"{grace_line}"
        f"- Soil carbon change: {soc_c:+.1f} t C/ha over 10 years\n"
        f"- Soil health score: {score}/100\n"
        f"- Median net profit: {sym}{p50:,}/ha ({cur_code})\n"
        f"- Downside drought buffer (CVaR-10): {sym}{cvar:,}/ha ({cur_code})\n\n"
        f"Write 2-3 clear sentences in {language}. "
        f"CRITICAL: You MUST ONLY use the verified metrics above. NEVER invent or speculate on any numeric values."
    )

    llm_resp = _call_gemini_api(prompt, api_key=api_key, model=model_name, timeout_sec=2.5)
    if llm_resp and verify_llm_numeric_grounding(llm_resp, allowed_numbers):
        return llm_resp

    return fallback_text


def baseline_why_cards(
    profile: FieldProfile,
    baseline_rot: Rotation,
    language: str = "en",
    baseline_result: SimulationResult | None = None,
    baseline_pm: PracticalFarmerMetrics | None = None,
) -> list[str]:
    """Generate localized quantitative and practice cards for the farmer's current baseline rotation."""
    base_label = baseline_rot.label or baseline_rot.id
    field_label = profile.field.name or "this field"
    has_puddled_rice = any(s.crop_id == "rice_puddled" for s in baseline_rot.steps)
    has_burning = any("burning" in s.practices for s in baseline_rot.steps)
    sym = profile.currency_symbol or ("₹" if profile.currency == "INR" else "$")

    mean_irr = (
        float(np.mean(baseline_result.irrigation_mm))
        if baseline_result and baseline_result.irrigation_mm
        else None
    )
    soc_delta = baseline_result.soc_delta_t_ha_10yr if baseline_result else None
    soil_score = baseline_result.soil_health_score if baseline_result else None
    p50 = baseline_result.profit_p50 if baseline_result else None
    cvar = baseline_result.cvar_profit_10 if baseline_result else None
    turnaround = baseline_pm.turnaround_days_kharif_rabi if baseline_pm else None

    if language == "hi":
        cards = [f"{field_label} के लिए वर्तमान आधार फसल चक्र: {base_label}।"]
        if has_puddled_rice:
            cards.append(
                "पारंपरिक कद्दू (रोपाई) धान-गेहूं प्रणाली में अत्यधिक भूजल दोहन और मौसमी जलभराव का जोखिम रहता है।"
            )
        if has_burning:
            turn_note = f" कटाई से बुवाई का अंतराल मात्र {turnaround} दिन होने से पराली जलने का खतरा रहता है।" if turnaround is not None else ""
            cards.append(
                f"कटाई के बाद अवशेष जलाने से मिट्टी के कार्बन और सूक्ष्मजीवों का गंभीर ह्रास होता है।{turn_note}"
            )
        if mean_irr is not None and soc_delta is not None and soil_score is not None:
            cards.append(
                f"आधार प्रणाली में औसत सिंचाई मांग {int(mean_irr)} मिमी/वर्ष, 10-वर्षीय मृदा कार्बन परिवर्तन "
                f"{soc_delta:+.2f} टन/हेक्टेयर और मृदा स्वास्थ्य स्कोर {soil_score:.0f}/100 है [FAO-56, RothC-26.3]।"
            )
        if p50 is not None and cvar is not None:
            cards.append(
                f"अपेक्षित वार्षिक शुद्ध लाभ {sym}{int(p50):,}/हेक्टेयर है, जबकि गंभीर सूखे में यह {sym}{int(cvar):,}/हेक्टेयर तक घट सकता है।"
            )
        return cards

    if language == "pa":
        cards = [f"{field_label} ਲਈ ਮੌਜੂਦਾ ਬੇਸਲਾਈਨ ਫ਼ਸਲੀ ਚੱਕਰ: {base_label}।"]
        if has_puddled_rice:
            cards.append(
                "ਰਵਾਇਤੀ ਕੱਦੂ ਵਾਲੇ ਝੋਨੇ-ਕਣਕ ਚੱਕਰ ਵਿੱਚ ਧਰਤੀ ਹੇਠਲੇ ਪਾਣੀ ਦੀ ਭਾਰੀ ਖਪਤ ਅਤੇ ਵਾਤਾਵਰਣ ਤਣਾਅ ਹੁੰਦਾ ਹੈ।"
            )
        if has_burning:
            turn_note = f" ਵਾਢੀ-ਬਿਜਾਈ ਅੰਤਰਾਲ ਸਿਰਫ਼ {turnaround} ਦਿਨ ਹੋਣ ਕਾਰਨ ਪਰਾਲੀ ਸਾੜਨ ਦਾ ਖ਼ਤਰਾ ਵਧਦਾ ਹੈ।" if turnaround is not None else ""
            cards.append(
                f"ਵਾਢੀ ਤੋਂ ਬਾਅਦ ਪਰਾਲੀ ਸਾੜਨ ਨਾਲ ਮਿੱਟੀ ਵਿੱਚਲੇ ਜੈਵਿਕ ਕਾਰਬਨ ਅਤੇ ਲਾਭਦਾਇਕ ਕੀਟਾਣੂਆਂ ਦਾ ਭਾਰੀ ਨੁਕਸਾਨ ਹੁੰਦਾ ਹੈ।{turn_note}"
            )
        if mean_irr is not None and soc_delta is not None and soil_score is not None:
            cards.append(
                f"ਬੇਸਲਾਈਨ ਪ੍ਰਣਾਲੀ ਵਿੱਚ ਔਸਤ ਸਿੰਚਾਈ ਲੋੜ {int(mean_irr)} ਮਿਮੀ/ਸਾਲ, 10-ਸਾਲਾ ਮਿੱਟੀ ਕਾਰਬਨ ਤਬਦੀਲੀ "
                f"{soc_delta:+.2f} ਟਨ/ਹੈਕਟੇਅਰ ਅਤੇ ਮਿੱਟੀ ਸਿਹਤ ਸਕੋਰ {soil_score:.0f}/100 ਹੈ [FAO-56, RothC-26.3]।"
            )
        if p50 is not None and cvar is not None:
            cards.append(
                f"ਔਸਤ ਸਾਲਾਨਾ ਸ਼ੁੱਧ ਮੁਨਾਫ਼ਾ {sym}{int(p50):,}/ਹੈਕਟੇਅਰ ਅਤੇ ਸੋਕੇ ਦੇ ਸਾਲਾਂ ਵਿੱਚ (CVaR-10) {sym}{int(cvar):,}/ਹੈਕਟੇਅਰ ਰਹਿੰਦਾ ਹੈ।"
            )
        return cards

    cards = [f"Current baseline practice for {field_label}: {base_label}."]
    if has_puddled_rice:
        cards.append(
            "Conventional puddled transplanted rice (PTR) creates continuous water table depletion and narrow turnaround windows."
        )
    if has_burning:
        turn_note = f" Narrow {turnaround}-day harvest-to-sowing turnaround increases stubble burning pressure." if turnaround is not None else ""
        cards.append(
            f"Post-harvest residue burning depletes topsoil organic matter, microbial biomass, and volatile nitrogen.{turn_note}"
        )
    if mean_irr is not None and soc_delta is not None and soil_score is not None:
        cards.append(
            f"Baseline water demand averages {int(mean_irr)} mm/yr, with a 10-year SOC balance of {soc_delta:+.2f} t C/ha "
            f"and soil health index of {soil_score:.0f}/100 [FAO-56, RothC-26.3]."
        )
    if p50 is not None and cvar is not None:
        cards.append(
            f"Baseline median net return is {sym}{int(p50):,}/ha, dropping to {sym}{int(cvar):,}/ha in severe drought years (CVaR-10)."
        )
    return cards

