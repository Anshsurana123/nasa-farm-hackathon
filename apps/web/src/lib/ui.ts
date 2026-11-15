// Shared UI helpers: unit scaling, formatting, crop & agro-climatic region metadata (zero science hardcoding).

import type {
  FieldProfile,
  SimulationResult,
  StrategyRecommendation,
  SupportedLanguage,
  UnitConvention,
} from "@/types/api";

export type UnitSystem = "acre" | "hectare" | "imperial";
export const ACRES_PER_HA = 2.47105;

export const toApiUnitConvention = (unit: UnitSystem): UnitConvention =>
  unit === "hectare" ? "metric" : unit;

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const mean = (xs?: number[] | null): number | null =>
  xs && xs.length > 0 ? xs.reduce((a, b) => a + b, 0) / xs.length : null;

export const fmtCoord = (lat: number, lon: number, digits = 3) =>
  `${Math.abs(lat).toFixed(digits)}°${lat >= 0 ? "N" : "S"}, ${Math.abs(lon).toFixed(digits)}°${lon >= 0 ? "E" : "W"}`;

export const fmtDMS = (deg: number, isLat: boolean): string => {
  const dir = isLat ? (deg >= 0 ? "N" : "S") : deg >= 0 ? "E" : "W";
  const abs = Math.abs(deg);
  const d = Math.floor(abs);
  const mFloat = (abs - d) * 60;
  const m = Math.floor(mFloat);
  const s = Math.round((mFloat - m) * 60);
  return `${d}°${String(m).padStart(2, "0")}'${String(s).padStart(2, "0")}"${dir}`;
};

export const fmtMoney = (v: number | null | undefined, sym: string, compact = true) => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (compact && sym === "₹" && abs >= 100000) return `${sign}₹${(abs / 100000).toFixed(2)}L`;
  if (compact && abs >= 1000000) return `${sign}${sym}${(abs / 1000000).toFixed(2)}M`;
  if (compact && abs >= 10000) return `${sign}${sym}${Math.round(abs / 1000)}k`;
  const locale = sym === "₹" ? "en-IN" : "en-US";
  return `${sign}${sym}${Math.round(abs).toLocaleString(locale)}`;
};

export const fmtAreaMoney = (
  vPerHa: number | null | undefined,
  sym: string,
  unit: UnitSystem = "acre",
  compact = true
) => {
  if (vPerHa === null || vPerHa === undefined || Number.isNaN(vPerHa)) return "—";
  const val = unit === "acre" || unit === "imperial" ? vPerHa / ACRES_PER_HA : vPerHa;
  return fmtMoney(val, sym, compact);
};

export const fmtAreaUnit = (unit: UnitSystem = "acre") =>
  unit === "hectare" ? "/ha" : "/ac";

export const fmtWaterDepth = (mm: number | null | undefined, unit: UnitSystem = "hectare") => {
  if (mm === null || mm === undefined || Number.isNaN(mm)) return "—";
  if (unit === "imperial") return `${(mm / 25.4).toFixed(1)} in`;
  return `${Math.round(mm)} mm`;
};

const BUSHEL_FACTORS_PER_THA: Record<string, number> = {
  wheat: 14.869,
  wheat_winter: 14.869,
  wheat_spring: 14.869,
  soybean: 14.869,
  chickpea: 14.869,
  lentil: 14.869,
  field_pea: 14.869,
  faba_bean: 14.869,
  lupin: 14.869,
  common_bean: 14.869,
  moong: 14.869,
  urad: 14.869,
  pigeon_pea: 14.869,
  maize: 15.932,
  sorghum: 15.932,
  pearl_millet: 15.932,
  rye_winter: 15.932,
  barley: 18.587,
  triticale: 18.587,
  oats: 27.88,
  rapeseed_canola: 17.844,
  mustard: 17.844,
  sunflower: 17.844,
};

export const fmtYield = (
  tHa: number | null | undefined,
  unit: UnitSystem = "hectare",
  currencySym = "$",
  cropId?: string
): string => {
  if (tHa === null || tHa === undefined || Number.isNaN(tHa)) return "—";
  if (unit === "hectare") return `${tHa.toFixed(2)} t/ha`;
  if (unit === "imperial") {
    const buFactor = cropId ? BUSHEL_FACTORS_PER_THA[cropId] : undefined;
    if (buFactor) return `${Math.round(tHa * buFactor)} bu/ac`;
    return `${(tHa * 0.44609).toFixed(2)} sh ton/ac`;
  }
  return currencySym === "₹"
    ? `${(tHa * 4.04686).toFixed(1)} q/ac`
    : `${(tHa * 0.404686).toFixed(2)} t/ac`;
};

