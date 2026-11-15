# NASA Space Apps Challenge 2026: Official Submission Package

**Project Name:** TerraLoop ⟳  
**Challenge:** Crop Rotations Planned with NASA Earth Observations  
**Team Members:** **Ansh Surana** (Team Leader, 11 AS LVL) · **Naksh Joge** (11 AS LVL)  
**Geographic Scope:** Global (3-Tier Validation: 17 Indian ICAR Zones + 5 Calibrated Global Breadbasket Hubs + Köppen-Geiger Biophysical Global Mode)  
**Live Demo:** Precomputed offline-ready for **11 Benchmark Fields across 6 Continents** (`sangrur`, `ludhiana`, `bathinda`, `vidarbha`, `bundelkhand`, `thanjavur`, `us_corn_belt`, `eu_maritime_west`, `brazil_cerrado`, `east_africa_highlands`, `australia_wheat_belt`)  
**Presentation Deck:** [`docs/TerraLoop_NASA_Space_Apps_2026_Deck.pptx`](TerraLoop_NASA_Space_Apps_2026_Deck.pptx) (exported PDF: [`docs/TerraLoop_NASA_Space_Apps_2026_Deck.pdf`](TerraLoop_NASA_Space_Apps_2026_Deck.pdf))

---

## 1. 30-Second Video Storyboard & Script (TASK-S01)

> **Format:** 30 seconds, 1080p 16:9, English narration with English, Hindi & Punjabi subtitles.

| Timestamp | Visual Shot | Audio Narration | On-Screen Graphic & Evidence |
|---|---|---|---|
| **00:00 – 00:06** | **Hook:** NASA GRACE Regional TWS anomaly map zoomed over NW India showing crimson aquifer drawdown (`-4.15 cm/yr`), overlaid with NASA FIRMS Oct–Nov stubble fire hotspots across Punjab. | *"From space, NASA satellites see aquifers dropping four centimeters a year while farmers face shrinking planting windows, extreme heat, and declining soils."* | **Signal:** NASA GRACE (`-4.15 cm/yr` Sangrur mascon) + NASA FIRMS (Stubble fires). |
| **00:06 – 00:12** | **Diagnosis:** User selects any pin worldwide (e.g., Sangrur hero field or Ames, Iowa) or enters a Government Soil Health Card. Report Card decodes satellite phenology, soil hydraulics, and heat risk. | *"Select any farm worldwide—or enter local soil lab results. TerraLoop fuses ten NASA Earth data streams, WorldCereal phenology, and SoilGrids into an instant field diagnosis."* | **Signal:** NASA POWER + GPM IMERG + SMAP L4 + HLS 30 m + WorldCereal + ISRIC / SHC override. |
| **00:12 – 00:20** | **Decision Engine:** Farmer adjusts 6 priorities (water, soil, profit, drought risk, labour, nutrition) or toggles `/Acre (Killa)` in Punjabi, Hindi, or English; FAO-56 + RothC + NSGA-II run live. | *"Farmers set their own priorities and run multi-year FAO-56 water balance, RothC carbon turnover, and CMIP6 climate stress ensembles in real time."* | **Action:** Priority Sliders + FAO-56 Root-Zone & RothC 10-yr Carbon simulation. |
| **00:20 – 00:26** | **Actionable Strategy:** Side-by-side cards compare Baseline (`Puddled Rice → Wheat`) vs Rank #1 (`DSR Rice → Sunflower → Mung bean`), #2 (`Maize → Sunflower → Mung bean`), and #3 (`Mung bean → Wheat → Blackgram`). | *"In Sangrur, top rotations cut irrigation 18% to 60%, expand sowing windows to 26–34 days to prevent burning, build +3 tonnes of soil carbon, and save up to 4.1 bags of Urea."* | **Results:** `-17.6% to -60.1%` Water · `26–34 d` Burn-Free Window · `+3.01 t C/ha` SOC · `3.5–4.1` Urea Bags Saved. |
| **00:26 – 00:30** | **Global Reach & Outro:** Montage pans from India across USA, France, Brazil, Kenya, and Australia golden hubs (`13.0%` held-out 5-continent MAPE). | *"TerraLoop: turning NASA Earth science into climate-resilient, profitable crop rotations for farmers everywhere."* | **Logo:** TerraLoop ⟳ · Team: Ansh Surana & Naksh Joge · Space Apps 2026. |

