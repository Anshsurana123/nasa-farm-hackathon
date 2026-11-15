# Issues We Encountered

A complete log of the issues diagnosed and resolved while making TerraLoop's global field profiling, rotation optimization, and CMIP6 climate stress simulations work reliably end-to-end without dropping features.

---

## 1. Next.js 30-Second Proxy Timeout Causing HTTP `500` & Double Error Banners

- **Symptom:** Any global or cold-cache coordinate triggered both the red **`COULD NOT LOAD DATA`** (`Failed to load /profile` / `Failed to load /recommend`) banner and the amber **`SYNTHETIC FALLBACK MODE`** banner in the browser (e.g., Alberta `(53.497, -112.8855)` and Jalgaon `(21.343, 76.0086)`).
- **Root Causes:**
  1. **Default 30s Next.js rewrite timeout:** [apps/web/next.config.ts](apps/web/next.config.ts) rewrote `/api/*` to `http://127.0.0.1:8000/:path*` without setting `proxyTimeout`. Next.js's internal `proxy-request.js` defaulted to `30,000 ms`, aborting slower requests at `30.1s` with plain-text `HTTP 500 Internal Server Error` even though frontend timeouts were `45s` (`/profile`) and `50s` (`/recommend`).
  2. **HTTP `500` slipped past gateway/offline checks:** In [apps/web/src/lib/api.ts](apps/web/src/lib/api.ts), `res.json()` failed on Next.js's plain-text `"Internal Server Error"` body (`backendError` stayed `null`), and the status checks (`httpStatus < 500` and `httpStatus >= 502`) missed `httpStatus === 500`, throwing `Failed to load /profile` or `Failed to load /recommend`.
  3. **Synchronous `/recommend` calls & incomplete retry recovery:** [apps/web/src/context/FieldContext.tsx](apps/web/src/context/FieldContext.tsx) called blocking synchronous `/recommend` instead of async job polling (`recommendWithProgress`), and `AppShell` Retry did not re-fetch `/profile` when the active profile was missing or fell back to `generateFallbackProfile(...)`.
- **Resolution:** Configured `experimental.proxyTimeout: 120000` in [apps/web/next.config.ts](apps/web/next.config.ts), fixed HTTP `500` gateway detection + `AbortController` / `abortableSleep` handling in [apps/web/src/lib/api.ts](apps/web/src/lib/api.ts), added `/profile/async` & `/profile/jobs/{job_id}` polling endpoints (exempted from IP rate-limiting alongside `/recommend/jobs`) in [apps/api/terraloop_api/main.py](apps/api/terraloop_api/main.py), and switched [apps/web/src/context/FieldContext.tsx](apps/web/src/context/FieldContext.tsx) to `profileWithProgress` + `recommendWithProgress` with full Retry state recovery.

---

## 2. Cold `/profile` Latency Exceeding 30 Seconds Outside India

- **Symptom:** First-time visits to uncached non-India coordinates (e.g., Alberta `(53.497, -112.8855)`, Buenos Aires `(-34.6037, -58.3816)`) timed out on `/profile`, whereas immediate retries succeeded once background tasks finished populating `data/cache/`.
- **Root Causes:**
  1. `gee.init()` executed synchronously (~6–14s cold start) **before** the 24s `ThreadPoolExecutor` pool (`PROFILE_LIVE_TIMEOUT_SEC = 24.0`) in [packages/engine/terraloop_engine/profiler.py](packages/engine/terraloop_engine/profiler.py).
  2. After the 24s cap expired, `_attach_tactical_advisory` in [apps/api/terraloop_api/main.py](apps/api/terraloop_api/main.py) made extra **synchronous** Meteomatics calls outside the timeout budget.
  3. Region/KB assets loaded lazily on the first request instead of at server startup, and `detect_region_config` lacked memoization.
