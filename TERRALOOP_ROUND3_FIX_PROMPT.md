# TerraLoop — Round 3 Final Closure Prompt (Iterative Fix & Verification Loop)

You are a Staff Agronomic Software Engineer and Technical Auditor. A previous pass created `docs/AUDIT_V3.md` and marked all workstreams "RESOLVED", but an independent line-by-line code audit proved that **20 specific items across the backend, frontend, golden data files, and test suite were either skipped, left half-finished in the UI, or backed by superficial/missing tests.**

Your mission is to **fix every single one of the 20 remaining issues below** by working in strict, self-verifying loops until 0 issues remain.

---

## 0. Mandatory Execution Protocol: The Iterative Verification Loop

You MUST NOT batch-edit files and claim success at the end. You must work through the groups below using this strict **4-Step Loop** for every item:

1. **INSPECT & REPRODUCE:** Read the exact file and line numbers cited below. Confirm the defect exists.
2. **IMPLEMENT THE FIX:** Write the minimal, clean, production-grade code change across Python (`packages/schemas`, `packages/engine`, `apps/api`) and TypeScript/React (`apps/web/src`) plus i18n (`en.json`, `hi.json`, `pa.json`).
3. **WRITE / UPGRADE THE TEST:** Write a real, falsifiable test in `tests/test_engine.py` that would **fail** on the old code and **passes** on your new code. Never write placeholder tests that only check a hardcoded list of strings.
4. **AUDIT & RE-CHECK (THE LOOP):**
   - Run `uv run pytest -q -m "not network"`
   - Run `uv run ruff check .`
   - In `apps/web`, run `npx tsc --noEmit` and `npm run lint`
   - Run a targeted `rg` / `python -c` audit command to verify the requirement is truly met in both data and UI.
   - **If ANY check fails or a gap remains, loop back to Step 2 immediately. Do NOT move to the next item until the current item is 100% verified.**

### Non-Negotiable Rules
- Read and obey all 15 rules in `AGENTS.md`.
- **Never invent citations, subsidy amounts, or satellite observations.**
- **Never claim a test exists unless you just ran it by name with `uv run pytest -k <test_name>` and saw it pass.**
- Every new schema field in `packages/schemas/terraloop_schemas/models.py` MUST have a sensible default value and be mirrored in `apps/web/src/types/api.ts` in the same step.

---

## 1. The 20 Remaining Issues to Fix (Complete All)

### GROUP 1: Data Honesty, Golden Snapshots & Provenance (WS-A & WS-B)

#### Issue 1 — `scripts/precompute_golden.py` and Golden Files Falsely Claim `"observed"` When GEE Is Offline (WS-A1)
* **Current Defect:**
  - `data/golden/gee_audit_log.json` shows `"gee_live": false` for all 6 golden fields, yet every `data/golden/<id>/profile.json` and `apps/web/public/golden/<id>/profile.json` has `"data_mode": "observed"`, `"is_fallback": false`, `"state": null`, `"served_from": "live_computation"`, `"snapshot_date": null`, and tags FIRMS/HLS as `"mode": "observed"`.
  - `scripts/precompute_golden.py` (lines 67–75) explicitly bypassed regeneration by copying over the old `existing_prof` whenever `existing_prof.data_mode == "observed"` and `not gee.is_live()`.
  - `docs/AUDIT_V3.md` cited `test_golden_provenance_consistency`, which **does not exist** in `tests/test_engine.py`. Meanwhile, `test_soil_health_breakdown_and_observed_golden_provenance` (line 814) asserts that Sangrur has `data_mode == "observed"`.
