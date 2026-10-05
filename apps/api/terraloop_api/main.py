"""TerraLoop HTTP API.

Run (from repo root):
    uv run uvicorn terraloop_api.main:app --reload --port 8000 --app-dir apps/api
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from terraloop_engine import crop_kb, profiler, suitability
from terraloop_schemas import CropSpec, FarmConstraints, FieldGeometry, FieldProfile, Priorities

log = logging.getLogger("terraloop.api")

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = REPO_ROOT / "data" / "golden"

app = FastAPI(title="TerraLoop API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/crops", response_model=list[CropSpec])
def list_crops() -> list[CropSpec]:
    return list(crop_kb.load_crops().values())


# ---------------------------------------------------------------------------
# Golden (precomputed demo) fields: the demo must never depend on live APIs
# ---------------------------------------------------------------------------
def _golden_index() -> list[dict]:
    return json.loads((GOLDEN_DIR / "fields.json").read_text(encoding="utf-8"))


@app.get("/golden")
def golden_fields() -> list[dict]:
    return _golden_index()


@app.get("/golden/{field_id}/profile", response_model=FieldProfile)
def golden_profile(field_id: str) -> FieldProfile:
    path = GOLDEN_DIR / field_id / "profile.json"
    if path.exists():
        return FieldProfile.model_validate_json(path.read_text(encoding="utf-8"))
    match = next((f for f in _golden_index() if f["id"] == field_id), None)
    if not match:
        raise HTTPException(404, f"Unknown golden field '{field_id}'")
    return profiler.build_profile(FieldGeometry(lat=match["lat"], lon=match["lon"], name=match["name"]))


# ---------------------------------------------------------------------------
# Live endpoints
# ---------------------------------------------------------------------------
@app.post("/profile", response_model=FieldProfile)
def build_profile(field: FieldGeometry) -> FieldProfile:
    try:
        return profiler.build_profile(field)
    except Exception as exc:
        log.exception("profile failed")
        raise HTTPException(502, f"Upstream data error: {exc}") from exc


class SuitabilityRequest(BaseModel):
    field: FieldGeometry
    constraints: FarmConstraints = FarmConstraints()


class SuitabilityItem(BaseModel):
    crop_id: str
    name: str
    score: float
    thermal_fit: float
    water_fit: float
    sowing_months: list[int]
    reasons: list[str]


@app.post("/suitability", response_model=list[SuitabilityItem])
def crop_suitability(req: SuitabilityRequest) -> list[SuitabilityItem]:
    prof = profiler.build_profile(req.field)
    crops = crop_kb.load_crops()
    return [
        SuitabilityItem(name=crops[r.crop_id].name, **r.__dict__)
        for r in suitability.rank_crops(prof, crops, req.constraints)
    ]


class RecommendRequest(BaseModel):
    field: FieldGeometry
    priorities: Priorities = Priorities()
    constraints: FarmConstraints = FarmConstraints()


@app.post("/recommend")
def recommend(req: RecommendRequest) -> dict:
    """TASK-A03: profile -> candidates (optimize.rotations) -> simulate (models.*) across
    scenarios (climate.ensembles) -> objectives -> optimize.selection.select_top -> why-cards.
    Must return list[StrategyRecommendation] incl. the baseline for comparison."""
    raise HTTPException(501, "Not implemented yet: TASK-A03 in docs/TASKS.md")
