"use client";

import { useEffect, useState } from "react";
import type { FieldProfile, StrategyRecommendation } from "@/types/api";
import { useI18n } from "@/i18n";
import { useField } from "@/context/FieldContext";
import { ProvenanceChip } from "./ProvenanceChip";
import { SoilColumn3D } from "./SoilColumn3D";
import { ProgressRing } from "./ProgressRing";
import { MONTHS, cropMeta, cropName, fmtDMS, seasonName } from "@/lib/ui";
import {
  CloudSun,
  Sprout,
  Droplets,
  AlertTriangle,
  Flame,
  Calendar,
  BarChart3,
  Gauge,
  ThermometerSun,
  Activity,
  ShieldCheck,
  FlaskConical,
  CheckCircle2,
} from "lucide-react";

interface ReportCardProps {
  profile: FieldProfile;
  strategies?: StrategyRecommendation[];
  show3DPedon?: boolean;
}

export function ReportCard({ profile, strategies = [], show3DPedon = true }: ReportCardProps) {
  const { t } = useI18n();
  const { soilHealthCard, setSoilHealthCard, baselineOverride, setBaselineOverride } = useField();
  const { field, climate, soil, water, hazards, agro_climatic_notes, crop_history, seasons_per_year } = profile;

  const [selectedMonth, setSelectedMonth] = useState<number>(
    climate.wettest_months?.[0] ? climate.wettest_months[0] - 1 : 6
  );
  const [showShcForm, setShowShcForm] = useState<boolean>(false);
  const defaultAvailN =
    soil.source === "farmer_test" && soil.nitrogen_g_kg != null ? soil.nitrogen_g_kg * 2240 : 210;
  const [shcPh, setShcPh] = useState<string>(String(soil.ph ?? 7.6));
  const [shcSocPct, setShcSocPct] = useState<string>(
    soil.soc_g_per_kg ? (soil.soc_g_per_kg / 10).toFixed(2) : "0.52"
  );
  const [shcN, setShcN] = useState<string>(String(Math.round(soilHealthCard?.available_n_kg_ha ?? defaultAvailN)));
  const [shcP, setShcP] = useState<string>(String(Math.round(soil.available_p_kg_ha ?? 18)));
  const [shcK, setShcK] = useState<string>(String(Math.round(soil.available_k_kg_ha ?? 240)));

  useEffect(() => {
    if (soilHealthCard) return;
    setShcPh(String(soil.ph ?? 7.5));
    setShcSocPct(soil.soc_g_per_kg ? (soil.soc_g_per_kg / 10).toFixed(2) : "0.52");
    setShcN(
      String(
        Math.round(
          soil.source === "farmer_test" && soil.nitrogen_g_kg != null ? soil.nitrogen_g_kg * 2240 : 210
        )
      )
    );
    setShcP(String(Math.round(soil.available_p_kg_ha ?? 18)));
    setShcK(String(Math.round(soil.available_k_kg_ha ?? 240)));
  }, [
    soilHealthCard,
    soil.source,
    soil.ph,
    soil.soc_g_per_kg,
    soil.nitrogen_g_kg,
    soil.available_p_kg_ha,
    soil.available_k_kg_ha,
  ]);

  const maxMonthlyRain = Math.max(...(climate?.monthly_precip_mm ?? [100]), 10);

  const sand = Math.round(soil.sand_pct ?? 40);
  const silt = Math.round(soil.silt_pct ?? 35);
  const clay = Math.round(soil.clay_pct ?? 25);

  const fcPct = soil.field_capacity_vol ? Math.round(soil.field_capacity_vol * 100) : 31;
  const wpPct = soil.wilting_point_vol ? Math.round(soil.wilting_point_vol * 100) : 14;
  const pawPct = Math.max(4, fcPct - wpPct);

  const activeRain = climate.monthly_precip_mm[selectedMonth] ?? 0;
  const activeTmax = climate.monthly_tmax_c?.[selectedMonth] ?? climate.mean_tmax_c;
  const activeTmin = climate.monthly_tmin_c?.[selectedMonth] ?? climate.mean_tmin_c;
  const activeSmap = water.root_zone_moisture_percentile?.[selectedMonth] ?? 50;

  return (
    <div className="space-y-6">
      {/* Field Survey Header & Automated NASA Agro-Climatic Insights */}
      <div className="glass rounded-2xl border border-line overflow-hidden reticle-frame">
        <div className="instrument-header px-5 py-3 flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40 font-bold uppercase tracking-wider">
              {t("report.surveyBadge")}
            </span>
            <span className="text-muted">
              {fmtDMS(field.lat, true)} · {fmtDMS(field.lon, false)}
            </span>
          </div>
          {seasons_per_year && (
            <span className="px-2.5 py-0.5 rounded-full bg-cyan-500/15 text-cyan-600 dark:text-cyan-300 border border-cyan-500/35 font-bold">
              {seasons_per_year === 2
                ? t("report.doubleCropped")
                : `${seasons_per_year} ${t("telemetry.seasonsPerYr")}`}
            </span>
          )}
        </div>

        <div className="p-5 sm:p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="font-serif text-xl sm:text-2xl font-bold text-foreground tracking-tight">
                  {field.name ?? t("report.selectedField")}
                </h2>
                {profile.agro_zone && (
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/15 text-amber-600 dark:text-amber-300 border border-amber-500/35">
                    {profile.agro_zone}
                  </span>
                )}
              </div>
              <p className="text-xs font-mono text-muted mt-0.5">
                {t("report.baselineClimatology")}: {climate.baseline_period} · {t("report.recentWindow")}:{" "}
                {climate.recent_period}
              </p>
            </div>

            <div className="flex items-center gap-3">
              <div className="text-right font-mono">
                <span className="text-[10px] text-muted uppercase block">{t("report.cropHeatUnits")}</span>
                <span className="text-base font-bold text-amber-500">
                  {Math.round(climate.gdd_base10_per_year).toLocaleString()} °C·d
                </span>
              </div>
            </div>
          </div>

          {/* Agro-climatic Field Observations */}
          {agro_climatic_notes && agro_climatic_notes.length > 0 && (
            <div className="p-4 rounded-xl bg-amber-500/12 border border-amber-500/35 text-xs space-y-2.5">
              <div className="font-mono text-[10px] font-bold uppercase tracking-widest text-amber-600 dark:text-amber-300 flex items-center gap-2">
                <Activity className="w-3.5 h-3.5 text-amber-400" />
                <span>
                  {t("section.insights")} — {t("report.anomalyScreen")}
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                {agro_climatic_notes.map((note, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-background/70 border border-line flex items-start gap-2.5 text-foreground/90 leading-relaxed"
                  >
                    <span className="font-mono text-amber-500 shrink-0 font-bold text-[11px]">
                      0{idx + 1}
                    </span>
                    <span>{note}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Interactive Monthly Hyetograph, Thermal Envelope & Month Inspector */}
      <div className="glass rounded-2xl border border-line overflow-hidden">
        <div className="instrument-header px-5 py-3.5 flex items-center justify-between flex-wrap gap-2">
          <h3 className="font-display font-bold text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-cyan-400" />
            <span>FIG. 01 // {t("report.hyetographTitle")}</span>
          </h3>
          <div className="flex items-center gap-4 text-[10px] font-mono">
            <span className="flex items-center gap-1.5 text-cyan-500 dark:text-cyan-300 font-semibold">
              <span className="w-2.5 h-2.5 rounded-xs bg-cyan-400 inline-block" /> {t("report.peakWetSeason")}
            </span>
            <span className="flex items-center gap-1.5 text-amber-500 dark:text-amber-300 font-semibold">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block" /> {t("report.tempLegend")}
            </span>
          </div>
        </div>

        <div className="p-5 sm:p-6 space-y-5">
          {/* Interactive Selected Month Spotlight Bar */}
          <div className="p-4 rounded-xl bg-background/75 border border-line-strong grid grid-cols-2 sm:grid-cols-4 gap-4 items-center font-mono text-xs">
            <div>
              <span className="text-[10px] text-muted uppercase block">{t("report.selectedMonth")}</span>
              <span className="text-base font-bold text-emerald-400">
                {MONTHS[selectedMonth]}{" "}
                {climate.wettest_months.includes(selectedMonth + 1)
                  ? `· ${t("report.wetSeason")}`
                  : `· ${t("report.dryBase")}`}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-muted uppercase block">{t("report.monthlyRain")}</span>
              <span className="text-base font-bold text-cyan-400">{activeRain.toFixed(1)} mm</span>
            </div>
            <div>
              <span className="text-[10px] text-muted uppercase block">{t("report.thermalEnvelope")}</span>
              <span className="text-base font-bold text-amber-400">
                {activeTmin.toFixed(1)}°C – {activeTmax.toFixed(1)}°C
              </span>
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] text-muted uppercase block">{t("report.rootSoilMoisture")}</span>
                <span className="text-[8px] px-1 py-0.2 rounded bg-foreground/10 text-muted font-mono uppercase tracking-wider">
                  {t("badge.contextOnly")}
                </span>
              </div>
              <span className="text-base font-bold text-foreground">
                {t("report.smapPercentileTag", { pct: activeSmap.toFixed(0) })}
              </span>
            </div>
          </div>

          {/* 12-Month Interactive Bar & Temperature Strip */}
          <div className="grid grid-cols-12 gap-2 items-end h-44 pt-6 px-1">
            {climate.monthly_precip_mm.map((val, idx) => {
              const heightPct = Math.round((val / maxMonthlyRain) * 100);
              const isMonsoon = climate.wettest_months.includes(idx + 1);
              const isSelected = selectedMonth === idx;
              const tmax = climate.monthly_tmax_c?.[idx] ?? 30;

              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setSelectedMonth(idx)}
                  onMouseEnter={() => setSelectedMonth(idx)}
                  className={`flex flex-col items-center gap-1.5 h-full justify-end group relative cursor-pointer rounded-lg p-1 transition-colors ${
                    isSelected ? "bg-foreground/[0.07] ring-1 ring-cyan-400/50" : "hover:bg-foreground/[0.04]"
                  }`}
                >
                  <span
                    className={`text-[9px] font-mono font-bold px-1 rounded ${
                      tmax >= 35
                        ? "text-rose-400 bg-rose-500/15"
                        : "text-amber-500 dark:text-amber-300"
                    }`}
                  >
                    {tmax.toFixed(0)}°
                  </span>

                  <span className="text-[9px] font-mono text-muted group-hover:text-foreground">
                    {val.toFixed(0)}
                  </span>

                  <div
                    style={{ height: `${Math.max(heightPct, 8)}%` }}
                    className={`w-full rounded-t-md transition-all ${
                      isSelected
                        ? "bg-emerald-500 shadow-md"
                        : isMonsoon
                        ? "bg-cyan-600/80 border-t border-cyan-300"
                        : "bg-foreground/20 border-t border-line-strong"
                    }`}
                  />

                  <span
                    className={`text-[10px] font-mono font-bold ${
                      isSelected
                        ? "text-emerald-400"
                        : isMonsoon
                        ? "text-cyan-500 dark:text-cyan-400"
                        : "text-muted"
                    }`}
                  >
                    {MONTHS[idx]}
                  </span>
                </button>
              );
            })}
          </div>

          <table className="sr-only">
            <caption>{t("report.climateTableCaption", { name: field.name ?? t("report.defaultParcelName") })}</caption>
            <thead>
              <tr>
                <th>{t("report.thMonth")}</th>
                <th>{t("report.thPrecipMm")}</th>
                <th>{t("report.thTmaxC")}</th>
                <th>{t("report.thTminC")}</th>
              </tr>
            </thead>
            <tbody>
              {climate.monthly_precip_mm.map((val, idx) => (
                <tr key={MONTHS[idx]}>
                  <td>{MONTHS[idx]}</td>
                  <td>{val.toFixed(1)}</td>
                  <td>{climate.monthly_tmax_c?.[idx]?.toFixed(1) ?? "—"}</td>
                  <td>{climate.monthly_tmin_c?.[idx]?.toFixed(1) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Grid: 4 Core Diagnostic Instruments */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* 1. Climate Instrument */}
        <div className="glass rounded-2xl border border-line flex flex-col justify-between overflow-hidden">
          <div>
            <div className="instrument-header px-5 py-3 flex items-center justify-between">
              <h3 className="font-display font-bold text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <CloudSun className="w-4 h-4 text-cyan-400" />
                <span>FIG. 02 // {t("section.climate")}</span>
              </h3>
              <span className="text-[10px] font-mono text-muted">
                {climate.baseline_period} → {climate.recent_period}
              </span>
            </div>

            <div className="p-5 grid grid-cols-2 gap-3">
              <div className="p-3.5 rounded-xl bg-background/60 border border-line">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted">
                  {t("climate.rain")}
                </p>
                <p className="text-xl font-bold font-mono text-foreground mt-1">
                  {climate.recent_annual_precip_mm.toFixed(0)}{" "}
                  <span className="text-xs font-normal text-muted">{t("unit.mmYr")}</span>
                </p>
                <p className="text-[10px] font-mono text-emerald-500 mt-1 font-semibold">
                  Δ {climate.precip_change_pct > 0 ? "+" : ""}
                  {climate.precip_change_pct.toFixed(0)}% {t("report.vsBaseline")}
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-background/60 border border-line">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted">
                  {t("climate.heatDays")}
                </p>
                <p className="text-xl font-bold font-mono text-amber-500 mt-1">
                  {climate.recent_heat_days_per_year.toFixed(0)}{" "}
                  <span className="text-xs font-normal text-muted">{t("unit.days")}</span>
                </p>
                <p className="text-[10px] text-muted mt-1 font-mono">
                  {t("report.baselineShort")}: {climate.heat_days_per_year.toFixed(0)} d/yr
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-background/60 border border-line">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted">
                  {t("climate.et0")}
                </p>
                <p className="text-xl font-bold font-mono text-cyan-400 mt-1">
                  {climate.annual_et0_mm ? climate.annual_et0_mm.toFixed(0) : "—"}{" "}
                  <span className="text-xs font-normal text-muted">{t("unit.mmYr")}</span>
                </p>
                <p className="text-[10px] text-muted mt-1 font-mono">{t("report.et0Method")}</p>
              </div>

              <div className="p-3.5 rounded-xl bg-background/60 border border-line">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted">
                  {t("climate.drySpell")}
                </p>
                <p className="text-xl font-bold font-mono text-foreground mt-1">
                  {climate.longest_dry_spell_days_mean.toFixed(0)}{" "}
                  <span className="text-xs font-normal text-muted">{t("unit.days")}</span>
                </p>
                <p className="text-[10px] text-muted mt-1 font-mono">{t("report.maxDryGap")}</p>
              </div>
            </div>
          </div>

          <div className="px-5 pb-4 pt-2 border-t border-line">
            <ProvenanceChip provenance={climate.provenance} />
          </div>
        </div>

        {/* 2. Pedology / Soil Instrument */}
        <div className="glass rounded-2xl border border-line flex flex-col justify-between overflow-hidden">
          <div>
            <div className="instrument-header px-5 py-3 flex items-center justify-between">
              <h3 className="font-display font-bold text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <Sprout className="w-4 h-4 text-emerald-400" />
                <span>
                  FIG. 03 // {t("section.soil")} &amp; {t("report.hydraulics")}
                </span>
              </h3>
              <div className="flex items-center gap-1.5 font-mono text-[10px]">
                {soil.texture_class && (
                  <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-600 dark:text-amber-300 border border-amber-500/40 capitalize font-bold">
                    {soil.texture_class}
                  </span>
                )}
                {soil.slope_pct !== undefined && soil.slope_pct !== null && (
                  <span className="px-2 py-0.5 rounded text-muted bg-background/60 border border-line">
                    {soil.slope_pct}% {t("report.grade")}
                  </span>
                )}
              </div>
            </div>

            <div className="p-5 grid grid-cols-2 gap-3">
              <div className="p-3.5 rounded-xl bg-background/60 border border-line flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-wider text-muted">
                    {t("soil.soc")}
                  </p>
                  <p className="text-xl font-bold font-mono text-emerald-400 mt-1">
                    {soil.soc_g_per_kg ? soil.soc_g_per_kg.toFixed(1) : "—"}{" "}
                    <span className="text-xs font-normal text-muted">{t("unit.gkg")}</span>
                  </p>
                  <p className="text-[10px] text-muted mt-1 font-mono">{t("report.horizonADepth")}</p>
                </div>
                <ProgressRing
                  value={Math.min(100, Math.round(((soil.soc_g_per_kg ?? 8) / 16) * 100))}
                  max={100}
                  label={t("soil.soc")}
                  size="2.8rem"
                  thickness="4px"
                  color="var(--accent-canopy)"
                >
                  <span className="text-[9px] font-mono font-bold text-emerald-400">SOC</span>
                </ProgressRing>
              </div>

              <div className="p-3.5 rounded-xl bg-background/60 border border-line">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted">
                  {t("soil.ph")} &amp; {t("report.bulkDensity")}
                </p>
                <p className="text-xl font-bold font-mono text-foreground mt-1">
                  pH {soil.ph ? soil.ph.toFixed(1) : "—"}
                </p>
                <p className="text-[10px] font-mono text-cyan-500 dark:text-cyan-300 mt-1">
                  {soil.ph && soil.ph > 7.5
                    ? t("report.phAlkaline")
                    : soil.ph && soil.ph < 6
                    ? t("report.phAcidic")
                    : t("report.phNeutral")}{" "}
                  · BD {soil.bulk_density_g_cm3?.toFixed(2) ?? "1.40"}
                </p>
              </div>

              {/* Sand / Silt / Clay Granulometry + Saxton-Rawls Available Water */}
              <div className="col-span-2 p-3.5 rounded-xl bg-background/60 border border-line space-y-2.5">
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span className="text-muted uppercase tracking-wider">{t("report.particleFraction")}</span>
                  <span className="text-foreground font-bold">
                    {sand}% {t("soil3d.sand")} · {silt}% {t("soil3d.silt")} · {clay}% {t("soil3d.clay")}
                  </span>
                </div>
                <div className="h-3.5 w-full rounded-full overflow-hidden flex bg-background border border-line">
                  <div style={{ width: `${sand}%` }} className="bg-amber-400" title={`${t("soil3d.sand")}: ${sand}%`} />
                  <div style={{ width: `${silt}%` }} className="bg-cyan-400" title={`${t("soil3d.silt")}: ${silt}%`} />
                  <div style={{ width: `${clay}%` }} className="bg-orange-500" title={`${t("soil3d.clay")}: ${clay}%`} />
                </div>
                <div className="flex items-center justify-between flex-wrap gap-1 text-[10px] font-mono text-muted pt-0.5">
                  <span>
                    {t("report.pawLabel")}: {pawPct}% vol
                  </span>
                  <span className="text-foreground font-semibold">
                    FC {fcPct}% · WP {wpPct}%
                    {soilHealthCard?.available_n_kg_ha != null
                      ? ` · N ${Math.round(soilHealthCard.available_n_kg_ha)}`
                      : soil.source === "farmer_test" && soil.nitrogen_g_kg != null
                      ? ` · N ${Math.round(soil.nitrogen_g_kg * 2240)}`
                      : ""}
                    {soil.available_p_kg_ha ? ` · P ${Math.round(soil.available_p_kg_ha)}` : ""}
                    {soil.available_k_kg_ha ? ` · K ${Math.round(soil.available_k_kg_ha)}` : ""}
                  </span>
                </div>
              </div>

              {/* Soil Health Card (SHC) Lab Override with N, P, K */}
              <div className="col-span-2 p-3 rounded-xl bg-emerald-500/[0.06] border border-emerald-500/30 space-y-2.5">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-1.5 text-[11px] font-mono font-bold text-emerald-600 dark:text-emerald-300">
                    <FlaskConical className="w-3.5 h-3.5 text-emerald-400" />
                    <span>{t("report.shcTitle")}</span>
                    {soil.source === "farmer_test" && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] bg-emerald-500 text-slate-950 font-bold uppercase">
                        {t("report.shcActiveLab")}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5">
                    {soilHealthCard && (
                      <button
                        type="button"
                        onClick={() => setSoilHealthCard(null)}
                        className="px-2 py-0.5 rounded text-[10px] font-mono bg-rose-500/15 text-rose-400 border border-rose-500/30 cursor-pointer"
                      >
                        {t("report.resetBtn")}
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setShowShcForm((v) => !v)}
                      className="px-2.5 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-500 border border-emerald-500/40 cursor-pointer hover:bg-emerald-500/30"
                    >
                      {showShcForm ? t("report.hideForm") : t("report.enterShcValues")}
                    </button>
                  </div>
                </div>

                {showShcForm && (
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-1 text-[11px] font-mono">
                    <label className="space-y-1">
                      <span className="text-[10px] text-muted block">{t("report.shcPhLabel")}</span>
                      <input
                        type="number"
                        step="0.1"
                        min="4.0"
                        max="10.0"
                        value={shcPh}
                        onChange={(e) => setShcPh(e.target.value)}
                        className="w-full px-2 py-1 rounded bg-background border border-line text-foreground"
                      />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-muted block">{t("report.shcSocLabel")}</span>
                      <input
                        type="number"
                        step="0.05"
                        min="0.05"
                        max="4.0"
                        value={shcSocPct}
                        onChange={(e) => setShcSocPct(e.target.value)}
                        className="w-full px-2 py-1 rounded bg-background border border-line text-foreground"
                      />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-muted block">{t("report.shcNLabel")}</span>
                      <input
                        type="number"
                        step="10"
                        min="40"
                        max="600"
                        value={shcN}
                        onChange={(e) => setShcN(e.target.value)}
                        className="w-full px-2 py-1 rounded bg-background border border-line text-foreground"
                      />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-muted block">{t("report.shcPLabel")}</span>
                      <input
                        type="number"
                        step="1"
                        min="1"
                        max="200"
                        value={shcP}
                        onChange={(e) => setShcP(e.target.value)}
                        className="w-full px-2 py-1 rounded bg-background border border-line text-foreground"
                      />
                    </label>
                    <label className="space-y-1">
                      <span className="text-[10px] text-muted block">{t("report.shcKLabel")}</span>
                      <input
                        type="number"
                        step="5"
                        min="10"
                        max="1000"
                        value={shcK}
                        onChange={(e) => setShcK(e.target.value)}
                        className="w-full px-2 py-1 rounded bg-background border border-line text-foreground"
                      />
                    </label>
                    <div className="col-span-2 sm:col-span-5 flex justify-end pt-1">
                      <button
                        type="button"
                        onClick={() => {
                          setSoilHealthCard({
                            ph: Number.isFinite(parseFloat(shcPh)) ? parseFloat(shcPh) : 7.5,
                            soc_pct: Number.isFinite(parseFloat(shcSocPct)) ? parseFloat(shcSocPct) : 0.52,
                            available_n_kg_ha: Number.isFinite(parseFloat(shcN)) ? parseFloat(shcN) : 210,
                            available_p_kg_ha: Number.isFinite(parseFloat(shcP)) ? parseFloat(shcP) : 18,
                            available_k_kg_ha: Number.isFinite(parseFloat(shcK)) ? parseFloat(shcK) : 240,
                          });
                          setShowShcForm(false);
                        }}
                        className="px-3 py-1 rounded-lg bg-emerald-500 text-slate-950 font-bold text-[11px] cursor-pointer hover:opacity-95"
                      >
                        {t("report.applyShcBtn")}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="px-5 pb-4 pt-2 border-t border-line">
            <ProvenanceChip provenance={soil.provenance} />
          </div>
        </div>

        {/* 3. Water & Aquifer Instrument */}
        <div className="glass rounded-2xl border border-line flex flex-col justify-between overflow-hidden">
          <div>
            <div className="instrument-header px-5 py-3 flex items-center justify-between">
              <h3 className="font-display font-bold text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <Droplets className="w-4 h-4 text-cyan-400" />
                <span>
                  FIG. 04 // {t("section.water")} &amp; {t("report.aquifer")}
                </span>
              </h3>
              <span className="text-[10px] font-mono text-muted">{t("report.sensorSourceTag")}</span>
            </div>

            <div className="p-5 grid grid-cols-2 gap-3">
              <div className="p-3.5 rounded-xl bg-background/60 border border-line">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted">
                  {t("water.balance")}
                </p>
                <p
                  className={`text-xl font-bold font-mono mt-1 ${
                    water.climatic_water_balance_mm !== undefined &&
                    water.climatic_water_balance_mm !== null &&
                    water.climatic_water_balance_mm < 0
                      ? "text-amber-500 dark:text-amber-400"
                      : "text-emerald-500"
                  }`}
                >
                  {water.climatic_water_balance_mm !== undefined && water.climatic_water_balance_mm !== null
                    ? `${water.climatic_water_balance_mm.toFixed(0)} mm`
                    : "—"}
                </p>
                <p className="text-[10px] text-muted mt-1 font-mono">{t("report.annualNetBalance")}</p>
              </div>

              <div className="p-3.5 rounded-xl bg-background/60 border border-line">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted">
                  {t("water.groundwater")}
                </p>
                <p
                  className={`text-xl font-bold font-mono mt-1 ${
                    water.groundwater_trend_cm_per_year !== undefined &&
                    water.groundwater_trend_cm_per_year !== null &&
                    water.groundwater_trend_cm_per_year < 0
                      ? "text-rose-500 dark:text-rose-400"
                      : "text-emerald-400"
                  }`}
                >
                  {water.groundwater_trend_cm_per_year !== undefined &&
                  water.groundwater_trend_cm_per_year !== null
                    ? `${water.groundwater_trend_cm_per_year > 0 ? "+" : ""}${water.groundwater_trend_cm_per_year} cm/yr`
                    : "—"}
                </p>
                <p className="text-[10px] font-mono text-muted mt-1 truncate">
                  {water.groundwater_trend_cm_per_year && water.groundwater_trend_cm_per_year < -2.0
                    ? t("report.jplMasconDepletion")
                    : t("report.aquiferStorageTrend")}
                </p>
              </div>

              {water.root_zone_moisture_percentile && (
                <div className="col-span-2 p-3.5 rounded-xl bg-background/60 border border-line space-y-2">
                  <div className="flex items-center justify-between text-[10px] font-mono">
                    <span className="font-bold text-foreground flex items-center gap-1.5 uppercase tracking-wider">
                      <Gauge className="w-3.5 h-3.5 text-cyan-400" />
                      <span>{t("water.smap")}</span>
                      <span className="text-[8px] px-1.5 py-0.5 rounded bg-foreground/10 text-muted font-mono uppercase tracking-wider font-normal">
                        {t("badge.contextOnly")}
                      </span>
                    </span>
                    <span className="text-muted">{t("report.climatologicalPct")}</span>
                  </div>

                  <div className="grid grid-cols-12 gap-1.5 items-end h-12 pt-1">
                    {water.root_zone_moisture_percentile.map((pct, idx) => {
                      const color =
                        pct < 30 ? "bg-rose-500" : pct < 60 ? "bg-amber-400" : "bg-cyan-400";
                      return (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => setSelectedMonth(idx)}
                          className="h-full flex flex-col justify-end items-center group relative cursor-pointer"
                        >
                          <div
                            style={{ height: `${Math.max(pct, 12)}%` }}
                            className={`w-full rounded-t-xs transition-all ${color} group-hover:brightness-125`}
                          />
                          <span className="text-[8px] font-mono text-muted mt-1 group-hover:text-foreground">
                            {MONTHS[idx][0]}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {water.soil_moisture_index_layers && (
                <div className="col-span-2 p-3.5 rounded-xl bg-background/60 border border-line space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono">
                    <span className="font-bold text-foreground flex items-center gap-1.5 uppercase tracking-wider">
                      <Activity className="w-3.5 h-3.5 text-emerald-400" />
                      <span>{t("water.smiLayers")}</span>
                    </span>
                    <div className="flex flex-wrap items-center gap-3 text-muted">
                      {water.soil_moisture_deficit_mm != null && (
                        <span>
                          {t("water.rootDeficit")}:{" "}
                          <strong className="text-foreground">
                            {water.soil_moisture_deficit_mm.toFixed(1)} mm
                          </strong>
                        </span>
                      )}
                      {water.seedbed_temp_5cm_c != null && (
                        <span>
                          {t("water.seedbed5cm")}:{" "}
                          <strong className="text-amber-500 dark:text-amber-400">
                            {water.seedbed_temp_5cm_c.toFixed(1)}°C
                          </strong>
                        </span>
                      )}
                      {water.volumetric_soil_water_layers && (
                        <span className="text-sky-600 dark:text-sky-400">
                          {t("water.vwcLayers")}
                        </span>
                      )}
                      {(water.seedbed_temp_5cm_c != null || water.volumetric_soil_water_layers != null) && (
                        <span className="px-1.5 py-0.5 rounded bg-foreground/5 border border-line text-muted text-[9px] uppercase">
                          {t("badge.contextOnly")}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="grid grid-cols-4 gap-2">
                    {(["-5cm", "-15cm", "-50cm", "-150cm"] as const).map((depth) => {
                      const val = water.soil_moisture_index_layers?.[depth];
                      const pct = val != null ? Math.max(4, Math.min(100, Math.round(val * 100))) : 0;
                      const barColor =
                        val == null
                          ? "bg-muted/30"
                          : val < 0.25
                          ? "bg-rose-500"
                          : val < 0.5
                          ? "bg-amber-400"
                          : val > 0.75
                          ? "bg-emerald-400"
                          : "bg-cyan-400";
                      return (
                        <div key={depth} className="space-y-1">
                          <div className="flex items-center justify-between text-[10px] font-mono">
                            <span className="text-muted">{depth}</span>
                            <span className="font-bold text-foreground">
                              {val != null ? val.toFixed(2) : "—"}
                            </span>
                          </div>
                          <div className="h-1.5 w-full rounded-full bg-foreground/10 overflow-hidden">
                            <div style={{ width: `${pct}%` }} className={`h-full rounded-full ${barColor}`} />
                          </div>
                          {water.volumetric_soil_water_layers?.[depth] != null && (
                            <p className="text-[9px] font-mono text-sky-600 dark:text-sky-400 tabular-nums">
                              {water.volumetric_soil_water_layers[depth]?.toFixed(2)} m³/m³
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="px-5 pb-4 pt-2 border-t border-line">
            <ProvenanceChip provenance={water.provenance} />
          </div>
        </div>

        {/* 4. Hazards & Climate Risks Instrument */}
        <div className="glass rounded-2xl border border-line flex flex-col justify-between overflow-hidden">
          <div>
            <div className="instrument-header px-5 py-3 flex items-center justify-between">
              <h3 className="font-display font-bold text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>FIG. 05 // {t("section.hazards")}</span>
              </h3>
              {hazards.residue_burning_detected === true ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/20 text-rose-500 dark:text-rose-300 border border-rose-500/40 flex items-center gap-1">
                  <Flame className="w-3 h-3" /> {t("telemetry.firmsAnomaly")}
                </span>
              ) : hazards.residue_burning_detected === false ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> {t("telemetry.clearSwath")}
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-500/15 text-amber-600 dark:text-amber-300 border border-amber-500/40 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" /> {t("telemetry.firmsUnverified")}
                </span>
              )}
            </div>

            <div className="p-5 grid grid-cols-2 gap-3">
              <div className="p-3.5 rounded-xl bg-background/60 border border-line">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted">
                  {t("hazards.erosion")}
                </p>
                <p className="text-xl font-bold text-foreground mt-1 uppercase font-mono">
                  {hazards.erosion_risk_class ?? "Low"}
                </p>
                <p className="text-[10px] text-muted mt-1 font-mono">{t("report.rusleFormula")}</p>
              </div>

              <div className="p-3.5 rounded-xl bg-background/60 border border-line">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted">
                  {t("hazards.drought")}
                </p>
                <p className="text-xl font-bold font-mono text-amber-400 mt-1">
                  {hazards.drought_frequency !== undefined && hazards.drought_frequency !== null
                    ? `${(hazards.drought_frequency * 100).toFixed(0)}%`
                    : "—"}
                </p>
                <p className="text-[10px] text-muted mt-1 font-mono">{t("report.historicalRecurrence")}</p>
              </div>

              {hazards.terminal_heat_days_per_year !== undefined &&
                hazards.terminal_heat_days_per_year !== null && (
                  <div className="p-3.5 rounded-xl bg-background/60 border border-line col-span-2 space-y-1">
                    <div className="flex justify-between items-center font-mono">
                      <p className="text-[10px] uppercase tracking-wider text-muted flex items-center gap-1.5">
                        <ThermometerSun className="w-3.5 h-3.5 text-amber-400" />
                        <span>{t("hazards.terminalHeat")}</span>
                      </p>
                      <span className="text-xs font-bold text-amber-500">
                        {hazards.terminal_heat_days_per_year.toFixed(1)} d/yr
                      </span>
                    </div>
                    <p className="text-[10px] text-muted font-mono">
                      {t("report.grainFillHeatDesc")}
                    </p>
                  </div>
                )}

              {(hazards.late_blight_risk_idx != null ||
                hazards.canopy_wetness_idx != null ||
                hazards.fire_weather_index != null ||
                hazards.max_30m_precip_rate_mmh != null ||
                hazards.hail_probability_pct != null ||
                hazards.meteorological_drought_idx != null) && (
                <div className="col-span-2 grid grid-cols-2 gap-2.5">
                  <div className="p-3 rounded-xl bg-background/60 border border-line">
                    <p className="text-[10px] font-mono uppercase tracking-wider text-muted truncate">
                      {t("hazards.lateBlight")}
                    </p>
                    <p className="text-base font-bold font-mono text-foreground mt-0.5">
                      {hazards.late_blight_risk_idx != null
                        ? hazards.late_blight_risk_idx.toFixed(0)
                        : "—"}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-background/60 border border-line">
                    <p className="text-[10px] font-mono uppercase tracking-wider text-muted truncate">
                      {t("hazards.canopyWetness")}
                    </p>
                    <p className="text-base font-bold font-mono text-foreground mt-0.5">
                      {hazards.canopy_wetness_idx != null
                        ? hazards.canopy_wetness_idx.toFixed(2)
                        : "—"}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-background/60 border border-line">
                    <div className="flex items-center justify-between gap-1">
                      <p className="text-[10px] font-mono uppercase tracking-wider text-muted truncate">
                        {t("hazards.fireWeather")}
                      </p>
                      <span className="text-[9px] font-mono px-1 py-0.5 rounded bg-foreground/5 border border-line text-muted shrink-0">
                        {t("badge.contextOnly")}
                      </span>
                    </div>
                    <p className="text-base font-bold font-mono text-amber-500 dark:text-amber-400 mt-0.5">
                      {hazards.fire_weather_index != null
                        ? `${hazards.fire_weather_index.toFixed(1)} FFWI`
                        : "—"}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-background/60 border border-line">
                    <p className="text-[10px] font-mono uppercase tracking-wider text-muted truncate">
                      {t("hazards.peakRainIntensity")}
                    </p>
                    <p className="text-base font-bold font-mono text-cyan-500 dark:text-cyan-400 mt-0.5">
                      {hazards.max_30m_precip_rate_mmh != null
                        ? `${hazards.max_30m_precip_rate_mmh.toFixed(1)} mm/h`
                        : "—"}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-background/60 border border-line">
                    <p className="text-[10px] font-mono uppercase tracking-wider text-muted truncate">
                      {t("hazards.hailRisk")}
                    </p>
                    <p className="text-base font-bold font-mono text-sky-600 dark:text-sky-400 mt-0.5">
                      {hazards.hail_probability_pct != null
                        ? `${hazards.hail_probability_pct.toFixed(1)}%`
                        : "—"}
                    </p>
                  </div>
                  <div className="p-3 rounded-xl bg-background/60 border border-line">
                    <p className="text-[10px] font-mono uppercase tracking-wider text-muted truncate">
                      {t("hazards.droughtIndex")}
                    </p>
                    <p className="text-base font-bold font-mono text-orange-500 dark:text-orange-400 mt-0.5">
                      {hazards.meteorological_drought_idx != null
                        ? `${hazards.meteorological_drought_idx.toFixed(2)} SPI`
                        : "—"}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="px-5 pb-4 pt-2 border-t border-line">
            <ProvenanceChip provenance={hazards.provenance} />
          </div>
        </div>
      </div>

      {/* Satellite Crop History Strip (Phenology & Seasons) */}
      {crop_history && crop_history.length > 0 && (
        <div className="glass rounded-2xl border border-line overflow-hidden">
          <div className="instrument-header px-5 py-3 flex items-center justify-between">
            <h3 className="font-display font-bold text-xs uppercase tracking-wider text-foreground flex items-center gap-2">
              <Calendar className="w-4 h-4 text-emerald-400" />
              <span>FIG. 06 // {t("section.cropHistory")}</span>
            </h3>
            <span className="text-[10px] font-mono text-emerald-500 font-bold px-2 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/35">
              NASA HLS L30/S30 ({t("badge.contextOnly")})
            </span>
          </div>

          <div className="px-4 pt-3 pb-1 border-b border-line bg-surface/50 flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono">
            <div className="flex items-center gap-1.5 text-foreground/90">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span className="font-bold">{t("report.baselineConfirmTitle")}:</span>
              <span className="text-muted">{t("report.baselineConfirmDesc")}</span>
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {[
                { label: t("report.satelliteAuto"), value: null },
                { label: `${cropName("rice_puddled")} → ${cropName("wheat")}`, value: ["rice_puddled", "wheat", "fallow"] },
                { label: `${cropName("cotton")} → ${cropName("wheat")}`, value: ["cotton", "wheat", "fallow"] },
                { label: `${cropName("cotton")} → ${cropName("chickpea")}`, value: ["cotton", "chickpea", "fallow"] },
                { label: `${cropName("sorghum")} → ${cropName("wheat")}`, value: ["sorghum", "wheat", "fallow"] },
                { label: `${cropName("rice_puddled")} → ${cropName("rice_puddled")}`, value: ["rice_puddled", "rice_puddled", "fallow"] },
              ].map((opt) => {
                const isActive =
                  (opt.value === null && baselineOverride === null) ||
                  (opt.value !== null &&
                    baselineOverride !== null &&
                    opt.value[0] === baselineOverride[0] &&
                    opt.value[1] === baselineOverride[1]);
                return (
                  <button
                    key={opt.label}
                    type="button"
                    onClick={() => setBaselineOverride(opt.value)}
                    className={`px-2 py-0.5 rounded text-[10px] transition-colors cursor-pointer border ${
                      isActive
                        ? "bg-emerald-500 text-slate-950 border-emerald-400 font-bold"
                        : "bg-background/70 text-muted hover:text-foreground border-line"
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="p-4 flex gap-3 overflow-x-auto">
            {crop_history.map((season, idx) => {
              const meta = cropMeta(season.crop_group);
              const sName = seasonName(field.lat, field.lon, season.season_index);

              return (
                <div
                  key={idx}
                  className={`flex-shrink-0 p-3.5 rounded-xl border min-w-[164px] transition-all hover:-translate-y-0.5 ${meta.tone} bg-background/70`}
                >
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="font-bold text-foreground">{season.year}</span>
                    <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-foreground/10 border border-line">
                      {sName}
                    </span>
                  </div>

                  <div className="mt-2.5 flex items-center gap-2">
                    <span
                      className="w-6 h-6 rounded text-[9px] font-mono font-bold flex items-center justify-center border border-current/35 shrink-0"
                      style={{ color: meta.color }}
                    >
                      {meta.emoji}
                    </span>
                    <span className="text-xs font-bold capitalize text-foreground truncate">
                      {season.crop_group ? cropName(season.crop_group) : "Crop"}
                    </span>
                  </div>

                  {season.peak && (
                    <div className="text-[10px] text-muted mt-2.5 font-mono flex items-center justify-between border-t border-line pt-1.5">
                      <span>{t("report.ndviPeak")}</span>
                      <span className="font-semibold text-foreground/90">{season.peak}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Optional 3D Stratigraphic Pedon */}
      {show3DPedon && <SoilColumn3D profile={profile} strategies={strategies} />}
    </div>
  );
}
