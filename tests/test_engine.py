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


def test_gee_sources_and_provenance(monkeypatch):
    from terraloop_engine.data import gee

    monkeypatch.setenv("GEE_DISABLE", "1")

    # D03: IMERG daily series (offline regional climatology fallback)
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
    slope_bundelkhand = gee.slope_pct(25.45, 78.57)
    assert slope_punjab < 2.0
    assert slope_bundelkhand > slope_punjab
    assert gee.NASADEM_PROVENANCE.doi is not None

    # D07: FIRMS fire detections — offline mode returns empty DataFrame + mode="unknown" (never fabricates fires)
    fires = gee.fire_detections(30.23, 75.84, "2019-01-01", "2023-12-31")
    assert fires.empty
    assert gee.provenance_with_mode(gee.FIRMS_PROVENANCE, unknown_if_offline=True).mode == "unknown"
    assert gee.FIRMS_PROVENANCE.doi is not None

    # D08: HLS NDVI timeseries — offline mode returns empty DataFrame + mode="unknown" (never fabricates Gaussian NDVI)
    ndvi_df = gee.ndvi_timeseries(30.23, 75.84, "2023-01-01", "2023-12-31")
    assert ndvi_df.empty
    assert gee.provenance_with_mode(gee.HLS_PROVENANCE, unknown_if_offline=True).mode == "unknown"
    assert gee.HLS_PROVENANCE.doi is not None


def test_profiler_with_gee_and_d11_safeguards(punjab_profile, monkeypatch):
    from datetime import date

    from terraloop_engine.data import nasa_power, soilgrids

    monkeypatch.setenv("GEE_DISABLE", "1")
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

    # Verify D07 & E02: When GEE is offline, FIRMS burning and HLS crop history are honestly reported as unknown
    assert profile.hazards.residue_burning_detected is None
    assert any(p.mode == "unknown" for p in profile.hazards.provenance)
    assert profile.crop_history == []
    assert any(p.mode == "unknown" for p in profile.crop_history_provenance)
    assert profile.data_mode == "hybrid_regional"

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
    assert "FAO-56" in text_en
    assert "GRACE" in text_en
    assert "RothC" in text_en
    assert "700 mm/yr" in text_en or "48%" in text_en  # 1450 - 750 = 700

    # Test Hindi
    text_hi = why_cards.grounded_llm_explain(punjab_profile, rec, base_rec, language="hi")
    assert "नासा GRACE" in text_hi
    assert "FAO-56" in text_hi
    assert "RothC" in text_hi
    assert "75/100" in text_hi

    # Test Punjabi
    text_pa = why_cards.grounded_llm_explain(punjab_profile, rec, base_rec, language="pa")
    assert "ਨਾਸਾ GRACE" in text_pa
    assert "FAO-56" in text_pa
    assert "RothC" in text_pa


def test_indian_golden_fields_suitability_and_baselines_distinct():
    import json
    from pathlib import Path

    from terraloop_engine import crop_kb, suitability
    from terraloop_engine.optimize import rotations
    from terraloop_schemas import FieldProfile

    golden_dir = Path("data/golden")
    crops = crop_kb.load_crops()

    # 1. Sangrur (Central Punjab Alluvial Rice-Wheat)
    sangrur_prof = FieldProfile.model_validate(
        json.loads((golden_dir / "sangrur" / "profile.json").read_text(encoding="utf-8"))
    )
    base_sangrur = rotations.derive_baseline_rotation(sangrur_prof, crops)
    assert base_sangrur.steps[0].crop_id == "rice_puddled"
    assert base_sangrur.steps[1].crop_id == "wheat"

    # 2. Vidarbha (Rainfed Black Cotton Vertisol)
    vid_prof = FieldProfile.model_validate(
        json.loads((golden_dir / "vidarbha" / "profile.json").read_text(encoding="utf-8"))
    )
    ranked_vid = {r.crop_id: r.score for r in suitability.rank_crops(vid_prof, crops)}
    assert ranked_vid.get("cotton", 0) > 0.25 or ranked_vid.get("chickpea", 0) > 0.25 or ranked_vid.get("soybean", 0) > 0.25
    base_vid = rotations.derive_baseline_rotation(vid_prof, crops)
    assert base_vid.steps[0].crop_id in ("cotton", "soybean")

    # 3. Bundelkhand (Semi-Arid Rainfed Pulse-Oilseed Belt)
    bund_prof = FieldProfile.model_validate(
        json.loads((golden_dir / "bundelkhand" / "profile.json").read_text(encoding="utf-8"))
    )
    base_bund = rotations.derive_baseline_rotation(bund_prof, crops)
    assert base_bund.steps[0].crop_id in ("sorghum", "pearl_millet", "maize")


