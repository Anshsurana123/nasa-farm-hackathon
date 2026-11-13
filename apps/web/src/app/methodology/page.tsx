"use client";

import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/i18n";
import {
  AlertTriangle,
  ArrowLeft,
  FlaskConical,
  Satellite,
  ShieldCheck,
} from "lucide-react";

export default function MethodologyPage() {
  const { t } = useI18n();
  return (
    <AppShell
      pageStep="REF"
      pageBadge="TECHNICAL SPECIFICATION // REV 2026.10 · NASA EARTH OBSERVATION & PROCESS MODELS"
      pageTitle={t("methodology.pageTitle")}
      pageDescription={t("methodology.pageDesc")}
      headerActions={
        <Link
          href="/"
          className="px-4 py-2.5 rounded-xl bg-surface-2 hover:bg-surface border border-line text-foreground font-mono text-xs font-bold flex items-center gap-2 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5 text-emerald-400" />
          <span>{t("methodology.returnBtn")}</span>
        </Link>
      }
    >
      <div className="space-y-8">
        {/* 1. NASA Datasets Registry */}
        <section className="glass rounded-2xl border border-line overflow-hidden reticle-frame">
          <div className="instrument-header px-6 py-3.5 flex items-center justify-between">
            <h2 className="font-display text-sm font-bold uppercase tracking-wider flex items-center gap-2">
              <Satellite className="w-4 h-4 text-emerald-400" />
              <span>{t("methodology.sec01")}</span>
            </h2>
            <span className="text-[10px] font-mono text-muted">GEE · NASA POWER · EARTHDATA</span>
          </div>

          <div className="p-6 overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-line text-muted font-mono text-[10px] uppercase tracking-wider">
                  <th className="py-2.5 pr-4">Dataset</th>
                  <th className="py-2.5 pr-4">Product ID / Collection</th>
                  <th className="py-2.5 pr-4">Resolution</th>
                  <th className="py-2.5 pr-4">Role in Decision Engine</th>
                  <th className="py-2.5">DOI / Citation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line font-mono text-[11px]">
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">NASA POWER</td>
                  <td className="py-3 pr-4 text-muted">Daily Agroclimatology (AG)</td>
                  <td className="py-3 pr-4">0.5° × 0.625°, Daily</td>
                  <td className="py-3 pr-4 font-sans">
                    Tmax, Tmin, Radiation, Rain → Hargreaves ET₀, GDD, FAO-56 daily water balance weather
                  </td>
                  <td className="py-3 text-cyan-400">power.larc.nasa.gov</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">NASA GPM IMERG</td>
                  <td className="py-3 pr-4 text-muted">GPM_L3/IMERG_V07</td>
                  <td className="py-3 pr-4">0.1°, Daily (2000–2024)</td>
                  <td className="py-3 pr-4 font-sans">
                    Rainfall totals, monsoon distribution, dry spells, RUSLE R-factor
                  </td>
                  <td className="py-3">10.5067/GPM/IMERGDF/DAY/07</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">NASA SMAP</td>
                  <td className="py-3 pr-4 text-muted">SPL4SMGP V008 (L4 Root-Zone)</td>
                  <td className="py-3 pr-4">9 km, Daily (2015–present)</td>
                  <td className="py-3 pr-4 font-sans">
                    12 monthly root-zone soil moisture percentiles (drought suitability modifier &amp; live dry-spell diagnostics; daily depletion modeled via FAO-56)
                  </td>
                  <td className="py-3">10.5067/K2VT90DE20GV</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">
                    NASA GRACE / GRACE-FO
                  </td>
                  <td className="py-3 pr-4 text-muted">JPL Tellus Mascon RL06 V04 CRI</td>
                  <td className="py-3 pr-4">0.5° (native 3°), Monthly</td>
                  <td className="py-3 pr-4 font-sans">
                    Regional groundwater decline rate (cm/yr) weighted into irrigation &amp; water-stress penalties
                  </td>
                  <td className="py-3">10.5067/TEMSC-3MJ62</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">NASA NASADEM</td>
                  <td className="py-3 pr-4 text-muted">NASADEM_HGT/001</td>
                  <td className="py-3 pr-4">30 m Elevation</td>
                  <td className="py-3 pr-4 font-sans">
                    Field slope (%) for RUSLE topographic LS-factor &amp; 3D Pedon tilt
                  </td>
                  <td className="py-3">10.5067/MEaSUREs/NASADEM.001</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">NASA FIRMS</td>
                  <td className="py-3 pr-4 text-muted">MODIS / VIIRS Active Fire</td>
                  <td className="py-3 pr-4">375 m / 1 km</td>
                  <td className="py-3 pr-4 font-sans">
                    Detection of Oct–Nov crop residue burning to flag status-quo residue management baseline
                  </td>
                  <td className="py-3">10.5067/FIRMS/MODIS</td>
                </tr>
                <tr>
                  <td className="py-3 pr-4 font-sans font-semibold text-foreground">NASA HLS</td>
                  <td className="py-3 pr-4 text-muted">HLSL30 / HLSS30 (Landsat + S2)</td>
                  <td className="py-3 pr-4">30 m, 2–3 day</td>
                  <td className="py-3 pr-4 font-sans">
                    Savitzky-Golay smoothed NDVI → baseline seasonal crop classification &amp; context history
                  </td>
                  <td className="py-3">10.5067/HLS/HLSL30.002</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* 2. Process Models */}
        <section className="glass rounded-2xl border border-line overflow-hidden">
          <div className="instrument-header px-6 py-3.5 flex items-center justify-between">
            <h2 className="font-display text-sm font-bold uppercase tracking-wider flex items-center gap-2">
              <FlaskConical className="w-4 h-4 text-amber-400" />
              <span>{t("methodology.sec02")}</span>
            </h2>
          </div>

          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-emerald-400">
                01 // FAO-56 / FAO-33 Soil-Water Balance
              </h3>
              <p className="text-muted leading-relaxed">
                Daily root-zone moisture depletion (TAW, RAW, Ks), evapotranspiration (ETc / ETa),
                and thermal heat stress simulation. Calibrated against PAU trials: puddled paddy
                rice requires 175 mm land-soaking and 3.5 mm/day plough-pan percolation; Direct-Seeded
                Rice (DSR) + AWD uses 75 mm pre-sowing wetting and 2.55 mm/day percolation on loam,
                saving 24–28% irrigation water.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-cyan-400">
                02 // RothC-lite 26.3 Carbon Model
              </h3>
              <p className="text-muted leading-relaxed">
                5 soil carbon pools (DPM, RPM, BIO, HUM, IOM) following Coleman &amp; Jenkinson
                (1996) and Falloon et al. (1998). Simulates 10-year SOC trajectory as modified by
                soil temperature, moisture, clay content, and vegetative cover. Residue retention
                adds active DPM/RPM inputs; stubble burning reduces carbon retention to ~10% ash.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-amber-400">
                03 // Nitrogen Mass Balance
              </h3>
              <p className="text-muted leading-relaxed">
                Seasonal N mass balance factoring synthetic fertilizer input, symbiotic biological
                nitrogen fixation (BNF) by grain and cover legumes, atmospheric deposition (10 kg
                N/ha/yr), and grain harvest removal. Preceding legumes credit 25 kg N/ha synthetic
                fertilizer reduction to successor crops.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-stone-400">
                04 // 5 USDA-NRCS Soil Health Principles
              </h3>
              <p className="text-muted leading-relaxed">
                Composite 0–100 index mapping rotation practices onto: (1) Minimise disturbance,
                (2) Maximise soil cover, (3) Maximise living roots, (4) Maximise biodiversity
                (Shannon botanical index), and (5) Integrate livestock/green manure, combined with
                10-year SOC trajectory and RUSLE soil erosion score.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-emerald-400">
                05 // RUSLE Soil Erosion Screen
              </h3>
              <p className="text-muted leading-relaxed">
                Revised Universal Soil Loss Equation (A = R·K·LS·C·P) using Renard rainfall
                erosivity (R), Williams (1995) topsoil erodibility (K), NASADEM 30 m slope
                length/steepness (LS), and rotation-specific canopy cover (C).
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/60 border border-line space-y-2">
              <h3 className="font-mono font-bold text-xs uppercase text-cyan-400">
                06 // Regional Agro-Economics
              </h3>
              <p className="text-muted leading-relaxed">
                Gross margins calculated from official Commission for Agricultural Costs and Prices
                (CACP) Minimum Support Prices (MSP), PAU Cost of Cultivation reports, ISU Ag
                Decision Maker, UC Davis Cost Studies, and Tegemeo/ICRISAT benchmarks.
              </p>
            </div>
          </div>
        </section>

        {/* 3. Climate Safeguards */}
        <section className="glass rounded-2xl border border-line overflow-hidden">
          <div className="instrument-header px-6 py-3.5">
            <h2 className="font-display text-sm font-bold uppercase tracking-wider flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>{t("methodology.sec03")}</span>
            </h2>
          </div>
          <div className="p-6 space-y-3 text-xs text-muted leading-relaxed prose-measure">
            <p>
              <strong className="text-foreground">Wheat Terminal Heat Stress:</strong> High
              temperatures (&gt;32 °C) during wheat grain-fill (1 March to 15 April) deactivate
              starch synthase and shorten duration, reducing yields by ~1.8% per degree-day above 32 °C. TerraLoop
              explicitly tracks average days exceeding this threshold and models -1.0 °C canopy cooling from Happy Seeder mulch.
            </p>
            <p>
              <strong className="text-foreground">Precipitation Trend Safeguard:</strong> Satellite
              reanalysis series may feature artificial decadal shifts. TerraLoop enforces a strict
              filter on automated trend advisory notes: only trends between 10% and 30% are
              reported; spurious step-change anomalies (&gt;30%) are suppressed.
            </p>
          </div>
        </section>

        {/* 4. Limitations */}
        <section className="rounded-2xl p-6 border border-amber-500/35 bg-amber-500/10 space-y-3">
          <h2 className="font-mono text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>{t("methodology.sec04")}</span>
          </h2>
          <ul className="list-disc list-inside space-y-1.5 text-xs text-foreground/85 prose-measure">
            <li>
              NASA POWER resolution is ~50 km; micro-climatic terrain variations are not captured.
            </li>
            <li>
              NASA SMAP (9 km) and GRACE (~300 km native) provide regional hydro-climatic context
              rather than sub-field resolution.
            </li>
            <li>
              Soil properties derive from ISRIC SoilGrids 250 m digital soil mapping; local
              laboratory soil tests should override modeled values when available.
            </li>
            <li>
              Simulated yields assume recommended standard fertilizer application and disease
              control guidelines.
            </li>
          </ul>
        </section>
      </div>
    </AppShell>
  );
}
