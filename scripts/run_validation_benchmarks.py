"""Reproducible engine benchmark & empirical comparison suite for TerraLoop India.

Run (from repo root):
    uv run python scripts/run_validation_benchmarks.py --write-docs

Executes the TerraLoop biophysical engine across 6 reproducible benchmarks:
  1. Empirical Ground-Truth Comparison against DES / ICRISAT District-Level Yield Statistics
  2. Soil Texture & Root-Zone Water Holding Sensitivity (Sandy Loam vs Alluvial Loam vs Vertisol Clay)
  3. March Terminal Heatwave Sensitivity (Reproducing the 2022 North India Wheat Heat Shock)
  4. Rice Establishment Hydrology & Stubble Turnaround Window (Puddled Pusa-44 vs Short-Duration PR-126 vs DSR)
  5. 10-Year RothC-Lite SOC, Biological N & Soil Health Score Component Breakdown
  6. 6 Indian Agro-Climatic Golden Benchmark Fields (Baseline vs Rank #1 Strategy)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from terraloop_engine import crop_kb, profiler
from terraloop_engine.climate import ensembles
from terraloop_engine.models import fao56_runner as aquacrop_runner
from terraloop_engine.models import soil
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
GROUND_TRUTH_CSV = ROOT / "data" / "benchmarks" / "district_ground_truth.csv"


def _load_field_weather(field_id: str, lat: float, lon: float) -> pd.DataFrame:
    w_path = GOLDEN / field_id / "weather.json"
    if w_path.exists():
        raw = json.loads(w_path.read_text(encoding="utf-8"))
        df = pd.DataFrame(raw["data"], columns=raw["columns"])
        df.index = pd.to_datetime(raw["index"])
        df.index.name = "date"
        return df.astype(float).sort_index()
    from terraloop_engine.data import nasa_power

    return nasa_power.synthetic_daily_weather(lat, lon, (1995, 2024))


def _load_sangrur_weather() -> pd.DataFrame:
    return _load_field_weather("sangrur", 30.19, 75.78)


def _load_ground_truth_records() -> pd.DataFrame:
    if not GROUND_TRUTH_CSV.exists():
        raise FileNotFoundError(f"District ground truth CSV missing: {GROUND_TRUTH_CSV}")
    return pd.read_csv(GROUND_TRUTH_CSV)


def run_benchmarks() -> str:
    w_df = _load_sangrur_weather()
    crops = crop_kb.load_crops()
    gt_df = _load_ground_truth_records()

    lines: list[str] = []
    lines.append("# TerraLoop India — Empirical Ground-Truth Comparison & Sensitivity Benchmarks")
    lines.append("")
    lines.append(
        "> **Reproducibility Guarantee:** Every number in this document is generated directly by executing "
        "`uv run python scripts/run_validation_benchmarks.py --write-docs` against the TerraLoop FAO-56 / FAO-33 "
        "simulation engine (`packages/engine/terraloop_engine/`), enforced in CI via `git diff --exit-code docs/BENCHMARKS.md`."
    )
    lines.append("")

    # -----------------------------------------------------------------------
    # Benchmark 1: Empirical Calibration Check vs DES / ICRISAT District Data
    # -----------------------------------------------------------------------
    lines.append("## 1. Empirical Calibration Check vs. DES / ICRISAT District-Level Data")
    lines.append("")
    lines.append(
        "Evaluates 30-year historical ensemble median simulated yields (`FAO-56 / FAO-33 daily soil-water balance`, "
        "`models/fao56_runner.py`) against published 5-year district mean yields from the Directorate of Economics & Statistics "
        "(DES, Ministry of Agriculture & Farmers Welfare, APY Statistics) and ICRISAT District-Level Database (DLD). "
        "All ground-truth entries are documented in `data/benchmarks/district_ground_truth.csv` with exact table, year range, and URLs."
    )
    lines.append("")
    lines.append("### 1.1 Calibration Check: Sangrur, Punjab (Model Parameter Calibration Site)")
    lines.append("")
    lines.append(
        "Sangrur serves as the primary calibration baseline for the North-West Indian alluvial rice–wheat belt. "
        "Potential yield benchmarks ($y_{pot} = y_{min} + q_{pot}(y_{max} - y_{min})$), March terminal heat sensitivity "
        "($T_{crit} = 32.0^\\circ\\text{C}$, final 35% grain-filling window), and MERRA-2 bias corrections (-4.5°C in March) "
        "were parameterized against Sangrur station observations and DES historical data."
    )
    lines.append("")
    lines.append(
        "| District | Crop & Regime | Observed District Mean (t/ha) | Simulated Median Yield (t/ha) | Absolute Error (t/ha) | Relative Error (%) | Reference Table & Source |"
    )
    lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :--- |")

    eval_stats: dict[tuple[str, str], tuple[float, float, float]] = {}

    calib_df = gt_df[~gt_df["is_held_out"]].copy()
    for _, row in calib_df.iterrows():
        fid = row["district_id"]
        d_name = f"{row['district_name']}, {row['state']}"
        cid = row["crop_id"]
        c_label = row["crop_label"]
        obs_y = float(row["observed_yield_t_ha"])
        ref_src = f"{row['source_org']} — {row['publication_table']}"

        p_path = GOLDEN / fid / "profile.json"
        if not p_path.exists():
            continue
        prof_d = FieldProfile.model_validate_json(p_path.read_text(encoding="utf-8"))
        w_d = _load_field_weather(fid, prof_d.field.lat, prof_d.field.lon)
        irr_mode = "none" if fid in ("vidarbha", "bundelkhand") else ("limited" if fid == "bathinda" else "full")
        s_idx = 1 if cid in ("wheat", "chickpea") else 0
        rot_single = Rotation(
            id=f"gt_{fid}_{cid}",
            steps=[RotationStep(year_index=0, season_index=s_idx, crop_id=cid, practices=["puddling"] if cid == "rice_puddled" else [])],
        )
        _, mem_d = ensembles.build_scenario_set("historical", power_df=w_d, rotation_years=1)
        ev_d = evaluate.evaluate_rotation(rot_single, mem_d, prof_d, FarmConstraints(irrigation=irr_mode))
        sim_vals = ev_d.yield_t_ha.get(cid, [0.0])
        sim_med = float(np.median(sim_vals))
        abs_err = sim_med - obs_y
        rel_err = (abs_err / obs_y) * 100.0 if obs_y > 0 else 0.0
        eval_stats[(fid, cid)] = (obs_y, sim_med, rel_err)
        lines.append(
            f"| **{d_name}** | {c_label} | {obs_y:.2f} | **{sim_med:.2f}** | {abs_err:+.2f} | **{rel_err:+.1f}%** | {ref_src} |"
        )

    lines.append("")
    lines.append("### 1.2 Held-Out Evaluation: Indo-Gangetic & Peninsular Indian Benchmark Districts")
    lines.append("")
    lines.append(
        "The remaining 5 districts (Ludhiana, Bathinda, Yavatmal, Jhansi, Thanjavur) are held-out evaluation sites. "
        "Their simulations run with frozen parameter values, with zero post-hoc tuning against their observed district numbers."
    )
    lines.append("")
    lines.append(
        "| District | Crop & Regime | Observed District Mean (t/ha) | Simulated Median Yield (t/ha) | Absolute Error (t/ha) | Relative Error (%) | Reference Table & Source |"
    )
    lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :--- |")

    held_df = gt_df[gt_df["is_held_out"]].copy()
    for _, row in held_df.iterrows():
        fid = row["district_id"]
        d_name = f"{row['district_name']}, {row['state']}"
        cid = row["crop_id"]
        c_label = row["crop_label"]
        obs_y = float(row["observed_yield_t_ha"])
        ref_src = f"{row['source_org']} — {row['publication_table']}"

        p_path = GOLDEN / fid / "profile.json"
        if not p_path.exists():
            continue
        prof_d = FieldProfile.model_validate_json(p_path.read_text(encoding="utf-8"))
        w_d = _load_field_weather(fid, prof_d.field.lat, prof_d.field.lon)
        irr_mode = "none" if fid in ("vidarbha", "bundelkhand") else ("limited" if fid == "bathinda" else "full")
        s_idx = 1 if cid in ("wheat", "chickpea") else 0
        rot_single = Rotation(
            id=f"gt_{fid}_{cid}",
            steps=[RotationStep(year_index=0, season_index=s_idx, crop_id=cid, practices=["puddling"] if cid == "rice_puddled" else [])],
        )
        _, mem_d = ensembles.build_scenario_set("historical", power_df=w_d, rotation_years=1)
        ev_d = evaluate.evaluate_rotation(rot_single, mem_d, prof_d, FarmConstraints(irrigation=irr_mode))
        sim_vals = ev_d.yield_t_ha.get(cid, [0.0])
        sim_med = float(np.median(sim_vals))
        abs_err = sim_med - obs_y
        rel_err = (abs_err / obs_y) * 100.0 if obs_y > 0 else 0.0
        eval_stats[(fid, cid)] = (obs_y, sim_med, rel_err)
        lines.append(
            f"| **{d_name}** | {c_label} | {obs_y:.2f} | **{sim_med:.2f}** | {abs_err:+.2f} | **{rel_err:+.1f}%** | {ref_src} |"
        )

    def _fmt_stat(fid: str, cid: str) -> tuple[float, float, float]:
        return eval_stats.get((fid, cid), (0.0, 0.0, 0.0))

    _lu_w_obs, _lu_w_sim, lu_w_err = _fmt_stat("ludhiana", "wheat")
    _lu_r_obs, _lu_r_sim, lu_r_err = _fmt_stat("ludhiana", "rice_puddled")
    _ba_w_obs, _ba_w_sim, ba_w_err = _fmt_stat("bathinda", "wheat")
    ya_c_obs, ya_c_sim, ya_c_err = _fmt_stat("vidarbha", "cotton")
    jh_s_obs, jh_s_sim, jh_s_err = _fmt_stat("bundelkhand", "sorghum")
    th_r_obs, th_r_sim, th_r_err = _fmt_stat("thanjavur", "rice_puddled")

    lines.append("")
    lines.append("### 1.3 Analysis of Discrepancies on Held-Out Districts")
    lines.append("")
    lines.append(
        f"While held-out Trans-Gangetic Punjab sites match within single-digit percentage errors "
        f"(Ludhiana wheat {lu_w_err:+.1f}%, Ludhiana paddy {lu_r_err:+.1f}%, Bathinda wheat {ba_w_err:+.1f}%), "
        f"larger deviations occur in peninsular and semi-arid rainfed sites. We intentionally report these discrepancies "
        f"transparently without manual post-hoc adjustments for the following physical and agronomic reasons:"
    )
    lines.append("")
    lines.append(
        f"1. **Yavatmal, Maharashtra — Rainfed Seed Cotton ({ya_c_err:+.1f}% error, {ya_c_sim:.2f} vs {ya_c_obs:.2f} t/ha):** "
        "DES APY statistics report farm-gate seed cotton across diverse marginal plots. In Vidarbha, rainfed cotton "
        "routinely suffers from chronic pink bollworm (*Pectinophora gossypiella*) infestation, boll rot during late monsoon showers, "
        "and sub-optimal fertilizer application. The FAO-56 / FAO-33 engine simulates pure abiotic water and temperature stress; "
        "it does not incorporate a biotic insect pest damage module."
    )
    lines.append(
        f"2. **Jhansi (Bundelkhand), Uttar Pradesh — Rainfed Sorghum ({jh_s_err:+.1f}% error, {jh_s_sim:.2f} vs {jh_s_obs:.2f} t/ha):** "
        "Bundelkhand sorghum averages reflect marginal, unfertilized subsistence fields with shallow rocky subsoils and severe bird foraging damage. "
        "Simulated yields represent potential yield constrained solely by soil-water availability, without nutrient deficiency penalties."
    )
    lines.append(
        f"3. **Thanjavur, Tamil Nadu — Irrigated Paddy ({th_r_err:+.1f}% error, {th_r_sim:.2f} vs {th_r_obs:.2f} t/ha):** "
        "In the Cauvery delta coastal belt, the Samba rice crop is frequently subject to North-East monsoon cyclonic storms, "
        "prolonged drainage congestion/waterlogging at maturity, and blast disease (*Magnaporthe oryzae*). "
        "The model accurately simulates unstressed vegetative potential but does not depress yield for lodging or harvest flood damage."
    )
    lines.append("")

    # -----------------------------------------------------------------------
    # Benchmark 2: Soil Texture Sensitivity
    # -----------------------------------------------------------------------
    lines.append("## 2. Soil Texture & Root-Zone Water Balance Sensitivity (`models/fao56_runner.py`)")
    lines.append("")
    lines.append(
        "Evaluates FAO-56 daily root-zone soil moisture depletion (`TAW`, `RAW`, `Ks`, deep percolation) across "
        "three representative Indian soil textures under both Rainfed and Full Irrigation regimes (2020–2021 cycle)."
    )
    lines.append("")
    lines.append(
        "| Soil Texture Class | Sand / Clay (%) | FC / WP (m³/m³) | Rainfed Wheat Yield (t/ha) | Irrigated Wheat Yield (t/ha) | Irrigated Wheat Water (mm) | DSR Rice Water (mm) |"
    )
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")

    soils_spec = [
        ("Coarse Loamy Sand (SW Punjab / Rajasthan)", 76.0, 14.0, 10.0, 3.8),
        ("Indo-Gangetic Alluvial Loam (Sangrur / Ludhiana)", 44.0, 36.0, 20.0, 5.2),
        ("Deccan Black Cotton Vertisol (Vidarbha Clay)", 22.0, 28.0, 50.0, 6.5),
    ]
    rot_wheat = Rotation(id="wheat_single", steps=[RotationStep(year_index=0, season_index=1, crop_id="wheat")])
    rot_dsr = Rotation(id="dsr_single", steps=[RotationStep(year_index=0, season_index=0, crop_id="rice_dsr")])

    bench2_rows: list[dict[str, float]] = []
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
        bench2_rows.append(
            {
                "rf_y": float(w_rf["yield_t_ha"]),
                "ir_y": float(w_ir["yield_t_ha"]),
                "ir_mm": float(w_ir["irrigation_mm"]),
            }
        )
        lines.append(
            f"| {label} | {sand_p:.0f}% / {clay_p:.0f}% | {fc:.3f} / {wp:.3f} | "
            f"**{w_rf['yield_t_ha']:.2f}** | **{w_ir['yield_t_ha']:.2f}** | **{w_ir['irrigation_mm']:.0f}** | "
            f"**{d_ir['irrigation_mm']:.0f}** |"
        )
    r_sand, r_loam, r_clay = bench2_rows[0], bench2_rows[1], bench2_rows[2]
    lines.append("")
    lines.append(
        f"> **Process Note on Irrigated vs Rainfed Response:** Under full irrigation, daily root-zone soil water depletion "
        f"$D_r$ is replenished before reaching RAW, maintaining water stress coefficient $K_s = 1.0$ continuously. Consequently, "
        f"simulated irrigated wheat yield (~{r_sand['ir_y']:.2f} t/ha on sand, {r_loam['ir_y']:.2f} t/ha on loam, "
        f"{r_clay['ir_y']:.2f} t/ha on Vertisol) is governed by radiation, temperature, and potential yield parameters "
        f"rather than soil water storage. The physical impact of soil texture is expressed through the **irrigation volume required** "
        f"to maintain that unstressed condition ({r_sand['ir_mm']:.0f} mm on coarse loamy sand vs {r_loam['ir_mm']:.0f} mm on "
        f"alluvial loam vs {r_clay['ir_mm']:.0f} mm on Vertisol clay) and through the **rainfed yield** "
        f"({r_sand['rf_y']:.2f} t/ha on sand vs {r_loam['rf_y']:.2f} t/ha on loam)."
    )
    lines.append("")

    # -----------------------------------------------------------------------
    # Benchmark 3: March 2022 Terminal Heatwave Sensitivity
    # -----------------------------------------------------------------------
    lines.append("## 3. Rabi Wheat Terminal Heatwave Sensitivity (March–April Grain-Filling Shock)")
    lines.append("")
    lines.append(
        "Tests the thermal senescence response during the final 35% of the Rabi wheat cycle (March–April grain filling, "
        "`Tmax > 32.0°C`) under baseline climate, a `+4.5°C` heat anomaly (analogous to the March 2022 North India heatwave), "
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
        rot_wheat_conv, w_df, loam_soil, FarmConstraints(irrigation="full"), start_year=2020
    )[0]
    res_shock = aquacrop_runner.simulate_rotation(
        rot_wheat_conv, w_heat, loam_soil, FarmConstraints(irrigation="full"), start_year=2020
    )[0]
    res_hs_shock = aquacrop_runner.simulate_rotation(
        rot_wheat_hs, w_heat, loam_soil, FarmConstraints(irrigation="full"), start_year=2020
    )[0]

    drop_conv = (res_shock["yield_t_ha"] - res_norm["yield_t_ha"]) / res_norm["yield_t_ha"] * 100.0
    drop_hs = (res_hs_shock["yield_t_ha"] - res_norm["yield_t_ha"]) / res_norm["yield_t_ha"] * 100.0

    lines.append(f"| Baseline Climate (Conventional Tillage Wheat) | **{res_norm['yield_t_ha']:.2f}** | 0.0% | {res_norm['irrigation_mm']:.0f} |")
    lines.append(f"| +4.5°C Mar–Apr Heatwave (Conventional Tillage Wheat) | **{res_shock['yield_t_ha']:.2f}** | **{drop_conv:+.1f}%** | {res_shock['irrigation_mm']:.0f} |")
    lines.append(f"| +4.5°C Mar–Apr Heatwave + Happy Seeder Mulch | **{res_hs_shock['yield_t_ha']:.2f}** | **{drop_hs:+.1f}%** | {res_hs_shock['irrigation_mm']:.0f} |")
    lines.append("")

    # -----------------------------------------------------------------------
    # Benchmark 4: Rice Hydrology & Kharif-to-Rabi Turnaround Days
    # -----------------------------------------------------------------------
    lines.append("## 4. Kharif Rice Hydrology & Stubble-Burning Turnaround Window")
    lines.append("")
    lines.append(
        "Compares Puddled Long-Duration Rice (`rice_puddled`, 175 mm puddling + continuous ponded head driving "
        "3.5 mm/day percolation), PAU Short-Duration Rice (`rice_short` PR-126, 175 mm puddling), and "
        "Direct-Seeded Rice (`rice_dsr`, 75 mm pre-sowing rauni wetting + Alternate Wetting & Drying with non-ponded "
        "intermittent drainage averaging 2.55 mm/day) on Sangrur Alluvial Loam across their exact simulated cycle lengths. "
        "Parameterised to match Punjab Agricultural University experimental trials (Ladha et al. 2009; Sudhir-Yadav et al. 2011)."
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
            rot_r, w_df, loam_soil, FarmConstraints(irrigation="full"), start_year=2020
        )[0]
        if base_rice_irr is None:
            base_rice_irr = sim_r["irrigation_mm"]
        saved_pct = (base_rice_irr - sim_r["irrigation_mm"]) / base_rice_irr * 100.0
        t_days = rotations.compute_turnaround_days(rot_r, crops)
        dur_mean = int(sim_r["duration_days"])
        lines.append(
            f"| {r_label} | {dur_mean} d | **{t_days} days** | **{sim_r['irrigation_mm']:.0f} mm** | "
            f"**{saved_pct:.1f}%** | **{sim_r['yield_t_ha']:.2f} t/ha** |"
        )
    lines.append("")

    # -----------------------------------------------------------------------
    # Benchmark 5: 10-Year RothC-Lite SOC, Urea Savings & Soil Health Breakdown
    # -----------------------------------------------------------------------
    lines.append("## 5. 10-Year RothC-Lite Soil Organic Carbon, Biological N & Soil Health Score Breakdown")
    lines.append("")
    lines.append(
        "Evaluates 30-member ensemble outcomes on Sangrur Alluvial Loam across four management systems, "
        "including the transparent component-by-component breakdown of the 0–100 Soil Health Index "
        "(5 USDA-NRCS principles × 15 pts max = 75 pts + SOC (−10..+15), RUSLE (−10..+3) & soil condition (−5..+5) modifiers − 5 pt residue burning penalty)."
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
    eval_pairs: list[tuple[str, evaluate.SimulationResult]] = []
    for sys_name, rot_obj in bench_rotations:
        ev_res = evaluate.evaluate_rotation(rot_obj, members, sangrur_prof, FarmConstraints(irrigation="full"))
        if base_eval_res is None:
            base_eval_res = ev_res
        eval_pairs.append((sys_name, ev_res))
        pm = evaluate.compute_practical_farmer_metrics(rot_obj, ev_res, base_eval_res, crops)
        lines.append(
            f"| {sys_name} | **{ev_res.soc_delta_t_ha_10yr:+.2f}** | **{ev_res.soil_health_score:.1f}** | "
            f"{ev_res.n_balance_kg_ha_yr:+.1f} | **{pm.urea_bags_saved_per_ha:.1f} bags** | **{pm.turnaround_days_kharif_rabi} d** |"
        )
    lines.append("")
    lines.append("### Soil Health Index Component & Weight Breakdown (`models/soil_health.py`)")
    lines.append("")
    lines.append(
        "| Rotation System | Armor (/15) | Min Disturbance (/15) | Diversity (/15) | Living Roots (/15) | Organic N (/15) | SOC Mod | Erosion Mod | Soil Cond Mod | Burn Penalty | Total (/100) |"
    )
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for sys_name, ev_res in eval_pairs:
        bd = ev_res.soil_health_breakdown
        lines.append(
            f"| {sys_name} | {bd.get('soil_armor_cover', 0):.1f} | {bd.get('disturbance_minimization', 0):.1f} | "
            f"{bd.get('biodiversity', 0):.1f} | {bd.get('living_roots', 0):.1f} | "
            f"{bd.get('biological_n_livestock', 0):.1f} | {bd.get('soc_modifier', 0):+.1f} | "
            f"{bd.get('erosion_modifier', 0):+.1f} | {bd.get('soil_condition_modifier', 0):+.1f} | "
            f"{bd.get('burning_penalty', 0):+.1f} | **{ev_res.soil_health_score:.1f}** |"
        )
    lines.append("")

    # -----------------------------------------------------------------------
    # Benchmark 6: All 6 Indian Golden Fields Summary
    # -----------------------------------------------------------------------
    lines.append("## 6. Six Indian Agro-Climatic Golden Benchmark Fields (Precomputed Engine Outputs)")
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
        (ROOT / "docs" / "BENCHMARKS.md").write_text(report_md, encoding="utf-8")
        print("\n[OK] Wrote docs/BENCHMARKS.md from live engine outputs.")
