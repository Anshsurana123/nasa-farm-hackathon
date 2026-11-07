"""Rotation candidate generation with Indian agro-climatic & calendar constraints. (TASK-O01)

A rotation = for each year, one crop (or 'fallow') per season slot (Kharif, Rabi, Zaid).
Hard constraints:
  * Crop thermal type matches the season (warm/cool)
  * Crop duration fits the season slot (Zaid restricted to <=80d summer pulses/green manure)
  * Dhaincha (green manure, Rs 0 grain revenue) restricted strictly to pre-Kharif Zaid slot
  * Fodder crops (berseem) included only when constraints.has_livestock is True
  * Total planted duration + turnaround days within each year <= 365 days
  * No same crop in consecutive planted slots; respect CropSpec.bad_predecessors
  * must_grow crops appear at least once; excluded crops never appear
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


# Standard Indian 3-season agro-climatic calendar: Kharif (Monsoon), Rabi (Winter), Zaid (Summer)
PUNJAB_SEASONS: tuple[SeasonSlot, ...] = (
    SeasonSlot("kharif", (6, 7), 165, "warm"),
    SeasonSlot("rabi", (10, 11), 175, "cool"),
    SeasonSlot("zaid", (4,), 75, "warm", optional=True),
)

# Southern / Coastal Tropical India (Thanjavur / Cauvery Delta: frost-free winter allows warm crops)
SOUTHERN_DELTA_SEASONS: tuple[SeasonSlot, ...] = (
    SeasonSlot("kharif_kuruvai", (6, 7), 135, "warm"),
    SeasonSlot("rabi_samba", (10, 11), 150, "warm"),
    SeasonSlot("summer_navarai", (2, 3), 80, "warm", optional=True),
)


def crops_for_slot(slot: SeasonSlot, crops: dict[str, CropSpec], constraints: FarmConstraints) -> list[str]:
    """Filter crops eligible for a specific seasonal slot."""
    ids: list[str] = []
    is_zaid = slot.name in ("zaid", "summer_navarai", "bridge")

    for c in crops.values():
        if c.id in constraints.exclude:
            continue
        if not constraints.has_livestock and c.group == "fodder":
            continue
        if slot.thermal not in c.season_type:
            continue

        if is_zaid:
            # No summer Zaid crop in hot April-May on strictly rainfed fields
            if constraints.irrigation == "none":
                continue
            # Only true short-duration summer crops (moong, urad, dhaincha) fit the 65-day Zaid gap
            if c.duration_days[1] > 80 or c.id not in ("moong", "urad", "dhaincha"):
                continue
        else:
            # Cover/green-manure crops with 0 grain yield (dhaincha) belong in Zaid, not main Kharif/Rabi
            if c.group == "cover":
                continue
            # Strictly rainfed fields cannot support paddy rice or irrigation-dependent crops
            if constraints.irrigation == "none" and (
                c.id in ("rice_puddled", "rice_short", "rice_dsr", "basmati", "sugarcane", "potato", "sunflower")
                or c.water_requirement_mm[0] > 650
            ):
                continue
            if c.duration_days[0] > slot.max_duration_days:
                continue

        ids.append(c.id)

    if slot.optional and FALLOW not in ids:
        ids.append(FALLOW)
    return ids


def _step_duration_days(crop_id: str, crops: dict[str, CropSpec]) -> int:
    """Effective field occupancy duration (days) for calendar feasibility checking."""
    if crop_id == FALLOW or crop_id not in crops:
        return 0
    if crop_id == "rice_puddled":
        return 132  # Transplanted field occupancy (June 20 - Oct 30)
    if crop_id == "rice_short":
        return 96   # PR-126 transplanted field occupancy (June 25 - Sept 29)
    if crop_id == "rice_dsr":
        return 115  # Direct-seeded rice occupancy (June 10 - Oct 3)
    if crop_id == "basmati":
        return 118  # Transplanted July 8 - Nov 3
    if crop_id == "wheat":
        return 135  # Timely sown Rabi wheat (Nov 8 - Mar 23)
    if crop_id == "moong":
        return 60   # Summer Sathi Moong (Apr 10 - Jun 9)
    c = crops[crop_id]
    return round(0.5 * (c.duration_days[0] + c.duration_days[1]))


def is_valid(
    sequence: list[str],
    crops: dict[str, CropSpec],
    constraints: FarmConstraints,
    slots_per_year: int = 3,
) -> bool:
    """Check agronomic & 365-day calendar constraints on a flat, cyclic sequence of crop IDs."""
    planted = [c for c in sequence if c != FALLOW]
    if not planted:
        return False

    if len(planted) > 1:
        for a, b in zip(planted, planted[1:] + planted[:1], strict=False):
            if a == b:
                return False
            if b in crops and a in crops[b].bad_predecessors:
                return False

    # Enforce <= 365-day annual calendar feasibility per year (allowing 12 days per crop for harvest & sowing turnaround)
    n_years = max(1, len(sequence) // slots_per_year)
    for y in range(n_years):
        yr_slice = sequence[y * slots_per_year : (y + 1) * slots_per_year]
        yr_planted = [cid for cid in yr_slice if cid != FALLOW]
        total_days = sum(_step_duration_days(cid, crops) for cid in yr_planted) + 12 * len(yr_planted)
        if total_days > 360:
            return False
        # Long-duration Kharif crops (cotton, pigeon_pea, rice_puddled) cannot fit a 3rd Zaid crop in the same year
        if len(yr_slice) >= 3 and yr_slice[2] != FALLOW and yr_slice[0] in ("rice_puddled", "cotton", "pigeon_pea"):
            return False
        # A 3-crop intensive annual cycle requires a short-duration Zaid legume/cover (<= 68d, e.g. summer moong/dhaincha)
        # and at least one staple cereal crop in Kharif or Rabi
        if len(yr_planted) == 3:
            if _step_duration_days(yr_slice[2], crops) > 68:
                return False
            if not any(crops[cid].group == "cereal" for cid in yr_planted[:2] if cid in crops):
                return False

    return all(m in sequence for m in constraints.must_grow)


def _assign_step_practices(crop_id: str, prev_crop_id: str, season_index: int) -> list[str]:
    """Assign realistic conservation agriculture practices to candidate rotation steps."""
    if crop_id == FALLOW:
        return ["residue_retained"]
    if crop_id == "rice_dsr":
        return ["direct_seeded", "residue_retained"]
    if crop_id in ("rice_short", "basmati"):
        return ["residue_retained"]
    if crop_id == "rice_puddled":
        return ["puddling", "residue_retained"]
    if crop_id == "wheat":
        if prev_crop_id in ("rice_short", "rice_dsr", "basmati", "rice_puddled", "maize", "soybean"):
            return ["happy_seeder", "zero_till", "residue_retained"]
        return ["zero_till", "residue_retained"]
    if crop_id in ("mustard", "chickpea", "lentil", "barley"):
        return ["zero_till", "residue_retained"]
    return ["residue_retained"]


def compute_turnaround_days(rotation: Rotation, crops: dict[str, CropSpec]) -> int:
    """Compute harvest-to-sowing turnaround days between Kharif harvest and Rabi sowing.

    In North-West India, <15 days turnaround between late puddled rice harvest (late Oct)
    and optimal wheat sowing (Nov 1-15) is the primary driver of stubble burning.
    """
    kharif_steps = [s for s in rotation.steps if s.season_index == 0 and s.crop_id != FALLOW]
    if not kharif_steps:
        return 30
    k_cid = kharif_steps[0].crop_id
    if k_cid == "rice_puddled":
        return 11
    if k_cid == "basmati":
        return 16
    if k_cid == "cotton":
        return 18
    if k_cid == "rice_dsr":
        return 26
    if k_cid == "rice_short":
        return 30
    if k_cid in ("maize", "soybean", "groundnut", "pearl_millet", "sorghum", "moong", "urad"):
        return 34
    if k_cid == "pigeon_pea":
        return 22
    dur = _step_duration_days(k_cid, crops)
    return int(max(10, min(42, 155 - dur)))


def _format_rotation_label(seq: list[str], crops: dict[str, CropSpec], slots_per_year: int) -> str:
    """Build a clean, human-readable rotation label."""
    names = []
    for cid in seq:
        if cid == FALLOW:
            names.append("Fallow")
        elif cid in crops:
            short_name = crops[cid].name.split("(")[0].strip()
            if cid == "rice_short":
                short_name = "Short Rice (PR-126)"
            elif cid == "rice_dsr":
                short_name = "DSR Rice"
            elif cid == "rice_puddled":
                short_name = "Puddled Rice"
            names.append(short_name)
        else:
            names.append(cid.replace("_", " ").title())
    return " → ".join(names)


def generate_rotations(
    crops: dict[str, CropSpec],
    constraints: FarmConstraints,
    seasons: tuple[SeasonSlot, ...] = PUNJAB_SEASONS,
    max_candidates: int = 600,
) -> list[Rotation]:
    """Generate agronomically valid, diverse candidate rotations (1-year or multi-year alternating)."""
    per_slot = [crops_for_slot(s, crops, constraints) for s in seasons]
    slots_per_yr = len(seasons)

    one_yr_seqs: list[list[str]] = []
    for combo in itertools.product(*per_slot):
        seq = list(combo)
        if not is_valid(seq, crops, constraints, slots_per_year=slots_per_yr):
            continue
        one_yr_seqs.append(seq)
        if len(one_yr_seqs) >= max_candidates:
            break

    eff_years = max(1, min(int(constraints.rotation_years or 1), 3))
    out: list[Rotation] = []

    if eff_years == 1:
        for seq in one_yr_seqs:
            steps: list[RotationStep] = []
            for i, cid in enumerate(seq):
                prev_cid = seq[i - 1] if i > 0 else seq[-1]
                s_idx = i % slots_per_yr
                practices = _assign_step_practices(cid, prev_cid, s_idx)
                steps.append(
                    RotationStep(
                        year_index=0,
                        season_index=s_idx,
                        crop_id=cid,
                        sowing_doy=None,
                        practices=practices,
                    )
                )
            label = _format_rotation_label(seq, crops, slots_per_yr)
            out.append(Rotation(id=f"r{len(out):04d}", steps=steps, label=label))
        return out

    # Multi-year horizon (2 or 3 years): combine complementary 1-year sequences into alternating cycles
    pool = one_yr_seqs[:14]
    for y1_seq in pool:
        for y2_seq in pool:
            if y1_seq == y2_seq:
                continue
            # Prefer alternating Kharif or Rabi crop family across years to break pest/weed cycles
            if y1_seq[0] == y2_seq[0] and y1_seq[1] == y2_seq[1]:
                continue
            full_seq: list[str] = []
            for yr in range(eff_years):
                full_seq.extend(y1_seq if yr % 2 == 0 else y2_seq)
            if not is_valid(full_seq, crops, constraints, slots_per_year=slots_per_yr):
                continue

            steps = []
            for i, cid in enumerate(full_seq):
                prev_cid = full_seq[i - 1] if i > 0 else full_seq[-1]
                s_idx = i % slots_per_yr
                practices = _assign_step_practices(cid, prev_cid, s_idx)
                steps.append(
                    RotationStep(
                        year_index=i // slots_per_yr,
                        season_index=s_idx,
                        crop_id=cid,
                        sowing_doy=None,
                        practices=practices,
                    )
                )
            lbl1 = _format_rotation_label(y1_seq, crops, slots_per_yr)
            lbl2 = _format_rotation_label(y2_seq, crops, slots_per_yr)
            label = f"Yr1: {lbl1} ⇄ Yr2: {lbl2}" if eff_years == 2 else f"3-Yr Cycle: {lbl1} ⇄ {lbl2}"
            out.append(Rotation(id=f"r{len(out):04d}", steps=steps, label=label))
            if len(out) >= max_candidates:
                break
        if len(out) >= max_candidates:
            break

    # Also include steady multi-year repetitions if pool was small
    for seq in one_yr_seqs[:10]:
        if len(out) >= max_candidates:
            break
        full_seq = seq * eff_years
        steps = []
        for i, cid in enumerate(full_seq):
            prev_cid = full_seq[i - 1] if i > 0 else full_seq[-1]
            s_idx = i % slots_per_yr
            practices = _assign_step_practices(cid, prev_cid, s_idx)
            steps.append(
                RotationStep(
                    year_index=i // slots_per_yr,
                    season_index=s_idx,
                    crop_id=cid,
                    sowing_doy=None,
                    practices=practices,
                )
            )
        label = _format_rotation_label(seq, crops, slots_per_yr)
        out.append(Rotation(id=f"r{len(out):04d}", steps=steps, label=label))

    return out


def baseline_rice_wheat(years: int = 1) -> Rotation:
    """Punjab / Indo-Gangetic baseline: puddled rice (kharif) -> wheat (rabi) -> fallow (zaid), residue burnt."""
    steps = []
    for y in range(years):
        steps += [
            RotationStep(year_index=y, season_index=0, crop_id="rice_puddled", practices=["puddling", "burning", "residue_burnt"]),
            RotationStep(year_index=y, season_index=1, crop_id="wheat", practices=["conventional", "burning", "residue_burnt"]),
            RotationStep(year_index=y, season_index=2, crop_id=FALLOW),
        ]
    return Rotation(id="baseline", steps=steps, label="Puddled Rice → Wheat → Fallow (Residue Burnt)", is_baseline=True)


def derive_seasons(profile: FieldProfile) -> tuple[SeasonSlot, ...]:
    """Determine seasonal slots for Indian agro-climatic zones."""
    lat = profile.field.lat
    c = profile.climate
    # Southern Coastal / Peninsular India with warm frost-free winter (e.g. Thanjavur Cauvery Delta)
    if lat < 16.5 and c.frost_days_per_year == 0 and min(c.monthly_tmin_c) >= 18.0:
        return SOUTHERN_DELTA_SEASONS
    return PUNJAB_SEASONS


def derive_baseline_rotation(
    profile: FieldProfile,
    crops: dict[str, CropSpec] | None = None,
    years: int = 1,
    baseline_override: list[str] | None = None,
) -> Rotation:
    """Determine the 1-year baseline rotation for an Indian field location.

    Precedence:
      1. Explicit farmer baseline confirmation (`baseline_override`).
      2. Observed satellite crop history (grouped into a single 1-year Kharif -> Rabi -> Zaid cycle).
      3. Indian agro-climatic zone benchmark (North-West Rice-Wheat, Malwa/Vidarbha Cotton, Bundelkhand Sorghum-Wheat, Cauvery Rice-Rice-Pulse).
    """
    lat = profile.field.lat
    lon = profile.field.lon
    burning = bool(profile.hazards.residue_burning_detected)

    # 1. Farmer explicit baseline override
    if baseline_override and len(baseline_override) >= 1:
        clean_ids = [cid for cid in baseline_override[:3] if cid]
        while len(clean_ids) < 3:
            clean_ids.append(FALLOW)
        steps = []
        for y in range(years):
            for s_idx, cid in enumerate(clean_ids):
                prac = ["burning", "residue_burnt"] if (burning and s_idx == 1 and clean_ids[0] == "rice_puddled") else (
                    ["puddling"] if cid == "rice_puddled" else []
                )
                steps.append(RotationStep(year_index=y, season_index=s_idx, crop_id=cid, practices=prac))
        label = _format_rotation_label(clean_ids, crops or {}, 3)
        return Rotation(id="farmer_confirmed_baseline", steps=steps, label=f"Confirmed: {label}", is_baseline=True)

    # 2. Observed satellite crop history — group into ONE 1-year cycle (season 0: Kharif, 1: Rabi, 2: Zaid)
    if profile.crop_history and len(profile.crop_history) >= 2:
        slot_map: dict[int, str] = {}
        # Iterate from oldest to newest so latest year's Kharif (0) and Rabi (1) win
        for h in profile.crop_history:
            if h.crop_id and h.crop_id != FALLOW and h.season_index in (0, 1, 2):
                slot_map[h.season_index] = h.crop_id
        if 0 in slot_map and 1 in slot_map:
            c0 = slot_map[0]
            c1 = slot_map[1]
            c2 = slot_map.get(2, FALLOW)
            steps = []
            for y in range(years):
                p0 = ["puddling", "burning", "residue_burnt"] if (burning and c0 == "rice_puddled") else (["puddling"] if c0 == "rice_puddled" else ["conventional"])
                p1 = ["conventional", "burning", "residue_burnt"] if (burning and c0 == "rice_puddled") else ["conventional"]
                steps.append(RotationStep(year_index=y, season_index=0, crop_id=c0, practices=p0))
                steps.append(RotationStep(year_index=y, season_index=1, crop_id=c1, practices=p1))
                steps.append(RotationStep(year_index=y, season_index=2, crop_id=c2, practices=[]))
            label = _format_rotation_label([c0, c1, c2], crops or {}, 3)
            return Rotation(id="observed_baseline", steps=steps, label=label, is_baseline=True)

    # 3. Regional Indian agro-climatic zone defaults
    # Vidarbha / Deccan Black Cotton Soil Belt
    if 17.5 <= lat <= 23.0 and 75.0 <= lon <= 81.0:
        steps = [
            step
            for y in range(years)
            for step in (
                RotationStep(year_index=y, season_index=0, crop_id="cotton", practices=[]),
                RotationStep(year_index=y, season_index=1, crop_id="chickpea", practices=[]),
                RotationStep(year_index=y, season_index=2, crop_id=FALLOW, practices=[]),
            )
        ]
        return Rotation(id="vidarbha_baseline", steps=steps, label="Cotton → Chickpea → Fallow", is_baseline=True)

    # Bundelkhand / Semi-Arid Central Plateau
    if 23.5 <= lat <= 26.8 and 77.5 <= lon <= 81.5:
        steps = [
            step
            for y in range(years)
            for step in (
                RotationStep(year_index=y, season_index=0, crop_id="sorghum", practices=[]),
                RotationStep(year_index=y, season_index=1, crop_id="wheat", practices=[]),
                RotationStep(year_index=y, season_index=2, crop_id=FALLOW, practices=[]),
            )
        ]
        return Rotation(id="bundelkhand_baseline", steps=steps, label="Sorghum → Wheat → Fallow", is_baseline=True)

    # Southern Coastal Delta (Thanjavur / Cauvery)
    if lat < 16.5:
        steps = [
            step
            for y in range(years)
            for step in (
                RotationStep(year_index=y, season_index=0, crop_id="rice_puddled", practices=["puddling"]),
                RotationStep(year_index=y, season_index=1, crop_id="rice_puddled", practices=["puddling"]),
                RotationStep(year_index=y, season_index=2, crop_id=FALLOW, practices=[]),
            )
        ]
        return Rotation(id="delta_baseline", steps=steps, label="Puddled Rice → Puddled Rice → Fallow", is_baseline=True)

    # Default Indo-Gangetic / Punjab baseline: Puddled Rice -> Wheat -> Fallow
    return baseline_rice_wheat(years=years)