def test_nsga2_selection_3yr():
    from terraloop_engine.optimize import selection

    cands = [
        {"profit": 110000.0, "water_savings": -1400.0, "soil_health": 45.0},
        {"profit": 95000.0, "water_savings": -900.0, "soil_health": 75.0},
        {"profit": 80000.0, "water_savings": -600.0, "soil_health": 85.0},
        {"profit": 60000.0, "water_savings": -1500.0, "soil_health": 35.0},
        {"profit": 92000.0, "water_savings": -880.0, "soil_health": 72.0},
        {"profit": 75000.0, "water_savings": -1200.0, "soil_health": 50.0},
    ]

    fronts = selection.fast_non_dominated_sort(cands)
    assert len(fronts) >= 2
    assert 0 in fronts[0]
    assert 1 in fronts[0]
    assert 2 in fronts[0]
    assert 3 not in fronts[0]

    selected = selection.nsga2_select(cands, k=3)
    assert len(selected) == 3
    assert 0 in selected or 1 in selected


def test_polynomial_ridge_surrogate():
    from terraloop_engine.models import surrogate

    rng = np.random.default_rng(42)
    n = 150
    clay = rng.uniform(10.0, 45.0, (n, 1))
    sand = rng.uniform(20.0, 70.0, (n, 1))
    et0 = rng.uniform(800.0, 1800.0, (n, 1))
    precip = rng.uniform(400.0, 1000.0, (n, 1))
    gdd = rng.uniform(1500.0, 3500.0, (n, 1))

    X = np.hstack([clay, sand, et0, precip, gdd])
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
    assert r2 > 0.85, f"Surrogate R² {r2:.3f} failed threshold > 0.85"


def test_phenology_crop_classifier():
    from terraloop_engine.eo import classifier

    clf = classifier.build_calibrated_phenology_classifier()
    assert len(clf.classes) == 4

    test_features = np.array([
        [262, 184, 114, 0.77, 61.5],
        [56, 334, 136, 0.81, 71.0],
        [228, 172, 94, 0.73, 49.5],
        [136, 101, 66, 0.59, 31.0],
    ])
    preds = clf.predict(test_features)
    assert preds == ["rice", "wheat", "maize", "mungbean"]

    eval_f1 = clf.evaluate_f1(["rice", "wheat", "maize", "mungbean"], preds)
    assert eval_f1["macro_f1"] >= 0.90


