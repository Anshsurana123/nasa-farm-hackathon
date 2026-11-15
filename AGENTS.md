# AGENTS.md: Instructions for AI Coding Agents

> **Read this entire file before changing anything.** It is the source of truth for working in this repository.
> - `docs/BUILD_PLAN.md` — architecture & design specification
> - `docs/METHODOLOGY.md` — biophysical science & cited equations
> - `docs/BENCHMARKS.md` — empirical calibration & sensitivity report (**script-generated**, never hand-edited)
> - `docs/DATASETS.md` — NASA, sponsor Meteomatics & ancillary dataset registry (product IDs, resolutions, DOIs/URLs)
> - `docs/NOTES.md` — historical findings, calibration rationales & architectural decisions
> - `docs/AUDIT.md`, `docs/AUDIT_V2.md`, `docs/AUDIT_V3.md` — closed security/science audit trails
> - `docs/FARMER_GUIDE.md`, `docs/JUDGE_QA.md`, `docs/MAGIC_NUMBERS.md`, `docs/SUBMISSION.md` — domain & judge references
> - `apps/web/AGENTS.md` — Next.js-managed agent file (preserve its `BEGIN:nextjs-agent-rules` / `END:nextjs-agent-rules` block)
> - If any doc and the code disagree, **trust the code**, then fix the doc in the same change.
> - **Code navigation:** query Graphify (`graphify-out/`) first for structural paths, `rg` for literal constants/keys, and read source files directly before editing (Section 3.3).

---

## 1. What This Project Is

**TerraLoop** is an open-science, biophysically grounded crop-rotation decision-support system built for the **NASA Space Apps Challenge** ("Crop Rotations Planned with NASA Earth Observations").

### Core Challenge Pillars
Every feature, model, and UI panel serves these core dimensions:
1. **Shifting Temperatures:** March–April wheat terminal grain-filling heat stress ($T_{\max} > 32.0^\circ\text{C}$ over final 35% of cycle) buffered by Happy Seeder surface residue mulch ($-1.0^\circ\text{C}$ soil/canopy cooling), alongside IGP MERRA-2 irrigated cooling bias correction (Ambika & Mishra 2019; 12-month lookup peaking at $-4.5^\circ\text{C}$ in March).
2. **Changing Rainfall Patterns:** Erratic monsoon distribution, longest dry-spell diagnostics, wettest 4-month windows, extreme rainfall days ($> 50\text{ mm/d}$), GPM IMERG V07 precipitation, and sub-daily kinetic storm erosivity (`r_factor_intensity`) in RUSLE.
3. **Water Shortages & Aquifer Depletion:** Regional aquifer decline from NASA GRACE/GRACE-FO mascons ($-3.85\text{ cm/yr}$ central Punjab zone baseline; $-4.15\text{ cm/yr}$ observed/golden Sangrur/Ludhiana/Bathinda JPL RL06 V04 mascon) dynamically scaling `water_savings` optimization weight up to $1.50\times$, coupled with NASA SMAP L4 root-zone moisture suitability modulation and Meteomatics 90m 4-layer seedbed moisture deficit (`initial_depletion_mm`).
4. **Extreme Weather & Stubble Burning:** Post-harvest residue burning monitored via NASA FIRMS (MODIS/VIIRS active fires), mitigated by shifting from late-maturing puddled rice (*Pusa-44*, 11-day Kharif–Rabi turnaround) to DSR Rice + AWD, PR-126 Short-Duration Rice, or Maize/Pulses (expanding turnaround to 26–34 days) and Happy Seeder zero-till drilling.
5. **Declining Soil Health:** 10-year 5-pool Soil Organic Carbon dynamics (RothC-lite 26.3), species-specific symbiotic biological nitrogen fixation + residue N mass balance (`models/soil_health.py`), and a transparent 0–100 composite USDA-NRCS Soil Health Index.
6. **Local Soil Information & Crop Characteristics:** Depth-weighted ISRIC SoilGrids 2.0 (250 m via REST with 3 km urban-mask neighborhood search and GEE asset fallback) overridable by farmer **Government Soil Health Card (SHC)** lab values (`pH`, `SOC %`, `N`, `P`, `K` kg/ha), paired with a 23-crop ICAR/PAU agronomic knowledge base (`packages/crop-kb/`).
7. **Farmer Priorities & Downside Risk:** 6-objective NSGA-II multi-objective Pareto optimization (`profit`, `water_savings`, `soil_health`, `low_risk` $CVaR_{10}$, `low_labour`, `food_security`) evaluated across 30-year historical weather moving blocks or 5–6 CMIP6 GCM projections (NASA NEX-GDDP-CMIP6 + Meteomatics `MRI-ESM2.0`) under optional drought, market price, and fertilizer shocks.

