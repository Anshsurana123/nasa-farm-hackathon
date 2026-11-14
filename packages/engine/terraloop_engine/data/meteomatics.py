"""Meteomatics 90m Weather, Soil Hydrology & Climate Scenarios client.

Official NASA Space Apps Challenge sponsor API providing 90m NASA-SRTM-downscaled
daily meteorology, 4-layer soil moisture & seedbed temperature, biotic blight/wetness
hazards, extreme rainfall intensity, and downscaled CMIP6 (MRI-ESM2.0) climate projections.

Docs: https://www.meteomatics.com/en/api/getting-started/
Requires METEOMATICS_USERNAME and METEOMATICS_PASSWORD in environment / .env.
Gracefully degrades cleanly when credentials are unset or network is offline.
"""

from __future__ import annotations

import logging
import math
import os
import threading
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import pandas as pd
from terraloop_schemas import (
    ClimateSummary,
    DataProvenance,
    HazardSummary,
    SoilSummary,
    TacticalAdvisory,
    TacticalDayForecast,
    WaterSummary,
)

from ..cache import disk_cache
from ..models import agroclimate

log = logging.getLogger(__name__)

BASE_URL = os.environ.get("METEOMATICS_BASE_URL", "https://api.meteomatics.com").rstrip("/")
TOKEN_URL = "https://login.meteomatics.com/api/v1/token"

_SENTINEL_MISSING = {-666.0, -777.0, -888.0, -999.0}
MAX_PARAMS_PER_QUERY = 10
_TOKEN_LOCK = threading.Lock()
_CACHED_TOKEN: dict[str, Any] = {"token": None, "expires_at": 0.0, "user": None}

METEOMATICS_MIX_PROVENANCE = DataProvenance(
    source="Meteomatics 90m Weather & Soil API",
    product="EURO1k / MIX (NASA SRTM 90m Downscaled)",
    resolution="90 m, daily / hourly",
    url="https://www.meteomatics.com/en/api/getting-started/",
    mode="observed",
)

METEOMATICS_CMIP6_PROVENANCE = DataProvenance(
    source="Meteomatics CMIP6 (MRI-ESM2.0)",
    product="mri-esm2-ssp126/245/370/585 (90m Downscaled)",
    resolution="90 m, daily",
    url="https://www.meteomatics.com/en/api/available-parameters/climate-data/",
    mode="observed",
)


def _load_dotenv_if_needed() -> None:
    """Load Meteomatics credentials from workspace .env if not already in os.environ."""
    if os.environ.get("METEOMATICS_USERNAME") and os.environ.get("METEOMATICS_PASSWORD"):
        return
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[4] / ".env",
    ]
    for env_path in candidates:
        if env_path.is_file():
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k and k not in os.environ:
                    os.environ[k] = v
            break


def _credentials() -> tuple[str, str]:
    _load_dotenv_if_needed()
    user = os.environ.get("METEOMATICS_USERNAME", "").strip()
    pwd = os.environ.get("METEOMATICS_PASSWORD", "").strip()
    return user, pwd


def is_configured() -> bool:
    """Return True when Meteomatics API credentials are present in the environment."""
    user, pwd = _credentials()
    return bool(user and pwd)


def _get_bearer_token(user: str, pwd: str, timeout: float = 8.0) -> str | None:
    """Exchange Basic credentials for a short-lived Meteomatics OAuth2 bearer token."""
    now = time.time()
    with _TOKEN_LOCK:
        if (
            _CACHED_TOKEN["token"]
            and _CACHED_TOKEN["user"] == user
            and float(_CACHED_TOKEN["expires_at"]) - 30.0 > now
        ):
            return str(_CACHED_TOKEN["token"])
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(TOKEN_URL, auth=(user, pwd))
            if resp.status_code == 200:
                payload = resp.json()
                token = payload.get("access_token")
                if token:
                    with _TOKEN_LOCK:
                        _CACHED_TOKEN["token"] = str(token)
                        _CACHED_TOKEN["expires_at"] = time.time() + float(payload.get("expires_in", 3600))
                        _CACHED_TOKEN["user"] = user
                    return str(token)
    except Exception as exc:  # noqa: BLE001
        log.debug("Meteomatics OAuth token endpoint fallback to Basic Auth: %s", exc)
    return None


def _clean_val(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f) or f in _SENTINEL_MISSING:
        return None
    return f


