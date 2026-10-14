# NASA Space Apps Challenge 2026: Official Submission Package

**Project Name:** TerraLoop ⟳  
**Challenge:** Crop Rotations Planned with NASA Earth Observations  
**Lead Demo Story:** Sangrur & Ludhiana, Punjab, India (Groundwater Depletion & Residue Burning)  
**Live Demo:** Precomputed offline-ready for all Golden Fields (Sangrur, Ludhiana, Bathinda, Iowa, Machakos)

---

## 1. 30-Second Video Storyboard & Script (TASK-S01)

> **Format:** 30 seconds, 1080p 16:9, English narration with English & Punjabi subtitles.

| Timestamp | Visual Shot | Audio Narration | On-Screen Graphic & Evidence |
|---|---|---|---|
| **00:00 – 00:06** | **Hook:** NASA GRACE groundwater anomaly map zoomed over NW India showing dark crimson aquifer loss, overlaid with NASA FIRMS active fire hotspots across Punjab. | *"From space, NASA satellites observe Punjab's groundwater dropping 4 centimeters every year, while post-harvest fields burn."* | **Signal:** NASA GRACE (-3.85 cm/yr) + NASA FIRMS (Stubble fires). Text: *Punjab's Aquifers Are Depleting.* |
| **00:06 – 00:12** | **Diagnosis:** User selects Sangrur hero field on TerraLoop map. Field Report Card generates instantly: 5-year HLS satellite crop history detects uninterrupted rice-wheat monoculture. | *"Drop a pin on any field. TerraLoop decodes years of satellite phenology, revealing the intensive monoculture driving the crisis."* | **Signal:** NASA HLS 30 m NDVI time series detecting Kharif Rice + Rabi Wheat seasons. |
| **00:12 – 00:20** | **Decision Engine:** Farmer toggles priorities (Water Savings & Soil Carbon). The engine simulates hundreds of crop rotations through FAO AquaCrop & RothC models. | *"Set your priorities in Punjabi or English. TerraLoop simulates hundreds of rotations across 40 years of NASA weather data."* | **Action:** Priority Sliders in Punjabi (ਪਾਣੀ ਦੀ ਬੱਚਤ, ਮਿੱਟੀ ਸਿਹਤ) → AquaCrop-OSPy 3.1 & RothC simulation. |
| **00:20 – 00:26** | **Actionable Strategy:** Side-by-side strategy cards compare Baseline vs Strategy 1 (DSR Rice ➔ Wheat + Mulch ➔ Summer Moong). | *"Strategy 1 saves 25% irrigation water, halts stubble burning, and builds 2 tons of organic carbon per hectare."* | **Results:** 💧 -24.7% Irrigation · 🌿 +2.1 t C/ha SOC · 💰 ₹104,000/ha Net Margin · Zero Burning. |
| **00:26 – 00:30** | **Global Outro:** Montage pans to global golden fields (Iowa corn-soy cover crops, Kenya dryland beans) with NASA Earth Observations badge. | *"TerraLoop: Transforming NASA Earth observations into resilient farms worldwide."* | **Logo:** TerraLoop ⟳ · Powered by 8 NASA Earth Data Collections · Space Apps 2026. |

---

## 2. 7-Slide Pitch Deck (TASK-S03)

### Slide 1: Title & The Vision
- **Header:** TerraLoop ⟳
- **Subheader:** Adaptive Crop-Rotation Decision Support with NASA Earth Observations
- **Visual:** High-resolution satellite view of the Punjab breadbasket overlaid with NASA GRACE groundwater drawdown vectors.
- **Key Takeaway:** Turning NASA satellite observations into grounded, farmer-first crop rotations that save aquifers, enrich soils, and ensure farm profitability.
- **Presenter Note:** "Judges, agriculture uses 70% of global freshwater. In Punjab, India, the rice-wheat cycle has pushed aquifers to the brink. We built TerraLoop to give every farmer a data-driven path to resilience."

### Slide 2: The Core Problem (Visible from Space)
- **Header:** The Double Crisis: Vanishing Aquifers & Autumn Smoke
- **Data Points:**
  - **-3.85 cm/year:** Groundwater decline detected by NASA GRACE/GRACE-FO across Northwest India.
  - **180 mm:** Evaporative ponding demand of conventional puddled paddy rice.
  - **FIRMS Hotspots:** Over 50,000 seasonal stubble fire detections in Oct–Nov due to tight planting windows.
