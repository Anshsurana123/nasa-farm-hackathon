# TerraLoop India — Empirical Ground-Truth Comparison & Sensitivity Benchmarks

> **Reproducibility Guarantee:** Every number in this document is generated directly by executing `uv run python scripts/run_validation_benchmarks.py --write-docs` against the TerraLoop FAO-56 / FAO-33 simulation engine (`packages/engine/terraloop_engine/`), enforced in CI via `git diff --exit-code docs/BENCHMARKS.md`.

## 1. Empirical Calibration Check vs. DES / ICRISAT District-Level Data

Evaluates 30-year historical ensemble median simulated yields (`FAO-56 / FAO-33 daily soil-water balance`, `models/fao56_runner.py`) against published 5-year district mean yields from the Directorate of Economics & Statistics (DES, Ministry of Agriculture & Farmers Welfare, APY Statistics) and ICRISAT District-Level Database (DLD). All ground-truth entries are documented in `data/benchmarks/district_ground_truth.csv` with exact table, year range, and URLs.

### 1.1 Calibration Check: Sangrur, Punjab (Model Parameter Calibration Site)

Sangrur serves as the primary calibration baseline for the North-West Indian alluvial rice–wheat belt. Potential yield benchmarks ($y_{pot} = y_{min} + q_{pot}(y_{max} - y_{min})$), March terminal heat sensitivity ($T_{crit} = 32.0^\circ\text{C}$, final 35% grain-filling window), and MERRA-2 bias corrections (-4.5°C in March) were parameterized against Sangrur station observations and DES historical data.

| District | Crop & Regime | Observed District Mean (t/ha) | Simulated Median Yield (t/ha) | Absolute Error (t/ha) | Relative Error (%) | Reference Table & Source |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Sangrur, Punjab** | Rabi Wheat (Irrigated) | 5.08 | **5.25** | +0.17 | **+3.4%** | Directorate of Economics & Statistics Punjab — Statistical Abstract of Punjab 2023 Table 5.6 (Principal Crops Average Yield) |
| **Sangrur, Punjab** | Kharif Paddy (Rough Rice) | 7.35 | **7.54** | +0.19 | **+2.5%** | Directorate of Economics & Statistics Punjab — Statistical Abstract of Punjab 2023 Table 5.6 (Paddy unhusked 1.49x milled) |

### 1.2 Held-Out Evaluation: Indo-Gangetic & Peninsular Indian Benchmark Districts

The remaining 5 districts (Ludhiana, Bathinda, Yavatmal, Jhansi, Thanjavur) are held-out evaluation sites. Their simulations run with frozen parameter values, with zero post-hoc tuning against their observed district numbers.

| District | Crop & Regime | Observed District Mean (t/ha) | Simulated Median Yield (t/ha) | Absolute Error (t/ha) | Relative Error (%) | Reference Table & Source |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Ludhiana, Punjab** | Rabi Wheat (Irrigated) | 5.02 | **5.27** | +0.25 | **+5.0%** | Directorate of Economics & Statistics Punjab / ICRISAT DLD — Statistical Abstract of Punjab 2023 Table 5.6 (Principal Crops Average Yield) |
| **Ludhiana, Punjab** | Kharif Paddy (Rough Rice) | 7.20 | **7.55** | +0.35 | **+4.9%** | Directorate of Economics & Statistics Punjab / ICRISAT DLD — Statistical Abstract of Punjab 2023 Table 5.6 (Paddy unhusked 1.49x milled) |
| **Bathinda, Punjab** | Rabi Wheat (Canal/Tubewell) | 4.82 | **5.05** | +0.23 | **+4.8%** | Directorate of Economics & Statistics Punjab — Statistical Abstract of Punjab 2023 Table 5.6 (Principal Crops Average Yield) |
| **Yavatmal, Maharashtra** | Kharif Cotton (Rainfed) | 1.35 | **2.00** | +0.65 | **+48.1%** | DES Maharashtra / ICRISAT DLD — DES APY District Statistics Table APY-Cotton-Yavatmal (Seed Cotton) |
| **Yavatmal, Maharashtra** | Rabi Gram / Chickpea (Rainfed) | 1.15 | **0.77** | -0.38 | **-33.5%** | DES Maharashtra / ICRISAT DLD — DES APY District Statistics Table APY-Gram-Yavatmal |
| **Jhansi, Uttar Pradesh** | Kharif Jowar / Sorghum (Rainfed) | 1.32 | **1.70** | +0.38 | **+28.8%** | Directorate of Agriculture Uttar Pradesh / ICRISAT DLD — DES APY District Statistics Table APY-Jowar-Jhansi |
| **Thanjavur, Tamil Nadu** | Kuruvai/Samba Paddy (Irrigated) | 5.85 | **6.29** | +0.44 | **+7.4%** | Department of Economics & Statistics Tamil Nadu — Season and Crop Report Tamil Nadu Table 4.4 (District Yield of Paddy) |

