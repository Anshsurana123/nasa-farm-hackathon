# DATASETS.md: Data registry

Every dataset used by TerraLoop. **Rule:** a dataset must be listed here (with ID + DOI/URL)
before code uses it. Status: ✅ integrated · ⬜ planned.

## NASA Earth observations
| Status | Dataset | Product / GEE collection | Resolution | Used for | Code | DOI / URL |
|---|---|---|---|---|---|---|
| ✅ | NASA POWER Agroclimatology | REST `temporal/daily/point`, community `AG` | 0.5°×0.625°, daily, 1981+ | Tmax/Tmin, rain, radiation, RH, wind → climate summary, ET0, GDD, AquaCrop weather | `data/nasa_power.py` | https://power.larc.nasa.gov/ |
| ✅ | GPM IMERG V07 | `NASA/GPM_L3/IMERG_V07` | 0.1°, 30-min → daily | Rainfall, extremes, RUSLE R | `data/gee.py::imerg_daily` | 10.5067/GPM/IMERG/3B-HH/07 |
| ✅ | SMAP L4 Soil Moisture | `NASA/SMAP/SPL4SMGP/008` | 9 km, 3-hourly | Root-zone moisture percentiles, drought | `gee.smap_rootzone` | 10.5067/K2VT90DE20GV |
| ✅ | GRACE / GRACE-FO mascons | `NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI` | ~0.5° (native ~3°) monthly | Groundwater/TWS trend | `gee.grace_trend` | 10.5067/TEMSC-3MJ62 |
| ✅ | NASADEM | `NASA/NASADEM_HGT/001` | 30 m | Slope → RUSLE LS | `gee.slope_pct` | 10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001 |
| ✅ | FIRMS active fire | `FIRMS` (MODIS/VIIRS) | 375 m–1 km | Residue burning detection | `gee.fire_detections` | https://firms.modaps.eosdis.nasa.gov/ |
| ✅ | HLS Landsat 30 m | `NASA/HLS/HLSL30/v002` | 30 m | NDVI time series → crop history | `gee.ndvi_timeseries` | 10.5067/HLS/HLSL30.002 |
| ✅ | HLS Sentinel-2 30 m | `NASA/HLS/HLSS30/v002` | 30 m | NDVI time series → crop history | `gee.ndvi_timeseries` | 10.5067/HLS/HLSL30.002 |
| ✅ | NEX-GDDP-CMIP6 | `NASA/GDDP-CMIP6` | 0.25°, daily | Future climate scenarios (SSP2-4.5 / SSP5-8.5, 2030s & 2050s) | `gee.cmip6_daily`, `climate/ensembles.py` | 10.7917/OASIS/NEX-GDDP-CMIP6 |
| ⬜ | GLDAS Noah 2.1 | `NASA/GLDAS/V021/NOAH/G025/T3H` | 0.25° | Gap-filling soil moisture/runoff | n/a | 10.5067/E7TYRXPJKWOQ |
| ⬜ | MODIS ET | `MODIS/061/MOD16A2` | 500 m, 8-day | ET context / validation | n/a | 10.5067/MODIS/MOD16A2.061 |
| ⬜ | ECOSTRESS ET/ESI | via AppEEARS / earthaccess | 70 m | Within-field stress (could-have) | n/a | LP DAAC |
| ⬜ | NASA GIBS | WMTS tiles | n/a | Map imagery layers in UI | `apps/web` | https://nasa-gibs.github.io/gibs-api-docs/ |

> DOIs marked "verify" must be confirmed on the dataset landing page (NASA Earthdata / GEE catalog) before submission.

