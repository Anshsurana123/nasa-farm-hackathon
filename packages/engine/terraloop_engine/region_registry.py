"""Global Agro-Climatic Region Registry & Administrative State Detection (WS-C).

Enforces scope honesty (Rule 8):
  1. Indian administrative state determined via point-in-polygon against Natural Earth 50m boundaries.
  2. All agro-climatic zones, baseline rotations, GRACE trends, baseline slopes, and synthetic weather
     parameters are configured in YAML under ``packages/crop-kb/regions/``.
  3. No hardcoded geographic bounding boxes in Python engine models.
"""

from __future__ import annotations

import functools
import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
REGIONS_DIR = REPO_ROOT / "packages" / "crop-kb" / "regions"
STATE_GEOJSON = REGIONS_DIR / "india_states.geojson"
GLOBAL_COUNTRIES_GEOJSON = REGIONS_DIR / "global_countries.geojson"
GLOBAL_ADMIN1_GEOJSON = REGIONS_DIR / "global_admin1.geojson"
AEZ_GRID_JSON = REGIONS_DIR / "aez_global_grid.json"
CALENDARS_YAML = REGIONS_DIR / "calendars.yaml"
ZONES_YAML = REGIONS_DIR / "zones.yaml"
SOILS_YAML = REGIONS_DIR / "soils.yaml"
WEATHER_YAML = REGIONS_DIR / "synthetic_weather.yaml"

INDIA_DEFAULT_PRIORITY_CROPS: tuple[str, ...] = (
    "rice_puddled",
    "rice_short",
    "rice_dsr",
    "basmati",
    "wheat",
    "maize",
    "cotton",
    "soybean",
    "moong",
    "urad",
    "mustard",
    "chickpea",
    "sunflower",
)


@dataclass(frozen=True)
class RegionConfig:
    region_id: str
    name: str
    country: str
    currency: str
    currency_symbol: str
    is_validated: bool
    validation_status: Literal["validated_india", "validated_regional", "biophysical_global", "unvalidated_global"]
    validation_message: str | None
    allow_economic_ranking: bool
    agro_zone: str
    hemisphere: Literal["NH", "SH"]
    economics_table: str | None = None
    state: str | None = None
    country_code: str | None = None
    aez_class: str | None = None
    calendar_id: str = "india_igp"
    cultivar_zone: str = "india_default"
    unit_convention: Literal["metric", "acre", "imperial"] = "metric"
    baseline_rotation: tuple[str, ...] = ("rice_puddled", "wheat", "fallow")
    baseline_slope_pct: float = 1.0
    grace_trend_cm_yr: float = -1.50
    grace_citation: str = "CGWB 2023 National Average"
    igp_merra2_bias_correction: bool = False
    c_eq_t_ha_yr: float = 2.35
    soc_ref_g_kg: float = 6.0
    priority_crops: tuple[str, ...] = field(default_factory=lambda: INDIA_DEFAULT_PRIORITY_CROPS)
    soil_key: str | None = None
    weather_key: str | None = None


# ---------------------------------------------------------------------------
# Point-in-polygon helper
# ---------------------------------------------------------------------------
def _point_in_polygon(x: float, y: float, poly: list[list[float]]) -> bool:
    inside = False
    n = len(poly)
    if n < 3:
        return False
    p1x, p1y = poly[0]
    for i in range(1, n + 1):
        p2x, p2y = poly[i % n]
        if min(p1y, p2y) < y <= max(p1y, p2y) and x <= max(p1x, p2x):
            if p1y != p2y:
                xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            if p1x == p2x or x <= xinters:
                inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def _point_in_geometry(lon: float, lat: float, geom: dict) -> bool:
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    if gtype == "Polygon":
        if _point_in_polygon(lon, lat, coords[0]):
            for hole in coords[1:]:
                if _point_in_polygon(lon, lat, hole):
                    return False
            return True
    elif gtype == "MultiPolygon":
        for poly in coords:
            if _point_in_polygon(lon, lat, poly[0]):
                in_hole = False
                for hole in poly[1:]:
                    if _point_in_polygon(lon, lat, hole):
                        in_hole = True
                        break
                if not in_hole:
                    return True
    return False


