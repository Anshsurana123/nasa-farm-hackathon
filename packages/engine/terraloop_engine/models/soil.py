"""Soil derivations: USDA texture class and Saxton & Rawls (2006) hydraulics."""

from __future__ import annotations


def usda_texture_class(sand: float, silt: float, clay: float) -> str:
    """Classify texture using the USDA soil texture triangle (inputs in %)."""
    total = sand + silt + clay
    if total <= 0:
        return "unknown"
    sand, silt, clay = (100 * v / total for v in (sand, silt, clay))
    if silt + 1.5 * clay < 15:
        return "sand"
    if silt + 1.5 * clay >= 15 and silt + 2 * clay < 30:
        return "loamy sand"
    if (7 <= clay < 20 and sand > 52 and silt + 2 * clay >= 30) or (
        clay < 7 and silt < 50 and silt + 2 * clay >= 30
    ):
        return "sandy loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "loam"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "silt loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "sandy clay loam"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "clay loam"
    if 27 <= clay < 40 and sand <= 20:
        return "silty clay loam"
    if clay >= 35 and sand > 45:
        return "sandy clay"
    if clay >= 40 and silt >= 40:
        return "silty clay"
    return "clay"


def saxton_rawls(sand_pct: float, clay_pct: float, soc_g_kg: float) -> tuple[float, float]:
    """Return (field capacity, wilting point) as volumetric fractions.

    Saxton, K.E. & Rawls, W.J. (2006) SSSAJ 70:1569-1578.
    Organic matter (%) = SOC (%) * 1.724.
    """
    s = sand_pct / 100
    c = clay_pct / 100
    om = min((soc_g_kg / 10) * 1.724, 8.0)

    t1500 = (
        -0.024 * s + 0.487 * c + 0.006 * om + 0.005 * s * om
        - 0.013 * c * om + 0.068 * s * c + 0.031
    )
    wp = t1500 + (0.14 * t1500 - 0.02)

    t33 = (
        -0.251 * s + 0.195 * c + 0.011 * om + 0.006 * s * om
        - 0.027 * c * om + 0.452 * s * c + 0.299
    )
    fc = t33 + (1.283 * t33**2 - 0.374 * t33 - 0.015)
    return round(fc, 3), round(wp, 3)
