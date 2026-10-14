"""Core interface contracts (see build plan section 11)."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


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


# ---------------------------------------------------------------------------
# Field
# ---------------------------------------------------------------------------
class FieldGeometry(BaseModel):
    """A field as a point (lat/lon) and optional GeoJSON polygon."""

    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    polygon: dict | None = Field(None, description="GeoJSON Polygon geometry")
    name: str | None = None


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
    agro_climatic_notes: list[str] = []
    currency: str = "USD"
    currency_symbol: str = "$"


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
    food_security: float = Field(0.0, ge=0)


class FarmConstraints(BaseModel):
    area_ha: float = Field(1.0, gt=0)
    irrigation: Literal["none", "limited", "full"] = "limited"
    irrigation_cap_mm: float | None = None
    must_grow: list[str] = []
    exclude: list[str] = []
    has_livestock: bool = False
    rotation_years: int = Field(3, ge=1, le=6)


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
    profit_p10: float
    profit_p50: float
    profit_p90: float
    cvar_profit_10: float


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
    currency: str = "USD"
    currency_symbol: str = "$"
