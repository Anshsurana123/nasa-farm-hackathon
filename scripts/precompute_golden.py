"""Precompute FieldProfiles, 30-year Weather Ensembles, and Recommendations for all 6 Indian golden benchmark fields. (TASK-D10)

Usage (repo root):  uv run python scripts/precompute_golden.py [field_id ...]
Writes data/golden/<id>/{profile.json, weather.json, recommendations.json}, which the API serves offline.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

from terraloop_engine import crop_kb, profiler
from terraloop_engine.data import nasa_power
from terraloop_schemas import FarmConstraints, FieldGeometry, Priorities

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from terraloop_api.main import RecommendRequest, recommend

GOLDEN = ROOT / "data" / "golden"
WEB_GOLDEN = ROOT / "apps" / "web" / "public" / "golden"


def _save_weather_json(df, path: Path) -> None:
    payload = {
        "index": [d.strftime("%Y-%m-%d") for d in df.index],
        "columns": list(df.columns),
        "data": df.round(2).values.tolist(),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def main(ids: list[str]) -> None:
    fields = json.loads((GOLDEN / "fields.json").read_text(encoding="utf-8"))
    WEB_GOLDEN.mkdir(parents=True, exist_ok=True)
    (WEB_GOLDEN / "fields.json").write_text(json.dumps(fields, indent=2), encoding="utf-8")

    # Sync crops.json to web public/golden
    crops_list = [json.loads(c.model_dump_json()) for c in crop_kb.load_crops().values()]
    (WEB_GOLDEN / "crops.json").write_text(json.dumps(crops_list, indent=2), encoding="utf-8")

    # Remove stale non-Indian directories from web public/golden
    valid_ids = {f["id"] for f in fields}
    for sub in WEB_GOLDEN.iterdir():
        if sub.is_dir() and sub.name not in valid_ids:
            shutil.rmtree(sub, ignore_errors=True)

    for f in fields:
        if ids and f["id"] not in ids:
            continue
        fid = f["id"]
        lat, lon, name = f["lat"], f["lon"], f["name"]
        print(f"-> {fid}: {name} ({lat}, {lon})", flush=True)
        field_dir = GOLDEN / fid
        field_dir.mkdir(parents=True, exist_ok=True)
        web_field_dir = WEB_GOLDEN / fid
        web_field_dir.mkdir(parents=True, exist_ok=True)

        # 1. Build and save FieldProfile
        prof = profiler.build_profile(FieldGeometry(lat=lat, lon=lon, name=name))
        prof_json_str = prof.model_dump_json(indent=2)
        (field_dir / "profile.json").write_text(prof_json_str, encoding="utf-8")
        (web_field_dir / "profile.json").write_text(prof_json_str, encoding="utf-8")

        # 2. Fetch or generate 30-year daily weather (1995-2024) for 30 historical ensemble members
        try:
            w_df = nasa_power.fetch_daily(
                nasa_power.PowerRequest(lat=lat, lon=lon, start=date(1995, 1, 1), end=date(2024, 12, 31))
            )
        except Exception:  # noqa: BLE001
            w_df = nasa_power.synthetic_daily_weather(lat, lon, (1995, 2024))
        _save_weather_json(w_df, field_dir / "weather.json")

        # 3. Compute default recommendations (using the newly saved profile & weather)
        irrigation_mode = "none" if fid in ("vidarbha", "bundelkhand") else ("limited" if fid == "bathinda" else "full")
        recs = recommend(
            RecommendRequest(
                field=FieldGeometry(lat=lat, lon=lon, name=name),
                priorities=Priorities(profit=4.0, water_savings=4.5, soil_health=4.0, low_risk=3.5, low_labour=3.0),
                constraints=FarmConstraints(irrigation=irrigation_mode, rotation_years=1),
            )
        )
        recs_json_str = json.dumps([json.loads(r.model_dump_json()) for r in recs], indent=2)
        (field_dir / "recommendations.json").write_text(recs_json_str, encoding="utf-8")
        (web_field_dir / "recommendations.json").write_text(recs_json_str, encoding="utf-8")

        c, s = prof.climate, prof.soil
        base_rec = recs[0]
        base_irr = sum(base_rec.results[0].irrigation_mm) / len(base_rec.results[0].irrigation_mm)
        print(
            f"   rain {c.annual_precip_mm} mm ({c.precip_change_pct:+.1f}%), "
            f"heat days {c.heat_days_per_year}->{c.recent_heat_days_per_year}, "
            f"soil {s.texture_class} SOC {s.soc_g_per_kg} g/kg",
            flush=True,
        )
        print(
            f"   Baseline: {base_rec.rotation.label} (irr={base_irr:.0f} mm, P50=INR {base_rec.results[0].profit_p50:,.0f}/ha, "
            f"SOC_10yr={base_rec.results[0].soc_delta_t_ha_10yr:+.2f} t/ha)",
            flush=True,
        )
        for rk in recs[1:]:
            rk_irr = sum(rk.results[0].irrigation_mm) / len(rk.results[0].irrigation_mm)
            print(
                f"   Rank #{rk.rank} : {rk.rotation.label} (irr={rk_irr:.0f} mm [{rk.vs_baseline.get('irrigation_change_pct', 0):+.1f}%], "
                f"P50=INR {rk.results[0].profit_p50:,.0f}/ha, SOC_10yr={rk.results[0].soc_delta_t_ha_10yr:+.2f} t/ha)",
                flush=True,
            )


if __name__ == "__main__":
    main(sys.argv[1:])