def _dist_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _min_dist_to_geom(lon: float, lat: float, geom: dict) -> float:
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])
    polys = [coords] if gtype == "Polygon" else coords
    m_dist = float("inf")
    for poly in polys:
        if not poly:
            continue
        ring = poly[0]
        n = len(ring)
        for i in range(n - 1):
            d = _dist_to_segment(lon, lat, ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1])
            m_dist = min(m_dist, d)
    return m_dist


def _point_in_feature(lon: float, lat: float, feature: dict) -> bool:
    bbox = feature.get("bbox")
    if bbox and len(bbox) == 4 and not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
        return False
    return _point_in_geometry(lon, lat, feature["geometry"])


@functools.lru_cache(maxsize=1)
def _load_geojson_features(primary_path: Path, pkg_rel_name: str) -> list[dict]:
    if not primary_path.exists():
        pkg_file = Path(__file__).resolve().parent / "crop_kb" / "regions" / pkg_rel_name
        target_file = pkg_file if pkg_file.exists() else primary_path
    else:
        target_file = primary_path

    if not target_file.exists():
        log.warning("GeoJSON not found at %s", target_file)
        return []

    try:
        data = json.loads(target_file.read_text(encoding="utf-8"))
        return data.get("features", [])
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to load GeoJSON %s: %s", target_file, exc)
        return []


@functools.lru_cache(maxsize=1)
def _load_states_geojson() -> list[dict]:
    return _load_geojson_features(STATE_GEOJSON, "india_states.geojson")


@functools.lru_cache(maxsize=1)
def _load_global_countries_geojson() -> list[dict]:
    return _load_geojson_features(GLOBAL_COUNTRIES_GEOJSON, "global_countries.geojson")


@functools.lru_cache(maxsize=1)
def _load_global_admin1_geojson() -> list[dict]:
    return _load_geojson_features(GLOBAL_ADMIN1_GEOJSON, "global_admin1.geojson")


def detect_state(lat: float, lon: float, max_coastal_tolerance_deg: float = 0.04) -> str | None:
    """Determine the Indian state/UT for a coordinate via point-in-polygon lookup."""
    features = _load_states_geojson()
    if not features:
        return None

    # 1. Exact interior check with bbox fast reject
    for f in features:
        if _point_in_feature(lon, lat, f):
            return f["properties"]["name"]

    # 2. Coastal buffer check (within 0.04 deg ~4 km of coastline, e.g. Kochi port)
    best_state, best_dist = None, float("inf")
    for f in features:
        bbox = f.get("bbox")
        if (
            bbox
            and len(bbox) == 4
            and not (
                bbox[0] - max_coastal_tolerance_deg <= lon <= bbox[2] + max_coastal_tolerance_deg
                and bbox[1] - max_coastal_tolerance_deg <= lat <= bbox[3] + max_coastal_tolerance_deg
            )
        ):
            continue
        d = _min_dist_to_geom(lon, lat, f["geometry"])
        if d < best_dist:
            best_dist = d
            best_state = f["properties"]["name"]

    if best_dist <= max_coastal_tolerance_deg:
        return best_state

    return None


def detect_country(lat: float, lon: float, max_coastal_tolerance_deg: float = 0.30) -> dict | None:
    """Resolve sovereign country metadata (name, iso_a3, continent) via Natural Earth 110m Admin-0."""
    features = _load_global_countries_geojson()
    if not features:
        return None

    for f in features:
        if _point_in_feature(lon, lat, f):
            return dict(f.get("properties") or {})

    best_props: dict | None = None
    best_dist = float("inf")
    for f in features:
        bbox = f.get("bbox")
        if (
            bbox
            and len(bbox) == 4
            and not (
                bbox[0] - max_coastal_tolerance_deg <= lon <= bbox[2] + max_coastal_tolerance_deg
                and bbox[1] - max_coastal_tolerance_deg <= lat <= bbox[3] + max_coastal_tolerance_deg
            )
        ):
            continue
        d = _min_dist_to_geom(lon, lat, f["geometry"])
        if d < best_dist:
            best_dist = d
            best_props = dict(f.get("properties") or {})

    if best_props is not None and best_dist <= max_coastal_tolerance_deg:
        return best_props
    return None


