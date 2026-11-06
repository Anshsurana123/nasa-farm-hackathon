# TerraLoop India — Empirical Ground-Truth Comparison & Sensitivity Benchmarks

> **Reproducibility Guarantee:** Every number in this document is generated directly by executing `uv run python scripts/run_validation_benchmarks.py --write-docs` against the TerraLoop FAO-56 / FAO-33 simulation engine (`packages/engine/terraloop_engine/`), enforced in CI via `git diff --exit-code docs/BENCHMARKS.md`.

## 1. Empirical Yield Comparison vs. DES / ICRISAT District-Level Data

Compares 30-year historical ensemble median simulated yields (`FAO-56 / FAO-33 daily soil-water balance`) against published 5-year district mean yields from the Directorate of Economics & Statistics (DES, Ministry of Agriculture & Farmers Welfare) and ICRISAT District-Level Database (DLD).

| District | Crop & Regime | Observed District Mean (t/ha) | Simulated Median Yield (t/ha) | Absolute Error (t/ha) | Relative Error (%) | Reference Source |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Sangrur, Punjab** | Rabi Wheat (Irrigated) | 5.08 | **5.16** | +0.08 | **+1.6%** | DES Punjab / Statistical Abstract of Punjab (2019–23) |
| **Sangrur, Punjab** | Kharif Paddy (Rough Rice) | 7.35 | **6.96** | -0.38 | **-5.2%** | DES Punjab / PAU District Paddy Yield (2019–23) |
| **Ludhiana, Punjab** | Rabi Wheat (Irrigated) | 5.02 | **5.21** | +0.20 | **+3.9%** | DES Punjab / ICRISAT DLD Ludhiana (2019–23) |
| **Ludhiana, Punjab** | Kharif Paddy (Rough Rice) | 7.20 | **6.97** | -0.23 | **-3.1%** | DES Punjab / ICRISAT DLD Ludhiana (2019–23) |
| **Bathinda, Punjab** | Rabi Wheat (Canal/Tubewell) | 4.82 | **4.66** | -0.16 | **-3.3%** | DES Punjab / ICRISAT DLD Bathinda (2019–23) |
| **Yavatmal, Maharashtra** | Kharif Cotton (Rainfed) | 1.35 | **1.68** | +0.33 | **+24.4%** | DES Maharashtra / ICRISAT DLD Yavatmal Seed Cotton |
| **Yavatmal, Maharashtra** | Rabi Gram / Chickpea (Rainfed) | 1.15 | **1.02** | -0.12 | **-10.9%** | DES Maharashtra / ICRISAT DLD Yavatmal |
| **Jhansi, Uttar Pradesh** | Kharif Jowar / Sorghum (Rainfed) | 1.32 | **1.58** | +0.26 | **+19.7%** | DES Uttar Pradesh / ICRISAT DLD Jhansi |
| **Thanjavur, Tamil Nadu** | Kuruvai/Samba Paddy (Irrigated) | 5.85 | **6.98** | +1.13 | **+19.3%** | Season & Crop Report Tamil Nadu / ICRISAT DLD |

## 2. Soil Texture & Root-Zone Water Balance Sensitivity (`models/aquacrop_runner.py`)

Evaluates FAO-56 daily root-zone soil moisture depletion (`TAW`, `RAW`, `Ks`, deep percolation) across three representative Indian soil textures under both Rainfed and Full Irrigation regimes (2020–2021 cycle).

| Soil Texture Class | Sand / Clay (%) | FC / WP (m³/m³) | Rainfed Wheat Yield (t/ha) | Irrigated Wheat Yield (t/ha) | Irrigated Wheat Water (mm) | DSR Rice Water (mm) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Coarse Loamy Sand (SW Punjab / Rajasthan) | 76% / 10% | 0.129 / 0.062 | **1.19** | **5.21** | **542** | **1244** |
| Indo-Gangetic Alluvial Loam (Sangrur / Ludhiana) | 44% / 20% | 0.254 / 0.127 | **2.07** | **5.21** | **391** | **713** |
| Deccan Black Cotton Vertisol (Vidarbha Clay) | 22% / 50% | 0.424 / 0.296 | **2.09** | **5.19** | **351** | **585** |

## 3. Rabi Wheat Terminal Heatwave Sensitivity (March–April Grain-Filling Shock)

Tests the thermal senescence response during the final 35% of the Rabi wheat cycle (March–April grain filling, `Tmax > 32.0°C`) under baseline climate, a `+4.5°C` heat anomaly (analogous to the March 2022 North India heatwave), and `+4.5°C` with **Happy Seeder surface residue mulch** (`-1.0°C` soil/canopy cooling + `-10%` evaporation).

| Scenario | Mean Rabi Yield (t/ha) | Yield Change vs Normal (%) | Seasonal Irrigation (mm) |
| :--- | :---: | :---: | :---: |
| Baseline Climate (Conventional Tillage Wheat) | **5.21** | 0.0% | 391 |
| +4.5°C Mar–Apr Heatwave (Conventional Tillage Wheat) | **3.99** | **-23.4%** | 389 |
| +4.5°C Mar–Apr Heatwave + Happy Seeder Mulch | **4.42** | **-15.2%** | 390 |

## 4. Kharif Rice Hydrology & Stubble-Burning Turnaround Window

Compares Puddled Long-Duration Rice (`rice_puddled`, 130 days, 175 mm puddling + 3.5 mm/day flooded percolation), PAU Short-Duration Rice (`rice_short` PR-126, 108 days, 175 mm puddling), and Direct-Seeded Rice (`rice_dsr`, 127 days, 75 mm pre-sowing rauni wetting + Alternate Wetting & Drying at 2.55 mm/day percolation) on Sangrur Alluvial Loam.

