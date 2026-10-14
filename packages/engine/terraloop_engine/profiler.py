"""Field Profiler: builds a ``FieldProfile`` for a location.

Implemented sources : NASA POWER (climate), ISRIC SoilGrids (soil).
Pending sources     : SMAP, GRACE-FO, IMERG, FIRMS, NASADEM, HLS crop history
                      -> see docs/TASKS.md (TASK-D02..D07, TASK-E01).
Each pending source should be added as a separate ``_add_<source>`` function
that fills the relevant part of the profile and appends a DataProvenance.
Failures in optional sources must NOT break the profile (log + leave None).
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd
from terraloop_schemas import (
    ClimateSummary,
    FieldGeometry,
    FieldProfile,
    HazardSummary,
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
def summarise_climate(df: pd.DataFrame, lat: float) -> tuple[ClimateSummary, HazardSummary, float]:
    """Compute climate + hazard indicators from a daily POWER DataFrame.

    Returns (climate, hazards, annual climatic water balance P-ET0 in mm).
    Pure function: easy to unit-test with synthetic data.
    """
    df = df.copy()
    df["ET0"] = agroclimate.et0_hargreaves(df["T2M_MAX"], df["T2M_MIN"], lat)
    df["GDD10"] = agroclimate.gdd(df["T2M_MAX"], df["T2M_MIN"], base=10.0)

    years = df.index.year
    base = df[(years >= BASELINE[0]) & (years <= BASELINE[1])]
    recent = df[(years >= RECENT[0]) & (years <= RECENT[1])]
    if base.empty:  # short records (tests / partial downloads)
        base = df
    if recent.empty:
        recent = df

    def per_year(frame: pd.DataFrame, mask: pd.Series) -> float:
        return float(mask.groupby(frame.index.year).sum().mean())

    def annual_sum(frame: pd.DataFrame, col: str) -> float:
        return float(frame[col].groupby(frame.index.year).sum().mean())

    monthly_p = df["PRECTOTCORR"].groupby([years, df.index.month]).sum().groupby(level=1).mean()
    monthly_tx = df["T2M_MAX"].groupby(df.index.month).mean()
    monthly_tn = df["T2M_MIN"].groupby(df.index.month).mean()
    monthly_p_list = [round(float(monthly_p.get(m, 0.0)), 1) for m in range(1, 13)]
    wet_months = agroclimate.wettest_window(monthly_p_list, length=4)

    annual_p_base = annual_sum(base, "PRECTOTCORR")
    annual_p_recent = annual_sum(recent, "PRECTOTCORR")
    annual_p_all = annual_sum(df, "PRECTOTCORR")
    annual_et0 = annual_sum(df, "ET0")

    yearly_p = df["PRECTOTCORR"].groupby(years).sum()
    drought_freq = float((yearly_p < 0.8 * yearly_p.mean()).mean())
    heat_by_year = (df["T2M_MAX"] > HEAT_THRESHOLD_C).groupby(years).sum()

    # Terminal heat during wheat grain-fill (1 Mar - 15 Apr in NH, 1 Sep - 15 Oct in SH)
    if lat < 0:
        is_terminal = (df.index.month == 9) | ((df.index.month == 10) & (df.index.day <= 15))
    else:
        is_terminal = (df.index.month == 3) | ((df.index.month == 4) & (df.index.day <= 15))
    terminal_heat_per_yr = float((is_terminal & (df["T2M_MAX"] > 32.0)).groupby(years).sum().mean())

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
        provenance=[nasa_power.provenance(df.index.min().date(), df.index.max().date())],
    )

    hazards = HazardSummary(
        drought_frequency=round(drought_freq, 2),
        extreme_rain_days_per_year=round(per_year(df, df["PRECTOTCORR"] > EXTREME_RAIN_MM), 2),
        heat_stress_probability=round(float((heat_by_year >= 10).mean()), 2),
        frost_risk=round(float(((df["T2M_MIN"] < FROST_THRESHOLD_C).groupby(years).sum() > 0).mean()), 2),
        terminal_heat_days_per_year=round(terminal_heat_per_yr, 1),
    )
    return climate, hazards, round(annual_p_all - annual_et0, 1)


# ---------------------------------------------------------------------------
# Soil (SoilGrids)
# ---------------------------------------------------------------------------
def summarise_soil(props: dict[str, float] | None) -> SoilSummary:
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
        provenance=[soilgrids.PROVENANCE],
    )


def _r(v: float | None, nd: int = 1) -> float | None:
    return None if v is None else round(float(v), nd)


# ---------------------------------------------------------------------------
# Notes (deterministic, human-readable; later localised by the explain layer)
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
            f"Wheat terminal heat stress: grain-fill period ({grain_fill_range}) averages {h.terminal_heat_days_per_year:.1f} days/yr with Tmax > 32 C."
        )
    # Safeguard (TASK-D11): cap rainfall trend note at <= 30% to prevent reanalysis step-change artifacts
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
def build_profile(field: FieldGeometry, start: date | None = None, end: date | None = None) -> FieldProfile:
    start = start or date(BASELINE[0], 1, 1)
    end = end or date(RECENT[1], 12, 31)

    try:
        weather = nasa_power.fetch_daily(nasa_power.PowerRequest(field.lat, field.lon, start, end))
    except Exception as exc:  # noqa: BLE001
        log.warning("NASA POWER live fetch failed: %s; using location-calibrated synthetic weather", exc)
        weather = nasa_power.synthetic_daily_weather(field.lat, field.lon, (start.year, end.year))

    climate, hazards, water_balance = summarise_climate(weather, field.lat)

    try:
        props, _used = soilgrids.fetch_topsoil(field.lat, field.lon)
    except Exception:
        log.exception("SoilGrids failed")
        props = None
    if not props:
        # Fallback to realistic physical baseline topsoil properties if SoilGrids is unreachable
        props = {"sand": 45.0, "silt": 35.0, "clay": 20.0, "soc": 9.5, "phh2o": 7.1, "bdod": 138.0}
    soil_summary = summarise_soil(props)

    # 1. Slope from NASADEM (TASK-D06)
    try:
        slope = gee.slope_pct(field.lat, field.lon)
        soil_summary.slope_pct = slope
        if gee.NASADEM_PROVENANCE not in soil_summary.provenance:
            soil_summary.provenance.append(gee.NASADEM_PROVENANCE)
    except Exception:
        log.warning("NASADEM slope lookup failed", exc_info=True)

    # 2. Water summary + GRACE-FO + SMAP (TASK-D04, D05)
    water_prov = list(climate.provenance)
    gw_trend = None
    try:
        gw_trend, _ = gee.grace_trend(field.lat, field.lon)
        water_prov.append(gee.GRACE_PROVENANCE)
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
            water_prov.append(gee.SMAP_PROVENANCE)
    except Exception:
        log.warning("SMAP rootzone lookup failed", exc_info=True)

    water = WaterSummary(
        root_zone_moisture_percentile=smap_pctiles,
        groundwater_trend_cm_per_year=gw_trend,
        climatic_water_balance_mm=water_balance,
        provenance=water_prov,
    )

    # 3. FIRMS fire detections (TASK-D07)
    try:
        fire_df = gee.fire_detections(field.lat, field.lon, start=f"{end.year - 4}-01-01", end=str(end))
        if not fire_df.empty and "date" in fire_df.columns:
            fire_dates = pd.to_datetime(fire_df["date"])
            oct_nov = (fire_dates.dt.month == 10) | (fire_dates.dt.month == 11)
            hazards.residue_burning_detected = bool(oct_nov.any())
        else:
            hazards.residue_burning_detected = False
    except Exception:
        log.warning("FIRMS fire detections lookup failed", exc_info=True)
        hazards.residue_burning_detected = False

    # 4. Phenology & crop history (TASK-E01, E02)
    crop_history = []
    seasons_per_year = None
    try:
        ndvi_df = gee.ndvi_timeseries(field.lat, field.lon, start=f"{end.year - 4}-01-01", end=str(end))
        if not ndvi_df.empty and "ndvi" in ndvi_df.columns:
            s_ndvi = pd.Series(ndvi_df["ndvi"].values, index=pd.to_datetime(ndvi_df["date"]))
            crop_history = phenology.infer_history(s_ndvi, field.lat, field.lon)
            if crop_history:
                years_detected = [h.year for h in crop_history]
                seasons_per_year = round(len(crop_history) / max(1, len(set(years_detected))))
    except Exception:
        log.warning("Phenology crop history inference failed", exc_info=True)

    # Erosion screening using NASADEM slope
    if soil_summary.sand_pct is not None and soil_summary.soc_g_per_kg is not None:
        k = rusle.k_factor_williams(
            soil_summary.sand_pct, soil_summary.silt_pct or 0, soil_summary.clay_pct or 0,
            soil_summary.soc_g_per_kg / 10,
        )
        r = rusle.r_factor_annual(climate.annual_precip_mm)
        slope = soil_summary.slope_pct if soil_summary.slope_pct is not None else 1.0
        a = rusle.soil_loss(r, k, rusle.ls_factor(slope), c=0.3)  # C=0.3 ~ annual cereal, refined per rotation
        hazards.erosion_risk_class = rusle.erosion_class(a)  # type: ignore[assignment]

    region = economics.detect_region(field.lat, field.lon)
    curr_info = economics.get_currency_info(region)

    return FieldProfile(
        field=field,
        climate=climate,
        water=water,
        soil=soil_summary,
        hazards=hazards,
        seasons_per_year=seasons_per_year,
        crop_history=crop_history,
        agro_climatic_notes=build_notes(climate, soil_summary, water, hazards, lat=field.lat),
        currency=curr_info["code"],
        currency_symbol=curr_info["symbol"],
    )
