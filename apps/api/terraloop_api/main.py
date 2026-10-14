"""TerraLoop HTTP API.

Run (from repo root):
    uv run uvicorn terraloop_api.main:app --reload --port 8000 --app-dir apps/api
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from datetime import date
from pathlib import Path

import httpx
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from terraloop_engine import crop_kb, profiler, suitability
from terraloop_engine.climate import ensembles
from terraloop_engine.data import nasa_power
from terraloop_engine.explain import why_cards
from terraloop_engine.optimize import evaluate, rotations, selection
from terraloop_schemas import (
    CropSpec,
    FarmConstraints,
    FieldGeometry,
    FieldProfile,
    Priorities,
    StrategyRecommendation,
)

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
        prof = FieldProfile.model_validate_json(path.read_text(encoding="utf-8"))
        from terraloop_engine.models import economics

        region = economics.detect_region(prof.field.lat, prof.field.lon)
        curr = economics.get_currency_info(region)
        prof.currency = curr["code"]
        prof.currency_symbol = curr["symbol"]
        return prof
    match = next((f for f in _golden_index() if f["id"] == field_id), None)
    if not match:
        raise HTTPException(404, f"Unknown golden field '{field_id}'")
    return profiler.build_profile(FieldGeometry(lat=match["lat"], lon=match["lon"], name=match["name"]))


# ---------------------------------------------------------------------------
# Geocoding & Location Resolution
# ---------------------------------------------------------------------------
class GeocodeResult(BaseModel):
    lat: float
    lon: float
    name: str


def _clean_place_name(name: str) -> str:
    parts = [p.strip() for p in name.split(",") if p.strip()]
    if not parts:
        return name
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}, {parts[-1]}"


def _extract_place_name_from_url(url_str: str) -> str | None:
    # Match /maps/dir/<From>/<To>/ or /maps/place/<PlaceName>/
    m = re.search(r"/maps/dir/(?:[^/]+/)?([^/@]+)", url_str)
    if m:
        name = urllib.parse.unquote(m.group(1).replace("+", " "))
        if not re.match(r"^[\d.,\s-]+$", name):
            return _clean_place_name(name)
    m = re.search(r"/maps/place/([^/@]+)", url_str)
    if m:
        name = urllib.parse.unquote(m.group(1).replace("+", " "))
        if not re.match(r"^[\d.,\s-]+$", name):
            return _clean_place_name(name)
    return None


def _reverse_geocode_nominatim(lat: float, lon: float) -> str | None:
    """Best-effort reverse geocode using OSM Nominatim to obtain a human-friendly place name."""
    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json"},
                headers={"User-Agent": "TerraLoop-SpaceApps/1.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                addr = data.get("address", {})
                local = (
                    addr.get("neighbourhood")
                    or addr.get("suburb")
                    or addr.get("village")
                    or addr.get("town")
                    or addr.get("city")
                    or addr.get("county")
                )
                state = addr.get("state")
                country = addr.get("country")
                if local and state:
                    return f"{local}, {state}"
                if local and country:
                    return f"{local}, {country}"
                disp = data.get("display_name")
                if disp:
                    parts = [p.strip() for p in disp.split(",") if p.strip()]
                    return parts[0] if len(parts) <= 2 else f"{parts[0]}, {parts[-1]}"
    except Exception:  # noqa: BLE001, S110
        pass
    return None


def _extract_coords_from_url_or_text(text: str) -> tuple[float | None, float | None, str | None] | None:
    raw = text.strip()

    # 1. Check if input looks like a URL or map link
    is_url = bool(re.match(r"^(https?://|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/)", raw)) or any(
        k in raw for k in ("goo.gl", "google.com/maps", "maps.google", "openstreetmap.org", "maps.apple", "bing.com/maps")
    )

    expanded_url = raw
    if is_url:
        target_url = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
        # Validate that target_url domain is a trusted map service to prevent SSRF
        parsed = urllib.parse.urlparse(target_url)
        host = (parsed.hostname or "").lower()
        trusted_hosts = (
            "maps.app.goo.gl",
            "goo.gl",
            "google.com",
            "maps.google.com",
            "www.google.com",
            "openstreetmap.org",
            "www.openstreetmap.org",
            "maps.apple.com",
            "bing.com",
            "www.bing.com",
        )
        is_trusted = any(host == th or host.endswith("." + th) for th in trusted_hosts)
        if is_trusted:
            # Follow HTTP redirects (handles maps.app.goo.gl and goo.gl/maps shortened links)
            try:
                with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                    resp = client.get(
                        target_url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                    )
                    expanded_url = str(resp.url)
            except Exception as exc:  # noqa: BLE001
                log.warning("URL redirect resolution failed for '%s': %s", target_url, exc)
                expanded_url = target_url
        else:
            expanded_url = target_url

    # Check both expanded URL and original raw text
    for candidate in [expanded_url, raw]:
        # Google Maps protobuf !1d(lon)!2d(lat)
        m = re.search(r"!1d(-?\d+\.\d+)!2d(-?\d+\.\d+)", candidate)
        if m:
            lat, lon = float(m.group(2)), float(m.group(1))
            return lat, lon, _extract_place_name_from_url(expanded_url)

        # Google Maps protobuf !3d(lat)!4d(lon)
        m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", candidate)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            return lat, lon, _extract_place_name_from_url(expanded_url)

        # Google Maps /@lat,lon
        m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", candidate)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            return lat, lon, _extract_place_name_from_url(expanded_url)

        # Query param ?q=lat,lon or ?ll=lat,lon or query=lat,lon
        m = re.search(r"[?&](?:q|query|ll)=(-?\d+\.\d+),(-?\d+\.\d+)", candidate)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            return lat, lon, _extract_place_name_from_url(expanded_url)

        # Google Maps directions /dir/<lat>,<lon>/
        m = re.search(r"/dir/(-?\d+\.\d+),(-?\d+\.\d+)", candidate)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            return lat, lon, _extract_place_name_from_url(expanded_url)

        # OpenStreetMap #map=zoom/lat/lon
        m = re.search(r"#map=\d+/(-?\d+\.\d+)/(-?\d+\.\d+)", candidate)
        if m:
            return float(m.group(1)), float(m.group(2)), "OpenStreetMap Location"

        # Bing Maps cp=lat~lon
        m = re.search(r"[?&]cp=(-?\d+\.\d+)~(-?\d+\.\d+)", candidate)
        if m:
            return float(m.group(1)), float(m.group(2)), "Bing Maps Location"

        # Direct coordinate string "lat, lon" or "lat lon"
        m = re.match(r"^(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)$", candidate)
        if m:
            try:
                lat, lon = float(m.group(1)), float(m.group(2))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon, None
            except ValueError:
                pass

    # If the URL did not contain explicit coordinates but had a search keyword (e.g. /search/Fresno+CA)
    if is_url:
        search_m = re.search(r"/maps/search/([^/?]+)", expanded_url)
        if search_m:
            term = urllib.parse.unquote(search_m.group(1).replace("+", " "))
            return None, None, term

    return None


@app.get("/geocode", response_model=GeocodeResult)
def geocode_location(q: str) -> GeocodeResult:
    text = q.strip()
    if not text:
        raise HTTPException(400, "Query string 'q' cannot be empty")

    # 1. Check if input is a URL, Google Maps link, or raw coordinate string
    res = _extract_coords_from_url_or_text(text)
    if res is not None:
        lat, lon, extracted_name = res
        if lat is not None and lon is not None:
            rev_name = _reverse_geocode_nominatim(lat, lon)
            final_name = extracted_name or rev_name or f"Location ({lat:.4f}°, {lon:.4f}°)"
            return GeocodeResult(lat=round(lat, 4), lon=round(lon, 4), name=final_name)
        elif extracted_name:
            # URL contained a search term without coords; geocode this term
            text = extracted_name

    # 2. OpenStreetMap Nominatim global address search for place names / addresses
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "TerraLoop-SpaceApps/1.0"}
    params = {"q": text, "format": "json", "limit": 1}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    item = data[0]
                    disp = item.get("display_name", text)
                    parts = [p.strip() for p in disp.split(",") if p.strip()]
                    short_name = parts[0] if len(parts) == 1 else f"{parts[0]}, {parts[-1]}"
                    return GeocodeResult(
                        lat=round(float(item["lat"]), 4),
                        lon=round(float(item["lon"]), 4),
                        name=short_name,
                    )
    except Exception as exc:  # noqa: BLE001
        log.warning("Nominatim geocoding failed for '%s': %s", text, exc)

    raise HTTPException(status_code=404, detail=f"Location or address '{q}' not found")


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


@app.post("/recommend", response_model=list[StrategyRecommendation])
def recommend(req: RecommendRequest) -> list[StrategyRecommendation]:
    """TASK-A03: profile -> candidates (optimize.rotations) -> simulate (models.*) across
    scenarios (climate.ensembles) -> objectives -> optimize.selection.select_top -> why-cards.
    Returns list[StrategyRecommendation] containing baseline (rank 0) plus top 3 recommendations."""
    # 1. Field Profile
    golden_matches = [
        f for f in _golden_index()
        if abs(f["lat"] - req.field.lat) < 0.15 and abs(f["lon"] - req.field.lon) < 0.15
    ]
    if golden_matches:
        prof = golden_profile(golden_matches[0]["id"])
    else:
        try:
            prof = profiler.build_profile(req.field)
        except Exception as exc:  # noqa: BLE001
            log.warning("Live profiler failed: %s; falling back to location-calibrated synthetic profile", exc)
            from terraloop_engine.models import economics
            from terraloop_schemas import WaterSummary

            syn_weather = nasa_power.synthetic_daily_weather(req.field.lat, req.field.lon, (2015, 2024))
            c, h, wb = profiler.summarise_climate(syn_weather, req.field.lat)
            s = profiler.summarise_soil({"sand": 45, "silt": 35, "clay": 20, "soc": 8, "phh2o": 7.2, "bdod": 140})
            region = economics.detect_region(req.field.lat, req.field.lon)
            curr = economics.get_currency_info(region)
            prof = FieldProfile(
                field=req.field,
                climate=c,
                water=WaterSummary(climatic_water_balance_mm=wb),
                soil=s,
                hazards=h,
                currency=curr["code"],
                currency_symbol=curr["symbol"],
                agro_climatic_notes=profiler.build_notes(
                    c, s, WaterSummary(climatic_water_balance_mm=wb), h, lat=req.field.lat
                ),
            )

    # 2. Historical Weather Ensemble
    crops = crop_kb.load_crops()
    weather_df = None
    try:
        req_power = nasa_power.PowerRequest(req.field.lat, req.field.lon, date(2015, 1, 1), date(2024, 12, 31))
        weather_df = nasa_power.fetch_daily(req_power)
    except Exception as exc:  # noqa: BLE001
        log.warning("Live weather fetch failed: %s", exc)

    if weather_df is None or weather_df.empty:
        # Fallback synthetic weather series calibrated to the field's actual coordinates
        weather_df = nasa_power.synthetic_daily_weather(req.field.lat, req.field.lon, (2015, 2024))

    scenario_set, members = ensembles.build_scenario_set(
        kind="historical",
        power_df=weather_df,
        rotation_years=1,
    )

    # 3. Generate candidate rotations pre-screened by suitability
    ranked_crops = suitability.rank_crops(prof, crops, req.constraints)
    suitable_ids = {r.crop_id for r in ranked_crops if r.score >= 0.20}
    top_ids = {r.crop_id for r in ranked_crops[:8]} | suitable_ids
    filtered_crops = {cid: crops[cid] for cid in top_ids if cid in crops}

    # Derive agro-climatic seasons dynamically for this field's geography
    seasons = rotations.derive_seasons(prof)
    candidate_rotations = rotations.generate_rotations(filtered_crops, req.constraints, seasons=seasons)
    if len(candidate_rotations) > 35:
        candidate_rotations = candidate_rotations[:35]

    # 4. Baseline rotation (current farm practice derived from satellite history or regional benchmark)
    baseline_rot = rotations.derive_baseline_rotation(prof, crops)
    all_rotations = [baseline_rot] + candidate_rotations

    # 5. Evaluate all candidates across climate members
    sim_results = evaluate.evaluate_candidates(
        rotations=all_rotations,
        members=members,
        profile=prof,
        constraints=req.constraints,
        scenario_set_id=scenario_set.id,
    )

    # 6. Map to objective scores for Pareto / Priority selection
    cand_obj_dicts: list[dict[str, float]] = []
    labels: list[str] = []
    for r, res in zip(all_rotations, sim_results, strict=False):
        mean_irr = float(np.mean(res.irrigation_mm)) if res.irrigation_mm else 0.0
        obj_dict = {
            "profit": res.profit_p50,
            "water_savings": -mean_irr,  # Higher is better
            "soil_health": res.soil_health_score,
            "low_risk": res.cvar_profit_10,
            "low_labour": 0.0,
            "food_security": 1.0 if any(s.crop_id in ("wheat", "rice_puddled", "rice_dsr", "maize") for s in r.steps) else 0.5,
        }
        cand_obj_dicts.append(obj_dict)
        labels.append(r.label or r.id)

    baseline_result = sim_results[0]
    baseline_obj = cand_obj_dicts[0]

    # Select top k=3 distinct candidates from alternatives
    alt_candidates = cand_obj_dicts[1:]
    alt_labels = labels[1:]
    alt_rotations = all_rotations[1:]
    alt_results = sim_results[1:]

    chosen_indices = selection.select_top(alt_candidates, alt_labels, req.priorities, k=3)

    # 7. Assemble recommendations with why-cards and provenance
    baseline_res_metrics = evaluate.compute_resilience_and_regret(baseline_result)
    base_label = baseline_rot.label or baseline_rot.id
    base_why = [f"Current baseline practice for {prof.field.name or 'this field'}: {base_label}."]
    if any(s.crop_id == "rice_puddled" for s in baseline_rot.steps) and any(s.crop_id == "wheat" for s in baseline_rot.steps):
        base_why.append("Traditional intensive flood-irrigated rice-wheat system prone to severe aquifer drawdown.")
    elif any(s.crop_id == "maize" for s in baseline_rot.steps) and any(s.crop_id == "soybean" for s in baseline_rot.steps):
        base_why.append("Standard Corn Belt intensive monoculture with winter soil vulnerability.")

    baseline_rec = StrategyRecommendation(
        rank=0,
        rotation=baseline_rot,
        results=[baseline_result],
        objective_scores=baseline_obj,
        vs_baseline={
            "climate_resilience_score": baseline_res_metrics["climate_resilience_score"],
            "profit_regret": baseline_res_metrics["profit_regret"],
            "irrigation_spike_mm": baseline_res_metrics["irrigation_spike_mm"],
        },
        why=base_why,
        provenance=scenario_set.provenance,
        currency=prof.currency,
        currency_symbol=prof.currency_symbol,
    )

    out_recs: list[StrategyRecommendation] = [baseline_rec]

    for rank_idx, idx in enumerate(chosen_indices, start=1):
        chosen_rot = alt_rotations[idx]
        chosen_res = alt_results[idx]
        chosen_obj = alt_candidates[idx]

        base_irr = float(np.mean(baseline_result.irrigation_mm))
        cand_irr = float(np.mean(chosen_res.irrigation_mm))
        irr_diff_pct = round((cand_irr - base_irr) / base_irr * 100.0, 1) if base_irr > 0 else 0.0
        profit_diff_pct = (
            round((chosen_res.profit_p50 - baseline_result.profit_p50) / baseline_result.profit_p50 * 100.0, 1)
            if baseline_result.profit_p50 > 0
            else 0.0
        )
        soil_diff = round(chosen_res.soil_health_score - baseline_result.soil_health_score, 1)

        cand_res_metrics = evaluate.compute_resilience_and_regret(chosen_res)

        vs_base = {
            "irrigation_change_pct": irr_diff_pct,
            "profit_change_pct": profit_diff_pct,
            "soil_health_change_pts": soil_diff,
            "climate_resilience_score": cand_res_metrics["climate_resilience_score"],
            "profit_regret": cand_res_metrics["profit_regret"],
            "irrigation_spike_mm": cand_res_metrics["irrigation_spike_mm"],
        }

        rec = StrategyRecommendation(
            rank=rank_idx,
            rotation=chosen_rot,
            results=[chosen_res],
            objective_scores=chosen_obj,
            vs_baseline=vs_base,
            why=[],
            provenance=[],
            currency=prof.currency,
            currency_symbol=prof.currency_symbol,
        )
        cards, provs = why_cards.why_cards(prof, rec, baseline_rec)
        rec.why = cards
        rec.provenance = provs
        out_recs.append(rec)

    return out_recs