---

## 2. 7-Slide Pitch Deck Structure (`docs/TerraLoop_NASA_Space_Apps_2026_Deck.pptx`)

> Strictly honors the NASA Space Apps **7-slide maximum (including title & intro slides)**.

### Slide 1: TerraLoop ⟳ — Title, Challenge Fit & Team
- **Header:** TerraLoop ⟳ — Adaptive Crop-Rotation Decision Support Powered by NASA Earth Observations
- **Challenge Alignment:** Translating NASA EO + local soils + crop traits + farmer priorities into profitable, water-saving, soil-regenerating rotations worldwide.
- **Team:** **Ansh Surana** (Team Leader, 11 AS LVL) · **Naksh Joge** (11 AS LVL)
- **At-a-Glance Metrics:** `10` NASA Data Products · `40` Crops · `11` Global Benchmarks (6 Continents) · `13.0%` Held-Out 5-Continent MAPE · `124/124` Passing Offline Tests.

### Slide 2: The Crisis Visible from Space (Why Static Calendars Fail)
- **Shifting Temperatures:** `+4.5°C` March terminal heatwaves (`Tmax > 32°C`) slash conventional wheat yields by **`-16.7%`** (`4.90 → 4.08 t/ha`), buffered to **`-10.8%`** (`4.37 t/ha`) under Happy Seeder mulch (`-1.0°C` canopy cooling).
- **Water Shortages:** NASA GRACE/GRACE-FO detects **`-4.15 cm/yr`** aquifer drawdown across Central Punjab (`-3.85 cm/yr` zone baseline), automatically scaling optimization `water_savings` urgency up to `1.50×`.
- **Extreme Weather & Stubble Fires:** Long-duration puddled rice leaves an **11-day** Kharif→Rabi turnaround, triggering NASA FIRMS post-harvest burning and **`-1.92 t C/ha/10yr`** RothC soil carbon loss.

### Slide 3: End-to-End Architecture & NASA Earth Observation Stack
- **Data Ingestion (10 NASA Streams + Local Overrides):** NASA POWER, GPM IMERG V07, SMAP L4, GRACE/GRACE-FO, NASADEM, FIRMS, HLS L30/S30, NEX-GDDP-CMIP6, NASA GIBS WMTS (`context only`), plus ISRIC SoilGrids 2.0, Govt Soil Health Card lab overrides, ESA WorldCereal 10 m, Köppen-Geiger 0.5° AEZs, and Meteomatics 90 m hydrology & agro-hazards.
- **Coupled Science Engine:** Penman–Monteith ET0 + Saxton–Rawls hydraulics + FAO-56/33 water & thermal balance + RothC-26.3 5-pool carbon + Species BNF N balance + Kinetic RUSLE $EI_{30}$ + ICMR-NIN / USDA FDC nutrition + Regional enterprise budgets.
- **Multi-Objective Optimization:** 6-objective NSGA-II Pareto sorting with `MIN_SPREADS` noise guards, `CVaR-10` drought-tail risk, Polynomial Ridge Surrogate (`>85` candidates), and a 3-tier global honesty gate.

