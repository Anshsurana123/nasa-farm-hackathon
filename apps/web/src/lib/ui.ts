// Shared presentation helpers for the TerraLoop UI (formatting, crop metadata, region context).
// Pure functions only: no data fetching, no invented numbers.

import type { FieldProfile, SimulationResult, StrategyRecommendation } from "@/types/api";

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const isSouthAsia = (lat: number, lon: number) => lat >= 20 && lat <= 35 && lon >= 68 && lon <= 90;

export const mean = (xs?: number[] | null): number | null =>
  xs && xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;

export const fmtCoord = (lat: number, lon: number, digits = 3) =>
  `${Math.abs(lat).toFixed(digits)}°${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(digits)}°${lon >= 0 ? "E" : "W"}`;

export const fmtMoney = (v: number | null | undefined, sym: string, compact = true) => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (compact && sym === "₹" && abs >= 100000) return `${sign}₹${(abs / 100000).toFixed(2)}L`;
  if (compact && abs >= 10000) return `${sign}${sym}${Math.round(abs / 1000)}k`;
  return `${sign}${sym}${Math.round(abs).toLocaleString()}`;
};

export const fmtSigned = (v: number, digits = 0, unit = "") => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}${unit}`;

/** Average irrigation (mm/yr) for a strategy's first scenario result, or null when unavailable. */
export const avgIrrigation = (r?: SimulationResult | null) => {
  const m = mean(r?.irrigation_mm);
  return m === null ? null : Math.round(m);
};

export const strategyLabel = (s: StrategyRecommendation) => s.rotation.label ?? s.rotation.id;

/** Water saved vs baseline in % (positive = saving), derived from backend vs_baseline fields. */
export const waterSavedPct = (s: StrategyRecommendation): number | null => {
  const c = s.vs_baseline?.irrigation_change_pct ?? s.vs_baseline?.irrigation_pct;
  return c === undefined ? null : -c;
};

// ---------------------------------------------------------------------------
// Crops
// ---------------------------------------------------------------------------
export interface CropMeta {
  emoji: string;
  /** Tailwind classes for a pill/block representing this crop */
  tone: string;
  /** Raw colour for SVG */
  color: string;
}

export function cropMeta(cropId?: string | null): CropMeta {
  const c = (cropId ?? "").toLowerCase();
  if (c.includes("rice") || c.includes("paddy"))
    return { emoji: "🌾", tone: "bg-sky-500/15 text-sky-700 dark:text-sky-300 ring-sky-400/30", color: "#38bdf8" };
  if (c.includes("wheat") || c.includes("barley") || c.includes("rye"))
    return { emoji: "🌾", tone: "bg-amber-500/15 text-amber-700 dark:text-amber-300 ring-amber-400/30", color: "#f59e0b" };
  if (c.includes("maize") || c.includes("corn"))
    return { emoji: "🌽", tone: "bg-yellow-500/15 text-yellow-700 dark:text-yellow-300 ring-yellow-400/30", color: "#eab308" };
  if (c.includes("cotton")) return { emoji: "☁️", tone: "bg-slate-400/15 text-slate-700 dark:text-slate-200 ring-slate-300/30", color: "#cbd5e1" };
  if (
    c.includes("moong") ||
    c.includes("bean") ||
    c.includes("chickpea") ||
    c.includes("soy") ||
    c.includes("pea") ||
    c.includes("gram") ||
    c.includes("clover") ||
    c.includes("berseem") ||
    c.includes("lentil")
  )
    return { emoji: "🫘", tone: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 ring-emerald-400/30", color: "#34d399" };
  if (c.includes("mustard") || c.includes("sunflower") || c.includes("canola"))
    return { emoji: "🌻", tone: "bg-orange-500/15 text-orange-700 dark:text-orange-300 ring-orange-400/30", color: "#fb923c" };
  if (c.includes("fallow")) return { emoji: "🟫", tone: "bg-stone-500/15 text-stone-700 dark:text-stone-300 ring-stone-400/30", color: "#78716c" };
  if (c.includes("sorghum") || c.includes("millet"))
    return { emoji: "🌿", tone: "bg-lime-500/15 text-lime-700 dark:text-lime-300 ring-lime-400/30", color: "#a3e635" };
  return { emoji: "🌱", tone: "bg-teal-500/15 text-teal-700 dark:text-teal-300 ring-teal-400/30", color: "#2dd4bf" };
}

export const cropName = (cropId: string) =>
  cropId
    .replace("rice_dsr", "DSR rice")
    .replace("rice_puddled", "Puddled rice")
    .replace(/_/g, " ")
    .replace(/^\w/, (m) => m.toUpperCase());

export function seasonName(lat: number, lon: number, idx: number): string {
  if (isSouthAsia(lat, lon)) return ["Kharif", "Rabi", "Zaid"][idx] ?? `S${idx + 1}`;
  if (lat >= -10 && lat <= 12 && lon >= 25 && lon <= 50) return ["Long rains", "Short rains", "Dry"][idx] ?? `S${idx + 1}`;
  if (lat < -10) return ["Summer", "Winter", "Spring"][idx] ?? `S${idx + 1}`;
  return ["Summer", "Winter", "Cover"][idx] ?? `S${idx + 1}`;
}

// ---------------------------------------------------------------------------
// Status classification (thresholds are UI bands, not science constants)
// ---------------------------------------------------------------------------
export type Tone = "good" | "warn" | "bad" | "neutral";

export const toneClasses: Record<Tone, { text: string; bg: string; dot: string; ring: string }> = {
  good: { text: "text-emerald-500 dark:text-emerald-400", bg: "bg-emerald-500/10", dot: "bg-emerald-400", ring: "ring-emerald-400/30" },
  warn: { text: "text-amber-600 dark:text-amber-400", bg: "bg-amber-500/10", dot: "bg-amber-400", ring: "ring-amber-400/30" },
  bad: { text: "text-rose-600 dark:text-rose-400", bg: "bg-rose-500/10", dot: "bg-rose-400", ring: "ring-rose-400/30" },
  neutral: { text: "text-foreground", bg: "bg-foreground/5", dot: "bg-slate-400", ring: "ring-line" },
};

export const groundwaterTone = (gw?: number | null): Tone =>
  gw === null || gw === undefined ? "neutral" : gw < -2 ? "bad" : gw < 0 ? "warn" : "good";

export const waterBalanceTone = (wb?: number | null): Tone =>
  wb === null || wb === undefined ? "neutral" : wb < -500 ? "bad" : wb < 0 ? "warn" : "good";

// ---------------------------------------------------------------------------
// Region context banner (narrative copy keyed to golden-field regions)
// ---------------------------------------------------------------------------
export interface RegionContext {
  key: "punjab" | "california" | "cornbelt" | "eastafrica" | "global";
  icon: string;
}

export function regionContext(lat: number, lon: number, goldenId: string | null): RegionContext {
  if (goldenId === "sangrur" || goldenId === "ludhiana" || goldenId === "bathinda" || isSouthAsia(lat, lon))
    return { key: "punjab", icon: "🚨" };
  if (goldenId === "fresno" || (lat >= 32 && lat <= 42.5 && lon >= -125 && lon <= -114)) return { key: "california", icon: "☀️" };
  if (goldenId === "iowa" || (lat >= 36 && lat <= 49 && lon >= -105 && lon <= -80)) return { key: "cornbelt", icon: "🌽" };
  if (goldenId === "machakos" || (lat >= -15 && lat <= 12 && lon >= 25 && lon <= 52)) return { key: "eastafrica", icon: "🌍" };
  return { key: "global", icon: "🌐" };
}

export const regionFlag = (id: string) =>
  ({ sangrur: "🇮🇳", ludhiana: "🇮🇳", bathinda: "🇮🇳", iowa: "🇺🇸", fresno: "🇺🇸", machakos: "🇰🇪" })[id] ?? "🌐";

export const currencyFor = (profile: FieldProfile | null, lat: number, lon: number) =>
  profile?.currency_symbol ?? (isSouthAsia(lat, lon) ? "₹" : "$");