### Operational Context & Scope Honesty
- **Lead Demo Story (`sangrur`, `ludhiana` in Punjab):** Replacing conventional puddled transplanted rice $\rightarrow$ wheat (`1,168.0 mm/yr` irrigation, `11d` turnaround, `-1.92 t C/ha/10yr` SOC, `22.3/100` soil health, `₹170,334/ha` P50, `₹77,208/ha` $CVaR_{10}$ on `sangrur` snapshot `2026-11-13`) with Top-3 alternatives (`DSR Rice → Sunflower → Mung bean`, `Maize → Sunflower → Mung bean`, `Mung bean → Wheat → Blackgram`) saves **17.6–60.1% irrigation water** (`113–386` borewell pumping hrs/ha), expands turnaround to **26–34 days**, sequesters **`+1.42` to `+3.29 t C/ha` SOC over 10 years**, and saves **3.5–4.1 bags (45 kg) of Urea/ha**.
- **Six Precomputed Golden Benchmark Fields** (`data/golden/<id>/` mirrored cleanly to `apps/web/public/golden/<id>/`):
  1. `sangrur` (Punjab): Trans-Gangetic alluvial plains (`30.19, 75.78`)
  2. `ludhiana` (Punjab): PAU central alluvial plains (`30.82, 75.68`)
  3. `bathinda` (Punjab): South-Western semi-arid cotton–wheat belt (`30.12, 74.86`)
  4. `bundelkhand` (Jhansi, UP): Central Plateau & Hills semi-arid pulse–cereal zone (`25.38, 78.62`)
  5. `vidarbha` (Yavatmal, Maharashtra): Deccan Black Vertisol cotton–chickpea belt (`20.39, 78.13`)
  6. `thanjavur` (Tamil Nadu): Cauvery Delta double-paddy & rice-fallow pulse relay system (`10.72, 79.25`)
- **Pan-India Registry & Global Honest Mode (`region_registry.py`):**
  - 36 Indian States/UTs (`packages/crop-kb/regions/india_states.geojson` with `0.04°` coastal snapping) map to **17 named ICAR agro-climatic zones** (+ `default_zone`), **5 state CACP 2024–25 economic budgets** (`punjab`, `haryana`, `uttar_pradesh`, `maharashtra`, `tamil_nadu`), and **16 Central + State agricultural schemes** (`packages/crop-kb/schemes/*.yaml`).
  - Any location **outside India** enters explicit `validation_status = "unvalidated_global"` mode (`USD/$` proxy display currency, global latitude-band synthetic climatology & FAO soil fallbacks). Crucially, `main.py` passes `allow_economic_ranking = (profile.validation_status != "unvalidated_global")` into `selection.py::select_top()`, which invokes `effective_priorities()` to **zero out India-proxy economic objectives (`profit`, `low_risk`, `low_labour`)** and rank strictly on biophysical objectives (`water_savings`, `soil_health`, `food_security`) alongside visible frontend disclaimers.
- **NASA GIBS Context Layers & Meteomatics Sponsor Integration:**
  - Interactive NASA GIBS WMTS overlays (`VIIRS_SNPP_CorrectedReflectance_TrueColor`, `SMAP_L4_Analyzed_Root_Zone_Soil_Moisture`, `MODIS_Terra_NDVI_8Day`) in `FieldMap.tsx` are strictly visual **`context only`** overlays and clearly labeled as such.
  - Optional Meteomatics 90m Sponsor API (`data/meteomatics.py`) enriches live profiles with 90m MIX/SRTM meteorology, 4-layer soil moisture & `initial_depletion_mm`, biotic blight/wetness/hail/fire hazards, 7-day `/tactical-advisory`, sub-daily $I_{30}$ RUSLE intensity, and `MRI-ESM2.0` as a 6th CMIP6 ensemble member — gracefully degrading when credentials (`METEOMATICS_USERNAME` / `METEOMATICS_PASSWORD`) are absent or offline.

---

## 2. Current Phase: Hardening & Maintenance

All core phases, audit items (`docs/AUDIT.md`, `docs/AUDIT_V2.md`, `docs/AUDIT_V3.md`), GIBS visual overlays, Meteomatics 90m coupling, pan-India 17-zone/5-state registry, and `unvalidated_global` biophysical ranking guards are implemented and verified with **114 passing offline pytest cases** (`test_deploy.py`: 4, `test_engine.py`: 89, `test_models.py`: 16 test functions / 21 parametrized cases).

Work comes in strict priority order:
1. **The user's explicit request.**
2. **Open items in `docs/AUDIT.md` or `docs/NOTES.md`.**
3. **Bug fixes or scientific calibration extensions backed by peer-reviewed sources.**

> **Golden Rule of Execution:** One cohesive change at a time — **code + test + docs**, then run Python & frontend verification gates before committing.

---

## 3. Repository Map, Request Flow & Graphify Navigation

