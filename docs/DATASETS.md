# DATASETS.md: Data registry

Every dataset used by TerraLoop. **Rule:** a dataset must be listed here (with ID + DOI/URL)
before code uses it. Status: ✅ integrated · ⬜ planned.

> **Full 64-Link Registry & Internal Data Inventory:** See [`docs/DATA_SOURCES_AND_PARTNER_LINKS.md`](DATA_SOURCES_AND_PARTNER_LINKS.md) for the complete 3×-verified catalog of all 12 NASA links, 52 partner/agency/science/software/basemap links, and all `packages/crop-kb/` + `data/` datasets.

## NASA Earth observations
| Status | Dataset | Product / GEE collection | Resolution | Used for | Code | DOI / URL |
|---|---|---|---|---|---|---|
| ✅ | NASA POWER Agroclimatology | REST `temporal/daily/point`, community `AG` | 0.5°×0.625°, daily, 1981+ | Tmax/Tmin, rain, radiation, RH, wind → climate summary, ET0, GDD, AquaCrop weather | `data/nasa_power.py` | https://power.larc.nasa.gov/ |
| ✅ | GPM IMERG V07 | `NASA/GPM_L3/IMERG_V07` | 0.1°, 30-min → daily | Rainfall, extremes, RUSLE R | `data/gee.py::imerg_daily` | https://doi.org/10.5067/GPM/IMERG/3B-HH/07 |
| ✅ | SMAP L4 Soil Moisture | `NASA/SMAP/SPL4SMGP/008` | 9 km, 3-hourly | Root-zone moisture percentiles, drought | `gee.smap_rootzone` | https://doi.org/10.5067/T5RUATAQREF8 |
| ✅ | GRACE / GRACE-FO mascons | `NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI` | ~0.5° (native ~3°) monthly | Groundwater/TWS trend | `gee.grace_trend` | https://doi.org/10.5067/TEMSC-3MJ62 |
| ✅ | NASADEM | `NASA/NASADEM_HGT/001` | 30 m | Slope → RUSLE LS | `gee.slope_pct` | https://doi.org/10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001 |
| ✅ | FIRMS active fire | `FIRMS` (MODIS/VIIRS) | 375 m–1 km | Residue burning detection | `gee.fire_detections` | https://firms.modaps.eosdis.nasa.gov/ |
| ✅ | HLS Landsat 30 m | `NASA/HLS/HLSL30/v002` | 30 m | NDVI time series → crop history | `gee.ndvi_timeseries` | https://doi.org/10.5067/HLS/HLSL30.002 |
| ✅ | HLS Sentinel-2 30 m | `NASA/HLS/HLSS30/v002` | 30 m | NDVI time series → crop history | `gee.ndvi_timeseries` | https://doi.org/10.5067/HLS/HLSS30.002 |
| ✅ | NEX-GDDP-CMIP6 | `NASA/GDDP-CMIP6` | 0.25°, daily | Future climate scenarios (SSP2-4.5 / SSP5-8.5, 2030s & 2050s) | `gee.cmip6_daily`, `climate/ensembles.py` | https://www.nccs.nasa.gov/data-collections/nex-gddp-cmip6/ |
| ✅ | NASA GIBS | WMTS tiles (`SMAP_L4_Analyzed_Root_Zone_Soil_Moisture`, `MODIS_Terra_NDVI_8Day`, `VIIRS_SNPP_CorrectedReflectance_TrueColor`) | 250 m – 9 km (WMTS EPSG:3857) | Interactive context-only map overlay layers in UI | `apps/web/src/components/FieldMap.tsx` | https://nasa-gibs.github.io/gibs-api-docs/ |

