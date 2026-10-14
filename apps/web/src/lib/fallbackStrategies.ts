// Offline fallback strategies, shown ONLY when the backend /recommend endpoint is unreachable.
// These are illustrative sample values (not engine output); the UI labels them as such.
// TODO(TASK-A03): replace with precomputed data/golden/<id>/recommendations.json once available.

import type { FieldGeometry, StrategyRecommendation } from "@/types/api";

export function getFallbackStrategies(field?: FieldGeometry, currencySymbol: string = "$"): StrategyRecommendation[] {
  const isSouthAsia = field && field.lat >= 20 && field.lat <= 35 && field.lon >= 68 && field.lon <= 90;

  if (!isSouthAsia) {
    return [
      {
        rank: 0,
        rotation: {
          id: "baseline_maize_wheat",
          label: "Grain Corn ➔ Winter Wheat ➔ Fallow",
          is_baseline: true,
          steps: [
            { year_index: 0, season_index: 0, crop_id: "maize", practices: ["conventional_tillage"] },
            { year_index: 0, season_index: 1, crop_id: "wheat", practices: ["conventional_tillage"] },
          ],
        },
        results: [
          {
            rotation_id: "baseline_maize_wheat",
            scenario_set_id: "historical_1985_2024",
            yield_t_ha: { maize: [8.5], wheat: [5.2] },
            irrigation_mm: [880.0],
            profit_per_ha: [820.0],
            soc_delta_t_ha_10yr: -0.45,
            erosion_t_ha_yr: 1.4,
            n_balance_kg_ha_yr: 42.0,
            living_root_days_pct: 0.65,
            family_diversity_index: 0.0,
            soil_health_score: 41.5,
            profit_p10: 640.0,
            profit_p50: 820.0,
            profit_p90: 950.0,
            cvar_profit_10: 590.0,
          },
        ],
        objective_scores: {},
        vs_baseline: {
          climate_resilience_score: 48.0,
          profit_regret: 230.0,
          irrigation_spike_mm: 180.0,
        },
        why: [
          "Conventional cereal double-crop with high summer irrigation demand in Central Valley.",
          "Groundwater depletion rate: -2.80 cm/yr recorded by NASA GRACE mascon satellites.",
        ],
        provenance: [
          { source: "NASA GRACE", product: "Tellus Mascon V04", period: "2002-2024", doi: "10.5067/TEMSC-3MJ62" },
        ],
        currency: "USD",
        currency_symbol: "$",
      },
      {
        rank: 1,
        rotation: {
          id: "cotton_chickpea_cover",
          label: "Pima Cotton ➔ Chickpea + Clover Cover",
          is_baseline: false,
          steps: [
            { year_index: 0, season_index: 0, crop_id: "cotton", practices: ["reduced_till", "residue_retained"] },
            { year_index: 0, season_index: 1, crop_id: "chickpea", practices: ["zero_till", "n_fixation"] },
          ],
        },
        results: [
          {
            rotation_id: "cotton_chickpea_cover",
            scenario_set_id: "historical_1985_2024",
            yield_t_ha: { cotton: [2.3], chickpea: [2.1] },
            irrigation_mm: [520.0],
            profit_per_ha: [1240.0],
            soc_delta_t_ha_10yr: 1.8,
            erosion_t_ha_yr: 0.5,
            n_balance_kg_ha_yr: 14.0,
            living_root_days_pct: 0.82,
            family_diversity_index: 0.69,
            soil_health_score: 75.0,
            profit_p10: 980.0,
            profit_p50: 1240.0,
            profit_p90: 1410.0,
            cvar_profit_10: 920.0,
          },
        ],
        objective_scores: {},
        vs_baseline: {
          irrigation_change_pct: -40.9,
          profit_change_pct: 51.2,
          soil_health_change_pts: 33.5,
          climate_resilience_score: 86.4,
          profit_regret: 110.0,
        },
        why: [
          "Saves 360 mm net irrigation (40.9% reduction) via deep taproot cotton and drought-hardy garbanzo bean [AquaCrop].",
          "Adds +1.8 t C/ha topsoil organic carbon over 10 years via zero-till and residue armor [RothC model].",
          "Legume biological fixation provides natural nitrogen credit, cutting input expenditure [UC Davis].",
        ],
        provenance: [
          { source: "AquaCrop-OSPy", product: "FAO AquaCrop 3.1", period: "1985-2024" },
          { source: "RothC-26.3", product: "RothC Lite", period: "10-yr horizon" },
        ],
        currency: "USD",
        currency_symbol: "$",
      },
      {
        rank: 2,
        rotation: {
          id: "maize_wheat_cover",
          label: "Corn Silage ➔ Winter Wheat + Red Clover",
          is_baseline: false,
          steps: [
            { year_index: 0, season_index: 0, crop_id: "maize", practices: ["strip_till", "residue_retained"] },
            { year_index: 0, season_index: 1, crop_id: "wheat", practices: ["no_till"] },
          ],
        },
        results: [
          {
            rotation_id: "maize_wheat_cover",
            scenario_set_id: "historical_1985_2024",
            yield_t_ha: { maize: [8.8], wheat: [5.4] },
            irrigation_mm: [660.0],
            profit_per_ha: [1080.0],
            soc_delta_t_ha_10yr: 1.3,
            erosion_t_ha_yr: 0.6,
            n_balance_kg_ha_yr: 18.0,
            living_root_days_pct: 0.88,
            family_diversity_index: 0.50,
            soil_health_score: 69.0,
            profit_p10: 890.0,
            profit_p50: 1080.0,
            profit_p90: 1220.0,
            cvar_profit_10: 830.0,
          },
        ],
        objective_scores: {},
        vs_baseline: {
          irrigation_change_pct: -25.0,
          profit_change_pct: 31.7,
          soil_health_change_pts: 27.5,
          climate_resilience_score: 81.2,
          profit_regret: 140.0,
        },
        why: [
          "Cuts irrigation by 25% (220 mm saved) through soil moisture retention under clover mulching.",
          "Significantly buffers root zone moisture against California summer heat spikes monitored by NASA POWER.",
        ],
        provenance: [
          { source: "NASA POWER", product: "Daily Agroclimatology", period: "1985-2024" },
        ],
        currency: "USD",
        currency_symbol: "$",
      },
      {
        rank: 3,
        rotation: {
          id: "sunflower_chickpea",
          label: "Sunflower ➔ Winter Garbanzo Bean",
          is_baseline: false,
          steps: [
            { year_index: 0, season_index: 0, crop_id: "sunflower", practices: ["minimum_till"] },
            { year_index: 0, season_index: 1, crop_id: "chickpea", practices: ["zero_till"] },
          ],
        },
        results: [
          {
            rotation_id: "sunflower_chickpea",
            scenario_set_id: "historical_1985_2024",
            yield_t_ha: { sunflower: [2.8], chickpea: [2.0] },
            irrigation_mm: [440.0],
            profit_per_ha: [990.0],
            soc_delta_t_ha_10yr: 0.8,
            erosion_t_ha_yr: 0.8,
            n_balance_kg_ha_yr: 10.0,
            living_root_days_pct: 0.76,
            family_diversity_index: 0.69,
            soil_health_score: 64.0,
            profit_p10: 810.0,
            profit_p50: 990.0,
            profit_p90: 1150.0,
            cvar_profit_10: 760.0,
          },
        ],
        objective_scores: {},
        vs_baseline: {
          irrigation_change_pct: -50.0,
          profit_change_pct: 20.7,
          soil_health_change_pts: 22.5,
          climate_resilience_score: 77.5,
          profit_regret: 170.0,
        },
        why: [
          "Maximum water conservation: 50% irrigation cut (440 mm saved) under severe drought conditions.",
          "Deep rooting depth of sunflower scavenges residual moisture and breaks soil compaction.",
        ],
        provenance: [
          { source: "NASA GRACE", product: "Tellus Mascon V04", period: "2002-2024", doi: "10.5067/TEMSC-3MJ62" },
        ],
        currency: "USD",
        currency_symbol: "$",
      },
    ];
  }

  return [
    {
      rank: 0,
      rotation: {
        id: "baseline_rice_wheat",
        label: "Puddled Rice ➔ Wheat ➔ Fallow",
        is_baseline: true,
        steps: [
          { year_index: 0, season_index: 0, crop_id: "rice_puddled", practices: ["puddled", "residue_burned"] },
          { year_index: 0, season_index: 1, crop_id: "wheat", practices: ["conventional_tillage"] },
          { year_index: 0, season_index: 2, crop_id: "fallow", practices: [] },
        ],
      },
      results: [
        {
          rotation_id: "baseline_rice_wheat",
          scenario_set_id: "historical_1985_2024",
          yield_t_ha: { rice_puddled: [6.2], wheat: [4.9] },
          irrigation_mm: [1580.0],
          profit_per_ha: [88000.0],
          soc_delta_t_ha_10yr: -0.85,
          erosion_t_ha_yr: 1.2,
          n_balance_kg_ha_yr: 48.0,
          living_root_days_pct: 0.62,
          family_diversity_index: 0.0,
          soil_health_score: 36.5,
          profit_p10: 71000.0,
          profit_p50: 88000.0,
          profit_p90: 97000.0,
          cvar_profit_10: 64000.0,
        },
      ],
      objective_scores: {},
      vs_baseline: {
        climate_resilience_score: 41.2,
        profit_regret: 24000.0,
        irrigation_spike_mm: 237.0,
      },
      why: [
        "Current practice with 180 mm ponding requirement and October stubble burning.",
        "Groundwater depletion rate: -3.85 cm/yr measured by NASA GRACE.",
      ],
      provenance: [
        { source: "NASA GRACE", product: "Tellus Mascon V04", period: "2002-2024", doi: "10.5067/TEMSC-3MJ62" },
      ],
    },
    {
      rank: 1,
      rotation: {
        id: "rice_dsr_wheat_moong",
        label: "DSR Rice ➔ Wheat + Mulch ➔ Summer Moong",
        is_baseline: false,
        steps: [
          { year_index: 0, season_index: 0, crop_id: "rice_dsr", practices: ["direct_seeded", "residue_retained"] },
          { year_index: 0, season_index: 1, crop_id: "wheat", practices: ["happy_seeder", "residue_retained"] },
          { year_index: 0, season_index: 2, crop_id: "moong", practices: ["zero_till", "n_fixation"] },
        ],
      },
      results: [
        {
          rotation_id: "rice_dsr_wheat_moong",
          scenario_set_id: "historical_1985_2024",
          yield_t_ha: { rice_dsr: [6.0], wheat: [5.1], moong: [1.1] },
          irrigation_mm: [1190.0],
          profit_per_ha: [104000.0],
          soc_delta_t_ha_10yr: 2.1,
          erosion_t_ha_yr: 0.6,
          n_balance_kg_ha_yr: 12.0,
          living_root_days_pct: 0.82,
          family_diversity_index: 0.69,
          soil_health_score: 72.0,
          profit_p10: 89000.0,
          profit_p50: 104000.0,
          profit_p90: 118000.0,
          cvar_profit_10: 82000.0,
        },
      ],
      objective_scores: {},
      vs_baseline: {
        irrigation_change_pct: -24.7,
        profit_change_pct: 18.2,
        soil_health_change_pts: 35.5,
        climate_resilience_score: 87.4,
        profit_regret: 11000.0,
      },
      why: [
        "Saves 390 mm net irrigation (24.7% reduction) via DSR non-puddled culture (AquaCrop simulation).",
        "Adds +2.1 t C/ha topsoil organic carbon over 10 years via zero burning and in-situ mulching (RothC model).",
        "Legume BNF supplies 25 kg N/ha natural fertilizer credit to succeeding wheat.",
      ],
      provenance: [
        { source: "AquaCrop-OSPy", product: "FAO AquaCrop 3.1", period: "1985-2024" },
        { source: "RothC-26.3", product: "RothC Lite", period: "10-yr horizon" },
      ],
    },
    {
      rank: 2,
      rotation: {
        id: "maize_wheat_moong",
        label: "Kharif Maize ➔ Wheat ➔ Summer Moong",
        is_baseline: false,
        steps: [
          { year_index: 0, season_index: 0, crop_id: "maize", practices: ["ridge_furrow", "residue_retained"] },
          { year_index: 0, season_index: 1, crop_id: "wheat", practices: ["happy_seeder"] },
          { year_index: 0, season_index: 2, crop_id: "moong", practices: ["zero_till"] },
        ],
      },
      results: [
        {
          rotation_id: "maize_wheat_moong",
          scenario_set_id: "historical_1985_2024",
          yield_t_ha: { maize: [6.8], wheat: [5.0], moong: [1.1] },
          irrigation_mm: [820.0],
          profit_per_ha: [96000.0],
          soc_delta_t_ha_10yr: 1.6,
          erosion_t_ha_yr: 0.7,
          n_balance_kg_ha_yr: 8.0,
          living_root_days_pct: 0.80,
          family_diversity_index: 0.69,
          soil_health_score: 68.0,
          profit_p10: 81000.0,
          profit_p50: 96000.0,
          profit_p90: 108000.0,
          cvar_profit_10: 74000.0,
        },
      ],
      objective_scores: {},
      vs_baseline: {
        irrigation_change_pct: -48.1,
        profit_change_pct: 9.1,
        soil_health_change_pts: 31.5,
        climate_resilience_score: 83.1,
        profit_regret: 13500.0,
      },
      why: [
        "Maximum water savings: cuts irrigation by 48.1% (760 mm saved) by substituting paddy with maize.",
        "Completely stops deep aquifer depletion, aligning with NASA GRACE groundwater conservation.",
      ],
      provenance: [
        { source: "NASA GRACE", product: "Tellus Mascon V04", period: "2002-2024", doi: "10.5067/TEMSC-3MJ62" },
      ],
    },
    {
      rank: 3,
      rotation: {
        id: "cotton_wheat",
        label: "Kharif Cotton ➔ Rabi Wheat",
        is_baseline: false,
        steps: [
          { year_index: 0, season_index: 0, crop_id: "cotton", practices: ["reduced_till"] },
          { year_index: 0, season_index: 1, crop_id: "wheat", practices: ["conventional_tillage"] },
        ],
      },
      results: [
        {
          rotation_id: "cotton_wheat",
          scenario_set_id: "historical_1985_2024",
          yield_t_ha: { cotton: [2.1], wheat: [4.8] },
          irrigation_mm: [910.0],
          profit_per_ha: [91000.0],
          soc_delta_t_ha_10yr: 0.5,
          erosion_t_ha_yr: 1.1,
          n_balance_kg_ha_yr: 22.0,
          living_root_days_pct: 0.74,
          family_diversity_index: 0.69,
          soil_health_score: 55.0,
          profit_p10: 69000.0,
          profit_p50: 91000.0,
          profit_p90: 109000.0,
          cvar_profit_10: 61000.0,
        },
      ],
      objective_scores: {},
      vs_baseline: {
        irrigation_change_pct: -42.4,
        profit_change_pct: 3.4,
        soil_health_change_pts: 18.5,
        climate_resilience_score: 72.8,
        profit_regret: 18000.0,
      },
      why: [
        "Deep-rooted cotton utilizes subsoil moisture, reducing irrigation requirement by 42.4%.",
        "Diversifies botanical family (Malvaceae + Poaceae) reducing pest and disease cycles.",
      ],
      provenance: [
        { source: "NASA POWER", product: "Daily Agroclimatology", period: "1985-2024" },
      ],
    },
  ];
}
