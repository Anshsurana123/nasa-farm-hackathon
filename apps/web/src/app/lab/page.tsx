"use client";

import { useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RotationExplorer } from "@/components/RotationExplorer";
import { useField } from "@/context/FieldContext";
import { useI18n } from "@/i18n";
import { ArrowRight, Box, Flame, Layers, Sparkles } from "lucide-react";

export default function LabPage() {
  const { t } = useI18n();
  const { selectedField, profile, strategies, setStrategies, optimizing } = useField();
  const [labMode, setLabMode] = useState<"pareto" | "whatif">("pareto");

  return (
    <AppShell
      pageStep="04"
      pageBadge="NSGA-II 3D PARETO SPACE · MONTE CARLO PERTURBATION · CMIP6 SSP2-4.5 / SSP5-8.5"
      pageTitle={t("lab.pageTitle")}
      pageDescription={t("lab.pageDesc")}
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
              <span>{t("lab.btnPareto")}</span>
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
              <span>{t("lab.btnShock")}</span>
            </button>
          </div>

          <Link
            href="/crops"
            className="px-4 py-2.5 rounded-xl bg-emerald-500 hover:opacity-95 text-slate-950 font-mono text-xs font-bold flex items-center gap-2 shadow-md transition-opacity"
          >
            <Sparkles className="w-4 h-4" />
            <span>{t("lab.btnCrops")}</span>
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
                {t("lab.mode1Tag")}
              </span>
              <Box className="w-4 h-4 text-cyan-400" />
            </div>
            <p className="font-display font-bold text-sm text-foreground">
              {t("lab.mode1Title")}
            </p>
            <p className="text-xs text-muted mt-1 leading-relaxed">
              {t("lab.mode1Desc")}
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
                {t("lab.mode2Tag")}
              </span>
              <Flame className="w-4 h-4 text-amber-400" />
            </div>
            <p className="font-display font-bold text-sm text-foreground">
              {t("lab.mode2Title")}
            </p>
            <p className="text-xs text-muted mt-1 leading-relaxed">
              {t("lab.mode2Desc")}
            </p>
          </button>

          <Link
            href="/rotations"
            className="text-left rounded-2xl p-4 glass border border-line hover:border-emerald-500/40 transition-all block"
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] font-mono uppercase tracking-widest text-emerald-400 font-bold">
                {t("lab.mode3Tag")}
              </span>
              <Layers className="w-4 h-4 text-emerald-400" />
            </div>
            <p className="font-display font-bold text-sm text-foreground">
              {t("lab.mode3Title")}
            </p>
            <p className="text-xs text-muted mt-1 leading-relaxed">
              {t("lab.mode3Desc")}
            </p>
          </Link>
        </div>

        <RotationExplorer
          field={selectedField}
          profile={profile ?? undefined}
          initialTab={labMode}
          strategies={strategies}
          loading={optimizing}
          onStrategiesLoaded={setStrategies}
        />
      </div>
    </AppShell>
  );
}