* **Required Fix:**
  1. In `scripts/precompute_golden.py`, remove the `if existing_prof.data_mode == "observed":` preservation bypass when `not gee.is_live()`. If GEE is not live during precomputation, `precompute_golden.py` must refuse to label GEE products (GRACE, SMAP, NASADEM, FIRMS, HLS) as `"observed"`; it must record their honest modes (`"regional_climatology"` for static lookups, `"unknown"` for FIRMS/HLS with `residue_burning_detected = None`), set `data_mode` honestly (`"hybrid_regional"` if NASA POWER/SoilGrids succeeded, or `"regional_climatology"`), and record per-product provenance in `gee_audit_log.json`.
  2. Ensure `precompute_golden.py` stamps every golden `profile.json` and `recommendations.json` with `served_from="demo_snapshot"`, `snapshot_date` (ISO date string, e.g. `"2026-11-10"`), and populates `state` via `region_registry.detect_state(lat, lon)` (never `null` for the 6 Indian benchmark fields).
  3. Write the actual `test_golden_provenance_consistency` in `tests/test_engine.py`: load `data/golden/gee_audit_log.json` and every golden `profile.json` and `recommendations.json`. Assert that if `gee_live` is `false` for a field in the audit log, no GEE-only product (FIRMS, HLS, GRACE, SMAP, NASADEM) in that field's `profile.json` has `mode == "observed"`, and `profile.state` is not `None`, and `profile.served_from == "demo_snapshot"`, and `profile.snapshot_date` is not `None`. Update `test_soil_health_breakdown_and_observed_golden_provenance` so it checks honest provenance consistency rather than hardcoded `"observed"` when `gee_live` is `false`.

#### Issue 2 — Missing Visible MERRA-2 Bias-Correction Provenance Note (WS-A3)
* **Current Defect:** `packages/engine/terraloop_engine/data/nasa_power.py` applies `apply_igp_irrigation_bias_correction` (up to `-4.5°C` in March) when `reg_cfg.igp_merra2_bias_correction` is True, and `docs/AUDIT_V3.md` claims *"Provenance notes disclose -4.5°C pre-monsoon correction"*, but `nasa_power.provenance()` (lines 44–52) returns a static `product` string with zero mention of the temperature bias correction.
* **Required Fix:**
  1. Update `nasa_power.provenance(start, end, mode="observed", bias_corrected: bool = False)` (and its call site in `profiler.py`) so that when `reg_cfg.igp_merra2_bias_correction` is True, the `DataProvenance.product` (or note) explicitly includes `"IGP irrigation warm-bias corrected (-4.5°C Mar Tmax; Ambika & Mishra 2019 / IMD 1981-2010)"` and `doi="10.1029/2019GL084367"`.
  2. Add a unit test `test_merra2_bias_correction_provenance_and_toggle` in `tests/test_engine.py` verifying the temperature delta AND the provenance string on an IGP point (Sangrur) vs a non-IGP point (Thanjavur/Yavatmal).

#### Issue 3 — Frontend API Client Still Silently Serves Closest Golden Field on Failure (WS-B2 & WS-J2)
* **Current Defect:** In `apps/web/src/lib/api.ts`, lines 63–93 (for `/recommend`) and lines 95–130 (for `/profile`), when the backend API is unreachable, the frontend loops over `fields.json` with `Math.hypot(f.lat - reqBody.field.lat, f.lon - reqBody.field.lon)`, finds the **closest golden field anywhere in India**, fetches `/golden/${closest.id}/...`, overwrites the coordinates with the user's coordinates, and returns it as if it were the user's field! This directly violates Rule 4 and WS-B.
* **Required Fix:**
  1. In `apps/web/src/lib/api.ts`, completely remove the `Math.hypot` closest-field loop for both `/recommend` and `/profile`.
  2. Only if the requested `field.id` is an **exact match** to a known demo field ID in `fields.json` may `api.ts` fall back to `/golden/${field.id}/profile.json` or `/golden/${field.id}/recommendations.json` (stamping `served_from: "demo_snapshot"`).
  3. For any custom coordinate without an exact golden `id`, if the backend request fails, `api.ts` MUST throw the error so `RotationExplorer.tsx` displays the localized error banner (`error.recommendFailedCustom`) and never displays another farm's data.

