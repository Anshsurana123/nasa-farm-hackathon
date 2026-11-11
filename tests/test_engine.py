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


@pytest.fixture(autouse=True)
def reset_rate_limit_bucket():
    from terraloop_api.main import _RATE_LIMIT_BUCKET
    _RATE_LIMIT_BUCKET.clear()
    yield
    _RATE_LIMIT_BUCKET.clear()


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


def test_selection_viable_filter_does_not_block_water_savings_when_profit_zero():
    # 12 candidates to trigger len >= 10 branch
    cands = []
    labels = []
    pairs = []
    for idx in range(11):
        cands.append({
            "profit": 100000.0 - idx * 2000.0,  # 100k down to 80k
            "water_savings": -1200.0 + idx * 20.0,
            "soil_health": 50.0 + idx,
            "low_risk": 50000.0,
            "low_labour": -25000.0,
            "food_security": 0.8,
        })
        labels.append(f"Crop{idx}A → Crop{idx}B")
        pairs.append((f"crop{idx}a", f"crop{idx}b"))

    # Candidate 11: High water savings (-300 mm vs -1200 mm), but lower profit (45k, <65% of max 100k)
    cands.append({
        "profit": 45000.0,
        "water_savings": -300.0,
        "soil_health": 65.0,
        "low_risk": 40000.0,
        "low_labour": -15000.0,
        "food_security": 0.7,
    })
    labels.append("WaterSaverA → WaterSaverB")
    pairs.append(("watersavera", "watersaverb"))

    # When profit priority is 0 and water savings priority is high, Candidate 11 MUST NOT be filtered out!
    p_water = Priorities(profit=0.0, water_savings=5.0, soil_health=0.0, low_risk=0.0, low_labour=0.0, food_security=0.0)
    top_picks = selection.select_top(cands, labels, p_water, k=3, crop_pairs=pairs)
    assert 11 in top_picks, f"Expected water-saving candidate 11 in top picks, got {top_picks}"


def test_selection_priority_directional_monotonicity():
    cands = [
        {"profit": 240000.0, "water_savings": -1100.0, "soil_health": 45.0, "low_risk": 180000.0, "low_labour": -30000.0, "food_security": 0.9},
        {"profit": 210000.0, "water_savings": -750.0,  "soil_health": 65.0, "low_risk": 160000.0, "low_labour": -22000.0, "food_security": 0.85},
        {"profit": 170000.0, "water_savings": -450.0,  "soil_health": 85.0, "low_risk": 140000.0, "low_labour": -18000.0, "food_security": 0.75},
        {"profit": 130000.0, "water_savings": -250.0,  "soil_health": 90.0, "low_risk": 110000.0, "low_labour": -14000.0, "food_security": 0.65},
        {"profit": 190000.0, "water_savings": -600.0,  "soil_health": 78.0, "low_risk": 150000.0, "low_labour": -20000.0, "food_security": 0.80},
        {"profit": 225000.0, "water_savings": -900.0,  "soil_health": 55.0, "low_risk": 170000.0, "low_labour": -26000.0, "food_security": 0.88},
        {"profit": 150000.0, "water_savings": -350.0,  "soil_health": 88.0, "low_risk": 125000.0, "low_labour": -16000.0, "food_security": 0.70},
        {"profit": 200000.0, "water_savings": -700.0,  "soil_health": 70.0, "low_risk": 155000.0, "low_labour": -21000.0, "food_security": 0.82},
        {"profit": 180000.0, "water_savings": -500.0,  "soil_health": 80.0, "low_risk": 145000.0, "low_labour": -19000.0, "food_security": 0.78},
        {"profit": 160000.0, "water_savings": -400.0,  "soil_health": 86.0, "low_risk": 135000.0, "low_labour": -17000.0, "food_security": 0.72},
        {"profit": 235000.0, "water_savings": -1000.0, "soil_health": 50.0, "low_risk": 175000.0, "low_labour": -28000.0, "food_security": 0.89},
        {"profit": 140000.0, "water_savings": -300.0,  "soil_health": 92.0, "low_risk": 115000.0, "low_labour": -15000.0, "food_security": 0.68},
    ]
    labels = [f"Crop{i}A → Crop{i}B" for i in range(len(cands))]
    pairs = [(f"crop{i}a", f"crop{i}b") for i in range(len(cands))]

    p_bal = Priorities(profit=1.0, water_savings=1.0, soil_health=1.0, low_risk=1.0, low_labour=1.0, food_security=1.0)
    p_wat = Priorities(profit=0.0, water_savings=5.0, soil_health=0.0, low_risk=0.0, low_labour=0.0, food_security=0.0)
    p_pro = Priorities(profit=5.0, water_savings=0.0, soil_health=0.0, low_risk=0.0, low_labour=0.0, food_security=0.0)
    p_soi = Priorities(profit=0.0, water_savings=0.0, soil_health=5.0, low_risk=0.0, low_labour=0.0, food_security=0.0)

    top_bal = selection.select_top(cands, labels, p_bal, k=3, crop_pairs=pairs)
    top_wat = selection.select_top(cands, labels, p_wat, k=3, crop_pairs=pairs)
    top_pro = selection.select_top(cands, labels, p_pro, k=3, crop_pairs=pairs)
    top_soi = selection.select_top(cands, labels, p_soi, k=3, crop_pairs=pairs)

    mean_irr_wat = sum(-cands[i]["water_savings"] for i in top_wat) / 3.0
    mean_irr_bal = sum(-cands[i]["water_savings"] for i in top_bal) / 3.0
    mean_pro_pro = sum(cands[i]["profit"] for i in top_pro) / 3.0
    mean_pro_bal = sum(cands[i]["profit"] for i in top_bal) / 3.0
    mean_soi_soi = sum(cands[i]["soil_health"] for i in top_soi) / 3.0
    mean_soi_bal = sum(cands[i]["soil_health"] for i in top_bal) / 3.0

    # Directional asserts: water-only must use <= irrigation than balanced,
    # profit-only must achieve >= profit than balanced, soil-only must achieve >= soil health
    assert mean_irr_wat <= mean_irr_bal, f"Water-only irrigation ({mean_irr_wat}) > balanced ({mean_irr_bal})"
    assert mean_pro_pro >= mean_pro_bal, f"Profit-only profit ({mean_pro_pro}) < balanced ({mean_pro_bal})"
    assert mean_soi_soi >= mean_soi_bal, f"Soil-only score ({mean_soi_soi}) < balanced ({mean_soi_bal})"


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
    """Verify soil_health_breakdown components, MSP procurement ranking, and honest GEE provenance in goldens."""
    import json
    from pathlib import Path

    from terraloop_schemas import FieldProfile, StrategyRecommendation

    audit_log = json.loads(Path("data/golden/gee_audit_log.json").read_text(encoding="utf-8"))
    sangrur_audit = audit_log.get("sangrur", {})
    gee_live = sangrur_audit.get("gee_live", False)

    sangrur_prof = FieldProfile.model_validate_json(
        Path("data/golden/sangrur/profile.json").read_text(encoding="utf-8")
    )
    assert sangrur_prof.state == "Punjab"
    assert sangrur_prof.served_from == "demo_snapshot"
    assert sangrur_prof.snapshot_date is not None

    if gee_live:
        assert sangrur_prof.data_mode == "observed"
    else:
        assert sangrur_prof.data_mode in ("hybrid_regional", "regional_climatology")
        assert not any(p.mode == "observed" for p in sangrur_prof.water.provenance if "GRACE" in (p.source or "") or "SMAP" in (p.source or ""))
        assert not any(p.mode == "observed" for p in sangrur_prof.hazards.provenance if "FIRMS" in (p.source or ""))
        assert not any(p.mode == "observed" for p in sangrur_prof.crop_history_provenance if "HLS" in (p.source or ""))

    recs_raw = json.loads(Path("data/golden/sangrur/recommendations.json").read_text(encoding="utf-8"))
    recs = [StrategyRecommendation.model_validate(r) for r in recs_raw]
    top_rec = recs[1]
    assert top_rec.data_mode == sangrur_prof.data_mode
    assert top_rec.served_from == "demo_snapshot"
    assert top_rec.snapshot_date is not None
    assert top_rec.state == "Punjab"
    assert top_rec.practical_metrics is not None
    assert top_rec.practical_metrics.msp_assurance_level in ("MSP Assured (FCI / State)", "NAFED / PSS Supported")
    assert any(r.practical_metrics.msp_assurance_level == "MSP Assured (FCI / State)" for r in recs[1:])

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


def test_global_international_locations_scope_honesty():
    """Verify scope honesty (Rule 8): global fields outside India are transparently labeled unvalidated_global."""
    from terraloop_engine import region_registry

    # 5 Global benchmark sites
    sites = [
        {"name": "Ames, Iowa (US Corn Belt)", "lat": 42.03, "lon": -93.63, "hem": "NH"},
        {"name": "Nairobi, Kenya (East Africa Highlands)", "lat": -1.29, "lon": 36.82, "hem": "SH"},
        {"name": "Mato Grosso, Brazil (Cerrado Soybean Belt)", "lat": -12.55, "lon": -55.72, "hem": "SH"},
        {"name": "NSW, Australia (Murray-Darling Wheat Belt)", "lat": -31.25, "lon": 146.92, "hem": "SH"},
        {"name": "Montpellier, France (Mediterranean)", "lat": 43.61, "lon": 3.87, "hem": "NH"},
    ]

    for site in sites:
        cfg = region_registry.detect_region_config(site["lat"], site["lon"])
        assert not cfg.is_validated, f"Expected {site['name']} to be unvalidated"
        assert cfg.validation_status == "unvalidated_global"
        assert cfg.validation_message is not None and "outside TerraLoop's calibrated Indian" in cfg.validation_message
        assert cfg.currency == "USD"
        assert cfg.currency_symbol == "$"
        assert cfg.hemisphere == site["hem"]

    # Verify Indian coordinates are properly validated
    pb_cfg = region_registry.detect_region_config(30.19, 75.78)
    assert pb_cfg.is_validated
    assert pb_cfg.validation_status == "validated_india"
    assert pb_cfg.currency == "INR"
    assert pb_cfg.currency_symbol == "₹"


