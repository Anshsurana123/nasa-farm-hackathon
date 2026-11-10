# AGENTS.md: Instructions for AI Coding Agents

> **Read this entire file before changing anything.** It is the source of truth for how to work in this repo.  
> - `docs/BUILD_PLAN.md` = what we are building  
> - `docs/METHODOLOGY.md` = the science & biophysical equations  
> - `docs/BENCHMARKS.md` = empirical calibration & sensitivity report (script-generated)  
> - `docs/DATASETS.md` = NASA & ancillary dataset registry (product IDs, DOIs)  
> - `docs/AUDIT.md` (if present) = open audit findings  
> - If this file and the code disagree, **trust the code**, then fix this file in the same change.  
> - **Code navigation:** use the Graphify graph (`graphify-out/`) first, grep for literals, read the source to confirm (Section 3).

---

## 1. What This Project Is

**TerraLoop** is an open-science, biophysically grounded crop-rotation decision-support system built for the **NASA Space Apps Challenge**.

### The Hackathon Challenge Statement
> *"Farmers around the world navigate shifting temperatures, changing rainfall patterns, water shortages, extreme weather, and declining soil health. These pressures make it difficult to choose crop rotations that protect fields, conserve water, and support long‑term resilience. Your challenge is to create a decision‑support tool that uses NASA Earth observations along with local soil information, crop characteristics, and farmer priorities to help farmers explore rotation strategies that could strengthen soil health and adapt their farms to changing conditions."*

Everything we build is judged against those core dimensions. Before starting work, confirm which challenge pillar your change serves:
1. **Shifting Temperatures:** March wheat terminal grain-filling heat stress (>32°C) and canopy cooling via Happy Seeder surface straw mulch (-1.0°C).
2. **Changing Rainfall Patterns:** Erratic monsoon distribution, mid-season dry spells, extreme rainfall days (>50 mm), and rainfall erosivity from NASA GPM IMERG V07.
3. **Water Shortages & Aquifer Depletion:** Regional groundwater collapse detected by NASA GRACE ($-3.85\text{ cm/year}$ in Punjab) and root-zone agricultural drought percentiles from NASA SMAP L4.
4. **Extreme Weather & Stubble Burning:** Narrow turnaround windows between rice harvest and wheat sowing forcing residue burning (detected by NASA FIRMS active fire hotspots).
5. **Declining Soil Health:** Long-term soil organic carbon (SOC) depletion modeled via RothC-lite 26.3, seasonal nitrogen mass balance with legume credits, and the USDA-NRCS 5-principle soil health index (0–100).
6. **Local Soil Information & Crop Characteristics:** Depth-weighted ISRIC SoilGrids 2.0 (250m) with Government of India Soil Health Card (SHC) laboratory test overrides, paired with a 23-crop agronomic knowledge base parameterized from Punjab Agricultural University (PAU) and ICAR field trials.
7. **Farmer Priorities & Downside Risk:** 6-objective Pareto optimization (Profit, Water Savings, Soil Health, Downside Risk $CVaR_{10}$, Low Labour, Food Security) evaluated across a 30-year historical weather ensemble or NEX-GDDP-CMIP6 climate projections.

### Operational Context & Scope Honesty
- **Lead Demo Story:** Trans-Gangetic Plains of Punjab, India (`sangrur` and `ludhiana`). Replaces conventional puddled rice (*Pusa-44*) with Short-Duration Rice (PR-126) or Direct-Seeded Rice (DSR) + Alternate Wetting & Drying (AWD) plus Happy Seeder zero-till wheat and summer moong—saving **14–59% irrigation water**, expanding turnaround to **26–34 days (eliminating stubble burning)**, sequestering **$+2.79\text{ t C/ha}$ of soil carbon over 10 years**, and saving **3.5 bags of Urea/ha**.
- **Six Golden Benchmark Fields:** Precomputed in `data/golden/<id>/` and `apps/web/public/golden/<id>/`:
  1. `sangrur` (Punjab): Trans-Gangetic alluvial plains (hero demo field).
  2. `ludhiana` (Punjab): PAU central alluvial plains (model calibration baseline).
  3. `bathinda` (Punjab): South-Western semi-arid cotton–wheat belt (saline water & whitefly risk).
  4. `bundelkhand` (Jhansi, UP): Central Plateau & Hills drought-prone red-black soils.
  5. `vidarbha` (Yavatmal, Maharashtra): Deccan Black Vertisol rainfed cotton–chickpea belt.
  6. `thanjavur` (Tamil Nadu): Cauvery Delta double-paddy and urad relay system.
- **Users:** Farmers and agricultural extension workers, not data scientists. They use mid-range Android smartphones on slow mobile connections, often reading Punjabi (Gurmukhi) or Hindi (Devanagari).
- **Scope Honesty:** The biophysical engine is calibrated and validated for **India only** (see `docs/BENCHMARKS.md`). Because the challenge mentions "farmers around the world", any location outside validated Indian agro-climatic zones must be handled explicitly and transparently (e.g. marked `data_mode="fallback_synthetic"` or `"regional_climatology"` with a visible disclaimer banner), never silently treated as Punjab (Section 4, Rule 8).