#### Issue 4 — Missing UI Badge for Demo Snapshot & Snapshot Date (WS-B3 & WS-J4)
* **Current Defect:** `served_from` and `snapshot_date` exist in `apps/web/src/types/api.ts`, but zero `.tsx` files in `apps/web/src/` reference or render them.
* **Required Fix:**
  1. Add localization keys in `apps/web/src/i18n/{en,hi,pa}.json` for the demo snapshot badge (e.g., `badge.demoSnapshot`: `"Demo field — saved snapshot from {date}"`, plus accurate Hindi and Punjabi translations) and for `data_mode` (`observed`, `hybrid_regional`, `regional_climatology`, `fallback_synthetic`).
  2. Render this badge prominently in `apps/web/src/components/RotationExplorer.tsx` and `apps/web/src/components/AgronomicBrief.tsx` whenever `profile.served_from === "demo_snapshot"` or `strategy.served_from === "demo_snapshot"`.

#### Issue 5 — Missing UI Badge for Proxy Economics (WS-D2 & WS-J4)
* **Current Defect:** `economics_basis` (`"local_verified"` | `"punjab_proxy"`) is returned by the API and defined in `apps/web/src/types/api.ts`, but never rendered anywhere in `apps/web/src/**/*.tsx`.
* **Required Fix:**
  1. Add localization keys in `en.json`, `hi.json`, `pa.json` for `badge.punjabProxyEconomics` (*"Cost estimate based on Punjab proxy data — treat as indicative"*) and `label.netOperatingIncomeNote` (*"Net operating income (Revenue minus CACP A2+FL paid-out & family labour costs; excludes land rent & fixed capital interest)"*).
  2. Render the proxy economics badge on recommendation cards in `RotationExplorer.tsx` and `AgronomicBrief.tsx` whenever `strategy.economics_basis === "punjab_proxy"`, and display the A2+FL clarification tooltip/sublabel next to profit figures.

---

### GROUP 2: Biophysical Engine, Soil Sensitivity & Decadal Carbon (WS-F & WS-G)

#### Issue 6 — Missing FAO-56 Annex Worked Examples Unit Tests (WS-F4)
* **Current Defect:** No test in `tests/` verifies the FAO-56 equations against published FAO Irrigation and Drainage Paper No. 56 worked examples.
* **Required Fix:**
  1. Audit `packages/engine/terraloop_engine/models/agroclimate.py` and `fao56_runner.py` (10 m → 2 m wind speed conversion $u_2 = u_z \frac{4.87}{\ln(67.8 z - 5.42)}$, psychrometric constant, saturation vapour pressure, Penman-Monteith $\text{ET}_0$, Saxton-Rawls TAW/RAW, and linear $K_s$ reduction under root-zone depletion).
  2. Add `test_fao56_annex_worked_examples` in `tests/test_engine.py` testing:
     - FAO-56 Example 18 (or standard reference conditions) daily Penman-Monteith $\text{ET}_0$ within $\pm 0.25\text{ mm/day}$ tolerance.
     - Wind profile conversion from 10 m to 2 m (`4.87 / ln(67.8*10 - 5.42) = 0.748`).
     - FAO-56 Box 11 / Example 35 root-zone depletion: $K_s = 1.0$ when $D_r \le \text{RAW}$, linear decline $K_s = \frac{\text{TAW} - D_r}{(1 - p)\text{TAW}}$ when $\text{RAW} < D_r < \text{TAW}$, and $K_s = 0.0$ when $D_r \ge \text{TAW}$.