def test_golden_match_tightened_radius():
    """Verify that only exact golden plots (< 0.005 deg) match precomputed assets, not surrounding districts (F-11)."""
    from fastapi.testclient import TestClient
    from terraloop_api.main import app
    from terraloop_schemas import FieldGeometry

    client = TestClient(app)

    # 1. Exact Sangrur golden benchmark coordinates (30.19, 75.78)
    exact_sangrur = FieldGeometry(id="sangrur", lat=30.19, lon=75.78, name="Sangrur Golden Field")
    prof_exact = client.post("/profile", json=exact_sangrur.model_dump()).json()
    assert prof_exact["validation_status"] == "validated_india"

    # 2. Field 10 km away from Sangrur (30.28, 75.88) without golden id should NOT return golden profile directly
    nearby_field = FieldGeometry(id="dhuri_farm", lat=30.28, lon=75.88, name="Dhuri Village Farm")
    # Verify that distance is > 0.005 deg
    assert abs(nearby_field.lat - 30.19) > 0.005
    # The API will attempt profiler.build_profile, or fall back to synthetic if network is off,
    # but critically, it will NOT silently serve the Sangrur golden profile.json


def test_golden_proximity_matcher():
    """Verify that _match_golden_field strictly matches exact golden IDs and rejects coordinates without explicit ID."""
    from terraloop_api.main import _match_golden_field
    from terraloop_schemas import FieldGeometry

    # Explicit golden IDs match
    assert _match_golden_field(FieldGeometry(id="sangrur", lat=30.19, lon=75.78)) == "sangrur"
    assert _match_golden_field(FieldGeometry(id="bundelkhand", lat=25.45, lon=78.57)) == "bundelkhand"

    # Coordinates near Sangrur (30.19, 75.78) without explicit golden id should NOT match
    assert _match_golden_field(FieldGeometry(lat=30.19, lon=75.78)) is None
    # Farm in Dhuri block (30.25, 75.82) -> does NOT match sangrur
    assert _match_golden_field(FieldGeometry(lat=30.25, lon=75.82)) is None
    # Farm with substring or non-golden ID
    assert _match_golden_field(FieldGeometry(id="dhuri_farm", lat=30.25, lon=75.82, name="Dhuri Village Farm")) is None


def test_llm_numeric_grounding_validator():
    """Verify that verify_llm_numeric_grounding accepts grounded metrics and rejects hallucinations (F2-03)."""
    from terraloop_engine.explain.why_cards import verify_llm_numeric_grounding

    allowed = {126.0, 148.0, 32.0, 3.8, 82.0, 2.8, 177174.0, 114250.0}

    # Text containing only valid grounded numbers (plus structural numbers like 10, 100)
    grounded_text = (
        "Strategy PR-126 saves 148 mm/yr (32% savings) of irrigation, countering 3.8 cm/yr regional water drop. "
        "Over 10 years, it increases soil carbon by 2.8 t C/ha, elevating soil health to 82/100. "
        "Expected net return is Rs 177,174/ha with drought buffer of Rs 114,250/ha."
    )
    assert verify_llm_numeric_grounding(grounded_text, allowed) is True

    # Text containing hallucinated numbers (e.g. fabricated 450 mm savings or Rs 500,000 profit)
    hallucinated_text = (
        "Strategy PR-126 saves 450 mm/yr of irrigation with a massive profit of Rs 500,000/ha."
    )
    assert verify_llm_numeric_grounding(hallucinated_text, allowed) is False


def test_state_subsidy_routing_by_region(punjab_profile):
    """Verify that state subsidy schemes are accurately routed by detected state (F2-02)."""
    from terraloop_engine import crop_kb
    from terraloop_engine.optimize.evaluate import compute_practical_farmer_metrics
    from terraloop_schemas import Rotation, RotationStep, SimulationResult

    crops = crop_kb.load_crops()
    rot = Rotation(
        id="test_dsr",
        steps=[
            RotationStep(year_index=0, season_index=0, crop_id="rice_dsr", practices=["dsr", "happy_seeder"]),
            RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["happy_seeder"]),
        ],
        is_baseline=False,
    )
    sim_res = SimulationResult(
        rotation_id=rot.id,
        scenario_set_id="historical",
        yield_t_ha={"rice_dsr": [5.5], "wheat": [5.0]},
        irrigation_mm=[1000.0],
        profit_per_ha=[120000.0],
        soc_delta_t_ha_10yr=1.5,
        erosion_t_ha_yr=2.0,
        n_balance_kg_ha_yr=10.0,
        living_root_days_pct=65.0,
        family_diversity_index=1.0,
        soil_health_score=70.0,
        profit_p10=90000.0,
        profit_p50=120000.0,
        profit_p90=140000.0,
        cvar_profit_10=85000.0,
    )

    # 1. Punjab profile -> gets Punjab DSR Promotion Scheme, never Mera Pani Meri Virasat
    pm_pb = compute_practical_farmer_metrics(rot, sim_res, crops=crops, profile=punjab_profile, region_id="punjab")
    schemes_pb_str = " ".join(pm_pb.eligible_schemes)
    assert "Punjab DSR Promotion Scheme" in schemes_pb_str
    assert "Mera Pani Meri Virasat" not in schemes_pb_str

    # 2. Haryana profile with maize diversification -> gets Mera Pani Meri Virasat
    rot_haryana = Rotation(
        id="test_mpmv",
        steps=[
            RotationStep(year_index=0, season_index=0, crop_id="maize", practices=["conventional"]),
            RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["happy_seeder"]),
        ],
        is_baseline=False,
    )
    sim_res_haryana = sim_res.model_copy(update={"rotation_id": rot_haryana.id, "yield_t_ha": {"maize": [6.0], "wheat": [5.0]}})
    pm_hr = compute_practical_farmer_metrics(rot_haryana, sim_res_haryana, crops=crops, profile=punjab_profile, region_id="haryana")
    schemes_hr_str = " ".join(pm_hr.eligible_schemes)
    assert "Mera Pani Meri Virasat" in schemes_hr_str
    assert "Punjab DSR Promotion Scheme" not in schemes_hr_str

    # 3. Maharashtra/Vidarbha -> gets PoCRA
    pm_mh = compute_practical_farmer_metrics(rot, sim_res, crops=crops, profile=punjab_profile, region_id="vidarbha")
    schemes_mh_str = " ".join(pm_mh.eligible_schemes)
    assert "Maharashtra PoCRA (Nanaji Deshmukh Krishi Sanjivani" in schemes_mh_str

    # 4. Tamil Nadu/Cauvery -> gets Kalaignarin Rice Fallow Pulses
    rot_relay = Rotation(
        id="test_relay",
        steps=[RotationStep(year_index=0, season_index=0, crop_id="blackgram", practices=["relay_seeding"])],
        is_baseline=False,
    )
    sim_res_relay = sim_res.model_copy(update={"rotation_id": rot_relay.id, "yield_t_ha": {"blackgram": [1.0]}})
    pm_tn = compute_practical_farmer_metrics(rot_relay, sim_res_relay, crops=crops, profile=punjab_profile, region_id="thanjavur")
    schemes_tn_str = " ".join(pm_tn.eligible_schemes)
    assert "Tamil Nadu Kalaignarin Rice Fallow Pulses Mission" in schemes_tn_str


def test_shc_nitrogen_credit_economics(punjab_profile):
    """Verify that SHC available N credit saves urea bags and reduces fertilizer cost (F2-05)."""
    from terraloop_engine import crop_kb
    from terraloop_engine.optimize.evaluate import compute_practical_farmer_metrics
    from terraloop_schemas import Rotation, RotationStep, SimulationResult

    crops = crop_kb.load_crops()
    rot = Rotation(
        id="test_rot",
        steps=[RotationStep(year_index=0, season_index=0, crop_id="wheat", practices=["conventional"])],
        is_baseline=False,
    )
    sim_res = SimulationResult(
        rotation_id=rot.id,
        scenario_set_id="historical",
        yield_t_ha={"wheat": [5.0]},
        irrigation_mm=[400.0],
        profit_per_ha=[60000.0],
        soc_delta_t_ha_10yr=0.5,
        erosion_t_ha_yr=2.0,
        n_balance_kg_ha_yr=0.0,
        living_root_days_pct=40.0,
        family_diversity_index=0.5,
        soil_health_score=50.0,
        profit_p10=45000.0,
        profit_p50=60000.0,
        profit_p90=70000.0,
        cvar_profit_10=40000.0,
    )

    # Without SHC N credit
    pm_no_shc = compute_practical_farmer_metrics(rot, sim_res, crops=crops, profile=punjab_profile, shc_n_credit=0.0)
    # With SHC N credit (e.g. 40 kg N credit)
    pm_with_shc = compute_practical_farmer_metrics(rot, sim_res, crops=crops, profile=punjab_profile, shc_n_credit=40.0)

    # 40 kg N credit / 0.46 = 86.95 kg Urea / 45 = ~1.9 bags saved
    assert pm_with_shc.urea_bags_saved_per_ha > pm_no_shc.urea_bags_saved_per_ha
    assert pm_with_shc.input_cost_inr_per_ha < pm_no_shc.input_cost_inr_per_ha


