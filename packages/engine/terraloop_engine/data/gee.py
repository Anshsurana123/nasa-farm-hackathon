"""Google Earth Engine helpers for NASA collections. (TASK-D02, D03, D05-D09)

GEE is our PRIMARY access path for NASA data (decision in docs/BUILD_PLAN.md 4.1).
Install: ``uv pip install -e packages/engine[gee]`` then ``earthengine authenticate``.
Set env ``GEE_PROJECT`` to your Google Cloud project id.

Every public function:
  * accepts (lat, lon[, buffer_m]) or coordinates,
  * returns plain Python / pandas objects (never ee.* objects),
  * caches LIVE GEE responses with ``@disk_cache`` (never caches synthetic fallbacks),
  * exposes a ``PROVENANCE`` DataProvenance with the NASA product id + DOI.
"""

from __future__ import annotations

import logging
import os
import zlib
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

import numpy as np
import pandas as pd
from terraloop_schemas import DataProvenance

from ..cache import disk_cache

log = logging.getLogger(__name__)

_initialised = False


def _load_dotenv_if_needed() -> None:
    """Load GEE_PROJECT and credentials from workspace .env if not already present in os.environ."""
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

IMERG_PROVENANCE = DataProvenance(
    source="NASA GPM IMERG",
    product="GPM_3IMERGDF (V07)",
    period="2000-2024",
    resolution="0.1 deg, daily",
    doi="10.5067/GPM/IMERGDF/DAY/07",
    url="https://gpm.nasa.gov/data/imerg",
)

SMAP_PROVENANCE = DataProvenance(
    source="NASA SMAP",
    product="SPL4SMGP V008 (L4 Root-Zone Soil Moisture)",
    period="2015-2024",
    resolution="9 km, daily",
    doi="10.5067/K2VT90DE20GV",
    url="https://smap.jpl.nasa.gov/",
)

GRACE_PROVENANCE = DataProvenance(
    source="NASA GRACE / GRACE-FO",
    product="Tellus Regional Terrestrial Water Storage (TWS) Mascon (JPL V04, 3° native)",
    period="2002-2024",
    resolution="0.5 deg grid (native ~3 deg mascon), monthly",
    doi="10.5067/TEMSC-3MJ62",
    url="https://grace.jpl.nasa.gov/",
)

NASADEM_PROVENANCE = DataProvenance(
    source="NASA NASADEM",
    product="NASADEM_HGT (30 m DEM)",
    resolution="30 m",
    doi="10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001",
    url="https://earthdata.nasa.gov/",
)

FIRMS_PROVENANCE = DataProvenance(
    source="NASA FIRMS",
    product="MODIS / VIIRS Active Fire Detections",
    period="2019-2024",
    resolution="375 m / 1 km",
    doi="10.5067/FIRMS/MODIS",
    url="https://firms.modaps.eosdis.nasa.gov/",
)

HLS_PROVENANCE = DataProvenance(
    source="NASA HLS",
    product="HLSL30 / HLSS30 (Harmonized Landsat Sentinel-2)",
    period="2019-2024",
    resolution="30 m, 2-3 day",
    doi="10.5067/HLS/HLSL30.002",
    url="https://hls.gsfc.nasa.gov/",
)

CMIP6_PROVENANCE = DataProvenance(
    source="NASA NEX-GDDP-CMIP6",
    product="Downscaled Climate Projections",
    period="2015-2100",
    resolution="0.25 deg, daily",
    doi="10.7917/OASIS/NEX-GDDP-CMIP6",
    url="https://www.nasa.gov/nex/gddp",
)