---

## 2. Current Phase: Hardening, Not Building

All 44 original backlog items and all 15 audit findings from `docs/AUDIT.md` are implemented, integrated, and verified with **61/61 passing offline tests**. There is no "next unchecked task".

Work comes from, in this strict order of priority:
1. **The user's explicit request.**
2. **Open audit findings in `docs/AUDIT.md`** (P0 first, then P1, then P2).
3. **New items added to `docs/TASKS.md` under `## Backlog` with clear acceptance criteria.**

> **Golden Rule of Execution:** Do one item at a time: **code + test + docs**, verify against linters, then move on.

---

## 3. Repository Map, Request Flow & Graphify Navigation

### 3.1 Repository Map
```
pyproject.toml                       uv workspace root (Python 3.11+); pytest + ruff config
packages/schemas/                    SHARED CONTRACTS (Pydantic v2). Frontend mirrors in apps/web/src/types/api.ts
  terraloop_schemas/models.py        FieldProfile, StrategyRecommendation, CropSpec, DataProvenance, etc.
packages/engine/terraloop_engine/    All biophysical science and logic. NO web code, NO HTTP in models/
  profiler.py                        build_profile(FieldGeometry) -> FieldProfile
  suitability.py                     Heuristic crop pre-filter (rank_crops)
  crop_kb.py                         Loads & validates packages/crop-kb/crops/*.yaml -> CropSpec
  cache.py                           @disk_cache(namespace=...) with serverless unwritable /tmp fallback
  data/                              nasa_power, soilgrids, gee (8 NASA collections: IMERG, SMAP, GRACE, etc.)
  eo/                                phenology (Savitzky-Golay 30m HLS NDVI), classifier (Gaussian ML crop classifier)
  climate/ensembles.py               Historical moving blocks + NEX-GDDP-CMIP6 with quantile mapping
  models/                            agroclimate (ET0, GDD), soil (texture, Saxton-Rawls),
                                     fao56_runner (FAO-56 dual Kc, rice hydrology, March heat),
                                     soil_health (RothC-lite 26.3, N balance, NRCS index),
                                     rusle (Universal Soil Loss Equation), economics (CACP MSP, CVaR-10),
                                     surrogate (polynomial ridge pre-screening),
                                     aquacrop_runner (backward-compatibility shim forwarding to fao56_runner)
  optimize/                          rotations (seasonal candidates + constraints),
                                     evaluate (multi-member simulation, practical metrics),
                                     selection (NSGA-II Pareto + priority-weighted top-3)
  explain/why_cards.py               Deterministic multilingual why-cards + grounded Gemini 3.8 Flash LLM summary
packages/crop-kb/                    crops/*.yaml (23 crops + _template.yaml), aquacrop_params/, economics/punjab.yaml
apps/api/terraloop_api/main.py       FastAPI backend: /health /crops /golden/* /geocode /profile /suitability /recommend
apps/web/                            Next.js 16 + React 19 + Tailwind CSS v4; i18n in src/i18n/{en,hi,pa}.json
data/golden/<id>/                    Precomputed profile, recommendations, weather. data/benchmarks/ = ground truth CSV
scripts/                             run_validation_benchmarks.py, precompute_golden.py, md_to_docx.py
tests/                               test_engine.py, test_models.py, test_deploy.py (100% offline passing)
docs/                                BUILD_PLAN, METHODOLOGY, BENCHMARKS, DATASETS, NOTES, SUBMISSION
```

### 3.2 End-to-End Request Flow (`POST /recommend`)
```
FieldGeometry (lat, lon, polygon)
  │
  ├─► [Match Golden Field? <0.15°] ──► Instant precomputed FieldProfile
  │   └─► Else profiler.build_profile(NASA POWER, GPM, SMAP, GRACE, NASADEM, FIRMS, HLS, SoilGrids)
  │       (On network failure: labelled regional Indian fallback profile with is_fallback=True)
  │
  ├─► Soil Health Card (SHC) Lab Override (optional: pH, SOC%, N, P, K)
  │
  ├─► Weather Scenario Set: 30-yr historical moving blocks OR NEX-GDDP-CMIP6 future projections
  │   └─► Apply stress shocks (drought shock %, mandi price shock %, fertilizer price shock %)
  │
  ├─► suitability.rank_crops ──► Pruned candidate crop set
  │
  ├─► rotations.generate_rotations ──► Multi-year seasonal candidate rotations (Kharif, Rabi, Zaid)
  │   └─► surrogate.py pre-screens candidates if candidate pool > 75
  │
  ├─► rotations.baseline_rotation ──► Derives current farmer baseline (Rank 0)
  │
  ├─► evaluate.evaluate_rotations_ensemble:
  │   ├─► fao56_runner.py : Daily soil-water balance, PTR vs DSR+AWD percolation, March terminal heat
  │   ├─► soil_health.py  : RothC-26.3 5-pool SOC turnover, N mass balance (25 kg N/ha legume credit)
  │   ├─► rusle.py        : Universal Soil Loss Equation (A = R·K·LS·C·P)
  │   └─► economics.py    : CACP 2024-25 MSP & A2+FL costs, P10/P50/P90 profits, CVaR-10 downside risk
  │
  ├─► selection.select_top ──► NSGA-II non-dominated Pareto sorting & priority-weighted ranking ──► Top 3
  │
  └─► explain.why_cards ──► Deterministic multilingual why-cards + practical farmer metrics (Urea bags,
                            pumping hours, turnaround days) + grounded Gemini 3.8 Flash agronomic summary
                            ──► list[StrategyRecommendation] (Index 0 = Baseline, Indices 1..3 = Top picks)
```

