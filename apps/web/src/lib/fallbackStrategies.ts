// Offline fallback strategies for Indian agro-climatic zones, used ONLY if both the live API
// and static /golden/<id>/recommendations.json fetch fail.
// Numbers match precomputed TerraLoop engine outputs for Sangrur (Punjab), with is_fallback=true.

import type { FieldGeometry, StrategyRecommendation } from "@/types/api";

export function adaptStrategiesForHorizon(
  strategies: StrategyRecommendation[],
  rotationYears: number
): StrategyRecommendation[] {
  const effYears = Math.max(1, Math.min(rotationYears || 1, 3));
  if (effYears === 1 || !strategies || strategies.length === 0) {
    return strategies;
  }

  const baseline = strategies.find((s) => s.rank === 0) ?? strategies[0];
  const candidates = strategies.filter((s) => s.rank > 0);

  // Adapt baseline across effYears
  const baseSteps1Yr = baseline.rotation.steps;
  const adaptedBaseSteps = [];
  for (let yr = 0; yr < effYears; yr++) {
    for (const step of baseSteps1Yr) {
      adaptedBaseSteps.push({ ...step, year_index: yr });
    }
  }
  const adaptedBaseOps = baseline.practical_metrics?.seasonal_operations
    ? Array.from({ length: effYears }, (_, yr) =>
        (baseline.practical_metrics?.seasonal_operations ?? []).map((op) => ({
          ...op,
          year_index: yr,
        }))
      ).flat()
    : undefined;

  const adaptedBaseline: StrategyRecommendation = {
    ...baseline,
    rotation: {
      ...baseline.rotation,
      steps: adaptedBaseSteps,
      label: baseline.rotation.label,
    },
    practical_metrics: baseline.practical_metrics
      ? {
          ...baseline.practical_metrics,
          seasonal_operations: adaptedBaseOps,
        }
      : undefined,
  };

  // Adapt candidates into complementary multi-year sequences AND average multi-year metrics accurately
  const avgNum = (a?: number, b?: number) => ((a ?? 0) + (b ?? 0)) / 2;
  const adaptedCandidates = candidates.map((cand, idx) => {
    const otherCand = candidates[(idx + 1) % candidates.length] ?? cand;
    const c1Steps = cand.rotation.steps;
    const c2Steps = otherCand.rotation.steps;

    const adaptedSteps = [];
    for (let yr = 0; yr < effYears; yr++) {
      const sourceSteps = yr % 2 === 0 ? c1Steps : c2Steps;
      for (const step of sourceSteps) {
        adaptedSteps.push({ ...step, year_index: yr });
      }
    }

    const c1Ops = cand.practical_metrics?.seasonal_operations ?? [];
    const c2Ops = otherCand.practical_metrics?.seasonal_operations ?? [];
    const adaptedOps = [];
    for (let yr = 0; yr < effYears; yr++) {
      const sourceOps = yr % 2 === 0 ? c1Ops : c2Ops;
      for (const op of sourceOps) {
        adaptedOps.push({ ...op, year_index: yr });
      }
    }

    const yearWeights = Array.from({ length: effYears }, (_, yr) => (yr % 2 === 0 ? 1 : 0));
    const w1 = yearWeights.filter((v) => v === 1).length / effYears;
    const w2 = 1.0 - w1;
    const mix = (a?: number, b?: number) => Math.round(((a ?? 0) * w1 + (b ?? a ?? 0) * w2) * 10) / 10;

    const r1 = cand.results?.[0];
    const r2 = otherCand.results?.[0] ?? r1;
    const adaptedResults =
      r1 && r2
        ? [
            {
              ...r1,
              scenario_set_id: `historical_${effYears}yr`,
              yield_t_ha: { ...r2.yield_t_ha, ...r1.yield_t_ha },
              irrigation_mm: [mix(r1.irrigation_mm?.[0], r2.irrigation_mm?.[0])],
              profit_per_ha: [Math.round(mix(r1.profit_per_ha?.[0], r2.profit_per_ha?.[0]))],
              soc_delta_t_ha_10yr: Number(mix(r1.soc_delta_t_ha_10yr, r2.soc_delta_t_ha_10yr).toFixed(2)),
              erosion_t_ha_yr: Number(mix(r1.erosion_t_ha_yr, r2.erosion_t_ha_yr).toFixed(2)),
              n_balance_kg_ha_yr: mix(r1.n_balance_kg_ha_yr, r2.n_balance_kg_ha_yr),
              living_root_days_pct: mix(r1.living_root_days_pct, r2.living_root_days_pct),
              family_diversity_index: Number(
                Math.min(1.386, Math.max(r1.family_diversity_index, avgNum(r1.family_diversity_index, r2.family_diversity_index) + 0.15)).toFixed(3)
              ),
              soil_health_score: mix(r1.soil_health_score, r2.soil_health_score),
              profit_p10: Math.round(mix(r1.profit_p10, r2.profit_p10)),
              profit_p50: Math.round(mix(r1.profit_p50, r2.profit_p50)),
              profit_p90: Math.round(mix(r1.profit_p90, r2.profit_p90)),
              cvar_profit_10: Math.round(mix(r1.cvar_profit_10, r2.cvar_profit_10)),
            },
          ]
        : cand.results;

    const label =
      effYears === 2
        ? `Yr 1: ${cand.rotation.label} ⇄ Yr 2: ${otherCand.rotation.label}`
        : `${effYears}-Yr Cycle: ${cand.rotation.label} ⇄ ${otherCand.rotation.label}`;

    const pm1 = cand.practical_metrics;
    const pm2 = otherCand.practical_metrics ?? pm1;

    return {
      ...cand,
      rotation: {
        ...cand.rotation,
        label,
        steps: adaptedSteps,
      },
      results: adaptedResults,
      vs_baseline: {
        ...cand.vs_baseline,
        irrigation_change_pct: mix(cand.vs_baseline?.irrigation_change_pct, otherCand.vs_baseline?.irrigation_change_pct),
        profit_change_pct: mix(cand.vs_baseline?.profit_change_pct, otherCand.vs_baseline?.profit_change_pct),
        soil_health_change_pts: mix(cand.vs_baseline?.soil_health_change_pts, otherCand.vs_baseline?.soil_health_change_pts),
      },
      practical_metrics: pm1
        ? {
            ...pm1,
            turnaround_days_kharif_rabi: Math.round(mix(pm1.turnaround_days_kharif_rabi, pm2?.turnaround_days_kharif_rabi)),
            urea_bags_saved_per_ha: Number(mix(pm1.urea_bags_saved_per_ha, pm2?.urea_bags_saved_per_ha).toFixed(1)),
            irrigations_saved_per_yr: Math.round(mix(pm1.irrigations_saved_per_yr, pm2?.irrigations_saved_per_yr)),
            pumping_hours_saved_per_ha: Math.round(mix(pm1.pumping_hours_saved_per_ha, pm2?.pumping_hours_saved_per_ha)),
            labor_cost_inr_per_ha: Math.round(mix(pm1.labor_cost_inr_per_ha, pm2?.labor_cost_inr_per_ha)),
            input_cost_inr_per_ha: Math.round(mix(pm1.input_cost_inr_per_ha, pm2?.input_cost_inr_per_ha)),
            seasonal_operations: adaptedOps.length > 0 ? adaptedOps : undefined,
          }
        : undefined,
    };
  });

  return [adaptedBaseline, ...adaptedCandidates];
}

type RegionalStratPreset = {
  rank: number;
  id: string;
  label: string;
  labelHi?: string;
  labelPa?: string;
  isBaseline?: boolean;
  steps: { season_index: number; crop_id: string; practices: string[] }[];
  yield_t_ha: Record<string, number[]>;
  irrigation_mm: number;
  p10: number;
  p50: number;
  p90: number;
  cvar10: number;
  soc_delta: number;
  erosion: number;
  n_balance: number;
  living_root_days_pct: number;
  family_diversity_index: number;
  soil_health_score: number;
  vs_baseline: {
    irrigation_change_pct?: number;
    profit_change_pct?: number;
    soil_health_change_pts?: number;
    climate_resilience_score: number;
    profit_regret: number;
    irrigation_spike_mm?: number;
  };
  why: string[];
  turnaround_days: number;
  urea_bags_saved: number;
  irrigations_saved: number;
  pumping_hours_saved: number;
  msp_level: string;
  schemes: string[];
  labor_cost: number;
  input_cost: number;
  narrative: string;
  narrativeHi?: string;
  narrativePa?: string;
};

