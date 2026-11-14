"""Vercel services deployment: `/api` prefix routing and read-only filesystem cache fallback (no network)."""

from pathlib import Path

from fastapi.testclient import TestClient
from terraloop_engine import cache


def test_api_serves_with_and_without_vercel_prefix():
    from terraloop_api.main import app

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health").json() == client.get("/health").json()
    assert client.get("/api/golden").json() == client.get("/golden").json()
    # Swagger UI behind the rewrite must point at the prefixed OpenAPI document
    assert "/api/openapi.json" in client.get("/api/docs").text
    assert client.get("/apiary").status_code == 404  # prefix match is segment-aware


def test_cache_dir_falls_back_to_tmp_when_unwritable(monkeypatch, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("TERRALOOP_CACHE_DIR", str(blocker / "cache"))  # parent is a file -> mkdir fails
    monkeypatch.setattr(cache.tempfile, "gettempdir", lambda: str(tmp_path))
    assert cache.cache_dir() == Path(tmp_path) / "terraloop-cache"


def test_gee_service_account_credentials_resolution(monkeypatch, tmp_path):
    import base64
    import json
    from unittest.mock import MagicMock

    from terraloop_engine.data import gee

    mock_ee = MagicMock()
    mock_ee.oauth.SCOPES = ["https://www.googleapis.com/auth/earthengine"]

    # 1. No credentials configured
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_KEY", raising=False)
    monkeypatch.delenv("EE_SERVICE_ACCOUNT_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    creds, proj = gee._resolve_credentials(mock_ee)
    assert creds is None and proj is None

    # 2. Raw JSON string in GEE_SERVICE_ACCOUNT_KEY
    fake_key = {"project_id": "test-vercel-proj", "client_email": "test@test.iam.gserviceaccount.com"}
    monkeypatch.setenv("GEE_SERVICE_ACCOUNT_KEY", json.dumps(fake_key))
    monkeypatch.setattr(
        "google.oauth2.service_account.Credentials.from_service_account_info",
        lambda info, scopes: ("mock_creds", info["project_id"]),
    )
    creds, proj = gee._resolve_credentials(mock_ee)
    assert creds == ("mock_creds", "test-vercel-proj")
    assert proj == "test-vercel-proj"

    # 3. Base64-encoded JSON in GEE_SERVICE_ACCOUNT_KEY
    b64_key = base64.b64encode(json.dumps(fake_key).encode()).decode()
    monkeypatch.setenv("GEE_SERVICE_ACCOUNT_KEY", b64_key)
    creds, proj = gee._resolve_credentials(mock_ee)
    assert proj == "test-vercel-proj"

    # 4. File path in GOOGLE_APPLICATION_CREDENTIALS
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_KEY", raising=False)
    key_file = tmp_path / "sa.json"
    key_file.write_text(json.dumps(fake_key))
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key_file))
    monkeypatch.setattr(
        "google.oauth2.service_account.Credentials.from_service_account_file",
        lambda path, scopes: MagicMock(project_id="file-proj"),
    )
    creds, proj = gee._resolve_credentials(mock_ee)
    assert proj == "file-proj"


def test_golden_profiles_include_meteomatics_fields():
    """All 6 golden profiles in data/ and apps/web/public/ include Meteomatics hydrology, hazards & provenance."""
    import json

    root = Path(__file__).resolve().parents[1]
    golden_ids = ("sangrur", "ludhiana", "bathinda", "vidarbha", "bundelkhand", "thanjavur")
    bases = (root / "data" / "golden", root / "apps" / "web" / "public" / "golden")

    for base in bases:
        for fid in golden_ids:
            prof = json.loads((base / fid / "profile.json").read_text(encoding="utf-8"))
            adv = prof.get("tactical_advisory")
            assert adv is not None, f"{base / fid}: missing tactical_advisory"
            assert len(adv.get("forecast_days", [])) == 7, f"{base / fid}: expected 7 tactical forecast days"
            assert any("Meteomatics" in p.get("source", "") for p in adv.get("provenance", []))

            water = prof["water"]
            assert water.get("seedbed_temp_5cm_c") is not None
            assert isinstance(water.get("soil_moisture_index_layers"), dict) and water["soil_moisture_index_layers"]
            assert isinstance(water.get("volumetric_soil_water_layers"), dict) and water["volumetric_soil_water_layers"]
            assert any("Meteomatics" in p.get("source", "") for p in water.get("provenance", []))

            hazards = prof["hazards"]
            assert hazards.get("late_blight_risk_idx") is not None
            assert hazards.get("fire_weather_index") is not None
            assert hazards.get("max_30m_precip_rate_mmh") is not None
            assert any("Meteomatics" in p.get("source", "") for p in hazards.get("provenance", []))
