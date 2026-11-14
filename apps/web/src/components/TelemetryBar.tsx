"use client";

import { useState } from "react";
import Link from "next/link";
import type { FieldProfile, TacticalAdvisory } from "@/types/api";
import { api } from "@/lib/api";
import { useI18n } from "@/i18n";
import { cropName } from "@/lib/ui";
import { ProgressRing } from "./ProgressRing";
import { ProvenanceChip } from "./ProvenanceChip";
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
  Thermometer,
  Gauge,
  SprayCan,
  RefreshCw,
  Wind,
} from "lucide-react";

export function TelemetryBar({ profile }: { profile: FieldProfile }) {
  const { t } = useI18n();
  const { climate, soil, water, hazards, seasons_per_year, crop_history, tactical_advisory: propAdvisory } = profile;
  const [liveOverride, setLiveOverride] = useState<{
    key: string;
    adv: TacticalAdvisory;
  } | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fieldKey = `${profile.field.lat.toFixed(4)},${profile.field.lon.toFixed(4)}`;
  const tactical_advisory =
    liveOverride && liveOverride.key === fieldKey ? liveOverride.adv : propAdvisory;

  const forecastDays = tactical_advisory?.forecast_days ?? [];
  const tempMin7d = forecastDays.length ? Math.min(...forecastDays.map((d) => d.tmin_c)) : null;
  const tempMax7d = forecastDays.length ? Math.max(...forecastDays.map((d) => d.tmax_c)) : null;
  const wind3dSlice = forecastDays.slice(0, 3);
  const maxWind3d = wind3dSlice.length ? Math.max(...wind3dSlice.map((d) => d.wind_speed_ms)) : null;

  async function handleRefreshForecast() {
    if (refreshing) return;
    setRefreshing(true);
    try {
      const updated = await api.tacticalAdvisory(profile.field.lat, profile.field.lon);
      setLiveOverride({ key: fieldKey, adv: updated });
    } catch {
      // Preserve existing advisory if live tactical endpoint is unavailable.
    } finally {
      setRefreshing(false);
    }
  }

  const gw = water.groundwater_trend_cm_per_year;
  const isSevereGw = gw !== undefined && gw !== null && gw < -2.0;
  const isModerateGw = gw !== undefined && gw !== null && gw < 0 && gw >= -2.0;
  const isPositiveGw = gw !== undefined && gw !== null && gw >= 0;

  const wb = water.climatic_water_balance_mm;
  const hasFire = hazards.residue_burning_detected;

  const soc = soil.soc_g_per_kg ?? 0;
  const socScore = Math.min(100, Math.round((soc / 16) * 100));

  const smapArr = water.root_zone_moisture_percentile ?? [];
  const meanSmap = smapArr.length
    ? Math.round(smapArr.reduce((a, b) => a + b, 0) / smapArr.length)
    : null;

  let historyLabel = seasons_per_year
    ? `${seasons_per_year} ${t("telemetry.seasonsPerYr")}`
    : t("telemetry.annualCropping");
  if (crop_history && crop_history.length >= 2) {
    const crops = crop_history.slice(-2).map((s) => cropName(s.crop_id ?? s.crop_group ?? "Crop"));
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
                  {t("telemetry.criticalDrawdown")}
                </span>
              ) : isModerateGw ? (
                <span className="text-amber-500 dark:text-amber-400 flex items-center gap-1 font-semibold">
                  <TrendingDown className="w-3 h-3" />
                  {t("telemetry.moderateOverdraft")}
                </span>
              ) : isPositiveGw ? (
                <span className="text-emerald-500 flex items-center gap-1 font-semibold">
                  <TrendingUp className="w-3 h-3" />
                  {t("telemetry.netRecharge")}
                </span>
              ) : (
                <span className="text-muted">{t("telemetry.equilibrium")}</span>
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
              <span className="text-[8px] px-1 rounded bg-foreground/10 text-muted font-mono uppercase tracking-wider">
                {t("badge.contextOnly")}
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
              <span className="text-[11px] font-mono text-muted">{t("unit.mmYr")}</span>
            </div>

            <p className="text-[10px] text-muted truncate font-mono">
              {t("telemetry.rainLabel")} {Math.round(climate.annual_precip_mm)} · ET₀{" "}
              {climate.annual_et0_mm != null ? `${Math.round(climate.annual_et0_mm)} mm` : "—"}
            </p>
          </div>

          <ProgressRing
            value={meanSmap ?? 0}
            max={100}
            label={`${t("water.smap")} (${t("badge.contextOnly")})`}
            size="2.9rem"
            thickness="4px"
            color="var(--accent-water)"
          >
            <span className="text-[9px] font-mono font-bold text-foreground">
              {meanSmap != null ? `${meanSmap}%` : "—"}
            </span>
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
              <span className="text-[11px] font-mono text-muted">{t("unit.gkg")}</span>
            </div>

            <p className="text-[10px] text-muted capitalize truncate font-mono">
              {soil.texture_class ?? "Loam"} · pH {soil.ph ? soil.ph.toFixed(1) : "—"}
            </p>
          </div>

          <ProgressRing
            value={socScore}
            max={100}
            label={t("telemetry.soc")}
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
              <span className="truncate">{t("telemetry.ndviVerified")}</span>
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
              {hasFire === true ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-mono font-bold bg-rose-500/20 text-rose-500 dark:text-rose-300 border border-rose-500/40">
                  <Flame className="w-3.5 h-3.5 text-rose-500" />
                  <span>{t("telemetry.thermalAnomaly")}</span>
                </span>
              ) : hasFire === false ? (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-mono font-bold bg-emerald-500/20 text-emerald-600 dark:text-emerald-300 border border-emerald-500/40">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                  <span>{t("telemetry.clearSwath")}</span>
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-mono font-bold bg-amber-500/15 text-amber-600 dark:text-amber-300 border border-amber-500/40">
                  <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                  <span>{t("telemetry.firmsUnverified")}</span>
                </span>
              )}
            </div>
            <p className="text-[10px] text-muted mt-1.5 truncate font-mono">
              {t("telemetry.rusleErosion")}:{" "}
              <strong className="uppercase text-foreground">
                {hazards.erosion_risk_class ?? "Low"}
              </strong>
            </p>
          </div>
        </Link>
      </div>

      {tactical_advisory && (
        <div className="border-t border-line bg-surface/40 px-4 py-3 space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-[10px] font-mono">
              <Thermometer className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
              <span className="uppercase tracking-wider font-bold text-foreground/85">
                {t("telemetry.tacticalTitle")}
              </span>
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/35 text-emerald-700 dark:text-emerald-300 font-bold text-[9px]">
                {tactical_advisory.provenance?.[0]?.mode === "observed"
                  ? t("telemetry.meteomaticsBadge")
                  : t("telemetry.regionalBadge")}
              </span>
              <button
                type="button"
                onClick={handleRefreshForecast}
                disabled={refreshing}
                title={t("telemetry.refreshForecast")}
                aria-label={t("telemetry.refreshForecast")}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-background/70 border border-line text-muted hover:text-foreground transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-3 h-3 ${refreshing ? "animate-spin" : ""}`} />
                <span className="hidden sm:inline text-[9px]">{t("telemetry.refreshForecast")}</span>
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-3 text-[11px] font-mono">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-background/70 border border-line text-foreground">
                <Thermometer className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                <span className="text-muted">{t("telemetry.seedbedTemp")}:</span>
                <strong>
                  {tactical_advisory.seedbed_temp_5cm_c != null
                    ? `${tactical_advisory.seedbed_temp_5cm_c.toFixed(1)}°C`
                    : "—"}
                </strong>
                <span
                  className={
                    tactical_advisory.sowing_ready
                      ? "text-emerald-600 dark:text-emerald-400 font-semibold"
                      : "text-amber-600 dark:text-amber-400 font-semibold"
                  }
                >
                  ·{" "}
                  {tactical_advisory.sowing_status_code === "optimal"
                    ? t("telemetry.sowingReady")
                    : tactical_advisory.sowing_status_code === "too_cold"
                    ? t("telemetry.sowingHoldCold")
                    : tactical_advisory.sowing_status_code === "too_hot"
                    ? t("telemetry.sowingHoldHot")
                    : tactical_advisory.sowing_status_code === "too_dry"
                    ? t("telemetry.sowingHoldDry")
                    : t("telemetry.sowingHoldWet")}
                </span>
              </span>

              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-background/70 border border-line text-foreground">
                <Gauge className="w-3.5 h-3.5 text-sky-500 shrink-0" />
                <span className="text-muted">{t("telemetry.soilDeficit")}:</span>
                <strong>
                  {tactical_advisory.soil_moisture_deficit_mm != null
                    ? `${tactical_advisory.soil_moisture_deficit_mm.toFixed(0)} mm`
                    : "—"}
                </strong>
                <span className="text-sky-600 dark:text-sky-400 font-semibold">
                  ·{" "}
                  {tactical_advisory.irrigation_action === "hold_rain_ahead"
                    ? t("telemetry.irrigationHold")
                    : tactical_advisory.irrigation_action === "irrigate_soon"
                    ? t("telemetry.irrigationPump")
                    : t("telemetry.irrigationAdequate")}
                </span>
                <span className="text-muted hidden md:inline">
                  ({t("telemetry.next7dRainEt0")
                    .replace("{rain}", String(Math.round(tactical_advisory.next_7d_precip_mm)))
                    .replace("{et0}", String(Math.round(tactical_advisory.next_7d_et0_mm)))})
                </span>
              </span>

              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-[11px] font-semibold ${
                  tactical_advisory.urea_spray_safe
                    ? "bg-emerald-500/15 border-emerald-500/35 text-emerald-700 dark:text-emerald-300"
                    : "bg-rose-500/15 border-rose-500/35 text-rose-600 dark:text-rose-300"
                }`}
              >
                <SprayCan className="w-3.5 h-3.5 shrink-0" />
                <span>
                  {tactical_advisory.urea_spray_safe ? t("telemetry.ureaSafe") : t("telemetry.ureaHold")}
                </span>
              </span>
              {tempMin7d != null && tempMax7d != null && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-line bg-background/70 text-[11px] font-mono text-foreground/90">
                  <Thermometer className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                  <span>
                    {t("telemetry.tempRange7d")}:{" "}
                    <strong>
                      {tempMin7d.toFixed(0)}–{tempMax7d.toFixed(0)}°C
                    </strong>
                  </span>
                </span>
              )}
              {maxWind3d != null && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-line bg-background/70 text-[11px] font-mono text-foreground/90">
                  <Wind className="w-3.5 h-3.5 text-cyan-500 shrink-0" />
                  <span>
                    {t("telemetry.wind3dMax")}:{" "}
                    <strong>{maxWind3d.toFixed(1)} m/s</strong>
                  </span>
                </span>
              )}
              {tactical_advisory.fire_weather_index != null && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-amber-500/35 bg-amber-500/10 text-[11px] font-mono text-amber-700 dark:text-amber-300">
                  <Flame className="w-3.5 h-3.5 shrink-0" />
                  <span>
                    {t("telemetry.fireWeather")}:{" "}
                    <strong>{tactical_advisory.fire_weather_index.toFixed(1)}</strong>
                  </span>
                  <span className="text-[9px] uppercase px-1 py-0.5 rounded bg-background/60 border border-line text-muted">
                    {t("badge.contextOnly")}
                  </span>
                </span>
              )}
            </div>
          </div>

          {tactical_advisory.forecast_days && tactical_advisory.forecast_days.length > 0 && (
            <div className="space-y-1.5 pt-2 border-t border-line/60">
              <p className="text-[10px] font-mono uppercase tracking-wider text-muted font-semibold">
                {t("telemetry.outlook7d")}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
                {tactical_advisory.forecast_days.slice(0, 7).map((day) => (
                  <div
                    key={day.date}
                    className="px-2.5 py-2 rounded-lg bg-background/70 border border-line text-[10px] font-mono flex flex-col gap-0.5"
                  >
                    <div className="flex items-center justify-between text-muted">
                      <span className="font-bold text-foreground">{day.date.slice(5)}</span>
                      <span className="text-sky-600 dark:text-sky-400 font-semibold">
                        {day.precip_mm.toFixed(1)}mm
                        {day.prob_precip_pct != null ? ` (${Math.round(day.prob_precip_pct)}%)` : ""}
                      </span>
                    </div>
                    <div className="text-foreground font-semibold">
                      {Math.round(day.tmax_c)}° / {Math.round(day.tmin_c)}°C
                    </div>
                    <div className="flex items-center justify-between text-[9px] text-muted">
                      <span>ET₀ {day.et0_mm.toFixed(1)}</span>
                      <span>
                        5cm {day.soil_temp_5cm_c != null ? `${day.soil_temp_5cm_c.toFixed(0)}°` : "—"}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <ProvenanceChip provenance={tactical_advisory.provenance} />
        </div>
      )}
    </div>
  );
}