#### Issue 7 — Peninsular Rainfed Yield-Gap Warning & Range Display Missing in UI (WS-F5)
* **Current Defect:** In `BENCHMARKS.md`, rainfed peninsular crops show +25% to +43% optimism (Yavatmal cotton +43.3%, Jhansi sorghum +29.9%) because the engine simulates water-and-radiation-limited potential yield ($Y_w$) without chronic biotic stresses (pink bollworm, pod borer). This is documented in `JUDGE_QA.md`, but the UI does not show the required yield-gap warning banner or range disclaimer.
* **Required Fix:**
  1. Add localization keys in `en.json`, `hi.json`, `pa.json` for `warning.yieldGapDisclaimer` explaining that simulated yields and profits represent water-limited agroclimatic potential ($Y_w$) and that real farm yields in rainfed/peninsular belts are typically 20–40% lower due to unmodeled pests, bollworm, and foliar diseases; always consult the P10–P90 income range.
  2. Render this banner in `RotationExplorer.tsx` and `AgronomicBrief.tsx` (especially highlighted when irrigation is `"none"` / rainfed or when viewing yield/profit projections), and ensure cards prominently show the `profit_p10`–`profit_p90` range alongside `profit_p50`.

#### Issue 8 — Missing Measured Soil Sensitivity Tests & Score Coupling (WS-G2)
* **Current Defect:** There is no test verifying that varying measured soil properties (SOC, clay, pH, available N via Soil Health Card or SoilGrids) meaningfully alters the 0–100 Soil Health Score, water balance, and candidate rankings.
* **Required Fix:**
  1. Inspect `packages/engine/terraloop_engine/models/soil_health.py` and `optimize/evaluate.py`. Ensure that extreme pH stress (e.g. acidic $\text{pH} < 5.5$ or sodic $\text{pH} > 8.5$), initial SOC stock depletion vs sufficiency, clay water-holding/carbon stabilization, and SHC available N directly and monotonically influence the simulated yields, N fertilizer requirement, decadal SOC change, and the 0–100 Soil Health Index.
  2. Add `test_soil_score_and_ranking_sensitivity_to_shc_and_soilgrids` in `tests/test_engine.py` that systematically varies SOC (2.0 vs 9.0 g/kg), clay (10% vs 48%), pH (5.1 vs 7.2 vs 8.9), and available N (110 vs 380 kg/ha) and asserts strict, physically sensible responses in water balance, Urea requirement, SOC delta, and Soil Health Score.

#### Issue 9 — `rothc_lite` Still Repeats a Single 12-Month Climate Array 10 Times (WS-G3)
* **Current Defect:** In `packages/engine/terraloop_engine/models/soil_health.py` (lines 128–160), `rothc_lite` only accepts 12 monthly values (`len(monthly_temp_c) == 12`) and repeats the exact same year 10 times, ignoring multi-year climate variability in the weather series.
* **Required Fix:**
  1. Update `rothc_lite` in `models/soil_health.py` so `monthly_temp_c`, `monthly_precip_mm`, and `monthly_et0_mm` can be either a 12-element climatology (repeated per year for backward compatibility) OR a multi-year monthly sequence of length $12 \times \text{years}$ (e.g. 120 months for 10 years, or arbitrary multi-year sequence indexed by `(yr * 12 + m) % len(seq)`).
  2. In `evaluate.py`, pass the actual multi-year monthly temperature and precipitation sequence extracted from the historical/CMIP6 weather DataFrame into `rothc_lite`.
  3. Add `test_rothc_mass_balance_and_multiyear_climate` in `tests/test_engine.py` verifying conservation of mass across DPM/RPM/BIO/HUM/IOM/CO2 pools and proving that a 120-month warming/drying trajectory produces a different 10-year SOC stock than a static 12-month average.

---

### GROUP 3: Performance, Caching & Async UI Wiring (WS-H)

