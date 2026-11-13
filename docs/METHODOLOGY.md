# METHODOLOGY.md

Living document: every model, equation and assumption used for user-facing numbers.
Agents: add a section whenever you implement a model (TASK-M05/M06/M07 etc.).

## Climate indicators (implemented: `models/agroclimate.py`, `profiler.py`)
- **Periods:** baseline 1985–2004 vs recent 2005–2024 (NASA POWER daily).
- **ET0:** FAO-56 Penman–Monteith (`et0_penman_monteith_series`) using NASA POWER radiation, RH, and 2m wind when available (>50% coverage), with Hargreaves–Samani (FAO-56 eq. 52) fallback.
- **GDD:** base 10 °C, daily Tmax/Tmin capped at 30 °C.
- **Heat day:** Tmax > 35 °C. **Frost day:** Tmin < 0 °C. **Extreme rain day:** > 50 mm.
- **Rainy-season dry spell:** longest run of days < 1 mm within the wettest consecutive 4 months, averaged across years (augmented by SMAP L4 root-zone soil moisture percentiles when live).
- **Drought frequency:** fraction of years with annual rain < 80% of mean (combined with SMAP L4 root-zone moisture adjustments in suitability).
- **Heat-stress probability:** fraction of years with ≥ 10 heat days.

## Soil (implemented: `models/soil.py`)
- SoilGrids 0–30 cm depth-weighted mean (0–5, 5–15, 15–30 cm), with Government of India Soil Health Card (`pH`, `OC %`, `Available N/P/K`) lab override support. Masked (urban/water) pixels → nearest valid pixel within ~3 km.
- USDA texture triangle classification.
- Field capacity / wilting point: Saxton & Rawls (2006), OM = SOC × 1.724 (capped at 8%).

## Erosion (implemented: `models/rusle.py`)
- RUSLE A = R·K·LS·C·P.
- R: Renard & Freimund (1994) from 2001+ homogeneous precipitation (GPM IMERG V07 / POWER).
- K: Williams (1995) EPIC equation.
- LS: Wischmeier & Smith (1978), slope length 50 m using 30 m NASADEM slope (%) where available (1% fallback when unavailable).
- C: 0.3 placeholder in the profiler; rotation-specific C from crop cover calendar in O02.
- Classes: < 2 low, 2–10 moderate, 10–20 high, > 20 very high (t/ha/yr).

## Crop suitability pre-filter (implemented: `suitability.py`)
Heuristic only, used to prune candidates before simulation. Thermal fit = a sowing window exists where heat units ≥ 85% of requirement, no month below crop min temperature or above max+4 °C. The score rises with the share of months inside the optimal range. Water fit combines season rain, post-monsoon SMAP L4-modulated residual soil moisture, irrigation cap, and drought tolerance, adjusted for aquifer overdraft (`groundwater_trend_cm_per_year`), drought/heat hazards, and SoilGrids/SHC soil pH, P, and K.

## Rotation constraints (implemented: `optimize/rotations.py`)
Season templates (IGP Kharif Jun–Jul ≤165 d, Rabi Oct–Nov ≤175 d, Zaid Apr ≤75 d; Southern Delta Kuruvai/Samba/Navarai; Southern Hemisphere shifted seasons). No same crop in consecutive slots; respect bad predecessors; must-grow, exclude, livestock, and irrigation-cap constraints.

## Priority selection (implemented: `optimize/selection.py`)
Hard agronomic screening (turnaround days, duration, irrigation cap, excluded crops) followed by NSGA-II non-dominated Pareto sorting and priority-weighted normalized ranking across 6 objectives (`profit`, `water_savings`, `soil_health`, `low_risk`, `low_labour`, `food_security`), returning top-k diverse strategies.

## Soil Carbon Model: RothC-lite (implemented: `models/soil_health.py`, TASK-M05)
Based on the Rothamsted Carbon Model (RothC-26.3; Coleman & Jenkinson, 1996) implemented at monthly time-step:
- **5 Carbon Pools:** Decomposable Plant Material (DPM), Resistant Plant Material (RPM), Microbial Biomass (BIO), Humified Organic Matter (HUM), Inert Organic Matter (IOM).
- **Initial pool distribution:** Total topsoil SOC stock $C_{tot} = 10\,000 \times \text{depth} \times \rho_b \times (\text{SOC}_{g/kg} / 1000)$ (t C/ha). Falloon et al. (1998): $IOM = 0.049 \times C_{tot}^{1.139}$. Active SOC partitioned into DPM (1.5%), RPM (18.5%), BIO (2.5%), HUM (77.5%).
- **Monthly rate constants:** $k_{DPM}=10.0/12$, $k_{RPM}=0.30/12$, $k_{BIO}=0.66/12$, $k_{HUM}=0.02/12$ $\text{month}^{-1}$.
- **Rate modifiers:** Overall rate modifier $\xi = a(T) \times b(M) \times c_{cov}$:
  - Temperature: $a(T) = \frac{47.91}{1 + \exp(106.06 / (T + 18.27))}$.
  - Moisture: $b(M) = \max(0.2, \min(1.0, 1.0 - 0.8 \times \frac{\max(0, 0.75 \times ET_0 - P)}{100}))$.
  - Vegetative cover: $c_{cov} = 0.6$ when crop canopy is present, $1.0$ for bare/fallow soil.
