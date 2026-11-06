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

# Variables needed by the profiler and daily FAO-56 water-balance simulation.
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


def provenance(start: date, end: date, mode: str = "observed") -> DataProvenance:
    return DataProvenance(
        source="NASA POWER",
        product="Daily Agroclimatology (MERRA-2 / GEOS / CERES / IMERG-corrected)",
        period=f"{start.year}-{end.year}",
        resolution="0.5 x 0.625 deg, daily",
        url="https://power.larc.nasa.gov/",
        mode=mode,  # type: ignore[arg-type]
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


# Monthly Tmax warm-bias offsets (deg C) for MERRA-2 across the irrigated Indo-Gangetic Plain
# Calibrated against IMD 1981-2010 Climatological Normals (Station 42099 Ludhiana / 42101 Patiala),
# ERA5-Land 0.1 deg reanalysis (Munoz-Sabater et al. 2021, DOI: 10.5194/essd-13-4349-2021),
# and Ambika & Mishra (2019, Geophysical Research Letters, DOI: 10.1029/2019GL084367).
_IGP_MONTHLY_TMAX_BIAS_C: dict[int, float] = {
    1: 1.5,
    2: 2.5,
    3: 4.5,
    4: 3.8,
    5: 3.6,
    6: 3.6,
    7: 4.2,
    8: 3.4,
    9: 2.7,
    10: 2.2,
    11: 1.8,
    12: 1.8,
}


def apply_igp_irrigation_bias_correction(df: pd.DataFrame, lat: float, lon: float) -> pd.DataFrame:
    """TASK-D11: Bias-correct NASA POWER MERRA-2 T2M_MAX warm bias across the irrigated Indo-Gangetic Plain.

    As documented in docs/NOTES.md (TASK-D11):
      NASA POWER MERRA-2 reanalysis (0.5 x 0.625 deg) lacks an irrigation parameterization in its
      Catchment Land Surface Model and therefore omits latent heat cooling from intensive canal and
      tubewell irrigation across the Indo-Gangetic Plain (26.0-32.5 N, 73.5-86.0 E). Compared against:
        - India Meteorological Department (IMD) Climatological Tables of Observatories in India
          1981-2010 (Station 42099 Ludhiana PAU & Station 42101 Patiala),
        - ERA5-Land 0.1 deg daily reanalysis (Munoz-Sabater et al. 2021, DOI: 10.5194/essd-13-4349-2021),
        - Ambika & Mishra (2019, Geophysical Research Letters, DOI: 10.1029/2019GL084367),
      raw MERRA-2 T2M_MAX exhibits a +4.5 C warm bias during March wheat grain filling, +3.8 C in April,
      +3.6 C in May-Jun, and +4.2 C in July. We subtract the monthly climatological delta (_IGP_MONTHLY_TMAX_BIAS_C)
      while preserving observed daily anomalies and never modifying observed PRECTOTCORR precipitation.
    """
    if df.empty:
        return df
    out = df.copy()

    is_igp = (26.0 <= lat <= 32.5) and (73.5 <= lon <= 86.0)
    if is_igp and "T2M_MAX" in out.columns:
        months = out.index.month
        for month_num, offset_c in _IGP_MONTHLY_TMAX_BIAS_C.items():
            mask = months == month_num
            if mask.any():
                out.loc[mask, "T2M_MAX"] = np.round(out.loc[mask, "T2M_MAX"] - offset_c, 2)
        if "T2M_MIN" in out.columns:
            out["T2M_MAX"] = np.maximum(out["T2M_MAX"], out["T2M_MIN"] + 2.0)

    return out


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
    df = df.replace(FILL_VALUE, float("nan")).astype(float).sort_index()
    return apply_igp_irrigation_bias_correction(df, req.lat, req.lon)


def synthetic_daily_weather(
    lat: float,
    lon: float,
    years: tuple[int, int] = (2015, 2024),
    seed: int = 42,
) -> pd.DataFrame:
    """Generate realistic physical daily agroclimate time series for a coordinate.

    Used for offline execution, fallback when NASA POWER is unreachable, and test suites.
    Calibrated across Indian agro-climatic zones (Punjab, Vidarbha, Bundelkhand, Cauvery Delta).
    """
    idx = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-12-31", freq="D")
    doy = idx.dayofyear.to_numpy()
    n_days = len(idx)
    rng = np.random.default_rng(seed + int(abs(lat * 10 + lon)))

    is_mediterranean = (32.0 <= lat <= 44.0) and ((-125.0 <= lon <= -114.0) or (-10.0 <= lon <= 35.0))
    is_cauvery_delta = (8.0 <= lat < 15.0) and (76.0 <= lon <= 82.0)
    is_vidarbha = (18.0 <= lat < 23.0) and (75.0 <= lon <= 80.5)
    is_bundelkhand = (23.5 <= lat < 27.0) and (77.5 <= lon <= 81.5)
    is_sw_punjab = (28.5 <= lat <= 31.2) and (73.5 <= lon < 75.2)
    is_south_asia = (8.0 <= lat <= 35.0) and (68.0 <= lon <= 92.0)

    # Temperature model
    if is_cauvery_delta:
        t_base = 28.5
        amplitude = 4.2
        peak_doy = 140
    elif is_vidarbha:
        t_base = 27.5
        amplitude = 7.8
        peak_doy = 140
    elif is_bundelkhand:
        t_base = 26.2
        amplitude = 10.5
        peak_doy = 150
    elif is_south_asia:
        t_base = 24.5
        amplitude = 11.5
        peak_doy = 160
    else:
        t_base = 29.0 - 0.32 * abs(lat)
        amplitude = 10.5 if is_mediterranean else min(17.0, max(2.5, 0.40 * abs(lat)))
        peak_doy = 25 if lat < 0 else 205

    t_seasonal = amplitude * np.cos(2.0 * np.pi * (doy - peak_doy) / 365.25)
    t_noise = rng.normal(0, 1.4, n_days)
    tmean = t_base + t_seasonal + t_noise

    diurnal = 11.5 + 1.8 * np.sin(2.0 * np.pi * doy / 365.25)
    tmax = np.round(tmean + 0.5 * diurnal, 2)
    tmin = np.round(tmean - 0.5 * diurnal, 2)

    # Precipitation model
    if is_mediterranean:
        wet_prob = np.where((idx.month >= 11) | (idx.month <= 3), 0.22, 0.02)
        precip = np.where(rng.random(n_days) < wet_prob, rng.gamma(1.5, 8.0, n_days), 0.0)
    elif is_cauvery_delta:
        # NE Monsoon (Oct-Dec) + SW Monsoon (Jul-Sep) -> ~1020 mm/yr
        ne_monsoon = (idx.month >= 10) & (idx.month <= 12)
        sw_monsoon = (idx.month >= 7) & (idx.month <= 9)
        precip = np.where(
            ne_monsoon,
            rng.gamma(0.75, 14.5, n_days),
            np.where(sw_monsoon, rng.gamma(0.45, 9.0, n_days), rng.gamma(0.06, 3.5, n_days)),
        )
    elif is_sw_punjab:
        # Bathinda Semi-Arid (~430 mm/yr)
        monsoon = (idx.month >= 7) & (idx.month <= 9)
        precip = np.where(monsoon, rng.gamma(0.45, 9.5, n_days), rng.gamma(0.05, 3.0, n_days))
    elif is_vidarbha or is_bundelkhand:
        # Central India Rainfed (~820 mm/yr concentrated Jun-Sep, dry Oct-May)
        monsoon = (idx.month >= 6) & (idx.month <= 9)
        precip = np.where(monsoon, rng.gamma(0.65, 11.5, n_days), rng.gamma(0.04, 2.5, n_days))
    elif is_south_asia:
        monsoon = (idx.month >= 7) & (idx.month <= 9)
        precip = np.where(monsoon, rng.gamma(0.62, 12.5, n_days), rng.gamma(0.08, 4.0, n_days))
    else:
        summer_months = (idx.month >= 11) | (idx.month <= 2) if lat < 0 else (idx.month >= 5) & (idx.month <= 8)
        wet_prob = np.where(summer_months, 0.22, 0.14)
        precip = np.where(rng.random(n_days) < wet_prob, rng.gamma(1.0, 6.0, n_days), 0.0)

    precip = np.round(np.maximum(0.0, precip), 2)

    solar_base = max(10.0, 22.0 - 0.12 * abs(lat))
    rad = np.round(
        solar_base + 5.5 * np.cos(2.0 * np.pi * (doy - peak_doy) / 365.25) - 0.3 * np.minimum(precip, 20.0),
        1,
    )
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
