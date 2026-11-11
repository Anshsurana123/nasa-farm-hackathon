"""TerraLoop HTTP API.

Run (from repo root):
    uv run uvicorn terraloop_api.main:app --reload --port 8000 --app-dir apps/api
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.parse
import uuid
from datetime import date
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from terraloop_engine import cache, crop_kb, profiler, region_registry, suitability
from terraloop_engine.climate import ensembles
from terraloop_engine.data import nasa_power
from terraloop_engine.explain import why_cards
from terraloop_engine.models import economics, nutrition
from terraloop_engine.optimize import evaluate, rotations, selection
from terraloop_schemas import (
    CropSpec,
    FieldGeometry,
    FieldProfile,
    GeocodeResult,
    RecommendRequest,
    StrategyRecommendation,
    SuitabilityItem,
    SuitabilityRequest,
    WaterSummary,
)

log = logging.getLogger("terraloop.api")

REPO_ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = REPO_ROOT / "data" / "golden"

app = FastAPI(title="TerraLoop India API", version="0.2.0")

# Public path prefix. On Vercel the top-level rewrite `/api/(.*)` forwards to this service with the
# prefix intact; locally (uvicorn on :8000) requests arrive without it. Both must resolve to the same routes.
API_PATH_PREFIX = "/" + os.environ.get("API_PATH_PREFIX", "/api").strip("/")


class _PathPrefixMiddleware:
    """Pure ASGI middleware: mark `API_PATH_PREFIX` as the ASGI root_path when a request carries it.

    Starlette strips `root_path` from the path before routing, and FastAPI uses it to build the
    `/docs` -> `openapi.json` URL, so `/api/health` and `/health` both hit the same handler.
    """

    def __init__(self, asgi_app, prefix: str) -> None:
        self.app = asgi_app
        self.prefix = prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket") and self.prefix != "/" and not scope.get("root_path"):
            path: str = scope["path"]
            if path == self.prefix or path.startswith(self.prefix + "/"):
                scope = {**scope, "root_path": self.prefix}
        await self.app(scope, receive, send)


app.add_middleware(_PathPrefixMiddleware, prefix=API_PATH_PREFIX)

cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Rate Limiting Middleware & Nominatim Throttling (Issue 19 / WS-K4)
# ---------------------------------------------------------------------------
_RATE_LIMIT_BUCKET: dict[str, list[float]] = {}
_RATE_LIMIT_LOCK = threading.Lock()
_NOMINATIM_LOCK = threading.Lock()
_LAST_NOMINATIM_CALL_TIME: float = 0.0


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Only rate-limit compute-heavy endpoints (/recommend and /profile) to prevent abuse (Issue 19 / WS-K4)
    path = request.url.path
    if not path.startswith(("/recommend", "/profile")):
        return await call_next(request)
    if path.startswith("/recommend/jobs"):
        return await call_next(request)

    limit_per_min = int(os.environ.get("TERRALOOP_RATE_LIMIT_PER_MIN", "60"))
    if limit_per_min <= 0:
        return await call_next(request)

    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()

    with _RATE_LIMIT_LOCK:
        timestamps = _RATE_LIMIT_BUCKET.setdefault(client_ip, [])
        # Prune timestamps older than 60s
        timestamps = [t for t in timestamps if now - t < 60.0]
        _RATE_LIMIT_BUCKET[client_ip] = timestamps

        if len(timestamps) >= limit_per_min:
            retry_after = int(60.0 - (now - timestamps[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit of {limit_per_min} requests/minute exceeded. Please retry after {retry_after}s.",
                    "client_ip": client_ip,
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )
        timestamps.append(now)

    return await call_next(request)


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
# Golden (precomputed Indian benchmark) fields: the demo must never depend on live APIs
# ---------------------------------------------------------------------------
def _golden_index() -> list[dict]:
    return json.loads((GOLDEN_DIR / "fields.json").read_text(encoding="utf-8"))


def _match_golden_field(field: FieldGeometry) -> str | None:
    """Match a field geometry to a precomputed golden benchmark field ONLY by exact field.id.

    Golden/precomputed data is strictly reserved for explicitly-selected demonstration fields.
    Spatial proximity matching (<0.15°) and name substring heuristics are prohibited (WS-B).
    """
    if not field.id:
        return None
    matches = [f for f in _golden_index() if f["id"] == field.id]
    return matches[0]["id"] if matches else None


def _load_golden_weather(field_id: str) -> pd.DataFrame | None:
    path = GOLDEN_DIR / field_id / "weather.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        df = pd.DataFrame(raw["data"], columns=raw["columns"])
        df.index = pd.to_datetime(raw["index"])
        df.index.name = "date"
        return df.astype(float).sort_index()
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to load golden weather for %s: %s", field_id, exc)
        return None


@app.get("/golden")
def golden_fields() -> list[dict]:
    return _golden_index()


@app.get("/golden/{field_id}/profile", response_model=FieldProfile)
def golden_profile(field_id: str) -> FieldProfile:
    path = GOLDEN_DIR / field_id / "profile.json"
    if path.exists():
        prof = FieldProfile.model_validate_json(path.read_text(encoding="utf-8"))
        prof.currency = "INR"
        prof.currency_symbol = "₹"
        prof.served_from = "demo_snapshot"
        prof.snapshot_date = "2026-11-10"
        if not prof.agro_zone:
            prof.agro_zone = economics.detect_agro_zone(prof.field.lat, prof.field.lon)
        return prof
    match = next((f for f in _golden_index() if f["id"] == field_id), None)
    if not match:
        raise HTTPException(404, f"Unknown golden field '{field_id}'")
    prof = profiler.build_profile(FieldGeometry(lat=match["lat"], lon=match["lon"], name=match["name"], id=field_id))
    prof.served_from = "demo_snapshot"
    prof.snapshot_date = "2026-11-10"
    return prof


@app.get("/golden/{field_id}/recommendations", response_model=list[StrategyRecommendation])
def golden_recommendations(field_id: str) -> list[StrategyRecommendation]:
    path = GOLDEN_DIR / field_id / "recommendations.json"
    if path.exists():
        raw_list = json.loads(path.read_text(encoding="utf-8"))
        recs = [StrategyRecommendation.model_validate(item) for item in raw_list]
        for r in recs:
            r.served_from = "demo_snapshot"
            r.snapshot_date = "2026-11-10"
        return recs
    match = next((f for f in _golden_index() if f["id"] == field_id), None)
    if not match:
        raise HTTPException(404, f"Unknown golden field '{field_id}'")
    return recommend(
        RecommendRequest(field=FieldGeometry(lat=match["lat"], lon=match["lon"], name=match["name"], id=field_id))
    )


# ---------------------------------------------------------------------------
# Geocoding & Location Resolution (India-focused)
# ---------------------------------------------------------------------------
def _clean_place_name(name: str) -> str:
    parts = [p.strip() for p in name.split(",") if p.strip()]
    if not parts:
        return name
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]}, {parts[-1]}"


def _extract_place_name_from_url(url_str: str) -> str | None:
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


@cache.disk_cache(namespace="geocode_reverse")
def _call_nominatim_reverse(lat: float, lon: float) -> str | None:
    global _LAST_NOMINATIM_CALL_TIME
    with _NOMINATIM_LOCK:
        now = time.time()
        elapsed = now - _LAST_NOMINATIM_CALL_TIME
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        _LAST_NOMINATIM_CALL_TIME = time.time()

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
                        addr.get("village")
                        or addr.get("town")
                        or addr.get("city")
                        or addr.get("county")
                        or addr.get("state_district")
                        or addr.get("suburb")
                    )
                    state = addr.get("state")
                    if local and state:
                        return f"{local}, {state}"
                    disp = data.get("display_name")
                    if disp:
                        parts = [p.strip() for p in disp.split(",") if p.strip()]
                        return parts[0] if len(parts) <= 2 else f"{parts[0]}, {parts[-1]}"
        except Exception as exc:  # noqa: BLE001
            log.debug("Nominatim reverse geocode lookup failed: %s", exc)
    return None


def _reverse_geocode_nominatim(lat: float, lon: float) -> str | None:
    """Best-effort reverse geocode using OSM Nominatim with disk caching & 1.0s thread-safe throttling."""
    return _call_nominatim_reverse(round(lat, 4), round(lon, 4))


@cache.disk_cache(namespace="geocode")
def _call_nominatim_search(query_text: str) -> list[dict] | None:
    global _LAST_NOMINATIM_CALL_TIME
    with _NOMINATIM_LOCK:
        now = time.time()
        elapsed = now - _LAST_NOMINATIM_CALL_TIME
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        _LAST_NOMINATIM_CALL_TIME = time.time()

        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "TerraLoop-SpaceApps/1.0"}
        params = {"q": query_text, "format": "json", "limit": 1, "countrycodes": "in"}
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("Nominatim geocoding failed for '%s': %s", query_text, exc)
    return None


def _extract_coords_from_url_or_text(text: str) -> tuple[float | None, float | None, str | None] | None:
    raw = text.strip()
    is_url = bool(re.match(r"^(https?://|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/)", raw)) or any(
        k in raw
        for k in ("goo.gl", "google.com/maps", "maps.google", "openstreetmap.org", "maps.apple", "bing.com/maps")
    )

    expanded_url = raw
    if is_url:
        target_url = raw if raw.startswith(("http://", "https://")) else f"https://{raw}"
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

    for candidate in [expanded_url, raw]:
        m = re.search(r"!1d(-?\d+\.\d+)!2d(-?\d+\.\d+)", candidate)
        if m:
            return float(m.group(2)), float(m.group(1)), _extract_place_name_from_url(expanded_url)

        m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", candidate)
        if m:
            return float(m.group(1)), float(m.group(2)), _extract_place_name_from_url(expanded_url)

        m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", candidate)
        if m:
            return float(m.group(1)), float(m.group(2)), _extract_place_name_from_url(expanded_url)

        m = re.search(r"[?&](?:q|query|ll)=(-?\d+\.\d+),(-?\d+\.\d+)", candidate)
        if m:
            return float(m.group(1)), float(m.group(2)), _extract_place_name_from_url(expanded_url)

        m = re.search(r"/dir/(-?\d+\.\d+),(-?\d+\.\d+)", candidate)
        if m:
            return float(m.group(1)), float(m.group(2)), _extract_place_name_from_url(expanded_url)

        m = re.search(r"#map=\d+/(-?\d+\.\d+)/(-?\d+\.\d+)", candidate)
        if m:
            return float(m.group(1)), float(m.group(2)), "OpenStreetMap Location"

        m = re.search(r"[?&]cp=(-?\d+\.\d+)~(-?\d+\.\d+)", candidate)
        if m:
            return float(m.group(1)), float(m.group(2)), "Bing Maps Location"

        m = re.match(r"^(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)$", candidate)
        if m:
            try:
                lat, lon = float(m.group(1)), float(m.group(2))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return lat, lon, None
            except ValueError:
                pass

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

    res = _extract_coords_from_url_or_text(text)
    if res is not None:
        lat, lon, extracted_name = res
        if lat is not None and lon is not None:
            rev_name = _reverse_geocode_nominatim(lat, lon)
            final_name = extracted_name or rev_name or f"Field ({lat:.4f}°N, {lon:.4f}°E)"
            return GeocodeResult(lat=round(lat, 4), lon=round(lon, 4), name=final_name)
        elif extracted_name:
            text = extracted_name

    data = _call_nominatim_search(text)
    if data and len(data) > 0:
        item = data[0]
        disp = item.get("display_name", text)
        parts = [p.strip() for p in disp.split(",") if p.strip()]
        short_name = parts[0] if len(parts) == 1 else f"{parts[0]}, {parts[-2] if len(parts) > 2 else parts[-1]}"
        return GeocodeResult(
            lat=round(float(item["lat"]), 4),
            lon=round(float(item["lon"]), 4),
            name=short_name,
        )

    raise HTTPException(status_code=404, detail=f"Indian location or village '{q}' not found")


@app.post("/profile", response_model=FieldProfile)
def build_profile(field: FieldGeometry) -> FieldProfile:
    reg_cfg = region_registry.detect_region_config(field.lat, field.lon)
    matched_id = _match_golden_field(field)
    if matched_id:
        prof = golden_profile(matched_id)
        prof.served_from = "demo_snapshot"
        prof.snapshot_date = "2026-11-10"
    else:
        try:
            prof = profiler.build_profile(field)
            prof.served_from = "live_computation"
            prof.snapshot_date = None
        except Exception as exc:
            log.exception("profile failed")
            raise HTTPException(502, f"Upstream data error: {exc}") from exc

    prof.agro_zone = reg_cfg.agro_zone
    prof.currency = reg_cfg.currency
    prof.currency_symbol = reg_cfg.currency_symbol
    prof.validation_status = reg_cfg.validation_status
    prof.validation_message = reg_cfg.validation_message
    return prof


@app.post("/suitability", response_model=list[SuitabilityItem])
def crop_suitability(req: SuitabilityRequest) -> list[SuitabilityItem]:
    matched_id = _match_golden_field(req.field)
    prof = golden_profile(matched_id) if matched_id else profiler.build_profile(req.field)
    crops = crop_kb.load_crops()
    return [
        SuitabilityItem(name=crops[r.crop_id].name, **r.__dict__)
        for r in suitability.rank_crops(prof, crops, req.constraints)
    ]


def build_objective_dict(
    rot: rotations.Rotation,
    res: evaluate.SimulationResult,
    pm: evaluate.PracticalFarmerMetrics,
    econ_crops: dict[str, dict] | None = None,
    prof: FieldProfile | None = None,
    rot_years: int = 1,
) -> dict[str, float]:
    """Build the 6-objective dictionary for multi-criteria NSGA-II Pareto & Priority ranking.

    Standardized Signs, Units, and Reference Points:
    -------------------------------------------------
    1. 'profit': Effective Median Operating Profit (P50) in ₹/ha/year.
       - Sign: Positive is better.
       - Unit: ₹/ha/year (INR).
       - Scaling: Scaled by procurement assurance factor (0.70 to 1.00) based on
         CACP open-ended MSP procurement (Wheat, Paddy) vs NAFED PSS (Pulses/Oilseeds)
         vs private mandi market realization risk.
    2. 'water_savings': Effective Annual Irrigation Extraction.
       - Sign: Negative irrigation (-mm/year) so that higher (less negative) is better.
       - Unit: -mm/year of net irrigation water pumped.
       - Scaling: Modulated by NASA GRACE groundwater depletion trend (+10%/cm/yr depletion,
         capped at 1.50x urgency multiplier for severely depleting aquifers like Punjab).
    3. 'soil_health': Decadal Soil Health Composite Score.
       - Sign: Higher is better (0 to 100 scale).
       - Unit: Score (0-100).
       - Composition: USDA-NRCS 5-principles (Armor, Min Disturbance, Diversity, Living Roots,
         Organic N) + RothC-lite 26.3 10-yr SOC delta modifier + RUSLE erosion modifier - burn penalty.
    4. 'low_risk': Downside Risk (CVaR-10).
       - Sign: Higher (less negative loss or higher positive income in worst 10% climate years) is better.
       - Unit: ₹/ha/year (INR).
       - Definition: Expected profit in the worst 10% historical/CMIP6 climate years (Conditional Value at Risk at alpha=0.10).
    5. 'low_labour': Negative Annual Labour Cost.
       - Sign: Negative (-₹/ha/year) so that higher (closer to 0) is better.
       - Unit: -₹/ha/year (-INR).
       - Definition: -pm.labor_cost_inr_per_ha. Less negative indicates lower hired and imputed labour requirement.
    6. 'food_security': Nutrition Adequacy Index.
       - Sign: Higher is better (0 to 100 scale).
       - Unit: Score (0-100).
       - Definition: ICMR-NIN (2020) RDA adequacy based on metabolizable food energy (Mcal/ha)
         and dietary protein (kg/ha) per hectare per year.
    """
    mean_irr = float(np.mean(res.irrigation_mm)) if res.irrigation_mm else 0.0
    active_cids = [s.crop_id for s in rot.steps if s.crop_id != "fallow"]
    main_cids = [s.crop_id for s in rot.steps if s.crop_id != "fallow" and s.season_index in (0, 1)]

    # Procurement assurance factor: reflects CACP open-ended MSP procurement (Wheat, Paddy)
    # vs NAFED PSS price support (25% cap) vs open mandi market realization
    proc_factors: list[float] = []
    msp_count = 0
    econ_lookup = econ_crops or {}
    for cid in active_cids:
        c_econ = econ_lookup.get(cid, {})
        p_type = str(c_econ.get("procurement_type", "nafed_pss"))
        m_risk = float(c_econ.get("market_risk", 0.12))
        if p_type == "msp_assured":
            p_base = 1.0
            if cid in main_cids:
                msp_count += 1
        elif p_type == "nafed_pss":
            p_base = 0.85
        else:
            p_base = 0.75
        proc_factors.append(p_base * (1.0 - 0.50 * m_risk))
    proc_assurance = float(np.mean(proc_factors)) if proc_factors else 0.85
    if msp_count >= 2:
        proc_assurance = min(1.0, proc_assurance + 0.10)
    elif msp_count == 1:
        proc_assurance = min(0.96, proc_assurance + 0.04)

    # Median Operating Profit (P50) with price realization floor
    p50 = res.profit_p50
    if p50 >= 0.0:
        effective_profit = p50 * (0.85 + 0.15 * proc_assurance)
    else:
        effective_profit = p50 * (2.0 - proc_assurance)

    # Downside Risk (CVaR-10): worst-10% ensemble climate profit.
    # When CVaR is negative (operating loss), lower procurement assurance deepens the loss
    # rather than artificially reducing it.
    cvar = res.cvar_profit_10
    if cvar >= 0.0:
        effective_cvar = cvar * (0.85 + 0.15 * proc_assurance)
    else:
        effective_cvar = cvar * (2.0 - proc_assurance)

    # Food Security: calculated metabolizable food energy (Mcal/ha) and dietary protein (kg/ha)
    # benchmarked against ICMR-NIN (2020) rural household Recommended Dietary Allowances.
    step_yields = [
        (s.crop_id, float(np.mean(res.yield_t_ha.get(s.crop_id, [0.0]))))
        for s in rot.steps
    ]
    nutr = nutrition.compute_nutrition_yield(step_yields, rotation_years=rot_years)

    # Groundwater trend from NASA GRACE-FO modulates water savings urgency (F-05)
    gw_trend = prof.water.groundwater_trend_cm_per_year if (prof and prof.water) else None
    if gw_trend is not None and gw_trend < -1.0:
        gw_mult = min(1.50, 1.0 + 0.10 * (abs(gw_trend) - 1.0))
    else:
        gw_mult = 1.0
    effective_water_obj = -mean_irr * gw_mult

    return {
        "profit": round(effective_profit, 1),
        "water_savings": round(effective_water_obj, 1),
        "soil_health": res.soil_health_score,
        "low_risk": round(effective_cvar, 1),
        "low_labour": -pm.labor_cost_inr_per_ha,
        "food_security": nutr["food_security_score"],
    }


@app.post("/recommend", response_model=list[StrategyRecommendation])
def recommend(req: RecommendRequest) -> list[StrategyRecommendation]:
    """TASK-A03: profile -> candidates (optimize.rotations) -> simulate (models.*) across
    scenarios (climate.ensembles) -> objectives -> optimize.selection.select_top -> why-cards.
    Returns list[StrategyRecommendation] containing baseline (rank 0) plus top 3 recommendations."""
    # 1. Field Profile & Regional Validation Status
    reg_cfg = region_registry.detect_region_config(req.field.lat, req.field.lon)
    matched_golden_id: str | None = _match_golden_field(req.field)

    if matched_golden_id:
        prof = golden_profile(matched_golden_id)
        prof.served_from = "demo_snapshot"
        prof.snapshot_date = "2026-11-10"
    else:
        try:
            prof = profiler.build_profile(req.field)
            prof.served_from = "live_computation"
            prof.snapshot_date = None
        except Exception as exc:  # noqa: BLE001
            log.warning("Live profiler failed: %s; falling back to regional Indian profile", exc)
            syn_weather = nasa_power.synthetic_daily_weather(req.field.lat, req.field.lon, (1995, 2024))
            c, h, wb = profiler.summarise_climate(syn_weather, req.field.lat, prov_mode="regional_climatology")
            s = profiler.summarise_soil(
                region_registry.get_regional_soil(req.field.lat, req.field.lon),
                prov_mode="regional_climatology",
            )
            prof = FieldProfile(
                field=req.field,
                state=reg_cfg.state,
                climate=c,
                water=WaterSummary(climatic_water_balance_mm=wb),
                soil=s,
                hazards=h,
                currency=reg_cfg.currency,
                currency_symbol=reg_cfg.currency_symbol,
                agro_zone=reg_cfg.agro_zone,
                validation_status=reg_cfg.validation_status,
                validation_message=reg_cfg.validation_message,
                is_fallback=True,
                data_mode="regional_climatology",
                served_from="live_computation",
                snapshot_date=None,
                agro_climatic_notes=profiler.build_notes(
                    c, s, WaterSummary(climatic_water_balance_mm=wb), h, lat=req.field.lat
                ),
            )

    prof.agro_zone = reg_cfg.agro_zone
    prof.currency = reg_cfg.currency
    prof.currency_symbol = reg_cfg.currency_symbol
    prof.validation_status = reg_cfg.validation_status
    prof.validation_message = reg_cfg.validation_message

    if req.soil_health_card is not None:
        prof = profiler.apply_soil_health_card_override(prof, req.soil_health_card)

    # 2. Weather Ensemble (30 years historical or NASA NEX-GDDP-CMIP6 future scenario)
    crops = crop_kb.load_crops()
    weather_df = _load_golden_weather(matched_golden_id) if matched_golden_id else None
    used_fallback_weather = False

    if weather_df is None:
        try:
            req_power = nasa_power.PowerRequest(req.field.lat, req.field.lon, date(1995, 1, 1), date(2024, 12, 31))
            weather_df = nasa_power.fetch_daily(req_power)
        except Exception as exc:  # noqa: BLE001
            log.warning("Live weather fetch failed: %s", exc)

    if weather_df is None or weather_df.empty:
        weather_df = nasa_power.synthetic_daily_weather(req.field.lat, req.field.lon, (1995, 2024))
        used_fallback_weather = True

    rot_years = req.constraints.rotation_years
    if req.climate_scenario == "historical":
        scenario_set, members = ensembles.build_scenario_set(
            kind="historical",
            power_df=weather_df,
            rotation_years=rot_years,
            lat=prof.field.lat,
            lon=prof.field.lon,
        )
    else:
        ssp_part, horizon_part = req.climate_scenario.split("_", 1)
        scenario_set, members = ensembles.build_scenario_set(
            kind="cmip6",
            power_df=weather_df,
            ssp=ssp_part,  # type: ignore[arg-type]
            horizon=horizon_part,  # type: ignore[arg-type]
            rotation_years=rot_years,
            lat=prof.field.lat,
            lon=prof.field.lon,
        )

    if req.drought_shock_pct > 0.0:
        precip_scale = max(0.20, 1.0 - req.drought_shock_pct / 100.0)
        heat_delta = 0.03 * req.drought_shock_pct
        shocked_members: dict[str, pd.DataFrame] = {}
        for m_id, m_df in members.items():
            df_s = m_df.copy()
            if "PRECTOTCORR" in df_s.columns:
                df_s["PRECTOTCORR"] = (df_s["PRECTOTCORR"] * precip_scale).clip(lower=0.0)
            for tcol in ("T2M", "T2M_MAX", "T2M_MIN"):
                if tcol in df_s.columns:
                    df_s[tcol] = df_s[tcol] + heat_delta
            shocked_members[m_id] = df_s
        members = shocked_members

    # 3. Generate candidate rotations pre-screened by suitability (no arbitrary alphabetical [:35] cut!)
    ranked_crops = suitability.rank_crops(prof, crops, req.constraints)
    rank_scores = {r.crop_id: r.score for r in ranked_crops}
    top_ids = {r.crop_id for r in ranked_crops[:10] if r.score >= 0.22}
    # Always include key regional diversification & staple crops if suitable
    is_punjab_belt = reg_cfg.region_id in ("punjab_central", "punjab_southwest", "haryana")
    is_semi_arid_limited = req.constraints.irrigation == "limited" and prof.climate.annual_precip_mm < 520.0
    for key_cid in (
        "wheat",
        "rice_short",
        "rice_dsr",
        "moong",
        "urad",
        "chickpea",
        "mustard",
        "groundnut",
        "maize",
        "soybean",
        "pigeon_pea",
        "sorghum",
        "pearl_millet",
    ):
        if is_punjab_belt and key_cid in ("soybean", "sorghum", "pigeon_pea"):
            continue
        if is_semi_arid_limited and key_cid in ("rice_puddled", "rice_short", "rice_dsr", "basmati"):
            continue
        if rank_scores.get(key_cid, 0.0) >= 0.25:
            top_ids.add(key_cid)
    if is_semi_arid_limited:
        top_ids -= {"rice_puddled", "rice_short", "rice_dsr", "basmati"}
    if req.constraints.irrigation == "none":
        # Strictly rainfed dryland cannot support water-intensive lowland paddy;
        # rainfed wheat is preserved per Central India benchmarks (ICAR / DES).
        top_ids -= {"rice_puddled", "rice_short", "rice_dsr", "basmati"}
    top_ids |= set(req.constraints.must_grow)
    filtered_crops = {cid: crops[cid] for cid in top_ids if cid in crops}

    seasons = rotations.derive_seasons(prof)
    candidate_rotations = rotations.generate_rotations(filtered_crops, req.constraints, seasons=seasons)

    if len(candidate_rotations) > 85:
        candidate_rotations = evaluate.prescreen_rotations_with_surrogate(
            candidate_rotations,
            prof,
            crops=crops,
            max_candidates=85,
            rank_scores=rank_scores,
        )

    # 4. Baseline rotation (current farm practice from satellite history, regional benchmark, or farmer 1-tap override)
    baseline_rot = rotations.derive_baseline_rotation(
        prof, crops, years=rot_years, baseline_override=req.baseline_override
    )
    base_seq = [s.crop_id for s in baseline_rot.steps]
    candidate_rotations = [r for r in candidate_rotations if [s.crop_id for s in r.steps] != base_seq]
    all_rotations = [baseline_rot] + candidate_rotations

    # 5. Evaluate all candidates across weather ensemble (with optional price & fertilizer shocks)
    sim_results = evaluate.evaluate_candidates(
        rotations=all_rotations,
        members=members,
        profile=prof,
        constraints=req.constraints,
        scenario_set_id=scenario_set.id,
        price_shock_pct=req.price_shock_pct,
        fertilizer_shock_pct=req.fertilizer_shock_pct,
    )

    baseline_result = sim_results[0]
    baseline_pm = evaluate.compute_practical_farmer_metrics(
        baseline_rot,
        baseline_result,
        baseline_result,
        crops,
        constraints=req.constraints,
        profile=prof,
        region_id=reg_cfg.region_id,
    )

    # 6. Map to objective scores for Pareto / Priority selection (incorporating procurement_type & market_risk)
    econ_region = reg_cfg.state.lower().replace(" ", "_") if reg_cfg.state else reg_cfg.region_id
    econ_data = economics.load_economics(econ_region)
    econ_crops = econ_data.get("crops", {})
    econ_basis = econ_data.get("economics_basis", "local_verified")

    def _build_objective_dict(
        rot: rotations.Rotation,
        res: evaluate.SimulationResult,
        pm: evaluate.PracticalFarmerMetrics,
    ) -> dict[str, float]:
        return build_objective_dict(
            rot, res, pm, econ_crops=econ_crops, prof=prof, rot_years=rot_years
        )

    cand_obj_dicts: list[dict[str, float]] = [
        _build_objective_dict(baseline_rot, baseline_result, baseline_pm)
    ]
    cand_pms = [baseline_pm]
    labels: list[str] = [baseline_rot.label or baseline_rot.id]

    for r, res in zip(all_rotations[1:], sim_results[1:], strict=False):
        pm = evaluate.compute_practical_farmer_metrics(
            r,
            res,
            baseline_result,
            crops,
            constraints=req.constraints,
            profile=prof,
            region_id=reg_cfg.region_id,
        )
        cand_pms.append(pm)
        obj_dict = _build_objective_dict(r, res, pm)
        cand_obj_dicts.append(obj_dict)
        labels.append(r.label or r.id)

    baseline_obj = cand_obj_dicts[0]

    alt_candidates = selection.annotate_pareto_metrics(cand_obj_dicts[1:])
    alt_labels = labels[1:]
    alt_rotations = all_rotations[1:]
    alt_results = sim_results[1:]
    alt_pms = cand_pms[1:]
    alt_crop_pairs = [
        (r.steps[0].crop_id, r.steps[1].crop_id if len(r.steps) > 1 else "")
        for r in alt_rotations
    ]

    chosen_indices = selection.select_top(
        alt_candidates,
        alt_labels,
        req.priorities,
        k=3,
        crop_pairs=alt_crop_pairs,
    )

    # 7. Assemble recommendations with localized why-cards, practical metrics, narrative, and provenance
    baseline_res_metrics = evaluate.compute_resilience_and_regret(baseline_result)
    rec_is_fallback = prof.is_fallback or used_fallback_weather
    rec_data_mode = "fallback_synthetic" if rec_is_fallback else prof.data_mode

    base_why = why_cards.baseline_why_cards(prof, baseline_rot, language=req.language)

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
        currency=reg_cfg.currency,
        currency_symbol=reg_cfg.currency_symbol,
        practical_metrics=baseline_pm,
        is_fallback=rec_is_fallback,
        data_mode=rec_data_mode,
        validation_status=reg_cfg.validation_status,
        validation_message=reg_cfg.validation_message,
        economics_basis=econ_basis,
        state=prof.state,
        served_from="demo_snapshot" if matched_golden_id else "live_computation",
        snapshot_date="2026-11-10" if matched_golden_id else None,
    )
    baseline_rec.narrative_summary = why_cards.grounded_llm_explain(
        prof, baseline_rec, baseline_rec, language=req.language
    )

    out_recs: list[StrategyRecommendation] = [baseline_rec]

    for rank_idx, idx in enumerate(chosen_indices, start=1):
        chosen_rot = alt_rotations[idx]
        chosen_res = alt_results[idx]
        chosen_obj = alt_candidates[idx]
        chosen_pm = alt_pms[idx]

        base_irr = float(np.mean(baseline_result.irrigation_mm))
        cand_irr = float(np.mean(chosen_res.irrigation_mm))
        irr_change_mm = round(cand_irr - base_irr, 1)
        is_rainfed = 1.0 if base_irr == 0.0 else 0.0
        irr_diff_pct = round((cand_irr - base_irr) / base_irr * 100.0, 1) if base_irr > 0 else 0.0
        profit_diff_pct = (
            round((chosen_res.profit_p50 - baseline_result.profit_p50) / baseline_result.profit_p50 * 100.0, 1)
            if baseline_result.profit_p50 > 0
            else 0.0
        )
        profit_change_abs = round(chosen_res.profit_p50 - baseline_result.profit_p50, 0)
        soil_diff = round(chosen_res.soil_health_score - baseline_result.soil_health_score, 1)

        cand_res_metrics = evaluate.compute_resilience_and_regret(chosen_res)

        vs_base = {
            "irrigation_change_pct": irr_diff_pct,
            "irrigation_change_mm": irr_change_mm,
            "is_rainfed_baseline": is_rainfed,
            "profit_change_pct": profit_diff_pct,
            "profit_change_abs": profit_change_abs,
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
            currency=reg_cfg.currency,
            currency_symbol=reg_cfg.currency_symbol,
            practical_metrics=chosen_pm,
            is_fallback=rec_is_fallback,
            data_mode=rec_data_mode,
            validation_status=reg_cfg.validation_status,
            validation_message=reg_cfg.validation_message,
            economics_basis=econ_basis,
            state=prof.state,
            served_from="demo_snapshot" if matched_golden_id else "live_computation",
            snapshot_date="2026-11-10" if matched_golden_id else None,
        )
        cards, provs = why_cards.why_cards(prof, rec, baseline_rec, language=req.language)
        if scenario_set.kind == "cmip6":
            provs = list(provs) + list(scenario_set.provenance)
        rec.why = cards
        rec.provenance = provs
        rec.narrative_summary = why_cards.grounded_llm_explain(
            prof, rec, baseline_rec, language=req.language
        )
        out_recs.append(rec)

    return out_recs


# ---------------------------------------------------------------------------
# Async Recommend Jobs (TASK-H02)
# ---------------------------------------------------------------------------
_RECOMMEND_JOBS: dict[str, dict] = {}


def _async_recommend_worker(job_id: str, req: RecommendRequest) -> None:
    try:
        _RECOMMEND_JOBS[job_id]["status"] = "running"
        _RECOMMEND_JOBS[job_id]["step"] = "evaluating"
        _RECOMMEND_JOBS[job_id]["progress"] = 0.3
        recs = recommend(req)
        _RECOMMEND_JOBS[job_id]["status"] = "completed"
        _RECOMMEND_JOBS[job_id]["step"] = "done"
        _RECOMMEND_JOBS[job_id]["progress"] = 1.0
        _RECOMMEND_JOBS[job_id]["result"] = [r.model_dump() for r in recs]
        _RECOMMEND_JOBS[job_id]["error"] = None
    except Exception as exc:
        log.exception("Async recommend worker error for job %s", job_id)
        _RECOMMEND_JOBS[job_id]["status"] = "failed"
        _RECOMMEND_JOBS[job_id]["step"] = "failed"
        _RECOMMEND_JOBS[job_id]["progress"] = 1.0
        _RECOMMEND_JOBS[job_id]["result"] = None
        _RECOMMEND_JOBS[job_id]["error"] = str(exc)


@app.post("/recommend/async")
def recommend_async(req: RecommendRequest) -> dict:
    """Submit an asynchronous crop-rotation recommendation simulation job (TASK-H02)."""
    job_id = str(uuid.uuid4())
    _RECOMMEND_JOBS[job_id] = {
        "job_id": job_id,
        "status": "running",
        "progress": 0.1,
        "step": "profile",
        "result": None,
        "error": None,
        "created_at": time.time(),
    }
    thread = threading.Thread(target=_async_recommend_worker, args=(job_id, req), daemon=True)
    thread.start()
    return {
        "job_id": job_id,
        "status": "running",
        "progress": 0.1,
        "step": "profile",
    }


@app.get("/recommend/jobs/{job_id}")
def get_recommend_job(job_id: str) -> dict:
    """Poll status and retrieve results of an asynchronous recommendation job (TASK-H02)."""
    job = _RECOMMEND_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job
