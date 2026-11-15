"""Field Profiler: builds a ``FieldProfile`` for an Indian field location.

Implemented sources : NASA POWER (climate), ISRIC SoilGrids (soil), GEE / Regional Climatology
                      (SMAP, GRACE-FO, IMERG, FIRMS, NASADEM, HLS crop history), and
                      Indian Government Soil Health Card (SHC) lab test overrides.
Failures in optional sources must NOT break the profile (log + leave None or regional climatology).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import date, timedelta

import numpy as np
import pandas as pd
from terraloop_schemas import (
    CalendarSlotSpec,
    ClimateSummary,
    DataProvenance,
    FieldGeometry,
    FieldProfile,
    HazardSummary,
    SoilHealthCardInput,
    SoilSummary,
    WaterSummary,
)

from .data import gee, meteomatics, nasa_power, soilgrids
from .eo import phenology
from .models import agroclimate, rusle, soil

log = logging.getLogger(__name__)

BASELINE = (1985, 2004)
RECENT = (2005, 2024)
HEAT_THRESHOLD_C = 35.0
FROST_THRESHOLD_C = 0.0
EXTREME_RAIN_MM = 50.0

# Trend notes enabled with TASK-D11 data validation safeguard
TREND_NOTES_ENABLED = True


# ---------------------------------------------------------------------------
# Climate (NASA POWER)
# ---------------------------------------------------------------------------
def summarise_climate(
    df: pd.DataFrame,
    lat: float,
    prov_mode: str = "observed",
    imerg_precip: pd.Series | None = None,
    imerg_prov: DataProvenance | None = None,
    lon: float | None = None,
    bias_corrected: bool | None = None,
) -> tuple[ClimateSummary, HazardSummary, float]:
    """Compute climate + hazard indicators from a daily POWER DataFrame (+ optional GPM IMERG V07 series).

    Returns (climate, hazards, annual climatic water balance P-ET0 in mm).
    Pure function: easy to unit-test with synthetic data.
    """
    if bias_corrected is None:
        if lon is not None:
            from . import region_registry

            reg_cfg = region_registry.detect_region_config(lat, lon)
            bias_corrected = bool(reg_cfg.igp_merra2_bias_correction)
        else:
            bias_corrected = False
    df = df.copy()
    has_valid_et0 = (
        "ET0" in df.columns
        and pd.to_numeric(df["ET0"], errors="coerce").notna().all()
        and (pd.to_numeric(df["ET0"], errors="coerce") >= 0.0).all()
        and (pd.to_numeric(df["ET0"], errors="coerce") <= 20.0).all()
    )
    if has_valid_et0:
        df["ET0"] = pd.to_numeric(df["ET0"], errors="coerce").astype(float)
    else:
        has_pm = (
            {"ALLSKY_SFC_SW_DWN", "RH2M", "WS2M"}.issubset(df.columns)
            and df["ALLSKY_SFC_SW_DWN"].notna().mean() > 0.5
            and df["RH2M"].notna().mean() > 0.5
            and df["WS2M"].notna().mean() > 0.5
        )
        if has_pm:
            pm_et0 = agroclimate.et0_penman_monteith_series(
                df["T2M_MAX"],
                df["T2M_MIN"],
                lat,
                rs_mj_m2_day=df["ALLSKY_SFC_SW_DWN"],
                rh_mean_pct=df["RH2M"],
                wind_m_s=df["WS2M"],
            )
            if "ET0" in df.columns:
                existing_et0 = pd.to_numeric(df["ET0"], errors="coerce")
                valid_mask = existing_et0.notna() & (existing_et0 >= 0.0) & (existing_et0 <= 20.0)
                df["ET0"] = existing_et0.where(valid_mask, pm_et0)
            else:
                df["ET0"] = pm_et0
        else:
            hg_et0 = agroclimate.et0_hargreaves(df["T2M_MAX"], df["T2M_MIN"], lat)
            if "ET0" in df.columns:
                existing_et0 = pd.to_numeric(df["ET0"], errors="coerce")
                valid_mask = existing_et0.notna() & (existing_et0 >= 0.0) & (existing_et0 <= 20.0)
                df["ET0"] = existing_et0.where(valid_mask, hg_et0)
            else:
                df["ET0"] = hg_et0
    df["GDD10"] = agroclimate.gdd(df["T2M_MAX"], df["T2M_MIN"], base=10.0)

    years = df.index.year
    base = df[(years >= BASELINE[0]) & (years <= BASELINE[1])]
    recent = df[(years >= RECENT[0]) & (years <= RECENT[1])]
    if base.empty:
        base = df
    if recent.empty:
        recent = df

    def per_year(frame: pd.DataFrame, mask: pd.Series) -> float:
        return float(mask.groupby(frame.index.year).sum().mean())

    def annual_sum(frame: pd.DataFrame, col: str) -> float:
        return float(frame[col].groupby(frame.index.year).sum().mean())

    # TASK-D11: Use homogeneous satellite-gauge GPM IMERG era (2001+) for rainfall statistics
    # and rainfall trend so pre-2001 MERRA-2 gauge inhomogeneity does not skew trends.
    if (years >= 2001).any() and (years <= 2000).any():
        p_series = df.loc[years >= 2001, "PRECTOTCORR"].copy()
    else:
        p_series = df["PRECTOTCORR"].copy()

    if imerg_precip is not None and not imerg_precip.empty:
        im_s = imerg_precip.copy()
        if not isinstance(im_s.index, pd.DatetimeIndex):
            im_s.index = pd.to_datetime(im_s.index)
        im_s.index = im_s.index.floor("D")
        if len(im_s) >= 0.7 * len(p_series):
            p_series = im_s
        else:
            common_idx = p_series.index.intersection(im_s.index)
            if len(common_idx) > 0:
                p_series.loc[common_idx] = im_s.loc[common_idx]

    p_years = p_series.index.year
    if (p_years >= 2001).all() and p_years.max() >= 2015:
        p_base = p_series[(p_years >= 2001) & (p_years <= 2012)]
        p_recent = p_series[(p_years >= 2013) & (p_years <= 2024)]
        if p_base.empty:
            p_base = p_series
        if p_recent.empty:
            p_recent = p_series
    else:
        p_base = p_series[(p_years >= BASELINE[0]) & (p_years <= BASELINE[1])]
        p_recent = p_series[(p_years >= RECENT[0]) & (p_years <= RECENT[1])]
        if p_base.empty:
            p_base = p_series
        if p_recent.empty:
            p_recent = p_series

    monthly_p = p_series.groupby([p_years, p_series.index.month]).sum().groupby(level=1).mean()
    monthly_tx = df["T2M_MAX"].groupby(df.index.month).mean()
    monthly_tn = df["T2M_MIN"].groupby(df.index.month).mean()
    monthly_p_list = [round(float(monthly_p.get(m, 0.0)), 1) for m in range(1, 13)]
    wet_months = agroclimate.wettest_window(monthly_p_list, length=4)

    annual_p_base = float(p_base.groupby(p_base.index.year).sum().mean())
    annual_p_recent = float(p_recent.groupby(p_recent.index.year).sum().mean())
    annual_p_all = float(p_series.groupby(p_years).sum().mean())
    annual_et0 = annual_sum(df, "ET0")

    yearly_p = p_series.groupby(p_years).sum()
    drought_freq = float((yearly_p < 0.8 * yearly_p.mean()).mean())
    heat_by_year = (df["T2M_MAX"] > HEAT_THRESHOLD_C).groupby(years).sum()

    # Terminal heat during wheat grain-fill (1 Mar - 15 Apr in NH, 1 Sep - 15 Oct in SH)
    if lat < 0:
        is_terminal = (df.index.month == 9) | ((df.index.month == 10) & (df.index.day <= 15))
    else:
        is_terminal = (df.index.month == 3) | ((df.index.month == 4) & (df.index.day <= 15))
    terminal_heat_per_yr = float((is_terminal & (df["T2M_MAX"] > 32.0)).groupby(years).sum().mean())

    power_prov = nasa_power.provenance(
        df.index.min().date(), df.index.max().date(), mode=prov_mode, bias_corrected=bias_corrected
    )
    clim_provs = [power_prov]
    if imerg_prov is not None:
        clim_provs.append(imerg_prov)

    climate = ClimateSummary(
        baseline_period=f"{base.index.year.min()}-{base.index.year.max()}",
        recent_period=f"{recent.index.year.min()}-{recent.index.year.max()}",
        mean_tmax_c=round(float(df["T2M_MAX"].mean()), 2),
        mean_tmin_c=round(float(df["T2M_MIN"].mean()), 2),
        annual_precip_mm=round(annual_p_base, 1),
        recent_annual_precip_mm=round(annual_p_recent, 1),
        precip_change_pct=round(100 * (annual_p_recent - annual_p_base) / max(annual_p_base, 1e-6), 1),
        tmax_change_c=round(float(recent["T2M_MAX"].mean() - base["T2M_MAX"].mean()), 2),
        heat_days_per_year=round(per_year(base, base["T2M_MAX"] > HEAT_THRESHOLD_C), 1),
        recent_heat_days_per_year=round(per_year(recent, recent["T2M_MAX"] > HEAT_THRESHOLD_C), 1),
        frost_days_per_year=round(per_year(df, df["T2M_MIN"] < FROST_THRESHOLD_C), 1),
        longest_dry_spell_days_mean=round(agroclimate.longest_dry_spell(df["PRECTOTCORR"], wet_months), 1),
        annual_et0_mm=round(annual_et0, 1),
        gdd_base10_per_year=round(annual_sum(df, "GDD10"), 0),
        monthly_precip_mm=monthly_p_list,
        monthly_tmax_c=[round(float(monthly_tx.get(m, np.nan)), 1) for m in range(1, 13)],
        monthly_tmin_c=[round(float(monthly_tn.get(m, np.nan)), 1) for m in range(1, 13)],
        wettest_months=wet_months,
        provenance=clim_provs,
    )

    hazards = HazardSummary(
        drought_frequency=round(drought_freq, 2),
        extreme_rain_days_per_year=round(per_year(df, df["PRECTOTCORR"] > EXTREME_RAIN_MM), 2),
        heat_stress_probability=round(float((heat_by_year >= 10).mean()), 2),
        frost_risk=round(float(((df["T2M_MIN"] < FROST_THRESHOLD_C).groupby(years).sum() > 0).mean()), 2),
        terminal_heat_days_per_year=round(terminal_heat_per_yr, 1),
        provenance=[power_prov],
    )
    return climate, hazards, round(annual_p_all - annual_et0, 1)


# ---------------------------------------------------------------------------
# Soil (SoilGrids & Regional Topsoil Fallbacks)
# ---------------------------------------------------------------------------
def regional_soil_fallback(lat: float, lon: float) -> dict[str, float]:
    """Return representative regional topsoil properties when ISRIC SoilGrids is offline."""
    from . import region_registry

    return region_registry.get_regional_soil(lat, lon)


def regional_indian_soil_fallback(lat: float, lon: float) -> dict[str, float]:
    """Backward-compatible alias for regional topsoil fallback."""
    return regional_soil_fallback(lat, lon)


def summarise_soil(
    props: dict[str, float] | None,
    prov_mode: str = "observed",
    is_india: bool = True,
) -> SoilSummary:
    if not props:
        return SoilSummary(provenance=[])
    sand, silt, clay = props.get("sand"), props.get("silt"), props.get("clay")
    soc = props.get("soc")
    fc = wp = None
    texture = None
    if None not in (sand, silt, clay):
        texture = soil.usda_texture_class(sand, silt, clay)
        if soc is not None:
            fc, wp = soil.saxton_rawls(sand, clay, soc)
    bd = props.get("bdod")
    citation = props.get("source_citation")
    if prov_mode == "observed":
        prov = soilgrids.PROVENANCE.model_copy(update={"mode": prov_mode})  # type: ignore[arg-type]
    else:
        prov = DataProvenance(
            source="ICAR-NBSS&LUP / SoilGrids" if is_india else "FAO-UNESCO / ISRIC SoilGrids",
            product=citation or "Regional Benchmark Topsoil 0-30cm",
            resolution="250 m Regional Benchmark",
            doi="10.5194/soil-7-217-2021",
            url="https://nbsslup.icar.gov.in/" if is_india else "https://soilgrids.org/",
            mode="regional_climatology",
        )
    return SoilSummary(
        texture_class=texture,
        sand_pct=_r(sand),
        silt_pct=_r(silt),
        clay_pct=_r(clay),
        soc_g_per_kg=_r(soc),
        ph=_r(props.get("phh2o")),
        bulk_density_g_cm3=_r(bd / 100 if bd is not None and bd > 10 else bd, 2),
        cec_cmol_kg=_r(props.get("cec")),
        nitrogen_g_kg=_r(props.get("nitrogen"), 2),
        field_capacity_vol=fc,
        wilting_point_vol=wp,
        provenance=[prov],
    )


def apply_soil_health_card_override(
    profile: FieldProfile,
    shc: SoilHealthCardInput,
    language: str = "en",
) -> FieldProfile:
    """Apply farmer soil lab test measurements (India SHC, Mehlich-3, Olsen, Bray-1, ISO) to the FieldProfile."""
    from . import region_registry

    profile = profile.model_copy(deep=True)
    s = profile.soil
    lab_standard = getattr(shc, "lab_standard", None) or "india_shc"

    if shc.ph is not None:
        s.ph = round(float(shc.ph), 2)

    soc_pct_val = shc.soc_pct
    if soc_pct_val is None and getattr(shc, "organic_matter_pct", None) is not None:
        soc_pct_val = float(shc.organic_matter_pct) / 1.724
    if soc_pct_val is not None:
        # Convert Organic Carbon % (Walkley-Black / Dumas) to g/kg (* 10.0)
        s.soc_g_per_kg = round(float(soc_pct_val) * 10.0, 2)
        if s.sand_pct is not None and s.clay_pct is not None:
            fc, wp = soil.saxton_rawls(s.sand_pct, s.clay_pct, s.soc_g_per_kg)
            s.field_capacity_vol = fc
            s.wilting_point_vol = wp

    avail_n = shc.available_n_kg_ha
    if avail_n is None and getattr(shc, "nitrate_n_ppm", None) is not None:
        avail_n = float(shc.nitrate_n_ppm) * 2.24
    if avail_n is not None:
        s.nitrogen_g_kg = round(float(avail_n) / 2240.0, 4)

    # Convert Bray-1 / Mehlich-3 extractable P to Olsen-equivalent kg/ha for unified crop-KB thresholds
    p_to_olsen = 0.65 if lab_standard == "mehlich3" else (0.78 if lab_standard == "bray1" else 1.0)
    avail_p_raw = shc.available_p_kg_ha
    if avail_p_raw is None and getattr(shc, "phosphorus_ppm", None) is not None:
        avail_p_raw = float(shc.phosphorus_ppm) * 2.24
    if avail_p_raw is not None:
        s.available_p_kg_ha = round(float(avail_p_raw) * p_to_olsen, 1)

    avail_k = shc.available_k_kg_ha
    if avail_k is None and getattr(shc, "potassium_ppm", None) is not None:
        avail_k = float(shc.potassium_ppm) * 2.24
    if avail_k is not None:
        s.available_k_kg_ha = round(float(avail_k), 1)

    s.source = "farmer_test"
    if lab_standard == "india_shc":
        shc_prov = DataProvenance(
            source="Indian Govt Soil Health Card (SHC)",
            product="Farmer Local Soil Testing Lab Override",
            resolution="Field-scale composite sample",
            url="https://soilhealth.dac.gov.in/",
            mode="observed",
        )
    else:
        shc_prov = DataProvenance(
            source="Local Accredited Soil Testing Lab",
            product=f"Farmer Soil Lab Override ({lab_standard})",
            resolution="Field-scale composite sample",
            mode="observed",
        )
    if not any(p.source == shc_prov.source for p in s.provenance):
        s.provenance.insert(0, shc_prov)

    reg_cfg = region_registry.detect_region_config(profile.field.lat, profile.field.lon)
    profile.agro_climatic_notes = build_notes(
        profile.climate,
        s,
        profile.water,
        profile.hazards,
        lat=profile.field.lat,
        language=language,
        soc_ref_g_kg=reg_cfg.soc_ref_g_kg,
        hemisphere=reg_cfg.hemisphere,
    )
    return profile


def _r(v: float | None, nd: int = 1) -> float | None:
    return None if v is None else round(float(v), nd)


# ---------------------------------------------------------------------------
# Notes (deterministic, human-readable)
# ---------------------------------------------------------------------------
def build_notes(
    c: ClimateSummary,
    s: SoilSummary,
    w: WaterSummary,
    h: HazardSummary | None = None,
    lat: float = 30.0,
    language: str = "en",
    soc_ref_g_kg: float = 6.0,
    hemisphere: str | None = None,
) -> list[str]:
    lang = language if language in ("en", "hi", "pa", "es", "pt", "fr") else "en"

    def _tr(en: str, hi: str, pa: str, es: str = "", pt: str = "", fr: str = "") -> str:
        mapping = {"en": en, "hi": hi, "pa": pa, "es": es or en, "pt": pt or en, "fr": fr or en}
        return mapping.get(lang, en)

    is_sh = (hemisphere == "SH") if hemisphere is not None else (lat < 0)
    notes: list[str] = []
    if TREND_NOTES_ENABLED and c.recent_heat_days_per_year - c.heat_days_per_year >= 5:
        notes.append(
            _tr(
                f"Heat-stress days (>35 C) rose from {c.heat_days_per_year:.0f} to "
                f"{c.recent_heat_days_per_year:.0f} per year ({c.baseline_period} vs {c.recent_period}).",
                f"तेज़ गर्मी (>35°C) के दिन {c.heat_days_per_year:.0f} से बढ़कर {c.recent_heat_days_per_year:.0f} दिन/वर्ष हो गए ({c.baseline_period} बनाम {c.recent_period})।",
                f"ਤੇਜ਼ ਗਰਮੀ (>35°C) ਦੇ ਦਿਨ {c.heat_days_per_year:.0f} ਤੋਂ ਵੱਧ ਕੇ {c.recent_heat_days_per_year:.0f} ਦਿਨ/ਸਾਲ ਹੋ ਗਏ ({c.baseline_period} ਬਨਾਮ {c.recent_period})।",
                f"Los días de estrés térmico (>35 °C) aumentaron de {c.heat_days_per_year:.0f} a {c.recent_heat_days_per_year:.0f} por año ({c.baseline_period} vs {c.recent_period}).",
                f"Os dias de estresse térmico (>35 °C) subiram de {c.heat_days_per_year:.0f} para {c.recent_heat_days_per_year:.0f} por ano ({c.baseline_period} vs {c.recent_period}).",
                f"Les jours de stress thermique (>35 °C) sont passés de {c.heat_days_per_year:.0f} à {c.recent_heat_days_per_year:.0f} par an ({c.baseline_period} vs {c.recent_period}).",
            )
        )
    if h is not None and h.terminal_heat_days_per_year is not None and h.terminal_heat_days_per_year >= 3:
        grain_fill_range = "1 Sep-15 Oct" if is_sh else "1 Mar-15 Apr"
        notes.append(
            _tr(
                f"Wheat terminal heat stress: grain-fill period ({grain_fill_range}) averages "
                f"{h.terminal_heat_days_per_year:.1f} days/yr with Tmax > 32 C.",
                f"गेहूं दाने भरने की अवधि ({grain_fill_range}) में औसतन {h.terminal_heat_days_per_year:.1f} दिन/वर्ष Tmax > 32°C ताप तनाव रहता है।",
                f"ਕਣਕ ਦੇ ਦਾਣੇ ਭਰਨ ਸਮੇਂ ({grain_fill_range}) ਔਸਤਨ {h.terminal_heat_days_per_year:.1f} ਦਿਨ/ਸਾਲ Tmax > 32°C ਗਰਮੀ ਦਾ ਦਬਾਅ ਰਹਿੰਦਾ ਹੈ।",
                f"Estrés térmico terminal en trigo: el llenado de grano ({grain_fill_range}) promedia {h.terminal_heat_days_per_year:.1f} días/año con Tmax > 32 °C.",
                f"Estresse térmico terminal no trigo: o enchimento de grãos ({grain_fill_range}) registra média de {h.terminal_heat_days_per_year:.1f} dias/ano com Tmax > 32 °C.",
                f"Stress thermique terminal du blé : le remplissage du grain ({grain_fill_range}) totalise {h.terminal_heat_days_per_year:.1f} j/an avec Tmax > 32 °C.",
            )
        )
    if TREND_NOTES_ENABLED and 10 <= abs(c.precip_change_pct) <= 30:
        direction = "increased" if c.precip_change_pct > 0 else "decreased"
        dir_hi = "बढ़ी है" if c.precip_change_pct > 0 else "घटी है"
        dir_pa = "ਵਧੀ ਹੈ" if c.precip_change_pct > 0 else "ਘਟੀ ਹੈ"
        dir_es = "aumentado" if c.precip_change_pct > 0 else "disminuido"
        dir_pt = "aumentado" if c.precip_change_pct > 0 else "diminuído"
        dir_fr = "augmenté" if c.precip_change_pct > 0 else "diminué"
        notes.append(
            _tr(
                f"Annual rainfall has {direction} by {abs(c.precip_change_pct):.0f}% between periods.",
                f"दोनों अवधियों के बीच वार्षिक वर्षा {abs(c.precip_change_pct):.0f}% {dir_hi}।",
                f"ਦੋਹਾਂ ਦੌਰਾਂ ਵਿੱਚ ਸਾਲਾਨਾ ਮੀਂਹ {abs(c.precip_change_pct):.0f}% {dir_pa}।",
                f"La precipitación anual ha {dir_es} un {abs(c.precip_change_pct):.0f}% entre períodos.",
                f"A precipitação anual tem {dir_pt} {abs(c.precip_change_pct):.0f}% entre os períodos.",
                f"Les précipitations annuelles ont {dir_fr} de {abs(c.precip_change_pct):.0f}% entre les périodes.",
            )
        )
    if w.climatic_water_balance_mm is not None and w.climatic_water_balance_mm < -300:
        notes.append(
            _tr(
                f"Evaporative demand exceeds rainfall by {abs(w.climatic_water_balance_mm):.0f} mm/yr: "
                "crops depend on irrigation; water-efficient rotations matter.",
                f"वाष्पीकरण मांग वर्षा से {abs(w.climatic_water_balance_mm):.0f} मिमी/वर्ष अधिक है: फसलें सिंचाई पर निर्भर हैं, इसलिए कम पानी वाले फसल चक्र आवश्यक हैं।",
                f"ਵਾਸ਼ਪੀਕਰਨ ਦੀ ਲੋੜ ਮੀਂਹ ਨਾਲੋਂ {abs(w.climatic_water_balance_mm):.0f} ਮਿ.ਮੀ./ਸਾਲ ਵੱਧ ਹੈ: ਫ਼ਸਲਾਂ ਸਿੰਚਾਈ 'ਤੇ ਨਿਰਭਰ ਹਨ, ਇਸ ਲਈ ਘੱਟ ਪਾਣੀ ਵਾਲੇ ਫ਼ਸਲੀ ਚੱਕਰ ਜ਼ਰੂਰੀ ਹਨ।",
                f"La demanda evaporativa supera la lluvia en {abs(w.climatic_water_balance_mm):.0f} mm/año: los cultivos dependen del riego y requieren rotaciones eficientes en agua.",
                f"A demanda evaporativa excede a chuva em {abs(w.climatic_water_balance_mm):.0f} mm/ano: as culturas dependem de irrigação; rotações eficientes em água são essenciais.",
                f"La demande évaporative dépasse les pluies de {abs(w.climatic_water_balance_mm):.0f} mm/an : l'irrigation et des rotations sobres en eau sont essentielles.",
            )
        )
    if s.soc_g_per_kg is not None and s.soc_g_per_kg < soc_ref_g_kg:
        notes.append(
            _tr(
                f"Topsoil organic carbon is low ({s.soc_g_per_kg} g/kg vs regional benchmark {soc_ref_g_kg:.1f} g/kg): residue retention and legumes help.",
                f"ऊपरी मिट्टी में जैविक कार्बन कम ({s.soc_g_per_kg} ग्राम/किग्रा) है: फसल अवशेष मल्च और दलहन मददगार हैं।",
                f"ਉੱਪਰਲੀ ਮਿੱਟੀ ਵਿੱਚ ਜੈਵਿਕ ਕਾਰਬਨ ਘੱਟ ({s.soc_g_per_kg} ਗ੍ਰਾਮ/ਕਿਲੋ) ਹੈ: ਪਰਾਲੀ ਸੰਭਾਲ ਅਤੇ ਦਾਲਾਂ ਮਦਦਗਾਰ ਹਨ।",
                f"El carbono orgánico superficial es bajo ({s.soc_g_per_kg} g/kg vs referencia {soc_ref_g_kg:.1f} g/kg): retener rastrojos e incluir leguminosas ayuda.",
                f"O carbono orgânico superficial está baixo ({s.soc_g_per_kg} g/kg vs referência {soc_ref_g_kg:.1f} g/kg): manter palhada e leguminosas ajuda.",
                f"Le carbone organique de surface est faible ({s.soc_g_per_kg} g/kg vs repère {soc_ref_g_kg:.1f} g/kg) : les résidus et légumineuses aident.",
            )
        )
    if c.longest_dry_spell_days_mean >= 15:
        notes.append(
            _tr(
                f"Rainy-season dry spells average {c.longest_dry_spell_days_mean:.0f} days: drought-tolerant options reduce risk.",
                f"वर्षा ऋतु में सूखे अंतराल औसतन {c.longest_dry_spell_days_mean:.0f} दिन के हैं: सूखा-सहिष्णु फसलें जोखिम घटाती हैं।",
                f"ਬਰਸਾਤ ਦੌਰਾਨ ਸੁੱਕੇ ਦਿਨਾਂ ਦਾ ਅੰਤਰਾਲ ਔਸਤਨ {c.longest_dry_spell_days_mean:.0f} ਦਿਨ ਹੈ: ਸੋਕਾ-ਸਹਿਣਸ਼ੀਲ ਫ਼ਸਲਾਂ ਖ਼ਤਰਾ ਘਟਾਉਂਦੀਆਂ ਹਨ।",
                f"Los veranillos en la estación húmeda promedian {c.longest_dry_spell_days_mean:.0f} días: las opciones tolerantes a la sequía reducen el riesgo.",
                f"Os veranicos na estação chuvosa têm média de {c.longest_dry_spell_days_mean:.0f} dias: culturas tolerantes à seca reduzem riscos.",
                f"Les épisodes secs en saison pluvieuse durent {c.longest_dry_spell_days_mean:.0f} jours en moyenne : des cultures tolérantes réduisent le risque.",
            )
        )
    if h is not None and h.residue_burning_detected:
        notes.append(
            _tr(
                "Post-harvest residue burning detected near field via NASA FIRMS: in-situ mulching or alternative rotations recommended.",
                "नासा FIRMS से खेत के पास पराली जलाने की गतिविधि दिखी है: खेत में मल्चिंग या वैकल्पिक फसल चक्र अपनाएं।",
                "ਨਾਸਾ FIRMS ਰਾਹੀਂ ਖੇਤ ਨੇੜੇ ਪਰਾਲੀ ਸਾੜਨ ਦੇ ਸੰਕੇਤ ਮਿਲੇ ਹਨ: ਖੇਤ ਵਿੱਚ ਮਲਚਿੰਗ ਜਾਂ ਬਦਲਵੇਂ ਫ਼ਸਲੀ ਚੱਕਰ ਅਪਣਾਓ।",
                "Quema de rastrojos detectada cerca de la parcela vía NASA FIRMS: se recomienda cobertura en superficie o rotación alternativa.",
                "Queima de palhada detectada próximo ao talhão via NASA FIRMS: recomenda-se plantio direto na palha ou rotação alternativa.",
                "Brûlage de résidus détecté à proximité via NASA FIRMS : le maintien des résidus ou une rotation alternative est recommandé.",
            )
        )
    if s.available_p_kg_ha is not None and s.available_p_kg_ha < 12.0:
        notes.append(
            _tr(
                f"Low available soil phosphorus ({s.available_p_kg_ha:.1f} kg/ha Olsen-equiv P): pulse/legume inclusion and basal P aid root establishment.",
                f"मिट्टी में उपलब्ध फॉस्फोरस कम ({s.available_p_kg_ha:.1f} किग्रा/हेक्टेयर P) है: दलहन और बेसल DAP जड़ों के विकास में सहायक हैं।",
                f"ਮਿੱਟੀ ਵਿੱਚ ਉਪਲਬਧ ਫਾਸਫੋਰਸ ਘੱਟ ({s.available_p_kg_ha:.1f} ਕਿਲੋ/ਹੈਕਟੇਅਰ P) ਹੈ: ਦਾਲਾਂ ਅਤੇ ਬੇਸਲ DAP ਜੜ੍ਹਾਂ ਦੀ ਮਜ਼ਬੂਤੀ ਲਈ ਸਹਾਇਕ ਹਨ।",
                f"Fósforo disponible bajo ({s.available_p_kg_ha:.1f} kg/ha P eq. Olsen): incluir leguminosas y fertilización basal fosforada ayuda al enraizamiento.",
                f"Fósforo disponível baixo ({s.available_p_kg_ha:.1f} kg/ha P eq. Olsen): leguminosas e adubação fosfatada de base favorecem as raízes.",
                f"Phosphore assimilable faible ({s.available_p_kg_ha:.1f} kg/ha P eq. Olsen) : les légumineuses et un apport de fond favorisent l'enracinement.",
            )
        )
    if s.available_k_kg_ha is not None and s.available_k_kg_ha < 110.0:
        notes.append(
            _tr(
                f"Low available soil potassium ({s.available_k_kg_ha:.1f} kg/ha K): residue retention recycles >80% crop K.",
                f"मिट्टी में उपलब्ध पोटाश कम ({s.available_k_kg_ha:.1f} किग्रा/हेक्टेयर K) है: पराली मल्च से 80% से अधिक फसल पोटाश लौट आता है।",
                f"ਮਿੱਟੀ ਵਿੱਚ ਉਪਲਬਧ ਪੋਟਾਸ਼ ਘੱਟ ({s.available_k_kg_ha:.1f} ਕਿਲੋ/ਹੈਕਟੇਅਰ K) ਹੈ: ਪਰਾਲੀ ਮਲਚ ਨਾਲ 80% ਤੋਂ ਵੱਧ ਫ਼ਸਲੀ ਪੋਟਾਸ਼ ਵਾਪਸ ਮਿਲਦਾ ਹੈ।",
                f"Potasio disponible bajo ({s.available_k_kg_ha:.1f} kg/ha K): mantener el rastrojo recicla >80% del K del cultivo.",
                f"Potássio disponível baixo ({s.available_k_kg_ha:.1f} kg/ha K): a manutenção da palhada recicla >80% do K da cultura.",
                f"Potassium assimilable faible ({s.available_k_kg_ha:.1f} kg/ha K) : la restitution des résidus recycle >80% du K.",
            )
        )
    if h is not None and h.late_blight_risk_idx is not None and h.late_blight_risk_idx > 150.0:
        notes.append(
            _tr(
                f"High Phytophthora late-blight index ({h.late_blight_risk_idx:.0f} > 150): monitor potato and solanaceous canopies.",
                f"फाइटोफ्थोरा लेट-ब्लाइट सूचकांक अधिक ({h.late_blight_risk_idx:.0f} > 150) है: आलू की फसल की निगरानी करें।",
                f"ਫਾਈਟੋਪਥੋਰਾ ਲੇਟ-ਬਲਾਈਟ ਸੂਚਕ ਵੱਧ ({h.late_blight_risk_idx:.0f} > 150) ਹੈ: ਆਲੂ ਦੀ ਫ਼ਸਲ ਦੀ ਨਿਗਰਾਨੀ ਕਰੋ।",
                f"Índice alto de tizón tardío ({h.late_blight_risk_idx:.0f} > 150): vigilar papa y solanáceas.",
                f"Índice elevado de requeima ({h.late_blight_risk_idx:.0f} > 150): monitorar batata e solanáceas.",
                f"Indice élevé de mildiou ({h.late_blight_risk_idx:.0f} > 150) : surveiller la pomme de terre.",
            )
        )
    if h is not None and h.hail_probability_pct is not None and h.hail_probability_pct > 25.0:
        notes.append(
            _tr(
                f"Elevated hailstorm exposure ({h.hail_probability_pct:.0f}%): select lodging-tolerant varieties during cool grain fill.",
                f"ओलावृष्टि जोखिम अधिक ({h.hail_probability_pct:.0f}%): रबी दाने भरते समय न गिरने वाली किस्में चुनें।",
                f"ਗੜੇਮਾਰੀ ਦਾ ਖ਼ਤਰਾ ਵੱਧ ({h.hail_probability_pct:.0f}%): ਹਾੜ੍ਹੀ ਦੌਰਾਨ ਨਾ ਡਿੱਗਣ ਵਾਲੀਆਂ ਕਿਸਮਾਂ ਚੁਣੋ।",
                f"Riesgo elevado de granizo ({h.hail_probability_pct:.0f}%): priorizar variedades resistentes al vuelco.",
                f"Risco elevado de granizo ({h.hail_probability_pct:.0f}%): selecionar cultivares resistentes ao acamamento.",
                f"Risque élevé de grêle ({h.hail_probability_pct:.0f}%) : privilégier des variétés résistantes à la verse.",
            )
        )
    if h is not None and h.fire_weather_index is not None and h.fire_weather_index > 50.0:
        notes.append(
            _tr(
                f"Elevated Fosberg fire-weather danger ({h.fire_weather_index:.0f}/100): avoid open stubble burning and use direct-seeding mulch.",
                f"फसल अवशेष आग-मौसम सूचकांक अधिक ({h.fire_weather_index:.0f}/100): पराली न जलाएं और हैप्पी सीडर मल्चिंग अपनाएं।",
                f"ਪਰਾਲੀ ਅੱਗ-ਮੌਸਮ ਖ਼ਤਰਾ ਵੱਧ ({h.fire_weather_index:.0f}/100): ਪਰਾਲੀ ਨਾ ਸਾੜੋ ਅਤੇ ਹੈਪੀ ਸੀਡਰ ਮਲਚਿੰਗ ਵਰਤੋ।",
                f"Peligro elevado de fuego agrícola ({h.fire_weather_index:.0f}/100): evitar la quema de rastrojos y usar siembra directa.",
                f"Risco elevado de incêndio rural ({h.fire_weather_index:.0f}/100): evitar queimadas e adotar plantio direto na palha.",
                f"Risque d'incendie élevé ({h.fire_weather_index:.0f}/100) : éviter le brûlage des chaumes et privilégier le semis direct.",
            )
        )
    if h is not None and h.meteorological_drought_idx is not None and h.meteorological_drought_idx <= -1.5:
        notes.append(
            _tr(
                f"Meteomatics SPI drought index is negative ({h.meteorological_drought_idx:+.1f}): prioritize drought-tolerant pulses, oilseeds, or deficit irrigation.",
                f"मेटियोमैटिक्स सूखा सूचकांक नकारात्मक ({h.meteorological_drought_idx:+.1f}) है: सूखा-रोधी दलहन, तिलहन या नियंत्रित सिंचाई को प्राथमिकता दें।",
                f"ਮੀਟੀਓਮੈਟਿਕਸ ਸੋਕਾ ਸੂਚਕ ਨਕਾਰਾਤਮਕ ({h.meteorological_drought_idx:+.1f}) ਹੈ: ਸੋਕਾ-ਰੋਧੀ ਦਾਲਾਂ, ਤੇਲ ਬੀਜ ਜਾਂ ਬਚਤ ਸਿੰਚਾਈ ਨੂੰ ਤਰਜੀਹ ਦਿਓ।",
                f"Índice de sequía SPI negativo ({h.meteorological_drought_idx:+.1f}): priorizar leguminosas, oleaginosas tolerantes o riego deficitario.",
                f"Índice de seca SPI negativo ({h.meteorological_drought_idx:+.1f}): priorizar leguminosas, oleaginosas tolerantes ou irrigação deficitária.",
                f"Indice de sécheresse SPI négatif ({h.meteorological_drought_idx:+.1f}) : prioriser légumineuses, oléagineux ou irrigation déficitaire.",
            )
        )
    return notes


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
@dataclass
class _InflightEntry:
    event: threading.Event = dc_field(default_factory=threading.Event)
    profile: FieldProfile | None = None


_INFLIGHT_LOCK = threading.Lock()
_INFLIGHT_PROFILES: dict[tuple[float, float, str, str], _InflightEntry] = {}


def _collect_future(fut, label: str | None = None):
    """Read a completed future or cancel an unfinished one without blocking."""
    if fut is None:
        return None
    if not fut.done():
        fut.cancel()
        if label:
            log.warning("%s live fetch timed out; using regional fallback", label)
        return None
    try:
        return fut.result()
    except Exception as exc:  # noqa: BLE001
        if label:
            log.warning("%s live fetch failed: %s; using regional fallback", label, exc)
        return None


def build_profile(
    field: FieldGeometry,
    start: date | None = None,
    end: date | None = None,
    soil_health_card: SoilHealthCardInput | None = None,
    use_live_network: bool = True,
    language: str = "en",
) -> FieldProfile:
    start = start or date(BASELINE[0], 1, 1)
    end = end or date(RECENT[1], 12, 31)

    inflight_key: tuple[float, float, str, str] | None = None
    inflight_entry: _InflightEntry | None = None
    is_owner = False

    if use_live_network:
        inflight_key = (round(field.lat, 4), round(field.lon, 4), str(start), str(end))
        with _INFLIGHT_LOCK:
            existing = _INFLIGHT_PROFILES.get(inflight_key)
            if existing is None:
                inflight_entry = _InflightEntry()
                _INFLIGHT_PROFILES[inflight_key] = inflight_entry
                is_owner = True
            else:
                inflight_entry = existing

        if not is_owner and inflight_entry is not None:
            wait_sec = float(os.environ.get("PROFILE_LIVE_TIMEOUT_SEC", "24.0")) + 6.0
            inflight_entry.event.wait(timeout=wait_sec)
            if inflight_entry.profile is not None:
                shared_profile = inflight_entry.profile.model_copy(deep=True)
                if soil_health_card is not None:
                    shared_profile = apply_soil_health_card_override(
                        shared_profile, soil_health_card, language=language
                    )
                elif language != "en":
                    from . import region_registry

                    rc = region_registry.detect_region_config(shared_profile.field.lat, shared_profile.field.lon)
                    shared_profile.agro_climatic_notes = build_notes(
                        shared_profile.climate,
                        shared_profile.soil,
                        shared_profile.water,
                        shared_profile.hazards,
                        lat=shared_profile.field.lat,
                        language=language,
                        soc_ref_g_kg=rc.soc_ref_g_kg,
                        hemisphere=rc.hemisphere,
                    )
                return shared_profile
            # Owner failed or timed out; fall through cleanly without sharing broken state
            inflight_key = None
            inflight_entry = None

    try:
        profile = _build_base_profile(field, start, end, use_live_network=use_live_network, language=language)
        if is_owner and inflight_entry is not None:
            inflight_entry.profile = profile.model_copy(deep=True)
    finally:
        if is_owner and inflight_key is not None and inflight_entry is not None:
            with _INFLIGHT_LOCK:
                if _INFLIGHT_PROFILES.get(inflight_key) is inflight_entry:
                    _INFLIGHT_PROFILES.pop(inflight_key, None)
            inflight_entry.event.set()

    if soil_health_card is not None:
        profile = apply_soil_health_card_override(profile, soil_health_card, language=language)
    return profile


def _build_base_profile(
    field: FieldGeometry,
    start: date,
    end: date,
    use_live_network: bool = True,
    language: str = "en",
) -> FieldProfile:
    power_mode = "observed"
    soil_mode = "observed"
    weather = None
    props = None
    slope_val = None
    gw_trend = None
    smap_series = None
    imerg_series = None
    fire_df = None
    ndvi_df = None
    mm_snap = None
    mm_tactical = None
    mm_slope = None
    mm_daily_recent = None
    slope_from_mm = False
    fused_mm_weather = False

    if use_live_network:
        mm_active = bool(meteomatics.is_configured())
        timeout_sec = float(os.environ.get("PROFILE_LIVE_TIMEOUT_SEC", "24.0"))
        t_start = time.monotonic()
        pool = ThreadPoolExecutor(max_workers=12)
        try:
            # Start non-GEE HTTP feeds immediately so cold GEE initialisation overlaps instead of adding 8-14s.
            fut_power = pool.submit(
                nasa_power.fetch_daily,
                nasa_power.PowerRequest(field.lat, field.lon, start, end),
            )
            fut_soil = pool.submit(soilgrids.fetch_topsoil, field.lat, field.lon)
            fut_gee_init = pool.submit(gee.init)
            fut_mm_snap = pool.submit(meteomatics.fetch_soil_and_hazards_snapshot, field.lat, field.lon) if mm_active else None
            fut_mm_tact = pool.submit(meteomatics.fetch_tactical_forecast, field.lat, field.lon) if mm_active else None
            fut_mm_daily = (
                pool.submit(
                    meteomatics.fetch_daily_weather,
                    field.lat,
                    field.lon,
                    max(start, end - timedelta(days=90)),
                    end,
                )
                if mm_active
                else None
            )

            init_budget = min(timeout_sec, 14.0)
            wait([fut_gee_init], timeout=init_budget)
            gee_init_done = fut_gee_init.done() and not fut_gee_init.cancelled()
            gee_active = False
            if gee_init_done:
                try:
                    gee_active = bool(fut_gee_init.result())
                except Exception as exc:  # noqa: BLE001
                    log.warning("GEE init future error: %s", exc)
                    gee_active = False

            if gee_init_done:
                fut_slope = pool.submit(gee.slope_pct, field.lat, field.lon)
                fut_grace = pool.submit(gee.grace_trend, field.lat, field.lon)
                fut_smap = pool.submit(gee.smap_rootzone, field.lat, field.lon, "2015-04-01", str(end))
            else:
                fut_slope = None
                fut_grace = None
                fut_smap = None
            fut_imerg = (
                pool.submit(gee.imerg_daily, field.lat, field.lon, f"{max(2001, end.year - 2)}-01-01", str(end))
                if gee_active
                else None
            )
            fut_firms = (
                pool.submit(gee.fire_detections, field.lat, field.lon, f"{end.year - 4}-01-01", str(end))
                if gee_active
                else None
            )
            fut_ndvi = (
                pool.submit(gee.ndvi_timeseries, field.lat, field.lon, f"{end.year - 4}-01-01", str(end))
                if gee_active
                else None
            )
            fut_mm_slope = (
                pool.submit(meteomatics.fetch_srtm_slope_pct, field.lat, field.lon)
                if (mm_active and not gee_active)
                else None
            )

            all_futs = [
                f
                for f in (
                    fut_power,
                    fut_soil,
                    fut_slope,
                    fut_grace,
                    fut_smap,
                    fut_imerg,
                    fut_firms,
                    fut_ndvi,
                    fut_mm_snap,
                    fut_mm_tact,
                    fut_mm_slope,
                    fut_mm_daily,
                )
                if f is not None
            ]
            rem_timeout = max(2.0, timeout_sec - (time.monotonic() - t_start))
            wait(all_futs, timeout=rem_timeout)

            weather = _collect_future(fut_power, "NASA POWER")
            soil_res = _collect_future(fut_soil, "SoilGrids")
            props = soil_res[0] if isinstance(soil_res, tuple) and soil_res else None
            slope_val = _collect_future(fut_slope)
            grace_res = _collect_future(fut_grace)
            gw_trend = grace_res[0] if isinstance(grace_res, tuple) and grace_res else None
            smap_series = _collect_future(fut_smap)
            imerg_series = _collect_future(fut_imerg)
            fire_df = _collect_future(fut_firms)
            ndvi_df = _collect_future(fut_ndvi)
            mm_snap = _collect_future(fut_mm_snap)
            mm_tactical = _collect_future(fut_mm_tact)
            mm_slope = _collect_future(fut_mm_slope)
            mm_daily_recent = _collect_future(fut_mm_daily)
            if mm_slope is not None:
                slope_val = mm_slope
                slope_from_mm = True
        except Exception as exc:  # noqa: BLE001
            log.warning("Parallel external fetcher pool error: %s", exc)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    else:
        slope_val = gee.slope_pct(field.lat, field.lon)
        gw_trend, _ = gee.grace_trend(field.lat, field.lon)
        smap_series = gee.smap_rootzone(field.lat, field.lon, "2015-04-01", str(end))

    if weather is None:
        weather = nasa_power.synthetic_daily_weather(field.lat, field.lon, (start.year, end.year))
        power_mode = "regional_climatology"

    if mm_daily_recent is not None and not mm_daily_recent.empty:
        # Fuse 90m Meteomatics recent observations onto multi-year NASA POWER / baseline series
        # without collapsing the multi-year climatology span down to 90 days.
        weather = weather.copy()
        mm_corr = nasa_power.apply_igp_irrigation_bias_correction(mm_daily_recent.copy(), field.lat, field.lon)
        if "ET0" in mm_corr.columns and "ET0" not in weather.columns:
            weather["ET0"] = np.nan
        common_cols = [
            c
            for c in ("T2M_MAX", "T2M_MIN", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN", "RH2M", "WS2M", "ET0")
            if c in weather.columns and c in mm_corr.columns
        ]
        if common_cols:
            weather.update(mm_corr[common_cols])
            new_rows = mm_corr.loc[~mm_corr.index.isin(weather.index), common_cols]
            if not new_rows.empty:
                weather = pd.concat([weather, new_rows]).sort_index()
            fused_mm_weather = True

    from . import region_registry

    reg_cfg = region_registry.detect_region_config(field.lat, field.lon)
    state = region_registry.detect_state(field.lat, field.lon) or reg_cfg.state or reg_cfg.country

    imerg_prov = (
        gee.provenance_with_mode(gee.IMERG_PROVENANCE)
        if imerg_series is not None and not imerg_series.empty
        else None
    )
    climate, hazards, water_balance = summarise_climate(
        weather,
        field.lat,
        imerg_precip=imerg_series,
        imerg_prov=imerg_prov,
        lon=field.lon,
        prov_mode=power_mode,
        bias_corrected=bool(reg_cfg.igp_merra2_bias_correction),
    )
    if fused_mm_weather and mm_daily_recent is not None:
        mm_clim_prov = meteomatics.METEOMATICS_MIX_PROVENANCE.model_copy(
            update={
                "period": f"{mm_daily_recent.index.min().date().isoformat()} to {mm_daily_recent.index.max().date().isoformat()}",
                "mode": "observed",
            }
        )
        if not any(p.source == mm_clim_prov.source for p in climate.provenance):
            climate.provenance.append(mm_clim_prov)

    raw_slots = region_registry.get_calendar_slots(field.lat, field.lon)

    if not props:
        props = regional_soil_fallback(field.lat, field.lon)
        soil_mode = "regional_climatology"
    soil_summary = summarise_soil(
        props,
        prov_mode=soil_mode,
        is_india=(reg_cfg.validation_status == "validated_india"),
    )

    # 1. Slope from NASADEM / Meteomatics SRTM 90m (TASK-D06)
    if slope_val is not None:
        soil_summary.slope_pct = slope_val
        slope_prov = (
            meteomatics.METEOMATICS_MIX_PROVENANCE.model_copy(
                update={"product": "elevation:m (NASA SRTM 90m via Meteomatics)", "mode": "observed"}
            )
            if slope_from_mm
            else gee.provenance_with_mode(gee.NASADEM_PROVENANCE)
        )
        if not any(p.source == slope_prov.source and p.product == slope_prov.product for p in soil_summary.provenance):
            soil_summary.provenance.append(slope_prov)

    # 2. Water summary + GRACE-FO + SMAP (TASK-D04, D05)
    water_prov = list(climate.provenance)
    if gw_trend is not None:
        water_prov.append(gee.provenance_with_mode(gee.GRACE_PROVENANCE))

    smap_pctiles = None
    if smap_series is not None and not smap_series.empty:
        recent_start = pd.Timestamp(end.year - 2, 1, 1)
        recent_smap = smap_series[smap_series.index >= recent_start]
        pctiles = []
        for m in range(1, 13):
            clim_m = smap_series[smap_series.index.month == m].dropna().to_numpy()
            rec_m = recent_smap[recent_smap.index.month == m].dropna().to_numpy()
            if len(clim_m) > 0 and len(rec_m) > 0:
                pct = float(np.mean(clim_m <= np.mean(rec_m)) * 100.0)
                pctiles.append(round(pct, 1))
            else:
                pctiles.append(50.0)
        smap_pctiles = pctiles
        water_prov.append(gee.provenance_with_mode(gee.SMAP_PROVENANCE))
    elif not (use_live_network and gee.is_live()):
        water_prov.append(gee.provenance_with_mode(gee.SMAP_PROVENANCE, unknown_if_offline=True))

    water = WaterSummary(
        root_zone_moisture_percentile=smap_pctiles,
        groundwater_trend_cm_per_year=gw_trend,
        climatic_water_balance_mm=water_balance,
        provenance=water_prov,
    )

    # 3. FIRMS fire detections (TASK-D07) — Kharif (Oct-Nov) & Rabi/calendar post-harvest windows
    if fire_df is not None and not fire_df.empty and "date" in fire_df.columns:
        fire_dates = pd.to_datetime(fire_df["date"])
        if reg_cfg.validation_status == "validated_india":
            burn_months = {4, 5, 10, 11}
        else:
            burn_months = {
                int(m)
                for s in raw_slots
                for hm in s.get("typical_harvest_months", [])
                for m in (int(hm), (int(hm) % 12) + 1)
            } or {3, 4, 5, 9, 10, 11}
        hazards.residue_burning_detected = bool(fire_dates.dt.month.isin(burn_months).any())
    elif use_live_network and gee.is_live():
        hazards.residue_burning_detected = False
    else:
        hazards.residue_burning_detected = None
    hazards.provenance.append(gee.provenance_with_mode(gee.FIRMS_PROVENANCE, unknown_if_offline=True))

    # 4. Phenology & crop history (TASK-E01, E02)
    crop_history = []
    seasons_per_year = None
    if ndvi_df is not None and not ndvi_df.empty and "ndvi" in ndvi_df.columns:
        s_ndvi = pd.Series(ndvi_df["ndvi"].values, index=pd.to_datetime(ndvi_df["date"]))
        crop_history = phenology.infer_history(s_ndvi, field.lat, field.lon)
        if crop_history:
            years_detected = [h.year for h in crop_history]
            seasons_per_year = round(len(crop_history) / max(1, len(set(years_detected))))
    crop_history_prov = [gee.provenance_with_mode(gee.HLS_PROVENANCE, unknown_if_offline=True)]

    # 4b. Satellite irrigation detection (dry-season active cropping or elevated SMAP moisture under water deficit)
    has_dry_crop = any(h.season_index in (1, 2) and h.crop_id not in (None, "fallow") for h in crop_history)
    if has_dry_crop and water_balance < -250:
        water.irrigation_detected = True
    elif smap_series is not None and not smap_series.empty and gee.is_live():
        wet_set = set(climate.wettest_months or ([12, 1, 2, 3] if reg_cfg.hemisphere == "SH" else [7, 8, 9]))
        dry_mask = ~smap_series.index.month.isin(wet_set)
        dry_sm = smap_series[dry_mask].dropna()
        if not dry_sm.empty:
            if float(dry_sm.mean()) >= 0.22 and water_balance < -300:
                water.irrigation_detected = True
            elif float(dry_sm.mean()) < 0.17 and not has_dry_crop:
                water.irrigation_detected = False

    # Erosion screening using NASADEM / Meteomatics SRTM slope & TASK-M04 kinetic R factor
    snap_meta, reg_tactical = meteomatics.estimate_regional_tactical_and_hazards(
        field.lat, field.lon, climate, soil_summary, water, hazards
    )
    active_snap = mm_snap if mm_snap is not None else snap_meta
    snap_prov = active_snap.get("provenance")

    water.soil_moisture_deficit_mm = active_snap.get("soil_moisture_deficit_mm")
    water.soil_moisture_index_layers = active_snap.get("soil_moisture_index_layers")
    water.volumetric_soil_water_layers = active_snap.get("volumetric_soil_water_layers")
    water.seedbed_temp_5cm_c = active_snap.get("seedbed_temp_5cm_c")
    if snap_prov is not None and not any(p.source == snap_prov.source for p in water.provenance):
        water.provenance.append(snap_prov)

    hazards.late_blight_risk_idx = active_snap.get("late_blight_risk_idx")
    hazards.canopy_wetness_idx = active_snap.get("canopy_wetness_idx")
    hazards.hail_probability_pct = active_snap.get("hail_probability_pct")
    hazards.fire_weather_index = active_snap.get("fire_weather_index")
    hazards.meteorological_drought_idx = active_snap.get("meteorological_drought_idx")
    hazards.max_30m_precip_rate_mmh = active_snap.get("max_30m_precip_rate_mmh")
    if snap_prov is not None and not any(p.source == snap_prov.source for p in hazards.provenance):
        hazards.provenance.append(snap_prov)

    tactical_advisory = mm_tactical if mm_tactical is not None else reg_tactical

    if soil_summary.sand_pct is not None and soil_summary.soc_g_per_kg is not None:
        k = rusle.k_factor_williams(
            soil_summary.sand_pct,
            soil_summary.silt_pct or 0,
            soil_summary.clay_pct or 0,
            soil_summary.soc_g_per_kg / 10,
        )
        if hazards.max_30m_precip_rate_mmh is not None:
            r = rusle.r_factor_intensity(
                climate.annual_precip_mm,
                max_30m_rate_mmh=hazards.max_30m_precip_rate_mmh,
                extreme_rain_days_per_yr=hazards.extreme_rain_days_per_year,
            )
        else:
            r = rusle.r_factor_annual(climate.annual_precip_mm)
        slope = soil_summary.slope_pct if soil_summary.slope_pct is not None else 1.0
        a = rusle.soil_loss(r, k, rusle.ls_factor(slope), c=0.3)
        hazards.erosion_risk_class = rusle.erosion_class(a)  # type: ignore[assignment]

    # Data mode truthfulness: only mark fallback_synthetic if NASA POWER climate fetch actually failed
    if power_mode != "observed":
        data_mode = "fallback_synthetic"
        is_fallback = True
    elif soil_mode != "observed" or not gee.is_live():
        data_mode = "hybrid_regional"
        is_fallback = False
    else:
        data_mode = "observed"
        is_fallback = False

    profile = FieldProfile(
        field=field,
        state=state,
        country=reg_cfg.country,
        country_code=reg_cfg.country_code,
        aez_class=reg_cfg.aez_class,
        calendar_id=reg_cfg.calendar_id,
        calendar_slots=[CalendarSlotSpec(**s) for s in raw_slots],
        unit_convention=reg_cfg.unit_convention,
        climate=climate,
        water=water,
        soil=soil_summary,
        hazards=hazards,
        seasons_per_year=seasons_per_year,
        crop_history=crop_history,
        crop_history_provenance=crop_history_prov,
        agro_climatic_notes=build_notes(
            climate,
            soil_summary,
            water,
            hazards,
            lat=field.lat,
            language=language,
            soc_ref_g_kg=reg_cfg.soc_ref_g_kg,
            hemisphere=reg_cfg.hemisphere,
        ),
        currency=reg_cfg.currency,
        currency_symbol=reg_cfg.currency_symbol,
        agro_zone=reg_cfg.agro_zone,
        validation_status=reg_cfg.validation_status,
        validation_message=reg_cfg.validation_message,
        is_fallback=is_fallback,
        data_mode=data_mode,  # type: ignore[arg-type]
        tactical_advisory=tactical_advisory,
    )
    return profile