def test_soil_texture_and_heatwave_sensitivity_in_simulation():
    """Verify that soil texture (sandy vs clay) and +5C heatwave anomalies physically alter yield & irrigation."""
    from terraloop_engine.models import aquacrop_runner, soil
    from terraloop_schemas import FarmConstraints, Rotation, RotationStep, SoilSummary

    w_normal = synthetic_punjab_weather((2018, 2020))
    w_hot = w_normal.copy()
    w_hot["T2M_MAX"] = w_hot["T2M_MAX"] + 5.0
    w_hot["T2M_MIN"] = w_hot["T2M_MIN"] + 5.0

    fc_sand, wp_sand = soil.saxton_rawls(78.0, 8.0, 3.5)
    sandy_soil = SoilSummary(
        texture_class="loamy sand",
        sand_pct=78.0,
        silt_pct=14.0,
        clay_pct=8.0,
        soc_g_per_kg=3.5,
        field_capacity_vol=fc_sand,
        wilting_point_vol=wp_sand,
    )

    fc_clay, wp_clay = soil.saxton_rawls(22.0, 48.0, 7.5)
    clay_soil = SoilSummary(
        texture_class="clay",
        sand_pct=22.0,
        silt_pct=30.0,
        clay_pct=48.0,
        soc_g_per_kg=7.5,
        field_capacity_vol=fc_clay,
        wilting_point_vol=wp_clay,
    )

    rot_wheat = Rotation(id="wheat_only", steps=[RotationStep(year_index=0, season_index=1, crop_id="wheat")])

    # 1. Soil texture sensitivity under rainfed / limited irrigation
    res_sand = aquacrop_runner.simulate_rotation(
        rot_wheat, w_normal, sandy_soil, FarmConstraints(irrigation="none"), start_year=2018
    )[0]
    res_clay = aquacrop_runner.simulate_rotation(
        rot_wheat, w_normal, clay_soil, FarmConstraints(irrigation="none"), start_year=2018
    )[0]
    assert res_clay["yield_t_ha"] > res_sand["yield_t_ha"]

    res_sand_irr = aquacrop_runner.simulate_rotation(
        rot_wheat, w_normal, sandy_soil, FarmConstraints(irrigation="full"), start_year=2018
    )[0]
    res_clay_irr = aquacrop_runner.simulate_rotation(
        rot_wheat, w_normal, clay_soil, FarmConstraints(irrigation="full"), start_year=2018
    )[0]
    assert res_sand_irr["irrigation_mm"] != res_clay_irr["irrigation_mm"]

    # 2. +5C heatwave reduces wheat yield by >= 10% (2022 March heatwave mechanism)
    res_hot = aquacrop_runner.simulate_rotation(
        rot_wheat, w_hot, clay_soil, FarmConstraints(irrigation="full"), start_year=2018
    )[0]
    yield_drop_pct = (res_clay_irr["yield_t_ha"] - res_hot["yield_t_ha"]) / res_clay_irr["yield_t_ha"] * 100.0
    assert yield_drop_pct >= 10.0, f"Expected >= 10% wheat yield drop under +5C heatwave, got {yield_drop_pct:.1f}%"

    # 3. DSR on coarse sand suffers seepage and iron/weed yield penalty compared to clay/loam
    rot_dsr = Rotation(id="dsr_only", steps=[RotationStep(year_index=0, season_index=0, crop_id="rice_dsr")])
    dsr_sand = aquacrop_runner.simulate_rotation(
        rot_dsr, w_normal, sandy_soil, FarmConstraints(irrigation="full"), start_year=2018
    )[0]
    dsr_clay = aquacrop_runner.simulate_rotation(
        rot_dsr, w_normal, clay_soil, FarmConstraints(irrigation="full"), start_year=2018
    )[0]
    assert dsr_sand["yield_t_ha"] < dsr_clay["yield_t_ha"]
    assert dsr_sand["irrigation_mm"] > dsr_clay["irrigation_mm"]


def test_soil_health_card_override_and_baseline_override(punjab_profile):
    from terraloop_schemas import SoilHealthCardInput

    shc = SoilHealthCardInput(ph=7.4, soc_pct=0.72, available_n_kg_ha=310.0)
    updated = profiler.apply_soil_health_card_override(punjab_profile.model_copy(deep=True), shc)
    assert updated.soil.ph == 7.4
    assert updated.soil.soc_g_per_kg == 7.2
    assert updated.soil.source == "farmer_test"
    assert any("Soil Health Card" in p.source for p in updated.soil.provenance)

    crops = crop_kb.load_crops()
    custom_base = rotations.derive_baseline_rotation(updated, crops, baseline_override=["maize", "wheat", "moong"])
    assert [s.crop_id for s in custom_base.steps] == ["maize", "wheat", "moong"]


