"""Climate scenario ensembles. (TASK-C01, C02)

C01 historical: each past year (NASA POWER) becomes one ensemble member.
    For a rotation of R years starting in year y, member = weather[y : y+R].
    Use moving blocks over 1985-2024 -> ~35-40 members.

C02 future (NEX-GDDP-CMIP6 via gee.cmip6_daily):
    GCMs (start with 5): ACCESS-CM2, MIROC6, MPI-ESM1-2-HR, NorESM2-MM, EC-Earth3
    Scenarios: ssp245, ssp585 ; horizons 2030s (2026-2045), 2050s (2041-2060)
    Bias correction: empirical quantile mapping per calendar month, using
    CMIP6 historical (1985-2014) vs NASA POWER (1985-2014) at the same point.
    Solar radiation / RH are not needed if ET0 uses Hargreaves.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from terraloop_schemas import DataProvenance, ScenarioSet

_HISTORICAL_PROVENANCE = DataProvenance(
    source="NASA POWER",
    product="Daily Agroclimatology (MERRA-2 / GEOS / CERES / IMERG-corrected)",
    period="1985-2024",
    resolution="0.5 x 0.625 deg, daily",
    url="https://power.larc.nasa.gov/",
)


def historical_members(power_df: pd.DataFrame, rotation_years: int = 1) -> dict[str, pd.DataFrame]:
    """TASK-C01: Generate moving multi-year blocks from NASA POWER daily series.

    Args:
        power_df: DataFrame with DatetimeIndex spanning historical years.
        rotation_years: Length of rotation in years (R).

    Returns:
        dict: {member_id: daily weather DataFrame spanning rotation_years}
    """
    if power_df.empty:
        return {}

    # Ensure DatetimeIndex
    df = power_df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            df.index = pd.to_datetime(df["Date"])
        elif "date" in df.columns:
            df.index = pd.to_datetime(df["date"])
        else:
            df.index = pd.to_datetime(df.index)

    df = df.sort_index()
    all_years = sorted(df.index.year.unique())
    if not all_years:
        return {}

    min_yr = all_years[0]
    max_yr = all_years[-1]

    members: dict[str, pd.DataFrame] = {}
    for start_yr in range(min_yr, max_yr - rotation_years + 2):
        end_yr = start_yr + rotation_years - 1
        mask = (df.index.year >= start_yr) & (df.index.year <= end_yr)
        sub = df.loc[mask]
        # Check that we have reasonable data (at least 350 days per year)
        expected_min_days = rotation_years * 350
        if len(sub) >= expected_min_days:
            member_id = f"hist_{start_yr}" if rotation_years == 1 else f"hist_{start_yr}_{end_yr}"
            members[member_id] = sub

    return members


CMIP6_MODELS = ["ACCESS-CM2", "MIROC6", "MPI-ESM1-2-HR", "NorESM2-MM", "EC-Earth3"]


def _interp_with_tail_extrapolation(
    mf_vals: np.ndarray, q_mh: np.ndarray, q_obs: np.ndarray, is_non_negative: bool = False
) -> np.ndarray:
    """Empirical quantile mapping with constant-anomaly extrapolation beyond historical [0, 100] percentiles."""
    corr_vals = np.interp(mf_vals, q_mh, q_obs)
    above = mf_vals > q_mh[-1]
    below = mf_vals < q_mh[0]
    if np.any(above):
        corr_vals[above] = q_obs[-1] + (mf_vals[above] - q_mh[-1])
    if np.any(below):
        corr_vals[below] = q_obs[0] + (mf_vals[below] - q_mh[0])
    if is_non_negative:
        corr_vals = np.maximum(0.0, corr_vals)
    return corr_vals


def quantile_map(obs: pd.Series, model_hist: pd.Series, model_future: pd.Series) -> pd.Series:
    """TASK-C02: Monthly empirical quantile mapping bias correction.

    Maps quantiles of model_future through CDF of model_hist to quantiles of obs:
        x_corr = Q_obs( F_model_hist( x_future ) )
    Preserves projected climate warming anomalies above the historical 100th percentile
    via constant-anomaly tail extrapolation (Cannon et al., 2015).
    """
    clean_obs = obs.dropna()
    clean_mh = model_hist.dropna()
    clean_mf = model_future.dropna()

    if len(clean_obs) == 0 or len(clean_mh) == 0 or len(clean_mf) == 0:
        return model_future.copy()

    is_non_neg = bool((clean_obs >= 0.0).all() and (clean_obs == 0.0).any())

    # Apply monthly empirical quantile mapping across the 12 calendar months if DatetimeIndex
    if hasattr(clean_obs.index, "month") and hasattr(clean_mh.index, "month") and hasattr(clean_mf.index, "month"):
        corr_chunks = []
        for m in range(1, 13):
            sub_obs = clean_obs[clean_obs.index.month == m]
            sub_mh = clean_mh[clean_mh.index.month == m]
            sub_mf = clean_mf[clean_mf.index.month == m]
            if sub_mf.empty:
                continue
            if len(sub_obs) < 5 or len(sub_mh) < 5:
                corr_chunks.append(sub_mf)
                continue
            percentiles = np.linspace(0.0, 100.0, 101)
            q_obs = np.percentile(sub_obs.to_numpy(), percentiles)
            q_mh = np.percentile(sub_mh.to_numpy(), percentiles)
            mf_vals = sub_mf.to_numpy(dtype=float)
            corr_vals = _interp_with_tail_extrapolation(mf_vals, q_mh, q_obs, is_non_negative=is_non_neg)
            corr_chunks.append(pd.Series(corr_vals, index=sub_mf.index))

        if corr_chunks:
            full_corr = pd.concat(corr_chunks).sort_index()
            full_corr.name = model_future.name
            return full_corr

    # Generic empirical quantile mapping across series
    percentiles = np.linspace(0.0, 100.0, 101)
    q_obs = np.percentile(clean_obs.to_numpy(), percentiles)
    q_mh = np.percentile(clean_mh.to_numpy(), percentiles)
    mf_vals = clean_mf.to_numpy(dtype=float)
    corr_vals = _interp_with_tail_extrapolation(mf_vals, q_mh, q_obs, is_non_negative=is_non_neg)
    return pd.Series(corr_vals, index=clean_mf.index, name=model_future.name)


def quantile_map_df(obs_df: pd.DataFrame, model_hist_df: pd.DataFrame, model_future_df: pd.DataFrame) -> pd.DataFrame:
    """Apply monthly empirical quantile mapping across daily weather variables."""
    corr_cols = {}
    col_mapping = {
        "T2M_MAX": "tasmax" if "tasmax" in model_future_df.columns else "T2M_MAX",
        "T2M_MIN": "tasmin" if "tasmin" in model_future_df.columns else "T2M_MIN",
        "PRECTOTCORR": "pr" if "pr" in model_future_df.columns else "PRECTOTCORR",
    }
    for obs_col, mod_col in col_mapping.items():
        if obs_col in obs_df.columns and mod_col in model_hist_df.columns and mod_col in model_future_df.columns:
            corr_cols[obs_col] = quantile_map(obs_df[obs_col], model_hist_df[mod_col], model_future_df[mod_col])

    res = pd.DataFrame(corr_cols, index=model_future_df.index)
    if "ALLSKY_SFC_SW_DWN" not in res.columns:
        res["ALLSKY_SFC_SW_DWN"] = 20.0
    if "RH2M" not in res.columns:
        res["RH2M"] = 50.0
    if "WS2M" not in res.columns:
        res["WS2M"] = 2.0
    return res


def build_scenario_set(
    kind: str = "historical",
    power_df: pd.DataFrame | None = None,
    rotation_years: int = 1,
    ssp: str | None = None,
    horizon: str | None = None,
    lat: float = 30.2,
    lon: float = 75.92,
) -> tuple[ScenarioSet, dict[str, pd.DataFrame]]:
    """Build a ScenarioSet and dictionary of daily weather sequences."""
    if kind == "historical":
        if power_df is None:
            raise ValueError("power_df must be provided for historical scenario set")
        members = historical_members(power_df, rotation_years=rotation_years)
        scen_id = f"historical_{rotation_years}yr"
        scenario_set = ScenarioSet(
            id=scen_id,
            kind="historical",
            members=list(members.keys()),
            provenance=[_HISTORICAL_PROVENANCE],
        )
        return scenario_set, members

    if kind == "cmip6":
        from ..data import gee

        ssp = ssp or "ssp245"
        horizon = horizon or "2050s"
        start_year = 2041 if horizon == "2050s" else 2026
        end_year = 2060 if horizon == "2050s" else 2045

        # Historical baseline 1985-2014 from NASA POWER
        power_hist = pd.DataFrame()
        if power_df is not None:
            power_hist = power_df[(power_df.index.year >= 1985) & (power_df.index.year <= 2014)]

        members: dict[str, pd.DataFrame] = {}
        for model in CMIP6_MODELS:
            hist_cmip = gee.cmip6_daily(lat, lon, model, "historical", "1985-01-01", "2014-12-31")
            fut_cmip = gee.cmip6_daily(lat, lon, model, ssp, f"{start_year}-01-01", f"{end_year}-12-31")
            if not power_hist.empty:
                corrected_df = quantile_map_df(power_hist, hist_cmip, fut_cmip)
            else:
                corrected_df = fut_cmip.rename(
                    columns={"tasmax": "T2M_MAX", "tasmin": "T2M_MIN", "pr": "PRECTOTCORR"}
                )
                corrected_df["ALLSKY_SFC_SW_DWN"] = 20.0
                corrected_df["RH2M"] = 50.0
                corrected_df["WS2M"] = 2.0
            member_id = f"{model.lower().replace('-', '_')}_{ssp}_{horizon}"
            members[member_id] = corrected_df

        scen_id = f"cmip6_{ssp}_{horizon}"
        cmip_prov = gee.provenance_with_mode(gee.CMIP6_PROVENANCE).model_copy(
            update={"period": f"{start_year}-{end_year}"}
        )
        scenario_set = ScenarioSet(
            id=scen_id,
            kind="cmip6",
            ssp=ssp,
            horizon=horizon,
            members=list(members.keys()),
            provenance=[cmip_prov],
        )
        return scenario_set, members

    raise ValueError(f"Unknown scenario kind: '{kind}'")
