"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type {
  ClimateScenarioId,
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
import { api, recommendWithProgress, type ProgressStage } from "@/lib/api";
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
  Wheat,
  AlertTriangle,
  Globe,
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
    crops,
    priorities,
    setPriorities,
    constraints,
    setConstraints,
    selectedRank,
    setSelectedRank,
    unitSystem,
    soilHealthCard,
    baselineOverride,
    setBaselineOverride,
  } = useField();

  const availableCropIds =
    crops.length > 0
      ? crops.map((c) => c.id).filter((id) => id !== "fallow")
      : [
          "rice_puddled",
          "rice_dsr",
          "rice_short",
          "basmati",
          "wheat",
          "maize",
          "moong",
          "chickpea",
          "mustard",
          "cotton",
          "soybean",
          "groundnut",
          "pearl_millet",
          "sorghum",
          "pigeon_pea",
          "lentil",
          "barley",
          "potato",
          "common_bean",
          "sunflower",
          "berseem",
          "urad",
          "dhaincha",
        ];

  const [isBaselineConfirmed, setIsBaselineConfirmed] = useState<boolean>(false);
  const [showBaselineSelector, setShowBaselineSelector] = useState<boolean>(false);
  const [customKharif, setCustomKharif] = useState<string>("rice_puddled");
  const [customRabi, setCustomRabi] = useState<string>("wheat");
  const [customZaid, setCustomZaid] = useState<string>("fallow");
  const [simProgress, setSimProgress] = useState<{
    stage: ProgressStage;
    progressPct: number;
    message?: string;
  } | null>(null);

  const isSA = isSouthAsia(field.lat, field.lon);
  const isSH = field.lat < 0;
  const currencySymbol = profile?.currency_symbol ?? (isSA ? "₹" : "$");
  const gwTrend = profile?.water?.groundwater_trend_cm_per_year ?? 0;
  const graceMult = gwTrend < -1.0 ? Math.min(1.5, 1.0 + 0.1 * (Math.abs(gwTrend) - 1.0)) : 1.0;
  const fieldKey = `${field.lat},${field.lon}`;
  const GOLDEN_IDS = new Set(["sangrur", "ludhiana", "bathinda", "bundelkhand", "vidarbha", "thanjavur"]);

  const [internalData, setInternalData] = useState<{ key: string; list: StrategyRecommendation[] }>({
    key: fieldKey,
    list: [],
  });
  const internalStrategies = internalData.key === fieldKey ? internalData.list : [];
  const setInternalStrategies = (list: StrategyRecommendation[]) =>
    setInternalData({ key: fieldKey, list });

  const [internalLoading, setInternalLoading] = useState(false);
  const autoFetchInFlightRef = useRef<string | null>(null);
  const [tabState, setTabState] = useState<{
    propTab?: "cards" | "pareto" | "whatif";
    tab: "cards" | "pareto" | "whatif";
  }>({ propTab: initialTab, tab: initialTab ?? "cards" });
  const activeTab = tabState.propTab === initialTab ? tabState.tab : (initialTab ?? "cards");
  const setActiveTab = (tab: "cards" | "pareto" | "whatif") =>
    setTabState({ propTab: initialTab, tab });

  const [paretoViewMode, setParetoViewMode] = useState<"3d" | "2d">("3d");

  // What-If Shock & CMIP6 Climate Horizon parameters (TASK-F06, TASK-C02)
  const [climateScenario, setClimateScenario] = useState<ClimateScenarioId>("historical");
  const [droughtShockPct, setDroughtShockPct] = useState<number>(15);
  const [priceShockPct, setPriceShockPct] = useState<number>(-5);
  const [fertilizerShockPct, setFertilizerShockPct] = useState<number>(25);
  const [stressedData, setStressedData] = useState<{
    key: string;
    list: StrategyRecommendation[] | null;
  }>({ key: fieldKey, list: null });
  const stressedStrategies = stressedData.key === fieldKey ? stressedData.list : null;
  const setStressedStrategies = (list: StrategyRecommendation[] | null) =>
    setStressedData({ key: fieldKey, list });
  const [stressLoading, setStressLoading] = useState<boolean>(false);
  const [stressError, setStressError] = useState<string | null>(null);

  const strategies = internalStrategies.length > 0 ? internalStrategies : (externalStrategies ?? []);
  const loading = Boolean(externalLoading || internalLoading);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const reusableProfile =
    profile &&
    !profile.is_fallback &&
    !(profile.soil?.source === "farmer_test" && !soilHealthCard) &&
    Math.abs(profile.field.lat - field.lat) < 1e-4 &&
    Math.abs(profile.field.lon - field.lon) < 1e-4
      ? profile
      : undefined;

  const fetchRecommendations = async (overrideP?: Priorities, overrideC?: FarmConstraints) => {
    const pToUse = overrideP ?? priorities;
    const cToUse = overrideC ?? constraints;
    setInternalLoading(true);
    setSuccessBanner(null);
    setErrorBanner(null);
    setSimProgress({ stage: "profile", progressPct: 15, message: t("async.stage.profile") });
    autoFetchInFlightRef.current = fieldKey;
    try {
      const recs = await recommendWithProgress(
        {
          field,
          priorities: pToUse,
          constraints: cToUse,
          language: (lang as "en" | "pa" | "hi") || "en",
          soil_health_card: soilHealthCard,
          profile: reusableProfile,
          baseline_override: baselineOverride,
          climate_scenario: climateScenario,
        },
        (status) => setSimProgress(status)
      );
      if (recs && recs.length > 0) {
        setInternalStrategies(recs);
        onStrategiesLoaded?.(recs);
        setSuccessBanner(t("priorities.generatedSuccess", { count: String(Math.max(1, recs.length - 1)) }));
        setTimeout(() => setSuccessBanner(null), 4000);
      }
    } catch (err) {
      console.warn("Backend /recommend failed", err);
      const isGolden = field?.id && GOLDEN_IDS.has(field.id);
      if (isGolden) {
        const fallback = getFallbackStrategies(
          field,
          currencySymbol,
          cToUse.rotation_years,
          (lang as "en" | "pa" | "hi") || "en"
        );
        setInternalStrategies(fallback);
        onStrategiesLoaded?.(fallback);
        setErrorBanner(t("error.recommendFailedDemo"));
      } else {
        setInternalStrategies([]);
        onStrategiesLoaded?.([]);
        setErrorBanner(t("error.recommendFailedCustom"));
      }
    } finally {
      setInternalLoading(false);
      setSimProgress(null);
    }
  };

  const runStressSimulation = async (overrideScenario?: ClimateScenarioId) => {
    const scen = overrideScenario ?? climateScenario;
    setStressLoading(true);
    setStressError(null);
    try {
      const recs = await api.recommend({
        field,
        priorities,
        constraints,
        language: (lang as "en" | "pa" | "hi") || "en",
        soil_health_card: soilHealthCard,
        profile: reusableProfile,
        baseline_override: baselineOverride,
        climate_scenario: scen,
        drought_shock_pct: droughtShockPct,
        price_shock_pct: priceShockPct,
        fertilizer_shock_pct: fertilizerShockPct,
      });
      if (recs && recs.length > 0) {
        setStressedStrategies(recs);
      }
    } catch (err) {
      console.warn("Stress simulation failed; showing sensitivity estimate", err);
      setStressError(t("whatif.engineFallbackNotice"));
    } finally {
      setStressLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    if (typeof window !== "undefined" && window.sessionStorage) {
      const activeJobId = sessionStorage.getItem("terraloop_active_job_id");
      if (activeJobId && !externalStrategies) {
        autoFetchInFlightRef.current = fieldKey;
        setInternalLoading(true);
        const resumeExistingJob = async () => {
          try {
            const started = Date.now();
            while (!cancelled && Date.now() - started < 60000) {
              const poll = await api.getRecommendJob(activeJobId);
              if (cancelled) return;
              if (poll.status === "completed" && poll.result) {
                sessionStorage.removeItem("terraloop_active_job_id");
                setInternalStrategies(poll.result);
                onStrategiesLoaded?.(poll.result);
                setInternalLoading(false);
                setSimProgress(null);
                return;
              }
              if (poll.status === "failed") {
                sessionStorage.removeItem("terraloop_active_job_id");
                break;
              }
              if (poll.status === "running") {
                setSimProgress({
                  stage: (poll.stage || poll.step || "simulating") as
                    | "profile"
                    | "weather"
                    | "simulating"
                    | "ranking"
                    | "done",
                  progressPct: Math.round(poll.progress_pct ?? (poll.progress ? poll.progress * 100 : 40)),
                  message: poll.message ?? undefined,
                });
                await new Promise((r) => setTimeout(r, 900));
                continue;
              }
              break;
            }
          } catch {
            try {
              sessionStorage.removeItem("terraloop_active_job_id");
            } catch {}
          } finally {
            if (!cancelled) {
              setInternalLoading(false);
              setSimProgress(null);
            }
          }
        };
        void resumeExistingJob();
      }
    }
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (externalStrategies !== undefined || externalLoading || !field) return;
    if (autoFetchInFlightRef.current === fieldKey) return;
    autoFetchInFlightRef.current = fieldKey;
    let isCancelled = false;
    api
      .recommend({
        field,
        priorities,
        constraints,
        language: (lang as "en" | "pa" | "hi") || "en",
        soil_health_card: soilHealthCard,
        baseline_override: baselineOverride,
        climate_scenario: climateScenario,
      })
      .then((recs) => {
        if (!isCancelled && recs && recs.length > 0) {
          setInternalData({ key: fieldKey, list: recs });
          onStrategiesLoaded?.(recs);
          setErrorBanner(null);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          console.warn("Backend /recommend failed", err);
          const isGolden = field?.id && GOLDEN_IDS.has(field.id);
          if (isGolden) {
            const fallback = getFallbackStrategies(
              field,
              currencySymbol,
              constraints.rotation_years,
              (lang as "en" | "pa" | "hi") || "en"
            );
            setInternalData({ key: fieldKey, list: fallback });
            onStrategiesLoaded?.(fallback);
            setErrorBanner(t("error.recommendFailedDemo"));
          } else {
            setInternalData({ key: fieldKey, list: [] });
            onStrategiesLoaded?.([]);
            setErrorBanner(t("error.recommendFailedCustom"));
          }
        }
      });
    return () => {
      isCancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fieldKey, Boolean(externalStrategies)]);

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
      priorities.low_labour +
      (priorities.food_security ?? 1.0)
  );
  const wWater = Math.round((priorities.water_savings / totalWeight) * 100);
  const wProfit = Math.round((priorities.profit / totalWeight) * 100);
  const wSoil = Math.round((priorities.soil_health / totalWeight) * 100);
  const wLabour = Math.round((priorities.low_labour / totalWeight) * 100);
  const wFood = Math.round(((priorities.food_security ?? 1.0) / totalWeight) * 100);
  const wRisk = Math.max(0, 100 - wWater - wProfit - wSoil - wLabour - wFood);

  const applyPreset = (type: "balanced" | "water" | "profit" | "soil" | "resilient" | "food") => {
    let newP: Priorities = { ...priorities };
    if (type === "balanced") {
      newP = { ...newP, water_savings: 1.5, profit: 1.5, soil_health: 1.5, low_risk: 1.5, low_labour: 1.0, food_security: 1.5 };
    } else if (type === "water") {
      newP = { ...newP, water_savings: 3.0, profit: 0.8, soil_health: 1.2, low_risk: 1.0, low_labour: 1.0, food_security: 1.0 };
    } else if (type === "profit") {
      newP = { ...newP, profit: 3.0, water_savings: 0.8, soil_health: 0.8, low_risk: 1.0, low_labour: 0.5, food_security: 1.0 };
    } else if (type === "soil") {
      newP = { ...newP, soil_health: 3.0, water_savings: 1.5, profit: 0.8, low_risk: 1.2, low_labour: 1.0, food_security: 1.2 };
    } else if (type === "resilient") {
      newP = { ...newP, low_risk: 3.0, water_savings: 2.0, profit: 0.8, soil_health: 1.5, low_labour: 1.5, food_security: 1.5 };
    } else if (type === "food") {
      newP = { ...newP, food_security: 3.0, profit: 1.2, water_savings: 1.0, soil_health: 1.2, low_risk: 1.0, low_labour: 0.5 };
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
            <span>{t("nav.executiveBrief")}</span>
          </Link>

          <button
            type="button"
            onClick={() => window.print()}
            className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-surface hover:bg-foreground/10 text-foreground border border-line flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Printer className="w-3.5 h-3.5 text-emerald-400" />
            <span>{t("common.print")}</span>
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
                <span>{t("tab.strategiesCalendar")}</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("pareto")}
                className={`px-3 py-1.5 rounded-lg font-semibold transition-colors cursor-pointer flex items-center gap-1.5 ${
                  activeTab === "pareto"
                    ? "bg-stone-500 text-white font-bold"
                    : "text-muted hover:text-foreground"
                }`}
              >
                <TrendingUp className="w-3.5 h-3.5" />
                <span>{t("tab.paretoSpace")}</span>
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
                <span>{t("tab.shockLab")}</span>
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
              <span className="text-muted pr-1 uppercase text-[10px]">{t("label.farmerPersonas")}</span>
              <button
                type="button"
                onClick={() => applyPreset("water")}
                className="px-2.5 py-1 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/40 text-cyan-600 dark:text-cyan-300 font-semibold transition-colors cursor-pointer"
              >
                {t("persona.water")}
              </button>
              <button
                type="button"
                onClick={() => applyPreset("profit")}
                className="px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/40 text-emerald-600 dark:text-emerald-300 font-semibold transition-colors cursor-pointer"
              >
                {t("persona.profit")}
              </button>
              <button
                type="button"
                onClick={() => applyPreset("soil")}
                className="px-2.5 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-amber-600 dark:text-amber-300 font-semibold transition-colors cursor-pointer"
              >
                {t("persona.soil")}
              </button>
              <button
                type="button"
                onClick={() => applyPreset("resilient")}
                className="px-2.5 py-1 rounded-lg bg-stone-500/15 hover:bg-stone-500/25 border border-stone-500/40 text-stone-600 dark:text-stone-300 font-semibold transition-colors cursor-pointer"
              >
                {t("persona.resilient")}
              </button>
              <button
                type="button"
                onClick={() => applyPreset("balanced")}
                className="px-2.5 py-1 rounded-lg bg-surface hover:bg-foreground/10 border border-line text-foreground transition-colors cursor-pointer"
              >
                {t("persona.balanced")}
              </button>
            </div>
          </div>

          {/* Live Proportional Weight Distribution Bar */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[10px] font-mono text-muted">
              <span>{t("label.weightAllocation")}</span>
              <span>
                {t("priorities.waterShort")} {wWater}% · {t("priorities.profitShort")} {wProfit}% · {t("priorities.soilShort")} {wSoil}% · {t("priorities.riskShort")} {wRisk}% · {t("priorities.labourShort")} {wLabour}% · {t("priorities.foodShort")} {wFood}%
              </span>
            </div>
            <div className="h-2.5 w-full rounded-full overflow-hidden flex bg-surface border border-line">
              <div
                style={{ width: `${wWater}%` }}
                className="bg-cyan-400 transition-all duration-300"
                title={`${t("priorities.water")}: ${wWater}%`}
              />
              <div
                style={{ width: `${wProfit}%` }}
                className="bg-emerald-400 transition-all duration-300"
                title={`${t("priorities.profit")}: ${wProfit}%`}
              />
              <div
                style={{ width: `${wSoil}%` }}
                className="bg-amber-400 transition-all duration-300"
                title={`${t("priorities.soil")}: ${wSoil}%`}
              />
              <div
                style={{ width: `${wRisk}%` }}
                className="bg-stone-400 transition-all duration-300"
                title={`${t("priorities.risk")}: ${wRisk}%`}
              />
              <div
                style={{ width: `${wLabour}%` }}
                className="bg-rose-400 transition-all duration-300"
                title={`${t("priorities.labour")}: ${wLabour}%`}
              />
              <div
                style={{ width: `${wFood}%` }}
                className="bg-lime-400 transition-all duration-300"
                title={`${t("priorities.food")}: ${wFood}%`}
              />
            </div>
          </div>

          {/* Sliders Grid (6 Objectives) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3.5">
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
                  <ShieldAlert className="w-3.5 h-3.5 text-stone-400" />
                  <span>{t("priorities.risk")}</span>
                </span>
                <span className="font-mono text-[11px] font-bold text-stone-400">
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
                className="w-full accent-stone-400 cursor-pointer"
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

            {/* Food Security & Nutrition */}
            <div className="space-y-2 p-3.5 rounded-xl bg-surface border border-line">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-foreground flex items-center gap-1.5">
                  <Wheat className="w-3.5 h-3.5 text-lime-400" />
                  <span>{t("priorities.food")}</span>
                </span>
                <span className="font-mono text-[11px] font-bold text-lime-400">
                  {(priorities.food_security ?? 1.0).toFixed(1)}×
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="3"
                step="0.5"
                value={priorities.food_security ?? 1.0}
                onChange={(e) =>
                  setPriorities({ ...priorities, food_security: parseFloat(e.target.value) })
                }
                className="w-full accent-lime-400 cursor-pointer"
              />
            </div>
          </div>

          {/* Constraint Bar & Re-simulate Action */}
          <div className="space-y-3 pt-3 border-t border-line text-xs">
            <div className="flex flex-wrap items-center justify-between gap-4">
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
                  <span>{t("label.integrateLivestock")}</span>
                </label>

                <div className="flex items-center gap-2">
                  <label htmlFor="farm-area-input" className="text-muted">
                    {t("constraints.farmSize")}
                  </label>
                  <div className="flex items-center gap-1">
                    <input
                      id="farm-area-input"
                      type="number"
                      min="0.2"
                      max="500"
                      step="0.5"
                      value={
                        unitSystem === "acre"
                          ? Number(((constraints.area_ha ?? 2.0) * 2.47105).toFixed(1))
                          : Number((constraints.area_ha ?? 2.0).toFixed(2))
                      }
                      onChange={(e) => {
                        const raw = parseFloat(e.target.value);
                        if (!Number.isFinite(raw) || raw <= 0) return;
                        const ha = unitSystem === "acre" ? raw / 2.47105 : raw;
                        setConstraints({
                          ...constraints,
                          area_ha: Math.max(0.1, Math.min(500, Number(ha.toFixed(2)))),
                        });
                      }}
                      className="w-16 px-2 py-1 rounded-lg border border-line-strong bg-surface text-foreground text-[11px] font-mono outline-none tabular-nums"
                    />
                    <span className="text-muted">{unitSystem === "acre" ? t("unit.acreShort") : t("unit.haShort")}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-muted">{t("label.waterSupply")}</span>
                  <select
                    value={constraints.irrigation}
                    onChange={(e) => {
                      const nextMode = e.target.value as "none" | "limited" | "full";
                      setConstraints({
                        ...constraints,
                        irrigation: nextMode,
                        irrigation_cap_mm: nextMode === "limited" ? constraints.irrigation_cap_mm : null,
                      });
                    }}
                    className="px-2.5 py-1 rounded-lg border border-line-strong bg-surface text-foreground text-[11px] font-mono outline-none cursor-pointer"
                  >
                    <option value="limited">{t("label.tubewellRestricted")}</option>
                    <option value="full">{t("label.tubewellUnrestricted")}</option>
                    <option value="none">{t("constraints.rainfedOnly")}</option>
                  </select>
                </div>

                {constraints.irrigation === "limited" && (
                  <div className="flex items-center gap-1.5">
                    <label htmlFor="irrigation-cap-input" className="text-muted">
                      {t("constraints.irrigationCap")}
                    </label>
                    <input
                      id="irrigation-cap-input"
                      type="number"
                      min="50"
                      max="3000"
                      step="50"
                      placeholder={t("constraints.auto")}
                      value={constraints.irrigation_cap_mm ?? ""}
                      onChange={(e) => {
                        const raw = e.target.value.trim();
                        if (!raw) {
                          setConstraints({ ...constraints, irrigation_cap_mm: null });
                          return;
                        }
                        const mm = parseFloat(raw);
                        if (Number.isFinite(mm) && mm >= 0) {
                          setConstraints({
                            ...constraints,
                            irrigation_cap_mm: Math.min(3000, Math.round(mm)),
                          });
                        }
                      }}
                      className="w-20 px-2 py-1 rounded-lg border border-line-strong bg-surface text-foreground text-[11px] font-mono outline-none tabular-nums"
                    />
                    <span className="text-muted">mm/yr</span>
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <span className="text-muted">{t("label.rotationHorizon")}</span>
                  <select
                    value={constraints.rotation_years}
                    onChange={(e) => {
                      const nextYrs = parseInt(e.target.value, 10) || 1;
                      const nextC = { ...constraints, rotation_years: nextYrs };
                      setConstraints(nextC);
                      fetchRecommendations(priorities, nextC);
                    }}
                    className="px-2.5 py-1 rounded-lg border border-line-strong bg-surface text-foreground text-[11px] font-mono outline-none cursor-pointer"
                  >
                    <option value={1}>{t("horizon.1year")}</option>
                    <option value={2}>{t("horizon.2year")}</option>
                    <option value={3}>{t("horizon.3year")}</option>
                  </select>
                </div>
              </div>

              <button
                type="button"
                onClick={() => fetchRecommendations(priorities, constraints)}
                disabled={loading}
                className={`px-5 py-2.5 rounded-xl text-xs font-mono font-bold transition-all flex items-center gap-2 shadow-sm ${
                  loading
                    ? "bg-emerald-500/60 text-slate-900 cursor-not-allowed opacity-80"
                    : "bg-emerald-500 hover:bg-emerald-400 text-slate-950 cursor-pointer hover:shadow-md active:scale-95"
                }`}
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
                <span>{loading ? t("priorities.optimizing") : t("priorities.optimize")}</span>
              </button>
            </div>

            {/* Crop Inclusion / Exclusion Preference Constraints */}
            <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-line/60 text-[11px] font-mono">
              <div className="flex items-center gap-1.5 flex-wrap">
                <label htmlFor="must-grow-select" className="text-muted">
                  {t("constraints.mustInclude")}
                </label>
                <select
                  id="must-grow-select"
                  value=""
                  onChange={(e) => {
                    const id = e.target.value;
                    if (!id) return;
                    const nextMust = Array.from(new Set([...(constraints.must_grow ?? []), id]));
                    const nextExcl = (constraints.exclude ?? []).filter((c) => c !== id);
                    setConstraints({ ...constraints, must_grow: nextMust, exclude: nextExcl });
                  }}
                  className="px-2 py-1 rounded-lg border border-line bg-surface text-foreground text-[11px] outline-none cursor-pointer"
                >
                  <option value="">{t("constraints.addCrop")}</option>
                  {availableCropIds
                    .filter((id) => !(constraints.must_grow ?? []).includes(id))
                    .map((id) => (
                      <option key={id} value={id}>
                        {cropName(id)}
                      </option>
                    ))}
                </select>
                {(constraints.must_grow ?? []).map((id) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() =>
                      setConstraints({
                        ...constraints,
                        must_grow: (constraints.must_grow ?? []).filter((c) => c !== id),
                      })
                    }
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border border-emerald-500/35 hover:bg-rose-500/20 hover:text-rose-400 cursor-pointer"
                    title={t("constraints.removeTag")}
                  >
                    <span>+{cropName(id)}</span>
                    <span aria-hidden="true">×</span>
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-1.5 flex-wrap">
                <label htmlFor="exclude-crop-select" className="text-muted">
                  {t("constraints.excludeCrops")}
                </label>
                <select
                  id="exclude-crop-select"
                  value=""
                  onChange={(e) => {
                    const id = e.target.value;
                    if (!id) return;
                    const nextExcl = Array.from(new Set([...(constraints.exclude ?? []), id]));
                    const nextMust = (constraints.must_grow ?? []).filter((c) => c !== id);
                    setConstraints({ ...constraints, must_grow: nextMust, exclude: nextExcl });
                  }}
                  className="px-2 py-1 rounded-lg border border-line bg-surface text-foreground text-[11px] outline-none cursor-pointer"
                >
                  <option value="">{t("constraints.addCrop")}</option>
                  {availableCropIds
                    .filter((id) => !(constraints.exclude ?? []).includes(id))
                    .map((id) => (
                      <option key={id} value={id}>
                        {cropName(id)}
                      </option>
                    ))}
                </select>
                {(constraints.exclude ?? []).map((id) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() =>
                      setConstraints({
                        ...constraints,
                        exclude: (constraints.exclude ?? []).filter((c) => c !== id),
                      })
                    }
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-500 border border-rose-500/35 hover:bg-rose-500/25 cursor-pointer"
                    title={t("constraints.removeTag")}
                  >
                    <span>−{cropName(id)}</span>
                    <span aria-hidden="true">×</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* VIEW MODE 1: Comparative Strategy Cards + Interactive Calendar & Radar */}
        {activeTab === "cards" && (
          <div className="space-y-6">
            {/* Prominent Multi-Objective Simulation Loading Banner with Live Progress (Issue 10 / WS-H3) */}
            {loading && (
              <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/40 flex flex-col gap-3 text-xs font-mono">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-emerald-600 dark:text-emerald-300">
                  <div className="flex items-center gap-3">
                    <RefreshCw className="w-4 h-4 animate-spin text-emerald-500 shrink-0" />
                    <div>
                      <div className="font-bold text-sm">
                        {simProgress?.stage === "profile"
                          ? t("async.stage.profile")
                          : simProgress?.stage === "weather"
                          ? t("async.stage.weather")
                          : simProgress?.stage === "simulating"
                          ? t("async.stage.simulating")
                          : simProgress?.stage === "ranking"
                          ? t("async.stage.ranking")
                          : t("async.stage.simulatingDefault", {
                              years: String(constraints.rotation_years),
                            })}
                      </div>
                      <div className="text-[11px] text-muted">
                        {simProgress?.message || t("async.stage.subtext")}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-emerald-500 text-sm">
                      {simProgress?.progressPct ? `${simProgress.progressPct}%` : t("async.inProgress")}
                    </span>
                    <span className="px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40 text-[10px] font-bold uppercase tracking-wider shrink-0 self-start sm:self-auto">
                      {t("async.horizonActive", { years: String(constraints.rotation_years) })}
                    </span>
                  </div>
                </div>
                <div className="w-full bg-surface h-2 rounded-full overflow-hidden border border-line">
                  <div
                    className="bg-emerald-500 h-full transition-all duration-300"
                    style={{ width: `${Math.max(10, simProgress?.progressPct ?? 35)}%` }}
                  />
                </div>
              </div>
            )}

            {/* Generated Success Toast/Banner */}
            {successBanner && !loading && (
              <div className="p-3 rounded-xl bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-between gap-2 text-xs font-mono text-emerald-600 dark:text-emerald-300 transition-opacity">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span className="font-bold">{successBanner}</span>
                </div>
                <span className="text-[10px] text-muted hidden sm:inline">{t("label.paretoUpdated")}</span>
              </div>
            )}

            {/* Offline Fallback / Failure Banner with Retry */}
            {errorBanner && !loading && (
              <div className="p-3 rounded-xl bg-amber-500/15 border border-amber-500/40 flex flex-wrap items-center justify-between gap-2 text-xs font-mono text-amber-700 dark:text-amber-300 transition-opacity">
                <div className="flex items-center gap-2 min-w-0">
                  <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
                  <span className="font-medium">{errorBanner}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <button
                    type="button"
                    onClick={() => fetchRecommendations(priorities, constraints)}
                    className="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-700 dark:text-amber-200 font-bold cursor-pointer flex items-center gap-1"
                  >
                    <RefreshCw className="w-3 h-3" />
                    <span>{t("common.retry")}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setErrorBanner(null)}
                    className="text-xs text-amber-600 dark:text-amber-400 underline hover:opacity-80 cursor-pointer"
                  >
                    {t("common.dismiss")}
                  </button>
                </div>
              </div>
            )}

            {/* Global Unvalidated Agro-Climatic Warning */}
            {baseline?.validation_status === "unvalidated_global" && !loading && (
              <div className="p-3.5 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-start justify-between gap-3 text-xs font-mono text-sky-700 dark:text-sky-300">
                <div className="flex items-start gap-2.5">
                  <Globe className="w-4 h-4 text-sky-500 shrink-0 mt-0.5" />
                  <div>
                    <strong className="font-bold block uppercase tracking-wider text-[11px] text-sky-600 dark:text-sky-400">
                      {t("rotations.scopeNoticeTitle")}
                    </strong>
                    <p className="mt-0.5 text-muted leading-relaxed">
                      {baseline.validation_message || t("rotations.scopeNoticeBody")}
                    </p>
                  </div>
                </div>
                <span className="text-[10px] uppercase px-2 py-0.5 rounded bg-sky-500/20 text-sky-600 dark:text-sky-400 border border-sky-500/30 shrink-0 font-bold">
                  {t("rotations.scopeNoticeBadge")}
                </span>
              </div>
            )}

            {/* Demo Snapshot Banner (Issue 4 / WS-B3 & WS-J4) */}
            {(profile?.served_from === "demo_snapshot" || baseline?.served_from === "demo_snapshot") && !loading && (
              <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-between text-xs font-mono text-cyan-700 dark:text-cyan-300">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                  <span className="font-bold">
                    {t("badge.demoSnapshot")}
                    {profile?.snapshot_date ? ` (${profile.snapshot_date})` : ""}
                  </span>
                </div>
                <span className="text-[10px] uppercase font-bold text-muted">
                  {profile?.data_mode ? t(`data_mode.${profile.data_mode}`) : t("badge.demoSnapshot")}
                </span>
              </div>
            )}

            {/* GRACE Aquifer Urgency Active Notice (Issue 18 / WS-J4) */}
            {graceMult > 1.0 && !loading && (
              <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-between text-xs font-mono text-sky-700 dark:text-sky-300">
                <div className="flex items-center gap-2">
                  <Droplets className="w-4 h-4 text-sky-500 shrink-0" />
                  <span className="font-bold">
                    {/* t("badge.graceUrgencyActive") */}
                    {t("badge.graceUrgencyActive", {
                      mult: graceMult.toFixed(2),
                      trend: Math.abs(gwTrend).toFixed(2),
                    })}
                  </span>
                </div>
                <span className="text-[10px] uppercase font-bold text-muted">
                  {t("sensor.grace")}
                </span>
              </div>
            )}

            {/* Yield-gap Potential Disclaimer Banner (Issue 7 / WS-F5) */}
            <div
              className={`p-3 rounded-xl border flex items-start gap-2.5 text-xs font-mono ${
                constraints.irrigation === "none"
                  ? "bg-amber-500/15 border-amber-500/40 text-amber-800 dark:text-amber-200"
                  : "bg-surface/80 border-line text-muted"
              }`}
            >
              <AlertTriangle
                className={`w-4 h-4 shrink-0 mt-0.5 ${
                  constraints.irrigation === "none" ? "text-amber-500" : "text-muted"
                }`}
              />
              <div>
                <span className="font-bold uppercase tracking-wider text-[10px] block">
                  {constraints.irrigation === "none"
                    ? t("warning.rainfedYieldTitle")
                    : t("warning.biophysicalYieldTitle")}
                </span>
                <p className="mt-0.5 leading-relaxed text-[11px]">
                  {t("warning.yieldGapDisclaimer")}
                </p>
              </div>
            </div>

            {/* Detected Current Farm Baseline Card (Issue 16 / WS-I7) */}
            {baseline && (
              <div className="p-4 sm:p-5 rounded-2xl bg-surface/80 border border-line space-y-3.5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Wheat className="w-4 h-4 text-amber-500" />
                      <span className="font-mono text-xs font-bold uppercase tracking-wider text-foreground">
                        {t("baseline.detectedTitle")}
                      </span>
                      {isBaselineConfirmed && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border border-emerald-500/40">
                          <CheckCircle2 className="w-3 h-3" />
                          {t("baseline.confirmed")}
                        </span>
                      )}
                      {baselineOverride && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-cyan-500/20 text-cyan-600 dark:text-cyan-400 border border-cyan-500/40">
                          {t("baseline.customSelected")}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] font-mono text-muted">
                      {profile?.crop_history && profile.crop_history.length > 0 ? (
                        <span>
                          {t("baseline.sourceHls")} (
                          {Math.round(
                            (profile.crop_history.reduce((a, b) => a + (b.confidence ?? 0.8), 0) /
                              profile.crop_history.length) *
                              100
                          )}
                          % {t("baseline.confidence")})
                        </span>
                      ) : (
                        <span>{t("baseline.sourceRegional")}</span>
                      )}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      type="button"
                      onClick={() => setIsBaselineConfirmed(!isBaselineConfirmed)}
                      className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold transition-all border flex items-center gap-1.5 cursor-pointer ${
                        isBaselineConfirmed
                          ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-600 dark:text-emerald-300"
                          : "bg-surface-2 border-line text-muted hover:text-foreground"
                      }`}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>{isBaselineConfirmed ? t("baseline.confirmed") : t("baseline.confirmButton")}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setShowBaselineSelector(!showBaselineSelector)}
                      className="px-3 py-1.5 rounded-xl text-xs font-mono font-bold bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/40 text-cyan-600 dark:text-cyan-300 transition-colors flex items-center gap-1.5 cursor-pointer"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>{t("baseline.changeButton")}</span>
                    </button>

                    {baselineOverride && (
                      <button
                        type="button"
                        onClick={() => {
                          setBaselineOverride(null);
                          fetchRecommendations(priorities, constraints);
                        }}
                        className="px-2 py-1.5 text-xs text-rose-500 hover:underline font-mono cursor-pointer"
                      >
                        {t("common.reset")}
                      </button>
                    )}
                  </div>
                </div>

                {/* Baseline Sequence Display */}
                <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-line/60">
                  <span className="text-xs font-mono text-muted mr-1">{t("baseline.detectedTitle")}:</span>
                  {baseline.rotation.steps.map((step, idx) => {
                    const meta = cropMeta(step.crop_id);
                    return (
                      <span
                        key={idx}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono font-medium border ${meta.tone}`}
                      >
                        <span>{meta.emoji}</span>
                        <span className="capitalize">{cropName(step.crop_id)}</span>
                      </span>
                    );
                  })}
                </div>

                {/* 1-Tap Crop Override Selector */}
                {showBaselineSelector && (
                  <div className="p-4 rounded-xl bg-background/80 border border-cyan-500/30 space-y-3 pt-3">
                    <div className="text-xs font-mono font-bold text-foreground">
                      {t("baseline.changeButton")}:
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
                      <div>
                        <label className="text-[10px] text-muted block mb-1 uppercase">
                          {t("baseline.selectKharif")}
                        </label>
                        <select
                          value={customKharif}
                          onChange={(e) => setCustomKharif(e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-surface border border-line text-foreground"
                        >
                          <option value="rice_puddled">{cropName("rice_puddled")}</option>
                          <option value="rice_dsr">{cropName("rice_dsr")}</option>
                          <option value="cotton">{cropName("cotton")}</option>
                          <option value="maize">{cropName("maize")}</option>
                          <option value="pearl_millet">{cropName("pearl_millet")}</option>
                          <option value="groundnut">{cropName("groundnut")}</option>
                          <option value="soybean">{cropName("soybean")}</option>
                          <option value="fallow">{cropName("fallow")}</option>
                        </select>
                      </div>

                      <div>
                        <label className="text-[10px] text-muted block mb-1 uppercase">
                          {t("baseline.selectRabi")}
                        </label>
                        <select
                          value={customRabi}
                          onChange={(e) => setCustomRabi(e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-surface border border-line text-foreground"
                        >
                          <option value="wheat">{cropName("wheat")}</option>
                          <option value="chickpea">{cropName("chickpea")}</option>
                          <option value="mustard">{cropName("mustard")}</option>
                          <option value="potato">{cropName("potato")}</option>
                          <option value="barley">{cropName("barley")}</option>
                          <option value="fallow">{cropName("fallow")}</option>
                        </select>
                      </div>

                      <div>
                        <label className="text-[10px] text-muted block mb-1 uppercase">
                          {t("baseline.selectZaid")}
                        </label>
                        <select
                          value={customZaid}
                          onChange={(e) => setCustomZaid(e.target.value)}
                          className="w-full px-2.5 py-1.5 rounded-lg bg-surface border border-line text-foreground"
                        >
                          <option value="fallow">{cropName("fallow")}</option>
                          <option value="moong">{cropName("moong")}</option>
                          <option value="sorghum">{cropName("sorghum")}</option>
                          <option value="urad">{cropName("urad")}</option>
                        </select>
                      </div>
                    </div>

                    <div className="flex justify-end pt-1">
                      <button
                        type="button"
                        onClick={() => {
                          const overrideArr = [customKharif, customRabi, customZaid];
                          setBaselineOverride(overrideArr);
                          setIsBaselineConfirmed(true);
                          setShowBaselineSelector(false);
                          fetchRecommendations(priorities, constraints);
                        }}
                        className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-mono text-xs font-bold transition-colors cursor-pointer"
                      >
                        {t("baseline.applyOverride")}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center justify-between flex-wrap gap-2">
              <h4 className="font-display font-bold text-xs uppercase tracking-wider text-foreground">
                {t("rotations.comparativeHeading")}
              </h4>
              <span className="text-[11px] font-mono text-emerald-500 font-semibold">
                {t("rotations.clickCardHint")}
              </span>
            </div>

            <div
              className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 transition-all duration-300 ${
                loading ? "opacity-40 pointer-events-none filter blur-[0.5px]" : "opacity-100"
              }`}
            >
              {baseline && (
                <StrategyCard
                  strategy={baseline}
                  isBaseline={true}
                  isSelected={selectedRank === 0}
                  onSelect={() => setSelectedRank(0)}
                  currencySymbol={currencySymbol}
                  unitSystem={unitSystem}
                  rotationYears={constraints.rotation_years}
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
                  rotationYears={constraints.rotation_years}
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
                      {t("rotations.groundedAdvisory")} — {focusedStrategy.rotation.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    {focusedStrategy.practical_metrics?.total_farm_profit_p50 != null && (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40">
                        {t("rotations.wholeFarmNet", {
                          area:
                            unitSystem === "acre"
                              ? `${((focusedStrategy.practical_metrics.area_ha ?? constraints.area_ha) * 2.47105).toFixed(1)} ${t("unit.acreShort")}`
                              : `${(focusedStrategy.practical_metrics.area_ha ?? constraints.area_ha).toFixed(1)} ${t("unit.haShort")}`,
                          amount: fmtMoney(focusedStrategy.practical_metrics.total_farm_profit_p50, currencySymbol),
                        })}
                      </span>
                    )}
                    {focusedStrategy.practical_metrics?.msp_assurance_level && (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/20 text-amber-600 dark:text-amber-300 border border-amber-500/40">
                        {focusedStrategy.practical_metrics.msp_assurance_level}
                      </span>
                    )}
                  </div>
                </div>

                {focusedStrategy.narrative_summary && (
                  <p className="text-xs sm:text-sm text-foreground/95 leading-relaxed font-medium bg-background/70 p-3.5 rounded-xl border border-line">
                    {focusedStrategy.narrative_summary}
                  </p>
                )}

                {focusedStrategy.practical_metrics && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                    <div className="p-3 rounded-xl bg-background/75 border border-line">
                      <span className="text-[10px] text-muted uppercase block">{t("brief.turnaroundWindow")}</span>
                      <span
                        className={`text-sm font-bold ${
                          focusedStrategy.practical_metrics.turnaround_days_kharif_rabi >= 20
                            ? "text-emerald-400"
                            : "text-rose-400"
                        }`}
                      >
                        {focusedStrategy.practical_metrics.turnaround_days_kharif_rabi} {t("unit.days")}{" "}
                        {focusedStrategy.practical_metrics.turnaround_days_kharif_rabi >= 20
                          ? `(${t("rotations.burnFree")})`
                          : `(${t("rotations.crunch")})`}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-background/75 border border-line">
                      <span className="text-[10px] text-muted uppercase block">{t("brief.irrigationsSaved")}</span>
                      <span className="text-sm font-bold text-cyan-400">
                        {focusedStrategy.practical_metrics.irrigations_saved_per_yr} {t("unit.irrigations")} (
                        {Math.round(
                          scaleByUnit(
                            focusedStrategy.practical_metrics.pumping_hours_saved_per_ha,
                            unitSystem
                          )
                        )}{" "}
                        {t("unit.hrs")}
                        {fmtAreaUnit(unitSystem)})
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-background/75 border border-line">
                      <span className="text-[10px] text-muted uppercase block">{t("brief.ureaBagsSaved")}</span>
                      <span className="text-sm font-bold text-emerald-400">
                        {scaleByUnit(
                          focusedStrategy.practical_metrics.urea_bags_saved_per_ha,
                          unitSystem
                        ).toFixed(1)}{" "}
                        {t("unit.bags")}
                        {fmtAreaUnit(unitSystem)}
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-background/75 border border-line">
                      <span className="text-[10px] text-muted uppercase block">{t("brief.labourCost")}</span>
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
                        {t("brief.eligibleSubsidies")}:
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

            {/* "What This Model Does NOT Capture" Disclosure Panel (Issue 18 / WS-J4 & WS-J5) */}
            <div className="p-4 sm:p-5 rounded-2xl bg-surface/60 border border-line space-y-2.5">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-amber-500 shrink-0" />
                <h4 className="font-mono text-xs font-bold uppercase tracking-wider text-foreground">
                  {t("unmodelled.title")}
                </h4>
              </div>
              <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs font-mono text-muted pt-1">
                <li className="flex items-start gap-2">
                  <span className="text-amber-500 shrink-0">•</span>
                  <span>{t("unmodelled.pests")}</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-amber-500 shrink-0">•</span>
                  <span>{t("unmodelled.weather")}</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-amber-500 shrink-0">•</span>
                  <span>{t("unmodelled.market")}</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-amber-500 shrink-0">•</span>
                  <span>{t("unmodelled.labour")}</span>
                </li>
                <li className="flex items-start gap-2 md:col-span-2">
                  <span className="text-amber-500 shrink-0">•</span>
                  <span>{t("unmodelled.water")}</span>
                </li>
              </ul>
            </div>

            {/* Interactive Deep-Dive: 12-Month Agronomic Calendar + 5-Axis Soil Health Radar */}
            {focusedStrategy && baseline && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 pt-2">
                {/* Left 7 Cols: 12-Month Seasonal Gantt Calendar */}
                <div className="lg:col-span-7 p-5 rounded-2xl bg-background/60 border border-line space-y-4">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-emerald-400" />
                      <h4 className="font-display font-bold text-sm text-foreground">
                        {t("gantt.title")} — {focusedStrategy.rotation.label}
                      </h4>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-500 border border-emerald-500/30 font-bold">
                      {focusedStrategy.rank === 0
                        ? t("gantt.baselineRegime")
                        : t("gantt.strategyRank", { rank: `0${focusedStrategy.rank}` })}
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
                      const isDelta = isSA && field.lat < 16.5;
                      const spanCols = isSH
                        ? step.season_index === 0
                          ? { start: 12, len: 5, window: t("gantt.shMain") }
                          : step.season_index === 1
                          ? { start: 5, len: 5, window: t("gantt.shCool") }
                          : { start: 10, len: 2, window: t("gantt.shCatch") }
                        : !isSA
                        ? step.season_index === 0
                          ? { start: 5, len: 5, window: t("gantt.nhMain") }
                          : step.season_index === 1
                          ? { start: 10, len: 5, window: t("gantt.nhCool") }
                          : { start: 3, len: 2, window: t("gantt.nhCatch") }
                        : isDelta
                        ? step.season_index === 0
                          ? { start: 6, len: 4, window: t("gantt.deltaKharif") }
                          : step.season_index === 1
                          ? { start: 10, len: 4, window: t("gantt.deltaRabi") }
                          : { start: 2, len: 3, window: t("gantt.deltaZaid") }
                        : step.season_index === 0
                        ? { start: 6, len: 5, window: t("gantt.igpKharif") }
                        : step.season_index === 1
                        ? { start: 11, len: 5, window: t("gantt.igpRabi") }
                        : { start: 4, len: 2, window: t("gantt.igpZaid") };

                      return (
                        <div
                          key={sIdx}
                          className="p-3 rounded-xl bg-surface border border-line space-y-2"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                            <div className="flex items-center gap-2">
                              {constraints.rotation_years > 1 && (
                                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/20 text-cyan-500 border border-cyan-500/40">
                                  {t("unit.yrShort")} {step.year_index + 1}
                                </span>
                              )}
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
                              const isActive = isSH
                                ? step.season_index === 0
                                  ? mNum >= 12 || mNum <= 4
                                  : step.season_index === 1
                                  ? mNum >= 5 && mNum <= 9
                                  : mNum >= 10 && mNum <= 11
                                : !isSA
                                ? step.season_index === 0
                                  ? mNum >= 5 && mNum <= 9
                                  : step.season_index === 1
                                  ? mNum >= 10 || mNum <= 2
                                  : mNum >= 3 && mNum <= 4
                                : isDelta
                                ? step.season_index === 0
                                  ? mNum >= 6 && mNum <= 9
                                  : step.season_index === 1
                                  ? mNum >= 10 || mNum <= 1
                                  : mNum >= 2 && mNum <= 4
                                : step.season_index === 0
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
                        {t("radar.usdaTitle")}
                      </h4>
                    </div>
                    <span className="text-[10px] font-mono text-muted">{t("radar.vsBaseline")}</span>
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
                      <span>{t("strategy.baseline")}</span>
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Seasonal Field Operations, Irrigation & Budget Ledger */}
            {focusedStrategy?.practical_metrics?.seasonal_operations &&
              focusedStrategy.practical_metrics.seasonal_operations.length > 0 && (
                <div className="p-5 rounded-2xl bg-background/60 border border-line space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-cyan-400" />
                      <h4 className="font-display font-bold text-sm text-foreground">
                        {t("rotations.ledgerTitle")} — {focusedStrategy.rotation.label}
                      </h4>
                    </div>
                    <span className="text-[10px] font-mono text-muted">
                      {isSA ? t("rotations.ledgerSubtitleIndia") : t("rotations.ledgerSubtitleGlobal")}
                    </span>
                  </div>

                  <div className="overflow-x-auto rounded-xl border border-line">
                    <table className="w-full text-left text-xs tabular-nums">
                      <caption className="sr-only">
                        {t("rotations.ledgerTitle")} — {focusedStrategy.rotation.label}
                      </caption>
                      <thead className="bg-foreground/[0.05] text-foreground font-mono text-[10px] uppercase tracking-wider border-b border-line">
                        <tr>
                          <th scope="col" className="py-3 px-3.5">
                            {t("rotations.colSeasonCrop")}
                          </th>
                          <th scope="col" className="py-3 px-3">
                            {t("rotations.colWindow")}
                          </th>
                          <th scope="col" className="py-3 px-3">
                            {t("rotations.colYield")}
                          </th>
                          <th scope="col" className="py-3 px-3">
                            {t("rotations.colIrrigation")}
                          </th>
                          <th scope="col" className="py-3 px-3">
                            {t("rotations.colNBalance")}
                          </th>
                          <th scope="col" className="py-3 px-3">
                            {t("rotations.colOutlay")}
                          </th>
                          <th scope="col" className="py-3 px-3">
                            {t("rotations.colMargin")}
                          </th>
                          <th scope="col" className="py-3 px-3.5">
                            {t("rotations.colGuidance")}
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line text-foreground/90">
                        {focusedStrategy.practical_metrics.seasonal_operations.map((op, opIdx) => {
                          const isFallow = op.crop_id === "fallow";
                          return (
                            <tr
                              key={`${op.year_index}-${op.season_index}-${opIdx}`}
                              className="hover:bg-foreground/[0.03] transition-colors"
                            >
                              <th scope="row" className="py-3 px-3.5 font-sans font-bold">
                                <div className="flex flex-col gap-0.5">
                                  <span className="text-[10px] font-mono text-muted">
                                    {constraints.rotation_years > 1 ? `${t("unit.yrShort")} ${op.year_index + 1} · ` : ""}
                                    {op.season_name}
                                  </span>
                                  <span className="text-foreground">{op.crop_name}</span>
                                </div>
                              </th>
                              <td className="py-3 px-3 font-mono text-[11px]">
                                <div className="flex flex-col">
                                  <span>
                                    {op.sowing_window} → {op.harvest_window}
                                  </span>
                                  <span className="text-[10px] text-muted">
                                    {op.duration_days} {t("rotations.fieldDays")}
                                  </span>
                                </div>
                              </td>
                              <td className="py-3 px-3 font-mono font-bold text-foreground">
                                {isFallow
                                  ? "—"
                                  : unitSystem === "acre"
                                  ? `${(op.yield_t_ha * 4.047).toFixed(1)} q/ac`
                                  : `${op.yield_t_ha.toFixed(2)} t/ha`}
                              </td>
                              <td className="py-3 px-3 font-mono">
                                {isFallow ? (
                                  <span className="text-muted">{t("rotations.rainfedMulch")}</span>
                                ) : (
                                  <div className="flex flex-col">
                                    <span className="font-bold text-cyan-400">{op.irrigation_mm} mm</span>
                                    <span className="text-[10px] text-muted">
                                      ~{op.irrigations_count} {t("unit.irrigations")}
                                    </span>
                                  </div>
                                )}
                              </td>
                              <td className="py-3 px-3 font-mono">
                                {op.n_fixation_kg_ha > 0 || op.urea_saved_kg_ha > 0 ? (
                                  <div className="flex flex-col text-emerald-400">
                                    {op.n_fixation_kg_ha > 0 && (
                                      <span className="font-bold">+{op.n_fixation_kg_ha} kg N/ha BNF</span>
                                    )}
                                    {op.urea_saved_kg_ha > 0 && (
                                      <span className="text-[10px]">
                                        {t("rotations.savesUrea", {
                                          kg: String(Math.round(scaleByUnit(op.urea_saved_kg_ha, unitSystem))),
                                          unit: fmtAreaUnit(unitSystem),
                                        })}
                                      </span>
                                    )}
                                  </div>
                                ) : (
                                  <span className="text-muted">{t("rotations.standardN")}</span>
                                )}
                              </td>
                              <td className="py-3 px-3 font-mono text-[11px]">
                                {isFallow ? (
                                  "—"
                                ) : (
                                  <div className="flex flex-col">
                                    <span>
                                      {fmtAreaMoney(
                                        op.input_cost_inr_ha,
                                        currencySymbol,
                                        unitSystem,
                                        false
                                      )}
                                      {fmtAreaUnit(unitSystem)}
                                    </span>
                                    <span className="text-[10px] text-muted">
                                      {t("rotations.labourLabel")}{" "}
                                      {fmtAreaMoney(
                                        op.labor_cost_inr_ha,
                                        currencySymbol,
                                        unitSystem,
                                        false
                                      )}
                                    </span>
                                  </div>
                                )}
                              </td>
                              <td className="py-3 px-3 font-mono font-bold text-emerald-400">
                                {isFallow
                                  ? "—"
                                  : `${fmtAreaMoney(
                                      op.net_profit_inr_ha,
                                      currencySymbol,
                                      unitSystem,
                                      false
                                    )}${fmtAreaUnit(unitSystem)}`}
                              </td>
                              <td className="py-3 px-3.5 text-[11px] text-foreground/85 max-w-xs leading-snug">
                                {op.agronomic_guidance}
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
        )}

        {/* VIEW MODE 2: 3D Multi-Objective Pareto Space + 2D Projection */}
        {activeTab === "pareto" && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h4 className="font-display font-bold text-sm text-foreground flex items-center gap-2">
                  <Box className="w-4 h-4 text-stone-400" />
                  <span>{t("pareto.frontierTitle")}</span>
                </h4>
                <p className="text-[11px] font-mono text-muted mt-0.5">
                  {t("pareto.subtitle", { currency: currencySymbol, unit: fmtAreaUnit(unitSystem) })}
                </p>
              </div>

              <div className="inline-flex rounded-lg bg-surface p-0.5 border border-line text-[11px] font-mono">
                <button
                  type="button"
                  onClick={() => setParetoViewMode("3d")}
                  className={`px-3 py-1 rounded-md font-semibold cursor-pointer transition-colors ${
                    paretoViewMode === "3d"
                      ? "bg-stone-500 text-white"
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  {t("pareto.view3d")}
                </button>
                <button
                  type="button"
                  onClick={() => setParetoViewMode("2d")}
                  className={`px-3 py-1 rounded-md font-semibold cursor-pointer transition-colors ${
                    paretoViewMode === "2d"
                      ? "bg-stone-500 text-white"
                      : "text-muted hover:text-foreground"
                  }`}
                >
                  {t("pareto.view2d")}
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
                  unitSystem={unitSystem}
                />
              ) : (
                <div className="p-6">
                  <ParetoScatterPlot
                    strategies={strategies}
                    selectedRank={selectedRank}
                    onSelectRank={(r) => setSelectedRank(r)}
                    currencySymbol={currencySymbol}
                    unitSystem={unitSystem}
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
                  rotationYears={constraints.rotation_years}
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
                  rotationYears={constraints.rotation_years}
                />
              ))}
            </div>
          </div>
        )}

        {/* VIEW MODE 3: What-If Stress Lab */}
        {activeTab === "whatif" && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="font-display font-bold text-sm text-foreground flex items-center gap-2">
                    <FlaskConical className="w-4 h-4 text-amber-400" />
                    <span>{t("whatif.title")}</span>
                  </h4>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold border ${
                      stressedStrategies
                        ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border-emerald-500/40"
                        : "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40"
                    }`}
                  >
                    {stressedStrategies ? t("whatif.badgeSimulated") : t("whatif.badgePreview")}
                  </span>
                </div>
                <p className="text-[11px] font-mono text-muted mt-0.5">
                  {t("whatif.subtitle")}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2.5 text-xs font-mono">
                <label className="flex items-center gap-2">
                  <span className="text-muted text-[11px]">{t("whatif.climateScenario")}</span>
                  <select
                    value={climateScenario}
                    onChange={(e) => {
                      const nextScen = e.target.value as ClimateScenarioId;
                      setClimateScenario(nextScen);
                      runStressSimulation(nextScen);
                    }}
                    className="px-2.5 py-1.5 rounded-lg border border-amber-500/40 bg-surface text-foreground text-[11px] font-mono outline-none cursor-pointer"
                  >
                    <option value="historical">{t("whatif.histBaseline")}</option>
                    <option value="ssp245_2030s">{t("whatif.ssp245Near")}</option>
                    <option value="ssp245_2050s">{t("whatif.ssp245Mid")}</option>
                    <option value="ssp585_2030s">{t("whatif.ssp585Near")}</option>
                    <option value="ssp585_2050s">{t("whatif.ssp585Mid")}</option>
                  </select>
                </label>

                <button
                  type="button"
                  onClick={() => runStressSimulation()}
                  disabled={stressLoading}
                  className="px-3.5 py-1.5 rounded-lg text-[11px] font-mono font-bold bg-amber-500 hover:bg-amber-400 text-slate-950 transition-colors disabled:opacity-50 cursor-pointer flex items-center gap-1.5"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${stressLoading ? "animate-spin" : ""}`} />
                  <span>{stressLoading ? t("whatif.simulatingCmip6") : t("whatif.runStressSim")}</span>
                </button>
              </div>
            </div>

            {stressError && (
              <div className="p-3 rounded-xl bg-amber-500/15 border border-amber-500/40 flex flex-wrap items-center justify-between gap-2 text-xs font-mono text-amber-700 dark:text-amber-300">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
                  <span>{stressError}</span>
                </div>
                <button
                  type="button"
                  onClick={() => runStressSimulation()}
                  className="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 font-bold cursor-pointer"
                >
                  {t("common.retry")}
                </button>
              </div>
            )}

            {/* Shock Sliders */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-5 rounded-2xl bg-amber-500/[0.07] border border-amber-500/35">
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span className="font-semibold text-foreground">{t("whatif.droughtEt0")}</span>
                  <span className="font-bold text-amber-500">+{droughtShockPct}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="40"
                  step="5"
                  value={droughtShockPct}
                  onChange={(e) => {
                    setDroughtShockPct(parseInt(e.target.value));
                    setStressedStrategies(null);
                  }}
                  className="w-full accent-amber-500 cursor-pointer"
                />
                <span className="text-[10px] font-mono text-muted block">
                  {t("whatif.droughtDesc")}
                </span>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span className="font-semibold text-foreground">{t("whatif.harvestPrice")}</span>
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
                  onChange={(e) => {
                    setPriceShockPct(parseInt(e.target.value));
                    setStressedStrategies(null);
                  }}
                  className="w-full accent-cyan-400 cursor-pointer"
                />
                <span className="text-[10px] font-mono text-muted block">
                  {t("whatif.priceDesc")}
                </span>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span className="font-semibold text-foreground">{t("whatif.ureaSpike")}</span>
                  <span className="font-bold text-rose-500">+{fertilizerShockPct}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="50"
                  step="10"
                  value={fertilizerShockPct}
                  onChange={(e) => {
                    setFertilizerShockPct(parseInt(e.target.value));
                    setStressedStrategies(null);
                  }}
                  className="w-full accent-rose-500 cursor-pointer"
                />
                <span className="text-[10px] font-mono text-muted block">
                  {t("whatif.ureaDesc")}
                </span>
              </div>
            </div>

            {/* Stressed Performance Comparative Matrix */}
            <div className="overflow-x-auto rounded-2xl border border-line">
              <table className="w-full text-left text-xs tabular-nums">
                <caption className="sr-only">
                  {t("whatif.tableCaption")}
                </caption>
                <thead className="bg-foreground/[0.05] text-foreground font-mono text-[11px] uppercase tracking-wider border-b border-line">
                  <tr>
                    <th scope="col" className="py-3.5 px-4">{t("whatif.rotStrategy")}</th>
                    <th scope="col" className="py-3.5 px-3">{t("whatif.baseMargin")}</th>
                    <th scope="col" className="py-3.5 px-3">{t("whatif.stressedMargin")}</th>
                    <th scope="col" className="py-3.5 px-3">{t("whatif.droughtIncome")}</th>
                    <th scope="col" className="py-3.5 px-3">{t("whatif.regretDrawdown")}</th>
                    <th scope="col" className="py-3.5 px-3">{t("whatif.stressedIrrigation")}</th>
                    <th scope="col" className="py-3.5 px-3">{t("whatif.resilienceClass")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line text-foreground/90 font-mono">
                  {strategies.map((strat) => {
                    const res = strat.results[0];
                    const normP = res?.profit_p50 ?? (isSA ? 85000 : 950);
                    const normIrr = res?.irrigation_mm?.length
                      ? res.irrigation_mm.reduce((a, b) => a + b, 0) / res.irrigation_mm.length
                      : 0;

                    const matchedEngineStress = stressedStrategies?.find(
                      (s) => s.rotation.id === strat.rotation.id || (strat.rank === 0 && s.rank === 0)
                    )?.results?.[0];

                    const cmipTempPen =
                      climateScenario === "ssp585_2050s"
                        ? 0.88
                        : climateScenario === "ssp245_2050s"
                        ? 0.92
                        : climateScenario === "ssp585_2030s"
                        ? 0.94
                        : climateScenario === "ssp245_2030s"
                        ? 0.96
                        : 1.0;

                    const extraIrr = normIrr * (droughtShockPct / 100);
                    const stressedIrr = matchedEngineStress?.irrigation_mm?.length
                      ? Math.round(
                          matchedEngineStress.irrigation_mm.reduce((a, b) => a + b, 0) /
                            matchedEngineStress.irrigation_mm.length
                        )
                      : Math.round(normIrr + extraIrr);
                    const pumpUnitCost = isSA ? 8.5 : 0.45;
                    const fertUnitCost = isSA ? 95 : 1.2;
                    const fertLegumeUnitCost = isSA ? 25 : 0.35;
                    const pumpPenalty = extraIrr * pumpUnitCost;
                    const revMult = (1 + priceShockPct / 100) * cmipTempPen;
                    const hasLegume = strat.rotation.steps.some((st) => {
                      const matched = crops.find((c) => c.id === st.crop_id);
                      if (matched) return matched.group === "legume";
                      return [
                        "moong",
                        "common_bean",
                        "chickpea",
                        "pigeon_pea",
                        "lentil",
                        "urad",
                        "dhaincha",
                        "berseem",
                        "soybean",
                        "groundnut",
                      ].includes(st.crop_id);
                    });
                    const baseInputCost = strat.practical_metrics?.input_cost_inr_per_ha;
                    const fertPenalty =
                      baseInputCost && baseInputCost > 0
                        ? baseInputCost * (hasLegume ? 0.06 : 0.16) * (fertilizerShockPct / 100)
                        : fertilizerShockPct * (hasLegume ? fertLegumeUnitCost : fertUnitCost);

                    const stressedP = matchedEngineStress
                      ? Math.round(matchedEngineStress.profit_p50)
                      : Math.round(normP * revMult - pumpPenalty - fertPenalty);
                    const cvarRatio =
                      normP !== 0 && res?.cvar_profit_10 !== undefined && res?.cvar_profit_10 !== null
                        ? res.cvar_profit_10 / normP
                        : 1;
                    const stressedCvar = matchedEngineStress
                      ? Math.round(matchedEngineStress.cvar_profit_10)
                      : Math.round(stressedP * cvarRatio - (droughtShockPct > 0 ? Math.abs(stressedP) * 0.08 * (droughtShockPct / 100) : 0));
                    const drop = Math.max(0, Math.round(normP - stressedP));
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
                        <th scope="row" className="py-3.5 px-4 font-sans font-bold flex items-center gap-2">
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
                        </th>
                        <td className="py-3.5 px-3">
                          {fmtMoney(scaleByUnit(normP, unitSystem), currencySymbol)}
                          {fmtAreaUnit(unitSystem)}
                        </td>
                        <td className="py-3.5 px-3 font-bold text-emerald-500">
                          {fmtMoney(scaleByUnit(stressedP, unitSystem), currencySymbol)}
                          {fmtAreaUnit(unitSystem)}
                        </td>
                        <td className="py-3.5 px-3 text-amber-400">
                          {fmtMoney(scaleByUnit(stressedCvar, unitSystem), currencySymbol)}
                          {fmtAreaUnit(unitSystem)}
                        </td>
                        <td className="py-3.5 px-3 text-rose-500">
                          −{fmtMoney(scaleByUnit(drop, unitSystem), currencySymbol)}
                          {fmtAreaUnit(unitSystem)}
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
                            {drop < dropThreshold ? t("whatif.buffered") : t("whatif.vulnerable")}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <ProvenanceChip provenance={(stressedStrategies ?? strategies)[0]?.provenance} />
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
  const { t } = useI18n();
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
    const livingRoots = Math.min(95, Math.round(r?.living_root_days_pct ?? 65));
    const diversity = Math.min(95, Math.round(35 + (r?.family_diversity_index ?? 0.2) * 80));
    const carbon = Math.min(
      95,
      Math.max(20, Math.round(50 + (r?.soc_delta_t_ha_10yr ?? 0) * 18))
    );
    return [armor, minDisturb, livingRoots, diversity, carbon];
  };

  const axesLabels = [
    t("radar.soilArmor"),
    t("radar.minTill"),
    t("radar.livingRoots"),
    t("radar.biodiversity"),
    t("radar.socGain"),
  ];
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
          stroke="#d06b5c"
          strokeWidth="1.5"
          strokeDasharray="3 2"
        />

        {/* Focused Strategy Polygon */}
        <polygon
          points={polyPoints(fVals)}
          fill="rgba(16, 185, 129, 0.25)"
          stroke="#5fae7b"
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
            <span>{t("radar.shComponent")}</span>
            <span>{t("radar.selectedVsBase")}</span>
          </div>
          {[
            { key: "disturbance_minimization", label: t("radar.bdDisturbance") },
            { key: "soil_armor_cover", label: t("radar.bdArmor") },
            { key: "living_roots", label: t("radar.bdLivingRoots") },
            { key: "biodiversity", label: t("radar.bdBiodiversity") },
            { key: "biological_n_livestock", label: t("radar.bdBioN") },
            { key: "soc_modifier", label: t("radar.bdSocMod") },
            { key: "erosion_modifier", label: t("radar.bdErosionMod") },
            { key: "burning_penalty", label: t("radar.bdBurnPenalty") },
          ].map((item) => {
            const fVal = fRes.soil_health_breakdown?.[item.key] ?? 0;
            const bVal = bRes?.soil_health_breakdown?.[item.key] ?? 0;
            return (
              <div key={item.key} className="flex justify-between items-center">
                <span className="text-muted">{item.label}</span>
                <span>
                  <strong className="text-emerald-400">{fVal > 0 && item.key.includes("mod") ? `+${fVal}` : fVal}</strong>
                  <span className="text-muted"> {t("common.vs")} {bVal > 0 && item.key.includes("mod") ? `+${bVal}` : bVal}</span>
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Accessible fallback table */}
      <table className="sr-only">
        <caption>{t("radar.usdaTitle")}</caption>
        <thead>
          <tr>
            <th>{t("radar.principleCol")}</th>
            <th>{t("radar.selectedStrategy")}</th>
            <th>{t("strategy.baseline")}</th>
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
  rotationYears = 1,
}: {
  strategy: StrategyRecommendation;
  isBaseline: boolean;
  isSelected: boolean;
  onSelect: () => void;
  currencySymbol?: string;
  unitSystem?: UnitSystem;
  rotationYears?: number;
}) {
  const { t } = useI18n();
  const currSym = strategy.currency_symbol || currencySymbol;
  const res = strategy.results[0];
  const irr = res?.irrigation_mm?.length
    ? Math.round(res.irrigation_mm.reduce((a, b) => a + b, 0) / res.irrigation_mm.length)
    : 0;

  const isRainfedBase = strategy.vs_baseline?.is_rainfed_baseline === 1.0;
  const waterChange =
    strategy.vs_baseline?.irrigation_change_pct ?? strategy.vs_baseline?.irrigation_pct;
  const waterChangeMm = strategy.vs_baseline?.irrigation_change_mm;
  const waterSaved = waterChange !== undefined ? -Math.round(waterChange) : 0;
  const resilienceScore = strategy.vs_baseline?.climate_resilience_score;
  const shScore = Math.round(res?.soil_health_score ?? 40);
  const pm = strategy.practical_metrics;

  const cardTone = isBaseline
    ? "border-line bg-surface/50 hatch-pattern"
    : strategy.rank === 1
    ? "border-emerald-500/60 bg-emerald-500/[0.09]"
    : "border-line-strong bg-surface/85";

  const selectedRing = isSelected
    ? "ring-2 ring-emerald-400 shadow-xl -translate-y-0.5"
    : "";

  const isMultiYear =
    (rotationYears && rotationYears > 1) ||
    strategy.rotation.steps.some((s) => (s.year_index ?? 0) > 0);

  const numYears = Math.max(
    rotationYears || 1,
    ...strategy.rotation.steps.map((s) => (s.year_index ?? 0) + 1)
  );

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
              : `OPT 0${strategy.rank} // ${t("strategy.recommended")}`}
          </span>

          <div className="flex items-center gap-1.5">
            {strategy.economics_basis === "punjab_proxy" && (
              <span
                className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/35"
                title={t("badge.punjabProxyTooltip")}
              >
                {t("badge.punjabProxyEconomics")}
              </span>
            )}
            {isMultiYear && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-600 dark:text-cyan-300 border border-cyan-500/35">
                {numYears}Y
              </span>
            )}
            {!isBaseline && isRainfedBase && waterChangeMm !== undefined && waterChangeMm > 0 && (
              <span className="text-[10px] font-bold text-amber-600 dark:text-amber-300 bg-amber-500/15 px-1.5 py-0.5 rounded border border-amber-500/35">
                +{Math.round(waterChangeMm)} mm H₂O ({t("strategy.vsRainfed")})
              </span>
            )}
            {!isBaseline && (!isRainfedBase || waterChangeMm === undefined || waterChangeMm <= 0) && waterSaved > 0 && (
              <span className="text-[10px] font-bold text-cyan-600 dark:text-cyan-300 bg-cyan-500/15 px-1.5 py-0.5 rounded border border-cyan-500/35">
                −{waterSaved}% H₂O
              </span>
            )}
            {resilienceScore !== undefined && (
              <span
                className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-stone-500/15 text-stone-600 dark:text-stone-300 border border-stone-500/35"
                title={t("strategy.climateResilienceTitle")}
              >
                RES {Math.round(resilienceScore)}
              </span>
            )}
          </div>
        </div>

        {/* Rotation Name & Botanical Sequence */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h4 className="font-display font-bold text-sm text-foreground leading-snug">
              {strategy.rotation.label ?? strategy.rotation.id}
            </h4>

            {isMultiYear ? (
              <div className="mt-2.5 space-y-1.5">
                {Array.from({ length: numYears }, (_, yr) => {
                  const yrSteps = strategy.rotation.steps.filter(
                    (s) => (s.year_index ?? 0) === yr
                  );
                  if (yrSteps.length === 0) return null;
                  return (
                    <div key={yr} className="flex flex-wrap items-center gap-1">
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-cyan-500/20 text-cyan-600 dark:text-cyan-300 border border-cyan-500/40 shrink-0">
                        {t("unit.yrShort")} {yr + 1}
                      </span>
                      {yrSteps.map((step, idx) => {
                        const meta = cropMeta(step.crop_id);
                        return (
                          <span
                            key={idx}
                            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border ${meta.tone}`}
                          >
                            <span className="font-mono text-[8px] opacity-80">{meta.emoji}</span>
                            <span className="capitalize">{cropName(step.crop_id)}</span>
                            {step.practices.includes("residue_retained") && (
                              <span className="text-[8px] font-mono uppercase px-1 rounded bg-emerald-500/20 text-emerald-600 dark:text-emerald-300">
                                {t("strategy.mulchTag")}
                              </span>
                            )}
                          </span>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            ) : (
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
                          {t("strategy.mulchTag")}
                        </span>
                      )}
                    </span>
                  );
                })}
              </div>
            )}
          </div>

          <ProgressRing
            value={shScore}
            max={100}
            label={t("strategy.soilHealthScore")}
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
            <span className="text-muted font-sans">{t("radar.irrigationDemand")}</span>
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
          {pm?.total_farm_profit_p50 != null && (
            <div className="flex justify-between items-center text-[10px] text-emerald-600 dark:text-emerald-300">
              <span className="font-sans">
                {t("strategy.wholeFarmLabel")} (
                {unitSystem === "acre"
                  ? `${((pm.area_ha ?? 2.0) * 2.47105).toFixed(1)} ${t("unit.acreShort")}`
                  : `${(pm.area_ha ?? 2.0).toFixed(1)} ${t("unit.haShort")}`}
                )
              </span>
              <span className="font-bold">{fmtMoney(pm.total_farm_profit_p50, currSym)}</span>
            </div>
          )}
          <div className="text-[9px] text-muted font-sans text-right -mt-1">
            {t("label.netOperatingIncomeNote")}
          </div>
          {res?.cvar_ci_low != null && res?.cvar_ci_high != null && (
            <div className="flex justify-between items-center text-[10px] text-muted">
              <span>{t("strategy.droughtCi")}</span>
              <span>
                [{fmtAreaMoney(res.cvar_ci_low, currSym, unitSystem)}–{fmtAreaMoney(res.cvar_ci_high, currSym, unitSystem)}]
              </span>
            </div>
          )}

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
              {(res?.soc_delta_t_ha_10yr ?? 0).toFixed(1)} t C/ha
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
                {t("strategy.windowTag")}: {pm.turnaround_days_kharif_rabi}d
              </span>
              {!isBaseline && pm.urea_bags_saved_per_ha > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
                  −{scaleByUnit(pm.urea_bags_saved_per_ha, unitSystem).toFixed(1)} {t("unit.ureaBags")}
                  {fmtAreaUnit(unitSystem)}
                </span>
              )}
              {!isBaseline && pm.irrigations_saved_per_yr > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-stone-500/10 text-stone-300 border border-stone-500/30">
                  −{pm.irrigations_saved_per_yr.toFixed(0)} {t("unit.irrigations")}
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
  currencySymbol = "₹",
  unitSystem = "acre",
}: {
  strategies: StrategyRecommendation[];
  selectedRank: number | null;
  onSelectRank: (rank: number) => void;
  currencySymbol?: string;
  unitSystem?: UnitSystem;
}) {
  const { t } = useI18n();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [yaw, setYaw] = useState<number>(-0.62);
  const [pitch, setPitch] = useState<number>(0.42);
  const [canvasSize, setCanvasSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
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
      const nw = Math.max(1, Math.round(entry.contentRect.width * dpr));
      const nh = Math.max(1, Math.round(entry.contentRect.height * dpr));
      if (canvas.width !== nw || canvas.height !== nh) {
        canvas.width = nw;
        canvas.height = nh;
      }
      setCanvasSize((prev) => (prev.w === nw && prev.h === nh ? prev : { w: nw, h: nh }));
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

    ctx.strokeStyle = "#5f9bbd";
    ctx.lineWidth = 2 * dpr;
    ctx.beginPath();
    ctx.moveTo(origin.x, origin.y);
    ctx.lineTo(xEnd.x, xEnd.y);
    ctx.stroke();

    ctx.strokeStyle = "#5fae7b";
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
    ctx.fillStyle = "#5f9bbd";
    ctx.fillText(t("pareto.axisWater"), xEnd.x - 40 * dpr, xEnd.y + 14 * dpr);
    ctx.fillStyle = "#5fae7b";
    ctx.fillText(`${t("pareto.axisMargin")} (${currSym}${fmtAreaUnit(unitSystem)})`, yEnd.x - 10 * dpr, yEnd.y - 8 * dpr);
    ctx.fillStyle = "#f59e0b";
    ctx.fillText(t("pareto.axisSoil"), zEnd.x - 30 * dpr, zEnd.y + 14 * dpr);
    ctx.restore();

    const irrs = strategies.map((s) => {
      const arr = s.results[0]?.irrigation_mm;
      return arr?.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
    });
    const profits = strategies.map((s) => scaleByUnit(s.results[0]?.profit_p50 ?? 1000, unitSystem));
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
      const color = isBase ? "#d06b5c" : item.strat.rank === 1 ? "#5fae7b" : "#5f9bbd";

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
      grad.addColorStop(1, "#141413");

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(item.pt.x, item.pt.y, radius, 0, Math.PI * 2);
      ctx.fill();

      const tag = isBase ? t("pareto.refBaseline") : `OPT #${item.strat.rank}`;
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
  }, [strategies, yaw, pitch, selectedRank, currSym, unitSystem, canvasSize, t]);

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
    for (const hit of hitTargetsRef.current) {
      const dist = Math.hypot(mx - hit.x, my - hit.y);
      if (dist <= hit.r) {
        onSelectRank(hit.rank);
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
        {t("pareto.dragHint")}
      </div>
      <button
        type="button"
        onClick={() => {
          setYaw(-0.62);
          setPitch(0.42);
        }}
        className="absolute top-3 right-3.5 p-1.5 rounded-lg glass-strong border border-line text-muted hover:text-foreground cursor-pointer"
        title={t("pareto.resetTitle")}
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
  currencySymbol = "₹",
  unitSystem = "acre",
}: {
  strategies: StrategyRecommendation[];
  selectedRank: number | null;
  onSelectRank: (rank: number) => void;
  currencySymbol?: string;
  unitSystem?: UnitSystem;
}) {
  const { t } = useI18n();
  if (!strategies || strategies.length === 0) return null;

  const currSym = strategies[0]?.currency_symbol || currencySymbol;

  const w = 550;
  const h = 220;
  const padL = 70;
  const padR = 30;
  const padT = 30;
  const padB = 40;

  const allProfits = strategies.map((s) => scaleByUnit(s.results[0]?.profit_p50 ?? 1000, unitSystem));
  const allIrrs = strategies.map((s) => {
    const irrs = s.results[0]?.irrigation_mm;
    return irrs?.length ? irrs.reduce((a, b) => a + b, 0) / irrs.length : 0;
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
      : 0;
    const p = scaleByUnit(res?.profit_p50 ?? 1000, unitSystem);
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
          {t("pareto.scatterXAxis")}
        </text>

        {points.filter((pt) => !pt.isBase).length > 1 && (
          <path
            d={points
              .filter((pt) => !pt.isBase)
              .sort((a, b) => a.x - b.x)
              .reduce((acc, curr, idx) => `${acc} ${idx === 0 ? "M" : "L"} ${curr.x} ${curr.y}`, "")}
            fill="none"
            stroke="#5fae7b"
            strokeWidth="2"
            strokeDasharray="4 3"
          />
        )}

        {points.map((pt) => {
          const isSelected = selectedRank === pt.rank;
          const color = pt.isBase ? "#d06b5c" : pt.score > 70 ? "#5fae7b" : "#5f9bbd";
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
                fill={pt.isBase ? "#d06b5c" : "#5fae7b"}
              >
                {pt.isBase ? t("pareto.refTag") : `OPT 0${pt.rank}`}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