#### Issue 10 — Web UI Ignores the Async Job API (`POST /recommend/async`) (WS-H3)
* **Current Defect:** `apps/api/terraloop_api/main.py` implements `POST /recommend/async` and `GET /recommend/jobs/{job_id}`, but `apps/web/src/lib/api.ts` and `apps/web/src/components/RotationExplorer.tsx` never call them — the frontend only calls synchronous `POST /recommend`.
* **Required Fix:**
  1. In `apps/web/src/types/api.ts`, add `RecommendJobStatus` interface (`job_id`, `status`, `stage`, `progress_pct`, `message`, `result`, `error`).
  2. In `apps/web/src/lib/api.ts`, add `recommendAsync(req: RecommendRequest)` (`POST /recommend/async`), `getRecommendJob(jobId: string)` (`GET /recommend/jobs/${jobId}`), and a helper `recommendWithProgress(req, onProgress)` that starts an async job, stores `terraloop_active_job_id` in `sessionStorage` (wrapped in `try/catch`), polls `/recommend/jobs/{job_id}` every 400 ms, updates progress (`profile` → `weather` → `simulating` → `ranking`), and falls back cleanly to synchronous `/recommend` if the async endpoint is unavailable (e.g. static offline mode for exact demo IDs).
  3. Wire `recommendWithProgress` into `RotationExplorer.tsx` so the user sees live simulation stage & percentage progress while computing, and if a mounted tab has an in-flight `terraloop_active_job_id` in `sessionStorage`, it can resume polling.

#### Issue 11 — Missing `scripts/warm_cache.py` & Grid-Cell Cache Equivalence Test (WS-H1 & WS-H4)
* **Current Defect:** `scripts/warm_cache.py` was required by WS-H1 but does not exist in `scripts/`. And there is no test proving grid-cell cache equivalence.
* **Required Fix:**
  1. Create `scripts/warm_cache.py` that iterates over major Indian agricultural regions (including all 6 golden districts and major state agricultural hubs) and pre-warms the `@disk_cache` for NASA POWER (`0.5° × 0.625°` native grid cells) and SoilGrids, with an `--offline-check` flag for CI that verifies cache key generation without network calls.
  2. Ensure cached NASA POWER provenance records when it was fetched/cached.
  3. Add `test_cache_key_grid_equivalence` in `tests/test_engine.py` proving that two distinct farm coordinates inside the same `0.5° × 0.625°` NASA POWER cell snap to the exact same grid center via `snap_to_power_grid` and return identical weather DataFrames with only 1 upstream call.

---

### GROUP 4: Optimization Rigor, Priority Sweep, Surrogate Recall & Baseline UI (WS-I)

#### Issue 12 — Missing ≥200-Vector Priority Monotonicity Sweep Across ≥4 Fields (WS-I3)
* **Current Defect:** `test_selection_priority_directional_monotonicity` in `tests/test_engine.py` only tests 7 hardcoded synthetic dictionaries. It does NOT run the required ≥200 random priority vectors across ≥4 fields.
* **Required Fix:**
  1. Add `test_priority_monotonicity_sweep_200_vectors_four_fields` in `tests/test_engine.py`.
  2. Load or evaluate the real candidate objective pools for at least 4 distinct benchmark fields (`sangrur`, `bathinda`, `vidarbha`, `thanjavur`).
  3. Using a seeded RNG (`np.random.default_rng(2026)`), generate ≥200 random `Priorities` vectors (50+ per field). For each vector and each objective $k \in \{\text{profit}, \text{water\_savings}, \text{soil\_health}, \text{low\_risk}, \text{low\_labour}, \text{food\_security}\}$, boost weight $w_k \leftarrow w_k + 2.5$ while holding other weights fixed, run `selection.select_top`, and assert that the mean of objective $k$ across the top-3 (and top-1) does not worsen beyond a small documented diversity tie-break tolerance.
  4. If `selection.select_top`'s structural diversity filter overrides strong priority weights and causes violations, adjust `selection.py` so priority weighting is respected.

#### Issue 13 — Missing Surrogate Pre-Screen Recall Test (WS-I4)
* **Current Defect:** `test_polynomial_ridge_surrogate` only tests Ridge regression on synthetic random numbers. It never checks whether `surrogate.prescreen_rotations` drops true Pareto/top-3 winners on real rotation candidate pools.
* **Required Fix:**
  1. Add `test_surrogate_prescreen_recall_on_candidate_pool` in `tests/test_engine.py`.
  2. Generate a large candidate rotation pool (>75 candidates) on at least 2 fields, evaluate the full unpruned pool to find the true top-3 under multiple priority profiles, and compare against the top-3 obtained after `surrogate.prescreen_rotations`.
  3. Assert recall $\ge 0.85$ (and top-1 exact match or within 2% objective score). If `surrogate.py` drops true winners, improve its feature vector (include crop economic/water/legume parameters alongside climate/soil) or increase `keep_top_n` so true winners are preserved.