def test_irrigated_sangrur_wheat_yield_and_march_heat_sanity():
    """Verify irrigated Sangrur wheat lands near the ~5.0 t/ha Punjab average after March Tmax bias correction."""
    import json
    from pathlib import Path

    from terraloop_engine.climate import ensembles
    from terraloop_engine.optimize import evaluate
    from terraloop_schemas import FarmConstraints, FieldProfile, Rotation, RotationStep

    golden = Path("data/golden/sangrur")
    prof = FieldProfile.model_validate_json((golden / "profile.json").read_text(encoding="utf-8"))
    raw_w = json.loads((golden / "weather.json").read_text(encoding="utf-8"))
    w_df = pd.DataFrame(raw_w["data"], index=pd.to_datetime(raw_w["index"]), columns=raw_w["columns"]).astype(float)

    # Verify March-April terminal heat days (Tmax > 32 C between Mar 1 and Apr 15) is bias-corrected (< 15 d/yr)
    assert prof.hazards.terminal_heat_days_per_year is not None
    assert prof.hazards.terminal_heat_days_per_year < 15.0

    # Verify irrigated Rabi wheat ensemble median yield is near the 5.0 t/ha state/district mean
    rot_wheat = Rotation(id="wheat_sanity", steps=[RotationStep(year_index=0, season_index=1, crop_id="wheat")])
    _, members = ensembles.build_scenario_set("historical", power_df=w_df, rotation_years=1)
    ev = evaluate.evaluate_rotation(rot_wheat, members, prof, FarmConstraints(irrigation="full"))
    med_wheat = float(np.median(ev.yield_t_ha["wheat"]))
    assert 4.7 <= med_wheat <= 5.4, f"Expected Sangrur irrigated wheat median in [4.7, 5.4] t/ha, got {med_wheat:.2f}"


def test_soil_health_breakdown_and_observed_golden_provenance():
    """Verify soil_health_breakdown components, MSP procurement ranking, and live observed GEE provenance in goldens."""
    import json
    from pathlib import Path

    from terraloop_schemas import FieldProfile, StrategyRecommendation

    sangrur_prof = FieldProfile.model_validate_json(
        Path("data/golden/sangrur/profile.json").read_text(encoding="utf-8")
    )
    assert sangrur_prof.data_mode == "observed"
    assert sangrur_prof.hazards.residue_burning_detected is True
    assert all(p.mode == "observed" for p in sangrur_prof.water.provenance)
    assert all(p.mode == "observed" for p in sangrur_prof.hazards.provenance)
    assert all(p.mode == "observed" for p in sangrur_prof.crop_history_provenance)

    recs_raw = json.loads(Path("data/golden/sangrur/recommendations.json").read_text(encoding="utf-8"))
    recs = [StrategyRecommendation.model_validate(r) for r in recs_raw]
    top_rec = recs[1]
    assert top_rec.data_mode == "observed"
    assert top_rec.practical_metrics is not None
    assert top_rec.practical_metrics.msp_assurance_level == "MSP Assured (FCI / State)"

    bd = top_rec.results[0].soil_health_breakdown
    for key in (
        "disturbance_minimization",
        "soil_armor_cover",
        "living_roots",
        "biodiversity",
        "biological_n_livestock",
        "soc_modifier",
        "erosion_modifier",
        "burning_penalty",
        "total_score",
    ):
        assert key in bd, f"Missing soil_health_breakdown key: {key}"
    assert bd["total_score"] == top_rec.results[0].soil_health_score


