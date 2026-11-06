"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type {
  FarmConstraints,
  FieldGeometry,
  FieldProfile,
  Priorities,
  StrategyRecommendation,
} from "@/types/api";
import { useI18n } from "@/i18n";
import { useField } from "@/context/FieldContext";
import { ProvenanceChip } from "./ProvenanceChip";
import { ProgressRing } from "./ProgressRing";
import {
  cropMeta,
  cropName,
  fmtAreaMoney,
  fmtAreaUnit,
  fmtMoney,
  isSouthAsia,
  MONTHS,
  scaleByUnit,
  seasonName,
  type UnitSystem,
} from "@/lib/ui";
import { getFallbackStrategies } from "@/lib/fallbackStrategies";
import { api } from "@/lib/api";
import {
  Printer,
  Sliders,
  TrendingUp,
  FlaskConical,
  Droplets,
  Coins,
  Sprout,
  ShieldAlert,
  CheckCircle2,
  RefreshCw,
  Box,
  RotateCcw,
  Layers,
  Calendar,
  Sparkles,
  FileText,
} from "lucide-react";

interface Props {
  field: FieldGeometry;
  profile?: FieldProfile;
  initialTab?: "cards" | "pareto" | "whatif";
  hideModeTabs?: boolean;
  onStrategiesLoaded?: (strategies: StrategyRecommendation[]) => void;
  strategies?: StrategyRecommendation[];
  loading?: boolean;
}