#### Issue 14 — Missing CVaR Bootstrap Confidence Intervals (WS-I5)
* **Current Defect:** No bootstrap confidence interval is computed for $CVaR_{10}$ in `models/economics.py`, `evaluate.py`, or `terraloop_schemas/models.py`.
* **Required Fix:**
  1. In `packages/engine/terraloop_engine/models/economics.py`, add a deterministic moving-block bootstrap function `cvar_bootstrap_ci(profits: Sequence[float], alpha: float = 0.10, n_boot: int = 200, block_len: int = 3, seed: int = 42) -> tuple[float, float]` returning the 5th and 95th percentile confidence bounds `(cvar_ci_low, cvar_ci_high)` of $CVaR_{10}$.
  2. Add `cvar_ci_low: float | None = None` and `cvar_ci_high: float | None = None` to `SimulationResult` in `packages/schemas/terraloop_schemas/models.py` and `apps/web/src/types/api.ts`, and populate them in `evaluate.py`.
  3. Add `test_cvar_bootstrap_confidence_interval` in `tests/test_engine.py` verifying `cvar_ci_low <= cvar_profit_10 <= cvar_ci_high` and proper handling of negative tail losses.

#### Issue 15 — Contradictory `low_labour` Semantics Between `selection.py` and `main.py` (WS-I6)
* **Current Defect:** `packages/engine/terraloop_engine/optimize/selection.py` line 8 documents `low_labour : negative labour days`, while `apps/api/terraloop_api/main.py` line 658 sets `"low_labour": -pm.labor_cost_inr_per_ha` (₹/ha).
* **Required Fix:**
  1. Standardize `low_labour` semantics everywhere (`selection.py` docstrings, `main.py::_build_objective_dict` comments, `JUDGE_QA.md`, `METHODOLOGY.md`, and UI labels) to explicitly state: **negative annual hired/imputed labour cost (`-labor_cost_inr_per_ha` in ₹/ha, where less negative = lower labour requirement)**.
  2. Document the exact sign, unit, and reference point of all 6 objectives in `_build_objective_dict` and add `test_objective_builder_signs_and_scales` in `tests/test_engine.py`.

#### Issue 16 — Missing Satellite Baseline Confidence & Farmer Confirmation UI (WS-I7)
* **Current Defect:** `confirmed_by_farmer` and `confidence` exist on `CropHistorySeason` in `apps/web/src/types/api.ts`, but no UI component in `apps/web/src/**/*.tsx` displays the satellite baseline detection confidence or asks the farmer to confirm or override their current baseline rotation.
* **Required Fix:**
  1. In `apps/web/src/components/RotationExplorer.tsx`, add a visible **"Detected Current Farm Baseline"** bar/card showing:
     - The baseline crop sequence (e.g., `Puddled Rice → Wheat → Fallow`),
     - Whether it was inferred from NASA HLS 30m NDVI (with mean confidence %, e.g. `96% confidence`) or from regional benchmark defaults (when satellite history is unavailable/offline),
     - A **"Confirm Baseline"** toggle (`confirmed_by_farmer`) and a 1-tap **"Change My Current Crops"** selector that passes `baseline_override` to `api.recommend` / `recommendWithProgress` and re-ranks strategies against the farmer's confirmed baseline.
  2. Localize all labels in `en.json`, `hi.json`, `pa.json`.
  3. Add `test_baseline_confirmation_and_no_satellite_history_path` in `tests/test_engine.py` verifying that when `crop_history` is empty (GEE offline), `profiler` does not fabricate satellite seasons and `baseline_override` re-computes `vs_baseline` deltas accurately.

