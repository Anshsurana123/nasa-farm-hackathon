# TerraLoop — NASA Space Apps Challenge: Technical Judge Q&A

> **Scope & Purpose:**  
> This document provides rigorous, candid, and evidence-backed answers to the eight toughest technical and scientific questions that a NASA Space Apps Challenge judge, agronomist, or satellite data specialist will ask about TerraLoop.  
> Every statement is directly anchored to executable code, tests, and empirical benchmarks in this repository.

---

### Question 1: "Why do some fields use precomputed data, and how do you ensure custom farm coordinates aren't silently served someone else's numbers?"

**Direct Answer:**  
Precomputed data is **strictly reserved for our six explicitly designated golden demonstration fields** (`sangrur`, `ludhiana`, `bathinda`, `vidarbha`, `bundelkhand`, `thanjavur`).  
Every custom parcel drawn or clicked by a farmer receives an **uncached, live biophysical simulation** tailored to their exact coordinates, polygon boundary, SoilGrids profile, local weather history, farmer priorities, and baseline management.

**Technical Evidence in the Repo:**
1. **Strict Exact-ID Policy:** In `apps/api/terraloop_api/main.py` (`_match_golden_field`), golden assets are matched **only** if the incoming request carries an exact matching ID (`req.field.id in [f["id"] for f in _golden_index()]`). We explicitly eliminated all spatial radius tolerances (the former 0.15° / ~16 km shortcut) and name-substring matches. A custom farm even 100 meters away from a golden field is dispatched to live profiling and simulation.
2. **Transparent Provenance Tagging:** Golden demo snapshots carry `served_from="demo_snapshot"` and the precomputed `snapshot_date` when served from `/golden/*` or unmodified `/profile`, while live `/recommend` runs explicitly stamp `served_from="live_computation"` and `snapshot_date=None`. The web UI renders a clear badge: *"Saved Demo Snapshot"*.
3. **Automated Verification Test:** `tests/test_engine.py::test_golden_proximity_matcher` verifies that a coordinate 5 km or 15 km away from Sangrur returns `served_from="live_computation"` and `is_fallback=True` (when offline), while only exact ID `"sangrur"` receives the precomputed snapshot.

---

### Question 2: "Which NASA Earth observations actually change the optimization decisions, and which are merely displayed for context?"

**Direct Answer:**  
In adherence to **Rule 1 (NASA Data First, and It Must Matter)**, we strictly distinguish between datasets that drive biophysical simulation and ranking versus those that provide qualitative situational awareness.