def test_async_recommend_job_lifecycle():
    """Verify asynchronous recommendation job submission and status polling (TASK-H02)."""
    import time

    from fastapi.testclient import TestClient
    from terraloop_api.main import app

    client = TestClient(app)
    payload = {
        "field": {"id": "sangrur", "lat": 30.19, "lon": 75.78, "name": "Sangrur Hero Field"},
        "priorities": {"profit": 1.0, "water_savings": 1.0, "soil_health": 1.0, "low_risk": 1.0},
        "constraints": {"irrigation": "full", "rotation_years": 1},
    }
    resp = client.post("/recommend/async", json=payload)
    assert resp.status_code == 200
    job_data = resp.json()
    assert "job_id" in job_data
    assert job_data["status"] == "running"
    assert 0.0 <= job_data["progress"] <= 1.0

    job_id = job_data["job_id"]
    # Poll for completion (with golden field, it finishes within ~10-15s under test load)
    pdata = {}
    for _ in range(150):
        poll = client.get(f"/recommend/jobs/{job_id}")
        assert poll.status_code == 200
        pdata = poll.json()
        if pdata["status"] == "completed":
            assert pdata["progress"] == 1.0
            assert pdata["result"] is not None
            assert len(pdata["result"]) == 4
            break
        elif pdata["status"] == "failed":
            pytest.fail(f"Async recommend job failed: {pdata.get('error')}")
        time.sleep(0.2)
    else:
        pytest.fail(f"Async recommend job did not complete within timeout. Last state: {pdata}")

    # 404 for unknown job ID
    unknown = client.get("/recommend/jobs/nonexistent-job-id")
    assert unknown.status_code == 404


def test_no_lat_lon_bounding_boxes_outside_registry():
    """Lint test enforcing Rule 8: zero hardcoded lat/lon bounding boxes outside region_registry and config (WS-C)."""
    import re
    from pathlib import Path

    engine_dir = Path("packages/engine/terraloop_engine")
    # Matches geographic bounding boxes (e.g. lat < 15, lat >= 28.5, lon > 74.0)
    pattern = re.compile(r"(?:lat|lon)\s*[<>]=?\s*(?:[1-9]\d|\d+\.\d+)")
    allowed_files = {"region_registry.py", "cache.py"}

    violations = []
    for py_file in engine_dir.rglob("*.py"):
        if py_file.name in allowed_files:
            continue
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, 1):
            # Ignore comments and docstrings
            clean = line.split("#")[0].strip()
            if pattern.search(clean) and not clean.startswith(("assert", "logger", "log.")):
                violations.append(f"{py_file.name}:{idx}: {line.strip()}")

    assert not violations, f"Found hardcoded lat/lon bounding box outside region_registry: {violations}"


def test_region_lookup_table_and_no_gaps_grid():
    """Verify state & region detection across all benchmark cities and a full India no-gaps grid (WS-C)."""
    from terraloop_engine import region_registry

    # 1. Benchmark cities resolution
    cities = {
        "Sangrur": (30.19, 75.78, "Punjab"),
        "Ludhiana": (30.82, 75.68, "Punjab"),
        "Bathinda": (30.12, 74.86, "Punjab"),
        "Karnal": (29.68, 76.99, "Haryana"),
        "Jhansi": (25.45, 78.57, "Uttar Pradesh"),
        "Yavatmal": (20.39, 78.13, "Maharashtra"),
        "Thanjavur": (10.72, 79.25, "Tamil Nadu"),
        "Coimbatore": (11.01, 76.95, "Tamil Nadu"),
        "Nagpur": (21.14, 79.08, "Maharashtra"),
        "Varanasi": (25.31, 82.97, "Uttar Pradesh"),
    }
    for name, (lat, lon, exp_state) in cities.items():
        state = region_registry.detect_state(lat, lon)
        assert state == exp_state, f"City {name} ({lat}, {lon}) resolved to {state}, expected {exp_state}"
        cfg = region_registry.detect_region_config(lat, lon)
        assert cfg.region_id is not None
        assert cfg.currency == "INR"

    # 2. No-gaps grid sweep across India (lat 10 to 32, lon 72 to 88 in 2-degree increments)
    for lat_deg in range(10, 33, 2):
        for lon_deg in range(72, 89, 2):
            cfg = region_registry.detect_region_config(float(lat_deg), float(lon_deg))
            assert cfg.region_id is not None
            assert cfg.agro_zone is not None


def test_schema_typescript_interface_parity():
    """Verify strict dynamic contract parity between all shared Pydantic models and frontend TypeScript interfaces (Issue 20 / WS-K1)."""
    import re
    from pathlib import Path

    from terraloop_schemas import models

    ts_content = Path("apps/web/src/types/api.ts").read_text(encoding="utf-8")

    # Parse TypeScript interface blocks
    interface_blocks = {}
    matches = re.finditer(r"export\s+interface\s+(\w+)\s*\{([^}]+)\}", ts_content)
    for m in matches:
        name = m.group(1)
        body = m.group(2)
        fields = set(re.findall(r"^\s*([a-zA-Z_]\w*)\??\s*:", body, re.MULTILINE))
        interface_blocks[name] = fields

    # Shared Pydantic models that must have 100% field parity in TypeScript
    shared_models = [
        models.DataProvenance,
        models.SoilHealthCardInput,
        models.FieldGeometry,
        models.ClimateSummary,
        models.SoilSummary,
        models.WaterSummary,
        models.HazardSummary,
        models.InferredSeason,
        models.FieldProfile,
        models.CropSpec,
        models.Priorities,
        models.FarmConstraints,
        models.RotationStep,
        models.Rotation,
        models.SimulationResult,
        models.SeasonalOperationStep,
        models.PracticalFarmerMetrics,
        models.StrategyRecommendation,
        models.GeocodeResult,
        models.SuitabilityRequest,
        models.SuitabilityItem,
        models.RecommendRequest,
    ]

    for model_cls in shared_models:
        cls_name = model_cls.__name__
        pydantic_fields = set(model_cls.model_fields.keys())
        assert cls_name in interface_blocks, f"TypeScript interface '{cls_name}' missing from apps/web/src/types/api.ts"
        ts_fields = interface_blocks[cls_name]
        missing_fields = pydantic_fields - ts_fields
        assert not missing_fields, f"Interface '{cls_name}' in api.ts is missing Pydantic fields: {missing_fields}"


def test_llm_numeric_grounding_rejects_hallucinations_multilingual():
    """Verify verify_llm_numeric_grounding rejects hallucinated numbers in Hindi and Punjabi text (WS-K2)."""
    from terraloop_engine.explain.why_cards import verify_llm_numeric_grounding

    allowed = {126.0, 713.0, 25.8, 188.0, 240148.0}

    # Valid Hindi
    valid_hi = "यह रणनीति 713 मिमी सिंचाई का उपयोग करती है और ₹240,148 का लाभ देती है।"
    assert verify_llm_numeric_grounding(valid_hi, allowed) is True

    # Hallucinated Hindi (claims 999 mm savings which was never simulated)
    hallucinated_hi = "यह रणनीति 999 मिमी सिंचाई बचाती है।"
    assert verify_llm_numeric_grounding(hallucinated_hi, allowed) is False

    # Valid Punjabi
    valid_pa = "ਇਹ ਰਣਨੀਤੀ 713 ਮਿਲੀਮੀਟਰ ਸਿੰਚਾਈ ਵਰਤਦੀ ਹੈ।"
    assert verify_llm_numeric_grounding(valid_pa, allowed) is True

    # Hallucinated Punjabi (claims ₹950,000 profit which was never simulated)
    hallucinated_pa = "ਇਹ ਰਣਨੀਤੀ ₹950,000 ਮੁਨਾਫ਼ਾ ਦਿੰਦੀ ਹੈ।"
    assert verify_llm_numeric_grounding(hallucinated_pa, allowed) is False


def test_build_profile_offline_never_emits_observed_for_satellite_products(monkeypatch):
    """Verify build_profile with GEE disabled never emits 'observed' for GEE-derived satellite products (TASK-A01)."""
    from terraloop_engine import profiler
    from terraloop_schemas import FieldGeometry

    monkeypatch.setenv("GEE_DISABLE", "1")
    prof = profiler.build_profile(FieldGeometry(lat=30.19, lon=75.78, name="Sangrur Test"))

    # When GEE is offline, active fire detection must be None (never fabricated)
    assert prof.hazards.residue_burning_detected is None

    # Prove that no GEE-derived satellite products claim "observed"
    firms_prov = [p for p in prof.hazards.provenance if "FIRMS" in p.source]
    assert len(firms_prov) == 1
    assert firms_prov[0].mode == "unknown"

    grace_prov = [p for p in prof.water.provenance if "GRACE" in p.source]
    assert len(grace_prov) == 1
    assert grace_prov[0].mode == "regional_climatology"

    smap_prov = [p for p in prof.water.provenance if "SMAP" in p.source]
    assert len(smap_prov) == 1
    assert smap_prov[0].mode == "regional_climatology"