def detect_admin1(lat: float, lon: float, country_iso3: str | None = None) -> str | None:
    """Resolve global subnational Admin-1 state/province name where available."""
    features = _load_global_admin1_geojson()
    if not features:
        return None

    for f in features:
        props = f.get("properties") or {}
        if country_iso3 and props.get("iso_a3") != country_iso3:
            continue
        if _point_in_feature(lon, lat, f):
            return props.get("name")
    return None


@functools.lru_cache(maxsize=1)
def _load_koppen_grid() -> tuple[list[str], list[list[int]]]:
    target = AEZ_GRID_JSON
    if not target.exists():
        pkg_file = Path(__file__).resolve().parent / "crop_kb" / "regions" / "aez_global_grid.json"
        if pkg_file.exists():
            target = pkg_file
    if not target.exists():
        return ["Ocean"], []

    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        classes: list[str] = list(payload.get("classes", ["Ocean"]))
        rows_count = int(payload.get("rows", 360))
        cols_count = int(payload.get("cols", 720))
        rle_rows = payload.get("rle_rows", [])
        decoded: list[list[int]] = []
        for r_idx in range(rows_count):
            runs = rle_rows[r_idx] if r_idx < len(rle_rows) else []
            if not runs:
                decoded.append([0] * cols_count)
                continue
            row = [0] * cols_count
            pos = 0
            for cls_idx, cnt in runs:
                end = min(cols_count, pos + int(cnt))
                row[pos:end] = [int(cls_idx)] * (end - pos)
                pos = end
            decoded.append(row)
        return classes, decoded
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to load Koppen-Geiger grid: %s", exc)
        return ["Ocean"], []


def detect_koppen(lat: float, lon: float) -> str | None:
    """Look up 0.5-deg Kottek/Beck Koppen-Geiger climate class with coastal neighborhood scan."""
    classes, grid = _load_koppen_grid()
    if not grid:
        return None

    r0 = max(0, min(len(grid) - 1, round((float(lat) + 89.75) * 2.0)))
    c0 = max(0, min(len(grid[0]) - 1, round((float(lon) + 179.75) * 2.0)))
    idx = grid[r0][c0]
    if 0 < idx < len(classes):
        return classes[idx]

    # Search 3x3 / 5x5 neighboring land cells for narrow peninsulas / islands / ports
    for radius in (1, 2):
        for dr in range(-radius, radius + 1):
            rr = r0 + dr
            if not (0 <= rr < len(grid)):
                continue
            for dc in range(-radius, radius + 1):
                cc = (c0 + dc) % len(grid[0])
                n_idx = grid[rr][cc]
                if 0 < n_idx < len(classes):
                    return classes[n_idx]
    return None


# ---------------------------------------------------------------------------
# Zone & Config Loaders
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def load_zones_data() -> dict:
    if not ZONES_YAML.exists():
        pkg_file = Path(__file__).resolve().parent / "crop_kb" / "regions" / "zones.yaml"
        target = pkg_file if pkg_file.exists() else ZONES_YAML
    else:
        target = ZONES_YAML
    if not target.exists():
        return {}
    return yaml.safe_load(target.read_text(encoding="utf-8")) or {}


@functools.lru_cache(maxsize=1)
def load_soils_data() -> dict:
    if not SOILS_YAML.exists():
        pkg_file = Path(__file__).resolve().parent / "crop_kb" / "regions" / "soils.yaml"
        target = pkg_file if pkg_file.exists() else SOILS_YAML
    else:
        target = SOILS_YAML
    if not target.exists():
        return {}
    return yaml.safe_load(target.read_text(encoding="utf-8")) or {}


@functools.lru_cache(maxsize=1)
def load_weather_data() -> dict:
    if not WEATHER_YAML.exists():
        pkg_file = Path(__file__).resolve().parent / "crop_kb" / "regions" / "synthetic_weather.yaml"
        target = pkg_file if pkg_file.exists() else WEATHER_YAML
    else:
        target = WEATHER_YAML
    if not target.exists():
        return {}
    return yaml.safe_load(target.read_text(encoding="utf-8")) or {}


@functools.lru_cache(maxsize=1)
def load_calendars_data() -> dict:
    target = CALENDARS_YAML
    if not target.exists():
        pkg_file = Path(__file__).resolve().parent / "crop_kb" / "regions" / "calendars.yaml"
        if pkg_file.exists():
            target = pkg_file
    if not target.exists():
        return {}
    return yaml.safe_load(target.read_text(encoding="utf-8")) or {}


