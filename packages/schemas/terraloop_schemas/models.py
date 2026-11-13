"""Core interface contracts (see build plan section 11)."""

from __future__ import annotations

import math
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Provenance: every number shown to a user must be traceable to a source.
# ---------------------------------------------------------------------------
class DataProvenance(BaseModel):
    source: str = Field(..., description="Dataset short name, e.g. 'NASA POWER', 'SMAP SPL4SMGP'")
    product: str | None = Field(None, description="Product ID / collection")
    period: str | None = Field(None, description="Time range used, e.g. '1995-2024'")
    resolution: str | None = None
    doi: str | None = None
    url: str | None = None
    mode: Literal["observed", "regional_climatology", "fallback_estimate", "unknown"] = "observed"


class SoilHealthCardInput(BaseModel):
    """Optional local laboratory values from an Indian Government Soil Health Card (SHC)."""

    ph: float | None = Field(None, ge=3.5, le=10.5)
    soc_pct: float | None = Field(None, ge=0.05, le=5.0, description="Organic Carbon (%) on SHC")
    available_n_kg_ha: float | None = Field(None, ge=0, le=1000)
    available_p_kg_ha: float | None = Field(None, ge=0, le=500)
    available_k_kg_ha: float | None = Field(None, ge=0, le=1500)


# ---------------------------------------------------------------------------
# Field
# ---------------------------------------------------------------------------
class FieldGeometry(BaseModel):
    """A field as a point (lat/lon) and optional GeoJSON polygon."""

    id: str | None = None
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    polygon: dict | None = Field(None, description="GeoJSON Polygon geometry")
    name: str | None = None

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, v: dict | None) -> dict | None:
        if v is None:
            return None
        if not isinstance(v, dict):
            raise TypeError("Polygon must be a dictionary")
        poly_type = v.get("type")
        if poly_type != "Polygon":
            raise ValueError(f"Expected GeoJSON Polygon geometry, got '{poly_type}'")
        coords = v.get("coordinates")
        if not isinstance(coords, list) or len(coords) == 0:
            raise ValueError("Polygon coordinates must be a non-empty list of rings")
        ring = coords[0]
        if not isinstance(ring, list) or len(ring) < 4:
            raise ValueError("Polygon exterior ring must contain at least 4 coordinate vertices")
        if len(ring) > 500:
            raise ValueError(f"Polygon ring exceeds maximum allowed vertex count (500), got {len(ring)}")

        lons = []
        lats = []
        for pt in ring:
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                raise ValueError(f"Invalid coordinate point in polygon: {pt}")
            x, y = float(pt[0]), float(pt[1])
            if not (-180.0 <= x <= 180.0 and -90.0 <= y <= 90.0):
                raise ValueError(f"Coordinate point out of bounds: lon={x}, lat={y}")
            lons.append(x)
            lats.append(y)

        mean_lat_rad = math.radians(sum(lats) / len(lats))
        cos_lat = math.cos(mean_lat_rad)
        x_km = [lon * 111.32 * cos_lat for lon in lons]
        y_km = [lat * 110.57 for lat in lats]
        area_km2 = 0.5 * abs(sum(x_km[i] * y_km[i + 1] - x_km[i + 1] * y_km[i] for i in range(len(x_km) - 1)))
        area_ha = area_km2 * 100.0
        if area_ha > 10000.0:
            raise ValueError(f"Polygon area ({area_ha:.1f} ha) exceeds maximum allowed farm field area (10,000 ha)")
        return v


class ClimateSummary(BaseModel):
    baseline_period: str
    recent_period: str
    mean_tmax_c: float
    mean_tmin_c: float
    annual_precip_mm: float
    recent_annual_precip_mm: float
    precip_change_pct: float
    tmax_change_c: float
    heat_days_per_year: float = Field(..., description="Days with Tmax > 35 C")
    recent_heat_days_per_year: float
    frost_days_per_year: float = Field(..., description="Days with Tmin < 0 C")
    longest_dry_spell_days_mean: float
    annual_et0_mm: float | None = None
    gdd_base10_per_year: float
    monthly_precip_mm: list[float] = Field(..., min_length=12, max_length=12)
    monthly_tmax_c: list[float] = Field(..., min_length=12, max_length=12)
    monthly_tmin_c: list[float] = Field(..., min_length=12, max_length=12)
    wettest_months: list[int] = Field(default_factory=list, description="Main rainy season (1-12)")
    provenance: list[DataProvenance] = []


