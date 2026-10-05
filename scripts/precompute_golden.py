"""Precompute FieldProfiles for all golden demo fields. (TASK-D10)

Usage (repo root):  uv run python scripts/precompute_golden.py [field_id ...]
Writes data/golden/<id>/profile.json, which the API serves without touching live APIs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from terraloop_engine import profiler
from terraloop_schemas import FieldGeometry

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"


def main(ids: list[str]) -> None:
    fields = json.loads((GOLDEN / "fields.json").read_text(encoding="utf-8"))
    for f in fields:
        if ids and f["id"] not in ids:
            continue
        print(f"-> {f['id']} ({f['lat']}, {f['lon']})")
        prof = profiler.build_profile(FieldGeometry(lat=f["lat"], lon=f["lon"], name=f["name"]))
        out = GOLDEN / f["id"] / "profile.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(prof.model_dump_json(indent=2), encoding="utf-8")
        c, s = prof.climate, prof.soil
        print(f"   rain {c.annual_precip_mm} mm, heat days {c.heat_days_per_year}->{c.recent_heat_days_per_year}, "
              f"soil {s.texture_class} SOC {s.soc_g_per_kg} g/kg, erosion {prof.hazards.erosion_risk_class}")


if __name__ == "__main__":
    main(sys.argv[1:])