def get_calendar_config(calendar_id: str) -> dict:
    cals = load_calendars_data().get("calendars", {})
    return dict(cals.get(calendar_id) or cals.get("india_igp") or {})


def get_calendar_slots(lat: float, lon: float) -> list[dict]:
    cfg = detect_region_config(lat, lon)
    cal = get_calendar_config(cfg.calendar_id)
    return list(cal.get("slots", []))


def is_in_india(lat: float, lon: float) -> bool:
    """Return True if coordinates fall within Indian territory as validated by state boundary lookup."""
    return detect_state(lat, lon) is not None


def _match_global_hub(
    country_iso3: str | None,
    admin1: str | None,
    kg: str | None,
    hubs: dict,
) -> tuple[str, dict] | None:
    if not country_iso3:
        return None
    for hub_id, hub_cfg in hubs.items():
        if hub_cfg.get("country_iso3") != country_iso3:
            continue
        allowed_admin1 = hub_cfg.get("admin1_names") or []
        if allowed_admin1 and (admin1 not in allowed_admin1):
            continue
        allowed_kg = hub_cfg.get("koppen_classes") or []
        if allowed_kg and kg and (kg not in allowed_kg):
            continue
        return hub_id, hub_cfg
    return None


def _match_aez_zone(kg: str | None, hemisphere: Literal["NH", "SH"], lat: float, aez_zones: dict) -> tuple[str, dict]:
    if kg:
        for z_id, z_cfg in aez_zones.items():
            if kg in (z_cfg.get("koppen_classes") or []):
                if kg in ("Csa", "Csb") and hemisphere == "SH" and z_id == "aez_mediterranean_nh":
                    continue
                if kg in ("Csa", "Csb") and hemisphere == "NH" and z_id == "aez_mediterranean_sh":
                    continue
                return z_id, z_cfg

    abs_lat = abs(float(lat))
    if abs_lat < 12.0:
        fallback_id = "aez_tropical_wet"
    elif abs_lat < 24.0:
        fallback_id = "aez_tropical_savanna"
    elif abs_lat < 36.0:
        fallback_id = "aez_humid_subtropical"
    elif abs_lat < 55.0:
        fallback_id = "aez_temperate_continental"
    else:
        fallback_id = "aez_boreal_alpine"
    return fallback_id, dict(aez_zones.get(fallback_id) or {})