def test_igp_march_tmax_bias_correction_matches_imd_normal():
    """Verify that Indo-Gangetic bias correction on NASA POWER T2M_MAX matches the IMD 1981-2010 normal within 1.0 C.

    IMD Station 42099 (Ludhiana P.A.U.) Climatological Tables 1981-2010 reports March Mean Daily
    Maximum Temperature (Tmax) of 27.3 C. Raw MERRA-2 exhibits an un-irrigated warm bias (~31.8 to 32.3 C).
    After applying the -4.5 C offset, the March mean must fall within 1.0 C of the 27.3 C IMD normal.
    """
    from terraloop_engine.data import nasa_power

    # Test across 30-year synthetic climatology baseline for Ludhiana (30.82 N, 75.68 E)
    df_raw = nasa_power.synthetic_daily_weather(30.82, 75.68, (1981, 2010))
    raw_mar = float(df_raw[df_raw.index.month == 3]["T2M_MAX"].mean())
    assert raw_mar > 31.0, f"Expected uncorrected MERRA-2 warm bias > 31 C, got {raw_mar:.2f} C"

    df_cor = nasa_power.apply_igp_irrigation_bias_correction(df_raw, 30.82, 75.68)
    cor_mar = float(df_cor[df_cor.index.month == 3]["T2M_MAX"].mean())

    imd_ludhiana_normal = 27.3
    assert abs(cor_mar - imd_ludhiana_normal) <= 1.0, (
        f"Corrected March Tmax {cor_mar:.2f} C deviates from IMD normal {imd_ludhiana_normal} C by > 1.0 C"
    )


def test_benchmarks_doc_matches_live_engine_reproducibility():
    """Enforce that committed docs/BENCHMARKS.md matches live engine execution 100%."""
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "run_validation_benchmarks", root / "scripts" / "run_validation_benchmarks.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    generated = mod.run_benchmarks().strip()
    committed = (root / "docs" / "BENCHMARKS.md").read_text(encoding="utf-8").strip()
    assert generated == committed, "docs/BENCHMARKS.md is out of sync with scripts/run_validation_benchmarks.py"


def test_fao56_practices_passthrough_and_seasonal_operations_ledger(punjab_profile):
    """Verify fao56_runner preserves step practices into evaluate_rotation and builds seasonal_operations."""
    from terraloop_engine.models import aquacrop_runner
    from terraloop_engine.optimize import evaluate
    from terraloop_schemas import FarmConstraints, Rotation, RotationStep

    w_df = synthetic_punjab_weather((2019, 2021))
    rot_conv = Rotation(
        id="conv_rw",
        steps=[
            RotationStep(year_index=0, season_index=0, crop_id="rice_dsr", practices=["conventional"]),
            RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["conventional"]),
        ],
    )
    rot_zt = Rotation(
        id="zt_rw",
        steps=[
            RotationStep(
                year_index=0,
                season_index=0,
                crop_id="rice_dsr",
                practices=["direct_seeded", "residue_retained"],
            ),
            RotationStep(
                year_index=0,
                season_index=1,
                crop_id="wheat",
                practices=["happy_seeder", "zero_till", "residue_retained"],
            ),
        ],
    )

    sim_steps = aquacrop_runner.simulate_rotation(
        rot_zt, w_df, punjab_profile.soil, FarmConstraints(irrigation="full"), start_year=2020
    )
    assert sim_steps[0]["practices"] == ["direct_seeded", "residue_retained"]
    assert sim_steps[1]["practices"] == ["happy_seeder", "zero_till", "residue_retained"]

    res_conv = evaluate.evaluate_rotation(
        rot_conv, {"m1": w_df}, punjab_profile, FarmConstraints(irrigation="full")
    )
    res_zt = evaluate.evaluate_rotation(
        rot_zt, {"m1": w_df}, punjab_profile, FarmConstraints(irrigation="full")
    )
    # Direct-seeded + Happy Seeder zero-till saves tillage and transplanting labour costs -> higher net profit
    assert res_zt.profit_p50 > res_conv.profit_p50

    pm = evaluate.compute_practical_farmer_metrics(
        rot_zt, res_zt, res_conv, constraints=FarmConstraints(irrigation="full")
    )
    assert len(pm.seasonal_operations) == 2
    assert pm.seasonal_operations[0].crop_id == "rice_dsr"
    assert pm.seasonal_operations[0].irrigation_mm > 0
    assert "AWD" in pm.seasonal_operations[0].agronomic_guidance
    assert pm.seasonal_operations[1].crop_id == "wheat"
    assert "Happy Seeder" in pm.seasonal_operations[1].agronomic_guidance