- **Decomposition & clay partition:** Clay-dependent partitioning $x = 1.67 \times (1.85 + 1.60 \times \exp(-0.0786 \times \text{clay}))$. Fraction lost as $\text{CO}_2$ is $x / (x + 1)$; remaining $1 / (x + 1)$ synthesized into BIO (46%) and HUM (54%).
- **Residue inputs:** Dry residue (t/ha) $\times 0.45$ C fraction partitioned into DPM/RPM (default ratio 1.44: 59% DPM, 41% RPM). Residue burning leaves only ~10% ash C, drastically penalizing long-term SOC.

## Nitrogen Balance Model (implemented: `models/soil_health.py`, TASK-M06)
Seasonal N mass balance (kg N/ha):
- **Inputs:** Fertilizer applied $N_{fert}$ (base crop demand or farmer rate minus legume credit), symbiotic biological nitrogen fixation $N_{fix}$ (`CropSpec.n_fixation_kg_ha`), and atmospheric wet/dry deposition $N_{dep}$ ($\sim 10$ kg N/ha/yr).
- **Legume credit:** Successor non-legume crops in rotation receive a $25$ kg N/ha reduction in synthetic fertilizer requirement.
- **Harvest removal:** $N_{removal} = \text{Yield} \times 1000 \times \text{grain\_N\_ratio}$ (cereals $\sim 1.5\text{--}2.0\%$, grain legumes $\sim 3.5\text{--}4.0\%$, soybean $\sim 6.0\%$, oilseeds $\sim 2.6\text{--}3.0\%$).
- **Surplus/Deficit:** $\text{Balance} = (N_{fert} + N_{fix} + N_{dep}) - N_{removal}$.

## Soil Health Score (implemented: `models/soil_health.py`, TASK-M07)
Composite 0–100 index mapping rotation outputs directly onto the **5 USDA-NRCS Soil Health Principles**:
1. **Minimise Disturbance (0–15 pts):** Tillage intensity penalty from management practices (`no_till`/`zero_till`/`happy_seeder` = 15, `reduced_till`/`strip_till`/`direct_seeded` = 12, `conventional` = 8, puddling = 5.5, residue burning = 3.5).
2. **Maximise Soil Cover (0–15 pts):** Proportion of days with living canopy or retained residue cover (`0.96` with retained residue/Happy Seeder, `0.72` conventional, `0.42` burned, `0.15–0.30` fallow).
3. **Maximise Living Roots (0–15 pts):** Annual growing-root duration normalized against 330 days/yr ($15 \times \text{living root fraction}$).
4. **Maximise Biodiversity (0–15 pts):** Shannon diversity index $H$ across botanical families represented in rotation ($15 \times \min(1.0, H / 0.95)$).
5. **Integrate Livestock / Organic (0–15 pts):** Livestock + fodder/legume = 15 pts, legume/green-manure = 12.5 pts, livestock only = 9.0 pts, monoculture cereal = 4.5 pts.
- **Modifiers & Penalties:**
  - **10-year SOC Trajectory (-10 to +15 pts):** Up to $+15$ pts for positive SOC accretion ($\ge +2.2\text{ t C/ha}$); down to $-10$ pts for SOC depletion.
  - **RUSLE Erosion (-10 to +3 pts):** Up to $+3$ pts when annual soil loss $\le 5.0\text{ t/ha/yr}$ ($T$-value); down to $-10$ pts for accelerated erosion above $5.0\text{ t/ha/yr}$.
  - **Baseline Soil Condition (-5 to +5 pts):** Topsoil SOC, pH acidity/alkalinity, and available P/K adjustment from SoilGrids / SHC.
  - **Residue Burning Penalty (-5 pts):** Direct penalty whenever residue burning practices occur.
- **Scale:** Clamped to $[0, 100]$.

## Terminal Heat & Climate Data Quality Safeguards (implemented: `profiler.py`, TASK-D11)
- **Wheat Terminal Heat Stress:** Evaluated during the reproductive/grain-filling phase (1 March to 15 April in NW India / Punjab). Metric measures average days/year with $T_{max} > 32^\circ\text{C}$ during this sensitive window. Above $32^\circ\text{C}$, starch synthase is deactivated and grain filling duration drops sharply, depressing yields by 4–8% per degree above threshold (Lobell et al., 2012; PAU agrometeorology bulletin).
- **Rainfall Inhomogeneity Safeguard:** To guard against satellite/reanalysis step changes across decades, trend claims in automated advisory notes are strictly filtered: only trends with $10\% \le |\Delta P| \le 30\%$ are reported; larger spikes are suppressed to avoid reanalysis artifacts. GPM IMERG V07 (2001–2024) is used for regional rainfall climatology.