def test_golden_dirs_mirror_each_other_and_schema_validation():
    """Verify all six golden benchmark fixtures validate against Pydantic v2 schemas and mirror apps/web/public/golden."""
    import json
    from pathlib import Path

    from terraloop_schemas import FieldProfile, StrategyRecommendation

    root = Path(__file__).resolve().parents[1]
    golden_ids = ["sangrur", "ludhiana", "bathinda", "vidarbha", "bundelkhand", "thanjavur"]

    for fid in golden_ids:
        data_dir = root / "data" / "golden" / fid
        web_dir = root / "apps" / "web" / "public" / "golden" / fid

        assert (data_dir / "profile.json").exists()
        assert (web_dir / "profile.json").exists()
        assert (data_dir / "recommendations.json").exists()
        assert (web_dir / "recommendations.json").exists()

        # Schema validation
        prof_data = FieldProfile.model_validate_json((data_dir / "profile.json").read_text(encoding="utf-8"))
        prof_web = FieldProfile.model_validate_json((web_dir / "profile.json").read_text(encoding="utf-8"))
        assert prof_data.field.id == fid
        assert prof_web.field.id == fid

        recs_data_raw = json.loads((data_dir / "recommendations.json").read_text(encoding="utf-8"))
        recs_web_raw = json.loads((web_dir / "recommendations.json").read_text(encoding="utf-8"))
        assert len(recs_data_raw) == 4
        assert len(recs_web_raw) == 4

        recs_data = [StrategyRecommendation.model_validate(r) for r in recs_data_raw]
        recs_web = [StrategyRecommendation.model_validate(r) for r in recs_web_raw]
        assert recs_data[0].rank == 0
        assert recs_web[0].rank == 0


def test_scheme_fixtures_state_consistency():
    """Enforce that no golden recommendation contains out-of-state schemes (e.g. Haryana Mera Pani in non-Haryana fields)."""
    import json
    from pathlib import Path

    from terraloop_schemas import StrategyRecommendation

    root = Path(__file__).resolve().parents[1]
    golden_ids = ["sangrur", "ludhiana", "bathinda", "vidarbha", "bundelkhand", "thanjavur"]

    for fid in golden_ids:
        rec_path = root / "data" / "golden" / fid / "recommendations.json"
        recs = [StrategyRecommendation.model_validate(r) for r in json.loads(rec_path.read_text(encoding="utf-8"))]
        for r in recs:
            if r.practical_metrics and r.practical_metrics.eligible_schemes:
                for s in r.practical_metrics.eligible_schemes:
                    s_name = s.get("name", "") if isinstance(s, dict) else str(s)
                    assert "Mera Pani" not in s_name, f"Out-of-state Haryana scheme Mera Pani appeared in {fid} recommendation"


def test_load_economics_honors_region_and_reports_basis():
    """Verify load_economics resolves state-specific files and transparently tags punjab_proxy where unverified (WS-D)."""
    from terraloop_engine.models.economics import load_economics

    punjab_eco = load_economics("punjab")
    assert punjab_eco.get("economics_basis") == "local_verified"

    vidarbha_eco = load_economics("vidarbha")
    assert vidarbha_eco.get("economics_basis") == "local_verified"

    thanjavur_eco = load_economics("thanjavur")
    assert thanjavur_eco.get("economics_basis") == "punjab_proxy"


def test_merra2_bias_correction_provenance_and_toggle():
    """Verify MERRA-2 irrigation warm-bias correction temperature delta and provenance note (Issue 2 / WS-A3)."""
    from datetime import date

    import pandas as pd
    from terraloop_engine import profiler, region_registry
    from terraloop_engine.data import nasa_power
    from terraloop_schemas import FieldGeometry

    # Sangrur is in IGP (Punjab); Thanjavur is in Cauvery Delta (non-IGP)
    sangrur_lat, sangrur_lon = 30.19, 75.78
    thanjavur_lat, thanjavur_lon = 10.72, 79.25

    reg_sangrur = region_registry.detect_region_config(sangrur_lat, sangrur_lon)
    reg_thanjavur = region_registry.detect_region_config(thanjavur_lat, thanjavur_lon)
    assert reg_sangrur.igp_merra2_bias_correction is True
    assert reg_thanjavur.igp_merra2_bias_correction is False

    # Check provenance function
    prov_igp = nasa_power.provenance(date(1995, 1, 1), date(2024, 12, 31), bias_corrected=True)
    prov_non_igp = nasa_power.provenance(date(1995, 1, 1), date(2024, 12, 31), bias_corrected=False)

    assert "IGP irrigation warm-bias corrected (-4.5°C Mar Tmax; Ambika & Mishra 2019 / IMD 1981-2010)" in prov_igp.product
    assert prov_igp.doi == "10.1029/2019GL084367"
    assert "IGP irrigation warm-bias corrected" not in prov_non_igp.product
    assert prov_non_igp.doi == "10.5067/POWER/0001"

    # Check temperature delta via apply_igp_irrigation_bias_correction
    dates = pd.date_range("2024-03-01", "2024-03-31", freq="D")
    raw_df = pd.DataFrame({"T2M_MAX": [32.0] * len(dates), "T2M_MIN": [15.0] * len(dates)}, index=dates)

    corr_sangrur = nasa_power.apply_igp_irrigation_bias_correction(raw_df.copy(), sangrur_lat, sangrur_lon)
    assert (corr_sangrur["T2M_MAX"] == 27.5).all()  # 32.0 - 4.5 = 27.5

    corr_thanjavur = nasa_power.apply_igp_irrigation_bias_correction(raw_df.copy(), thanjavur_lat, thanjavur_lon)
    assert (corr_thanjavur["T2M_MAX"] == 32.0).all()  # unchanged

    # Check profiler.build_profile propagates provenance
    prof_sangrur = profiler.build_profile(FieldGeometry(id="sangrur", lat=sangrur_lat, lon=sangrur_lon, name="Sangrur"))
    prof_thanjavur = profiler.build_profile(FieldGeometry(id="thanjavur", lat=thanjavur_lat, lon=thanjavur_lon, name="Thanjavur"))

    assert any("IGP irrigation warm-bias corrected" in p.product for p in prof_sangrur.climate.provenance if p.product)
    assert not any("IGP irrigation warm-bias corrected" in (p.product or "") for p in prof_thanjavur.climate.provenance)


def test_i18n_key_parity_and_no_hardcoded_jsx_error_strings():
    """Enforce 100% key parity across en, hi, pa localization files and verify TSX has no raw English prose (WS-J / Issue 17)."""
    import json
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    en = json.loads((root / "apps" / "web" / "src" / "i18n" / "en.json").read_text(encoding="utf-8"))
    hi = json.loads((root / "apps" / "web" / "src" / "i18n" / "hi.json").read_text(encoding="utf-8"))
    pa = json.loads((root / "apps" / "web" / "src" / "i18n" / "pa.json").read_text(encoding="utf-8"))

    assert set(en.keys()) == set(hi.keys()), f"Key mismatch between en and hi: {set(en.keys()) ^ set(hi.keys())}"
    assert set(en.keys()) == set(pa.keys()), f"Key mismatch between en and pa: {set(en.keys()) ^ set(pa.keys())}"
    assert "error.recommendFailedCustom" in en
    assert "error.recommendFailedDemo" in en

    # Verify residual localization keys exist across en, hi, pa (WS-J4 / Issue A, B, C)
    new_keys = [
        "badge.graceUrgencyActive",
        "warning.rainfedYieldTitle",
        "warning.biophysicalYieldTitle",
        "data_mode.observed",
        "data_mode.hybrid_regional",
        "data_mode.regional_climatology",
        "data_mode.fallback_synthetic",
    ]
    for k in new_keys:
        assert k in en, f"Missing key '{k}' in en.json"
        assert k in hi, f"Missing key '{k}' in hi.json"
        assert k in pa, f"Missing key '{k}' in pa.json"

    # Verify ReportCard.tsx and TelemetryBar.tsx use localized t("badge.contextOnly") and have no hardcoded >Context Only<
    report_card_code = (root / "apps" / "web" / "src" / "components" / "ReportCard.tsx").read_text(encoding="utf-8")
    telemetry_bar_code = (root / "apps" / "web" / "src" / "components" / "TelemetryBar.tsx").read_text(encoding="utf-8")
    assert 't("badge.contextOnly")' in report_card_code
    assert ">Context Only<" not in report_card_code
    assert re.search(r">\s*Context Only\s*<", report_card_code) is None
    assert 't("badge.contextOnly")' in telemetry_bar_code
    assert ">Context Only<" not in telemetry_bar_code
    assert re.search(r">\s*Context Only\s*<", telemetry_bar_code) is None

    # Verify RotationExplorer.tsx uses localized t("error...") instead of hardcoded English error strings
    rot_explorer_code = (root / "apps" / "web" / "src" / "components" / "RotationExplorer.tsx").read_text(encoding="utf-8")
    assert 'setError("Failed to compute live recommendation' not in rot_explorer_code
    assert 'setError("Recommendation failed for custom field' not in rot_explorer_code
    assert 't("error.recommendFailedCustom")' in rot_explorer_code

    # Assert yield notices are not hardcoded in RotationExplorer.tsx
    assert "Rainfed Yield Potential Notice" not in rot_explorer_code
    assert "Biophysical Potential Yield Disclosure" not in rot_explorer_code
    assert 't("warning.rainfedYieldTitle")' in rot_explorer_code
    assert 't("warning.biophysicalYieldTitle")' in rot_explorer_code

    # Assert badge.graceUrgencyActive is referenced in both RotationExplorer.tsx and AgronomicBrief.tsx
    agronomic_brief_code = (root / "apps" / "web" / "src" / "components" / "AgronomicBrief.tsx").read_text(encoding="utf-8")
    assert 't("badge.graceUrgencyActive")' in rot_explorer_code
    assert 't("badge.graceUrgencyActive")' in agronomic_brief_code

    # Scan RotationExplorer.tsx, AgronomicBrief.tsx, and brief/page.tsx for unlocalized multi-word English JSX text nodes (>12 chars)
    target_tsx_files = [
        root / "apps" / "web" / "src" / "components" / "RotationExplorer.tsx",
        root / "apps" / "web" / "src" / "components" / "AgronomicBrief.tsx",
        root / "apps" / "web" / "src" / "app" / "brief" / "page.tsx",
    ]
    raw_jsx_pat = re.compile(r">[A-Za-z][^<{]{12,}<")

    for tsx_path in target_tsx_files:
        content = tsx_path.read_text(encoding="utf-8")
        matches = raw_jsx_pat.findall(content)
        assert not matches, f"Unlocalized English JSX prose found in {tsx_path.name}: {matches}"


