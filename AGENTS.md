# AGENTS.md: Instructions for AI coding agents

> **Read this whole file before writing any code.** Then read `docs/TASKS.md` and pick the
> **first unchecked task whose dependencies are done**. Do one task at a time, finish it
> completely (code + test + docs checkbox), then move to the next.

---

## 1. What this project is
**TerraLoop** is our NASA Space Apps Challenge entry: a crop-rotation decision-support tool.
It combines NASA Earth observations, soil data, crop characteristics and **farmer priorities**
to recommend rotations that protect soil health, save water and adapt to climate change.

- **Lead demo story:** Punjab, India (rice-wheat → groundwater depletion, stubble burning).
- **Full product vision:** `docs/BUILD_PLAN.md` (also `docs/BUILD_PLAN.docx`). That file is the source of truth for *what* to build.
- **This file** is the source of truth for *how* to build it.
- **Task backlog:** `docs/TASKS.md` (ordered by priority, with acceptance criteria).
- **Datasets:** `docs/DATASETS.md` (every NASA product, ID, DOI, GEE collection).

## 2. Repository map
```
pyproject.toml              uv workspace root (Python 3.11+); pytest + ruff config
packages/schemas/           SHARED CONTRACTS (Pydantic). Change with care: frontend depends on them
  terraloop_schemas/models.py
packages/engine/            all science + logic, NO web code here
  terraloop_engine/
    cache.py                @disk_cache decorator (JSON, data/cache/)
    crop_kb.py              loads packages/crop-kb/crops/*.yaml -> CropSpec
    profiler.py             build_profile(FieldGeometry) -> FieldProfile   [WORKING]
    suitability.py          heuristic crop pre-filter                      [WORKING]
    data/nasa_power.py      NASA POWER daily client                        [WORKING]
    data/soilgrids.py       ISRIC SoilGrids client                         [WORKING]
    data/gee.py             Google Earth Engine (NASA collections)         [STUBS]
    eo/phenology.py         NDVI -> seasons -> crop history                [STUBS]
    models/agroclimate.py   ET0, GDD, dry spells                           [WORKING]
    models/soil.py          texture class, Saxton-Rawls                    [WORKING]
    models/rusle.py         erosion (REFERENCE STYLE for all models)       [WORKING]
    models/aquacrop_runner.py  yield/water simulation                      [STUB + spec]
    models/soil_health.py   RothC-lite, N balance, soil health score       [PARTIAL]
    climate/ensembles.py    historical + CMIP6 scenarios                   [STUBS]
    optimize/rotations.py   candidate generation + constraints             [WORKING]
    optimize/selection.py   Pareto + priority-weighted top-k               [WORKING]
    explain/why_cards.py    explanations                                   [STUB + templates]
packages/crop-kb/crops/     one YAML per crop (21 crops). _template.yaml documents fields
apps/api/terraloop_api/main.py  FastAPI: /health /crops /golden /profile /suitability /recommend(501)
apps/web/                   Next.js frontend (map + Field Report Card)
data/golden/fields.json     demo fields (Sangrur = hero). Precomputed outputs go in data/golden/<id>/
data/cache/                 API response cache (git-ignored)
scripts/precompute_golden.py
tests/                      pytest; offline by default
docs/                       BUILD_PLAN, TASKS, DATASETS, METHODOLOGY
```
Files marked `[STUB]` contain the function signatures **and a written spec in the docstring**.
Implement exactly that spec; don't redesign the interface without updating the schemas and docs.

## 3. Setup and commands (Windows PowerShell; also works on macOS/Linux)
```powershell
uv sync                                   # install all Python packages (editable)
uv run pytest -q                          # run tests (must stay green)
uv run pytest -q -m "not network"         # skip tests that call live APIs
uv run ruff check .                       # lint
uv run python scripts/precompute_golden.py           # build golden profiles (needs internet)
uv run uvicorn terraloop_api.main:app --reload --port 8000 --app-dir apps/api
# frontend
cd apps/web; npm install; npm run dev     # http://localhost:3000 (expects API on :8000)
```
Optional heavy extras (install only when your task needs them):
```powershell
uv pip install -e "packages/engine[gee]"        # Earth Engine; then: earthengine authenticate
uv pip install -e "packages/engine[sim]"        # AquaCrop-OSPy
uv pip install -e "packages/engine[opt]"        # pymoo, scikit-learn, lightgbm
uv pip install -e "packages/engine[earthdata]"  # earthaccess, xarray (needs NASA Earthdata login)
```
Environment variables: see `.env.example`.

