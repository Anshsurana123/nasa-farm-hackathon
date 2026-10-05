"""Export all contracts to JSON Schema for frontend type generation.

Usage:
    python -m terraloop_schemas.export ../../apps/web/src/types/schemas.json
Then in apps/web:
    npx json-schema-to-typescript src/types/schemas.json > src/types/schemas.d.ts
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic.json_schema import models_json_schema

from . import models as m

EXPORTED = [
    m.FieldGeometry,
    m.FieldProfile,
    m.CropSpec,
    m.Priorities,
    m.FarmConstraints,
    m.Rotation,
    m.ScenarioSet,
    m.SimulationResult,
    m.StrategyRecommendation,
]


def build() -> dict:
    _, schema = models_json_schema([(model, "validation") for model in EXPORTED], title="TerraLoop")
    return schema


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("schemas.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build(), indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