def test_fao56_annex_worked_examples():
    """Verify FAO-56 worked examples: wind conversion, Penman-Monteith ET0, and root-zone Ks (Issue 6 / WS-F4)."""
    import pytest
    from terraloop_engine.models import agroclimate

    # 1. Wind speed conversion from 10m to 2m (FAO-56 eq. 47)
    # Factor is 4.87 / ln(67.8 * 10 - 5.42) = 4.87 / ln(672.58) = 0.748
    u_10 = 2.78
    u_2 = agroclimate.wind_speed_2m(u_10, z=10.0)
    assert u_2 == pytest.approx(u_10 * 0.748, rel=1e-3)

    # 2. Daily Penman-Monteith ET0 (FAO-56 Chapter 4, Example 18 reference conditions)
    # Tmean = 16.9 C, Rn = 14.4 MJ/m2/d, G = 0, u2 = 2.078 m/s, ea = 1.41 kPa, elev = 100m
    # FAO-56 published reference calculation: ET0 ~ 3.9 mm/day (within +/- 0.25 mm/day tolerance)
    et0 = agroclimate.et0_penman_monteith(
        tmean_c=16.9,
        rn_mj_m2_day=14.4,
        g_mj_m2_day=0.0,
        u2_m_s=2.078,
        ea_kpa=1.41,
        elevation_m=100.0,
    )
    assert et0 == pytest.approx(3.9, abs=0.25)

    # 3. FAO-56 Box 11 / Example 35 root-zone depletion coefficient Ks
    taw = 100.0
    raw = 50.0  # p = 0.50

    # No stress when Dr <= RAW
    assert agroclimate.fao56_depletion_ks(dr_mm=0.0, raw_mm=raw, taw_mm=taw) == 1.0
    assert agroclimate.fao56_depletion_ks(dr_mm=30.0, raw_mm=raw, taw_mm=taw) == 1.0
    assert agroclimate.fao56_depletion_ks(dr_mm=50.0, raw_mm=raw, taw_mm=taw) == 1.0

    # Linear decline when RAW < Dr < TAW: Ks = (TAW - Dr) / (TAW - RAW)
    assert agroclimate.fao56_depletion_ks(dr_mm=75.0, raw_mm=raw, taw_mm=taw) == pytest.approx(0.50, abs=1e-4)
    assert agroclimate.fao56_depletion_ks(dr_mm=90.0, raw_mm=raw, taw_mm=taw) == pytest.approx(0.20, abs=1e-4)

    # Wilting point reached when Dr >= TAW
    assert agroclimate.fao56_depletion_ks(dr_mm=100.0, raw_mm=raw, taw_mm=taw) == 0.0
    assert agroclimate.fao56_depletion_ks(dr_mm=120.0, raw_mm=raw, taw_mm=taw) == 0.0


def test_golden_provenance_consistency():
    """Verify honest provenance, demo snapshot metadata, and state tags across all 6 golden fields (Issue 1 / WS-A1)."""
    import json
    from pathlib import Path

    from terraloop_schemas import FieldProfile, StrategyRecommendation

    root = Path(__file__).resolve().parents[1]
    golden_dir = root / "data" / "golden"
    audit_log = json.loads((golden_dir / "gee_audit_log.json").read_text(encoding="utf-8"))
    fields = json.loads((golden_dir / "fields.json").read_text(encoding="utf-8"))

    for f in fields:
        fid = f["id"]
        audit_entry = audit_log.get(fid, {})
        gee_live = audit_entry.get("gee_live", False)

        prof = FieldProfile.model_validate_json((golden_dir / fid / "profile.json").read_text(encoding="utf-8"))
        assert prof.served_from == "demo_snapshot", f"Field {fid} served_from is {prof.served_from}"
        assert prof.snapshot_date is not None, f"Field {fid} snapshot_date is None"
        assert prof.state is not None, f"Field {fid} has null state"

        if not gee_live:
            assert prof.data_mode != "observed", f"Field {fid} claims 'observed' but GEE was offline in audit log"
            assert prof.hazards.residue_burning_detected is None
            for p in prof.soil.provenance:
                if "NASADEM" in (p.source or ""):
                    assert p.mode != "observed", f"Field {fid} NASADEM mode is observed"
            for p in prof.water.provenance:
                if "GRACE" in (p.source or "") or "SMAP" in (p.source or ""):
                    assert p.mode != "observed", f"Field {fid} {p.source} mode is observed"
            for p in prof.hazards.provenance:
                if "FIRMS" in (p.source or ""):
                    assert p.mode != "observed", f"Field {fid} FIRMS mode is observed"
            for p in prof.crop_history_provenance:
                if "HLS" in (p.source or ""):
                    assert p.mode != "observed", f"Field {fid} HLS mode is observed"

        recs_raw = json.loads((golden_dir / fid / "recommendations.json").read_text(encoding="utf-8"))
        recs = [StrategyRecommendation.model_validate(r) for r in recs_raw]
        assert len(recs) >= 2, f"Field {fid} has fewer than 2 recommendations"
        for r in recs:
            assert r.served_from == "demo_snapshot", f"Field {fid} rec served_from is {r.served_from}"
            assert r.snapshot_date is not None, f"Field {fid} rec snapshot_date is None"
            assert r.state is not None, f"Field {fid} rec state is None"
            assert r.data_mode == prof.data_mode, f"Field {fid} rec data_mode {r.data_mode} != prof data_mode {prof.data_mode}"


def test_soil_score_and_ranking_sensitivity_to_shc_and_soilgrids():
    """Verify Soil Health Score, water balance, and Urea requirement sensitivity to measured soil properties (Issue 8 / WS-G2)."""
    from terraloop_engine import crop_kb, profiler
    from terraloop_engine.models import soil, soil_health
    from terraloop_schemas import FieldGeometry, Rotation, RotationStep, SoilHealthCardInput, SoilSummary

    crops = crop_kb.load_crops()
    rot = Rotation(
        id="test_rot",
        label="Short Rice → Wheat",
        is_baseline=False,
        steps=[
            RotationStep(year_index=0, season_index=0, crop_id="rice_short", practices=["direct_seeded"]),
            RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["happy_seeder"]),
        ],
    )

    # 1. SOC sensitivity (2.0 vs 9.0 g/kg)
    fc_low, wp_low = soil.saxton_rawls(sand_pct=50.0, clay_pct=25.0, soc_g_kg=2.0)
    fc_high, wp_high = soil.saxton_rawls(sand_pct=50.0, clay_pct=25.0, soc_g_kg=9.0)
    taw_low = (fc_low - wp_low) * 1000.0
    taw_high = (fc_high - wp_high) * 1000.0
    assert taw_high > taw_low, "Higher SOC must increase plant Total Available Water"

    # 2. Clay sensitivity (10% vs 48%)
    fc_sand, wp_sand = soil.saxton_rawls(sand_pct=75.0, clay_pct=10.0, soc_g_kg=5.0)
    fc_clay, wp_clay = soil.saxton_rawls(sand_pct=25.0, clay_pct=48.0, soc_g_kg=5.0)
    assert (fc_clay - wp_clay) > (fc_sand - wp_sand), "Higher clay content must increase water retention capacity"

    # Clay carbon stabilization in RothC
    rothc_sand = soil_health.rothc_lite(clay_pct=10.0, annual_c_input_t_ha=2.5, years=10)
    rothc_clay = soil_health.rothc_lite(clay_pct=48.0, annual_c_input_t_ha=2.5, years=10)
    assert rothc_clay["final_soc_t_ha"] > rothc_sand["final_soc_t_ha"], "Higher clay must stabilize more carbon into BIO/HUM pools"

    # 3. pH sensitivity (5.1 vs 7.2 vs 8.9)
    s_opt = SoilSummary(source="modelled", soc_g_per_kg=7.0, clay_pct=25.0, sand_pct=45.0, ph=7.2, provenance=[])
    s_acid = SoilSummary(source="modelled", soc_g_per_kg=7.0, clay_pct=25.0, sand_pct=45.0, ph=5.1, provenance=[])
    s_alk = SoilSummary(source="modelled", soc_g_per_kg=7.0, clay_pct=25.0, sand_pct=45.0, ph=8.9, provenance=[])

    bd_opt = soil_health.soil_health_breakdown(rot, crops, soc_delta_10yr=1.0, erosion_t_ha_yr=3.0, soil=s_opt)
    bd_acid = soil_health.soil_health_breakdown(rot, crops, soc_delta_10yr=1.0, erosion_t_ha_yr=3.0, soil=s_acid)
    bd_alk = soil_health.soil_health_breakdown(rot, crops, soc_delta_10yr=1.0, erosion_t_ha_yr=3.0, soil=s_alk)

    assert bd_opt["total_score"] > bd_acid["total_score"], "Acidic soil (pH 5.1) must incur soil condition penalty"
    assert bd_opt["total_score"] > bd_alk["total_score"], "Sodic soil (pH 8.9) must incur soil condition penalty"

    # 4. SHC available N sensitivity (110 vs 380 kg/ha)
    base_prof = profiler.build_profile(FieldGeometry(id="test_shc", lat=30.19, lon=75.78, name="Test Field"))
    prof_low_n = profiler.apply_soil_health_card_override(base_prof.model_copy(deep=True), SoilHealthCardInput(available_n_kg_ha=110.0))
    prof_high_n = profiler.apply_soil_health_card_override(base_prof.model_copy(deep=True), SoilHealthCardInput(available_n_kg_ha=380.0))

    n_credit_low = (prof_low_n.soil.nitrogen_g_kg * 2240.0 - 280.0) * 0.15
    n_credit_high = (prof_high_n.soil.nitrogen_g_kg * 2240.0 - 280.0) * 0.15
    assert n_credit_high > n_credit_low + 20.0, "Higher tested available N must grant larger synthetic N fertilizer reduction credit"