## 4. Golden rules (do not break these)
1. **NASA data first.** Any new data source must be NASA where possible. Record it in `docs/DATASETS.md` with product ID + DOI.
2. **Provenance on every number.** Any function producing a user-facing number must attach a `DataProvenance` (see `models.py`). No provenance = not done.
3. **Never invent numbers in explanations.** LLM text may only use values returned by engine functions.
4. **The demo must never fail.** Golden fields are served from `data/golden/<id>/*.json`. Every new pipeline step must be included in `scripts/precompute_golden.py`.
5. **Optional sources must not crash the profile.** Wrap external calls in try/except, log, leave the field `None`.
6. **Contracts first.** If you need a new field, add it to `packages/schemas/terraloop_schemas/models.py` with a default value (so old JSON still validates), then use it.
7. **Pure functions for science.** Models take numbers/DataFrames and return numbers/DataFrames: no HTTP, no file I/O. Copy the style of `models/rusle.py` (cited equations, units in docstrings).
8. **Cache every external call** with `@disk_cache(namespace=...)`.
9. **Tests are required.** Each task adds at least one offline test. Network tests must be marked `@pytest.mark.network`.
10. **Don't delete or rewrite working modules** to fix a small bug. Make the smallest correct change.
11. **Units:** mm (water), °C, t/ha (yield, SOC stocks), kg/ha (N), % (texture), g/kg (SOC concentration), days. Put the unit in the variable name when ambiguous (`irrigation_mm`).
12. **Crop data** goes in YAML (`packages/crop-kb/crops/`), never hard-coded in Python. Every value needs a `sources` entry.

## 5. Data flow (what calls what)
```
FieldGeometry
  └─ profiler.build_profile ──> FieldProfile (climate, soil, water, hazards, crop_history)
        ├─ data.nasa_power      (done)
        ├─ data.soilgrids       (done)
        ├─ data.gee.*           (TASK-D02..D09) -> water/hazards/crop_history
        └─ eo.phenology         (TASK-E01..E02)
FieldProfile + FarmConstraints
  └─ suitability.rank_crops ──> candidate crop list
  └─ optimize.rotations.generate_rotations ──> list[Rotation]   (+ baseline_rice_wheat)
Rotation x ScenarioSet (climate.ensembles)
  └─ models.aquacrop_runner.simulate_rotation  -> yields, irrigation
  └─ models.soil_health (RothC, N, score), models.rusle -> SimulationResult
list[SimulationResult] + Priorities
  └─ optimize.selection.select_top ──> top 3 ──> explain.why_cards ──> StrategyRecommendation
API /recommend (TASK-A03) wires this whole chain.
```

## 6. Coding conventions
- Python 3.11+, type hints everywhere, `from __future__ import annotations`.
- Pydantic v2 (`model_validate`, `model_dump`, `model_dump_json`).
- Line length 120 (ruff). Run `uv run ruff check . --fix` before finishing.
- Module docstring explains purpose + references the TASK id.
- Frontend: TypeScript, functional React components, Tailwind classes, no CSS frameworks beyond Tailwind.
- Keep UI strings in `apps/web/src/i18n/*.json` (en, pa, hi) from the start. Never hard-code user-facing text.

## 7. Definition of done (for every task)
- [ ] Code implements the spec in the stub docstring / TASKS.md acceptance criteria
- [ ] Offline test added and `uv run pytest -q -m "not network"` passes
- [ ] `uv run ruff check .` passes
- [ ] Provenance attached to new user-facing numbers
- [ ] Golden precompute updated if the pipeline changed
- [ ] Checkbox ticked in `docs/TASKS.md` + one-line note of what was done
- [ ] `docs/DATASETS.md` / `docs/METHODOLOGY.md` updated if you added a dataset or method

## 8. When you are unsure
- Re-read the stub docstring and `docs/BUILD_PLAN.md` section referenced in TASKS.md.
- Prefer the simplest implementation that meets the acceptance criteria; mark refinements as `# TODO(TASK-XXX):`.
- If a dataset/API doesn't behave as described, write what you found in `docs/NOTES.md` and use a fallback rather than guessing values.
- Never fabricate scientific constants: cite a source in the code comment or YAML.