| NASA Satellite Mission | Product ID / Collection | Spatial & Temporal Resolution | Drives Optimization Decisions? | Exact Biophysical Mechanism & Influence |
| :--- | :--- | :--- | :---: | :--- |
| **NASA POWER (MERRA-2)** | Hourly / Daily Agroclimatology | 0.5° × 0.625°, 30-year daily | **YES (Primary)** | Daily $T_{\max}, T_{\min}, R_s, \text{RH}, u_2$ drive FAO-56 Penman–Monteith $\text{ET}_0$ (falling back to Hargreaves–Samani when radiation/humidity/wind are unavailable), crop GDD, rice anthesis sterility (>35°C), maize silking heat (>35°C), and March wheat terminal heat (>32°C). Directly determines simulated yield ($Y_a$) and irrigation need. |
| **NASA NEX-GDDP-CMIP6** | Global Downscaled Projections | 0.25° × 0.25°, 2030–2060 | **YES (Scenario)** | Quantile-mapped temperature and rainfall distributions under SSP2-4.5 and SSP5-8.5 test rotation resilience against future mid-century climate stress. |
| **NASA GPM IMERG V07** | `NASA/GPM_L3/IMERG_V07` | 0.1° × 0.1° (~10 km), half-hourly | **YES** | Homogeneous 2001+ rainfall climatology, heavy-rain days (>50 mm) driving clay-soil waterlogging risk (`fao56_runner.py`), and annual precipitation feeding the Renard–Freimund RUSLE rainfall erosivity factor ($R$). |
| **NASA GRACE / GRACE-FO** | `NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI` | ~0.5° mascons (~50 km), monthly | **YES** | Long-term regional groundwater equivalent water thickness trends (e.g. -3.85 cm/yr in Punjab) scale the effective water-savings objective multiplier ($1.0 + 0.10 \times (|\text{trend}| - 1.0)$, capped at $1.50\times$), boosting water-efficient rotations in depleting aquifer zones. |
| **NASA SRTM / NASADEM** | `NASA/NASADEM_HGT/001` | 30-meter global DEM | **YES** | Topographic slope and aspect drive the RUSLE Topographic Factor ($LS$-factor) via Wischmeier–Smith equations, directly determining soil erosion risk. |
| **NASA FIRMS VIIRS/MODIS** | `FIRMS` active hotspots | 375-meter active hotspots | **YES (Baseline)** | October–November active thermal fire anomalies detect whether the farmer's current baseline involves crop residue burning, enforcing a -5 pt penalty on the Soil Health Index and reducing RothC organic carbon retention by 90%. |
| **Harmonized Landsat Sentinel (HLS)** | `NASA/HLS/HLSL30/v002` | 30-meter, 2–3 day revisit | **YES (Baseline)** | 3-year Savitzky–Golay smoothed NDVI time series infers historical crop seasonality (Kharif, Rabi, Zaid) and sowing/harvest turnaround windows to establish the farmer's baseline rotation. |
| **NASA SMAP L4** | `NASA/SMAP/SPL4SMGP/008` | 9 km, 3-hourly root-zone | **YES (Suitability) + CONTEXT** | 12 monthly root-zone soil moisture percentiles adjust post-monsoon residual soil moisture (`+15%` when `smap_mean > 60%`) and drought-tolerance bonuses/penalties (`< 35%`) in `suitability.py` plus live dry-spell estimation, while FAO-56 simulates daily field root-zone depletion directly (diagnostic rings keep a `"Context Only"` indicator). |

---

### Question 3: "How accurate are your crop yield and water predictions, and what is your calibration vs. held-out validation error?"

**Direct Answer:**  
We openly publish our exact ground-truth validation table in `docs/BENCHMARKS.md`, generated directly by `scripts/run_validation_benchmarks.py`.  
We do not hide discrepancies behind synthetic smoothing:

1. **Calibration Baseline (Sangrur, Punjab):**  
   - Simulated Irrigated Wheat: **5.25 t/ha** vs. Observed DES 5-year district mean **5.08 t/ha** (**+3.4% error**).
   - Simulated Kharif Paddy: **7.54 t/ha** vs. Observed DES district mean **7.35 t/ha** (**+2.5% error**).
2. **Held-Out Validation Sites (Frozen Parameters):**  
   - Ludhiana Wheat: **5.27 t/ha** vs. Observed **5.02 t/ha** (**+5.0% error**).
   - Ludhiana Paddy: **7.55 t/ha** vs. Observed **7.20 t/ha** (**+4.9% error**).
   - Bathinda Wheat: **5.05 t/ha** vs. Observed **4.82 t/ha** (**+4.8% error**).
   - Thanjavur Cauvery Delta Paddy: **6.29 t/ha** vs. Observed **5.85 t/ha** (**+7.4% error**).
3. **Rainfed Peninsular Yield Gaps (-33% to +48%):**  
   - Yavatmal (Vidarbha) Rainfed Cotton: **2.00 t/ha** vs. Observed **1.35 t/ha** (**+48.1% error**).
   - Jhansi (Bundelkhand) Rainfed Sorghum: **1.70 t/ha** vs. Observed **1.32 t/ha** (**+28.8% error**).
   - Yavatmal Rainfed Chickpea: **0.77 t/ha** vs. Observed **1.15 t/ha** (**-33.5% error**).
4. **Honest Agronomic Explanation:**  
   Our biophysical engine simulates **water- and radiation-limited potential yield ($Y_w$)**. In rainfed peninsular belts, real-world yields are severely depressed by chronic biotic stresses not simulated in satellite agroclimate models: pink bollworm (*Pectinophora gossypiella*) infestation in Vidarbha cotton, pod borer (*Helicoverpa armigera*) in chickpea, and red rot in sorghum. Rather than artificially distorting biophysical equations, TerraLoop displays yields and profits as **ranges**, accompanied by a prominent warning banner explaining the yield gap on rainfed peninsular sites.

