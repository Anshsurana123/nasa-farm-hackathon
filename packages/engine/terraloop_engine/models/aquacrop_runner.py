"""FAO-56 / FAO-33 Daily Soil-Water & Thermal Stress Simulation. (TASK-M02, M03)

Note: This module has been renamed to `fao56_runner.py` to accurately reflect the
pure-Python FAO-56 / FAO-33 root-zone simulation engine. `aquacrop_runner.py` is
preserved as a backward-compatible shim re-exporting all symbols.
"""

from __future__ import annotations

from .fao56_runner import (
    _SLOT_DEFAULTS,
    _compute_thermal_and_waterlog_factors,
    _extract_season_weather,
    _simulate_step,
    _stage_kc_series,
    simulate_rotation,
    to_aquacrop_weather,
    to_daily_simulation_weather,
)

__all__ = [
    "_SLOT_DEFAULTS",
    "_compute_thermal_and_waterlog_factors",
    "_extract_season_weather",
    "_simulate_step",
    "_stage_kc_series",
    "simulate_rotation",
    "to_aquacrop_weather",
    "to_daily_simulation_weather",
]