### 1.3 Analysis of Discrepancies on Held-Out Districts

While held-out Trans-Gangetic Punjab sites match within single-digit percentage errors (Ludhiana wheat +5.0%, Ludhiana paddy +4.9%, Bathinda wheat +4.8%), larger deviations occur in peninsular and semi-arid rainfed sites. We intentionally report these discrepancies transparently without manual post-hoc adjustments for the following physical and agronomic reasons:

1. **Yavatmal, Maharashtra — Rainfed Seed Cotton (+48.1% error, 2.00 vs 1.35 t/ha):** DES APY statistics report farm-gate seed cotton across diverse marginal plots. In Vidarbha, rainfed cotton routinely suffers from chronic pink bollworm (*Pectinophora gossypiella*) infestation, boll rot during late monsoon showers, and sub-optimal fertilizer application. The FAO-56 / FAO-33 engine simulates pure abiotic water and temperature stress; it does not incorporate a biotic insect pest damage module.
2. **Jhansi (Bundelkhand), Uttar Pradesh — Rainfed Sorghum (+28.8% error, 1.70 vs 1.32 t/ha):** Bundelkhand sorghum averages reflect marginal, unfertilized subsistence fields with shallow rocky subsoils and severe bird foraging damage. Simulated yields represent potential yield constrained solely by soil-water availability, without nutrient deficiency penalties.
3. **Thanjavur, Tamil Nadu — Irrigated Paddy (+7.4% error, 6.29 vs 5.85 t/ha):** In the Cauvery delta coastal belt, the Samba rice crop is frequently subject to North-East monsoon cyclonic storms, prolonged drainage congestion/waterlogging at maturity, and blast disease (*Magnaporthe oryzae*). The model accurately simulates unstressed vegetative potential but does not depress yield for lodging or harvest flood damage.

## 2. Soil Texture & Root-Zone Water Balance Sensitivity (`models/fao56_runner.py`)

Evaluates FAO-56 daily root-zone soil moisture depletion (`TAW`, `RAW`, `Ks`, deep percolation) across three representative Indian soil textures under both Rainfed and Full Irrigation regimes (2020–2021 cycle).

| Soil Texture Class | Sand / Clay (%) | FC / WP (m³/m³) | Rainfed Wheat Yield (t/ha) | Irrigated Wheat Yield (t/ha) | Irrigated Wheat Water (mm) | DSR Rice Water (mm) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Coarse Loamy Sand (SW Punjab / Rajasthan) | 76% / 10% | 0.129 / 0.062 | **1.29** | **4.23** | **396** | **1162** |
| Indo-Gangetic Alluvial Loam (Sangrur / Ludhiana) | 44% / 20% | 0.254 / 0.127 | **2.30** | **4.90** | **325** | **691** |
| Deccan Black Cotton Vertisol (Vidarbha Clay) | 22% / 50% | 0.424 / 0.296 | **2.37** | **5.01** | **325** | **595** |

