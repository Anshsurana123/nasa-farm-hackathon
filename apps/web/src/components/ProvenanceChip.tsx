"use client";

import type { DataProvenance } from "@/types/api";

export function ProvenanceChip({ provenance }: { provenance?: DataProvenance | DataProvenance[] | null }) {
  if (!provenance) return null;
  const items = Array.isArray(provenance) ? provenance : [provenance];
  if (items.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {items.map((p, idx) => {
        const href = p.doi ? `https://doi.org/${p.doi}` : p.url ?? undefined;
        const isClimatology = p.mode === "regional_climatology" || p.mode === "fallback_estimate";
        const modeLabel =
          p.mode === "regional_climatology"
            ? "Regional Climatology"
            : p.mode === "fallback_estimate"
            ? "Fallback Estimate"
            : "Observed";
        const tooltip = `${p.product ?? p.source}${p.period ? ` (${p.period})` : ""}${
          p.resolution ? ` · ${p.resolution}` : ""
        }${p.doi ? ` · DOI: ${p.doi}` : ""} · Mode: ${modeLabel}`;

        const content = (
          <>
            <span
              className={`w-1.5 h-1.5 rounded-xs ${
                isClimatology ? "bg-amber-400/90" : "bg-emerald-500/85"
              }`}
            />
            <span className="font-semibold text-foreground/85">{p.source}</span>
            {p.period && <span className="opacity-75">[{p.period}]</span>}
            {isClimatology && (
              <span className="text-[9px] px-1 rounded bg-amber-500/15 text-amber-600 dark:text-amber-300 border border-amber-500/30">
                Climatology
              </span>
            )}
            {p.doi && (
              <span className="text-[9px] text-cyan-600 dark:text-cyan-300 underline decoration-dotted">
                DOI
              </span>
            )}
          </>
        );

        const cls =
          "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono tracking-tight bg-foreground/[0.04] text-muted hover:text-foreground border border-line transition-colors";

        if (href) {
          return (
            <a
              key={idx}
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              title={tooltip}
              className={`${cls} cursor-pointer hover:border-cyan-500/40`}
            >
              {content}
            </a>
          );
        }

        return (
          <span key={idx} title={tooltip} className={`${cls} cursor-help`}>
            {content}
          </span>
        );
      })}
    </div>
  );
}
