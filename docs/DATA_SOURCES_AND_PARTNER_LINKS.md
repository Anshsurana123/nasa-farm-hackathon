# TerraLoop: Complete Data Sources, Partner Links & Attribution Registry

This document catalogs every **NASA Earth Observation dataset**, **Space Agency Partner API**, **peer-reviewed biophysical model**, **national/international agricultural & statistical portal**, **map tile/elevation service**, **open-source software component**, and **internal data artifact** used in **TerraLoop**.

> **Open-Source License:** TerraLoop is licensed under the canonical OSI [**MIT License**](../LICENSE) (`Copyright (c) 2026 TerraLoop Contributors`), also declared in root [`pyproject.toml`](../pyproject.toml), workspace package manifests, and [`apps/web/package.json`](../apps/web/package.json).

---

## Link Verification Methodology

Every primary external link in Sections 1 and 2 passed a **3-pass verification audit**:
1. **Codebase & Knowledge-Base Audit:** Cross-referenced against [`docs/DATASETS.md`](DATASETS.md), `packages/engine/`, `packages/crop-kb/`, `data/benchmarks/*.csv`, and `apps/web/src/`.
2. **DOI Handle & Registry Resolution:** Queried via `https://doi.org/api/handles/...` (`responseCode: 1`) and official agency portals. Stale/404 repository links were updated (SMAP L4 V007 `10.5067/K2VT90DE20GV` → SMAP L4 `SPL4SMGP V008` `https://doi.org/10.5067/T5RUATAQREF8`; HLS S30 → `https://doi.org/10.5067/HLS/HLSS30.002`; NEX-GDDP-CMIP6 → `https://www.nccs.nasa.gov/data-collections/nex-gddp-cmip6/`).
3. **Live HTTP Reachability Check:** Verified live HTTP `200` (or `DOI OK [1]` handle resolution). Two Wiley/ACSESS peer-reviewed journal DOIs (`#13` and `#14` in Section 2B) resolve cleanly at `doi.org` (`DOI OK [1]`) and load in desktop browsers while returning `403` to automated `curl` requests due to publisher bot filtering.

---

## 1. NASA Data & Earth Observation Resources (12 Verified Links)

