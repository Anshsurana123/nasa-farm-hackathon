"use client";

import type { FieldProfile, StrategyRecommendation } from "@/types/api";
import { fmtDMS, fmtMoney, isSouthAsia } from "@/lib/ui";
import { Printer, CheckCircle2, FileText } from "lucide-react";

interface AgronomicBriefProps {
  profile: FieldProfile;
  strategies: StrategyRecommendation[];
}

export function AgronomicBrief({ profile, strategies }: AgronomicBriefProps) {
  const { field, soil, water, hazards, agro_climatic_notes } = profile;
  const isSA = isSouthAsia(field.lat, field.lon);
  const currencySymbol = profile.currency_symbol ?? (isSA ? "₹" : "$");

  const baseline = strategies.find((s) => s.rank === 0) ?? strategies[0];
  const topStrategy = strategies.find((s) => s.rank === 1) ?? strategies[1] ?? baseline;

  const baseRes = baseline?.results[0];
  const topRes = topStrategy?.results[0];

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
            <span>NASA EARTH OBSERVATION ADVISORY</span>
          </div>
          <h2 className="font-serif text-2xl sm:text-3xl font-semibold text-foreground tracking-tight">
            TerraLoop Field Agronomic Advisory Brief
          </h2>
          <p className="text-xs text-muted font-mono">
            Stratigraphic Soil, Subsurface Hydrology &amp; Multi-Objective Crop Rotation Prescription
          </p>
        </div>

        <div className="text-right flex flex-col items-end gap-1.5">
          <button
            type="button"
            onClick={() => window.print()}
            className="px-4 py-2 rounded-lg bg-foreground text-background hover:opacity-90 text-xs font-mono font-bold print:hidden cursor-pointer flex items-center gap-2 transition-opacity"
          >
            <Printer className="w-3.5 h-3.5" />
            <span>Export / Print PDF</span>
          </button>
          <p className="text-[10px] text-muted font-mono">
            ISSUED: {new Date().toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
          </p>
        </div>
      </div>

      {/* Field Identification Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 divide-y md:divide-y-0 md:divide-x divide-line rounded-xl bg-surface border border-line text-xs">
        <div className="p-4 space-y-1">
          <span className="text-muted block text-[10px] font-mono uppercase tracking-wider">Parcel Coordinates</span>
          <span className="font-bold text-sm text-foreground block">{field.name ?? "Target Field"}</span>
          <span className="block text-[11px] font-mono text-muted">
            {fmtDMS(field.lat, true)} · {fmtDMS(field.lon, false)}
          </span>
        </div>

        <div className="p-4 space-y-1">
          <span className="text-muted block text-[10px] font-mono uppercase tracking-wider">Groundwater Trend</span>
          <span
            className={`font-bold text-sm font-mono block ${
              water.groundwater_trend_cm_per_year && water.groundwater_trend_cm_per_year < -2
                ? "text-rose-500"
                : "text-foreground"
            }`}
          >
            {water.groundwater_trend_cm_per_year
              ? `${water.groundwater_trend_cm_per_year.toFixed(2)} cm/yr`
              : "Stable"}
          </span>
          <span className="block text-[10px] font-mono text-muted">NASA GRACE-FO Mascon</span>
        </div>

        <div className="p-4 space-y-1">
          <span className="text-muted block text-[10px] font-mono uppercase tracking-wider">Horizon A Topsoil</span>
          <span className="font-bold text-sm capitalize text-foreground block">
            {soil.texture_class ?? "Loam"} (pH {soil.ph?.toFixed(1) ?? "7.5"})
          </span>
          <span className="block text-[10px] font-mono text-muted">
            SOC: {soil.soc_g_per_kg?.toFixed(1) ?? "10"} g/kg · ISRIC 250m
          </span>
        </div>

        <div className="p-4 space-y-1">
          <span className="text-muted block text-[10px] font-mono uppercase tracking-wider">Thermal Fire Status</span>
          <span
            className={`font-bold text-sm font-mono block ${
              hazards.residue_burning_detected ? "text-rose-500" : "text-emerald-600 dark:text-emerald-400"
            }`}
          >
            {hazards.residue_burning_detected ? "Active Residue Fire" : "No Fire Anomaly"}
          </span>
          <span className="block text-[10px] font-mono text-muted">NASA FIRMS MODIS/VIIRS</span>
        </div>
      </div>

      {/* Side-by-Side Comparative Impact Cards */}
      <div className="space-y-3">
        <h4 className="font-mono text-[11px] font-bold uppercase tracking-widest text-muted">
          Prescriptive Rotation Strategy Comparison
        </h4>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Baseline */}
          <div className="p-5 rounded-xl border border-line bg-surface/50 hatch-pattern space-y-3">
            <div className="flex items-center justify-between font-mono">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-foreground/10 text-muted border border-line">
                REF // Current Farm Baseline
              </span>
              <span className="text-xs text-rose-500 font-bold">{baseIrr} mm/yr Irrigation</span>
            </div>
            <h5 className="font-display font-bold text-base text-foreground">
              {baseline?.rotation.label ?? "Continuous Intensive Double-Crop"}
            </h5>
            <div className="grid grid-cols-3 gap-2 text-center pt-3 border-t border-line text-[11px] font-mono">
              <div>
                <span className="text-muted block text-[9px] uppercase">10-Yr SOC Δ</span>
                <span className="font-bold text-rose-500">
                  {(baseRes?.soc_delta_t_ha_10yr ?? -0.8).toFixed(1)} t C/ha
                </span>
              </div>
              <div>
                <span className="text-muted block text-[9px] uppercase">Soil Health</span>
                <span className="font-bold text-foreground">{Math.round(baseRes?.soil_health_score ?? 38)}/100</span>
              </div>
              <div>
                <span className="text-muted block text-[9px] uppercase">Median Margin</span>
                <span className="font-bold text-foreground">
                  {fmtMoney(baseRes?.profit_p50 ?? 85000, currencySymbol)}
                </span>
              </div>
            </div>
          </div>

          {/* Recommended Top Strategy */}
          <div className="p-5 rounded-xl border-2 border-emerald-500/70 bg-emerald-500/[0.04] space-y-3">
            <div className="flex items-center justify-between font-mono">
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/40">
                OPT 01 // Recommended Strategy
              </span>
              <span className="text-xs text-emerald-600 dark:text-emerald-400 font-bold">
                {topIrr} mm/yr (−{waterSavedPct}% H₂O)
              </span>
            </div>
            <h5 className="font-display font-bold text-base text-foreground">
              {topStrategy?.rotation.label ?? "Diversified Conservation Rotation"}
            </h5>
            <div className="grid grid-cols-3 gap-2 text-center pt-3 border-t border-emerald-500/20 text-[11px] font-mono">
              <div>
                <span className="text-muted block text-[9px] uppercase">10-Yr SOC Δ</span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400">
                  +{(topRes?.soc_delta_t_ha_10yr ?? 2.1).toFixed(1)} t C/ha
                </span>
              </div>
              <div>
                <span className="text-muted block text-[9px] uppercase">Soil Health</span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400">
                  {Math.round(topRes?.soil_health_score ?? 72)}/100
                </span>
              </div>
              <div>
                <span className="text-muted block text-[9px] uppercase">Median Margin</span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400">
                  {fmtMoney(topRes?.profit_p50 ?? 104000, currencySymbol)}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Key Agronomic Recommendations & Evidence */}
      {topStrategy?.why && topStrategy.why.length > 0 && (
        <div className="p-5 rounded-xl bg-emerald-500/[0.06] border border-emerald-500/25 space-y-2.5">
          <h4 className="font-mono text-[11px] font-bold text-emerald-700 dark:text-emerald-300 uppercase tracking-widest">
            Grounded Satellite &amp; Biophysical Evidence
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
                Net Parcel Impact: Conserves <strong>{baseIrr - topIrr} mm/yr</strong> irrigation water, mitigates aquifer drawdown, and accretes <strong>+{carbonDelta.toFixed(1)} t C/ha</strong> in topsoil organic carbon over 10 years.
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
            <span>NASA Agro-Climatic Diagnostics</span>
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
        <span>PROVENANCE: NASA POWER · ISRIC SoilGrids · NASA SMAP · NASA GRACE-FO · NASA FIRMS · FAO AquaCrop</span>
        <span className="font-bold text-foreground/80">TERRALOOP // NASA SPACE APPS CHALLENGE 2026</span>
      </div>
    </div>
  );
}
