// Shared presentation helpers for the TerraLoop UI (formatting, crop metadata, region context).
// Pure functions only: no data fetching, no invented numbers.

import type { FieldProfile, SimulationResult, StrategyRecommendation } from "@/types/api";

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const isSouthAsia = (lat: number, lon: number) => lat >= 20 && lat <= 35 && lon >= 68 && lon <= 90;

export const mean = (xs?: number[] | null): number | null =>
  xs && xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;

export const fmtCoord = (lat: number, lon: number, digits = 3) =>
  `${Math.abs(lat).toFixed(digits)}°${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(digits)}°${lon >= 0 ? "E" : "W"}`;

export const fmtDMS = (deg: number, isLat: boolean): string => {
  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const mFloat = (abs - d) * 60;
  const m = Math.floor(mFloat);
  const s = Math.round((mFloat - m) * 60);
  const dir = isLat ? (deg >= 0 ? "N" : "S") : deg >= 0 ? "E" : "W";
  return `${d}°${String(m).padStart(2, "0")}′${String(s).padStart(2, "0")}″${dir}`;
};

export const fmtMoney = (v: number | null | undefined, sym: string, compact = true) => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (compact && sym === "₹" && abs >= 100000) return `${sign}₹${(abs / 100000).toFixed(2)}L`;
  if (compact && abs >= 10000) return `${sign}${sym}${Math.round(abs / 1000)}k`;
  return `${sign}${sym}${Math.round(abs).toLocaleString()}`;
};

export const fmtSigned = (v: number, digits = 0, unit = "") =>
  `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}${unit}`;

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
  code: string;
  family: "cereal" | "legume" | "oilseed" | "fiber" | "fallow" | "forage";
  /** Tailwind classes for a pill/block representing this crop */
  tone: string;
  /** Raw colour for SVG / 3D Canvas */
  color: string;
}

export function cropMeta(cropId?: string | null): CropMeta {
  const c = (cropId ?? "").toLowerCase();
  if (c.includes("rice") || c.includes("paddy"))
    return {
      emoji: "ORI",
      code: c.includes("dsr") ? "DSR-ORI" : "PAD-ORI",
      family: "cereal",
      tone: "bg-sky-500/12 text-sky-800 dark:text-sky-300 border-sky-500/30",
      color: "#3898c8",
    };
  if (c.includes("wheat") || c.includes("barley") || c.includes("rye"))
    return {
      emoji: "TRI",
      code: "WHT-TRI",
      family: "cereal",
      tone: "bg-amber-500/12 text-amber-800 dark:text-amber-300 border-amber-500/30",
      color: "#d49b35",
    };
  if (c.includes("maize") || c.includes("corn"))
    return {
      emoji: "ZEA",
      code: "MZE-ZEA",
      family: "cereal",
      tone: "bg-yellow-500/12 text-yellow-800 dark:text-yellow-300 border-yellow-500/30",
      color: "#ca8a04",
    };
  if (c.includes("cotton"))
    return {
      emoji: "GOS",
      code: "CTN-GOS",
      family: "fiber",
      tone: "bg-stone-500/12 text-stone-800 dark:text-stone-200 border-stone-400/30",
      color: "#a8a29e",
    };
  if (
    c.includes("moong") ||
    c.includes("bean") ||
    c.includes("chickpea") ||
    c.includes("soy") ||
    c.includes("pea") ||
    c.includes("gram") ||
    c.includes("clover") ||
    c.includes("berseem") ||
    c.includes("lentil") ||
    c.includes("cowpea") ||
    c.includes("pigeon")
  )
    return {
      emoji: "FAB",
      code: "LEG-BNF",
      family: "legume",
      tone: "bg-emerald-500/12 text-emerald-800 dark:text-emerald-300 border-emerald-500/30",
      color: "#4d9e6d",
    };
  if (c.includes("mustard") || c.includes("sunflower") || c.includes("canola") || c.includes("groundnut"))
    return {
      emoji: "OLS",
      code: "OIL-BRS",
      family: "oilseed",
      tone: "bg-orange-500/12 text-orange-800 dark:text-orange-300 border-orange-500/30",
      color: "#d97746",
    };
  if (c.includes("fallow"))
    return {
      emoji: "FLW",
      code: "FLW-00",
      family: "fallow",
      tone: "bg-stone-500/10 text-stone-700 dark:text-stone-400 border-stone-500/25",
      color: "#78716c",
    };
  if (c.includes("sorghum") || c.includes("millet") || c.includes("bajra"))
    return {
      emoji: "MIL",
      code: "C4-MIL",
      family: "cereal",
      tone: "bg-lime-500/12 text-lime-800 dark:text-lime-300 border-lime-500/30",
      color: "#84cc16",
    };
  return {
    emoji: "CRP",
    code: "AGR-CRP",
    family: "forage",
    tone: "bg-teal-500/12 text-teal-800 dark:text-teal-300 border-teal-500/30",
    color: "#2dd4bf",
  };
}

export const cropName = (cropId: string) =>
  cropId
    .replace("rice_dsr", "DSR Rice")
    .replace("rice_puddled", "Puddled Rice")
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
  good: {
    text: "text-emerald-700 dark:text-emerald-400",
    bg: "bg-emerald-500/10",
    dot: "bg-emerald-500",
    ring: "ring-emerald-500/30",
  },
  warn: {
    text: "text-amber-700 dark:text-amber-400",
    bg: "bg-amber-500/10",
    dot: "bg-amber-500",
    ring: "ring-amber-500/30",
  },
  bad: {
    text: "text-rose-700 dark:text-rose-400",
    bg: "bg-rose-500/10",
    dot: "bg-rose-500",
    ring: "ring-rose-500/30",
  },
  neutral: {
    text: "text-foreground",
    bg: "bg-foreground/5",
    dot: "bg-stone-400",
    ring: "ring-line",
  },
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
  code: string;
}

export function regionContext(lat: number, lon: number, goldenId: string | null): RegionContext {
  if (goldenId === "sangrur" || goldenId === "ludhiana" || goldenId === "bathinda" || isSouthAsia(lat, lon))
    return { key: "punjab", icon: "IN-PB", code: "SECTOR // NW-INDIA" };
  if (goldenId === "fresno" || (lat >= 32 && lat <= 42.5 && lon >= -125 && lon <= -114))
    return { key: "california", icon: "US-CA", code: "SECTOR // CENTRAL-VALLEY" };
  if (goldenId === "iowa" || (lat >= 36 && lat <= 49 && lon >= -105 && lon <= -80))
    return { key: "cornbelt", icon: "US-IA", code: "SECTOR // CORN-BELT" };
  if (goldenId === "machakos" || (lat >= -15 && lat <= 12 && lon >= 25 && lon <= 52))
    return { key: "eastafrica", icon: "KE-MC", code: "SECTOR // EAST-AFRICA" };
  return { key: "global", icon: "EO-GLB", code: "SECTOR // GLOBAL-PARCEL" };
}

export const regionFlag = (id: string) =>
  ({ sangrur: "IN·PB", ludhiana: "IN·LD", bathinda: "IN·BT", iowa: "US·IA", fresno: "US·CA", machakos: "KE·MK" })[id] ?? "GLB";

export const currencyFor = (profile: FieldProfile | null, lat: number, lon: number) =>
  profile?.currency_symbol ?? (isSouthAsia(lat, lon) ? "₹" : "$");
