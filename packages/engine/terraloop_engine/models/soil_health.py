"""Soil carbon, nitrogen balance, soil health score. (TASK-M05, M06, M07)

M05 RothC-lite (monthly):
    Pools DPM, RPM, BIO, HUM, IOM. Rate constants (yr-1): DPM 10, RPM 0.3, BIO 0.66, HUM 0.02.
    Rate modifiers: temperature a = 47.91 / (1 + exp(106.06 / (T + 18.27))),
    moisture b from topsoil moisture deficit, soil cover c = 0.6 when crop present else 1.
    Inputs: monthly residue C (crop residue_t_ha * 0.45 C fraction, returned only if not burnt),
    DPM/RPM ratio 1.44 for crops. Initial SOC from SoilSummary.soc_g_per_kg * bulk density * depth.
    Output: annual SOC (t C/ha, 0-30 cm) for 10-20 years.
    Reference: Coleman & Jenkinson (1996) RothC-26.3.

M06 N-balance per season (kg N/ha):
    surplus = fertiliser + fixation (CropSpec.n_fixation_kg_ha) + deposition(~10)
              - removal (yield * grain N conc.)

M07 Soil Health Score (0-100) built on the 5 USDA-NRCS principles:
    disturbance  : tillage practices in RotationStep.practices (no_till best)
    cover        : % days with living cover (from season calendar)
    biodiversity : Shannon index over CropFamily across the rotation
    living roots : % of year with a growing crop
    livestock    : FarmConstraints.has_livestock / fodder crops
  plus SOC trend (M05) and erosion (rusle.py) as modifiers. Weights documented in docs/METHODOLOGY.md.
"""

from __future__ import annotations

import math
from collections import Counter

from terraloop_schemas import CropSpec, Rotation


def family_shannon_index(rotation: Rotation, crops: dict[str, CropSpec]) -> float:
    """Shannon diversity of botanical families across the rotation (implemented example)."""
    fams = Counter(crops[s.crop_id].family for s in rotation.steps if s.crop_id in crops)
    total = sum(fams.values())
    if total == 0:
        return 0.0
    return round(-sum((n / total) * math.log(n / total) for n in fams.values()), 3)


def rothc_lite(*args, **kwargs):
    raise NotImplementedError("TASK-M05")


def n_balance(*args, **kwargs):
    raise NotImplementedError("TASK-M06")


def soil_health_score(*args, **kwargs):
    raise NotImplementedError("TASK-M07")
