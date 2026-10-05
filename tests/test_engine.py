"""Profiler, crop KB, suitability, rotations, selection, API (no network)."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from terraloop_engine import crop_kb, profiler, suitability
from terraloop_engine.models.soil_health import family_shannon_index
from terraloop_engine.optimize import rotations, selection
from terraloop_schemas import FarmConstraints, FieldGeometry, FieldProfile, Priorities, WaterSummary


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


def test_api_basics():
    from terraloop_api.main import app

    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert len(client.get("/crops").json()) >= 20
    assert any(f["id"] == "sangrur" for f in client.get("/golden").json())
    assert client.post("/recommend", json={"field": {"lat": 30, "lon": 75}}).status_code == 501
