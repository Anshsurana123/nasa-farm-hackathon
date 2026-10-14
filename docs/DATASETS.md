# DATASETS.md: Data registry

Every dataset used by TerraLoop. **Rule:** a dataset must be listed here (with ID + DOI/URL)
before code uses it. Status: ✅ integrated · ⬜ planned.

## NASA Earth observations
| Status | Dataset | Product / GEE collection | Resolution | Used for | Code | DOI / URL |
|---|---|---|---|---|---|---|
| ✅ | NASA POWER Agroclimatology | REST `temporal/daily/point`, community `AG` | 0.5°×0.625°, daily, 1981+ | Tmax/Tmin, rain, radiation, RH, wind → climate summary, ET0, GDD, AquaCrop weather | `data/nasa_power.py` | https://power.larc.nasa.gov/ |
| ✅ | GPM IMERG V07 | `NASA/GPM_L3/IMERG_V07` | 0.1°, 30-min → daily | Rainfall, extremes, RUSLE R | `data/gee.py::imerg_daily` | 10.5067/GPM/IMERG/3B-HH/07 |
| ✅ | SMAP L4 Soil Moisture | `NASA/SMAP/SPL4SMGP/007` | 9 km, 3-hourly | Root-zone moisture percentiles, drought | `gee.smap_rootzone` | 10.5067/K2VT90DE20GV |
| ✅ | GRACE / GRACE-FO mascons | `NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI` | ~0.5° (native ~3°) monthly | Groundwater/TWS trend | `gee.grace_trend` | 10.5067/TEMSC-3MJ62 |
| ✅ | NASADEM | `NASA/NASADEM_HGT/001` | 30 m | Slope → RUSLE LS | `gee.slope_pct` | 10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001 |
| ✅ | FIRMS active fire | `FIRMS` (MODIS/VIIRS) | 375 m–1 km | Residue burning detection | `gee.fire_detections` | https://firms.modaps.eosdis.nasa.gov/ |
| ✅ | HLS Landsat 30 m | `NASA/HLS/HLSL30/v002` | 30 m | NDVI time series → crop history | `gee.ndvi_timeseries` | 10.5067/HLS/HLSL30.002 |
| ✅ | HLS Sentinel-2 30 m | `NASA/HLS/HLSS30/v002` | 30 m | NDVI time series → crop history | `gee.ndvi_timeseries` | 10.5067/HLS/HLSL30.002 |
| ⬜ | MODIS NDVI | `MODIS/061/MOD13Q1` | 250 m, 16-day | Long-history phenology fallback (2000+) | `gee.ndvi_timeseries` | 10.5067/MODIS/MOD13Q1.061 |
| ⬜ | NEX-GDDP-CMIP6 | `NASA/GDDP-CMIP6` | 0.25°, daily | Future climate scenarios | `gee.cmip6_daily` | 10.7917/OASIS/NEX-GDDP-CMIP6 |
| ⬜ | GLDAS Noah 2.1 | `NASA/GLDAS/V021/NOAH/G025/T3H` | 0.25° | Gap-filling soil moisture/runoff | n/a | 10.5067/E7TYRXPJKWOQ |
| ⬜ | MODIS ET | `MODIS/061/MOD16A2` | 500 m, 8-day | ET context / validation | n/a | 10.5067/MODIS/MOD16A2.061 |
| ⬜ | ECOSTRESS ET/ESI | via AppEEARS / earthaccess | 70 m | Within-field stress (could-have) | n/a | LP DAAC |
| ⬜ | NASA GIBS | WMTS tiles | n/a | Map imagery layers in UI | `apps/web` | https://nasa-gibs.github.io/gibs-api-docs/ |

> DOIs marked "verify" must be confirmed on the dataset landing page (NASA Earthdata / GEE catalog) before submission.

## Non-NASA (credited)
| Status | Dataset | Used for | Code | Reference |
|---|---|---|---|---|
| ✅ | ISRIC SoilGrids 2.0 (250 m) | Topsoil texture, SOC, pH, BD, CEC, N | `data/soilgrids.py` | 10.5194/soil-7-217-2021 |
| ⬜ | ESA WorldCereal | Crop-type validation labels | E02/E03 | https://esa-worldcereal.org/ |
| ⬜ | USDA Cropland Data Layer | Crop labels (Iowa) | E03 | https://nassgeodata.gmu.edu/CropScape/ |
| ⬜ | ICRISAT District Level Database | Punjab yield validation | V01 | http://data.icrisat.org/dld/ |
| ⬜ | CGWB / India-WRIS well levels | GRACE validation | V02 | https://indiawris.gov.in/ |
| ⬜ | FAO-56 tables | Kc, root depth | crop KB | FAO Irrigation & Drainage Paper 56 |
| ⬜ | PAU Package of Practices | Punjab crop calendars & practices | crop KB | https://www.pau.edu/ |