export const scaleByUnit = (vPerHa: number, unit: UnitSystem = "acre") =>
  unit === "acre" || unit === "imperial" ? vPerHa / ACRES_PER_HA : vPerHa;

export const fmtSigned = (v: number, digits = 0, unit = "") =>
  `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(digits)}${unit}`;

export const avgIrrigation = (r?: SimulationResult | null) => {
  if (!r?.irrigation_mm?.length) return null;
  return r.irrigation_mm.reduce((a, b) => a + b, 0) / r.irrigation_mm.length;
};

export const strategyLabel = (s: StrategyRecommendation) => s.rotation.label ?? s.rotation.id;

export const waterSavedPct = (s: StrategyRecommendation): number | null => {
  const v = s.vs_baseline?.irrigation_change_pct;
  if (v === undefined || v === null || Number.isNaN(v)) return null;
  return Math.round(-v);
};

export interface CropMeta {
  emoji: string;
  code: string;
  family: "cereal" | "legume" | "oilseed" | "fiber" | "fallow" | "forage" | "tuber";
  /** Tailwind classes for a pill/block representing this crop */
  tone: string;
  /** Raw colour for SVG / 3D Canvas */
  color: string;
}

export function cropMeta(cropId?: string | null): CropMeta {
  const c = (cropId ?? "").toLowerCase();
  if (c.includes("rice") || c.includes("paddy") || c.includes("basmati"))
    return {
      emoji: "ORI",
      code: c.includes("dsr") ? "DSR-ORI" : c.includes("basmati") ? "BAS-ORI" : "PAD-ORI",
      family: "cereal",
      tone: "bg-sky-500/12 text-sky-800 dark:text-sky-300 border-sky-500/30",
      color: "#3898c8",
    };
  if (c.includes("wheat") || c.includes("barley") || c.includes("rye") || c.includes("triticale") || c.includes("oats"))
    return {
      emoji: "TRI",
      code: c.includes("barley")
        ? "BRL-HOR"
        : c.includes("oats")
          ? "OAT-AVE"
          : c.includes("rye")
            ? "RYE-SEC"
            : c.includes("triticale")
              ? "TRT-XTR"
              : "WHT-TRI",
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
  if (c.includes("potato") || c.includes("cassava") || c.includes("sugar_beet") || c.includes("tuber"))
    return {
      emoji: c.includes("sugar") ? "BET" : c.includes("cassava") ? "MAN" : "SOL",
      code: c.includes("sugar") ? "SBT-BET" : c.includes("cassava") ? "CSV-MAN" : "POT-SOL",
      family: "tuber",
      tone: "bg-purple-500/12 text-purple-800 dark:text-purple-300 border-purple-500/30",
      color: "#a855f7",
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
    c.includes("urad") ||
    c.includes("groundnut") ||
    c.includes("bean") ||
    c.includes("chickpea") ||
    c.includes("soy") ||
    c.includes("pea") ||
    c.includes("gram") ||
    c.includes("clover") ||
    c.includes("berseem") ||
    c.includes("dhaincha") ||
    c.includes("lentil") ||
    c.includes("lupin") ||
    c.includes("alfalfa") ||
    c.includes("vetch") ||
    c.includes("cowpea") ||
    c.includes("pigeon")
  )
    return {
      emoji: "FAB",
      code: c.includes("groundnut") ? "GNT-FAB" : c.includes("soy") ? "SOY-GLX" : "LEG-BNF",
      family: c.includes("alfalfa") || c.includes("berseem") || c.includes("clover") ? "forage" : "legume",
      tone: "bg-emerald-500/12 text-emerald-800 dark:text-emerald-300 border-emerald-500/30",
      color: "#4d9e6d",
    };
  if (c.includes("mustard") || c.includes("sunflower") || c.includes("canola") || c.includes("rapeseed"))
    return {
      emoji: "OLS",
      code: c.includes("sunflower") ? "SUN-HEL" : "OIL-BRS",
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
  rice_upland: "Upland Rice",
  rice_japonica_temperate: "Japonica Temperate Rice",
  wheat: "Wheat",
  wheat_winter: "Winter Wheat",
  wheat_spring: "Spring Wheat",
  maize: "Maize (Corn)",
  moong: "Mung Bean (Greengram)",
  urad: "Blackgram (Urad)",
  groundnut: "Groundnut (Peanut)",
  chickpea: "Chickpea (Garbanzo)",
  mustard: "Mustard",
  rapeseed_canola: "Canola / Oilseed Rape",
  pigeon_pea: "Pigeon Pea",
  pearl_millet: "Pearl Millet",
  sorghum: "Grain Sorghum",
  soybean: "Soybean",
  cotton: "Cotton",
  lentil: "Lentil",
  barley: "Barley",
  oats: "Oats",
  rye_winter: "Winter Rye (Cover/Grain)",
  triticale: "Triticale",
  sunflower: "Sunflower",
  potato: "Potato",
  sweet_potato: "Sweet Potato",
  cassava: "Cassava",
  sugar_beet: "Sugar Beet",
  common_bean: "Common Dry Bean",
  field_pea: "Field Pea",
  faba_bean: "Faba Bean",
  lupin: "Narrowleaf Lupin",
  alfalfa: "Alfalfa / Lucerne",
  berseem: "Berseem Clover",
  dhaincha: "Dhaincha (Green Manure)",
  crimson_clover_vetch: "Crimson Clover / Vetch",
  brachiaria_cover: "Brachiaria Forage Cover",
  fallow: "Fallow",
};

const CROP_LABELS_I18N: Partial<Record<SupportedLanguage, Record<string, string>>> = {
  es: {
    maize: "Maíz",
    soybean: "Soja",
    wheat: "Trigo",
    wheat_winter: "Trigo de Invierno",
    wheat_spring: "Trigo de Primavera",
    barley: "Cebada",
    oats: "Avena",
    rye_winter: "Centeno de Invierno",
    rapeseed_canola: "Colza / Canola",
    sunflower: "Girasol",
    common_bean: "Frijol Común",
    chickpea: "Garbanzo",
    lentil: "Lenteja",
    field_pea: "Guisante Seco",
    faba_bean: "Haba",
    lupin: "Altramuz",
    alfalfa: "Alfalfa",
    potato: "Patata",
    sweet_potato: "Batata",
    cassava: "Yuca",
    sugar_beet: "Remolacha Azucarera",
    cotton: "Algodón",
    sorghum: "Sorgo",
    groundnut: "Cacahuete / Maní",
    fallow: "Barbecho",
  },
  pt: {
    maize: "Milho",
    soybean: "Soja",
    wheat: "Trigo",
    wheat_winter: "Trigo de Inverno",
    wheat_spring: "Trigo de Primavera",
    barley: "Cevada",
    oats: "Aveia",
    rye_winter: "Centeio",
    rapeseed_canola: "Canola / Colza",
    sunflower: "Girassol",
    common_bean: "Feijão Comum",
    chickpea: "Grão-de-Bico",
    lentil: "Lentilha",
    field_pea: "Ervilha Seca",
    faba_bean: "Fava",
    lupin: "Tremoço",
    alfalfa: "Alfafa",
    potato: "Batata",
    sweet_potato: "Batata-Doce",
    cassava: "Mandioca",
    sugar_beet: "Beterraba Açucareira",
    cotton: "Algodão",
    sorghum: "Sorgo",
    groundnut: "Amendoim",
    rice_upland: "Arroz de Sequeiro",
    brachiaria_cover: "Braquiária (Cobertura)",
    fallow: "Pousio",
  },
  fr: {
    maize: "Maïs",
    soybean: "Soja",
    wheat: "Blé Tendre",
    wheat_winter: "Blé d'Hiver",
    wheat_spring: "Blé de Printemps",
    barley: "Orge",
    oats: "Avoine",
    rye_winter: "Seigle d'Hiver",
    rapeseed_canola: "Colza / Canola",
    sunflower: "Tournesol",
    common_bean: "Haricot Sec",
    chickpea: "Pois Chiche",
    lentil: "Lentille",
    field_pea: "Pois Protéagineux",
    faba_bean: "Féverole",
    lupin: "Lupin",
    alfalfa: "Luzerne",
    potato: "Pomme de Terre",
    sweet_potato: "Patate Douce",
    cassava: "Manioc",
    sugar_beet: "Betterave Sucrière",
    cotton: "Coton",
    sorghum: "Sorgho",
    groundnut: "Arachide",
    fallow: "Jachère",
  },
};

export const cropName = (cropId: string, lang: SupportedLanguage = "en") =>
  CROP_LABELS_I18N[lang]?.[cropId] ??
  CROP_LABELS[cropId] ??
  cropId.replace(/_/g, " ").replace(/^\w/, (m) => m.toUpperCase());

export function seasonName(
  lat: number,
  _lon: number,
  idx: number,
  profile?: FieldProfile | null
): string {
  const slot = profile?.calendar_slots?.[idx];
  if (slot?.name) return slot.name;
  if (lat < 0) {
    return ["Main Wet / Safra", "Second / Winter", "Cover / Catch"][idx] ?? `Slot ${idx + 1}`;
  }
  return ["Main Growing Season", "Cool / Overwinter", "Shoulder / Cover"][idx] ?? `Slot ${idx + 1}`;
}

// ---------------------------------------------------------------------------
// Status classification
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
// Region context banner (driven dynamically by FieldProfile + golden IDs, zero bounding boxes)
// ---------------------------------------------------------------------------
export interface RegionContext {
  key: string;
  icon: string;
  code: string;
  shortName: string;
  regionName: string;
  defaultBadge: string;
  defaultTone: string;
  currencySymbol: string;
}

const GOLDEN_REGION_PRESETS: Record<string, RegionContext> = {
  sangrur: {
    key: "punjab",
    icon: "IN·PB",
    code: "SECTOR // TRANS-GANGETIC",
    shortName: "Central Punjab Plains",
    regionName: "Trans-Gangetic Alluvial Plains (Punjab)",
    defaultBadge: "AQUIFER RECOVERY CORRIDOR",
    defaultTone: "border-rose-500/50 bg-rose-500/15 text-rose-600 dark:text-rose-300",
    currencySymbol: "₹",
  },
  ludhiana: {
    key: "punjab",
    icon: "IN·PB",
    code: "SECTOR // TRANS-GANGETIC",
    shortName: "Central Punjab Plains",
    regionName: "Trans-Gangetic Alluvial Plains (Ludhiana)",
    defaultBadge: "AQUIFER RECOVERY CORRIDOR",
    defaultTone: "border-rose-500/50 bg-rose-500/15 text-rose-600 dark:text-rose-300",
    currencySymbol: "₹",
  },
  bathinda: {
    key: "malwa",
    icon: "IN·PB",
    code: "SECTOR // SW-PUNJAB",
    shortName: "SW Punjab Malwa Belt",
    regionName: "South-Western Punjab Semi-Arid Cotton–Wheat Belt",
    defaultBadge: "SEMI-ARID SALINITY WATCH",
    defaultTone: "border-amber-500/50 bg-amber-500/15 text-amber-600 dark:text-amber-300",
    currencySymbol: "₹",
  },
  vidarbha: {
    key: "vidarbha",
    icon: "IN·MH",
    code: "SECTOR // DECCAN-VERTISOL",
    shortName: "Deccan Vertisol Belt",
    regionName: "Deccan Trap Vertisols (Maharashtra)",
    defaultBadge: "RAINFED VERTISOL CORRIDOR",
    defaultTone: "border-emerald-500/50 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
    currencySymbol: "₹",
  },
  bundelkhand: {
    key: "bundelkhand",
    icon: "IN·UP",
    code: "SECTOR // BUNDELKHAND",
    shortName: "Bundelkhand Plateau",
    regionName: "Bundelkhand Hard-Rock Plateau",
    defaultBadge: "DRYLAND PLATEAU ADAPTATION",
    defaultTone: "border-amber-500/50 bg-amber-500/15 text-amber-600 dark:text-amber-300",
    currencySymbol: "₹",
  },
  thanjavur: {
    key: "cauvery",
    icon: "IN·TN",
    code: "SECTOR // CAUVERY-DELTA",
    shortName: "Cauvery Delta",
    regionName: "Cauvery Delta Plains (Tamil Nadu)",
    defaultBadge: "DELTAIC RICE-PULSE SYSTEM",
    defaultTone: "border-cyan-500/50 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300",
    currencySymbol: "₹",
  },
  us_corn_belt: {
    key: "us_corn_belt",
    icon: "US·IA",
    code: "SECTOR // US-CORN-BELT",
    shortName: "US Midwest Mollisols",
    regionName: "Upper Midwest Prairie Mollisols (Iowa)",
    defaultBadge: "USDA TEMPERATE BENCHMARK",
    defaultTone: "border-emerald-500/50 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
    currencySymbol: "$",
  },
  eu_maritime_west: {
    key: "eu_maritime_west",
    icon: "FR·BC",
    code: "SECTOR // EU-BEAUCE",
    shortName: "Western European Plains",
    regionName: "Paris Basin Maritime Loess Plains (France)",
    defaultBadge: "EU CAP ECO-SCHEME BENCHMARK",
    defaultTone: "border-cyan-500/50 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300",
    currencySymbol: "€",
  },
  brazil_cerrado: {
    key: "brazil_cerrado",
    icon: "BR·MT",
    code: "SECTOR // CERRADO-SAFRA",
    shortName: "Cerrado Oxisol Plains",
    regionName: "Mato Grosso Savanna Oxisols (Brazil)",
    defaultBadge: "DOUBLE-SAFRA & ABC+ HUB",
    defaultTone: "border-emerald-500/50 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300",
    currencySymbol: "R$",
  },
  east_africa_highlands: {
    key: "east_africa_highlands",
    icon: "KE·NK",
    code: "SECTOR // RIFT-HIGHLANDS",
    shortName: "East African Highlands",
    regionName: "Central Rift Highlands Bimodal Belt (Kenya)",
    defaultBadge: "BIMODAL INTERCROP HUB",
    defaultTone: "border-teal-500/50 bg-teal-500/15 text-teal-600 dark:text-teal-300",
    currencySymbol: "KSh",
  },
  australia_wheat_belt: {
    key: "australia_wheat_belt",
    icon: "AU·RV",
    code: "SECTOR // MURRAY-DARLING",
    shortName: "Murray-Darling Dryland",
    regionName: "Riverina Mediterranean Dryland Belt (Australia)",
    defaultBadge: "CONSERVATION BREAK-CROP HUB",
    defaultTone: "border-amber-500/50 bg-amber-500/15 text-amber-600 dark:text-amber-300",
    currencySymbol: "A$",
  },
};

export function regionContext(
  lat: number,
  lon: number,
  goldenId: string | null,
  profile?: FieldProfile | null
): RegionContext {
  if (goldenId && GOLDEN_REGION_PRESETS[goldenId]) {
    const preset = GOLDEN_REGION_PRESETS[goldenId];
    return profile?.currency_symbol
      ? { ...preset, currencySymbol: profile.currency_symbol }
      : preset;
  }

  if (profile) {
    const cc = profile.country_code?.toUpperCase() || (lat >= 0 ? "NH" : "SH");
    const sub = profile.state ? profile.state.slice(0, 3).toUpperCase() : "EO";
    const zoneName = profile.agro_zone || profile.state || profile.country || "Global EO Parcel";
    const status = profile.validation_status;
    const isVerified = status === "validated_india" || status === "validated_regional";
    return {
      key: profile.calendar_id || cc.toLowerCase(),
      icon: `${cc}·${sub}`,
      code: `SECTOR // ${(profile.aez_class || profile.calendar_id || cc).toUpperCase()}`,
      shortName: zoneName,
      regionName: profile.state && profile.country ? `${profile.state} (${profile.country})` : zoneName,
      defaultBadge: isVerified
        ? `${cc} VERIFIED REGIONAL HUB`
        : "BIOPHYSICAL EARTH OBSERVATION MODE",
      defaultTone: isVerified
        ? "border-emerald-500/50 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300"
        : "border-cyan-500/50 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300",
      currencySymbol: profile.currency_symbol ?? "$",
    };
  }

  return {
    key: "global",
    icon: lat >= 0 ? "EO·NH" : "EO·SH",
    code: "SECTOR // GLOBAL-EO",
    shortName: "Earth Observation Parcel",
    regionName: `${fmtDMS(lat, true)} · ${fmtDMS(lon, false)}`,
    defaultBadge: "MULTI-OBJECTIVE EO PARCEL",
    defaultTone: "border-cyan-500/50 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300",
    currencySymbol: "$",
  };
}

export interface SectorBriefing {
  badge: string;
  badgeTone: string;
  title: string;
  description: string;
}

const SYNC_TITLES: Record<SupportedLanguage, (name: string) => string> = {
  en: (n) => `${n}: Synchronizing Satellite Swath…`,
  hi: (n) => `${n}: सैटेलाइट डेटा लोड हो रहा है…`,
  pa: (n) => `${n}: ਸੈਟੇਲਾਈਟ ਡਾਟਾ ਲੋਡ ਹੋ ਰਿਹਾ ਹੈ…`,
  es: (n) => `${n}: Sincronizando observaciones satelitales…`,
  pt: (n) => `${n}: Sincronizando dados de satélite…`,
  fr: (n) => `${n} : Synchronisation satellitaire…`,
};

const SYNC_DESCS: Record<SupportedLanguage, (coords: string) => string> = {
  en: (c) => `Sampling NASA POWER daily agroclimatology, ISRIC SoilGrids 250m soil physics, NASA SMAP root-zone moisture, and GRACE-FO groundwater trends for ${c}.`,
  hi: (c) => `${c} के लिए NASA POWER, SoilGrids 250m, SMAP और GRACE-FO भूजल डेटा प्राप्त किया जा रहा है।`,
  pa: (c) => `${c} ਲਈ NASA POWER, SoilGrids 250m, SMAP ਅਤੇ GRACE-FO ਧਰਤੀ ਹੇਠਲੇ ਪਾਣੀ ਦਾ ਡਾਟਾ ਲਿਆ ਜਾ ਰਿਹਾ ਹੈ।`,
  es: (c) => `Consultando agroclimatología NASA POWER, física de suelos ISRIC SoilGrids 250m, humedad SMAP y acuíferos GRACE-FO para ${c}.`,
  pt: (c) => `Consultando agroclimatologia NASA POWER, física de solos ISRIC SoilGrids 250m, umidade SMAP e aquíferos GRACE-FO para ${c}.`,
  fr: (c) => `Interrogation de NASA POWER, ISRIC SoilGrids 250 m, humidité racinaire SMAP et tendances GRACE-FO pour ${c}.`,
};

/**
 * Build a dynamic Mission Control hero title, badge, and telemetry narrative
 * from the active coordinates and live NASA POWER / SoilGrids / GRACE-FO profile.
 */
export function buildSectorBriefing(
  lat: number,
  lon: number,
  goldenId: string | null,
  profile: FieldProfile | null,
  topRec?: StrategyRecommendation | null,
  lang: SupportedLanguage = "en"
): SectorBriefing {
  const reg = regionContext(lat, lon, goldenId, profile);

  if (!profile) {
    const coords = `${fmtDMS(lat, true)} ${fmtDMS(lon, false)}`;
    return {
      badge: reg.defaultBadge,
      badgeTone: reg.defaultTone,
      title: SYNC_TITLES[lang](reg.regionName),
      description: SYNC_DESCS[lang](coords),
    };
  }

  const { climate, soil, water, hazards } = profile;
  const precip = Math.round(climate.annual_precip_mm);
  const et0 = Math.round(climate.annual_et0_mm ?? 1400);
  const wb =
    water.climatic_water_balance_mm !== undefined && water.climatic_water_balance_mm !== null
      ? Math.round(water.climatic_water_balance_mm)
      : precip - et0;
  const gw = water.groundwater_trend_cm_per_year;
  const texture = soil.texture_class ?? "Loam";
  const sand = Math.round(soil.sand_pct ?? 40);
  const clay = Math.round(soil.clay_pct ?? 20);
  const soc =
    soil.soc_g_per_kg !== undefined && soil.soc_g_per_kg !== null ? soil.soc_g_per_kg.toFixed(1) : "8.0";
  const ph = soil.ph !== undefined && soil.ph !== null ? soil.ph.toFixed(1) : "7.0";

  let badge = reg.defaultBadge;
  let badgeTone = reg.defaultTone;

  if (gw !== undefined && gw !== null && gw < -2.0) {
    badge = `CRITICAL AQUIFER OVERDRAFT (${gw.toFixed(1)} CM/YR)`;
    badgeTone = "border-rose-500/50 bg-rose-500/15 text-rose-600 dark:text-rose-300";
  } else if (precip < 450 || wb < -1050) {
    badge = `ARID WATER DEFICIT (${precip} MM/YR RAIN)`;
    badgeTone = "border-orange-500/50 bg-orange-500/15 text-orange-600 dark:text-orange-300";
  } else if (precip < 750 || wb < -650) {
    badge = `SEMI-ARID WATER BALANCE (${precip} MM/YR)`;
    badgeTone = "border-amber-500/50 bg-amber-500/15 text-amber-600 dark:text-amber-300";
  } else if (clay >= 40) {
    badge = `CLAY / VERTISOL REGIME (${clay}% CLAY · ${precip} MM)`;
    badgeTone = "border-emerald-500/50 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300";
  } else if (precip >= 1150) {
    badge = `HUMID / HIGH-RAINFALL ZONE (${precip} MM/YR)`;
    badgeTone = "border-cyan-500/50 bg-cyan-500/15 text-cyan-600 dark:text-cyan-300";
  } else {
    badge = `${reg.defaultBadge} · ${precip} MM/YR`;
  }

  let focusHeadline = "Water-Smart Rotation & Soil Carbon Stewardship";
  if (lang === "hi") {
    focusHeadline = "जल-संरक्षण फसल चक्र एवं मृदा कार्बन संवर्धन";
    if (precip < 450) focusHeadline = "शुष्क जल संरक्षण और बाजरा-दलहन प्रणाली";
    else if (gw !== undefined && gw !== null && gw < -2.0 && hazards.residue_burning_detected)
      focusHeadline = "भूजल संकट व पराली जलाने का समाधान";
    else if (gw !== undefined && gw !== null && gw < -2.0)
      focusHeadline = "भूजल संरक्षण और कम सिंचाई फसल विविधीकरण";
    else if (clay >= 40) focusHeadline = "चिकनी मिट्टी नमी संरक्षण और वर्षा-आधारित फसल चक्र";
    else if (sand >= 58) focusHeadline = "हल्की मिट्टी में नमी व दलहन-तिलहन चक्र";
  } else if (lang === "pa") {
    focusHeadline = "ਪਾਣੀ-ਸੰਭਾਲ ਫ਼ਸਲੀ ਚੱਕਰ ਅਤੇ ਮਿੱਟੀ ਕਾਰਬਨ ਸੁਧਾਰ";
    if (precip < 450) focusHeadline = "ਖੁਸ਼ਕ ਖੇਤਰ ਨਮੀ ਸੰਭਾਲ ਅਤੇ ਬਾਜਰਾ-ਦਾਲਾਂ ਪ੍ਰਣਾਲੀ";
    else if (gw !== undefined && gw !== null && gw < -2.0 && hazards.residue_burning_detected)
      focusHeadline = "ਧਰਤੀ ਹੇਠਲੇ ਪਾਣੀ ਦੀ ਬਚਤ ਤੇ ਪਰਾਲੀ-ਮੁਕਤ ਖੇਤੀ";
    else if (gw !== undefined && gw !== null && gw < -2.0)
      focusHeadline = "ਭੂ-ਜਲ ਸੰਕਟ ਸੁਧਾਰ ਅਤੇ ਘੱਟ-ਪਾਣੀ ਵਾਲਾ ਫ਼ਸਲੀ ਵਿਭਿੰਨਤਾ ਚੱਕਰ";
  } else if (lang === "es") {
    focusHeadline =
      gw !== undefined && gw !== null && gw < -2.0
        ? "Recuperación de Acuíferos y Diversificación Hídrica"
        : precip < 500
          ? "Conservación de Humedad y Rotación Tolerante a Sequía"
          : "Rotación Regenerativa y Secuestro de Carbono Edáfico";
  } else if (lang === "pt") {
    focusHeadline =
      gw !== undefined && gw !== null && gw < -2.0
        ? "Recuperação de Aquífero e Eficiência Hídrica"
        : precip >= 1150
          ? "Intensificação Sustentável em Plantio Direto e Fixação de N"
          : "Rotação Conservacionista e Carbono no Solo";
  } else if (lang === "fr") {
    focusHeadline =
      gw !== undefined && gw !== null && gw < -2.0
        ? "Gestion Hydrique Durable et Diversification des Cultures"
        : "Rotation Agroécologique, Légumineuses et Carbone du Sol";
  } else {
    if (precip < 450) {
      focusHeadline = "Arid Moisture Conservation & Drought-Hardy Break-Crop Systems";
    } else if (gw !== undefined && gw !== null && gw < -2.0 && hazards.residue_burning_detected) {
      focusHeadline = "Aquifer Depletion & Stubble Fire Mitigation";
    } else if (gw !== undefined && gw !== null && gw < -2.0) {
      focusHeadline = "Groundwater Overdraft Recovery & Low-Irrigation Diversification";
    } else if (clay >= 40) {
      focusHeadline = "Heavy Clay Moisture Storage & Legume–Cereal Sequencing";
    } else if (sand >= 58) {
      focusHeadline = "Coarse-Textured Root-Zone Retention & Pulse–Oilseed Rotation";
    } else if (wb < -650) {
      focusHeadline = "Evaporative Deficit Adaptation & Water-Productive Diversification";
    } else if (precip >= 1150) {
      focusHeadline = "High-Rainfall Conservation Tillage & Biological Nitrogen Optimization";
    }
  }

  const title = `${reg.regionName}: ${focusHeadline}`;
  const wbStr = `${wb > 0 ? "+" : ""}${wb.toLocaleString()} mm/yr`;
  const savedPct = topRec ? waterSavedPct(topRec) : null;
  const coordsStr = `${fmtDMS(lat, true)} ${fmtDMS(lon, false)}`;

  if (lang === "hi") {
    const gwHi = gw !== undefined && gw !== null ? `, तथा NASA GRACE-FO भूजल प्रवृत्ति ${gw > 0 ? "+" : ""}${gw.toFixed(2)} सेमी/वर्ष है` : "";
    const recHi = topRec?.rotation.label
      ? ` अनुशंसित विकल्प: ${topRec.rotation.label}${savedPct && savedPct > 0 ? ` (−${savedPct}% सिंचाई जल)` : ""}।`
      : "";
    return {
      badge,
      badgeTone,
      title,
      description: `${coordsStr} पर वार्षिक वर्षा ${precip.toLocaleString()} मिमी तथा ET₀ ${et0.toLocaleString()} मिमी (${wbStr})${gwHi}। मिट्टी: ${texture} (${sand}% रेत, ${clay}% चिकनी, ${soc} g/kg कार्बन, pH ${ph})।${recHi}`,
    };
  }
  if (lang === "pa") {
    const gwPa = gw !== undefined && gw !== null ? `, ਅਤੇ NASA GRACE-FO ਰੁਝਾਨ ${gw > 0 ? "+" : ""}${gw.toFixed(2)} ਸੈਂਟੀਮੀਟਰ/ਸਾਲ ਹੈ` : "";
    const recPa = topRec?.rotation.label
      ? ` ਸਿਫ਼ਾਰਿਸ਼ ਚੱਕਰ: ${topRec.rotation.label}${savedPct && savedPct > 0 ? ` (−${savedPct}% ਸਿੰਚਾਈ ਪਾਣੀ)` : ""}।`
      : "";
    return {
      badge,
      badgeTone,
      title,
      description: `${coordsStr} 'ਤੇ ਸਾਲਾਨਾ ਮੀਂਹ ${precip.toLocaleString()} ਮਿਮੀ ਅਤੇ ET₀ ${et0.toLocaleString()} ਮਿਮੀ (${wbStr})${gwPa}। ਮਿੱਟੀ: ${texture} (${sand}% ਰੇਤ, ${clay}% ਚੀਕਣੀ, ${soc} g/kg ਕਾਰਬਨ, pH ${ph})।${recPa}`,
    };
  }
  if (lang === "es") {
    const recEs = topRec?.rotation.label ? ` Prescripción destacada: ${topRec.rotation.label}.` : "";
    return {
      badge,
      badgeTone,
      title,
      description: `En ${coordsStr}, NASA POWER registra ${precip.toLocaleString()} mm/año de precipitación frente a ${et0.toLocaleString()} mm/año de ET₀ (${wbStr}). Suelo ${texture} (${sand}% arena, ${clay}% arcilla, ${soc} g/kg COS, pH ${ph}).${recEs}`,
    };
  }
  if (lang === "pt") {
    const recPt = topRec?.rotation.label ? ` Prescrição principal: ${topRec.rotation.label}.` : "";
    return {
      badge,
      badgeTone,
      title,
      description: `Em ${coordsStr}, NASA POWER registra ${precip.toLocaleString()} mm/ano de chuva ante ${et0.toLocaleString()} mm/ano de ET₀ (${wbStr}). Solo ${texture} (${sand}% areia, ${clay}% argila, ${soc} g/kg COS, pH ${ph}).${recPt}`,
    };
  }
  if (lang === "fr") {
    const recFr = topRec?.rotation.label ? ` Rotation prioritaire : ${topRec.rotation.label}.` : "";
    return {
      badge,
      badgeTone,
      title,
      description: `À ${coordsStr}, NASA POWER enregistre ${precip.toLocaleString()} mm/an de pluie pour ${et0.toLocaleString()} mm/an d'ET₀ (${wbStr}). Sol ${texture} (${sand}% sable, ${clay}% argile, ${soc} g/kg COS, pH ${ph}).${recFr}`,
    };
  }

  const gwClause =
    gw !== undefined && gw !== null
      ? `, while NASA GRACE-FO mascons track ${gw > 0 ? "+" : ""}${gw.toFixed(2)} cm/yr groundwater storage change`
      : "";
  const fireOrDryClause = hazards.residue_burning_detected
    ? " with active post-harvest burning detected by NASA FIRMS"
    : climate.longest_dry_spell_days_mean >= 15
      ? ` with ${Math.round(climate.longest_dry_spell_days_mean)}-day mean dry spells and ${Math.round(climate.recent_heat_days_per_year)} heat-stress days/yr (>35°C)`
      : ` across ${Math.round(climate.recent_heat_days_per_year)} heat-stress days/yr (>35°C)`;
  const recClause = topRec?.rotation.label
    ? `TerraLoop prescribes ${topRec.rotation.label}${savedPct && savedPct > 0 ? ` (−${savedPct}% irrigation water)` : ""} to match this parcel's water balance and rebuild soil organic carbon.`
    : "TerraLoop evaluates drought-hardy pulses, oilseeds, and conservation rotations tailored to this parcel's hydro-edaphic envelope.";

  return {
    badge,
    badgeTone,
    title,
    description:
      `At ${coordsStr}, NASA POWER & GPM IMERG record ${precip.toLocaleString()} mm/yr rainfall against ${et0.toLocaleString()} mm/yr ET₀ evaporative demand (${wbStr} net balance)${gwClause}. ` +
      `ISRIC SoilGrids 250m identifies ${texture} topsoil (${sand}% sand, ${clay}% clay, ${soc} g/kg SOC, pH ${ph})${fireOrDryClause}. ` +
      recClause,
  };
}

export const regionFlag = (id: string) =>
  ({
    sangrur: "IN·PB",
    ludhiana: "IN·PB",
    bathinda: "IN·PB",
    vidarbha: "IN·MH",
    bundelkhand: "IN·UP",
    thanjavur: "IN·TN",
    us_corn_belt: "US·IA",
    eu_maritime_west: "FR·BC",
    brazil_cerrado: "BR·MT",
    east_africa_highlands: "KE·NK",
    australia_wheat_belt: "AU·RV",
  })[id] ?? (id ? id.slice(0, 5).toUpperCase() : "GL·EO");

export const currencyFor = (profile: FieldProfile | null) =>
  profile?.currency_symbol ?? "$";
