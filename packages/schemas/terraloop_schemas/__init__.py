"""Shared data contracts for TerraLoop.

These Pydantic models are the interface between workstreams (data, EO/ML,
modelling, optimisation, API, frontend). They are exported to JSON Schema
(see ``export.py``) so the frontend can generate TypeScript types.
"""

from .models import (
    ClimateSummary,
    CropFamily,
    CropSpec,
    DataProvenance,
    FarmConstraints,
    FieldGeometry,
    FieldProfile,
    HazardSummary,
    InferredSeason,
    PracticalFarmerMetrics,
    Priorities,
    Rotation,
    RotationStep,
    ScenarioSet,
    SimulationResult,
    SoilHealthCardInput,
    SoilSummary,
    StrategyRecommendation,
    WaterSummary,
)

__all__ = [
    "ClimateSummary",
    "CropFamily",
    "CropSpec",
    "DataProvenance",
    "FarmConstraints",
    "FieldGeometry",
    "FieldProfile",
    "HazardSummary",
    "InferredSeason",
    "PracticalFarmerMetrics",
    "Priorities",
    "Rotation",
    "RotationStep",
    "ScenarioSet",
    "SimulationResult",
    "SoilHealthCardInput",
    "SoilSummary",
    "StrategyRecommendation",
    "WaterSummary",
]
