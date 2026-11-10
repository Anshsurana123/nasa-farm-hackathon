# NOTES.md: Findings, gotchas, decisions

Agents: append findings here (newest at top). Include date, what you saw, and what you decided.

---

### 2026-11-06: Fact-check audit & 8-point scientific resolution
1. **March–April Tmax bias & GPM IMERG rainfall homogeneity:** Extended `apply_igp_irrigation_bias_correction` to a full 12-month lookup (`_IGP_MONTHLY_TMAX_BIAS_C`, including March `-4.5 °C` and Feb `-2.5 °C`) cited against IMD Climatological Normals (1991–2020) and ERA5-Land; removed pre-2001 `PRECTOTCORR` rescaling in `nasa_power.py` and switched `profiler.summarise_climate` to use GPM IMERG (2001–2024) for rainfall statistics and trends. Irrigated Sangrur wheat median now lands at `5.16 t/ha` (within `1.6%` of the `5.08 t/ha` DES Sangrur district average).
2. **Live Google Earth Engine precomputation & honest offline fallbacks:** Precomputed all 6 Indian golden fields against live GEE (`GEE_PROJECT=<your-gee-project-id>`, `mode: "observed"` across all 8 NASA collections). Removed fabricated FIRMS fire dates and synthetic Gaussian NDVI curves when GEE is offline (`residue_burning_detected: None`, `crop_history: []`, `mode: "unknown"`).
3. **FAO-56 / FAO-33 naming & PAU rice water-saving calibration:** Replaced `"AquaCrop"` references with `"FAO-56 / FAO-33 Soil-Water Balance"`; calibrated `rice_puddled` (175 mm puddling, 3.5 mm/d percolation), `rice_short` PR-126 (`21.6%` water saved from 22 fewer field days), and `rice_dsr` + AWD (75 mm pre-sowing *rauni* wetting, 2.55 mm/d percolation, `27.5%` water saved).
4. **CACP A2+FL economics, MSP procurement ranking & Soil Health breakdown:** Updated `punjab.yaml` to full CACP 2024–25 A2+FL cost of cultivation (`rice_puddled: ₹64,500/ha`, `wheat: ₹48,500/ha`), wired `procurement_type` and `market_risk` into candidate evaluation and multi-objective ranking, added `soil_health_breakdown` (`5 × 15 pt` NRCS sub-scores + modifiers), and renamed `docs/VALIDATION.md` to `docs/BENCHMARKS.md` with DES/ICRISAT ground-truth comparisons and a CI reproducibility check.

### 2026-10-05: NASA POWER data quality at Punjab (→ TASK-D11, top priority)
Observed for Ludhiana (30.82 N, 75.68 E), POWER daily 1985–2024:
- **Tmax warm bias:** monthly mean Tmax May 42.2 °C, Jun 42.8 °C, Jul 38.9 °C. Typical station normals for
  Ludhiana are roughly 39–40 / 38–39 / 34 °C. That's a ~3–4 °C warm bias in the hot season (likely because the
  reanalysis lacks the cooling effect of heavy irrigation). Result: "heat days > 35 °C" ≈ 140–190/yr, far too high.
- **Rainfall inhomogeneity:** annual totals avg ~520 mm in 1985–2004 but 750–1000+ mm in 2013–2024
  (2023: 1397 mm, a flood year). Station climatology for Ludhiana is ~700–750 mm/yr. Baseline-vs-recent
  comparison gives an artificial "+48%" trend.
- **Decision:** `profiler.TREND_NOTES_ENABLED = False`, so no trend claims in the UI until D11 is done.
  The numbers are still computed and returned.
- **D11 plan:**
  1. Use **GPM IMERG (2001+)** for rainfall statistics and any rainfall trend (D03).
  2. Replace the absolute 35 °C heat metric with crop-stage metrics that are robust to bias,
     e.g. *wheat terminal heat* = days with Tmax > 32 °C during 1 Mar–15 Apr, and report the **change** only
     within one homogeneous source/period.
  3. Optionally bias-correct POWER Tmax by month using published station normals (document source),
     or compare against MODIS LST (MOD11A2) for a sanity check.
  4. Re-enable trend notes and add a test that asserts no note claims a >30% rainfall change for Ludhiana.
- These biases also affect AquaCrop inputs (TASK-M02): calibrate/validate yields before trusting absolute numbers.

### 2026-10-05: SoilGrids masks urban pixels
Ludhiana city centre (30.90, 75.85) returns `null` for all properties. `soilgrids.fetch_topsoil` now searches
offsets up to ~3 km. Golden field coordinates were moved to rural locations; still **verify on imagery** (D10).

### 2026-10-05: Rotation constraint decision
Same botanical family back-to-back (maize → wheat) is allowed; only same-crop repeats and explicit
`bad_predecessors` are hard constraints. Family diversity is scored in the soil health score (M07).