### 3.3 Navigating the Code with Graphify
A persistent Graphify knowledge graph of this repository is stored in `graphify-out/` (`GRAPH_REPORT.md`, `graph.json`, and `graph.html`). Use it to explore architectural relationships quickly, then verify in the source code.

1. **Query the graph before opening dozens of files:**
   - `graphify query "<question>"`: Query relationships across modules.
   - `graphify explain "<symbol>"`: Inspect callers, callees, community, and file location for a specific symbol.
   - `graphify path "<symbol_A>" "<symbol_B>"`: Find the shortest structural path between two components.
   - Use `graphify-out/GRAPH_REPORT.md` for high-level module communities and god nodes; never paste raw `graph.json` into context.
2. **Best applications in TerraLoop:**
   - Tracing the `/recommend` pipeline end to end (`main.py` $\rightarrow$ `evaluate.py` $\rightarrow$ `fao56_runner` / `soil_health` / `rusle` / `economics` $\rightarrow$ `selection.py` $\rightarrow$ `why_cards.py`).
   - Impact analysis before modifying schemas in `packages/schemas/terraloop_schemas/models.py` (check callers, then verify `apps/web/src/types/api.ts`).
   - Finding all callers of `select_top`, `load_crops`, or `build_profile` before editing signatures.
   - Auditing NASA dataset consumption: verifying whether a satellite product directly influences an optimization decision or is purely descriptive.
3. **Use `grep` / `rg` for literals:** The knowledge graph captures structural relationships, not literal constants. Magic numbers (e.g. `28.5`, `32.0`, `-4.5`), region identifiers (`"punjab"`, `"INR"`), model thresholds, i18n translation keys, and `TODO` comments must be located using `rg` or PowerShell `Select-String`.
4. **Verify before modifying:** Graph edges (especially inferred cross-language links between Python and TypeScript) are structural clues. Always open the destination file and verify the implementation before committing changes.
5. **Keep the graph clean:** Exclude `node_modules`, `.next`, lockfiles (`package-lock.json`, `uv.lock`), `public/maplibre/`, and large precomputed data (`data/golden/*/weather.json`, `data/cache/`). Re-run `graphify .` after structural reorganizations.
6. **Graph shows structure, not scientific validity:** The graph cannot determine whether an agronomic equation, Saxton-Rawls parameter, or CACP cost is correct. Correctness comes from `tests/`, `docs/BENCHMARKS.md`, and cited peer-reviewed literature.

---

## 4. The 15 Golden Engineering & Science Rules

Follow these non-negotiable rules at all times:

1. **NASA Data First, and It Must Matter:** Prioritize NASA Earth observations. Any NASA dataset that is merely displayed without influencing suitability, simulation, or ranking must be labeled `"context only"` in the UI. Register every new dataset in `docs/DATASETS.md` with product ID, GEE collection name, resolution, and DOI.
2. **Provenance on Every Number:** Every number displayed to a user must carry a `DataProvenance` model (source name, product ID, temporal range, DOI/URL, and observation mode). If a function outputs user-facing metrics without provenance, it is incomplete.
3. **Never Invent Numbers:** LLM-generated text (Gemini 3.8 Flash via `why_cards.py`) must strictly explain values computed by biophysical modules. Never fabricate yields, water savings, costs, or constants. If an agronomic parameter cannot be cited, record it in `docs/AUDIT.md` as `"needs domain expert"` and do not guess.
4. **The Demo Must Never Crash, and Must Never Mislead:** 
   - Live external failures must fall back gracefully to regional climatology or precomputed golden assets.
   - Fallback or synthetic data must always carry a visible label (`is_fallback=True`, `data_mode="regional_climatology"` or `"fallback_synthetic"`).
   - A failed `/recommend` call must show an explicit error or stale-data state—never display another field's numbers disguised as the current field's, and never show a success banner on failure.
