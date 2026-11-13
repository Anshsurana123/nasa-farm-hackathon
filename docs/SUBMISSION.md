# NASA Space Apps Challenge 2026: Official Submission Package

**Project Name:** TerraLoop ⟳  
**Challenge:** Crop Rotations Planned with NASA Earth Observations  
**Geographic Focus:** India (15 ICAR Agro-Climatic Zones — Hero Story: Sangrur & Ludhiana, Punjab)  
**Live Demo:** Precomputed offline-ready for 6 Indian Benchmark Fields (`sangrur`, `ludhiana`, `bathinda`, `vidarbha`, `bundelkhand`, `thanjavur`)

---

## 1. 30-Second Video Storyboard & Script (TASK-S01)

> **Format:** 30 seconds, 1080p 16:9, English narration with English, Hindi & Punjabi subtitles.

| Timestamp | Visual Shot | Audio Narration | On-Screen Graphic & Evidence |
|---|---|---|---|
| **00:00 – 00:06** | **Hook:** NASA GRACE Regional TWS anomaly map zoomed over NW India showing crimson aquifer drawdown, overlaid with NASA FIRMS Oct–Nov stubble fire hotspots across Punjab. | *"From space, NASA satellites observe Northwest India's regional water storage dropping 3.8 centimeters every year, while post-harvest fields burn in a tight 11-day sowing window."* | **Signal:** NASA GRACE (-3.85 cm/yr Regional TWS) + NASA FIRMS (Stubble fires). Text: *Punjab's Aquifers & Air Are Under Siege.* |
| **00:06 – 00:12** | **Diagnosis:** User selects Sangrur hero field on TerraLoop map (or enters their Govt Soil Health Card lab values). Field Report Card detects intensive Rice–Wheat monoculture. | *"Select any Indian field—or enter your Government Soil Health Card. TerraLoop decodes satellite phenology, soil water holding capacity, and terminal heat stress."* | **Signal:** NASA HLS 30 m NDVI + NASA POWER + ISRIC / Govt SHC override. |
| **00:12 – 00:20** | **Decision Engine:** Farmer toggles `/Acre (Killa)` mode and sets priorities in Punjabi, Hindi, or English. The FAO-56 root-zone water balance & RothC engine simulates multi-season rotations. | *"Switch to Per-Acre (Killa) units in Punjabi or Hindi. TerraLoop simulates rotations through an FAO-56 daily root-zone soil water balance and RothC carbon model."* | **Action:** Priority Sliders in Punjabi (ਪਾਣੀ ਦੀ ਬੱਚਤ, ਮਿੱਟੀ ਸਿਹਤ, ਘੱਟ ਮਜ਼ਦੂਰੀ) → FAO-56 Root-Zone & RothC simulation. |
| **00:20 – 00:26** | **Actionable Strategy:** Side-by-side strategy cards compare Puddled Rice–Wheat vs Strategy 1 (DSR Rice ➔ Sunflower ➔ Summer Moong), Strategy 2 (Maize ➔ Sunflower ➔ Summer Moong), and Strategy 3 (Mung bean ➔ Wheat ➔ Blackgram). | *"Recommended rotations cut irrigation by 18% to 60%, expand the Kharif-to-Rabi turnaround window from 11 to 26–34 days to eliminate burning, save 3.5 to 4.1 bags of Urea per hectare, and unlock Diversification & Conservation Tillage subsidies."* | **Results:** 💧 -18% to -60% Irrigation · ⏱️ 26–34 Day Turnaround (Zero Burn) · 🧪 3.5–4.1 Urea Bags Saved · 🏛️ Govt Scheme Matched. |
| **00:26 – 00:30** | **Pan-India Outro:** Montage pans across all 6 Indian agro-climatic zones (Punjab, Vidarbha Cotton-Tur, Bundelkhand Pulses, Cauvery Delta Rice-Urad). | *"TerraLoop: Turning NASA Earth observations into profitable, burn-free, water-saving crop rotations for Indian farmers."* | **Logo:** TerraLoop ⟳ · Powered by 8 NASA Earth Data Collections · Space Apps 2026. |