| # | Resource Name (`Link Text`) | Product / Collection | Resolution | Role in TerraLoop (`Module`) | Verified Link (`Link Url`) |
|---:|---|---|---|---|---|
| 1 | NASA POWER Agroclimatology API (MERRA-2 Climate & Radiation) | REST `temporal/daily/point` (`AG`) | `0.5° × 0.625°`, daily (1981+) | Daily `Tmax/Tmin`, rain, solar radiation, RH, wind → Penman–Monteith ET0, GDD, climate blocks (`data/nasa_power.py`) | https://power.larc.nasa.gov/ |
| 2 | NASA GPM IMERG V07 Final Precipitation (`NASA/GPM_L3/IMERG_V07`) | `NASA/GPM_L3/IMERG_V07` | `0.1°`, 30-min → daily | Homogeneous precipitation, dry-spell duration, heavy rain (`>50 mm`), RUSLE $R$ (`data/gee.py::imerg_daily`) | https://doi.org/10.5067/GPM/IMERG/3B-HH/07 |
| 3 | NASA SMAP Level-4 Root-Zone Soil Moisture (`SPL4SMGP V008`) | `NASA/SMAP/SPL4SMGP/008` | `9 km`, 3-hourly | Monthly root-zone soil moisture percentiles & suitability scaling (`data/gee.py::smap_rootzone`) | https://doi.org/10.5067/T5RUATAQREF8 |
| 4 | NASA GRACE / GRACE-FO Tellus Mascon RL06 Groundwater Anomaly | `NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI` | `~0.5°` grid (`~3°` mascon), monthly | Aquifer TWS decline rate (`cm/yr`) → dynamically scales `water_savings` optimization priority (`data/gee.py::grace_trend`) | https://doi.org/10.5067/TEMSC-3MJ62 |
| 5 | NASA NASADEM 30m Digital Elevation Model (`NASADEM_HGT v001`) | `NASA/NASADEM_HGT/001` | `30 m` | Terrain elevation & slope % → RUSLE $LS$ erosion factor (`data/gee.py::slope_pct`) | https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001 |
| 6 | NASA FIRMS Active Fire Data (MODIS & VIIRS Stubble Burning) | MODIS / VIIRS active thermal hotspots | `375 m – 1 km` | Oct–Nov crop-residue burning detection affecting baseline SOC & Soil Health (`data/gee.py::fire_detections`) | https://firms.modaps.eosdis.nasa.gov/ |
| 7 | NASA HLS Landsat 30m Surface Reflectance (`HLSL30 v002`) | `NASA/HLS/HLSL30/v002` | `30 m`, 2–3 day composite | 3-year NDVI phenology extraction for baseline rotation classification (`data/gee.py::ndvi_timeseries`) | https://doi.org/10.5067/HLS/HLSL30.002 |
| 8 | NASA HLS Sentinel-2 30m Surface Reflectance (`HLSS30 v002`) | `NASA/HLS/HLSS30/v002` | `30 m`, 2–3 day composite | Gap-filled high-cadence NDVI phenology across Kharif/Rabi/Zaid (`data/gee.py::ndvi_timeseries`) | https://doi.org/10.5067/HLS/HLSS30.002 |
| 9 | NASA NEX-GDDP-CMIP6 Downscaled Climate Projections (SSP2-4.5 & SSP5-8.5) | `NASA/GDDP-CMIP6` | `0.25°`, daily (2015–2100) | 5 bias-corrected GCM scenarios (2030s & 2050s stress lab) (`data/gee.py::cmip6_daily`, `climate/ensembles.py`) | https://www.nccs.nasa.gov/data-collections/nex-gddp-cmip6/ |
| 10 | NASA GIBS WMTS Overlays (SMAP L4, MODIS NDVI & VIIRS True Color) | WMTS `EPSG:3857` tiles | `250 m – 9 km` | Visual **context-only** orbital map overlays in the UI (`apps/web/src/components/FieldMap.tsx`) | https://nasa-gibs.github.io/gibs-api-docs/ |
| 11 | NASA SRTM Elevation Dataset (via Meteomatics 90m Terrain Fusion) | SRTM `elevation:m` | `90 m` | Elevation/slope fallback when NASADEM GEE is unavailable (`data/meteomatics.py`) | https://www.earthdata.nasa.gov/data/instruments/srtm |
| 12 | NASA Earthdata Search & Catalog Portal | EOSDIS Catalog | Global | Primary metadata discovery & EOSDIS provenance verification | https://www.earthdata.nasa.gov/ |

---

## 2. Space Agency Partner & Other Data, Science, Policy & Tools (52 Verified Links)

### 2A. Space Agency Partners, Soil Grids & Environmental APIs (#1–#10)

| # | Resource Name (`Link Text`) | Role in TerraLoop | Verified Link (`Link Url`) |
|---:|---|---|---|
| 1 | ESA WorldCereal 10m Active Cropland & Crop Classification | Active temporary cropland, maize & seasonal cereal priors (`data/gee.py::worldcereal_priors`) | https://doi.org/10.5281/zenodo.7875105 |
| 2 | Meteomatics Weather & Microclimate API (90m MIX & Daily Forecast) | 90m daily observations, 7-day `/tactical-advisory`, sub-hourly `precip_30min` (`data/meteomatics.py`) | https://www.meteomatics.com/en/api/getting-started/ |
| 3 | Meteomatics 4-Layer Soil Hydrology & Moisture Deficit API | 4-depth soil moisture (`-5/-15/-50/-150 cm`) & `initial_depletion_mm` (`models/fao56_runner.py`) | https://www.meteomatics.com/en/api/available-parameters/soil-parameters/ |
| 4 | Meteomatics Agricultural Biotic, Drought & Fire-Hazard API | Potato blight, leaf wetness, hail, Fosberg fire index & drought hazard screening (`suitability.py`) | https://www.meteomatics.com/en/api/available-parameters/agricultural-parameters/ |
| 5 | Meteomatics CMIP6 Climate Projections API (MRI-ESM2.0) | `source=mri-esm2` 6th CMIP6 ensemble member & zero-GEE climate fallback (`climate/ensembles.py`) | https://www.meteomatics.com/en/api/available-parameters/climate-data/ |
| 6 | ISRIC SoilGrids 2.0 (250m Global Soil Properties REST API) | 250m depth-weighted clay, sand, silt, SOC, pH, bulk density, CEC & N (`data/soilgrids.py`) | https://soilgrids.org/ |
| 7 | ISRIC SoilGrids 2.0 Scientific Paper (Poggio et al. 2021) | Peer-reviewed SoilGrids 2.0 uncertainty & depth-interval methodology | https://doi.org/10.5194/soil-7-217-2021 |
| 8 | Google Earth Engine (Cloud Earth Observation Processing Platform) | Cloud geospatial execution platform for 8 satellite/EO streams (`data/gee.py`) | https://earthengine.google.com/ |
| 9 | Koppen-Geiger Global Climate Classification Maps (Beck et al. 2023) | Global 0.5° Agro-Ecological Zone biomes & synthetic normals (`region_registry.py`) | https://www.gloh2o.org/koppen/ |
| 10 | Natural Earth Vector Country & Admin-1 Boundaries (GeoJSON) | Admin-0 sovereign borders & Admin-1 province boundary lookup (`packages/crop-kb/regions/`) | https://www.naturalearthdata.com/ |