@disk_cache(namespace="meteomatics")
def _fetch_meteomatics_json(valid_datetime: str, parameters: str, location: str, extra_query: str = "") -> dict:
    """Perform a cached GET call against the Meteomatics REST API."""
    user, pwd = _credentials()
    if not (user and pwd):
        raise RuntimeError("METEOMATICS_USERNAME / METEOMATICS_PASSWORD not configured")

    base = os.environ.get("METEOMATICS_BASE_URL", BASE_URL).rstrip("/")
    url = f"{base}/{valid_datetime}/{parameters}/{location}/json"
    if extra_query:
        url = f"{url}?{extra_query}"

    timeout = float(os.environ.get("METEOMATICS_TIMEOUT", "14.0"))
    headers = {
        "User-Agent": "TerraLoop-NASA-SpaceApps/2.6",
        "Accept": "application/json",
    }
    token = _get_bearer_token(user, pwd, timeout=min(timeout, 8.0))
    auth_arg = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        auth_arg = (user, pwd)

    with httpx.Client(timeout=timeout, headers=headers) as client:
        resp = client.get(url, auth=auth_arg)
        if resp.status_code == 401 and token:
            # Token may have expired or server expects HTTP Basic directly; retry once with Basic Auth
            with _TOKEN_LOCK:
                _CACHED_TOKEN["token"] = None
            headers.pop("Authorization", None)
            resp = client.get(url, auth=(user, pwd))
        resp.raise_for_status()
        payload = resp.json()
    if not isinstance(payload, dict) or "data" not in payload:
        raise RuntimeError("Unexpected Meteomatics JSON payload structure")
    return payload


def _extract_param_series(payload: dict) -> dict[str, pd.Series]:
    """Parse Meteomatics single-point JSON payload into {parameter: Series(DatetimeIndex)}."""
    out: dict[str, pd.Series] = {}
    for entry in payload.get("data", []):
        pname = str(entry.get("parameter", ""))
        coords = entry.get("coordinates") or []
        if not pname or not coords:
            continue
        dates_list = coords[0].get("dates") or []
        idx_vals: list[pd.Timestamp] = []
        num_vals: list[float] = []
        for item in dates_list:
            ts_str = item.get("date")
            if not ts_str:
                continue
            v = _clean_val(item.get("value"))
            idx_vals.append(pd.to_datetime(ts_str, utc=True).tz_localize(None).floor("D"))
            num_vals.append(float("nan") if v is None else v)
        if idx_vals:
            ser = pd.Series(num_vals, index=pd.DatetimeIndex(idx_vals), name=pname, dtype=float)
            if ser.notna().any():
                out[pname] = ser[~ser.index.duplicated(keep="last")].sort_index()
    return out


def _query_param_batches(
    valid_datetime: str,
    params: list[str],
    location: str,
    extra_query: str = "",
) -> dict[str, pd.Series]:
    """Query parameters in Meteomatics-compliant batches (max 10/request), degrading per-parameter on tier errors."""
    if not params:
        return {}
    merged: dict[str, pd.Series] = {}
    for i in range(0, len(params), MAX_PARAMS_PER_QUERY):
        chunk = params[i : i + MAX_PARAMS_PER_QUERY]
        try:
            payload = _fetch_meteomatics_json(valid_datetime, ",".join(chunk), location, extra_query=extra_query)
            merged.update(_extract_param_series(payload))
        except httpx.HTTPStatusError as exc:
            # 400 / 403 / 404 often means one optional parameter in the batch isn't in user's license tier.
            if exc.response.status_code in (400, 403, 404) and len(params) > 1:
                if len(chunk) > 1:
                    for p in chunk:
                        try:
                            sub_payload = _fetch_meteomatics_json(valid_datetime, p, location, extra_query=extra_query)
                            merged.update(_extract_param_series(sub_payload))
                        except Exception as sub_exc:  # noqa: BLE001
                            log.debug("Meteomatics parameter %s unavailable on current plan: %s", p, sub_exc)
                else:
                    log.debug("Meteomatics parameter %s unavailable on current plan: %s", chunk[0], exc)
            else:
                raise
    return merged


