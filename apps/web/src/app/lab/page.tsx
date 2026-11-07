"use client";

import { useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RotationExplorer } from "@/components/RotationExplorer";
import { useField } from "@/context/FieldContext";
import { ArrowRight, Box, Flame, Layers, Sparkles } from "lucide-react";

export default function LabPage() {
  const { selectedField, profile, strategies, setStrategies, optimizing } = useField();
  const [labMode, setLabMode] = useState<"pareto" | "whatif">("pareto");

  return (
    <AppShell
      pageStep="04"
      pageBadge="NSGA-II 3D PARETO SPACE · MONTE CARLO PERTURBATION · CMIP6 SSP2-4.5 / SSP5-8.5"
      pageTitle="3D Pareto Frontier Cube & Climate Shock Simulator"
      pageDescription="Rotate the 3-dimensional objective space (Water Saved × Net Profit × Soil Health Score) to inspect non-dominated Pareto strategies, or subject candidate rotations to monsoon failure, commodity price drops, and fertilizer price spikes."
      headerActions={
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="inline-flex rounded-xl bg-surface-2 p-1 border border-line">
            <button
              type="button"
              onClick={() => setLabMode("pareto")}
              className={`px-3.5 py-2 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 transition-colors ${
                labMode === "pareto"
                  ? "bg-cyan-500 text-slate-950 shadow-sm"
                  : "text-muted hover:text-foreground"
              }`}
            >
              <Box className="w-3.5 h-3.5" />
              <span>3D Pareto Cube</span>
            </button>
            <button
              type="button"
              onClick={() => setLabMode("whatif")}
              className={`px-3.5 py-2 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 transition-colors ${
                labMode === "whatif"
                  ? "bg-amber-500 text-slate-950 shadow-sm"
                  : "text-muted hover:text-foreground"
              }`}
            >
              <Flame className="w-3.5 h-3.5" />
              <span>Climate &amp; Market Shock Lab</span>
            </button>
          </div>

          <Link
            href="/crops"
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-500 hover:opacity-95 text-slate-950 font-mono text-xs font-bold flex items-center gap-2 shadow-md transition-opacity"
          >
            <Sparkles className="w-4 h-4" />
            <span>Explore 23-Crop Atlas</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      }
    >
      <div className="space-y-6">
        {/* Interactive Lab Guide Banner */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            type="button"
            onClick={() => setLabMode("pareto")}
            className={`text-left rounded-2xl p-4 border transition-all ${
              labMode === "pareto"
                ? "glass border-cyan-500/50 bg-cyan-500/5 shadow-lg shadow-cyan-500/5"
                : "glass border-line hover:border-cyan-500/30"
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-mono uppercase tracking-widest text-cyan-400 font-bold">
                Mode 01 · Multi-Objective Topology
              </span>
              <Box className="w-4 h-4 text-cyan-400" />
            </div>
            <p className="font-display font-bold text-sm text-foreground">
              Interactive 3D Pareto Frontier Cube
            </p>
            <p className="text-xs text-muted mt-1 leading-relaxed">
              Drag to orbit 360° around X (Water Saved), Y (Net Profit), and Z (Soil Health). Click any glowing sphere to inspect its rotation breakdown.
            </p>
          </button>

          <button
            type="button"
            onClick={() => setLabMode("whatif")}
            className={`text-left rounded-2xl p-4 border transition-all ${
              labMode === "whatif"
                ? "glass border-amber-500/50 bg-amber-500/5 shadow-lg shadow-amber-500/5"
                : "glass border-line hover:border-amber-500/30"
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-mono uppercase tracking-widest text-amber-400 font-bold">
                Mode 02 · Stress Perturbation
              </span>
              <Flame className="w-4 h-4 text-amber-400" />
            </div>
            <p className="font-display font-bold text-sm text-foreground">
              What-If Drought, Price &amp; Urea Shock Simulator
            </p>
            <p className="text-xs text-muted mt-1 leading-relaxed">
              Test El Niño monsoon deficits, commodity price crashes, and synthetic fertilizer cost surges with real-time P10 downside survival bars.
            </p>
          </button>

          <Link
            href="/rotations"
            className="text-left rounded-2xl p-4 glass border border-line hover:border-emerald-500/40 transition-all block"
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-mono uppercase tracking-widest text-emerald-400 font-bold">
                Mode 03 · Phenology &amp; Radar
              </span>
              <Layers className="w-4 h-4 text-emerald-400" />
            </div>
            <p className="font-display font-bold text-sm text-foreground">
              Return to Rotation Studio &amp; Calendar
            </p>
            <p className="text-xs text-muted mt-1 leading-relaxed">
              View the 12-month Kharif–Rabi–Zaid Gantt chart, 5-axis USDA-NRCS soil health radar polygon, and full rotation cards.
            </p>
          </Link>
        </div>

        <RotationExplorer
          field={selectedField}
          profile={profile ?? undefined}
          initialTab={labMode}
          strategies={strategies}
          loading={optimizing && strategies.length === 0}
          onStrategiesLoaded={setStrategies}
        />
      </div>
    </AppShell>
  );
}