### 2B. Peer-Reviewed Biophysical & Agronomic Literature (#11–#14)

| # | Resource Name (`Link Text`) | Role in TerraLoop | Verified Link (`Link Url`) |
|---:|---|---|---|
| 11 | FAO Irrigation & Drainage Paper 56 (Crop Evapotranspiration Model) | Penman–Monteith ET0, Dual-$K_c$, TAW/RAW water stress (`models/agroclimate.py`, `fao56_runner.py`) | https://www.fao.org/4/x0490e/x0490e00.htm |
| 12 | RothC-26.3 Soil Organic Carbon Turnover Model (Coleman & Jenkinson 1996) | 10-year 5-pool (`DPM/RPM/BIO/HUM/IOM`) SOC dynamics (`models/soil_health.py`) | https://doi.org/10.1007/978-3-642-61094-3_17 |
| 13 | Saxton & Rawls (2006) Soil Water Hydraulic Characteristics | Texture + SOC pedotransfer equations for FC & WP (`models/soil.py`) *(DOI OK; Wiley blocks `curl` bots)* | https://doi.org/10.2136/sssaj2005.0117 |
| 14 | Ambika & Mishra (2019) IGP Irrigation Cooling Bias in MERRA-2 | 12-month IGP `Tmax` bias-correction curve (`data/nasa_power.py`) *(DOI OK; Wiley blocks `curl` bots)* | https://doi.org/10.1029/2019GL084367 |

### 2C. Nutrition Databases, Indian Soil/Statistics Agencies & Support Schemes (#15–#30)

| # | Resource Name (`Link Text`) | Role in TerraLoop | Verified Link (`Link Url`) |
|---:|---|---|---|
| 15 | USDA FoodData Central (Crop Energy & Protein Nutrition Database) | Global crop nutritional energy (`kcal/100g`) & protein (`g/100g`) reference (`models/nutrition.py`) | https://fdc.nal.usda.gov/ |
| 16 | ICMR-National Institute of Nutrition (Indian RDA & Food Composition) | 5-member household RDA & Indian crop nutrition lookup (`models/nutrition.py`) | https://www.nin.res.in/ |
| 17 | Government of India Soil Health Card Portal (Lab Override Standard) | Field lab test override specification (`pH`, `SOC %`, `N`, `P`, `K` kg/ha) | https://soilhealth.dac.gov.in/ |
| 18 | Commission for Agricultural Costs and Prices (CACP India Budgets & MSP) | State A2+FL cultivation cost schedules & MSP pricing (`packages/crop-kb/economics/*.yaml`) | https://cacp.da.gov.in/ |
| 19 | India Unified Portal for Agricultural Statistics (UPAg / DES APY Yields) | Official Indian crop production & yield baseline portal | https://www.upag.gov.in/ |
| 20 | DES Ministry of Agriculture Data Portal (India District Crop Statistics) | District-level area/production/yield reference data (`data/benchmarks/district_ground_truth.csv`) | https://data.desagri.gov.in/ |
| 21 | ICAR-NBSS&LUP National Bureau of Soil Survey & Land Use Planning | Indian 17-zone agro-climatic & regional soil baselines (`packages/crop-kb/regions/zones.yaml`) | https://icar-nbsslup.org.in/ |
| 22 | India-WRIS / Central Ground Water Board (CGWB Groundwater Reference) | In-situ aquifer depletion cross-validation against NASA GRACE-FO mascons | https://www.indiawris.gov.in/ |
| 23 | ICRISAT District Level Database & Semi-Arid Tropics Research | Semi-arid Indian district yield & pulse agronomic ground truth | https://www.icrisat.org/ |
| 24 | Department of Fertilizers India (PM-PRANAM Bio-Fertilizer Scheme) | Central fertilizer-reduction & organic/natural incentive metadata (`schemes/central.yaml`) | https://fert.gov.in/ |
| 25 | NAFED India (e-Samridhi Pulses MSP Procurement) | NFSM-Pulses / e-Samridhi MSP procurement support matching (`schemes/central.yaml`) | https://www.nafed-india.com/ |
| 26 | National Mission on Edible Oils - Oilseeds (NMEO-Oilseeds) | Oilseed diversification & quality-seed incentive metadata (`schemes/central.yaml`) | https://nmeo.dac.gov.in/ |
| 27 | Department of Agriculture Punjab (DSR & Residue Management Schemes) | Punjab DSR subsidy & Crop Residue Management / Happy Seeder scheme data (`schemes/punjab.yaml`) | https://agri.punjab.gov.in/ |
| 28 | Haryana Agriculture Department (Mera Pani Meri Virasat / Fasal) | Haryana paddy-diversification incentive metadata (`schemes/haryana.yaml`) | https://fasal.haryana.gov.in/ |
| 29 | Maharashtra PoCRA Climate-Resilient Agriculture Project | Vidarbha/Marathwada climate-resilient & broad-bed furrow incentives (`schemes/maharashtra.yaml`) | https://mahapocra.gov.in/ |
| 30 | TNAU Agritech Portal (Tamil Nadu & Cauvery Delta Crop Reference) | Rice-fallow pulse & water-conservation agronomic reference (`schemes/tamil_nadu.yaml`) | https://agritech.tnau.ac.in/ |

