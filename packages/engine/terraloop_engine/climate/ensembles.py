"""Climate scenario ensembles. (TASK-C01, C02)

C01 historical: each past year (NASA POWER) becomes one ensemble member.
    For a rotation of R years starting in year y, member = weather[y : y+R].
    Use moving blocks over 1985-2024 -> ~35 members.

C02 future (NEX-GDDP-CMIP6 via gee.cmip6_daily):
    GCMs (start with 5): ACCESS-CM2, MIROC6, MPI-ESM1-2-HR, NorESM2-MM, EC-Earth3
    Scenarios: ssp245, ssp585 ; horizons 2030s (2026-2045), 2050s (2041-2060)
    Bias correction: empirical quantile mapping per calendar month, using
    CMIP6 historical (1985-2014) vs NASA POWER (1985-2014) at the same point.
    Solar radiation / RH are not needed if ET0 uses Hargreaves.
"""

from __future__ import annotations

import pandas as pd
from terraloop_schemas import ScenarioSet


def historical_members(power_df: pd.DataFrame, rotation_years: int) -> dict[str, pd.DataFrame]:
    """TASK-C01: {member_id: daily weather DataFrame spanning rotation_years}."""
    raise NotImplementedError("TASK-C01")


def quantile_map(obs: pd.Series, model_hist: pd.Series, model_future: pd.Series) -> pd.Series:
    """TASK-C02: monthly empirical quantile mapping."""
    raise NotImplementedError("TASK-C02")


def build_scenario_set(kind: str, **kwargs) -> tuple[ScenarioSet, dict[str, pd.DataFrame]]:
    raise NotImplementedError("TASK-C01/C02")