### 3.1 Repository Map
```
pyproject.toml                         uv workspace root (Python >=3.11); pytest & ruff (line-length=120)
uv.lock / requirements.txt             Locked workspace & flat pip/Vercel requirements
vercel.json / api/index.py             Vercel multi-service config (api + web bindings) & FastAPI serverless entry
Dockerfile / .dockerignore             Python 3.11-slim + uv container running terraloop_api.main:app on :8000
.env.example / .vercelignore           Environment template & slim deployment ignore rules
LICENSE                                MIT License (TerraLoop Contributors, 2026)
.github/workflows/ci.yml               GitHub Actions: ruff check, offline pytest, BENCHMARKS.md diff guard, tsc & eslint

packages/schemas/                      SHARED PYDANTIC V2 CONTRACTS (mirrored in apps/web/src/types/api.ts)
  terraloop_schemas/__init__.py        Public exports
  terraloop_schemas/models.py          FieldGeometry, FieldProfile, TacticalAdvisory, CropSpec, Priorities, StrategyRecommendation, etc.
  terraloop_schemas/export.py          JSON Schema exporter (`python -m terraloop_schemas.export`)

packages/engine/                       BIOPHYSICAL SCIENCE, EO, CLIMATE & OPTIMIZATION ENGINE (zero web framework imports)
  pyproject.toml                       Core deps include earthengine-api, google-auth, httpx, numpy, pandas, pydantic, pyyaml
  terraloop_engine/
    profiler.py                        build_profile(FieldGeometry) -> FieldProfile (parallel 12-future pool + single-flight dedup)
    suitability.py                     Heuristic crop pre-filter (rank_crops: SMAP, GRACE, SHC N/P/K/pH, Meteomatics biotic/hail/drought)
    crop_kb.py                         Loads packages/crop-kb/crops/*.yaml + aquacrop_params/*.yaml -> dict[str, CropSpec]
    region_registry.py                 36-state/UT GeoJSON + 17 Indian ICAR zones + default_zone + unvalidated_global fallbacks
    scheme_kb.py                       16 Central & State agricultural support schemes with localized en/hi/pa matching
    cache.py                           @disk_cache(namespace=...) (`<repo>/data/cache`, unwritable fallback `<tempdir>/terraloop-cache`)
    data/
      nasa_power.py                    NASA POWER REST daily client, 0.5°×0.625° grid snap, IGP MERRA-2 12-month Tmax bias lookup
      soilgrids.py                     ISRIC SoilGrids 2.0 250m REST + 3 km urban-mask offset + GEE asset fallback
      gee.py                           Google Earth Engine client (8 NASA collections + headless JSON/base64/file SA auth)
      meteomatics.py                   Meteomatics 90m MIX/SRTM, 4-layer soil hydrology, hazards, tactical 7d forecast, MRI-ESM2.0
    eo/
      phenology.py                     5-day NDVI resampling, pure-NumPy Savitzky-Golay smooth, prominence-adaptive season detection
      classifier.py                    Gaussian ML PhenologyCropClassifier with circular DOY wrapping
    climate/
      ensembles.py                     30-yr historical moving blocks, 5 NEX-GDDP-CMIP6 GCMs + MRI-ESM2.0, Cannon tail quantile mapping
    models/
      agroclimate.py                   FAO-56 Penman-Monteith ET0 primary, Hargreaves ET0 fallback, Ra, GDD, dry spells, wettest window
      soil.py                          12-class USDA texture triangle & Saxton-Rawls (2006) FC/WP hydraulics
      fao56_runner.py                  Daily FAO-56 / FAO-33 root-zone depletion, PTR vs DSR+AWD percolation, March heat & mulch cooling
      aquacrop_runner.py               Backward-compatible re-export shim forwarding to fao56_runner.py
      soil_health.py                   RothC-lite 26.3 5-pool SOC model, species-specific N balance, 0–100 NRCS Soil Health Index
      rusle.py                         RUSLE A = R·K·LS·C·P with kinetic storm-intensity r_factor_intensity
      economics.py                     CACP 2024–25 A2+FL state budgets, irrigation/mulch/legume adjustments, P10/P50/P90 & CVaR-10 + CI
      nutrition.py                     ICMR-NIN (2020) caloric/protein yield & [0, 1] food_security_score (Liebig minimum)
      surrogate.py                     Pure-NumPy PolynomialRidgeSurrogate for >85-candidate pre-screening
    optimize/
      rotations.py                     1/2/3-year Kharif/Rabi/Zaid rotation generator, bad_predecessor & seed turnaround constraints
      evaluate.py                      Multi-scenario ensemble simulator + practical metrics (Urea bags, pumping hrs, turnaround days)
      selection.py                     NSGA-II non-dominated sorting, MIN_SPREADS weighting, diversity filter & allow_economic_ranking gate
    explain/
      why_cards.py                     Deterministic trilingual why-cards + optional Gemini Flash synthesis gated by numeric grounding check

packages/crop-kb/                      DOMAIN DATA IN YAML / GEOJSON (no magic params in Python)
  crops/*.yaml (+ _template.yaml)      23 crops + parameter template
  aquacrop_params/*.yaml               9 calibrated pulse/oilseed/fodder parameter overrides
  economics/*.yaml                     5 state budgets (punjab, haryana, uttar_pradesh, maharashtra, tamil_nadu)
  regions/                             india_states.geojson (36 States/UTs), zones.yaml (17 + default), soils.yaml, synthetic_weather.yaml
  schemes/*.yaml                       central.yaml (4) + punjab (3) + uttar_pradesh (4) + maharashtra (2) + tamil_nadu (2) + haryana (1)

apps/api/terraloop_api/main.py         FastAPI v0.2.0: 12 endpoints, /api prefix middleware, 60/min IP rate limiter, async job store
apps/web/                              Next.js 16 + React 19 + Tailwind CSS v4 + MapLibre GL 6 + 7 routes + 739 i18n keys (en/hi/pa)
data/                                  golden/<id>/ (6 precomputed fields + weather + gee_audit_log.json), benchmarks/district_ground_truth.csv, jobs/
scripts/                               run_validation_benchmarks.py, precompute_golden.py, warm_cache.py, check_api_health.py, md_to_docx.py
tests/                                 test_engine.py (89), test_models.py (16 / 21 cases), test_deploy.py (4) — 114 offline tests
```