---

## 2. 7-Slide Pitch Deck (TASK-S03)

### Slide 1: Title & The Vision
- **Header:** TerraLoop ⟳
- **Subheader:** Adaptive Crop-Rotation Decision Support for Indian Farmers with NASA Earth Observations
- **Visual:** High-resolution satellite view of the Indo-Gangetic Plains and Peninsular India overlaid with NASA GRACE regional water storage vectors and ICAR Agro-Climatic Zones.
- **Key Takeaway:** Turning NASA satellite observations into grounded, KVK-ready crop rotations measured in farmer-native units (`/Acre (Killa)`, 45-kg Urea bags saved, borewell pumping hours saved, and Kharif-to-Rabi turnaround days).

### Slide 2: The Core Problem (Visible from Space)
- **Header:** The Triple Crisis: Vanishing Aquifers, 11-Day Stubble Fires & March Terminal Heat
- **Data Points:**
  - **-3.85 cm/year:** Regional Terrestrial Water Storage (TWS) decline detected by NASA GRACE/GRACE-FO across Northwest India.
  - **11-Day Window:** Late-maturing puddled rice (`Pusa-44`, 126 field days) harvested late October leaves only 11 days before optimal wheat sowing (Nov 15), forcing stubble burning detected by NASA FIRMS.
  - **-16.7% Yield Loss:** Unmulched Rabi wheat suffers severe grain-filling loss during `+4.5°C` March terminal heatwaves (`Tmax > 32°C`), buffered to **-10.8%** under Happy Seeder residue mulch.

### Slide 3: What TerraLoop Does
- **Header:** End-to-End Decision Support: Pin to KVK Field Prescription
- **Workflow Architecture:**
  1. **Field Profiler & SHC Override:** Combines NASA POWER, GPM IMERG, SMAP L4, GRACE, NASADEM, FIRMS, and HLS with optional **Government of India Soil Health Card (SHC)** lab overrides (`pH`, `OC %`, `Available N/P/K`).
  2. **23-Crop Indian Knowledge Base:** Curated ICAR/PAU parameters including Short-Duration Rice (`PR-126`), DSR Rice, Sunflower, Urad, Groundnut, Tur, Gram, Mustard, Cotton, Soybean, and Millets with state-level CACP 2024–25 MSP vs. mandi price volatility across Punjab, Haryana, UP, Maharashtra, and Tamil Nadu.
  3. **Coupled Process Simulation:** Daily FAO-56 / FAO-33 root-zone water balance (`TAW`/`RAW`, `Dr`, `Ks`, percolation, reproductive heat sterilization) + 10-year RothC-26.3 soil carbon & symbiotic N mass balance.
  4. **6-Objective Optimization:** Evaluates profit, irrigation savings, soil health, climate downside risk ($CVaR_{10}$), low labour constraints, and nutritional food security (`food_security`).

### Slide 4: Reproducible Engine Results (`scripts/run_validation_benchmarks.py`)
- **Header:** Verified Impact Across Sangrur Hero Field (All Engine-Computed, Zero Hardcoded Numbers)
- **Comparison Table (from `data/golden/sangrur/recommendations.json` & `docs/BENCHMARKS.md`):**
  | Metric | Baseline (`Puddled Rice ➔ Wheat`) | Rank #1 (`DSR Rice ➔ Sunflower ➔ Moong`) | Rank #2 (`Maize ➔ Sunflower ➔ Moong`) | Rank #3 (`Moong ➔ Wheat ➔ Blackgram`) |
  |---|---|---|---|---|
  | **Net Irrigation** | 1,168 mm/yr | **962 mm/yr (-17.6% H₂O)** | **466 mm/yr (-60.1% H₂O)** | **584 mm/yr (-50.0% H₂O)** |
  | **Borewell Savings** | Baseline | **3 Irrigations / 113 Pump Hrs/ha saved** | **9 Irrigations / 386 Pump Hrs/ha saved** | **8 Irrigations / 321 Pump Hrs/ha saved** |
  | **Kharif→Rabi Window** | 11 days (High Burn Risk) | **26 days (Happy Seeder Window)** | **34 days (Zero Burning Needed)** | **34 days (Zero Burning Needed)** |
  | **10-Yr Soil Carbon** | -1.92 t C/ha | **+3.01 t C/ha (+4.93 t C/ha vs Base)** | **+3.29 t C/ha (+5.21 t C/ha vs Base)** | **+1.42 t C/ha (+3.34 t C/ha vs Base)** |
  | **45-kg Urea Saved** | 0 bags | **3.5 bags/ha (1.4 bags/acre)** | **3.5 bags/ha (1.4 bags/acre)** | **4.1 bags/ha (1.7 bags/acre)** |
  | **Median Net Profit** | ₹1,70,334 /ha (₹68,932 /acre) | **₹2,71,978 /ha (₹1,10,066 /acre)** | **₹2,30,542 /ha (₹93,297 /acre)** | **₹2,14,188 /ha (₹86,679 /acre)** |

