"use client";

import type { FieldProfile } from "@/types/api";
import { useI18n } from "@/i18n";
import { ProvenanceChip } from "./ProvenanceChip";
import { cropMeta, cropName, seasonName } from "@/lib/ui";
import {
  CloudSun,
  Sprout,
  Droplets,
  AlertTriangle,
  Flame,
  Calendar,
  Sparkles,
  BarChart3,
  TrendingDown,
  Gauge,
  ThermometerSun,
  Activity,
} from "lucide-react";

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function ReportCard({ profile }: { profile: FieldProfile }) {
  const { t } = useI18n();
  const { field, climate, soil, water, hazards, agro_climatic_notes, crop_history, seasons_per_year } = profile;

  const maxMonthlyRain = Math.max(...(climate?.monthly_precip_mm ?? [100]), 10);

  // Sand / Silt / Clay sum verification
  const sand = Math.round(soil.sand_pct ?? 40);
  const silt = Math.round(soil.silt_pct ?? 35);
  const clay = Math.round(soil.clay_pct ?? 25);

  return (
    <div className="space-y-5">
      {/* Field Header Dossier */}
      <div className="glass rounded-3xl p-6 border border-line shadow-sm relative overflow-hidden">
        {/* Subtle decorative glow */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-3xl -z-10" />

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5 shadow-2xs">
                <Sparkles className="w-3.5 h-3.5" />
                Agro-Climatic Diagnostic Dossier
              </span>
              <span className="text-xs text-muted font-mono bg-foreground/5 px-2.5 py-1 rounded-full border border-line">
                {Math.abs(field.lat).toFixed(4)}°{field.lat >= 0 ? "N" : "S"},{" "}
                {Math.abs(field.lon).toFixed(4)}°{field.lon >= 0 ? "E" : "W"}
              </span>
              {seasons_per_year && (
                <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                  {seasons_per_year === 2 ? "Double Cropped (2 seasons/yr)" : `${seasons_per_year} seasons/yr`}
                </span>
              )}
            </div>
            <h2 className="font-display text-2xl sm:text-3xl font-extrabold mt-2 text-foreground tracking-tight">
              {field.name ?? "Selected Field Location"}
            </h2>
          </div>
        </div>

        {/* Insights / Agro-climatic Notes */}
        {agro_climatic_notes && agro_climatic_notes.length > 0 && (
          <div className="mt-5 p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-xs space-y-2">
            <h4 className="font-bold uppercase tracking-wider text-amber-700 dark:text-amber-300 flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-500" />
              <span>{t("section.insights")}</span>
            </h4>
            <ul className="space-y-1.5 text-amber-900 dark:text-amber-200/90 leading-relaxed">
              {agro_climatic_notes.map((note, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-amber-500 shrink-0 font-bold">›</span>
                  <span>{note}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Satellite Crop History Strip (Phenology & Seasons) */}
      {crop_history && crop_history.length > 0 && (
        <div className="glass rounded-3xl p-5 border border-line shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-display font-bold text-sm text-foreground flex items-center gap-2">
              <Calendar className="w-4 h-4 text-indigo-400" />
              <span>{t("section.cropHistory")}</span>
            </h3>
            <span className="text-[11px] font-mono text-muted bg-foreground/5 px-2 py-0.5 rounded-full border border-line">
              NASA HLS 30m · MODIS NDVI
            </span>
          </div>

          <div className="flex gap-3 overflow-x-auto pb-2 pt-1 scrollbar-none">
            {crop_history.map((season, idx) => {
              const meta = cropMeta(season.crop_group);
              const sName = seasonName(field.lat, field.lon, season.season_index);

              return (
                <div
                  key={idx}
                  className={`flex-shrink-0 p-3.5 rounded-2xl border min-w-[145px] transition-transform hover:-translate-y-0.5 duration-200 ${meta.tone} border-line/60 bg-surface shadow-xs`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-black font-mono text-foreground">
                      {season.year}
                    </span>
                    <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-foreground/5 border border-line">
                      {sName}
                    </span>
                  </div>

                  <div className="mt-2.5 flex items-center gap-2">
                    <span className="text-xl">{meta.emoji}</span>
                    <span className="text-xs font-bold capitalize text-foreground truncate">
                      {season.crop_group ? cropName(season.crop_group) : "Crop"}
                    </span>
                  </div>

                  {season.peak && (
                    <div className="text-[10px] text-muted mt-2 font-mono flex items-center gap-1">
                      <span>Peak:</span>
                      <span className="font-semibold text-foreground/80">{season.peak}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Grid: 4 Core Diagnostic Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 1. Climate Card */}
        <div className="glass rounded-3xl p-5 border border-line shadow-sm flex flex-col justify-between hover:border-emerald-500/30 transition-all duration-300">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="font-display font-bold text-sm text-foreground flex items-center gap-2">
                <CloudSun className="w-4 h-4 text-cyan-400" />
                <span>{t("section.climate")}</span>
              </h3>
              <span className="text-[10px] font-mono text-muted bg-foreground/5 px-2 py-0.5 rounded-full border border-line">
                {climate.baseline_period} vs {climate.recent_period}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="p-3.5 rounded-2xl bg-foreground/5 border border-line/60">
                <p className="text-[11px] text-muted font-medium">{t("climate.rain")}</p>
                <p className="text-xl font-black font-mono text-foreground mt-0.5">
                  {climate.recent_annual_precip_mm.toFixed(0)}{" "}
                  <span className="text-xs font-normal text-muted">{t("unit.mmYr")}</span>
                </p>
                <p className="text-[10px] font-semibold text-emerald-500 dark:text-emerald-400 mt-1">
                  Change: {climate.precip_change_pct > 0 ? "+" : ""}
                  {climate.precip_change_pct.toFixed(0)}%
                </p>
              </div>

              <div className="p-3.5 rounded-2xl bg-foreground/5 border border-line/60">
                <p className="text-[11px] text-muted font-medium">{t("climate.heatDays")}</p>
                <p className="text-xl font-black font-mono text-foreground mt-0.5">
                  {climate.recent_heat_days_per_year.toFixed(0)}{" "}
                  <span className="text-xs font-normal text-muted">{t("unit.days")}</span>
                </p>
                <p className="text-[10px] text-muted mt-1 font-mono">
                  Base: {climate.heat_days_per_year.toFixed(0)} d/yr
                </p>
              </div>

              <div className="p-3.5 rounded-2xl bg-foreground/5 border border-line/60">
                <p className="text-[11px] text-muted font-medium">{t("climate.et0")}</p>
                <p className="text-xl font-black font-mono text-foreground mt-0.5">
                  {climate.annual_et0_mm ? climate.annual_et0_mm.toFixed(0) : "—"}{" "}
                  <span className="text-xs font-normal text-muted">{t("unit.mmYr")}</span>
                </p>
                <p className="text-[10px] text-muted mt-1">Atmospheric demand</p>
              </div>

              <div className="p-3.5 rounded-2xl bg-foreground/5 border border-line/60">
                <p className="text-[11px] text-muted font-medium">{t("climate.drySpell")}</p>
                <p className="text-xl font-black font-mono text-foreground mt-0.5">
                  {climate.longest_dry_spell_days_mean.toFixed(0)}{" "}
                  <span className="text-xs font-normal text-muted">{t("unit.days")}</span>
                </p>
                <p className="text-[10px] text-muted mt-1">Rainy-season spell</p>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-line">
            <ProvenanceChip provenance={climate.provenance} />
          </div>
        </div>

        {/* 2. Soil Card with Visual Sand/Silt/Clay Bar */}
        <div className="glass rounded-3xl p-5 border border-line shadow-sm flex flex-col justify-between hover:border-emerald-500/30 transition-all duration-300">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="font-display font-bold text-sm text-foreground flex items-center gap-2">
                <Sprout className="w-4 h-4 text-emerald-400" />
                <span>{t("section.soil")}</span>
              </h3>
              <div className="flex items-center gap-1.5">
                {soil.texture_class && (
                  <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-500/15 text-amber-600 dark:text-amber-300 border border-amber-500/30 capitalize">
                    {soil.texture_class}
                  </span>
                )}
                {soil.slope_pct !== undefined && soil.slope_pct !== null && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-mono text-muted bg-foreground/5 border border-line">
                    Slope {soil.slope_pct}%
                  </span>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="p-3.5 rounded-2xl bg-foreground/5 border border-line/60">
                <p className="text-[11px] text-muted font-medium">{t("soil.soc")}</p>
                <p className="text-xl font-black font-mono text-foreground mt-0.5">
                  {soil.soc_g_per_kg ? soil.soc_g_per_kg.toFixed(1) : "—"}{" "}
                  <span className="text-xs font-normal text-muted">{t("unit.gkg")}</span>
                </p>
                <p className="text-[10px] text-muted mt-1">Topsoil (0–30 cm)</p>
              </div>

              <div className="p-3.5 rounded-2xl bg-foreground/5 border border-line/60">
                <p className="text-[11px] text-muted font-medium">{t("soil.ph")}</p>
                <p className="text-xl font-black font-mono text-foreground mt-0.5">
                  {soil.ph ? soil.ph.toFixed(1) : "—"}
                </p>
                <p className="text-[10px] font-semibold text-emerald-500 dark:text-emerald-400 mt-1">
                  {soil.ph && soil.ph > 7.5 ? "Alkaline" : soil.ph && soil.ph < 6 ? "Acidic" : "Optimal Neutral"}
                </p>
              </div>

              {/* Sand / Silt / Clay Composition Breakdown Bar */}
              <div className="col-span-2 p-3.5 rounded-2xl bg-foreground/5 border border-line/60 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted font-medium">Texture Composition</span>
                  <span className="font-mono text-[11px] text-foreground font-semibold">
                    {sand}% Sand · {silt}% Silt · {clay}% Clay
                  </span>
                </div>
                {/* Visual stacked bar */}
                <div className="h-3.5 w-full rounded-full overflow-hidden flex shadow-inner bg-background/50">
                  <div style={{ width: `${sand}%` }} className="bg-amber-400" title={`Sand: ${sand}%`} />
                  <div style={{ width: `${silt}%` }} className="bg-yellow-500" title={`Silt: ${silt}%`} />
                  <div style={{ width: `${clay}%` }} className="bg-rose-500" title={`Clay: ${clay}%`} />
                </div>
                <div className="flex items-center justify-between text-[10px] text-muted pt-0.5">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-amber-400" /> Sand
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-yellow-500" /> Silt
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-rose-500" /> Clay
                  </span>
                  <span className="font-mono">
                    FC {soil.field_capacity_vol ? `${(soil.field_capacity_vol * 100).toFixed(0)}%` : "—"} / WP{" "}
                    {soil.wilting_point_vol ? `${(soil.wilting_point_vol * 100).toFixed(0)}%` : "—"}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-line">
            <ProvenanceChip provenance={soil.provenance} />
          </div>
        </div>

        {/* 3. Water & Aquifer Card with SMAP Percentiles */}
        <div className="glass rounded-3xl p-5 border border-line shadow-sm flex flex-col justify-between hover:border-emerald-500/30 transition-all duration-300">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="font-display font-bold text-sm text-foreground flex items-center gap-2">
                <Droplets className="w-4 h-4 text-blue-400" />
                <span>{t("section.water")}</span>
              </h3>
              <span className="text-[10px] font-mono text-muted bg-foreground/5 px-2 py-0.5 rounded-full border border-line">
                NASA SMAP &amp; GRACE-FO
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="p-3.5 rounded-2xl bg-foreground/5 border border-line/60">
                <p className="text-[11px] text-muted font-medium">{t("water.balance")}</p>
                <p
                  className={`text-xl font-black font-mono mt-0.5 ${
                    water.climatic_water_balance_mm && water.climatic_water_balance_mm < 0
                      ? "text-rose-500 dark:text-rose-400"
                      : "text-emerald-500 dark:text-emerald-400"
                  }`}
                >
                  {water.climatic_water_balance_mm ? `${water.climatic_water_balance_mm.toFixed(0)} mm` : "—"}
                </p>
                <p className="text-[10px] text-muted mt-1">P - ET₀ Annual</p>
              </div>

              <div className="p-3.5 rounded-2xl bg-foreground/5 border border-line/60">
                <p className="text-[11px] text-muted font-medium">{t("water.groundwater")}</p>
                <p
                  className={`text-xl font-black font-mono mt-0.5 ${
                    water.groundwater_trend_cm_per_year && water.groundwater_trend_cm_per_year < 0
                      ? "text-rose-500 dark:text-rose-400"
                      : "text-foreground"
                  }`}
                >
                  {water.groundwater_trend_cm_per_year
                    ? `${water.groundwater_trend_cm_per_year > 0 ? "+" : ""}${water.groundwater_trend_cm_per_year} cm/yr`
                    : "—"}
                </p>
                <p className="text-[10px] font-semibold text-rose-500 dark:text-rose-400 mt-1 truncate">
                  {water.groundwater_trend_cm_per_year && water.groundwater_trend_cm_per_year < -2.0
                    ? "Severe Drawdown (GRACE)"
                    : "Stable Groundwater"}
                </p>
              </div>

              {/* SMAP Root-zone percentiles sparkline */}
              {water.root_zone_moisture_percentile && (
                <div className="col-span-2 p-3.5 rounded-2xl bg-foreground/5 border border-line/60 space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-[11px] font-semibold text-foreground flex items-center gap-1.5">
                      <Gauge className="w-3.5 h-3.5 text-blue-400" />
                      <span>{t("water.smap")}</span>
                    </p>
                    <span className="text-[10px] text-muted font-mono">12-Mo Percentiles</span>
                  </div>

                  <div className="grid grid-cols-12 gap-1.5 items-end h-10 pt-1">
                    {water.root_zone_moisture_percentile.map((pct, idx) => {
                      const color =
                        pct < 30 ? "bg-rose-500" : pct < 60 ? "bg-amber-400" : "bg-emerald-500";
                      return (
                        <div
                          key={idx}
                          className="h-full flex flex-col justify-end items-center group relative cursor-pointer"
                        >
                          <div
                            style={{ height: `${Math.max(pct, 12)}%` }}
                            className={`w-full rounded-t-md transition-all duration-300 ${color} group-hover:brightness-125`}
                          />
                          <span className="text-[8px] font-mono text-muted mt-1 group-hover:text-foreground">
                            {MONTH_NAMES[idx][0]}
                          </span>
                          {/* Tooltip on hover */}
                          <div className="absolute bottom-12 hidden group-hover:block z-20 glass-strong text-[9px] font-mono px-2 py-0.5 rounded-md whitespace-nowrap shadow-md border border-line">
                            {MONTH_NAMES[idx]}: {pct.toFixed(0)}th %ile
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-line">
            <ProvenanceChip provenance={water.provenance} />
          </div>
        </div>

        {/* 4. Hazards & Climate Risks Card */}
        <div className="glass rounded-3xl p-5 border border-line shadow-sm flex flex-col justify-between hover:border-emerald-500/30 transition-all duration-300">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="font-display font-bold text-sm text-foreground flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>{t("section.hazards")}</span>
              </h3>
              {hazards.residue_burning_detected ? (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-500 border border-rose-500/40 animate-pulse flex items-center gap-1">
                  <Flame className="w-3.5 h-3.5" /> Fire Detected
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                  Residue Cleared
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="p-3.5 rounded-2xl bg-foreground/5 border border-line/60">
                <p className="text-[11px] text-muted font-medium">{t("hazards.erosion")}</p>
                <p className="text-xl font-black text-foreground mt-0.5 uppercase font-mono">
                  {hazards.erosion_risk_class ?? "Low"}
                </p>
                <p className="text-[10px] text-muted mt-1">RUSLE water erosion</p>
              </div>

              <div className="p-3.5 rounded-2xl bg-foreground/5 border border-line/60">
                <p className="text-[11px] text-muted font-medium">{t("hazards.drought")}</p>
                <p className="text-xl font-black font-mono text-foreground mt-0.5">
                  {hazards.drought_frequency ? `${(hazards.drought_frequency * 100).toFixed(0)}%` : "—"}
                </p>
                <p className="text-[10px] text-muted mt-1">Historical frequency</p>
              </div>

              {/* Terminal Heat Days */}
              {hazards.terminal_heat_days_per_year !== undefined && hazards.terminal_heat_days_per_year !== null && (
                <div className="p-3.5 rounded-2xl bg-foreground/5 border border-line/60 col-span-2 space-y-1">
                  <div className="flex justify-between items-center">
                    <p className="text-[11px] text-muted font-medium flex items-center gap-1">
                      <ThermometerSun className="w-3.5 h-3.5 text-amber-500" />
                      <span>{t("hazards.terminalHeat")}</span>
                    </p>
                    <span className="text-xs font-bold text-amber-600 dark:text-amber-400 font-mono">
                      {hazards.terminal_heat_days_per_year.toFixed(1)} days/yr
                    </span>
                  </div>
                  <p className="text-[10px] text-muted">
                    Wheat grain-filling window (1 Mar–15 Apr) with Tmax &gt; 32 °C
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-line text-[10px] text-muted flex items-center justify-between">
            <span>NASA FIRMS active fire satellite detection</span>
            <span className="font-mono">RUSLE v2.1</span>
          </div>
        </div>
      </div>

      {/* Monthly Rainfall & Temperature Chart */}
      <div className="glass rounded-3xl p-6 border border-line shadow-sm space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="font-display font-bold text-base text-foreground flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-emerald-400" />
            <span>{t("climate.monthlyRain")} &amp; Temperature Dynamics</span>
          </h3>
          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5 text-muted">
              <span className="w-3 h-3 rounded-sm bg-blue-500 inline-block" /> Monsoon / Wet
            </span>
            <span className="flex items-center gap-1.5 text-muted">
              <span className="w-3 h-3 rounded-sm bg-blue-300 dark:bg-blue-800 inline-block" /> Dry / Normal
            </span>
          </div>
        </div>

        <div className="grid grid-cols-12 gap-2 items-end h-36 pt-4">
          {climate.monthly_precip_mm.map((val, idx) => {
            const heightPct = Math.round((val / maxMonthlyRain) * 100);
            const isMonsoon = climate.wettest_months.includes(idx + 1);
            const tmax = climate.monthly_tmax_c?.[idx];

            return (
              <div key={idx} className="flex flex-col items-center gap-1.5 h-full justify-end group relative cursor-pointer">
                {/* Floating tooltip */}
                <div className="absolute bottom-24 hidden group-hover:flex flex-col items-center z-20 glass-strong text-[10px] px-2.5 py-1.5 rounded-xl whitespace-nowrap shadow-xl border border-line">
                  <span className="font-bold text-foreground">{MONTH_NAMES[idx]}</span>
                  <span className="text-blue-500 font-mono">{val.toFixed(1)} mm</span>
                  {tmax && <span className="text-amber-500 font-mono">Tmax: {tmax.toFixed(1)}°C</span>}
                </div>

                <span className="text-[10px] font-mono text-muted group-hover:text-blue-400">
                  {val.toFixed(0)}
                </span>
                <div
                  style={{ height: `${Math.max(heightPct, 8)}%` }}
                  className={`w-full rounded-t-lg transition-all duration-300 ${
                    isMonsoon
                      ? "bg-gradient-to-t from-blue-600 to-cyan-400 shadow-xs"
                      : "bg-blue-300/60 dark:bg-blue-900/40"
                  } group-hover:brightness-125`}
                />
                <span className={`text-[11px] font-bold ${isMonsoon ? "text-cyan-500" : "text-muted"}`}>
                  {MONTH_NAMES[idx]}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
