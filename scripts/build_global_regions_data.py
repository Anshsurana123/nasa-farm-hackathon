"""Build compact offline GIS & climate classification artifacts for TerraLoop global registry.

Downloads official public-domain vector boundaries and published Köppen-Geiger climate grids:
1. Natural Earth 110m Admin-0 Countries -> packages/crop-kb/regions/global_countries.geojson
2. Natural Earth 50m Admin-1 States/Provinces (selected agricultural nations) -> packages/crop-kb/regions/global_admin1.geojson
3. Kottek et al. (2006) 0.5-deg Koppen-Geiger ASCII grid -> packages/crop-kb/regions/aez_global_grid.json

Usage:
    uv run python scripts/build_global_regions_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
REGIONS_DIR = ROOT / "packages" / "crop-kb" / "regions"

NE_COUNTRIES_URL = (
    "https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/geojson/ne_110m_admin_0_countries.geojson"
)
NE_ADMIN1_URL = (
    "https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@master/geojson/ne_50m_admin_1_states_provinces.geojson"
)
KOPPEN_URL = "https://cdn.jsdelivr.net/gh/zliobaite/teeth-redescription@master/koeppen/Koeppen-Geiger-ASCII.txt"

ADMIN1_TARGET_ISO3 = {
    "USA",
    "FRA",
    "BRA",
    "KEN",
    "AUS",
    "CAN",
    "ARG",
    "DEU",
    "GBR",
    "UKR",
    "CHN",
    "ESP",
    "ITA",
    "MEX",
    "ZAF",
    "ETH",
    "NGA",
    "IDN",
    "THA",
    "VNM",
    "PAK",
    "BGD",
}


def _round_coords(coords: object, decimals: int) -> object:
    if isinstance(coords, list):
        if coords and isinstance(coords[0], (int, float)):
            return [round(float(coords[0]), decimals), round(float(coords[1]), decimals)]
        return [_round_coords(c, decimals) for c in coords]
    return coords


def _compute_bbox(geom: dict) -> list[float]:
    min_x, min_y = 180.0, 90.0
    max_x, max_y = -180.0, -90.0

    def _walk(node: object) -> None:
        nonlocal min_x, min_y, max_x, max_y
        if isinstance(node, list):
            if node and isinstance(node[0], (int, float)):
                x, y = float(node[0]), float(node[1])
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
            else:
                for child in node:
                    _walk(child)

    _walk(geom.get("coordinates", []))
    return [round(min_x, 4), round(min_y, 4), round(max_x, 4), round(max_y, 4)]


def build_countries() -> None:
    print(f"Downloading {NE_COUNTRIES_URL} ...")
    resp = httpx.get(NE_COUNTRIES_URL, follow_redirects=True, timeout=60.0)
    resp.raise_for_status()
    raw = resp.json()

    features = []
    for feat in raw.get("features", []):
        props = feat.get("properties") or {}
        geom = feat.get("geometry")
        if not geom:
            continue
        rounded = {"type": geom["type"], "coordinates": _round_coords(geom["coordinates"], 3)}
        iso_a3 = props.get("ADM0_A3") or props.get("ISO_A3") or ""
        iso_a2 = props.get("ISO_A2") if props.get("ISO_A2") != "-99" else ""
        features.append({
            "type": "Feature",
            "bbox": _compute_bbox(rounded),
            "properties": {
                "name": props.get("NAME_EN") or props.get("NAME") or props.get("ADMIN"),
                "admin": props.get("ADMIN"),
                "iso_a3": iso_a3,
                "iso_a2": iso_a2,
                "continent": props.get("CONTINENT"),
                "subregion": props.get("SUBREGION"),
            },
            "geometry": rounded,
        })

    out = REGIONS_DIR / "global_countries.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out} ({len(features)} countries, {out.stat().st_size / 1024:.1f} KB)")


def build_admin1() -> None:
    print(f"Downloading {NE_ADMIN1_URL} ...")
    resp = httpx.get(NE_ADMIN1_URL, follow_redirects=True, timeout=90.0)
    resp.raise_for_status()
    raw = resp.json()

    features = []
    for feat in raw.get("features", []):
        props = feat.get("properties") or {}
        iso3 = props.get("adm0_a3") or props.get("ADM0_A3") or ""
        if iso3 not in ADMIN1_TARGET_ISO3:
            continue
        geom = feat.get("geometry")
        if not geom:
            continue
        rounded = {"type": geom["type"], "coordinates": _round_coords(geom["coordinates"], 3)}
        features.append({
            "type": "Feature",
            "bbox": _compute_bbox(rounded),
            "properties": {
                "name": props.get("name") or props.get("name_en"),
                "admin": props.get("admin"),
                "iso_a3": iso3,
                "postal": props.get("postal") or "",
                "iso_3166_2": props.get("iso_3166_2") or "",
            },
            "geometry": rounded,
        })

    out = REGIONS_DIR / "global_admin1.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out} ({len(features)} admin-1 polygons, {out.stat().st_size / 1024:.1f} KB)")


def build_koppen_grid() -> None:
    print(f"Downloading {KOPPEN_URL} ...")
    resp = httpx.get(KOPPEN_URL, follow_redirects=True, timeout=60.0)
    resp.raise_for_status()
    lines = resp.text.splitlines()

    classes: list[str] = ["Ocean"]
    class_to_idx: dict[str, int] = {"Ocean": 0}
    grid = [[0] * 720 for _ in range(360)]

    parsed_rows = 0
    for line in lines:
        s = line.strip()
        if not s or s.startswith(("Lat", "#")):
            continue
        parts = s.split()
        if len(parts) < 3:
            continue
        try:
            lat_v = float(parts[0])
            lon_v = float(parts[1])
        except ValueError:
            continue
        cls = parts[2]
        if cls not in class_to_idx:
            class_to_idx[cls] = len(classes)
            classes.append(cls)
        r = max(0, min(359, round((lat_v + 89.75) * 2.0)))
        c = max(0, min(719, round((lon_v + 179.75) * 2.0)))
        grid[r][c] = class_to_idx[cls]
        parsed_rows += 1

    # Run-length encode each latitude row: [[class_idx, count], ...] for compact fast load
    rle_rows = []
    for r in range(360):
        row = grid[r]
        if all(v == 0 for v in row):
            rle_rows.append([])
            continue
        runs = []
        cur = row[0]
        cnt = 1
        for v in row[1:]:
            if v == cur:
                cnt += 1
            else:
                runs.append([cur, cnt])
                cur = v
                cnt = 1
        runs.append([cur, cnt])
        rle_rows.append(runs)

    payload = {
        "citation": "Kottek, M., Grieser, J., Beck, C., Rudolf, B., Rubel, F. (2006) Meteorol. Z. 15(3):259-263 (DOI:10.1127/0941-2948/2006/0130)",
        "resolution_deg": 0.5,
        "lat_start": -89.75,
        "lon_start": -179.75,
        "rows": 360,
        "cols": 720,
        "classes": classes,
        "rle_rows": rle_rows,
    }
    out = REGIONS_DIR / "aez_global_grid.json"
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {out} ({parsed_rows} land cells, {len(classes)-1} classes, {out.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    REGIONS_DIR.mkdir(parents=True, exist_ok=True)
    build_countries()
    build_admin1()
    build_koppen_grid()