5. **Farmer Priorities Must Steer the Result:** Altering `Priorities` weights must meaningfully shift rotation rankings. Hardcoded filters that bypass farmer priorities are bugs. Any change to `selection.py` or the objective builder in `main.py` requires running the priority-sensitivity verification suite (Section 8).
6. **Pure Functions for Science Models:** Biophysical modules (`models/fao56_runner.py`, `models/soil_health.py`, `models/rusle.py`, `models/soil.py`, `models/agroclimate.py`, `models/economics.py`) must be pure deterministic functions taking numbers, NumPy arrays, or DataFrames and returning numbers, dictionaries, or DataFrames. No HTTP calls, no file I/O, no unseeded randomness. Follow the reference style of `models/rusle.py` with cited equations and physical units in docstrings.
7. **Calibration Is Not Validation:** Parameters tuned against empirical targets (e.g. PAU DSR water savings or Sangrur district wheat yields) are calibration targets, not independent validation. Never edit physical constants just to make a benchmark test pass. If a scientific change moves headline yields or water savings, report before/after metrics in the commit note.
8. **No Region Hardcoding Outside Region Config:** Do not introduce arbitrary geographic hacks (e.g. `lat >= 28.5`) in engine models. Region-specific parameters (economics, seasonal windows, bias corrections, zones, currency) belong in `packages/crop-kb/economics/` or regional registries. When evaluated outside validated regions, explicitly inform the user instead of silently assuming Punjab conditions.
9. **Contracts First (Pydantic v2):** Shared contracts live in `packages/schemas/terraloop_schemas/models.py`. Any new field must provide a default value to maintain backward compatibility with existing golden JSON files. Frontend TypeScript interfaces in `apps/web/src/types/api.ts` must be updated in the same change.
10. **Cache Every External Call:** Wrap external API calls with `@disk_cache(namespace=...)`. Optional external sources must catch exceptions, log warnings, and leave fields as `None` rather than crashing the profile. Never replace missing satellite observations with fabricated data.
11. **Agronomic Data in YAML:** Crop parameters belong in `packages/crop-kb/crops/*.yaml`, economic parameters in `packages/crop-kb/economics/*.yaml`. Never hardcode agronomic limits, GDD, or prices in Python source code.
12. **Standard Units & Explicit Naming:**
    - Storage units: mm (water), °C (temperature), t/ha (yield and SOC stocks), kg N/ha (nitrogen), % (soil texture), g/kg (SOC concentration), days (durations), ₹/ha (economics).
    - Disambiguate variable names: `irrigation_mm`, `yield_t_ha`, `soc_delta_t_ha_10yr`.
13. **Smallest Correct Change:** Do not refactor or rewrite working modules to fix minor defects. If an audit uncovers a structural flaw, document the issue and proposal in `docs/AUDIT.md` before refactoring.
14. **Document Numbers Originate from Scripts:** All empirical figures in `docs/BENCHMARKS.md` must be generated by `uv run python scripts/run_validation_benchmarks.py --write-docs`. Hand-editing benchmark tables is prohibited; CI validates this with `git diff --exit-code docs/BENCHMARKS.md`.
15. **Secrets & Credentials Safety:** Never commit `.env` files, API keys, or personal GCP service account keys. Use `.env.example` placeholders.

---

## 5. Farmer-First Standards (UI & API Text)

- **Trilingual Accessibility:** Every user-visible string must be localized via `apps/web/src/i18n/{en,hi,pa}.json` (English, Hindi, Punjabi in Gurmukhi). Never hardcode English sentences in React TSX components or engine explanation templates.
- **Plain Language over Academic Jargon:** Never display raw technical terms like *CVaR-10*, *Pareto optimal*, *P10/P90*, or *RothC-26.3* on primary farmer cards. Translate into intuitive farming concepts:
  - $CVaR_{10} \rightarrow$ *"Income in a severe drought year"*
  - RothC SOC $\Delta \rightarrow$ *"Soil carbon built over 10 years"*
  - FAO-56 Net Irrigation $\Delta \rightarrow$ *"Borewell pumping hours saved"* and *"75 mm canal irrigations saved"*
  - Biological N balance $\rightarrow$ *"45-kg Urea bags saved per hectare"*
  - Technical parameters belong in an expandable "Scientific Details" drawer.
- **Actionable Agronomic Specifics:** Recommendations must state what to sow, when to sow, operational practices (e.g. *Happy Seeder direct-drilling into standing stubble*), expected income ranges, turnaround days before the next crop, and matching government support schemes (e.g. *Mera Pani Meri Virasat*, *CRM Subsidies*).
- **Visible Uncertainty:** Communicate climate ranges from ensemble simulations, display data modes transparently, and explicitly state unmodeled factors (e.g. insect pest outbreaks, hail, or localized market gluts).
- **Mobile & Low-Bandwidth Performance:** Designed for a 360×640 viewport over 3G cellular connections. Lazy-load heavy visualizers (MapLibre basemap, 3D Soil Column); ensure the core decision flow functions with minimal data transfer.
- **Visual Accessibility:** Maintain WCAG AA contrast, generous touch tap targets ($\ge 44\text{ px}$), clear form labels, and never rely exclusively on color to convey risk or performance.

---

## 6. Biophysical Process Models Reference

### 6.1 FAO-56 / FAO-33 Daily Soil-Water Balance (`models/fao56_runner.py`)
- **Daily Evapotranspiration:**
  $$\text{ET}_c = K_c(t) \times \text{ET}_0, \quad \text{ET}_a = K_s(t) \times K_c(t) \times \text{ET}_0$$
  $K_c(t)$ uses piecewise linear stages ($K_{c,\text{ini}}, K_{c,\text{mid}}, K_{c,\text{end}}$). Surface residue mulch (`happy_seeder` / `residue_retained`) reduces soil evaporation by **10%** ($K_c \times 0.90$).
