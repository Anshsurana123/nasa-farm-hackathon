"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { ProgressRing } from "@/components/ProgressRing";
import { useField } from "@/context/FieldContext";
import { api } from "@/lib/api";
import type { CropSpec, FieldProfile, SuitabilityItem } from "@/types/api";
import { cropMeta, cropName } from "@/lib/ui";
import { useI18n } from "@/i18n";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Droplets,
  Filter,
  Layers,
  Leaf,
  Search,
  Sparkles,
  Sprout,
  Thermometer,
  XCircle,
} from "lucide-react";

const GROUP_COLORS: Record<string, { badge: string; border: string; text: string; key: string }> = {
  legume: {
    badge: "bg-emerald-500/15 text-emerald-400 border-emerald-500/35",
    border: "border-emerald-500/40",
    text: "text-emerald-400",
    key: "crops.groupLegumeShort",
  },
  cereal: {
    badge: "bg-amber-500/15 text-amber-400 border-amber-500/35",
    border: "border-amber-500/40",
    text: "text-amber-400",
    key: "crops.groupCerealShort",
  },
  oilseed: {
    badge: "bg-cyan-500/15 text-cyan-400 border-cyan-500/35",
    border: "border-cyan-500/40",
    text: "text-cyan-400",
    key: "crops.groupOilseed",
  },
  fibre: {
    badge: "bg-stone-500/15 text-stone-400 border-stone-500/35",
    border: "border-stone-500/40",
    text: "text-stone-400",
    key: "crops.groupFibreShort",
  },
  fodder: {
    badge: "bg-teal-500/15 text-teal-400 border-teal-500/35",
    border: "border-teal-500/40",
    text: "text-teal-400",
    key: "crops.groupFodder",
  },
  cover: {
    badge: "bg-lime-500/15 text-lime-400 border-lime-500/35",
    border: "border-lime-500/40",
    text: "text-lime-400",
    key: "crops.groupCoverShort",
  },
  vegetable: {
    badge: "bg-rose-500/15 text-rose-400 border-rose-500/35",
    border: "border-rose-500/40",
    text: "text-rose-400",
    key: "crops.groupVeg",
  },
  tuber: {
    badge: "bg-orange-500/15 text-orange-400 border-orange-500/35",
    border: "border-orange-500/40",
    text: "text-orange-400",
    key: "crops.groupTuberShort",
  },
};

function computeParcelSuitability(
  crop: CropSpec,
  profile: FieldProfile | null
): {
  score: number;
  thermalScore: number;
  waterScore: number;
  droughtAligned: boolean;
} {
  if (!profile) {
    return { score: 84, thermalScore: 86, waterScore: 82, droughtAligned: true };
  }

  const isSH = profile.field.lat < 0;
  const monthlyTmax = profile.climate.monthly_tmax_c;
  const isCoolOnly = crop.season_type.includes("cool") && !crop.season_type.includes("warm");
  let seasonalTemp = profile.climate.mean_tmax_c;
  if (monthlyTmax && monthlyTmax.length === 12) {
    const coolMonths = isSH ? [4, 5, 6, 7, 8] : [10, 11, 0, 1, 2];
    const warmMonths = isSH ? [10, 11, 0, 1, 2] : [5, 6, 7, 8, 9];
    const indices = isCoolOnly ? coolMonths : warmMonths;
    seasonalTemp = indices.reduce((acc, idx) => acc + monthlyTmax[idx], 0) / indices.length;
  } else if (isCoolOnly) {
    seasonalTemp = profile.climate.mean_tmin_c + 8.0;
  }

  const [optLow, optHigh] = crop.optimal_temp_c;
  let thermalScore = 96;
  if (seasonalTemp < optLow) {
    thermalScore = Math.max(45, Math.round(96 - (optLow - seasonalTemp) * 4.5));
  } else if (seasonalTemp > optHigh) {
    const excess = seasonalTemp - optHigh;
    const headroom = Math.max(2, crop.max_temp_c - optHigh);
    thermalScore = Math.max(40, Math.round(96 - (excess / headroom) * 35));
  }

  const midWater = (crop.water_requirement_mm[0] + crop.water_requirement_mm[1]) / 2;
  const waterEfficiency = Math.max(
    30,
    Math.min(99, Math.round(105 - midWater / 22 + crop.drought_tolerance * 6))
  );

  const socBonus =
    (profile.soil.soc_g_per_kg ?? 8) < 10 && crop.n_fixation_kg_ha > 0 ? 8 : 0;

  const rawScore = thermalScore * 0.45 + waterEfficiency * 0.45 + socBonus + 6;
  const droughtAligned = crop.drought_tolerance >= 3 || midWater <= 650;

  return {
    score: Math.max(20, Math.min(99, Math.round(rawScore))),
    thermalScore,
    waterScore: waterEfficiency,
    droughtAligned,
  };
}

