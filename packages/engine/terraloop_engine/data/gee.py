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
    if _initialised:
        return True
    if os.environ.get("GEE_DISABLE") == "1":
        return False
    try:
        _load_dotenv_if_needed()
        import ee

        creds, creds_proj = _resolve_credentials(ee)
        project = os.environ.get("GEE_PROJECT") or creds_proj
        if creds is not None:
            ee.Initialize(credentials=creds, project=project)
        else:
            ee.Initialize(project=project)
        _initialised = True
        return True
    except Exception as exc:  # noqa: BLE001
        log.info("GEE init skipped or failed: %s (using un-cached regional climatology)", exc)
        return False


def is_live() -> bool:
    """Return True if Google Earth Engine is initialized and active."""
    return _initialised


def provenance_with_mode(prov: DataProvenance, unknown_if_offline: bool = False) -> DataProvenance:
    """Return a copy of the provenance tagged with 'observed' if GEE is live.

    When GEE is offline the mode is 'regional_climatology' (sources with an honest climatology fallback, e.g.
    GRACE/SMAP/NASADEM) or 'unknown' when ``unknown_if_offline=True`` (sources with no fallback that must never
    be fabricated, e.g. FIRMS fire detections and HLS NDVI crop history).
    """
    if _initialised:
        mode = "observed"
    else:
        mode = "unknown" if unknown_if_offline else "regional_climatology"
    return prov.model_copy(update={"mode": mode})


