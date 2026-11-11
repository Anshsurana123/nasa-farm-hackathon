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

  // Adapt candidates into complementary multi-year sequences
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

    const label =
      effYears === 2
        ? `Yr 1: ${cand.rotation.label} ⇄ Yr 2: ${otherCand.rotation.label}`
        : `3-Yr Cycle: ${cand.rotation.label} ⇄ ${otherCand.rotation.label}`;

    return {
      ...cand,
      rotation: {
        ...cand.rotation,
        label,
        steps: adaptedSteps,
      },
      practical_metrics: cand.practical_metrics
        ? {
            ...cand.practical_metrics,
            seasonal_operations: adaptedOps.length > 0 ? adaptedOps : undefined,
          }
        : undefined,
    };
  });

  return [adaptedBaseline, ...adaptedCandidates];
}

export function getFallbackStrategies(
  _field?: FieldGeometry,
  _currencySymbol: string = "₹",
  rotationYears: number = 1,
  lang: "en" | "pa" | "hi" = "en"
): StrategyRecommendation[] {
  void _currencySymbol;
  // Ensure fallback strategies are ONLY ever served if explicitly requested for the Sangrur demo snapshot (WS-J2)
  const isSangrur =
    !_field ||
    !_field.id ||
    _field.id === "sangrur" ||
    (Math.abs(_field.lat - 30.19) < 0.25 && Math.abs(_field.lon - 75.78) < 0.25);
  if (!isSangrur) {
    return [];
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
        label = "ਬੀਟੀ ਨਰਮਾ/ਕਪਾਹ → ਕਣਕ → ਮੂੰਗੀ";
        narrative = "ਨਰਮਾ-ਕਣਕ ਪ੍ਰਣਾਲੀ: ਝੋਨੇ ਨੂੰ ਨਰਮੇ ਨਾਲ ਬਦਲ ਕੇ 41% ਪਾਣੀ ਦੀ ਬਚਤ ਅਤੇ ਉੱਚ ਸ਼ੁੱਧ ਆਮਦਨ।";
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
        label = "बीटी कपास → गेहूं → ग्रीष्मकालीन मूंग";
        narrative = "कपास-गेहूं प्रणाली: धान के स्थान पर कपास से 41% जल संरक्षण एवं उच्च शुद्ध आय।";
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
