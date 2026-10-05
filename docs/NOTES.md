# NOTES.md: Findings, gotchas, decisions

Agents: append findings here (newest at top). Include date, what you saw, and what you decided.

---

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