- **Hydraulic Depletion Limits (Saxton-Rawls 2006):**
  $$\text{TAW} = 1000 \times (\theta_{\text{FC}} - \theta_{\text{WP}}) \times Z_r, \quad \text{RAW} = p \times \text{TAW}$$
  $$K_s(t) = \frac{\text{TAW} - D_{r,t}}{(1 - p)\cdot\text{TAW}} \quad \text{when } D_{r,t} > \text{RAW}$$
- **Yield Response to Water Deficit (FAO Paper No. 33):**
  $$\left(1 - \frac{Y}{Y_{\max}}\right) = K_y \left(1 - \frac{\sum \text{ET}_a}{\sum \text{ET}_c}\right)$$
- **Rice Establishment Hydrology:**
  - *Puddled Transplanted Rice (`rice_puddled`):* Requires $175\text{ mm}$ land-soaking puddling irrigation. Continuous ponded water ($5\text{--}10\text{ cm}$) drives steady downward percolation of **$3.5\text{ mm/day}$ on alluvial loam** until pre-harvest drainage.
  - *Direct-Seeded Rice with AWD (`rice_dsr`):* Replaces puddling with a non-ponded $75\text{ mm}$ pre-sowing *rauni* irrigation. Unsaturated soil matrix between wetting cycles drops percolation to **$2.55\text{ mm/day}$**, saving **24–28% water**.
- **March Wheat Reproductive Terminal Heat Stress:**
  During the final 35% of the Rabi wheat cycle (grain filling, March 1 to April 15):
  $$\Delta Y_{\text{heat}} = \sum_{t \in \text{grain-fill}} \max\left(0, T_{\max,t} - 32.0^\circ\text{C}\right) \times 0.018$$
  Surface residue mulch buffers canopy and topsoil temperature by **$-1.0^\circ\text{C}$**, dampening heatwave yield loss from **-19.7% to -12.6%**.

### 6.2 RothC-Lite 26.3 Decadal Soil Organic Carbon Model (`models/soil_health.py`)
- Monthly time step tracking 5 carbon pools over 10 years:
  1. Decomposable Plant Material (DPM, $k = 10.0\text{ yr}^{-1}$)
  2. Resistant Plant Material (RPM, $k = 0.30\text{ yr}^{-1}$)
  3. Microbial Biomass (BIO, $k = 0.66\text{ yr}^{-1}$)
  4. Humified Organic Matter (HUM, $k = 0.02\text{ yr}^{-1}$)
  5. Inert Organic Matter (IOM, computed via Falloon et al. 1998: $\text{IOM} = 0.049 \times C_{\text{tot}}^{1.139}$)
- Monthly abiotic rate modifier $\xi = a(T) \times b(M) \times c_{\text{cov}}$, where $c_{\text{cov}} = 0.6$ under canopy or mulch, $1.0$ under bare fallow.
- Clay-dependent partitioning: $x = 1.67 \times (1.85 + 1.60 \times \exp(-0.0786 \times \text{clay}))$. Fraction lost as $\text{CO}_2$ is $x / (x+1)$; remainder synthesized into BIO and HUM.
- Residue burning retains only ~10% ash carbon (driving $-1.86\text{ t C/ha/10yr}$ loss), whereas mulch retention sequesters $+2.79\text{ t C/ha/10yr}$.

### 6.3 Seasonal Nitrogen Mass Balance & Legume Credit (`models/soil_health.py`)
$$\text{Balance}_N = (N_{\text{fert}} + N_{\text{fix}} + N_{\text{dep}}) - N_{\text{removal}}$$
- Biological Fixation: Summer Moong (+50 kg N/ha), Chickpea (+60 kg N/ha), Urad (+45 kg N/ha), Dhaincha (+80 kg N/ha).
- **Legume Credit:** Succeeding cereal crops receive a **$25\text{ kg N/ha}$ synthetic nitrogen reduction**, saving **3.5 standard 45-kg bags of Urea per hectare (1.4 bags/acre)**.

### 6.4 USDA-NRCS 5 Principles Soil Health Index (0–100) (`models/soil_health.py`)
$$\text{Total Score} = \text{Clamp}_{0}^{100}\Big(\sum_{i=1}^5 \text{Principle}_i + \text{SOC Mod} + \text{Erosion Mod} + \text{Burn Penalty}\Big)$$
- Principle 1: Minimize Disturbance (15 pts max) — Happy Seeder No-Till: 15, DSR: 12, Conventional: 8, Puddling: 5.5, Residue Burning: 3.5.
- Principle 2: Maximize Soil Armor/Cover (15 pts max) — Annual canopy/mulch cover fraction $\times 15$.
- Principle 3: Continuous Living Roots (15 pts max) — Active growing days / 330 days $\times 15$.
- Principle 4: Maximize Biodiversity (15 pts max) — Shannon botanical family diversity index $\times 15$.
- Principle 5: Integrate Livestock/Legumes (15 pts max) — Fodder/livestock: 15, Legume/green manure: 12.5, Monoculture cereal: 4.5.
- Modifiers: 10-yr SOC accretion ($\pm 15$ pts), RUSLE erosion ($\pm 10$ pts), Residue burning penalty ($-5$ pts).