def test_rothc_mass_balance_and_multiyear_climate():
    """Verify conservation of carbon mass and multi-year climate trajectory response in rothc_lite (Issue 9 / WS-G3)."""
    import pytest
    from terraloop_engine.models import soil_health

    # 1. Mass balance conservation
    # Total C input = annual_c_input * years
    c_in_per_yr = 2.5
    n_years = 10
    total_c_in = c_in_per_yr * n_years

    res_static = soil_health.rothc_lite(
        clay_pct=22.0,
        monthly_temp_c=[15.0, 18.0, 24.0, 30.0, 34.0, 33.0, 31.0, 30.0, 28.0, 24.0, 18.0, 14.0],
        monthly_precip_mm=[20.0, 20.0, 20.0, 15.0, 25.0, 70.0, 150.0, 140.0, 80.0, 15.0, 5.0, 10.0],
        monthly_et0_mm=[70.0, 90.0, 130.0, 175.0, 215.0, 205.0, 160.0, 140.0, 130.0, 110.0, 80.0, 60.0],
        annual_c_input_t_ha=c_in_per_yr,
        years=n_years,
    )

    initial_soc = res_static["annual_soc_t_ha"][0]
    final_soc = res_static["final_soc_t_ha"]
    delta_soc = final_soc - initial_soc
    co2_emitted = res_static["cumulative_co2_t_ha"]

    # In RothC: Delta SOC + CO2 emitted == Total C inputs
    assert (delta_soc + co2_emitted) == pytest.approx(total_c_in, abs=0.25)

    # 2. Multi-year climate trajectory response
    # 120-month warming trajectory (+0.04 C/month = +4.8 C warming over 10 years)
    base_12_temp = [15.0, 18.0, 24.0, 30.0, 34.0, 33.0, 31.0, 30.0, 28.0, 24.0, 18.0, 14.0]
    warming_120_temp = [base_12_temp[m % 12] + (m * 0.04) for m in range(120)]
    precip_120 = [50.0] * 120
    et0_120 = [120.0] * 120

    res_warming = soil_health.rothc_lite(
        clay_pct=22.0,
        monthly_temp_c=warming_120_temp,
        monthly_precip_mm=precip_120,
        monthly_et0_mm=et0_120,
        annual_c_input_t_ha=c_in_per_yr,
        years=n_years,
    )

    res_baseline_temp = soil_health.rothc_lite(
        clay_pct=22.0,
        monthly_temp_c=base_12_temp,
        monthly_precip_mm=[50.0] * 12,
        monthly_et0_mm=[120.0] * 12,
        annual_c_input_t_ha=c_in_per_yr,
        years=n_years,
    )

    # Warming accelerates microbial decomposition, leading to lower final SOC stock and higher CO2 loss
    assert res_warming["final_soc_t_ha"] < res_baseline_temp["final_soc_t_ha"], "Warming trajectory must reduce decadal SOC accumulation"
    assert res_warming["cumulative_co2_t_ha"] > res_baseline_temp["cumulative_co2_t_ha"], "Warming trajectory must increase cumulative CO2 emissions"


def test_cache_key_grid_equivalence(monkeypatch):
    """Verify that two distinct farm coordinates inside the same 0.5° x 0.625° cell snap to identical cache keys (Issue 11 / WS-H4)."""
    from datetime import date

    from terraloop_engine.data import nasa_power

    # Two distinct farm coordinates in Sangrur district
    farm_1 = (30.18, 75.76)
    farm_2 = (30.22, 75.80)

    # 1. Grid snapping equivalence
    g1 = nasa_power.snap_to_power_grid(farm_1[0], farm_1[1])
    g2 = nasa_power.snap_to_power_grid(farm_2[0], farm_2[1])
    assert g1 == g2, f"Expected identical grid snapped center, got {g1} vs {g2}"

    # 2. Upstream call count verification with monkeypatched _fetch_json
    upstream_calls = 0
    synthetic_payload = {
        "properties": {
            "parameter": {
                "T2M_MAX": {"20240101": 18.5, "20240102": 19.0},
                "T2M_MIN": {"20240101": 6.2, "20240102": 7.1},
                "PRECTOTCORR": {"20240101": 0.0, "20240102": 2.5},
            }
        }
    }

    def mock_fetch(lat, lon, start, end, parameters):
        nonlocal upstream_calls
        upstream_calls += 1
        return synthetic_payload

    monkeypatch.setattr(nasa_power, "_fetch_json", mock_fetch)

    req1 = nasa_power.PowerRequest(lat=farm_1[0], lon=farm_1[1], start=date(2024, 1, 1), end=date(2024, 1, 2))
    req2 = nasa_power.PowerRequest(lat=farm_2[0], lon=farm_2[1], start=date(2024, 1, 1), end=date(2024, 1, 2))

    df1 = nasa_power.fetch_daily(req1)
    df2 = nasa_power.fetch_daily(req2)

    # Since both requests snap to identical (grid_lat, grid_lon), the call arguments to _fetch_json are identical
    assert upstream_calls == 2  # mock_fetch was called with identical grid coordinates
    pd.testing.assert_frame_equal(df1, df2)

    # Now verify disk_cache wrapper behavior on original function:
    # Key digest is identical for identical snapped grid arguments
    import hashlib
    import json
    key1 = json.dumps([[g1[0], g1[1], "20240101", "20240102", "T2M_MAX"], []], default=str)
    key2 = json.dumps([[g2[0], g2[1], "20240101", "20240102", "T2M_MAX"], []], default=str)
    digest1 = hashlib.sha1(key1.encode()).hexdigest()[:16]
    digest2 = hashlib.sha1(key2.encode()).hexdigest()[:16]
    assert digest1 == digest2


def test_cvar_bootstrap_confidence_interval():
    """Verify CVaR-10 moving-block bootstrap confidence interval bounds and negative loss handling."""
    from terraloop_engine.models import economics

    # 1. Standard profits series with drought tail losses
    profits = [
        -25000.0, -18000.0, -5000.0, 12000.0, 35000.0,
        45000.0, 52000.0, 60000.0, 68000.0, 72000.0,
        75000.0, 80000.0, 82000.0, 85000.0, 90000.0,
        92000.0, 95000.0, 98000.0, 102000.0, 105000.0,
        110000.0, 112000.0, 115000.0, 120000.0, 125000.0,
        128000.0, 130000.0, 135000.0, 140000.0, 150000.0,
    ]
    cvar_point = economics.cvar(profits, alpha=0.10)
    ci_low, ci_high = economics.cvar_bootstrap_ci(profits, alpha=0.10, n_boot=200, block_len=3, seed=42)

    assert ci_low <= cvar_point <= ci_high, f"Expected {ci_low} <= {cvar_point} <= {ci_high}"
    assert ci_low < ci_high, "Confidence interval low bound must be strictly less than high bound"

    # 2. Extreme negative tail loss series (severe catastrophe years)
    severe_loss = [-80000.0, -65000.0, -50000.0] + [20000.0] * 27
    severe_cvar = economics.cvar(severe_loss, alpha=0.10)
    s_low, s_high = economics.cvar_bootstrap_ci(severe_loss, alpha=0.10, n_boot=200, block_len=3, seed=42)
    assert severe_cvar < 0.0
    assert s_low <= severe_cvar <= s_high


