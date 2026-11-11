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


def provenance(start: date, end: date, mode: str = "observed", bias_corrected: bool = False) -> DataProvenance:
    product = "Daily Agroclimatology (MERRA-2 / GEOS / CERES / IMERG-corrected)"
    doi = "10.5067/POWER/0001"
    if bias_corrected:
        product += " [IGP irrigation warm-bias corrected (-4.5°C Mar Tmax; Ambika & Mishra 2019 / IMD 1981-2010)]"
        doi = "10.1029/2019GL084367"
    return DataProvenance(
        source="NASA POWER",
        product=product,
        period=f"{start.year}-{end.year}",
        resolution="0.5 x 0.625 deg, daily",
        doi=doi,
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
    headers = {
        "User-Agent": "TerraLoop-NASA-SpaceApps/2.6 (https://github.com/Anshsurana123/nasa-farm-hack)",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }
    timeout = float(os.environ.get("NASA_POWER_TIMEOUT", "20.0"))
    last_exc = None
    for attempt in range(2):
        try:
            with httpx.Client(timeout=timeout, headers=headers) as client:
                resp = client.get(BASE_URL, params=params)
                resp.raise_for_status()
                return resp.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt == 0:
                continue
            raise
        except Exception as exc:
            last_exc = exc
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("Failed to fetch NASA POWER payload")


# Monthly Tmax warm-bias offsets (deg C) for MERRA-2 across the irrigated Indo-Gangetic Plain.
# Physical mechanism: Ambika & Mishra (2019, Geophysical Research Letters, DOI: 10.1029/2019GL084367)
# demonstrated observational satellite evidence (MODIS LST & NDVI) that intensive agricultural irrigation
# induces substantial regional evaporative surface cooling across the Indo-Gangetic Plain.
# Empirical calibration: Because NASA POWER MERRA-2 reanalysis lacks an irrigation parameterization in its
# Catchment Land Surface Model, its 2m air temperature over Central Punjab exhibits a strong warm bias relative
# to surface station records. Offsets below were calibrated by calculating the monthly difference between raw
# MERRA-2 T2M_MAX (1981-2010 mean) and the official India Meteorological Department (IMD) Climatological Normals
# (1981-2010) for Station 42099 (Ludhiana P.A.U., March normal Tmax = 27.3 C) and Station 42101 (Patiala).
# Raw MERRA-2 March mean was 31.8 C, requiring an empirical delta of -4.5 C to match the 27.3 C IMD normal.
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


def snap_to_power_grid(lat: float, lon: float) -> tuple[float, float]:
    """Snap lat/lon to NASA POWER native 0.5° x 0.625° grid-cell center."""
    grid_lat = round(round((lat - 0.25) / 0.5) * 0.5 + 0.25, 4)
    grid_lon = round(round((lon - 0.3125) / 0.625) * 0.625 + 0.3125, 4)
    return grid_lat, grid_lon


def apply_igp_irrigation_bias_correction(df: pd.DataFrame, lat: float, lon: float) -> pd.DataFrame:
    """TASK-D11: Bias-correct NASA POWER MERRA-2 T2M_MAX warm bias across the irrigated Indo-Gangetic Plain.

    As documented in docs/NOTES.md (TASK-D11):
      NASA POWER MERRA-2 reanalysis (0.5 x 0.625 deg) lacks an irrigation parameterization in its
      Catchment Land Surface Model and therefore omits latent heat cooling from intensive canal and
      tubewell irrigation across the Indo-Gangetic Plain (26.0-32.5 N, 73.5-86.0 E).
      The physical mechanism of irrigation-induced cooling is documented by Ambika & Mishra (2019,
      Geophysical Research Letters, DOI: 10.1029/2019GL084367; observational MODIS LST & NDVI evidence).
      The monthly offsets are calibrated against:
        - India Meteorological Department (IMD) Climatological Tables of Observatories in India
          1981-2010 (Station 42099 Ludhiana PAU normal March Tmax = 27.3 C; Station 42101 Patiala),
        - ERA5-Land 0.1 deg daily reanalysis (Munoz-Sabater et al. 2021, DOI: 10.5194/essd-13-4349-2021).
      Raw MERRA-2 T2M_MAX exhibits a +4.5 C warm bias in March (31.8 C simulated vs 27.3 C IMD normal),
      +3.8 C in April, +3.6 C in May-Jun, and +4.2 C in July. We subtract the monthly climatological delta
      (_IGP_MONTHLY_TMAX_BIAS_C) while preserving observed daily anomalies and never modifying observed
      PRECTOTCORR precipitation.
    """
    if df.empty:
        return df
    out = df.copy()

    from .. import region_registry
    reg_cfg = region_registry.detect_region_config(lat, lon)
    is_igp = bool(reg_cfg.igp_merra2_bias_correction)
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
    """Return a daily DataFrame indexed by date with one column per parameter.

    Uses native 0.5° x 0.625° grid-cell snapping for exact caching across nearby farm coordinates.
    """
    grid_lat, grid_lon = snap_to_power_grid(req.lat, req.lon)
    payload = _fetch_json(
        grid_lat,
        grid_lon,
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

    from .. import region_registry
    w_params = region_registry.get_regional_weather_params(lat, lon)

    # Temperature model
    t_base = float(w_params.get("t_base", 25.0))
    amplitude = float(w_params.get("amplitude", 9.0))
    peak_doy = int(w_params.get("peak_doy", 150))

    t_seasonal = amplitude * np.cos(2.0 * np.pi * (doy - peak_doy) / 365.25)
    t_noise = rng.normal(0, 1.4, n_days)
    tmean = t_base + t_seasonal + t_noise

    diurnal = float(w_params.get("trange_c", 11.0))
    tmax = np.round(tmean + 0.5 * diurnal, 2)
    tmin = np.round(tmean - 0.5 * diurnal, 2)

    # Precipitation model from regional gamma parameters
    wet_start = int(w_params.get("wet_start_month", 7))
    wet_end = int(w_params.get("wet_end_month", 9))
    gamma_wet = w_params.get("gamma_wet", [0.5, 10.0])
    gamma_dry = w_params.get("gamma_dry", [0.08, 3.0])

    wet = (idx.month >= wet_start) & (idx.month <= wet_end)
    precip = np.where(
        wet,
        rng.gamma(gamma_wet[0], gamma_wet[1], n_days),
        rng.gamma(gamma_dry[0], gamma_dry[1], n_days),
    )
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
