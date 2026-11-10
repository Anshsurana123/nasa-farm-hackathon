# What a Farmer Sees: Understanding TerraLoop Recommendations

> **A Plain-Language Guide for Farmers, Extension Workers, and Agricultural Planners**  
> *TerraLoop translates complex satellite observations and biophysical soil-water simulations into actionable, honest crop-rotation advice.*

---

## 1. What TerraLoop Calculates for Your Field

When you enter your farm coordinates or select a field, TerraLoop runs an end-to-end biophysical simulation:
1. **Daily Water Balance (FAO-56 / FAO-33):** Tracks daily rainfall, reference evapotranspiration ($ET_0$), root-zone moisture depletion, and deep percolation. It calculates exactly how much canal or borewell irrigation each crop requires across its vegetative, flowering, and grain-filling stages.
2. **Extreme Heat & Canopy Cooling:** Evaluates whether March terminal heatwaves ($>32^\circ\text{C}$) will shrivel wheat grain filling, and quantifies how surface straw mulch (via the Happy Seeder) buffers the canopy by $-1.0^\circ\text{C}$.
3. **Aquifer Conservation:** Pairs your field with regional NASA GRACE satellite gravity observations. In regions facing severe groundwater depletion (such as the $-3.85\text{ cm/year}$ decline in Punjab), rotations that conserve water are prioritized.
4. **10-Year Soil Carbon & Nitrogen Balance (RothC-Lite 26.3):** Forecasts changes in soil organic carbon (SOC) over a 10-year horizon and credits biological nitrogen fixation from summer pulses (e.g. $+50\text{ kg N/ha}$ from Summer Moong), saving synthetic fertilizer bags.
5. **Downside Economic Risk ($CVaR_{10}$):** Evaluates farm income over a 30-year historical weather ensemble or future climate projection. It shows your expected median income ($P_{50}$) and your guaranteed income during a 1-in-10-year severe drought year ($CVaR_{10}$).
6. **Nutritional Security:** Computes metabolizable dietary energy (Mcal/ha) and protein (kg/ha) produced by each rotation based on ICMR-NIN (2020) rural household recommended dietary allowances.

---

## 2. Plain Language on Your Screen: Translating the Numbers

| Technical Parameter | What It Means to You (Farmer-Facing) | How to Use It |
| :--- | :--- | :--- |
| **Net Irrigation Demand (mm)** | **Borewell Pumping Hours & Canal Turns** | $1\text{ mm} \approx 0.42\text{ hours}$ of 5-HP borewell pumping/ha. A saving of $200\text{ mm}$ means ~84 fewer hours of diesel/electric pumping and 2–3 fewer 75-mm canal floodings. |
| **Legume Nitrogen Credit** | **45-kg Urea Bags Saved per Hectare** | Succeeding cereal crops after summer pulses receive a $25\text{ kg N/ha}$ synthetic nitrogen reduction—saving **3.5 bags of Urea per hectare** (1.4 bags/acre). |
| **Turnaround Window (Days)** | **Breathing Room Between Harvest & Sowing** | Days between rice harvest and wheat sowing. Switching from long-duration rice (11 days) to short-duration PR-126 (30 days) allows straw management without stubble burning. |
| **Downside Risk ($CVaR_{10}$)** | **Income in a Severe Drought Year** | The average net profit in the worst 10% of climate years. Protects against crop failure and debt accumulation. |
| **Soil Health Score (0–100)** | **USDA-NRCS Soil Health Index** | Evaluates 5 physical principles: soil armor/cover, minimal disturbance, living roots, botanical diversity, and legume integration. |

---

## 3. What is Validated vs. What is Simulated vs. Unmodeled

### What is Empirically Validated
- **Trans-Gangetic Plains (Punjab & Haryana):** Calibrated and validated against 5-year district yields from the Directorate of Economics & Statistics (DES) and field trial data from Punjab Agricultural University (PAU).
  - Sangrur wheat: simulated $5.25\text{ t/ha}$ vs. observed $5.08\text{ t/ha}$ (+3.2% error).
  - Sangrur paddy: simulated $7.01\text{ t/ha}$ vs. observed $7.35\text{ t/ha}$ (-4.6% error).
  - Ludhiana wheat: simulated $5.30\text{ t/ha}$ vs. observed $5.02\text{ t/ha}$ (+5.7% error).
- **Direct-Seeded Rice (DSR) & Happy Seeder Trials:** Water savings (14%–24%) and turnaround window expansions (26–34 days) match PAU published agronomic trial benchmarks.
- **Economic Price Baselines:** Grounded in Government of India CACP 2024–25 Minimum Support Prices (MSP) and PAU A2+FL costs of cultivation.

### What is Simulated via Satellite Data
- **Daily Weather:** Sourced from NASA POWER (MERRA-2 reanalysis calibrated against IMD station normals).
- **Soil Stratigraphy:** Sourced from ISRIC SoilGrids 2.0 (250m resolution), overridden by your Soil Health Card laboratory test when provided.
- **Rainfall Erosivity:** Computed from NASA GPM IMERG V07 satellite precipitation.
- **Root-Zone Moisture:** Contextualized with NASA SMAP L4 observational percentiles.
- **Groundwater Trends:** Derived from NASA GRACE / GRACE-FO terrestrial water storage anomalies.

### What is Unmodeled (Honest Boundaries)
> [!IMPORTANT]
> TerraLoop is an abiotic biophysical decision-support system. It simulates radiation, temperature, water balance, and soil carbon. The following localized hazards are **not currently modeled**:
> 1. **Biotic Pest & Disease Outbreaks:** Hailstorms, pink bollworm infestations in cotton, yellow rust in wheat, or locust swarms.
> 2. **Localized Market Gluts:** Perishable vegetable price crashes (e.g. potato/onion wholesale price collapse outside MSP safety nets).
> 3. **Non-Indian Agronomy:** Fields outside validated Indian agro-climatic zones are labeled `unvalidated_global`. While NASA physics operates globally, international crop calendars and foreign economic markets require local calibration before making binding farm investments.

---

## 4. Steering Recommendations with Your Priorities

TerraLoop gives you full control. Adjusting the priority sliders directly shifts your recommendations:
- **Prioritize Water:** The engine elevates drought-hardy pulses, millets, mustard, and DSR rice, cutting groundwater pumping by up to 68%.
- **Prioritize Profit:** The engine selects high-margin cash rotations backed by guaranteed MSP procurement (FCI / State Agencies).
- **Prioritize Soil Health:** The engine maximizes residue retention, multi-family botanical diversity, and continuous living root cover.
- **Prioritize Food Security:** The engine balances household caloric and protein self-sufficiency.
