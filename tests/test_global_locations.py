from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from terraloop_api.main import app
from terraloop_engine.data import nasa_power

client = TestClient(app)

LOCATIONS = [
    ("California Central Valley", 36.75, -119.80, "USD", "$"),
    ("US Corn Belt (Iowa)", 42.05, -93.55, "USD", "$"),
    ("East Africa (Kenya)", -1.45, 37.40, "USD", "$"),
    ("Punjab (India)", 30.20, 75.92, "INR", "₹"),
    ("Australia (Western)", -31.95, 115.86, "USD", "$"),
    ("Brazil (Cerrado)", -15.78, -47.93, "USD", "$"),
    ("Southern Europe (Spain)", 37.38, -5.98, "USD", "$"),
]


@pytest.mark.parametrize("name,lat,lon,expected_curr,expected_sym", LOCATIONS)
def test_global_profile_and_recommend(name, lat, lon, expected_curr, expected_sym):
    def fake_fetch_daily(req):
        return nasa_power.synthetic_daily_weather(req.lat, req.lon, (req.start.year, req.end.year))

    def fake_fetch_topsoil(lat, lon):
        return {
            "sand": 45.0,
            "silt": 35.0,
            "clay": 20.0,
            "soc": 9.5,
            "phh2o": 7.1,
            "bdod": 138.0,
            "cec": 18.0,
            "nitrogen": 1.2,
        }, (lat, lon)

    with (
        patch("terraloop_engine.data.nasa_power.fetch_daily", side_effect=fake_fetch_daily),
        patch("terraloop_engine.data.soilgrids.fetch_topsoil", side_effect=fake_fetch_topsoil),
    ):
        # 1. Test /profile
        p_resp = client.post("/profile", json={"lat": lat, "lon": lon, "name": name})
        assert p_resp.status_code == 200, f"Profile failed for {name}: {p_resp.text}"
        prof = p_resp.json()
        assert prof["currency"] == expected_curr
        assert prof["currency_symbol"] == expected_sym
        assert prof["climate"]["mean_tmax_c"] is not None
        assert prof["climate"]["annual_precip_mm"] is not None
        assert len(prof["climate"]["monthly_precip_mm"]) == 12

        # 2. Test /recommend
        r_resp = client.post("/recommend", json={"field": {"lat": lat, "lon": lon, "name": name}})
        assert r_resp.status_code == 200, f"Recommend failed for {name}: {r_resp.text}"
        recs = r_resp.json()
        assert len(recs) >= 2  # Baseline + at least 1 top strategy
        assert recs[0]["rank"] == 0
        assert recs[0]["currency"] == expected_curr
        assert recs[1]["rank"] == 1
        assert recs[1]["currency"] == expected_curr
        assert len(recs[1]["why"]) > 0


def test_geocode_formats():
    # 1. Plain coordinate string
    resp = client.get("/geocode?q=30.2000,75.9200")
    assert resp.status_code == 200
    data = resp.json()
    assert abs(data["lat"] - 30.20) < 0.01
    assert abs(data["lon"] - 75.92) < 0.01

    # 2. Google Maps @lat,lon URL
    resp = client.get("/geocode?q=https://www.google.com/maps/@28.6139,77.2090,14z")
    assert resp.status_code == 200
    data = resp.json()
    assert abs(data["lat"] - 28.6139) < 0.01
    assert abs(data["lon"] - 77.2090) < 0.01

    # 3. Google Maps place protobuf URL
    resp = client.get("/geocode?q=https://www.google.com/maps/place/Test/@20.0357,73.8027,17z/data=!1d73.8027!2d20.0357")
    assert resp.status_code == 200
    data = resp.json()
    assert abs(data["lat"] - 20.0357) < 0.01
    assert abs(data["lon"] - 73.8027) < 0.01
    assert "Test" in data["name"] or "Location" in data["name"]

    # 4. OpenStreetMap URL
    resp = client.get("/geocode?q=https://www.openstreetmap.org/%23map=16/36.7500/-119.8000")
    assert resp.status_code == 200
    data = resp.json()
    assert abs(data["lat"] - 36.75) < 0.01
    assert abs(data["lon"] - (-119.80)) < 0.01

