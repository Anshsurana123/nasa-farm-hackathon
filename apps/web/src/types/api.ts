// Hand-written subset of the backend contracts (packages/schemas/terraloop_schemas/models.py).

export interface DataProvenance {
  source: string;
  product?: string | null;
  period?: string | null;
  resolution?: string | null;
  doi?: string | null;
  url?: string | null;
  mode?: "observed" | "regional_climatology" | "fallback_estimate" | "unknown";
}

export interface SoilHealthCardInput {
  ph?: number | null;
  soc_pct?: number | null;
  available_n_kg_ha?: number | null;
  available_p_kg_ha?: number | null;
  available_k_kg_ha?: number | null;
}

export interface FieldGeometry {
  id?: string | null;
  lat: number;
  lon: number;
  polygon?: Record<string, unknown> | null;
  name?: string | null;
}

export interface ClimateSummary {
  baseline_period: string;
  recent_period: string;
  mean_tmax_c: number;
  mean_tmin_c: number;
  annual_precip_mm: number;
  recent_annual_precip_mm: number;
  precip_change_pct: number;
  tmax_change_c: number;
  heat_days_per_year: number;
  recent_heat_days_per_year: number;
  frost_days_per_year: number;
  longest_dry_spell_days_mean: number;
  annual_et0_mm?: number | null;
  gdd_base10_per_year: number;
  monthly_precip_mm: number[];
  monthly_tmax_c: number[];
  monthly_tmin_c: number[];
  wettest_months: number[];
  provenance: DataProvenance[];
}

export interface SoilSummary {
  texture_class?: string | null;
  sand_pct?: number | null;
  silt_pct?: number | null;
  clay_pct?: number | null;
  soc_g_per_kg?: number | null;
  nitrogen_g_kg?: number | null;
  ph?: number | null;
  bulk_density_g_cm3?: number | null;
  field_capacity_vol?: number | null;
  wilting_point_vol?: number | null;
  slope_pct?: number | null;
  source: "modelled" | "farmer_test";
  provenance: DataProvenance[];
}

export interface WaterSummary {
  root_zone_moisture_percentile?: number[] | null;
  groundwater_trend_cm_per_year?: number | null;
  climatic_water_balance_mm?: number | null;
  irrigation_detected?: boolean | null;
  provenance: DataProvenance[];
}

export interface HazardSummary {
  drought_frequency?: number | null;
  extreme_rain_days_per_year?: number | null;
  heat_stress_probability?: number | null;
  frost_risk?: number | null;
  erosion_risk_class?: "low" | "moderate" | "high" | "very_high" | null;
  residue_burning_detected?: boolean | null;
  terminal_heat_days_per_year?: number | null;
  provenance?: DataProvenance[];
}

export interface InferredSeason {
  year: number;
  season_index: number;
  start?: string | null;
  peak?: string | null;
  end?: string | null;
  crop_group?: string | null;
  crop_id?: string | null;
  confidence: number;
  confirmed_by_farmer?: boolean;
}

export interface FieldProfile {
  field: FieldGeometry;
  climate: ClimateSummary;
  water: WaterSummary;
  soil: SoilSummary;
  hazards: HazardSummary;
  seasons_per_year?: number | null;
  crop_history: InferredSeason[];
  crop_history_provenance?: DataProvenance[];
  agro_climatic_notes: string[];
  currency?: string;
  currency_symbol?: string;
  agro_zone?: string | null;
  is_fallback?: boolean;
  data_mode?: "observed" | "hybrid_regional" | "fallback_synthetic";
  validation_status?: "validated_india" | "unvalidated_global";
  validation_message?: string | null;
}

export interface GoldenField {
  id: string;
  name: string;
  lat: number;
  lon: number;
  region: string;
  story: string;
  baseline_rotation: string;
  verified_cropland: boolean;
}

