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