> **Scope & 3-Tier Validation Architecture:** Earlier draft candidates (`GLDAS Noah 2.1`, `MODIS/061/MOD16A2`, `ECOSTRESS` via AppEEARS) were intentionally omitted rather than kept as unimplemented placeholders because their roles are covered at higher local fidelity or lower latency by integrated **NASA SMAP L4 (9 km)**, **NASA POWER Penman–Monteith ET0 + FAO-56**, **NASA HLS 30 m NDVI**, and **Meteomatics 90 m hydrology**. Locations resolve through TerraLoop's 3-tier validation hierarchy: (1) `validated_india` (17 Indian ICAR agro-climatic zones + CACP 2024–25 economic budgets + DES/ICRISAT validation), (2) `validated_regional` (5 calibrated global breadbaskets — US Corn Belt, EU Beauce, Brazil Cerrado, Kenya Highlands, Australia Riverina — with cited agency enterprise budgets and held-out yield benchmarks), and (3) `biophysical_global` (backward-compatible API alias `unvalidated_global`, where Köppen-Geiger AEZs + NASA EO + SoilGrids drive full biophysical crop/soil/water simulations with economic ranking disabled to avoid uncalibrated price distortion).

## Non-NASA (credited)
| Status | Dataset | Used for | Code | Reference |
|---|---|---|---|---|
| ✅ | ISRIC SoilGrids 2.0 (250 m) | Topsoil texture, SOC, pH, BD, CEC, N | `data/soilgrids.py` | https://doi.org/10.5194/soil-7-217-2021 |
| ✅ | ESA WorldCereal 10 m (`ESA/WorldCereal/2021/MODELS/v100`) | Active temporary cropland, winter/spring cereals, maize & irrigation classification priors | `data/gee.py::worldcereal_priors`, `eo/phenology.py`, `eo/classifier.py` | https://esa-worldcereal.org/ · https://doi.org/10.5281/zenodo.7875105 |
| ✅ | Natural Earth Vector (110m Countries & 50m Admin-1) | Global Admin-0 sovereign borders & Tier-A Admin-1 state/province polygon lookup | `region_registry.py`, `packages/crop-kb/regions/global_*.geojson` | https://www.naturalearthdata.com/ |
| ✅ | Köppen-Geiger Climate Classification (0.5° Global Grid) | Biome climate archetypes, seasonal calendars, synthetic fallback normals & RothC biome equilibrium baselines | `region_registry.py`, `packages/crop-kb/regions/aez_global_grid.json` | Kottek et al. (2006) https://doi.org/10.1127/0941-2948/2006/0130 · Beck et al. (2023) https://doi.org/10.1038/s41597-023-02549-6 |
| ✅ | DES / ICRISAT District Level Database | District yield ground-truth validation (6 Indian districts) | `data/benchmarks/district_ground_truth.csv`, `scripts/run_validation_benchmarks.py` | https://www.icrisat.org/ · https://data.desagri.gov.in/ · https://www.upag.gov.in/ |
| ✅ | CGWB / India-WRIS well levels | GRACE-FO groundwater trend cross-validation | `data/gee.py::grace_trend` | https://www.indiawris.gov.in/ |
| ✅ | FAO-56 / FAO-33 tables | Dual Kc, root depth, depletion fraction $p$, yield-response $K_y$, vernalization/dormancy curves | `packages/crop-kb/crops/*.yaml`, `models/fao56_runner.py` | https://www.fao.org/4/x0490e/x0490e00.htm |
| ✅ | PAU Package of Practices & CACP MSP | Crop calendars, Happy Seeder / DSR practices & state CACP 2024–25 budgets | `packages/crop-kb/crops/*.yaml`, `packages/crop-kb/economics/*.yaml` | https://agri.punjab.gov.in/ · https://cacp.da.gov.in/ |
| ✅ | USDA NASS / ERS & ISU Ag Decision Maker | US Corn Belt enterprise budgets, county yield validation (Story County IA) & USDA NRCS programs (EQIP/CSP) | `packages/crop-kb/economics/usa_iowa.yaml`, `data/benchmarks/global_ground_truth.csv`, `packages/crop-kb/schemes/us_usda.yaml` | https://quickstats.nass.usda.gov/ |
| ✅ | Agreste SAA / ARVALIS & EU CAP | France Beauce (Eure-et-Loir) enterprise budgets, yield validation & EU CAP Eco-Schemes | `packages/crop-kb/economics/france.yaml`, `data/benchmarks/global_ground_truth.csv`, `packages/crop-kb/schemes/eu_cap.yaml` | https://agreste.agriculture.gouv.fr/ · https://www.arvalis.fr/ · https://agriculture.ec.europa.eu/common-agricultural-policy_en |
| ✅ | IMEA Mato Grosso & IBGE PAM / Plano ABC+ | Brazil Cerrado (Sorriso MT) enterprise budgets, municipal yield validation & Plano ABC+ / ZARC | `packages/crop-kb/economics/brazil_mt.yaml`, `data/benchmarks/global_ground_truth.csv`, `packages/crop-kb/schemes/brazil.yaml` | https://sidra.ibge.gov.br/tabela/5457 · https://www.imea.com.br/ · https://www.gov.br/agricultura/pt-br/assuntos/sustentabilidade/planoabc-abcmais |
| ✅ | GRDC & Australian Clean Energy Regulator | Australia Riverina (Wagga Wagga NSW) winter-crop gross margins, yields & ACCU schemes | `packages/crop-kb/economics/australia_nsw.yaml`, `data/benchmarks/global_ground_truth.csv`, `packages/crop-kb/schemes/australia.yaml` | https://grdc.com.au/ · https://cer.gov.au/ |
| ✅ | KALRO / KNBS & NPCK Kenya | East Africa Highlands (Nakuru KE) budgets, county yields & KCSAP climate-smart incentives | `packages/crop-kb/economics/kenya.yaml`, `data/benchmarks/global_ground_truth.csv`, `packages/crop-kb/schemes/kenya.yaml` | https://kalro.org/ · https://www.knbs.or.ke/ · https://npck.org/ |
| ✅ | USDA FoodData Central / FAO Food Composition | Global crop nutritional energy (kcal/100g) & protein (g/100g) database | `models/nutrition.py` | https://fdc.nal.usda.gov/ |