def _resolve_credentials(ee_module) -> tuple[object | None, str | None]:
    """Resolve Earth Engine credentials and project from environment.

    Supports headless/serverless deployments (Vercel, Cloud Run, Docker):
      1. GEE_SERVICE_ACCOUNT_KEY (or EE_SERVICE_ACCOUNT_KEY):
         - Raw JSON string of service account key
         - Base64-encoded JSON string
         - Path to a service account JSON file
      2. GOOGLE_APPLICATION_CREDENTIALS: path to service account JSON file
      3. GEE_PROJECT: explicit project ID override

    Returns (credentials, project_id).
    """
    import base64
    import json

    try:
        from google.oauth2 import service_account
    except ImportError:
        return None, None

    scopes = getattr(
        getattr(ee_module, "oauth", None),
        "SCOPES",
        [
            "https://www.googleapis.com/auth/earthengine",
            "https://www.googleapis.com/auth/cloud-platform",
        ],
    )

    raw_key = os.environ.get("GEE_SERVICE_ACCOUNT_KEY") or os.environ.get("EE_SERVICE_ACCOUNT_KEY")
    if raw_key:
        raw_key = raw_key.strip()
        # Case A: File path
        try:
            key_path = Path(raw_key)
            if key_path.is_file():
                creds = service_account.Credentials.from_service_account_file(str(key_path), scopes=scopes)
                proj = getattr(creds, "project_id", None)
                return creds, proj
        except (OSError, ValueError) as exc:
            log.debug("GEE service account file read skipped: %s", exc)

        # Case B: Inline JSON or Base64-encoded JSON
        key_dict = None
        if raw_key.startswith("{"):
            try:
                key_dict = json.loads(raw_key)
            except json.JSONDecodeError as exc:
                log.debug("GEE_SERVICE_ACCOUNT_KEY JSON decode skipped: %s", exc)
        else:
            try:
                decoded = base64.b64decode(raw_key).decode("utf-8")
                if decoded.strip().startswith("{"):
                    key_dict = json.loads(decoded)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                log.debug("GEE_SERVICE_ACCOUNT_KEY base64 decode skipped: %s", exc)

        if key_dict and isinstance(key_dict, dict):
            creds = service_account.Credentials.from_service_account_info(key_dict, scopes=scopes)
            proj = key_dict.get("project_id")
            return creds, proj

    gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if gac:
        try:
            gac_path = Path(gac)
            if gac_path.is_file():
                creds = service_account.Credentials.from_service_account_file(str(gac_path), scopes=scopes)
                proj = getattr(creds, "project_id", None)
                return creds, proj
        except (OSError, ValueError) as exc:
            log.debug("GOOGLE_APPLICATION_CREDENTIALS read skipped: %s", exc)

    return None, None


def init() -> bool:
    """Initialise Earth Engine once per process. Returns True if successfully initialized."""
    global _initialised
    if os.environ.get("GEE_DISABLE") == "1":
        return False
    if _initialised:
        return True
    try:
        _load_dotenv_if_needed()
        import ee

        creds, creds_proj = _resolve_credentials(ee)
        project = os.environ.get("GEE_PROJECT") or creds_proj
        if creds is not None:
            ee.Initialize(credentials=creds, project=project)
        else:
            ee.Initialize(project=project)
        deadline_ms = int(float(os.environ.get("GEE_DEADLINE_MS", "18000")))
        if deadline_ms > 0:
            try:
                ee.data.setDeadline(deadline_ms)
            except Exception as exc:  # noqa: BLE001
                log.debug("ee.data.setDeadline ignored: %s", exc)
        _initialised = True
        return True
    except Exception as exc:  # noqa: BLE001
        log.info("GEE init skipped or failed: %s (using un-cached regional climatology)", exc)
        return False


def is_live() -> bool:
    """Return True if Google Earth Engine is initialized and active."""
    if os.environ.get("GEE_DISABLE") == "1":
        return False
    return _initialised


def provenance_with_mode(
    prov: DataProvenance,
    mode: str | None = None,
    unknown_if_offline: bool = False,
) -> DataProvenance:
    """Return a copy of the provenance tagged with the actual data collection mode.

    If ``mode`` is explicitly provided, it is used.
    Otherwise, if GEE is live, mode is 'observed'.
    When GEE is offline, mode is 'unknown' if ``unknown_if_offline=True``, else 'regional_climatology'.
    """
    if mode is not None:
        effective_mode = mode
    elif is_live():
        effective_mode = "observed"
    else:
        effective_mode = "unknown" if unknown_if_offline else "regional_climatology"
    return prov.model_copy(update={"mode": effective_mode})


