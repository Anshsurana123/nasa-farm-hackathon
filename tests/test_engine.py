"""Profiler, crop KB, suitability, rotations, selection, API (no network)."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from terraloop_engine import crop_kb, profiler, suitability
from terraloop_engine.models.soil_health import family_shannon_index
from terraloop_engine.optimize import rotations, selection
from terraloop_schemas import (
    FarmConstraints,
    FieldGeometry,
    FieldProfile,
    Priorities,
    SimulationResult,
    WaterSummary,
)


def synthetic_punjab_weather(years=(2000, 2009)) -> pd.DataFrame:
    """Monsoon-like synthetic daily weather resembling central Punjab."""
    idx = pd.date_range(f"{years[0]}-01-01", f"{years[1]}-12-31", freq="D")
    doy = idx.dayofyear.to_numpy()
    tmax = 30 + 10 * np.sin(2 * np.pi * (doy - 80) / 365)
    tmin = tmax - 13
    rng = np.random.default_rng(0)
    monsoon = (idx.month >= 7) & (idx.month <= 9)
    precip = np.where(monsoon, rng.gamma(0.6, 12, len(idx)), rng.gamma(0.1, 5, len(idx)))
    return pd.DataFrame(
        {"T2M_MAX": tmax, "T2M_MIN": tmin, "PRECTOTCORR": precip,
         "ALLSKY_SFC_SW_DWN": 20.0, "RH2M": 50.0, "WS2M": 2.0},
        index=idx,
    )


@pytest.fixture(scope="module")
def punjab_profile() -> FieldProfile:
    climate, hazards, wb = profiler.summarise_climate(synthetic_punjab_weather(), 30.9)
    soil = profiler.summarise_soil({"sand": 45, "silt": 35, "clay": 20, "soc": 5, "phh2o": 8.0, "bdod": 150})
    return FieldProfile(
        field=FieldGeometry(lat=30.9, lon=75.8),
        climate=climate,
        water=WaterSummary(climatic_water_balance_mm=wb),
        soil=soil,
        hazards=hazards,
    )


def test_climate_summary(punjab_profile):
    c = punjab_profile.climate
    assert len(c.monthly_precip_mm) == 12
    assert c.wettest_months[0] in (6, 7)
    assert c.annual_et0_mm > c.annual_precip_mm  # semi-arid, irrigation-dependent


def test_soil_summary(punjab_profile):
    s = punjab_profile.soil
    assert s.texture_class == "loam"
    assert s.bulk_density_g_cm3 == 1.5
    assert s.field_capacity_vol > s.wilting_point_vol


def test_crop_kb_loads_and_is_consistent():
    crops = crop_kb.load_crops()
    assert len(crops) >= 20
    for c in crops.values():
        for ref in c.good_predecessors + c.bad_predecessors:
            assert ref in crops, f"{c.id} references unknown crop '{ref}'"


def test_aquacrop_params_coverage():
    crops = crop_kb.load_crops()
    overrides = crop_kb.load_all_aquacrop_overrides()
    for crop_id, c in crops.items():
        assert c.aquacrop_name is not None or crop_id in overrides, (
            f"Crop {crop_id} lacks both built-in aquacrop_name and an aquacrop_params override file"
        )



def test_suitability_punjab_seasons(punjab_profile):
    crops = crop_kb.load_crops()
    ranked = {r.crop_id: r for r in suitability.rank_crops(punjab_profile, crops)}
    assert ranked["wheat"].score > 0.3
    assert ranked["rice_puddled"].score > 0.3
    assert ranked["wheat"].sowing_months[0] in (10, 11, 12)


def test_rotation_generation_constraints():
    crops = crop_kb.load_crops()
    cons = FarmConstraints(rotation_years=1, must_grow=["wheat"])
    rots = rotations.generate_rotations(crops, cons)
    assert rots, "should generate candidates"
    for r in rots:
        ids = [s.crop_id for s in r.steps]
        assert "wheat" in ids
        assert ids[0] in crops and "warm" in crops[ids[0]].season_type


def test_baseline_and_diversity():
    crops = crop_kb.load_crops()
    base = rotations.baseline_rice_wheat()
    assert family_shannon_index(base, crops) == 0.0  # two cereals: no family diversity


def test_selection_respects_priorities():
    cands = [
        {"profit": 100, "water_savings": -1500, "soil_health": 40},
        {"profit": 80, "water_savings": -800, "soil_health": 60},
        {"profit": 60, "water_savings": -500, "soil_health": 75},
    ]
    labels = ["a", "b", "c"]
    profit_first = selection.select_top(cands, labels, Priorities(profit=5, water_savings=0, soil_health=0, low_risk=0), k=1)
    water_first = selection.select_top(cands, labels, Priorities(profit=0, water_savings=5, soil_health=1, low_risk=0), k=1)
    assert profit_first == [0] and water_first == [2]


def test_api_basics_and_recommend_endpoint():
    from terraloop_api.main import app

    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert len(client.get("/crops").json()) >= 20
    assert any(f["id"] == "sangrur" for f in client.get("/golden").json())

    # TASK-A03: Sangrur + 'water first' priorities -> top strategy uses less irrigation than baseline
    payload = {
        "field": {"lat": 30.2, "lon": 75.92, "name": "Sangrur hero field"},
        "priorities": {"profit": 0.0, "water_savings": 5.0, "soil_health": 1.0, "low_risk": 0.0},
        "constraints": {"irrigation": "full", "rotation_years": 1},
    }
    resp = client.post("/recommend", json=payload)
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) == 4
    baseline = recs[0]
    top_strat = recs[1]
    assert baseline["rank"] == 0
    assert top_strat["rank"] == 1

    # Assert top strategy uses less irrigation than baseline
    base_irr = float(np.mean(baseline["results"][0]["irrigation_mm"]))
    top_irr = float(np.mean(top_strat["results"][0]["irrigation_mm"]))
    assert top_irr < base_irr, f"Top strategy irrigation {top_irr} not < baseline {base_irr}"

    # TASK-X01: why cards and provenances present
    assert len(top_strat["why"]) >= 2
    assert len(top_strat["provenance"]) >= 1



def test_historical_members_moving_blocks():
    from terraloop_engine.climate import ensembles

    # 40-year daily weather series 1985-2024
    w40 = synthetic_punjab_weather(years=(1985, 2024))
    members = ensembles.historical_members(w40, rotation_years=1)
    assert len(members) >= 30, f"Expected >= 30 members for 1-yr rotation, got {len(members)}"
    assert "hist_1985" in members
    assert "hist_2024" in members

    # 3-year rotation moving blocks
    members_3yr = ensembles.historical_members(w40, rotation_years=3)
    assert len(members_3yr) >= 30


def test_quantile_mapping():
    from terraloop_engine.climate import ensembles

    obs = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    model_hist = pd.Series([12.0, 22.0, 32.0, 42.0, 52.0])  # +2 warm bias
    model_future = pd.Series([15.0, 25.0, 35.0, 45.0, 55.0])
    corrected = ensembles.quantile_map(obs, model_hist, model_future)
    # The bias should be removed (values lower than model_future)
    assert (corrected < model_future).all()


def test_evaluate_rotation_baseline_vs_alternatives(punjab_profile):
    import time

    from terraloop_engine.climate import ensembles
    from terraloop_engine.optimize import evaluate, rotations
    from terraloop_schemas import FarmConstraints, Rotation, RotationStep

    w = synthetic_punjab_weather(years=(2010, 2019))
    members = ensembles.historical_members(w, rotation_years=1)
    constraints = FarmConstraints(irrigation="full")

    # Baseline: rice_puddled + wheat + fallow
    baseline = rotations.baseline_rice_wheat()

    # Smart alternative: rice_dsr + wheat + moong
    alt_smart = Rotation(
        id="rice_dsr_wheat_moong",
        steps=[
            RotationStep(year_index=0, season_index=0, crop_id="rice_dsr", practices=["direct_seeded", "residue_retained"]),
            RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["no_till", "residue_retained"]),
            RotationStep(year_index=0, season_index=2, crop_id="moong", practices=["no_till", "residue_retained"]),
        ],
    )

    # Water-saving alternative: maize + wheat + moong
    alt_maize = Rotation(
        id="maize_wheat_moong",
        steps=[
            RotationStep(year_index=0, season_index=0, crop_id="maize", practices=["residue_retained"]),
            RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["residue_retained"]),
            RotationStep(year_index=0, season_index=2, crop_id="moong", practices=["residue_retained"]),
        ],
    )

    t0 = time.time()
    res_base = evaluate.evaluate_rotation(baseline, members, punjab_profile, constraints)
    res_smart = evaluate.evaluate_rotation(alt_smart, members, punjab_profile, constraints)
    res_maize = evaluate.evaluate_rotation(alt_maize, members, punjab_profile, constraints)
    t_elapsed = time.time() - t0

    # Runtime is fast
    assert t_elapsed < 5.0, f"Evaluation took {t_elapsed} s"

    # Objectives differ distinctly
    # Mean irrigation: baseline > smart > maize
    irr_base = np.mean(res_base.irrigation_mm)
    irr_smart = np.mean(res_smart.irrigation_mm)
    irr_maize = np.mean(res_maize.irrigation_mm)
    assert irr_base > irr_smart > irr_maize

    # Soil health score: smart > baseline
    assert res_smart.soil_health_score > res_base.soil_health_score + 20.0


def test_phenology_double_hump_seasons_and_crop_history():
    from terraloop_engine.eo import phenology

    # Generate 5 years (2019-2023) of synthetic double-hump NDVI representing rice-wheat in Punjab
    idx = pd.date_range("2019-01-01", "2023-12-31", freq="8D")
    doy = idx.dayofyear.to_numpy()

    # Base NDVI ~0.20
    # Rabi hump: peak around DOY 60 (late Feb), width ~28 days, peak ~0.72
    rabi_hump = 0.52 * np.exp(-0.5 * ((doy - 60) / 28) ** 2)
    # Kharif hump: peak around DOY 240 (late Aug), width ~28 days, peak ~0.76
    kharif_hump = 0.56 * np.exp(-0.5 * ((doy - 240) / 28) ** 2)

    ndvi_raw = pd.Series(0.20 + rabi_hump + kharif_hump, index=idx)

    # 1. Smooth series (TASK-E01)
    smoothed = phenology.smooth(ndvi_raw)
    assert not smoothed.empty
    assert (smoothed >= 0.15).all()

    # 2. Detect seasons (TASK-E01: exactly 2 seasons/yr -> 10 seasons for 5 years)
    seasons = phenology.detect_seasons(smoothed)
    assert len(seasons) == 10, f"Expected 10 seasons (2/yr), found {len(seasons)}"

    # 3. Classify crop history (TASK-E02: rice + wheat for >= 4 of 5 years)
    inferred = phenology.infer_history(ndvi_raw, lat=30.2, lon=75.92)
    assert len(inferred) == 10

    rice_count = sum(1 for s in inferred if s.crop_group == "rice")
    wheat_count = sum(1 for s in inferred if s.crop_group == "wheat")
    assert rice_count >= 4, f"Expected >= 4 rice seasons, got {rice_count}"
    assert wheat_count >= 4, f"Expected >= 4 wheat seasons, got {wheat_count}"


def test_gee_sources_and_provenance():
    from terraloop_engine.data import gee

    # D03: IMERG daily series
    imerg = gee.imerg_daily(30.23, 75.84, "2020-01-01", "2020-12-31")
    assert not imerg.empty
    assert 400.0 <= imerg.sum() <= 950.0  # plausible Punjab rainfall
    assert gee.IMERG_PROVENANCE.doi is not None

    # D04: SMAP root-zone moisture
    smap = gee.smap_rootzone(30.23, 75.84, "2020-01-01", "2020-12-31")
    assert not smap.empty
    assert (smap >= 0.05).all() and (smap <= 0.50).all()
    assert gee.SMAP_PROVENANCE.doi is not None

    # D05: GRACE trend
    trend, lwe = gee.grace_trend(30.23, 75.84)
    assert trend < 0.0, f"Expected negative groundwater trend in Punjab, got {trend}"
    assert not lwe.empty
    assert gee.GRACE_PROVENANCE.doi is not None

    # D06: NASADEM slope
    slope_punjab = gee.slope_pct(30.23, 75.84)
    slope_iowa = gee.slope_pct(42.03, -93.63)
    assert slope_punjab < 2.0
    assert slope_iowa > slope_punjab
    assert gee.NASADEM_PROVENANCE.doi is not None

    # D07: FIRMS fire detections
    fires = gee.fire_detections(30.23, 75.84, "2019-01-01", "2023-12-31")
    assert not fires.empty
    fire_months = pd.to_datetime(fires["date"]).dt.month
    assert (fire_months.isin([10, 11])).any()
    assert gee.FIRMS_PROVENANCE.doi is not None

    # D08: HLS NDVI timeseries
    ndvi_df = gee.ndvi_timeseries(30.23, 75.84, "2023-01-01", "2023-12-31")
    assert len(ndvi_df) >= 40, f"Expected >= 40 observations per year, got {len(ndvi_df)}"
    assert gee.HLS_PROVENANCE.doi is not None


def test_profiler_with_gee_and_d11_safeguards(punjab_profile, monkeypatch):
    from datetime import date

    from terraloop_engine.data import nasa_power, soilgrids

    # Mock weather and soilgrids to use synthetic offline data
    synth_weather = synthetic_punjab_weather((1985, 2024))
    monkeypatch.setattr(nasa_power, "fetch_daily", lambda req: synth_weather)
    monkeypatch.setattr(
        soilgrids,
        "fetch_topsoil",
        lambda lat, lon: ({"sand": 45, "silt": 35, "clay": 20, "soc": 5, "phh2o": 8.0, "bdod": 150}, None),
    )

    geom = FieldGeometry(lat=30.23, lon=75.84, name="Sangrur Hero Field")
    profile = profiler.build_profile(geom, start=date(1985, 1, 1), end=date(2024, 12, 31))

    # Verify D04: SMAP 12 percentiles in 0-100
    assert profile.water.root_zone_moisture_percentile is not None
    assert len(profile.water.root_zone_moisture_percentile) == 12
    for p in profile.water.root_zone_moisture_percentile:
        assert 0.0 <= p <= 100.0

    # Verify D05: GRACE groundwater trend is negative
    assert profile.water.groundwater_trend_cm_per_year is not None
    assert profile.water.groundwater_trend_cm_per_year < 0.0

    # Verify D06: NASADEM slope < 2%
    assert profile.soil.slope_pct is not None
    assert profile.soil.slope_pct < 2.0

    # Verify D07: Residue burning detected
    assert profile.hazards.residue_burning_detected is True

    # Verify E02: Crop history shows rice & wheat
    assert len(profile.crop_history) >= 8
    assert profile.seasons_per_year == 2
    groups = [h.crop_group for h in profile.crop_history]
    assert "rice" in groups
    assert "wheat" in groups

    # Verify D11: Terminal heat days computed & no rainfall trend note > 30%
    assert profile.hazards.terminal_heat_days_per_year is not None
    for note in profile.agro_climatic_notes:
        if "Annual rainfall has" in note:
            # Check percentage in note is <= 30%
            import re
            m = re.search(r"(\d+)%", note)
            if m:
                pct = int(m.group(1))
                assert pct <= 30, f"Rainfall change note exceeded 30%: {note}"


def test_cmip6_scenario_set():
    from terraloop_engine.climate import ensembles

    w = synthetic_punjab_weather((1985, 2024))
    scenario_set, members = ensembles.build_scenario_set(
        kind="cmip6",
        power_df=w,
        ssp="ssp245",
        horizon="2050s",
        lat=30.2,
        lon=75.9,
    )
    assert scenario_set.kind == "cmip6"
    assert len(members) == 5  # 5 CMIP6 GCMs
    assert len(scenario_set.provenance) > 0
    assert "10.7917/OASIS/NEX-GDDP-CMIP6" in (scenario_set.provenance[0].doi or "")
    for m_df in members.values():
        assert "T2M_MAX" in m_df.columns
        assert "T2M_MIN" in m_df.columns
        assert "PRECTOTCORR" in m_df.columns
        assert len(m_df) > 365


def _make_sim_res(
    rot_id: str,
    irr: list[float],
    score: float,
    soc: float,
    p10: float,
    p50: float,
    p90: float,
    cvar: float,
) -> SimulationResult:
    return SimulationResult(
        rotation_id=rot_id,
        scenario_set_id="hist_1yr",
        yield_t_ha={"wheat": [4.5]},
        irrigation_mm=irr,
        profit_per_ha=[p50],
        soc_delta_t_ha_10yr=soc,
        erosion_t_ha_yr=2.0,
        n_balance_kg_ha_yr=15.0,
        living_root_days_pct=65.0,
        family_diversity_index=0.8,
        soil_health_score=score,
        profit_p10=p10,
        profit_p50=p50,
        profit_p90=p90,
        cvar_profit_10=cvar,
    )


def test_compute_resilience_and_regret():
    from terraloop_engine.optimize import evaluate

    res_good = _make_sim_res(
        rot_id="rice_dsr_mung_wheat",
        irr=[650.0, 700.0, 680.0],
        score=78.0,
        soc=1.5,
        p10=72000.0,
        p50=89000.0,
        p90=98000.0,
        cvar=69000.0,
    )

    res_stress = _make_sim_res(
        rot_id="rice_dsr_mung_wheat",
        irr=[780.0, 820.0, 800.0],
        score=78.0,
        soc=1.5,
        p10=62000.0,
        p50=79000.0,
        p90=88000.0,
        cvar=59000.0,
    )

    metrics = evaluate.compute_resilience_and_regret(res_good, res_stress)
    assert 10.0 <= metrics["climate_resilience_score"] <= 98.0
    assert metrics["profit_regret"] == 10000.0  # 89000 - 79000
    assert metrics["irrigation_spike_mm"] > 0.0


def test_grounded_llm_explain(punjab_profile):
    from terraloop_engine.explain import why_cards
    from terraloop_schemas import Rotation, RotationStep, StrategyRecommendation

    sim_res = _make_sim_res(
        rot_id="dsr_wheat",
        irr=[750.0],
        score=75.0,
        soc=1.2,
        p10=70000.0,
        p50=88000.0,
        p90=96000.0,
        cvar=67000.0,
    )

    rot = Rotation(
        id="dsr_wheat",
        label="DSR - Wheat",
        steps=[RotationStep(year_index=0, season_index=0, crop_id="rice_dsr")],
    )
    rec = StrategyRecommendation(
        rank=1,
        rotation=rot,
        results=[sim_res],
        objective_scores={"profit": 88000.0},
    )

    base_sim = _make_sim_res(
        rot_id="rice_puddled_wheat",
        irr=[1450.0],
        score=42.0,
        soc=-0.9,
        p10=60000.0,
        p50=82000.0,
        p90=92000.0,
        cvar=54000.0,
    )
    base_rec = StrategyRecommendation(
        rank=0,
        rotation=rot,
        results=[base_sim],
        objective_scores={"profit": 82000.0},
    )

    # Test English
    text_en = why_cards.grounded_llm_explain(punjab_profile, rec, base_rec, language="en")
    assert "AquaCrop" in text_en
    assert "GRACE" in text_en
    assert "RothC" in text_en
    assert "700 mm/yr" in text_en or "48%" in text_en  # 1450 - 750 = 700

    # Test Hindi
    text_hi = why_cards.grounded_llm_explain(punjab_profile, rec, base_rec, language="hi")
    assert "नासा GRACE" in text_hi
    assert "AquaCrop" in text_hi
    assert "RothC" in text_hi
    assert "75/100" in text_hi

    # Test Punjabi
    text_pa = why_cards.grounded_llm_explain(punjab_profile, rec, base_rec, language="pa")
    assert "ਨਾਸਾ GRACE" in text_pa
    assert "AquaCrop" in text_pa
    assert "RothC" in text_pa


def test_global_golden_fields_suitability_distinct():
    import json
    from pathlib import Path

    from terraloop_engine import crop_kb, suitability
    from terraloop_schemas import FieldProfile

    golden_dir = Path("data/golden")
    crops = crop_kb.load_crops()

    # Iowa
    iowa_prof = FieldProfile.model_validate(
        json.loads((golden_dir / "iowa" / "profile.json").read_text(encoding="utf-8"))
    )
    ranked_iowa = {r.crop_id: r.score for r in suitability.rank_crops(iowa_prof, crops)}
    assert ranked_iowa.get("maize", 0) > 0.25 or ranked_iowa.get("soybean", 0) > 0.25
    assert ranked_iowa.get("rice_puddled", 0) < 0.25

    # Machakos
    mach_prof = FieldProfile.model_validate(
        json.loads((golden_dir / "machakos" / "profile.json").read_text(encoding="utf-8"))
    )
    ranked_mach = {r.crop_id: r.score for r in suitability.rank_crops(mach_prof, crops)}
    assert ranked_mach.get("pigeonpea", 0) > 0.25 or ranked_mach.get("maize", 0) > 0.25
    assert ranked_mach.get("rice_puddled", 0) < 0.25


def test_nsga2_selection_3yr():
    from terraloop_engine.optimize import selection

    # 6 multi-year rotation candidates with trade-offs between profit, water, and soil
    cands = [
        {"profit": 110000.0, "water_savings": -1400.0, "soil_health": 45.0},  # high profit, high water
        {"profit": 95000.0, "water_savings": -900.0, "soil_health": 75.0},   # balanced / Pareto optimal
        {"profit": 80000.0, "water_savings": -600.0, "soil_health": 85.0},   # low water, high soil health
        {"profit": 60000.0, "water_savings": -1500.0, "soil_health": 35.0},  # strictly dominated
        {"profit": 92000.0, "water_savings": -880.0, "soil_health": 72.0},   # close alternative
        {"profit": 75000.0, "water_savings": -1200.0, "soil_health": 50.0},  # dominated
    ]

    fronts = selection.fast_non_dominated_sort(cands)
    assert len(fronts) >= 2
    # The first front contains non-dominated solutions
    assert 0 in fronts[0]
    assert 1 in fronts[0]
    assert 2 in fronts[0]
    assert 3 not in fronts[0]  # candidate 3 is dominated

    selected = selection.nsga2_select(cands, k=3)
    assert len(selected) == 3
    # Top 3 must include the primary Pareto points
    assert 0 in selected or 1 in selected


def test_polynomial_ridge_surrogate():
    from terraloop_engine.models import surrogate

    rng = np.random.default_rng(42)
    # Generate 150 synthetic AquaCrop runs: [clay_pct, sand_pct, annual_et0, annual_precip, gdd]
    n = 150
    clay = rng.uniform(10.0, 45.0, (n, 1))
    sand = rng.uniform(20.0, 70.0, (n, 1))
    et0 = rng.uniform(800.0, 1800.0, (n, 1))
    precip = rng.uniform(400.0, 1000.0, (n, 1))
    gdd = rng.uniform(1500.0, 3500.0, (n, 1))

    X = np.hstack([clay, sand, et0, precip, gdd])
    # Target: yield = non-linear function of moisture + soil + noise
    y = (
        2.5
        + 0.04 * clay.squeeze()
        + 0.002 * precip.squeeze()
        - 0.001 * et0.squeeze()
        + 0.000001 * (precip.squeeze() ** 2)
        + rng.normal(0, 0.05, n)
    )

    train_X, test_X = X[:100], X[100:]
    train_y, test_y = y[:100], y[100:]

    model = surrogate.train_crop_surrogate(train_X, train_y, degree=2, alpha=0.1)
    r2 = model.score(test_X, test_y)
    # AC: R² > 0.85 vs simulated held-out
    assert r2 > 0.85, f"Surrogate R² {r2:.3f} failed threshold > 0.85"


def test_phenology_crop_classifier():
    from terraloop_engine.eo import classifier

    clf = classifier.build_calibrated_phenology_classifier()
    assert len(clf.classes) == 4

    # Test test set
    test_features = np.array([
        [262, 184, 114, 0.77, 61.5],  # Kharif Rice
        [56, 334, 136, 0.81, 71.0],   # Rabi Wheat
        [228, 172, 94, 0.73, 49.5],   # Kharif Maize
        [136, 101, 66, 0.59, 31.0],   # Zaid Moong
    ])
    preds = clf.predict(test_features)
    assert preds == ["rice", "wheat", "maize", "mungbean"]

    # F1 evaluation
    eval_f1 = clf.evaluate_f1(["rice", "wheat", "maize", "mungbean"], preds)
    assert eval_f1["macro_f1"] >= 0.90


def test_california_central_valley_pipeline():
    """Verify dynamic behavior for California Central Valley (Fresno: 36.75 N, -119.80 W)."""
    from terraloop_engine import profiler, suitability
    from terraloop_engine.data import gee, nasa_power
    from terraloop_engine.models import economics
    from terraloop_engine.optimize import rotations

    # 1. Generate realistic weather for California coordinate
    weather_ca = nasa_power.synthetic_daily_weather(36.75, -119.80, years=(2015, 2024))
    climate_ca, hazards_ca, wb_ca = profiler.summarise_climate(weather_ca, 36.75)
    soil_ca = profiler.summarise_soil({"sand": 55, "silt": 30, "clay": 15, "soc": 9.5, "phh2o": 7.4, "bdod": 135})

    field_ca = FieldGeometry(lat=36.75, lon=-119.80, name="Fresno County, CA")
    region = economics.detect_region(field_ca.lat, field_ca.lon)
    curr_info = economics.get_currency_info(region)
    gw_trend, _ = gee.grace_trend(field_ca.lat, field_ca.lon)

    prof_ca = FieldProfile(
        field=field_ca,
        climate=climate_ca,
        water=WaterSummary(climatic_water_balance_mm=wb_ca, groundwater_trend_cm_per_year=gw_trend),
        soil=soil_ca,
        hazards=hazards_ca,
        currency=curr_info["code"],
        currency_symbol=curr_info["symbol"],
    )

    # 2. Check dynamic currency
    assert prof_ca.currency == "USD"
    assert prof_ca.currency_symbol == "$"

    # 3. Check GRACE groundwater depletion fallback for Central Valley (-2.8 cm/yr)
    assert prof_ca.water.groundwater_trend_cm_per_year == -2.8

    # 4. Check dynamic seasons for Mediterranean/California
    seasons_ca = rotations.derive_seasons(prof_ca)
    assert len(seasons_ca) == 3
    assert seasons_ca[0].name == "summer"
    assert seasons_ca[1].name == "winter"
    assert seasons_ca[2].name == "bridge"

    # 5. Check baseline rotation is maize > wheat (not hardcoded Punjab rice-wheat!)
    crops = crop_kb.load_crops()
    baseline = rotations.derive_baseline_rotation(prof_ca, crops)
    assert baseline.steps[0].crop_id == "maize"
    assert baseline.steps[1].crop_id == "wheat"
    assert not any(s.crop_id == "rice_puddled" for s in baseline.steps)

    # 6. Check suitability ranking runs cleanly
    ranks = suitability.rank_crops(prof_ca, crops, FarmConstraints())
    top_cids = [r.crop_id for r in ranks[:8]]
    assert "chickpea" in top_cids or "wheat" in top_cids or "barley" in top_cids


def test_southern_hemisphere_seasons():
    """Verify seasons and thermal phase invert correctly south of equator."""
    from terraloop_engine import profiler
    from terraloop_engine.data import nasa_power
    from terraloop_engine.optimize import rotations

    lat_sh = -34.5
    lon_sh = -58.5
    weather_sh = nasa_power.synthetic_daily_weather(lat_sh, lon_sh, years=(2015, 2024))
    c_sh, h_sh, wb_sh = profiler.summarise_climate(weather_sh, lat_sh)
    prof_sh = FieldProfile(
        field=FieldGeometry(lat=lat_sh, lon=lon_sh, name="Buenos Aires Pampas"),
        climate=c_sh,
        water=WaterSummary(climatic_water_balance_mm=wb_sh),
        soil=profiler.summarise_soil(None),
        hazards=h_sh,
    )
    seasons = rotations.derive_seasons(prof_sh)
    assert len(seasons) == 3
    assert seasons[0].name == "summer"
    assert seasons[1].name == "winter"
    assert seasons[2].name == "bridge"
    # Southern hemisphere summer starts in Nov-Jan
    assert 11 in seasons[0].sowing_months or 12 in seasons[0].sowing_months or 1 in seasons[0].sowing_months
    # Winter starts in May-Jun
    assert 5 in seasons[1].sowing_months or 6 in seasons[1].sowing_months


def test_east_africa_bimodal_seasons():
    """Verify bimodal rainfall seasons in equatorial East Africa."""
    from terraloop_engine import profiler
    from terraloop_engine.data import nasa_power
    from terraloop_engine.optimize import rotations

    lat_ea = -1.45
    lon_ea = 37.40
    weather_ea = nasa_power.synthetic_daily_weather(lat_ea, lon_ea, years=(2015, 2024))
    c_ea, h_ea, wb_ea = profiler.summarise_climate(weather_ea, lat_ea)
    prof_ea = FieldProfile(
        field=FieldGeometry(lat=lat_ea, lon=lon_ea, name="Machakos, Kenya"),
        climate=c_ea,
        water=WaterSummary(climatic_water_balance_mm=wb_ea),
        soil=profiler.summarise_soil(None),
        hazards=h_ea,
    )
    seasons = rotations.derive_seasons(prof_ea)
    assert len(seasons) == 2
    assert "long_rains" in seasons[0].name
    assert "short_rains" in seasons[1].name


def test_synthetic_weather_global_properties():
    """Verify physical consistency of global weather generator."""
    from terraloop_engine.data import nasa_power

    # California: Mediterranean (winter wet, summer dry)
    df_ca = nasa_power.synthetic_daily_weather(36.75, -119.80, years=(2020, 2022))
    assert not df_ca.isna().any().any()
    winter_rain = df_ca[df_ca.index.month.isin([12, 1, 2])]["PRECTOTCORR"].sum()
    summer_rain = df_ca[df_ca.index.month.isin([6, 7, 8])]["PRECTOTCORR"].sum()
    assert winter_rain > summer_rain

    # Punjab: Monsoon (summer wet, winter dry)
    df_pb = nasa_power.synthetic_daily_weather(30.2, 75.9, years=(2020, 2022))
    monsoon_rain = df_pb[df_pb.index.month.isin([7, 8, 9])]["PRECTOTCORR"].sum()
    winter_pb = df_pb[df_pb.index.month.isin([12, 1, 2])]["PRECTOTCORR"].sum()
    assert monsoon_rain > winter_pb








