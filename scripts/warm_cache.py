"""Pre-warm @disk_cache for NASA POWER (0.5° x 0.625° native cells) and SoilGrids across Indian hubs (WS-H1).

Usage:
  uv run python scripts/warm_cache.py
  uv run python scripts/warm_cache.py --offline-check
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "engine"))
sys.path.insert(0, str(ROOT / "packages" / "schemas"))

from terraloop_engine.data import nasa_power, soilgrids

REGIONAL_HUBS = [
    {"name": "Sangrur (Punjab)", "lat": 30.19, "lon": 75.78},
    {"name": "Ludhiana (Punjab)", "lat": 30.82, "lon": 75.68},
    {"name": "Bathinda (Punjab)", "lat": 30.12, "lon": 74.86},
    {"name": "Karnal (Haryana)", "lat": 29.69, "lon": 76.98},
    {"name": "Jhansi (UP / Bundelkhand)", "lat": 25.38, "lon": 78.62},
    {"name": "Yavatmal (Maharashtra / Vidarbha)", "lat": 20.39, "lon": 78.13},
    {"name": "Thanjavur (Tamil Nadu / Cauvery)", "lat": 10.72, "lon": 79.25},
    {"name": "Indore (Madhya Pradesh / Malwa)", "lat": 22.72, "lon": 75.86},
]


def warm_cache(offline_check: bool = False) -> None:
    print(f"-> Pre-warming cache for {len(REGIONAL_HUBS)} regional agricultural hubs (offline_check={offline_check})...")
    snapped_cells: set[tuple[float, float]] = set()

    for hub in REGIONAL_HUBS:
        lat, lon, name = hub["lat"], hub["lon"], hub["name"]
        grid_lat, grid_lon = nasa_power.snap_to_power_grid(lat, lon)
        snapped_cells.add((grid_lat, grid_lon))
        print(f"   [{name}] ({lat}, {lon}) -> Snapped NASA POWER cell: ({grid_lat}, {grid_lon})")

        if not offline_check:
            try:
                # Pre-warm NASA POWER daily weather
                nasa_power.fetch_daily(
                    nasa_power.PowerRequest(
                        lat=lat,
                        lon=lon,
                        start=date(1995, 1, 1),
                        end=date(2024, 12, 31),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                print(f"      NASA POWER warm warning for {name}: {exc}")

            try:
                # Pre-warm SoilGrids
                soilgrids.fetch_topsoil(lat, lon)
            except Exception as exc:  # noqa: BLE001
                print(f"      SoilGrids warm warning for {name}: {exc}")

    print(f"-> Successfully processed {len(REGIONAL_HUBS)} hubs across {len(snapped_cells)} distinct grid cells.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-warm disk cache for Indian agricultural hubs")
    parser.add_argument("--offline-check", action="store_true", help="Verify grid cell snapping and cache keys offline without network calls")
    args = parser.parse_args()
    warm_cache(offline_check=args.offline_check)


if __name__ == "__main__":
    main()