def _run_parallel_chunks(fn, tasks: list, max_workers: int = 6, timeout_sec: float = 18.0) -> list:
    """Execute independent GEE chunk queries in parallel with non-blocking shutdown on timeout."""
    if not tasks:
        return []
    workers = max(1, min(max_workers, len(tasks)))
    pool = ThreadPoolExecutor(max_workers=workers)
    results: list = []
    try:
        futures = [pool.submit(fn, t) for t in tasks]
        done, not_done = wait(futures, timeout=timeout_sec)
        for fut in not_done:
            fut.cancel()
        for fut in done:
            try:
                res = fut.result()
                if res is not None:
                    results.append(res)
            except Exception as exc:  # noqa: BLE001
                log.debug("GEE parallel chunk error: %s", exc)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return results


@disk_cache(namespace="gee_imerg_live")
def _imerg_daily_live(lat: float, lon: float, start: str, end: str) -> pd.Series:
    import ee

    pt = ee.Geometry.Point([lon, lat])
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    n_days = max(1, (end_ts - start_ts).days)

    if n_days <= 60:
        col = (
            ee.ImageCollection("NASA/GPM_L3/IMERG_V07")
            .filterBounds(pt)
            .filterDate(start, end)
            .select("precipitation")
        )
        data = col.getRegion(pt, 10000).getInfo()
        if len(data) <= 1:
            raise RuntimeError("Empty IMERG response from GEE")
        df_ee = pd.DataFrame(data[1:], columns=data[0])
        df_ee["date"] = pd.to_datetime(df_ee["time"], unit="ms").dt.date
        # IMERG_V07 half-hourly rate (mm/hr) * 0.5 hr = mm per 30-min interval
        daily = df_ee.groupby("date")["precipitation"].sum() * 0.5
        return pd.Series(daily.values, index=pd.to_datetime(daily.index), name="precipitation_mm")

    # Parallel server-side daily summation per 90-day block from IMERG_V07 half-hourly scenes (preserves true daily extremes)
    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    chunk_start = start_ts
    while chunk_start < end_ts:
        chunk_end = min(chunk_start + pd.Timedelta(days=90), end_ts)
        windows.append((chunk_start, chunk_end))
        chunk_start = chunk_end

    def _fetch_imerg_chunk(bounds: tuple[pd.Timestamp, pd.Timestamp]) -> pd.Series | None:
        c_start, c_end = bounds
        c_days = max(1, (c_end - c_start).days)
        raw_col = (
            ee.ImageCollection("NASA/GPM_L3/IMERG_V07")
            .filterBounds(pt)
            .filterDate(c_start.strftime("%Y-%m-%d"), c_end.strftime("%Y-%m-%d"))
            .select("precipitation")
        )

        def _make_mapper(start_s: str, collection: ee.ImageCollection):
            base_d = ee.Date(start_s)

            def _make_daily(offset):
                d0 = base_d.advance(offset, "day")
                d1 = d0.advance(1, "day")
                day_col = collection.filterDate(d0, d1)
                img = ee.Image(
                    ee.Algorithms.If(
                        day_col.size().gt(0),
                        day_col.mean().multiply(24.0),
                        ee.Image.constant(-1.0).rename("precipitation").toFloat(),
                    )
                )
                return img.set("system:time_start", d0.millis())

            return _make_daily

        daily_col = ee.ImageCollection.fromImages(
            ee.List.sequence(0, c_days - 1).map(_make_mapper(c_start.strftime("%Y-%m-%d"), raw_col))
        )
        data = daily_col.getRegion(pt, 10000).getInfo()
        if len(data) <= 1:
            return None
        df_c = pd.DataFrame(data[1:], columns=data[0]).dropna(subset=["precipitation"])
        df_c = df_c[df_c["precipitation"].astype(float) >= 0.0]
        if df_c.empty:
            return None
        df_c["date"] = pd.to_datetime(df_c["time"], unit="ms").dt.floor("D")
        return pd.Series(
            np.maximum(0.0, df_c["precipitation"].astype(float).to_numpy()),
            index=df_c["date"],
        )

    daily_frames = _run_parallel_chunks(_fetch_imerg_chunk, windows, max_workers=6, timeout_sec=18.0)

    if not daily_frames:
        raise RuntimeError("Empty daily IMERG response from GEE")
    combined = pd.concat(daily_frames).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    combined.name = "precipitation_mm"
    return combined


