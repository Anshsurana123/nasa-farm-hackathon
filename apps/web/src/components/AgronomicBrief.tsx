"use client";

import type { FieldProfile, StrategyRecommendation } from "@/types/api";
import { useField } from "@/context/FieldContext";
import { useI18n } from "@/i18n";
import { fmtAreaMoney, fmtAreaUnit, fmtDMS, fmtSigned, isSouthAsia, scaleByUnit } from "@/lib/ui";
import { Printer, CheckCircle2, FileText, Award, ShieldCheck } from "lucide-react";

interface AgronomicBriefProps {
  profile: FieldProfile;
  strategies: StrategyRecommendation[];
}

export function AgronomicBrief({ profile, strategies }: AgronomicBriefProps) {
  const { t } = useI18n();
  const { selectedRank, unitSystem } = useField();
  const { field, soil, water, hazards, agro_climatic_notes } = profile;
  const isSA = isSouthAsia(field.lat, field.lon);
  const currencySymbol = profile.currency_symbol ?? (isSA ? "₹" : "$");
  const gwTrend = profile?.water?.groundwater_trend_cm_per_year ?? 0;
  const graceMult = gwTrend < -1.0 ? Math.min(1.5, 1.0 + 0.1 * (Math.abs(gwTrend) - 1.0)) : 1.0;

  const baseline = strategies.find((s) => s.rank === 0) ?? strategies[0];
  const topStrategy =
    strategies.find((s) => s.rank === selectedRank && s.rank > 0) ??
    strategies.find((s) => s.rank === 1) ??
    strategies[1] ??
    baseline;

  const baseRes = baseline?.results[0];
  const topRes = topStrategy?.results[0];
  const pm = topStrategy?.practical_metrics;

  const baseIrr = baseRes?.irrigation_mm?.length
    ? Math.round(baseRes.irrigation_mm.reduce((a, b) => a + b, 0) / baseRes.irrigation_mm.length)
    : 1400;
  const topIrr = topRes?.irrigation_mm?.length
    ? Math.round(topRes.irrigation_mm.reduce((a, b) => a + b, 0) / topRes.irrigation_mm.length)
    : 950;

  const waterSavedPct = baseIrr > 0 ? Math.round(((baseIrr - topIrr) / baseIrr) * 100) : 0;
  const carbonDelta = (topRes?.soc_delta_t_ha_10yr ?? 2.1) - (baseRes?.soc_delta_t_ha_10yr ?? -0.8);

  return (
    <div className="glass rounded-2xl p-6 sm:p-10 border border-line shadow-xl space-y-7 font-sans reticle-frame print:p-0 print:border-none print:shadow-none print:bg-white print:text-black">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between border-b-2 border-foreground/20 pb-5 gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-muted">
            <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 font-bold">
              DOC // FIELD-BRIEF-2026
            </span>
            <span>{t("brief.badge")}</span>
            { profile.agro_zone && (
              <span className="px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-600 dark:text-cyan-300 border border-cyan-500/30 font-bold">
                {profile.agro_zone}
              </span>
            )}
            { profile.served_from === "demo_snapshot" && (
              <span className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-300 border border-amber-500/30 font-bold">
                {t("badge.demoSnapshot")}
                {profile.snapshot_date ? ` (${profile.snapshot_date})` : ""}
              </span>
            )}
            { topStrategy?.economics_basis === "punjab_proxy" && (
              <span className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-300 border border-amber-500/30 font-bold" title={t("badge.punjabProxyTooltip")}>
                {t("badge.punjabProxyEconomics")}
              </span>
            )}
          </div>
          <h2 className="font-serif text-2xl sm:text-3xl font-semibold text-foreground tracking-tight">
            {t("brief.title")}
          </h2>
          <p className="text-xs text-muted font-mono">
            {t("brief.subtitle")} ({fmtAreaUnit(unitSystem)})
          </p>
        </div>

        <div className="text-right flex flex-col items-end gap-1.5">
          <button
            type="button"
            onClick={() => window.print()}
            className="px-4 py-2 rounded-lg bg-foreground text-background hover:opacity-90 text-xs font-mono font-bold print:hidden cursor-pointer flex items-center gap-2 transition-opacity"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>{t("brief.exportPdf")}</span>
          </button>
          <p className="text-[10px] text-muted font-mono">
            {t("brief.issued")}:{" "}
            {new Date().toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
          </p>
        </div>
      </div>

      {/* Field Identification Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 divide-y md:divide-y-0 md:divide-x divide-line rounded-xl bg-surface border border-line text-xs">
        <div className="p-4 space-y-1">
          <span className="text-muted block text-[10px] font-mono uppercase tracking-wider">{t("brief.parcelCoords")}</span>
          <span className="font-bold text-sm text-foreground block">{field.name ?? t("brief.targetField")}</span>
          <span className="block text-[11px] font-mono text-muted">
            {fmtDMS(field.lat, true)} · {fmtDMS(field.lon, false)}
          </span>
        </div>

        <div className="p-4 space-y-1">
          <span className="text-muted block text-[10px] font-mono uppercase tracking-wider">{t("brief.twsTrend")}</span>
          <span
            className={`font-bold text-sm font-mono block ${
              water.groundwater_trend_cm_per_year != null && water.groundwater_trend_cm_per_year < -2
                ? "text-rose-500"
                : "text-foreground"
            }`}
          >
            {water.groundwater_trend_cm_per_year != null
              ? `${water.groundwater_trend_cm_per_year.toFixed(2)} cm/yr`
              : "—"}
          </span>
          <span className="block text-[10px] font-mono text-muted">{t("sensor.grace")}</span>
          {graceMult > 1.0 && (
            <div className="pt-1">
              <span className="inline-block text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30 font-semibold leading-tight">
                {t("badge.graceUrgencyActive", {
                  mult: graceMult.toFixed(2),
                  trend: Math.abs(gwTrend).toFixed(2),
                })}
              </span>
            </div>
          )}
        </div>

        <div className="p-4 space-y-1">
          <span className="text-muted block text-[10px] font-mono uppercase tracking-wider">{t("brief.topsoil")}</span>
          <span className="font-bold text-sm capitalize text-foreground block">
            {soil.texture_class ?? "Loam"} (pH {soil.ph?.toFixed(1) ?? "7.5"})
          </span>
          <span className="block text-[10px] font-mono text-muted">
            SOC: {soil.soc_g_per_kg !== undefined && soil.soc_g_per_kg !== null ? soil.soc_g_per_kg.toFixed(1) : "—"} g/kg ·{" "}
            {soil.source === "farmer_test" ? t("brief.govtShcLab") : t("brief.isric250m")}
          </span>
        </div>

        <div className="p-4 space-y-1">
          <span className="text-muted block text-[10px] font-mono uppercase tracking-wider">{t("brief.fireStatus")}</span>
          <span
            className={`font-bold text-sm font-mono block ${
              hazards.residue_burning_detected === true
                ? "text-rose-500"
                : hazards.residue_burning_detected === false
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-muted"
            }`}
          >
            {hazards.residue_burning_detected === true
              ? t("brief.activeFire")
              : hazards.residue_burning_detected === false
              ? t("brief.noFire")
              : t("telemetry.firmsUnverified")}
          </span>
          <span className="block text-[10px] font-mono text-muted">{t("sensor.firms")}</span>
        </div>
      </div>

      {/* Side-by-Side Comparative Impact Cards */}
      <div className="space-y-3">
        <h4 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted">
          {t("brief.strategyComp")} ({fmtAreaUnit(unitSystem)})
        </h4>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Baseline */}
          <div className="p-5 rounded-xl border border-line bg-surface/50 hatch-pattern space-y-3">
            <div className="flex items-center justify-between font-mono">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-foreground/10 text-muted border border-line">
                REF // {t("strategy.baseline")}
              </span>
              <span className="text-xs text-rose-500 font-bold">
                {baseIrr} {t("brief.irrigationYr")}
              </span>
            </div>
            <h5 className="font-display font-bold text-base text-foreground">
              {baseline?.rotation.label ?? t("brief.defaultBaselineLabel")}
            </h5>
            <div className="grid grid-cols-3 gap-2 text-center pt-3 border-t border-line text-[11px] font-mono">
              <div>
                <span className="text-muted block text-[9px] uppercase">{t("brief.soc10yr")}</span>
                <span className="font-bold text-rose-500">
                  {fmtSigned(baseRes?.soc_delta_t_ha_10yr ?? -0.8, 1, " t C/ha")}
                </span>
              </div>
              <div>
                <span className="text-muted block text-[9px] uppercase">{t("brief.soilHealthLabel")}</span>
                <span className="font-bold text-foreground">{Math.round(baseRes?.soil_health_score ?? 38)}/100</span>
              </div>
              <div>
                <span className="text-muted block text-[9px] uppercase">
                  {t("brief.medianMargin")} ({fmtAreaUnit(unitSystem)})
                </span>
                <span className="font-bold text-foreground">
                  {fmtAreaMoney(baseRes?.profit_p50 ?? 85000, currencySymbol, unitSystem)}
                </span>
              </div>
            </div>
          </div>

          {/* Recommended Top Strategy */}
          <div className="p-5 rounded-xl border-2 border-emerald-500/70 bg-emerald-500/[0.04] space-y-3">
            <div className="flex items-center justify-between font-mono">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40">
                {`OPT 0${topStrategy?.rank || 1} // ${t("brief.recommended")}`}
              </span>
              <span className="text-xs text-emerald-600 dark:text-emerald-400 font-bold">
                {topIrr} mm/yr (−{waterSavedPct}% H₂O)
              </span>
            </div>
            <h5 className="font-display font-bold text-base text-foreground">
              {topStrategy?.rotation.label ?? t("brief.defaultRecLabel")}
            </h5>
            <div className="grid grid-cols-3 gap-2 text-center pt-3 border-t border-emerald-500/20 text-[11px] font-mono">
              <div>
                <span className="text-muted block text-[9px] uppercase">{t("brief.soc10yr")}</span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400">
                  {fmtSigned(topRes?.soc_delta_t_ha_10yr ?? 2.1, 1, " t C/ha")}
                </span>
              </div>
              <div>
                <span className="text-muted block text-[9px] uppercase">{t("brief.soilHealthLabel")}</span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400">
                  {Math.round(topRes?.soil_health_score ?? 72)}/100
                </span>
              </div>
              <div>
                <span className="text-muted block text-[9px] uppercase">
                  {t("brief.medianMargin")} ({fmtAreaUnit(unitSystem)})
                </span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400">
                  {fmtAreaMoney(topRes?.profit_p50 ?? 104000, currencySymbol, unitSystem)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* KVK Practical Field Action & Government Subsidy Card */}
      {(pm || topStrategy?.narrative_summary) && (
        <div className="p-5 rounded-xl bg-surface-2/80 border border-cyan-500/30 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-mono text-[11px] font-bold text-cyan-600 dark:text-cyan-300 uppercase tracking-widest flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-cyan-400" />
              <span>{t("brief.kvkTitle")}</span>
            </h4>
            {pm && (
              <span className="px-2.5 py-0.5 rounded-md bg-emerald-500/15 text-emerald-600 dark:text-emerald-300 border border-emerald-500/30 text-[10px] font-mono font-bold">
                {t("brief.mspProcurement")}: {pm.msp_assurance_level.toUpperCase()}
              </span>
            )}
          </div>

          {topStrategy?.narrative_summary && (
            <p className="text-xs text-foreground/90 leading-relaxed border-l-2 border-cyan-500 pl-3 py-0.5">
              {topStrategy.narrative_summary}
            </p>
          )}

          {pm && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1 text-xs font-mono">
              <div className="p-3 rounded-lg bg-surface border border-line">
                <span className="text-[10px] text-muted block uppercase">{t("brief.turnaroundWindow")}</span>
                <span className="text-sm font-bold text-emerald-500 dark:text-emerald-400">
                  {pm.turnaround_days_kharif_rabi} {t("unit.days")}
                </span>
                <span className="text-[10px] text-muted block font-sans">
                  {pm.turnaround_days_kharif_rabi >= 20 ? t("brief.happySeederWindow") : t("brief.tightWindow")}
                </span>
              </div>

              <div className="p-3 rounded-lg bg-surface border border-line">
                <span className="text-[10px] text-muted block uppercase">{t("brief.irrigationsSaved")}</span>
                <span className="text-sm font-bold text-cyan-500 dark:text-cyan-300">
                  {pm.irrigations_saved_per_yr > 0 ? `−${pm.irrigations_saved_per_yr.toFixed(1)}` : "0"}{" "}
                  {t("brief.irrigationsUnit")}
                </span>
                <span className="text-[10px] text-muted block font-sans">
                  {Math.round(scaleByUnit(pm.pumping_hours_saved_per_ha, unitSystem))} {t("brief.hrsPumpUnit")}
                  {fmtAreaUnit(unitSystem)}
                </span>
              </div>

              <div className="p-3 rounded-lg bg-surface border border-line">
                <span className="text-[10px] text-muted block uppercase">{t("brief.ureaBagsSaved")}</span>
                <span className="text-sm font-bold text-emerald-500 dark:text-emerald-400">
                  {scaleByUnit(pm.urea_bags_saved_per_ha, unitSystem).toFixed(1)} {t("brief.bagsUnit")}
                  {fmtAreaUnit(unitSystem)}
                </span>
                <span className="text-[10px] text-muted block font-sans">
                  {currencySymbol === "₹"
                    ? `${t("brief.savesWord")} ₹${Math.round(scaleByUnit(pm.urea_bags_saved_per_ha, unitSystem) * 266.5)}${fmtAreaUnit(unitSystem)}`
                    : t("brief.bioNSaved")}
                </span>
              </div>

              <div className="p-3 rounded-lg bg-surface border border-line">
                <span className="text-[10px] text-muted block uppercase">{t("brief.labourCost")}</span>
                <span className="text-sm font-bold text-foreground">
                  {fmtAreaMoney(pm.labor_cost_inr_per_ha, currencySymbol, unitSystem)}
                </span>
                <span className="text-[10px] text-muted block font-sans">
                  {t("brief.inputsWord")}: {fmtAreaMoney(pm.input_cost_inr_per_ha, currencySymbol, unitSystem)}
                </span>
              </div>
            </div>
          )}

          {pm?.eligible_schemes && pm.eligible_schemes.length > 0 && (
            <div className="pt-2 border-t border-line/60 flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-amber-500 flex items-center gap-1 font-bold">
                <Award className="w-3.5 h-3.5" /> {t("brief.eligibleSubsidies")}:
              </span>
              {pm.eligible_schemes.map((scheme: string, i: number) => (
                <span
                  key={i}
                  className="px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-200 border border-amber-500/30 text-[11px] font-medium"
                >
                  {scheme}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* What the Model Does NOT Capture (Disclosure Panel) */}
      <div className="p-5 rounded-xl bg-amber-500/[0.07] border border-amber-500/30 space-y-2.5 print:block">
        <h4 className="font-mono text-[11px] font-bold text-amber-700 dark:text-amber-300 uppercase tracking-widest flex items-center gap-1.5">
          <span>⚠️ {t("unmodelled.title")}</span>
        </h4>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-foreground/85">
          <li className="flex items-start gap-1.5">
            <span className="text-amber-500 font-bold">•</span>
            <span>{t("unmodelled.pests")}</span>
          </li>
          <li className="flex items-start gap-1.5">
            <span className="text-amber-500 font-bold">•</span>
            <span>{t("unmodelled.weather")}</span>
          </li>
          <li className="flex items-start gap-1.5">
            <span className="text-amber-500 font-bold">•</span>
            <span>{t("unmodelled.market")}</span>
          </li>
          <li className="flex items-start gap-1.5">
            <span className="text-amber-500 font-bold">•</span>
            <span>{t("unmodelled.labour")}</span>
          </li>
          <li className="flex items-start gap-1.5 sm:col-span-2">
            <span className="text-amber-500 font-bold">•</span>
            <span>{t("unmodelled.water")}</span>
          </li>
        </ul>
        <p className="text-[10px] font-mono text-muted pt-1 border-t border-amber-500/20">
          {t("warning.yieldGapDisclaimer")}
        </p>
      </div>

      {/* Key Agronomic Recommendations & Evidence */}
      {topStrategy?.why && topStrategy.why.length > 0 && (
        <div className="p-5 rounded-xl bg-emerald-500/[0.06] border border-emerald-500/25 space-y-2.5">
          <h4 className="font-mono text-[11px] font-bold text-emerald-700 dark:text-emerald-300 uppercase tracking-widest">
            {t("brief.evidenceTitle")}
          </h4>
          <ul className="space-y-2 text-xs text-foreground/90 leading-relaxed prose-measure">
            {topStrategy.why.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                <span>{reason}</span>
              </li>
            ))}
            <li className="flex items-start gap-2 font-medium">
              <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
              <span>
                {t("brief.netImpact")}: {t("brief.conserves")} <strong>{baseIrr - topIrr} mm/yr</strong> {t("brief.irrWaterMitigates")} <strong>{fmtSigned(carbonDelta, 1, " t C/ha")}</strong> {t("brief.vsBaseline10Yr")}
              </span>
            </li>
          </ul>
        </div>
      )}

      {/* Agro-climatic Diagnostic Notes */}
      {agro_climatic_notes && agro_climatic_notes.length > 0 && (
        <div className="space-y-1.5 text-xs">
          <h4 className="text-[10px] font-mono font-bold text-muted uppercase tracking-widest flex items-center gap-1.5">
            <FileText className="w-3.5 h-3.5 text-muted" />
            <span>{t("brief.diagnosticsTitle")}</span>
          </h4>
          <ul className="space-y-1 text-muted list-disc list-inside leading-relaxed prose-measure">
            {agro_climatic_notes.map((note, idx) => (
              <li key={idx}>{note}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer Provenance */}
      <div className="pt-5 border-t border-line text-[10px] font-mono text-muted flex flex-wrap items-center justify-between gap-2">
        <span>{t("brief.provenanceFooter")}</span>
        <span className="font-bold text-foreground/80">{t("brief.challengeFooter")}</span>
      </div>
    </div>
  );
}