### 3.2 End-to-End Request Flow (`POST /recommend` & `/recommend/async`)
```
FieldGeometry (lat, lon, polygon <=500 pts / <=10,000 ha)
  │
  ├─► [Exact golden field ID match & no custom profile needed?] ─► Instant data/golden/<id>/profile.json
  │   └─► Else profiler.build_profile: 12-future parallel pool (24s cap, single-flight dedup)
  │       ├── NASA POWER + GPM IMERG + SMAP L4 + GRACE-FO + NASADEM + FIRMS + HLS L30/S30 + ISRIC SoilGrids
  │       ├── Optional Meteomatics 90m fusion (daily weather overlay, 4-layer soil deficit, hazards, SRTM slope, 7d forecast)
  │       └── Explicit fallback hierarchy: observed -> hybrid -> regional_climatology (17 Indian zones) -> unvalidated_global
  │
  ├─► Optional Farmer Inputs: SoilHealthCardInput (pH, SOC%, N, P, K), baseline_override, climate_scenario, shocks
  │
  ├─► ensembles: 30-yr historical moving blocks OR 5 NEX-GDDP-CMIP6 GCMs (+ optional 6th Meteomatics MRI-ESM2.0)
  │
  ├─► suitability.rank_crops ──► Pruned crop shortlist (seasonal fit, SMAP, GRACE, SHC N/P/K/pH, Meteomatics hazards)
  │
  ├─► rotations.generate_rotations (+ surrogate.py pre-screening if candidate count > 85)
  │
  ├─► evaluate.evaluate_rotations_ensemble (parallel climate member evaluation):
  │     fao56_runner -> soil_health (RothC + N balance + NRCS 0–100) -> rusle (r_factor_intensity) -> economics -> nutrition
  │
  ├─► selection.select_top(..., allow_economic_ranking = validation_status != "unvalidated_global")
  │     └── effective_priorities -> weighted MIN_SPREADS + NSGA-II Pareto + distinct (Kharif, Rabi) / family diversity -> Top 3
  │
  └─► explain.why_cards + scheme_kb.match_schemes + practical metrics + optional Gemini grounded narrative
        └── Returns [Baseline Rank 0, Strategy #1, Strategy #2, Strategy #3]
```

### 3.3 Navigating the Code with Graphify
A persistent Graphify knowledge graph lives in `graphify-out/` (`GRAPH_REPORT.md`, `graph.json`, `graph.html`).
1. **Query structure first:** use `graphify query`, `graphify explain "<symbol>"`, or `graphify path "<A>" "<B>"`, or read sections of `graphify-out/GRAPH_REPORT.md` (never dump `graph.json` into context).
2. **Use `rg` for literals:** constants (`32.0`, `85`, `20.7`), YAML keys, region IDs, and i18n keys live in literals—always grep with `rg`.
3. **Verify in source:** always read the actual file slice before editing; inferred cross-language links are hints only.
4. **Exclusions:** exclude `node_modules`, `.next`, `uv.lock`, `apps/web/package-lock.json`, `apps/web/public/maplibre/`, `data/golden/*/weather.json`, and `data/cache/` when rebuilding with `graphify .`.
5. **Structure ≠ correctness:** test & equation validity comes from `tests/`, `docs/BENCHMARKS.md`, and cited literature, not graph edges.

---

## 4. The 15 Golden Engineering & Science Rules

