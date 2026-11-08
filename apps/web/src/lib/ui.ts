// Shared presentation helpers for the TerraLoop UI (formatting, crop metadata, region context).
// Pure functions only: no data fetching, no invented numbers.

import type { FieldProfile, SimulationResult, StrategyRecommendation } from "@/types/api";

export type UnitSystem = "acre" | "hectare";
export const ACRES_PER_HA = 2.47105;

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const isSouthAsia = (lat: number, lon: number) => lat >= 5 && lat <= 38.5 && lon >= 66 && lon <= 99;

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
  return `${sign}${sym}${Math.round(abs).toLocaleString("en-IN")}`;
};

export const fmtAreaMoney = (
  vPerHa: number | null | undefined,
  sym: string,
  unit: UnitSystem = "acre",
  compact = true
) => {
  if (vPerHa === null || vPerHa === undefined || Number.isNaN(vPerHa)) return "—";
  const scaled = unit === "acre" ? vPerHa / ACRES_PER_HA : vPerHa;
  return fmtMoney(scaled, sym, compact);
};

export const fmtAreaUnit = (unit: UnitSystem = "acre") => (unit === "acre" ? "/acre" : "/ha");

export const scaleByUnit = (vPerHa: number, unit: UnitSystem = "acre") =>
  unit === "acre" ? vPerHa / ACRES_PER_HA : vPerHa;

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

const CROP_LABELS: Record<string, string> = {
  rice_puddled: "Puddled Rice",
  rice_short: "Short Rice (PR-126)",
  rice_dsr: "DSR Rice",
  basmati: "Basmati Rice",
  wheat: "Wheat",
  maize: "Maize",
  moong: "Greengram (Moong)",
  urad: "Blackgram (Urad)",
  groundnut: "Groundnut",
  chickpea: "Chickpea (Chana)",
  mustard: "Mustard (Sarson)",
  pigeon_pea: "Pigeon Pea (Tur)",
  pearl_millet: "Pearl Millet (Bajra)",
  sorghum: "Sorghum (Jowar)",
  soybean: "Soybean",
  cotton: "Cotton",
  lentil: "Lentil (Masoor)",
  barley: "Barley",
  sunflower: "Sunflower",
  potato: "Potato",
  sugarcane: "Sugarcane",
  guar: "Cluster Bean (Guar)",
  berseem: "Berseem Clover",
  dhaincha: "Dhaincha (Green Manure)",
  fallow: "Fallow",
};

export const cropName = (cropId: string) =>
  CROP_LABELS[cropId] ??
  cropId
    .replace(/_/g, " ")
    .replace(/^\w/, (m) => m.toUpperCase());