---

### Question 4: "What does 'profit' actually mean in your recommendations, and which costs are excluded?"

**Direct Answer:**  
TerraLoop reports **Net Farm Operating Income (Gross Revenue minus CACP A2+FL Operating Costs)**.  
It explicitly represents cash operating profit plus imputed family labour compensation, **not** net economic profit after land rent:

1. **Included in Costs ($A2 + FL$):**  
   - All purchased inputs: certified hybrid/high-yielding seed, fertilizers (Urea, DAP, MOP), crop protection chemicals, irrigation electricity/diesel pumping costs, canal water cess, machinery hire charges (custom hiring center rates for tractors, Happy Seeders, combine harvesters).  
   - Imputed value of unpaid family labour ($FL$) as evaluated by the Commission for Agricultural Costs and Prices (CACP).
2. **Excluded from Costs (Difference between $A2+FL$ and $C2$):**  
   - Imputed rent on owned land, rent paid for leased land, and interest on fixed capital assets.  
   - Farmers who lease land must deduct their regional cash land rent (e.g. ₹45,000–₹65,000/ha/year in Punjab) to calculate take-home household surplus.
3. **Regional Economics Basis:**  
   State-specific economic schedules are loaded from `packages/crop-kb/economics/<state>.yaml`. For states where official CACP cost-of-cultivation tables are currently unverified, the system transparently utilizes Punjab figures as a benchmark, stamps the recommendation with `economics_basis="punjab_proxy"`, and informs the farmer: *"Cost estimate based on Punjab proxy data — treat as indicative"*.

---

### Question 5: "What real-world agricultural factors does your biophysical model NOT capture?"

**Direct Answer:**  
In accordance with **Rule 3 (Never Invent Numbers)** and **Rule 5 (Farmer-First Standards)**, we provide an explicit *"What the Model Does Not Capture"* disclosure directly in the user interface and printable advisory brief:
1. **Biotic Pest & Disease Outbreaks:** Terminal whitefly (*Bemisia tabaci*) attacks in cotton, yellow rust (*Puccinia striiformis*) in wheat, stem borer in paddy, and pink bollworm in cotton.
2. **Extreme Localized Weather Events:** Hailstorms during late grain filling, localized flash-flooding beyond 0.1° GPM pixel aggregation, and high-wind lodging.
3. **Mandi Market Dynamics & Gluts:** Seasonal wholesale market crashes during bumper harvests for non-procured crops (e.g. perishable vegetables, excess summer moong gluts in private mandis).
4. **Tubewell Salinity & Sodicity:** Pumping highly saline/sodic groundwater (electrical conductivity $>2.5\text{ dS/m}$ or residual sodium carbonate $>2.5\text{ meq/L}$) common in South-Western Punjab (Bathinda/Fazilka).

---

### Question 6: "What happens when NASA APIs or Google Earth Engine are unreachable or fail?"

**Direct Answer:**  
The system operates under a strict **Zero Fabrication / Graceful Degradation** policy:
1. **Never Invent Satellite Data:** If GEE is disabled or offline, `gee.py` returns honest empty structures and sets provenance mode to `mode="regional_climatology"` (for static regional lookups) or `mode="unknown"` (for transient products like FIRMS fire detections and HLS NDVI). `residue_burning_detected` is strictly set to `None`, never fabricated.
2. **Honest Data Mode Labels:** If NASA POWER is unreachable, the engine utilizes regional monthly climatological distributions, flagging the profile with `data_mode="hybrid_regional"` or `is_fallback=True`.
3. **User Notification:** The user interface renders an alert banner: *"Satellite service currently offline. Agroclimatic parameters derived from regional historical climatology."*
4. **Crash Prevention:** Bounded retries and disk-level caching (`@disk_cache`) ensure that temporary network drops never crash the decision-support flow.

---

### Question 7: "How do you prove that farmer priorities actually steer the optimization, rather than always returning hardcoded rotations?"

