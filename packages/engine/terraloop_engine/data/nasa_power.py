"""NASA POWER (Prediction Of Worldwide Energy Resources) client.

Agroclimatology community daily point data. No authentication required.
Docs: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

import httpx
import numpy as np
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
    timeout = float(os.environ.get("NASA_POWER_TIMEOUT", "10.0"))
    with httpx.Client(timeout=timeout) as client:
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


def synthetic_daily_weather(
    lat: float,
    lon: float,
    years: tuple[int, int] = (2015, 2024),
    seed: int = 42,
) -> pd.DataFrame:
    """Generate realistic physical daily agroclimate time series for ANY coordinate on Earth.

    Used for offline execution, fallback when NASA POWER is unreachable, and test suites.
    Parameterised by solar declination, latitude-dependent seasonality, continental thermal lag,
    and regional precipitation patterns.
    """
    idx = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-12-31", freq="D")
    doy = idx.dayofyear.to_numpy()
    n_days = len(idx)
    rng = np.random.default_rng(seed)

    # 1. Regional classification
    is_california = (32.0 <= lat <= 43.0) and (-125.0 <= lon <= -114.0)
    is_mediterranean = is_california or ((34.0 <= lat <= 44.0) and (-10.0 <= lon <= 35.0))
    is_south_asia = (15.0 <= lat <= 35.0) and (68.0 <= lon <= 92.0)
    is_cornbelt = (36.0 <= lat <= 49.0) and (-102.0 <= lon <= -80.0)
    is_east_africa = (-12.0 <= lat <= 12.0) and (25.0 <= lon <= 50.0)

    # 2. Temperature model
    t_base = 29.0 - 0.32 * abs(lat)
    if is_mediterranean:
        amplitude = 10.5
    elif is_east_africa:
        amplitude = 2.5
    else:
        amplitude = min(17.0, max(2.5, 0.40 * abs(lat)))

    peak_doy = 25 if lat < 0 else 205
    t_seasonal = amplitude * np.cos(2.0 * np.pi * (doy - peak_doy) / 365.25)
    t_noise = rng.normal(0, 1.5, n_days)
    tmean = t_base + t_seasonal + t_noise

    diurnal = 11.0 + 2.0 * np.sin(2.0 * np.pi * doy / 365.25)
    tmax = np.round(tmean + 0.5 * diurnal, 2)
    tmin = np.round(tmean - 0.5 * diurnal, 2)

    # 3. Precipitation model
    if is_mediterranean:
        wet_prob = np.where((idx.month >= 11) | (idx.month <= 3), 0.22, 0.02)
        precip = np.where(rng.random(n_days) < wet_prob, rng.gamma(1.5, 8.0, n_days), 0.0)
    elif is_south_asia:
        monsoon = (idx.month >= 7) & (idx.month <= 9)
        precip = np.where(monsoon, rng.gamma(0.65, 14.0, n_days), rng.gamma(0.08, 4.0, n_days))
    elif is_cornbelt:
        wet_prob = np.where((idx.month >= 5) & (idx.month <= 9), 0.28, 0.15)
        precip = np.where(rng.random(n_days) < wet_prob, rng.gamma(1.2, 7.5, n_days), 0.0)
    elif is_east_africa:
        bimodal = ((idx.month >= 3) & (idx.month <= 5)) | ((idx.month >= 10) & (idx.month <= 12))
        precip = np.where(bimodal, rng.gamma(0.7, 10.0, n_days), rng.gamma(0.05, 3.0, n_days))
    else:
        summer_months = (idx.month >= 11) | (idx.month <= 2) if lat < 0 else (idx.month >= 5) & (idx.month <= 8)
        wet_prob = np.where(summer_months, 0.22, 0.14)
        precip = np.where(rng.random(n_days) < wet_prob, rng.gamma(1.0, 6.0, n_days), 0.0)

    precip = np.round(np.maximum(0.0, precip), 2)

    # 3. Solar Radiation, Relative Humidity, Wind
    solar_base = max(10.0, 22.0 - 0.12 * abs(lat))
    rad = np.round(solar_base + 6.0 * np.cos(2.0 * np.pi * (doy - peak_doy) / 365.25) - 0.3 * np.minimum(precip, 20.0), 1)
    rh = np.round(
        np.clip(55.0 + 20.0 * (precip > 1.0) - 10.0 * np.cos(2.0 * np.pi * (doy - peak_doy) / 365.25), 20.0, 95.0),
        1,
    )
    wind = np.round(rng.weibull(2.0, n_days) * 2.2, 1)

    return pd.DataFrame(
        {
            "T2M_MAX": tmax,
            "T2M_MIN": tmin,
            "PRECTOTCORR": precip,
            "ALLSKY_SFC_SW_DWN": rad,
            "RH2M": rh,
            "WS2M": wind,
        },
        index=idx,
    )

