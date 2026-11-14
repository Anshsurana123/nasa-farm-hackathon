"use client";

import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { ReportCard } from "@/components/ReportCard";
import { FieldMap } from "@/components/FieldMap";
import { useField } from "@/context/FieldContext";
import { useI18n } from "@/i18n";
import { ArrowRight, Layers, Satellite } from "lucide-react";

export default function DiagnosticsPage() {
  const { t } = useI18n();
  const { selectedField, goldenFields, profile, strategies, selectGolden, selectLocation } = useField();

  return (
    <AppShell
      pageStep="02"
      pageBadge={t("nav.badge.diagnostics")}
      pageTitle={t("diagnostics.pageTitle")}
      pageDescription={t("diagnostics.pageDesc")}
      headerActions={
        <Link
          href="/rotations"
          className="px-4 py-2.5 rounded-xl bg-emerald-500 hover:opacity-95 text-slate-950 font-mono text-xs font-bold flex items-center gap-2 shadow-md transition-opacity"
        >
          <Layers className="w-4 h-4" />
          <span>{t("diagnostics.optimizeBtn")}</span>
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
                  {t("diagnostics.mapTitle")}
                </h3>
              </div>
              <span className="text-xs font-mono text-muted">
                {t("diagnostics.mapHint")}
              </span>
            </div>

            <FieldMap
              selectedField={selectedField}
              goldenFields={goldenFields}
              onSelect={(pt) => {
                const matched = pt.id ? goldenFields.find((g) => g.id === pt.id) : undefined;
                if (matched) selectGolden(matched);
                else selectLocation(pt);
              }}
            />
          </div>
        </div>
      )}
    </AppShell>
  );
}