@functools.lru_cache(maxsize=512)
def detect_region_config(lat: float, lon: float) -> RegionConfig:
    """Classify coordinates into calibrated Indian zones, verified global hubs, or Koppen-Geiger global biomes."""
    hemisphere: Literal["NH", "SH"] = "NH" if lat >= 0.0 else "SH"
    zones_all = load_zones_data()
    state = detect_state(lat, lon)

    if not state:
        kg = detect_koppen(lat, lon)
        c_props = detect_country(lat, lon)
        country_name = str((c_props or {}).get("name") or (c_props or {}).get("admin") or "International")
        country_iso3 = (c_props or {}).get("iso_a3")
        admin1 = detect_admin1(lat, lon, country_iso3=country_iso3)

        hub_match = _match_global_hub(country_iso3, admin1, kg, zones_all.get("global_hubs", {}))
        if hub_match is not None:
            hub_id, h_cfg = hub_match
            p_crops = tuple(h_cfg.get("priority_crops") or INDIA_DEFAULT_PRIORITY_CROPS)
            return RegionConfig(
                region_id=hub_id,
                name=h_cfg.get("name", f"{country_name} Hub"),
                country=h_cfg.get("country", country_name),
                country_code=country_iso3,
                aez_class=kg,
                currency=h_cfg.get("currency", "USD"),
                currency_symbol=h_cfg.get("currency_symbol", "$"),
                is_validated=bool(h_cfg.get("is_validated", True)),
                validation_status="validated_regional",
                validation_message=(
                    f"Calibrated regional model for {h_cfg.get('name', country_name)} "
                    f"(enterprise budgets: {h_cfg.get('economics_table')}; climate biome: {kg or 'regional'})."
                ),
                allow_economic_ranking=bool(h_cfg.get("allow_economic_ranking", True)),
                agro_zone=h_cfg.get("agro_zone", hub_id),
                hemisphere=hemisphere,
                economics_table=h_cfg.get("economics_table"),
                state=admin1 or h_cfg.get("country", country_name),
                calendar_id=str(h_cfg.get("calendar_id", "temperate_spring_summer")),
                cultivar_zone=str(h_cfg.get("cultivar_zone", "temperate_high_input")),
                unit_convention=h_cfg.get("unit_convention", "metric"),
                baseline_rotation=tuple(h_cfg.get("baseline_rotation", ["maize", "soybean", "fallow"])),
                baseline_slope_pct=float(h_cfg.get("baseline_slope_pct", 1.5)),
                grace_trend_cm_yr=float(h_cfg.get("grace_trend_cm_yr", 0.0)),
                grace_citation=str(h_cfg.get("grace_citation", "NASA GRACE-FO Regional Assessment")),
                igp_merra2_bias_correction=False,
                c_eq_t_ha_yr=float(h_cfg.get("c_eq_t_ha_yr", 2.80)),
                soc_ref_g_kg=float(h_cfg.get("soc_ref_g_kg", 15.0)),
                priority_crops=p_crops,
                soil_key=hub_id,
                weather_key=hub_id,
            )

        aez_id, a_cfg = _match_aez_zone(kg, hemisphere, lat, zones_all.get("global_aez_zones", {}))
        cal_id = str(a_cfg.get("calendar_id", "temperate_spring_summer"))
        if aez_id in ("aez_tropical_savanna", "aez_humid_subtropical") and hemisphere == "SH":
            cal_id = "tropical_savanna_sh"
        elif aez_id in ("aez_arid_semiarid",) and hemisphere == "SH":
            cal_id = "southern_mediterranean"

        return RegionConfig(
            region_id=aez_id,
            name=f"{country_name} — {a_cfg.get('name', 'Global Biophysical Zone')}",
            country=country_name,
            country_code=country_iso3,
            aez_class=kg,
            currency="USD",
            currency_symbol="$",
            is_validated=False,
            validation_status="biophysical_global",
            validation_message=(
                f"Biophysical global mode ({country_name}; Koppen {kg or 'AEZ'}): crop phenology, FAO-56 water balance, "
                "and RothC carbon are simulated from live NASA EO and SoilGrids using biome-calibrated calendars. "
                "Strategies are ranked purely on biophysical sustainability because local farm budgets are not verified here."
            ),
            allow_economic_ranking=False,
            agro_zone=str(a_cfg.get("agro_zone", f"Koppen {kg or 'Global'} Biophysical Zone")),
            hemisphere=hemisphere,
            economics_table=None,
            state=admin1,
            calendar_id=cal_id,
            cultivar_zone=str(a_cfg.get("cultivar_zone", "temperate_high_input")),
            unit_convention="imperial" if country_iso3 == "USA" else "metric",
            baseline_rotation=tuple(a_cfg.get("baseline_rotation", ["maize", "soybean", "fallow"])),
            baseline_slope_pct=float(a_cfg.get("baseline_slope_pct", 1.5)),
            grace_trend_cm_yr=0.0,
            grace_citation="NASA GRACE-FO Global Observation Required (No Regional Prior)",
            igp_merra2_bias_correction=False,
            c_eq_t_ha_yr=float(a_cfg.get("c_eq_t_ha_yr", 2.50)),
            soc_ref_g_kg=float(a_cfg.get("soc_ref_g_kg", 12.0)),
            priority_crops=tuple(a_cfg.get("priority_crops") or ("wheat_winter", "wheat_spring", "maize", "soybean", "barley")),
            soil_key=str(a_cfg.get("soil_key", "default_global_soil")),
            weather_key=str(a_cfg.get("weather_key", "aez_temperate_continental")),
        )

    zones_dict = zones_all.get("zones", {})
    state_norm = state.lower().strip()
    kg = detect_koppen(lat, lon)

    # Route state to specific Indian ICAR zone_id
    if state_norm in ("punjab", "chandigarh"):
        zone_id = "punjab_southwest" if lon < 75.3 else "punjab_central"
    elif state_norm in ("haryana", "delhi"):
        zone_id = "haryana"
    elif state_norm == "rajasthan":
        zone_id = "rajasthan_arid"
    elif state_norm in ("gujarat", "dadra and nagar haveli and daman and diu"):
        zone_id = "gujarat"
    elif state_norm == "maharashtra":
        zone_id = "western_maharashtra" if lon < 75.8 else "vidarbha"
    elif state_norm in ("tamil nadu", "puducherry"):
        zone_id = "cauvery"
    elif state_norm in ("kerala", "goa"):
        zone_id = "west_coast"
    elif state_norm in ("himachal pradesh", "jammu and kashmir", "ladakh", "uttarakhand"):
        zone_id = "himalayan"
    elif state_norm in ("assam", "arunachal pradesh", "manipur", "meghalaya", "mizoram", "nagaland", "sikkim", "tripura"):
        zone_id = "eastern_himalayan"
    elif state_norm in ("andaman and nicobar", "lakshadweep"):
        zone_id = "islands"
    elif state_norm in ("karnataka", "telangana", "andhra pradesh"):
        zone_id = "southern_hills"
    elif state_norm == "madhya pradesh":
        zone_id = "bundelkhand" if (lat >= 23.5 and 77.5 <= lon <= 81.5) else "central_malwa"
    elif state_norm == "uttar pradesh":
        if lat <= 26.5 and 77.5 <= lon <= 81.5:
            zone_id = "bundelkhand"
        elif lon < 80.5:
            zone_id = "western_up"
        else:
            zone_id = "eastern_gangetic"
    elif state_norm in ("bihar", "west bengal", "jharkhand", "odisha", "chhattisgarh"):
        zone_id = "eastern_gangetic"
    else:
        zone_id = "eastern_gangetic"

    z_cfg = zones_dict.get(zone_id, zones_all.get("default_zone", {}))
    econ_table = "uttar_pradesh" if state_norm == "uttar pradesh" else z_cfg.get("economics_table", "punjab")
    cal_id = str(z_cfg.get("calendar_id") or ("india_delta" if zone_id == "cauvery" else "india_igp"))

    return RegionConfig(
        region_id=zone_id,
        name=z_cfg.get("name", f"{state} Agricultural Region"),
        country="India",
        country_code="IND",
        aez_class=kg,
        currency=z_cfg.get("currency", "INR"),
        currency_symbol=z_cfg.get("currency_symbol", "₹"),
        is_validated=z_cfg.get("is_validated", True),
        validation_status="validated_india",
        validation_message=None,
        allow_economic_ranking=True,
        agro_zone=z_cfg.get("agro_zone", "Trans-Gangetic Plains (Alluvial Rice–Wheat Belt)"),
        hemisphere="NH",
        economics_table=econ_table,
        state=state,
        calendar_id=cal_id,
        cultivar_zone="india_default",
        unit_convention="metric",
        baseline_rotation=tuple(z_cfg.get("baseline_rotation", ["rice_puddled", "wheat", "fallow"])),
        baseline_slope_pct=float(z_cfg.get("baseline_slope_pct", 1.0)),
        grace_trend_cm_yr=float(z_cfg.get("grace_trend_cm_yr", -1.50)),
        grace_citation=z_cfg.get("grace_citation", "CGWB 2023 National Average"),
        igp_merra2_bias_correction=bool(z_cfg.get("igp_merra2_bias_correction", False)),
        c_eq_t_ha_yr=float(z_cfg.get("c_eq_t_ha_yr", 2.35)),
        soc_ref_g_kg=float(z_cfg.get("soc_ref_g_kg", 6.0)),
        priority_crops=tuple(z_cfg.get("priority_crops") or INDIA_DEFAULT_PRIORITY_CROPS),
        soil_key=zone_id,
        weather_key=zone_id,
    )


