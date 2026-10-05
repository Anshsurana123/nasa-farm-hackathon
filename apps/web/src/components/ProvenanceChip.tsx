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
          title={`${p.product ?? ""} ${p.period ? `(${p.period})` : ""} ${p.resolution ? `· ${p.resolution}` : ""}`}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono tracking-tight bg-blue-50 text-blue-700 border border-blue-200/60 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800/50 cursor-help"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
          <span>{p.source}</span>
          {p.period && <span className="opacity-75">· {p.period}</span>}
        </span>
      ))}
    </div>
  );
}