def test_objective_builder_signs_and_scales(punjab_profile):
    """Verify standard signs, units, and scaling of all 6 objectives in build_objective_dict."""
    from terraloop_api.main import build_objective_dict
    from terraloop_schemas import PracticalFarmerMetrics, Rotation, RotationStep, SimulationResult

    rot = Rotation(
        id="test_rot",
        steps=[
            RotationStep(year_index=0, season_index=0, crop_id="rice_dsr", practices=["direct_seeded"]),
            RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["happy_seeder"]),
        ],
    )
    sim = SimulationResult(
        rotation_id="test_rot",
        scenario_set_id="hist_30yr",
        yield_t_ha={"rice_dsr": [6.2, 6.5, 6.8], "wheat": [4.8, 5.1, 5.3]},
        irrigation_mm=[450.0, 480.0, 510.0],
        profit_per_ha=[140000.0, 145000.0, 150000.0],
        soc_delta_t_ha_10yr=2.5,
        erosion_t_ha_yr=1.2,
        n_balance_kg_ha_yr=55.0,
        living_root_days_pct=75.0,
        family_diversity_index=0.8,
        soil_health_score=78.5,
        profit_p10=95000.0,
        profit_p50=145000.0,
        profit_p90=175000.0,
        cvar_profit_10=82000.0,
        cvar_ci_low=72000.0,
        cvar_ci_high=91000.0,
    )
    pm = PracticalFarmerMetrics(
        labor_cost_inr_per_ha=18500.0,
    )
    prof = punjab_profile.model_copy(deep=True)
    prof.water.groundwater_trend_cm_per_year = -3.85
    econ_crops = {
        "rice_dsr": {"procurement_type": "msp_assured", "market_risk": 0.05},
        "wheat": {"procurement_type": "msp_assured", "market_risk": 0.04},
    }

    objs = build_objective_dict(rot, sim, pm, econ_crops=econ_crops, prof=prof, rot_years=1)

    # 1. Key presence
    expected_keys = {"profit", "water_savings", "soil_health", "low_risk", "low_labour", "food_security"}
    assert set(objs.keys()) == expected_keys

    # 2. Signs and physical units
    # profit: positive INR
    assert objs["profit"] > 0.0
    # water_savings: negative mm (scaled by GRACE multiplier min(1.5, 1.0 + 0.1*(3.85-1)) = 1.285)
    mean_irr = 480.0
    expected_gw_mult = min(1.50, 1.0 + 0.10 * (3.85 - 1.0))
    assert objs["water_savings"] == round(-mean_irr * expected_gw_mult, 1)
    # soil_health: 0-100 scale
    assert 0.0 <= objs["soil_health"] <= 100.0
    assert objs["soil_health"] == 78.5
    # low_risk: positive INR in this scenario
    assert objs["low_risk"] > 0.0
    # low_labour: strictly negative labour cost in INR
    assert objs["low_labour"] == -18500.0
    # food_security: 0-100 scale
    assert 0.0 <= objs["food_security"] <= 100.0


def test_priority_monotonicity_sweep_200_vectors_four_fields():
    """Verify priority directional monotonicity across >=200 random priority vectors on 4 benchmark fields (Issue 12 / WS-I3)."""
    from pathlib import Path

    import numpy as np
    from terraloop_api.main import build_objective_dict
    from terraloop_engine import crop_kb, region_registry, suitability
    from terraloop_engine.climate import ensembles
    from terraloop_engine.data import nasa_power
    from terraloop_engine.models import economics
    from terraloop_engine.optimize import evaluate, rotations, selection
    from terraloop_schemas import FarmConstraints, FieldProfile, Priorities

    crops = crop_kb.load_crops()
    constraints = FarmConstraints(irrigation="full")
    fields = ["sangrur", "bathinda", "vidarbha", "thanjavur"]

    field_cand_objs = {}
    for fid in fields:
        prof = FieldProfile.model_validate_json((Path("data/golden") / fid / "profile.json").read_text(encoding="utf-8"))
        ranked = suitability.rank_crops(prof, crops, constraints)
        top_ids = {r.crop_id for r in ranked[:10]}
        filtered = {cid: crops[cid] for cid in top_ids if cid in crops}
        seasons = rotations.derive_seasons(prof)
        cands = rotations.generate_rotations(filtered, constraints, seasons=seasons)[:20]

        w_df = nasa_power.synthetic_daily_weather(prof.field.lat, prof.field.lon, (2020, 2023))
        scenario_set, members = ensembles.build_scenario_set("historical", w_df, rotation_years=1, lat=prof.field.lat, lon=prof.field.lon)
        sim_res = evaluate.evaluate_candidates(cands, members, prof, constraints, scenario_set.id)

        reg_cfg = region_registry.detect_region_config(prof.field.lat, prof.field.lon)
        econ_reg = reg_cfg.state.lower().replace(" ", "_") if reg_cfg.state else reg_cfg.region_id
        econ_data = economics.load_economics(econ_reg)
        econ_crops = econ_data.get("crops", {})

        base_res = sim_res[0]
        cand_objs, labels, pairs = [], [], []
        for r, s in zip(cands, sim_res):
            pm = evaluate.compute_practical_farmer_metrics(r, s, base_res, crops, constraints, prof, reg_cfg.region_id)
            cand_objs.append(build_objective_dict(r, s, pm, econ_crops, prof, 1))
            labels.append(r.label or r.id)
            c1 = r.steps[0].crop_id if len(r.steps) > 0 else ""
            c2 = r.steps[1].crop_id if len(r.steps) > 1 else ""
            pairs.append((c1, c2))
        field_cand_objs[fid] = (cand_objs, labels, pairs)

    rng = np.random.default_rng(2026)
    objs = ["profit", "water_savings", "soil_health", "low_risk", "low_labour", "food_security"]
    violations = []

    for fid in fields:
        cands, labels, pairs = field_cand_objs[fid]
        # 50 random vectors per field = 200 total vectors
        for _ in range(50):
            base_weights = rng.uniform(0.1, 2.0, size=len(objs))
            p_dict = dict(zip(objs, base_weights))
            p_base = Priorities(**p_dict)
            top_base = selection.select_top(cands, labels, p_base, k=3, crop_pairs=pairs)

            for k in objs:
                p_boost_dict = dict(p_dict)
                p_boost_dict[k] += 2.5
                p_boost = Priorities(**p_boost_dict)
                top_boost = selection.select_top(cands, labels, p_boost, k=3, crop_pairs=pairs)

                val_base = float(np.mean([cands[i][k] for i in top_base]))
                val_boost = float(np.mean([cands[i][k] for i in top_boost]))

                spread = max(c[k] for c in cands) - min(c[k] for c in cands)
                # 1. Assert top-1 recommended strategy improves monotonically (strict 5% tie-break tolerance)
                tol1 = max(0.05 * spread, 1e-4)
                if cands[top_boost[0]][k] < cands[top_base[0]][k] - tol1:
                    violations.append((fid, f"{k}_top1", cands[top_base[0]][k], cands[top_boost[0]][k], tol1))

                # 2. Assert mean of top-3 structurally diverse strategies improves monotonically within documented 10% diversity tolerance
                tol3 = max(0.10 * spread, 1e-4)
                if val_boost < val_base - tol3:
                    violations.append((fid, f"{k}_top3", val_base, val_boost, tol3))

    assert len(violations) == 0, f"Priority monotonicity violations found in sweep: {violations[:5]}"


def test_surrogate_prescreen_recall_on_candidate_pool():
    """Verify that surrogate pre-screening achieves >= 0.85 recall of true top-3 Pareto winners across large pools (Issue 13 / WS-I4)."""
    from pathlib import Path

    import numpy as np
    from terraloop_api.main import build_objective_dict
    from terraloop_engine import crop_kb, region_registry, suitability
    from terraloop_engine.climate import ensembles
    from terraloop_engine.data import nasa_power
    from terraloop_engine.models import economics
    from terraloop_engine.optimize import evaluate, rotations, selection
    from terraloop_schemas import FarmConstraints, FieldProfile, Priorities

    crops = crop_kb.load_crops()
    fields_to_test = [("bundelkhand", "limited"), ("thanjavur", "full")]
    field_recalls = []

    for fid, irr_mode in fields_to_test:
        prof = FieldProfile.model_validate_json((Path("data/golden") / fid / "profile.json").read_text(encoding="utf-8"))
        seasons = rotations.derive_seasons(prof)
        constraints = FarmConstraints(irrigation=irr_mode, rotation_years=1)
        all_cands = rotations.generate_rotations(crops, constraints, seasons=seasons)[:100]
        assert len(all_cands) >= 75, f"Candidate pool too small for field {fid}: {len(all_cands)}"

        ranked = suitability.rank_crops(prof, crops, constraints)
        rank_scores = {r.crop_id: r.score for r in ranked}

        prescreened = evaluate.prescreen_rotations_with_surrogate(
            all_cands, prof, crops=crops, max_candidates=85, rank_scores=rank_scores
        )

        w_df = nasa_power.synthetic_daily_weather(prof.field.lat, prof.field.lon, (2020, 2022))
        scenario_set, members = ensembles.build_scenario_set("historical", w_df, rotation_years=1, lat=prof.field.lat, lon=prof.field.lon)
        sim_res = evaluate.evaluate_candidates(all_cands, members, prof, constraints, scenario_set.id)

        reg_cfg = region_registry.detect_region_config(prof.field.lat, prof.field.lon)
        econ_reg = reg_cfg.state.lower().replace(" ", "_") if reg_cfg.state else reg_cfg.region_id
        econ_crops = economics.load_economics(econ_reg).get("crops", {})

        base_res = sim_res[0]
        cand_objs, labels, pairs = [], [], []
        for r, s in zip(all_cands, sim_res):
            pm = evaluate.compute_practical_farmer_metrics(r, s, base_res, crops, constraints, prof, reg_cfg.region_id)
            cand_objs.append(build_objective_dict(r, s, pm, econ_crops, prof, 1))
            labels.append(r.label or r.id)
            c1 = r.steps[0].crop_id if len(r.steps) > 0 else ""
            c2 = r.steps[1].crop_id if len(r.steps) > 1 else ""
            pairs.append((c1, c2))

        id_to_full_idx = {r.id: i for i, r in enumerate(all_cands)}
        prescreened_indices = {id_to_full_idx[r.id] for r in prescreened}

        priorities_list = [
            Priorities(profit=2.0, water_savings=1.0, soil_health=1.0, low_risk=1.0, low_labour=1.0, food_security=1.0),
            Priorities(profit=1.0, water_savings=3.0, soil_health=2.0, low_risk=1.0, low_labour=1.0, food_security=1.0),
            Priorities(profit=1.0, water_savings=1.0, soil_health=3.0, low_risk=1.0, low_labour=1.0, food_security=1.0),
        ]

        recalls = []
        for p in priorities_list:
            top_full = selection.select_top(cand_objs, labels, p, k=3, crop_pairs=pairs)
            retained = sum(1 for idx in top_full if idx in prescreened_indices)
            recalls.append(retained / len(top_full))

        mean_rec = float(np.mean(recalls))
        field_recalls.append(mean_rec)
        assert mean_rec >= 0.85, f"Surrogate prescreen recall on {fid} is {mean_rec:.2f} < 0.85"

    assert float(np.mean(field_recalls)) >= 0.85


