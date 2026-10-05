// Hand-written subset of the backend contracts (packages/schemas/terraloop_schemas/models.py).
// TODO(TASK-F02): generate these from JSON Schema instead:
//   uv run python -m terraloop_schemas.export apps/web/src/types/schemas.json
//   npx json-schema-to-typescript apps/web/src/types/schemas.json > apps/web/src/types/schemas.d.ts

export interface DataProvenance {
  source: string;
  product?: string | null;
  period?: string | null;
  resolution?: string | null;
  doi?: string | null;
  url?: string | null;
}

export interface FieldGeometry {
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
}

export interface FieldProfile {
  field: FieldGeometry;
  climate: ClimateSummary;
  water: WaterSummary;
  soil: SoilSummary;
  hazards: HazardSummary;
  seasons_per_year?: number | null;
  crop_history: unknown[];
  agro_climatic_notes: string[];
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
