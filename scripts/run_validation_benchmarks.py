"""Reproducible engine validation & benchmark suite for TerraLoop India.

Run (from repo root):
    uv run python scripts/run_validation_benchmarks.py --write-docs

Executes the actual TerraLoop biophysical engine across 5 verification benchmarks:
  1. Soil Texture & Root-Zone Water Holding Sensitivity (Sandy Loam vs Alluvial Loam vs Vertisol Clay)
  2. March Terminal Heatwave Sensitivity (Reproducing the 2022 North India Wheat Heat Shock)
  3. Rice Establishment Hydrology & Stubble Turnaround Window (Puddled Pusa-44 vs Short-Duration PR-126 vs DSR)
  4. 10-Year RothC-Lite Soil Organic Carbon & Biological N / Urea Savings Trajectory
  5. 6 Indian Agro-Climatic Golden Benchmark Fields (Baseline vs Rank #1 Strategy)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from terraloop_engine import crop_kb, profiler
from terraloop_engine.climate import ensembles
from terraloop_engine.models import aquacrop_runner, soil
from terraloop_engine.optimize import evaluate, rotations
from terraloop_schemas import (
    FarmConstraints,
    FieldGeometry,
    FieldProfile,
    Rotation,
    RotationStep,
    SoilSummary,
    WaterSummary,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "data" / "golden"


def _load_sangrur_weather() -> pd.DataFrame:
    w_path = GOLDEN / "sangrur" / "weather.json"
    if w_path.exists():
        raw = json.loads(w_path.read_text(encoding="utf-8"))
        df = pd.DataFrame(raw["data"], columns=raw["columns"])
        df.index = pd.to_datetime(raw["index"])
        df.index.name = "date"
        return df.astype(float).sort_index()
    from terraloop_engine.data import nasa_power

    return nasa_power.synthetic_daily_weather(30.19, 75.78, (1995, 2024))


def run_benchmarks() -> str:
    w_df = _load_sangrur_weather()
    crops = crop_kb.load_crops()

    lines: list[str] = []
    lines.append("# TerraLoop India — Reproducible Biophysical & Economic Validation Report")
    lines.append("")
    lines.append(
        "> **Reproducibility Guarantee:** Every number in this document is generated directly by executing "
        "`uv run python scripts/run_validation_benchmarks.py --write-docs` against the TerraLoop simulation engine "
        "(`packages/engine/terraloop_engine/`)."
    )
    lines.append("")

    # -----------------------------------------------------------------------
    # Benchmark 1: Soil Texture Sensitivity
    # -----------------------------------------------------------------------
    lines.append("## 1. Soil Texture & Root-Zone Water Balance Sensitivity (`models/aquacrop_runner.py`)")
    lines.append("")
    lines.append(
        "Evaluates FAO-56 daily root-zone soil moisture depletion (`TAW`, `RAW`, `Ks`, deep percolation) across "
        "three representative Indian soil textures under both Rainfed/Limited and Full Irrigation regimes (2020–2021 cycle)."
    )
    lines.append("")
    lines.append(
        "| Soil Texture Class | Sand / Clay (%) | FC / WP (m³/m³) | Rainfed Wheat Yield (t/ha) | Irrigated Wheat Irrigation (mm) | DSR Rice Yield (t/ha) | DSR Rice Irrigation (mm) |"
    )
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

    soils_spec = [
        ("Coarse Loamy Sand (SW Punjab / Rajasthan)", 76.0, 14.0, 10.0, 3.8),
        ("Indo-Gangetic Alluvial Loam (Sangrur / Ludhiana)", 44.0, 36.0, 20.0, 5.2),
        ("Deccan Black Cotton Vertisol (Vidarbha Clay)", 22.0, 28.0, 50.0, 6.5),
    ]
    rot_wheat = Rotation(id="wheat_single", steps=[RotationStep(year_index=0, season_index=1, crop_id="wheat")])
    rot_dsr = Rotation(id="dsr_single", steps=[RotationStep(year_index=0, season_index=0, crop_id="rice_dsr")])

    for label, sand_p, silt_p, clay_p, soc_g in soils_spec:
        fc, wp = soil.saxton_rawls(sand_p, clay_p, soc_g)
        s_obj = SoilSummary(
            texture_class=soil.usda_texture_class(sand_p, silt_p, clay_p),
            sand_pct=sand_p,
            silt_pct=silt_p,
            clay_pct=clay_p,
            soc_g_per_kg=soc_g,
            field_capacity_vol=fc,
            wilting_point_vol=wp,
        )
        w_rf = aquacrop_runner.simulate_rotation(
            rot_wheat, w_df, s_obj, FarmConstraints(irrigation="none"), start_year=2020
        )[0]
        w_ir = aquacrop_runner.simulate_rotation(
            rot_wheat, w_df, s_obj, FarmConstraints(irrigation="full"), start_year=2020
        )[0]
        d_ir = aquacrop_runner.simulate_rotation(
            rot_dsr, w_df, s_obj, FarmConstraints(irrigation="full"), start_year=2020
        )[0]
        lines.append(
            f"| {label} | {sand_p:.0f}% / {clay_p:.0f}% | {fc:.3f} / {wp:.3f} | "
            f"**{w_rf['yield_t_ha']:.2f}** | **{w_ir['irrigation_mm']:.0f}** | "
            f"**{d_ir['yield_t_ha']:.2f}** | **{d_ir['irrigation_mm']:.0f}** |"
        )
    lines.append("")

    # -----------------------------------------------------------------------
    # Benchmark 2: March 2022 Terminal Heatwave Sensitivity
    # -----------------------------------------------------------------------
    lines.append("## 2. Rabi Wheat Terminal Heatwave Sensitivity (March–April Grain-Filling Shock)")
    lines.append("")
    lines.append(
        "Tests the thermal senescence response during the final 40% of the Rabi wheat cycle (March–April grain filling, "
        "`Tmax > 31.5°C`) under baseline climate, a `+4.5°C` heat anomaly (analogous to the March 2022 North India heatwave), "
        "and `+4.5°C` with **Happy Seeder surface residue mulch** (`-1.0°C` soil/canopy cooling + `-10%` evaporation)."
    )
    lines.append("")
    lines.append("| Scenario | Mean Rabi Yield (t/ha) | Yield Change vs Normal (%) | Seasonal Irrigation (mm) |")
    lines.append("| :--- | :---: | :---: | :---: |")

    fc_l, wp_l = soil.saxton_rawls(44.0, 20.0, 5.2)
    loam_soil = SoilSummary(
        texture_class="loam", sand_pct=44.0, silt_pct=36.0, clay_pct=20.0, soc_g_per_kg=5.2,
        field_capacity_vol=fc_l, wilting_point_vol=wp_l
    )
    w_heat = w_df.copy()
    mar_apr = (w_heat.index.month == 3) | (w_heat.index.month == 4)
    w_heat.loc[mar_apr, "T2M_MAX"] = w_heat.loc[mar_apr, "T2M_MAX"] + 4.5
    w_heat.loc[mar_apr, "T2M_MIN"] = w_heat.loc[mar_apr, "T2M_MIN"] + 4.5

    rot_wheat_conv = Rotation(
        id="wheat_conv", steps=[RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["conventional"])]
    )
    rot_wheat_hs = Rotation(
        id="wheat_hs",
        steps=[RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["happy_seeder", "residue_retained"])],
    )

    res_norm = aquacrop_runner.simulate_rotation(
        rot_wheat_conv, w_df, loam_soil, FarmConstraints(irrigation="full"), start_year=2021
    )[0]
    res_shock = aquacrop_runner.simulate_rotation(
        rot_wheat_conv, w_heat, loam_soil, FarmConstraints(irrigation="full"), start_year=2021
    )[0]
    res_hs_shock = aquacrop_runner.simulate_rotation(
        rot_wheat_hs, w_heat, loam_soil, FarmConstraints(irrigation="full"), start_year=2021
    )[0]

    drop_conv = (res_shock["yield_t_ha"] - res_norm["yield_t_ha"]) / res_norm["yield_t_ha"] * 100.0
    drop_hs = (res_hs_shock["yield_t_ha"] - res_norm["yield_t_ha"]) / res_norm["yield_t_ha"] * 100.0

    lines.append(f"| Baseline Climate (Conventional Tillage Wheat) | **{res_norm['yield_t_ha']:.2f}** | 0.0% | {res_norm['irrigation_mm']:.0f} |")
    lines.append(f"| +4.5°C Mar–Apr Heatwave (Conventional Tillage Wheat) | **{res_shock['yield_t_ha']:.2f}** | **{drop_conv:+.1f}%** | {res_shock['irrigation_mm']:.0f} |")
    lines.append(f"| +4.5°C Mar–Apr Heatwave + Happy Seeder Mulch | **{res_hs_shock['yield_t_ha']:.2f}** | **{drop_hs:+.1f}%** | {res_hs_shock['irrigation_mm']:.0f} |")
    lines.append("")

    # -----------------------------------------------------------------------
    # Benchmark 3: Rice Hydrology & Kharif-to-Rabi Turnaround Days
    # -----------------------------------------------------------------------
    lines.append("## 3. Kharif Rice Hydrology & Stubble-Burning Turnaround Window")
    lines.append("")
    lines.append(
        "Compares Puddled Long-Duration Rice (`rice_puddled`, 142 days, 180 mm puddling + standing water), "
        "PAU Short-Duration Rice (`rice_short` PR-126, 123 days), and Direct-Seeded Rice (`rice_dsr`, 125 days, "
        "0 mm puddling + Alternate Wetting & Drying) on Sangrur Alluvial Loam."
    )
    lines.append("")
    lines.append(
        "| Kharif Rice System | Duration (days) | Turnaround Before Wheat (days) | Irrigation (mm) | Water Saved vs Puddled (%) | Simulated Yield (t/ha) |"
    )
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    rice_variants = [
        ("Puddled Long-Duration Rice (Pusa-44)", "rice_puddled", ["conventional", "burning"]),
        ("Short-Duration Rice (PAU PR-126)", "rice_short", ["residue_retained"]),
        ("Direct-Seeded Rice (DSR + AWD)", "rice_dsr", ["direct_seeded", "residue_retained"]),
    ]
    base_rice_irr = None
    for r_label, cid, pracs in rice_variants:
        rot_r = Rotation(
            id=f"{cid}_wheat",
            steps=[
                RotationStep(year_index=0, season_index=0, crop_id=cid, practices=pracs),
                RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["happy_seeder"]),
            ],
        )
        sim_r = aquacrop_runner.simulate_rotation(
            rot_r, w_df, loam_soil, FarmConstraints(irrigation="full"), start_year=2021
        )[0]
        if base_rice_irr is None:
            base_rice_irr = sim_r["irrigation_mm"]
        saved_pct = (base_rice_irr - sim_r["irrigation_mm"]) / base_rice_irr * 100.0
        t_days = rotations.compute_turnaround_days(rot_r, crops)
        dur_mean = int(sum(crops[cid].duration_days) / 2)
        lines.append(
            f"| {r_label} | {dur_mean} d | **{t_days} days** | **{sim_r['irrigation_mm']:.0f} mm** | "
            f"**{saved_pct:.1f}%** | **{sim_r['yield_t_ha']:.2f} t/ha** |"
        )
    lines.append("")

    # -----------------------------------------------------------------------
    # Benchmark 4: 10-Year RothC-Lite SOC & Urea Savings
    # -----------------------------------------------------------------------
    lines.append("## 4. 10-Year RothC-Lite Soil Organic Carbon & Biological Nitrogen Trajectory")
    lines.append("")
    lines.append(
        "Evaluates 30-member ensemble outcomes on Sangrur Alluvial Loam (`SOC = 5.2 g/kg`) across three management systems."
    )
    lines.append("")
    lines.append(
        "| Rotation & Management System | 10-Yr SOC Change (t C/ha) | Soil Health Score (/100) | N Balance (kg N/ha/yr) | 45-kg Urea Bags Saved/ha | Turnaround Window (days) |"
    )
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")

    sangrur_prof_path = GOLDEN / "sangrur" / "profile.json"
    if sangrur_prof_path.exists():
        sangrur_prof = FieldProfile.model_validate_json(sangrur_prof_path.read_text(encoding="utf-8"))
    else:
        c_s, h_s, wb_s = profiler.summarise_climate(w_df, 30.19)
        sangrur_prof = FieldProfile(
            field=FieldGeometry(lat=30.19, lon=75.78, name="Sangrur, Punjab"),
            climate=c_s,
            water=WaterSummary(climatic_water_balance_mm=wb_s, groundwater_trend_cm_per_year=-3.85),
            soil=loam_soil,
            hazards=h_s,
        )

    _, members = ensembles.build_scenario_set("historical", power_df=w_df, rotation_years=1)
    bench_rotations = [
        (
            "Baseline: Puddled Rice → Wheat (Residue Burned)",
            Rotation(
                id="base_rw_burn",
                is_baseline=True,
                steps=[
                    RotationStep(year_index=0, season_index=0, crop_id="rice_puddled", practices=["conventional", "burning"]),
                    RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["conventional"]),
                    RotationStep(year_index=0, season_index=2, crop_id="fallow", practices=[]),
                ],
            ),
        ),
        (
            "PR-126 Short Rice → Happy Seeder Wheat → Summer Moong",
            Rotation(
                id="pr126_wheat_moong",
                steps=[
                    RotationStep(year_index=0, season_index=0, crop_id="rice_short", practices=["residue_retained"]),
                    RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["happy_seeder", "residue_retained"]),
                    RotationStep(year_index=0, season_index=2, crop_id="moong", practices=["zero_till", "residue_retained"]),
                ],
            ),
        ),
        (
            "Direct-Seeded Rice (DSR) → Zero-Till Wheat → Summer Moong",
            Rotation(
                id="dsr_wheat_moong",
                steps=[
                    RotationStep(year_index=0, season_index=0, crop_id="rice_dsr", practices=["direct_seeded", "residue_retained"]),
                    RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["happy_seeder", "residue_retained"]),
                    RotationStep(year_index=0, season_index=2, crop_id="moong", practices=["zero_till", "residue_retained"]),
                ],
            ),
        ),
        (
            "Kharif Maize → Happy Seeder Wheat → Summer Moong",
            Rotation(
                id="maize_wheat_moong",
                steps=[
                    RotationStep(year_index=0, season_index=0, crop_id="maize", practices=["residue_retained"]),
                    RotationStep(year_index=0, season_index=1, crop_id="wheat", practices=["happy_seeder", "residue_retained"]),
                    RotationStep(year_index=0, season_index=2, crop_id="moong", practices=["zero_till", "residue_retained"]),
                ],
            ),
        ),
    ]

    base_eval_res = None
    for sys_name, rot_obj in bench_rotations:
        ev_res = evaluate.evaluate_rotation(rot_obj, members, sangrur_prof, FarmConstraints(irrigation="full"))
        if base_eval_res is None:
            base_eval_res = ev_res
        pm = evaluate.compute_practical_farmer_metrics(rot_obj, ev_res, base_eval_res, crops)
        lines.append(
            f"| {sys_name} | **{ev_res.soc_delta_t_ha_10yr:+.2f}** | **{ev_res.soil_health_score:.1f}** | "
            f"{ev_res.n_balance_kg_ha_yr:+.1f} | **{pm.urea_bags_saved_per_ha:.1f} bags** | **{pm.turnaround_days_kharif_rabi} d** |"
        )
    lines.append("")

    # -----------------------------------------------------------------------
    # Benchmark 5: All 6 Indian Golden Fields Summary
    # -----------------------------------------------------------------------
    lines.append("## 5. Six Indian Agro-Climatic Golden Benchmark Fields (Precomputed Engine Outputs)")
    lines.append("")
    lines.append(
        "| Benchmark Field | Agro-Climatic Zone | Baseline Rotation | Rank #1 Recommended Strategy | Irrigation Change | Median Net Profit (₹/ha) | 10-Yr SOC Delta (t C/ha) | Soil Health Score |"
    )
    lines.append("| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |")

    fields_idx = json.loads((GOLDEN / "fields.json").read_text(encoding="utf-8"))
    for f in fields_idx:
        fid = f["id"]
        p_path = GOLDEN / fid / "profile.json"
        r_path = GOLDEN / fid / "recommendations.json"
        if not (p_path.exists() and r_path.exists()):
            continue
        prof_f = FieldProfile.model_validate_json(p_path.read_text(encoding="utf-8"))
        recs_f = json.loads(r_path.read_text(encoding="utf-8"))
        base_r = recs_f[0]
        top_r = recs_f[1]
        irr_chg = top_r["vs_baseline"].get("irrigation_change_pct", 0.0)
        p50 = top_r["results"][0]["profit_p50"]
        soc_d = top_r["results"][0]["soc_delta_t_ha_10yr"]
        sh_s = top_r["results"][0]["soil_health_score"]
        lines.append(
            f"| **{f['name']}** (`{fid}`) | {prof_f.agro_zone or f['region']} | {base_r['rotation']['label']} | "
            f"**{top_r['rotation']['label']}** | **{irr_chg:+.1f}%** | **₹{p50:,.0f}** | **{soc_d:+.2f}** | **{sh_s:.0f}/100** |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    report_md = run_benchmarks()
    print(report_md)
    if "--write-docs" in sys.argv:
        (ROOT / "docs" / "VALIDATION.md").write_text(report_md, encoding="utf-8")
        print("\n[OK] Wrote docs/VALIDATION.md from live engine outputs.")