export function RotationExplorer({
  field,
  profile,
  initialTab,
  hideModeTabs = false,
  onStrategiesLoaded,
  strategies: externalStrategies,
  loading: externalLoading,
}: Props) {
  const { t, lang } = useI18n();
  const {
    priorities,
    setPriorities,
    constraints,
    setConstraints,
    selectedRank,
    setSelectedRank,
    unitSystem,
    soilHealthCard,
    baselineOverride,
  } = useField();

  const isSA = isSouthAsia(field.lat, field.lon);
  const currencySymbol = profile?.currency_symbol ?? "₹";

  const [internalStrategies, setInternalStrategies] = useState<StrategyRecommendation[]>([]);
  const [internalLoading, setInternalLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"cards" | "pareto" | "whatif">(initialTab ?? "cards");
  const [paretoViewMode, setParetoViewMode] = useState<"3d" | "2d">("3d");

  // What-If Shock parameters (TASK-F06)
  const [droughtShockPct, setDroughtShockPct] = useState<number>(15);
  const [priceShockPct, setPriceShockPct] = useState<number>(-5);
  const [fertilizerShockPct, setFertilizerShockPct] = useState<number>(25);

  const strategies = internalStrategies.length > 0 ? internalStrategies : (externalStrategies ?? []);
  const loading = externalLoading ?? internalLoading;

  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);

  const fetchRecommendations = async (overrideP?: Priorities, overrideC?: FarmConstraints) => {
    const pToUse = overrideP ?? priorities;
    const cToUse = overrideC ?? constraints;
    setInternalLoading(true);
    try {
      const recs = await api.recommend({
        field,
        priorities: pToUse,
        constraints: cToUse,
        language: (lang as "en" | "pa" | "hi") || "en",
        soil_health_card: soilHealthCard,
        baseline_override: baselineOverride,
      });
      if (recs && recs.length > 0) {
        setInternalStrategies(recs);
        onStrategiesLoaded?.(recs);
      }
    } catch (err) {
      console.warn("Backend /recommend failed, falling back to simulated strategies", err);
      const fallback = getFallbackStrategies(field, currencySymbol);
      setInternalStrategies(fallback);
      onStrategiesLoaded?.(fallback);
    } finally {
      setInternalLoading(false);
    }
  };

  useEffect(() => {
    setInternalStrategies([]);
    if (!externalStrategies && field) {
      fetchRecommendations();
    }
  }, [field.lat, field.lon]);

  const baseline = strategies.find((s) => s.rank === 0) ?? strategies[0];
  const candidates = strategies.filter((s) => s.rank > 0);
  const focusedStrategy =
    strategies.find((s) => s.rank === selectedRank) ?? candidates[0] ?? baseline;

  const totalWeight = Math.max(
    0.1,
    priorities.water_savings +
      priorities.profit +
      priorities.soil_health +
      priorities.low_risk +
      priorities.low_labour
  );
  const wWater = Math.round((priorities.water_savings / totalWeight) * 100);
  const wProfit = Math.round((priorities.profit / totalWeight) * 100);
  const wSoil = Math.round((priorities.soil_health / totalWeight) * 100);
  const wLabour = Math.round((priorities.low_labour / totalWeight) * 100);
  const wRisk = Math.max(0, 100 - wWater - wProfit - wSoil - wLabour);

  const applyPreset = (type: "balanced" | "water" | "profit" | "soil" | "resilient") => {
    let newP: Priorities = { ...priorities };
    if (type === "balanced") {
      newP = { ...newP, water_savings: 1.5, profit: 1.5, soil_health: 1.5, low_risk: 1.5, low_labour: 1.0 };
    } else if (type === "water") {
      newP = { ...newP, water_savings: 3.0, profit: 0.8, soil_health: 1.2, low_risk: 1.0, low_labour: 1.0 };
    } else if (type === "profit") {
      newP = { ...newP, profit: 3.0, water_savings: 0.8, soil_health: 0.8, low_risk: 1.0, low_labour: 0.5 };
    } else if (type === "soil") {
      newP = { ...newP, soil_health: 3.0, water_savings: 1.5, profit: 0.8, low_risk: 1.2, low_labour: 1.0 };
    } else if (type === "resilient") {
      newP = { ...newP, low_risk: 3.0, water_savings: 2.0, profit: 0.8, soil_health: 1.5, low_labour: 1.5 };
    }
    setPriorities(newP);
    fetchRecommendations(newP, constraints);
  };

  return (
    <div className="glass rounded-2xl border border-line overflow-hidden reticle-frame">
      {/* Instrument Header Bar */}
      <div className="instrument-header px-5 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 font-mono text-[10px]">
            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40 font-bold uppercase tracking-widest">
              NSGA-II // MULTI-OBJECTIVE SOLVER
            </span>
            <span className="text-muted hidden sm:inline">
              FAO-56 Water Balance · RothC-26.3 · USDA-NRCS
            </span>
          </div>
          <h3 className="font-serif text-xl sm:text-2xl font-bold text-foreground mt-1 tracking-tight">
            {lang === "pa"
              ? "ਫ਼ਸਲੀ ਚੱਕਰ ਅਨੁਕੂਲਨ ਅਤੇ ਸਿਫ਼ਾਰਿਸ਼ਾਂ"
              : lang === "hi"
              ? "फसल चक्र अनुकूलन एवं अनुशंसित रणनीतियां"
              : "Crop Rotation Decision & Optimization Studio"}
          </h3>
        </div>

        {/* View Mode Navigation & Export Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          <Link
            href="/brief"
            className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-surface hover:bg-foreground/10 text-foreground border border-line flex items-center gap-1.5 transition-colors"
          >
            <FileText className="w-3.5 h-3.5 text-sky-400" />
            <span>Executive Brief</span>
          </Link>

          <button
            type="button"
            onClick={() => window.print()}
            className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-surface hover:bg-foreground/10 text-foreground border border-line flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Printer className="w-3.5 h-3.5 text-emerald-400" />
            <span>Print</span>
          </button>

          {!hideModeTabs && (
            <div className="inline-flex rounded-xl bg-background/80 p-1 border border-line text-xs font-mono">
              <button
                type="button"
                onClick={() => setActiveTab("cards")}
                className={`px-3 py-1.5 rounded-lg font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
                  activeTab === "cards"
                    ? "bg-emerald-500 text-slate-950 font-bold"
                    : "text-muted hover:text-foreground"
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>Strategies &amp; Calendar</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("pareto")}
                className={`px-3 py-1.5 rounded-lg font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
                  activeTab === "pareto"
                    ? "bg-violet-500 text-white font-bold"
                    : "text-muted hover:text-foreground"
                }`}
              >
                <TrendingUp className="w-3.5 h-3.5" />
                <span>3D Pareto Space</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("whatif")}
                className={`px-3 py-1.5 rounded-lg font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
                  activeTab === "whatif"
                    ? "bg-amber-500 text-slate-950 font-bold"
                    : "text-muted hover:text-foreground"
                }`}
              >
                <FlaskConical className="w-3.5 h-3.5" />
                <span>Shock Lab</span>
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="p-5 sm:p-6 space-y-6">
        {/* Priorities & Farm Constraints Control Panel */}
        <div className="p-5 rounded-2xl bg-background/60 border border-line space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-emerald-400" />
              <h4 className="font-display font-bold text-xs uppercase tracking-wider text-foreground">
                {t("section.priorities")}
              </h4>
            </div>

            {/* Quick Weighting Persona Presets */}
            <div className="flex items-center gap-1.5 flex-wrap text-[11px] font-mono">
              <span className="text-muted pr-1 uppercase text-[10px]">Farmer Personas:</span>
              <button
                type="button"
                onClick={() => applyPreset("water")}
                className="px-2.5 py-1 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/40 text-cyan-600 dark:text-cyan-300 font-semibold transition-colors cursor-pointer"
              >
                Aquifer Rescue
              </button>
              <button
                type="button"
                onClick={() => applyPreset("profit")}
                className="px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/40 text-emerald-600 dark:text-emerald-300 font-semibold transition-colors cursor-pointer"
              >
                Max Net Margin
              </button>
              <button
                type="button"
                onClick={() => applyPreset("soil")}
                className="px-2.5 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-600 dark:text-amber-300 font-semibold transition-colors cursor-pointer"
              >
                Carbon Builder
              </button>
              <button
                type="button"
                onClick={() => applyPreset("resilient")}
                className="px-2.5 py-1 rounded-lg bg-violet-500/15 hover:bg-violet-500/25 border border-violet-500/40 text-violet-600 dark:text-violet-300 font-semibold transition-colors cursor-pointer"
              >
                Drought Shield
              </button>
              <button
                type="button"
                onClick={() => applyPreset("balanced")}
                className="px-2.5 py-1 rounded-lg bg-surface hover:bg-foreground/10 border border-line text-foreground transition-colors cursor-pointer"
              >
                Balanced
              </button>
            </div>
          </div>

          {/* Live Proportional Weight Distribution Bar */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[10px] font-mono text-muted">
              <span>OBJECTIVE WEIGHT ALLOCATION</span>
              <span>
                Water {wWater}% · Profit {wProfit}% · Soil {wSoil}% · Resilience {wRisk}% · Labour {wLabour}%
              </span>
            </div>
            <div className="h-2.5 w-full rounded-full overflow-hidden flex bg-surface border border-line">
              <div
                style={{ width: `${wWater}%` }}
                className="bg-cyan-400 transition-all duration-300"
                title={`Water Conservation: ${wWater}%`}
              />
              <div
                style={{ width: `${wProfit}%` }}
                className="bg-emerald-400 transition-all duration-300"
                title={`Profit Maximization: ${wProfit}%`}
              />
              <div
                style={{ width: `${wSoil}%` }}
                className="bg-amber-400 transition-all duration-300"
                title={`Soil Carbon & Health: ${wSoil}%`}
              />
              <div
                style={{ width: `${wRisk}%` }}
                className="bg-violet-400 transition-all duration-300"
                title={`Climate Resilience: ${wRisk}%`}
              />
              <div
                style={{ width: `${wLabour}%` }}
                className="bg-rose-400 transition-all duration-300"
                title={`Labour & Cost Savings: ${wLabour}%`}
              />
            </div>
          </div>

          {/* Sliders Grid (5 Objectives) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
            {/* Water Conservation */}
            <div className="space-y-2 p-3.5 rounded-xl bg-surface border border-line">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-foreground flex items-center gap-1.5">
                  <Droplets className="w-3.5 h-3.5 text-cyan-400" />
                  <span>{t("priorities.water")}</span>
                </span>
                <span className="font-mono text-[11px] font-bold text-cyan-400">
                  {priorities.water_savings.toFixed(1)}×
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="3"
                step="0.5"
                value={priorities.water_savings}
                onChange={(e) =>
                  setPriorities({ ...priorities, water_savings: parseFloat(e.target.value) })
                }
                className="w-full accent-cyan-400 cursor-pointer"
              />
            </div>

            {/* Profit Maximization */}
            <div className="space-y-2 p-3.5 rounded-xl bg-surface border border-line">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-foreground flex items-center gap-1.5">
                  <Coins className="w-3.5 h-3.5 text-emerald-400" />
                  <span>{t("priorities.profit")}</span>
                </span>
                <span className="font-mono text-[11px] font-bold text-emerald-400">
                  {priorities.profit.toFixed(1)}×
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="3"
                step="0.5"
                value={priorities.profit}
                onChange={(e) =>
                  setPriorities({ ...priorities, profit: parseFloat(e.target.value) })
                }
                className="w-full accent-emerald-400 cursor-pointer"
              />
            </div>

            {/* Soil Carbon & Health */}
            <div className="space-y-2 p-3.5 rounded-xl bg-surface border border-line">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-foreground flex items-center gap-1.5">
                  <Sprout className="w-3.5 h-3.5 text-amber-400" />
                  <span>{t("priorities.soil")}</span>
                </span>
                <span className="font-mono text-[11px] font-bold text-amber-400">
                  {priorities.soil_health.toFixed(1)}×
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="3"
                step="0.5"
                value={priorities.soil_health}
                onChange={(e) =>
                  setPriorities({ ...priorities, soil_health: parseFloat(e.target.value) })
                }
                className="w-full accent-amber-400 cursor-pointer"
              />
            </div>

            {/* Climate Resilience */}
            <div className="space-y-2 p-3.5 rounded-xl bg-surface border border-line">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-foreground flex items-center gap-1.5">
                  <ShieldAlert className="w-3.5 h-3.5 text-violet-400" />
                  <span>{t("priorities.risk")}</span>
                </span>
                <span className="font-mono text-[11px] font-bold text-violet-400">
                  {priorities.low_risk.toFixed(1)}×
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="3"
                step="0.5"
                value={priorities.low_risk}
                onChange={(e) =>
                  setPriorities({ ...priorities, low_risk: parseFloat(e.target.value) })
                }
                className="w-full accent-violet-400 cursor-pointer"
              />
            </div>

            {/* Labour & Cost Savings */}
            <div className="space-y-2 p-3.5 rounded-xl bg-surface border border-line">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-foreground flex items-center gap-1.5">
                  <RotateCcw className="w-3.5 h-3.5 text-rose-400" />
                  <span>{t("priorities.labour")}</span>
                </span>
                <span className="font-mono text-[11px] font-bold text-rose-400">
                  {priorities.low_labour.toFixed(1)}×
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="3"
                step="0.5"
                value={priorities.low_labour}
                onChange={(e) =>
                  setPriorities({ ...priorities, low_labour: parseFloat(e.target.value) })
                }
                className="w-full accent-rose-400 cursor-pointer"
              />
            </div>
          </div>

          {/* Constraint Bar & Re-simulate Action */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-3 border-t border-line text-xs">
            <div className="flex flex-wrap items-center gap-4 font-mono text-[11px]">
              <label className="flex items-center gap-2 cursor-pointer text-foreground/90">
                <input
                  type="checkbox"
                  checked={constraints.has_livestock}
                  onChange={(e) =>
                    setConstraints({ ...constraints, has_livestock: e.target.checked })
                  }
                  className="w-4 h-4 rounded accent-emerald-500 cursor-pointer"
                />
                <span>Integrate Fodder / Livestock</span>
              </label>

              <div className="flex items-center gap-2">
                <span className="text-muted">Water Supply:</span>
                <select
                  value={constraints.irrigation}
                  onChange={(e) =>
                    setConstraints({
                      ...constraints,
                      irrigation: e.target.value as "none" | "limited" | "full",
                    })
                  }
                  className="px-2.5 py-1 rounded-lg border border-line-strong bg-surface text-foreground text-[11px] font-mono outline-none cursor-pointer"
                >
                  <option value="limited">Tube-well (Restricted Cap)</option>
                  <option value="full">Tube-well / Canal (Unrestricted)</option>
                  <option value="none">Rainfed Only</option>
                </select>
              </div>
            </div>

            <button
              type="button"
              onClick={() => fetchRecommendations()}
              disabled={loading}
              className="px-5 py-2 rounded-xl text-xs font-mono font-bold bg-gradient-to-r from-emerald-500 to-cyan-500 hover:opacity-95 text-slate-950 transition-opacity disabled:opacity-50 cursor-pointer flex items-center gap-2 shadow-sm"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              <span>{loading ? t("priorities.optimizing") : t("priorities.optimize")}</span>
            </button>
          </div>
        </div>

        {/* VIEW MODE 1: Comparative Strategy Cards + Interactive Calendar & Radar */}
        {activeTab === "cards" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h4 className="font-display font-bold text-xs uppercase tracking-wider text-foreground">
                Comparative Performance vs Current Farm Baseline
              </h4>
              <span className="text-[11px] font-mono text-emerald-500 font-semibold">
                Click any strategy card below to inspect its 12-Month Gantt Calendar &amp; Soil Health Radar
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {baseline && (
                <StrategyCard
                  strategy={baseline}
                  isBaseline={true}
                  isSelected={selectedRank === 0}
                  onSelect={() => setSelectedRank(0)}
                  currencySymbol={currencySymbol}
                  unitSystem={unitSystem}
                />
              )}

              {candidates.map((strat) => (
                <StrategyCard
                  key={strat.rank}
                  strategy={strat}
                  isBaseline={false}
                  isSelected={selectedRank === strat.rank}
                  onSelect={() => setSelectedRank(strat.rank)}
                  currencySymbol={currencySymbol}
                  unitSystem={unitSystem}
                />
              ))}
            </div>

            {/* Focused Strategy Grounded Narrative & Government Schemes Dossier */}
            {focusedStrategy && (
              <div className="p-5 rounded-2xl bg-emerald-500/[0.06] border border-emerald-500/30 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-xs font-mono font-bold text-emerald-600 dark:text-emerald-300 uppercase tracking-wider">
                    <Sparkles className="w-4 h-4 text-emerald-400" />
                    <span>
                      Grounded Advisory &amp; Government Scheme Eligibility — {focusedStrategy.rotation.label}
                    </span>
                  </div>
                  {focusedStrategy.practical_metrics?.msp_assurance_level && (
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/20 text-amber-600 dark:text-amber-300 border border-amber-500/40">
                      {focusedStrategy.practical_metrics.msp_assurance_level}
                    </span>
                  )}
                </div>

                {focusedStrategy.narrative_summary && (
                  <p className="text-xs sm:text-sm text-foreground/95 leading-relaxed font-medium bg-background/70 p-3.5 rounded-xl border border-line">
                    {focusedStrategy.narrative_summary}
                  </p>
                )}

                {focusedStrategy.practical_metrics && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                    <div className="p-3 rounded-xl bg-background/75 border border-line">
                      <span className="text-[10px] text-muted uppercase block">Kharif–Rabi Turnaround</span>
                      <span
                        className={`text-sm font-bold ${
                          focusedStrategy.practical_metrics.turnaround_days_kharif_rabi >= 20
                            ? "text-emerald-400"
                            : "text-rose-400"
                        }`}
                      >
                        {focusedStrategy.practical_metrics.turnaround_days_kharif_rabi} Days{" "}
                        {focusedStrategy.practical_metrics.turnaround_days_kharif_rabi >= 20
                          ? "(Burn-Free)"
                          : "(Crunch)"}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-background/75 border border-line">
                      <span className="text-[10px] text-muted uppercase block">Irrigations Saved</span>
                      <span className="text-sm font-bold text-cyan-400">
                        {focusedStrategy.practical_metrics.irrigations_saved_per_yr} Irrigations (
                        {Math.round(
                          scaleByUnit(
                            focusedStrategy.practical_metrics.pumping_hours_saved_per_ha,
                            unitSystem
                          )
                        )}{" "}
                        hrs{fmtAreaUnit(unitSystem)})
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-background/75 border border-line">
                      <span className="text-[10px] text-muted uppercase block">45-kg Urea Saved</span>
                      <span className="text-sm font-bold text-emerald-400">
                        {scaleByUnit(
                          focusedStrategy.practical_metrics.urea_bags_saved_per_ha,
                          unitSystem
                        ).toFixed(1)}{" "}
                        Bags{fmtAreaUnit(unitSystem)}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-background/75 border border-line">
                      <span className="text-[10px] text-muted uppercase block">Labour Outlay</span>
                      <span className="text-sm font-bold text-foreground">
                        {fmtAreaMoney(
                          focusedStrategy.practical_metrics.labor_cost_inr_per_ha,
                          currencySymbol,
                          unitSystem,
                          false
                        )}
                        {fmtAreaUnit(unitSystem)}
                      </span>
                    </div>
                  </div>
                )}

                {focusedStrategy.practical_metrics?.eligible_schemes &&
                  focusedStrategy.practical_metrics.eligible_schemes.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      <span className="text-[10px] font-mono font-bold uppercase text-muted mr-1">
                        Eligible Schemes:
                      </span>
                      {focusedStrategy.practical_metrics.eligible_schemes.map((sch, idx) => (
                        <span
                          key={idx}
                          className="px-2.5 py-1 rounded-lg text-[11px] font-mono bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border border-emerald-500/35"
                        >
                          {sch}
                        </span>
                      ))}
                    </div>
                  )}
              </div>
            )}

            {/* Interactive Deep-Dive: 12-Month Agronomic Calendar + 5-Axis Soil Health Radar */}
            {focusedStrategy && baseline && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 pt-2">
                {/* Left 7 Cols: 12-Month Seasonal Gantt Calendar */}
                <div className="lg:col-span-7 p-5 rounded-2xl bg-background/60 border border-line space-y-4">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-emerald-400" />
                      <h4 className="font-display font-bold text-sm text-foreground">
                        12-Month Agronomic Rotation Calendar — {focusedStrategy.rotation.label}
                      </h4>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-500 border border-emerald-500/30 font-bold">
                      {focusedStrategy.rank === 0 ? "BASELINE REGIME" : `STRATEGY #0${focusedStrategy.rank}`}
                    </span>
                  </div>

                  {/* Month Header Grid */}
                  <div className="space-y-3">
                    <div className="grid grid-cols-12 gap-1 text-center font-mono text-[10px] text-muted border-b border-line pb-1.5">
                      {MONTHS.map((m) => (
                        <span key={m}>{m}</span>
                      ))}
                    </div>

                    {focusedStrategy.rotation.steps.map((step, sIdx) => {
                      const meta = cropMeta(step.crop_id);
                      const sLabel = seasonName(field.lat, field.lon, step.season_index);
                      // Map season_index to typical month span for visual Gantt bar
                      const spanCols =
                        step.season_index === 0
                          ? { start: 6, len: 5, window: "Jun – Oct" }
                          : step.season_index === 1
                          ? { start: 11, len: 5, window: "Nov – Mar" }
                          : { start: 4, len: 2, window: "Apr – May" };

                      return (
                        <div
                          key={sIdx}
                          className="p-3 rounded-xl bg-surface border border-line space-y-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-foreground/10 text-foreground">
                                {sLabel} ({spanCols.window})
                              </span>
                              <span className="font-display font-bold text-foreground capitalize">
                                {cropName(step.crop_id)}
                              </span>
                            </div>

                            <div className="flex items-center gap-1.5 flex-wrap">
                              {step.practices.map((p) => (
                                <span
                                  key={p}
                                  className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border border-emerald-500/30"
                                >
                                  {p.replace(/_/g, " ")}
                                </span>
                              ))}
                            </div>
                          </div>

                          {/* 12-Month Active Bar */}
                          <div className="grid grid-cols-12 gap-1 h-3">
                            {MONTHS.map((m, mIdx) => {
                              const mNum = mIdx + 1;
                              const isActive =
                                step.season_index === 0
                                  ? mNum >= 6 && mNum <= 10
                                  : step.season_index === 1
                                  ? mNum >= 11 || mNum <= 3
                                  : mNum >= 4 && mNum <= 5;
                              return (
                                <div
                                  key={m}
                                  className="rounded-xs transition-all"
                                  style={{
                                    backgroundColor: isActive ? meta.color : "rgba(148,163,184,0.12)",
                                    opacity: isActive ? 0.9 : 0.4,
                                  }}
                                />
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Right 5 Cols: 5-Axis USDA-NRCS Soil Health Radar Chart */}
                <div className="lg:col-span-5 p-5 rounded-2xl bg-background/60 border border-line flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-amber-400" />
                      <h4 className="font-display font-bold text-sm text-foreground">
                        5-Axis USDA-NRCS Soil Health Radar
                      </h4>
                    </div>
                    <span className="text-[10px] font-mono text-muted">vs. Baseline</span>
                  </div>

                  <SoilHealthRadar
                    focused={focusedStrategy}
                    baseline={baseline}
                  />

                  <div className="flex items-center justify-center gap-5 text-[11px] font-mono pt-2 border-t border-line">
                    <span className="flex items-center gap-1.5 text-emerald-400 font-bold">
                      <span className="w-3 h-1.5 rounded bg-emerald-400 inline-block" />
                      <span>{focusedStrategy.rotation.label}</span>
                    </span>
                    <span className="flex items-center gap-1.5 text-rose-400">
                      <span className="w-3 h-1.5 rounded bg-rose-400 inline-block" />
                      <span>Current Baseline</span>
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* VIEW MODE 2: 3D Multi-Objective Pareto Space + 2D Projection */}
        {activeTab === "pareto" && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h4 className="font-display font-bold text-sm text-foreground flex items-center gap-2">
                  <Box className="w-4 h-4 text-violet-400" />
                  <span>Multi-Objective Pareto Trade-Off Frontier</span>
                </h4>
                <p className="text-[11px] font-mono text-muted mt-0.5">
                  Simultaneous optimization across Irrigation Demand [mm/yr], Net Margin [
                  {currencySymbol}/ha], and Soil Health [0–100]
                </p>
              </div>

              <div className="inline-flex rounded-lg bg-surface p-0.5 border border-line text-[11px] font-mono">
                <button
                  type="button"
                  onClick={() => setParetoViewMode("3d")}
                  className={`px-3 py-1 rounded-md font-semibold cursor-pointer transition-colors ${
                    paretoViewMode === "3d"
                      ? "bg-violet-500 text-white"
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  3D Decision Cube
                </button>
                <button
                  type="button"
                  onClick={() => setParetoViewMode("2d")}
                  className={`px-3 py-1 rounded-md font-semibold cursor-pointer transition-colors ${
                    paretoViewMode === "2d"
                      ? "bg-violet-500 text-white"
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  2D Engineering Plot
                </button>
              </div>
            </div>

            <div className="rounded-2xl bg-surface border border-line overflow-hidden">
              {paretoViewMode === "3d" ? (
                <ParetoCube3D
                  strategies={strategies}
                  selectedRank={selectedRank}
                  onSelectRank={(r) => setSelectedRank(r)}
                  currencySymbol={currencySymbol}
                />
              ) : (
                <div className="p-6">
                  <ParetoScatterPlot
                    strategies={strategies}
                    selectedRank={selectedRank}
                    onSelectRank={(r) => setSelectedRank(r)}
                    currencySymbol={currencySymbol}
                  />
                </div>
              )}
            </div>

            {/* Cards below plot for quick reference */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 pt-1">
              {baseline && (
                <StrategyCard
                  strategy={baseline}
                  isBaseline={true}
                  isSelected={selectedRank === 0}
                  onSelect={() => setSelectedRank(0)}
                  currencySymbol={currencySymbol}
                  unitSystem={unitSystem}
                />
              )}
              {candidates.map((strat) => (
                <StrategyCard
                  key={strat.rank}
                  strategy={strat}
                  isBaseline={false}
                  isSelected={selectedRank === strat.rank}
                  onSelect={() => setSelectedRank(strat.rank)}
                  currencySymbol={currencySymbol}
                  unitSystem={unitSystem}
                />
              ))}
            </div>
          </div>
        )}

        {/* VIEW MODE 3: What-If Stress Lab */}
        {activeTab === "whatif" && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="font-display font-bold text-sm text-foreground flex items-center gap-2">
                <FlaskConical className="w-4 h-4 text-amber-400" />
                <span>What-If Hydro-Climatic &amp; Market Stress Perturbation Lab</span>
              </h4>
              <span className="text-[11px] font-mono text-muted">
                Perturb ET₀ drought anomaly, MSP/market price, and synthetic N-fertilizer cost
              </span>
            </div>

            {/* Shock Sliders */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-5 rounded-2xl bg-amber-500/[0.07] border border-amber-500/35">
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span className="font-semibold text-foreground">Drought / ET₀ Anomaly</span>
                  <span className="font-bold text-amber-500">+{droughtShockPct}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="40"
                  step="5"
                  value={droughtShockPct}
                  onChange={(e) => setDroughtShockPct(parseInt(e.target.value))}
                  className="w-full accent-amber-500 cursor-pointer"
                />
                <span className="text-[10px] font-mono text-muted block">
                  Increases atmospheric water demand &amp; groundwater pumping cost
                </span>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span className="font-semibold text-foreground">Harvest Price Perturbation</span>
                  <span className="font-bold text-cyan-400">
                    {priceShockPct > 0 ? `+${priceShockPct}` : priceShockPct}%
                  </span>
                </div>
                <input
                  type="range"
                  min="-25"
                  max="25"
                  step="5"
                  value={priceShockPct}
                  onChange={(e) => setPriceShockPct(parseInt(e.target.value))}
                  className="w-full accent-cyan-400 cursor-pointer"
                />
                <span className="text-[10px] font-mono text-muted block">
                  Simulates market price deviation vs baseline MSP
                </span>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span className="font-semibold text-foreground">Urea / Synthetic N Cost Spike</span>
                  <span className="font-bold text-rose-500">+{fertilizerShockPct}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="50"
                  step="10"
                  value={fertilizerShockPct}
                  onChange={(e) => setFertilizerShockPct(parseInt(e.target.value))}
                  className="w-full accent-rose-500 cursor-pointer"
                />
                <span className="text-[10px] font-mono text-muted block">
                  Legume rotations buffer cost via 25 kg N/ha biological fixation credit
                </span>
              </div>
            </div>

            {/* Stressed Performance Comparative Matrix */}
            <div className="overflow-x-auto rounded-2xl border border-line">
              <table className="w-full text-left text-xs">
                <thead className="bg-foreground/[0.05] text-foreground font-mono text-[11px] uppercase tracking-wider border-b border-line">
                  <tr>
                    <th className="py-3.5 px-4">Rotation Strategy</th>
                    <th className="py-3.5 px-3">Baseline Margin</th>
                    <th className="py-3.5 px-3">Stressed Margin</th>
                    <th className="py-3.5 px-3">Regret / Drawdown</th>
                    <th className="py-3.5 px-3">Stressed Irrigation</th>
                    <th className="py-3.5 px-3">Resilience Class</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line text-foreground/90 font-mono">
                  {strategies.map((strat) => {
                    const res = strat.results[0];
                    const normP = res?.profit_p50 ?? (isSA ? 85000 : 950);
                    const normIrr = res?.irrigation_mm?.length
                      ? res.irrigation_mm.reduce((a, b) => a + b, 0) / res.irrigation_mm.length
                      : 1200;

                    const extraIrr = normIrr * (droughtShockPct / 100);
                    const stressedIrr = Math.round(normIrr + extraIrr);
                    const pumpUnitCost = isSA ? 8.5 : 0.45;
                    const fertUnitCost = isSA ? 95 : 1.2;
                    const fertLegumeUnitCost = isSA ? 25 : 0.35;
                    const pumpPenalty = extraIrr * pumpUnitCost;
                    const revMult = 1 + priceShockPct / 100;
                    const fertPenalty =
                      (res?.n_balance_kg_ha_yr ?? 30) > 15
                        ? fertilizerShockPct * fertUnitCost
                        : fertilizerShockPct * fertLegumeUnitCost;

                    const stressedP = Math.round(normP * revMult - pumpPenalty - fertPenalty);
                    const drop = normP - stressedP;
                    const isBase = strat.rank === 0;
                    const dropThreshold = isSA ? 18000 : 250;

                    return (
                      <tr
                        key={strat.rank}
                        className={
                          isBase
                            ? "bg-rose-500/[0.07] font-medium"
                            : "hover:bg-foreground/[0.04] transition-colors"
                        }
                      >
                        <td className="py-3.5 px-4 font-sans font-bold flex items-center gap-2">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[9px] font-mono uppercase ${
                              isBase
                                ? "bg-rose-500/20 text-rose-500 border border-rose-500/40"
                                : "bg-emerald-500/20 text-emerald-500 border border-emerald-500/40"
                            }`}
                          >
                            {isBase ? "REF" : `S0${strat.rank}`}
                          </span>
                          <span>{strat.rotation.label ?? strat.rotation.id}</span>
                        </td>
                        <td className="py-3.5 px-3">{fmtMoney(normP, currencySymbol)}</td>
                        <td className="py-3.5 px-3 font-bold text-emerald-500">
                          {fmtMoney(stressedP, currencySymbol)}
                        </td>
                        <td className="py-3.5 px-3 text-rose-500">
                          −{fmtMoney(drop, currencySymbol)}
                        </td>
                        <td className="py-3.5 px-3">{stressedIrr} mm/yr</td>
                        <td className="py-3.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              drop < dropThreshold
                                ? "bg-emerald-500/20 text-emerald-500 border border-emerald-500/40"
                                : "bg-rose-500/20 text-rose-500 border border-rose-500/40"
                            }`}
                          >
                            {drop < dropThreshold ? "Buffered" : "Vulnerable"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * 5-Axis USDA-NRCS Soil Health Radar Chart (SVG + Accessible sr-only Table)
 */
function SoilHealthRadar({
  focused,
  baseline,
}: {
  focused: StrategyRecommendation;
  baseline: StrategyRecommendation;
}) {
  const fRes = focused.results[0];
  const bRes = baseline.results[0];

  const computeAxes = (s: StrategyRecommendation, r?: typeof fRes) => {
    const bd = r?.soil_health_breakdown;
    if (bd && typeof bd.soil_armor_cover === "number") {
      return [
        Math.round((bd.soil_armor_cover / 15) * 100),
        Math.round((bd.disturbance_minimization / 15) * 100),
        Math.round((bd.living_roots / 15) * 100),
        Math.round((bd.biodiversity / 15) * 100),
        Math.round((bd.biological_n_livestock / 15) * 100),
      ];
    }
    const practices = s.rotation.steps.flatMap((st) => st.practices);
    const hasMulch = practices.some((p) => p.includes("residue_retained") || p.includes("mulch"));
    const hasBurn = practices.some((p) => p.includes("burned"));
    const hasZeroTill = practices.some(
      (p) => p.includes("zero_till") || p.includes("no_till") || p.includes("happy_seeder") || p.includes("direct_seeded")
    );

    const armor = hasMulch ? 88 : hasBurn ? 18 : 52;
    const minDisturb = hasZeroTill ? 85 : 35;
    const livingRoots = Math.min(95, Math.round((r?.living_root_days_pct ?? 0.65) * 100));
    const diversity = Math.min(95, Math.round(35 + (r?.family_diversity_index ?? 0.2) * 80));
    const carbon = Math.min(
      95,
      Math.max(20, Math.round(50 + (r?.soc_delta_t_ha_10yr ?? 0) * 18))
    );
    return [armor, minDisturb, livingRoots, diversity, carbon];
  };

  const axesLabels = ["Soil Armor", "Min Till", "Living Roots", "Biodiversity", "SOC Gain"];
  const fVals = computeAxes(focused, fRes);
  const bVals = computeAxes(baseline, bRes);

  const cx = 130;
  const cy = 105;
  const maxR = 72;

  const ptAt = (idx: number, val: number) => {
    const angle = -Math.PI / 2 + (idx * 2 * Math.PI) / 5;
    const r = (val / 100) * maxR;
    return {
      x: cx + Math.cos(angle) * r,
      y: cy + Math.sin(angle) * r,
    };
  };

  const polyPoints = (vals: number[]) =>
    vals
      .map((v, i) => {
        const p = ptAt(i, v);
        return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
      })
      .join(" ");

  return (
    <div className="w-full flex flex-col items-center py-1">
      <svg viewBox="0 0 260 210" className="w-full max-w-[270px] h-auto font-mono select-none">
        {/* Concentric Pentagon Rings */}
        {[33, 66, 100].map((lvl) => (
          <polygon
            key={lvl}
            points={polyPoints([lvl, lvl, lvl, lvl, lvl])}
            fill="none"
            stroke="currentColor"
            strokeOpacity="0.14"
            strokeWidth="1"
          />
        ))}

        {/* Axis Spokes & Labels */}
        {axesLabels.map((label, i) => {
          const end = ptAt(i, 100);
          const lbl = ptAt(i, 124);
          return (
            <g key={label}>
              <line
                x1={cx}
                y1={cy}
                x2={end.x}
                y2={end.y}
                stroke="currentColor"
                strokeOpacity="0.18"
                strokeWidth="1"
              />
              <text
                x={lbl.x}
                y={lbl.y}
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize="8.5"
                fill="currentColor"
                opacity="0.8"
                fontWeight="600"
              >
                {label}
              </text>
            </g>
          );
        })}

        {/* Baseline Polygon */}
        <polygon
          points={polyPoints(bVals)}
          fill="rgba(244, 63, 94, 0.16)"
          stroke="#f43f5e"
          strokeWidth="1.5"
          strokeDasharray="3 2"
        />

        {/* Focused Strategy Polygon */}
        <polygon
          points={polyPoints(fVals)}
          fill="rgba(16, 185, 129, 0.25)"
          stroke="#10b981"
          strokeWidth="2"
        />

        {fVals.map((v, i) => {
          const p = ptAt(i, v);
          return <circle key={i} cx={p.x} cy={p.y} r="3" fill="#34d399" />;
        })}
      </svg>

      {/* Explicit Soil Health Component & Weight Breakdown */}
      {fRes?.soil_health_breakdown && (
        <div className="w-full mt-2 pt-2 border-t border-line space-y-1 text-[10px] font-mono">
          <div className="flex justify-between text-muted uppercase font-bold">
            <span>Soil Health Component (Weight)</span>
            <span>Selected vs Base</span>
          </div>
          {[
            { key: "disturbance_minimization", label: "1. Min Disturbance (/15)" },
            { key: "soil_armor_cover", label: "2. Soil Armor (/15)" },
            { key: "living_roots", label: "3. Living Roots (/15)" },
            { key: "biodiversity", label: "4. Biodiversity (/15)" },
            { key: "biological_n_livestock", label: "5. Bio-N / Fodder (/15)" },
            { key: "soc_modifier", label: "+ SOC 10yr Mod (-15..+18)" },
            { key: "erosion_modifier", label: "+ RUSLE Mod (-10..+10)" },
            { key: "burning_penalty", label: "+ Burn Penalty (-8..0)" },
          ].map((item) => {
            const fVal = fRes.soil_health_breakdown?.[item.key] ?? 0;
            const bVal = bRes?.soil_health_breakdown?.[item.key] ?? 0;
            return (
              <div key={item.key} className="flex justify-between items-center">
                <span className="text-muted">{item.label}</span>
                <span>
                  <strong className="text-emerald-400">{fVal > 0 && item.key.includes("mod") ? `+${fVal}` : fVal}</strong>
                  <span className="text-muted"> vs {bVal > 0 && item.key.includes("mod") ? `+${bVal}` : bVal}</span>
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Accessible fallback table */}
      <table className="sr-only">
        <caption>USDA-NRCS 5-Axis Soil Health Comparison</caption>
        <thead>
          <tr>
            <th>Principle</th>
            <th>Selected Strategy</th>
            <th>Baseline</th>
          </tr>
        </thead>
        <tbody>
          {axesLabels.map((lbl, i) => (
            <tr key={lbl}>
              <td>{lbl}</td>
              <td>{fVals[i]}/100</td>
              <td>{bVals[i]}/100</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StrategyCard({
  strategy,
  isBaseline,
  isSelected,
  onSelect,
  currencySymbol = "₹",
  unitSystem = "acre",
}: {
  strategy: StrategyRecommendation;
  isBaseline: boolean;
  isSelected: boolean;
  onSelect: () => void;
  currencySymbol?: string;
  unitSystem?: UnitSystem;
}) {
  const { t } = useI18n();
  const currSym = strategy.currency_symbol || currencySymbol;
  const res = strategy.results[0];
  const irr = res?.irrigation_mm?.length
    ? Math.round(res.irrigation_mm.reduce((a, b) => a + b, 0) / res.irrigation_mm.length)
    : 1200;

  const waterChange =
    strategy.vs_baseline?.irrigation_change_pct ?? strategy.vs_baseline?.irrigation_pct;
  const waterSaved = waterChange !== undefined ? -Math.round(waterChange) : 0;
  const resilienceScore = strategy.vs_baseline?.climate_resilience_score;
  const shScore = Math.round(res?.soil_health_score ?? 40);
  const pm = strategy.practical_metrics;

  const cardTone = isBaseline
    ? "border-line bg-surface/50 hatch-pattern"
    : strategy.rank === 1
    ? "border-emerald-500/60 bg-gradient-to-b from-emerald-500/[0.09] to-transparent"
    : "border-line-strong bg-surface/85";

  const selectedRing = isSelected
    ? "ring-2 ring-emerald-400 shadow-xl -translate-y-0.5"
    : "";

  return (
    <div
      onClick={onSelect}
      className={`rounded-2xl border p-4.5 flex flex-col justify-between transition-all cursor-pointer hover:border-emerald-400/60 ${cardTone} ${selectedRing}`}
    >
      <div className="space-y-3.5">
        {/* Header Badges */}
        <div className="flex items-center justify-between gap-2 font-mono">
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
              isBaseline
                ? "bg-foreground/10 text-muted border-line"
                : strategy.rank === 1
                ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border-emerald-500/40"
                : "bg-cyan-500/15 text-cyan-600 dark:text-cyan-300 border-cyan-500/35"
            }`}
          >
            {isBaseline
              ? `REF // ${t("strategy.baseline")}`
              : `OPT 0${strategy.rank} // RECOMMENDED`}
          </span>

          <div className="flex items-center gap-1.5">
            {!isBaseline && waterSaved > 0 && (
              <span className="text-[10px] font-bold text-cyan-600 dark:text-cyan-300 bg-cyan-500/15 px-1.5 py-0.5 rounded border border-cyan-500/35">
                −{waterSaved}% H₂O
              </span>
            )}
            {resilienceScore !== undefined && (
              <span
                className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-600 dark:text-violet-300 border border-violet-500/35"
                title="Climate Resilience Index"
              >
                RES {Math.round(resilienceScore)}
              </span>
            )}
          </div>
        </div>

        {/* Rotation Name & Botanical Sequence */}
        <div className="flex items-start justify-between gap-2">
          <div>
            <h4 className="font-display font-bold text-sm text-foreground leading-snug">
              {strategy.rotation.label ?? strategy.rotation.id}
            </h4>

            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              {strategy.rotation.steps.map((step, idx) => {
                const meta = cropMeta(step.crop_id);
                return (
                  <span
                    key={idx}
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium border ${meta.tone}`}
                  >
                    <span className="font-mono text-[9px] font-bold opacity-80">{meta.emoji}</span>
                    <span className="capitalize">{cropName(step.crop_id)}</span>
                    {step.practices.includes("residue_retained") && (
                      <span className="text-[9px] font-mono uppercase px-1 rounded bg-emerald-500/20 text-emerald-600 dark:text-emerald-300">
                        Mulch
                      </span>
                    )}
                  </span>
                );
              })}
            </div>
          </div>

          <ProgressRing
            value={shScore}
            max={100}
            label="Soil Health Score"
            size="2.75rem"
            thickness="4px"
            color={shScore >= 60 ? "var(--accent-canopy)" : "var(--accent-soil)"}
          >
            <span className="text-[10px] font-mono font-bold text-foreground">{shScore}</span>
          </ProgressRing>
        </div>

        {/* Quantitative Metrics Grid */}
        <div className="pt-2.5 border-t border-line space-y-2 text-xs font-mono">
          <div className="flex justify-between items-center">
            <span className="text-muted font-sans">Irrigation Demand</span>
            <span
              className={`font-bold ${
                isBaseline ? "text-rose-500" : "text-cyan-500 dark:text-cyan-300"
              }`}
            >
              {irr} mm/yr
            </span>
          </div>

          <div className="flex justify-between items-center">
            <span className="text-muted font-sans">
              {t("strategy.profitRange")} ({fmtAreaUnit(unitSystem)})
            </span>
            <span className="font-bold text-foreground">
              {fmtAreaMoney(res?.profit_p50, currSym, unitSystem)}{" "}
              <span className="text-[10px] text-muted font-normal">
                [{fmtAreaMoney(res?.profit_p10, currSym, unitSystem)}–{fmtAreaMoney(res?.profit_p90, currSym, unitSystem)}]
              </span>
            </span>
          </div>

          <div className="flex justify-between items-center">
            <span className="text-muted font-sans">{t("strategy.socTrajectory")}</span>
            <span
              className={`font-bold ${
                (res?.soc_delta_t_ha_10yr ?? 0) >= 0
                  ? "text-emerald-500 dark:text-emerald-400"
                  : "text-rose-500"
              }`}
            >
              {(res?.soc_delta_t_ha_10yr ?? 0) > 0 ? "+" : ""}
              {(res?.soc_delta_t_ha_10yr ?? -0.8).toFixed(1)} t C/ha
            </span>
          </div>

          {pm && (
            <div className="pt-1.5 flex flex-wrap items-center gap-1.5 text-[10px] font-mono">
              <span
                className={`px-1.5 py-0.5 rounded border ${
                  pm.turnaround_days_kharif_rabi >= 20
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                }`}
              >
                Window: {pm.turnaround_days_kharif_rabi}d
              </span>
              {!isBaseline && pm.urea_bags_saved_per_ha > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                  −{scaleByUnit(pm.urea_bags_saved_per_ha, unitSystem).toFixed(1)} Urea bags{fmtAreaUnit(unitSystem)}
                </span>
              )}
              {!isBaseline && pm.irrigations_saved_per_yr > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-300 border border-violet-500/30">
                  −{pm.irrigations_saved_per_yr.toFixed(0)} Irrigations
                </span>
              )}
            </div>
          )}
        </div>

        {/* Grounded NASA Evidence Points */}
        {strategy.why && strategy.why.length > 0 && (
          <div className="pt-2.5 border-t border-line">
            <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-muted mb-1.5">
              {t("strategy.whyThisWorks")}
            </p>
            <ul className="space-y-1.5 text-[11px] text-foreground/85 leading-relaxed">
              {strategy.why.slice(0, 2).map((item, idx) => (
                <li key={idx} className="flex items-start gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="mt-4 pt-2 border-t border-line">
        <ProvenanceChip provenance={strategy.provenance} />
      </div>
    </div>
  );
}

/**
 * Interactive 3D Multi-Objective Pareto Space Cube (Irrigation vs Profit vs Soil Health)
 */
function ParetoCube3D({
  strategies,
  selectedRank,
  onSelectRank,
  currencySymbol = "$",
}: {
  strategies: StrategyRecommendation[];
  selectedRank: number | null;
  onSelectRank: (rank: number) => void;
  currencySymbol?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [yaw, setYaw] = useState<number>(-0.62);
  const [pitch, setPitch] = useState<number>(0.42);
  const isDraggingRef = useRef<boolean>(false);
  const lastPosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const hitTargetsRef = useRef<Array<{ rank: number; x: number; y: number; r: number }>>([]);

  const currSym = strategies[0]?.currency_symbol || currencySymbol;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.round(entry.contentRect.width * dpr));
      canvas.height = Math.max(1, Math.round(entry.contentRect.height * dpr));
    });
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !strategies.length) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    const dpr = window.devicePixelRatio || 1;
    ctx.clearRect(0, 0, w, h);

    const isDark = document.documentElement.classList.contains("dark");
    const cx = w * 0.5;
    const cy = h * 0.54;
    const scale = Math.min(w, h) * 0.31;

    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const cosP = Math.cos(pitch);
    const sinP = Math.sin(pitch);

    const project = (x: number, y: number, z: number) => {
      const x1 = x * cosY - z * sinY;
      const z1 = x * sinY + z * cosY;
      const y2 = y * cosP - z1 * sinP;
      const z2 = y * sinP + z1 * cosP;
      const fov = 4.2;
      const p = fov / Math.max(1.5, fov + z2 * 0.45);
      return {
        x: cx + x1 * scale * p,
        y: cy - y2 * scale * p,
        z: z2,
        s: p,
      };
    };

    ctx.save();
    ctx.strokeStyle = isDark ? "rgba(148, 163, 184, 0.14)" : "rgba(15, 23, 42, 0.12)";
    ctx.lineWidth = 1 * dpr;

    for (let i = -1; i <= 1.001; i += 0.5) {
      const f1 = project(i, -0.85, -1);
      const f2 = project(i, -0.85, 1);
      ctx.beginPath();
      ctx.moveTo(f1.x, f1.y);
      ctx.lineTo(f2.x, f2.y);
      ctx.stroke();

      const f3 = project(-1, -0.85, i);
      const f4 = project(1, -0.85, i);
      ctx.beginPath();
      ctx.moveTo(f3.x, f3.y);
      ctx.lineTo(f4.x, f4.y);
      ctx.stroke();
    }

    const origin = project(-1, -0.85, -1);
    const xEnd = project(1.08, -0.85, -1);
    const yEnd = project(-1, 0.95, -1);
    const zEnd = project(-1, -0.85, 1.08);

    ctx.strokeStyle = "#06b6d4";
    ctx.lineWidth = 2 * dpr;
    ctx.beginPath();
    ctx.moveTo(origin.x, origin.y);
    ctx.lineTo(xEnd.x, xEnd.y);
    ctx.stroke();

    ctx.strokeStyle = "#10b981";
    ctx.beginPath();
    ctx.moveTo(origin.x, origin.y);
    ctx.lineTo(yEnd.x, yEnd.y);
    ctx.stroke();

    ctx.strokeStyle = "#f59e0b";
    ctx.beginPath();
    ctx.moveTo(origin.x, origin.y);
    ctx.lineTo(zEnd.x, zEnd.y);
    ctx.stroke();

    ctx.font = `700 ${Math.round(10 * dpr)}px var(--font-geist-mono), monospace`;
    ctx.fillStyle = "#06b6d4";
    ctx.fillText("X // WATER SAVED (mm/yr)", xEnd.x - 40 * dpr, xEnd.y + 14 * dpr);
    ctx.fillStyle = "#10b981";
    ctx.fillText("Y // NET MARGIN (" + currSym + "/ha)", yEnd.x - 10 * dpr, yEnd.y - 8 * dpr);
    ctx.fillStyle = "#f59e0b";
    ctx.fillText("Z // SOIL HEALTH [0-100]", zEnd.x - 30 * dpr, zEnd.y + 14 * dpr);
    ctx.restore();

    const irrs = strategies.map((s) => {
      const arr = s.results[0]?.irrigation_mm;
      return arr?.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 1000;
    });
    const profits = strategies.map((s) => s.results[0]?.profit_p50 ?? 1000);
    const soils = strategies.map((s) => s.results[0]?.soil_health_score ?? 50);

    const minIrr = Math.min(...irrs);
    const maxIrr = Math.max(...irrs, minIrr + 100);
    const minP = Math.min(...profits);
    const maxP = Math.max(...profits, minP + 100);
    const minS = Math.min(...soils, 25);
    const maxS = Math.max(...soils, 85);

    const mapped = strategies.map((s, idx) => {
      const nx = -0.7 + ((maxIrr - irrs[idx]) / Math.max(1, maxIrr - minIrr)) * 1.4;
      const ny = -0.65 + ((profits[idx] - minP) / Math.max(1, maxP - minP)) * 1.35;
      const nz = -0.7 + ((soils[idx] - minS) / Math.max(1, maxS - minS)) * 1.4;
      const pt = project(nx, ny, nz);
      const floorPt = project(nx, -0.85, nz);
      return {
        strat: s,
        irr: Math.round(irrs[idx]),
        profit: profits[idx],
        soil: Math.round(soils[idx]),
        pt,
        floorPt,
      };
    });

    const nonBase = mapped.filter((m) => m.strat.rank > 0);
    if (nonBase.length >= 2) {
      ctx.save();
      ctx.beginPath();
      nonBase.forEach((m, i) => {
        if (i === 0) ctx.moveTo(m.pt.x, m.pt.y);
        else ctx.lineTo(m.pt.x, m.pt.y);
      });
      if (nonBase.length >= 3) ctx.closePath();
      ctx.fillStyle = "rgba(16, 185, 129, 0.16)";
      ctx.fill();
      ctx.strokeStyle = "rgba(52, 211, 153, 0.75)";
      ctx.lineWidth = 1.6 * dpr;
      ctx.setLineDash([4 * dpr, 3 * dpr]);
      ctx.stroke();
      ctx.restore();
    }

    mapped.sort((a, b) => b.pt.z - a.pt.z);
    hitTargetsRef.current = [];

    for (const item of mapped) {
      const isBase = item.strat.rank === 0;
      const isSelected = selectedRank === item.strat.rank;
      const color = isBase ? "#f43f5e" : item.strat.rank === 1 ? "#10b981" : "#06b6d4";

      ctx.save();
      ctx.strokeStyle = isSelected
        ? color
        : isDark
        ? "rgba(148,163,184,0.28)"
        : "rgba(15,23,42,0.25)";
      ctx.lineWidth = (isSelected ? 1.8 : 1) * dpr;
      ctx.setLineDash([2 * dpr, 2 * dpr]);
      ctx.beginPath();
      ctx.moveTo(item.pt.x, item.pt.y);
      ctx.lineTo(item.floorPt.x, item.floorPt.y);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = color;
      ctx.globalAlpha = 0.35;
      ctx.beginPath();
      ctx.arc(item.floorPt.x, item.floorPt.y, 3.5 * dpr, 0, Math.PI * 2);
      ctx.fill();
      ctx.globalAlpha = 1;

      const radius = (isSelected ? 10 : 7.5) * dpr * item.pt.s;
      if (isSelected) {
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.24;
        ctx.beginPath();
        ctx.arc(item.pt.x, item.pt.y, radius * 1.8, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      }

      const grad = ctx.createRadialGradient(
        item.pt.x - radius * 0.3,
        item.pt.y - radius * 0.3,
        radius * 0.1,
        item.pt.x,
        item.pt.y,
        radius
      );
      grad.addColorStop(0, "#ffffff");
      grad.addColorStop(0.35, color);
      grad.addColorStop(1, "#060b16");

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(item.pt.x, item.pt.y, radius, 0, Math.PI * 2);
      ctx.fill();

      const tag = isBase ? "REF (Baseline)" : `OPT #${item.strat.rank}`;
      ctx.font = `700 ${Math.round(10.5 * dpr)}px var(--font-geist-mono), monospace`;
      ctx.fillStyle = isDark ? "#f1f5f9" : "#0b1324";
      ctx.textAlign = "center";
      ctx.fillText(tag, item.pt.x, item.pt.y - radius - 14 * dpr);

      ctx.font = `500 ${Math.round(9.5 * dpr)}px var(--font-geist-mono), monospace`;
      ctx.fillStyle = isDark ? "rgba(241,245,249,0.75)" : "rgba(11,19,36,0.75)";
      ctx.fillText(
        `${item.irr}mm · ${fmtMoney(item.profit, currSym)} · SH ${item.soil}`,
        item.pt.x,
        item.pt.y - radius - 3 * dpr
      );
      ctx.restore();

      hitTargetsRef.current.push({
        rank: item.strat.rank,
        x: item.pt.x / dpr,
        y: item.pt.y / dpr,
        r: 22,
      });
    }
  }, [strategies, yaw, pitch, selectedRank, currSym]);

  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    isDraggingRef.current = true;
    lastPosRef.current = { x: e.clientX, y: e.clientY };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - lastPosRef.current.x;
    const dy = e.clientY - lastPosRef.current.y;
    lastPosRef.current = { x: e.clientX, y: e.clientY };
    setYaw((y) => y + dx * 0.009);
    setPitch((p) => Math.max(0.15, Math.min(1.0, p + dy * 0.007)));
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    isDraggingRef.current = false;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    for (const t of hitTargetsRef.current) {
      const dist = Math.hypot(mx - t.x, my - t.y);
      if (dist <= t.r) {
        onSelectRank(t.rank);
        break;
      }
    }
  };

  return (
    <div className="relative w-full h-[340px] sm:h-[380px] select-none">
      <canvas
        ref={canvasRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onClick={handleClick}
        className="w-full h-full cursor-grab active:cursor-grabbing block touch-none"
      />
      <div className="absolute top-3 left-3.5 pointer-events-none glass-strong px-3 py-1 rounded-lg border border-line text-[10px] font-mono text-muted">
        Drag to rotate 3D objective space · Click node to inspect rotation
      </div>
      <button
        type="button"
        onClick={() => {
          setYaw(-0.62);
          setPitch(0.42);
        }}
        className="absolute top-3 right-3.5 p-1.5 rounded-lg glass-strong border border-line text-muted hover:text-foreground cursor-pointer"
        title="Reset 3D orientation"
      >
        <RotateCcw className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function ParetoScatterPlot({
  strategies,
  selectedRank,
  onSelectRank,
  currencySymbol = "$",
}: {
  strategies: StrategyRecommendation[];
  selectedRank: number | null;
  onSelectRank: (rank: number) => void;
  currencySymbol?: string;
}) {
  if (!strategies || strategies.length === 0) return null;

  const currSym = strategies[0]?.currency_symbol || currencySymbol;

  const w = 550;
  const h = 220;
  const padL = 70;
  const padR = 30;
  const padT = 30;
  const padB = 40;

  const allProfits = strategies.map((s) => s.results[0]?.profit_p50 ?? 1000);
  const allIrrs = strategies.map((s) => {
    const irrs = s.results[0]?.irrigation_mm;
    return irrs?.length ? irrs.reduce((a, b) => a + b, 0) / irrs.length : 800;
  });

  const rawMinP = Math.min(...allProfits);
  const rawMaxP = Math.max(...allProfits);
  const pMargin = Math.max((rawMaxP - rawMinP) * 0.15, rawMaxP * 0.05, 50);
  const minP = Math.max(0, Math.floor(rawMinP - pMargin));
  const maxP = Math.ceil(rawMaxP + pMargin);

  const rawMinIrr = Math.min(...allIrrs);
  const rawMaxIrr = Math.max(...allIrrs);
  const irrMargin = Math.max((rawMaxIrr - rawMinIrr) * 0.15, 50);
  const minIrr = Math.max(0, Math.floor(rawMinIrr - irrMargin));
  const maxIrr = Math.ceil(rawMaxIrr + irrMargin);

  const midP = Math.round((minP + maxP) / 2);
  const midIrr = Math.round((minIrr + maxIrr) / 2);

  const toX = (irr: number) =>
    padL + ((irr - minIrr) / Math.max(1, maxIrr - minIrr)) * (w - padL - padR);
  const toY = (p: number) =>
    h - padB - ((p - minP) / Math.max(1, maxP - minP)) * (h - padT - padB);

  const formatProfit = (val: number) => fmtMoney(val, currSym);

  const points = strategies.map((s) => {
    const res = s.results[0];
    const irr = res?.irrigation_mm?.length
      ? res.irrigation_mm.reduce((a, b) => a + b, 0) / res.irrigation_mm.length
      : 800;
    const p = res?.profit_p50 ?? 1000;
    const score = res?.soil_health_score ?? 50;
    return {
      rank: s.rank,
      label: s.rotation.label ?? s.rotation.id,
      irr,
      p,
      score,
      x: toX(irr),
      y: toY(p),
      isBase: s.rank === 0,
    };
  });

  return (
    <div className="w-full overflow-hidden">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto select-none font-mono">
        <line
          x1={padL}
          y1={toY(midP)}
          x2={w - padR}
          y2={toY(midP)}
          stroke="currentColor"
          strokeOpacity="0.1"
          strokeDasharray="3 3"
        />
        <line
          x1={padL}
          y1={toY(maxP - pMargin)}
          x2={w - padR}
          y2={toY(maxP - pMargin)}
          stroke="currentColor"
          strokeOpacity="0.1"
          strokeDasharray="3 3"
        />
        <line
          x1={toX(midIrr)}
          y1={padT}
          x2={toX(midIrr)}
          y2={h - padB}
          stroke="currentColor"
          strokeOpacity="0.1"
          strokeDasharray="3 3"
        />

        <line
          x1={padL}
          y1={h - padB}
          x2={w - padR}
          y2={h - padB}
          stroke="currentColor"
          strokeOpacity="0.3"
          strokeWidth="1.5"
        />
        <line
          x1={padL}
          y1={padT}
          x2={padL}
          y2={h - padB}
          stroke="currentColor"
          strokeOpacity="0.3"
          strokeWidth="1.5"
        />

        <text x={padL - 10} y={toY(midP)} textAnchor="end" fontSize="9" fill="currentColor" opacity="0.7" dy="3">
          {formatProfit(midP)}
        </text>
        <text x={padL - 10} y={toY(maxP - pMargin)} textAnchor="end" fontSize="9" fill="currentColor" opacity="0.7" dy="3">
          {formatProfit(maxP - pMargin)}
        </text>
        <text x={toX(minIrr + irrMargin)} y={h - padB + 16} textAnchor="middle" fontSize="9" fill="currentColor" opacity="0.7">
          {Math.round(minIrr + irrMargin)}mm
        </text>
        <text x={toX(midIrr)} y={h - padB + 16} textAnchor="middle" fontSize="9" fill="currentColor" opacity="0.7">
          {Math.round(midIrr)}mm
        </text>
        <text x={toX(maxIrr - irrMargin)} y={h - padB + 16} textAnchor="middle" fontSize="9" fill="currentColor" opacity="0.7">
          {Math.round(maxIrr - irrMargin)}mm
        </text>

        <text x={w / 2} y={h - 6} textAnchor="middle" fontSize="10" fontWeight="bold" fill="currentColor" opacity="0.85">
          Net Irrigation Demand [mm/yr]
        </text>

        {points.filter((pt) => !pt.isBase).length > 1 && (
          <path
            d={points
              .filter((pt) => !pt.isBase)
              .sort((a, b) => a.x - b.x)
              .reduce((acc, curr, idx) => `${acc} ${idx === 0 ? "M" : "L"} ${curr.x} ${curr.y}`, "")}
            fill="none"
            stroke="#10b981"
            strokeWidth="2"
            strokeDasharray="4 3"
          />
        )}

        {points.map((pt) => {
          const isSelected = selectedRank === pt.rank;
          const color = pt.isBase ? "#f43f5e" : pt.score > 70 ? "#10b981" : "#06b6d4";
          return (
            <g
              key={pt.rank}
              className="cursor-pointer transition-all"
              onClick={() => onSelectRank(pt.rank)}
            >
              {isSelected && (
                <circle cx={pt.x} cy={pt.y} r="14" fill={color} fillOpacity="0.25" />
              )}
              <circle
                cx={pt.x}
                cy={pt.y}
                r={isSelected ? "8" : "6"}
                fill={color}
                stroke="#ffffff"
                strokeWidth="2"
              />
              <text
                x={pt.x}
                y={pt.y - 11}
                textAnchor="middle"
                fontSize="10"
                fontWeight="bold"
                fill={pt.isBase ? "#f43f5e" : "#10b981"}
              >
                {pt.isBase ? "REF" : `OPT 0${pt.rank}`}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