## Sponsor APIs (NASA Space Apps Promoted)
| Status | Dataset | Parameters / Product | Resolution | Used for | Code | Reference |
|---|---|---|---|---|---|---|
| ✅ | Meteomatics Weather & Microclimate (EURO1k / MIX) | `t_max_2m_24h:C`, `t_min_2m_24h:C`, `precip_24h:mm`, `precip_30min:mm`, `prob_precip_24h:p`, `global_rad_24h:Wh`, `relative_humidity_2m:p`, `wind_speed_2m:ms`, `evapotranspiration_24h:mm`, `elevation:m` (NASA SRTM 90m) | 90 m, daily / sub-hourly | Recent observation fusion, 7-day tactical farm advisory, `TASK-M04` RUSLE kinetic $EI_{30}$, SRTM slope fallback | `data/meteomatics.py`, `models/rusle.py` | https://www.meteomatics.com/en/api/getting-started/ |
| ✅ | Meteomatics 4-Layer Soil Hydrology | `soil_moisture_deficit:mm`, `soil_moisture_index_-5cm/-15cm/-50cm/-150cm:idx`, `volumetric_soil_water_-5cm/-15cm/-50cm/-150cm:m3m3`, `t_-5cm:C` | 90 m, daily | Initial FAO-56 root-zone depletion ($D_{r,0}$) and 5 cm seedbed sowing readiness | `data/meteomatics.py`, `models/fao56_runner.py` | https://www.meteomatics.com/en/api/available-parameters/soil-parameters/ |
| ✅ | Meteomatics Agro-Hazards & Extreme Events | `phytophthora_negative:idx`, `leaf_wetness:idx`, `hail_24h:cm`, `fosberg_fire_weather_index:idx`, `drought_index:idx` | 90 m, daily | Biotic blight/fungal screening, hailstorm risk, turnaround fire-weather danger | `data/meteomatics.py`, `suitability.py` | https://www.meteomatics.com/en/api/available-parameters/agricultural-parameters/ |
| ✅ | Meteomatics CMIP6 Climate Scenarios | `source=mri-esm2` (historical + SSP1-2.6/2-4.5/3-7.0/4-6.0/5-8.5, `MRI-ESM2.0`) | 90 m, daily (1995–2100) | 6th CMIP6 ensemble member and zero-GEE REST fallback for climate runs | `data/meteomatics.py`, `climate/ensembles.py` | https://www.meteomatics.com/en/api/available-parameters/climate-data/ |
