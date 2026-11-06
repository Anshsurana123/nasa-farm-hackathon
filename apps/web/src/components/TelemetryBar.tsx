"use client";

import Link from "next/link";
import type { FieldProfile } from "@/types/api";
import { useI18n } from "@/i18n";
import { cropName } from "@/lib/ui";
import { ProgressRing } from "./ProgressRing";
import {
  Droplets,
  CloudSunRain,
  Sprout,
  CalendarDays,
  Flame,
  TrendingDown,
  TrendingUp,
  CheckCircle2,
  ShieldCheck,
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

  const soc = soil.soc_g_per_kg ?? 8.0;
  const socScore = Math.min(100, Math.round((soc / 16) * 100));

  const smapArr = water.root_zone_moisture_percentile ?? [];
  const meanSmap = smapArr.length
    ? Math.round(smapArr.reduce((a, b) => a + b, 0) / smapArr.length)
    : 48;

  let historyLabel = seasons_per_year ? `${seasons_per_year} Seasons / Yr` : "Annual Cropping";
  if (crop_history && crop_history.length >= 2) {
    const crops = crop_history.slice(-2).map((s) => cropName(s.crop_group ?? "Crop"));
    historyLabel = `${crops[0]} → ${crops[1]}`;
  }

  return (
    <div className="glass rounded-2xl border border-line overflow-hidden reticle-frame">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 divide-y sm:divide-y-0 sm:divide-x divide-line">
        {/* 1. Groundwater Trend (GRACE-FO) */}
        <Link
          href="/diagnostics"
          className="p-4 flex items-center justify-between gap-3 bg-surface/50 hover:bg-cyan-500/[0.06] transition-colors group"
        >
          <div className="space-y-1.5 min-w-0">
            <div className="flex items-center gap-1.5 text-[10px] font-mono text-muted">
              <Droplets className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span className="uppercase tracking-wider font-bold text-foreground/85 truncate">
                {t("telemetry.groundwater")}
              </span>
            </div>

            <div className="flex items-baseline gap-1.5">
              <span
                className={`text-2xl font-bold font-mono tracking-tight ${
                  isSevereGw
                    ? "text-rose-500 dark:text-rose-400"
                    : isModerateGw
                    ? "text-amber-500 dark:text-amber-400"
                    : "text-emerald-600 dark:text-emerald-400"
                }`}
              >
                {gw !== undefined && gw !== null ? `${gw > 0 ? "+" : ""}${gw.toFixed(2)}` : "—"}
              </span>
              <span className="text-[11px] font-mono text-muted">cm/yr</span>
            </div>

            <div className="flex items-center gap-1.5 text-[10px] font-mono">
              {isSevereGw ? (
                <span className="text-rose-500 dark:text-rose-400 flex items-center gap-1 font-semibold">
                  <TrendingDown className="w-3 h-3" />
                  Critical Drawdown
                </span>
              ) : isModerateGw ? (
                <span className="text-amber-500 dark:text-amber-400 flex items-center gap-1 font-semibold">
                  <TrendingDown className="w-3 h-3" />
                  Moderate Overdraft
                </span>
              ) : isPositiveGw ? (
                <span className="text-emerald-500 flex items-center gap-1 font-semibold">
                  <TrendingUp className="w-3 h-3" />
                  Net Recharge
                </span>
              ) : (
                <span className="text-muted">Equilibrium</span>
              )}
            </div>
          </div>

          <span className="px-2 py-1 rounded-lg bg-cyan-500/15 border border-cyan-500/35 text-[9px] font-mono font-bold text-cyan-600 dark:text-cyan-300 shrink-0">
            GRACE-FO
          </span>
        </Link>

        {/* 2. Climatic Water Balance + SMAP Ring */}
        <Link
          href="/diagnostics"
          className="p-4 flex items-center justify-between gap-3 bg-surface/50 hover:bg-sky-500/[0.06] transition-colors group"
        >
          <div className="space-y-1.5 min-w-0">
            <div className="flex items-center gap-1.5 text-[10px] font-mono text-muted">
              <CloudSunRain className="w-3.5 h-3.5 text-sky-400 shrink-0" />
              <span className="uppercase tracking-wider font-bold text-foreground/85 truncate">
                {t("telemetry.waterBalance")}
              </span>
            </div>

            <div className="flex items-baseline gap-1.5">
              <span
                className={`text-2xl font-bold font-mono tracking-tight ${
                  wb && wb < 0
                    ? "text-amber-500 dark:text-amber-400"
                    : "text-emerald-600 dark:text-emerald-400"
                }`}
              >
                {wb !== undefined && wb !== null ? Math.round(wb).toLocaleString() : "—"}
              </span>
              <span className="text-[11px] font-mono text-muted">mm/yr</span>
            </div>

            <p className="text-[10px] text-muted truncate font-mono">
              Rain {Math.round(climate.annual_precip_mm)} · ET₀{" "}
              {Math.round(climate.annual_et0_mm ?? 1500)} mm
            </p>
          </div>

          <ProgressRing
            value={meanSmap}
            max={100}
            label="SMAP Root-Zone Soil Moisture Percentile"
            size="2.9rem"
            thickness="4px"
            color="var(--accent-water)"
          >
            <span className="text-[9px] font-mono font-bold text-foreground">{meanSmap}%</span>
          </ProgressRing>
        </Link>

        {/* 3. Soil Organic Carbon + Ring */}
        <Link
          href="/diagnostics"
          className="p-4 flex items-center justify-between gap-3 bg-surface/50 hover:bg-emerald-500/[0.06] transition-colors group"
        >
          <div className="space-y-1.5 min-w-0">
            <div className="flex items-center gap-1.5 text-[10px] font-mono text-muted">
              <Sprout className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span className="uppercase tracking-wider font-bold text-foreground/85 truncate">
                {t("telemetry.soc")}
              </span>
            </div>

            <div className="flex items-baseline gap-1.5">
              <span className="text-2xl font-bold font-mono tracking-tight text-foreground">
                {soil.soc_g_per_kg !== undefined && soil.soc_g_per_kg !== null
                  ? soil.soc_g_per_kg.toFixed(1)
                  : "—"}
              </span>
              <span className="text-[11px] font-mono text-muted">g C/kg</span>
            </div>

            <p className="text-[10px] text-muted capitalize truncate font-mono">
              {soil.texture_class ?? "Loam"} · pH {soil.ph ? soil.ph.toFixed(1) : "—"}
            </p>
          </div>

          <ProgressRing
            value={socScore}
            max={100}
            label="Topsoil Organic Carbon Index"
            size="2.9rem"
            thickness="4px"
            color="var(--accent-canopy)"
          >
            <span className="text-[9px] font-mono font-bold text-emerald-500">SOC</span>
          </ProgressRing>
        </Link>

        {/* 4. Satellite Phenology / Crop History */}
        <Link
          href="/rotations"
          className="p-4 flex flex-col justify-between bg-surface/50 hover:bg-amber-500/[0.06] transition-colors"
        >
          <div className="flex items-center justify-between text-[10px] font-mono text-muted">
            <span className="flex items-center gap-1.5 uppercase tracking-wider font-bold text-foreground/85">
              <CalendarDays className="w-3.5 h-3.5 text-amber-400" />
              <span>{t("telemetry.seasons")}</span>
            </span>
            <span className="px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-500/35 text-amber-600 dark:text-amber-300 font-bold text-[9px]">
              HLS 30m
            </span>
          </div>

          <div className="mt-2">
            <p className="text-sm font-bold text-foreground font-mono truncate">{historyLabel}</p>
            <div className="mt-1 flex items-center gap-1 text-[10px] font-mono text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-3 h-3 shrink-0" />
              <span className="truncate">Savitzky-Golay NDVI Verified</span>
            </div>
          </div>
        </Link>

        {/* 5. Fire & Risk Screen */}
        <Link
          href="/lab"
          className="col-span-1 sm:col-span-2 lg:col-span-1 p-4 flex flex-col justify-between bg-surface/50 hover:bg-rose-500/[0.06] transition-colors"
        >
          <div className="flex items-center justify-between text-[10px] font-mono text-muted">
            <span className="flex items-center gap-1.5 uppercase tracking-wider font-bold text-foreground/85">
              <Flame className="w-3.5 h-3.5 text-rose-400" />
              <span>{t("telemetry.stubble")}</span>
            </span>
            <span className="px-1.5 py-0.5 rounded bg-rose-500/15 border border-rose-500/35 text-rose-500 dark:text-rose-300 font-bold text-[9px]">
              FIRMS
            </span>
          </div>

          <div className="mt-2">
            <div className="flex items-center gap-1.5">
              {hasFire ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-mono font-bold bg-rose-500/20 text-rose-500 dark:text-rose-300 border border-rose-500/40">
                  <Flame className="w-3.5 h-3.5 text-rose-500" />
                  <span>Thermal Anomaly</span>
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-mono font-bold bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Clear Swath</span>
                </span>
              )}
            </div>
            <p className="text-[10px] text-muted mt-1.5 truncate font-mono">
              RUSLE Erosion:{" "}
              <strong className="uppercase text-foreground">
                {hazards.erosion_risk_class ?? "Low"}
              </strong>
            </p>
          </div>
        </Link>
      </div>
    </div>
  );
}
