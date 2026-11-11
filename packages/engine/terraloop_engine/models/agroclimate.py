"""Agro-climatic indicators computed from daily weather."""

from __future__ import annotations

import numpy as np
import pandas as pd


def extraterrestrial_radiation(lat_deg: float, doy: np.ndarray) -> np.ndarray:
    """Ra in MJ m-2 day-1 (FAO-56 eq. 21)."""
    phi = np.deg2rad(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(delta), -1, 1))
    gsc = 0.0820
    return (24 * 60 / np.pi) * gsc * dr * (
        ws * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(ws)
    )


def et0_hargreaves(tmax: pd.Series, tmin: pd.Series, lat_deg: float) -> pd.Series:
    """Reference ET (mm/day) via Hargreaves-Samani (FAO-56 eq. 52)."""
    doy = tmax.index.dayofyear.to_numpy()
    ra = extraterrestrial_radiation(lat_deg, doy)
    tmean = (tmax + tmin) / 2
    trange = (tmax - tmin).clip(lower=0)
    et0 = 0.0023 * 0.408 * ra * (tmean + 17.8) * np.sqrt(trange)
    return et0.clip(lower=0)


def gdd(tmax: pd.Series, tmin: pd.Series, base: float = 10.0, cap: float = 30.0) -> pd.Series:
    """Growing degree days (method with upper cap)."""
    tx = tmax.clip(upper=cap)
    tn = tmin.clip(upper=cap)
    return (((tx + tn) / 2) - base).clip(lower=0)


def wettest_window(monthly_precip: list[float], length: int = 4) -> list[int]:
    """Return month numbers (1-12) of the wettest consecutive window (wraps the year)."""
    arr = np.array(monthly_precip)
    best_start, best = 0, -1.0
    for start in range(12):
        idx = [(start + i) % 12 for i in range(length)]
        total = arr[idx].sum()
        if total > best:
            best, best_start = total, start
    return [((best_start + i) % 12) + 1 for i in range(length)]


def longest_dry_spell(precip: pd.Series, months: list[int], threshold_mm: float = 1.0) -> float:
    """Mean across years of the longest run of dry days within the given months."""
    sub = precip[precip.index.month.isin(months)]
    if sub.empty:
        return float("nan")
    spells = []
    for _, year_series in sub.groupby(sub.index.year):
        dry = (year_series < threshold_mm).to_numpy()
        longest = run = 0
        for d in dry:
            run = run + 1 if d else 0
            longest = max(longest, run)
        spells.append(longest)
    return float(np.mean(spells))


# ---------------------------------------------------------------------------
# FAO-56 Annex Worked Examples & Equations (WS-F4)
# ---------------------------------------------------------------------------
def wind_speed_2m(u_z: float, z: float = 10.0) -> float:
    """Convert wind speed measured at height z (m) to standard 2m height (FAO-56 eq. 47).

    u_2 = u_z * 4.87 / ln(67.8 * z - 5.42).
    For standard 10m anemometer height: conversion factor is 4.87 / ln(672.58) = 0.748.
    """
    if z <= 2.0:
        return float(u_z)
    factor = 4.87 / np.log(67.8 * z - 5.42)
    return float(u_z * factor)


def saturation_vapor_pressure(t_c: float) -> float:
    """Saturation vapour pressure e_s(T) in kPa from air temperature (FAO-56 eq. 11)."""
    return float(0.6108 * np.exp(17.27 * t_c / (t_c + 237.3)))


def vapor_pressure_slope(t_c: float) -> float:
    """Slope of saturation vapour pressure curve Delta in kPa/°C (FAO-56 eq. 13)."""
    es = saturation_vapor_pressure(t_c)
    return float(4098.0 * es / ((t_c + 237.3) ** 2))


def psychrometric_constant(elevation_m: float = 0.0) -> float:
    """Psychrometric constant gamma in kPa/°C at given elevation (FAO-56 eq. 7, 8)."""
    # Atmospheric pressure P in kPa (FAO-56 eq. 7)
    p = 101.3 * (((293.0 - 0.0065 * elevation_m) / 293.0) ** 5.26)
    return float(0.000665 * p)


def et0_penman_monteith(
    tmean_c: float,
    rn_mj_m2_day: float,
    g_mj_m2_day: float,
    u2_m_s: float,
    ea_kpa: float,
    elevation_m: float = 0.0,
) -> float:
    """Standard daily reference evapotranspiration ET0 (mm/day) via FAO-56 Penman-Monteith (eq. 6)."""
    es = saturation_vapor_pressure(tmean_c)
    delta = vapor_pressure_slope(tmean_c)
    gamma = psychrometric_constant(elevation_m)

    numerator = 0.408 * delta * (rn_mj_m2_day - g_mj_m2_day) + gamma * (900.0 / (tmean_c + 273.0)) * u2_m_s * (es - ea_kpa)
    denominator = delta + gamma * (1.0 + 0.34 * u2_m_s)
    return float(max(0.0, numerator / denominator))


def fao56_depletion_ks(dr_mm: float, raw_mm: float, taw_mm: float) -> float:
    """Daily root-zone water stress coefficient Ks (FAO-56 eq. 84, Box 11).

    When Dr <= RAW: Ks = 1.0 (no water stress).
    When RAW < Dr < TAW: Ks declines linearly: Ks = (TAW - Dr) / (TAW - RAW).
    When Dr >= TAW: Ks = 0.0 (wilting point reached).
    """
    if dr_mm <= raw_mm:
        return 1.0
    if dr_mm >= taw_mm:
        return 0.0
    return float(max(0.0, (taw_mm - dr_mm) / max(1e-6, (taw_mm - raw_mm))))