---

### GROUP 5: Trilingual UX, Unmodelled Factors Panel & Contract/API Hardening (WS-J & WS-K)

#### Issue 17 — Hardcoded English in `AgronomicBrief.tsx`, `brief/page.tsx`, `fallbackStrategies.ts` & Weak TSX Scanner Test (WS-J1, WS-J2, WS-J3)
* **Current Defect:**
  - `apps/web/src/components/AgronomicBrief.tsx` does not even import `useTranslation` — 100% of its headings and labels are hardcoded English.
  - `apps/web/src/app/brief/page.tsx` has hardcoded English headings/labels.
  - `apps/web/src/components/RotationExplorer.tsx` line 651 still has hardcoded JSX text (`<option value={2}>2 Years (Alternating Pest-Break)</option>` and neighboring options).
  - `test_i18n_key_parity_and_no_hardcoded_jsx_error_strings` in `tests/test_engine.py` only checks `assert 'setError("Failed to compute live recommendation' not in rot_explorer_code` instead of scanning TSX files for unlocalized JSX text.
* **Required Fix:**
  1. Wire `useLanguage()` / `t(...)` into `AgronomicBrief.tsx`, `brief/page.tsx`, and all remaining hardcoded JSX labels in `RotationExplorer.tsx`. Add all corresponding translation keys to `en.json`, `hi.json`, and `pa.json` with natural Hindi (Devanagari) and Punjabi (Gurmukhi) translations.
  2. In `apps/web/src/lib/fallbackStrategies.ts`, localize or map fallback descriptions via the active language and ensure `fallbackStrategies.ts` is ONLY ever used if explicitly requested for the Sangrur demo snapshot.
  3. Upgrade `test_i18n_key_parity_and_no_hardcoded_jsx_error_strings` in `tests/test_engine.py` so it scans `RotationExplorer.tsx`, `AgronomicBrief.tsx`, and `brief/page.tsx` for unlocalized multi-word English JSX text nodes (`>[A-Za-z][^<{]{12,}<`) and fails if hardcoded English prose is left in JSX.

#### Issue 18 — Missing "What the Model Does NOT Capture" Panel on Cards & Printable Brief (WS-J4 & WS-J5)
* **Current Defect:** Neither `RotationExplorer.tsx` nor the printable `AgronomicBrief.tsx` includes the required *"What the Model Does Not Capture"* disclosure panel (pests/bollworm/rust, hail/lodging, localized mandi gluts, seasonal labour shortages, tubewell salinity/sodicity), nor explicit `"Context Only"` badges on SMAP soil moisture.
* **Required Fix:**
  1. Add localized keys in `en.json`, `hi.json`, `pa.json` for the *"What This Model Does Not Capture"* panel (title + 5 concrete bullet points: biotic pests/diseases, localized hail/flash-flooding, private mandi price gluts, peak harvesting labour bottlenecks, and tubewell water EC/salinity) and `badge.contextOnly` (`"Context Only — does not alter ranking"`).
  2. Render this disclosure panel visibly in `RotationExplorer.tsx` AND in the printable one-page `AgronomicBrief.tsx` (ensuring it stays visible in `@media print`).
  3. Add the `"Context Only"` badge to SMAP soil moisture displays, and show when GRACE groundwater urgency scaling (`+10%/cm/yr`, capped at `1.5x`) is active.

#### Issue 19 — Missing API Input Validation, Rate Limiting & `/geocode` Caching/Throttling (WS-K4)
* **Current Defect:**
  - `FieldGeometry.polygon` in `packages/schemas/terraloop_schemas/models.py` has no vertex count or area validation.
  - `RecommendRequest` shock fields (`drought_shock_pct`, `price_shock_pct`, `fertilizer_shock_pct`) have no range bounds (`ge`/`le`).
  - `apps/api/terraloop_api/main.py` has no rate limiting middleware.
  - `/geocode` in `main.py` has no `@disk_cache` and no 1 req/sec throttling for Nominatim.
