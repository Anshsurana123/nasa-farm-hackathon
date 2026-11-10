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
import urllib.parse
from datetime import date
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from terraloop_engine import crop_kb, profiler, region_registry, suitability
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


def _match_golden_field(field: FieldGeometry, radius: float = 0.15) -> str | None:
    """Match a field geometry to a precomputed golden benchmark field by ID, name, or spatial proximity (<0.15°)."""
    f_name = (field.name or "").lower()
    matches = [
        f for f in _golden_index()
        if (field.id and f["id"] == field.id)
        or (f_name and f["id"] in f_name)
        or (abs(f["lat"] - field.lat) < radius and abs(f["lon"] - field.lon) < radius)
    ]
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
        if not prof.agro_zone:
            prof.agro_zone = economics.detect_agro_zone(prof.field.lat, prof.field.lon)
        return prof
    match = next((f for f in _golden_index() if f["id"] == field_id), None)
    if not match:
        raise HTTPException(404, f"Unknown golden field '{field_id}'")
    return profiler.build_profile(FieldGeometry(lat=match["lat"], lon=match["lon"], name=match["name"]))


@app.get("/golden/{field_id}/recommendations", response_model=list[StrategyRecommendation])
def golden_recommendations(field_id: str) -> list[StrategyRecommendation]:
    path = GOLDEN_DIR / field_id / "recommendations.json"
    if path.exists():
        raw_list = json.loads(path.read_text(encoding="utf-8"))
        return [StrategyRecommendation.model_validate(item) for item in raw_list]
    match = next((f for f in _golden_index() if f["id"] == field_id), None)
    if not match:
        raise HTTPException(404, f"Unknown golden field '{field_id}'")
    return recommend(
        RecommendRequest(field=FieldGeometry(lat=match["lat"], lon=match["lon"], name=match["name"]))
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
    except Exception:  # noqa: BLE001, S110
        pass
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

    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "TerraLoop-SpaceApps/1.0"}
    params = {"q": text, "format": "json", "limit": 1, "countrycodes": "in"}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
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
    except Exception as exc:  # noqa: BLE001
        log.warning("Nominatim geocoding failed for '%s': %s", text, exc)

    raise HTTPException(status_code=404, detail=f"Indian location or village '{q}' not found")


@app.post("/profile", response_model=FieldProfile)
def build_profile(field: FieldGeometry) -> FieldProfile:
    reg_cfg = region_registry.detect_region_config(field.lat, field.lon)
    matched_id = _match_golden_field(field, radius=0.15)
    if matched_id:
        prof = golden_profile(matched_id)
    else:
        try:
            prof = profiler.build_profile(field)
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
    matched_id = _match_golden_field(req.field, radius=0.15)
    prof = golden_profile(matched_id) if matched_id else profiler.build_profile(req.field)
    crops = crop_kb.load_crops()
    return [
        SuitabilityItem(name=crops[r.crop_id].name, **r.__dict__)
        for r in suitability.rank_crops(prof, crops, req.constraints)
    ]


@app.post("/recommend", response_model=list[StrategyRecommendation])
def recommend(req: RecommendRequest) -> list[StrategyRecommendation]:
    """TASK-A03: profile -> candidates (optimize.rotations) -> simulate (models.*) across
    scenarios (climate.ensembles) -> objectives -> optimize.selection.select_top -> why-cards.
    Returns list[StrategyRecommendation] containing baseline (rank 0) plus top 3 recommendations."""
    # 1. Field Profile & Regional Validation Status
    reg_cfg = region_registry.detect_region_config(req.field.lat, req.field.lon)
    matched_golden_id: str | None = _match_golden_field(req.field, radius=0.15)

    if matched_golden_id:
        prof = golden_profile(matched_golden_id)
    else:
        try:
            prof = profiler.build_profile(req.field)
        except Exception as exc:  # noqa: BLE001
            log.warning("Live profiler failed: %s; falling back to regional Indian profile", exc)
            syn_weather = nasa_power.synthetic_daily_weather(req.field.lat, req.field.lon, (1995, 2024))
            c, h, wb = profiler.summarise_climate(syn_weather, req.field.lat, prov_mode="regional_climatology")
            s = profiler.summarise_soil(
                profiler.regional_indian_soil_fallback(req.field.lat, req.field.lon),
                prov_mode="regional_climatology",
            )
            prof = FieldProfile(
                field=req.field,
                climate=c,
                water=WaterSummary(climatic_water_balance_mm=wb),
                soil=s,
                hazards=h,
                currency=reg_cfg.currency,
                currency_symbol=reg_cfg.currency_symbol,
                agro_zone=reg_cfg.agro_zone,
                is_fallback=True,
                data_mode="fallback_synthetic",
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

    if len(candidate_rotations) > 75:
        candidate_rotations = evaluate.prescreen_rotations_with_surrogate(
            candidate_rotations,
            prof,
            crops=crops,
            max_candidates=75,
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
    econ_crops = economics.load_economics("punjab").get("crops", {})

    def _build_objective_dict(
        rot: rotations.Rotation,
        res: evaluate.SimulationResult,
        pm: evaluate.PracticalFarmerMetrics,
    ) -> dict[str, float]:
        mean_irr = float(np.mean(res.irrigation_mm)) if res.irrigation_mm else 0.0
        active_cids = [s.crop_id for s in rot.steps if s.crop_id != "fallow"]
        main_cids = [s.crop_id for s in rot.steps if s.crop_id != "fallow" and s.season_index in (0, 1)]

        # Procurement assurance factor: reflects CACP open-ended MSP procurement (Wheat, Paddy)
        # vs NAFED PSS price support (25% cap) vs open mandi market realization
        proc_factors: list[float] = []
        msp_count = 0
        for cid in active_cids:
            c_econ = econ_crops.get(cid, {})
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
        gw_trend = prof.water.groundwater_trend_cm_per_year
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