export interface CropSpec {
  id: string;
  name: string;
  family: string;
  group: "cereal" | "legume" | "oilseed" | "tuber" | "vegetable" | "fibre" | "cover" | "fodder";
  season_type: ("warm" | "cool")[];
  gdd_to_maturity: number;
  base_temp_c: number;
  optimal_temp_c: [number, number];
  max_temp_c: number;
  min_temp_c: number;
  duration_days: [number, number];
  water_requirement_mm: [number, number];
  kc: [number, number, number];
  root_depth_m: number;
  drought_tolerance: number;
  heat_tolerance: number;
  waterlogging_tolerance: number;
  n_fixation_kg_ha: number;
  n_demand_kg_ha: number;
  residue_t_ha: number;
  residue_cn_ratio?: number | null;
  typical_yield_t_ha: [number, number];
  aquacrop_name?: string | null;
  good_predecessors: string[];
  bad_predecessors: string[];
  notes?: string | null;
  sources: string[];
}

export interface Priorities {
  profit: number;
  water_savings: number;
  soil_health: number;
  low_risk: number;
  low_labour: number;
  food_security: number;
}

export interface FarmConstraints {
  area_ha: number;
  irrigation: "none" | "limited" | "full";
  irrigation_cap_mm?: number | null;
  must_grow: string[];
  exclude: string[];
  has_livestock: boolean;
  rotation_years: number;
}

export interface RotationStep {
  year_index: number;
  season_index: number;
  crop_id: string;
  sowing_doy?: number | null;
  practices: string[];
}

export interface Rotation {
  id: string;
  steps: RotationStep[];
  label?: string | null;
  is_baseline: boolean;
}

export interface SimulationResult {
  rotation_id: string;
  scenario_set_id: string;
  yield_t_ha: Record<string, number[]>;
  irrigation_mm: number[];
  profit_per_ha: number[];
  soc_delta_t_ha_10yr: number;
  erosion_t_ha_yr: number;
  n_balance_kg_ha_yr: number;
  living_root_days_pct: number;
  family_diversity_index: number;
  soil_health_score: number;
  soil_health_breakdown?: Record<string, number>;
  profit_p10: number;
  profit_p50: number;
  profit_p90: number;
  cvar_profit_10: number;
}

export interface SeasonalOperationStep {
  year_index: number;
  season_index: number;
  season_name: string;
  crop_id: string;
  crop_name: string;
  sowing_window: string;
  harvest_window: string;
  duration_days: number;
  practices: string[];
  yield_t_ha: number;
  irrigation_mm: number;
  irrigations_count: number;
  input_cost_inr_ha: number;
  labor_cost_inr_ha: number;
  net_profit_inr_ha: number;
  n_fixation_kg_ha: number;
  urea_saved_kg_ha: number;
  agronomic_guidance: string;
}

export interface PracticalFarmerMetrics {
  turnaround_days_kharif_rabi: number;
  urea_bags_saved_per_ha: number;
  irrigations_saved_per_yr: number;
  pumping_hours_saved_per_ha: number;
  msp_assurance_level: string;
  eligible_schemes: string[];
  labor_cost_inr_per_ha: number;
  input_cost_inr_per_ha: number;
  seasonal_operations?: SeasonalOperationStep[];
}

export interface StrategyRecommendation {
  rank: number;
  rotation: Rotation;
  results: SimulationResult[];
  objective_scores: Record<string, number>;
  vs_baseline: Record<string, number>;
  why: string[];
  provenance: DataProvenance[];
  currency?: string;
  currency_symbol?: string;
  practical_metrics?: PracticalFarmerMetrics | null;
  narrative_summary?: string | null;
  is_fallback?: boolean;
  data_mode?: "observed" | "hybrid_regional" | "fallback_synthetic";
  validation_status?: "validated_india" | "unvalidated_global";
  validation_message?: string | null;
}

export type ClimateScenarioId =
  | "historical"
  | "ssp245_2030s"
  | "ssp245_2050s"
  | "ssp585_2030s"
  | "ssp585_2050s";

export interface RecommendRequest {
  field: FieldGeometry;
  priorities?: Priorities;
  constraints?: FarmConstraints;
  language?: "en" | "pa" | "hi";
  soil_health_card?: SoilHealthCardInput | null;
  baseline_override?: string[] | null;
  climate_scenario?: ClimateScenarioId;
  drought_shock_pct?: number;
  price_shock_pct?: number;
  fertilizer_shock_pct?: number;
}

export interface SuitabilityItem {
  crop_id: string;
  name?: string;
  score: number;
  thermal_fit: number;
  water_fit: number;
  sowing_months: number[];
  reasons: string[];
}

export interface GeocodeResult {
  lat: number;
  lon: number;
  name: string;
}
