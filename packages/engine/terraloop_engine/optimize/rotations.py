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

from terraloop_schemas import CropSpec, FarmConstraints, FieldProfile, Rotation, RotationStep

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


def derive_seasons(profile: FieldProfile) -> tuple[SeasonSlot, ...]:
    """Dynamically determine season slots for any field location globally.

    Analyzes latitude, hemisphere, frost frequency, and temperature seasonality:
      - Cold temperate (e.g. Iowa, Canada, Northern Europe): Main summer warm slot + overwinter cover
      - Southern Hemisphere (e.g. Australia, Brazil): Summer (Nov-Jan) + Winter (May-Jun)
      - Equatorial Bimodal (e.g. Kenya, East Africa): Long rains (Mar-Apr) + Short rains (Oct-Nov)
      - Mediterranean / California (e.g. Central Valley): Summer warm slot (Apr-May) + Winter cool slot (Oct-Nov) + optional bridge
      - South Asia / Indo-Gangetic (e.g. Punjab): Kharif (Jun-Jul) + Rabi (Oct-Nov) + Zaid (Apr)
    """
    lat = profile.field.lat
    c = profile.climate

    # 1. Southern Hemisphere (lat < -10)
    if lat < -10.0:
        return (
            SeasonSlot("summer", (11, 12, 1), 150, "warm"),
            SeasonSlot("winter", (5, 6), 160, "cool"),
            SeasonSlot("bridge", (3, 4), 75, "warm", optional=True),
        )

    # 2. Equatorial Bimodal (-10 <= lat <= 12 and East Africa or low annual temperature range)
    temp_swing = max(c.monthly_tmax_c) - min(c.monthly_tmax_c)
    if -10.0 <= lat <= 12.0 and (20.0 <= profile.field.lon <= 52.0 or temp_swing < 10.0):
        return (
            SeasonSlot("long_rains", (3, 4), 140, "warm"),
            SeasonSlot("short_rains", (10, 11), 120, "warm"),
        )

    # 3. California / Mediterranean (lat 32-45 in Western US / Mediterranean Europe)
    if (32.0 <= lat <= 44.0) and (profile.field.lon < -110.0 or -10.0 <= profile.field.lon <= 35.0):
        return (
            SeasonSlot("summer", (4, 5), 170, "warm"),
            SeasonSlot("winter", (10, 11), 180, "cool"),
            SeasonSlot("bridge", (3,), 70, "warm", optional=True),
        )

    # 4. Cold Continental / Temperate Single Main Season (frost_days >= 50 or severe winter)
    if c.frost_days_per_year >= 50 or min(c.monthly_tmin_c) < -3.0:
        return (
            SeasonSlot("summer_main", (5, 6), 160, "warm"),
            SeasonSlot("overwinter_cover", (9, 10), 200, "cool", optional=True),
        )

    # 5. Default Subtropical / Indo-Gangetic / South Asia
    return PUNJAB_SEASONS


def derive_baseline_rotation(
    profile: FieldProfile,
    crops: dict[str, CropSpec] | None = None,
    years: int = 1,
) -> Rotation:
    """Dynamically determine the baseline rotation for any location worldwide.

    Precedence:
      1. Observed satellite crop history (if >= 2 seasons detected from HLS/MODIS).
      2. Regional ag-economic baselines (California, Iowa, Kenya, Punjab).
      3. Global fallback from suitable staple crops.
    """
    lat = profile.field.lat
    lon = profile.field.lon

    # Check observed satellite crop history first
    if profile.crop_history and len(profile.crop_history) >= 2:
        recent_crops = [h.crop_id for h in profile.crop_history[-3:] if h.crop_id != FALLOW]
        if len(recent_crops) >= 2 and crops:
            steps = []
            for y in range(years):
                for s_idx, cid in enumerate(recent_crops):
                    steps.append(RotationStep(year_index=y, season_index=s_idx, crop_id=cid, practices=[]))
            label = " > ".join(c.replace("_", " ").title() for c in recent_crops)
            return Rotation(id="observed_baseline", steps=steps, label=f"Observed: {label}", is_baseline=True)

    # California / US Pacific: Grain Corn > Winter Wheat
    if (32.0 <= lat <= 42.5) and (-125.0 <= lon <= -114.0):
        steps = []
        for y in range(years):
            steps.append(RotationStep(year_index=y, season_index=0, crop_id="maize", practices=["conventional_tillage"]))
            steps.append(RotationStep(year_index=y, season_index=1, crop_id="wheat", practices=["conventional_tillage"]))
            steps.append(RotationStep(year_index=y, season_index=2, crop_id=FALLOW))
        return Rotation(id="california_baseline", steps=steps, label="Grain Corn > Winter Wheat > Fallow", is_baseline=True)

    # US Corn Belt / Midwest: Corn > Soy
    if (36.0 <= lat <= 49.0) and (-105.0 <= lon <= -80.0):
        steps = []
        for y in range(years):
            steps.append(RotationStep(year_index=y, season_index=0, crop_id="maize", practices=["conventional_tillage"]))
            steps.append(RotationStep(year_index=y, season_index=1, crop_id="soybean", practices=["conventional_tillage"]))
        return Rotation(id="cornbelt_baseline", steps=steps, label="Corn > Soybean", is_baseline=True)

    # East Africa (Kenya, etc.): Maize > Pigeonpea
    if (-15.0 <= lat <= 12.0) and (25.0 <= lon <= 52.0):
        steps = []
        for y in range(years):
            steps.append(RotationStep(year_index=y, season_index=0, crop_id="maize", practices=["conventional_tillage"]))
            steps.append(RotationStep(year_index=y, season_index=1, crop_id="pigeon_pea", practices=["conventional_tillage"]))
        return Rotation(id="east_africa_baseline", steps=steps, label="Maize > Pigeonpea", is_baseline=True)

    # South Asia / Punjab: Puddled Rice > Wheat > Fallow
    if (20.0 <= lat <= 35.0) and (68.0 <= lon <= 90.0):
        return baseline_rice_wheat(years=years)

    # Global default based on staples: Maize > Wheat
    steps = []
    for y in range(years):
        c1 = "maize" if crops and "maize" in crops else "wheat"
        c2 = "wheat" if crops and "wheat" in crops else FALLOW
        steps.append(RotationStep(year_index=y, season_index=0, crop_id=c1))
        steps.append(RotationStep(year_index=y, season_index=1, crop_id=c2))
    return Rotation(id="global_baseline", steps=steps, label="Maize > Wheat", is_baseline=True)
