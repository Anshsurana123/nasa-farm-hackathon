import Link from "next/link";

export default function MethodologyPage() {
  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
      <header className="sticky top-0 z-40 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md border-b border-zinc-200 dark:border-zinc-800">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 font-bold hover:opacity-80 transition-opacity">
            <span className="w-8 h-8 rounded-lg bg-emerald-600 text-white flex items-center justify-center font-black">
              ⟳
            </span>
            <span>TerraLoop</span>
          </Link>
          <div className="flex items-center gap-4 text-xs font-medium">
            <Link href="/" className="text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100">
              ← Back to App
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-10 space-y-10">
        <div>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
            Scientific Documentation
          </span>
          <h1 className="text-3xl font-extrabold mt-2 tracking-tight">
            Methodology &amp; Data Provenance
          </h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-2 max-w-3xl leading-relaxed">
            TerraLoop couples NASA satellite Earth observations with peer-reviewed process-based biophysical
            and soil health models. Every recommendation is grounded in open science and reproducible data.
          </p>
        </div>

        {/* 1. NASA Datasets Registry */}
        <section className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm space-y-4">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <span>🛰️</span> NASA Earth Observation Data Registry
          </h2>
          <p className="text-xs text-zinc-500">
            All satellite observations ingested via Google Earth Engine and NASA REST APIs:
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-zinc-200 dark:border-zinc-800 text-zinc-400 font-semibold">
                  <th className="py-2.5 pr-4">Dataset</th>
                  <th className="py-2.5 pr-4">Product ID / Collection</th>
                  <th className="py-2.5 pr-4">Resolution</th>
                  <th className="py-2.5 pr-4">Role in Decision Engine</th>
                  <th className="py-2.5">DOI / Citation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/60 font-mono text-[11px]">
                <tr>
                  <td className="py-2.5 pr-4 font-sans font-medium text-zinc-900 dark:text-zinc-100">NASA POWER</td>
                  <td className="py-2.5 pr-4 text-zinc-600 dark:text-zinc-400">Daily Agroclimatology (AG)</td>
                  <td className="py-2.5 pr-4">0.5° × 0.625°, Daily</td>
                  <td className="py-2.5 pr-4 font-sans">Tmax, Tmin, Radiation, Rain → Hargreaves ET₀, GDD, AquaCrop weather</td>
                  <td className="py-2.5 text-blue-600 dark:text-blue-400">power.larc.nasa.gov</td>
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 font-sans font-medium text-zinc-900 dark:text-zinc-100">NASA GPM IMERG</td>
                  <td className="py-2.5 pr-4 text-zinc-600 dark:text-zinc-400">GPM_L3/IMERG_V07</td>
                  <td className="py-2.5 pr-4">0.1°, Daily (2000–2024)</td>
                  <td className="py-2.5 pr-4 font-sans">Rainfall totals, monsoon distribution, dry spells, RUSLE R-factor</td>
                  <td className="py-2.5">10.5067/GPM/IMERGDF/DAY/07</td>
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 font-sans font-medium text-zinc-900 dark:text-zinc-100">NASA SMAP</td>
                  <td className="py-2.5 pr-4 text-zinc-600 dark:text-zinc-400">SPL4SMGP (L4 Root-Zone)</td>
                  <td className="py-2.5 pr-4">9 km, Daily (2015–2024)</td>
                  <td className="py-2.5 pr-4 font-sans">12 monthly root-zone soil moisture percentiles vs climatology</td>
                  <td className="py-2.5">10.5067/K2VT90DE20GV</td>
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 font-sans font-medium text-zinc-900 dark:text-zinc-100">NASA GRACE / GRACE-FO</td>
                  <td className="py-2.5 pr-4 text-zinc-600 dark:text-zinc-400">JPL Tellus Mascon RL06 V04 CRI</td>
                  <td className="py-2.5 pr-4">0.5° (native 3°), Monthly</td>
                  <td className="py-2.5 pr-4 font-sans">Regional groundwater decline rate (cm/yr) across NW India / Punjab</td>
                  <td className="py-2.5">10.5067/TEMSC-3MJ62</td>
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 font-sans font-medium text-zinc-900 dark:text-zinc-100">NASA NASADEM</td>
                  <td className="py-2.5 pr-4 text-zinc-600 dark:text-zinc-400">NASADEM_HGT/001</td>
                  <td className="py-2.5 pr-4">30 m Elevation</td>
                  <td className="py-2.5 pr-4 font-sans">Field slope (%) for RUSLE topographic LS-factor</td>
                  <td className="py-2.5">10.5067/MEaSUREs/NASADEM.001</td>
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 font-sans font-medium text-zinc-900 dark:text-zinc-100">NASA FIRMS</td>
                  <td className="py-2.5 pr-4 text-zinc-600 dark:text-zinc-400">MODIS / VIIRS Active Fire</td>
                  <td className="py-2.5 pr-4">375 m / 1 km</td>
                  <td className="py-2.5 pr-4 font-sans">Detection of Oct–Nov crop residue (paddy stubble) burning</td>
                  <td className="py-2.5">10.5067/FIRMS/MODIS</td>
                </tr>
                <tr>
                  <td className="py-2.5 pr-4 font-sans font-medium text-zinc-900 dark:text-zinc-100">NASA HLS</td>
                  <td className="py-2.5 pr-4 text-zinc-600 dark:text-zinc-400">HLSL30 / HLSS30 (Landsat + S2)</td>
                  <td className="py-2.5 pr-4">30 m, 2–3 day</td>
                  <td className="py-2.5 pr-4 font-sans">Savitzky-Golay smoothed NDVI → season peak detection &amp; crop history</td>
                  <td className="py-2.5">10.5067/HLS/HLSL30.002</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* 2. Process Models */}
        <section className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm space-y-6">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <span>🔬</span> Biophysical &amp; Economic Models
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
            <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 space-y-2">
              <h3 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">1. AquaCrop-OSPy 3.1 (FAO)</h3>
              <p className="text-zinc-600 dark:text-zinc-300 leading-relaxed">
                Daily canopy growth, transpiration, and yield simulation. Calibrated for Punjab conditions:
                puddled paddy rice requires 180 mm ponding and 3.0 mm/day deep percolation; Direct-Seeded Rice (DSR)
                eliminates puddling and lowers percolation to 2.3 mm/day, yielding a validated 20–25% irrigation saving.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 space-y-2">
              <h3 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">2. RothC-lite 26.3 Carbon Model</h3>
              <p className="text-zinc-600 dark:text-zinc-300 leading-relaxed">
                5 soil carbon pools (DPM, RPM, BIO, HUM, IOM) following Coleman &amp; Jenkinson (1996) and Falloon et al. (1998).
                Simulates 10-year SOC trajectory as modified by soil temperature, moisture, clay content, and vegetative cover.
                Residue retention adds active DPM/RPM inputs; stubble burning reduces carbon retention to ~10% ash.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 space-y-2">
              <h3 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">3. Nitrogen Mass Balance</h3>
              <p className="text-zinc-600 dark:text-zinc-300 leading-relaxed">
                Seasonal N mass balance factoring synthetic fertilizer input, symbiotic biological nitrogen fixation (BNF)
                by grain and cover legumes, atmospheric deposition (10 kg N/ha/yr), and grain harvest removal. Preceding legumes
                credit 25 kg N/ha synthetic fertilizer reduction to successor crops.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 space-y-2">
              <h3 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">4. 5 USDA-NRCS Soil Health Principles</h3>
              <p className="text-zinc-600 dark:text-zinc-300 leading-relaxed">
                Composite 0–100 index mapping rotation practices onto: (1) Minimise disturbance, (2) Maximise soil cover,
                (3) Maximise living roots, (4) Maximise biodiversity (Shannon botanical index), and (5) Integrate livestock/green manure,
                combined with 10-year SOC trajectory and RUSLE soil erosion score.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 space-y-2">
              <h3 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">5. RUSLE Soil Erosion Screen</h3>
              <p className="text-zinc-600 dark:text-zinc-300 leading-relaxed">
                Revised Universal Soil Loss Equation (A = R·K·LS·C·P) using Renard rainfall erosivity (R), Williams (1995)
                topsoil erodibility (K), NASADEM 30 m slope length/steepness (LS), and rotation-specific canopy cover (C).
              </p>
            </div>

            <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 space-y-2">
              <h3 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">6. Punjab Agro-Economics (CACP &amp; PAU)</h3>
              <p className="text-zinc-600 dark:text-zinc-300 leading-relaxed">
                Gross margins calculated from official Commission for Agricultural Costs and Prices (CACP) Minimum Support Prices (MSP)
                and Punjab Agricultural University (PAU) comprehensive Cost of Cultivation reports (A₂ + FL operational costs).
              </p>
            </div>
          </div>
        </section>

        {/* 3. Climate Safeguards */}
        <section className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm space-y-3">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <span>🛡️</span> Data Quality &amp; Climate Safeguards (TASK-D11)
          </h2>
          <div className="space-y-2 text-xs text-zinc-600 dark:text-zinc-300 leading-relaxed">
            <p>
              <strong>Wheat Terminal Heat Stress:</strong> High temperatures (&gt;32 °C) during wheat grain-fill (1 March to 15 April)
              deactivate starch synthase and shorten duration, reducing yields by 4–8% per degree. TerraLoop explicitly tracks
              average days exceeding this threshold to recommend early-maturing or heat-tolerant cultivars.
            </p>
            <p>
              <strong>Precipitation Trend Safeguard:</strong> Satellite reanalysis series may feature artificial decadal shifts.
              TerraLoop enforces a strict filter on automated trend advisory notes: only trends between 10% and 30% are reported;
              spurious step-change anomalies (&gt;30%) are suppressed.
            </p>
          </div>
        </section>

        {/* 4. Limitations */}
        <section className="bg-amber-50/70 dark:bg-amber-950/20 rounded-2xl p-6 border border-amber-200 dark:border-amber-800/60 space-y-3">
          <h2 className="text-base font-bold text-amber-900 dark:text-amber-200 flex items-center gap-2">
            <span>⚠️</span> Known Limitations &amp; Assumptions
          </h2>
          <ul className="list-disc list-inside space-y-1.5 text-xs text-amber-950/90 dark:text-amber-300/90">
            <li>NASA POWER resolution is ~50 km; micro-climatic terrain variations are not captured.</li>
            <li>NASA SMAP (9 km) and GRACE (~300 km native) provide regional hydro-climatic context rather than sub-field resolution.</li>
            <li>Soil properties derive from ISRIC SoilGrids 250 m digital soil mapping; local laboratory soil tests should override modeled values when available.</li>
            <li>Simulated yields assume recommended standard fertilizer application and disease control guidelines.</li>
          </ul>
        </section>
      </main>
    </div>
  );
}