### 2D. Global Breadbasket Agencies & International Conservation Programs (#31–#42)

| # | Resource Name (`Link Text`) | Role in TerraLoop | Verified Link (`Link Url`) |
|---:|---|---|---|
| 31 | USDA NASS Quick Stats (US Corn Belt Yield Benchmarks) | Story County, Iowa corn, soybean & oat ground-truth yields (`data/benchmarks/global_ground_truth.csv`) | https://quickstats.nass.usda.gov/ |
| 32 | Agreste Statistique Agricole Annuelle (France Beauce Yields) | Eure-et-Loir wheat, rapeseed/colza & barley yields (`global_ground_truth.csv`) | https://agreste.agriculture.gouv.fr/ |
| 33 | ARVALIS Institut du Vegetal (France Cereal & Oilseed Economics) | French arable rotation & gross-margin benchmark reference (`economics/france.yaml`) | https://www.arvalis.fr/ |
| 34 | European Commission Common Agricultural Policy (EU CAP Eco-Schemes) | EU crop diversification & legume support schemes (`schemes/eu_cap.yaml`) | https://agriculture.ec.europa.eu/common-agricultural-policy_en |
| 35 | IBGE SIDRA Table 5457 PAM (Brazil Sorriso Municipal Yields) | Mato Grosso soybean & *safrinha* maize municipal yield validation (`global_ground_truth.csv`) | https://sidra.ibge.gov.br/tabela/5457 |
| 36 | IMEA Instituto Mato-grossense de Economia Agropecuaria (Brazil Budgets) | Mato Grosso cost-of-production & farm-gate revenue schedules (`economics/brazil_mt.yaml`) | https://www.imea.com.br/ |
| 37 | Brazil Ministry of Agriculture Plano ABC+ (Low-Carbon Agriculture) | Low-carbon integration & ZARC risk-zoning scheme data (`schemes/brazil.yaml`) | https://www.gov.br/agricultura/pt-br/assuntos/sustentabilidade/planoabc-abcmais |
| 38 | GRDC Grains Research & Development Corporation (Australia) | Riverina break-crop & dryland wheat economic/agronomic guidance (`schemes/australia.yaml`) | https://grdc.com.au/ |
| 39 | Australian Clean Energy Regulator (ACCU Soil Carbon Scheme) | Soil carbon sequestration incentive metadata (`schemes/australia.yaml`) | https://cer.gov.au/ |
| 40 | Kenya Agricultural and Livestock Research Organization (KALRO) | Nakuru highland maize & common bean economics & benchmarks (`economics/kenya.yaml`) | https://kalro.org/ |
| 41 | Kenya National Bureau of Statistics (KNBS Crop Production Data) | Nakuru County agricultural survey yield validation (`global_ground_truth.csv`) | https://www.knbs.or.ke/ |
| 42 | National Potato Council of Kenya (NPCK Potato Benchmarks) | Kenyan highland *Shangi* Irish potato target yield benchmarks (`global_ground_truth.csv`) | https://npck.org/ |

