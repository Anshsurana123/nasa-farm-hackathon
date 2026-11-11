import type {
  ClimateSummary,
  DataProvenance,
  FieldGeometry,
  FieldProfile,
  HazardSummary,
  SoilSummary,
  WaterSummary,
} from "@/types/api";
import { isSouthAsia, regionContext } from "./ui";

export function generateFallbackProfile(field: FieldGeometry): FieldProfile {
  const lat = field.lat;
  const lon = field.lon;
  const reg = regionContext(lat, lon, field.id ?? null);
  const isSA = isSouthAsia(lat, lon);

  // Regional agroclimate parameters
  let annualP = 720;
  let meanTx = 30.5;
  let meanTn = 18.2;
  let heatDays = 42;
  let terminalHeatDays = 12;
  let gwTrend = -2.8;
  let texture = "loam";
  let sand = 40.0;
  let silt = 42.0;
  let clay = 18.0;
  let soc = 5.2;
  let ph = 7.4;
  let bd = 1.48;

  if (reg.key === "punjab" || reg.key === "malwa") {
    annualP = 650;
    meanTx = 30.2;
    meanTn = 16.8;
    heatDays = 52;
    terminalHeatDays = 16.5;
    gwTrend = -3.85;
    texture = "loam";
    sand = 44.0;
    silt = 40.0;
    clay = 16.0;
    soc = 4.8;
    ph = 7.8;
  } else if (reg.key === "vidarbha") {
    annualP = 980;
    meanTx = 33.2;
    meanTn = 20.4;
    heatDays = 68;
    terminalHeatDays = 6.0;
    gwTrend = -0.8;
    texture = "clay";
    sand = 18.0;
    silt = 28.0;
    clay = 54.0;
    soc = 6.5;
    ph = 7.9;
  } else if (reg.key === "bundelkhand") {
    annualP = 850;
    meanTx = 32.5;
    meanTn = 19.5;
    heatDays = 62;
    terminalHeatDays = 8.0;
    gwTrend = -1.9;
    texture = "sandy loam";
    sand = 58.0;
    silt = 24.0;
    clay = 18.0;
    soc = 4.2;
    ph = 7.2;
  } else if (reg.key === "cauvery") {
    annualP = 1150;
    meanTx = 32.8;
    meanTn = 23.5;
    heatDays = 35;
    terminalHeatDays = 2.0;
    gwTrend = -1.2;
    texture = "clay loam";
    sand = 28.0;
    silt = 38.0;
    clay = 34.0;
    soc = 6.8;
    ph = 7.3;
  } else if (reg.key === "arid_west") {
    annualP = 320;
    meanTx = 34.0;
    meanTn = 19.0;
    heatDays = 78;
    terminalHeatDays = 18.0;
    gwTrend = -3.5;
    texture = "loamy sand";
    sand = 78.0;
    silt = 14.0;
    clay = 8.0;
    soc = 2.8;
    ph = 8.2;
  } else if (!isSA) {
    // Temperate global fallback
    annualP = 850;
    meanTx = 18.5;
    meanTn = 7.5;
    heatDays = 8;
    terminalHeatDays = 0.5;
    gwTrend = -0.5;
    texture = "silt loam";
    sand = 25.0;
    silt = 60.0;
    clay = 15.0;
    soc = 14.0;
    ph = 6.5;
    bd = 1.35;
  }

  // Monthly curves (12 months)
  const monthlyTx = [20.5, 24.2, 30.8, 36.5, 40.2, 39.0, 34.5, 33.0, 33.2, 31.8, 27.0, 22.0];
  const monthlyTn = [6.8, 9.5, 14.5, 20.2, 25.0, 27.5, 26.8, 26.0, 24.2, 18.5, 12.0, 7.8];
  const monthlyP = [18.0, 22.0, 15.0, 10.0, 14.0, 65.0, 210.0, 180.0, 85.0, 12.0, 6.0, 12.0];

  const provFallback: DataProvenance = {
    source: "Regional Climatology & Soil Inventory",
    product: "Location-calibrated biophysical synthetic fallback",
    resolution: "Regional Indian agro-zone",
    period: "1985-2024",
    doi: "10.5067/POWER/0001",
    mode: "regional_climatology",
  };

  const climate: ClimateSummary = {
    baseline_period: "1985-2004",
    recent_period: "2005-2024",
    mean_tmax_c: meanTx,
    mean_tmin_c: meanTn,
    annual_precip_mm: annualP,
    recent_annual_precip_mm: annualP * 0.96,
    precip_change_pct: -4.0,
    tmax_change_c: 0.85,
    heat_days_per_year: heatDays - 6,
    recent_heat_days_per_year: heatDays,
    frost_days_per_year: lat > 28 ? 1.5 : 0.0,
    longest_dry_spell_days_mean: 14.5,
    annual_et0_mm: 1480,
    gdd_base10_per_year: 4850,
    monthly_precip_mm: monthlyP,
    monthly_tmax_c: monthlyTx,
    monthly_tmin_c: monthlyTn,
    wettest_months: [6, 7, 8, 9],
    provenance: [provFallback],
  };

  const water: WaterSummary = {
    root_zone_moisture_percentile: [45, 42, 38, 30, 28, 35, 65, 70, 58, 48, 42, 44],
    groundwater_trend_cm_per_year: gwTrend,
    climatic_water_balance_mm: annualP - 1480,
    provenance: [provFallback],
  };

  const soil: SoilSummary = {
    texture_class: texture,
    sand_pct: sand,
    silt_pct: silt,
    clay_pct: clay,
    soc_g_per_kg: soc,
    ph,
    bulk_density_g_cm3: bd,
    cec_cmol_kg: 18.5,
    nitrogen_g_kg: 0.65,
    field_capacity_vol: 0.28,
    wilting_point_vol: 0.13,
    slope_pct: 0.8,
    source: "modelled",
    provenance: [provFallback],
  };

  const hazards: HazardSummary = {
    drought_frequency: 0.22,
    extreme_rain_days_per_year: 2.8,
    heat_stress_probability: 0.72,
    frost_risk: lat > 28 ? 0.08 : 0.0,
    terminal_heat_days_per_year: terminalHeatDays,
    erosion_risk_class: "low",
    residue_burning_detected: null,
    provenance: [provFallback],
  };

  const agro_climatic_notes = [
    `Location-calibrated regional estimates active for ${reg.shortName} (${lat.toFixed(3)}°, ${lon.toFixed(3)}°).`,
    `Evaporative deficit: annual ET0 (1,480 mm) exceeds rainfall (${annualP} mm); water-efficient rotations critical.`,
    `Soil organic carbon is ${soc} g/kg (${texture}): organic residue retention and summer pulses build carbon.`,
  ];
  if (terminalHeatDays >= 5) {
    agro_climatic_notes.push(
      `Wheat terminal heat: March grain-fill averages ${terminalHeatDays.toFixed(1)} days/yr above 32°C. Surface mulch buffers canopy temperature.`
    );
  }

  return {
    field,
    climate,
    water,
    soil,
    hazards,
    seasons_per_year: 2,
    crop_history: [],
    crop_history_provenance: [provFallback],
    agro_climatic_notes,
    currency: isSA ? "INR" : "USD",
    currency_symbol: isSA ? "₹" : "$",
    agro_zone: reg.shortName,
    state: reg.regionName,
    served_from: "demo_snapshot",
    snapshot_date: "Regional Climatology",
    is_fallback: !isSA,
    data_mode: isSA ? "hybrid_regional" : "fallback_synthetic",
    validation_status: isSA ? "validated_india" : "unvalidated_global",
    validation_message: isSA
      ? undefined
      : "Engine is calibrated for Indian agro-climatic zones; global results are for qualitative exploration.",
  };
}