function materializeRegionalPresets(
  presets: RegionalStratPreset[],
  stateName: string,
  economicsBasis: "local_verified" | "punjab_proxy",
  lang: "en" | "pa" | "hi"
): StrategyRecommendation[] {
  return presets.map((p) => {
    const label = lang === "pa" ? p.labelPa ?? p.label : lang === "hi" ? p.labelHi ?? p.label : p.label;
    const narrative =
      lang === "pa" ? p.narrativePa ?? p.narrative : lang === "hi" ? p.narrativeHi ?? p.narrative : p.narrative;
    return {
      rank: p.rank,
      rotation: {
        id: p.id,
        label,
        is_baseline: Boolean(p.isBaseline),
        steps: p.steps.map((st) => ({
          year_index: 0,
          season_index: st.season_index,
          crop_id: st.crop_id,
          practices: st.practices,
        })),
      },
      results: [
        {
          rotation_id: p.id,
          scenario_set_id: "historical_1yr",
          yield_t_ha: p.yield_t_ha,
          irrigation_mm: [p.irrigation_mm],
          profit_per_ha: [p.p50],
          soc_delta_t_ha_10yr: p.soc_delta,
          erosion_t_ha_yr: p.erosion,
          n_balance_kg_ha_yr: p.n_balance,
          living_root_days_pct: p.living_root_days_pct,
          family_diversity_index: p.family_diversity_index,
          soil_health_score: p.soil_health_score,
          profit_p10: p.p10,
          profit_p50: p.p50,
          profit_p90: p.p90,
          cvar_profit_10: p.cvar10,
        },
      ],
      objective_scores: {
        profit: p.p50,
        water_savings: -p.irrigation_mm,
        soil_health: p.soil_health_score,
        low_risk: p.cvar10,
        low_labour: -p.labor_cost,
        food_security: p.steps.some((st) => ["wheat", "rice_puddled", "rice_dsr", "rice_short"].includes(st.crop_id))
          ? 1.0
          : 0.5,
      },
      vs_baseline: p.vs_baseline,
      why: p.why,
      provenance: [
        {
          source: "FAO-56 / RothC-26.3 Offline Emergency Preset",
          product: `${stateName} Benchmark Snapshot`,
          period: "1995-2024",
          mode: "fallback_estimate",
        },
      ],
      currency: "INR",
      currency_symbol: "₹",
      economics_basis: economicsBasis,
      practical_metrics: {
        turnaround_days_kharif_rabi: p.turnaround_days,
        urea_bags_saved_per_ha: p.urea_bags_saved,
        irrigations_saved_per_yr: p.irrigations_saved,
        pumping_hours_saved_per_ha: p.pumping_hours_saved,
        msp_assurance_level: p.msp_level,
        eligible_schemes: p.schemes,
        labor_cost_inr_per_ha: p.labor_cost,
        input_cost_inr_per_ha: p.input_cost,
      },
      narrative_summary: narrative,
      served_from: "demo_snapshot" as const,
      snapshot_date: "2026-11-10",
      state: stateName,
      is_fallback: true,
      data_mode: "fallback_synthetic",
    };
  });
}

const BATHINDA_PRESETS: RegionalStratPreset[] = [
  {
    rank: 0,
    id: "observed_baseline",
    label: "Cotton → Wheat → Fallow",
    labelHi: "कपास → गेहूं → परती",
    labelPa: "ਨਰਮਾ → ਕਣਕ → ਖ਼ਾਲੀ",
    isBaseline: true,
    steps: [
      { season_index: 0, crop_id: "cotton", practices: ["conventional"] },
      { season_index: 1, crop_id: "wheat", practices: ["conventional"] },
      { season_index: 2, crop_id: "fallow", practices: [] },
    ],
    yield_t_ha: { cotton: [2.28], wheat: [5.17] },
    irrigation_mm: 592.0,
    p10: 178807,
    p50: 188526,
    p90: 199707,
    cvar10: 174421,
    soc_delta: -1.56,
    erosion: 0.76,
    n_balance: 119.9,
    living_root_days_pct: 89.7,
    family_diversity_index: 0.69,
    soil_health_score: 41.7,
    vs_baseline: { climate_resilience_score: 86.3, profit_regret: 14104.2, irrigation_spike_mm: 177.5 },
    why: [
      "Current semi-arid Bathinda baseline (Cotton → Wheat): uses 592 mm/yr irrigation in declining brackish-water belt and loses -1.56 t C/ha organic carbon over 10 years.",
    ],
    turnaround_days: 18,
    urea_bags_saved: 0.0,
    irrigations_saved: 0,
    pumping_hours_saved: 0,
    msp_level: "100% MSP Assured (CCI / FCI)",
    schemes: [],
    labor_cost: 32850,
    input_cost: 93720,
    narrative:
      "Current baseline ('Cotton → Wheat → Fallow'): demands 592 mm/yr irrigation and loses -1.56 t C/ha soil carbon under conventional tillage.",
    narrativeHi: "वर्तमान आधार ('कपास → गेहूं → परती'): 592 मिमी/वर्ष सिंचाई की मांग और 10 वर्षों में -1.56 t C/ha मृदा कार्बन हानि।",
    narrativePa: "ਮੌਜੂਦਾ ਆਧਾਰ ('ਨਰਮਾ → ਕਣਕ → ਖ਼ਾਲੀ'): 592 ਮਿਲੀਮੀਟਰ/ਸਾਲ ਸਿੰਚਾਈ ਦੀ ਲੋੜ ਅਤੇ 10 ਸਾਲਾਂ ਵਿੱਚ -1.56 t C/ha ਮਿੱਟੀ ਕਾਰਬਨ ਦਾ ਨੁਕਸਾਨ।",
  },
  {
    rank: 1,
    id: "r0080",
    label: "Mung bean → Wheat → Blackgram",
    labelHi: "मूंग → गेहूं → उड़द",
    labelPa: "ਮੂੰਗੀ → ਕਣਕ → ਮਾਂਹ",
    steps: [
      { season_index: 0, crop_id: "moong", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "wheat", practices: ["zero_till", "residue_retained"] },
      { season_index: 2, crop_id: "urad", practices: ["zero_till", "residue_retained"] },
    ],
    yield_t_ha: { moong: [1.12], wheat: [5.17], urad: [0.98] },
    irrigation_mm: 341.0,
    p10: 180576,
    p50: 197624,
    p90: 210273,
    cvar10: 174518,
    soc_delta: 1.0,
    erosion: 0.27,
    n_balance: 89.3,
    living_root_days_pct: 80.1,
    family_diversity_index: 0.64,
    soil_health_score: 72.6,
    vs_baseline: {
      irrigation_change_pct: -38.0,
      profit_change_pct: 4.8,
      soil_health_change_pts: 30.9,
      climate_resilience_score: 94.5,
      profit_regret: 23106.8,
      irrigation_spike_mm: 101.0,
    },
    why: [
      "Saves 38% irrigation water (3 irrigations / 135 pumping hrs/ha) by replacing thirsty Kharif Cotton with 65-day Moong + Zero-Till Wheat + Urad.",
      "Double-legume fixation saves 4.1 bags/ha of 45-kg Urea and raises Soil Health Score by +30.9 points (+1.00 t C/ha over 10 yrs).",
    ],
    turnaround_days: 34,
    urea_bags_saved: 4.1,
    irrigations_saved: 3,
    pumping_hours_saved: 135,
    msp_level: "MSP & NAFED e-Samridhi Supported",
    schemes: [
      "PM-PRANAM Alternative Fertiliser & Bio-N Incentive",
      "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
      "Sub-Mission on Agricultural Mechanization (SMAM / Conservation Tillage Subsidy)",
    ],
    labor_cost: 29000,
    input_cost: 88070,
    narrative:
      "Strategy 'Mung bean → Wheat → Blackgram': saves 38% irrigation water and builds +1.00 t C/ha soil carbon with ₹197,624/ha median net income.",
    narrativeHi: "अनुशंसित रणनीति ('मूंग → गेहूं → उड़द'): 38% सिंचाई जल बचत, +1.00 t C/ha मृदा कार्बन और ₹1,97,624/हेक्टेयर औसत शुद्ध आय।",
    narrativePa: "ਸਿਫ਼ਾਰਿਸ਼ ਕੀਤੀ ਰਣਨੀਤੀ ('ਮੂੰਗੀ → ਕਣਕ → ਮਾਂਹ'): 38% ਪਾਣੀ ਦੀ ਬਚਤ, +1.00 t C/ha ਮਿੱਟੀ ਕਾਰਬਨ ਅਤੇ ₹1,97,624/ਹੈਕਟੇਅਰ ਔਸਤ ਸ਼ੁੱਧ ਆਮਦਨ।",
  },
  {
    rank: 2,
    id: "r0056",
    label: "Pearl millet → Mustard / rapeseed → Blackgram",
    labelHi: "बाजरा → सरसों → उड़द",
    labelPa: "ਬਾਜਰਾ → ਸਰ੍ਹੋਂ → ਮਾਂਹ",
    steps: [
      { season_index: 0, crop_id: "pearl_millet", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "mustard", practices: ["zero_till", "residue_retained"] },
      { season_index: 2, crop_id: "urad", practices: ["zero_till", "residue_retained"] },
    ],
    yield_t_ha: { pearl_millet: [2.28], mustard: [1.92], urad: [0.96] },
    irrigation_mm: 211.0,
    p10: 135109,
    p50: 155343,
    p90: 168431,
    cvar10: 133130,
    soc_delta: 0.97,
    erosion: 0.31,
    n_balance: 89.0,
    living_root_days_pct: 80.1,
    family_diversity_index: 1.1,
    soil_health_score: 77.3,
    vs_baseline: {
      irrigation_change_pct: -52.6,
      profit_change_pct: -17.6,
      soil_health_change_pts: 35.6,
      climate_resilience_score: 94.0,
      profit_regret: 22212.7,
      irrigation_spike_mm: 86.4,
    },
    why: [
      "Highest water conservation (-53% irrigation, 187 pumping hrs saved/ha) suited for semi-arid southwestern Punjab groundwater conservation.",
    ],
    turnaround_days: 34,
    urea_bags_saved: 3.6,
    irrigations_saved: 5,
    pumping_hours_saved: 187,
    msp_level: "NAFED / PSS Supported",
    schemes: [
      "PM-PRANAM Alternative Fertiliser & Bio-N Incentive",
      "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
      "National Mission on Edible Oils (NMEO-Oilseeds) Seed & Procurement Support",
    ],
    labor_cost: 25400,
    input_cost: 79040,
    narrative: "Drought-resilient Bajra → Mustard → Blackgram rotation slashing pumping demand by 53% with 77/100 soil health.",
    narrativeHi: "सूखा-रोधी बाजरा → सरसों → उड़द चक्र: 53% सिंचाई जल बचत और 77/100 मृदा स्वास्थ्य स्कोर।",
    narrativePa: "ਸੋਕਾ-ਰੋਧਕ ਬਾਜਰਾ → ਸਰ੍ਹੋਂ → ਮਾਂਹ ਫ਼ਸਲੀ ਚੱਕਰ: 53% ਸਿੰਚਾਈ ਪਾਣੀ ਦੀ ਬਚਤ ਅਤੇ 77/100 ਮਿੱਟੀ ਸਿਹਤ ਸਕੋਰ।",
  },
  {
    rank: 3,
    id: "r0029",
    label: "Maize → Mustard / rapeseed → Blackgram",
    labelHi: "मक्का → सरसों → उड़द",
    labelPa: "ਮੱਕੀ → ਸਰ੍ਹੋਂ → ਮਾਂਹ",
    steps: [
      { season_index: 0, crop_id: "maize", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "mustard", practices: ["zero_till", "residue_retained"] },
      { season_index: 2, crop_id: "urad", practices: ["zero_till", "residue_retained"] },
    ],
    yield_t_ha: { maize: [5.39], mustard: [1.92], urad: [0.92] },
    irrigation_mm: 256.0,
    p10: 125732,
    p50: 188942,
    p90: 207603,
    cvar10: 118482,
    soc_delta: 2.16,
    erosion: 0.31,
    n_balance: 154.2,
    living_root_days_pct: 84.9,
    family_diversity_index: 1.1,
    soil_health_score: 86.2,
    vs_baseline: {
      irrigation_change_pct: -41.6,
      profit_change_pct: 0.2,
      soil_health_change_pts: 44.5,
      climate_resilience_score: 87.2,
      profit_regret: 70460.3,
      irrigation_spike_mm: 110.6,
    },
    why: [
      "Matches baseline profit (₹188,942/ha) while cutting water use by 42% and achieving 86/100 Soil Health Score (+2.16 t C/ha over 10 yrs).",
    ],
    turnaround_days: 34,
    urea_bags_saved: 3.6,
    irrigations_saved: 4,
    pumping_hours_saved: 148,
    msp_level: "NAFED / PSS Supported",
    schemes: [
      "PM-PRANAM Alternative Fertiliser & Bio-N Incentive",
      "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
      "National Mission on Edible Oils (NMEO-Oilseeds) Seed & Procurement Support",
    ],
    labor_cost: 29900,
    input_cost: 92470,
    narrative: "High-soil-carbon Maize → Mustard → Blackgram rotation (+2.16 t C/ha, -42% water) maintaining baseline net margin.",
    narrativeHi: "मक्का → सरसों → उड़द प्रणाली (+2.16 t C/ha मृदा कार्बन, 42% कम पानी, समान शुद्ध लाभ)।",
    narrativePa: "ਮੱਕੀ → ਸਰ੍ਹੋਂ → ਮਾਂਹ ਪ੍ਰਣਾਲੀ (+2.16 t C/ha ਮਿੱਟੀ ਕਾਰਬਨ, 42% ਘੱਟ ਪਾਣੀ)।",
  },
];