- **Resolution:** Added `_INIT_LOCK` in [packages/engine/terraloop_engine/data/gee.py](packages/engine/terraloop_engine/data/gee.py), overlapped `gee.init()` inside the parallel pool within the 24s cap in [packages/engine/terraloop_engine/profiler.py](packages/engine/terraloop_engine/profiler.py), added a FastAPI `_lifespan` background warmup thread (`crop_kb`, `region_registry`, `gee.init()`), and memoized `detect_region_config` (`@functools.lru_cache(maxsize=512)`) in [packages/engine/terraloop_engine/region_registry.py](packages/engine/terraloop_engine/region_registry.py).

---

## 3. Simulation Engine CPU Bottlenecks in `/recommend` (~41.7s Everywhere)

- **Symptom:** Even on cached Indian coordinates (e.g., Jalgaon `(21.343, 76.0086)`), `/recommend` took `41.7s` (`31.49s` inside `evaluate_candidates`), guaranteeing a 30s Next.js proxy timeout everywhere in the world.
- **Root Causes (`cProfile` findings):**
  1. **Invariant work repeated 85 times:** [packages/engine/terraloop_engine/optimize/evaluate.py](packages/engine/terraloop_engine/optimize/evaluate.py) re-resolved `detect_region_config`, `crop_kb.resolve_crop_spec`, `agroclimate.et0_penman_monteith_series`, and `.resample("MS")` for 30-year weather DataFrames inside every candidate rotation (~510 redundant passes).
  2. **Pandas overhead in daily crop water balance:** [packages/engine/terraloop_engine/models/fao56_runner.py](packages/engine/terraloop_engine/models/fao56_runner.py) performed repeated DataFrame `.loc` / `dayofyear.isin()` slicing, `pd.Timestamp` arithmetic, and `np.clip` calls inside every simulated day.
  3. **Unvectorized bootstrap CVaR CI:** `cvar_bootstrap_ci` in [packages/engine/terraloop_engine/models/economics.py](packages/engine/terraloop_engine/models/economics.py) ran iterative Python loops instead of NumPy vectorization.
- **Resolution:** Extracted rotation-invariant precomputation (`_build_eval_context`), reused precomputed `ReferenceET` for RothC monthly climate, replaced hot-path DataFrame slicing with NumPy epoch-day `np.searchsorted` arrays (`_WeatherArrays` / `_extract_season_arrays`), `datetime.date` arithmetic, `@functools.lru_cache(maxsize=256)` `_cached_stage_kc`, and Python `.tolist()` daily loops, and vectorized `cvar_bootstrap_ci`. Result: 85-candidate evaluation dropped from **~30.5–31.5s to ~1.95–2.6s** with bit-for-bit identical numerical outputs.

---

## 4. Concurrent Gemini `429` API Quota Failures (`why_cards.py`)

- **Symptom:** Concurrent calls to `grounded_llm_explain` fired multiple parallel Gemini HTTP requests when rate-limited (`429`), generating burst failures instead of honoring the shared 60s cooldown immediately.
- **Resolution:** Added `_LLM_LOCK = threading.Lock()` in [packages/engine/terraloop_engine/explain/why_cards.py](packages/engine/terraloop_engine/explain/why_cards.py) serializing the cooldown check and REST request inside `_call_gemini_api`, cleanly falling back to deterministic trilingual explanations.

---

## 5. CMIP6 Climate Stress Simulation Stall (`Error: Simulation stalled` on `/lab`)

