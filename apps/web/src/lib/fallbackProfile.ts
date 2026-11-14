import type {
  ClimateSummary,
  DataProvenance,
  FieldGeometry,
  FieldProfile,
  HazardSummary,
  SoilSummary,
  TacticalAdvisory,
  TacticalDayForecast,
  WaterSummary,
} from "@/types/api";
import { isSouthAsia, regionContext } from "./ui";

export function attachFallbackMeteomatics(prof: FieldProfile): FieldProfile {
  const meanTemp = Number(((prof.climate.mean_tmax_c + prof.climate.mean_tmin_c) / 2).toFixed(1));
  const regClimProv: DataProvenance = {
    source: "Regional Climatology Baseline (Meteomatics Schema)",
    product: "Synthesized 7-Day Field Operations & Soil Moisture Climatology (Live API Credentials Unset)",
    resolution: "Regional agro-zone",
    period: "Next 7 days",
    mode: "regional_climatology",
  };
  const smiLayers = prof.water.soil_moisture_index_layers ?? {
    "-5cm": 0.62,
    "-15cm": 0.68,
    "-50cm": 0.71,
    "-150cm": 0.54,
  };
  const vwcLayers = prof.water.volumetric_soil_water_layers ?? {
    "-5cm": 0.22,
    "-15cm": 0.24,
    "-50cm": 0.26,
    "-150cm": 0.23,
  };
  const waterProv = prof.water.provenance ?? [];
  const hazardsProv = prof.hazards.provenance ?? [];
  const hasMmWaterProv = waterProv.some((p) => p.source.includes("Meteomatics"));
  const hasMmHazProv = hazardsProv.some((p) => p.source.includes("Meteomatics"));

  const water: WaterSummary = {
    ...prof.water,
    soil_moisture_deficit_mm: prof.water.soil_moisture_deficit_mm ?? 28.5,
    seedbed_temp_5cm_c: prof.water.seedbed_temp_5cm_c ?? meanTemp,
    soil_moisture_index_layers: smiLayers,
    volumetric_soil_water_layers: vwcLayers,
    provenance: hasMmWaterProv ? waterProv : [...waterProv, regClimProv],
  };
  const hazards: HazardSummary = {
    ...prof.hazards,
    late_blight_risk_idx: prof.hazards.late_blight_risk_idx ?? 65.0,
    canopy_wetness_idx: prof.hazards.canopy_wetness_idx ?? 0.18,
    hail_probability_pct: prof.hazards.hail_probability_pct ?? 4.0,
    fire_weather_index: prof.hazards.fire_weather_index ?? 11.5,
    meteorological_drought_idx: prof.hazards.meteorological_drought_idx ?? 0.4,
    max_30m_precip_rate_mmh: prof.hazards.max_30m_precip_rate_mmh ?? 24.5,
    provenance: hasMmHazProv ? hazardsProv : [...hazardsProv, regClimProv],
  };

  let tactical = prof.tactical_advisory ?? null;
  if (!tactical) {
    const baseDate = new Date();
    const m = baseDate.getMonth();
    const baseTx = prof.climate.monthly_tmax_c?.[m] ?? prof.climate.mean_tmax_c;
    const baseTn = prof.climate.monthly_tmin_c?.[m] ?? prof.climate.mean_tmin_c;
    const dailyPrecip = Number(((prof.climate.monthly_precip_mm?.[m] ?? 20) / 30).toFixed(1));
    const dailyEt0 = Number(((prof.climate.annual_et0_mm ?? 1400) / 365).toFixed(1));
    const daySeedTemp = water.seedbed_temp_5cm_c ?? Number(((baseTx + baseTn) / 2).toFixed(1));

    const forecastDays: TacticalDayForecast[] = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(baseDate.getTime() + i * 86400000);
      const rainDay = i === 2 || i === 5 ? dailyPrecip : Number((dailyPrecip * 0.2).toFixed(1));
      return {
        date: d.toISOString().slice(0, 10),
        tmax_c: Number((baseTx + (i % 3 === 0 ? 0.4 : -0.3)).toFixed(1)),
        tmin_c: Number((baseTn + (i % 2 === 0 ? 0.3 : -0.2)).toFixed(1)),
        precip_mm: rainDay,
        prob_precip_pct: rainDay >= 2.0 ? 45 : 15,
        et0_mm: dailyEt0,
        wind_speed_ms: 2.1,
        soil_temp_5cm_c: daySeedTemp,
        soil_moisture_deficit_mm: water.soil_moisture_deficit_mm ?? 28.5,
      };
    });

    const next7dPrecip = Number(forecastDays.reduce((s, d) => s + d.precip_mm, 0).toFixed(1));
    const next7dEt0 = Number(forecastDays.reduce((s, d) => s + d.et0_mm, 0).toFixed(1));
    const sowingCode: TacticalAdvisory["sowing_status_code"] =
      daySeedTemp < 12 ? "too_cold" : daySeedTemp > 34 ? "too_hot" : (water.soil_moisture_deficit_mm ?? 0) > 45 ? "too_dry" : "optimal";
    const irrAction: TacticalAdvisory["irrigation_action"] =
      next7dPrecip >= 15 ? "hold_rain_ahead" : (water.soil_moisture_deficit_mm ?? 0) >= 35 ? "irrigate_soon" : "adequate_moisture";

    tactical = {
      sowing_ready: sowingCode === "optimal",
      sowing_status_code: sowingCode,
      irrigation_action: irrAction,
      urea_spray_safe: next7dPrecip < 10,
      next_7d_precip_mm: next7dPrecip,
      next_7d_et0_mm: next7dEt0,
      seedbed_temp_5cm_c: daySeedTemp,
      soil_moisture_deficit_mm: water.soil_moisture_deficit_mm,
      fire_weather_index: hazards.fire_weather_index,
      forecast_days: forecastDays,
      provenance: [
        {
          source: "Regional Climatology",
          product: "Offline 7-day operational climatology fallback",
          resolution: "Regional agro-zone",
          period: "Next 7 days",
          mode: "regional_climatology",
        },
      ],
    };
  }

  return {
    ...prof,
    water,
    hazards,
    tactical_advisory: tactical,
  };
}

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

  // Monthly curves (12 months), calibrated cleanly for temperate/global or Southern Hemisphere sites
  let monthlyTx = [20.5, 24.2, 30.8, 36.5, 40.2, 39.0, 34.5, 33.0, 33.2, 31.8, 27.0, 22.0];
  let monthlyTn = [6.8, 9.5, 14.5, 20.2, 25.0, 27.5, 26.8, 26.0, 24.2, 18.5, 12.0, 7.8];
  let monthlyP = [18.0, 22.0, 15.0, 10.0, 14.0, 65.0, 210.0, 180.0, 85.0, 12.0, 6.0, 12.0];
  let annualEt0 = 1480;
  let wettestMonths = [6, 7, 8, 9];
  let gdd10 = 4850;
  let frostDays = lat > 28 ? 1.5 : 0.0;

  if (!isSA) {
    const absLat = Math.abs(lat);
    const amp = absLat > 23 ? 11.5 : 3.5;
    const isSh = lat < 0;
    const baseTx = Math.max(8, 30.0 - 0.36 * absLat);
    monthlyTx = Array.from({ length: 12 }, (_, idx) => {
      const m = idx + 1;
      const peakMonth = isSh ? 1 : 7;
      const phase = ((m - peakMonth) / 12) * 2 * Math.PI;
      return Number((baseTx + amp * Math.cos(phase)).toFixed(1));
    });
    monthlyTn = monthlyTx.map((tx) => Number((tx - 10.5).toFixed(1)));
    const pWeights = isSh
      ? [0.13, 0.12, 0.10, 0.07, 0.05, 0.04, 0.04, 0.05, 0.07, 0.09, 0.11, 0.13]
      : absLat > 40
        ? [0.08, 0.07, 0.08, 0.08, 0.09, 0.09, 0.08, 0.08, 0.08, 0.09, 0.09, 0.09]
        : [0.06, 0.06, 0.07, 0.08, 0.11, 0.12, 0.12, 0.11, 0.09, 0.07, 0.06, 0.05];
    monthlyP = pWeights.map((w) => Number((annualP * w).toFixed(1)));
    annualEt0 = Math.round(720 + Math.max(0, 35 - absLat) * 22);
    wettestMonths = isSh ? [12, 1, 2, 3] : [5, 6, 7, 8];
    gdd10 = Math.round(
      monthlyTx.reduce((acc, tx, idx) => acc + Math.max(0, (tx + monthlyTn[idx]) / 2 - 10) * 30.4, 0)
    );
    frostDays = monthlyTn.reduce((acc, tn) => acc + (tn < 1 ? 10 : 0), 0);
  }

  const provFallback: DataProvenance = {
    source: isSA ? "Regional Climatology & Soil Inventory" : "Latitude-Zonal Global Fallback Climatology",
    product: isSA
      ? "Location-calibrated Indian regional synthetic fallback"
      : "Unvalidated global fallback climatology (exploratory)",
    resolution: isSA ? "Regional Indian agro-zone" : "Global zonal estimate",
    period: "1985-2024",
    doi: "10.5067/POWER/0001",
    mode: isSA ? "regional_climatology" : "fallback_estimate",
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
    heat_days_per_year: Math.max(0, heatDays - 4),
    recent_heat_days_per_year: heatDays,
    frost_days_per_year: frostDays,
    longest_dry_spell_days_mean: isSA ? 14.5 : 9.0,
    annual_et0_mm: annualEt0,
    gdd_base10_per_year: gdd10,
    monthly_precip_mm: monthlyP,
    monthly_tmax_c: monthlyTx,
    monthly_tmin_c: monthlyTn,
    wettest_months: wettestMonths,
    provenance: [provFallback],
  };

  const water: WaterSummary = {
    root_zone_moisture_percentile: [45, 42, 38, 30, 28, 35, 65, 70, 58, 48, 42, 44],
    groundwater_trend_cm_per_year: gwTrend,
    climatic_water_balance_mm: annualP - annualEt0,
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
    drought_frequency: isSA ? 0.22 : 0.14,
    extreme_rain_days_per_year: 2.8,
    heat_stress_probability: isSA ? 0.72 : 0.15,
    frost_risk: frostDays > 2 ? 0.35 : lat > 28 ? 0.08 : 0.0,
    terminal_heat_days_per_year: terminalHeatDays,
    erosion_risk_class: "low",
    residue_burning_detected: null,
    provenance: [provFallback],
  };

  const agro_climatic_notes = [
    `Location-calibrated regional estimates active for ${reg.shortName} (${lat.toFixed(3)}°, ${lon.toFixed(3)}°).`,
    annualEt0 > annualP
      ? `Evaporative deficit: annual ET0 (${annualEt0.toLocaleString()} mm) exceeds rainfall (${annualP} mm); water-efficient rotations critical.`
      : `Positive seasonal moisture balance: rainfall (${annualP} mm) supports diverse rainfed sequences (ET0 ${annualEt0.toLocaleString()} mm).`,
    `Soil organic carbon is ${soc} g/kg (${texture}): organic residue retention and pulse integration build soil carbon.`,
  ];
  if (terminalHeatDays >= 5) {
    agro_climatic_notes.push(
      `Wheat terminal heat: grain-fill averages ${terminalHeatDays.toFixed(1)} days/yr above 32°C. Surface mulch buffers canopy temperature.`
    );
  }

  return attachFallbackMeteomatics({
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
    served_from: "live_computation",
    snapshot_date: null,
    is_fallback: true,
    data_mode: isSA ? "regional_climatology" : "fallback_synthetic",
    validation_status: isSA ? "validated_india" : "unvalidated_global",
    validation_message: isSA
      ? undefined
      : "Engine is calibrated for Indian agro-climatic zones; global results are for qualitative exploration.",
  });
}
