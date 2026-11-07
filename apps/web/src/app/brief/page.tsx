"use client";

import { useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { AgronomicBrief } from "@/components/AgronomicBrief";
import { useField } from "@/context/FieldContext";
import { fmtMoney, isSouthAsia } from "@/lib/ui";
import {
  BookOpen,
  Coins,
  Droplets,
  Layers,
  Leaf,
  Printer,
  Sliders,
  Sprout,
} from "lucide-react";

export default function BriefPage() {
  const { profile, strategies, selectedField } = useField();
  const [areaHa, setAreaHa] = useState<number>(2.5);
  const [selectedRank, setSelectedRank] = useState<number>(1);

  const isSA = isSouthAsia(selectedField.lat, selectedField.lon);
  const currencySymbol = profile?.currency_symbol ?? (isSA ? "₹" : "$");

  const baseline = strategies.find((s) => s.rank === 0) ?? strategies[0];
  const activeStrategy =
    strategies.find((s) => s.rank === selectedRank) ??
    strategies.find((s) => s.rank === 1) ??
    strategies[1] ??
    baseline;

  const baseRes = baseline?.results[0];
  const activeRes = activeStrategy?.results[0];

  const baseIrrMm = baseRes?.irrigation_mm?.length
    ? Math.round(baseRes.irrigation_mm.reduce((a, b) => a + b, 0) / baseRes.irrigation_mm.length)
    : 1400;
  const activeIrrMm = activeRes?.irrigation_mm?.length
    ? Math.round(
        activeRes.irrigation_mm.reduce((a, b) => a + b, 0) / activeRes.irrigation_mm.length
      )
    : 890;

  // 1 mm over 1 ha = 10 m³ = 10,000 Liters
  const waterSavedMmPerHa = Math.max(0, baseIrrMm - activeIrrMm);
  const totalWaterSavedM3 = Math.round(waterSavedMmPerHa * 10 * areaHa);
  const totalWaterSavedLiters = totalWaterSavedM3 * 1000;

  const profitPerHa = Math.round(activeRes?.profit_p50 ?? 138000);
  const baseProfitPerHa = Math.round(baseRes?.profit_p50 ?? 124000);
  const totalFarmProfit = Math.round(profitPerHa * areaHa);
  const totalProfitDelta = Math.round((profitPerHa - baseProfitPerHa) * areaHa);

  const socDeltaPerHa10Yr = activeRes?.soc_delta_t_ha_10yr ?? 2.1;
  const totalSocTonnes10Yr = +(socDeltaPerHa10Yr * areaHa).toFixed(1);
  const totalCo2eTonnes10Yr = +(totalSocTonnes10Yr * 3.67).toFixed(1);

  const nBalancePerHa = activeRes?.n_balance_kg_ha_yr ?? 42;
  const ureaBagsSavedPerHa = activeStrategy?.practical_metrics?.urea_bags_saved_per_ha ?? 0;
  const totalUreaBagsSavedYr = +(ureaBagsSavedPerHa * areaHa).toFixed(1);
  const totalNSavedKgYr = Math.round(ureaBagsSavedPerHa * 20.7 * areaHa);

  const acres = +(areaHa * 2.47105).toFixed(1);

  return (
    <AppShell
      pageStep="06"
      pageBadge="EXECUTIVE EXTENSION DOSSIER · FARM-SCALE IMPACT CALCULATOR · PRINT-READY PDF"
      pageTitle="Agronomic Advisory Brief & Farm Holding Impact Scaler"
      pageDescription="Scale per-hectare biophysical simulations across your total farm holding (hectares / acres) and generate a print-ready extension dossier with full NASA satellite provenance."
      headerActions={
        <div className="flex flex-wrap items-center gap-2.5 print:hidden">
          <Link
            href="/rotations"
            className="px-3.5 py-2.5 rounded-xl bg-surface-2 hover:bg-surface border border-line text-foreground font-mono text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <Layers className="w-3.5 h-3.5 text-cyan-400" />
            <span>Adjust Rotation</span>
          </Link>
          <Link
            href="/methodology"
            className="px-3.5 py-2.5 rounded-xl bg-surface-2 hover:bg-surface border border-line text-foreground font-mono text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <BookOpen className="w-3.5 h-3.5 text-stone-400" />
            <span>Equations &amp; DOIs</span>
          </Link>
          <button
            type="button"
            onClick={() => window.print()}
            className="px-4 py-2.5 rounded-xl bg-emerald-500 hover:opacity-95 text-slate-950 font-mono text-xs font-bold flex items-center gap-2 shadow-md transition-opacity cursor-pointer"
          >
            <Printer className="w-4 h-4" />
            <span>Print / Save Advisory PDF</span>
          </button>
        </div>
      }
    >
      <div className="space-y-6">
        {/* Interactive Farm Holding Scaler (Hidden when printing) */}
        <section className="glass rounded-2xl p-6 border border-emerald-500/35 space-y-5 print:hidden">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-line pb-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-emerald-400" />
                <span className="text-[10px] font-mono uppercase tracking-widest text-emerald-400 font-bold">
                  Interactive Holding Multiplier
                </span>
              </div>
              <h2 className="text-lg font-display font-bold text-foreground">
                Farm-Scale Cumulative Impact Calculator ({areaHa} ha / {acres} acres)
              </h2>
            </div>

            {/* Strategy Selector Pills */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-mono text-muted">Active Prescription:</span>
              {strategies
                .filter((s) => s.rank > 0)
                .map((strat) => (
                  <button
                    key={strat.rank}
                    type="button"
                    onClick={() => setSelectedRank(strat.rank)}
                    className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold transition-all border ${
                      selectedRank === strat.rank
                        ? "bg-emerald-500 text-slate-950 border-emerald-400 shadow-sm"
                        : "bg-surface-2 text-muted hover:text-foreground border-line"
                    }`}
                  >
                    Rank #{strat.rank}: {strat.rotation.label ?? strat.rotation.id}
                  </button>
                ))}
            </div>
          </div>

          {/* Slider + Preset Holding Buttons */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
            <div className="lg:col-span-7 space-y-2">
              <div className="flex items-center justify-between text-xs font-mono">
                <label htmlFor="farm-area-slider" className="text-muted">
                  Drag to scale farm area (0.5 ha – 50 ha):
                </label>
                <span className="text-sm font-bold text-emerald-400">
                  {areaHa.toFixed(1)} Hectares ({acres} Acres)
                </span>
              </div>
              <input
                id="farm-area-slider"
                type="range"
                min={0.5}
                max={50}
                step={0.5}
                value={areaHa}
                onChange={(e) => setAreaHa(parseFloat(e.target.value))}
                className="w-full accent-emerald-400 cursor-pointer"
              />
              <div className="flex justify-between text-[10px] font-mono text-muted">
                <span>0.5 ha (Marginal)</span>
                <span>2.0 ha (Smallholder)</span>
                <span>10 ha (Medium)</span>
                <span>50 ha (FPO / Co-op)</span>
              </div>
            </div>

            <div className="lg:col-span-5 flex flex-wrap gap-2">
              {[
                { ha: 1.0, label: "1 ha (2.5 ac)" },
                { ha: 2.5, label: "2.5 ha (6.2 ac)" },
                { ha: 5.0, label: "5 ha (12.4 ac)" },
                { ha: 15.0, label: "15 ha (37 ac)" },
                { ha: 50.0, label: "50 ha (Village FPO)" },
              ].map((preset) => (
                <button
                  key={preset.ha}
                  type="button"
                  onClick={() => setAreaHa(preset.ha)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-mono border transition-colors ${
                    areaHa === preset.ha
                      ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/50 font-bold"
                      : "bg-surface-2 text-muted hover:text-foreground border-line"
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

          {/* 4 Scaled Impact Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
            <div className="p-4 rounded-xl bg-surface-2/80 border border-cyan-500/30 space-y-1">
              <div className="flex items-center justify-between text-cyan-400">
                <span className="text-[10px] font-mono uppercase tracking-wider font-bold">
                  Groundwater Saved / Yr
                </span>
                <Droplets className="w-4 h-4" />
              </div>
              <p className="text-2xl font-display font-extrabold text-foreground">
                {totalWaterSavedM3.toLocaleString()} m³
              </p>
              <p className="text-[11px] font-mono text-cyan-400">
                {(totalWaterSavedLiters / 1_000_000).toFixed(2)} Million Liters / yr saved
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/80 border border-amber-500/30 space-y-1">
              <div className="flex items-center justify-between text-amber-400">
                <span className="text-[10px] font-mono uppercase tracking-wider font-bold">
                  Total Farm Net Margin
                </span>
                <Coins className="w-4 h-4" />
              </div>
              <p className="text-2xl font-display font-extrabold text-foreground">
                {fmtMoney(totalFarmProfit, currencySymbol)}
              </p>
              <p className="text-[11px] font-mono text-emerald-400">
                {totalProfitDelta >= 0 ? "+" : ""}
                {fmtMoney(totalProfitDelta, currencySymbol)} vs. status-quo
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/80 border border-emerald-500/30 space-y-1">
              <div className="flex items-center justify-between text-emerald-400">
                <span className="text-[10px] font-mono uppercase tracking-wider font-bold">
                  10-Yr Carbon Sequestered
                </span>
                <Leaf className="w-4 h-4" />
              </div>
              <p className="text-2xl font-display font-extrabold text-foreground">
                {totalSocTonnes10Yr >= 0 ? "+" : ""}
                {totalSocTonnes10Yr} t C
              </p>
              <p className="text-[11px] font-mono text-emerald-400">
                ≈ {totalCo2eTonnes10Yr} t CO₂e atmospheric drawdown
              </p>
            </div>

            <div className="p-4 rounded-xl bg-surface-2/80 border border-stone-500/30 space-y-1">
              <div className="flex items-center justify-between text-stone-400">
                <span className="text-[10px] font-mono uppercase tracking-wider font-bold">
                  Biological &amp; Residue N Credit
                </span>
                <Sprout className="w-4 h-4" />
              </div>
              <p className="text-2xl font-display font-extrabold text-foreground">
                +{totalNSavedKgYr.toLocaleString()} kg N
              </p>
              <p className="text-[11px] font-mono text-stone-400">
                ≈ {totalUreaBagsSavedYr} bags (45kg) Urea saved/yr · Net N: {nBalancePerHa >= 0 ? "+" : ""}
                {Math.round(nBalancePerHa * areaHa)} kg
              </p>
            </div>
          </div>
        </section>

        {/* Printable 1-Page Executive Brief */}
        {profile && strategies.length > 0 && (
          <AgronomicBrief profile={profile} strategies={strategies} />
        )}
      </div>
    </AppShell>
  );
}