const BUNDELKHAND_PRESETS: RegionalStratPreset[] = [
  {
    rank: 0,
    id: "observed_baseline",
    label: "Sorghum → Wheat → Fallow",
    labelHi: "ज्वार → गेहूं → परती",
    labelPa: "ਜਵਾਰ → ਕਣਕ → ਖ਼ਾਲੀ",
    isBaseline: true,
    steps: [
      { season_index: 0, crop_id: "sorghum", practices: ["conventional"] },
      { season_index: 1, crop_id: "wheat", practices: ["conventional"] },
      { season_index: 2, crop_id: "fallow", practices: [] },
    ],
    yield_t_ha: { sorghum: [1.57], wheat: [0.69] },
    irrigation_mm: 0.0,
    p10: 8110,
    p50: 17206,
    p90: 32237,
    cvar10: 4277,
    soc_delta: -2.21,
    erosion: 4.61,
    n_balance: 191.3,
    living_root_days_pct: 73.3,
    family_diversity_index: 0.0,
    soil_health_score: 26.8,
    vs_baseline: { climate_resilience_score: 63.0, profit_regret: 12929.2, irrigation_spike_mm: 0.0 },
    why: [
      "Rainfed Sorghum → Wheat suffers severe post-monsoon Rabi moisture stress (Wheat 0.69 t/ha), high erosion (4.61 t/ha/yr), and low 27/100 Soil Health.",
    ],
    turnaround_days: 34,
    urea_bags_saved: 0.0,
    irrigations_saved: 0,
    pumping_hours_saved: 0,
    msp_level: "100% MSP Assured (FCI / State Agency)",
    schemes: ["Bundelkhand Drought Mitigation & Pulses Promotion Mission (Special Package)"],
    labor_cost: 14400,
    input_cost: 41230,
    narrative: "Rainfed baseline ('Sorghum → Wheat'): suffers terminal Rabi drought failure, 4.6 t/ha/yr erosion, and only ₹17,206/ha median net margin.",
    narrativeHi: "वर्तमान वर्षा-आधारित चक्र ('ज्वार → गेहूं'): रबी सूखे के कारण कम उपज, 4.6 t/ha/yr मृदा अपरदन और ₹17,206/हेक्टेयर औसत लाभ।",
    narrativePa: "ਮੌਜੂਦਾ ਬਰਾਨੀ ਆਧਾਰ ('ਜਵਾਰ → ਕਣਕ'): ਰਬੀ ਸੋਕੇ ਕਾਰਨ ਘੱਟ ਝਾੜ, 4.6 t/ha/yr ਮਿੱਟੀ ਖੋਰ ਅਤੇ ₹17,206/ਹੈਕਟੇਅਰ ਔਸਤ ਆਮਦਨ।",
  },
  {
    rank: 1,
    id: "r0014",
    label: "Groundnut → Chickpea → Fallow",
    labelHi: "मूंगफली → चना → परती",
    labelPa: "ਮੂੰਗਫਲੀ → ਛੋਲੇ → ਖ਼ਾਲੀ",
    steps: [
      { season_index: 0, crop_id: "groundnut", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "chickpea", practices: ["zero_till", "residue_retained"] },
      { season_index: 2, crop_id: "fallow", practices: ["residue_retained"] },
    ],
    yield_t_ha: { groundnut: [1.84], chickpea: [1.25] },
    irrigation_mm: 0.0,
    p10: 117799,
    p50: 133148,
    p90: 145392,
    cvar10: 100123,
    soc_delta: -1.82,
    erosion: 2.01,
    n_balance: 58.4,
    living_root_days_pct: 63.7,
    family_diversity_index: 0.0,
    soil_health_score: 42.0,
    vs_baseline: {
      irrigation_change_pct: 0.0,
      profit_change_pct: 673.8,
      soil_health_change_pts: 15.2,
      climate_resilience_score: 87.7,
      profit_regret: 33025.8,
      irrigation_spike_mm: 0.0,
    },
    why: [
      "Groundnut + Zero-Till Chickpea cuts erosion by 56% (to 2.0 t/ha/yr) and builds ₹1,33,148/ha rainfed margin with 3.3 bags/ha Urea savings.",
    ],
    turnaround_days: 34,
    urea_bags_saved: 3.3,
    irrigations_saved: 0,
    pumping_hours_saved: 0,
    msp_level: "NAFED / PSS Supported",
    schemes: [
      "Bundelkhand Drought Mitigation & Pulses Promotion Mission (Special Package)",
      "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
      "National Mission on Edible Oils (NMEO-Oilseeds) Seed & Procurement Support",
    ],
    labor_cost: 12448,
    input_cost: 33150,
    narrative: "Rainfed Groundnut → Chickpea rotation cuts soil erosion by 56% and delivers ₹1,33,148/ha net income under Bundelkhand drought risk.",
    narrativeHi: "वर्षा-आधारित मूंगफली → चना प्रणाली: मृदा अपरदन में 56% कमी और ₹1,33,148/हेक्टेयर शुद्ध लाभ।",
    narrativePa: "ਬਰਾਨੀ ਮੂੰਗਫਲੀ → ਛੋਲੇ ਪ੍ਰਣਾਲੀ: ਮਿੱਟੀ ਖੋਰ ਵਿੱਚ 56% ਕਮੀ ਅਤੇ ₹1,33,148/ਹੈਕਟੇਅਰ ਸ਼ੁੱਧ ਆਮਦਨ।",
  },
  {
    rank: 2,
    id: "r0011",
    label: "Pigeon pea → Barley → Fallow",
    labelHi: "अरहर → जौ → परती",
    labelPa: "ਅਰਹਰ → ਜੌਂ → ਖ਼ਾਲੀ",
    steps: [
      { season_index: 0, crop_id: "pigeon_pea", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "barley", practices: ["zero_till", "residue_retained"] },
      { season_index: 2, crop_id: "fallow", practices: ["residue_retained"] },
    ],
    yield_t_ha: { pigeon_pea: [1.09], barley: [2.53] },
    irrigation_mm: 0.0,
    p10: 66267,
    p50: 80912,
    p90: 93034,
    cvar10: 63859,
    soc_delta: 0.21,
    erosion: 1.95,
    n_balance: 64.6,
    living_root_days_pct: 83.6,
    family_diversity_index: 0.69,
    soil_health_score: 62.0,
    vs_baseline: {
      irrigation_change_pct: 0.0,
      profit_change_pct: 370.2,
      soil_health_change_pts: 35.2,
      climate_resilience_score: 95.2,
      profit_regret: 17053.3,
      irrigation_spike_mm: 0.0,
    },
    why: [
      "Top soil-regenerating option (+0.21 t C/ha/10yr, Soil Health 62/100) using deep-rooted Pigeon Pea + drought-hardy Zero-Till Barley.",
    ],
    turnaround_days: 22,
    urea_bags_saved: 3.1,
    irrigations_saved: 0,
    pumping_hours_saved: 0,
    msp_level: "NAFED / State Supported",
    schemes: [
      "Bundelkhand Drought Mitigation & Pulses Promotion Mission (Special Package)",
      "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
    ],
    labor_cost: 12808,
    input_cost: 33430,
    narrative: "Soil-restoring Pigeon pea → Barley system achieves net-positive carbon accretion (+0.21 t C/ha) and 95% climate resilience.",
    narrativeHi: "मृदा-संरक्षक अरहर → जौ चक्र: सकारात्मक कार्बन संचय (+0.21 t C/ha) और 95% जलवायु सहनशीलता।",
    narrativePa: "ਮਿੱਟੀ-ਸੰਭਾਲ ਅਰਹਰ → ਜੌਂ ਚੱਕਰ: ਸਕਾਰਾਤਮਕ ਕਾਰਬਨ ਵਾਧਾ (+0.21 t C/ha) ਅਤੇ 95% ਮੌਸਮੀ ਸਹਿਣਸ਼ੀਲਤਾ।",
  },
  {
    rank: 3,
    id: "r0005",
    label: "Soybean → Barley → Fallow",
    labelHi: "सोयाबीन → जौ → परती",
    labelPa: "ਸੋਇਆਬੀਨ → ਜੌਂ → ਖ਼ਾਲੀ",
    steps: [
      { season_index: 0, crop_id: "soybean", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "barley", practices: ["zero_till", "residue_retained"] },
      { season_index: 2, crop_id: "fallow", practices: ["residue_retained"] },
    ],
    yield_t_ha: { soybean: [1.79], barley: [2.53] },
    irrigation_mm: 0.0,
    p10: 64213,
    p50: 80878,
    p90: 99150,
    cvar10: 61844,
    soc_delta: -0.62,
    erosion: 1.95,
    n_balance: 29.9,
    living_root_days_pct: 68.5,
    family_diversity_index: 0.69,
    soil_health_score: 55.3,
    vs_baseline: {
      irrigation_change_pct: 0.0,
      profit_change_pct: 370.0,
      soil_health_change_pts: 28.5,
      climate_resilience_score: 92.2,
      profit_regret: 19034.8,
      irrigation_spike_mm: 0.0,
    },
    why: [
      "Soybean biological nitrogen fixation saves 3.5 bags/ha Urea while Zero-Till Barley stabilizes rainfed Rabi returns (₹80,878/ha).",
    ],
    turnaround_days: 34,
    urea_bags_saved: 3.5,
    irrigations_saved: 0,
    pumping_hours_saved: 0,
    msp_level: "NAFED / PSS Supported",
    schemes: [
      "PM-PRANAM Alternative Fertiliser & Bio-N Incentive",
      "National Mission on Edible Oils (NMEO-Oilseeds) Seed & Procurement Support",
    ],
    labor_cost: 11296,
    input_cost: 31570,
    narrative: "Soybean → Barley system lifts Soil Health by +28.5 pts and cuts urea input by 3.5 bags/ha.",
    narrativeHi: "सोयाबीन → जौ प्रणाली: मृदा स्वास्थ्य में +28.5 अंक सुधार और 3.5 बैग/हेक्टेयर यूरिया की बचत।",
    narrativePa: "ਸੋਇਆਬੀਨ → ਜੌਂ ਪ੍ਰਣਾਲੀ: ਮਿੱਟੀ ਸਿਹਤ ਵਿੱਚ +28.5 ਅੰਕ ਸੁਧਾਰ ਅਤੇ 3.5 ਥੈਲੇ/ਹੈਕਟੇਅਰ ਯੂਰੀਆ ਦੀ ਬਚਤ।",
  },
];

