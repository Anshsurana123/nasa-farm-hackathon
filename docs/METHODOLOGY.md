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

## To document when implemented
AquaCrop setup & calibration (M02/M03) · RothC-lite (M05) · N balance (M06) · Soil Health Score weights (M07) · Economics (M08) · Scenario ensembles & bias correction (C01/C02) · Risk metrics (O02).

## Known limitations (state these openly on the project page)
- NASA POWER is ~50 km resolution; field-level microclimate is not captured.
- SMAP (9 km) and GRACE (~300 km native) give regional context, not field-scale values.
- SoilGrids is modelled; farmer soil tests override it when provided.
- Crop parameters are literature defaults pending calibration.
