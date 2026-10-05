"use client";

import type { FieldProfile } from "@/types/api";
import { useI18n } from "@/i18n";
import { ProvenanceChip } from "./ProvenanceChip";

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function ReportCard({ profile }: { profile: FieldProfile }) {
  const { t } = useI18n();
  const { field, climate, soil, water, hazards, agro_climatic_notes } = profile;

  const maxMonthlyRain = Math.max(...(climate?.monthly_precip_mm ?? [100]), 10);

  return (
    <div className="space-y-6">
      {/* Field Header */}
      <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                Field Profile
              </span>
              <span className="text-xs text-zinc-500 font-mono">
                {field.lat.toFixed(4)}°N, {field.lon.toFixed(4)}°E
              </span>
            </div>
            <h2 className="text-2xl font-bold mt-1 text-zinc-900 dark:text-zinc-50">
              {field.name ?? "Selected Location"}
            </h2>
          </div>
        </div>

        {/* Insights / Agro-climatic Notes */}
        {agro_climatic_notes && agro_climatic_notes.length > 0 && (
          <div className="mt-4 p-4 rounded-xl bg-amber-50/70 dark:bg-amber-950/30 border border-amber-200/80 dark:border-amber-800/50">
            <h4 className="text-xs font-bold uppercase tracking-wider text-amber-900 dark:text-amber-200 mb-2 flex items-center gap-1.5">
              <span>💡</span>
              <span>{t("section.insights")}</span>
            </h4>
            <ul className="space-y-1.5 text-xs text-amber-950 dark:text-amber-300/90 list-disc list-inside">
              {agro_climatic_notes.map((note, idx) => (
                <li key={idx} className="leading-relaxed">
                  {note}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Grid: 4 Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Climate Card */}
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-5 border border-zinc-200 dark:border-zinc-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                <span>🌦️</span> {t("section.climate")}
              </h3>
              <span className="text-[11px] font-mono text-zinc-400">
                {climate.baseline_period} vs {climate.recent_period}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50">
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{t("climate.rain")}</p>
                <p className="text-lg font-bold text-zinc-900 dark:text-zinc-50 mt-0.5">
                  {climate.recent_annual_precip_mm.toFixed(0)}{" "}
                  <span className="text-xs font-normal text-zinc-500">{t("unit.mmYr")}</span>
                </p>
                <p className="text-[10px] text-zinc-400 mt-1">
                  Change: {climate.precip_change_pct > 0 ? "+" : ""}
                  {climate.precip_change_pct.toFixed(0)}%
                </p>
              </div>

              <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50">
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{t("climate.heatDays")}</p>
                <p className="text-lg font-bold text-zinc-900 dark:text-zinc-50 mt-0.5">
                  {climate.recent_heat_days_per_year.toFixed(0)}{" "}
                  <span className="text-xs font-normal text-zinc-500">{t("unit.days")}</span>
                </p>
                <p className="text-[10px] text-zinc-400 mt-1">
                  Baseline: {climate.heat_days_per_year.toFixed(0)} d/yr
                </p>
              </div>

              <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50">
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{t("climate.et0")}</p>
                <p className="text-lg font-bold text-zinc-900 dark:text-zinc-50 mt-0.5">
                  {climate.annual_et0_mm ? climate.annual_et0_mm.toFixed(0) : "—"}{" "}
                  <span className="text-xs font-normal text-zinc-500">{t("unit.mmYr")}</span>
                </p>
              </div>

              <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50">
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{t("climate.drySpell")}</p>
                <p className="text-lg font-bold text-zinc-900 dark:text-zinc-50 mt-0.5">
                  {climate.longest_dry_spell_days_mean.toFixed(0)}{" "}
                  <span className="text-xs font-normal text-zinc-500">{t("unit.days")}</span>
                </p>
              </div>
            </div>
          </div>

          <ProvenanceChip provenance={climate.provenance} />
        </div>

        {/* Soil Card */}
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-5 border border-zinc-200 dark:border-zinc-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                <span>🌱</span> {t("section.soil")}
              </h3>
              {soil.texture_class && (
                <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 capitalize">
                  {soil.texture_class}
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50">
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{t("soil.soc")}</p>
                <p className="text-lg font-bold text-zinc-900 dark:text-zinc-50 mt-0.5">
                  {soil.soc_g_per_kg ? soil.soc_g_per_kg.toFixed(1) : "—"}{" "}
                  <span className="text-xs font-normal text-zinc-500">{t("unit.gkg")}</span>
                </p>
                <p className="text-[10px] text-zinc-400 mt-1">Topsoil (0–30 cm)</p>
              </div>

              <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50">
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{t("soil.ph")}</p>
                <p className="text-lg font-bold text-zinc-900 dark:text-zinc-50 mt-0.5">
                  {soil.ph ? soil.ph.toFixed(1) : "—"}
                </p>
                <p className="text-[10px] text-zinc-400 mt-1">
                  {soil.ph && soil.ph > 7.5 ? "Alkaline" : soil.ph && soil.ph < 6 ? "Acidic" : "Neutral"}
                </p>
              </div>

              <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50">
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">Sand / Silt / Clay</p>
                <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 mt-1">
                  {soil.sand_pct?.toFixed(0)}% / {soil.silt_pct?.toFixed(0)}% / {soil.clay_pct?.toFixed(0)}%
                </p>
              </div>

              <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50">
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{t("soil.fcwp")}</p>
                <p className="text-xs font-semibold text-zinc-900 dark:text-zinc-100 mt-1">
                  {soil.field_capacity_vol ? `${(soil.field_capacity_vol * 100).toFixed(0)}%` : "—"} /{" "}
                  {soil.wilting_point_vol ? `${(soil.wilting_point_vol * 100).toFixed(0)}%` : "—"}
                </p>
              </div>
            </div>
          </div>

          <ProvenanceChip provenance={soil.provenance} />
        </div>

        {/* Water & Balance Card */}
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-5 border border-zinc-200 dark:border-zinc-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                <span>💧</span> {t("section.water")}
              </h3>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50 col-span-2">
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{t("water.balance")}</p>
                <p
                  className={`text-lg font-bold mt-0.5 ${
                    water.climatic_water_balance_mm && water.climatic_water_balance_mm < 0
                      ? "text-rose-600 dark:text-rose-400"
                      : "text-emerald-600 dark:text-emerald-400"
                  }`}
                >
                  {water.climatic_water_balance_mm ? `${water.climatic_water_balance_mm.toFixed(0)} mm/yr` : "—"}
                </p>
                <p className="text-[10px] text-zinc-400 mt-1">
                  {water.climatic_water_balance_mm && water.climatic_water_balance_mm < -400
                    ? "Severe deficit: highly dependent on irrigation tube-wells"
                    : "Moderate or positive moisture balance"}
                </p>
              </div>
            </div>
          </div>

          <ProvenanceChip provenance={water.provenance} />
        </div>

        {/* Hazards & Risks Card */}
        <div className="bg-white dark:bg-zinc-900 rounded-2xl p-5 border border-zinc-200 dark:border-zinc-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                <span>⚠️</span> {t("section.hazards")}
              </h3>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4">
              <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50">
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{t("hazards.erosion")}</p>
                <p className="text-sm font-bold text-zinc-900 dark:text-zinc-50 mt-1 uppercase">
                  {hazards.erosion_risk_class ?? "Low"}
                </p>
                <p className="text-[10px] text-zinc-400 mt-1">RUSLE soil loss</p>
              </div>

              <div className="p-3 rounded-xl bg-zinc-50 dark:bg-zinc-800/50">
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">{t("hazards.drought")}</p>
                <p className="text-sm font-bold text-zinc-900 dark:text-zinc-50 mt-1">
                  {hazards.drought_frequency ? `${(hazards.drought_frequency * 100).toFixed(0)}%` : "—"}
                </p>
                <p className="text-[10px] text-zinc-400 mt-1">Historical frequency</p>
              </div>
            </div>
          </div>

          <div className="text-[10px] text-zinc-400 mt-3">
            Erosion: RUSLE (A = R·K·LS·C·P) screen
          </div>
        </div>
      </div>

      {/* Monthly Rainfall Chart */}
      <div className="bg-white dark:bg-zinc-900 rounded-2xl p-5 border border-zinc-200 dark:border-zinc-800 shadow-sm">
        <h3 className="font-semibold text-sm text-zinc-900 dark:text-zinc-100 mb-4 flex items-center gap-2">
          <span>📊</span> {t("climate.monthlyRain")}
        </h3>
        <div className="grid grid-cols-12 gap-1.5 items-end h-32 pt-4">
          {climate.monthly_precip_mm.map((val, idx) => {
            const heightPct = Math.round((val / maxMonthlyRain) * 100);
            const isMonsoon = climate.wettest_months.includes(idx + 1);
            return (
              <div key={idx} className="flex flex-col items-center gap-1 h-full justify-end group">
                <span className="text-[9px] font-mono text-zinc-400 group-hover:text-blue-500">
                  {val.toFixed(0)}
                </span>
                <div
                  style={{ height: `${Math.max(heightPct, 4)}%` }}
                  className={`w-full rounded-t transition-all ${
                    isMonsoon
                      ? "bg-blue-600 dark:bg-blue-500"
                      : "bg-blue-200 dark:bg-blue-900/60"
                  } group-hover:brightness-110`}
                  title={`${MONTH_NAMES[idx]}: ${val.toFixed(1)} mm`}
                />
                <span className={`text-[10px] font-medium ${isMonsoon ? "text-blue-600 font-bold" : "text-zinc-400"}`}>
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