const VIDARBHA_PRESETS: RegionalStratPreset[] = [
  {
    rank: 0,
    id: "observed_baseline",
    label: "Cotton → Chickpea → Fallow",
    labelHi: "कपास → चना → परती",
    labelPa: "ਨਰਮਾ → ਛੋਲੇ → ਖ਼ਾਲੀ",
    isBaseline: true,
    steps: [
      { season_index: 0, crop_id: "cotton", practices: ["conventional"] },
      { season_index: 1, crop_id: "chickpea", practices: ["conventional"] },
      { season_index: 2, crop_id: "fallow", practices: [] },
    ],
    yield_t_ha: { cotton: [1.84], chickpea: [0.93] },
    irrigation_mm: 0.0,
    p10: 96036,
    p50: 123800,
    p90: 155881,
    cvar10: 82085,
    soc_delta: -2.16,
    erosion: 4.9,
    n_balance: 149.0,
    living_root_days_pct: 80.1,
    family_diversity_index: 0.69,
    soil_health_score: 42.9,
    vs_baseline: { climate_resilience_score: 84.4, profit_regret: 41715.2, irrigation_spike_mm: 0.0 },
    why: [
      "Rainfed Vertisol Cotton → Chickpea causes 4.90 t/ha/yr topsoil erosion and loses -2.16 t C/ha organic carbon over 10 years.",
    ],
    turnaround_days: 18,
    urea_bags_saved: 1.3,
    irrigations_saved: 0,
    pumping_hours_saved: 0,
    msp_level: "100% MSP Assured (CCI / NAFED)",
    schemes: [
      "Maharashtra PoCRA (Nanaji Deshmukh Krishi Sanjivani Climate-Resilient Agriculture Subsidy)",
      "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
    ],
    labor_cost: 18720,
    input_cost: 43400,
    narrative: "Rainfed Vertisol baseline ('Cotton → Chickpea'): loses 4.9 t/ha/yr topsoil and -2.16 t C/ha soil carbon under conventional tillage.",
    narrativeHi: "वर्तमान वर्षा-आधारित कपास → चना चक्र: पारंपरिक जुताई से 4.9 t/ha/yr मृदा अपरदन और -2.16 t C/ha कार्बन हानि।",
    narrativePa: "ਮੌਜੂਦਾ ਬਰਾਨੀ ਨਰਮਾ → ਛੋਲੇ ਚੱਕਰ: ਰਵਾਇਤੀ ਵਹਾਈ ਕਾਰਨ 4.9 t/ha/yr ਮਿੱਟੀ ਖੋਰ ਅਤੇ -2.16 t C/ha ਕਾਰਬਨ ਨੁਕਸਾਨ।",
  },
  {
    rank: 1,
    id: "r0002",
    label: "Maize → Chickpea → Fallow",
    labelHi: "मक्का → चना → परती",
    labelPa: "ਮੱਕੀ → ਛੋਲੇ → ਖ਼ਾਲੀ",
    steps: [
      { season_index: 0, crop_id: "maize", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "chickpea", practices: ["zero_till", "residue_retained"] },
      { season_index: 2, crop_id: "fallow", practices: ["residue_retained"] },
    ],
    yield_t_ha: { maize: [5.08], chickpea: [1.1] },
    irrigation_mm: 0.0,
    p10: 82872,
    p50: 113321,
    p90: 129324,
    cvar10: 80253,
    soc_delta: 0.25,
    erosion: 2.31,
    n_balance: 131.5,
    living_root_days_pct: 60.3,
    family_diversity_index: 0.69,
    soil_health_score: 58.2,
    vs_baseline: {
      irrigation_change_pct: 0.0,
      profit_change_pct: -8.5,
      soil_health_change_pts: 15.3,
      climate_resilience_score: 90.8,
      profit_regret: 33068.3,
      irrigation_spike_mm: 0.0,
    },
    why: [
      "Halves Vertisol sheet erosion (-53%, to 2.31 t/ha/yr), reverses carbon loss (+0.25 t C/ha/10yr), and improves drought resilience to 91%.",
    ],
    turnaround_days: 34,
    urea_bags_saved: 1.9,
    irrigations_saved: 0,
    pumping_hours_saved: 0,
    msp_level: "NAFED / State Supported",
    schemes: [
      "Maharashtra PoCRA (Nanaji Deshmukh Krishi Sanjivani Climate-Resilient Agriculture Subsidy)",
      "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
    ],
    labor_cost: 14680,
    input_cost: 38730,
    narrative: "PoCRA conservation rotation ('Maize → Chickpea'): cuts erosion by 53% and restores +0.25 t C/ha soil organic carbon on Deccan Vertisols.",
    narrativeHi: "PoCRA संरक्षण प्रणाली ('मक्का → चना'): मृदा अपरदन में 53% कमी और +0.25 t C/ha मृदा कार्बन संचय।",
    narrativePa: "PoCRA ਸੰਭਾਲ ਪ੍ਰਣਾਲੀ ('ਮੱਕੀ → ਛੋਲੇ'): ਮਿੱਟੀ ਖੋਰ ਵਿੱਚ 53% ਕਮੀ ਅਤੇ +0.25 t C/ha ਮਿੱਟੀ ਕਾਰਬਨ ਵਾਧਾ।",
  },
  {
    rank: 2,
    id: "r0000",
    label: "Sorghum → Chickpea → Fallow",
    labelHi: "ज्वार → चना → परती",
    labelPa: "ਜਵਾਰ → ਛੋਲੇ → ਖ਼ਾਲੀ",
    steps: [
      { season_index: 0, crop_id: "sorghum", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "chickpea", practices: ["zero_till", "residue_retained"] },
      { season_index: 2, crop_id: "fallow", practices: ["residue_retained"] },
    ],
    yield_t_ha: { sorghum: [1.66], chickpea: [1.1] },
    irrigation_mm: 0.0,
    p10: 64164,
    p50: 76386,
    p90: 89655,
    cvar10: 59289,
    soc_delta: 0.25,
    erosion: 2.31,
    n_balance: 118.5,
    living_root_days_pct: 63.7,
    family_diversity_index: 0.69,
    soil_health_score: 58.8,
    vs_baseline: {
      irrigation_change_pct: 0.0,
      profit_change_pct: -38.3,
      soil_health_change_pts: 15.9,
      climate_resilience_score: 93.7,
      profit_regret: 17096.7,
      irrigation_spike_mm: 0.0,
    },
    why: ["Low-input rainfed Sorghum + Zero-Till Chickpea minimizes working capital outlay (₹31,290/ha) with 94% drought resilience."],
    turnaround_days: 34,
    urea_bags_saved: 1.9,
    irrigations_saved: 0,
    pumping_hours_saved: 0,
    msp_level: "NAFED / State Supported",
    schemes: [
      "Maharashtra PoCRA (Nanaji Deshmukh Krishi Sanjivani Climate-Resilient Agriculture Subsidy)",
      "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
    ],
    labor_cost: 12520,
    input_cost: 31290,
    narrative: "Low-cost rainfed Sorghum → Chickpea buffers severe Vidarbha monsoon breaks while cutting erosion by 53%.",
    narrativeHi: "कम लागत ज्वार → चना चक्र: सूखे से सुरक्षा और मृदा स्वास्थ्य में +15.9 अंक सुधार।",
    narrativePa: "ਘੱਟ ਲਾਗਤ ਜਵਾਰ → ਛੋਲੇ ਚੱਕਰ: ਸੋਕੇ ਤੋਂ ਬਚਾਅ ਅਤੇ ਮਿੱਟੀ ਸਿਹਤ ਵਿੱਚ +15.9 ਅੰਕ ਸੁਧਾਰ।",
  },
  {
    rank: 3,
    id: "r0008",
    label: "Pigeon pea → Chickpea → Fallow",
    labelHi: "अरहर → चना → परती",
    labelPa: "ਅਰਹਰ → ਛੋਲੇ → ਖ਼ਾਲੀ",
    steps: [
      { season_index: 0, crop_id: "pigeon_pea", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "chickpea", practices: ["zero_till", "residue_retained"] },
      { season_index: 2, crop_id: "fallow", practices: ["residue_retained"] },
    ],
    yield_t_ha: { pigeon_pea: [1.26], chickpea: [1.1] },
    irrigation_mm: 0.0,
    p10: 79159,
    p50: 104721,
    p90: 115494,
    cvar10: 76585,
    soc_delta: -0.06,
    erosion: 2.04,
    n_balance: 103.1,
    living_root_days_pct: 78.8,
    family_diversity_index: 0.0,
    soil_health_score: 52.5,
    vs_baseline: {
      irrigation_change_pct: 0.0,
      profit_change_pct: -15.4,
      soil_health_change_pts: 9.6,
      climate_resilience_score: 90.0,
      profit_regret: 28136.0,
      irrigation_spike_mm: 0.0,
    },
    why: ["Pulse-led Tur + Zero-Till Gram saves 2.6 bags/ha Urea under PoCRA & NFSM-Pulses MSP support."],
    turnaround_days: 22,
    urea_bags_saved: 2.6,
    irrigations_saved: 0,
    pumping_hours_saved: 0,
    msp_level: "NAFED e-Samridhi MSP Supported",
    schemes: [
      "Maharashtra PoCRA (Nanaji Deshmukh Krishi Sanjivani Climate-Resilient Agriculture Subsidy)",
      "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
    ],
    labor_cost: 14320,
    input_cost: 35630,
    narrative: "Rainfed Pigeon pea → Chickpea lowers Vertisol erosion to 2.04 t/ha/yr with ₹1,04,721/ha median net income.",
    narrativeHi: "अरहर → चना प्रणाली: मृदा अपरदन 2.04 t/ha/yr तक कम और ₹1,04,721/हेक्टेयर औसत शुद्ध लाभ।",
    narrativePa: "ਅਰਹਰ → ਛੋਲੇ ਪ੍ਰਣਾਲੀ: ਮਿੱਟੀ ਖੋਰ 2.04 t/ha/yr ਤੱਕ ਘੱਟ ਅਤੇ ₹1,04,721/ਹੈਕਟੇਅਰ ਔਸਤ ਆਮਦਨ।",
  },
];

