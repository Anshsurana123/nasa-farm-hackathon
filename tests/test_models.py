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


def test_rothc_convergence_and_retention_vs_burning():
    from terraloop_engine.models import soil_health

    # 1. Constant inputs -> SOC converges
    res_long = soil_health.rothc_lite(initial_soc_t_ha=40.0, annual_c_input_t_ha=2.5, years=30)
    socs = res_long["annual_soc_t_ha"]
    # Change in first 5 years vs change in last 5 years shows damping
    early_change = abs(socs[5] - socs[0])
    late_change = abs(socs[-1] - socs[-6])
    assert late_change < early_change

    # 2. Retention vs burning over 10 years
    # Retaining 4 t residue * 0.45 = 1.8 t C/ha vs burnt (only 0.2 t C/ha ash)
    res_retention = soil_health.rothc_lite(initial_soc_t_ha=35.0, annual_c_input_t_ha=2.5, years=10)
    res_burning = soil_health.rothc_lite(initial_soc_t_ha=35.0, annual_c_input_t_ha=0.4, years=10)
    assert res_retention["final_soc_t_ha"] > res_burning["final_soc_t_ha"]
    assert res_retention["soc_delta_10yr"] > res_burning["soc_delta_10yr"]


def test_n_balance_legume_credit():
    from terraloop_engine import crop_kb
    from terraloop_engine.models import soil_health

    crops = crop_kb.load_crops()
    wheat = crops["wheat"]
    moong = crops["moong"]

    # Wheat following cereal (no legume)
    bal_std = soil_health.n_balance(wheat, yield_t_ha=4.8, preceded_by_legume=False)
    # Wheat following legume credit
    bal_cred = soil_health.n_balance(wheat, yield_t_ha=4.8, preceded_by_legume=True)

    assert bal_cred["fertilizer_saved_kg_ha"] == 25.0
    assert bal_cred["fertilizer_applied_kg_ha"] < bal_std["fertilizer_applied_kg_ha"]

    # Moong itself fixes atmospheric N
    bal_moong = soil_health.n_balance(moong, yield_t_ha=1.2)
    assert bal_moong["n_fixation_kg_ha"] > 40.0


def test_soil_health_score_differentiation():
    from terraloop_engine import crop_kb
    from terraloop_engine.models import soil_health
    from terraloop_schemas import Rotation, RotationStep

    crops = crop_kb.load_crops()

    # Baseline: rice_puddled - wheat - fallow with burning & puddling
    baseline_rot = Rotation(
        id="baseline",
        is_baseline=True,
        steps=[
            RotationStep(year_index=0, season_index=0, crop_id="rice_puddled", practices=["conventional", "burning"]),
            RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["conventional"]),
            RotationStep(year_index=0, season_index=2, crop_id="fallow", practices=[]),
        ],
    )

    # Regenerative alternative: rice_dsr - wheat - moong with zero till & residue retention
    regen_rot = Rotation(
        id="regen",
        steps=[
            RotationStep(year_index=0, season_index=0, crop_id="rice_dsr", practices=["direct_seeded", "residue_retained"]),
            RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["no_till", "residue_retained"]),
            RotationStep(year_index=0, season_index=2, crop_id="moong", practices=["no_till", "residue_retained"]),
        ],
    )

    score_base = soil_health.soil_health_score(baseline_rot, crops, soc_delta_10yr=-1.5, erosion_t_ha_yr=8.0)
    score_regen = soil_health.soil_health_score(regen_rot, crops, soc_delta_10yr=2.2, erosion_t_ha_yr=2.0)

    assert score_regen > score_base + 25.0
    assert 0 <= score_base <= 100
    assert 0 <= score_regen <= 100


def test_economics_punjab_plausible():
    from terraloop_engine.models import economics

    # Wheat in Punjab: 4.8 t/ha yield
    wheat_econ_inr = economics.profit_per_ha("wheat", yield_t_ha=4.8, currency="INR")
    # Operating revenue ~ 4.8 * 22,750 = ~109,200; cost ~ 30,000; profit ~ 79,200
    assert 60_000 <= wheat_econ_inr["profit_per_ha"] <= 95_000

    # Rice in Punjab: 6.5 t/ha yield
    rice_econ_inr = economics.profit_per_ha("rice_puddled", yield_t_ha=6.5, currency="INR")
    assert 85_000 <= rice_econ_inr["profit_per_ha"] <= 125_000

    # USD test
    wheat_usd = economics.profit_per_ha("wheat", yield_t_ha=4.8, currency="USD")
    assert 700 <= wheat_usd["profit_per_ha"] <= 1300


