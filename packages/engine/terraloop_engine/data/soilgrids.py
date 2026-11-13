"""ISRIC SoilGrids 2.0 REST client (global 250 m soil properties).

Docs: https://rest.isric.org/soilgrids/v2.0/docs
Urban / water pixels are masked (null). We search a small neighbourhood
around the point to find the nearest valid agricultural pixel.
"""

from __future__ import annotations

import httpx
from terraloop_schemas import DataProvenance

from ..cache import disk_cache

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
    timeout = float(os.environ.get("SOILGRIDS_TIMEOUT", "6.0"))
    with httpx.Client(timeout=timeout, headers=headers) as client:
        resp = client.get(BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()


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

    Units: clay/sand/silt %, soc g/kg, phh2o pH, bdod g/cm3 (cg/cm3 / 100),
    cec cmol(c)/kg, nitrogen g/kg.
    """
    for dlat, dlon in _OFFSETS:
        plat, plon = lat + dlat, lon + dlon
        try:
            raw = _query(plat, plon)
            parsed = _parse(raw)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError):
            # Abort offset search immediately on network-level outage or timeout
            break
        except httpx.HTTPStatusError as exc:
            # 5xx server errors indicate SoilGrids service outage; do not retry 12 times
            if exc.response.status_code >= 500:
                break
            continue
        except httpx.HTTPError:
            continue
        if parsed:
            return parsed, (plat, plon)
    return None, None