### Slide 5: Scientific Integrity & Provenance
- **Header:** Transparent Provenance & Reproducible Benchmarks
- **Highlights:**
  - **Every Number Has Provenance (`mode: "observed"` vs `"regional_climatology"` vs `"unknown"`):** Provenance badges display clickable DOIs, live GEE observation status, and an explicit UI fallback banner when offline/regional climatology is active.
  - **Soil Texture & Mulch Physics:** Rainfed wheat yields `1.29 t/ha` on Coarse Loamy Sand vs `2.30 t/ha` on Alluvial Loam; Happy Seeder residue mulch (`residue_retained`) cuts soil evaporation by 10% and buffers `+4.5°C` March heatwave yield loss from `-16.7%` to `-10.8%`.
  - **Reproducible Benchmark Script:** Anyone can run `uv run python scripts/run_validation_benchmarks.py --write-docs` offline to verify every table in `docs/BENCHMARKS.md`.

### Slide 6: Built for Real Indian Farmers
- **Header:** Killa/Acre Units, Government Schemes & Trilingual Advisory
- **Features:**
  - **1-Click `/Acre (Killa)` vs `/Ha` Toggle:** Translates all financial margins, Urea bags, and pumping hours into farmer-native units (`1 ha = 2.47105 acres`).
  - **Government Scheme Matcher:** Automatically links rotations to *Mera Pani Meri Virasat* (`₹17,500/ha`), *CRM Happy Seeder Subsidy* (`50–80%`), *NFSM / NAFED e-Samridhi Pulses*, and *NMEO-Oilseeds*.
  - **English, Hindi (`हिन्दी`) & Punjabi (`ਪੰਜਾਬੀ`):** Localized UI and native engine-generated Why-Cards & KVK narrative advisories.

### Slide 7: Pan-India Coverage Across 6 Benchmark Agro-Climatic Zones
- **Header:** Tailored for India's Diverse Agro-Ecology
- **6 Golden Fields Ready Offline:**
  1. **Sangrur, Punjab:** Trans-Gangetic Plains (Sweet-water over-exploited tube-well zone).
  2. **Ludhiana, Punjab:** Central Alluvial Plains (PAU benchmark).
  3. **Bathinda, Punjab:** South-Western Semi-Arid Cotton & Brackish-Water Belt.
  4. **Yavatmal (Vidarbha), Maharashtra:** Central Plateau Rainfed Vertisol Cotton–Soybean–Tur Belt.
  5. **Jhansi (Bundelkhand), Uttar Pradesh:** Semi-Arid Pulse–Oilseed Belt.
  6. **Thanjavur (Cauvery Delta), Tamil Nadu:** Southern Coastal Alluvial Rice–Urad Pulse Relay Belt.

---

## 3. Reproducibility & Verification Commands

```powershell
uv run pytest -q -m "not network"                          # Offline unit & biophysical tests
uv run ruff check .                                        # Zero lint errors
uv run python scripts/precompute_golden.py                 # Rebuild all 6 Indian golden fields + sync to web
uv run python scripts/run_validation_benchmarks.py --write-docs  # Regenerate docs/BENCHMARKS.md from engine
cd apps/web; npm run build                                 # Verify Next.js production build
```