1. **NASA Data First, and It Must Matter:** Prioritize NASA EO streams. Any purely visual layer (such as NASA GIBS WMTS overlays in `FieldMap.tsx`) must be visibly tagged `context only`. Register every data stream in `docs/DATASETS.md` with collection ID and DOI/URL.
2. **Provenance on Every Number:** Every user-facing metric must trace to a `DataProvenance` model (`source`, `product`, `period`, `resolution`, `doi`, `url`, `mode`).
3. **Never Invent Numbers:** LLM narratives (`why_cards.py::grounded_llm_explain`) must only phrase pre-computed engine outputs and are gated by `verify_llm_numeric_grounding` (5% numeric tolerance). Unsourced agronomic values must not be guessed.
4. **Never Crash, Never Mislead:** External API timeouts/outages degrade gracefully to cached or clearly labeled `regional_climatology` / `fallback_synthetic` / `demo_snapshot` outputs with `is_fallback=True` where applicable. Never swap another parcel's results in for a failed `/recommend` request.
5. **Farmer Priorities Must Steer the Result:** Changes to `Priorities` weights must shift rankings monotonically (validated by a 200-vector 4-field monotonicity sweep in `test_engine.py`), except inside `unvalidated_global` where `allow_economic_ranking=False` explicitly restricts ranking to biophysical weights.
6. **Pure Functions for Science Models:** Modules in `packages/engine/terraloop_engine/models/` accept numbers, NumPy arrays, or DataFrames and return pure data with zero network calls, zero file I/O, and zero unseeded randomness. Keep cited equations and SI units in docstrings (modelled on `rusle.py`).
7. **Calibration Is Not Validation:** Sangrur serves as the calibration site; Ludhiana, Bathinda, Yavatmal, Jhansi, and Thanjavur are held-out evaluation districts (`data/benchmarks/district_ground_truth.csv`). Never tweak physical constants solely to pass a test.
8. **No Geographic Hardcoding Outside Config:** Never scatter `lat >= ...` / `lon <= ...` bounding boxes in models. Put zones, state economics, soils, weather climatologies, and `igp_merra2_bias_correction` flags in `packages/crop-kb/` + `region_registry.py`.
9. **Contracts First (Pydantic v2 ↔ TypeScript):** Update `packages/schemas/terraloop_schemas/models.py` (with backward-compatible defaults so existing golden JSONs validate) and `apps/web/src/types/api.ts` in lockstep (enforced by `test_schema_typescript_interface_parity`).
10. **Cache Every Live External Call, Never Fabricate Missing Obs:** Wrap external calls with `@disk_cache(namespace=...)` (live responses only). Optional feeds log warnings and leave fields `None` when offline (`test_build_profile_offline_never_emits_observed_for_satellite_products`).
11. **Agronomic & Economic Parameters Belong in YAML:** Add/edit crops in `packages/crop-kb/crops/*.yaml` (using `_template.yaml`), AquaCrop parameters in `aquacrop_params/*.yaml`, budgets in `economics/*.yaml`, schemes in `schemes/*.yaml`.
12. **Standard Units & Clear Naming:** `mm` water, `°C` temperature, `t/ha` yield/SOC, `kg N/ha`, `%` sand/silt/clay, `g/kg` SOC, `days`, `₹/ha` (or USD proxy in `unvalidated_global`). Disambiguate names (`irrigation_mm`, `yield_t_ha`, `soc_delta_t_ha_10yr`).
13. **Smallest Correct Change:** Fix defects locally without unrequested rewrites of unrelated working modules.
14. **Benchmark Numbers Originate from Scripts:** Never hand-edit `docs/BENCHMARKS.md`. Regenerate via `uv run python scripts/run_validation_benchmarks.py --write-docs`; CI verifies with `git diff --exit-code docs/BENCHMARKS.md`.
15. **Secrets Safety:** Never commit `.env` files, API tokens, or service account keys. Use `.env.example`.

---

## 5. Farmer-First UI & Trilingual Standards

- **Trilingual Parity (739 keys):** All UI copy in `apps/web/src/i18n/{en,hi,pa}.json` must maintain 100% key parity (enforced by `test_i18n_key_parity_and_no_hardcoded_jsx_error_strings`). Engine `why_cards.py` and `schemes/*.yaml` also provide native English, Hindi (Devanagari), and Punjabi (Gurmukhi) strings.
- **Plain Language First:** Surface $CVaR_{10}$ as *"Income in a severe drought year"*, FAO-56 water savings as *"Borewell pumping hours saved"* + *"75 mm irrigations saved"*, N balance as *"45-kg Urea bags saved/ha"*, RothC SOC as *"Soil carbon built over 10 years"*, and support 1-click `/Acre (Killa)` conversion (`1 ha = 2.47105 acres`). Keep technical equations in `/methodology` and collapsible drawers.
- **7 Frontend App Routes (`apps/web/src/app/`):**
  - `/` — Home workspace (3D `FieldMap` with Esri/OSM/NASA GIBS WMTS overlays + geocoder, live `TelemetryBar`, `SoilColumn3D` 5-layer canvas stratigraphy, quick summary)
  - `/diagnostics` — Full satellite & SHC lab `ReportCard` (climate hyetograph, hydraulics, GRACE/SMAP, hazards, Soil Health Card inputs, baseline confirmation)
  - `/rotations` — `RotationExplorer` (priorities/personas, constraints, `/Acre` toggle, top-3 cards, seasonal Gantt calendar, USDA Radar + score breakdown)
  - `/lab` — Pareto Explorer (2D/3D scatter) & Climate/Price Stress Lab (CMIP6 SSPs + drought/mandi/fertilizer shocks)
  - `/crops` — 23-crop Agronomic Atlas with suitability scores, Kc curves, N demand/fixation & predecessor compatibility
  - `/brief` — `AgronomicBrief` printable KVK field prescription with farm-scale multiplier & matched government schemes
  - `/methodology` — Complete dataset DOIs, biophysical equations, and transparent limitation reference
- **10 Components (`apps/web/src/components/`):** `AppShell`, `Navbar`, `TelemetryBar`, `FieldMap`, `SoilColumn3D`, `ReportCard`, `RotationExplorer`, `AgronomicBrief`, `ProgressRing`, `ProvenanceChip`.