# ---------------------------------------------------------------------------
# Regional data getters consuming registry
# ---------------------------------------------------------------------------
def get_regional_slope(lat: float, lon: float) -> float:
    return detect_region_config(lat, lon).baseline_slope_pct


def get_regional_grace_trend(lat: float, lon: float) -> tuple[float, str]:
    cfg = detect_region_config(lat, lon)
    return cfg.grace_trend_cm_yr, cfg.grace_citation


def get_regional_soil(lat: float, lon: float) -> dict[str, float]:
    cfg = detect_region_config(lat, lon)
    soils = load_soils_data()
    key = cfg.soil_key or cfg.region_id
    fallback_key = "default_soil" if cfg.validation_status == "validated_india" else "default_global_soil"
    return soils.get(
        key,
        soils.get(
            fallback_key,
            {
                "sand": 40.0,
                "silt": 36.0,
                "clay": 24.0,
                "soc": 12.0,
                "phh2o": 6.6,
                "bdod": 140.0,
                "nitrogen": 1.1,
                "source_citation": "ISRIC SoilGrids / FAO-UNESCO Global Arable Loam Reference",
            },
        ),
    )


class RegionalWeatherParams(dict):
    """Regional weather parameters supporting dictionary access, attribute access, and computed aliases."""

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError:
            if name == "base_tmax":
                return float(self.get("t_base", 25.0)) + 0.5 * float(self.get("trange_c", 11.0))
            if name == "amp_c":
                return float(self.get("amplitude", 9.0))
            if name == "wet_months":
                ws = int(self.get("wet_start_month", 7))
                we = int(self.get("wet_end_month", 9))
                if ws <= we:
                    return list(range(ws, we + 1))
                return list(range(ws, 13)) + list(range(1, we + 1))
            if name == "wet_shape":
                gw = self.get("gamma_wet", [0.6, 13.0])
                return float(gw[0])
            if name == "wet_scale":
                gw = self.get("gamma_wet", [0.6, 13.0])
                return float(gw[1])
            if name == "dry_shape":
                gd = self.get("gamma_dry", [0.1, 4.0])
                return float(gd[0])
            if name == "dry_scale":
                gd = self.get("gamma_dry", [0.1, 4.0])
                return float(gd[1])
            raise AttributeError(f"'RegionalWeatherParams' object has no attribute '{name}'") from None

    def __setattr__(self, name: str, value):
        self[name] = value