class WaterSummary(BaseModel):
    root_zone_moisture_percentile: list[float] | None = Field(
        None, description="Monthly percentiles (SMAP L4), 12 values"
    )
    groundwater_trend_cm_per_year: float | None = Field(None, description="GRACE/GRACE-FO")
    climatic_water_balance_mm: float | None = Field(None, description="P - ET0, annual")
    irrigation_detected: bool | None = None
    provenance: list[DataProvenance] = []


class SoilSummary(BaseModel):
    texture_class: str | None = None
    sand_pct: float | None = None
    silt_pct: float | None = None
    clay_pct: float | None = None
    soc_g_per_kg: float | None = None
    ph: float | None = None
    bulk_density_g_cm3: float | None = None
    cec_cmol_kg: float | None = None
    nitrogen_g_kg: float | None = None
    available_p_kg_ha: float | None = None
    available_k_kg_ha: float | None = None
    field_capacity_vol: float | None = None
    wilting_point_vol: float | None = None
    slope_pct: float | None = None
    source: Literal["modelled", "farmer_test"] = "modelled"
    provenance: list[DataProvenance] = []


class HazardSummary(BaseModel):
    drought_frequency: float | None = Field(None, description="Fraction of years in drought")
    extreme_rain_days_per_year: float | None = None
    heat_stress_probability: float | None = None
    frost_risk: float | None = None
    erosion_risk_class: Literal["low", "moderate", "high", "very_high"] | None = None
    residue_burning_detected: bool | None = Field(None, description="FIRMS active fire on field")
    terminal_heat_days_per_year: float | None = Field(
        None,
        description="Days with Tmax > 32 C during wheat grain-fill (1 Mar - 15 Apr in NH, 1 Sep - 15 Oct in SH)",
    )
    provenance: list[DataProvenance] = []


class InferredSeason(BaseModel):
    year: int
    season_index: int
    start: date | None = None
    peak: date | None = None
    end: date | None = None
    crop_group: str | None = None
    crop_id: str | None = None
    confidence: float = Field(0.0, ge=0, le=1)
    confirmed_by_farmer: bool = False


class FieldProfile(BaseModel):
    field: FieldGeometry
    climate: ClimateSummary
    water: WaterSummary
    soil: SoilSummary
    hazards: HazardSummary
    seasons_per_year: int | None = None
    crop_history: list[InferredSeason] = []
    crop_history_provenance: list[DataProvenance] = []
    agro_climatic_notes: list[str] = []
    currency: str = "INR"
    currency_symbol: str = "₹"
    agro_zone: str | None = None
    state: str | None = None
    served_from: Literal["live_computation", "demo_snapshot"] = "live_computation"
    snapshot_date: str | None = None
    is_fallback: bool = False
    data_mode: Literal["observed", "hybrid_regional", "fallback_synthetic", "regional_climatology"] = "observed"
    validation_status: Literal["validated_india", "unvalidated_global"] = "validated_india"
    validation_message: str | None = None


# ---------------------------------------------------------------------------
# Crops
# ---------------------------------------------------------------------------
class CropFamily(str, Enum):
    poaceae = "poaceae"  # cereals & grasses
    fabaceae = "fabaceae"  # legumes
    brassicaceae = "brassicaceae"
    solanaceae = "solanaceae"
    cucurbitaceae = "cucurbitaceae"
    malvaceae = "malvaceae"  # cotton
    asteraceae = "asteraceae"  # sunflower
    amaranthaceae = "amaranthaceae"
    pedaliaceae = "pedaliaceae"  # sesame
    euphorbiaceae = "euphorbiaceae"  # cassava
    convolvulaceae = "convolvulaceae"  # sweet potato
    polygonaceae = "polygonaceae"  # buckwheat
    other = "other"


