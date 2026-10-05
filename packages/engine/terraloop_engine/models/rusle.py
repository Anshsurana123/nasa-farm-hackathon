"""Revised Universal Soil Loss Equation (RUSLE): A = R * K * LS * C * P.

A  : soil loss, t ha-1 yr-1
R  : rainfall erosivity, MJ mm ha-1 h-1 yr-1
K  : soil erodibility, t ha h ha-1 MJ-1 mm-1
LS : slope length & steepness factor (dimensionless)
C  : cover-management factor (0-1), depends on the ROTATION -> optimiser input
P  : support practice factor (0-1)

This module is the reference example of how a process model should look:
pure functions, SI units in names/docstrings, cited equations, no I/O.
"""

from __future__ import annotations

import math


def r_factor_annual(annual_precip_mm: float) -> float:
    """Rainfall erosivity from annual precipitation.

    Renard & Freimund (1994), J. Hydrology 157:287-306. Converted to SI.
    Used until a GPM IMERG intensity-based R factor is implemented (TASK-M04).
    """
    p = max(annual_precip_mm, 0.0)
    if p < 850:
        return 0.0483 * p**1.61
    return 587.8 - 1.219 * p + 0.004105 * p**2


def k_factor_williams(sand_pct: float, silt_pct: float, clay_pct: float, soc_pct: float) -> float:
    """Soil erodibility (EPIC equation, Williams 1995), SI units t ha h / (ha MJ mm)."""
    sn = sand_pct
    si = silt_pct
    cl = clay_pct
    oc = soc_pct
    sn1 = 1 - sn / 100
    f_csand = 0.2 + 0.3 * math.exp(-0.256 * sn * (1 - si / 100))
    f_clsi = (si / max(cl + si, 1e-6)) ** 0.3
    f_orgc = 1 - (0.25 * oc) / (oc + math.exp(3.72 - 2.95 * oc))
    f_hisand = 1 - (0.7 * sn1) / (sn1 + math.exp(-5.51 + 22.9 * sn1))
    return f_csand * f_clsi * f_orgc * f_hisand * 0.1317


def ls_factor(slope_pct: float, slope_length_m: float = 50.0) -> float:
    """Wischmeier & Smith (1978) LS factor."""
    s = max(slope_pct, 0.0)
    theta = math.atan(s / 100)
    if s < 1:
        m = 0.2
    elif s < 3.5:
        m = 0.3
    elif s < 4.5:
        m = 0.4
    else:
        m = 0.5
    return (slope_length_m / 22.13) ** m * (65.41 * math.sin(theta) ** 2 + 4.56 * math.sin(theta) + 0.065)


def soil_loss(r: float, k: float, ls: float, c: float, p: float = 1.0) -> float:
    """Annual soil loss A (t ha-1 yr-1)."""
    return r * k * ls * c * p


def erosion_class(a_t_ha_yr: float) -> str:
    """Map soil loss to a qualitative class (FAO-style thresholds)."""
    if a_t_ha_yr < 2:
        return "low"
    if a_t_ha_yr < 10:
        return "moderate"
    if a_t_ha_yr < 20:
        return "high"
    return "very_high"