## Non-NASA (credited)
| Status | Dataset | Used for | Code | Reference |
|---|---|---|---|---|
| ✅ | ISRIC SoilGrids 2.0 (250 m) | Topsoil texture, SOC, pH, BD, CEC, N | `data/soilgrids.py` | 10.5194/soil-7-217-2021 |
| ✅ | ESA WorldCereal 10 m | Active cropland mask & crop-type phenology reference | `eo/phenology.py`, `eo/classifier.py` | https://esa-worldcereal.org/ |
| ⬜ | USDA Cropland Data Layer | Crop labels (Iowa) | E03 | https://nassgeodata.gmu.edu/CropScape/ |
| ✅ | DES / ICRISAT District Level Database | District yield ground-truth validation (6 Indian districts) | `data/benchmarks/district_ground_truth.csv`, `scripts/run_validation_benchmarks.py` | http://data.icrisat.org/dld/ |
| ✅ | CGWB / India-WRIS well levels | GRACE-FO groundwater trend cross-validation | `data/gee.py::grace_trend` | https://indiawris.gov.in/ |
| ✅ | FAO-56 / FAO-33 tables | Dual Kc, root depth, depletion fraction $p$, yield-response $K_y$ | `packages/crop-kb/crops/*.yaml`, `models/fao56_runner.py` | FAO Irrigation & Drainage Papers 56 & 33 |
| ✅ | PAU Package of Practices & CACP MSP | Crop calendars, Happy Seeder / DSR practices & state CACP 2024–25 budgets | `packages/crop-kb/crops/*.yaml`, `packages/crop-kb/economics/*.yaml` | https://www.pau.edu/ · https://cacp.dacnet.nic.in/ |

## Sponsor APIs (NASA Space Apps Promoted)
| Status | Dataset | Parameters / Product | Resolution | Used for | Code | Reference |
|---|---|---|---|---|---|---|
| ✅ | Meteomatics Weather & Microclimate (EURO1k / MIX) | `t_max_2m_24h:C`, `t_min_2m_24h:C`, `precip_24h:mm`, `precip_30min:mm`, `prob_precip_24h:p`, `global_rad_24h:Wh`, `relative_humidity_2m:p`, `wind_speed_2m:ms`, `evapotranspiration_24h:mm`, `elevation:m` (NASA SRTM 90m) | 90 m, daily / sub-hourly | Recent observation fusion, 7-day tactical farm advisory, `TASK-M04` RUSLE kinetic $EI_{30}$, SRTM slope fallback | `data/meteomatics.py`, `models/rusle.py` | https://www.meteomatics.com/en/api/getting-started/ |
| ✅ | Meteomatics 4-Layer Soil Hydrology | `soil_moisture_deficit:mm`, `soil_moisture_index_-5cm/-15cm/-50cm/-150cm:idx`, `volumetric_soil_water_-5cm/-15cm/-50cm/-150cm:m3m3`, `t_-5cm:C` | 90 m, daily | Initial FAO-56 root-zone depletion ($D_{r,0}$) and 5 cm seedbed sowing readiness | `data/meteomatics.py`, `models/fao56_runner.py` | https://www.meteomatics.com/en/api/available-parameters/soil-parameters/ |
| ✅ | Meteomatics Agro-Hazards & Extreme Events | `phytophthora_negative:idx`, `leaf_wetness:idx`, `hail_24h:cm`, `fosberg_fire_weather_index:idx`, `drought_index:idx` | 90 m, daily | Biotic blight/fungal screening, hailstorm risk, turnaround fire-weather danger | `data/meteomatics.py`, `suitability.py` | https://www.meteomatics.com/en/api/available-parameters/agricultural-parameters/ |
| ✅ | Meteomatics CMIP6 Climate Scenarios | `source=mri-esm2` (historical + SSP1-2.6/2-4.5/3-7.0/4-6.0/5-8.5, `MRI-ESM2.0`) | 90 m, daily (1995–2100) | 6th CMIP6 ensemble member and zero-GEE REST fallback for climate runs | `data/meteomatics.py`, `climate/ensembles.py` | https://www.meteomatics.com/en/api/available-parameters/climate-data/ |
