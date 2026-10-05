"""NASA POWER (Prediction Of Worldwide Energy Resources) client.

Agroclimatology community daily point data. No authentication required.
Docs: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx
import pandas as pd
from terraloop_schemas import DataProvenance

from ..cache import disk_cache

BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# Variables needed by the profiler and later by AquaCrop.
DEFAULT_PARAMETERS = [
    "T2M_MAX",  # daily max air temp at 2 m (C)
    "T2M_MIN",  # daily min air temp at 2 m (C)
    "PRECTOTCORR",  # bias-corrected precipitation (mm/day)
    "ALLSKY_SFC_SW_DWN",  # surface shortwave radiation (MJ/m2/day)
    "RH2M",  # relative humidity at 2 m (%)
    "WS2M",  # wind speed at 2 m (m/s)
]

FILL_VALUE = -999.0


@dataclass(frozen=True)
class PowerRequest:
    lat: float
    lon: float
    start: date
    end: date
    parameters: tuple[str, ...] = tuple(DEFAULT_PARAMETERS)


def provenance(start: date, end: date) -> DataProvenance:
    return DataProvenance(
        source="NASA POWER",
        product="Daily Agroclimatology (MERRA-2 / GEOS / CERES / IMERG-corrected)",
        period=f"{start.year}-{end.year}",
        resolution="0.5 x 0.625 deg, daily",
        url="https://power.larc.nasa.gov/",
    )


@disk_cache(namespace="nasa_power")
def _fetch_json(lat: float, lon: float, start: str, end: str, parameters: str) -> dict:
    params = {
        "parameters": parameters,
        "community": "AG",
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start": start,
        "end": end,
        "format": "JSON",
    }
    with httpx.Client(timeout=120) as client:
        resp = client.get(BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()


def fetch_daily(req: PowerRequest) -> pd.DataFrame:
    """Return a daily DataFrame indexed by date with one column per parameter."""
    payload = _fetch_json(
        req.lat,
        req.lon,
        req.start.strftime("%Y%m%d"),
        req.end.strftime("%Y%m%d"),
        ",".join(req.parameters),
    )
    data = payload["properties"]["parameter"]
    df = pd.DataFrame(data)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"
    df = df.replace(FILL_VALUE, float("nan")).astype(float)
    return df.sort_index()