def test_multiyear_rotations_and_cmip6_shock_recommend():
    """Verify multi-year alternating rotation generation (rotation_years=2) and /recommend CMIP6 + shock parameters."""
    from fastapi.testclient import TestClient
    from terraloop_api.main import app
    from terraloop_engine import crop_kb
    from terraloop_engine.optimize import rotations
    from terraloop_schemas import FarmConstraints

    crops = crop_kb.load_crops()
    subset = {k: crops[k] for k in ("rice_dsr", "maize", "wheat", "mustard", "moong")}
    rots_2yr = rotations.generate_rotations(subset, FarmConstraints(irrigation="full", rotation_years=2))
    assert len(rots_2yr) > 0
    assert any(max(s.year_index for s in r.steps) == 1 for r in rots_2yr)
    assert any("⇄" in (r.label or "") for r in rots_2yr)

    client = TestClient(app)
    resp = client.post(
        "/recommend",
        json={
            "field": {"lat": 30.19, "lon": 75.78, "name": "Sangrur, Punjab"},
            "constraints": {"irrigation": "full", "rotation_years": 1},
            "climate_scenario": "ssp245_2030s",
            "drought_shock_pct": 15.0,
            "price_shock_pct": -5.0,
            "fertilizer_shock_pct": 20.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    top = data[1]
    assert "cmip6_ssp245_2030s" in top["results"][0]["scenario_set_id"]
    assert "pareto_front" in top["objective_scores"]
    assert "crowding_distance" in top["objective_scores"]
    assert len(top["practical_metrics"]["seasonal_operations"]) == 3
    assert any("CMIP6" in p["source"] for p in top["provenance"])


def test_zaid_calendar_year_and_fallow_depletion_carryover(punjab_profile):
    """Verify Zaid (season_index=2) runs in year+1 and fallow steps preserve root-zone depletion."""
    from terraloop_engine.models import aquacrop_runner
    from terraloop_schemas import FarmConstraints, Rotation, RotationStep

    w_df = synthetic_punjab_weather((2019, 2021)).copy()
    # Make 2020 summer mild/wet and 2021 summer hot/dry so Zaid moong in year=2020 must sample 2021
    mask_2020 = (w_df.index.year == 2020) & (w_df.index.month.isin([4, 5, 6]))
    mask_2021 = (w_df.index.year == 2021) & (w_df.index.month.isin([4, 5, 6]))
    w_df.loc[mask_2020, "PRECTOTCORR"] = 12.0
    w_df.loc[mask_2021, "PRECTOTCORR"] = 0.0

    rot = Rotation(
        id="zaid_yr_test",
        steps=[
            RotationStep(year_index=0, season_index=0, crop_id="maize"),
            RotationStep(year_index=0, season_index=1, crop_id="wheat"),
            RotationStep(year_index=0, season_index=2, crop_id="moong"),
        ],
    )
    res = aquacrop_runner.simulate_rotation(
        rot, w_df, punjab_profile.soil, FarmConstraints(irrigation="full"), start_year=2020
    )
    # Because Zaid for agricultural year 2020-21 runs in Apr-Jun 2021 (0 mm rain), irrigation must be >= 100 mm
    assert res[2]["irrigation_mm"] >= 100.0

    # Verify fallow does not reset root-zone depletion to 0.0
    from terraloop_engine.models import fao56_runner

    _, carry_dep = fao56_runner._simulate_step(
        "fallow",
        [],
        1,
        2020,
        w_df,
        punjab_profile.soil,
        FarmConstraints(irrigation="none"),
        {},
        initial_depletion_mm=45.0,
    )
    assert carry_dep == 45.0


def test_cmip6_tail_quantile_mapping_and_multiyear_eval(punjab_profile):
    """Verify quantile_map preserves tail warming above historical max and evaluate_rotation samples CMIP6 years."""
    from terraloop_engine.climate import ensembles
    from terraloop_engine.optimize import evaluate
    from terraloop_schemas import FarmConstraints, Rotation, RotationStep

    obs = synthetic_punjab_weather((2015, 2019))
    mod_hist = obs.copy()
    mod_fut = obs.copy()
    mod_fut.index = pd.date_range("2031-01-01", periods=len(obs), freq="D")
    mod_fut["T2M_MAX"] = mod_fut["T2M_MAX"] + 4.0
    mod_fut["T2M_MIN"] = mod_fut["T2M_MIN"] + 4.0

    mapped_tmax = ensembles.quantile_map(obs["T2M_MAX"], mod_hist["T2M_MAX"], mod_fut["T2M_MAX"])
    assert float(mapped_tmax.max()) > float(obs["T2M_MAX"].max()) + 3.0

    rot = Rotation(
        id="cmip_eval",
        steps=[
            RotationStep(year_index=0, season_index=0, crop_id="maize"),
            RotationStep(year_index=0, season_index=1, crop_id="wheat"),
        ],
    )
    ev = evaluate.evaluate_rotation(rot, {"m_fut": mod_fut}, punjab_profile, FarmConstraints(irrigation="full"))
    assert len(ev.yield_t_ha["wheat"]) >= 1
    assert ev.yield_t_ha["wheat"][0] > 0.0


def test_rainfed_vidarbha_chickpea_suitability_and_shc_n_credit():
    """Verify rainfed Vidarbha ranks chickpea as top Rabi legume and Soil Health Card N credit updates urea savings."""
    from pathlib import Path

    from terraloop_engine import crop_kb, profiler, suitability
    from terraloop_engine.models import soil_health
    from terraloop_schemas import FarmConstraints, FieldProfile, SoilHealthCardInput

    vid_prof = FieldProfile.model_validate_json(
        Path("data/golden/vidarbha/profile.json").read_text(encoding="utf-8")
    )
    crops = crop_kb.load_crops()
    ranked = suitability.rank_crops(vid_prof, crops, FarmConstraints(irrigation="none"))
    top_ids = [r.crop_id for r in ranked[:12]]
    assert "chickpea" in top_ids, f"Expected chickpea in rainfed Vidarbha top crops, got {top_ids}"

    # Verify Soil Health Card available_n_kg_ha credits soil_health.n_balance
    shc_high_n = SoilHealthCardInput(ph=7.1, soc_pct=0.80, available_n_kg_ha=420.0)
    prof_n = profiler.apply_soil_health_card_override(vid_prof.model_copy(deep=True), shc_high_n)
    assert prof_n.soil.nitrogen_g_kg is not None and prof_n.soil.nitrogen_g_kg > 0.15

    nb_base = soil_health.n_balance(crops["wheat"], 4.5, soil_n_credit_kg_ha=0.0)["fertilizer_saved_kg_ha"]
    nb_credit = soil_health.n_balance(crops["wheat"], 4.5, soil_n_credit_kg_ha=35.0)["fertilizer_saved_kg_ha"]
    assert nb_credit == round(nb_base + 35.0, 1)


def test_agro_zone_and_regional_soil_classification():
    """Verify ICAR agro-climatic zone and topsoil fallback distinguish Rajasthan, Deccan, Himalayas, and Punjab."""
    from terraloop_engine import profiler
    from terraloop_engine.models import economics

    # Rajasthan / Thar Arid (25°43'19"N, 72°39'05"E)
    rj_zone = economics.detect_agro_zone(25.7219, 72.6514)
    assert "Western Dry" in rj_zone or "Rajasthan" in rj_zone
    rj_soil = profiler.regional_indian_soil_fallback(25.7219, 72.6514)
    assert rj_soil["sand"] >= 70.0

    # Punjab Trans-Gangetic
    pb_zone = economics.detect_agro_zone(30.19, 75.78)
    assert "Trans-Gangetic" in pb_zone

    # Vidarbha Deccan Vertisol
    mh_zone = economics.detect_agro_zone(20.93, 77.75)
    assert "Deccan" in mh_zone or "Vidarbha" in mh_zone
    mh_soil = profiler.regional_indian_soil_fallback(20.93, 77.75)
    assert mh_soil["clay"] >= 45.0



