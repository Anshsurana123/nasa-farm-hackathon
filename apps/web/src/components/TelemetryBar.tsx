"use client";

import type { FieldProfile } from "@/types/api";
import { useI18n } from "@/i18n";
import {
  Droplets,
  CloudSunRain,
  Sprout,
  CalendarDays,
  Flame,
  ShieldAlert,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

export function TelemetryBar({ profile }: { profile: FieldProfile }) {
  const { t } = useI18n();
  const { climate, soil, water, hazards, seasons_per_year, crop_history } = profile;

  const gw = water.groundwater_trend_cm_per_year;
  const isSevereGw = gw !== undefined && gw !== null && gw < -2.0;
  const isModerateGw = gw !== undefined && gw !== null && gw < 0 && gw >= -2.0;
  const isPositiveGw = gw !== undefined && gw !== null && gw >= 0;

  const wb = water.climatic_water_balance_mm;
  const hasFire = hazards.residue_burning_detected;

  // Determine dominant recent rotation from history
  let historyLabel = seasons_per_year ? `${seasons_per_year} Seasons / Year` : "Annual Cropping";
  if (crop_history && crop_history.length >= 2) {
    const crops = crop_history.slice(-2).map((s) => s.crop_group ?? "Crop");
    historyLabel = `${crops[0]} ➔ ${crops[1]}`;
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3.5">
      {/* 1. Groundwater Trend */}
      <div className="glass rounded-2xl p-4 flex flex-col justify-between hover:border-emerald-500/40 transition-all duration-300 group shadow-sm hover:shadow-md">
        <div className="flex items-center justify-between text-[11px] text-muted font-medium">
          <span className="flex items-center gap-1.5 font-semibold text-foreground/80">
            <Droplets className="w-3.5 h-3.5 text-cyan-400" />
            <span>{t("telemetry.groundwater")}</span>
          </span>
          <span className="font-mono text-[9px] px-1.5 py-0.5 rounded-md bg-foreground/5 text-muted border border-line">
            GRACE-FO
          </span>
        </div>

        <div className="mt-3">
          <div className="flex items-baseline gap-1.5">
            <span
              className={`text-2xl font-black font-mono tracking-tight ${
                isSevereGw
                  ? "text-rose-500 dark:text-rose-400"
                  : isModerateGw
                  ? "text-amber-500 dark:text-amber-400"
                  : "text-emerald-500 dark:text-emerald-400"
              }`}
            >
              {gw !== undefined && gw !== null ? `${gw > 0 ? "+" : ""}${gw.toFixed(2)}` : "—"}
            </span>
            <span className="text-xs font-semibold text-muted font-mono">cm/yr</span>
          </div>

          <div className="mt-2 flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  isSevereGw ? "bg-rose-400" : isModerateGw ? "bg-amber-400" : "bg-emerald-400"
                }`}
              />
              <span
                className={`relative inline-flex rounded-full h-2 w-2 ${
                  isSevereGw ? "bg-rose-500" : isModerateGw ? "bg-amber-500" : "bg-emerald-500"
                }`}
              />
            </span>
            <span className="text-[10px] font-semibold text-foreground/90 truncate flex items-center gap-1">
              {isSevereGw ? (
                <>
                  <TrendingDown className="w-3 h-3 text-rose-500" />
                  <span>Severe Aquifer Drawdown</span>
                </>
              ) : isModerateGw ? (
                <>
                  <TrendingDown className="w-3 h-3 text-amber-500" />
                  <span>Moderate Overdraft</span>
                </>
              ) : isPositiveGw ? (
                <>
                  <TrendingUp className="w-3 h-3 text-emerald-500" />
                  <span>Stable Storage</span>
                </>
              ) : (
                <span>Baseline Steady</span>
              )}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Climatic Water Balance */}
      <div className="glass rounded-2xl p-4 flex flex-col justify-between hover:border-emerald-500/40 transition-all duration-300 group shadow-sm hover:shadow-md">
        <div className="flex items-center justify-between text-[11px] text-muted font-medium">
          <span className="flex items-center gap-1.5 font-semibold text-foreground/80">
            <CloudSunRain className="w-3.5 h-3.5 text-blue-400" />
            <span>{t("telemetry.waterBalance")}</span>
          </span>
          <span className="font-mono text-[9px] px-1.5 py-0.5 rounded-md bg-foreground/5 text-muted border border-line">
            P - ET₀
          </span>
        </div>

        <div className="mt-3">
          <div className="flex items-baseline gap-1.5">
            <span
              className={`text-2xl font-black font-mono tracking-tight ${
                wb && wb < 0 ? "text-amber-500 dark:text-amber-400" : "text-emerald-500 dark:text-emerald-400"
              }`}
            >
              {wb !== undefined && wb !== null ? Math.round(wb).toLocaleString() : "—"}
            </span>
            <span className="text-xs font-semibold text-muted font-mono">mm/yr</span>
          </div>
          <p className="text-[10px] text-muted mt-2 truncate font-mono">
            Rain {Math.round(climate.annual_precip_mm)} · ET₀ {Math.round(climate.annual_et0_mm ?? 1500)}
          </p>
        </div>
      </div>

      {/* 3. Soil Organic Carbon */}
      <div className="glass rounded-2xl p-4 flex flex-col justify-between hover:border-emerald-500/40 transition-all duration-300 group shadow-sm hover:shadow-md">
        <div className="flex items-center justify-between text-[11px] text-muted font-medium">
          <span className="flex items-center gap-1.5 font-semibold text-foreground/80">
            <Sprout className="w-3.5 h-3.5 text-emerald-400" />
            <span>{t("telemetry.soc")}</span>
          </span>
          <span className="font-mono text-[9px] px-1.5 py-0.5 rounded-md bg-foreground/5 text-muted border border-line">
            SoilGrids
          </span>
        </div>

        <div className="mt-3">
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-black font-mono tracking-tight text-foreground">
              {soil.soc_g_per_kg !== undefined && soil.soc_g_per_kg !== null ? soil.soc_g_per_kg.toFixed(1) : "—"}
            </span>
            <span className="text-xs font-semibold text-muted font-mono">g C/kg</span>
          </div>
          <p className="text-[10px] text-muted mt-2 capitalize truncate">
            {soil.texture_class ?? "Loam"} · pH {soil.ph ? soil.ph.toFixed(1) : "—"}
          </p>
        </div>
      </div>

      {/* 4. Satellite Phenology / Crop History */}
      <div className="glass rounded-2xl p-4 flex flex-col justify-between hover:border-emerald-500/40 transition-all duration-300 group shadow-sm hover:shadow-md">
        <div className="flex items-center justify-between text-[11px] text-muted font-medium">
          <span className="flex items-center gap-1.5 font-semibold text-foreground/80">
            <CalendarDays className="w-3.5 h-3.5 text-indigo-400" />
            <span>{t("telemetry.seasons")}</span>
          </span>
          <span className="font-mono text-[9px] px-1.5 py-0.5 rounded-md bg-foreground/5 text-muted border border-line">
            HLS / MODIS
          </span>
        </div>

        <div className="mt-3">
          <p className="text-sm font-bold text-foreground capitalize truncate">
            {historyLabel}
          </p>
          <div className="mt-2 flex items-center gap-1 text-[10px] text-emerald-500 dark:text-emerald-400 font-semibold">
            <ShieldCheck className="w-3 h-3 shrink-0" />
            <span className="truncate">NDVI Phenology Inferred</span>
          </div>
        </div>
      </div>

      {/* 5. Fire & Risk Screen */}
      <div className="col-span-2 sm:col-span-2 md:col-span-3 lg:col-span-1 glass rounded-2xl p-4 flex flex-col justify-between hover:border-emerald-500/40 transition-all duration-300 group shadow-sm hover:shadow-md">
        <div className="flex items-center justify-between text-[11px] text-muted font-medium">
          <span className="flex items-center gap-1.5 font-semibold text-foreground/80">
            <Flame className="w-3.5 h-3.5 text-rose-400" />
            <span>{t("telemetry.stubble")}</span>
          </span>
          <span className="font-mono text-[9px] px-1.5 py-0.5 rounded-md bg-foreground/5 text-muted border border-line">
            FIRMS
          </span>
        </div>

        <div className="mt-3">
          <div className="flex items-center gap-1.5">
            {hasFire ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-rose-500/15 text-rose-500 border border-rose-500/30 animate-pulse">
                <Flame className="w-3 h-3" />
                Active Fire
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-500 border border-emerald-500/30">
                <ShieldCheck className="w-3 h-3" />
                Clean / No Fire
              </span>
            )}
          </div>
          <p className="text-[10px] text-muted mt-2 truncate flex items-center gap-1">
            <ShieldAlert className="w-3 h-3 text-amber-400 shrink-0" />
            <span>
              Erosion: <strong className="uppercase text-foreground">{hazards.erosion_risk_class ?? "Low"}</strong>
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}