def imerg_daily(lat: float, lon: float, start: str, end: str) -> pd.Series:
    """TASK-D03: Daily precipitation (mm) from GPM IMERG V07."""
    if init():
        try:
            return _imerg_daily_live(lat, lon, start, end)
        except Exception as exc:  # noqa: BLE001
            log.warning("GEE IMERG call failed: %s, using regional climatology", exc)

    idx = pd.date_range(start, end, freq="D")
    rng = np.random.default_rng(int(abs(lat * 100 + lon * 10)))

    # Regional Indian monsoon distribution
    from .. import region_registry
    reg = region_registry.detect_region_config(lat, lon)

    if reg.region_id in ("cauvery", "southern_hills"):
        # Southern Peninsula / Cauvery Delta (NE + SW monsoon, Oct-Dec peak + Jul-Sep)
        wet_season = (idx.month >= 8) & (idx.month <= 12)
        rain_prob = np.where(wet_season, 0.38, 0.07)
        rain_amounts = np.where(wet_season, rng.gamma(1.3, 14.0, len(idx)), rng.gamma(0.8, 5.0, len(idx)))
    elif reg.region_id in ("punjab_southwest", "rajasthan_arid"):
        # Bathinda Semi-Arid SW Punjab (~420 mm/yr)
        monsoon = (idx.month >= 7) & (idx.month <= 9)
        rain_prob = np.where(monsoon, 0.24, 0.04)
        rain_amounts = np.where(monsoon, rng.gamma(1.1, 11.5, len(idx)), rng.gamma(0.7, 4.0, len(idx)))
    else:
        # Central Punjab / Bundelkhand / Vidarbha (~650-850 mm/yr Jul-Sep monsoon)
        monsoon = (idx.month >= 7) & (idx.month <= 9)
        rain_prob = np.where(monsoon, 0.35, 0.05)
        rain_amounts = np.where(monsoon, rng.gamma(1.2, 14.0, len(idx)), rng.gamma(0.8, 5.0, len(idx)))

    has_rain = rng.random(len(idx)) < rain_prob
    rain = np.where(has_rain, np.round(rain_amounts, 1), 0.0)
    return pd.Series(rain, index=idx, name="precipitation_mm")


@disk_cache(namespace="gee_smap_live")
def _smap_rootzone_live(lat: float, lon: float, start: str, end: str) -> pd.Series:
    import ee

    pt = ee.Geometry.Point([lon, lat])
    start_ts = max(pd.Timestamp("2015-04-01"), pd.Timestamp(start))
    end_ts = pd.Timestamp(end)
    if start_ts >= end_ts:
        raise RuntimeError("Invalid SMAP date range")

    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    chunk_start = start_ts
    while chunk_start < end_ts:
        chunk_end = min(chunk_start + pd.Timedelta(days=365), end_ts)
        windows.append((chunk_start, chunk_end))
        chunk_start = chunk_end

    def _fetch_smap_chunk(bounds: tuple[pd.Timestamp, pd.Timestamp]) -> pd.Series | None:
        c_start, c_end = bounds
        col = (
            ee.ImageCollection("NASA/SMAP/SPL4SMGP/008")
            .filterBounds(pt)
            .filterDate(c_start.strftime("%Y-%m-%d"), c_end.strftime("%Y-%m-%d"))
            .filter(ee.Filter.calendarRange(13, 13, "hour"))
            .select("sm_rootzone")
        )
        data = col.getRegion(pt, 9000).getInfo()
        if len(data) <= 1:
            return None
        df_ee = pd.DataFrame(data[1:], columns=data[0]).dropna(subset=["sm_rootzone"])
        if df_ee.empty:
            return None
        df_ee["date"] = pd.to_datetime(df_ee["time"], unit="ms").dt.date
        daily = df_ee.groupby("date")["sm_rootzone"].mean()
        return pd.Series(daily.values, index=pd.to_datetime(daily.index))

    chunks = _run_parallel_chunks(_fetch_smap_chunk, windows, max_workers=6, timeout_sec=20.0)

    if not chunks:
        raise RuntimeError("Empty SMAP response from GEE")
    out = pd.concat(chunks).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    out.name = "sm_rootzone_m3_m3"
    return out


