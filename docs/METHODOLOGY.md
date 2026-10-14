# METHODOLOGY.md

Living document: every model, equation and assumption used for user-facing numbers.
Agents: add a section whenever you implement a model (TASK-M05/M06/M07 etc.).

## Climate indicators (implemented: `models/agroclimate.py`, `profiler.py`)
- **Periods:** baseline 1985–2004 vs recent 2005–2024 (NASA POWER daily).
- **ET0:** Hargreaves-Samani (FAO-56 eq. 52) with extraterrestrial radiation (FAO-56 eq. 21). *Upgrade path:* FAO-56 Penman-Monteith using POWER radiation, RH, wind.
- **GDD:** base 10 °C, daily Tmax/Tmin capped at 30 °C.
- **Heat day:** Tmax > 35 °C. **Frost day:** Tmin < 0 °C. **Extreme rain day:** > 50 mm.
- **Rainy-season dry spell:** longest run of days < 1 mm within the wettest consecutive 4 months, averaged across years.
- **Drought frequency:** fraction of years with annual rain < 80% of mean (*placeholder until SMAP/SPI-based index*).
- **Heat-stress probability:** fraction of years with ≥ 10 heat days.

## Soil (implemented: `models/soil.py`)
- SoilGrids 0–30 cm depth-weighted mean (0–5, 5–15, 15–30 cm). Masked (urban/water) pixels → nearest valid pixel within ~3 km.
- USDA texture triangle classification.
- Field capacity / wilting point: Saxton & Rawls (2006), OM = SOC × 1.724 (capped at 8%).

## Erosion (implemented: `models/rusle.py`)
- RUSLE A = R·K·LS·C·P.
- R: Renard & Freimund (1994) from annual rain (*to be replaced by IMERG intensity-based R, TASK-M04*).
- K: Williams (1995) EPIC equation.
- LS: Wischmeier & Smith (1978), slope length 50 m; slope default 1% until NASADEM (TASK-D06).
- C: 0.3 placeholder in the profiler; rotation-specific C from crop cover calendar in O02.
- Classes: < 2 low, 2–10 moderate, 10–20 high, > 20 very high (t/ha/yr).

## Crop suitability pre-filter (implemented: `suitability.py`)
Heuristic only, used to prune candidates before simulation. Thermal fit = a sowing window exists where heat units ≥ 85% of requirement, no month below crop min temperature or above max+3 °C. The score rises with the share of months inside the optimal range. Water fit = season rain / minimum requirement, relaxed by irrigation availability and drought tolerance.

## Rotation constraints (implemented: `optimize/rotations.py`)
Season templates (Punjab: kharif Jun–Jul sowing ≤160 d, rabi Oct–Nov ≤175 d, zaid Apr ≤75 d, fallow allowed). No same crop in consecutive slots; respect bad predecessors; must-grow and exclude lists.

## Priority selection (implemented: `optimize/selection.py`)
Pareto filter on objectives (higher = better), min-max normalisation, weighted sum by farmer priorities, top-k distinct.

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
1. **Minimise Disturbance (0–15 pts):** Tillage intensity penalty from management practices (`no_till` = 15, `reduced_till`/`direct_seeded` = 11, `conventional` = 7, puddling = 4, residue burning = 2).
2. **Maximise Soil Cover (0–15 pts):** Proportion of days with living canopy or retained residue cover ($15 \times \text{cover fraction}$).
3. **Maximise Living Roots (0–15 pts):** Days with active growing crops divided by $365 \times \text{years}$ ($15 \times \text{living root fraction}$).
4. **Maximise Biodiversity (0–15 pts):** Shannon diversity index $H$ across botanical families represented in rotation ($15 \times \min(1.0, H / 1.0)$).
5. **Integrate Livestock / Organic (0–15 pts):** Fodder crops or livestock presence = 15 pts, green manure/cover crop = 12 pts, grain legume = 10 pts, monoculture cereal = 4 pts.
- **Modifiers ($\pm 25$ pts):**
  - **10-year SOC Trajectory:** Up to $+15$ pts for positive SOC accretion; up to $-10$ pts for SOC depletion.
  - **RUSLE Erosion:** $+10$ pts for soil loss $\le 3$ t/ha/yr; $0$ to $-10$ pts for loss $> 12$ t/ha/yr.
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

## Crop Simulation: AquaCrop-OSPy (implemented: `models/aquacrop_runner.py`, TASK-M02, M03)
- Daily soil-water-crop simulation using AquaCrop-OSPy 3.1:
  - Transpiration driven by water productivity ($WP^*$) and green canopy cover ($CC$).
  - Soil water balance across soil layers using Saxton-Rawls hydraulic properties ($FC, WP, SAT$).
  - Puddled rice modeled with 180 mm ponding requirement and 3.0 mm/day percolation.
  - Direct Seeded Rice (DSR) eliminates ponding requirement and reduces deep percolation to 2.3 mm/day, yielding a 20–25% net irrigation saving.

## Multi-Objective Risk Evaluation & Economics (implemented: `optimize/evaluate.py`, `models/economics.py`, TASK-O02, M08)
- **Historical Climate Ensemble:** Multi-year moving blocks from 40-year daily weather records ($N \ge 30$ members).
- **Objectives:**
  - P50 Profit (₹/ha/yr) from official CACP/PAU Minimum Support Prices (MSP) and comprehensive cultivation costs ($A_2 + FL$).
  - Downside Risk (CVaR-10): Conditional Value at Risk representing average profit in the worst 10% climate years.
  - Irrigation Demand (mm/yr): P50 annual net irrigation requirement across ensemble members.
  - Soil Health Score (0–100): Composite index covering the 5 NRCS soil health principles.
  - 10-year SOC Trajectory ($\Delta$ t C/ha/decade) from RothC-lite.
  - RUSLE Soil Loss (t/ha/yr).

## Known limitations (state these openly on the project page)
- NASA POWER is ~50 km resolution; field-level microclimate is not captured.
- SMAP (9 km) and GRACE (~300 km native) give regional context, not field-scale values.
- SoilGrids is modelled; farmer soil tests override it when provided.
- Crop parameters are calibrated against PAU/ICRISAT benchmarks and literature defaults.

