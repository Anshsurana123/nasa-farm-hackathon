"use client";

import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RotationExplorer } from "@/components/RotationExplorer";
import { useField } from "@/context/FieldContext";
import { ArrowRight, Box, FileText, Sprout } from "lucide-react";

export default function RotationsPage() {
  const { selectedField, profile, strategies, setStrategies, optimizing } = useField();

  return (
    <AppShell
      pageStep="03"
      pageBadge="AquaCrop-OSPy · RothC-26.3 · RUSLE · NSGA-II Multi-Objective"
      pageTitle="Rotation Studio & 12-Month Agronomic Calendar"
      pageDescription="Tune farmer priority weights, apply persona presets, inspect the 12-month Kharif–Rabi–Zaid phenology Gantt timeline, and evaluate 5-axis USDA-NRCS soil health trade-offs against the status-quo monoculture."
      headerActions={
        <div className="flex flex-wrap items-center gap-2.5">
          <Link
            href="/crops"
            className="px-3.5 py-2.5 rounded-xl bg-surface-2 hover:bg-surface border border-line text-foreground font-mono text-xs font-semibold flex items-center gap-1.5 transition-colors"
          >
            <Sprout className="w-3.5 h-3.5 text-emerald-400" />
            <span>21-Crop Atlas</span>
          </Link>
          <Link
            href="/lab"
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-500 hover:opacity-95 text-slate-950 font-mono text-xs font-bold flex items-center gap-2 shadow-md transition-opacity"
          >
            <Box className="w-4 h-4" />
            <span>Open 3D Pareto &amp; Shock Lab</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
          <Link
            href="/brief"
            className="px-3.5 py-2.5 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/35 text-emerald-400 font-mono text-xs font-bold flex items-center gap-1.5 transition-colors"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Advisory Brief</span>
          </Link>
        </div>
      }
    >
      <RotationExplorer
        field={selectedField}
        profile={profile ?? undefined}
        initialTab="cards"
        strategies={strategies}
        loading={optimizing && strategies.length === 0}
        onStrategiesLoaded={setStrategies}
      />
    </AppShell>
  );
}