- **Visual:** Side-by-side satellite images of GRACE Terrestrial Water Storage decline and FIRMS active fire clusters.
- **Presenter Note:** "NASA data doesn't just show climate change—it pinpoints the exact failure points of unsustainable rotations."

### Slide 3: What TerraLoop Does
- **Header:** End-to-End Decision Support: Pin to Strategy
- **Workflow Architecture:**
  1. **Field Profiler:** Queries NASA POWER, GPM IMERG, SMAP L4, GRACE, NASADEM, and HLS.
  2. **Crop Knowledge Base:** 21 curated crops with phenology, rooting depth, thermal units, and economics.
  3. **Process-Based Simulation:** Daily crop-water balance (AquaCrop-OSPy) and 10-year soil carbon (RothC).
  4. **Multi-Objective Selection:** Optimizes for farmer priorities (Water, Profit, Carbon, Resilience).
- **Visual:** Clean diagram showing satellite data feeding the simulation engine and producing 3 ranked strategies.

### Slide 4: Real Field Results: Sangrur Hero Demo
- **Header:** Validated Impact: Baseline vs Regenerative Alternatives
- **Comparison Table:**
  | Metric | Current Practice (Puddled Rice - Wheat) | Strategy 1 (DSR Rice - Wheat + Mulch - Moong) | Strategy 2 (Maize - Wheat - Moong) |
  |---|---|---|---|
  | **Net Irrigation** | 1,580 mm/yr | **1,190 mm/yr (-24.7%)** | **820 mm/yr (-48.1%)** |
  | **10-Yr Soil Carbon** | -0.85 t C/ha (Degrading) | **+2.10 t C/ha (Building)** | **+1.60 t C/ha (Building)** |
  | **Expected Profit** | ₹88,000 / ha | **₹104,000 / ha (+18%)** | **₹96,000 / ha (+9%)** |
  | **Stubble Burning** | Active (FIRMS detected) | **Zero (In-situ Mulched)** | **Zero (Incorporated)** |
  | **Soil Health Score** | 36 / 100 | **72 / 100** | **68 / 100** |
- **Presenter Note:** "By replacing puddling with Direct-Seeded Rice and introducing summer mung bean, the farmer saves 390 mm of water, halts smoke, and makes 18% higher profit."

### Slide 5: The Science: Process Models Over Black Boxes
- **Header:** Rigorous Biophysical Simulation, Not LLM Guesses
- **Models:**
  - **FAO AquaCrop-OSPy 3.1:** Dynamic canopy expansion, transpiration, and water productivity across 40 years of climate members.
  - **RothC-lite 26.3 Carbon Dynamics:** 5 pools (DPM, RPM, BIO, HUM, IOM) factoring soil temperature, moisture, and clay content.
  - **Nitrogen Mass Balance:** Symbiotic BNF crediting 25 kg N/ha synthetic fertilizer saving to subsequent crops.
  - **USDA-NRCS 5 Principles:** Composite soil health scoring.
- **Presenter Note:** "Every single number has provenance. We never invent agronomic yields or water savings—they are calculated from peer-reviewed equations."

### Slide 6: Farmer-Centric UX & Local Accessibility
- **Header:** Built for Real Farmers: Multilingual & Zero-Latency
- **Features:**
  - **Language Accessibility:** Full English and authentic Punjabi (Gurmukhi) localization.
  - **Precomputed Golden Fields:** Instant zero-network demo performance for key agricultural regions.
  - **Explainable Why-Cards:** Explains *why* each rotation works in plain language with clickable NASA provenance citations.
- **Visual:** Screenshot of the Punjabi interface on mobile viewport showing strategy cards and why-cards.

### Slide 7: Global Scalability & Future Roadmap
- **Header:** From Punjab to the World
- **Scalability:**
  - **Proven Global Generalization:** Tested on Story County, Iowa (Corn-Soy erosion) and Machakos, Kenya (Semi-arid smallholder bean).
  - **Roadmap:** High-resolution ECOSTRESS field stress monitoring, WhatsApp extension bot, and carbon-credit certification.
- **Closing Call to Action:** "TerraLoop: Giving farmers the power of NASA Earth observation to regenerate our planet's soil and water."

---

## 3. NASA Space Apps Challenge Project Page (TASK-S02)

### High-Level Project Summary
TerraLoop is an open-science decision-support system that empowers farmers to transition from water-depleting monocultures to regenerative, climate-resilient crop rotations. By integrating 8 NASA Earth observation products (POWER, GPM IMERG, SMAP, GRACE, NASADEM, FIRMS, HLS, NEX-GDDP-CMIP6) with FAO AquaCrop-OSPy and RothC carbon models, TerraLoop evaluates field-specific climate risks, simulates multi-year rotations, and recommends top-performing strategies aligned with farmer priorities in English and Punjabi.

