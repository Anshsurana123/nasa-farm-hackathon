# TerraLoop ⟳

> **Adaptive Crop-Rotation Decision Support System Powered by NASA Earth Observations**  
> *NASA Space Apps Challenge 2026 Entry*

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/next.js-16+-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![NASA Earth Observations](https://img.shields.io/badge/NASA-Earth%20Observations-critical.svg)](https://earthdata.nasa.gov/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🌾 The Challenge & Vision

Around the world, farmers navigate shifting rainfall patterns, severe groundwater depletion, extreme heat waves, and degrading soils. Nowhere is this tension more acute than in the **Indo-Gangetic Plain of Punjab, India**:
- **Aquifer Depletion:** NASA GRACE / GRACE-FO satellites observe groundwater depletion rates of **~3.5 to 4.2 cm/year** due to water-intensive puddled paddy rice.
- **Air Pollution & Soil Carbon Loss:** The narrow window between rice harvest and wheat sowing drives widespread stubble burning (monitored by NASA FIRMS), burning crucial organic carbon and causing hazardous air quality across northern India.

**TerraLoop** is an open-science decision-support tool that transforms NASA Earth observations into actionable, resilient crop-rotation strategies tailored to individual fields and farmer priorities.

---

## 🛰️ NASA Earth Observations Registry

Every recommendation, chart, and metric in TerraLoop carries end-to-end data provenance:

| Dataset | Product ID / Collection | Spatial / Temporal Resolution | Engine Integration | Reference / DOI |
|---|---|---|---|---|
| **NASA POWER** | Daily Agroclimatology (`AG`) | 0.5° × 0.625°, Daily (1981–2024) | Tmax, Tmin, Precip, Solar Rad → Hargreaves ET₀, GDD, FAO-56 daily weather | [power.larc.nasa.gov](https://power.larc.nasa.gov/) |
| **NASA GPM IMERG** | `NASA/GPM_L3/IMERG_V07` | 0.1°, Daily (2000–2024) | Precipitation totals, monsoon distribution, dry spells, RUSLE R-factor | [10.5067/GPM/IMERGDF/DAY/07](https://doi.org/10.5067/GPM/IMERGDF/DAY/07) |
| **NASA SMAP** | `NASA/SMAP/SPL4SMGP/008` | 9 km, Daily (2015–2024) | 12 monthly root-zone soil moisture percentiles vs 10-year climatology | [10.5067/K2VT90DE20GV](https://doi.org/10.5067/K2VT90DE20GV) |
| **NASA GRACE / GRACE-FO** | `NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI` | ~0.5° (native 3°), Monthly | Terrestrial water storage / groundwater trend rate (cm/yr) | [10.5067/TEMSC-3MJ62](https://doi.org/10.5067/TEMSC-3MJ62) |
| **NASA NASADEM** | `NASA/NASADEM_HGT/001` | 30 m Elevation | Topographic field slope (%) for RUSLE LS erosion factor | [10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001) |
| **NASA FIRMS** | `FIRMS` (MODIS / VIIRS) | 375 m / 1 km | Detection of Oct–Nov crop residue (paddy stubble) burning | [10.5067/FIRMS/MODIS](https://doi.org/10.5067/FIRMS/MODIS) |
| **NASA HLS** | `NASA/HLS/HLSL30/v002` & `HLSS30/v002` | 30 m, 2–3 day | Cloud-masked NDVI time series → Savitzky-Golay smoothing → season detection & crop history | [10.5067/HLS/HLSL30.002](https://doi.org/10.5067/HLS/HLSL30.002) |
| **ISRIC SoilGrids** | SoilGrids 2.0 Digital Soil Map | 250 m | Topsoil 0–30 cm Sand, Silt, Clay, SOC, pH, BD, CEC, N | [10.5194/soil-7-217-2021](https://doi.org/10.5194/soil-7-217-2021) |

---

## 🔬 Scientific Methodology & Process Models

TerraLoop links Earth observations directly to rigorous agronomic models:

1. **FAO-56 / FAO-33 Soil-Water Balance (`models/aquacrop_runner.py`):** Daily root-zone soil moisture depletion (`TAW`, `RAW`, water stress coefficient `Ks`, stage-wise `Kc`, deep percolation, and reproductive thermal senescence). Calibrated for puddled transplanted rice (175 mm puddling, 3.5 mm/day flooded percolation) vs PAU Short-Duration PR-126 (~21% water saved from 22 fewer field days) and Direct Seeded Rice + AWD (75 mm pre-sowing wetting, 2.55 mm/day percolation on loam, ~27.5% irrigation reduction).
2. **RothC-lite 26.3 Carbon Model:** 5-pool monthly carbon model (DPM, RPM, BIO, HUM, IOM) based on Coleman & Jenkinson (1996) and Falloon et al. (1998). Simulates decadal topsoil organic carbon accretion ($\Delta$ t C/ha/10yr) accounting for in-situ mulching vs stubble burning penalties.
3. **Nitrogen Mass Balance & Legume Credit:** Seasonal N balance accounting for crop removal, BNF by legumes (moong, dhaincha, chickpea), and granting a 25 kg N/ha synthetic fertilizer credit to succeeding cereals.
4. **5 USDA-NRCS Soil Health Principles Index:** 0–100 composite index with transparent component breakdown (`soil_health_breakdown`: 5 principles × 15 pts max = 75 pts + SOC & RUSLE modifiers ±25 pts − 5 pt residue burning penalty).
5. **RUSLE Soil Erosion:** Revised Universal Soil Loss Equation screening using NASADEM slope and GPM IMERG rainfall erosivity.
6. **Agro-Economics & Procurement Risk:** Profit distributions ($P_{10}, P_{50}, P_{90}$) and Downside Risk ($CVaR_{10}$) based on official Indian Commission for Agricultural Costs & Prices (CACP 2024–25) MSP, state $A_2 + FL$ cost of cultivation (Punjab paddy ₹64,500/ha, wheat ₹48,500/ha), and procurement assurance (`msp_assured`, `nafed_pss`, `mandi_linked`).
7. **Wheat Terminal Heat Stress:** Explicit tracking of days with $T_{max} > 32^\circ\text{C}$ during reproductive grain-filling (1 March–15 April) with 12-month Indo-Gangetic irrigation cooling bias correction.
8. **Reproducible Benchmarks (`docs/BENCHMARKS.md`):** Automated empirical comparison against DES / ICRISAT district-level yield statistics across 6 Indian agro-climatic zones (`uv run python scripts/run_validation_benchmarks.py --write-docs`).

---

## 📁 Repository Structure

```
├── packages/
│   ├── schemas/              # Pydantic v2 data models (shared contract)
│   ├── engine/               # Pure science modules (models, EO phenology, GEE, optimizers)
│   │   ├── terraloop_engine/
│   │   │   ├── profiler.py   # Synthesizes NASA data into FieldProfile
│   │   │   ├── data/         # NASA POWER, ISRIC, Google Earth Engine clients
│   │   │   ├── eo/           # HLS NDVI smoothing, phenology & crop history
│   │   │   ├── models/       # FAO-56 water balance, RothC, N-balance, Soil Health, RUSLE, Economics
│   │   │   ├── optimize/     # Candidate rotation generator & multi-objective selection
│   │   │   └── explain/      # Deterministic why-cards with provenance citations
│   └── crop-kb/              # Agronomic parameters for 23 crops + CACP A2+FL economics
├── apps/
│   ├── api/                  # FastAPI backend (/profile, /recommend, /golden)
│   └── web/                  # Next.js 16 (Turbopack) frontend + Tailwind CSS + i18n
├── data/
│   ├── golden/               # Precomputed benchmark demo fields (Sangrur, Ludhiana, etc.)
│   └── cache/                # Disk-cached API responses for zero-network resilience
├── tests/                    # Pytest test suite (100% offline-passing)
└── docs/                     # BUILD_PLAN, METHODOLOGY, BENCHMARKS, DATASETS, TASKS
```

---

## ⚡ Quick Start

### 1. Prerequisites & Environment
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)
- Node.js 18+ (for frontend)

```powershell
# Clone the repository
git clone https://github.com/your-org/terraloop.git
cd terraloop

# Install Python workspace dependencies
uv sync
```

### 2. Run Tests & Linters
```powershell
# Run offline test suite
uv run pytest -q

# Run ruff linter
uv run ruff check .
```

### 3. Google Earth Engine Setup (Optional for Live Mode)
TerraLoop includes precomputed cached profiles for all demo fields, enabling 100% offline operation. To query live satellite pixels:
```powershell
uv pip install -e "packages/engine[gee]"
earthengine authenticate
```
Set your Google Cloud project in `.env`:
```env
GEE_PROJECT=your-gcp-project-id
```

### 4. Start the API Backend
```powershell
uv run uvicorn terraloop_api.main:app --reload --port 8000 --app-dir apps/api
```
API Documentation will be live at `http://localhost:8000/docs`.

### 5. Start the Web Frontend
```powershell
cd apps/web
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to launch the TerraLoop interactive dashboard.

---

## 🌐 Localization (i18n)

TerraLoop is designed for grassroots accessibility and multilingual farmer engagement:
- **English**
- **ਪੰਜਾਬੀ (Punjabi in Gurmukhi script)**
- Instant toggle in navigation bar with zero hardcoded UI strings.

---

## 📄 License & Attribution

Developed for the **NASA Space Apps Challenge 2026**.  
Released under the [MIT License](LICENSE). All NASA datasets and third-party scientific models are credited in `docs/DATASETS.md` and `docs/METHODOLOGY.md`.
