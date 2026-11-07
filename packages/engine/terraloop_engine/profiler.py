"""Field Profiler: builds a ``FieldProfile`` for an Indian field location.

Implemented sources : NASA POWER (climate), ISRIC SoilGrids (soil), GEE / Regional Climatology
                      (SMAP, GRACE-FO, IMERG, FIRMS, NASADEM, HLS crop history), and
                      Indian Government Soil Health Card (SHC) lab test overrides.
Failures in optional sources must NOT break the profile (log + leave None or regional climatology).
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd
from terraloop_schemas import (
    ClimateSummary,
    DataProvenance,
    FieldGeometry,
    FieldProfile,
    HazardSummary,
    SoilHealthCardInput,
    SoilSummary,
    WaterSummary,
)

from .data import gee, nasa_power, soilgrids
from .eo import phenology
from .models import agroclimate, economics, rusle, soil

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
) -> tuple[ClimateSummary, HazardSummary, float]:
    """Compute climate + hazard indicators from a daily POWER DataFrame (+ optional GPM IMERG V07 series).

    Returns (climate, hazards, annual climatic water balance P-ET0 in mm).
    Pure function: easy to unit-test with synthetic data.
    """
    df = df.copy()
    df["ET0"] = agroclimate.et0_hargreaves(df["T2M_MAX"], df["T2M_MIN"], lat)
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
    if imerg_precip is not None and not imerg_precip.empty:
        p_series = imerg_precip.copy()
        if not isinstance(p_series.index, pd.DatetimeIndex):
            p_series.index = pd.to_datetime(p_series.index)
    elif (years >= 2001).any() and (years <= 2000).any():
        p_series = df.loc[years >= 2001, "PRECTOTCORR"]
    else:
        p_series = df["PRECTOTCORR"]

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

    power_prov = nasa_power.provenance(df.index.min().date(), df.index.max().date(), mode=prov_mode)
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
# Soil (SoilGrids & Indian Regional Topsoil Fallbacks)
# ---------------------------------------------------------------------------
def regional_indian_soil_fallback(lat: float, lon: float) -> dict[str, float]:
    """Return representative NBSS&LUP / ICAR topsoil properties for Indian agro-zones when SoilGrids is offline."""
    if (18.0 <= lat < 23.0) and (75.0 <= lon <= 80.5):
        # Vidarbha Deccan Vertisol (Black Cotton Soil - high clay, high water holding)
        return {"sand": 22.0, "silt": 26.0, "clay": 52.0, "soc": 6.2, "phh2o": 7.8, "bdod": 136.0, "nitrogen": 0.65}
    if (23.5 <= lat < 27.0) and (77.5 <= lon <= 81.5):
        # Bundelkhand Red/Parwa Sandy Loam (low SOC, low water holding)
        return {"sand": 62.0, "silt": 22.0, "clay": 16.0, "soc": 4.2, "phh2o": 7.3, "bdod": 152.0, "nitrogen": 0.48}
    if (28.5 <= lat <= 31.2) and (73.5 <= lon < 75.2):
        # Bathinda SW Punjab Arid Sandy Loam (coarse texture, alkaline pH)
        return {"sand": 64.0, "silt": 22.0, "clay": 14.0, "soc": 4.0, "phh2o": 8.2, "bdod": 154.0, "nitrogen": 0.45}
    if lat < 15.0:
        # Thanjavur Cauvery Delta Alluvial Clay Loam
        return {"sand": 32.0, "silt": 32.0, "clay": 36.0, "soc": 7.4, "phh2o": 6.9, "bdod": 140.0, "nitrogen": 0.78}
    # Central Punjab Indo-Gangetic Alluvial Loam (Sangrur / Ludhiana)
    return {"sand": 44.0, "silt": 36.0, "clay": 20.0, "soc": 5.2, "phh2o": 7.9, "bdod": 148.0, "nitrogen": 0.58}


def summarise_soil(props: dict[str, float] | None, prov_mode: str = "observed") -> SoilSummary:
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
    prov = soilgrids.PROVENANCE.model_copy(update={"mode": prov_mode})  # type: ignore[arg-type]
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


def apply_soil_health_card_override(profile: FieldProfile, shc: SoilHealthCardInput) -> FieldProfile:
    """Apply farmer's Indian Government Soil Health Card (SHC) lab test measurements to the FieldProfile."""
    s = profile.soil
    if shc.ph is not None:
        s.ph = round(float(shc.ph), 2)
    if shc.soc_pct is not None:
        # Convert Organic Carbon % (walkley-black) to g/kg (* 10.0)
        s.soc_g_per_kg = round(float(shc.soc_pct) * 10.0, 2)
        if s.sand_pct is not None and s.clay_pct is not None:
            fc, wp = soil.saxton_rawls(s.sand_pct, s.clay_pct, s.soc_g_per_kg)
            s.field_capacity_vol = fc
            s.wilting_point_vol = wp
    if shc.available_n_kg_ha is not None:
        s.nitrogen_g_kg = round(float(shc.available_n_kg_ha) / 2240.0, 2)

    s.source = "farmer_test"
    shc_prov = DataProvenance(
        source="Indian Govt Soil Health Card (SHC)",
        product="Farmer Local Soil Testing Lab Override",
        resolution="Field-scale composite sample",
        url="https://soilhealth.dac.gov.in/",
        mode="observed",
    )
    if not any(p.source == shc_prov.source for p in s.provenance):
        s.provenance.insert(0, shc_prov)

    profile.agro_climatic_notes = build_notes(
        profile.climate, s, profile.water, profile.hazards, lat=profile.field.lat
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
) -> list[str]:
    notes: list[str] = []
    if TREND_NOTES_ENABLED and c.recent_heat_days_per_year - c.heat_days_per_year >= 5:
        notes.append(
            f"Heat-stress days (>35 C) rose from {c.heat_days_per_year:.0f} to "
            f"{c.recent_heat_days_per_year:.0f} per year ({c.baseline_period} vs {c.recent_period})."
        )
    if h is not None and h.terminal_heat_days_per_year is not None and h.terminal_heat_days_per_year >= 3:
        grain_fill_range = "1 Sep-15 Oct" if lat < 0 else "1 Mar-15 Apr"
        notes.append(
            f"Wheat terminal heat stress: grain-fill period ({grain_fill_range}) averages "
            f"{h.terminal_heat_days_per_year:.1f} days/yr with Tmax > 32 C."
        )
    if TREND_NOTES_ENABLED and 10 <= abs(c.precip_change_pct) <= 30:
        direction = "increased" if c.precip_change_pct > 0 else "decreased"
        notes.append(f"Annual rainfall has {direction} by {abs(c.precip_change_pct):.0f}% between periods.")
    if w.climatic_water_balance_mm is not None and w.climatic_water_balance_mm < -300:
        notes.append(
            f"Evaporative demand exceeds rainfall by {abs(w.climatic_water_balance_mm):.0f} mm/yr: "
            "crops depend on irrigation; water-efficient rotations matter."
        )
    if s.soc_g_per_kg is not None and s.soc_g_per_kg < 6:
        notes.append(f"Topsoil organic carbon is low ({s.soc_g_per_kg} g/kg): residue retention and legumes help.")
    if c.longest_dry_spell_days_mean >= 15:
        notes.append(
            f"Rainy-season dry spells average {c.longest_dry_spell_days_mean:.0f} days: drought-tolerant options reduce risk."
        )
    if h is not None and h.residue_burning_detected:
        notes.append(
            "Post-harvest residue burning detected near field via NASA FIRMS: in-situ mulching or alternative rotations recommended."
        )
    return notes


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def build_profile(
    field: FieldGeometry,
    start: date | None = None,
    end: date | None = None,
    soil_health_card: SoilHealthCardInput | None = None,
) -> FieldProfile:
    start = start or date(BASELINE[0], 1, 1)
    end = end or date(RECENT[1], 12, 31)

    power_mode = "observed"
    try:
        weather = nasa_power.fetch_daily(nasa_power.PowerRequest(field.lat, field.lon, start, end))
    except Exception as exc:  # noqa: BLE001
        log.warning("NASA POWER live fetch failed: %s; using location-calibrated regional weather", exc)
        weather = nasa_power.synthetic_daily_weather(field.lat, field.lon, (start.year, end.year))
        power_mode = "regional_climatology"

    imerg_s = None
    imerg_prov = None
    if gee.init():
        try:
            imerg_s = gee.imerg_daily(field.lat, field.lon, start="2001-01-01", end=str(end))
            imerg_prov = gee.IMERG_PROVENANCE.model_copy(update={"mode": "observed"})
        except Exception:
            log.warning("GEE IMERG lookup failed; using POWER post-2001 IMERG-fused series", exc_info=True)

    climate, hazards, water_balance = summarise_climate(
        weather, field.lat, prov_mode=power_mode, imerg_precip=imerg_s, imerg_prov=imerg_prov
    )

    soil_mode = "observed"
    try:
        props, _used = soilgrids.fetch_topsoil(field.lat, field.lon)
    except Exception:
        log.exception("SoilGrids failed")
        props = None
    if not props:
        props = regional_indian_soil_fallback(field.lat, field.lon)
        soil_mode = "regional_climatology"
    soil_summary = summarise_soil(props, prov_mode=soil_mode)

    # 1. Slope from NASADEM (TASK-D06)
    try:
        slope = gee.slope_pct(field.lat, field.lon)
        soil_summary.slope_pct = slope
        nasadem_prov = gee.provenance_with_mode(gee.NASADEM_PROVENANCE)
        if not any(p.source == nasadem_prov.source for p in soil_summary.provenance):
            soil_summary.provenance.append(nasadem_prov)
    except Exception:
        log.warning("NASADEM slope lookup failed", exc_info=True)

    # 2. Water summary + GRACE-FO + SMAP (TASK-D04, D05)
    water_prov = list(climate.provenance)
    gw_trend = None
    try:
        gw_trend, _ = gee.grace_trend(field.lat, field.lon)
        water_prov.append(gee.provenance_with_mode(gee.GRACE_PROVENANCE))
    except Exception:
        log.warning("GRACE trend lookup failed", exc_info=True)

    smap_pctiles = None
    try:
        smap_series = gee.smap_rootzone(field.lat, field.lon, start="2015-04-01", end=str(end))
        if not smap_series.empty:
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
    except Exception:
        log.warning("SMAP rootzone lookup failed", exc_info=True)

    water = WaterSummary(
        root_zone_moisture_percentile=smap_pctiles,
        groundwater_trend_cm_per_year=gw_trend,
        climatic_water_balance_mm=water_balance,
        provenance=water_prov,
    )

    # 3. FIRMS fire detections (TASK-D07)
    firms_mode = "unknown"
    try:
        if gee.init():
            fire_df = gee.fire_detections(field.lat, field.lon, start=f"{end.year - 4}-01-01", end=str(end))
            firms_mode = "observed"
            if not fire_df.empty and "date" in fire_df.columns:
                fire_dates = pd.to_datetime(fire_df["date"])
                oct_nov = (fire_dates.dt.month == 10) | (fire_dates.dt.month == 11)
                hazards.residue_burning_detected = bool(oct_nov.any())
            else:
                hazards.residue_burning_detected = False
        else:
            hazards.residue_burning_detected = None
    except Exception:
        log.warning("FIRMS fire detections lookup failed", exc_info=True)
        hazards.residue_burning_detected = None
    hazards.provenance.append(gee.FIRMS_PROVENANCE.model_copy(update={"mode": firms_mode}))  # type: ignore[arg-type]

    # 4. Phenology & crop history (TASK-E01, E02)
    crop_history = []
    seasons_per_year = None
    hls_mode = "unknown"
    try:
        ndvi_df = gee.ndvi_timeseries(field.lat, field.lon, start=f"{end.year - 4}-01-01", end=str(end))
        if not ndvi_df.empty and "ndvi" in ndvi_df.columns:
            hls_mode = "observed" if gee.is_live() else "regional_climatology"
            s_ndvi = pd.Series(ndvi_df["ndvi"].values, index=pd.to_datetime(ndvi_df["date"]))
            crop_history = phenology.infer_history(s_ndvi, field.lat, field.lon)
            if crop_history:
                years_detected = [h.year for h in crop_history]
                seasons_per_year = round(len(crop_history) / max(1, len(set(years_detected))))
    except Exception:
        log.warning("Phenology crop history inference failed", exc_info=True)
    crop_history_prov = [gee.HLS_PROVENANCE.model_copy(update={"mode": hls_mode})]  # type: ignore[arg-type]

    # Erosion screening using NASADEM slope
    if soil_summary.sand_pct is not None and soil_summary.soc_g_per_kg is not None:
        k = rusle.k_factor_williams(
            soil_summary.sand_pct,
            soil_summary.silt_pct or 0,
            soil_summary.clay_pct or 0,
            soil_summary.soc_g_per_kg / 10,
        )
        r = rusle.r_factor_annual(climate.annual_precip_mm)
        slope = soil_summary.slope_pct if soil_summary.slope_pct is not None else 1.0
        a = rusle.soil_loss(r, k, rusle.ls_factor(slope), c=0.3)
        hazards.erosion_risk_class = rusle.erosion_class(a)  # type: ignore[assignment]

    region = economics.detect_region(field.lat, field.lon)
    curr_info = economics.get_currency_info(region)
    agro_zone = economics.detect_agro_zone(field.lat, field.lon)

    if power_mode != "observed" or soil_mode != "observed":
        data_mode = "fallback_synthetic"
    elif not gee.is_live():
        data_mode = "hybrid_regional"
    else:
        data_mode = "observed"

    profile = FieldProfile(
        field=field,
        climate=climate,
        water=water,
        soil=soil_summary,
        hazards=hazards,
        seasons_per_year=seasons_per_year,
        crop_history=crop_history,
        crop_history_provenance=crop_history_prov,
        agro_climatic_notes=build_notes(climate, soil_summary, water, hazards, lat=field.lat),
        currency=curr_info["code"],
        currency_symbol=curr_info["symbol"],
        agro_zone=agro_zone,
        is_fallback=(data_mode == "fallback_synthetic"),
        data_mode=data_mode,  # type: ignore[arg-type]
    )

    if soil_health_card is not None:
        profile = apply_soil_health_card_override(profile, soil_health_card)

    return profile