### Detailed Description
The Green Revolution transformed Northwest India into a national food basket, but decades of intensive puddled rice-wheat cultivation have led to severe unintended consequences:
1. Ground water depletion exceeding 3.5 cm/yr (observed by NASA GRACE),
2. Autumn air pollution from stubble burning (detected by NASA FIRMS),
3. Topsoil carbon depletion below 0.6% organic carbon.

Farmers want to adopt sustainable rotations, but lack localized evidence on which alternatives (such as Direct-Seeded Rice, Maize, Mustard, or Summer Moong) balance water conservation with economic survival.

TerraLoop addresses this challenge through four innovations:
- **Instant Field Report Card:** Users drop a pin anywhere on Earth to view localized NASA agro-climatology (POWER, IMERG), root-zone soil moisture percentiles (SMAP), regional groundwater trends (GRACE), topographic slope (NASADEM), and active burning history (FIRMS).
- **Satellite Crop-History Reconstruction:** Applies Savitzky-Golay filtering and peak prominence detection to Harmonized Landsat-Sentinel (HLS 30 m) NDVI series, automatically inferring past cropping seasons.
- **Calibrated Biophysical Simulation:** Couples AquaCrop-OSPy with RothC-lite and seasonal nitrogen mass balances across a 40-year historical climate ensemble to calculate P10/P50/P90 profit, net irrigation, and 10-year carbon accretion.
- **Priority-Weighted Optimization & Grounded Explainability:** Evaluates rotations using multi-objective Pareto ranking weighted by farmer preferences, generating deterministic why-cards where every number traces to an official NASA DOI.

### NASA Datasets & Services Ingested
1. **NASA POWER Agroclimatology:** Daily Tmax, Tmin, Precip, Solar Radiation, Humidity, Wind (`data/nasa_power.py`).
2. **NASA GPM IMERG V07:** Daily 0.1° precipitation totals and extreme rainfall screening (DOI: 10.5067/GPM/IMERGDF/DAY/07).
3. **NASA SMAP L4:** 9 km Root-Zone Soil Moisture percentiles against 2015–2024 climatology (DOI: 10.5067/K2VT90DE20GV).
4. **NASA GRACE / GRACE-FO Mascons:** 0.5° Terrestrial Water Storage monthly anomalies and linear trends (DOI: 10.5067/TEMSC-3MJ62).
5. **NASA NASADEM:** 30 m Digital Elevation Model slope calculation for RUSLE erosion (DOI: 10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001).
6. **NASA FIRMS:** MODIS / VIIRS active fire detections for crop residue burning (DOI: 10.5067/FIRMS/MODIS).
7. **NASA HLS (HLSL30 / HLSS30):** 30 m Harmonized Landsat Sentinel-2 NDVI phenology (DOI: 10.5067/HLS/HLSL30.002).
8. **NASA NEX-GDDP-CMIP6:** Downscaled climate projections for climate stress testing (DOI: 10.7917/OASIS/NEX-GDDP-CMIP6).

### Open Source Tools & Frameworks
- **Python Backend:** Python 3.11, Pydantic v2, FastAPI, AquaCrop-OSPy 3.1, NumPy, Pandas, Scipy algorithms in pure NumPy.
- **Frontend:** Next.js 16 (Turbopack), React 19, TypeScript, Tailwind CSS, Lucide Icons, Custom i18n engine.
- **Data & Soil Grids:** Google Earth Engine Python API, ISRIC SoilGrids 2.0 REST API.

---

## 4. Deployment Guide (TASK-S00)

### Frontend (Vercel)
1. Import repository into [Vercel](https://vercel.com).
2. Set Root Directory to `apps/web`.
3. Set Environment Variable:
   ```env
   NEXT_PUBLIC_API_URL=https://your-terraloop-api.onrender.com
   ```
4. Deploy! The frontend builds statically and serves all golden profiles offline with instant response time.

### Backend (Render / Cloud Run)
1. Connect repository to [Render](https://render.com) as a Web Service or build with Docker.
2. Build Command: `uv sync`
3. Start Command: `uv run uvicorn terraloop_api.main:app --host 0.0.0.0 --port $PORT --app-dir apps/api`
4. Set Environment Variables:
   ```env
   TERRALOOP_CACHE_DIR=/opt/render/project/src/data/cache
   GEE_PROJECT=your-gcp-project-id  # Optional, golden fields are cached
   ```