### 6.5 Agro-Economics & Downside Risk (`models/economics.py`)
$$\text{Net Profit} = \sum_{\text{season}} \left(\text{Yield} \times \text{MSP} - \text{Cost}_{A_2+FL}\right)$$
- **Downside Risk ($CVaR_{10}$):** Expected net profit in the worst 10% climate years across the weather ensemble.
- **Procurement Certainty Factor:** `msp_assured` (FCI wheat/paddy: 1.0), `nafed_pss` (pulses/oilseeds: 0.78), `mandi_linked` (volatile open market: 0.52).

---

## 7. The 23-Crop Agronomic Knowledge Base

Curated in `packages/crop-kb/crops/*.yaml`:

| Crop ID | Crop Name | Botanical Family | Group | Season | Duration | Water Need | Base / Opt / Max $T$ (°C) | Biological N Fixation |
|---|---|---|---|---|---|---|---|---|
| `wheat` | Wheat (Rabi) | Poaceae | Cereal | Cool | 135–155 d | 300–450 mm | 4.0 / (15, 22) / 32.0 | 0 kg N/ha |
| `rice_puddled` | Puddled Paddy Rice | Poaceae | Cereal | Warm | 120–155 d | 1200–1600 mm | 10.0 / (25, 33) / 40.0 | 0 kg N/ha |
| `rice_short` | Short Rice (PR-126) | Poaceae | Cereal | Warm | 100–110 d | 950–1250 mm | 10.0 / (25, 33) / 40.0 | 0 kg N/ha |
| `rice_dsr` | Direct-Seeded Rice | Poaceae | Cereal | Warm | 110–145 d | 900–1300 mm | 10.0 / (25, 32) / 40.0 | 0 kg N/ha |
| `basmati` | Basmati Rice | Poaceae | Cereal | Warm | 130–155 d | 1100–1450 mm | 10.0 / (24, 32) / 38.0 | 0 kg N/ha |
| `maize` | Maize / Corn | Poaceae | Cereal | Warm | 90–120 d | 450–650 mm | 8.0 / (20, 30) / 38.0 | 0 kg N/ha |
| `pearl_millet` | Bajra (Pearl Millet) | Poaceae | Cereal | Warm | 75–90 d | 300–450 mm | 12.0 / (28, 35) / 45.0 | 0 kg N/ha |
| `sorghum` | Jowar (Sorghum) | Poaceae | Cereal | Warm | 95–115 d | 350–500 mm | 10.0 / (26, 34) / 42.0 | 0 kg N/ha |
| `barley` | Barley (Jau) | Poaceae | Cereal | Cool | 110–130 d | 250–380 mm | 4.0 / (15, 22) / 30.0 | 0 kg N/ha |
| `moong` | Summer Moong | Fabaceae | Legume | Warm | 60–75 d | 250–350 mm | 12.0 / (25, 35) / 42.0 | **+50 kg N/ha** |
| `urad` | Blackgram (Urad) | Fabaceae | Legume | Warm | 70–85 d | 300–400 mm | 12.0 / (25, 35) / 42.0 | **+45 kg N/ha** |
| `chickpea` | Gram / Chickpea | Fabaceae | Legume | Cool | 105–130 d | 250–350 mm | 5.0 / (18, 26) / 35.0 | **+60 kg N/ha** |
| `pigeon_pea` | Arhar / Tur | Fabaceae | Legume | Warm | 140–180 d | 500–700 mm | 10.0 / (22, 32) / 38.0 | **+70 kg N/ha** |
| `lentil` | Masoor (Lentil) | Fabaceae | Legume | Cool | 110–130 d | 200–300 mm | 4.0 / (15, 24) / 30.0 | **+40 kg N/ha** |
| `soybean` | Soybean | Fabaceae | Legume | Warm | 95–115 d | 450–650 mm | 10.0 / (22, 30) / 38.0 | **+80 kg N/ha** |
| `common_bean` | Rajma (Kidney Bean) | Fabaceae | Legume | Cool | 90–115 d | 300–450 mm | 8.0 / (16, 24) / 32.0 | **+30 kg N/ha** |
| `mustard` | Sarson / Mustard | Brassicaceae | Oilseed | Cool | 110–135 d | 250–380 mm | 5.0 / (15, 25) / 32.0 | 0 kg N/ha |
| `groundnut` | Peanut / Groundnut | Fabaceae | Oilseed | Warm | 105–125 d | 450–600 mm | 10.0 / (24, 30) / 38.0 | **+60 kg N/ha** |
| `sunflower` | Sunflower | Asteraceae | Oilseed | Warm | 85–100 d | 400–550 mm | 8.0 / (20, 28) / 36.0 | 0 kg N/ha |
| `cotton` | Cotton (Kapas) | Malvaceae | Fibre | Warm | 150–180 d | 700–1000 mm | 14.0 / (25, 35) / 42.0 | 0 kg N/ha |
| `potato` | Potato (Aloo) | Solanaceae | Tuber | Cool | 85–110 d | 400–550 mm | 7.0 / (16, 22) / 30.0 | 0 kg N/ha |
| `berseem` | Berseem Clover | Fabaceae | Fodder | Cool | 140–180 d | 600–800 mm | 5.0 / (15, 24) / 32.0 | **+90 kg N/ha** |
| `dhaincha` | Sesbania Green Manure | Fabaceae | Cover | Warm | 45–60 d | 200–300 mm | 12.0 / (25, 35) / 42.0 | **+80 kg N/ha** |

