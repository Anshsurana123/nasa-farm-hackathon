"use client";

import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { ReportCard } from "@/components/ReportCard";
import { FieldMap } from "@/components/FieldMap";
import { useField } from "@/context/FieldContext";
import { ArrowRight, Layers, Satellite } from "lucide-react";

export default function DiagnosticsPage() {
  const { selectedField, goldenFields, profile, strategies, selectLocation } = useField();

  return (
    <AppShell
      pageStep="02"
      pageBadge="NASA POWER · SMAP L4 · GRACE-FO · ISRIC 250m · HLS 30m"
      pageTitle="Deep Field Diagnostics & Satellite Telemetry Atlas"
      pageDescription="Explore 24-year daily agroclimatology, monthly rainfall vs. thermal envelopes, USDA soil particle fractions, Saxton-Rawls hydraulic limits, and satellite-reconstructed crop history."
      headerActions={
        <Link
          href="/rotations"
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-500 hover:opacity-95 text-slate-950 font-mono text-xs font-bold flex items-center gap-2 shadow-md transition-opacity"
        >
          <Layers className="w-4 h-4" />
          <span>Optimize Rotations for This Parcel</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      }
    >
      {profile && (
        <div className="space-y-6">
          {/* Full Interactive Diagnostic Report Card + 3D Stratigraphic Pedon */}
          <ReportCard profile={profile} strategies={strategies} show3DPedon={true} />

          {/* Companion Satellite Swath Context Map */}
          <div className="glass rounded-2xl p-5 border border-line space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Satellite className="w-4 h-4 text-emerald-400" />
                <h3 className="font-display font-bold text-sm uppercase tracking-wider text-foreground">
                  Interactive Satellite Swath &amp; Terrain Reference
                </h3>
              </div>
              <span className="text-xs font-mono text-muted">
                Click any neighboring parcel on the map to compare diagnostics live
              </span>
            </div>

            <FieldMap
              selectedField={selectedField}
              goldenFields={goldenFields}
              onSelect={selectLocation}
            />
          </div>
        </div>
      )}
    </AppShell>
  );
}
