"use client";

import { useEffect, useState } from "react";
import type {
  FarmConstraints,
  FieldGeometry,
  FieldProfile,
  Priorities,
  StrategyRecommendation,
} from "@/types/api";
import { useI18n } from "@/i18n";
import { ProvenanceChip } from "./ProvenanceChip";
import { cropMeta, cropName, fmtMoney, isSouthAsia } from "@/lib/ui";
import { getFallbackStrategies } from "@/lib/fallbackStrategies";
import { api } from "@/lib/api";
import {
  Sparkles,
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
  Info,
  ChevronRight,
  ShieldCheck,
} from "lucide-react";

interface Props {
  field: FieldGeometry;
  profile?: FieldProfile;
  initialTab?: "cards" | "pareto" | "whatif";
  onStrategiesLoaded?: (strategies: StrategyRecommendation[]) => void;
  strategies?: StrategyRecommendation[];
  loading?: boolean;
}

export function RotationExplorer({
  field,
  profile,
  initialTab,
  onStrategiesLoaded,
  strategies: externalStrategies,
  loading: externalLoading,
}: Props) {
  const { t, lang } = useI18n();

  const isSA = isSouthAsia(field.lat, field.lon);
  const currencySymbol = profile?.currency_symbol ?? (isSA ? "₹" : "$");

  const [priorities, setPriorities] = useState<Priorities>({
    profit: 1.0,
    water_savings: 1.5,
    soil_health: 1.2,
    low_risk: 1.0,
    low_labour: 0.0,
    food_security: 0.0,
  });

  const [constraints, setConstraints] = useState<FarmConstraints>({
    area_ha: 2.0,
    irrigation: "limited",
    irrigation_cap_mm: undefined,
    must_grow: [],
    exclude: [],
    has_livestock: false,
    rotation_years: 1,
  });

  const [internalStrategies, setInternalStrategies] = useState<StrategyRecommendation[]>([]);
  const [internalLoading, setInternalLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"cards" | "pareto" | "whatif">(initialTab ?? "cards");
  const [selectedRank, setSelectedRank] = useState<number | null>(null);

  // What-If Shock parameters (TASK-F06)
  const [droughtShockPct, setDroughtShockPct] = useState<number>(15);
  const [priceShockPct, setPriceShockPct] = useState<number>(-5);
  const [fertilizerShockPct, setFertilizerShockPct] = useState<number>(25);

  const strategies = externalStrategies ?? internalStrategies;
  const loading = externalLoading ?? internalLoading;

  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);

  const fetchRecommendations = async () => {
    setInternalLoading(true);
    try {
      const recs = await api.recommend({
        field,
        priorities,
        constraints,
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
    if (!externalStrategies && field) {
      fetchRecommendations();
    }
  }, [field.lat, field.lon]);

  const baseline = strategies.find((s) => s.rank === 0) ?? strategies[0];
  const candidates = strategies.filter((s) => s.rank > 0);

  const applyPreset = (type: "balanced" | "water" | "profit" | "soil" | "resilient") => {
    let newP: Priorities = { ...priorities };
    if (type === "balanced") {
      newP = { ...newP, water_savings: 1.5, profit: 1.5, soil_health: 1.5, low_risk: 1.5 };
    } else if (type === "water") {
      newP = { ...newP, water_savings: 3.0, profit: 0.8, soil_health: 1.2, low_risk: 1.0 };
    } else if (type === "profit") {
      newP = { ...newP, profit: 3.0, water_savings: 0.8, soil_health: 0.8, low_risk: 1.0 };
    } else if (type === "soil") {
      newP = { ...newP, soil_health: 3.0, water_savings: 1.5, profit: 0.8, low_risk: 1.2 };
    } else if (type === "resilient") {
      newP = { ...newP, low_risk: 3.0, water_savings: 2.0, profit: 0.8, soil_health: 1.5 };
    }
    setPriorities(newP);
  };

  return (
    <div className="glass rounded-3xl p-6 sm:p-8 border border-line shadow-lg space-y-7">
      {/* Section Header with Mode Navigation & Export */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-3 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
              Multi-Objective Pareto Optimization
            </span>
            <span className="text-xs text-muted font-mono hidden sm:inline">
              AquaCrop 3.1 · RothC-Lite
            </span>
          </div>
          <h3 className="font-display text-2xl font-black text-foreground mt-1 tracking-tight">
            {lang === "pa"
              ? "ਫ਼ਸਲੀ ਚੱਕਰ ਅਨੁਕੂਲਨ ਅਤੇ ਸਿਫ਼ਾਰਿਸ਼ਾਂ"
              : lang === "hi"
              ? "फसल चक्र अनुकूलन एवं अनुशंसित रणनीतियां"
              : "Crop Rotation Decision Engine"}
          </h3>
        </div>

        {/* View Mode Navigation & Export Toolbar */}
        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => window.print()}
            className="px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-surface hover:bg-foreground/5 text-foreground border border-line shadow-2xs flex items-center gap-1.5 transition-all cursor-pointer"
            title="Export / Print one-page Field Agronomic Brief"
          >
            <Printer className="w-3.5 h-3.5 text-emerald-500" />
            <span>Export Brief</span>
          </button>

          <div className="inline-flex rounded-xl bg-surface p-1 border border-line text-xs shadow-2xs">
            <button
              onClick={() => setActiveTab("cards")}
              className={`px-3 py-1 rounded-lg font-semibold transition-all duration-200 cursor-pointer ${
                activeTab === "cards"
                  ? "bg-emerald-600 text-white shadow-xs"
                  : "text-muted hover:text-foreground"
              }`}
            >
              Strategy Cards
            </button>
            <button
              onClick={() => setActiveTab("pareto")}
              className={`px-3 py-1 rounded-lg font-semibold transition-all duration-200 cursor-pointer flex items-center gap-1.5 ${
                activeTab === "pareto"
                  ? "bg-emerald-600 text-white shadow-xs"
                  : "text-muted hover:text-foreground"
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Pareto Frontier</span>
            </button>
            <button
              onClick={() => setActiveTab("whatif")}
              className={`px-3 py-1 rounded-lg font-semibold transition-all duration-200 cursor-pointer flex items-center gap-1.5 ${
                activeTab === "whatif"
                  ? "bg-emerald-600 text-white shadow-xs"
                  : "text-muted hover:text-foreground"
              }`}
            >
              <FlaskConical className="w-3.5 h-3.5" />
              <span>What-If Stress Lab</span>
            </button>
          </div>
        </div>
      </div>

      {/* Priorities & Farm Constraints Control Panel */}
      <div className="p-5 sm:p-6 rounded-3xl bg-surface/80 border border-line shadow-xs space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-emerald-500" />
            <h4 className="font-display font-bold text-sm text-foreground">
              {t("section.priorities")}
            </h4>
          </div>

          {/* Quick Presets */}
          <div className="flex items-center gap-1.5 flex-wrap text-xs">
            <span className="text-[11px] text-muted font-medium pr-1">Presets:</span>
            <button
              onClick={() => applyPreset("balanced")}
              className="px-2.5 py-1 rounded-lg bg-foreground/5 hover:bg-emerald-500/10 hover:text-emerald-500 border border-line text-[11px] font-medium transition-colors cursor-pointer"
            >
              Balanced
            </button>
            <button
              onClick={() => applyPreset("water")}
              className="px-2.5 py-1 rounded-lg bg-foreground/5 hover:bg-cyan-500/10 hover:text-cyan-500 border border-line text-[11px] font-medium transition-colors cursor-pointer"
            >
              💧 Water Saver
            </button>
            <button
              onClick={() => applyPreset("profit")}
              className="px-2.5 py-1 rounded-lg bg-foreground/5 hover:bg-emerald-500/10 hover:text-emerald-500 border border-line text-[11px] font-medium transition-colors cursor-pointer"
            >
              💰 Max Profit
            </button>
            <button
              onClick={() => applyPreset("soil")}
              className="px-2.5 py-1 rounded-lg bg-foreground/5 hover:bg-amber-500/10 hover:text-amber-500 border border-line text-[11px] font-medium transition-colors cursor-pointer"
            >
              🌱 Soil Health
            </button>
            <button
              onClick={() => applyPreset("resilient")}
              className="px-2.5 py-1 rounded-lg bg-foreground/5 hover:bg-purple-500/10 hover:text-purple-500 border border-line text-[11px] font-medium transition-colors cursor-pointer"
            >
              🛡️ Climate Resilient
            </button>
          </div>
        </div>

        {/* Sliders Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-1">
          {/* Water Conservation */}
          <div className="space-y-2 p-3 rounded-2xl bg-foreground/5 border border-line/60">
            <div className="flex justify-between items-center text-xs">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <Droplets className="w-3.5 h-3.5 text-cyan-400" />
                <span>{t("priorities.water")}</span>
              </span>
              <span className="font-mono font-bold text-cyan-500">{priorities.water_savings.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0"
              max="3"
              step="0.5"
              value={priorities.water_savings}
              onChange={(e) => setPriorities({ ...priorities, water_savings: parseFloat(e.target.value) })}
              className="w-full accent-cyan-500 cursor-pointer"
            />
          </div>

          {/* Profit Maximization */}
          <div className="space-y-2 p-3 rounded-2xl bg-foreground/5 border border-line/60">
            <div className="flex justify-between items-center text-xs">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <Coins className="w-3.5 h-3.5 text-emerald-400" />
                <span>{t("priorities.profit")}</span>
              </span>
              <span className="font-mono font-bold text-emerald-500">{priorities.profit.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0"
              max="3"
              step="0.5"
              value={priorities.profit}
              onChange={(e) => setPriorities({ ...priorities, profit: parseFloat(e.target.value) })}
              className="w-full accent-emerald-500 cursor-pointer"
            />
          </div>

          {/* Soil Carbon & Health */}
          <div className="space-y-2 p-3 rounded-2xl bg-foreground/5 border border-line/60">
            <div className="flex justify-between items-center text-xs">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <Sprout className="w-3.5 h-3.5 text-amber-400" />
                <span>{t("priorities.soil")}</span>
              </span>
              <span className="font-mono font-bold text-amber-500">{priorities.soil_health.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0"
              max="3"
              step="0.5"
              value={priorities.soil_health}
              onChange={(e) => setPriorities({ ...priorities, soil_health: parseFloat(e.target.value) })}
              className="w-full accent-amber-500 cursor-pointer"
            />
          </div>

          {/* Climate Resilience */}
          <div className="space-y-2 p-3 rounded-2xl bg-foreground/5 border border-line/60">
            <div className="flex justify-between items-center text-xs">
              <span className="font-semibold text-foreground flex items-center gap-1.5">
                <ShieldAlert className="w-3.5 h-3.5 text-purple-400" />
                <span>{t("priorities.risk")}</span>
              </span>
              <span className="font-mono font-bold text-purple-500">{priorities.low_risk.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0"
              max="3"
              step="0.5"
              value={priorities.low_risk}
              onChange={(e) => setPriorities({ ...priorities, low_risk: parseFloat(e.target.value) })}
              className="w-full accent-purple-500 cursor-pointer"
            />
          </div>
        </div>

        {/* Constraint Bar & Re-simulate Action */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-3 border-t border-line text-xs">
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer font-medium text-foreground/80">
              <input
                type="checkbox"
                checked={constraints.has_livestock}
                onChange={(e) => setConstraints({ ...constraints, has_livestock: e.target.checked })}
                className="w-4 h-4 rounded accent-emerald-600 cursor-pointer"
              />
              <span>Dairy / Livestock present on farm</span>
            </label>

            <div className="flex items-center gap-2">
              <span className="text-muted">Irrigation:</span>
              <select
                value={constraints.irrigation}
                onChange={(e) =>
                  setConstraints({
                    ...constraints,
                    irrigation: e.target.value as "none" | "limited" | "full",
                  })
                }
                className="px-2.5 py-1 rounded-xl border border-line bg-surface text-foreground text-xs outline-none cursor-pointer"
              >
                <option value="limited">Tube-well (Restricted)</option>
                <option value="full">Tube-well / Canal (Full)</option>
                <option value="none">Rainfed Only</option>
              </select>
            </div>
          </div>

          <button
            onClick={fetchRecommendations}
            disabled={loading}
            className="px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-md transition-all disabled:opacity-50 cursor-pointer flex items-center gap-2"
          >
            {loading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>{t("priorities.optimizing")}</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>{t("priorities.optimize")}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* VIEW MODE 1: Comparative Cards */}
      {activeTab === "cards" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-display font-bold text-base text-foreground flex items-center gap-2">
              <span>📊</span> Comparative Performance vs Farm Baseline
            </h4>
            <span className="text-xs text-muted">
              Select card to spotlight on Pareto curve
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Baseline Card */}
            {baseline && (
              <StrategyCard
                strategy={baseline}
                isBaseline={true}
                isSelected={selectedRank === 0}
                onSelect={() => setSelectedRank(selectedRank === 0 ? null : 0)}
                currencySymbol={currencySymbol}
              />
            )}

            {/* Top 3 Recommendation Cards */}
            {candidates.map((strat) => (
              <StrategyCard
                key={strat.rank}
                strategy={strat}
                isBaseline={false}
                isSelected={selectedRank === strat.rank}
                onSelect={() => setSelectedRank(selectedRank === strat.rank ? null : strat.rank)}
                currencySymbol={currencySymbol}
              />
            ))}
          </div>
        </div>
      )}

      {/* VIEW MODE 2: Pareto Multi-Objective Frontier Plot */}
      {activeTab === "pareto" && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-display font-bold text-base text-foreground flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              <span>Pareto Trade-off Frontier (Irrigation vs Profit)</span>
            </h4>
            <span className="text-xs text-muted font-mono">
              X: Net Irrigation (Lower is Better) · Y: Expected Profit (Higher is Better)
            </span>
          </div>

          <div className="p-6 rounded-3xl bg-surface border border-line shadow-xs">
            <ParetoScatterPlot
              strategies={strategies}
              selectedRank={selectedRank}
              onSelectRank={(r) => setSelectedRank(r)}
              currencySymbol={currencySymbol}
            />
          </div>

          {/* Cards below plot for quick reference */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 pt-2">
            {baseline && (
              <StrategyCard
                strategy={baseline}
                isBaseline={true}
                isSelected={selectedRank === 0}
                onSelect={() => setSelectedRank(selectedRank === 0 ? null : 0)}
                currencySymbol={currencySymbol}
              />
            )}
            {candidates.map((strat) => (
              <StrategyCard
                key={strat.rank}
                strategy={strat}
                isBaseline={false}
                isSelected={selectedRank === strat.rank}
                onSelect={() => setSelectedRank(selectedRank === strat.rank ? null : strat.rank)}
                currencySymbol={currencySymbol}
              />
            ))}
          </div>
        </div>
      )}

      {/* VIEW MODE 3: What-If Stress Lab */}
      {activeTab === "whatif" && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-display font-bold text-base text-foreground flex items-center gap-2">
              <FlaskConical className="w-4 h-4 text-amber-400" />
              <span>What-If Climate &amp; Economic Shock Lab</span>
            </h4>
            <span className="text-xs text-muted">
              Live stress-testing against evaporative drought shocks, fertilizer spikes, and market drops
            </span>
          </div>

          {/* Shock Sliders */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-5 rounded-3xl bg-amber-500/10 border border-amber-500/20">
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="font-semibold text-amber-700 dark:text-amber-300">
                  ☀️ Drought / ET Shock:
                </span>
                <span className="font-mono font-bold text-amber-600 dark:text-amber-400">+{droughtShockPct}%</span>
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
              <span className="text-[10px] text-muted block">Boosts crop evapotranspiration &amp; pumping hours</span>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="font-semibold text-blue-700 dark:text-blue-300">
                  📉 Harvest Price Shock:
                </span>
                <span className="font-mono font-bold text-blue-600 dark:text-blue-400">{priceShockPct}%</span>
              </div>
              <input
                type="range"
                min="-25"
                max="25"
                step="5"
                value={priceShockPct}
                onChange={(e) => setPriceShockPct(parseInt(e.target.value))}
                className="w-full accent-blue-500 cursor-pointer"
              />
              <span className="text-[10px] text-muted block">Market sale price swings vs CACP MSP</span>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="font-semibold text-rose-700 dark:text-rose-300">
                  🧪 Urea / N Fertilizer Spike:
                </span>
                <span className="font-mono font-bold text-rose-600 dark:text-rose-400">+{fertilizerShockPct}%</span>
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
              <span className="text-[10px] text-muted block">Legume rotations absorb shock via biological N credit</span>
            </div>
          </div>

          {/* Stressed Performance Comparative Matrix */}
          <div className="overflow-x-auto rounded-2xl border border-line shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-foreground/5 text-foreground font-bold border-b border-line">
                <tr>
                  <th className="py-3 px-4">Rotation Strategy</th>
                  <th className="py-3 px-3">Normal Margin</th>
                  <th className="py-3 px-3">Stressed Margin</th>
                  <th className="py-3 px-3">Downside Drop</th>
                  <th className="py-3 px-3">Stressed Irrigation</th>
                  <th className="py-3 px-3">Climate Buffer</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line text-foreground/90">
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
                          ? "bg-rose-500/10 font-medium"
                          : "hover:bg-foreground/5 transition-colors"
                      }
                    >
                      <td className="py-3 px-4 font-bold flex items-center gap-2">
                        <span>{isBase ? "⚠️" : "🛡️"}</span>
                        <span>{strat.rotation.label ?? strat.rotation.id}</span>
                      </td>
                      <td className="py-3 px-3 font-mono">{fmtMoney(normP, currencySymbol)}</td>
                      <td className="py-3 px-3 font-mono font-bold text-emerald-500 dark:text-emerald-400">
                        {fmtMoney(stressedP, currencySymbol)}
                      </td>
                      <td className="py-3 px-3 font-mono text-rose-500">
                        -{fmtMoney(drop, currencySymbol)}
                      </td>
                      <td className="py-3 px-3 font-mono">{stressedIrr} mm/yr</td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            drop < dropThreshold
                              ? "bg-emerald-500/15 text-emerald-500 border border-emerald-500/30"
                              : "bg-rose-500/15 text-rose-500 border border-rose-500/30"
                          }`}
                        >
                          {drop < dropThreshold ? "High Resilience" : "High Regret"}
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
  );
}

function StrategyCard({
  strategy,
  isBaseline,
  isSelected,
  onSelect,
  currencySymbol = "$",
}: {
  strategy: StrategyRecommendation;
  isBaseline: boolean;
  isSelected: boolean;
  onSelect: () => void;
  currencySymbol?: string;
}) {
  const { t } = useI18n();
  const currSym = strategy.currency_symbol || currencySymbol;
  const res = strategy.results[0];
  const irr = res?.irrigation_mm?.length
    ? Math.round(res.irrigation_mm.reduce((a, b) => a + b, 0) / res.irrigation_mm.length)
    : 1200;

  const waterChange = strategy.vs_baseline?.irrigation_change_pct ?? strategy.vs_baseline?.irrigation_pct;
  const waterSavedPct = waterChange !== undefined ? -Math.round(waterChange) : 0;
  const resilienceScore = strategy.vs_baseline?.climate_resilience_score;

  const cardBorder = isBaseline
    ? "border-line bg-surface/60"
    : strategy.rank === 1
    ? "border-emerald-500/50 bg-emerald-500/5 shadow-md ring-1 ring-emerald-500/20"
    : "border-blue-500/40 bg-blue-500/5";

  const selectedRing = isSelected ? "ring-2 ring-emerald-500 shadow-xl" : "";

  return (
    <div
      onClick={onSelect}
      className={`rounded-3xl border p-5 flex flex-col justify-between transition-all duration-200 cursor-pointer hover:-translate-y-1 ${cardBorder} ${selectedRing}`}
    >
      <div className="space-y-3.5">
        {/* Header Badges */}
        <div className="flex items-center justify-between">
          <span
            className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${
              isBaseline
                ? "bg-foreground/10 text-muted"
                : strategy.rank === 1
                ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                : "bg-blue-500/20 text-blue-600 dark:text-blue-400 border border-blue-500/30"
            }`}
          >
            {isBaseline ? t("strategy.baseline") : `Strategy ${strategy.rank} · Top Pick`}
          </span>

          <div className="flex items-center gap-1.5">
            {!isBaseline && waterSavedPct > 0 && (
              <span className="text-[11px] font-black text-cyan-500 dark:text-cyan-400 flex items-center gap-0.5">
                <Droplets className="w-3 h-3" /> {waterSavedPct}% Saved
              </span>
            )}
            {resilienceScore !== undefined && (
              <span
                className="text-[10px] font-bold px-1.5 py-0.2 rounded-md bg-purple-500/15 text-purple-600 dark:text-purple-400 border border-purple-500/30"
                title="Climate Resilience Index"
              >
                🛡️ {Math.round(resilienceScore)}/100
              </span>
            )}
          </div>
        </div>

        {/* Rotation Name & Sequence */}
        <div>
          <h4 className="font-display font-extrabold text-sm text-foreground leading-snug">
            {strategy.rotation.label ?? strategy.rotation.id}
          </h4>

          {/* Sequence Flow */}
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            {strategy.rotation.steps.map((step, idx) => {
              const meta = cropMeta(step.crop_id);
              return (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[11px] font-semibold bg-surface border border-line shadow-2xs"
                >
                  <span>{meta.emoji}</span>
                  <span className="capitalize">{cropName(step.crop_id)}</span>
                  {step.practices.includes("residue_retained") && <span title="Mulched">🌿</span>}
                </span>
              );
            })}
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="pt-2 border-t border-line space-y-2 text-xs">
          <div className="flex justify-between items-center">
            <span className="text-muted">Net Irrigation:</span>
            <span
              className={`font-black font-mono ${
                isBaseline ? "text-rose-500" : "text-emerald-500 dark:text-emerald-400"
              }`}
            >
              {irr} mm/yr
            </span>
          </div>

          <div className="flex justify-between items-center">
            <span className="text-muted">{t("strategy.profitRange")}:</span>
            <span className="font-bold text-foreground font-mono">
              {fmtMoney(res?.profit_p50, currSym)}{" "}
              <span className="text-[10px] text-muted font-normal">
                ({fmtMoney(res?.profit_p10, currSym)}–{fmtMoney(res?.profit_p90, currSym)})
              </span>
            </span>
          </div>

          <div className="flex justify-between items-center">
            <span className="text-muted">{t("strategy.soilHealthScore")}:</span>
            <div className="flex items-center gap-2">
              <div className="w-12 h-1.5 rounded-full bg-foreground/10 overflow-hidden">
                <div
                  style={{ width: `${Math.min(res?.soil_health_score ?? 40, 100)}%` }}
                  className={`h-full ${
                    (res?.soil_health_score ?? 40) > 60 ? "bg-emerald-500" : "bg-amber-500"
                  }`}
                />
              </div>
              <span className="font-bold font-mono text-foreground">
                {Math.round(res?.soil_health_score ?? 40)}/100
              </span>
            </div>
          </div>

          <div className="flex justify-between items-center">
            <span className="text-muted">{t("strategy.socTrajectory")}:</span>
            <span
              className={`font-bold font-mono ${
                (res?.soc_delta_t_ha_10yr ?? 0) >= 0
                  ? "text-emerald-500 dark:text-emerald-400"
                  : "text-rose-500"
              }`}
            >
              {(res?.soc_delta_t_ha_10yr ?? 0) > 0 ? "+" : ""}
              {(res?.soc_delta_t_ha_10yr ?? -0.8).toFixed(1)} t C/ha
            </span>
          </div>
        </div>

        {/* Why this works / Evidence points */}
        {strategy.why && strategy.why.length > 0 && (
          <div className="pt-2 border-t border-line">
            <p className="text-[10px] font-black uppercase tracking-wider text-muted mb-1.5">
              {t("strategy.whyThisWorks")}
            </p>
            <ul className="space-y-1 text-[11px] text-foreground/80 leading-relaxed">
              {strategy.why.slice(0, 2).map((item, idx) => (
                <li key={idx} className="flex items-start gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
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

  const toX = (irr: number) => padL + ((irr - minIrr) / Math.max(1, maxIrr - minIrr)) * (w - padL - padR);
  const toY = (p: number) => h - padB - ((p - minP) / Math.max(1, maxP - minP)) * (h - padT - padB);

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
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto select-none font-sans">
        {/* Background Grid Lines */}
        <line x1={padL} y1={toY(midP)} x2={w - padR} y2={toY(midP)} stroke="currentColor" strokeOpacity="0.08" strokeDasharray="3 3" />
        <line x1={padL} y1={toY(maxP - pMargin)} x2={w - padR} y2={toY(maxP - pMargin)} stroke="currentColor" strokeOpacity="0.08" strokeDasharray="3 3" />
        <line x1={toX(midIrr)} y1={padT} x2={toX(midIrr)} y2={h - padB} stroke="currentColor" strokeOpacity="0.08" strokeDasharray="3 3" />

        {/* Axes */}
        <line x1={padL} y1={h - padB} x2={w - padR} y2={h - padB} stroke="currentColor" strokeOpacity="0.3" strokeWidth="1.5" />
        <line x1={padL} y1={padT} x2={padL} y2={h - padB} stroke="currentColor" strokeOpacity="0.3" strokeWidth="1.5" />

        {/* Axis Labels */}
        <text x={padL - 10} y={toY(midP)} textAnchor="end" fontSize="9" fill="currentColor" opacity="0.6" dy="3">
          {formatProfit(midP)}
        </text>
        <text x={padL - 10} y={toY(maxP - pMargin)} textAnchor="end" fontSize="9" fill="currentColor" opacity="0.6" dy="3">
          {formatProfit(maxP - pMargin)}
        </text>
        <text x={toX(minIrr + irrMargin)} y={h - padB + 16} textAnchor="middle" fontSize="9" fill="currentColor" opacity="0.6">
          {Math.round(minIrr + irrMargin)}mm
        </text>
        <text x={toX(midIrr)} y={h - padB + 16} textAnchor="middle" fontSize="9" fill="currentColor" opacity="0.6">
          {Math.round(midIrr)}mm
        </text>
        <text x={toX(maxIrr - irrMargin)} y={h - padB + 16} textAnchor="middle" fontSize="9" fill="currentColor" opacity="0.6">
          {Math.round(maxIrr - irrMargin)}mm
        </text>

        <text x={w / 2} y={h - 6} textAnchor="middle" fontSize="10" fontWeight="bold" fill="currentColor" opacity="0.8">
          Net Irrigation Demand (mm/year)
        </text>

        {/* Frontier Line */}
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

        {/* Points */}
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
                <circle cx={pt.x} cy={pt.y} r="14" fill={color} fillOpacity="0.25" className="animate-pulse" />
              )}
              <circle
                cx={pt.x}
                cy={pt.y}
                r={isSelected ? "8" : "6"}
                fill={color}
                stroke="#ffffff"
                strokeWidth="2"
                className="transition-transform hover:scale-125"
              />
              <text
                x={pt.x}
                y={pt.y - 11}
                textAnchor="middle"
                fontSize="10"
                fontWeight="black"
                fill={pt.isBase ? "#e11d48" : "#10b981"}
              >
                {pt.isBase ? "Baseline" : `S${pt.rank}`}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