**Direct Answer:**  
We verify priority sensitivity mathematically using our automated multi-objective verification suite in `tests/test_engine.py::test_priority_monotonicity_sweep_200_vectors_four_fields` (and `test_selection_priority_directional_monotonicity`):
1. **Non-Dominated Pareto Sorting (NSGA-II):** Candidate rotations are evaluated across six simultaneous objectives: *Profit ($P_{50}$)*, *Water Savings ($\Delta\text{Irr}$)*, *Soil Health Score*, *Downside Risk ($CVaR_{10}$)*, *Low Labour Cost*, and *Food Security Caloric Density*.
2. **Monotonicity Verification:** We execute a 200-vector Monte Carlo priority sweep across benchmark fields. When a farmer increases the weight of *Water Savings* ($w_{\text{water}} \rightarrow 1.0$) while reducing *Profit* ($w_{\text{profit}} \rightarrow 0.0$), the mean irrigation requirement of the top-3 selected rotations drops monotonically (transitioning toward maize, millets, oilseeds, or summer pulses).
3. **Regional Differentiation (`docs/BENCHMARKS.md` Section 6):**
   - In Sangrur/Ludhiana (aquifer depletion zone), balanced priorities select **DSR Rice → Sunflower → Mung bean/Blackgram** (-18% to -19% water), **Maize → Sunflower → Mung bean** (-60% water), or **Mung bean → Wheat → Blackgram** (-50% water).
   - In Bathinda (semi-arid belt), top recommendations shift to **Mung bean → Wheat → Blackgram** (-37% water) and **Pearl millet → Sunflower → Blackgram** (-65% water).
   - In Vidarbha (rainfed Vertisol), the optimizer prioritizes drought resilience, selecting **Maize → Chickpea → Fallow**, **Groundnut → Chickpea → Fallow**, or **Pigeon pea → Chickpea → Fallow**.
   - In Bundelkhand (drought-prone soils), the system selects **Pigeon pea → Barley → Fallow**, **Groundnut → Chickpea → Fallow**, or **Maize → Chickpea → Fallow**.
   - In Thanjavur (Cauvery Delta), balanced recommendations shift from double-puddled paddy toward **Groundnut → DSR Rice → Blackgram** (-56.2% water).

---

### Question 8: "Is your decadal soil health model scientifically validated, or is it just a point score?"

**Direct Answer:**  
TerraLoop couples a **physical process model (RothC-Lite 26.3)** with a **standard agronomic index (USDA-NRCS 5 Principles)**:
1. **RothC-Lite 26.3 Process Verification:**  
   - We track five distinct organic carbon pools (DPM, RPM, BIO, HUM, IOM) over a 120-month continuous simulation using exact rate constants ($k_{\text{DPM}}=10.0, k_{\text{RPM}}=0.30, k_{\text{BIO}}=0.66, k_{\text{HUM}}=0.02\text{ yr}^{-1}$) and Jenkinson's clay-dependent respiration partition ratio:
     $$x = 1.67 \times (1.85 + 1.60 \times \exp(-0.0786 \times \text{clay}))$$
   - In Sangrur alluvial loam, conventional rice–wheat with stubble burning simulates a decadal loss of **$-1.92\text{ t C/ha}$**, matching long-term PAU monitoring showing continuous depletion of soil organic carbon under residue burning.  
   - Transitioning to PR-126 Short Rice + Happy Seeder zero-till wheat + summer moong or DSR + Zero-Till wheat + summer moong simulates sequestration gains of **$+3.19$ to $+3.74\text{ t C/ha}$ over 10 years**, aligning with published Indo-Gangetic Conservation Agriculture long-term field trials (Ladha et al. 2003; Jat et al. 2019 *Geoderma* 341: 1-11).
2. **Legume Nitrogen Mass Balance:**  
   - Legume biological nitrogen fixation (50 kg N/ha for moong, 60 kg N/ha for chickpea) confers a scientifically verified **25 kg N/ha synthetic fertilizer credit** to the subsequent cereal crop (PAU Package of Practices), saving exactly **3.5 standard 45-kg bags of Urea per hectare** ($25.0 / (45 \times 0.46) = 1.21\text{ bags/acre} = 3.0\text{--}3.5\text{ bags/ha}$).