---

## 6. Verified Biophysical Models Reference

### 6.1 Agroclimatology & ET0 (`models/agroclimate.py`, `data/nasa_power.py`)
- **Primary Reference ET (`ET0`):** `et0_penman_monteith_series` computes FAO-56 Penman–Monteith ET0 whenever radiation, RH, and wind exceed 50% availability, automatically falling back to `et0_hargreaves` (`0.0023 · 0.408 · Ra · (Tmean + 17.8) · √(Tmax - Tmin)`) otherwise.
- **IGP Irrigated Cooling Bias Correction (`nasa_power.py`):** Applied where `igp_merra2_bias_correction=True` in `zones.yaml` using `_IGP_MONTHLY_TMAX_BIAS_C` (peaking at `-4.5°C` in March, `-4.2°C` July, `-3.8°C` April, `-2.5°C` Feb; calibrated against IMD Station 42099 Ludhiana PAU & Station 42101 Patiala normals per Ambika & Mishra 2019, `10.1029/2019GL084367`).

### 6.2 Daily Soil-Water & Thermal Stress (`models/fao56_runner.py`; shim: `models/aquacrop_runner.py`)
- **Evapotranspiration & Depletion:** Piecewise linear $K_c(t)$ ($K_{c,\text{ini}}, K_{c,\text{mid}}, K_{c,\text{end}}$); `happy_seeder` / `residue_retained` lowers surface evaporation ($K_c \times 0.90$). Saxton–Rawls (2006) derives $\theta_{\text{FC}}, \theta_{\text{WP}}$ so $\text{TAW} = 1000(\theta_{\text{FC}}-\theta_{\text{WP}})Z_r$, $\text{RAW} = p \cdot \text{TAW}$, and stress coefficient $K_s(t) = (\text{TAW} - D_{r,t})/((1-p)\text{TAW})$ when $D_{r,t} > \text{RAW}$. FAO-33 yield response: $1 - Y/Y_{\max} = K_y(1 - \sum \text{ET}_a / \sum \text{ET}_c)$.
- **Meteomatics Deficit Coupling:** Accepts live `initial_depletion_mm` from Meteomatics 90m 4-layer hydrology as starting $D_{r,0}$.
- **Rice Hydrology:**
  - *Puddled Rice (`rice_puddled`, `rice_short`, `basmati`):* `175 mm` puddling/soaking + continuous ponded percolation (`~3.5 mm/day` on alluvial loam).
  - *Direct-Seeded Rice (`rice_dsr` + AWD):* `75 mm` *rauni* wetting + unsaturated pulse percolation averaging `~2.55 mm/day` on loam (`24–28%` irrigation reduction; coarse sand `>55%` raises percolation to `4.2 mm/day`).
- **March Wheat Terminal Heat Stress:** During the final 35% of cool-season Rabi grain-filling, thermal penalty accumulates at `0.018` per degree-day above $32.0^\circ\text{C}$. Happy Seeder surface mulch cools canopy/topsoil by **$-1.0^\circ\text{C}$**, cutting `+4.5°C` heatwave yield loss from **-16.7% to -10.8%** (`docs/BENCHMARKS.md` Section 3).

### 6.3 RothC-Lite 26.3, N Mass Balance & NRCS Soil Health (`models/soil_health.py`)
- **RothC-Lite 26.3 (10-yr monthly):** 5 pools (`DPM` $k=10.0$, `RPM` $k=0.30$, `BIO` $k=0.66$, `HUM` $k=0.02\text{ yr}^{-1}$, Falloon `IOM = 0.049 * C^1.139`) with temperature $a(T)$, moisture $b(M)$, cover $c_{\text{cov}}$ (`0.6` covered / `1.0` bare) modifiers and clay $\text{CO}_2$-partitioning $x = 1.67(1.85 + 1.60\exp(-0.0786 \cdot \text{clay}))$. Burning retains only ~10% ash carbon (`-1.92 t C/ha/10yr` in baseline Sangrur), whereas mulch retention builds `+3.19` to `+4.01 t C/ha/10yr` across benchmark strategies.
- **Seasonal Nitrogen Mass Balance:** Species-specific preceding legume N credit is computed dynamically as `clip(n_fix * (0.50 if residue_retained else 0.35), 15.0, 45.0)` kg N/ha (fallback `25.0` only when no preceding `CropSpec` is supplied), plus `12.0 kg N/ha` non-legume retained-residue mineralization and optional Soil Health Card available N credit (`urea_bags_saved = ann_n_saved_kg / 20.7` for 45-kg 46%-N Urea bags).
- **Composite Soil Health Index (0–100):**
  $$\text{Score} = \underbrace{\text{Armor}_{/15} + \text{MinDisturb}_{/15} + \text{Diversity}_{/15} + \text{LivingRoots}_{/15} + \text{OrganicN}_{/15}}_{75\text{ max USDA-NRCS points}} + \text{SOCMod}_{[-10,+15]} + \text{ErosionMod}_{[-10,+3]} + \text{SoilCondMod}_{[-5,+5]} - \text{BurnPenalty}_{5\text{ or }0}$$