## Earth Observation Phenology & Crop History (implemented: `eo/phenology.py`, TASK-E01, E02)
- **NDVI Smoothing:** Harmonized Landsat-Sentinel (HLS 30 m) or MODIS 250 m time series regularised to 5-day time step via linear time interpolation and smoothed with a pure-NumPy Savitzky-Golay order-2 polynomial filter.
- **Season Peak Detection:** Local maxima identified with peak prominence threshold $\ge 0.15$ NDVI. Start and end of growing season detected at $20\%$ amplitude above base.
- **Rule-based Agro-Ecological Classification:**
  - Kharif (Summer monsoon, peak in Jul–Oct): Peak $\ge 0.60$ NDVI $\rightarrow$ Paddy Rice (`rice_puddled` or `rice_dsr`); peak $< 0.60$ $\rightarrow$ Maize or Cotton.
  - Rabi (Winter, peak in Jan–Apr): Peak in January $\rightarrow$ Mustard; peak in Feb–Apr $\rightarrow$ Wheat.
  - Zaid (Pre-monsoon, peak in May–Jun) $\rightarrow$ Summer Moong or fodder.

## Crop Simulation: FAO-56 / FAO-33 Daily Soil-Water Balance (implemented: `models/fao56_runner.py` with `aquacrop_runner.py` shim, TASK-M02, M03)
- Daily root-zone soil-water-crop simulation based on FAO Irrigation & Drainage Paper No. 56 (Allen et al., 1998) and Paper No. 33 (Doorenbos & Kassam, 1979):
  - Daily crop evapotranspiration $ET_c = K_c(t) \times ET_0$ with 4-stage piecewise linear $K_c$ curve (`kc_ini`, `kc_mid`, `kc_end`) and $-10\%$ evaporation reduction under retained surface mulch (`happy_seeder` / `residue_retained`).
  - Root-zone water balance across Total Available Water ($TAW = 1000(\theta_{FC} - \theta_{WP})Z_r$) and Readily Available Water ($RAW = p \cdot TAW$) using Saxton-Rawls (2006) hydraulic properties, daily depletion $D_{r,t}$, and water stress coefficient $K_s(t)$.
  - Reproductive heat stress above $32.0^\circ\text{C}$ during the final $35\%$ of the Rabi cycle (Asseng et al., 2011; Lobell et al., 2012), buffered by $-1.0^\circ\text{C}$ canopy/topsoil cooling under Happy Seeder surface straw mulch (Sidhu et al., 2007).
  - Puddled Transplanted Rice (`rice_puddled`, 126 field days) modeled with $175\text{ mm}$ puddling requirement and $3.5\text{ mm/day}$ plough-pan percolation until pre-harvest drainage (14 days before harvest).
  - PAU Short-Duration Rice (`rice_short` PR-126, 104 field days) saves $\sim 21\%$ irrigation water from 22 fewer field days and expands the Kharif-to-Rabi turnaround window from 11 to 30 days.
  - Direct-Seeded Rice + AWD (`rice_dsr`) replaces $175\text{ mm}$ puddling with a $75\text{ mm}$ pre-sowing *rauni* wetting and $2.55\text{ mm/day}$ AWD percolation on medium/fine soils, saving $\sim 25\text{--}28\%$ irrigation water (Yadav et al., 2011; Bouman & Tuong, 2001).

## Multi-Objective Risk Evaluation & Economics (implemented: `optimize/evaluate.py`, `models/economics.py`, TASK-O02, M08)
- **Historical Climate Ensemble:** Multi-year moving blocks from 40-year daily weather records ($N \ge 30$ members).
- **Objectives:**
  - P50 Profit from state CACP Minimum Support Prices / market realization and comprehensive cultivation costs ($A_2 + FL$).
  - Downside Risk (CVaR-10): Conditional Value at Risk representing average profit in the worst 10% climate years.
  - Water Savings / Irrigation Demand (mm/yr): P50 annual net irrigation requirement across ensemble members, modulated by NASA GRACE groundwater depletion urgency.
  - Soil Health Score (0–100): Composite index covering the 5 NRCS soil health principles + RothC SOC, RUSLE erosion, and topsoil condition modifiers.
  - Low Labour Cost: Inverse cultivation labor demand across the rotation.
  - Food Security: Nutritional energy/protein score adjusted by state procurement assurance (`models/nutrition.py`).
- **Additional Diagnostics:** 10-year SOC Trajectory ($\Delta$ t C/ha/decade) from RothC-lite and RUSLE Soil Loss (t/ha/yr).

## Known limitations (state these openly on the project page)
- NASA POWER is ~50 km resolution; field-level microclimate is not captured.
- SMAP (9 km) and GRACE (~300 km native) give regional context and macro-scale urgency/moisture signals, not parcel-scale measurements.
- SoilGrids is modelled; farmer soil tests (Soil Health Card) override it when provided.
- Calibrated and validated for Indian agro-climatic zones; coordinates outside India are explicitly flagged as `unvalidated_global` with proxy benchmark economics.
- Crop parameters are calibrated against PAU/ICRISAT benchmarks and literature defaults.

