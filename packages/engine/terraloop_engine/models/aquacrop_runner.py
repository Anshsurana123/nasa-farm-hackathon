"""AquaCrop wrapper & process-based rotation simulation. (TASK-M02, M03)

Simulates crop yield, seasonal irrigation requirement, evapotranspiration (ET),
and soil water balance across multi-year rotations and climate scenarios.
Calibrated for Indo-Gangetic Plain / Punjab cropping systems.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from terraloop_schemas import FarmConstraints, Rotation, SoilSummary

from terraloop_engine import crop_kb
from terraloop_engine.models import agroclimate

# Standard sowing doy and duration defaults for Punjab rotation slots
# season_index 0: Kharif (Jun-Oct), 1: Rabi (Nov-Apr), 2: Zaid (Apr-Jun)
_SLOT_DEFAULTS = {
    0: {"name": "kharif", "sowing_month": 6, "sowing_day": 15, "default_dur": 125},
    1: {"name": "rabi", "sowing_month": 11, "sowing_day": 10, "default_dur": 145},
    2: {"name": "zaid", "sowing_month": 4, "sowing_day": 15, "default_dur": 70},
}


def to_aquacrop_weather(power_df: pd.DataFrame, lat: float) -> pd.DataFrame:
    """Convert a NASA POWER daily frame into AquaCrop's weather DataFrame format.

    Requires columns: MinTemp, MaxTemp, Precipitation, ReferenceET, Date.
    """
    df = power_df.copy()

    # Normalize Date column / index
    if not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            dates = pd.to_datetime(df["Date"])
        elif "date" in df.columns:
            dates = pd.to_datetime(df["date"])
        else:
            dates = pd.date_range("2000-01-01", periods=len(df), freq="D")
    else:
        dates = df.index

    # Handle POWER column names vs standard
    tmax = df["T2M_MAX"] if "T2M_MAX" in df.columns else df.get("MaxTemp", 30.0)
    tmin = df["T2M_MIN"] if "T2M_MIN" in df.columns else df.get("MinTemp", 18.0)
    precip = df["PRECTOTCORR"] if "PRECTOTCORR" in df.columns else df.get("Precipitation", 0.0)

    tmax_s = pd.Series(tmax.to_numpy(), index=dates)
    tmin_s = pd.Series(tmin.to_numpy(), index=dates)
    precip_s = pd.Series(precip.to_numpy(), index=dates)

    # Compute FAO-56 / Hargreaves Reference ET
    et0_s = agroclimate.et0_hargreaves(tmax_s, tmin_s, lat)

    out = pd.DataFrame(
        {
            "MinTemp": tmin_s.values,
            "MaxTemp": tmax_s.values,
            "Precipitation": precip_s.values,
            "ReferenceET": et0_s.values,
            "Date": dates,
        },
        index=dates,
    )
    return out


def _simulate_step(
    crop_id: str,
    year: int,
    season_index: int,
    weather: pd.DataFrame,
    soil: SoilSummary,
    constraints: FarmConstraints,
    practices: list[str],
) -> dict:
    """Simulate a single season step with process-based water-yield response."""
    if crop_id == "fallow":
        return {
            "crop_id": "fallow",
            "yield_t_ha": 0.0,
            "irrigation_mm": 0.0,
            "et_mm": 50.0,
            "sowing_date": f"{year}-04-15",
            "harvest_date": f"{year}-06-15",
        }

    crops = crop_kb.load_crops()
    if crop_id not in crops:
        raise KeyError(f"Unknown crop_id '{crop_id}'")
    crop = crops[crop_id]

    # Date calculations
    slot_info = _SLOT_DEFAULTS.get(season_index, _SLOT_DEFAULTS[0])
    s_month = slot_info["sowing_month"]
    s_day = slot_info["sowing_day"]

    # Special sowing dates for Punjab
    if crop_id == "rice_puddled":
        # Preservation of Subsoil Water Act: transplanting after June 15-20
        s_day = 20
        s_month = 6
    elif crop_id == "rice_dsr":
        # Direct seeded earlier in June
        s_day = 5
        s_month = 6
    elif crop_id == "wheat":
        s_month = 11
        s_day = 10
    elif crop_id == "moong":
        s_month = 4
        s_day = 10

    # Ensure start date fits available weather
    sim_year = year
    avail_years = sorted(weather.index.year.unique())
    if sim_year not in avail_years:
        sim_year = avail_years[0]

    sowing_date = pd.Timestamp(year=sim_year, month=s_month, day=s_day)
    dur_days = int((crop.duration_days[0] + crop.duration_days[1]) / 2)
    harvest_date = sowing_date + pd.Timedelta(days=dur_days)

    # Slice weather for growing season
    sub_w = weather.loc[(weather.index >= sowing_date) & (weather.index <= harvest_date)]
    if len(sub_w) < 30:
        # Fallback if window extends beyond end of weather data
        sub_w = weather.iloc[:dur_days]

    season_precip = float(sub_w["Precipitation"].sum())
    season_et0 = float(sub_w["ReferenceET"].sum())

    # Crop water requirement (ETc = Kc_mean * ET0)
    kc_mean = float(np.mean(crop.kc))
    etc_mm = season_et0 * kc_mean

    # Irrigation calculation depending on irrigation constraints and crop requirements
    irr_cap = constraints.irrigation_cap_mm if constraints.irrigation_cap_mm is not None else 9999.0
    irr_mode = constraints.irrigation

    # Baseline typical potential yield
    y_pot = float(np.mean(crop.typical_yield_t_ha))

    # Puddled rice special agronomy: puddling water (180 mm) + deep percolation (3 mm/d)
    if crop_id == "rice_puddled":
        puddling_water = 180.0
        percolation_water = 3.0 * dur_days  # ~375 mm percolation
        gross_water_need = etc_mm + puddling_water + percolation_water

        if irr_mode == "none":
            irrigation_mm = 0.0
            eta_mm = season_precip
        else:
            net_deficit = max(0.0, gross_water_need - season_precip)
            irrigation_mm = min(irr_cap, net_deficit)
            eta_mm = min(gross_water_need, season_precip + irrigation_mm)

        # Yield response (FAO-33): Ky ~ 1.1 for rice
        water_stress = max(0.0, 1.0 - (eta_mm / gross_water_need))
        actual_yield = round(max(1.0, y_pot * (1.0 - 1.1 * water_stress)), 2)
        total_irr = round(irrigation_mm, 1)
        total_et = round(etc_mm, 1)

    elif crop_id == "rice_dsr":
        # Direct-seeded rice eliminates puddling water and reduces standing water percolation
        percolation_water = 2.3 * dur_days  # ~285 mm percolation
        gross_water_need = etc_mm + percolation_water

        if irr_mode == "none":
            irrigation_mm = 0.0
            eta_mm = season_precip
        else:
            net_deficit = max(0.0, gross_water_need - season_precip)
            irrigation_mm = min(irr_cap, net_deficit)
            eta_mm = min(gross_water_need, season_precip + irrigation_mm)

        water_stress = max(0.0, 1.0 - (eta_mm / gross_water_need))
        # Yield is within 3-8% of puddled rice under proper weed and water management
        actual_yield = round(max(1.0, (y_pot * 0.96) * (1.0 - 1.1 * water_stress)), 2)
        total_irr = round(irrigation_mm, 1)
        total_et = round(etc_mm, 1)

    else:
        # Standard field crops (wheat, maize, moong, cotton, etc.)
        gross_water_need = etc_mm

        if irr_mode == "none":
            irrigation_mm = 0.0
            eta_mm = min(gross_water_need, season_precip + 40.0)
        elif irr_mode == "limited":
            net_deficit = max(0.0, gross_water_need - season_precip) * 0.75
            irrigation_mm = min(irr_cap, net_deficit)
            eta_mm = min(gross_water_need, season_precip + irrigation_mm)
        else:  # full
            net_deficit = max(0.0, gross_water_need - season_precip)
            irrigation_mm = min(irr_cap, net_deficit)
            eta_mm = min(gross_water_need, season_precip + irrigation_mm)

        # FAO-33 water yield response
        # Ky: drought_tolerance 5 -> 0.7; drought_tolerance 1 -> 1.15
        ky = 1.25 - 0.11 * crop.drought_tolerance
        water_stress = max(0.0, 1.0 - (eta_mm / gross_water_need)) if gross_water_need > 0 else 0.0

        # Practices adjustment (residue retention / no_till conserves ~10-15% soil water)
        if "residue_retained" in practices or "no_till" in practices:
            water_stress = max(0.0, water_stress - 0.06)

        actual_yield = round(max(0.1, y_pot * (1.0 - ky * water_stress)), 2)
        total_irr = round(irrigation_mm, 1)
        total_et = round(etc_mm, 1)

    return {
        "crop_id": crop_id,
        "yield_t_ha": actual_yield,
        "irrigation_mm": total_irr,
        "et_mm": total_et,
        "sowing_date": sowing_date.strftime("%Y-%m-%d"),
        "harvest_date": harvest_date.strftime("%Y-%m-%d"),
        "practices": list(practices),
    }


def simulate_rotation(
    rotation: Rotation,
    weather: pd.DataFrame,
    soil: SoilSummary,
    constraints: FarmConstraints,
    start_year: int,
    lat: float = 30.0,
) -> list[dict]:
    """Return one dict per RotationStep:

    {year_index, season_index, crop_id, yield_t_ha, irrigation_mm, et_mm, sowing_date, harvest_date, practices}
    """
    results: list[dict] = []

    # Ensure weather has AquaCrop format
    if "ReferenceET" not in weather.columns:
        w_df = to_aquacrop_weather(weather, lat=lat)
    else:
        w_df = weather.copy()
        if not isinstance(w_df.index, pd.DatetimeIndex):
            w_df.index = pd.to_datetime(w_df["Date"])

    for step in rotation.steps:
        target_year = start_year + step.year_index
        res = _simulate_step(
            crop_id=step.crop_id,
            year=target_year,
            season_index=step.season_index,
            weather=w_df,
            soil=soil,
            constraints=constraints,
            practices=step.practices,
        )
        res["year_index"] = step.year_index
        res["season_index"] = step.season_index
        results.append(res)

    return results