---

## 8. Developer & Agent Command Center

Execute commands from the repository root:

```powershell
# 1. Environment Synchronization
uv sync                                               # Install all workspace packages in editable mode

# 2. Testing (Must stay 100% green)
uv run pytest -q -m "not network"                     # 56 offline tests
uv run pytest -q                                      # Full suite (including live GEE/POWER if authenticated)
uv run pytest tests/test_models.py -q                 # Biophysical unit tests only
uv run pytest tests/test_engine.py -q                 # Engine integration tests only

# 3. Linting & Formatting
uv run ruff check . --fix                             # Ruff linter (120 char line limit)
uv run ruff format --check .                          # Code formatting verification

# 4. Scientific Benchmarks & Reproducibility Check
# Regenerates docs/BENCHMARKS.md from live engine simulations
uv run python scripts/run_validation_benchmarks.py --write-docs

# 5. Golden Dataset Precomputation
# Recomputes 6 Indian benchmark fields (requires internet + GEE_PROJECT)
uv run python scripts/precompute_golden.py

# 6. Running Local Backend & Frontend
# Terminal A (FastAPI):
uv run uvicorn terraloop_api.main:app --reload --port 8000 --app-dir apps/api
# Terminal B (Next.js 16 Web App):
cd apps/web; npm ci; npm run dev

# 7. Frontend Verification Suite
cd apps/web; npx tsc --noEmit; npm run lint; npm run build

# 8. Codebase Navigation with Graphify (Run without leading slash)
graphify query "how does /recommend pick the top 3?"
graphify explain "select_top"
graphify path "recommend" "soil_health_score"
```

### Continuous Integration (CI) Contract
GitHub Actions (`.github/workflows/ci.yml`) enforces:
1. `uv run ruff check .`
2. `uv run pytest -q -m "not network"` (56 tests)
3. `uv run python scripts/run_validation_benchmarks.py --write-docs` followed by `git diff --exit-code docs/BENCHMARKS.md`
4. `cd apps/web && npx tsc --noEmit && npm run lint`

### Priority-Sensitivity Verification Protocol
Required whenever modifying `optimize/selection.py`, the objective builder in `main.py`, or frontend priority sliders:
- Execute `/recommend` across at least `sangrur`, `bathinda`, `vidarbha`, and `thanjavur` using 6 priority vectors:
  1. Profit-only (`profit=1.0`, others `0.0`)
  2. Water-only (`water_savings=1.0`, others `0.0`)
  3. Soil-only (`soil_health=1.0`, others `0.0`)
  4. Risk-only (`low_risk=1.0`, others `0.0`)
  5. Balanced (`all=1.0`)
  6. Zero-profit (`profit=0.0`, others `1.0`)
- **Assertion:** The top-3 strategies must shift in the expected direction (e.g. water-only must yield mean irrigation $\le$ balanced; soil-only must yield soil score $\ge$ balanced). Identical top-3 rankings across distinct vectors indicates a broken objective builder or inactive weights.

---

## 9. Scientific Model Modification Protocol

When modifying or adding a biophysical process model:
1. **Equations & Citations First:** State the exact equation, physical units, and peer-reviewed literature source in the module and function docstrings.
2. **Property Tests:** Add tests for mathematical bounds, monotonicity, mass balance, and edge cases (e.g. leap year, missing rainfall, $T_{\max} < T_{\min}$).
3. **Execute Benchmark Verification:** Run `uv run python scripts/run_validation_benchmarks.py --write-docs` and `scripts/precompute_golden.py`. Note every headline number that moved and provide scientific rationale in the commit message.
4. **Agronomic Sensitivity Verification:** Verify that outputs respond to soil texture, rainfall gradients, and temperature extremes as agronomy dictates. A model whose output remains flat across varied soils or weather extremes indicates an unintended clamp or calculation bug.
5. **Documentation Synchronization:** Update `docs/METHODOLOGY.md` for scientific equations and `docs/DATASETS.md` for new satellite products.

---

## 10. Agent Boundaries: Always, Ask First, Never

### ALWAYS
- Query the Graphify knowledge graph to locate components, then read the source before writing code.
- Reproduce any bug with an offline test before attempting a fix.
- Synchronize Pydantic schemas in `packages/schemas/` with TypeScript interfaces in `apps/web/src/types/api.ts`.
- Attach `DataProvenance` to all user-facing numbers.
- Add user-visible strings to all three i18n files (`en.json`, `hi.json`, `pa.json`).
- Verify `ruff`, `pytest`, `npx tsc --noEmit`, and `npm run lint` before completing work.