def smap_rootzone(lat: float, lon: float, start: str, end: str) -> pd.Series:
    """TASK-D04: Daily mean root-zone soil moisture (m3/m3) from SMAP L4."""
    if init():
        try:
            return _smap_rootzone_live(lat, lon, start, end)
        except Exception as exc:  # noqa: BLE001
            log.warning("GEE SMAP call failed: %s, using regional climatology", exc)

    idx = pd.date_range(start, end, freq="D")
    doy = idx.dayofyear.to_numpy()
    years = (idx.year - idx.year.min()).to_numpy()

    from .. import region_registry
    reg = region_registry.detect_region_config(lat, lon)

    if reg.region_id == "bundelkhand":
        sm_base = 0.18 + 0.09 * np.sin(2 * np.pi * (doy - 205) / 365) - 0.004 * years
    elif reg.region_id == "vidarbha":
        sm_base = 0.24 + 0.10 * np.sin(2 * np.pi * (doy - 210) / 365) - 0.003 * years
    elif reg.region_id in ("punjab_southwest", "rajasthan_arid"):
        sm_base = 0.17 + 0.07 * np.sin(2 * np.pi * (doy - 200) / 365) - 0.002 * years
    elif reg.region_id in ("cauvery", "southern_hills"):
        sm_base = 0.28 + 0.08 * np.sin(2 * np.pi * (doy - 270) / 365) + 0.002 * years
    else:
        sm_base = 0.23 + 0.08 * np.sin(2 * np.pi * (doy - 200) / 365) - 0.001 * years

    rng = np.random.default_rng(int(abs(lat * 100 + lon)))
    noise = rng.normal(0.0, 0.015, len(idx))
    sm_vals = np.clip(sm_base + noise, 0.08, 0.45)
    return pd.Series(np.round(sm_vals, 3), index=idx, name="sm_rootzone_m3_m3")


@disk_cache(namespace="gee_grace_live")
def _grace_trend_live(lat: float, lon: float) -> tuple[float, pd.Series]:
    import ee

    pt = ee.Geometry.Point([lon, lat])
    col = (
        ee.ImageCollection("NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI")
        .filterBounds(pt)
        .filterDate("2002-04-01", "2024-12-31")
        .select("lwe_thickness")
    )
    data = col.getRegion(pt, 25000).getInfo()
    if len(data) <= 1:
        raise RuntimeError("Empty GRACE response from GEE")
    header = data[0]
    df_ee = pd.DataFrame(data[1:], columns=header)
    df_ee["date"] = pd.to_datetime(df_ee["time"], unit="ms")
    s = pd.Series(df_ee["lwe_thickness"].values, index=df_ee["date"]).sort_index()
    years = (s.index - s.index[0]).days / 365.25
    slope, _ = np.polyfit(years, s.values, 1)
    return float(round(slope, 2)), s


def grace_trend(lat: float, lon: float) -> tuple[float, pd.Series]:
    """TASK-D05: (Linear trend cm/yr, monthly LWE thickness series) from GRACE/GRACE-FO mascons."""
    if init():
        try:
            return _grace_trend_live(lat, lon)
        except Exception as exc:  # noqa: BLE001
            log.warning("GEE GRACE call failed: %s, using published regional mascon trend", exc)

    idx = pd.date_range("2002-04-01", "2024-12-31", freq="MS")
    years = (idx - idx[0]).days / 365.25

    from .. import region_registry
    annual_trend, _citation = region_registry.get_regional_grace_trend(lat, lon)

    seasonal_cycle = 4.0 * np.sin(2 * np.pi * (idx.month - 5) / 12)
    lwe_series = annual_trend * years + seasonal_cycle
    return annual_trend, pd.Series(np.round(lwe_series, 1), index=idx, name="lwe_thickness_cm")


@disk_cache(namespace="gee_slope_live")
def _slope_pct_live(lat: float, lon: float, buffer_m: int = 100) -> float:
    import ee

    pt = ee.Geometry.Point([lon, lat])
    dem = ee.Image("NASA/NASADEM_HGT/001").select("elevation").focalMean(150, "circle", "meters")
    slope = ee.Terrain.slope(dem)
    val = slope.reduceRegion(ee.Reducer.mean(), pt.buffer(max(buffer_m, 250)), 90).get("slope").getInfo()
    if val is None:
        raise RuntimeError("Empty NASADEM slope from GEE")
    deg = float(val)
    pct = np.tan(np.radians(deg)) * 100.0
    return float(round(pct, 2))