export default function CropsPage() {
  const { t } = useI18n();
  const { crops, profile, selectedField, constraints, soilHealthCard } = useField();

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedGroup, setSelectedGroup] = useState<string>("all");
  const [selectedSeason, setSelectedSeason] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"suitability" | "water" | "nfix" | "residue">(
    "suitability"
  );
  const [activeCropId, setActiveCropId] = useState<string>("moong");
  const [apiSuitability, setApiSuitability] = useState<Record<string, SuitabilityItem>>({});

  useEffect(() => {
    let cancelled = false;
    api
      .suitability({
        field: { lat: selectedField.lat, lon: selectedField.lon, name: selectedField.name },
        constraints,
        profile,
        soil_health_card: soilHealthCard,
      })
      .then((items) => {
        if (cancelled || !items) return;
        const map: Record<string, SuitabilityItem> = {};
        for (const it of items) {
          map[it.crop_id] = it;
        }
        setApiSuitability(map);
      })
      .catch(() => {
        if (!cancelled) setApiSuitability({});
      });
    return () => {
      cancelled = true;
    };
  }, [selectedField.lat, selectedField.lon, selectedField.name, constraints, profile, soilHealthCard]);

  const enrichedCrops = useMemo(() => {
    return crops.map((crop) => {
      const localSuit = computeParcelSuitability(crop, profile);
      const apiItem = apiSuitability[crop.id];
      const mergedScore = apiItem
        ? Math.max(0, Math.min(100, Math.round(apiItem.score * 100)))
        : localSuit.score;
      return {
        crop,
        suitability: {
          ...localSuit,
          score: mergedScore,
          reasons: apiItem?.reasons ?? [],
          fromEngine: Boolean(apiItem),
        },
        midWaterMm: Math.round(
          (crop.water_requirement_mm[0] + crop.water_requirement_mm[1]) / 2
        ),
      };
    });
  }, [crops, profile, apiSuitability]);

  const filteredCrops = useMemo(() => {
    return enrichedCrops
      .filter(({ crop }) => {
        if (selectedGroup !== "all" && crop.group !== selectedGroup) return false;
        if (
          selectedSeason !== "all" &&
          !crop.season_type.includes(selectedSeason as "warm" | "cool")
        ) {
          return false;
        }
        if (searchQuery.trim() !== "") {
          const q = searchQuery.toLowerCase();
          const inName = crop.name.toLowerCase().includes(q);
          const inFam = crop.family.toLowerCase().includes(q);
          const inId = crop.id.toLowerCase().includes(q);
          const inLocal = cropName(crop.id).toLowerCase().includes(q);
          if (!inName && !inFam && !inId && !inLocal) return false;
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === "suitability") return b.suitability.score - a.suitability.score;
        if (sortBy === "water") return a.midWaterMm - b.midWaterMm;
        if (sortBy === "nfix") return b.crop.n_fixation_kg_ha - a.crop.n_fixation_kg_ha;
        if (sortBy === "residue") return b.crop.residue_t_ha - a.crop.residue_t_ha;
        return 0;
      });
  }, [enrichedCrops, selectedGroup, selectedSeason, searchQuery, sortBy]);

  const activeEntry =
    enrichedCrops.find((c) => c.crop.id === activeCropId) ??
    filteredCrops[0] ??
    enrichedCrops[0];

  const groupCounts = useMemo(() => {
    const counts: Record<string, number> = { all: crops.length };
    for (const c of crops) {
      counts[c.group] = (counts[c.group] ?? 0) + 1;
    }
    return counts;
  }, [crops]);

  return (
    <AppShell
      pageStep="05"
      pageBadge={t("nav.badge.crops")}
      pageTitle={t("crops.pageTitle", { count: String(crops.length || 23) })}
      pageDescription={t("crops.pageDesc", { count: String(crops.length || 23) })}
      headerActions={
        <Link
          href="/rotations"
          className="px-4 py-2.5 rounded-xl bg-emerald-500 hover:opacity-95 text-slate-950 font-mono text-xs font-bold flex items-center gap-2 shadow-md transition-opacity"
        >
          <Layers className="w-4 h-4" />
          <span>{t("crops.buildRotationBtn")}</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      }
    >
      <div className="space-y-6">
        {/* Top Filter & Search Control Bar */}
        <div className="glass rounded-2xl p-5 border border-line space-y-4">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            {/* Search input */}
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 text-muted absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t("crops.searchPlaceholder")}
                aria-label={t("crops.searchAria")}
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-surface-2 border border-line text-sm text-foreground placeholder:text-muted focus:outline-none focus:border-emerald-400"
              />
            </div>

            {/* Season + Sort Controls */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <Filter className="w-3.5 h-3.5 text-cyan-400" />
                <label htmlFor="season-select" className="text-xs font-mono text-muted">
                  {t("crops.thermalRegime")}:
                </label>
                <select
                  id="season-select"
                  value={selectedSeason}
                  onChange={(e) => setSelectedSeason(e.target.value)}
                  className="bg-surface-2 border border-line rounded-xl px-3 py-2 text-xs font-mono text-foreground focus:outline-none focus:border-cyan-400"
                >
                  <option value="all">{t("crops.allRegimes")}</option>
                  <option value="warm">{t("crops.warmRegime")}</option>
                  <option value="cool">{t("crops.coolRegime")}</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                <label htmlFor="sort-select" className="text-xs font-mono text-muted">
                  {t("crops.sortBy")}:
                </label>
                <select
                  id="sort-select"
                  value={sortBy}
                  onChange={(e) =>
                    setSortBy(
                      e.target.value as "suitability" | "water" | "nfix" | "residue"
                    )
                  }
                  className="bg-surface-2 border border-line rounded-xl px-3 py-2 text-xs font-mono text-foreground focus:outline-none focus:border-emerald-400"
                >
                  <option value="suitability">
                    {t("crops.sortParcelMatch")} ({selectedField.name.split(",")[0]})
                  </option>
                  <option value="water">{t("crops.sortLowestWater")}</option>
                  <option value="nfix">{t("crops.sortHighestNfix")}</option>
                  <option value="residue">{t("crops.sortHighestResidue")}</option>
                </select>
              </div>
            </div>
          </div>

          {/* Botanical Group Pills */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-line">
            {[
              { id: "all", label: t("crops.filterAll") },
              { id: "legume", label: t("crops.filterLegumes") },
              { id: "cereal", label: t("crops.filterCereals") },
              { id: "oilseed", label: t("crops.filterOilseeds") },
              { id: "fibre", label: t("crops.filterFibre") },
              { id: "fodder", label: t("crops.filterFodder") },
              { id: "cover", label: t("crops.filterCover") },
              { id: "vegetable", label: t("crops.filterVeg") },
              { id: "tuber", label: t("crops.filterTuber") },
            ].map((grp) => {
              const count = groupCounts[grp.id] ?? 0;
              if (grp.id !== "all" && count === 0) return null;
              const isSelected = selectedGroup === grp.id;
              return (
                <button
                  key={grp.id}
                  type="button"
                  onClick={() => setSelectedGroup(grp.id)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-mono font-medium transition-all flex items-center gap-1.5 border ${
                    isSelected
                      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-sm"
                      : "bg-surface-2/70 text-muted hover:text-foreground border-line"
                  }`}
                >
                  <span>{grp.label}</span>
                  <span className="px-1.5 py-0.5 rounded-md bg-surface text-[10px] text-muted">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Main 2-Column Interactive Layout: Crop Grid + Sticky Botanical Inspector */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
          {/* Left 7 Columns: Crop Cards Grid */}
          <div className="xl:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {filteredCrops.map(({ crop, suitability }) => {
              const meta = cropMeta(crop.id);
              const grpStyle = GROUP_COLORS[crop.group] ?? GROUP_COLORS.cereal;
              const isSelected = activeEntry?.crop.id === crop.id;

              return (
                <button
                  key={crop.id}
                  type="button"
                  onClick={() => setActiveCropId(crop.id)}
                  className={`text-left rounded-2xl p-4 transition-all border relative overflow-hidden group ${
                    isSelected
                      ? "glass border-emerald-400/70 bg-emerald-500/5 shadow-lg shadow-emerald-500/10"
                      : "glass border-line hover:border-emerald-500/35"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className="w-11 h-11 rounded-xl bg-surface-2 border border-line flex items-center justify-center text-2xl shrink-0">
                        {meta.emoji}
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-display font-bold text-base text-foreground group-hover:text-emerald-400 transition-colors">
                            {cropName(crop.id)}
                          </h3>
                          <span
                            className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${grpStyle.badge}`}
                          >
                            {t(grpStyle.key)}
                          </span>
                        </div>
                        <p className="text-xs italic text-muted font-serif mt-0.5 capitalize">
                          {t("crops.family")}: {crop.family}
                        </p>
                      </div>
                    </div>

                    {/* Live Parcel Compatibility Ring */}
                    <div className="flex flex-col items-center shrink-0">
                      <ProgressRing
                        value={suitability.score}
                        max={100}
                        size="2.75rem"
                        thickness="4px"
                        color={
                          suitability.score >= 80
                            ? "#5fae7b"
                            : suitability.score >= 60
                            ? "#5f9bbd"
                            : suitability.score >= 30
                            ? "#f59e0b"
                            : "#e11d48"
                        }
                        label={`${crop.name} ${t("crops.match")}`}
                      >
                        <span className="text-[10px] font-mono font-bold text-foreground">
                          {suitability.score}%
                        </span>
                      </ProgressRing>
                      <span className="text-[9px] font-mono text-muted mt-0.5">{t("crops.match")}</span>
                    </div>
                  </div>

                  {/* Key Biophysical Telemetry Strip */}
                  <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-line text-xs font-mono">
                    <div>
                      <span className="text-[10px] text-muted block">{t("crops.waterNeed")}</span>
                      <span className="font-bold text-cyan-400">
                        {crop.water_requirement_mm[0]}–{crop.water_requirement_mm[1]} mm
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-muted block">{t("crops.nFixation")}</span>
                      <span
                        className={`font-bold ${
                          crop.n_fixation_kg_ha > 0 ? "text-emerald-400" : "text-muted"
                        }`}
                      >
                        {crop.n_fixation_kg_ha > 0
                          ? `+${crop.n_fixation_kg_ha} kg/ha`
                          : "0 kg/ha"}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-muted block">{t("crops.duration")}</span>
                      <span className="font-bold text-foreground">
                        {crop.duration_days[0]}–{crop.duration_days[1]} d
                      </span>
                    </div>
                  </div>

                  {/* Compatibility Pills */}
                  <div className="flex flex-wrap items-center justify-between gap-2 mt-3">
                    <div className="flex flex-wrap gap-1">
                      {crop.season_type.map((s) => (
                        <span
                          key={s}
                          className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-surface-2 text-muted border border-line"
                        >
                          {s === "warm" ? t("crops.seasonWarm") : t("crops.seasonCool")}
                        </span>
                      ))}
                    </div>
                    <span
                      className={`text-[10px] font-mono flex items-center gap-1 ${
                        suitability.droughtAligned ? "text-emerald-400" : "text-amber-400"
                      }`}
                    >
                      {suitability.droughtAligned ? (
                        <CheckCircle2 className="w-3 h-3" />
                      ) : (
                        <Sprout className="w-3 h-3" />
                      )}
                      <span>{t("crops.droughtTol")}: {crop.drought_tolerance}/5</span>
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Right 5 Columns: Sticky Deep Botanical Inspector */}
          {activeEntry && (
            <div className="xl:col-span-5 xl:sticky xl:top-24 glass rounded-2xl p-6 border border-emerald-500/35 space-y-5">
              <div className="flex items-start justify-between gap-4 border-b border-line pb-4">
                <div className="flex items-center gap-3.5">
                  <div className="w-14 h-14 rounded-2xl bg-surface-2 border border-emerald-500/40 flex items-center justify-center text-3xl shadow-inner">
                    {cropMeta(activeEntry.crop.id).emoji}
                  </div>
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-widest text-emerald-400 font-bold">
                      {t("crops.botanicalSpec")} · ID: {activeEntry.crop.id}
                    </span>
                    <h2 className="text-xl font-display font-bold text-foreground">
                      {cropName(activeEntry.crop.id)}
                    </h2>
                    <p className="text-xs italic text-muted font-serif capitalize">
                      {t("crops.botanicalFamily")}: {activeEntry.crop.family} · GDD:{" "}
                      {activeEntry.crop.gdd_to_maturity} °C·d
                    </p>
                  </div>
                </div>

                <div className="text-right">
                  <span className="text-[10px] font-mono uppercase text-muted block">
                    {t("crops.parcelFit")}
                  </span>
                  <span
                    className={`text-2xl font-display font-extrabold ${
                      activeEntry.suitability.score >= 60
                        ? "text-emerald-400"
                        : activeEntry.suitability.score >= 30
                        ? "text-amber-400"
                        : "text-rose-500"
                    }`}
                  >
                    {activeEntry.suitability.score}%
                  </span>
                </div>
              </div>

              {/* Engine Suitability Reasons */}
              {activeEntry.suitability.reasons.length > 0 && (
                <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 space-y-1 text-xs font-mono">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-500 block">
                    {t("crops.engineReasons")}
                  </span>
                  <ul className="space-y-0.5 text-foreground/90">
                    {activeEntry.suitability.reasons.map((r, i) => (
                      <li key={i}>• {r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Agronomic Field Note */}
              {activeEntry.crop.notes && (
                <div className="p-3.5 rounded-xl bg-surface-2/80 border border-line text-xs text-foreground leading-relaxed">
                  {activeEntry.crop.notes}
                </div>
              )}

              {/* 1. FAO-56 Evapotranspiration Kc Curve SVG */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
                    <Droplets className="w-3.5 h-3.5" />
                    <span>{t("crops.kcCurveTitle")}</span>
                  </span>
                  <span className="text-[11px] font-mono text-muted">
                    ini: {activeEntry.crop.kc[0]} → mid: {activeEntry.crop.kc[1]} → end:{" "}
                    {activeEntry.crop.kc[2]}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-surface-2/60 border border-line">
                  <svg
                    viewBox="0 0 320 100"
                    className="w-full h-24 overflow-visible"
                    role="img"
                    aria-label={`FAO-56 Kc curve for ${activeEntry.crop.name}`}
                  >
                    <line
                      x1="20"
                      y1="80"
                      x2="300"
                      y2="80"
                      stroke="currentColor"
                      className="text-line"
                      strokeWidth="1"
                    />
                    <line
                      x1="20"
                      y1="20"
                      x2="300"
                      y2="20"
                      stroke="currentColor"
                      className="text-line"
                      strokeDasharray="3 3"
                      strokeWidth="1"
                    />
                    {(() => {
                      const [kcIni, kcMid, kcEnd] = activeEntry.crop.kc;
                      const yIni = 80 - (kcIni / 1.35) * 60;
                      const yMid = 80 - (kcMid / 1.35) * 60;
                      const yEnd = 80 - (kcEnd / 1.35) * 60;
                      const path = `M 25 ${yIni} L 85 ${yIni} L 145 ${yMid} L 235 ${yMid} L 295 ${yEnd}`;
                      const area = `${path} L 295 80 L 25 80 Z`;
                      return (
                        <>
                          <path d={area} fill="rgba(6, 182, 212, 0.16)" />
                          <path
                            d={path}
                            fill="none"
                            stroke="#5f9bbd"
                            strokeWidth="2.5"
                            strokeLinecap="round"
                          />
                          <circle cx="55" cy={yIni} r="3.5" fill="#5f9bbd" />
                          <circle cx="190" cy={yMid} r="4" fill="#5fae7b" />
                          <circle cx="295" cy={yEnd} r="3.5" fill="#f59e0b" />
                          <text
                            x="55"
                            y={yIni - 7}
                            textAnchor="middle"
                            className="fill-cyan-400 text-[9px] font-mono"
                          >
                            Kc ini ({kcIni})
                          </text>
                          <text
                            x="190"
                            y={yMid - 7}
                            textAnchor="middle"
                            className="fill-emerald-400 text-[9px] font-mono font-bold"
                          >
                            Kc mid ({kcMid})
                          </text>
                          <text
                            x="275"
                            y={yEnd - 7}
                            textAnchor="middle"
                            className="fill-amber-400 text-[9px] font-mono"
                          >
                            Kc end ({kcEnd})
                          </text>
                        </>
                      );
                    })()}
                    <text x="25" y="94" className="fill-muted text-[9px] font-mono">
                      {t("crops.day1")}
                    </text>
                    <text
                      x="160"
                      y="94"
                      textAnchor="middle"
                      className="fill-muted text-[9px] font-mono"
                    >
                      {t("crops.peakCanopy")}
                    </text>
                    <text
                      x="295"
                      y="94"
                      textAnchor="end"
                      className="fill-muted text-[9px] font-mono"
                    >
                      {t("crops.harvestLabel")} ({activeEntry.crop.duration_days[1]}d)
                    </text>
                  </svg>
                </div>
              </div>

              {/* 2. Thermal Envelope vs Parcel Climate */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
                    <Thermometer className="w-3.5 h-3.5" />
                    <span>{t("crops.thermalTitle")}</span>
                  </span>
                  <span className="text-[11px] font-mono text-muted">
                    Base {activeEntry.crop.base_temp_c}°C · Opt{" "}
                    {activeEntry.crop.optimal_temp_c[0]}–{activeEntry.crop.optimal_temp_c[1]}°C
                    · Max {activeEntry.crop.max_temp_c}°C
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-surface-2/60 border border-line space-y-2">
                  <div className="relative h-4 rounded-full bg-surface border border-line overflow-hidden">
                    <div
                      className="absolute top-0 bottom-0 bg-emerald-500/60 border-x border-emerald-400"
                      style={{
                        left: `${(activeEntry.crop.optimal_temp_c[0] / 50) * 100}%`,
                        width: `${
                          ((activeEntry.crop.optimal_temp_c[1] -
                            activeEntry.crop.optimal_temp_c[0]) /
                            50) *
                          100
                        }%`,
                      }}
                    />
                    {profile && (
                      <div
                        className="absolute top-0 bottom-0 w-1 bg-cyan-400 shadow"
                        style={{
                          left: `${Math.min(
                            98,
                            (profile.climate.mean_tmax_c / 50) * 100
                          )}%`,
                        }}
                        title={`Parcel Mean Tmax: ${profile.climate.mean_tmax_c.toFixed(1)}°C`}
                      />
                    )}
                  </div>
                  <div className="flex justify-between text-[10px] font-mono text-muted">
                    <span>Tbase: {activeEntry.crop.base_temp_c}°C</span>
                    <span className="text-emerald-400 font-bold">
                      {t("crops.optimal")}: {activeEntry.crop.optimal_temp_c[0]}–
                      {activeEntry.crop.optimal_temp_c[1]}°C
                    </span>
                    <span>{t("crops.heatCeiling")}: {activeEntry.crop.max_temp_c}°C</span>
                  </div>
                </div>
              </div>

              {/* 3. Soil & Root Biophysical Grid */}
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-3 rounded-xl bg-surface-2/60 border border-line">
                  <span className="text-[10px] text-muted block">{t("crops.rootDepth")}</span>
                  <span className="text-sm font-bold text-foreground">
                    {activeEntry.crop.root_depth_m.toFixed(1)} m
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-surface-2/60 border border-line">
                  <span className="text-[10px] text-muted block">{t("crops.residueInput")}</span>
                  <span className="text-sm font-bold text-emerald-400">
                    +{activeEntry.crop.residue_t_ha.toFixed(1)} t/ha (C:N{" "}
                    {activeEntry.crop.residue_cn_ratio ?? 40})
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-surface-2/60 border border-line">
                  <span className="text-[10px] text-muted block">{t("crops.nDemandVsFix")}</span>
                  <span className="text-sm font-bold text-cyan-400">
                    {activeEntry.crop.n_demand_kg_ha} / +{activeEntry.crop.n_fixation_kg_ha} kg/ha
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-surface-2/60 border border-line">
                  <span className="text-[10px] text-muted block">{t("crops.typicalYield")}</span>
                  <span className="text-sm font-bold text-amber-400">
                    {activeEntry.crop.typical_yield_t_ha[0]}–
                    {activeEntry.crop.typical_yield_t_ha[1]} t/ha
                  </span>
                </div>
              </div>

              {/* 4. Interactive Rotation Sequencing Matrix (Good / Bad Predecessors) */}
              <div className="space-y-2.5 pt-2 border-t border-line">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-foreground flex items-center gap-1.5">
                  <Leaf className="w-3.5 h-3.5 text-emerald-400" />
                  <span>{t("crops.seqRulesTitle")}</span>
                </span>

                <div className="space-y-2">
                  <div>
                    <span className="text-[10px] font-mono text-emerald-400 block mb-1">
                      {t("crops.goodPredecessors")}:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {activeEntry.crop.good_predecessors.length > 0 ? (
                        activeEntry.crop.good_predecessors.map((predId) => (
                          <button
                            key={predId}
                            type="button"
                            onClick={() => setActiveCropId(predId)}
                            className="px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/35 text-emerald-300 text-xs font-mono flex items-center gap-1 transition-colors"
                          >
                            <CheckCircle2 className="w-3 h-3" />
                            <span>{cropMeta(predId).emoji}</span>
                            <span>{cropName(predId)}</span>
                          </button>
                        ))
                      ) : (
                        <span className="text-xs text-muted font-mono">{t("crops.flexibleSeq")}</span>
                      )}
                    </div>
                  </div>

                  <div>
                    <span className="text-[10px] font-mono text-rose-400 block mb-1">
                      {t("crops.badPredecessors")}:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {activeEntry.crop.bad_predecessors.length > 0 ? (
                        activeEntry.crop.bad_predecessors.map((badId) => (
                          <button
                            key={badId}
                            type="button"
                            onClick={() => setActiveCropId(badId)}
                            className="px-2.5 py-1 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/35 text-rose-300 text-xs font-mono flex items-center gap-1 transition-colors"
                          >
                            <XCircle className="w-3 h-3" />
                            <span>{cropMeta(badId).emoji}</span>
                            <span>{cropName(badId)}</span>
                          </button>
                        ))
                      ) : (
                        <span className="text-xs text-muted font-mono">{t("crops.noneFlagged")}</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* 5. Scientific Literature Provenance */}
              {activeEntry.crop.sources && activeEntry.crop.sources.length > 0 && (
                <div className="pt-3 border-t border-line space-y-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-muted flex items-center gap-1">
                    <BookOpen className="w-3 h-3 text-cyan-400" />
                    <span>{t("crops.citationsTitle")}</span>
                  </span>
                  <ul className="space-y-1 text-[11px] font-mono text-muted list-disc list-inside">
                    {activeEntry.crop.sources.map((citation, idx) => (
                      <li key={idx} className="leading-snug">
                        {citation}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