### 6.4 Kinetic RUSLE (`models/rusle.py`)
- Computes $A = R \cdot K \cdot LS \cdot C \cdot P$.
- `r_factor_intensity(annual_precip_mm, max_30m_rate_mmh, extreme_rain_days_per_yr)` couples Renard–Freimund annual $R$ with Brown–Foster / Wischmeier–Smith storm kinetic energy $I_{30}$ and extreme rain frequency ($>50\text{ mm/d}$), preserving baseline `r_factor_annual` when $I_{30} \le 25\text{ mm/h}$ or absent so dry-day snapshots never artificially depress erosion risk.

### 6.5 Economics, Nutrition, Surrogate & Explainability
- **Economics (`models/economics.py`):** Loads CACP 2024–25 A2+FL state budgets (`TERRALOOP_ECONOMICS` or detected region YAML across 5 calibrated Indian states, else labeled `punjab_proxy`), adjusts variable irrigation pumping & tillage/residue costs, applies `-₹650/ha` legume N credit, and reports median P50, P10/P90 spread, and $CVaR_{10}$ downside income with bootstrap CI (`cvar_bootstrap_ci`).
- **Nutrition (`models/nutrition.py`):** ICMR-NIN (2020) `CROP_NUTRITIVE_VALUE` computes `annual_energy_mcal_ha`, `annual_protein_kg_ha`, `households_nourished` (Liebig minimum against 5-member household RDA: `4,015 Mcal/yr`, `91.25 kg protein/yr`), and `[0, 1]` `food_security_score`.
- **Surrogate Pre-Screening (`models/surrogate.py`, `main.py`):** `PolynomialRidgeSurrogate` (degree 2) activates when generated candidate rotations exceed **85** (`len(candidate_rotations) > 85`), pruning safely before full ensemble simulation.
- **EO Phenology & Classifier (`eo/phenology.py`, `eo/classifier.py`):** 5-day NDVI resample + pure-NumPy Savitzky–Golay smoothing (`window=9, poly=2`) + prominence-adaptive peak detection (`>= 0.15` normal / adaptive down to `0.07` on sparse dryland Vertisols) + circular-DOY Gaussian ML `PhenologyCropClassifier`.
- **Grounded Explainability (`explain/why_cards.py`):** Deterministic multilingual `why_cards` and `baseline_why_cards` in `en`/`hi`/`pa`. Optional LLM synthesis in `grounded_llm_explain` calls Gemini REST (`x-goog-api-key`, 2.5s timeout, 429/401/403/404 cooldown circuit breaker) using `GEMINI_MODEL` / `LLM_MODEL` (runtime default `gemini-2.0-flash`; `.env.example` specifies `gemini-3.8-flash`) and rejects any response whose numbers fail `verify_llm_numeric_grounding` (5% tolerance). Disabled when `TERRALOOP_DISABLE_LLM` is truthy or no API key is set.

---

## 7. Crops, Zones, Endpoints & Environment Variables

### 7.1 23 Crops in `packages/crop-kb/crops/*.yaml` (+ `_template.yaml` & 9 `aquacrop_params/*.yaml` overrides)
| Group | Crops (IDs) | Key Agronomic Notes |
|---|---|---|
| **Cereals (9)** | `rice_puddled`, `rice_short` (PR-126), `rice_dsr`, `basmati`, `wheat`, `maize`, `pearl_millet`, `sorghum`, `barley` | `rice_dsr` cuts water via non-ponded AWD + 75 mm *rauni*; `rice_short` expands Kharif→Rabi turnaround to 30d |
| **Pulses / Legumes (7)** | `chickpea`, `moong`, `urad`, `pigeon_pea`, `lentil`, `soybean`, `common_bean` | BNF fixation `45–80 kg N/ha`; Zaid `moong` / `urad` bridge Apr–Jun turnaround & earn N credits |
| **Oilseeds (3)** | `mustard`, `sunflower`, `groundnut` | High-value water-saving Kharif/Zaid/Rabi diversification (`groundnut` also fixes `65 kg N/ha`) |
| **Fibre / Tuber / Cover / Fodder (4)** | `cotton` (`malvaceae`), `potato` (`solanaceae`), `berseem` (`fabaceae`, `100 kg N/ha`), `dhaincha` (`fabaceae`, `80 kg N/ha`) | `dhaincha` green manure builds rapid summer SOM; `berseem` supports livestock constraints |

- **17 Indian Agro-Zones (`zones.yaml` + `default_zone`):** `punjab_central`, `punjab_southwest`, `haryana`, `bundelkhand`, `vidarbha`, `western_maharashtra`, `western_up`, `cauvery`, `rajasthan_arid`, `gujarat`, `eastern_gangetic`, `southern_hills`, `west_coast`, `himalayan`, `eastern_himalayan`, `central_malwa`, `islands`.
- **16 Gov Schemes (`schemes/*.yaml`):** `central` (4), `punjab` (3), `uttar_pradesh` (4), `maharashtra` (2), `tamil_nadu` (2), `haryana` (1).

