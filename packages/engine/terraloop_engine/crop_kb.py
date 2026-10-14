"""Crop knowledge base loader.

Crop specs live as one YAML file per crop in ``packages/crop-kb/crops/``.
Each file must validate against ``terraloop_schemas.CropSpec``.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path

import yaml
from terraloop_schemas import CropSpec

_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "crop-kb" / "crops"


def kb_dir() -> Path:
    return Path(os.environ.get("TERRALOOP_CROP_KB", _DEFAULT_DIR))


@functools.lru_cache(maxsize=1)
def load_crops() -> dict[str, CropSpec]:
    crops: dict[str, CropSpec] = {}
    for path in sorted(kb_dir().glob("*.yaml")):
        if path.name.startswith("_"):
            continue  # templates
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        spec = CropSpec.model_validate(raw)
        if spec.id != path.stem:
            raise ValueError(f"{path.name}: id '{spec.id}' must equal file name '{path.stem}'")
        crops[spec.id] = spec
    return crops


def get_crop(crop_id: str) -> CropSpec:
    crops = load_crops()
    if crop_id not in crops:
        raise KeyError(f"Unknown crop '{crop_id}'. Known: {sorted(crops)}")
    return crops[crop_id]


_DEFAULT_PARAMS_DIR = Path(__file__).resolve().parents[2] / "crop-kb" / "aquacrop_params"


def aquacrop_params_dir() -> Path:
    return Path(os.environ.get("TERRALOOP_AQUACROP_PARAMS", _DEFAULT_PARAMS_DIR))


@functools.lru_cache(maxsize=1)
def load_all_aquacrop_overrides() -> dict[str, dict]:
    overrides: dict[str, dict] = {}
    pdir = aquacrop_params_dir()
    if pdir.exists():
        for path in sorted(pdir.glob("*.yaml")):
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "crop_id" in raw:
                overrides[raw["crop_id"]] = raw
    return overrides


def load_aquacrop_override(crop_id: str) -> dict | None:
    return load_all_aquacrop_overrides().get(crop_id)