class CropSpec(BaseModel):
    id: str
    name: str
    family: CropFamily
    group: Literal[
        "cereal", "legume", "oilseed", "tuber", "vegetable", "fibre", "cover", "fodder"
    ]
    season_type: list[Literal["warm", "cool"]]
    gdd_to_maturity: float = Field(..., description="Growing degree days, base temp below")
    base_temp_c: float
    optimal_temp_c: tuple[float, float]
    max_temp_c: float
    min_temp_c: float
    duration_days: tuple[int, int]
    water_requirement_mm: tuple[float, float]
    kc: tuple[float, float, float] = Field(..., description="FAO-56 Kc ini, mid, end")
    root_depth_m: float
    drought_tolerance: int = Field(..., ge=1, le=5)
    heat_tolerance: int = Field(..., ge=1, le=5)
    waterlogging_tolerance: int = Field(..., ge=1, le=5)
    n_fixation_kg_ha: float = 0.0
    n_demand_kg_ha: float = 0.0
    residue_t_ha: float = 0.0
    residue_cn_ratio: float | None = None
    typical_yield_t_ha: tuple[float, float]
    aquacrop_name: str | None = None
    good_predecessors: list[str] = []
    bad_predecessors: list[str] = []
    notes: str | None = None
    sources: list[str] = []


# ---------------------------------------------------------------------------
# Farmer priorities & constraints
# ---------------------------------------------------------------------------
class Priorities(BaseModel):
    """Relative weights (normalised internally)."""

    profit: float = Field(1.0, ge=0)
    water_savings: float = Field(1.0, ge=0)
    soil_health: float = Field(1.0, ge=0)
    low_risk: float = Field(1.0, ge=0)
    low_labour: float = Field(0.0, ge=0)
    food_security: float = Field(1.0, ge=0)


class FarmConstraints(BaseModel):
    area_ha: float = Field(1.0, gt=0)
    irrigation: Literal["none", "limited", "full"] = "limited"
    irrigation_cap_mm: float | None = None
    must_grow: list[str] = []
    exclude: list[str] = []
    has_livestock: bool = False
    rotation_years: int = Field(1, ge=1, le=6)


# ---------------------------------------------------------------------------
# Rotation, scenarios, results
# ---------------------------------------------------------------------------
class RotationStep(BaseModel):
    year_index: int
    season_index: int
    crop_id: str
    sowing_doy: int | None = None
    practices: list[str] = Field(default_factory=list, description="e.g. 'no_till', 'residue_retained'")


class Rotation(BaseModel):
    id: str
    steps: list[RotationStep]
    label: str | None = None
    is_baseline: bool = False


class ScenarioSet(BaseModel):
    id: str
    kind: Literal["historical", "cmip6"]
    ssp: str | None = None
    horizon: str | None = None
    members: list[str] = Field(..., description="IDs of weather sequences (years or GCM-years)")
    provenance: list[DataProvenance] = []


class SimulationResult(BaseModel):
    rotation_id: str
    scenario_set_id: str
    yield_t_ha: dict[str, list[float]] = Field(
        ..., description="crop_id -> per-member mean yields"
    )
    irrigation_mm: list[float]
    profit_per_ha: list[float]
    soc_delta_t_ha_10yr: float
    erosion_t_ha_yr: float
    n_balance_kg_ha_yr: float
    living_root_days_pct: float
    family_diversity_index: float
    soil_health_score: float = Field(..., ge=0, le=100)
    soil_health_breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="5 USDA-NRCS principles + SOC & erosion modifier component scores",
    )
    profit_p10: float
    profit_p50: float
    profit_p90: float
    cvar_profit_10: float
    cvar_ci_low: float | None = None
    cvar_ci_high: float | None = None
    step_yields: dict[str, float] = Field(
        default_factory=dict,
        description="Per-step ensemble mean yields keyed by '{year_index}:{season_index}:{crop_id}'",
    )
    step_irrigations_mm: dict[str, float] = Field(
        default_factory=dict,
        description="Per-step ensemble mean irrigation demand (mm) keyed by '{year_index}:{season_index}:{crop_id}'",
    )


class SeasonalOperationStep(BaseModel):
    """Actionable per-season field operation, water, nutrient, and margin entry."""

    year_index: int = 0
    season_index: int = 0
    season_name: str = "Kharif"
    crop_id: str = "fallow"
    crop_name: str = "Fallow"
    sowing_window: str = ""
    harvest_window: str = ""
    duration_days: int = 60
    practices: list[str] = Field(default_factory=list)
    yield_t_ha: float = 0.0
    irrigation_mm: float = 0.0
    irrigations_count: int = 0
    input_cost_inr_ha: float = 0.0
    labor_cost_inr_ha: float = 0.0
    net_profit_inr_ha: float = 0.0
    n_fixation_kg_ha: float = 0.0
    urea_saved_kg_ha: float = 0.0
    agronomic_guidance: str = ""