### Slide 4: Hero Field Transformation — Sangrur, Punjab (`data/golden/sangrur/recommendations.json`)
- **Direct Comparison Chart (`Baseline` vs. Top-3 NSGA-II Recommendations):**
  | Metric | Baseline (`Puddled Rice → Wheat`) | Rank #1 (`DSR Rice → Sunflower → Mung bean`) | Rank #2 (`Maize → Sunflower → Mung bean`) | Rank #3 (`Mung bean → Wheat → Blackgram`) |
  |---|---|---|---|---|
  | **Irrigation Savings** | `1,128.6 mm/yr` (Baseline) | **-17.6%** (`3 irr.`, `113 pump hrs/ha`) | **-60.1%** (`9 irr.`, `386 pump hrs/ha`) | **-50.0%** (`8 irr.`, `321 pump hrs/ha`) |
  | **Kharif→Rabi Window** | `11 days` (Burn crunch) | **`26 days`** (Burn-free) | **`34 days`** (Zero-till ready) | **`34 days`** (Zero-till ready) |
  | **10-Yr Soil Carbon** | `-1.92 t C/ha` (`22.3/100`) | **`+3.01 t C/ha`** (`87.7/100`) | **`+3.29 t C/ha`** (`85.2/100`) | **`+1.42 t C/ha`** (`78.1/100`) |
  | **45-kg Urea Saved** | `0 bags` | **`3.5 bags/ha`** | **`3.5 bags/ha`** | **`4.1 bags/ha`** |
  | **Profit (`P50` / `CVaR-10`)** | `₹170,334` / `₹77,208` | **`₹271,978`** / **`₹217,384`** | `₹230,542` / `₹165,596` | `₹214,188` / `₹196,628` |

### Slide 5: Global Multi-Continent Validation & 3-Tier Scientific Honesty
- **Held-Out Empirical Accuracy (`docs/BENCHMARKS.md`):**
  - **India Calibration & Held-Out Sites:** Sangrur wheat `+3.4%`, paddy `+2.5%`; held-out Ludhiana `+4.9%–5.0%`, Bathinda `+4.8%`, Thanjavur `+7.4%` (while transparently documenting rainfed peninsular biotic yield gaps).
  - **5-Continent Global Breadbaskets (`13.0%` MAPE across 14 held-out crop-hub pairs):** Iowa Soybean `-0.3%` & Corn `-7.9%`; France Beauce Barley `+3.0%` & Colza `+6.5%`; Brazil Safrinha Corn `-6.2%`; Kenya Highland Maize `+1.3%` & Potato `+3.4%`; Australia Canola `+15.5%` & Wheat `+18.4%`.
- **3-Tier Global Honesty Gate:** `validated_india` (17 ICAR zones, 5 CACP states) · `validated_regional` (5 global hubs in local currencies + schemes) · `biophysical_global` (disables uncalibrated economic ranking globally so only water, soil health, and nutrition steer ranks).

### Slide 6: Farmer-First Design & Priority Control
- **Farmer Priorities Steer Every Rank:** Verified by 200-vector Monte Carlo monotonicity sweep (`0` violations across 1,200 checks) + CMIP6 (`SSP2-4.5` & `SSP5-8.5`) & drought/price Stress Lab.
- **Built for Field Accessibility:** Trilingual UI (`English` / `हिन्दी` / `ਪੰਜਾਬੀ`, `780` synchronized keys), 1-click `/Acre (Killa)` vs `/Ha` toggle, Soil Health Card (`pH`, `SOC`, `N`, `P`, `K`) override, printable KVK Brief, and automatic matching across **26 Central, State & Global Conservation Schemes** (e.g., Punjab DSR, CRM Happy Seeder, USDA EQIP/CSP, EU CAP Eco-Schemes, Brazil Plano ABC+, Kenya KCSAP, Australia ACCU).

### Slide 7: Engineering Proof, Reproducibility & Adoption Path
- **Production-Grade Verification:** `124/124` offline pytest cases passing, `0` Ruff / TypeScript / ESLint errors, deterministic CI diff guard (`git diff --exit-code docs/BENCHMARKS.md`), strict provenance (`observed` vs `hybrid_regional` vs `demo_snapshot` with zero fabricated satellite numbers), and `0.03s–8.5s` async CMIP6 execution.
- **Open-Source Impact & Next Steps:** MIT-licensed full-stack platform (FastAPI + Next.js 16 + MapLibre 6 + Vercel/Docker ready) poised for KVK, FPO, and extension-advisor pilots worldwide.

---

## 3. Portal "References" Field (Ready to Copy-Paste for Space Apps Submission)