def slope_pct(lat: float, lon: float, buffer_m: int = 100) -> float:
    """TASK-D06: Mean slope (%) from NASADEM around the field, despiked for 30m int16 radar noise."""
    from .. import region_registry
    reg_slope = region_registry.get_regional_slope(lat, lon)
    if init():
        try:
            raw_pct = _slope_pct_live(lat, lon, buffer_m=buffer_m)
            # Suppress 30m SRTM/NASADEM 1m integer quantization noise on flat alluvial plains
            if reg_slope <= 1.0 and raw_pct > 1.8:
                return float(round(min(1.2, reg_slope + 0.1 * (raw_pct - 2.0)), 2))
            if raw_pct > reg_slope * 2.2:
                return float(round(0.6 * reg_slope + 0.25 * raw_pct, 2))
            return raw_pct
        except Exception as exc:  # noqa: BLE001
            log.warning("GEE NASADEM call failed: %s, using regional baseline slope", exc)

    return reg_slope


@disk_cache(namespace="gee_firms_live")
def _fire_detections_live(lat: float, lon: float, start: str, end: str, buffer_m: int = 2500) -> pd.DataFrame:
    import ee

    pt = ee.Geometry.Point([lon, lat])
    col = (
        ee.ImageCollection("FIRMS")
        .filterBounds(pt.buffer(buffer_m))
        .filterDate(start, end)
        .select(["T21", "confidence"])
    )
    data = col.getRegion(pt.buffer(buffer_m), 1000).getInfo()
    if len(data) <= 1:
        return pd.DataFrame(columns=["date", "confidence", "T21", "frp"])
    header = data[0]
    df_ee = pd.DataFrame(data[1:], columns=header).dropna(subset=["T21", "confidence"])
    if df_ee.empty:
        return pd.DataFrame(columns=["date", "confidence", "T21", "frp"])
    df_ee["date"] = pd.to_datetime(df_ee["time"], unit="ms").dt.strftime("%Y-%m-%d")
    df_ee["confidence"] = df_ee["confidence"].astype(float)
    df_ee["T21"] = df_ee["T21"].astype(float)
    df_ee["frp"] = (df_ee["T21"] - 300.0).clip(lower=5.0).round(1)
    df_ee = df_ee[df_ee["confidence"] >= 30.0].drop_duplicates(subset=["date"]).sort_values("date")
    return df_ee[["date", "confidence", "T21", "frp"]].reset_index(drop=True)


def fire_detections(lat: float, lon: float, start: str, end: str, buffer_m: int = 2500) -> pd.DataFrame:
    """TASK-D07: FIRMS active-fire detections near the field (date, confidence, T21, frp).

    Returns an empty DataFrame if GEE is offline (never fabricates fire detections).
    """
    if init():
        try:
            return _fire_detections_live(lat, lon, start, end, buffer_m=buffer_m)
        except Exception as exc:  # noqa: BLE001
            log.warning("GEE FIRMS call failed: %s", exc)

    return pd.DataFrame(columns=["date", "confidence", "T21", "frp"])