| Kharif Rice System | Duration (days) | Turnaround Before Wheat (days) | Irrigation (mm) | Water Saved vs Puddled (%) | Simulated Yield (t/ha) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Puddled Long-Duration Rice (Pusa-44) | 130 d | **11 days** | **897 mm** | **0.0%** | **6.95 t/ha** |
| Short-Duration Rice (PAU PR-126) | 108 d | **30 days** | **704 mm** | **21.5%** | **7.02 t/ha** |
| Direct-Seeded Rice (DSR + AWD) | 127 d | **26 days** | **651 mm** | **27.5%** | **6.33 t/ha** |

## 5. 10-Year RothC-Lite Soil Organic Carbon, Biological N & Soil Health Score Breakdown

Evaluates 30-member ensemble outcomes on Sangrur Alluvial Loam across four management systems, including the transparent component-by-component breakdown of the 0–100 Soil Health Index (5 USDA-NRCS principles × 15 pts max = 75 pts + SOC & RUSLE modifiers ±25 pts − 5 pt residue burning penalty).

| Rotation & Management System | 10-Yr SOC Change (t C/ha) | Soil Health Score (/100) | N Balance (kg N/ha/yr) | 45-kg Urea Bags Saved/ha | Turnaround Window (days) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Baseline: Puddled Rice → Wheat (Residue Burned) | **-1.86** | **17.2** | +78.4 | **0.0 bags** | **11 d** |
| PR-126 Short Rice → Happy Seeder Wheat → Summer Moong | **+2.39** | **78.6** | +68.2 | **3.5 bags** | **30 d** |
| Direct-Seeded Rice (DSR) → Zero-Till Wheat → Summer Moong | **+2.79** | **80.9** | +87.3 | **3.5 bags** | **26 d** |
| Kharif Maize → Happy Seeder Wheat → Summer Moong | **+3.08** | **79.2** | +128.8 | **3.5 bags** | **34 d** |

### Soil Health Index Component & Weight Breakdown (`models/soil_health.py`)

| Rotation System | Armor (/15) | Min Disturbance (/15) | Diversity (/15) | Living Roots (/15) | Organic N (/15) | SOC Mod | Erosion Mod | Burn Penalty | Total (/100) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Baseline: Puddled Rice → Wheat (Residue Burned) | 6.4 | 6.5 | 4.0 | 12.8 | 4.5 | -8.5 | -3.6 | -5.0 | **17.2** |
| PR-126 Short Rice → Happy Seeder Wheat → Summer Moong | 14.4 | 11.8 | 10.1 | 14.9 | 12.5 | +15.0 | -0.1 | +0.0 | **78.6** |
| Direct-Seeded Rice (DSR) → Zero-Till Wheat → Summer Moong | 14.4 | 14.0 | 10.1 | 15.0 | 12.5 | +15.0 | -0.1 | +0.0 | **80.9** |
| Kharif Maize → Happy Seeder Wheat → Summer Moong | 14.4 | 12.7 | 10.1 | 14.7 | 12.5 | +15.0 | -0.1 | +0.0 | **79.2** |

## 6. Six Indian Agro-Climatic Golden Benchmark Fields (Precomputed Engine Outputs)

| Benchmark Field | Agro-Climatic Zone | Baseline Rotation | Rank #1 Recommended Strategy | Irrigation Change | Median Net Profit (₹/ha) | 10-Yr SOC Delta (t C/ha) | Soil Health Score |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **Sangrur, Punjab** (`sangrur`) | Trans-Gangetic Plains (Alluvial Rice–Wheat Belt) | Puddled Rice → Wheat → Fallow | **DSR Rice → Wheat → Mung bean** | **-18.1%** | **₹212,637** | **+2.79** | **78/100** |
| **Ludhiana, Punjab** (`ludhiana`) | Trans-Gangetic Plains (Alluvial Rice–Wheat Belt) | Puddled Rice → Wheat → Fallow | **DSR Rice → Wheat → Mung bean** | **-19.9%** | **₹215,220** | **+2.81** | **85/100** |
| **Bathinda, Punjab** (`bathinda`) | Trans-Gangetic Semi-Arid Belt (South-West Punjab / Haryana) | Cotton → Wheat → Fallow | **Blackgram → Wheat → Fallow** | **-57.0%** | **₹132,041** | **-0.20** | **63/100** |
| **Yavatmal (Vidarbha), Maharashtra** (`vidarbha`) | Western / Central Deccan Plateau (Vidarbha Black Cotton Vertisol Belt) | Cotton → Chickpea → Fallow | **Soybean → Wheat → Fallow** | **+0.0%** | **₹50,536** | **+0.87** | **63/100** |
| **Jhansi (Bundelkhand), Uttar Pradesh** (`bundelkhand`) | Central Plateau & Hills (Bundelkhand Semi-Arid Zone) | Sorghum → Wheat → Fallow | **Maize → Chickpea → Fallow** | **+0.0%** | **₹101,874** | **+0.07** | **55/100** |
| **Thanjavur (Cauvery Delta), Tamil Nadu** (`thanjavur`) | East Coast Plains & Deltas (Cauvery / Coastal Alluvial Zone) | Puddled Rice → Puddled Rice → Fallow | **Maize → DSR Rice → Mung bean** | **-49.5%** | **₹214,430** | **+3.02** | **72/100** |