class PracticalFarmerMetrics(BaseModel):
    """Actionable farm-level metrics in Indian agricultural units."""

    turnaround_days_kharif_rabi: int = Field(
        20, description="Days between Kharif harvest and Rabi sowing (>=20d enables burn-free sowing)"
    )
    urea_bags_saved_per_ha: float = Field(
        0.0, description="45-kg Urea bags saved per ha/yr via biological N fixation and residue retention"
    )
    irrigations_saved_per_yr: int = Field(
        0, description="Standard 75 mm flood irrigations saved per year vs baseline"
    )
    pumping_hours_saved_per_ha: int = Field(
        0, description="5 HP submersible borewell pumping hours saved per ha/yr vs baseline"
    )
    msp_assurance_level: str = Field(
        "MSP Assured (FCI / State)",
        description="Market procurement certainty: 'MSP Assured (FCI / State)', 'NAFED / PSS Supported', or 'Mandi Market-Linked'",
    )
    eligible_schemes: list[str] = Field(
        default_factory=list, description="Matching central/state Indian agricultural schemes"
    )
    labor_cost_inr_per_ha: float = 0.0
    input_cost_inr_per_ha: float = 0.0
    area_ha: float = Field(1.0, gt=0)
    total_farm_profit_p50: float = 0.0
    total_farm_input_cost: float = 0.0
    total_farm_urea_bags_saved: float = 0.0
    total_farm_pumping_hours_saved: int = 0
    seasonal_operations: list[SeasonalOperationStep] = Field(
        default_factory=list,
        description="Per-season actionable field operation, budget, irrigation, and nutrient ledger",
    )


class StrategyRecommendation(BaseModel):
    rank: int
    rotation: Rotation
    results: list[SimulationResult]
    objective_scores: dict[str, float]
    vs_baseline: dict[str, float] = Field(
        default_factory=dict, description="Relative change vs farmer's current rotation"
    )
    why: list[str] = []
    provenance: list[DataProvenance] = []
    currency: str = "INR"
    currency_symbol: str = "₹"
    practical_metrics: PracticalFarmerMetrics | None = None
    narrative_summary: str | None = None
    state: str | None = None
    served_from: Literal["live_computation", "demo_snapshot"] = "live_computation"
    snapshot_date: str | None = None
    economics_basis: Literal["local_verified", "punjab_proxy"] = "local_verified"
    is_fallback: bool = False
    data_mode: Literal["observed", "hybrid_regional", "fallback_synthetic", "regional_climatology"] = "observed"
    validation_status: Literal["validated_india", "unvalidated_global"] = "validated_india"
    validation_message: str | None = None


# ---------------------------------------------------------------------------
# API Request & Response Contracts (TASK-A01, A03)
# ---------------------------------------------------------------------------
class GeocodeResult(BaseModel):
    lat: float
    lon: float
    name: str


class SuitabilityRequest(BaseModel):
    field: FieldGeometry
    constraints: FarmConstraints = Field(default_factory=FarmConstraints)
    profile: FieldProfile | None = None
    soil_health_card: SoilHealthCardInput | None = None


class SuitabilityItem(BaseModel):
    crop_id: str
    name: str = ""
    score: float
    thermal_fit: float
    water_fit: float
    sowing_months: list[int]
    reasons: list[str] = Field(default_factory=list)


class RecommendRequest(BaseModel):
    field: FieldGeometry
    priorities: Priorities = Field(default_factory=Priorities)
    constraints: FarmConstraints = Field(default_factory=FarmConstraints)
    language: Literal["en", "pa", "hi"] = "en"
    soil_health_card: SoilHealthCardInput | None = None
    profile: FieldProfile | None = None
    baseline_override: list[str] | None = None
    climate_scenario: Literal[
        "historical",
        "ssp245_2030s",
        "ssp245_2050s",
        "ssp585_2030s",
        "ssp585_2050s",
    ] = "historical"
    drought_shock_pct: float = Field(0.0, ge=-100.0, le=100.0)
    price_shock_pct: float = Field(0.0, ge=-100.0, le=200.0)
    fertilizer_shock_pct: float = Field(0.0, ge=-100.0, le=300.0)
