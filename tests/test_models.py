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


def test_rusle_r_factor_intensity():
    base_r = rusle.r_factor_annual(900.0)
    assert rusle.r_factor_intensity(900.0) == pytest.approx(base_r)

    cloudburst_r = rusle.r_factor_intensity(900.0, max_30m_rate_mmh=65.0, extreme_rain_days_per_yr=6.0)
    drizzle_r = rusle.r_factor_intensity(900.0, max_30m_rate_mmh=6.0, extreme_rain_days_per_yr=0.5)
    assert cloudburst_r > base_r
    assert drizzle_r < cloudburst_r


def test_fao56_initial_depletion_mm():
    from terraloop_engine.models import fao56_runner
    from terraloop_schemas import FarmConstraints, Rotation, RotationStep, SoilSummary

    idx = pd.date_range("2015-01-01", "2016-12-31", freq="D")
    tmax = np.full(len(idx), 28.0)
    tmin = np.full(len(idx), 14.0)
    precip = np.full(len(idx), 0.4)
    w_df = pd.DataFrame({"T2M_MAX": tmax, "T2M_MIN": tmin, "PRECTOTCORR": precip}, index=idx)
    soil_s = SoilSummary(texture_class="loam", sand_pct=45.0, silt_pct=35.0, clay_pct=20.0, soc_g_per_kg=6.0)
    rot = Rotation(id="wheat_dep", steps=[RotationStep(year_index=0, season_index=1, crop_id="wheat")])

    res_wet = fao56_runner.simulate_rotation(
        rot, w_df, soil_s, FarmConstraints(irrigation="none"), start_year=2015, initial_depletion_mm=0.0
    )
    res_dry = fao56_runner.simulate_rotation(
        rot, w_df, soil_s, FarmConstraints(irrigation="none"), start_year=2015, initial_depletion_mm=95.0
    )
    assert res_dry[0]["yield_t_ha"] <= res_wet[0]["yield_t_ha"]
    assert res_dry[0]["water_stress_coefficient"] <= res_wet[0]["water_stress_coefficient"]


def test_fao56_vernalization_and_dormancy_frost_kill():
    from terraloop_engine import crop_kb
    from terraloop_engine.models import fao56_runner
    from terraloop_schemas import FarmConstraints, Rotation, RotationStep, SoilSummary

    crops = crop_kb.load_crops()
    soil_s = SoilSummary(texture_class="silty clay loam", sand_pct=15.0, silt_pct=55.0, clay_pct=30.0, soc_g_per_kg=18.0)
    rot = Rotation(id="ww_test", steps=[RotationStep(year_index=0, season_index=1, crop_id="wheat_winter", sowing_doy=280)])

    # Cool vernalizing winter (~4 C mean, ~12 C late spring) vs unchilled warm winter (~18 C) vs -25 C lethal frost
    idx = pd.date_range("2015-01-01", "2017-12-31", freq="D")
    doy = idx.dayofyear.to_numpy()
    winter_cool = 9.0 - 9.0 * np.cos(2 * np.pi * (doy - 20) / 365.0)  # Jan ~0 C, Jul ~18 C
    warm_nochill = 19.0 - 4.0 * np.cos(2 * np.pi * (doy - 20) / 365.0)  # Jan ~15 C, never chills
    severe_kill = np.where((doy >= 10) & (doy <= 30), -25.0, winter_cool)

    def _make_df(tmean: np.ndarray, tmin_shift: float = -4.0) -> pd.DataFrame:
        return pd.DataFrame(
            {"T2M_MAX": tmean + 4.0, "T2M_MIN": tmean + tmin_shift, "PRECTOTCORR": np.full(len(idx), 2.5)},
            index=idx,
        )

    res_chill = fao56_runner.simulate_rotation(
        rot, _make_df(winter_cool), soil_s, FarmConstraints(irrigation="none"), crops=crops, start_year=2015, cultivar_zone="maritime_europe"
    )
    res_unchilled = fao56_runner.simulate_rotation(
        rot, _make_df(warm_nochill), soil_s, FarmConstraints(irrigation="none"), crops=crops, start_year=2015, cultivar_zone="maritime_europe"
    )
    res_kill = fao56_runner.simulate_rotation(
        rot, _make_df(severe_kill, tmin_shift=-4.0), soil_s, FarmConstraints(irrigation="none"), crops=crops, start_year=2015, cultivar_zone="maritime_europe"
    )
    assert res_chill[0]["yield_t_ha"] > res_unchilled[0]["yield_t_ha"]
    assert res_chill[0]["yield_t_ha"] > res_kill[0]["yield_t_ha"]


def test_soil_health_card_multi_standard_conversions():
    from terraloop_engine import profiler
    from terraloop_schemas import (
        ClimateSummary,
        FieldGeometry,
        FieldProfile,
        HazardSummary,
        SoilHealthCardInput,
        SoilSummary,
        WaterSummary,
    )

    base_soil = SoilSummary(texture_class="loam", sand_pct=40.0, silt_pct=40.0, clay_pct=20.0, ph=6.5, soc_g_per_kg=10.0)
    base_prof = FieldProfile(
        field=FieldGeometry(lat=42.03, lon=-93.62, name="Test"),
        climate=ClimateSummary(
            baseline_period="1985-2004",
            recent_period="2005-2024",
            mean_tmax_c=16.0,
            mean_tmin_c=4.0,
            annual_precip_mm=850.0,
            recent_annual_precip_mm=880.0,
            precip_change_pct=3.5,
            tmax_change_c=0.8,
            heat_days_per_year=4.0,
            recent_heat_days_per_year=5.0,
            frost_days_per_year=120.0,
            longest_dry_spell_days_mean=18.0,
            annual_et0_mm=950.0,
            gdd_base10_per_year=1800.0,
            monthly_precip_mm=[30.0, 32.0, 55.0, 85.0, 115.0, 125.0, 115.0, 105.0, 80.0, 55.0, 33.0, 20.0],
            monthly_tmax_c=[-2.0, 1.0, 8.0, 16.0, 22.0, 27.0, 29.0, 28.0, 23.0, 16.0, 7.0, 0.0],
            monthly_tmin_c=[-12.0, -9.0, -3.0, 4.0, 10.0, 15.0, 18.0, 16.0, 11.0, 4.0, -3.0, -9.0],
        ),
        water=WaterSummary(climatic_water_balance_mm=-100.0),
        soil=base_soil,
        hazards=HazardSummary(),
    )

    m3 = profiler.apply_soil_health_card_override(
        base_prof,
        SoilHealthCardInput(lab_standard="mehlich3", ph=6.4, organic_matter_pct=3.448, phosphorus_ppm=20.0, potassium_ppm=150.0, nitrate_n_ppm=25.0),
    )
    olsen = profiler.apply_soil_health_card_override(
        base_prof,
        SoilHealthCardInput(lab_standard="olsen", ph=6.4, organic_matter_pct=3.448, phosphorus_ppm=20.0, potassium_ppm=150.0),
    )
    assert m3.soil.soc_g_per_kg == pytest.approx(20.0, abs=0.2)
    assert m3.soil.available_p_kg_ha == pytest.approx(20.0 * 2.24 * 0.65, abs=0.2)
    assert olsen.soil.available_p_kg_ha == pytest.approx(20.0 * 2.24, abs=0.2)
    assert m3.soil.available_p_kg_ha < olsen.soil.available_p_kg_ha
    assert m3.soil.available_k_kg_ha == pytest.approx(150.0 * 2.24, abs=0.2)
    assert any("Local Accredited Soil Testing Lab" in (p.source or "") for p in m3.soil.provenance)