> NASA Space Apps Eligibility requires listing **all external data, code, APIs, text, and visual resources** in the project's References field. See [`docs/DATA_SOURCES_AND_PARTNER_LINKS.md`](DATA_SOURCES_AND_PARTNER_LINKS.md) for all 64 verified URLs and the complete internal dataset inventory:

- **NASA Earth Observations & Tools:** NASA POWER Agroclimatology API (`https://power.larc.nasa.gov/`); NASA GPM IMERG V07 (`https://doi.org/10.5067/GPM/IMERG/3B-HH/07`); NASA SMAP L4 Root-Zone Soil Moisture `SPL4SMGP V008` (`https://doi.org/10.5067/T5RUATAQREF8`); NASA GRACE / GRACE-FO Mascon CRI RL06 V04 (`https://doi.org/10.5067/TEMSC-3MJ62`); NASA NASADEM 30 m (`https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001`); NASA FIRMS Active Fire Data (`https://firms.modaps.eosdis.nasa.gov/`); NASA Harmonized Landsat Sentinel-2 HLS L30/S30 v002 (`https://doi.org/10.5067/HLS/HLSL30.002`, `https://doi.org/10.5067/HLS/HLSS30.002`); NASA NEX-GDDP-CMIP6 (`https://www.nccs.nasa.gov/data-collections/nex-gddp-cmip6/`); NASA GIBS WMTS (`https://nasa-gibs.github.io/gibs-api-docs/`); NASA SRTM (`https://www.earthdata.nasa.gov/data/instruments/srtm`).
- **Sponsor, Soil & Satellite Land Cover APIs:** Meteomatics 90 m Weather, 4-Layer Soil Hydrology, Agro-Hazards & MRI-ESM2.0 API (`meteomatics.com`); ISRIC SoilGrids 2.0 (`https://doi.org/10.5194/soil-7-217-2021`); ESA WorldCereal 10 m v100 (`https://doi.org/10.5281/zenodo.7875105`); Google Earth Engine (`https://earthengine.google.com/`); Natural Earth Vector (`https://www.naturalearthdata.com/`); Köppen-Geiger Climate Grid (`https://www.gloh2o.org/koppen/`).
- **Agronomic, Nutritional & Economic Ground Truth:** FAO Irrigation & Drainage Papers 56 & 33 (`https://www.fao.org/4/x0490e/x0490e00.htm`); Saxton & Rawls (2006, `https://doi.org/10.2136/sssaj2005.0117`); RothC-26.3 (`https://doi.org/10.1007/978-3-642-61094-3_17`); Ambika & Mishra (2019, `https://doi.org/10.1029/2019GL084367`); ICMR-NIN (`https://www.nin.res.in/`) & USDA FoodData Central (`https://fdc.nal.usda.gov/`); Soil Health Card, CACP, UPAg, DES, ICAR-NBSS&LUP, India-WRIS, ICRISAT, NAFED & State Agriculture Portals; USDA NASS, Agreste, ARVALIS, EU CAP, IBGE SIDRA, IMEA, Plano ABC+, GRDC, CER, KALRO, KNBS, and NPCK.
- **Open-Source Software & Basemaps:** Python, FastAPI, Pydantic v2, NumPy, pandas, Next.js, React, Tailwind CSS, MapLibre GL JS, Esri World Imagery, OpenStreetMap / Nominatim, AWS Terrain Tiles, Google Gemini API, and Canva.

---

## 4. Reproducibility & Verification Commands

```powershell
uv run pytest -q -m "not network"                                # 124 offline unit & biophysical tests
uv run ruff check .                                              # Zero Python lint errors
uv run python scripts/precompute_golden.py                       # Rebuild all 11 golden fields + sync to web
uv run python scripts/run_validation_benchmarks.py --write-docs  # Regenerate docs/BENCHMARKS.md from engine
git diff --exit-code docs/BENCHMARKS.md                          # CI benchmark reproducibility guard
cd apps/web; npx tsc --noEmit; npm run lint; npm run build       # Verify TypeScript, ESLint & production build
```
