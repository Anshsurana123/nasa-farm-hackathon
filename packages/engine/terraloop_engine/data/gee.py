"""Google Earth Engine helpers for NASA collections. (TASK-D02, D03, D05-D09)

GEE is our PRIMARY access path for NASA data (decision in docs/BUILD_PLAN.md 4.1).
Install: ``uv pip install -e packages/engine[gee]`` then ``earthengine authenticate``.
Set env ``GEE_PROJECT`` to your Google Cloud project id.

Every public function MUST:
  * accept (lat, lon[, buffer_m]) or a GeoJSON polygon,
  * return plain Python / pandas objects (never ee.* objects) so callers stay GEE-agnostic,
  * be wrapped with ``@disk_cache`` so golden fields work offline,
  * expose a ``PROVENANCE`` DataProvenance with the NASA product id + DOI.

NASA collection ids on GEE (verify in the GEE catalog before use):
    GPM IMERG daily      : "NASA/GPM_L3/IMERG_V07"            (half-hourly; aggregate to daily)
    SMAP L4 soil moisture: "NASA/SMAP/SPL4SMGP/007"
    GRACE mascon         : "NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI" (or newer version)
    NASADEM              : "NASA/NASADEM_HGT/001"
    FIRMS                : "FIRMS"
    MODIS NDVI 250 m     : "MODIS/061/MOD13Q1"
    HLS Landsat / S2     : "NASA/HLS/HLSL30/v002", "NASA/HLS/HLSS30/v002"
    NEX-GDDP-CMIP6       : "NASA/GDDP-CMIP6"
    GLDAS Noah           : "NASA/GLDAS/V021/NOAH/G025/T3H"
"""

from __future__ import annotations

import os

import pandas as pd

_initialised = False


def init() -> None:
    """Initialise Earth Engine once per process."""
    global _initialised
    if _initialised:
        return
    import ee  # imported lazily so the engine works without the [gee] extra

    ee.Initialize(project=os.environ.get("GEE_PROJECT"))
    _initialised = True


def ndvi_timeseries(lat: float, lon: float, start: str, end: str, buffer_m: int = 60) -> pd.DataFrame:
    """TASK-D08: HLS (30 m) NDVI time series, cloud-masked via Fmask.

    Returns DataFrame[date, ndvi, sensor]. Fall back to MODIS MOD13Q1 where HLS is sparse.
    """
    raise NotImplementedError("TASK-D08")


def imerg_daily(lat: float, lon: float, start: str, end: str) -> pd.Series:
    """TASK-D03: daily precipitation (mm) from GPM IMERG."""
    raise NotImplementedError("TASK-D03")


def smap_rootzone(lat: float, lon: float, start: str, end: str) -> pd.Series:
    """TASK-D04: daily mean root-zone soil moisture (m3/m3) from SMAP L4 (sm_rootzone)."""
    raise NotImplementedError("TASK-D04")


def grace_trend(lat: float, lon: float) -> tuple[float, pd.Series]:
    """TASK-D05: (linear trend cm/yr, monthly LWE thickness series) from GRACE/GRACE-FO mascons."""
    raise NotImplementedError("TASK-D05")


def slope_pct(lat: float, lon: float, buffer_m: int = 100) -> float:
    """TASK-D06: mean slope (%) from NASADEM around the field."""
    raise NotImplementedError("TASK-D06")


def fire_detections(lat: float, lon: float, start: str, end: str, buffer_m: int = 500) -> pd.DataFrame:
    """TASK-D07: FIRMS active-fire detections near the field (date, confidence)."""
    raise NotImplementedError("TASK-D07")


def cmip6_daily(lat: float, lon: float, model: str, scenario: str, start: str, end: str) -> pd.DataFrame:
    """TASK-D09: NEX-GDDP-CMIP6 daily tasmax/tasmin (C) and pr (mm/day) for one GCM + scenario."""
    raise NotImplementedError("TASK-D09")