### 2E. Geospatial Basemaps, Elevation Tiles, Source Repository & Stack (#43–#52)

| # | Resource Name (`Link Text`) | Role in TerraLoop | Verified Link (`Link Url`) |
|---:|---|---|---|
| 43 | Esri World Imagery Basemap Tiles | Satellite parcel-drawing basemap in `FieldMap.tsx` | https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9 |
| 44 | OpenStreetMap & Nominatim Geocoding Service | Street map tiles & global coordinate/place geocoding (`/geocode` API & `FieldMap.tsx`) | https://www.openstreetmap.org/ |
| 45 | AWS Open Data Terrain Tiles (Mapzen Terrarium 3D Elevation) | Interactive 3D terrain extrusion in `FieldMap.tsx` | https://registry.opendata.aws/terrain-tiles/ |
| 46 | TerraLoop Open-Source GitHub Repository (Codebase & Benchmarks) | Complete source code, YAML knowledge base, precomputed golden fixtures & 124 offline tests | https://github.com/Anshsurana123/nasa-farm-hackathon |
| 47 | Next.js Web Framework & React UI Platform | 7-route trilingual web application & `/api` proxy (`apps/web/`) | https://nextjs.org/ |
| 48 | MapLibre GL JS (Open-Source 3D Geospatial Mapping) | Interactive 3D vector/raster web GIS parcel explorer (`FieldMap.tsx`) | https://maplibre.org/ |
| 49 | FastAPI Web Framework | High-performance async REST & OpenAPI backend (`apps/api/`) | https://fastapi.tiangolo.com/ |
| 50 | Python Scientific Stack (NumPy, pandas, Pydantic, PyYAML) | Vectorized FAO-56/RothC/NSGA-II simulation, Pydantic v2 contracts & YAML knowledge loading | https://www.python.org/ |
| 51 | Google Gemini API (Grounded Trilingual Explanation Synthesis) | Optional LLM farmer-brief narrative polish gated by `verify_llm_numeric_grounding` | https://ai.google.dev/ |
| 52 | Canva Presentation Design & Visual Assets | Project visual slide elements & infographic assets | https://www.canva.com/ |

---

## 3. Additional Source Citations Noted in CSV/YAML Comments

The following agency/publication URLs also appear inside raw repository comments, CSV ground-truth citation columns, or scheme files, and were excluded from the verified live-HTTP list above because automated checks returned timeouts, DNS errors, or bot blocks during external validation (their live equivalent portals are included in Section 2):

- **India Benchmarks & Schemes:** `https://esopb.gov.in/static/PDF/StatisticalAbstract2023.pdf` (`data/benchmarks/district_ground_truth.csv`), `https://aps.dac.gov.in/APY/Public_Report1.aspx` (`district_ground_truth.csv`), `https://des.tn.gov.in/season-and-crop-report` (`district_ground_truth.csv`), `https://agrimachinery.nic.in/` (`schemes/central.yaml`, `schemes/punjab.yaml`), `https://upagripardarshi.gov.in/` (`schemes/uttar_pradesh.yaml`), `https://krishi.maharashtra.gov.in/` (`schemes/maharashtra.yaml`), `https://tnhorticulture.tn.gov.in/` (`schemes/tamil_nadu.yaml`), `https://www.pau.edu/` (`docs/DATASETS.md`).
- **Global Benchmarks & Schemes:** `https://www.extension.iastate.edu/agdm/crops/html/a1-12.html` (`global_ground_truth.csv`), `https://www.nrcs.usda.gov/...` (`schemes/us_usda.yaml`), `https://agriculture.gouv.fr/` (`schemes/eu_cap.yaml`), `https://www.conab.gov.br/` (`docs/DATASETS.md`), `https://www.agriculture.gov.au/abares/...` (`global_ground_truth.csv`), `https://kilimo.go.ke/` & `https://www.ncpb.co.ke/` (`schemes/kenya.yaml`).

---

## 4. Complete Internal Repository Data & Knowledge Base Inventory

All domain parameters, regional boundaries, ground-truth validation fixtures, and precomputed demo snapshots are open, human-readable files in this repository:

| Category | Directory / File | Contents & Scale |
|---|---|---|
| **Crop Specifications** | [`packages/crop-kb/crops/`](../packages/crop-kb/crops/) | **40 crop YAML configs** + `_template.yaml`: `alfalfa`, `barley`, `basmati`, `berseem`, `brachiaria_cover`, `cassava`, `chickpea`, `common_bean`, `cotton`, `crimson_clover_vetch`, `dhaincha`, `faba_bean`, `field_pea`, `groundnut`, `lentil`, `lupin`, `maize`, `moong`, `mustard`, `oats`, `pearl_millet`, `pigeon_pea`, `potato`, `rapeseed_canola`, `rice_dsr`, `rice_japonica_temperate`, `rice_puddled`, `rice_short`, `rice_upland`, `rye_winter`, `sorghum`, `soybean`, `sugar_beet`, `sunflower`, `sweet_potato`, `triticale`, `urad`, `wheat`, `wheat_spring`, `wheat_winter`. |
| **AquaCrop Overrides** | [`packages/crop-kb/aquacrop_params/`](../packages/crop-kb/aquacrop_params/) | **21 YAML files** supplying calibrated canopy, root, water-productivity & salinity parameters for pulses, oilseeds, millets, covers, tubers, and upland/temperate cereals. |
| **Regional Economics** | [`packages/crop-kb/economics/`](../packages/crop-kb/economics/) | **10 enterprise cost/MSP budget YAMLs**: 5 Indian states (`punjab`, `haryana`, `uttar_pradesh`, `maharashtra`, `tamil_nadu`) + 5 global breadbasket hubs (`usa_iowa`, `france`, `brazil_mt`, `kenya`, `australia_nsw`). |
| **Support & Conservation Schemes** | [`packages/crop-kb/schemes/`](../packages/crop-kb/schemes/) | **11 YAML files (26 total schemes)**: `central` (4), `punjab` (3), `uttar_pradesh` (4), `maharashtra` (2), `tamil_nadu` (2), `haryana` (1), `us_usda` (2), `eu_cap` (2), `brazil` (2), `kenya` (2), `australia` (2). |
| **Agro-Ecological Regions & Calendars** | [`packages/crop-kb/regions/`](../packages/crop-kb/regions/) | **8 registry files**: `india_states.geojson` (36 States/UTs), `global_countries.geojson`, `global_admin1.geojson`, `aez_global_grid.json` (0.5° Köppen–Geiger AEZ grid), `zones.yaml`, `calendars.yaml` (NH/SH seasons), `soils.yaml`, `synthetic_weather.yaml`. |
| **Empirical Ground-Truth Benchmarks** | [`data/benchmarks/`](../data/benchmarks/) | **2 validation tables**: `district_ground_truth.csv` (9 Indian district crop-regime benchmarks) and `global_ground_truth.csv` (14 held-out 5-continent breadbasket crop-hub benchmarks; 13.0% MAPE). |
| **Precomputed Golden Fields** | [`data/golden/`](../data/golden/) *(mirrored to [`apps/web/public/golden/`](../apps/web/public/golden/))* | **11 precomputed field bundles** (`profile.json`, `recommendations.json`, `weather.json`): 6 India (`sangrur`, `ludhiana`, `bathinda`, `bundelkhand`, `vidarbha`, `thanjavur`) + 5 global (`us_corn_belt`, `eu_maritime_west`, `brazil_cerrado`, `east_africa_highlands`, `australia_wheat_belt`), plus `fields.json`, `gee_audit_log.json`, and `precompute.log`. |
| **UI Localization** | [`apps/web/src/i18n/`](../apps/web/src/i18n/) | **6 JSON translation bundles**: English (`en`), Hindi (`hi`), Punjabi (`pa`), Spanish (`es`), French (`fr`), and Portuguese (`pt`). |

---

## 5. Space Apps Submission Portal Note (25-Link UI Cap)

The NASA Space Apps Challenge submission portal enforces a **maximum of 25 rows** in the **Space Agency Partner & Other Data** field (`NASA Data *` accepts all 12 entries). If populating that web form directly, all 64 resources remain documented here via our GitHub repository link, while the portal's 25 partner slots can prioritize the 10 partner/soil/climate entries (`#1–#10`), core science papers (`#11–#14`), nutrition & national soil/statistics portals (`#15–#19`), Esri/OSM/AWS tiles (`#43–#45`), and core software/repository links (`#46–#52`) depending on whether regional agency portals or technical stack attribution are emphasized.
