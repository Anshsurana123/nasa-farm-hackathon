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
