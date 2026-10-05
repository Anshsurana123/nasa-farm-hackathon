"use client";

import { useI18n } from "@/i18n";

export function RotationExplorer({ region }: { region?: string }) {
  const { lang } = useI18n();

  return (
    <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-100 dark:border-zinc-800 pb-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
            Decision Engine
          </span>
          <h3 className="text-xl font-bold text-zinc-900 dark:text-zinc-50">
            {lang === "pa" ? "ਫ਼ਸਲੀ ਚੱਕਰ ਵਿਕਲਪ ਅਤੇ ਅਨੁਕੂਲਨ" : "Rotation Strategies & Optimization"}
          </h3>
        </div>
        <span className="px-3 py-1 rounded-full text-xs font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
          Simulated via AquaCrop & Soil Models
        </span>
      </div>

      {/* Baseline vs Candidate Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Baseline Card */}
        <div className="rounded-xl border-2 border-zinc-200 dark:border-zinc-800 p-4 bg-zinc-50/50 dark:bg-zinc-800/20 relative">
          <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-zinc-200 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300 mb-2">
            Current Baseline
          </span>
          <h4 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">
            Puddled Rice ➔ Wheat ➔ Fallow
          </h4>
          <p className="text-xs text-zinc-500 mt-1">
            Standard 2-season intensive monoculture with Oct residue burning.
          </p>

          <div className="mt-4 space-y-1.5 pt-3 border-t border-zinc-200 dark:border-zinc-700/60 text-xs font-medium">
            <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>Irrigation:</span>
              <span className="font-bold text-rose-600 dark:text-rose-400">~1,600 mm/yr</span>
            </div>
            <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>10-yr SOC Δ:</span>
              <span className="font-bold text-amber-600">-0.8 t/ha</span>
            </div>
            <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>Soil Health Score:</span>
              <span className="font-bold text-zinc-700 dark:text-zinc-300">38 / 100</span>
            </div>
          </div>
        </div>

        {/* Strategy 1: Smarter Rice */}
        <div className="rounded-xl border-2 border-emerald-500/40 dark:border-emerald-500/30 p-4 bg-emerald-50/20 dark:bg-emerald-950/10 relative">
          <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300 mb-2">
            Strategy A · High Adoption
          </span>
          <h4 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">
            DSR Rice (PR-126) ➔ Wheat + Mulch ➔ Moong
          </h4>
          <p className="text-xs text-zinc-500 mt-1">
            Direct-seeded rice saves water; summer mung bean fixes N; zero stubble burning.
          </p>

          <div className="mt-4 space-y-1.5 pt-3 border-t border-emerald-200/60 dark:border-emerald-800/40 text-xs font-medium">
            <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>Water Saving:</span>
              <span className="font-bold text-emerald-600 dark:text-emerald-400">-22% vs baseline</span>
            </div>
            <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>10-yr SOC Δ:</span>
              <span className="font-bold text-emerald-600">+1.9 t/ha</span>
            </div>
            <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>Soil Health Score:</span>
              <span className="font-bold text-emerald-700 dark:text-emerald-300">68 / 100</span>
            </div>
          </div>
        </div>

        {/* Strategy 2: Maize & Legume Diversification */}
        <div className="rounded-xl border-2 border-blue-500/40 dark:border-blue-500/30 p-4 bg-blue-50/20 dark:bg-blue-950/10 relative">
          <span className="inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-blue-100 text-blue-800 dark:bg-blue-900/60 dark:text-blue-300 mb-2">
            Strategy B · Maximum Water Saver
          </span>
          <h4 className="font-bold text-sm text-zinc-900 dark:text-zinc-100">
            Kharif Maize ➔ Wheat / Mustard ➔ Moong
          </h4>
          <p className="text-xs text-zinc-500 mt-1">
            Replaces water-thirsty paddy with cereal-pulse rotation, protecting deep aquifers.
          </p>

          <div className="mt-4 space-y-1.5 pt-3 border-t border-blue-200/60 dark:border-blue-800/40 text-xs font-medium">
            <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>Water Saving:</span>
              <span className="font-bold text-blue-600 dark:text-blue-400">-42% vs baseline</span>
            </div>
            <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>10-yr SOC Δ:</span>
              <span className="font-bold text-emerald-600">+3.1 t/ha</span>
            </div>
            <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
              <span>Soil Health Score:</span>
              <span className="font-bold text-blue-700 dark:text-blue-300">82 / 100</span>
            </div>
          </div>
        </div>
      </div>

      {/* Decision Support Rationale Box */}
      <div className="rounded-xl bg-zinc-50 dark:bg-zinc-800/40 p-4 border border-zinc-200 dark:border-zinc-700 text-xs space-y-2">
        <div className="font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
          <span>🎯</span>
          <span>How Farmer Priorities Drive the Recommendation</span>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed">
          TerraLoop generates thousands of agronomically valid rotations, runs multi-season bio-physical simulations across 40 years of historical weather & future CMIP6 climate projections, and evaluates the Pareto frontier across <strong>Profit</strong>, <strong>Water Savings</strong>, <strong>Soil Health</strong>, and <strong>Climate Downside Risk</strong>.
        </p>
      </div>
    </div>
  );
}