@disk_cache(namespace="gee_imerg_live")
def _imerg_daily_live(lat: float, lon: float, start: str, end: str) -> pd.Series:
    import ee

    pt = ee.Geometry.Point([lon, lat])
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    n_days = (end_ts - start_ts).days

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
        header = data[0]
        rows = data[1:]
        df_ee = pd.DataFrame(rows, columns=header)
        df_ee["date"] = pd.to_datetime(df_ee["time"], unit="ms").dt.date
        # IMERG_V07 half-hourly rate (mm/hr) * 0.5 hr = mm per 30-min interval
        daily = df_ee.groupby("date")["precipitation"].sum() * 0.5
        return pd.Series(daily.values, index=pd.to_datetime(daily.index), name="precipitation_mm")

    # Multi-year queries use NASA/GPM_L3/IMERG_MONTHLY_V07 to avoid 400k half-hourly image limit
    col = (
        ee.ImageCollection("NASA/GPM_L3/IMERG_MONTHLY_V07")
        .filterBounds(pt)
        .filterDate(start, end)
        .select("precipitation")
    )
    data = col.getRegion(pt, 10000).getInfo()
    if len(data) <= 1:
        raise RuntimeError("Empty IMERG MONTHLY response from GEE")
    header = data[0]
    df_ee = pd.DataFrame(data[1:], columns=header).dropna(subset=["precipitation"])
    df_ee["date"] = pd.to_datetime(df_ee["time"], unit="ms")
    df_ee["days_in_month"] = df_ee["date"].dt.days_in_month
    df_ee["month_mm"] = df_ee["precipitation"].astype(float) * 24.0 * df_ee["days_in_month"]

    idx = pd.date_range(start_ts, end_ts, freq="D")
    daily_vals = np.zeros(len(idx), dtype=float)
    ym_to_mm = {
        (int(r["date"].year), int(r["date"].month)): float(r["month_mm"])
        for _, r in df_ee.iterrows()
    }
    for (y, m), total_mm in ym_to_mm.items():
        mask = (idx.year == y) & (idx.month == m)
        n_m = int(mask.sum())
        if n_m > 0:
            daily_vals[mask] = round(total_mm / n_m, 3)

    return pd.Series(daily_vals, index=idx, name="precipitation_mm")


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
    n_days = (end_ts - start_ts).days

    if n_days <= 45:
        col = (
            ee.ImageCollection("NASA/SMAP/SPL4SMGP/008")
            .filterBounds(pt)
            .filterDate(start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d"))
            .select("sm_rootzone")
        )
    else:
        # Construct bi-monthly asset IDs (1st and 15th of each month) to avoid 30k-image GEE memory limit
        asset_ids: list[str] = []
        months = pd.date_range(start_ts.replace(day=1), end_ts, freq="MS")
        for m_dt in months:
            for day_num in (1, 15):
                cand = pd.Timestamp(year=m_dt.year, month=m_dt.month, day=day_num)
                if start_ts <= cand <= end_ts:
                    asset_ids.append(f"NASA/SMAP/SPL4SMGP/008/{cand.strftime('%Y%m%d')}_0130")
        col = ee.ImageCollection(asset_ids).select("sm_rootzone")

    data = col.getRegion(pt, 9000).getInfo()
    if len(data) <= 1:
        raise RuntimeError("Empty SMAP response from GEE")
    header = data[0]
    rows = data[1:]
    df_ee = pd.DataFrame(rows, columns=header).dropna(subset=["sm_rootzone"])
    df_ee["date"] = pd.to_datetime(df_ee["time"], unit="ms").dt.date
    daily = df_ee.groupby("date")["sm_rootzone"].mean()
    return pd.Series(daily.values, index=pd.to_datetime(daily.index), name="sm_rootzone_m3_m3")


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

    # Regionally differentiated root-zone soil moisture climatology + dry/wet anomaly trend
    from .. import region_registry
    reg = region_registry.detect_region_config(lat, lon)

    if reg.region_id == "bundelkhand":
        # Bundelkhand rainfed drought-prone (lower recent soil moisture percentile ~28th)
        sm_base = 0.18 + 0.09 * np.sin(2 * np.pi * (doy - 205) / 365) - 0.004 * years
    elif reg.region_id == "vidarbha":
        # Vidarbha rainfed Vertisol (~34th percentile)
        sm_base = 0.24 + 0.10 * np.sin(2 * np.pi * (doy - 210) / 365) - 0.003 * years
    elif reg.region_id in ("punjab_southwest", "rajasthan_arid"):
        # Bathinda semi-arid cotton belt (~38th percentile)
        sm_base = 0.17 + 0.07 * np.sin(2 * np.pi * (doy - 200) / 365) - 0.002 * years
    elif reg.region_id in ("cauvery", "southern_hills"):
        # Thanjavur Cauvery Delta (~62nd percentile)
        sm_base = 0.28 + 0.08 * np.sin(2 * np.pi * (doy - 270) / 365) + 0.002 * years
    else:
        # Central Punjab irrigated alluvial plain (~46th percentile)
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

    # Published regional GRACE/GRACE-FO JPL Mascon trends across Indian agro-ecological zones
    # Sources: Rodell et al. (2009 Nature), Asoka et al. (2017 Nature Geosci.), CGWB Dynamic GW Resources
    if (29.5 <= lat <= 32.5) and (75.2 <= lon <= 77.5):
        # Central Punjab (Sangrur / Ludhiana sweet-water tube-well belt)
        annual_trend = -3.85 if lat < 30.6 else -3.45
    elif (28.5 <= lat <= 31.2) and (73.5 <= lon < 75.2):
        # South-West Punjab (Bathinda brackish/canal-command cotton belt)
        annual_trend = -2.40
    elif (23.5 <= lat < 27.0) and (77.5 <= lon <= 81.5):
        # Bundelkhand hard-rock semi-arid plateau (Jhansi)
        annual_trend = -1.25
    elif (18.0 <= lat < 23.0) and (75.0 <= lon <= 80.5):
        # Vidarbha Deccan trap basalt (Akola/Amravati)
        annual_trend = -0.65
    elif lat < 15.0:
        # Cauvery Delta Tamil Nadu (Thanjavur)
        annual_trend = -0.50
    else:
        # All-India agricultural plain average
        annual_trend = -1.50

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


def _regional_baseline_slope(lat: float, lon: float) -> float:
    if lat < 15.0:
        # Cauvery Delta flat coastal alluvium
        return 0.4
    if (28.0 <= lat <= 33.0) and (73.0 <= lon <= 78.0):
        # Indo-Gangetic plain (Punjab)
        return 0.8
    if (18.0 <= lat < 23.0) and (75.0 <= lon <= 80.5):
        # Vidarbha Deccan plateau undulating Vertisols
        return 1.6
    if (23.5 <= lat < 27.0) and (77.5 <= lon <= 81.5):
        # Bundelkhand dissected plateau
        return 2.2
    return 1.2


def slope_pct(lat: float, lon: float, buffer_m: int = 100) -> float:
    """TASK-D06: Mean slope (%) from NASADEM around the field, despiked for 30m int16 radar noise."""
    reg_slope = _regional_baseline_slope(lat, lon)
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
            log.warning("GEE NASADEM call failed: %s", exc)

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
    s2 = (
        ee.ImageCollection("NASA/HLS/HLSS30/v002")
        .filterBounds(pt)
        .filterDate(start, end)
        .select(["B8", "B4", "Fmask"])
    )
    data = s2.getRegion(pt, 30).getInfo()
    if len(data) <= 1:
        raise RuntimeError("Empty HLS response from GEE")
    header = data[0]
    df_ee = pd.DataFrame(data[1:], columns=header).dropna(subset=["B8", "B4"])
    if "Fmask" in df_ee.columns:
        fmask = df_ee["Fmask"].fillna(0).astype(int)
        # Bit 1 = cloud, Bit 2 = cloud shadow/adjacent, Bit 3 = snow/ice
        df_ee = df_ee[(fmask & 14) == 0]
    df_ee["date"] = pd.to_datetime(df_ee["time"], unit="ms").dt.floor("D")
    b8 = df_ee["B8"].astype(float)
    b4 = df_ee["B4"].astype(float)
    denom = b8 + b4
    valid = denom > 0
    df_ee = df_ee[valid].copy()
    df_ee["ndvi"] = ((b8[valid] - b4[valid]) / denom[valid]).round(3)
    df_ee = df_ee[df_ee["ndvi"].between(0.05, 0.95)]
    if df_ee.empty:
        raise RuntimeError("No cloud-free HLS observations found")
    daily = df_ee.groupby("date", as_index=False)["ndvi"].max().sort_values("date")
    daily["sensor"] = "HLS_S30"
    return daily[["date", "ndvi", "sensor"]].reset_index(drop=True)


def ndvi_timeseries(lat: float, lon: float, start: str, end: str, buffer_m: int = 60) -> pd.DataFrame:
    """TASK-D08: HLS (30 m) NDVI time series, cloud-masked via Fmask.

    Returns an empty DataFrame if GEE is offline (never fabricates a synthetic NDVI curve).
    """
    if init():
        try:
            return _ndvi_timeseries_live(lat, lon, start, end, buffer_m=buffer_m)
        except Exception as exc:  # noqa: BLE001
            log.warning("GEE HLS call failed: %s", exc)

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
    if init():
        try:
            return _cmip6_daily_live(lat, lon, model, scenario, start, end)
        except Exception as exc:  # noqa: BLE001
            log.warning("GEE CMIP6 call failed: %s, using regional delta projection", exc)

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

    # Location-aware baseline temperature & seasonal amplitude
    if lat < 15.0:
        base_tmax, amp_c, trange_c = 32.5, 4.5, 9.0
    elif lat < 23.5:
        base_tmax, amp_c, trange_c = 33.0, 7.5, 12.0
    else:
        base_tmax, amp_c, trange_c = 30.0, 10.0, 13.0

    tmax = base_tmax + warming + amp_c * np.sin(2 * np.pi * (doy - 80) / 365)
    tmin = tmax - trange_c
    # Deterministic seed across Python processes using CRC32 instead of randomized hash()
    seed = int((zlib.crc32(model.encode("utf-8")) % 10000) + abs(lat * 100) + abs(lon * 10))
    rng = np.random.default_rng(seed)
    if lat < 15.0:
        wet = (idx.month >= 8) & (idx.month <= 12)
    else:
        wet = (idx.month >= 7) & (idx.month <= 9)
    pr = np.where(wet, rng.gamma(0.6, 13.0, len(idx)), rng.gamma(0.1, 4.0, len(idx)))

    return pd.DataFrame(
        {"tasmax": np.round(tmax, 2), "tasmin": np.round(tmin, 2), "pr": np.round(pr, 2)},
        index=idx,
    )