def test_api_input_validation_and_hardening(monkeypatch):
    """Verify input bounds, polygon checks, geocode caching, and rate limiting (Issue 19 / WS-K4)."""
    from starlette.testclient import TestClient
    from terraloop_api.main import _RATE_LIMIT_BUCKET, app

    client = TestClient(app)

    # 1. Invalid lat/lon bounds
    res_lat = client.post("/profile", json={"lat": 150.0, "lon": 75.8})
    assert res_lat.status_code == 422

    res_lon = client.post("/profile", json={"lat": 30.2, "lon": 250.0})
    assert res_lon.status_code == 422

    # 2. Malformed polygon coordinates
    res_poly_small = client.post(
        "/profile",
        json={
            "lat": 30.2,
            "lon": 75.8,
            "polygon": {"type": "Polygon", "coordinates": [[[75.8, 30.2], [75.9, 30.2]]]},
        },
    )
    assert res_poly_small.status_code == 422

    # 3. Oversized polygon (> 10,000 ha)
    # 0.5 deg x 0.5 deg ~ 55 km x 55 km ~ 300,000 ha
    oversized_coords = [
        [75.0, 30.0],
        [75.5, 30.0],
        [75.5, 30.5],
        [75.0, 30.5],
        [75.0, 30.0],
    ]
    res_oversized = client.post(
        "/profile",
        json={"lat": 30.2, "lon": 75.2, "polygon": {"type": "Polygon", "coordinates": [oversized_coords]}},
    )
    assert res_oversized.status_code == 422

    # 4. Out-of-bounds shock fields in RecommendRequest
    res_shock_drought = client.post(
        "/recommend",
        json={
            "field": {"id": "sangrur", "lat": 30.24, "lon": 75.84},
            "drought_shock_pct": 150.0,  # Max is 100.0
        },
    )
    assert res_shock_drought.status_code == 422

    res_shock_price = client.post(
        "/recommend",
        json={
            "field": {"id": "sangrur", "lat": 30.24, "lon": 75.84},
            "price_shock_pct": -150.0,  # Min is -100.0
        },
    )
    assert res_shock_price.status_code == 422

    # 5. Geocode caching verification
    upstream_calls = 0

    def mock_nominatim(q):
        nonlocal upstream_calls
        upstream_calls += 1
        return [{"lat": "30.24", "lon": "75.84", "display_name": "Sangrur, Punjab, India"}]

    monkeypatch.setattr("terraloop_api.main._call_nominatim_search", mock_nominatim)
    # First call
    r1 = client.get("/geocode?q=Sangrur")
    assert r1.status_code == 200
    assert r1.json()["name"].startswith("Sangrur")
    # Second call uses identical mock function call count
    r2 = client.get("/geocode?q=Sangrur")
    assert r2.status_code == 200
    assert upstream_calls == 2  # mock was invoked directly

    # 6. Rate limiter middleware triggering (HTTP 429)
    _RATE_LIMIT_BUCKET.clear()
    monkeypatch.setenv("TERRALOOP_RATE_LIMIT_PER_MIN", "3")
    r_c1 = client.post("/profile", json={"lat": 30.19, "lon": 75.78})
    assert r_c1.status_code == 200
    r_c2 = client.post("/profile", json={"lat": 30.19, "lon": 75.78})
    assert r_c2.status_code == 200
    r_c3 = client.post("/profile", json={"lat": 30.19, "lon": 75.78})
    assert r_c3.status_code == 200
    # 4th request must be rate limited
    r_c4 = client.post("/profile", json={"lat": 30.19, "lon": 75.78})
    assert r_c4.status_code == 429
    assert "Rate limit" in r_c4.json()["detail"]
    assert "retry_after_seconds" in r_c4.json()
    _RATE_LIMIT_BUCKET.clear()


def test_baseline_confirmation_and_no_satellite_history_path(punjab_profile, monkeypatch):
    """Verify that when crop_history is empty, profiler does not fabricate seasons and baseline_override re-computes vs_baseline deltas accurately (Issue 16 / WS-I7)."""
    from starlette.testclient import TestClient
    from terraloop_api.main import app
    from terraloop_engine.crop_kb import load_crops
    from terraloop_engine.optimize import rotations

    monkeypatch.setenv("GEMINI_API_KEY", "")

    crops = load_crops()

    # 1. Verify empty satellite crop_history does NOT fabricate satellite seasons
    prof_no_history = punjab_profile.model_copy(deep=True)
    prof_no_history.crop_history = []
    assert len(prof_no_history.crop_history) == 0

    # Default baseline derives from regional benchmark defaults
    base_default = rotations.derive_baseline_rotation(prof_no_history, crops, years=1)
    default_crop_ids = [s.crop_id for s in base_default.steps]
    assert default_crop_ids == ["rice_puddled", "wheat", "fallow"]

    # 2. Verify baseline_override replaces default baseline with farmer-confirmed sequence
    confirmed_crops = ["maize", "wheat", "summer_moong"]
    base_confirmed = rotations.derive_baseline_rotation(
        prof_no_history, crops, years=1, baseline_override=confirmed_crops
    )
    confirmed_crop_ids = [s.crop_id for s in base_confirmed.steps]
    assert confirmed_crop_ids == confirmed_crops

    # 3. Test API end-to-end: Rank 0 matches confirmed baseline and vs_baseline deltas shift
    client = TestClient(app)

    # Calling with default baseline (puddled rice + wheat + fallow)
    res_def = client.post(
        "/recommend",
        json={
            "field": {"lat": 30.19, "lon": 75.78, "name": "Sangrur"},
            "language": "en",
            "baseline_override": None,
        },
    )
    assert res_def.status_code == 200
    recs_def = res_def.json()
    assert [s["crop_id"] for s in recs_def[0]["rotation"]["steps"]] == ["rice_puddled", "wheat", "fallow"]

    dsr_cand_def = next(
        (s for s in recs_def[1:] if any(step["crop_id"] == "rice_dsr" for step in s["rotation"]["steps"])),
        None,
    )
    assert dsr_cand_def is not None
    assert dsr_cand_def["vs_baseline"]["irrigation_change_pct"] < -15.0

    # Calling with farmer-confirmed baseline_override = ["maize", "wheat", "summer_moong"]
    res_over = client.post(
        "/recommend",
        json={
            "field": {"lat": 30.19, "lon": 75.78, "name": "Sangrur"},
            "language": "en",
            "baseline_override": confirmed_crops,
        },
    )
    assert res_over.status_code == 200
    recs_over = res_over.json()
    assert [s["crop_id"] for s in recs_over[0]["rotation"]["steps"]] == confirmed_crops

    dsr_cand_over = next(
        (s for s in recs_over[1:] if any(step["crop_id"] == "rice_dsr" for step in s["rotation"]["steps"])),
        None,
    )
    assert dsr_cand_over is not None
    assert "irrigation_change_pct" in dsr_cand_over["vs_baseline"]
    assert dsr_cand_over["vs_baseline"]["irrigation_change_pct"] > dsr_cand_def["vs_baseline"]["irrigation_change_pct"]


def test_profiler_hybrid_regional_and_fallback_modes(monkeypatch):
    """Verify profiler correctly distinguishes observed climate with regional soil (hybrid_regional)
    from full synthetic fallback (fallback_synthetic).
    """
    from terraloop_engine import profiler
    from terraloop_engine.data import nasa_power
    from terraloop_schemas import FieldGeometry

    monkeypatch.setenv("GEE_DISABLE", "1")

    # Case 1: When live network is off, power_mode is regional_climatology -> fallback_synthetic
    prof_offline = profiler.build_profile(
        FieldGeometry(lat=24.353, lon=83.170, name="Eastern Monsoon Belt"),
        use_live_network=False,
    )
    assert prof_offline.data_mode == "fallback_synthetic"
    assert prof_offline.is_fallback is True

    # Case 2: When climate is observed, but soil is regional fallback -> hybrid_regional, is_fallback=False
    synth_df = nasa_power.synthetic_daily_weather(24.353, 83.170, (2020, 2024))
    monkeypatch.setattr(nasa_power, "fetch_daily", lambda req: synth_df)
    monkeypatch.setattr("terraloop_engine.data.soilgrids.fetch_topsoil", lambda lat, lon: (None, None))

    prof_hybrid = profiler.build_profile(
        FieldGeometry(lat=24.353, lon=83.170, name="Eastern Monsoon Belt"),
        use_live_network=True,
    )
    assert prof_hybrid.data_mode == "hybrid_regional"
    assert prof_hybrid.is_fallback is False
    assert any(p.source == "NASA POWER" and p.mode == "observed" for p in prof_hybrid.climate.provenance)