### 7.2 FastAPI v0.2.0 Routes (`apps/api/terraloop_api/main.py`)
Dual-mounted at `/` and `/api/*` via `_PathPrefixMiddleware`; sliding-window rate limiter (`TERRALOOP_RATE_LIMIT_PER_MIN=60`) guards `/recommend`, `/profile`, `/tactical-advisory`, `/suitability`, and `/geocode`:
- `GET /health` · `GET /tactical-advisory` · `GET /crops` · `GET /golden` · `GET /golden/{field_id}/profile` · `GET /golden/{field_id}/recommendations` · `GET /geocode` (1s Nominatim throttle + offline coord/Google Maps regex parser)
- `POST /profile` · `POST /suitability` · `POST /recommend` · `POST /recommend/async` (executes inline synchronously when `VERCEL` env var is set; otherwise background thread up to 8 concurrent jobs persisted to `data/jobs/`) · `GET /recommend/jobs/{job_id}`

### 7.3 Environment Variables
| Variable | Purpose / Default |
|---|---|
| `GEE_PROJECT`, `GEE_SERVICE_ACCOUNT_KEY` / `GOOGLE_APPLICATION_CREDENTIALS` | Google Earth Engine auth (inline JSON, base64 JSON, or path for headless deploys) |
| `EARTHDATA_USERNAME`, `EARTHDATA_PASSWORD` | NASA Earthdata credentials (AppEEARS / Earthdata downloads if enabled) |
| `METEOMATICS_USERNAME`, `METEOMATICS_PASSWORD`, `METEOMATICS_BASE_URL` | Meteomatics 90m Sponsor API (`https://api.meteomatics.com` default) |
| `GEMINI_API_KEY` / `LLM_API_KEY`, `GEMINI_MODEL` / `LLM_MODEL`, `TERRALOOP_DISABLE_LLM` | Optional grounded narrative generation (runtime default `gemini-2.0-flash`; `.env.example` sets `gemini-3.8-flash`) |
| `TERRALOOP_CACHE_DIR`, `TERRALOOP_CROP_KB`, `TERRALOOP_AQUACROP_PARAMS`, `TERRALOOP_ECONOMICS` | Path overrides for disk cache and YAML knowledge bases |
| `PROFILE_LIVE_TIMEOUT_SEC`, `NASA_POWER_TIMEOUT`, `SOILGRIDS_TIMEOUT`, `TERRALOOP_RATE_LIMIT_PER_MIN` | Network/latency caps (`24.0s` / `12.0s` / `4.5s` / `60 req/min`) |
| `NEXT_PUBLIC_API_URL`, `API_URL`, `VERCEL` | Frontend/proxy API URL & Vercel serverless detection |

---

## 8. Commands, CI Verification & Known Gotchas

### Standard Developer Commands
```powershell
uv sync                                                    # Install workspace packages & dev tools
uv run uvicorn terraloop_api.main:app --app-dir apps/api --reload --port 8000
cd apps/web; npm run dev                                   # Next.js dev UI on :3000 (or `vercel dev` from repo root)

# Verification & CI Gates (exact match to .github/workflows/ci.yml)
uv run ruff check .
uv run pytest -q -m "not network"                          # 114 offline tests
uv run python scripts/run_validation_benchmarks.py --write-docs
git diff --exit-code docs/BENCHMARKS.md                    # Ensures benchmarks match engine code
cd apps/web; npm ci; npx tsc --noEmit; npm run lint        # Frontend TS & ESLint checks
cd apps/web; npm run build                                 # Local production webpack build verification

# Utility Scripts
uv run python scripts/precompute_golden.py                 # Rebuild data/golden/* + sync apps/web/public/golden/*
uv run python scripts/warm_cache.py --offline-check        # Verify 8-hub POWER grid snapping & cache keys
uv run python scripts/check_api_health.py                  # Audit external NASA / SoilGrids / endpoint reachability
```

### Known Gotchas
- **No `packages/engine[gee]` extra:** `earthengine-api` and `google-auth` are standard core dependencies in `packages/engine/pyproject.toml`. Use `uv sync` rather than `[gee]`.
- **Unwritable cache fallback:** `cache.py` writes to `<repo>/data/cache` unless read-only, falling back to `Path(tempfile.gettempdir()) / "terraloop-cache"` (hyphenated, not underscore).
- **Exact CI vs local web build:** `.github/workflows/ci.yml` runs `npx tsc --noEmit` and `npm run lint` (not `npm run build`), though running `cd apps/web && npm run build` (`next build --webpack`) locally is recommended before release.
- **Windows Console Encoding:** Long UTF-8 symbols (`₹`, Gurmukhi, Devanagari, `→`) in scripts call `sys.stdout.reconfigure(encoding="utf-8")`.
- **Serverless Async Endpoint:** On Vercel (`VERCEL` env set), `/recommend/async` runs synchronously and returns a completed job payload because background threads cannot outlive an HTTP invocation.
- **Polygon & Rate Caps:** `FieldGeometry` validates polygons strictly at `<= 500` vertices and `<= 10,000 ha`. Urban ISRIC pixels auto-search a `~3 km` rural offset grid.