def test_aquacrop_runner_wheat_yield_and_rice_vs_maize_irrigation():
    from terraloop_engine.models import aquacrop_runner
    from terraloop_schemas import FarmConstraints, Rotation, RotationStep, SoilSummary

    # Synthetic multi-year weather
    idx = pd.date_range("2010-01-01", "2020-12-31", freq="D")
    doy = idx.dayofyear.to_numpy()
    tmax = 30 + 10 * np.sin(2 * np.pi * (doy - 80) / 365)
    tmin = tmax - 13
    rng = np.random.default_rng(42)
    monsoon = (idx.month >= 7) & (idx.month <= 9)
    precip = np.where(monsoon, rng.gamma(0.6, 12, len(idx)), rng.gamma(0.1, 5, len(idx)))
    w_df = pd.DataFrame(
        {"T2M_MAX": tmax, "T2M_MIN": tmin, "PRECTOTCORR": precip},
        index=idx,
    )
    soil = SoilSummary(texture_class="loam", sand_pct=45.0, silt_pct=35.0, clay_pct=20.0, soc_g_per_kg=6.0)
    constraints = FarmConstraints(irrigation="full")

    # 1. Wheat yield 3.5 - 6.0 t/ha
    rot_wheat = Rotation(
        id="wheat_test",
        steps=[RotationStep(year_index=0, season_index=1, crop_id="wheat")],
    )
    res_wheat = aquacrop_runner.simulate_rotation(rot_wheat, w_df, soil, constraints, start_year=2015)
    wheat_yield = res_wheat[0]["yield_t_ha"]
    assert 3.5 <= wheat_yield <= 6.0, f"Wheat yield {wheat_yield} not in [3.5, 6.0]"

    # 2. Rice irrigation > Maize irrigation
    rot_rice = Rotation(
        id="rice_test",
        steps=[RotationStep(year_index=0, season_index=0, crop_id="rice_puddled")],
    )
    rot_maize = Rotation(
        id="maize_test",
        steps=[RotationStep(year_index=0, season_index=0, crop_id="maize")],
    )
    res_rice = aquacrop_runner.simulate_rotation(rot_rice, w_df, soil, constraints, start_year=2015)
    res_maize = aquacrop_runner.simulate_rotation(rot_maize, w_df, soil, constraints, start_year=2015)

    assert res_rice[0]["irrigation_mm"] > res_maize[0]["irrigation_mm"] * 1.5


def test_aquacrop_puddled_vs_dsr_calibration():
    from terraloop_engine.models import aquacrop_runner
    from terraloop_schemas import FarmConstraints, Rotation, RotationStep, SoilSummary

    idx = pd.date_range("2015-01-01", "2016-12-31", freq="D")
    doy = idx.dayofyear.to_numpy()
    tmax = 30 + 10 * np.sin(2 * np.pi * (doy - 80) / 365)
    tmin = tmax - 13
    precip = np.where((idx.month >= 7) & (idx.month <= 9), 4.0, 0.5)
    w_df = pd.DataFrame(
        {"T2M_MAX": tmax, "T2M_MIN": tmin, "PRECTOTCORR": precip},
        index=idx,
    )
    soil = SoilSummary(texture_class="loam", sand_pct=45.0, silt_pct=35.0, clay_pct=20.0, soc_g_per_kg=6.0)
    constraints = FarmConstraints(irrigation="full")

    rot_puddled = Rotation(
        id="puddled",
        steps=[RotationStep(year_index=0, season_index=0, crop_id="rice_puddled")],
    )
    rot_dsr = Rotation(
        id="dsr",
        steps=[RotationStep(year_index=0, season_index=0, crop_id="rice_dsr")],
    )

    res_puddled = aquacrop_runner.simulate_rotation(rot_puddled, w_df, soil, constraints, start_year=2015)
    res_dsr = aquacrop_runner.simulate_rotation(rot_dsr, w_df, soil, constraints, start_year=2015)

    irr_puddled = res_puddled[0]["irrigation_mm"]
    irr_dsr = res_dsr[0]["irrigation_mm"]
    yield_puddled = res_puddled[0]["yield_t_ha"]
    yield_dsr = res_dsr[0]["yield_t_ha"]

    # DSR irrigation 10-30% below puddled
    water_saving_pct = (irr_puddled - irr_dsr) / irr_puddled * 100.0
    assert 10.0 <= water_saving_pct <= 30.0, f"Water saving {water_saving_pct}% not in [10%, 30%]"

    # Yields within 15%
    yield_diff_pct = abs(yield_puddled - yield_dsr) / yield_puddled * 100.0
    assert yield_diff_pct <= 15.0, f"Yield diff {yield_diff_pct}% exceeds 15%"



