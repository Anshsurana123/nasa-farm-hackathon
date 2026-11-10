# TerraLoop ⟳

> **Adaptive Crop-Rotation Decision Support System Powered by NASA Earth Observations**  
> *NASA Space Apps Challenge Entry*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16.3+-black.svg?logo=next.js&logoColor=white)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19.2+-61DAFB.svg?logo=react&logoColor=black)](https://react.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-v4-38B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![NASA Earth Observations](https://img.shields.io/badge/NASA-Earth%20Observations-critical.svg?logo=nasa&logoColor=white)](https://earthdata.nasa.gov/)
[![Tests: 66/66 Passing](https://img.shields.io/badge/Tests-66%2F66%20Passing-success.svg?logo=pytest&logoColor=white)](tests/)
[![Ruff](https://img.shields.io/badge/Linter-Ruff%20Clean-brightgreen.svg?logo=ruff&logoColor=white)](https://astral.sh/ruff)
[![i18n](https://img.shields.io/badge/Languages-English%20%7C%20%E0%A8%AA%E0%A9%B0%E0%A8%9C%E0%A8%BE%E0%A8%AC%E0%A9%80%20%7C%20%E0%A4%B9%E0%A4%BF%E0%A4%A8%E0%A5%8D%E0%A4%A6%E0%A5%80-orange.svg)](#-multilingual-grassroots-accessibility-i18n)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📑 Table of Contents
1. [The Challenge & Problem Statement](#-the-challenge--problem-statement)
2. [How TerraLoop Solves the Challenge](#-how-terraloop-solves-the-challenge)
3. [Lead Demo Story: Punjab's Rice–Wheat Crisis](#-lead-demo-story-punjabs-ricewheat-crisis)
4. [NASA Earth Observations Registry](#-nasa-earth-observations-registry)
5. [System Architecture & Data Flow](#-system-architecture--data-flow)
6. [Scientific Methodology & Process Models](#-scientific-methodology--process-models)
   - [FAO-56 / FAO-33 Daily Soil-Water Balance & Rice Hydrology](#1-fao-56--fao-33-daily-soil-water-balance--rice-hydrology-modelsfao56_runnerpy)
   - [March Wheat Reproductive Terminal Heat Stress](#2-march-wheat-reproductive-terminal-heat-stress-modelsfao56_runnerpy)
   - [RothC-lite 26.3 Decadal Soil Organic Carbon Model](#3-rothc-lite-263-decadal-soil-organic-carbon-model-modelssoil_healthpy)
   - [Seasonal Nitrogen Mass Balance & Legume Credit](#4-seasonal-nitrogen-mass-balance--legume-credit-modelssoil_healthpy)
   - [USDA-NRCS 5 Principles Soil Health Index (0–100)](#5-usda-nrcs-5-principles-soil-health-index-0100-modelssoil_healthpy)
   - [RUSLE Soil Erosion Screening](#6-rusle-soil-erosion-screening-modelsruslepy)
   - [Agro-Economics & Downside Risk ($CVaR_{10}$)](#7-agro-economics--downside-risk-cvar_10-modelseconomicspy)
7. [23-Crop Agronomic Knowledge Base](#-23-crop-agronomic-knowledge-base)
8. [Six Indian Agro-Climatic Golden Benchmark Fields](#-six-indian-agro-climatic-golden-benchmark-fields)
9. [Empirical Ground-Truth Validation & Sensitivity Benchmarks](#-empirical-ground-truth-validation--sensitivity-benchmarks)
10. [Web Application & Farmer Experience](#-web-application--farmer-experience)
11. [Multilingual Grassroots Accessibility (i18n)](#-multilingual-grassroots-accessibility-i18n)
12. [Repository Structure](#-repository-structure)
13. [API Reference & OpenAPI Specification](#-api-reference--openapi-specification)
14. [Quick Start & Developer Setup](#-quick-start--developer-setup)
15. [Deployment & Offline Resilience Architecture](#-deployment--offline-resilience-architecture)
16. [Scientific Citations & References](#-scientific-citations--references)
17. [License & Attribution](#-license--attribution)

---

## 🎯 The Challenge & Problem Statement

> **The Hackathon Problem Statement:**  
> *"Farmers around the world navigate shifting temperatures, changing rainfall patterns, water shortages, extreme weather, and declining soil health. These pressures make it difficult to choose crop rotations that protect fields, conserve water, and support long‑term resilience. Your challenge is to create a decision‑support tool that uses NASA Earth observations along with local soil information, crop characteristics, and farmer priorities to help farmers explore rotation strategies that could strengthen soil health and adapt their farms to changing conditions."*

### The Real-World Breakdown

Modern agriculture operates under an unprecedented convergence of environmental stresses:

| Environmental Stress | Ground Reality & Vulnerability | What Makes Traditional Planning Fail |
|---|---|---|
| **Shifting Temperatures** | Warming winters cause rapid heat accumulation, triggering premature flowering and catastrophic **terminal heat shock** during reproductive grain-filling. | Farmers rely on calendar dates rather than thermal time (Growing Degree Days, GDD) and historical temperature extremes. |
| **Changing Rainfall Patterns** | Erratic monsoons feature intense downpours followed by prolonged mid-season dry spells, disrupting transplanting and rainfed vegetative growth. | Static crop recommendations assume historical rainfall averages and ignore dry-spell frequency or intensity. |
| **Water Shortages & Aquifer Depletion** | Flood-irrigated monocultures extract groundwater far faster than recharge rates, causing regional water tables to collapse by meters per year. | Irrigation advice rarely accounts for regional aquifer depletion signals or pumping energy expenditure. |
| **Extreme Weather & Stubble Burning** | Narrow turnaround windows between harvest and the next sowing force farmers to burn crop residues, destroying soil organic matter and causing severe air pollution. | Extension systems prescribe crop changes without evaluating whether the field operation calendar actually leaves time for zero-till mulch seeding. |
| **Declining Soil Health** | Intensive tillage, residue burning, and unbalanced synthetic nitrogen application exhaust soil organic carbon (SOC), collapse soil structure, and increase erosion. | Soil testing is sporadic, and farmers lack tools to predict the multi-year trajectory of their soil organic carbon under different management practices. |

---

## 💡 How TerraLoop Solves the Challenge

**TerraLoop** is an open-science, biophysically grounded decision-support system designed to turn satellite Earth observations and agronomic process models into actionable, farmer-friendly crop rotation plans.

```
       NASA Earth Observations             Local Soil & Farm Context         Farmer Priorities & Constraints
  ┌─────────────────────────────────┐   ┌───────────────────────────────┐   ┌───────────────────────────────┐
  │ • NASA POWER (Agroclimate)      │   │ • ISRIC SoilGrids 2.0 (250m)  │   │ • Profit vs Water vs Soil     │
  │ • NASA GPM IMERG (Precipitation)│   │ • Govt Soil Health Card (SHC) │   │ • Downside Risk (CVaR-10)     │
  │ • NASA SMAP L4 (Soil Moisture)  │   │ • 23-Crop Agronomic KB (PAU)  │   │ • Low Labour & Food Security  │
  │ • NASA GRACE/GRACE-FO (TWS Rate)│   │ • Topographic Slope (NASADEM) │   │ • Must-grow / Exclude crops   │
  │ • NASA FIRMS (Residue Burning)  │   │ • Inferred HLS Crop History   │   │ • Irrigation Cap & /Acre Unit │
  │ • NASA HLS 30m (NDVI Phenology) │   │ • CACP MSP & Mandi Price Risk │   │ • 1 to 6-Year Rotation Length │
  │ • NASA NEX-GDDP-CMIP6 (Climate) │   │ • State A2+FL Cost of Prod.   │   │ • Livestock / Fodder Access   │
  └────────────────┬────────────────┘   └───────────────┬───────────────┘   └───────────────┬───────────────┘
                   │                                    │                                   │
                   └────────────────────────────────────┼───────────────────────────────────┘
                                                        ▼
                                       ┌─────────────────────────────────┐
                                       │     TERRALOOP ENGINE CORE       │
                                       │ • FAO-56 Daily Root-Zone Balance│
                                       │ • March Wheat Terminal Heat Mod │
                                       │ • RothC-26.3 5-Pool Carbon Mod  │
                                       │ • Symbiotic N & Legume Credits  │
                                       │ • USDA-NRCS 5-Principle Index   │
                                       │ • RUSLE Topographic Soil Loss   │
                                       │ • NSGA-II Pareto Optimization   │
                                       └────────────────┬────────────────┘
                                                        ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   GROUNDED MULTILINGUAL RECOMMENDATIONS                                 │
 │  1. Baseline Rotation vs Top 3 Pareto Strategies (Side-by-Side Comparison)                              │
 │  2. Actionable Farmer Units: 45-kg Urea Bags Saved, Borewell Pumping Hours, Turnaround Days             │
 │  3. Matching Government Schemes: Mera Pani Meri Virasat (₹17,500/ha), CRM Happy Seeder, NFSM Pulses    │
 │  4. Trilingual Field Advisory: English, ਪੰਜਾਬੀ (Gurmukhi), and हिन्दी with Strict Data Provenance       │
 │  5. Interactive What-If Stress Testing Lab: CMIP6 Climate Scenarios, Drought, Price & Fertilizer Shocks │
 └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Direct Alignment with Hackathon Requirements

| Hackathon Requirement | How TerraLoop Solves It | Implementation & Code Reference |
|---|---|---|
| **Use NASA Earth Observations** | Synthesizes **8 NASA Earth Observation products** covering climate, precipitation, soil moisture, groundwater depletion, fire hotspots, 30 m phenology, and future climate projections. Every metric carries verifiable metadata (`DOI`, product ID, temporal range, and observation mode). | `packages/engine/terraloop_engine/data/`, `docs/DATASETS.md` |
| **Local Soil Information** | Combines ISRIC SoilGrids 2.0 depth-weighted topsoil physical properties (sand, silt, clay, bulk density, CEC, pH, SOC, N) with a manual **Government of India Soil Health Card (SHC)** lab test override interface (`pH`, `Organic Carbon %`, `Available N/P/K`). | `terraloop_engine/profiler.py`, `terraloop_engine/models/soil.py`, `terraloop_schemas/models.py` |
| **Crop Characteristics** | Curates a 23-crop Indian knowledge base parameterized against Punjab Agricultural University (PAU) and ICAR trials: thermal limits, GDD, water demand, FAO-56 dual crop coefficients ($K_{c,\text{ini}}, K_{c,\text{mid}}, K_{c,\text{end}}$), root depth, biological N fixation, and residue production. | `packages/crop-kb/crops/*.yaml`, `terraloop_engine/crop_kb.py` |
| **Farmer Priorities** | Solves a 6-dimensional multi-objective optimization problem: **Profit ($P_{50}$)**, **Water Savings ($-\text{irrigation}$)**, **Soil Health (0–100 score)**, **Downside Climate Risk ($CVaR_{10}$)**, **Low Labour**, and **Food Security**. Allows customized weights and hard constraints. | `terraloop_engine/optimize/selection.py`, `terraloop_engine/optimize/rotations.py` |
| **Explore Rotation Strategies** | Evaluates hundreds of multi-season rotation candidates against a 30-year historical weather ensemble or NEX-GDDP-CMIP6 future projections, presenting the baseline practice alongside the top 3 Pareto-optimal, structurally diverse strategies. | `terraloop_engine/optimize/evaluate.py`, `terraloop_engine/optimize/rotations.py` |
| **Strengthen Soil Health** | Integrates the 5-pool RothC-26.3 carbon turnover model and an N mass-balance accounting for legume fixation to compute decadal SOC accretion ($\Delta$ t C/ha/10yr), synthetic fertilizer reductions (45-kg Urea bags saved), and a transparent 0–100 USDA-NRCS Soil Health Index. | `terraloop_engine/models/soil_health.py` |
| **Adapt to Changing Conditions** | Dedicated **What-If Stress Testing Lab** allows farmers and extension workers to simulate future climate pathways (NEX-GDDP-CMIP6 SSP2-4.5 & SSP5-8.5 in 2030s & 2050s), severe drought shocks, urea price spikes, and mandi crop price crashes. | `terraloop_engine/climate/ensembles.py`, `apps/web/src/app/lab/page.tsx` |

---

## 🌾 Lead Demo Story: Punjab's Rice–Wheat Crisis

The lead demonstration is set in **Sangrur and Ludhiana districts in the Trans-Gangetic Plains of Punjab, India**—the ground zero of India's Green Revolution and its current ecological crisis:

```
               CONVENTIONAL BASELINE                                     TERRALOOP STRATEGY 1
         Puddled Paddy (Pusa-44) ➔ Wheat                    DSR Rice (PR-126) ➔ Zero-Till Wheat ➔ Moong
 ┌──────────────────────────────────────────────┐   ┌──────────────────────────────────────────────┐
 │ • Groundwater: -3.85 cm/yr (NASA GRACE)      │   │ • Net Irrigation: -14.1% (-170 mm/yr)        │
 │ • Net Irrigation: 1,207 mm/yr                │   │ • Borewell Pumping: 94 hours/ha saved        │
 │ • Turnaround: 11 Days (Forces Stubble Burn)  │   │ • Turnaround: 26 Days (Zero Burning Needed)  │
 │ • 10-Yr Soil Carbon: -1.86 t C/ha (Declining)│   │ • 10-Yr Soil Carbon: +2.79 t C/ha Accretion  │
 │ • Synthetic Fertilizer: High Urea Demand     │   │ • Fertilizer: 3.5 Urea Bags/ha Saved         │
 │ • Soil Health Score: 28.1 / 100              │   │ • Soil Health Score: 89.9 / 100              │
 │ • Subsidies: Zero Diversification Support    │   │ • Govt Schemes: Mera Pani Meri Virasat Matched│
 └──────────────────────────────────────────────┘   └──────────────────────────────────────────────┘
```

1. **Aquifer Collapse Visible from Space:**
   NASA GRACE and GRACE-FO satellite gravimetry records reveal Northwest India's regional Terrestrial Water Storage (TWS) dropping at **$-3.85\text{ cm/year}$**. Conventional puddled transplanted rice (PTR) requires ~175 mm of pre-sowing soaking plus continuous standing water, driving ~3.5 mm/day of deep percolation down past the root zone.
2. **The 11-Day Harvest Fire Trap:**
   Long-duration paddy varieties like `Pusa-44` (155 days) mature in late October, leaving as few as **11 days** before the optimal sowing window for winter wheat (November 15). Lacking time for mechanical straw management, farmers burn crop residues—a practice detected by **NASA FIRMS active fire sensors**—causing toxic smog across northern India and burning critical organic carbon.
3. **March Terminal Heat Shock:**
   During grain-filling (March 1 to April 15), maximum temperatures increasingly exceed $32^\circ\text{C}$, deactivating starch synthase enzymes and depressing wheat yields by 15–20%.
4. **TerraLoop's Engineered Transition:**
   - **Strategy 1 (DSR Rice ➔ Happy Seeder Wheat ➔ Summer Moong):** Replaces puddling with Direct-Seeded Rice and Alternate Wetting & Drying (AWD), saving 170 mm of irrigation and **94 borewell pumping hours/ha**. Harvest matures 15–20 days earlier, expanding the Kharif-to-Rabi turnaround to **26 days**. This allows wheat to be direct-drilled into standing paddy residue with a **Happy Seeder**, insulating the soil, buffering March heatwaves by $1.0^\circ\text{C}$, building $+2.79\text{ t C/ha}$ of SOC, saving **3.5 bags of Urea/ha**, and capturing ₹17,500/ha state diversification subsidies.
   - **Strategy 3 (Kharif Maize ➔ Happy Seeder Wheat ➔ Summer Moong):** Eliminates paddy entirely, slashing annual irrigation by **59.3% (saving 717 mm/yr and 394 borewell pumping hours/ha)**, expanding turnaround to **34 days**, and achieving a Soil Health Score of **88.3/100**.

---

## 🛰️ NASA Earth Observations Registry

Every metric, chart, and recommendation in TerraLoop links back to peer-reviewed NASA Earth science data with full provenance metadata (`DataProvenance` Pydantic models):

| Dataset | Product ID / Collection | Spatial / Temporal Resolution | Engine Integration & Purpose | DOI / Reference |
|---|---|---|---|---|
| **NASA POWER** | Agroclimatology (`AG` Point API) | $0.5^\circ \times 0.625^\circ$, Daily (1981–2024) | Daily $T_{\max}, T_{\min}$, surface solar radiation, relative humidity, wind speed $\rightarrow$ Hargreaves-Samani $ET_0$, GDD, daily simulation weather for FAO-56. | [power.larc.nasa.gov](https://power.larc.nasa.gov/) |
| **NASA GPM IMERG** | `NASA/GPM_L3/IMERG_V07` | $0.1^\circ$, Daily (2000–2024) | High-accuracy precipitation totals, extreme rain days ($>50\text{ mm}$), monsoon dry-spell frequency, and RUSLE rainfall erosivity $R$-factor. Safeguards against reanalysis trends. | [10.5067/GPM/IMERG/3B-HH/07](https://doi.org/10.5067/GPM/IMERG/3B-HH/07) |
| **NASA SMAP** | `NASA/SMAP/SPL4SMGP/007` | 9 km, 3-hourly (2015–2024) | Root-zone soil moisture percentiles ($0\text{--}100\text{ cm}$) compared against a 10-year climatological baseline across all 12 calendar months to detect agricultural drought. | [10.5067/K2VT90DE20GV](https://doi.org/10.5067/K2VT90DE20GV) |
| **NASA GRACE / GRACE-FO** | `NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI` | $\sim 0.5^\circ$ grid (native $\sim 3^\circ$), Monthly (2002–2024) | Regional Terrestrial Water Storage (TWS) mascon trend rate ($\text{cm/year}$) used to diagnose regional aquifer depletion. | [10.5067/TEMSC-3MJ62](https://doi.org/10.5067/TEMSC-3MJ62) |
| **NASA NASADEM** | `NASA/NASADEM_HGT/001` | 30 m Digital Elevation Model | Topographic elevation and field slope gradient (%) $\rightarrow$ Wischmeier-Smith $LS$ topographic factor for RUSLE soil erosion screening. | [10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001](https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001) |
| **NASA FIRMS** | `FIRMS` (MODIS / VIIRS) | 375 m / 1 km Active Fire Hotspots | Field-level detection of October–November crop residue burning events to penalize soil health and compute turnaround risk. | [10.5067/FIRMS/MODIS](https://doi.org/10.5067/FIRMS/MODIS) |
| **NASA HLS** | `NASA/HLS/HLSL30/v002` & `HLSS30/v002` | 30 m, 2–3 Day Revisit | Harmonized Landsat-Sentinel cloud-masked surface reflectance $\rightarrow$ 5-day Savitzky-Golay smoothed NDVI time series $\rightarrow$ automated 5-year crop history and season peak detection. | [10.5067/HLS/HLSL30.002](https://doi.org/10.5067/HLS/HLSL30.002) |
| **NASA NEX-GDDP-CMIP6** | `NASA/GDDP-CMIP6` | $0.25^\circ$, Daily (to 2060) | Bias-corrected downscaled climate projections across 5 Global Climate Models (ACCESS-CM2, MIROC6, MPI-ESM1-2-HR, NorESM2-MM, EC-Earth3) for SSP2-4.5 and SSP5-8.5. | [10.7917/OASIS/NEX-GDDP-CMIP6](https://doi.org/10.7917/OASIS/NEX-GDDP-CMIP6) |

### Non-NASA Complementary Datasets

- **ISRIC SoilGrids 2.0 (250 m):** Global depth-weighted ($0\text{--}30\text{ cm}$) physical soil properties: sand, silt, clay, bulk density, pH, cation exchange capacity (CEC), nitrogen, and soil organic carbon (SOC). [DOI: 10.5194/soil-7-217-2021](https://doi.org/10.5194/soil-7-217-2021).
- **Government of India Soil Health Card (SHC):** Physical laboratory test parameters entered by the farmer (`pH`, `Organic Carbon %`, `Available N/P/K in kg/ha`) overriding satellite-modeled soil attributes.
- **DES & ICRISAT District-Level Database (DLD):** Official 5-year district mean yield statistics from the Directorate of Economics & Statistics (Ministry of Agriculture & Farmers Welfare) used to validate model yields. [http://data.icrisat.org/dld/](http://data.icrisat.org/dld/).
- **CACP MSP & Cost of Cultivation (2024–25):** Comprehensive Scheme for Studying the Cost of Cultivation of Principal Crops ($A_2 + FL$ operational costs and Minimum Support Prices).

---

## 🏗️ System Architecture & Data Flow

TerraLoop is architected as a modular, pure-science engine decoupled from web transport, fronted by a FastAPI service and a modern Next.js 16 Progressive Web App:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               NEXT.JS 16 PROGRESSIVE WEB APP                           │
│  • MapLibre GL Interactive Satellite Basemap & Pin Placement                          │
│  • Field Report Card & 3D Interactive Soil Column (SoilColumn3D.tsx)                  │
│  • Farmer Priority Sliders (Profit, Water, Soil, Risk, Labour, Food Security)         │
│  • Unit Conversion Toggle: Per Hectare (/ha) ⇄ Per Acre / Killa (/acre)               │
│  • Strategy Recommendation Cards, Pareto Scatter Plot, & Seasonal Operation Gantt     │
│  • What-If Climate & Economic Stress Lab (/lab) & Crop KB Explorer (/crops)          │
│  • Printable KVK Agronomic Extension Advisory Brief (/brief)                          │
│  • Localized in English, ਪੰਜਾਬੀ (Gurmukhi), and हिन्दी (Devanagari)                   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ HTTP / JSON (or Zero-Crash Static Fallback)
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                    FASTAPI BACKEND                                     │
│  • /geocode          : Nominatim reverse-geocoding, coordinates & Google Maps URLs     │
│  • /profile          : Synthesizes NASA Earth observations + SoilGrids + SHC override │
│  • /suitability      : Prunes 23 Indian crops by thermal and moisture windows          │
│  • /recommend        : Simulates rotations across 30-yr weather ensemble & CMIP6       │
│  • /golden/*         : Offline demo endpoints serving 6 precomputed Indian fields      │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              TERRALOOP BIOPHYSICAL ENGINE                              │
│                                                                                        │
│   ┌───────────────────────────┐                    ┌──────────────────────────────┐    │
│   │   DATA INGESTION LAYER    │                    │     AGRONOMIC KNOWLEDGE      │    │
│   │ • nasa_power.py           │                    │ • crop_kb.py (23 Crops YAML) │    │
│   │ • soilgrids.py            │                    │ • CACP MSP & A2+FL Economics │    │
│   │ • gee.py (IMERG/SMAP/GRACE│                    │ • Predecessor compatibility  │    │
│   │ • eo/phenology.py (HLS)   │                    │ • Sowing DOY & thermal limits│    │
│   └─────────────┬─────────────┘                    └──────────────┬───────────────┘    │
│                 │                                                 │                    │
│                 ▼                                                 ▼                    │
│   ┌───────────────────────────────────────────────────────────────────────────────┐    │
│   │                         ROTATION GENERATION & SCREENING                       │    │
│   │ • rotations.py: Indian seasonal slots (Kharif, Rabi, Zaid) & agronomic rules  │    │
│   │ • surrogate.py: Polynomial Ridge surrogate pre-screening (<1 ms per candidate)│    │
│   └───────────────────────────────────────┬───────────────────────────────────────┘    │
│                                           │                                            │
│                                           ▼                                            │
│   ┌───────────────────────────────────────────────────────────────────────────────┐    │
│   │                          PROCESS-BASED SIMULATION MODELS                      │    │
│   │ • fao56_runner.py: Daily root-zone soil-water balance (TAW, RAW, Ks, Kc)      │    │
│   │ • fao56_runner.py: Rice hydrology (PTR puddling head vs DSR unsaturated AWD)  │    │
│   │ • fao56_runner.py: March terminal heat stress (>32°C) & Happy Seeder cooling  │    │
│   │ • soil_health.py : RothC-26.3 5-pool carbon turnover & SOC accretion          │    │
│   │ • soil_health.py : Symbiotic N balance & 25 kg N/ha legume fertilizer credit  │    │
│   │ • soil_health.py : USDA-NRCS 5-principle soil health scoring index (0–100)    │    │
│   │ • rusle.py       : Universal Soil Loss Equation screening (A = R·K·LS·C·P)    │    │
│   │ • economics.py   : P10/P50/P90 profits, CVaR-10 downside risk, mandi risk     │    │
│   └───────────────────────────────────────┬───────────────────────────────────────┘    │
│                                           │                                            │
│                                           ▼                                            │
│   ┌───────────────────────────────────────────────────────────────────────────────┐    │
│   │                          MULTI-OBJECTIVE OPTIMIZATION                         │    │
│   │ • selection.py: NSGA-II non-dominated sorting & Pareto front identification   │    │
│   │ • selection.py: Priority-weighted scoring & structural diversity filtering    │    │
│   │ • why_cards.py: Deterministic why-cards with strictly cited NASA provenances  │    │
│   └───────────────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔬 Scientific Methodology & Process Models

All engine calculations are governed by pure, deterministic biophysical equations with units documented in docstrings.

### 1. FAO-56 / FAO-33 Daily Soil-Water Balance & Rice Hydrology (`models/fao56_runner.py`)

Daily root-zone soil moisture is modeled using the dual crop coefficient approach from FAO Irrigation and Drainage Paper No. 56:

$$\text{ET}_c = K_c(t) \times \text{ET}_0$$

$$\text{ET}_a = K_s(t) \times K_c(t) \times \text{ET}_0$$

Where $K_c(t)$ is constructed from crop-specific parameters ($K_{c,\text{ini}}, K_{c,\text{mid}}, K_{c,\text{end}}$). Soil moisture limits are parameterized from Saxton-Rawls hydraulic pedotransfer functions:

$$\text{TAW} = 1000 \times (\theta_{\text{FC}} - \theta_{\text{WP}}) \times Z_r$$

$$\text{RAW} = p \times \text{TAW}$$

When root-zone moisture depletion $D_{r,t} > \text{RAW}$, actual evapotranspiration is throttled by the water stress coefficient $K_s$:

$$K_s(t) = \frac{\text{TAW} - D_{r,t}}{\text{TAW} - \text{RAW}} = \frac{\text{TAW} - D_{r,t}}{(1 - p)\cdot\text{TAW}}$$

Yield response to seasonal water deficit follows FAO Paper No. 33 (Doorenbos & Kassam, 1979):

$$\left(1 - \frac{Y}{Y_{\max}}\right) = K_y \left(1 - \frac{\sum \text{ET}_a}{\sum \text{ET}_c}\right)$$

#### Rice Establishment Hydrology: Puddled Transplanted Rice vs. DSR + AWD
Parameterised to match experimental field trials from Punjab Agricultural University (Bouman & Tuong 2001; Sudhir-Yadav et al. 2011):
- **Puddled Transplanted Rice (PTR, `rice_puddled`):** Mechanical wet tillage destroys soil macro-pores and forms a dense plough pan. However, PTR maintains a continuous standing water head ($5\text{--}10\text{ cm}$). This continuous positive hydrostatic pressure drives a steady-state downward percolation rate of **$\sim 3.5\text{ mm/day}$ on alluvial loam**, in addition to an initial **$175\text{ mm}$ land-soaking puddling requirement**.
- **Direct-Seeded Rice with Alternate Wetting & Drying (DSR + AWD, `rice_dsr`):** Replaces puddling with an aerobic pre-sowing *rauni* irrigation ($75\text{ mm}$). Soil remains unsaturated between irrigations; matric suction develops, dropping unsaturated hydraulic conductivity by several orders of magnitude. Downward percolation occurs only during transient drainage pulses, averaging **$2.55\text{ mm/day}$**. This saves **24–28% irrigation water** while eliminating puddling tractor diesel costs ($\sim \text{₹}10,000/\text{ha}$).

---

### 2. March Wheat Reproductive Terminal Heat Stress (`models/fao56_runner.py`)

In the Indo-Gangetic Plains, Rabi wheat is vulnerable to sudden temperature spikes during the grain-filling phase (March 1 to April 15). Daily heat stress is evaluated during the final 35% of the crop cycle:

$$\Delta Y_{\text{heat}} = \sum_{t \in \text{grain-fill}} \max\left(0, T_{\max,t} - 32.0^\circ\text{C}\right) \times 0.018$$

- **Happy Seeder Surface Residue Mulch Effect:** Retaining standing rice residue on the soil surface reduces soil evaporation by **10%** ($K_c \times 0.90$) and provides a microclimatic cooling buffer of **$-1.0^\circ\text{C}$** to topsoil and crop canopy (Sidhu et al., 2007). Under a simulated $+4.5^\circ\text{C}$ heatwave (replicating the devastating March 2022 North India event), residue mulch reduces wheat yield loss from **-19.7% down to -12.6%**.

---

### 3. RothC-lite 26.3 Decadal Soil Organic Carbon Model (`models/soil_health.py`)

Based on the Rothamsted Carbon Model (Coleman & Jenkinson, 1996), running on a monthly time step over 10 years:

- **Five Carbon Pools:**
  1. Decomposable Plant Material (DPM, $k = 10.0\text{ yr}^{-1}$)
  2. Resistant Plant Material (RPM, $k = 0.30\text{ yr}^{-1}$)
  3. Microbial Biomass (BIO, $k = 0.66\text{ yr}^{-1}$)
  4. Humified Organic Matter (HUM, $k = 0.02\text{ yr}^{-1}$)
  5. Inert Organic Matter (IOM, $k = 0.0\text{ yr}^{-1}$)

Initial IOM is computed from total topsoil SOC stock $C_{\text{tot}}$ via Falloon et al. (1998):

$$\text{IOM} = 0.049 \times C_{\text{tot}}^{1.139} \quad (\text{t C/ha})$$

Monthly decomposition is governed by abiotic rate modifiers:

$$\xi = a(T) \times b(M) \times c_{\text{cov}}$$

$$a(T) = \frac{47.91}{1 + \exp\left(\frac{106.06}{T + 18.27}\right)}$$

$$b(M) = \max\left(0.2, \min\left(1.0, 1.0 - 0.8 \times \frac{\max(0, 0.75 \times \text{ET}_0 - P)}{100}\right)\right)$$

Where $c_{\text{cov}} = 0.6$ when living canopy or residue mulch covers the soil, and $1.0$ under bare fallow. Carbon partitioning into BIO and HUM is governed by topsoil clay content:

$$x = 1.67 \times \left(1.85 + 1.60 \times \exp(-0.0786 \times \text{clay})\right)$$

$$\text{Fraction released as }\text{CO}_2 = \frac{x}{x + 1}, \quad \text{Synthesized into BIO+HUM} = \frac{1}{x + 1}$$

- **Residue Management Penalty:** In-situ retention of crop residue contributes 45% carbon with a DPM/RPM ratio of 1.44. Open-field residue burning leaves only ~10% ash carbon, driving long-term SOC depletion ($-1.86\text{ t C/ha/10yr}$ under rice–wheat burning vs $+2.79\text{ t C/ha}$ under DSR–wheat–moong mulch retention).

---

### 4. Seasonal Nitrogen Mass Balance & Legume Credit (`models/soil_health.py`)

Tracks the seasonal input-removal mass balance of nitrogen (kg N/ha):

$$\text{Balance}_N = (N_{\text{fert}} + N_{\text{fix}} + N_{\text{dep}}) - N_{\text{removal}}$$

- **Biological Nitrogen Fixation ($N_{\text{fix}}$):** Grain and fodder legumes fix atmospheric nitrogen:
  - Summer Moong: $+50\text{ kg N/ha}$
  - Chickpea / Gram: $+60\text{ kg N/ha}$
  - Urad / Blackgram: $+45\text{ kg N/ha}$
  - Dhaincha (Sesbania Green Manure): $+80\text{ kg N/ha}$
- **Legume Fertilizer Credit:** A succeeding cereal (e.g. wheat after moong) receives a **$25\text{ kg N/ha}$ reduction in synthetic nitrogen requirement**, equivalent to saving **3.5 standard 45-kg bags of Urea per hectare (1.4 bags/acre)**.
- **Crop Removal ($N_{\text{removal}}$):** Calculated from crop grain yield and grain nitrogen concentration (1.8% for wheat, 1.3% for rough rice, 3.8% for pulses).

---

### 5. USDA-NRCS 5 Principles Soil Health Index (0–100) (`models/soil_health.py`)

A composite score mapping rotation outcomes directly onto the USDA Natural Resources Conservation Service (NRCS) Soil Health Principles:

$$\text{Total Score} = \text{Clamp}_{0}^{100}\Big(\sum_{i=1}^5 \text{Principle}_i + \text{SOC Mod} + \text{Erosion Mod} + \text{Burn Penalty}\Big)$$

| Principle / Component | Maximum Weight | Calculation Logic |
|---|---|---|
| **1. Minimize Soil Disturbance** | 15 pts | Tillage intensity: No-Till / Happy Seeder = 15 pts, Direct-Seeded Rice / Strip Till = 12 pts, Conventional Till = 8 pts, Puddling PTR = 5.5 pts, Residue Burning = 3.5 pts. |
| **2. Maximize Soil Armor / Cover** | 15 pts | Proportion of year soil is protected by living canopy or surface straw mulch ($15 \times \text{cover fraction}$). |
| **3. Continuous Living Roots** | 15 pts | Active crop growing days divided by $330\text{ days/year}$ ($15 \times \text{living root fraction}$). |
| **4. Maximize Biodiversity** | 15 pts | Botanical family diversity scored via Shannon index ($15 \times \min(1.0, H' / 0.95)$). |
| **5. Integrate Livestock / Legumes** | 15 pts | Livestock integration with fodder = 15 pts, Grain legume or green manure = 12.5 pts, Monoculture cereal = 4.5 pts. |
| **SOC Trajectory Modifier** | $-10 \text{ to } +15$ pts | Up to $+15$ pts for positive 10-year SOC accretion; down to $-10$ pts for SOC depletion. |
| **RUSLE Erosion Modifier** | $-8 \text{ to } +10$ pts | $+10$ pts if soil loss $\le 5\text{ t/ha/yr}$; down to $-8$ pts for severe erosion. |
| **Residue Burning Penalty** | $-5$ pts | Direct penalty if FIRMS or farmer practices indicate open-field burning. |

---

### 6. RUSLE Soil Erosion Screening (`models/rusle.py`)

Screens topographic soil loss hazard using the Revised Universal Soil Loss Equation:

$$A = R \times K \times LS \times C \times P \quad (\text{t/ha/year})$$

- **$R$ (Rainfall Erosivity):** Computed from annual precipitation (GPM IMERG) via Renard & Freimund (1994).
- **$K$ (Soil Erodibility):** Computed from topsoil sand, silt, clay, and organic matter via the Williams (1995) EPIC formulation.
- **$LS$ (Topographic Factor):** Computed from 30 m NASADEM elevation and field slope gradient (%) via Wischmeier & Smith (1978).
- **$C$ (Cover Management):** Dynamic cover factor derived from the rotation's seasonal canopy and residue cover.

---

### 7. Agro-Economics & Downside Risk ($CVaR_{10}$) (`models/economics.py`)

Financial returns are modeled from official Government of India Commission for Agricultural Costs & Prices (CACP 2024–25) data:

$$\text{Net Profit} = \sum_{\text{season}} \left(\text{Yield} \times \text{MSP} - \text{Cost}_{A_2+FL}\right)$$

- **Downside Risk (Conditional Value at Risk, $CVaR_{10}$):** The expected net profit in the worst 10% climate years across the 30-year historical weather ensemble.
- **Procurement Certainty Factor:** Weights profitability by market procurement infrastructure:
  - `msp_assured`: Assured government open-ended procurement (FCI wheat & paddy in Punjab: $1.0\times$).
  - `nafed_pss`: NAFED Price Support Scheme for pulses and oilseeds ($0.78\times$).
  - `mandi_linked`: Volatile open-market auctions ($0.52\times$).

---

## 🌾 23-Crop Agronomic Knowledge Base

TerraLoop maintains a curated knowledge base of 23 crops across 6 agricultural groups, detailed in `packages/crop-kb/crops/*.yaml`:

| Crop ID | Crop Name | Botanical Family | Crop Group | Season | Duration (days) | Water Need (mm) | Base/Opt/Max $T$ (°C) | Biological N Fixation |
|---|---|---|---|---|---|---|---|---|
| `wheat` | Wheat (Rabi) | Poaceae | Cereal | Cool | 135–155 | 300–450 | 4.0 / (15, 22) / 32.0 | 0 kg N/ha |
| `rice_puddled` | Puddled Paddy Rice | Poaceae | Cereal | Warm | 120–155 | 1200–1600 | 10.0 / (25, 33) / 40.0 | 0 kg N/ha |
| `rice_short` | Short Rice (PR-126) | Poaceae | Cereal | Warm | 100–110 | 950–1250 | 10.0 / (25, 33) / 40.0 | 0 kg N/ha |
| `rice_dsr` | Direct-Seeded Rice | Poaceae | Cereal | Warm | 110–145 | 900–1300 | 10.0 / (25, 32) / 40.0 | 0 kg N/ha |
| `basmati` | Basmati Rice | Poaceae | Cereal | Warm | 130–155 | 1100–1450 | 10.0 / (24, 32) / 38.0 | 0 kg N/ha |
| `maize` | Maize / Corn | Poaceae | Cereal | Warm | 90–120 | 450–650 | 8.0 / (20, 30) / 38.0 | 0 kg N/ha |
| `pearl_millet` | Bajra (Pearl Millet) | Poaceae | Cereal | Warm | 75–90 | 300–450 | 12.0 / (28, 35) / 45.0 | 0 kg N/ha |
| `sorghum` | Jowar (Sorghum) | Poaceae | Cereal | Warm | 95–115 | 350–500 | 10.0 / (26, 34) / 42.0 | 0 kg N/ha |
| `barley` | Barley (Jau) | Poaceae | Cereal | Cool | 110–130 | 250–380 | 4.0 / (15, 22) / 30.0 | 0 kg N/ha |
| `moong` | Summer Moong | Fabaceae | Legume | Warm | 60–75 | 250–350 | 12.0 / (25, 35) / 42.0 | **+50 kg N/ha** |
| `urad` | Blackgram (Urad) | Fabaceae | Legume | Warm | 70–85 | 300–400 | 12.0 / (25, 35) / 42.0 | **+45 kg N/ha** |
| `chickpea` | Gram / Chickpea | Fabaceae | Legume | Cool | 105–130 | 250–350 | 5.0 / (18, 26) / 35.0 | **+60 kg N/ha** |
| `pigeon_pea` | Arhar / Tur | Fabaceae | Legume | Warm | 140–180 | 500–700 | 10.0 / (22, 32) / 38.0 | **+70 kg N/ha** |
| `lentil` | Masoor (Lentil) | Fabaceae | Legume | Cool | 110–130 | 200–300 | 4.0 / (15, 24) / 30.0 | **+40 kg N/ha** |
| `soybean` | Soybean | Fabaceae | Legume | Warm | 95–115 | 450–650 | 10.0 / (22, 30) / 38.0 | **+80 kg N/ha** |
| `common_bean` | Rajma (Kidney Bean) | Fabaceae | Legume | Cool | 90–115 | 300–450 | 8.0 / (16, 24) / 32.0 | **+30 kg N/ha** |
| `mustard` | Sarson / Mustard | Brassicaceae | Oilseed | Cool | 110–135 | 250–380 | 5.0 / (15, 25) / 32.0 | 0 kg N/ha |
| `groundnut` | Peanut / Groundnut | Fabaceae | Oilseed | Warm | 105–125 | 450–600 | 10.0 / (24, 30) / 38.0 | **+60 kg N/ha** |
| `sunflower` | Sunflower | Asteraceae | Oilseed | Warm | 85–100 | 400–550 | 8.0 / (20, 28) / 36.0 | 0 kg N/ha |
| `cotton` | Cotton (Kapas) | Malvaceae | Fibre | Warm | 150–180 | 700–1000 | 14.0 / (25, 35) / 42.0 | 0 kg N/ha |
| `potato` | Potato (Aloo) | Solanaceae | Tuber | Cool | 85–110 | 400–550 | 7.0 / (16, 22) / 30.0 | 0 kg N/ha |
| `berseem` | Berseem Clover | Fabaceae | Fodder | Cool | 140–180 | 600–800 | 5.0 / (15, 24) / 32.0 | **+90 kg N/ha** |
| `dhaincha` | Sesbania Green Manure | Fabaceae | Cover | Warm | 45–60 | 200–300 | 12.0 / (25, 35) / 42.0 | **+80 kg N/ha** |

---

## 🗺️ Six Indian Agro-Climatic Golden Benchmark Fields

TerraLoop precomputes end-to-end profiles and recommendations across **6 representative agro-climatic zones of India**, stored in `data/golden/<id>/` and `apps/web/public/golden/<id>/` for 100% offline-passing demo reliability:

```
                                  MAP OF INDIAN BENCHMARK FIELDS
                                     
                                       [Bathinda]  [Ludhiana]
                                            \       /
                                           [Sangrur] (Punjab Alluvial Rice-Wheat)
                                               |
                                        [Bundelkhand] (Semi-Arid Hard-Rock Pulses)
                                               |
                                          [Vidarbha] (Deccan Black Vertisol Cotton-Tur)
                                               |
                                          [Thanjavur] (Cauvery Delta Rice-Urad Relay)
```

| ID | District & State | ICAR Agro-Climatic Zone | Baseline System | Top Recommended Rotation | Impact Highlights |
|---|---|---|---|---|---|
| `sangrur` | **Sangrur, Punjab** (Hero Field) | Trans-Gangetic Plains (Malwa Sweet-Water Belt) | Puddled Paddy ➔ Wheat | **DSR Rice ➔ Wheat ➔ Summer Moong** | **-14.1% Water**, +2.79 t C/ha SOC, 26-day turnaround (zero burning), 3.5 Urea bags saved. |
| `ludhiana` | **Ludhiana, Punjab** (PAU Site) | Central Alluvial Plains | Puddled Paddy ➔ Wheat | **DSR Rice ➔ Wheat ➔ Summer Moong** | **-15.2% Water**, ₹2,29,966/ha median profit, Soil Health 90/100. |
| `bathinda` | **Bathinda, Punjab** | South-Western Semi-Arid Cotton Belt | Cotton ➔ Wheat | **Moong ➔ Wheat ➔ Blackgram (Urad)** | **-35.7% Water**, overcomes brackish groundwater and cotton whitefly risk. |
| `vidarbha` | **Yavatmal, Maharashtra** | Central Deccan Plateau (Vertisol Clay Belt) | Rainfed Cotton ➔ Chickpea | **Maize ➔ Chickpea ➔ Fallow** | Vertisol moisture buffering, breaks pink bollworm pest cycle, resilient to dry spells. |
| `bundelkhand` | **Jhansi, Uttar Pradesh** | Central Plateau & Hills (Semi-Arid Drought Zone) | Sorghum ➔ Wheat | **Maize ➔ Chickpea ➔ Fallow** | Adapts to shallow red-black soils, reduces drought failure risk, high protein pulse yield. |
| `thanjavur` | **Thanjavur, Tamil Nadu** | Southern East Coast Plains & Cauvery Delta | Double Puddled Paddy ➔ Urad | **Short Rice (PR-126) ➔ DSR Rice ➔ Blackgram** | **-24.0% Water**, ₹2,65,904/ha profit, relay cropping into residual delta moisture. |

---

## 📊 Empirical Ground-Truth Validation & Sensitivity Benchmarks

All engine performance numbers are empirically validated and reproducible offline via `uv run python scripts/run_validation_benchmarks.py --write-docs`, as documented in `docs/BENCHMARKS.md`.

### 1. Model Calibration vs. DES / ICRISAT District Statistics

Simulated 30-year median yields were benchmarked against 5-year official district averages from the Directorate of Economics & Statistics (DES, Ministry of Agriculture):

| District & Crop | Observed District Mean | Simulated Median Yield | Error (t/ha) | Relative Error (%) | Validation Source |
|---|---|---|---|---|---|
| **Sangrur Rabi Wheat** | 5.08 t/ha | **5.25 t/ha** | +0.17 t/ha | **+3.2%** | DES Statistical Abstract of Punjab Table 5.6 |
| **Sangrur Kharif Paddy** | 7.35 t/ha | **7.01 t/ha** | -0.34 t/ha | **-4.6%** | DES Statistical Abstract of Punjab Table 5.6 |
| **Ludhiana Rabi Wheat** (Held-out) | 5.02 t/ha | **5.30 t/ha** | +0.29 t/ha | **+5.7%** | ICRISAT District-Level Database / DES |
| **Ludhiana Kharif Paddy** (Held-out) | 7.20 t/ha | **7.00 t/ha** | -0.20 t/ha | **-2.7%** | ICRISAT District-Level Database / DES |
| **Bathinda Rabi Wheat** (Held-out) | 4.82 t/ha | **5.21 t/ha** | +0.39 t/ha | **+8.2%** | DES Statistical Abstract of Punjab Table 5.6 |

> [!NOTE]
> Held-out peninsular rainfed sites (e.g. Yavatmal cotton) exhibit higher deviations (+20% to +42%) because the FAO-56 / FAO-33 engine simulates abiotic water and temperature constraints, transparently omitting biotic pest damage (e.g. pink bollworm) and unfertilized subsistence management.

### 2. Soil Texture & Water Holding Capacity Sensitivity

| Soil Texture Class | Sand / Clay (%) | Field Cap / Wilt Point | Rainfed Wheat Yield | Irrigated Wheat Yield | Irrigated Wheat Water | DSR Rice Water |
|---|---|---|---|---|---|---|
| **Coarse Loamy Sand** (SW Punjab / Rajasthan) | 76% / 10% | 0.129 / 0.062 | **1.47 t/ha** | 5.23 t/ha | **402 mm** | **1226 mm** |
| **Alluvial Loam** (Sangrur / Ludhiana) | 44% / 20% | 0.254 / 0.127 | **2.40 t/ha** | 5.23 t/ha | **325 mm** | **758 mm** |
| **Deccan Black Vertisol** (Vidarbha Clay) | 22% / 50% | 0.424 / 0.296 | **2.42 t/ha** | 5.23 t/ha | **325 mm** | **662 mm** |

---

## 🖥️ Web Application & Farmer Experience

The Next.js 16 frontend is crafted for intuitive, low-friction farmer engagement across 7 purpose-built views:

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │ [🗺️ Explore Fields]  [🌱 Crop KB]  [🧪 What-If Lab]  [📄 KVK Brief]    │
  ├────────────────────────────────────────────────────────────────────────┤
  │                                                                        │
  │  📍 Sangrur, Punjab (30.19°N, 75.78°E)       [Unit: /Acre (Killa) ▾]  │
  │  NASA GRACE Groundwater Trend: -3.85 cm/yr ⚠️ (Over-Exploited)         │
  │                                                                        │
  │  ┌──────────────────────┐  ┌────────────────────────────────────────┐  │
  │  │ FIELD REPORT CARD    │  │ 3D SOIL COLUMN                         │  │
  │  │ • Clay Loam (44/36/20│  │ ┌────────────────────────────────────┐ │  │
  │  │ • SOC: 5.4 g/kg      │  │ │ 0-15cm: Root Zone / Mulch (A-Horiz)│ │  │
  │  │ • pH: 7.9 (Normal)   │  │ │ 15-30cm: Subsoil / TAW (B-Horiz)   │ │  │
  │  │ • Rain: 612 mm/yr    │  │ └────────────────────────────────────┘ │  │
  │  └──────────────────────┘  └────────────────────────────────────────┘  │
  │                                                                        │
  │  FARMER PRIORITIES: [ Profit: 90% ] [ Water: 85% ] [ Soil Health: 95% ]│
  │                                                                        │
  │  STRATEGY RECOMMENDATIONS (Side-by-Side):                              │
  │  ┌─────────────────────────┐  ┌──────────────────────────────────────┐ │
  │  │ Strategy 1 (Top Pick)   │  │ Strategy 3 (Maximum Water Savings)   │ │
  │  │ DSR Rice ➔ Wheat ➔ Moong│  │ Kharif Maize ➔ Wheat ➔ Moong         │ │
  │  │ 💧 -14.1% Irrigation    │  │ 💧 -59.3% Irrigation (-717 mm)       │ │
  │  │ ⏱️ 26-Day Turnaround    │  │ ⏱️ 34-Day Turnaround (Zero Burn)     │ │
  │  │ 🧪 3.5 Urea Bags Saved  │  │ ⚡ 394 Borewell Pump Hours Saved      │ │
  │  │ 🏛️ Mera Pani Subsidy    │  │ 🏛️ CRM Happy Seeder Subsidy Matched  │ │
  │  └─────────────────────────┘  └──────────────────────────────────────┘ │
  └────────────────────────────────────────────────────────────────────────┘
```

### Key Frontend Features

1. **Interactive Field Map & Geocoder (`FieldMap.tsx`):**
   - Built on MapLibre GL with responsive pins, GPS geolocation, and support for Indian village name search, coordinates, and pasted Google Maps / OpenStreetMap URLs.
2. **Field Report Card (`ReportCard.tsx`):**
   - Synthesizes NASA POWER climate anomalies, GPM IMERG rainfall, SMAP root-zone moisture percentiles, GRACE groundwater depletion trend, and inferred 5-year HLS crop history.
3. **3D Interactive Soil Column (`SoilColumn3D.tsx`):**
   - Renders a physical 3D visualization of soil texture horizons, bulk density, pH, rooting depth, and water-holding capacity (TAW/RAW).
4. **Soil Health Card (SHC) Lab Test Override:**
   - Farmers can input their physical laboratory values from their Government Soil Health Card (`pH`, `Organic Carbon %`, `Available N/P/K`) to override satellite pedotransfer estimates.
5. **Instant `/Acre (Killa)` Unit Conversion:**
   - One-click toggle transforms all financial margins, 45-kg Urea bags, and borewell pumping hours between metric hectares and traditional Indian agricultural acres ($1\text{ ha} = 2.47105\text{ acres / killas}$).
6. **Strategy Cards with Operational Gantt Timelines (`RotationExplorer.tsx`):**
   - Visualizes sowing-to-harvest windows, Kharif-to-Rabi turnaround days, borewell pumping hours saved, Urea bags saved, and matching government schemes.
7. **Interactive Pareto Scatter Plot:**
   - Multi-objective trade-off explorer plotting Profit vs. Water Savings vs. Soil Health score.
8. **What-If Stress Testing Lab (`/lab`):**
   - Interactive sliders to test rotation resilience against NEX-GDDP-CMIP6 climate scenarios (SSP2-4.5 / SSP5-8.5 in 2030s/2050s), percentage drought shocks, fertilizer cost spikes, and market price crashes.
9. **KVK Agronomic Extension Brief (`/brief`):**
   - Printable, field-ready extension advisory formatted for Krishi Vigyan Kendra (KVK) officers and farmers, with full provenance appendices.

---

## 🌐 Multilingual Grassroots Accessibility (i18n)

To empower grassroots Indian smallholders, TerraLoop features complete, native trilingual support across the entire user interface and engine-generated narratives:

- **English (`en`)**
- **ਪੰਜਾਬੀ (Punjabi in Gurmukhi script, `pa`)** — Essential for Punjab and Haryana farmers.
- **हिन्दी (Hindi in Devanagari script, `hi`)** — Reaching Central, Northern, and Western India.

```json
// Example from apps/web/src/i18n/pa.json
{
  "app": {
    "title": "ਟੈਰਾ-ਲੂਪ ⟳",
    "subtitle": "ਨਾਸਾ ਧਰਤੀ ਨਿਰੀਖਣਾਂ ਦੁਆਰਾ ਸੰਚਾਲਿਤ ਲਚਕੀਲਾ ਫ਼ਸਲੀ ਚੱਕਰ ਪ੍ਰਣਾਲੀ"
  },
  "metrics": {
    "water_savings": "ਪਾਣੀ ਦੀ ਬੱਚਤ",
    "urea_saved": "ਯੂਰੀਆ ਦੇ ਗੱਟੇ ਬਚੇ",
    "turnaround_days": "ਵਾਢੀ ਤੋਂ ਬਿਜਾਈ ਦਾ ਸਮਾਂ"
  }
}
```

Every UI label, tooltip, and engine narrative summary adapts dynamically with zero hardcoded English text.

---

## 📁 Repository Structure

```
terraloop/
├── apps/
│   ├── api/                              # FastAPI backend service
│   │   ├── terraloop_api/
│   │   │   ├── __init__.py
│   │   │   └── main.py                   # REST endpoints (/profile, /recommend, /golden, /geocode)
│   │   └── pyproject.toml
│   └── web/                              # Next.js 16 (App Router) frontend
│       ├── public/
│       │   └── golden/                   # Precomputed offline assets for 6 benchmark fields
│       ├── src/
│       │   ├── app/                      # Next.js routes (/, /rotations, /lab, /crops, /brief, etc.)
│       │   ├── components/               # React UI components (ReportCard, FieldMap, SoilColumn3D)
│       │   ├── context/                  # FieldContext state provider
│       │   ├── i18n/                     # Translations (en.json, hi.json, pa.json)
│       │   └── types/                    # TypeScript interfaces
│       ├── package.json
│       └── tsconfig.json
├── packages/
│   ├── schemas/                          # Shared Pydantic v2 data contracts
│   │   ├── terraloop_schemas/
│   │   │   ├── __init__.py
│   │   │   └── models.py                 # FieldProfile, StrategyRecommendation, CropSpec, etc.
│   │   └── pyproject.toml
│   ├── engine/                           # Pure biophysical and agronomic science engine
│   │   ├── terraloop_engine/
│   │   │   ├── cache.py                  # Disk caching decorator (@disk_cache)
│   │   │   ├── crop_kb.py                # Crop YAML loader & validator
│   │   │   ├── profiler.py               # FieldProfile builder synthesizing NASA data
│   │   │   ├── suitability.py            # Heuristic suitability pre-filter
│   │   │   ├── climate/
│   │   │   │   └── ensembles.py          # Historical moving blocks & NEX-GDDP-CMIP6 scenarios
│   │   │   ├── data/
│   │   │   │   ├── gee.py                # Google Earth Engine client (8 NASA collections)
│   │   │   │   ├── nasa_power.py         # NASA POWER daily REST API client & synthetic generator
│   │   │   │   └── soilgrids.py          # ISRIC SoilGrids 2.0 REST client
│   │   │   ├── eo/
│   │   │   │   ├── classifier.py         # Pure-NumPy Gaussian ML crop classifier
│   │   │   │   └── phenology.py          # Savitzky-Golay NDVI smoothing & peak detection
│   │   │   ├── explain/
│   │   │   │   └── why_cards.py          # Deterministic why-cards & grounded LLM narrative
│   │   │   ├── models/
│   │   │   │   ├── agroclimate.py        # Hargreaves ET0, GDD, dry spells, heat days
│   │   │   │   ├── economics.py          # CACP MSP, state A2+FL costs, CVaR-10 downside risk
│   │   │   │   ├── fao56_runner.py       # FAO-56 dual Kc water balance & March heat model
│   │   │   │   ├── rusle.py              # Revised Universal Soil Loss Equation (A = R·K·LS·C·P)
│   │   │   │   ├── soil.py               # Saxton-Rawls hydrology & USDA texture triangle
│   │   │   │   ├── soil_health.py        # RothC-26.3 carbon model, N balance, NRCS 0-100 score
│   │   │   │   └── surrogate.py          # Polynomial Ridge surrogate for fast screening
│   │   │   └── optimize/
│   │   │       ├── evaluate.py           # Multi-member ensemble rotation evaluator
│   │   │       ├── rotations.py          # Agronomic candidate generator (Kharif, Rabi, Zaid)
│   │   │       └── selection.py          # NSGA-II Pareto sorting & priority selection
│   │   └── pyproject.toml
│   └── crop-kb/                          # Agronomic parameters & state economics
│       ├── crops/                        # 23 Indian crop YAML specifications
│       └── economics/
│           └── punjab.yaml               # CACP 2024-25 MSP & state cost of cultivation
├── data/
│   ├── golden/                           # Precomputed offline JSONs for benchmark fields
│   ├── benchmarks/                       # District ground truth yield validation CSVs
│   └── cache/                            # Disk-cached API responses (git-ignored)
├── docs/                                 # Full technical and submission documentation
│   ├── BENCHMARKS.md                     # Reproducible ground-truth validation report
│   ├── BUILD_PLAN.md                     # Product vision & architectural specification
│   ├── DATASETS.md                       # NASA dataset registry, product IDs & DOIs
│   ├── METHODOLOGY.md                    # Scientific equations, citations & limitations
│   └── SUBMISSION.md                     # 30-sec pitch video storyboard & 7-slide deck
├── scripts/
│   ├── precompute_golden.py              # Precomputes golden fields from live GEE/POWER
│   └── run_validation_benchmarks.py      # Executes and verifies empirical benchmark suite
├── tests/                                # Pytest test suite (66 tests, 100% offline passing)
│   ├── test_deploy.py                    # Vercel service routing & filesystem tests
│   ├── test_engine.py                    # Engine integration, suitability & API tests
│   └── test_models.py                    # Biophysical unit tests (FAO-56, RothC, RUSLE, etc.)
├── pyproject.toml                        # uv workspace configuration
└── README.md                             # You are here
```

---

## 🔌 API Reference & OpenAPI Specification

When running the API backend (`uvicorn terraloop_api.main:app`), full interactive Swagger docs are available at `http://localhost:8000/docs`.

### Primary Endpoints

| Method | Endpoint | Description | Request Body / Query Params | Response Model |
|---|---|---|---|---|
| `GET` | `/health` | Service health status. | None | `{"status": "ok"}` |
| `GET` | `/crops` | Lists all 23 crops from the knowledge base. | None | `list[CropSpec]` |
| `GET` | `/golden` | Lists the 6 precomputed Indian golden benchmark fields. | None | `list[dict]` |
| `GET` | `/golden/{id}/profile` | Retrieves precomputed `FieldProfile` for golden field. | `id: str` | `FieldProfile` |
| `GET` | `/golden/{id}/recommendations` | Retrieves precomputed top 3 strategies for golden field. | `id: str` | `list[StrategyRecommendation]` |
| `GET` | `/geocode` | Resolves Indian village names, coordinates, or Google Maps URLs. | `q: str` | `GeocodeResult` |
| `POST` | `/profile` | Generates a live `FieldProfile` from coordinates. | `FieldGeometry` | `FieldProfile` |
| `POST` | `/suitability` | Prunes and ranks crops suitable for field climate/soil. | `SuitabilityRequest` | `list[SuitabilityItem]` |
| `POST` | `/recommend` | Full simulation pipeline: candidates $\rightarrow$ FAO-56 $\rightarrow$ RothC $\rightarrow$ Pareto selection $\rightarrow$ why-cards. | `RecommendRequest` | `list[StrategyRecommendation]` |

#### Example: Running `/recommend`
```bash
curl -X POST "http://localhost:8000/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "field": { "lat": 30.19, "lon": 75.78, "name": "Sangrur Field" },
    "priorities": { "profit": 1.0, "water_savings": 2.0, "soil_health": 2.0, "low_risk": 1.0 },
    "constraints": { "irrigation": "limited", "rotation_years": 1 },
    "language": "pa"
  }'
```

---

## ⚡ Quick Start & Developer Setup

### Prerequisites
- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (high-performance Python workspace manager)
- **Node.js 18+** & **npm**

### 1. Clone & Set Up Workspace
```powershell
# Clone the repository
git clone https://github.com/your-org/terraloop.git
cd terraloop

# Install Python workspace dependencies in editable mode
uv sync

# Install frontend dependencies
cd apps/web
npm install
cd ../..
```

### 2. Run Test Suite & Linters
```powershell
# Run the 56-test offline biophysical and integration test suite
uv run pytest -q -m "not network"

# Verify zero lint errors with Ruff
uv run ruff check .
```

### 3. Verify Reproducible Benchmarks
```powershell
# Re-run all 6 biophysical benchmarks and ensure exact match with docs/BENCHMARKS.md
uv run python scripts/run_validation_benchmarks.py --write-docs
```

### 4. Start the Application

#### Terminal A: Start the FastAPI Backend
```powershell
uv run uvicorn terraloop_api.main:app --reload --port 8000 --app-dir apps/api
```
*API docs will be active at `http://localhost:8000/docs`.*

#### Terminal B: Start the Next.js Frontend
```powershell
cd apps/web
npm run dev
```
*Open [http://localhost:3000](http://localhost:3000) in your browser.*

---

## 🚀 Deployment & Offline Resilience Architecture

TerraLoop is engineered with **zero-network failover resilience** for agricultural field deployments and zero-dependency judging:

1. **Vercel Multi-Service Architecture:**
   - The Next.js frontend and FastAPI backend are configured via `vercel.json` with service bindings and segment-aware URL rewrites (`/api/(.*)`).
2. **Offline-First Golden Fallbacks:**
   - If live Earth Engine or NASA POWER APIs are unreachable, the backend smoothly falls back to regional climatology without throwing exceptions.
   - If the entire Python backend is stopped, the Next.js web application (`apps/web/src/lib/api.ts`) automatically falls back to static JSON assets in `public/golden/`, ensuring 100% functionality for all 6 benchmark demo fields.
3. **Google Earth Engine (Live Mode, Optional):**
   - For live satellite queries beyond precomputed fields, authenticate Earth Engine:
     ```powershell
     uv pip install -e "packages/engine[gee]"
     earthengine authenticate
     ```
   - Provide credentials via `GEE_PROJECT` or `GEE_SERVICE_ACCOUNT_KEY` in `.env`.

---

## 📚 Scientific Citations & References

1. **FAO-56 Irrigation and Drainage:** Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop evapotranspiration - Guidelines for computing crop water requirements*. FAO Irrigation and Drainage Paper 56, Rome. [Link](https://www.fao.org/3/x0490e/x0490e00.htm).
2. **FAO-33 Yield Response to Water:** Doorenbos, J., & Kassam, A. H. (1979). *Yield response to water*. FAO Irrigation and Drainage Paper 33, Rome.
3. **RothC-26.3 Soil Carbon Model:** Coleman, K., & Jenkinson, D. S. (1996). *RothC-26.3: A model for the turnover of carbon in soil*. In Evaluation of Soil Organic Matter Models (pp. 237-246). Springer, Berlin. [DOI: 10.1007/978-3-642-61094-3_17](https://doi.org/10.1007/978-3-642-61094-3_17).
4. **RothC Inert Organic Matter (IOM):** Falloon, P., Smith, P., Coleman, K., & Marshall, S. (1998). *Estimating the size of the inert organic matter pool from total soil organic carbon content for use in the RothC model*. Soil Biology and Biochemistry, 30(8-9), 1207-1211. [DOI: 10.1016/S0038-0717(97)00256-3](https://doi.org/10.1016/S0038-0717(97)00256-3).
5. **Rice Hydrology & AWD:** Bouman, B. A. M., & Tuong, T. P. (2001). *Field water management to save water and increase its productivity in irrigated lowland rice*. Agricultural Water Management, 49(1), 11-30.
6. **Punjab Rice Water Balance Trials:** Sudhir-Yadav, Humphreys, E., Kukal, S. S., Gill, G., & Rangarajan, R. (2011). *Performance of direct seeded rice and puddled transplanted rice with different water management in the Indo-Gangetic Plains of India*. Field Crops Research, 121(1), 162-174.
7. **Happy Seeder Straw Mulching & Microclimate:** Sidhu, H. S., Singh, M., Humphreys, E., et al. (2007). *The Happy Seeder enables direct drilling of wheat into rice stubble*. Australian Journal of Experimental Agriculture, 47(7), 844-854.
8. **Wheat Terminal Heat Stress:** Lobell, D. B., Sibley, A., & Ortiz-Monasterio, J. I. (2012). *Extreme heat effects on wheat senescence in India*. Nature Climate Change, 2(3), 186-189. [DOI: 10.1038/nclimate1356](https://doi.org/10.1038/nclimate1356).
9. **Saxton-Rawls Soil Hydrology:** Saxton, K. E., & Rawls, W. J. (2006). *Soil water characteristic estimates by texture and organic matter for hydrologic solutions*. Soil Science Society of America Journal, 70(5), 1569-1578. [DOI: 10.2136/sssaj2005.0117](https://doi.org/10.2136/sssaj2005.0117).
10. **RUSLE Soil Loss Equation:** Renard, K. G., Foster, G. R., Weesies, G. A., McCool, D. K., & Yoder, D. C. (1997). *Predicting soil erosion by water: A guide to conservation planning with the Revised Universal Soil Loss Equation (RUSLE)*. USDA Agriculture Handbook No. 703.

---

## 📄 License & Attribution

Developed for the **NASA Space Apps Challenge**.  
Released under the [MIT License](LICENSE).  
*All NASA Earth observation datasets are courtesy of NASA Earth Science Data Systems (ESDS), NASA Earthdata, and the Google Earth Engine public data catalog.*
