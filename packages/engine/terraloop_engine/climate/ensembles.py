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

    is_non_neg = bool((clean_obs >= 0.0).all() and float((clean_obs == 0.0).mean()) > 0.05)

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


def _derive_missing_surface_vars(
    res: pd.DataFrame,
    obs_df: pd.DataFrame | None = None,
    lat: float = 30.2,
) -> pd.DataFrame:
    """Populate solar radiation, relative humidity, and wind physically when GCMs omit them."""
    out = res.copy()
    if "T2M_MAX" in out.columns and "T2M_MIN" in out.columns:
        out["T2M_MIN"] = np.minimum(out["T2M_MIN"].to_numpy(dtype=float), out["T2M_MAX"].to_numpy(dtype=float) - 0.5)

    months = out.index.month if isinstance(out.index, pd.DatetimeIndex) else pd.Series(6, index=out.index)

    if "ALLSKY_SFC_SW_DWN" not in out.columns:
        if "T2M_MAX" in out.columns and "T2M_MIN" in out.columns:
            doy = (
                out.index.dayofyear.to_numpy(dtype=float)
                if isinstance(out.index, pd.DatetimeIndex)
                else np.arange(1, len(out) + 1, dtype=float)
            )
            lat_r = float(np.deg2rad(np.clip(lat, -66.0, 66.0)))
            dr = 1.0 + 0.033 * np.cos(2.0 * np.pi * doy / 365.0)
            delta = 0.409 * np.sin(2.0 * np.pi * doy / 365.0 - 1.39)
            ws = np.arccos(np.clip(-np.tan(lat_r) * np.tan(delta), -0.9999, 0.9999))
            ra = (24.0 * 60.0 / np.pi) * 0.0820 * dr * (
                ws * np.sin(lat_r) * np.sin(delta) + np.cos(lat_r) * np.cos(delta) * np.sin(ws)
            )
            dt = np.maximum(0.5, out["T2M_MAX"].to_numpy(dtype=float) - out["T2M_MIN"].to_numpy(dtype=float))
            out["ALLSKY_SFC_SW_DWN"] = np.round(np.clip(0.16 * np.sqrt(dt) * ra, 2.5, 32.0), 3)
        elif obs_df is not None and not obs_df.empty and "ALLSKY_SFC_SW_DWN" in obs_df.columns:
            m_rad = obs_df["ALLSKY_SFC_SW_DWN"].groupby(obs_df.index.month).median()
            out["ALLSKY_SFC_SW_DWN"] = pd.Series(months, index=out.index).map(m_rad).fillna(18.0).to_numpy()
        else:
            out["ALLSKY_SFC_SW_DWN"] = 18.0

    if "RH2M" not in out.columns:
        if obs_df is not None and not obs_df.empty and "RH2M" in obs_df.columns:
            m_rh = obs_df["RH2M"].groupby(obs_df.index.month).median()
            out["RH2M"] = pd.Series(months, index=out.index).map(m_rh).fillna(55.0).to_numpy()
        elif "T2M_MAX" in out.columns and "T2M_MIN" in out.columns:
            tmax = out["T2M_MAX"].to_numpy(dtype=float)
            tmin = out["T2M_MIN"].to_numpy(dtype=float)
            tmean = 0.5 * (tmax + tmin)
            tdew = tmin - 1.0
            es_tmean = 0.6108 * np.exp((17.27 * tmean) / np.maximum(1.0, tmean + 237.3))
            ea = 0.6108 * np.exp((17.27 * tdew) / np.maximum(1.0, tdew + 237.3))
            out["RH2M"] = np.round(np.clip(100.0 * ea / np.maximum(0.05, es_tmean), 25.0, 95.0), 1)
        else:
            out["RH2M"] = 55.0

    if "WS2M" not in out.columns:
        if obs_df is not None and not obs_df.empty and "WS2M" in obs_df.columns:
            m_ws = obs_df["WS2M"].groupby(obs_df.index.month).median()
            out["WS2M"] = pd.Series(months, index=out.index).map(m_ws).fillna(2.0).to_numpy()
        else:
            out["WS2M"] = 2.0

    return out