> **Process Note on Irrigated vs Rainfed Response:** Under full irrigation, daily root-zone soil water depletion $D_r$ is replenished before reaching RAW, maintaining water stress coefficient $K_s = 1.0$ continuously. Consequently, simulated irrigated wheat yield (~4.23 t/ha on sand, 4.90 t/ha on loam, 5.01 t/ha on Vertisol) is governed by radiation, temperature, and potential yield parameters rather than soil water storage. The physical impact of soil texture is expressed through the **irrigation volume required** to maintain that unstressed condition (396 mm on coarse loamy sand vs 325 mm on alluvial loam vs 325 mm on Vertisol clay) and through the **rainfed yield** (1.29 t/ha on sand vs 2.30 t/ha on loam).

## 3. Rabi Wheat Terminal Heatwave Sensitivity (March–April Grain-Filling Shock)

Tests the thermal senescence response during the final 35% of the Rabi wheat cycle (March–April grain filling, `Tmax > 32.0°C`) under baseline climate, a `+4.5°C` heat anomaly (analogous to the March 2022 North India heatwave), and `+4.5°C` with **Happy Seeder surface residue mulch** (`-1.0°C` soil/canopy cooling + `-10%` evaporation).

| Scenario | Mean Rabi Yield (t/ha) | Yield Change vs Normal (%) | Seasonal Irrigation (mm) |
| :--- | :---: | :---: | :---: |
| Baseline Climate (Conventional Tillage Wheat) | **4.90** | 0.0% | 325 |
| +4.5°C Mar–Apr Heatwave (Conventional Tillage Wheat) | **4.08** | **-16.7%** | 325 |
| +4.5°C Mar–Apr Heatwave + Happy Seeder Mulch | **4.37** | **-10.8%** | 325 |

## 4. Kharif Rice Hydrology & Stubble-Burning Turnaround Window

Compares Puddled Long-Duration Rice (`rice_puddled`, 175 mm puddling + continuous ponded head driving 3.5 mm/day percolation), PAU Short-Duration Rice (`rice_short` PR-126, 175 mm puddling), and Direct-Seeded Rice (`rice_dsr`, 75 mm pre-sowing rauni wetting + Alternate Wetting & Drying with non-ponded intermittent drainage averaging 2.55 mm/day) on Sangrur Alluvial Loam across their exact simulated cycle lengths. Parameterised to match Punjab Agricultural University experimental trials (Ladha et al. 2009; Sudhir-Yadav et al. 2011).

| Kharif Rice System | Duration (days) | Turnaround Before Wheat (days) | Irrigation (mm) | Water Saved vs Puddled (%) | Simulated Yield (t/ha) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Puddled Long-Duration Rice (Pusa-44) | 126 d | **11 days** | **845 mm** | **0.0%** | **7.12 t/ha** |
| Short-Duration Rice (PAU PR-126) | 104 d | **30 days** | **663 mm** | **21.5%** | **6.48 t/ha** |
| Direct-Seeded Rice (DSR + AWD) | 128 d | **26 days** | **623 mm** | **26.2%** | **6.49 t/ha** |

## 5. 10-Year RothC-Lite Soil Organic Carbon, Biological N & Soil Health Score Breakdown

Evaluates 30-member ensemble outcomes on Sangrur Alluvial Loam across four management systems, including the transparent component-by-component breakdown of the 0–100 Soil Health Index (5 USDA-NRCS principles × 15 pts max = 75 pts + SOC (−10..+15), RUSLE (−10..+3) & soil condition (−5..+5) modifiers − 5 pt residue burning penalty).

| Rotation & Management System | 10-Yr SOC Change (t C/ha) | Soil Health Score (/100) | N Balance (kg N/ha/yr) | 45-kg Urea Bags Saved/ha | Turnaround Window (days) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Baseline: Puddled Rice → Wheat (Residue Burned) | **-1.92** | **25.4** | +85.7 | **0.0 bags** | **11 d** |
| PR-126 Short Rice → Happy Seeder Wheat → Summer Moong | **+3.19** | **84.1** | +58.6 | **3.5 bags** | **30 d** |
| Direct-Seeded Rice (DSR) → Zero-Till Wheat → Summer Moong | **+3.74** | **86.4** | +66.2 | **3.5 bags** | **26 d** |
| Kharif Maize → Happy Seeder Wheat → Summer Moong | **+4.01** | **84.7** | +112.6 | **3.5 bags** | **34 d** |

