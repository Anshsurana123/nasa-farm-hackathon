"""Rotation candidate generation with hard agronomic constraints. (TASK-O01)

Implemented: season templates + constrained enumeration for small search spaces.
Pending   : evaluator (O02), NSGA-II for large spaces (O03), surrogate (O05).

A rotation = for each year, one crop (or 'fallow') per season slot.
Hard constraints (build plan 5.5):
  * crop thermal type matches the season (warm/cool)
  * crop's minimum duration fits the season window
  * no same crop in consecutive planted slots; respect CropSpec.bad_predecessors
  * must_grow crops appear at least once; excluded crops never appear
Soft (scored, not filtered): botanical family diversity -> soil health score.

Search-space size for Punjab: ~13 kharif x 8 rabi x 3 zaid ~ 300 per year.
rotation_years=1 (annual cycle repeated) is exhaustive; multi-year needs NSGA-II (TASK-O03).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from terraloop_schemas import CropSpec, FarmConstraints, Rotation, RotationStep

FALLOW = "fallow"


@dataclass(frozen=True)
class SeasonSlot:
    name: str
    sowing_months: tuple[int, ...]
    max_duration_days: int
    thermal: str  # "warm" | "cool"
    optional: bool = False  # fallow allowed / expected


# Punjab (and much of the Indo-Gangetic Plain). Other regions: derive from suitability (TODO O01b).
PUNJAB_SEASONS: tuple[SeasonSlot, ...] = (
    SeasonSlot("kharif", (6, 7), 160, "warm"),
    SeasonSlot("rabi", (10, 11), 175, "cool"),
    SeasonSlot("zaid", (4,), 75, "warm", optional=True),
)


def crops_for_slot(slot: SeasonSlot, crops: dict[str, CropSpec], constraints: FarmConstraints) -> list[str]:
    ids = [
        c.id
        for c in crops.values()
        if slot.thermal in c.season_type
        and c.duration_days[0] <= slot.max_duration_days
        and c.id not in constraints.exclude
    ]
    if slot.optional:
        ids.append(FALLOW)
    return ids


def _family(crop_id: str, crops: dict[str, CropSpec]) -> str | None:
    return None if crop_id == FALLOW else crops[crop_id].family.value


def is_valid(sequence: list[str], crops: dict[str, CropSpec], constraints: FarmConstraints) -> bool:
    """Check constraints on a flat, cyclic sequence of crop ids (slot order).

    NOTE: same *family* back-to-back (e.g. maize -> wheat, both Poaceae) is allowed on purpose;
    it is penalised softly via family_shannon_index in the soil health score (TASK-M07).
    """
    planted = [c for c in sequence if c != FALLOW]
    if len(planted) > 1:
        for a, b in zip(planted, planted[1:] + planted[:1]):  # cyclic: rotation repeats
            if a == b:
                return False
            if a in crops[b].bad_predecessors:
                return False
    return all(m in sequence for m in constraints.must_grow)


def generate_rotations(
    crops: dict[str, CropSpec],
    constraints: FarmConstraints,
    seasons: tuple[SeasonSlot, ...] = PUNJAB_SEASONS,
    max_candidates: int = 5000,
) -> list[Rotation]:
    """Enumerate valid rotations for ``constraints.rotation_years`` years.

    Enumeration explodes quickly (options ** (slots*years)); for > ~1e5 combinations
    switch to NSGA-II sampling (TASK-O03). We cap with ``max_candidates``.
    """
    per_slot = [crops_for_slot(s, crops, constraints) for s in seasons]
    slot_choices = per_slot * constraints.rotation_years
    out: list[Rotation] = []
    for combo in itertools.product(*slot_choices):
        seq = list(combo)
        if not is_valid(seq, crops, constraints):
            continue
        steps = [
            RotationStep(
                year_index=i // len(seasons),
                season_index=i % len(seasons),
                crop_id=cid,
                sowing_doy=None,
            )
            for i, cid in enumerate(seq)
        ]
        out.append(Rotation(id=f"r{len(out):05d}", steps=steps, label=" > ".join(seq)))
        if len(out) >= max_candidates:
            break
    return out


def baseline_rice_wheat(years: int = 1) -> Rotation:
    """Punjab baseline: puddled rice (kharif) - wheat (rabi) - fallow (zaid), residue burnt."""
    steps = []
    for y in range(years):
        steps += [
            RotationStep(year_index=y, season_index=0, crop_id="rice_puddled", practices=["puddling"]),
            RotationStep(year_index=y, season_index=1, crop_id="wheat", practices=["residue_burnt"]),
            RotationStep(year_index=y, season_index=2, crop_id=FALLOW),
        ]
    return Rotation(id="baseline", steps=steps, label="Rice > Wheat > Fallow", is_baseline=True)
