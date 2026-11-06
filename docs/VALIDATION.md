# TerraLoop India — Reproducible Biophysical & Economic Validation Report

> **Reproducibility Guarantee:** Every number in this document is generated directly by executing `uv run python scripts/run_validation_benchmarks.py --write-docs` against the TerraLoop simulation engine (`packages/engine/terraloop_engine/`).

## 1. Soil Texture & Root-Zone Water Balance Sensitivity (`models/aquacrop_runner.py`)

Evaluates FAO-56 daily root-zone soil moisture depletion (`TAW`, `RAW`, `Ks`, deep percolation) across three representative Indian soil textures under both Rainfed/Limited and Full Irrigation regimes (2020–2021 cycle).

| Soil Texture Class | Sand / Clay (%) | FC / WP (m³/m³) | Rainfed Wheat Yield (t/ha) | Irrigated Wheat Irrigation (mm) | DSR Rice Yield (t/ha) | DSR Rice Irrigation (mm) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Coarse Loamy Sand (SW Punjab / Rajasthan) | 76% / 10% | 0.129 / 0.062 | **1.16** | **489** | **4.81** | **1161** |
| Indo-Gangetic Alluvial Loam (Sangrur / Ludhiana) | 44% / 20% | 0.254 / 0.127 | **2.05** | **390** | **6.20** | **548** |
| Deccan Black Cotton Vertisol (Vidarbha Clay) | 22% / 50% | 0.424 / 0.296 | **2.06** | **351** | **6.20** | **466** |

## 2. Rabi Wheat Terminal Heatwave Sensitivity (March–April Grain-Filling Shock)

Tests the thermal senescence response during the final 40% of the Rabi wheat cycle (March–April grain filling, `Tmax > 31.5°C`) under baseline climate, a `+4.5°C` heat anomaly (analogous to the March 2022 North India heatwave), and `+4.5°C` with **Happy Seeder surface residue mulch** (`-1.0°C` soil/canopy cooling + `-10%` evaporation).

| Scenario | Mean Rabi Yield (t/ha) | Yield Change vs Normal (%) | Seasonal Irrigation (mm) |
| :--- | :---: | :---: | :---: |
| Baseline Climate (Conventional Tillage Wheat) | **4.80** | 0.0% | 307 |
| +4.5°C Mar–Apr Heatwave (Conventional Tillage Wheat) | **4.06** | **-15.4%** | 308 |
| +4.5°C Mar–Apr Heatwave + Happy Seeder Mulch | **4.26** | **-11.3%** | 236 |

## 3. Kharif Rice Hydrology & Stubble-Burning Turnaround Window

Compares Puddled Long-Duration Rice (`rice_puddled`, 142 days, 180 mm puddling + standing water), PAU Short-Duration Rice (`rice_short` PR-126, 123 days), and Direct-Seeded Rice (`rice_dsr`, 125 days, 0 mm puddling + Alternate Wetting & Drying) on Sangrur Alluvial Loam.

| Kharif Rice System | Duration (days) | Turnaround Before Wheat (days) | Irrigation (mm) | Water Saved vs Puddled (%) | Simulated Yield (t/ha) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Puddled Long-Duration Rice (Pusa-44) | 130 d | **11 days** | **727 mm** | **0.0%** | **6.89 t/ha** |
| Short-Duration Rice (PAU PR-126) | 108 d | **30 days** | **451 mm** | **38.0%** | **7.02 t/ha** |
| Direct-Seeded Rice (DSR + AWD) | 127 d | **26 days** | **334 mm** | **54.1%** | **6.32 t/ha** |

## 4. 10-Year RothC-Lite Soil Organic Carbon & Biological Nitrogen Trajectory

Evaluates 30-member ensemble outcomes on Sangrur Alluvial Loam (`SOC = 5.2 g/kg`) across three management systems.

| Rotation & Management System | 10-Yr SOC Change (t C/ha) | Soil Health Score (/100) | N Balance (kg N/ha/yr) | 45-kg Urea Bags Saved/ha | Turnaround Window (days) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Baseline: Puddled Rice → Wheat (Residue Burned) | **-1.98** | **15.2** | +81.1 | **0.0 bags** | **11 d** |
| PR-126 Short Rice → Happy Seeder Wheat → Summer Moong | **+2.44** | **89.1** | +58.9 | **3.6 bags** | **30 d** |
| Direct-Seeded Rice (DSR) → Zero-Till Wheat → Summer Moong | **+2.86** | **93.3** | +79.1 | **3.6 bags** | **26 d** |
| Kharif Maize → Happy Seeder Wheat → Summer Moong | **+3.15** | **90.9** | +108.7 | **3.6 bags** | **34 d** |

## 5. Six Indian Agro-Climatic Golden Benchmark Fields (Precomputed Engine Outputs)

| Benchmark Field | Agro-Climatic Zone | Baseline Rotation | Rank #1 Recommended Strategy | Irrigation Change | Median Net Profit (₹/ha) | 10-Yr SOC Delta (t C/ha) | Soil Health Score |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **Sangrur, Punjab** (`sangrur`) | Trans-Gangetic Plains (Alluvial Rice–Wheat Belt) | Puddled Rice → Wheat → Fallow | **Sorghum → Mustard / rapeseed → Mung bean** | **-50.2%** | **₹245,646** | **+1.96** | **90/100** |
| **Ludhiana, Punjab** (`ludhiana`) | Trans-Gangetic Plains (Alluvial Rice–Wheat Belt) | Puddled Rice → Wheat → Fallow | **Sorghum → Mustard / rapeseed → Mung bean** | **-48.4%** | **₹246,126** | **+1.96** | **89/100** |
| **Bathinda, Punjab** (`bathinda`) | Trans-Gangetic Semi-Arid Belt (South-West Punjab / Haryana) | Cotton → Wheat → Fallow | **Sunflower → Wheat → Mung bean** | **-13.9%** | **₹270,179** | **+1.88** | **89/100** |
| **Yavatmal (Vidarbha), Maharashtra** (`vidarbha`) | Western / Central Deccan Plateau (Vidarbha Black Cotton Vertisol Belt) | Cotton → Chickpea → Fallow | **Soybean → Mustard / rapeseed → Fallow** | **+0.0%** | **₹117,445** | **-0.38** | **60/100** |
| **Jhansi (Bundelkhand), Uttar Pradesh** (`bundelkhand`) | Central Plateau & Hills (Bundelkhand Semi-Arid Zone) | Sorghum → Wheat → Fallow | **Sunflower → Chickpea → Fallow** | **+0.0%** | **₹133,172** | **-1.07** | **54/100** |
| **Thanjavur (Cauvery Delta), Tamil Nadu** (`thanjavur`) | East Coast Plains & Deltas (Cauvery / Coastal Alluvial Zone) | Puddled Rice → Puddled Rice → Fallow | **Soybean → DSR Rice → Mung bean** | **-52.0%** | **₹304,508** | **+2.04** | **83/100** |
