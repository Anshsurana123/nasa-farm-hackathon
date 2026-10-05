"""Unit tests for pure science functions (no network)."""

import math

import numpy as np
import pandas as pd
import pytest
from terraloop_engine.models import agroclimate, rusle, soil


@pytest.mark.parametrize(
    "sand,silt,clay,expected",
    [
        (92, 5, 3, "sand"),
        (40, 40, 20, "loam"),
        (20, 65, 15, "silt loam"),
        (10, 30, 60, "clay"),
        (65, 20, 15, "sandy loam"),
        (30, 35, 35, "clay loam"),
    ],
)
def test_usda_texture(sand, silt, clay, expected):
    assert soil.usda_texture_class(sand, silt, clay) == expected


def test_saxton_rawls_loam_reasonable():
    fc, wp = soil.saxton_rawls(40, 20, 15)
    assert 0.25 < fc < 0.35
    assert 0.08 < wp < 0.16
    assert fc > wp


def test_extraterrestrial_radiation_equator_range():
    ra = agroclimate.extraterrestrial_radiation(0.0, np.arange(1, 366))
    assert 33 < ra.mean() < 40  # ~37 MJ/m2/day at the equator


def test_et0_hargreaves_positive_and_plausible():
    idx = pd.date_range("2020-06-01", periods=30, freq="D")
    tmax = pd.Series(38.0, index=idx)
    tmin = pd.Series(26.0, index=idx)
    et0 = agroclimate.et0_hargreaves(tmax, tmin, 30.9)
    assert (et0 > 4).all() and (et0 < 10).all()


def test_gdd_capped():
    idx = pd.date_range("2020-01-01", periods=3)
    g = agroclimate.gdd(pd.Series([40, 20, 5], index=idx), pd.Series([30, 10, 0], index=idx), base=10)
    assert list(g) == [20.0, 5.0, 0.0]


def test_wettest_window_monsoon():
    monthly = [20, 25, 20, 10, 15, 60, 200, 180, 100, 15, 5, 10]
    assert agroclimate.wettest_window(monthly, 4) == [6, 7, 8, 9]


def test_longest_dry_spell():
    idx = pd.date_range("2020-07-01", "2020-07-31")
    p = pd.Series(5.0, index=idx)
    p.iloc[5:15] = 0.0  # 10-day gap
    assert agroclimate.longest_dry_spell(p, [7]) == 10


def test_rusle_components():
    assert rusle.r_factor_annual(600) > 0
    k = rusle.k_factor_williams(40, 40, 20, 1.0)
    assert 0.01 < k < 0.06
    assert rusle.ls_factor(0.5) < rusle.ls_factor(5) < rusle.ls_factor(15)
    assert rusle.erosion_class(1) == "low" and rusle.erosion_class(25) == "very_high"
    assert math.isclose(rusle.soil_loss(100, 0.03, 1.0, 0.5, 1.0), 1.5)