def fetch_daily_weather(
    lat: float,
    lon: float,
    start: date,
    end: date,
    source: str = "mix",
) -> pd.DataFrame | None:
    """Fetch 90m-downscaled daily weather mapped to TerraLoop's canonical DataFrame schema.

    Columns returned when available:
      T2M_MAX (C), T2M_MIN (C), PRECTOTCORR (mm/day),
      ALLSKY_SFC_SW_DWN (MJ/m2/day via Wh * 0.0036), RH2M (%), WS2M (m/s), ET0 (mm/day).
    Returns None cleanly if Meteomatics credentials are unset or the call fails.
    """
    if not is_configured():
        return None
    vrange = f"{start.isoformat()}T00:00:00Z--{end.isoformat()}T00:00:00Z:P1D"
    loc = f"{round(lat, 4)},{round(lon, 4)}"
    params = [
        "t_max_2m_24h:C",
        "t_min_2m_24h:C",
        "precip_24h:mm",
        "global_rad_24h:Wh",
        "relative_humidity_2m:p",
        "wind_speed_2m:ms",
        "evapotranspiration_24h:mm",
    ]
    extra = f"source={source}" if source else ""
    try:
        series_map = _query_param_batches(vrange, params, loc, extra_query=extra)
    except Exception as exc:  # noqa: BLE001
        log.warning("Meteomatics daily weather fetch failed: %s", exc)
        return None

    if "t_max_2m_24h:C" not in series_map or "t_min_2m_24h:C" not in series_map:
        return None

    df = pd.DataFrame(index=series_map["t_max_2m_24h:C"].index)
    df.index.name = "date"
    df["T2M_MAX"] = series_map["t_max_2m_24h:C"]
    df["T2M_MIN"] = series_map["t_min_2m_24h:C"]
    df["PRECTOTCORR"] = (
        series_map["precip_24h:mm"].reindex(df.index).fillna(0.0).clip(lower=0.0)
        if "precip_24h:mm" in series_map
        else 0.0
    )
    if "global_rad_24h:Wh" in series_map:
        # 1 Wh/m2 = 0.0036 MJ/m2
        df["ALLSKY_SFC_SW_DWN"] = (series_map["global_rad_24h:Wh"] * 0.0036).clip(lower=1.0, upper=35.0)
    if "relative_humidity_2m:p" in series_map:
        df["RH2M"] = series_map["relative_humidity_2m:p"].clip(lower=5.0, upper=100.0)
    if "wind_speed_2m:ms" in series_map:
        df["WS2M"] = series_map["wind_speed_2m:ms"].clip(lower=0.1, upper=30.0)
    if "evapotranspiration_24h:mm" in series_map:
        df["ET0"] = series_map["evapotranspiration_24h:mm"].clip(lower=0.0, upper=20.0)
    clean_df = df.dropna(subset=["T2M_MAX", "T2M_MIN"]).sort_index()
    return None if clean_df.empty else clean_df