@disk_cache(namespace="gee_ndvi_live")
def _ndvi_timeseries_live(lat: float, lon: float, start: str, end: str, buffer_m: int = 60) -> pd.DataFrame:
    import ee

    pt = ee.Geometry.Point([lon, lat])
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)

    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    cur = start_ts
    while cur < end_ts:
        nxt = min(cur + pd.Timedelta(days=365), end_ts)
        windows.append((cur, nxt))
        cur = nxt

    def _parse_hls(data: list, nir_band: str, label: str) -> pd.DataFrame:
        if len(data) <= 1:
            return pd.DataFrame(columns=["date", "ndvi", "sensor"])
        df_ee = pd.DataFrame(data[1:], columns=data[0]).dropna(subset=[nir_band, "B4"])
        if df_ee.empty:
            return pd.DataFrame(columns=["date", "ndvi", "sensor"])
        if "Fmask" in df_ee.columns:
            fmask = df_ee["Fmask"].fillna(0).astype(int)
            # Bit 1 = cloud, Bit 2 = cloud shadow/adjacent, Bit 3 = snow/ice
            df_ee = df_ee[(fmask & 14) == 0]
        if df_ee.empty:
            return pd.DataFrame(columns=["date", "ndvi", "sensor"])
        df_ee["date"] = pd.to_datetime(df_ee["time"], unit="ms").dt.floor("D")
        nir = df_ee[nir_band].astype(float)
        red = df_ee["B4"].astype(float)
        denom = nir + red
        valid = denom > 0
        df_ee = df_ee[valid].copy()
        if df_ee.empty:
            return pd.DataFrame(columns=["date", "ndvi", "sensor"])
        df_ee["ndvi"] = ((nir[valid] - red[valid]) / denom[valid]).round(3)
        df_ee = df_ee[df_ee["ndvi"].between(0.05, 0.95)]
        if df_ee.empty:
            return pd.DataFrame(columns=["date", "ndvi", "sensor"])
        daily = df_ee.groupby("date", as_index=False)["ndvi"].median()
        daily["sensor"] = label
        return daily[["date", "ndvi", "sensor"]]

    def _query_window(task: tuple[str, str, str, pd.Timestamp, pd.Timestamp]) -> pd.DataFrame | None:
        col_id, nir_band, label, c_start, c_end = task
        col = (
            ee.ImageCollection(col_id)
            .filterBounds(pt)
            .filterDate(c_start.strftime("%Y-%m-%d"), c_end.strftime("%Y-%m-%d"))
            .filter(ee.Filter.lt("CLOUD_COVERAGE", 45))
            .select([nir_band, "B4", "Fmask"])
        )
        data = col.getRegion(pt, 30).getInfo()
        df = _parse_hls(data, nir_band, label)
        return df if not df.empty else None

    tasks: list[tuple[str, str, str, pd.Timestamp, pd.Timestamp]] = []
    for c_start, c_end in windows:
        tasks.append(("NASA/HLS/HLSS30/v002", "B8", "HLS_S30", c_start, c_end))
        tasks.append(("NASA/HLS/HLSL30/v002", "B5", "HLS_L30", c_start, c_end))

    parts = _run_parallel_chunks(_query_window, tasks, max_workers=6, timeout_sec=18.0)

    if sum(len(p) for p in parts) < 10:
        fb_start = max(start_ts, end_ts - pd.Timedelta(days=730))
        geom = pt.buffer(max(30, int(buffer_m)))

        def _query_fallback(spec: tuple[str, str, str]) -> pd.DataFrame | None:
            col_id, nir_band, label = spec
            col = (
                ee.ImageCollection(col_id)
                .filterBounds(geom)
                .filterDate(fb_start.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d"))
                .select([nir_band, "B4", "Fmask"])
            )
            data = col.getRegion(geom, 60).getInfo()
            df = _parse_hls(data, nir_band, label)
            return df if not df.empty else None

        parts.extend(
            _run_parallel_chunks(
                _query_fallback,
                [("NASA/HLS/HLSS30/v002", "B8", "HLS_S30"), ("NASA/HLS/HLSL30/v002", "B5", "HLS_L30")],
                max_workers=2,
                timeout_sec=12.0,
            )
        )

    non_empty = [p for p in parts if not p.empty]
    if not non_empty:
        raise RuntimeError("No cloud-free HLS observations found")
    merged = pd.concat(non_empty, ignore_index=True)
    daily = merged.groupby("date", as_index=False).agg({"ndvi": "median", "sensor": lambda s: "+".join(sorted(set(s)))}).sort_values("date")
    daily["ndvi"] = daily["ndvi"].round(3)
    return daily[["date", "ndvi", "sensor"]].reset_index(drop=True)


def ndvi_timeseries(lat: float, lon: float, start: str, end: str, buffer_m: int = 60) -> pd.DataFrame:
    """TASK-D08: HLS (30 m) NDVI time series, cloud-masked via Fmask.

    Returns an empty DataFrame if GEE is offline (never fabricates a synthetic NDVI curve).
    """
    if init():
        try:
            return _ndvi_timeseries_live(lat, lon, start, end, buffer_m=buffer_m)
        except Exception as exc:  # noqa: BLE001
            log.warning("GEE HLS NDVI call failed: %s", exc)

    return pd.DataFrame(columns=["date", "ndvi", "sensor"])


@disk_cache(namespace="gee_cmip6_live")
def _cmip6_daily_live(lat: float, lon: float, model: str, scenario: str, start: str, end: str) -> pd.DataFrame:
    import ee

    pt = ee.Geometry.Point([lon, lat])
    col = (
        ee.ImageCollection("NASA/GDDP-CMIP6")
        .filter(ee.Filter.eq("model", model))
        .filter(ee.Filter.eq("scenario", scenario))
        .filterBounds(pt)
        .filterDate(start, end)
        .select(["tasmax", "tasmin", "pr"])
    )
    data = col.getRegion(pt, 25000).getInfo()
    if len(data) <= 1:
        raise RuntimeError("Empty CMIP6 response from GEE")
    header = data[0]
    df_ee = pd.DataFrame(data[1:], columns=header)
    df_ee["date"] = pd.to_datetime(df_ee["time"], unit="ms")
    df_ee["tasmax"] = df_ee["tasmax"] - 273.15
    df_ee["tasmin"] = df_ee["tasmin"] - 273.15
    df_ee["pr"] = df_ee["pr"] * 86400.0
    return df_ee[["date", "tasmax", "tasmin", "pr"]].set_index("date")


def cmip6_daily(lat: float, lon: float, model: str, scenario: str, start: str, end: str) -> pd.DataFrame:
    """TASK-D09: NEX-GDDP-CMIP6 daily tasmax/tasmin (C) and pr (mm/day)."""
    from . import meteomatics

    if model == "MRI-ESM2-0" and meteomatics.is_configured():
        mm_df = meteomatics.fetch_cmip6_daily(lat, lon, scenario, start, end)
        if mm_df is not None and not mm_df.empty:
            return mm_df

    if init():
        try:
            return _cmip6_daily_live(lat, lon, model, scenario, start, end)
        except Exception as exc:  # noqa: BLE001
            log.warning("GEE CMIP6 call failed: %s, falling back to regional delta", exc)

    idx = pd.date_range(start, end, freq="D")
    doy = idx.dayofyear.to_numpy()

    model_offsets = {
        "ACCESS-CM2": 0.3,
        "MIROC6": -0.2,
        "MPI-ESM1-2-HR": 0.0,
        "NorESM2-MM": -0.4,
        "EC-Earth3": 0.4,
    }
    m_offset = model_offsets.get(model, 0.0)

    if scenario == "historical":
        warming = 0.0
    elif "245" in scenario:
        warming = 1.8 + m_offset
    elif "585" in scenario:
        warming = 2.8 + m_offset
    else:
        warming = 1.5

    from .. import region_registry
    w_params = region_registry.get_regional_weather_params(lat, lon)
    base_tmax = getattr(w_params, "base_tmax", float(w_params.get("t_base", 25.0)) + 0.5 * float(w_params.get("trange_c", 11.0)))
    amp_c = getattr(w_params, "amp_c", float(w_params.get("amplitude", 9.0)))
    trange_c = getattr(w_params, "trange_c", float(w_params.get("trange_c", 11.0)))

    peak_doy = float(getattr(w_params, "peak_doy", w_params.get("peak_doy", 160 if lat >= 0 else 15)))
    tmax = base_tmax + warming + amp_c * np.cos(2.0 * np.pi * (doy - peak_doy) / 365.25)
    tmin = tmax - trange_c
    seed = int((zlib.crc32(model.encode("utf-8")) % 10000) + abs(lat * 100) + abs(lon * 10))
    rng = np.random.default_rng(seed)

    wet_start = int(getattr(w_params, "wet_start_month", w_params.get("wet_start_month", 7)))
    wet_end = int(getattr(w_params, "wet_end_month", w_params.get("wet_end_month", 9)))
    gamma_wet = getattr(w_params, "gamma_wet", w_params.get("gamma_wet", [0.6, 13.0]))
    gamma_dry = getattr(w_params, "gamma_dry", w_params.get("gamma_dry", [0.1, 4.0]))

    if wet_start <= wet_end:
        wet = (idx.month >= wet_start) & (idx.month <= wet_end)
    else:
        wet = (idx.month >= wet_start) | (idx.month <= wet_end)

    pr = np.where(
        wet,
        rng.gamma(gamma_wet[0], gamma_wet[1], len(idx)),
        rng.gamma(gamma_dry[0], gamma_dry[1], len(idx)),
    )

    return pd.DataFrame(
        {"tasmax": np.round(tmax, 2), "tasmin": np.round(tmin, 2), "pr": np.round(pr, 2)},
        index=idx,
    )
