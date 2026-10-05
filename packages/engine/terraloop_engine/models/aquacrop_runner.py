"""AquaCrop-OSPy wrapper for multi-season rotation simulation. (TASK-M02, M03)

Install: ``uv pip install -e packages/engine[sim]`` (package name: ``aquacrop``).
Docs: https://aquacropos.github.io/aquacrop/

Design:
  * One call simulates a full ``Rotation`` (all seasons, all years) for ONE weather sequence.
  * Soil water at the end of season N is the initial water content of season N+1
    (pass ``InitialWaterContent`` from the previous run's final soil profile).
  * Weather DataFrame comes from NASA POWER (historical) or CMIP6 (future) and must have
    columns MinTemp, MaxTemp, Precipitation, ReferenceET, Date (AquaCrop's expected names).
    ReferenceET: use models.agroclimate.et0_hargreaves (or FAO-56 Penman-Monteith later).
  * Soil: build a custom aquacrop.Soil from SoilSummary (texture class + FC/WP from Saxton-Rawls).
  * Crop: CropSpec.aquacrop_name maps to a built-in AquaCrop crop (e.g. 'Wheat', 'Maize',
    'PaddyRice', 'Soybean', 'Cotton', 'Potato', 'SugarBeet', 'Sorghum', 'Barley', 'Sunflower').
    Crops without a built-in (moong, mustard, chickpea...) need a parameter override dict (TASK-M01).
  * Irrigation: map FarmConstraints.irrigation -> IrrigationManagement
        none -> irrigation_method=0 ; limited -> method=1 with SMT ~[40,40,40,40] and MaxIrrSeason=cap
        full -> method=1 with SMT [70,70,70,70].
  * Puddled rice (TASK-M03): PaddyRice + bund/ponding; DSR: PaddyRice params with no ponding,
    earlier sowing. Calibrate yields against PAU / ICRISAT district data.

Output per season: yield (t/ha), irrigation (mm), ET (mm), final soil water.
"""

from __future__ import annotations

import pandas as pd
from terraloop_schemas import FarmConstraints, Rotation, SoilSummary


def to_aquacrop_weather(power_df: pd.DataFrame, lat: float) -> pd.DataFrame:
    """Convert a NASA POWER daily frame into AquaCrop's weather DataFrame format."""
    raise NotImplementedError("TASK-M02")


def simulate_rotation(
    rotation: Rotation,
    weather: pd.DataFrame,
    soil: SoilSummary,
    constraints: FarmConstraints,
    start_year: int,
) -> list[dict]:
    """Return one dict per RotationStep:
    {year_index, season_index, crop_id, yield_t_ha, irrigation_mm, et_mm, sowing_date, harvest_date}
    """
    raise NotImplementedError("TASK-M02")