def fetch_cmip6_daily(
    lat: float,
    lon: float,
    ssp: str,
    start: str,
    end: str,
) -> pd.DataFrame | None:
    """Fetch 90m-downscaled CMIP6 MRI-ESM2.0 projections as live REST alternative to GEE NEX-GDDP.

    Returns DataFrame indexed by date with tasmax (C), tasmin (C), pr (mm/day),
    plus optional ALLSKY_SFC_SW_DWN, RH2M, WS2M when available.
    """
    if not is_configured():
        return None
    ssp_clean = ssp.lower().replace("-", "").strip()
    source_map = {
        "historical": "mri-esm2",
        "ssp126": "mri-esm2-ssp126",
        "ssp245": "mri-esm2-ssp245",
        "ssp370": "mri-esm2-ssp370",
        "ssp460": "mri-esm2-ssp460",
        "ssp585": "mri-esm2-ssp585",
    }
    mm_source = source_map.get(ssp_clean)
    if not mm_source:
        return None

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    span_days = max(0, (end_ts - start_ts).days)
    loc = f"{round(lat, 4)},{round(lon, 4)}"
    params = [
        "t_max_2m_24h:C",
        "t_min_2m_24h:C",
        "precip_24h:mm",
        "global_rad_24h:Wh",
        "relative_humidity_2m:p",
        "wind_speed_2m:ms",
    ]

    def _fetch_span(q_start: str, q_end: str) -> pd.DataFrame | None:
        vrange = f"{q_start}T00:00:00Z--{q_end}T00:00:00Z:P1D"
        try:
            series_map = _query_param_batches(vrange, params, loc, extra_query=f"source={mm_source}")
        except Exception as exc:  # noqa: BLE001
            log.warning("Meteomatics CMIP6 (%s) fetch failed: %s", mm_source, exc)
            return None

        if "t_max_2m_24h:C" not in series_map or "t_min_2m_24h:C" not in series_map:
            return None

        sub = pd.DataFrame(index=series_map["t_max_2m_24h:C"].index)
        sub.index.name = "date"
        sub["tasmax"] = series_map["t_max_2m_24h:C"]
        sub["tasmin"] = series_map["t_min_2m_24h:C"]
        sub["pr"] = (
            series_map["precip_24h:mm"].reindex(sub.index).fillna(0.0).clip(lower=0.0)
            if "precip_24h:mm" in series_map
            else 0.0
        )
        if "global_rad_24h:Wh" in series_map:
            sub["ALLSKY_SFC_SW_DWN"] = (series_map["global_rad_24h:Wh"] * 0.0036).clip(lower=1.0, upper=35.0)
        if "relative_humidity_2m:p" in series_map:
            sub["RH2M"] = series_map["relative_humidity_2m:p"].clip(lower=5.0, upper=100.0)
        if "wind_speed_2m:ms" in series_map:
            sub["WS2M"] = series_map["wind_speed_2m:ms"].clip(lower=0.1, upper=30.0)
        clean_sub = sub.dropna(subset=["tasmax", "tasmin"]).sort_index()
        return None if clean_sub.empty else clean_sub

    if span_days <= 366:
        df = _fetch_span(start, end)
        return df

    # Sample early, mid, and late representative years to preserve interannual climate variance
    # while bounding each REST call to <= 1 year.
    sample_years = list(dict.fromkeys([start_ts.year, (start_ts.year + end_ts.year) // 2, end_ts.year]))
    sample_by_doy: list[pd.DataFrame] = []
    for yr in sample_years:
        sub = _fetch_span(f"{yr}-01-01", f"{yr}-12-31")
        if sub is not None and not sub.empty:
            sub_doy = sub.copy()
            sub_doy["_doy"] = sub_doy.index.dayofyear
            by_doy = sub_doy.groupby("_doy").mean(numeric_only=True).reindex(range(1, 367)).bfill().ffill()
            sample_by_doy.append(by_doy)

    if not sample_by_doy:
        return None

    full_idx = pd.date_range(start_ts, end_ts, freq="D")
    n_samples = len(sample_by_doy)
    year_offsets = (full_idx.year - start_ts.year).to_numpy() % n_samples
    doys = np.clip(full_idx.dayofyear.to_numpy(), 1, 366)
    cols = sample_by_doy[0].columns
    out_arrays: dict[str, np.ndarray] = {c: np.empty(len(full_idx), dtype=float) for c in cols}
    sample_arrs = [{c: s[c].to_numpy() for c in cols} for s in sample_by_doy]
    for s_idx in range(n_samples):
        mask = year_offsets == s_idx
        if np.any(mask):
            doy_pos = doys[mask] - 1
            for c in cols:
                out_arrays[c][mask] = sample_arrs[s_idx][c][doy_pos]
    tiled = pd.DataFrame(out_arrays, index=full_idx)
    tiled.index.name = "date"
    return tiled


def fetch_soil_and_hazards_snapshot(
    lat: float,
    lon: float,
    ref_date: date | None = None,
) -> dict[str, Any] | None:
    """Fetch 90m 4-layer soil hydrology, seedbed temperature, and biotic/extreme agro-hazards."""
    if not is_configured():
        return None
    target_d = ref_date or datetime.now(UTC).date()
    vdt = f"{target_d.isoformat()}T06:00:00Z"
    loc = f"{round(lat, 4)},{round(lon, 4)}"
    params = [
        "soil_moisture_deficit:mm",
        "soil_moisture_index_-5cm:idx",
        "soil_moisture_index_-15cm:idx",
        "soil_moisture_index_-50cm:idx",
        "soil_moisture_index_-150cm:idx",
        "volumetric_soil_water_-5cm:m3m3",
        "volumetric_soil_water_-15cm:m3m3",
        "volumetric_soil_water_-50cm:m3m3",
        "volumetric_soil_water_-150cm:m3m3",
        "t_-5cm:C",
        "phytophthora_negative:idx",
        "leaf_wetness:idx",
        "hail_24h:cm",
        "fosberg_fire_weather_index:idx",
        "drought_index:idx",
        "precip_30min:mm",
    ]
    try:
        series_map = _query_param_batches(vdt, params, loc)
    except Exception as exc:  # noqa: BLE001
        log.warning("Meteomatics soil/hazards snapshot failed: %s", exc)
        return None

    if not series_map:
        return None

    def _first(key: str) -> float | None:
        ser = series_map.get(key)
        if ser is None or ser.empty:
            return None
        val = ser.iloc[0]
        return None if pd.isna(val) else round(float(val), 3)

    smi_layers: dict[str, float] = {}
    for depth in ("-5cm", "-15cm", "-50cm", "-150cm"):
        val = _first(f"soil_moisture_index_{depth}:idx")
        if val is not None:
            smi_layers[depth] = round(val, 2)

    vwc_layers: dict[str, float] = {}
    for depth in ("-5cm", "-15cm", "-50cm", "-150cm"):
        val = _first(f"volumetric_soil_water_{depth}:m3m3")
        if val is not None:
            vwc_layers[depth] = round(val, 3)

    hail_cm = _first("hail_24h:cm")
    hail_prob_pct = None
    if hail_cm is not None and hail_cm > 0.0:
        # Map active hailstone size detection into probabilistic exposure indicator (%)
        hail_prob_pct = round(min(100.0, hail_cm * 35.0), 1)

    p30_mm = _first("precip_30min:mm")
    max_30m_rate_mmh = round(p30_mm * 2.0, 2) if p30_mm is not None and p30_mm > 0.0 else None

    deficit_mm = _first("soil_moisture_deficit:mm")
    return {
        "soil_moisture_deficit_mm": round(max(0.0, deficit_mm), 1) if deficit_mm is not None else None,
        "soil_moisture_index_layers": smi_layers or None,
        "volumetric_soil_water_layers": vwc_layers or None,
        "seedbed_temp_5cm_c": round(_first("t_-5cm:C"), 1) if _first("t_-5cm:C") is not None else None,
        "late_blight_risk_idx": (
            round(_first("phytophthora_negative:idx"), 1)
            if _first("phytophthora_negative:idx") is not None
            else None
        ),
        "canopy_wetness_idx": _first("leaf_wetness:idx"),
        "hail_probability_pct": hail_prob_pct,
        "fire_weather_index": (
            round(_first("fosberg_fire_weather_index:idx"), 1)
            if _first("fosberg_fire_weather_index:idx") is not None
            else None
        ),
        "meteorological_drought_idx": (
            round(_first("drought_index:idx"), 2) if _first("drought_index:idx") is not None else None
        ),
        "max_30m_precip_rate_mmh": max_30m_rate_mmh,
        "provenance": METEOMATICS_MIX_PROVENANCE.model_copy(
            update={"period": target_d.isoformat(), "mode": "observed"}
        ),
    }


def fetch_srtm_slope_pct(lat: float, lon: float) -> float | None:
    """Compute local terrain slope (%) via a 3x3 micro-grid of Meteomatics NASA SRTM 90m elevation."""
    if not is_configured():
        return None
    d_deg = 0.0009  # ~90-100m cell spacing
    pts = [
        f"{round(lat + d_deg, 5)},{round(lon, 5)}",
        f"{round(lat - d_deg, 5)},{round(lon, 5)}",
        f"{round(lat, 5)},{round(lon + d_deg, 5)}",
        f"{round(lat, 5)},{round(lon - d_deg, 5)}",
    ]
    # Static terrain elevation: use a fixed reference date so disk caching persists across days
    vdt = "2024-01-01T00:00:00Z"
    try:
        payload = _fetch_meteomatics_json(vdt, "elevation:m", "+".join(pts))
    except Exception as exc:  # noqa: BLE001
        log.debug("Meteomatics SRTM slope fallback failed: %s", exc)
        return None

    elevs: list[float] = []
    for entry in payload.get("data", []):
        for coord in entry.get("coordinates", []):
            dates = coord.get("dates") or []
            if dates:
                v = _clean_val(dates[0].get("value"))
                if v is not None:
                    elevs.append(v)
    if len(elevs) != 4:
        return None
    e_n, e_s, e_e, e_w = elevs
    dy_m = 2.0 * d_deg * 111320.0
    dx_m = 2.0 * d_deg * 111320.0 * max(0.2, math.cos(math.radians(lat)))
    dz_dy = (e_n - e_s) / dy_m
    dz_dx = (e_e - e_w) / dx_m
    slope = math.hypot(dz_dx, dz_dy) * 100.0

    from .. import region_registry

    reg_slope = region_registry.get_regional_slope(lat, lon)
    raw_pct = round(float(np.clip(slope, 0.0, 60.0)), 2)
    # Suppress 90m SRTM radar integer quantization / micro-canopy jumps on flat alluvial plains
    if reg_slope <= 1.0 and raw_pct > 1.8:
        return float(round(min(1.2, reg_slope + 0.1 * (raw_pct - 2.0)), 2))
    if raw_pct > reg_slope * 2.2:
        return float(round(0.6 * reg_slope + 0.25 * raw_pct, 2))
    return raw_pct


def _build_tactical_advisory_from_days(
    forecast_days: list[TacticalDayForecast],
    seedbed_temp: float | None,
    deficit_mm: float | None,
    fire_idx: float | None,
    provenance: list[DataProvenance],
) -> TacticalAdvisory:
    next_7d_precip = round(sum(d.precip_mm for d in forecast_days[:7]), 1)
    next_7d_et0 = round(sum(d.et0_mm for d in forecast_days[:7]), 1)

    s_code: str = "optimal"
    sowing_ready = True
    if seedbed_temp is not None:
        if seedbed_temp < 11.0:
            s_code = "too_cold"
            sowing_ready = False
        elif seedbed_temp > 34.0:
            s_code = "too_hot"
            sowing_ready = False
    if deficit_mm is not None and deficit_mm > 65.0:
        s_code = "too_dry"
        sowing_ready = False
    elif forecast_days and sum(d.precip_mm for d in forecast_days[:3]) > 75.0:
        s_code = "waterlogged"
        sowing_ready = False

    if sum(d.precip_mm for d in forecast_days[:3]) >= 15.0 or (
        forecast_days and forecast_days[0].prob_precip_pct >= 65.0
    ):
        irr_action = "hold_rain_ahead"
    elif (deficit_mm is not None and deficit_mm >= 40.0) or (next_7d_et0 - next_7d_precip > 24.0):
        irr_action = "irrigate_soon"
    else:
        irr_action = "adequate_moisture"

    first_2d = forecast_days[:2]
    high_rain_prob = any(d.prob_precip_pct >= 55.0 or d.precip_mm >= 8.0 for d in first_2d)
    high_wind = any(d.wind_speed_ms >= 5.5 for d in first_2d)
    urea_safe = not (high_rain_prob or high_wind)

    return TacticalAdvisory(
        sowing_ready=sowing_ready,
        sowing_status_code=s_code,  # type: ignore[arg-type]
        irrigation_action=irr_action,  # type: ignore[arg-type]
        urea_spray_safe=urea_safe,
        next_7d_precip_mm=next_7d_precip,
        next_7d_et0_mm=next_7d_et0,
        seedbed_temp_5cm_c=round(seedbed_temp, 1) if seedbed_temp is not None else None,
        soil_moisture_deficit_mm=round(deficit_mm, 1) if deficit_mm is not None else None,
        fire_weather_index=round(fire_idx, 1) if fire_idx is not None else None,
        forecast_days=forecast_days,
        provenance=provenance,
    )


def fetch_tactical_forecast(
    lat: float,
    lon: float,
    days: int = 7,
    start_date: date | None = None,
) -> TacticalAdvisory | None:
    """Fetch 7-day 90m tactical farm forecast from Meteomatics (sowing, irrigation, Urea/spray safety)."""
    if not is_configured():
        return None
    d0 = start_date or datetime.now(UTC).date()
    d1 = d0 + timedelta(days=max(1, days - 1))
    # Query at 12:00 UTC (17:30 IST afternoon) so wind_speed_2m and soil heat reflect daytime operational conditions
    vrange = f"{d0.isoformat()}T12:00:00Z--{d1.isoformat()}T12:00:00Z:P1D"
    loc = f"{round(lat, 4)},{round(lon, 4)}"
    params = [
        "t_max_2m_24h:C",
        "t_min_2m_24h:C",
        "precip_24h:mm",
        "prob_precip_24h:p",
        "evapotranspiration_24h:mm",
        "wind_speed_2m:ms",
        "t_-5cm:C",
        "soil_moisture_deficit:mm",
        "fosberg_fire_weather_index:idx",
    ]
    try:
        series_map = _query_param_batches(vrange, params, loc)
    except Exception as exc:  # noqa: BLE001
        log.warning("Meteomatics tactical forecast fetch failed: %s", exc)
        return None

    tx_s = series_map.get("t_max_2m_24h:C")
    tn_s = series_map.get("t_min_2m_24h:C")
    if tx_s is None or tn_s is None or tx_s.dropna().empty:
        return None

    days_out: list[TacticalDayForecast] = []
    for ts in tx_s.dropna().index[:days]:
        tmax = float(tx_s.loc[ts])
        tmin = (
            float(tn_s.loc[ts])
            if (ts in tn_s.index and not pd.isna(tn_s.loc[ts]))
            else tmax - 10.0
        )

        def _at(key: str, default: float | None = 0.0, _ts: pd.Timestamp = ts) -> float | None:
            s = series_map.get(key)
            if s is None or _ts not in s.index or pd.isna(s.loc[_ts]):
                return default
            return float(s.loc[_ts])

        et0_raw = _at("evapotranspiration_24h:mm", default=None)
        if et0_raw is None:
            et0_raw = float(agroclimate.et0_hargreaves(pd.Series([tmax]), pd.Series([tmin]), lat, index=pd.DatetimeIndex([ts])).iloc[0])

        days_out.append(
            TacticalDayForecast(
                date=ts.strftime("%Y-%m-%d"),
                tmax_c=round(tmax, 1),
                tmin_c=round(tmin, 1),
                precip_mm=round(max(0.0, float(_at("precip_24h:mm", 0.0) or 0.0)), 1),
                prob_precip_pct=round(float(np.clip(_at("prob_precip_24h:p", 10.0) or 0.0, 0.0, 100.0)), 1),
                et0_mm=round(max(0.0, float(et0_raw)), 1),
                wind_speed_ms=round(max(0.2, float(_at("wind_speed_2m:ms", 2.0) or 2.0)), 1),
                soil_temp_5cm_c=round(float(v), 1) if (v := _at("t_-5cm:C", default=None)) is not None else None,
                soil_moisture_deficit_mm=(
                    round(max(0.0, float(v)), 1)
                    if (v := _at("soil_moisture_deficit:mm", default=None)) is not None
                    else None
                ),
            )
        )

    if not days_out:
        return None

    prov = METEOMATICS_MIX_PROVENANCE.model_copy(
        update={"period": f"{d0.isoformat()} to {d1.isoformat()}", "mode": "observed"}
    )
    fire_s = series_map.get("fosberg_fire_weather_index:idx")
    fire_val = float(fire_s.dropna().iloc[0]) if fire_s is not None and not fire_s.dropna().empty else None
    return _build_tactical_advisory_from_days(
        forecast_days=days_out,
        seedbed_temp=days_out[0].soil_temp_5cm_c,
        deficit_mm=days_out[0].soil_moisture_deficit_mm,
        fire_idx=fire_val,
        provenance=[prov],
    )


def estimate_regional_tactical_and_hazards(
    lat: float,
    lon: float,
    climate: ClimateSummary,
    soil: SoilSummary,
    water: WaterSummary,
    hazards: HazardSummary,
    ref_date: date | None = None,
) -> tuple[dict[str, Any], TacticalAdvisory]:
    """Deterministic regional climatology fallback for Meteomatics 90m tactical & agro-hazard fields.

    Labeled strictly as mode='regional_climatology' so users know live Meteomatics API
    credentials are inactive while preserving realistic physical behavior.
    """
    d0 = ref_date or datetime.now(UTC).date()
    mo_idx = max(0, min(11, d0.month - 1))
    m_tx = float(climate.monthly_tmax_c[mo_idx])
    m_tn = float(climate.monthly_tmin_c[mo_idx])
    m_pr_day = float(climate.monthly_precip_mm[mo_idx]) / 30.0
    m_tmean = 0.5 * (m_tx + m_tn)
    et0_day = float(climate.annual_et0_mm or 1500.0) / 365.0

    # Derive topsoil 5cm temperature and 4-layer moisture indices from regional climate & SMAP percentiles
    seedbed_t = round(m_tmean + 1.2, 1)
    smap_p = None
    if water.root_zone_moisture_percentile and len(water.root_zone_moisture_percentile) == 12:
        smap_p = float(water.root_zone_moisture_percentile[mo_idx])
    smi_base = round(float(np.clip((smap_p if smap_p is not None else 48.0) / 100.0, 0.15, 0.95)), 2)
    smi_layers = {
        "-5cm": round(float(np.clip(smi_base - (0.08 if m_pr_day < 1.5 else -0.05), 0.10, 0.98)), 2),
        "-15cm": smi_base,
        "-50cm": round(float(np.clip(smi_base + 0.05, 0.15, 0.98)), 2),
        "-150cm": round(float(np.clip(smi_base + 0.08, 0.20, 0.98)), 2),
    }

    fc = soil.field_capacity_vol or 0.28
    wp = soil.wilting_point_vol or 0.12
    avail_cap = max(0.06, fc - wp)
    vwc_layers = {
        depth: round(float(np.clip(wp + smi_val * avail_cap, 0.04, 0.50)), 3)
        for depth, smi_val in smi_layers.items()
    }
    taw_1m = max(60.0, (fc - wp) * 1000.0)
    deficit_mm = round(float(np.clip((1.0 - smi_base) * 0.55 * taw_1m, 8.0, 85.0)), 1)

    est_p30_rate = round(
        float(
            np.clip(
                18.0
                + (climate.annual_precip_mm or 700.0) * 0.015
                + (max(climate.monthly_precip_mm) if climate.monthly_precip_mm else 150.0) * 0.06,
                18.0,
                68.0,
            )
        ),
        1,
    )

    rh_est = float(np.clip(35.0 + m_pr_day * 5.0, 25.0, 88.0))
    leaf_wetness = round(float(np.clip((rh_est - 40.0) / 60.0 + (0.15 if m_pr_day > 3.0 else 0.0), 0.05, 0.92)), 2)
    late_blight_idx = round(
        85.0 + (75.0 if 14.0 <= m_tmean <= 24.0 and leaf_wetness >= 0.50 else 15.0) + min(40.0, m_pr_day * 4.0),
        1,
    )
    fire_idx = round(float(np.clip((m_tx - 18.0) * 1.6 + (65.0 - rh_est) * 0.65, 8.0, 78.0)), 1)
    hail_prob = 12.0 if (d0.month in (2, 3, 4) and m_tn < 18.0) else 2.0
    drought_idx = round(float(np.clip((smi_base - 0.50) * 4.0, -3.5, 3.5)), 2)

    forecast_days: list[TacticalDayForecast] = []
    for offset in range(7):
        dt = d0 + timedelta(days=offset)
        wave = math.sin((offset + int(abs(lat * 10))) * 0.9)
        rain_d = round(max(0.0, m_pr_day * (1.1 + 0.5 * wave)), 1)
        prob_p = round(float(np.clip(rain_d * 8.0 + (8.0 if m_pr_day > 2.0 else 2.0), 3.0, 85.0)), 1)
        forecast_days.append(
            TacticalDayForecast(
                date=dt.isoformat(),
                tmax_c=round(m_tx + 0.8 * wave, 1),
                tmin_c=round(m_tn + 0.5 * wave, 1),
                precip_mm=rain_d,
                prob_precip_pct=prob_p,
                et0_mm=round(max(1.0, et0_day + 0.3 * wave), 1),
                wind_speed_ms=round(2.2 + 0.6 * abs(wave), 1),
                soil_temp_5cm_c=round(seedbed_t + 0.4 * wave, 1),
                soil_moisture_deficit_mm=round(max(5.0, deficit_mm + (offset * (et0_day - rain_d)) * 0.5), 1),
            )
        )

    prov = DataProvenance(
        source="Regional Climatology Baseline (Meteomatics Schema)",
        product="Synthesized 7-Day Field Operations & Soil Moisture Climatology (Live API Credentials Unset)",
        period=f"{d0.isoformat()} to {(d0 + timedelta(days=6)).isoformat()}",
        resolution="Regional baseline (live 90m requires METEOMATICS_USERNAME)",
        url="https://www.meteomatics.com/en/api/getting-started/",
        mode="regional_climatology",
    )
    advisory = _build_tactical_advisory_from_days(
        forecast_days=forecast_days,
        seedbed_temp=seedbed_t,
        deficit_mm=deficit_mm,
        fire_idx=fire_idx,
        provenance=[prov],
    )
    snapshot_meta = {
        "soil_moisture_deficit_mm": deficit_mm,
        "soil_moisture_index_layers": smi_layers,
        "volumetric_soil_water_layers": vwc_layers,
        "seedbed_temp_5cm_c": seedbed_t,
        "late_blight_risk_idx": late_blight_idx if hazards.late_blight_risk_idx is None else hazards.late_blight_risk_idx,
        "canopy_wetness_idx": leaf_wetness if hazards.canopy_wetness_idx is None else hazards.canopy_wetness_idx,
        "hail_probability_pct": hail_prob if hazards.hail_probability_pct is None else hazards.hail_probability_pct,
        "fire_weather_index": fire_idx if hazards.fire_weather_index is None else hazards.fire_weather_index,
        "meteorological_drought_idx": (
            drought_idx if hazards.meteorological_drought_idx is None else hazards.meteorological_drought_idx
        ),
        "max_30m_precip_rate_mmh": est_p30_rate if hazards.max_30m_precip_rate_mmh is None else hazards.max_30m_precip_rate_mmh,
        "provenance": prov,
    }
    return snapshot_meta, advisory