- **Symptom:** Selecting `CMIP6 SSP2-4.5 (2030s)` or clicking **Run Live Engine Stress Simulation** on `/lab` threw `Error: Simulation stalled at recommendWithProgress (src/lib/api.ts:568)` in [apps/web/src/components/RotationExplorer.tsx](apps/web/src/components/RotationExplorer.tsx) after 45 seconds of polling without progress updates.
- **Root Causes (measured per-stage):**
  1. **Sequential 5-GCM GEE fetches (~90.4s uncached) with zero progress ticks:** `build_scenario_set(kind="cmip6", ...)` in [packages/engine/terraloop_engine/climate/ensembles.py](packages/engine/terraloop_engine/climate/ensembles.py) fetched historical (`1985–2014`) and future (`2026–2045` / `2041–2060`) time series for all 5 GEE `NASA/GDDP-CMIP6` models sequentially (~52.4s even with cached 5 GCMs + uncached MRI, ~133s uncached), without emitting any `progress_cb` heartbeats between `0.250` and `0.400`.
  2. **Meteomatics `source=mri-esm2` `400` retry storm (~21s per run):** Querying Meteomatics CMIP6 `"historical"` with `source=mri-esm2` returned `HTTP 400: couldn't parse mri-esm2 as a source`. `_query_param_batches` in [packages/engine/terraloop_engine/data/meteomatics.py](packages/engine/terraloop_engine/data/meteomatics.py) treated `400` as a single-parameter tier restriction and retried all 6 parameters individually across 3 sample years (~21 sequential failing HTTP requests on every run, uncached because exceptions bypass `@disk_cache`).
  3. **Meteomatics subscription date-horizon `403` retry storm (~22s per run):** Querying `ssp245` / `ssp585` for `2035`, `2045`, or `2041–2060` hit `HTTP 403: Request with valid date ... requires data access later than 2028-11-15T00:00:00Z, which is not granted with this subscription`, triggering 6-parameter individual retries across rejected future sample years even though `2026–2028` succeeded in `2.44s`.
  4. **Slow per-string `pd.to_datetime` loop (~3.85–4.55s CPU on cached reads):** `_extract_param_series` parsed 4,380 ISO timestamps one-by-one inside a Python loop for every cached Meteomatics JSON payload.
  5. **UI race window:** The Climate Scenario `<select>` in [apps/web/src/components/RotationExplorer.tsx](apps/web/src/components/RotationExplorer.tsx) remained enabled while `stressLoading` was active, allowing overlapping simulation triggers.
- **Resolution:**
  - Parallelized all GEE CMIP6 and Meteomatics future queries in [packages/engine/terraloop_engine/climate/ensembles.py](packages/engine/terraloop_engine/climate/ensembles.py) using `ThreadPoolExecutor(max_workers=8)` and `wait(..., return_when=FIRST_COMPLETED)` with streaming `progress_cb("weather", 0.26..0.39)` updates passed from [apps/api/terraloop_api/main.py](apps/api/terraloop_api/main.py).
  - Added `_MeteomaticsNonParamError`, `_UNSUPPORTED_SOURCES`, and `_MAX_GRANTED_DATE` Horizon clamping (`2026` + `2027` on `2030s`, fast `None` on `2050s`) plus vectorized ISO timestamp parsing in [packages/engine/terraloop_engine/data/meteomatics.py](packages/engine/terraloop_engine/data/meteomatics.py) (cutting warm `fetch_cmip6_daily` reads from `3.85s` to `0.03s`).
  - Increased async job polling budgets in [apps/web/src/lib/api.ts](apps/web/src/lib/api.ts) (`maxWaitMs = 150000`, `stallTimeoutMs = 60000`) and added `disabled={stressLoading}` to the scenario selector in [apps/web/src/components/RotationExplorer.tsx](apps/web/src/components/RotationExplorer.tsx).
  - Measured `/recommend` CMIP6 `ssp245_2030s` dropped from `~56s` (stalling) to **`8.45s`** (`30.03s` cold uncached), and `ssp585_2050s` completed in **`13.27s`**.

---

## 6. Verification & Environment Issues Caught During Testing

- **Next.js build vs running dev server:** Running `next build` while `next dev` held active `.next` file handles on Windows risked lock conflicts; stopped the dev server for `npm run build` (`10/10` static pages compiled cleanly) and restarted both dev daemons cleanly afterward.
- **Verification suite coverage:** All issues above were covered with regression unit tests in [tests/test_engine.py](tests/test_engine.py) (`124 passed` offline pytest suite, `ruff check .`, `npx tsc --noEmit`, `eslint`, `next build --webpack`, `scripts/run_validation_benchmarks.py --write-docs`, and live Chrome E2E verification across Jalgaon and Ames, Iowa).
