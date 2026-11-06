"use client";

import type { DataProvenance } from "@/types/api";

export function ProvenanceChip({ provenance }: { provenance?: DataProvenance | DataProvenance[] | null }) {
  if (!provenance) return null;
  const items = Array.isArray(provenance) ? provenance : [provenance];
  if (items.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {items.map((p, idx) => (
        <span
          key={idx}
          title={`${p.product ?? p.source} ${p.period ? `(${p.period})` : ""} ${p.resolution ? `· ${p.resolution}` : ""}${p.doi ? ` · DOI: ${p.doi}` : ""}`}
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono tracking-tight bg-foreground/[0.04] text-muted hover:text-foreground border border-line cursor-help transition-colors"
        >
          <span className="w-1.5 h-1.5 rounded-xs bg-emerald-500/80" />
          <span className="font-semibold text-foreground/85">{p.source}</span>
          {p.period && <span className="opacity-75">[{p.period}]</span>}
        </span>
      ))}
    </div>
  );
}