### ASK FIRST (Document in `docs/AUDIT.md` before proceeding)
- Modifying calibrated biophysical constants or crop parameters without a verified scientific source.
- Introducing a new external dependency into `pyproject.toml` or `package.json`.
- Modifying the semantic meaning of an existing schema field.
- Deleting an established feature, endpoint, or golden benchmark field.
- Introducing agronomic parameter data for a new country outside India.

### NEVER
- Treat the Graphify graph as absolute truth or paste entire `graph.json` files into context.
- Fabricate satellite detections, fire dates, NDVI curves, crop coefficients, or citations.
- Hide a pipeline failure behind a fake success message or present uncalibrated regional data as validated local data.
- Hand-edit generated documentation (`docs/BENCHMARKS.md`) or golden JSON files.
- Bypass access controls or commit secrets, credentials, or GCP service account keys.
- Mark a task complete without offline tests proving its correctness.

---

## 11. Definition of Done (Checklist for AI Agents)

Before marking any task complete, verify each item:

- [ ] **Behavior Verified:** Code meets acceptance criteria, reproduced before the change and verified after.
- [ ] **Offline Tests Pass:** `uv run pytest -q -m "not network"` passes (56/56 tests passing).
- [ ] **Linters & Typings Clean:** `uv run ruff check .`, `cd apps/web && npx tsc --noEmit`, and `npm run lint` pass with zero warnings.
- [ ] **Data Provenance Attached:** Every user-facing number carries verifiable `DataProvenance` metadata; fallbacks are labeled.
- [ ] **Trilingual Synchronization:** All three translation files (`en.json`, `hi.json`, `pa.json`) are updated; no hardcoded English strings in TSX or Python templates.
- [ ] **Contracts Synchronized:** Changes to Pydantic models in `packages/schemas/` include default values and match `apps/web/src/types/api.ts`.
- [ ] **Benchmarks Maintained:** If biophysical models or crop YAMLs changed, `uv run python scripts/run_validation_benchmarks.py --write-docs` was run and moved numbers are documented.
- [ ] **Graph Integrity Maintained:** If modules or functions were renamed or restructured, `graphify .` was re-run (or documented if unavailable).
- [ ] **Documentation Aligned:** `docs/METHODOLOGY.md` / `docs/DATASETS.md` updated if models or datasets changed; this guide updated if any section became inaccurate.

---

## 12. Known Sharp Edges & Codebase Gotchas

Keep these known issues in mind when working in the repository:

1. **`selection.select_top` Sorting Hierarchy:** The weighted priority score currently operates as the third sort key behind hardcoded agronomic viability and Pareto dominance filters. Keep this in mind when debugging priority sensitivity.
2. **`/recommend` Objective Builder:** Procurement assurance factors currently feed into `profit`, `low_risk`, and `food_security` objectives simultaneously. Furthermore, `food_security` uses a crop group lookup rather than direct caloric density calculations.
3. **Region Hardcoding in `/recommend`:** The API contains legacy fallback checks (e.g. `lat >= 28.5` for the Punjab belt and `load_economics("punjab")`). These should be transitioned to dynamic zone detection via `economics.detect_agro_zone()`.
4. **Frontend Fallback Presentation in `RotationExplorer.tsx`:** When the live `/recommend` API fails, the frontend falls back to static golden data. Ensure the UI displays an informative fallback badge rather than an unqualified success state.
5. **Golden-Field Coordinate Tolerance ($\pm 0.15^\circ$):** The API golden-match threshold ($\sim 16\text{ km}$) means nearby fields can snap to precomputed golden benchmarks. Maintain transparency by exposing `data_mode` in the UI.
6. **Web Priority Sliders vs. API Constraints:** The web UI currently exposes 5 priority sliders (omitting `food_security`) and limits rotation horizons to 3 years, whereas the backend API supports 6 objectives and up to 6-year rotation horizons.
7. **NASA POWER Hot-Season Warm Bias in Northwest India:** MERRA-2 reanalysis lacks the localized cooling effect of extensive flood irrigation in Punjab and Haryana (+3°C to +4.5°C warm bias in March/June). Always route POWER data through `apply_igp_irrigation_bias_correction` (`packages/engine/terraloop_engine/data/nasa_power.py`).
8. **Rainfall Inhomogeneity Across Satellite Epochs:** Do not mix pre-2001 reanalysis precipitation with post-2001 GPM observations when computing multi-decadal trends. Use GPM IMERG V07 (2001–2024) for rainfall statistics, extremes, and RUSLE $R$-factor calculations.
9. **SoilGrids Urban & Water Pixel Masking:** SoilGrids 2.0 returns `null` for urban clusters. `soilgrids.fetch_topsoil()` uses a 3 km spiral search to find adjacent agricultural soils.
10. **Vercel Serverless Read-Only Filesystem:** Serverless functions cannot write to `data/cache`. `cache.py` detects unwritable environments and falls back to `/tmp/terraloop_cache`.