* **Required Fix:**
  1. In `packages/schemas/terraloop_schemas/models.py`:
     - Bound `drought_shock_pct: float = Field(0.0, ge=-100.0, le=100.0)`, `price_shock_pct: float = Field(0.0, ge=-100.0, le=200.0)`, `fertilizer_shock_pct: float = Field(0.0, ge=-100.0, le=300.0)`.
     - Add a `@field_validator("polygon")` on `FieldGeometry` that validates GeoJSON Polygon structure, caps coordinate ring vertices (e.g. $\le 500$ points), checks valid lat/lon bounds inside the ring, and rejects polygons larger than $10,000\text{ ha}$ ($100\text{ km}^2$).
  2. In `apps/api/terraloop_api/main.py`:
     - Add a lightweight in-memory token-bucket / sliding-window rate-limiting middleware (e.g. 60 requests/min per client IP, configurable via `TERRALOOP_RATE_LIMIT_PER_MIN`, returning HTTP 429 with a structured JSON error).
     - Wrap the Nominatim HTTP call in `/geocode` with `@disk_cache(namespace="geocode")` and enforce a thread-safe 1.0-second minimum interval between live Nominatim requests.
  3. Add `test_api_input_validation_and_hardening` in `tests/test_engine.py` testing invalid lat/lon, oversized/malformed polygons, out-of-range shocks (expecting HTTP 422), geocode caching, and rate-limiter triggering (expecting HTTP 429 when limit is set low via monkeypatch).

#### Issue 20 — Superficial Schema ↔ TypeScript Parity Test & Final Golden/Docs Sync (WS-K1 & WS-K5)
* **Current Defect:** `test_schema_typescript_interface_parity` in `tests/test_engine.py` only checks a hardcoded list of 10 field names with regex.
* **Required Fix:**
  1. Upgrade `test_schema_typescript_interface_parity` in `tests/test_engine.py` so it dynamically inspects every Pydantic `BaseModel` class in `terraloop_schemas.models` (`FieldGeometry`, `ClimateSummary`, `SoilSummary`, `WaterSummary`, `HazardSummary`, `CropHistorySeason`, `FieldProfile`, `Priorities`, `FarmConstraints`, `RotationStep`, `Rotation`, `SoilHealthBreakdown`, `SimulationResult`, `BaselineComparison`, `SeasonalOperation`, `PracticalFarmerMetrics`, `StrategyRecommendation`, `RecommendRequest`, `SuitabilityItem`), parses `apps/web/src/types/api.ts` interface blocks, and asserts that **every single field name** on every shared Pydantic model exists on the corresponding TypeScript interface.
  2. Re-run `uv run python scripts/precompute_golden.py` so all 6 golden fields in `data/golden/` and `apps/web/public/golden/` are freshly generated with all new fields (`served_from="demo_snapshot"`, `snapshot_date`, `state`, `economics_basis`, `cvar_ci_low`, `cvar_ci_high`, honest `data_mode` and provenance modes).
  3. Re-run `uv run python scripts/run_validation_benchmarks.py --write-docs` and verify `git diff --exit-code docs/BENCHMARKS.md` is empty.
  4. Update `docs/AUDIT_V3.md`, `README.md`, and `AGENTS.md` with the exact new test count and honest verification outputs.

---

## 2. Final Verification Gate (Do Not Stop Until All Pass)

Before finishing your response, execute all of the following commands and verify **zero errors**:

```powershell
uv run pytest -q -m "not network"
uv run ruff check .
uv run python scripts/run_validation_benchmarks.py --write-docs
git diff --exit-code docs/BENCHMARKS.md
cd apps/web; npx tsc --noEmit; npm run lint; npm run build
```

If any command fails or any of the 20 items above is incomplete, **stay in the loop, fix the root cause, and re-run the entire verification gate** until every check passes cleanly. In your final report, list each of the 20 issues, the exact test name proving it is fixed, and the command outputs.