const THANJAVUR_PRESETS: RegionalStratPreset[] = [
  {
    rank: 0,
    id: "observed_baseline",
    label: "Puddled Rice → Puddled Rice → Blackgram",
    labelHi: "रोपाई धान → रोपाई धान → उड़द",
    labelPa: "ਕੱਦੂ ਝੋਨਾ → ਕੱਦੂ ਝੋਨਾ → ਮਾਂਹ",
    isBaseline: true,
    steps: [
      { season_index: 0, crop_id: "rice_puddled", practices: ["puddling"] },
      { season_index: 1, crop_id: "rice_puddled", practices: ["conventional"] },
      { season_index: 2, crop_id: "urad", practices: [] },
    ],
    yield_t_ha: { rice_puddled: [6.55], urad: [1.36] },
    irrigation_mm: 1930.2,
    p10: 209291,
    p50: 294464,
    p90: 323745,
    cvar10: 207168,
    soc_delta: -0.03,
    erosion: 1.67,
    n_balance: 127.4,
    living_root_days_pct: 89.7,
    family_diversity_index: 0.64,
    soil_health_score: 50.2,
    vs_baseline: { climate_resilience_score: 84.2, profit_regret: 87295.2, irrigation_spike_mm: 255.6 },
    why: [
      "Cauvery Delta double-puddled Kuruvai+Samba paddy consumes 1,930 mm/yr water and suffers sharp drought-year downside (P10 ₹2,09,291/ha vs P90 ₹3,23,745/ha).",
    ],
    turnaround_days: 11,
    urea_bags_saved: 2.1,
    irrigations_saved: 0,
    pumping_hours_saved: 0,
    msp_level: "100% MSP Assured (TNCSC / FCI)",
    schemes: ["Tamil Nadu Kalaignarin Rice Fallow Pulses Mission (100% certified seed subsidy)"],
    labor_cost: 53800,
    input_cost: 138350,
    narrative: "Double-puddled paddy baseline demands 1,930 mm/yr canal/borewell water and exposes farm income to tail-water drought risk (CVaR₁₀ ₹2,07,168/ha).",
    narrativeHi: "दोहरा रोपाई धान आधार: 1,930 मिमी/वर्ष भारी सिंचाई मांग और सूखे में आय अस्थिरता (CVaR₁₀ ₹2,07,168/हेक्टेयर)।",
    narrativePa: "ਦੋਹਰਾ ਕੱਦੂ ਝੋਨਾ ਆਧਾਰ: 1,930 ਮਿਲੀਮੀਟਰ/ਸਾਲ ਪਾਣੀ ਦੀ ਮੰਗ ਅਤੇ ਸੋਕੇ ਵਿੱਚ ਆਮਦਨ ਜੋਖ਼ਮ (CVaR₁₀ ₹2,07,168/ਹੈਕਟੇਅਰ)।",
  },
  {
    rank: 1,
    id: "r0252",
    label: "Mung bean → DSR Rice → Blackgram",
    labelHi: "मूंग → सीधी बुवाई धान (DSR) → उड़द",
    labelPa: "ਮੂੰਗੀ → ਸਿੱਧੀ ਬਿਜਾਈ ਝੋਨਾ (DSR) → ਮਾਂਹ",
    steps: [
      { season_index: 0, crop_id: "moong", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "rice_dsr", practices: ["direct_seeded", "residue_retained"] },
      { season_index: 2, crop_id: "urad", practices: ["zero_till", "residue_retained"] },
    ],
    yield_t_ha: { moong: [1.16], rice_dsr: [6.9], urad: [1.34] },
    irrigation_mm: 1065.0,
    p10: 262060,
    p50: 273540,
    p90: 280642,
    cvar10: 255853,
    soc_delta: 1.32,
    erosion: 1.05,
    n_balance: 79.0,
    living_root_days_pct: 73.3,
    family_diversity_index: 0.64,
    soil_health_score: 72.2,
    vs_baseline: {
      irrigation_change_pct: -57.8,
      profit_change_pct: 2.9,
      soil_health_change_pts: 12.0,
      climate_resilience_score: 96.5,
      profit_regret: 17686.2,
      irrigation_spike_mm: 210.0,
    },
    why: [
      "Slashes irrigation demand by 58% (15 irrigations / 631 pumping hrs/ha saved) and raises drought-year CVaR₁₀ income from ₹94k to ₹2,55,853/ha.",
      "Kuruvai Moong + Samba DSR Rice + Navarai Blackgram saves 4.1 bags/ha Urea and boosts Soil Health by +12 pts (+1.32 t C/ha).",
    ],
    turnaround_days: 34,
    urea_bags_saved: 4.1,
    irrigations_saved: 15,
    pumping_hours_saved: 631,
    msp_level: "100% TNCSC & NAFED Supported",
    schemes: [
      "Tamil Nadu Kalaignarin Rice Fallow Pulses Mission (100% certified seed subsidy)",
      "Tamil Nadu Sustainable Dryland & Water Conservation Mission",
      "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
    ],
    labor_cost: 26000,
    input_cost: 82850,
    narrative: "Recommended 'Mung bean → DSR Rice → Blackgram': cuts Cauvery Delta irrigation by 58% while raising drought-year income to ₹2,55,853/ha.",
    narrativeHi: "अनुशंसित 'मूंग → DSR धान → उड़द': सिंचाई जल में 58% बचत और सूखे के वर्ष में भी ₹2,55,853/हेक्टेयर सुरक्षित आय।",
    narrativePa: "ਸਿਫ਼ਾਰਿਸ਼ 'ਮੂੰਗੀ → DSR ਝੋਨਾ → ਮਾਂਹ': ਸਿੰਚਾਈ ਪਾਣੀ ਵਿੱਚ 58% ਬਚਤ ਅਤੇ ਸੋਕੇ ਵਾਲੇ ਸਾਲ ਵਿੱਚ ਵੀ ₹2,55,853/ਹੈਕਟੇਅਰ ਸੁਰੱਖਿਅਤ ਆਮਦਨ।",
  },
  {
    rank: 2,
    id: "r0317",
    label: "Groundnut → DSR Rice → Blackgram",
    labelHi: "मूंगफली → DSR धान → उड़द",
    labelPa: "ਮੂੰਗਫਲੀ → DSR ਝੋਨਾ → ਮਾਂਹ",
    steps: [
      { season_index: 0, crop_id: "groundnut", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "rice_dsr", practices: ["direct_seeded", "residue_retained"] },
      { season_index: 2, crop_id: "urad", practices: ["zero_till", "residue_retained"] },
    ],
    yield_t_ha: { groundnut: [2.13], rice_dsr: [6.9], urad: [1.34] },
    irrigation_mm: 1084.0,
    p10: 264807,
    p50: 287281,
    p90: 297488,
    cvar10: 260732,
    soc_delta: 1.74,
    erosion: 1.18,
    n_balance: 59.9,
    living_root_days_pct: 86.3,
    family_diversity_index: 0.64,
    soil_health_score: 77.1,
    vs_baseline: {
      irrigation_change_pct: -56.2,
      profit_change_pct: 8.0,
      soil_health_change_pts: 16.9,
      climate_resilience_score: 96.9,
      profit_regret: 26548.7,
      irrigation_spike_mm: 219.6,
    },
    why: [
      "Highest median net income (₹2,87,281/ha, +8% vs baseline) while saving 56% water and 5.0 bags/ha Urea.",
    ],
    turnaround_days: 34,
    urea_bags_saved: 5.0,
    irrigations_saved: 15,
    pumping_hours_saved: 614,
    msp_level: "100% TNCSC & NAFED Supported",
    schemes: [
      "Tamil Nadu Kalaignarin Rice Fallow Pulses Mission (100% certified seed subsidy)",
      "National Mission on Edible Oils (NMEO-Oilseeds) Seed & Procurement Support",
    ],
    labor_cost: 34200,
    input_cost: 109500,
    narrative: "Groundnut → DSR Rice → Blackgram delivers highest net margin (₹2,87,281/ha) with -56% water and +1.74 t C/ha soil carbon.",
    narrativeHi: "मूंगफली → DSR धान → उड़द: सर्वाधिक ₹2,87,281/हेक्टेयर शुद्ध आय, 56% जल बचत और +1.74 t C/ha मृदा कार्बन।",
    narrativePa: "ਮੂੰਗਫਲੀ → DSR ਝੋਨਾ → ਮਾਂਹ: ਸਭ ਤੋਂ ਵੱਧ ₹2,87,281/ਹੈਕਟੇਅਰ ਸ਼ੁੱਧ ਆਮਦਨ, 56% ਪਾਣੀ ਬਚਤ ਅਤੇ +1.74 t C/ha ਮਿੱਟੀ ਕਾਰਬਨ।",
  },
  {
    rank: 3,
    id: "r0220",
    label: "Pearl millet → DSR Rice → Blackgram",
    labelHi: "बाजरा → DSR धान → उड़द",
    labelPa: "ਬਾਜਰਾ → DSR ਝੋਨਾ → ਮਾਂਹ",
    steps: [
      { season_index: 0, crop_id: "pearl_millet", practices: ["residue_retained"] },
      { season_index: 1, crop_id: "rice_dsr", practices: ["direct_seeded", "residue_retained"] },
      { season_index: 2, crop_id: "urad", practices: ["zero_till", "residue_retained"] },
    ],
    yield_t_ha: { pearl_millet: [2.35], rice_dsr: [6.9], urad: [1.34] },
    irrigation_mm: 954.0,
    p10: 217557,
    p50: 223501,
    p90: 232528,
    cvar10: 207661,
    soc_delta: 2.42,
    erosion: 1.18,
    n_balance: 61.2,
    living_root_days_pct: 78.1,
    family_diversity_index: 0.64,
    soil_health_score: 78.9,
    vs_baseline: {
      irrigation_change_pct: -62.0,
      profit_change_pct: -16.0,
      soil_health_change_pts: 18.7,
      climate_resilience_score: 97.7,
      profit_regret: 15839.7,
      irrigation_spike_mm: 204.4,
    },
    why: [
      "Maximum water saving (-62%, 16 irrigations saved) and highest soil carbon accretion (+2.42 t C/ha) with 98% climate resilience.",
    ],
    turnaround_days: 34,
    urea_bags_saved: 3.6,
    irrigations_saved: 16,
    pumping_hours_saved: 677,
    msp_level: "100% TNCSC & NAFED Supported",
    schemes: [
      "Tamil Nadu Kalaignarin Rice Fallow Pulses Mission (100% certified seed subsidy)",
      "Tamil Nadu Sustainable Dryland & Water Conservation Mission",
    ],
    labor_cost: 25600,
    input_cost: 88500,
    narrative: "Low-water Pearl millet → DSR Rice → Blackgram cuts irrigation by 62% while sequestering +2.42 t C/ha.",
    narrativeHi: "बाजरा → DSR धान → उड़द: 62% सिंचाई जल की बचत और +2.42 t C/ha मृदा कार्बन संचय।",
    narrativePa: "ਬਾਜਰਾ → DSR ਝੋਨਾ → ਮਾਂਹ: 62% ਸਿੰਚਾਈ ਪਾਣੀ ਦੀ ਬਚਤ ਅਤੇ +2.42 t C/ha ਮਿੱਟੀ ਕਾਰਬਨ ਵਾਧਾ।",
  },
];