def quantile_map_df(
    obs_df: pd.DataFrame,
    model_hist_df: pd.DataFrame,
    model_future_df: pd.DataFrame,
    lat: float = 30.2,
) -> pd.DataFrame:
    """Apply monthly empirical quantile mapping across daily weather variables."""
    corr_cols = {}
    col_mapping = {
        "T2M_MAX": "tasmax" if "tasmax" in model_future_df.columns else "T2M_MAX",
        "T2M_MIN": "tasmin" if "tasmin" in model_future_df.columns else "T2M_MIN",
        "PRECTOTCORR": "pr" if "pr" in model_future_df.columns else "PRECTOTCORR",
    }
    for obs_col, mod_col in col_mapping.items():
        if obs_col in obs_df.columns and mod_col in model_hist_df.columns and mod_col in model_future_df.columns:
            if obs_col in ("T2M_MAX", "T2M_MIN"):
                mapped = quantile_map(
                    obs_df[obs_col] + 273.15,
                    model_hist_df[mod_col] + 273.15,
                    model_future_df[mod_col] + 273.15,
                )
                corr_cols[obs_col] = mapped - 273.15
            else:
                corr_cols[obs_col] = quantile_map(obs_df[obs_col], model_hist_df[mod_col], model_future_df[mod_col])

    res = pd.DataFrame(corr_cols, index=model_future_df.index)
    for extra_col in ("ALLSKY_SFC_SW_DWN", "RH2M", "WS2M"):
        if extra_col in model_future_df.columns and extra_col not in res.columns:
            res[extra_col] = model_future_df[extra_col]
    return _derive_missing_surface_vars(res, obs_df=obs_df, lat=lat)


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
        from ..data import gee, meteomatics

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
                corrected_df = quantile_map_df(power_hist, hist_cmip, fut_cmip, lat=lat)
            else:
                corrected_df = fut_cmip.rename(
                    columns={"tasmax": "T2M_MAX", "tasmin": "T2M_MIN", "pr": "PRECTOTCORR"}
                )
                corrected_df = _derive_missing_surface_vars(corrected_df, obs_df=None, lat=lat)
            member_id = f"{model.lower().replace('-', '_')}_{ssp}_{horizon}"
            members[member_id] = corrected_df

        mm_active = False
        if meteomatics.is_configured():
            mm_fut = meteomatics.fetch_cmip6_daily(lat, lon, ssp, f"{start_year}-01-01", f"{end_year}-12-31")
            if mm_fut is not None and not mm_fut.empty:
                mm_hist = meteomatics.fetch_cmip6_daily(lat, lon, "historical", "1995-01-01", "2014-12-31")
                if mm_hist is None or mm_hist.empty:
                    try:
                        mm_hist = gee.cmip6_daily(lat, lon, "MRI-ESM2-0", "historical", "1995-01-01", "2014-12-31")
                    except Exception:  # noqa: BLE001
                        mm_hist = None
                if not power_hist.empty and mm_hist is not None and not mm_hist.empty:
                    mm_corr = quantile_map_df(power_hist, mm_hist, mm_fut, lat=lat)
                else:
                    mm_corr = mm_fut.rename(
                        columns={"tasmax": "T2M_MAX", "tasmin": "T2M_MIN", "pr": "PRECTOTCORR"}
                    )
                    mm_corr = _derive_missing_surface_vars(
                        mm_corr, obs_df=power_hist if not power_hist.empty else None, lat=lat
                    )
                members[f"mri_esm2_0_{ssp}_{horizon}"] = mm_corr
                mm_active = True

        scen_id = f"cmip6_{ssp}_{horizon}"
        cmip_prov = gee.provenance_with_mode(gee.CMIP6_PROVENANCE).model_copy(
            update={"period": f"{start_year}-{end_year}"}
        )
        provs = [cmip_prov]
        if mm_active:
            provs.append(
                meteomatics.METEOMATICS_CMIP6_PROVENANCE.model_copy(
                    update={"period": f"{start_year}-{end_year}", "mode": "observed"}
                )
            )
        scenario_set = ScenarioSet(
            id=scen_id,
            kind="cmip6",
            ssp=ssp,
            horizon=horizon,
            members=list(members.keys()),
            provenance=provs,
        )
        return scenario_set, members

    raise ValueError(f"Unknown scenario kind: '{kind}'")