### Soil Health Index Component & Weight Breakdown (`models/soil_health.py`)

| Rotation System | Armor (/15) | Min Disturbance (/15) | Diversity (/15) | Living Roots (/15) | Organic N (/15) | SOC Mod | Erosion Mod | Soil Cond Mod | Burn Penalty | Total (/100) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Baseline: Puddled Rice → Wheat (Residue Burned) | 6.4 | 6.5 | 4.0 | 12.8 | 4.5 | -8.7 | +2.1 | +2.8 | -5.0 | **25.4** |
| PR-126 Short Rice → Happy Seeder Wheat → Summer Moong | 14.4 | 11.8 | 10.1 | 14.9 | 12.5 | +15.0 | +2.7 | +2.8 | +0.0 | **84.1** |
| Direct-Seeded Rice (DSR) → Zero-Till Wheat → Summer Moong | 14.4 | 14.0 | 10.1 | 15.0 | 12.5 | +15.0 | +2.7 | +2.8 | +0.0 | **86.4** |
| Kharif Maize → Happy Seeder Wheat → Summer Moong | 14.4 | 12.7 | 10.1 | 14.7 | 12.5 | +15.0 | +2.7 | +2.8 | +0.0 | **84.7** |

## 6. Six Indian Agro-Climatic Golden Benchmark Fields (Precomputed Engine Outputs)

| Benchmark Field | Agro-Climatic Zone | Baseline Rotation | Rank #1 Recommended Strategy | Irrigation Change | Median Net Profit (₹/ha) | 10-Yr SOC Delta (t C/ha) | Soil Health Score |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **Sangrur, Punjab** (`sangrur`) | Trans-Gangetic Plains (Alluvial Rice–Wheat Belt) | Puddled Rice → Wheat → Fallow | **DSR Rice → Sunflower → Mung bean** | **-17.6%** | **₹271,978** | **+3.01** | **88/100** |
| **Ludhiana, Punjab** (`ludhiana`) | Trans-Gangetic Plains (Alluvial Rice–Wheat Belt) | Puddled Rice → Wheat → Fallow | **DSR Rice → Sunflower → Blackgram** | **-18.8%** | **₹293,344** | **+3.27** | **88/100** |
| **Bathinda, Punjab** (`bathinda`) | Trans-Gangetic Semi-Arid Belt (South-West Punjab / Haryana) | Cotton → Wheat → Fallow | **Mung bean → Wheat → Blackgram** | **-36.9%** | **₹191,788** | **+1.37** | **76/100** |
| **Yavatmal (Vidarbha), Maharashtra** (`vidarbha`) | Western / Central Deccan Plateau (Vidarbha Black Cotton Vertisol Belt) | Cotton → Chickpea → Fallow | **Maize → Chickpea → Fallow** | **+0.0%** | **₹119,939** | **+0.69** | **64/100** |
| **Jhansi (Bundelkhand), Uttar Pradesh** (`bundelkhand`) | Central Plateau & Hills (Bundelkhand Semi-Arid Zone) | Sorghum → Wheat → Fallow | **Pigeon pea → Barley → Fallow** | **+0.0%** | **₹94,040** | **+0.96** | **68/100** |
| **Thanjavur (Cauvery Delta), Tamil Nadu** (`thanjavur`) | East Coast Plains & Deltas (Cauvery / Coastal Alluvial Zone) | Puddled Rice → Puddled Rice → Blackgram | **Groundnut → DSR Rice → Blackgram** | **-56.2%** | **₹292,517** | **+2.29** | **84/100** |