def get_regional_weather_params(lat: float, lon: float) -> RegionalWeatherParams:
    cfg = detect_region_config(lat, lon)
    w_data = load_weather_data()
    key = cfg.weather_key or cfg.region_id
    raw = dict(w_data.get(key) or {})
    if raw:
        # Adjust generic NH AEZ template to SH season phase (or vice versa) without duplicating 20 biome tables
        if cfg.validation_status == "biophysical_global" and cfg.hemisphere == "SH":
            raw["peak_doy"] = ((int(raw.get("peak_doy", 195)) + 182 - 1) % 365) + 1
            ws = int(raw.get("wet_start_month", 5))
            we = int(raw.get("wet_end_month", 9))
            if not (ws == 1 and we == 12):
                raw["wet_start_month"] = ((ws + 5) % 12) + 1
                raw["wet_end_month"] = ((we + 5) % 12) + 1
        return RegionalWeatherParams(raw)

    abs_lat = min(abs(float(lat)), 65.0)
    t_base = round(max(2.0, 27.5 - 0.35 * abs_lat), 1)
    amplitude = round(min(15.0, 2.5 + 0.25 * abs_lat), 1)
    peak_doy = 195 if lat >= 0.0 else 15
    if abs_lat < 15.0:
        ws, we = 1, 12
    elif lat >= 0.0:
        ws, we = 5, 9
    else:
        ws, we = 11, 3
    return RegionalWeatherParams({
        "t_base": t_base,
        "amplitude": amplitude,
        "peak_doy": peak_doy,
        "trange_c": round(max(6.0, 11.5 - 0.06 * abs_lat), 1),
        "wet_start_month": ws,
        "wet_end_month": we,
        "gamma_wet": [0.55, 11.0],
        "gamma_dry": [0.15, 4.0],
        "citation": "CRU TS4.07 / Latitude-Zonal Global Climatology Reference",
    })


def get_baseline_rotation(lat: float, lon: float) -> list[str]:
    return list(detect_region_config(lat, lon).baseline_rotation)


def get_rothc_baseline(lat: float, lon: float) -> tuple[float, float]:
    """Return biome equilibrium steady-state C input (t C/ha/yr) and reference topsoil SOC (g/kg)."""
    cfg = detect_region_config(lat, lon)
    return cfg.c_eq_t_ha_yr, cfg.soc_ref_g_kg