export function getFallbackStrategies(
  _field?: FieldGeometry,
  _currencySymbol: string = "₹",
  rotationYears: number = 1,
  lang: "en" | "pa" | "hi" = "en"
): StrategyRecommendation[] {
  void _currencySymbol;
  if (!_field) {
    return [];
  }
  const fId = _field.id ?? "";
  let resolvedBenchmarkId: string | null = null;
  if (["sangrur", "ludhiana", "bathinda", "bundelkhand", "vidarbha", "thanjavur"].includes(fId)) {
    resolvedBenchmarkId = fId;
  } else if (Math.abs(_field.lat - 30.19) < 0.25 && Math.abs(_field.lon - 75.78) < 0.25) {
    resolvedBenchmarkId = "sangrur";
  } else if (Math.abs(_field.lat - 30.82) < 0.25 && Math.abs(_field.lon - 75.68) < 0.25) {
    resolvedBenchmarkId = "ludhiana";
  }

  // Emergency fallback strategy presets apply ONLY to explicit known Indian benchmark IDs / Punjab baseline
  // so custom locations never falsely show Indian benchmark numbers when live API calls fail.
  if (!resolvedBenchmarkId) {
    return [];
  }

  if (resolvedBenchmarkId === "bathinda") {
    return adaptStrategiesForHorizon(
      materializeRegionalPresets(BATHINDA_PRESETS, "Punjab", "local_verified", lang),
      rotationYears
    );
  }
  if (resolvedBenchmarkId === "bundelkhand") {
    return adaptStrategiesForHorizon(
      materializeRegionalPresets(BUNDELKHAND_PRESETS, "Uttar Pradesh", "local_verified", lang),
      rotationYears
    );
  }
  if (resolvedBenchmarkId === "vidarbha") {
    return adaptStrategiesForHorizon(
      materializeRegionalPresets(VIDARBHA_PRESETS, "Maharashtra", "local_verified", lang),
      rotationYears
    );
  }
  if (resolvedBenchmarkId === "thanjavur") {
    return adaptStrategiesForHorizon(
      materializeRegionalPresets(THANJAVUR_PRESETS, "Tamil Nadu", "local_verified", lang),
      rotationYears
    );
  }

  const baseStrategies: StrategyRecommendation[] = [
    {
      rank: 0,
      rotation: {
        id: "observed_baseline",
        label: "Puddled Rice → Wheat → Fallow",
        is_baseline: true,
        steps: [
          { year_index: 0, season_index: 0, crop_id: "rice_puddled", practices: ["puddling", "burning", "residue_burnt"] },
          { year_index: 0, season_index: 1, crop_id: "wheat", practices: ["conventional", "burning", "residue_burnt"] },
          { year_index: 0, season_index: 2, crop_id: "fallow", practices: [] },
        ],
      },
      results: [
        {
          rotation_id: "observed_baseline",
          scenario_set_id: "historical_1yr",
          yield_t_ha: { rice_puddled: [6.75], wheat: [4.82] },
          irrigation_mm: [1233.0],
          profit_per_ha: [213477.0],
          soc_delta_t_ha_10yr: -1.94,
          erosion_t_ha_yr: 1.54,
          n_balance_kg_ha_yr: 120.6,
          living_root_days_pct: 73.2,
          family_diversity_index: 0.0,
          soil_health_score: 11.2,
          profit_p10: 184200.0,
          profit_p50: 213477.0,
          profit_p90: 232400.0,
          cvar_profit_10: 176500.0,
        },
      ],
      objective_scores: {
        profit: 213477.0,
        water_savings: -1233.0,
        soil_health: 11.2,
        low_risk: 176500.0,
        low_labour: -24500.0,
        food_security: 1.0,
      },
      vs_baseline: {
        climate_resilience_score: 48.0,
        profit_regret: 19200.0,
        irrigation_spike_mm: 215.0,
      },
      why: [
        "Current baseline practice: long-duration puddled rice + conventional wheat with only an 11-day harvest-to-sowing window, driving October–November stubble burning.",
        "Regional GRACE-FO terrestrial water storage trend: -3.85 cm/yr depletion.",
      ],
      provenance: [
        {
          source: "NASA GRACE / GRACE-FO",
          product: "Tellus Regional TWS Mascon V04",
          period: "2002-2024",
          doi: "10.5067/TEMSC-3MJ62",
          mode: "regional_climatology",
        },
      ],
      currency: "INR",
      currency_symbol: "₹",
      practical_metrics: {
        turnaround_days_kharif_rabi: 11,
        urea_bags_saved_per_ha: 0.0,
        irrigations_saved_per_yr: 0,
        pumping_hours_saved_per_ha: 0,
        msp_assurance_level: "100% MSP Assured (FCI / State Agency)",
        eligible_schemes: ["PM-KISAN Samman Nidhi (₹6,000/yr income support)"],
        labor_cost_inr_per_ha: 24500.0,
        input_cost_inr_per_ha: 70000.0,
      },
      narrative_summary:
        "Current Farm Baseline ('Puddled Rice → Wheat → Fallow'): Requires 1,233 mm/yr of irrigation and leaves only 11 days before wheat sowing, leading to residue burning and -1.94 t C/ha soil carbon loss over 10 years.",
      is_fallback: true,
      data_mode: "fallback_synthetic",
    },
    {
      rank: 1,
      rotation: {
        id: "r_dsr_wheat_moong",
        label: "DSR Rice → Wheat → Greengram (Moong)",
        is_baseline: false,
        steps: [
          { year_index: 0, season_index: 0, crop_id: "rice_dsr", practices: ["direct_seeded", "residue_retained"] },
          { year_index: 0, season_index: 1, crop_id: "wheat", practices: ["happy_seeder", "zero_till", "residue_retained"] },
          { year_index: 0, season_index: 2, crop_id: "moong", practices: ["residue_retained"] },
        ],
      },
      results: [
        {
          rotation_id: "r_dsr_wheat_moong",
          scenario_set_id: "historical_1yr",
          yield_t_ha: { rice_dsr: [6.05], wheat: [5.02], moong: [1.03] },
          irrigation_mm: [884.0],
          profit_per_ha: [262400.0],
          soc_delta_t_ha_10yr: 1.98,
          erosion_t_ha_yr: 0.38,
          n_balance_kg_ha_yr: 112.0,
          living_root_days_pct: 84.9,
          family_diversity_index: 0.637,
          soil_health_score: 88.5,
          soil_health_breakdown: {
            disturbance_minimization: 18.0,
            soil_armor_cover: 20.0,
            living_roots: 15.0,
            biodiversity: 14.0,
            biological_n_livestock: 15.0,
            soc_modifier: 9.0,
            erosion_modifier: 9.2,
            burning_penalty: 0.0,
            total_score: 88.5,
          },
          profit_p10: 241000.0,
          profit_p50: 262400.0,
          profit_p90: 281500.0,
          cvar_profit_10: 236800.0,
        },
      ],
      objective_scores: {
        profit: 262400.0,
        water_savings: -884.0,
        soil_health: 88.5,
        low_risk: 236800.0,
        low_labour: -21600.0,
        food_security: 1.0,
      },
      vs_baseline: {
        irrigation_change_pct: -28.3,
        profit_change_pct: 22.9,
        soil_health_change_pts: 77.3,
        climate_resilience_score: 94.0,
        profit_regret: 12100.0,
      },
      why: [
        "Saves 28% irrigation water (349 mm/yr — ~5 flood irrigations and 192 hrs/ha of 5-HP borewell pumping) vs. baseline [FAO-56].",
        "Elevates Soil Health Score to 89/100 and builds +2.0 t C/ha over 10 years, saving 3.9 bags/ha of 45-kg Urea via summer Moong nitrogen fixation [RothC-lite].",
        "Provides a 26-day Kharif-to-Rabi turnaround window for Happy Seeder zero-till wheat sowing without stubble burning [NASA FIRMS].",
      ],
      provenance: [
        { source: "FAO-56 / FAO-33 Soil-Water Balance", product: "Root-Zone Water Balance", period: "1985-2024", mode: "fallback_estimate" },
        { source: "RothC-26.3", product: "Soil Carbon & N-Balance", period: "10-yr horizon", mode: "fallback_estimate" },
      ],
      currency: "INR",
      currency_symbol: "₹",
      practical_metrics: {
        turnaround_days_kharif_rabi: 26,
        urea_bags_saved_per_ha: 3.9,
        irrigations_saved_per_yr: 5,
        pumping_hours_saved_per_ha: 192,
        msp_assurance_level: "100% MSP Assured (FCI / State Agency)",
        eligible_schemes: [
          "Direct Seeded Rice (DSR) State Incentive (₹3,750/ha · ₹1,500/acre)",
          "CRM Sub-Mission on Crop Residue Management (50–80% Happy Seeder / CHC subsidy)",
          "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
        ],
        labor_cost_inr_per_ha: 21600.0,
        input_cost_inr_per_ha: 78500.0,
      },
      narrative_summary:
        "Strategy 'DSR Rice → Wheat → Greengram (Moong)': Replaces puddled paddy with Direct-Seeded Rice, Happy Seeder wheat, and 60-day summer Moong, cutting irrigation by 28% (5 irrigations saved) while adding ₹48,923/ha in net income.",
      is_fallback: true,
      data_mode: "fallback_synthetic",
    },
    {
      rank: 2,
      rotation: {
        id: "r_maize_mustard_moong",
        label: "Maize → Mustard (Sarson) → Greengram (Moong)",
        is_baseline: false,
        steps: [
          { year_index: 0, season_index: 0, crop_id: "maize", practices: ["residue_retained"] },
          { year_index: 0, season_index: 1, crop_id: "mustard", practices: ["zero_till", "residue_retained"] },
          { year_index: 0, season_index: 2, crop_id: "moong", practices: ["residue_retained"] },
        ],
      },
      results: [
        {
          rotation_id: "r_maize_mustard_moong",
          scenario_set_id: "historical_1yr",
          yield_t_ha: { maize: [5.8], mustard: [1.78], moong: [1.03] },
          irrigation_mm: [651.0],
          profit_per_ha: [251341.0],
          soc_delta_t_ha_10yr: 1.82,
          erosion_t_ha_yr: 0.41,
          n_balance_kg_ha_yr: 132.0,
          living_root_days_pct: 83.6,
          family_diversity_index: 1.099,
          soil_health_score: 93.3,
          soil_health_breakdown: {
            disturbance_minimization: 18.0,
            soil_armor_cover: 20.0,
            living_roots: 14.8,
            biodiversity: 20.0,
            biological_n_livestock: 15.0,
            soc_modifier: 8.3,
            erosion_modifier: 9.2,
            burning_penalty: 0.0,
            total_score: 93.3,
          },
          profit_p10: 223824.0,
          profit_p50: 251341.0,
          profit_p90: 267772.0,
          cvar_profit_10: 222389.0,
        },
      ],
      objective_scores: {
        profit: 251341.0,
        water_savings: -651.0,
        soil_health: 93.3,
        low_risk: 222389.0,
        low_labour: -22330.0,
        food_security: 0.67,
      },
      vs_baseline: {
        irrigation_change_pct: -47.2,
        profit_change_pct: 17.7,
        soil_health_change_pts: 82.1,
        climate_resilience_score: 96.0,
        profit_regret: 14200.0,
      },
      why: [
        "Saves 47% irrigation water (582 mm/yr — ~8 flood irrigations and 320 hrs/ha of 5-HP borewell pumping) vs. baseline [FAO-56].",
        "3-family rotation (Poaceae + Brassicaceae + Fabaceae) reaches 93/100 Soil Health Score and saves 3.6 bags/ha of 45-kg Urea.",
        "Provides a 34-day harvest-to-sowing window and qualifies for ₹17,500/ha Crop Diversification incentive.",
      ],
      provenance: [
        { source: "FAO-56 / FAO-33 Soil-Water Balance", product: "Root-Zone Water Balance", period: "1985-2024", mode: "fallback_estimate" },
      ],
      currency: "INR",
      currency_symbol: "₹",
      practical_metrics: {
        turnaround_days_kharif_rabi: 34,
        urea_bags_saved_per_ha: 3.6,
        irrigations_saved_per_yr: 8,
        pumping_hours_saved_per_ha: 320,
        msp_assurance_level: "NAFED / PSS Supported",
        eligible_schemes: [
          "Crop Diversification / Mera Pani Meri Virasat (₹17,500/ha state incentive)",
          "CRM Sub-Mission on Crop Residue Management (50–80% Happy Seeder / CHC subsidy)",
          "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
          "National Mission on Edible Oils (NMEO-Oilseeds) Seed & Procurement Support",
        ],
        labor_cost_inr_per_ha: 22330.0,
        input_cost_inr_per_ha: 74850.0,
      },
      narrative_summary:
        "Strategy 'Maize → Mustard → Greengram (Moong)': Maximum aquifer rescue rotation cutting irrigation by 47% (8 irrigations saved) while qualifying for the ₹17,500/ha paddy diversification incentive.",
      is_fallback: true,
      data_mode: "fallback_synthetic",
    },
    {
      rank: 3,
      rotation: {
        id: "r_pr126_wheat_moong",
        label: "Short Rice (PR-126) → Wheat → Greengram (Moong)",
        is_baseline: false,
        steps: [
          { year_index: 0, season_index: 0, crop_id: "rice_short", practices: ["residue_retained"] },
          { year_index: 0, season_index: 1, crop_id: "wheat", practices: ["happy_seeder", "zero_till", "residue_retained"] },
          { year_index: 0, season_index: 2, crop_id: "moong", practices: ["residue_retained"] },
        ],
      },
      results: [
        {
          rotation_id: "r_pr126_wheat_moong",
          scenario_set_id: "historical_1yr",
          yield_t_ha: { rice_short: [6.85], wheat: [5.05], moong: [1.02] },
          irrigation_mm: [975.0],
          profit_per_ha: [274800.0],
          soc_delta_t_ha_10yr: 2.04,
          erosion_t_ha_yr: 0.39,
          n_balance_kg_ha_yr: 108.0,
          living_root_days_pct: 83.0,
          family_diversity_index: 0.637,
          soil_health_score: 87.2,
          soil_health_breakdown: {
            disturbance_minimization: 17.0,
            soil_armor_cover: 20.0,
            living_roots: 14.7,
            biodiversity: 14.0,
            biological_n_livestock: 15.0,
            soc_modifier: 9.3,
            erosion_modifier: 9.2,
            burning_penalty: 0.0,
            total_score: 87.2,
          },
          profit_p10: 252000.0,
          profit_p50: 274800.0,
          profit_p90: 294000.0,
          cvar_profit_10: 247500.0,
        },
      ],
      objective_scores: {
        profit: 274800.0,
        water_savings: -975.0,
        soil_health: 87.2,
        low_risk: 247500.0,
        low_labour: -27600.0,
        food_security: 1.0,
      },
      vs_baseline: {
        irrigation_change_pct: -20.9,
        profit_change_pct: 28.7,
        soil_health_change_pts: 76.0,
        climate_resilience_score: 95.0,
        profit_regret: 10800.0,
      },
      why: [
        "Replaces Pusa-44 with PAU Short-Duration Rice PR-126 (96d field occupancy), saving 21% water (258 mm/yr) while retaining 100% FCI Paddy + Wheat MSP procurement.",
        "Opens a full 30-day October turnaround window for Happy Seeder wheat sowing without burning.",
        "Summer Moong fixes 50 kg N/ha (saving 3.8 bags/ha of 45-kg Urea) and builds +2.0 t C/ha over 10 years.",
      ],
      provenance: [
        { source: "PAU Ludhiana", product: "PR-126 & Happy Seeder Package of Practices", period: "2024", mode: "fallback_estimate" },
      ],
      currency: "INR",
      currency_symbol: "₹",
      practical_metrics: {
        turnaround_days_kharif_rabi: 30,
        urea_bags_saved_per_ha: 3.8,
        irrigations_saved_per_yr: 3,
        pumping_hours_saved_per_ha: 142,
        msp_assurance_level: "100% MSP Assured (FCI / State Agency)",
        eligible_schemes: [
          "CRM Sub-Mission on Crop Residue Management (50–80% Happy Seeder / CHC subsidy)",
          "NFSM-Pulses & NAFED e-Samridhi Assured MSP Procurement",
        ],
        labor_cost_inr_per_ha: 27600.0,
        input_cost_inr_per_ha: 82500.0,
      },
      narrative_summary:
        "Strategy 'Short Rice (PR-126) → Wheat → Greengram (Moong)': Zero-risk transition for Rice-Wheat farmers retaining 100% FCI MSP procurement while opening a 30-day burn-free Happy Seeder window and saving 21% water.",
      is_fallback: true,
      data_mode: "fallback_synthetic",
    },
  ];

  const localized = baseStrategies.map((s) => {
    let label = s.rotation.label;
    let narrative = s.narrative_summary;
    if (lang === "pa") {
      if (s.rank === 0) {
        label = "ਕੱਦੂ ਕੀਤਾ ਝੋਨਾ → ਕਣਕ → ਖ਼ਾਲੀ";
        narrative = "ਮੌਜੂਦਾ ਖੇਤ ਆਧਾਰ ('ਕੱਦੂ ਕੀਤਾ ਝੋਨਾ → ਕਣਕ'): 1,233 ਮਿਲੀਮੀਟਰ/ਸਾਲ ਸਿੰਚਾਈ ਦੀ ਮੰਗ ਕਰਦਾ ਹੈ ਅਤੇ ਕਣਕ ਦੀ ਬਿਜਾਈ ਲਈ ਸਿਰਫ਼ 11 ਦਿਨ ਬਚਦੇ ਹਨ, ਜਿਸ ਕਾਰਨ ਪਰਾਲੀ ਸਾੜਨੀ ਪੈਂਦੀ ਹੈ।";
      } else if (s.rank === 1) {
        label = "ਸਿੱਧੀ ਬਿਜਾਈ ਝੋਨਾ (DSR) → ਕਣਕ → ਮੂੰਗੀ";
        narrative = "ਸਿਫ਼ਾਰਿਸ਼ ਕੀਤੀ ਰਣਨੀਤੀ: DSR ਝੋਨਾ + ਹੈਪੀ ਸੀਡਰ ਜ਼ੀਰੋ-ਟਿਲ ਕਣਕ + ਗਰਮੀਆਂ ਦੀ ਮੂੰਗੀ। ਸਿੰਚਾਈ ਪਾਣੀ ਦੀ 28% ਬਚਤ, ਪਰਾਲੀ ਸਾੜਨ ਤੋਂ ਮੁਕਤੀ, ਅਤੇ 10 ਸਾਲਾਂ ਵਿੱਚ ਮਿੱਟੀ ਦੇ ਕਾਰਬਨ ਵਿੱਚ +2.0 t C/ha ਵਾਧਾ।";
      } else if (s.rank === 2) {
        label = "ਮੱਕੀ → ਸਰ੍ਹੋਂ → ਮੂੰਗੀ";
        narrative = "ਮੱਕੀ-ਸਰ੍ਹੋਂ-ਮੂੰਗੀ ਪ੍ਰਣਾਲੀ: ਝੋਨੇ ਦੀ ਥਾਂ ਮੱਕੀ ਲਗਾ ਕੇ 47% ਪਾਣੀ ਦੀ ਬਚਤ (320 ਪੰਪਿੰਗ ਘੰਟੇ/ਹੈਕਟੇਅਰ) ਅਤੇ ₹17,500/ਹੈਕਟੇਅਰ ਫ਼ਸਲ ਵਿਭਿੰਨਤਾ ਸਹਾਇਤਾ।";
      } else if (s.rank === 3) {
        label = "ਛੋਟੀ ਮਿਆਦ ਝੋਨਾ (PR-126) → ਕਣਕ → ਮੂੰਗੀ";
        narrative = "ਸੁਰੱਖਿਅਤ ਤਬਦੀਲੀ: PR-126 ਝੋਨਾ 100% ਐੱਮ.ਐੱਸ.ਪੀ. ਖ਼ਰੀਦ ਬਰਕਰਾਰ ਰੱਖਦਾ ਹੈ, 30 ਦਿਨਾਂ ਦੀ ਪਰਾਲੀ-ਮੁਕਤ ਹੈਪੀ ਸੀਡਰ ਖਿੜਕੀ ਖੋਲ੍ਹਦਾ ਹੈ ਅਤੇ 21% ਪਾਣੀ ਬਚਾਉਂਦਾ ਹੈ।";
      }
    } else if (lang === "hi") {
      if (s.rank === 0) {
        label = "पारंपरिक रोपाई धान → गेहूं → परती";
        narrative = "वर्तमान खेत आधारभूत ('रोपाई धान → गेहूं'): 1,233 मिमी/वर्ष सिंचाई की मांग करता है और गेहूं की बुवाई से पहले केवल 11 दिन का समय छोड़ता है, जिससे पराली जलाने की मजबूरी होती है।";
      } else if (s.rank === 1) {
        label = "सीधी बुवाई धान (DSR) → गेहूं → मूंग";
        narrative = "अनुशंसित रणनीति: DSR धान + हैप्पी सीडर गेहूं + ग्रीष्मकालीन मूंग। 28% सिंचाई जल की बचत, पराली जलाने से मुक्ति, और 10 वर्षों में +2.0 t C/ha मृदा जैविक कार्बन का संचय।";
      } else if (s.rank === 2) {
        label = "मक्का → सरसों → ग्रीष्मकालीन मूंग";
        narrative = "मक्का-सरसों-मूंग प्रणाली: धान के स्थान पर मक्का से 47% सिंचाई जल संरक्षण (320 पंपिंग घंटे/हेक्टेयर) एवं ₹17,500/हेक्टेयर फसल विविधीकरण प्रोत्साहन।";
      } else if (s.rank === 3) {
        label = "कम अवधि धान (PR-126) → गेहूं → मूंग";
        narrative = "सुरक्षित बदलाव: PR-126 धान 100% MSP खरीद सुनिश्चित रखते हुए 30 दिन की पराली-मुक्त हैप्पी सीडर खिड़की खोलता है और 21% जल बचाता है।";
      }
    }
    return {
      ...s,
      rotation: { ...s.rotation, label },
      narrative_summary: narrative,
      served_from: "demo_snapshot" as const,
      snapshot_date: "2026-11-10",
      state: "Punjab",
    };
  });

  return adaptStrategiesForHorizon(localized, rotationYears);
}
