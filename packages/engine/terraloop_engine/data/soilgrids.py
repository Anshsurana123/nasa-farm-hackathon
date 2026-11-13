"""ISRIC SoilGrids 2.0 REST client (global 250 m soil properties).

Docs: https://rest.isric.org/soilgrids/v2.0/docs
Urban / water pixels are masked (null). We search a small neighbourhood
around the point to find the nearest valid agricultural pixel.
"""

from __future__ import annotations

import logging
import time

import httpx
from terraloop_schemas import DataProvenance

from ..cache import disk_cache

log = logging.getLogger(__name__)

BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"

PROPERTIES = ["clay", "sand", "silt", "soc", "phh2o", "bdod", "cec", "nitrogen"]
TOPSOIL_DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
DEPTH_WEIGHTS = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}

# Neighbourhood offsets in degrees (~1-3 km) tried when the exact pixel is masked.
_OFFSETS = [(0, 0), (0.01, 0), (-0.01, 0), (0, 0.01), (0, -0.01),
            (0.02, 0.02), (-0.02, -0.02), (0.02, -0.02), (-0.02, 0.02),
            (0.03, 0), (-0.03, 0), (0, 0.03), (0, -0.03)]

PROVENANCE = DataProvenance(
    source="ISRIC SoilGrids 2.0",
    product="Topsoil 0-30 cm weighted mean",
    resolution="250 m",
    doi="10.5194/soil-7-217-2021",
    url="https://soilgrids.org/",
)


@disk_cache(namespace="soilgrids")
def _query(lat: float, lon: float) -> dict:
    import os

    params: list[tuple[str, str | float]] = [("lon", round(lon, 5)), ("lat", round(lat, 5))]
    params += [("property", p) for p in PROPERTIES]
    params += [("depth", d) for d in TOPSOIL_DEPTHS]
    params.append(("value", "mean"))

    headers = {
        "User-Agent": "TerraLoop-NASA-SpaceApps/2.6 (https://github.com/Anshsurana123/nasa-farm-hack)",
        "Accept": "application/json",
    }
    timeout = float(os.environ.get("SOILGRIDS_TIMEOUT", "4.5"))
    with httpx.Client(timeout=timeout, headers=headers) as client:
        resp = client.get(BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()


# ISRIC SoilGrids 2.0 GEE asset conversion factors to target units:
#   clay/sand/silt: g/kg -> % (/10), soc: dg/kg -> g/kg (/10), phh2o: pH*10 -> pH (/10),
#   bdod: cg/cm3 -> g/cm3 (/100), cec: mmol(c)/kg -> cmol(c)/kg (/10),
#   nitrogen: mg/kg (matching ISRIC SoilGrids REST target units in golden profiles) -> g/kg (/1000).
_GEE_DFACTORS: dict[str, float] = {
    "clay": 10.0,
    "sand": 10.0,
    "silt": 10.0,
    "soc": 10.0,
    "phh2o": 10.0,
    "bdod": 100.0,
    "cec": 10.0,
    "nitrogen": 1000.0,
}
_GEE_OFFSETS = [(0.0, 0.0), (0.01, 0.0), (-0.01, 0.0), (0.0, 0.01), (0.0, -0.01)]


@disk_cache(namespace="soilgrids_gee")
def _query_gee_soilgrids(lat: float, lon: float) -> dict[str, float]:
    import ee

    pt = ee.Geometry.Point([round(lon, 5), round(lat, 5)])
    img = ee.Image.cat(
        [
            ee.Image(f"projects/soilgrids-isric/{prop}_mean").select(
                [f"{prop}_{d}_mean" for d in TOPSOIL_DEPTHS]
            )
            for prop in PROPERTIES
        ]
    )
    raw = img.reduceRegion(ee.Reducer.first(), pt, 250).getInfo() or {}
    out: dict[str, float] = {}
    for prop in PROPERTIES:
        d_factor = _GEE_DFACTORS[prop]
        total, weight = 0.0, 0.0
        for depth in TOPSOIL_DEPTHS:
            val = raw.get(f"{prop}_{depth}_mean")
            if val is None:
                continue
            w = DEPTH_WEIGHTS.get(depth, 1)
            total += (float(val) / d_factor) * w
            weight += w
        if weight:
            out[prop] = total / weight
    if out.get("clay") is None:
        raise ValueError(f"Masked SoilGrids GEE pixel at ({lat:.4f}, {lon:.4f})")
    return out


def _fetch_via_gee(lat: float, lon: float) -> tuple[dict[str, float] | None, tuple[float, float] | None]:
    from . import gee

    if not gee.init():
        return None, None
    for dlat, dlon in _GEE_OFFSETS:
        plat, plon = lat + dlat, lon + dlon
        try:
            parsed = _query_gee_soilgrids(plat, plon)
            if parsed and parsed.get("clay") is not None:
                return parsed, (plat, plon)
        except Exception as exc:  # noqa: BLE001
            log.debug("GEE SoilGrids query skipped at (%.4f, %.4f): %s", plat, plon, exc)
            continue
    return None, None


def _parse(payload: dict) -> dict[str, float] | None:
    out: dict[str, float] = {}
    for layer in payload.get("properties", {}).get("layers", []):
        d_factor = layer["unit_measure"]["d_factor"] or 1
        total, weight = 0.0, 0.0
        for depth in layer["depths"]:
            val = depth["values"].get("mean")
            if val is None:
                continue
            w = DEPTH_WEIGHTS.get(depth["label"], 1)
            total += (val / d_factor) * w
            weight += w
        if weight:
            out[layer["name"]] = total / weight
    return out if out.get("clay") is not None else None


def fetch_topsoil(lat: float, lon: float) -> tuple[dict[str, float] | None, tuple[float, float] | None]:
    """Return (properties in target units, (lat, lon) actually used) or (None, None).

    Uses ISRIC SoilGrids 2.0 via Google Earth Engine (250 m, ~0.5 s) when GEE is live,
    and falls back to the ISRIC SoilGrids REST API when GEE is offline/masked.

    Units: clay/sand/silt %, soc g/kg, phh2o pH, bdod g/cm3 (cg/cm3 / 100),
    cec cmol(c)/kg, nitrogen g/kg.
    """
    gee_props, gee_used = _fetch_via_gee(lat, lon)
    if gee_props:
        return gee_props, gee_used

    t_start = time.monotonic()
    for dlat, dlon in _OFFSETS[:5]:
        if time.monotonic() - t_start > 8.0:
            break
        plat, plon = lat + dlat, lon + dlon
        try:
            raw = _query(plat, plon)
            parsed = _parse(raw)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError):
            # Abort offset search immediately on network-level outage or timeout
            break
        except httpx.HTTPStatusError as exc:
            # 429 rate limits and 5xx server errors should abort retries immediately
            if exc.response.status_code >= 500 or exc.response.status_code == 429:
                break
            continue
        except httpx.HTTPError:
            continue
        if parsed:
            return parsed, (plat, plon)
    return None, None