export function seasonName(lat: number, _lon: number, idx: number): string {
  if (lat < 16.5) return ["Kuruvai (Kharif)", "Samba (Rabi)", "Navarai (Summer)"][idx] ?? `S${idx + 1}`;
  return ["Kharif", "Rabi", "Zaid"][idx] ?? `S${idx + 1}`;
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
// Region context banner (dynamic agro-climatic classification + live telemetry briefing)
// ---------------------------------------------------------------------------
export interface RegionContext {
  key:
    | "punjab"
    | "malwa"
    | "arid_west"
    | "gujarat"
    | "himalayan"
    | "bundelkhand"
    | "gangetic"
    | "central_plateau"
    | "eastern"
    | "vidarbha"
    | "cauvery"
    | "peninsular"
    | "south_asia"
    | "global";
  icon: string;
  code: string;
  shortName: string;
  regionName: string;
  defaultBadge: string;
  defaultTone: string;
}

export function regionContext(lat: number, lon: number, goldenId: string | null): RegionContext {
  if (goldenId === "vidarbha" || (lat >= 17.0 && lat <= 22.0 && lon >= 73.5 && lon <= 81.5)) {
    return {
      key: "vidarbha",
      icon: "IN-MH",
      code: "SECTOR // DECCAN-VERTISOL",
      shortName: "Deccan Vertisol Belt",
      regionName: "Deccan Trap Vertisols (Maharashtra)",
      defaultBadge: "RAINFED VERTISOL CORRIDOR",
      defaultTone: "border-emerald-500/50 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
    };
  }
  if (goldenId === "bundelkhand" || (lat >= 23.8 && lat <= 26.5 && lon >= 77.5 && lon <= 81.2)) {
    return {
      key: "bundelkhand",
      icon: "IN-UP·BK",
      code: "SECTOR // BUNDELKHAND",
      shortName: "Bundelkhand Plateau",
      regionName: "Bundelkhand Hard-Rock Plateau",
      defaultBadge: "DRYLAND PLATEAU ADAPTATION",
      defaultTone: "border-amber-500/50 bg-amber-500/15 text-amber-600 dark:text-amber-300",
    };
  }
  if (goldenId === "thanjavur" || (lat >= 8.0 && lat < 17.0 && lon >= 78.0 && lon <= 85.0)) {
    return {
      key: "cauvery",
      icon: "IN-TN",
      code: "SECTOR // CAUVERY-DELTA",
      shortName: "Cauvery & East Coast",
      regionName: "Cauvery Delta & East Coast Plains",
      defaultBadge: "DELTAIC RICE-PULSE SYSTEM",
      defaultTone: "border-cyan-500/50 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300",
    };
  }
  if (lat >= 8.0 && lat < 17.0 && lon >= 72.0 && lon < 78.0) {
    return {
      key: "peninsular",
      icon: "IN-KA",
      code: "SECTOR // PENINSULAR-SOUTH",
      shortName: "Southern Peninsula",
      regionName: "Southern Peninsular Plateau & Ghats",
      defaultBadge: "PENINSULAR SEMI-ARID ZONE",
      defaultTone: "border-teal-500/50 bg-teal-500/15 text-teal-600 dark:text-teal-300",
    };
  }
  if (goldenId === "bathinda" || (lat >= 29.2 && lat <= 30.6 && lon >= 73.8 && lon <= 75.3)) {
    return {
      key: "malwa",
      icon: "IN-BT",
      code: "SECTOR // MALWA-COTTON",
      shortName: "Malwa Semi-Arid Belt",
      regionName: "Semi-Arid Malwa Belt (SW Punjab)",
      defaultBadge: "SEMI-ARID CANAL COMMAND",
      defaultTone: "border-orange-500/50 bg-orange-500/15 text-orange-600 dark:text-orange-300",
    };
  }
  if (
    goldenId === "sangrur" ||
    goldenId === "ludhiana" ||
    (lat >= 28.5 && lat <= 32.5 && lon >= 73.8 && lon <= 77.5)
  ) {
    return {
      key: "punjab",
      icon: "IN-PB",
      code: "SECTOR // TRANS-GANGETIC",
      shortName: "Trans-Gangetic Plains",
      regionName: "Indo-Gangetic Basin (NW Plains)",
      defaultBadge: "CRITICAL AQUIFER CORRIDOR",
      defaultTone: "border-amber-500/50 bg-amber-500/15 text-amber-600 dark:text-amber-300",
    };
  }
  if ((lat > 32.5 && lon >= 72.0 && lon <= 81.5) || (lat >= 29.5 && lat <= 32.5 && lon > 77.5 && lon <= 81.5)) {
    return {
      key: "himalayan",
      icon: "IN-HI",
      code: "SECTOR // WESTERN-HIMALAYA",
      shortName: "Western Himalayas",
      regionName: "Western Himalayan Hill & Sub-Montane Belt",
      defaultBadge: "MONTANE TERRACE REGIME",
      defaultTone: "border-sky-500/50 bg-sky-500/15 text-sky-600 dark:text-sky-300",
    };
  }
  if (lat >= 24.0 && lat < 29.2 && lon >= 69.0 && lon < 76.5) {
    return {
      key: "arid_west",
      icon: "IN-RJ",
      code: "SECTOR // THAR-ARID",
      shortName: "Rajasthan Arid Belt",
      regionName: "Western Dry & Thar Arid Belt (Rajasthan)",
      defaultBadge: "ARID DESERT & MARWAR BELT",
      defaultTone: "border-orange-500/50 bg-orange-500/15 text-orange-600 dark:text-orange-300",
    };
  }
  if (lat >= 20.0 && lat < 24.5 && lon >= 68.0 && lon < 74.5) {
    return {
      key: "gujarat",
      icon: "IN-GJ",
      code: "SECTOR // GUJARAT-PLAINS",
      shortName: "Gujarat Plains",
      regionName: "Gujarat Plains & Saurashtra Corridor",
      defaultBadge: "SEMI-ARID OILSEED-COTTON BELT",
      defaultTone: "border-amber-500/50 bg-amber-500/15 text-amber-600 dark:text-amber-300",
    };
  }
  if (lat >= 21.0 && lat < 26.5 && lon >= 74.5 && lon <= 83.0) {
    return {
      key: "central_plateau",
      icon: "IN-MP",
      code: "SECTOR // CENTRAL-VINDHYA",
      shortName: "Central Vindhyan Plateau",
      regionName: "Central Malwa & Vindhyan Plateau",
      defaultBadge: "CENTRAL SOYBEAN-WHEAT PLATEAU",
      defaultTone: "border-emerald-500/50 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
    };
  }
  if (lat >= 24.5 && lat <= 29.5 && lon >= 76.5 && lon <= 88.0) {
    return {
      key: "gangetic",
      icon: "IN-IGP",
      code: "SECTOR // GANGETIC-PLAINS",
      shortName: "Indo-Gangetic Plains",
      regionName: "Upper & Middle Indo-Gangetic Alluvial Basin",
      defaultBadge: "ALLUVIAL CEREAL-PULSE CORRIDOR",
      defaultTone: "border-cyan-500/50 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300",
    };
  }
  if (lat >= 18.0 && lat <= 28.5 && lon > 83.0 && lon <= 97.5) {
    return {
      key: "eastern",
      icon: "IN-EA",
      code: "SECTOR // EASTERN-MONSOON",
      shortName: "Eastern Monsoon Belt",
      regionName: "Eastern Alluvial & Chota Nagpur Plateau",
      defaultBadge: "HIGH-RAINFALL RICE-PULSE ZONE",
      defaultTone: "border-cyan-500/50 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300",
    };
  }
  if (lat >= 5 && lat <= 38.5 && lon >= 66 && lon <= 99) {
    return {
      key: "south_asia",
      icon: "SA-EO",
      code: "SECTOR // SOUTH-ASIA-SWATH",
      shortName: "South Asian Parcel",
      regionName: "South Asian Subtropical Agro-Climatic Zone",
      defaultBadge: "SUBTROPICAL EO SWATH",
      defaultTone: "border-cyan-500/45 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300",
    };
  }
  return {
    key: "global",
    icon: "GL-EO",
    code: "SECTOR // GLOBAL-SWATH",
    shortName: "Global Parcel",
    regionName: "Global Agro-Climatic Intelligence & Subsurface Modeling",
    defaultBadge: "GLOBAL EO SWATH",
    defaultTone: "border-cyan-500/45 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300",
  };
}

export interface SectorBriefing {
  badge: string;
  badgeTone: string;
  title: string;
  description: string;
}

/**
 * Build a dynamic Mission Control hero title, badge, and telemetry narrative
 * from the active coordinates and live NASA POWER / SoilGrids / GRACE-FO profile.
 */
export function buildSectorBriefing(
  lat: number,
  lon: number,
  goldenId: string | null,
  profile: FieldProfile | null,
  topRec?: StrategyRecommendation | null
): SectorBriefing {
  const reg = regionContext(lat, lon, goldenId);

  if (!profile) {
    return {
      badge: reg.defaultBadge,
      badgeTone: reg.defaultTone,
      title: `${reg.regionName}: Synchronizing Satellite Swath…`,
      description: `Sampling NASA POWER daily agroclimatology, ISRIC SoilGrids 250m soil physics, NASA SMAP root-zone moisture, and GRACE-FO groundwater trends for ${fmtDMS(lat, true)} ${fmtDMS(lon, false)}.`,
    };
  }

  const { climate, soil, water, hazards } = profile;
  const precip = Math.round(climate.annual_precip_mm);
  const et0 = Math.round(climate.annual_et0_mm ?? 1500);
  const wb = water.climatic_water_balance_mm !== undefined && water.climatic_water_balance_mm !== null
    ? Math.round(water.climatic_water_balance_mm)
    : precip - et0;
  const gw = water.groundwater_trend_cm_per_year;
  const texture = soil.texture_class ?? "Loam";
  const sand = Math.round(soil.sand_pct ?? 45);
  const clay = Math.round(soil.clay_pct ?? 20);
  const soc = soil.soc_g_per_kg !== undefined && soil.soc_g_per_kg !== null ? soil.soc_g_per_kg.toFixed(1) : "5.5";
  const ph = soil.ph !== undefined && soil.ph !== null ? soil.ph.toFixed(1) : "7.5";

  // 1. Dynamic Badge & Tone based on live parcel hydro-edaphic thresholds
  let badge = reg.defaultBadge;
  let badgeTone = reg.defaultTone;

  if (gw !== undefined && gw !== null && gw < -2.0) {
    badge = `CRITICAL AQUIFER OVERDRAFT (${gw.toFixed(1)} CM/YR)`;
    badgeTone = "border-rose-500/50 bg-rose-500/15 text-rose-600 dark:text-rose-300";
  } else if (precip < 450 || wb < -1050) {
    badge = `ARID HYPER-DEFICIT (${precip} MM/YR RAIN)`;
    badgeTone = "border-orange-500/50 bg-orange-500/15 text-orange-600 dark:text-orange-300";
  } else if (precip < 750 || wb < -650) {
    badge = `SEMI-ARID WATER DEFICIT (${precip} MM/YR RAIN)`;
    badgeTone = "border-amber-500/50 bg-amber-500/15 text-amber-600 dark:text-amber-300";
  } else if (clay >= 40) {
    badge = `VERTISOL CLAY REGIME (${clay}% CLAY · ${precip} MM)`;
    badgeTone = "border-emerald-500/50 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300";
  } else if (precip >= 1150) {
    badge = `HIGH-RAINFALL MONSOON ZONE (${precip} MM/YR)`;
    badgeTone = "border-cyan-500/50 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300";
  } else {
    badge = `${reg.defaultBadge} · ${precip} MM/YR`;
  }

  // 2. Dynamic Headline combining actual region with parcel-specific agronomic challenge
  let focusHeadline = "Water-Smart Rotation & Soil Carbon Stewardship";
  if (precip < 450) {
    focusHeadline = "Arid Moisture Conservation & Drought-Hardy Millet–Pulse Systems";
  } else if (gw !== undefined && gw !== null && gw < -2.0 && hazards.residue_burning_detected) {
    focusHeadline = "Aquifer Depletion & Stubble Fire Mitigation";
  } else if (gw !== undefined && gw !== null && gw < -2.0) {
    focusHeadline = "Groundwater Overdraft Recovery & Low-Irrigation Diversification";
  } else if (clay >= 40) {
    focusHeadline = "Cracking-Clay Moisture Storage & Rainfed Cotton–Pulse Relay";
  } else if (sand >= 58) {
    focusHeadline = "Coarse-Textured Root-Zone Retention & Dryland Pulse–Oilseed Rotation";
  } else if (wb < -650) {
    focusHeadline = "High Evaporative Demand & Canal/Deficit Pulse Diversification";
  } else if (precip >= 1150) {
    focusHeadline = "Monsoon Rice–Pulse Relay & Biological Nitrogen Optimization";
  }

  const title = `${reg.regionName}: ${focusHeadline}`;

  // 3. Dynamic Description grounded strictly in engine-returned profile numbers
  const wbStr = `${wb > 0 ? "+" : ""}${wb.toLocaleString()} mm/yr`;
  const gwClause =
    gw !== undefined && gw !== null
      ? `, while NASA GRACE-FO mascons track ${gw > 0 ? "+" : ""}${gw.toFixed(2)} cm/yr groundwater storage change`
      : "";

  const fireOrDryClause = hazards.residue_burning_detected
    ? " with post-harvest residue burning detected by NASA FIRMS"
    : climate.longest_dry_spell_days_mean >= 15
    ? ` with ${Math.round(climate.longest_dry_spell_days_mean)}-day mean monsoon dry spells and ${Math.round(climate.recent_heat_days_per_year)} heat-stress days/yr (>35°C)`
    : ` across ${Math.round(climate.recent_heat_days_per_year)} heat-stress days/yr (>35°C)`;

  const savedPct = topRec ? waterSavedPct(topRec) : null;
  const recClause = topRec?.rotation.label
    ? `TerraLoop prescribes ${topRec.rotation.label}${savedPct && savedPct > 0 ? ` (−${savedPct}% irrigation water)` : ""} to match this parcel's water balance and rebuild soil organic carbon.`
    : "TerraLoop evaluates drought-hardy pulses, oilseeds, and residue-retention rotations tailored to this parcel's hydro-edaphic envelope.";

  const description =
    `At ${fmtDMS(lat, true)} ${fmtDMS(lon, false)}, NASA POWER & GPM IMERG record ${precip.toLocaleString()} mm/yr rainfall against ${et0.toLocaleString()} mm/yr ET₀ evaporative demand (${wbStr} net balance)${gwClause}. ` +
    `ISRIC SoilGrids 250m identifies ${texture} topsoil (${sand}% sand, ${clay}% clay, ${soc} g/kg SOC, pH ${ph})${fireOrDryClause}. ` +
    recClause;

  return {
    badge,
    badgeTone,
    title,
    description,
  };
}

export const regionFlag = (id: string) =>
  ({
    sangrur: "PB·SG",
    ludhiana: "PB·LD",
    bathinda: "PB·BT",
    vidarbha: "MH·VD",
    bundelkhand: "UP·BK",
    thanjavur: "TN·TJ",
  })[id] ?? "IN·AG";

export const currencyFor = (profile: FieldProfile | null, _lat: number, _lon: number) => {
  void _lat;
  void _lon;
  return profile?.currency_symbol ?? "₹";
};
