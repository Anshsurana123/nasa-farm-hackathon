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

# Southern Hemisphere temperate/subtropical cropping calendar (6-month shifted)
SH_TEMPERATE_SEASONS: tuple[SeasonSlot, ...] = (
    SeasonSlot("sh_summer_wet", (10, 11, 12), 165, "warm"),
    SeasonSlot("sh_winter_cool", (4, 5, 6), 175, "cool"),
    SeasonSlot("sh_spring_catch", (8, 9), 75, "warm", optional=True),
)

CROP_ID_ALIASES: dict[str, str] = {
    "summer_moong": "moong",
    "fodder_sorghum": "sorghum",
    "blackgram": "urad",
    "greengram": "moong",
}


def _normalize_crop_id(cid: str) -> str:
    clean = (cid or "").strip()
    if not clean:
        return FALLOW
    return CROP_ID_ALIASES.get(clean.lower(), clean)


def _default_sowing_doy(crop_id: str, season_index: int, is_delta: bool = False, is_sh: bool = False) -> int | None:
    if not crop_id or crop_id == FALLOW:
        return None
    if season_index == 0:
        doy_map = {
            "rice_dsr": 161,
            "rice_puddled": 171,
            "rice_short": 173,
            "basmati": 189,
            "cotton": 135,
        }
        doy = doy_map.get(crop_id, 176)
    elif season_index == 1:
        if crop_id in ("rice_puddled", "rice_short", "rice_dsr", "basmati") or is_delta:
            doy = 288 if crop_id in ("rice_puddled", "rice_short", "rice_dsr", "basmati") else 300
        else:
            doy = {
                "mustard": 293,
                "chickpea": 300,
                "lentil": 300,
                "potato": 304,
                "barley": 304,
                "wheat": 309,
            }.get(crop_id, 305)
    else:
        doy = 55 if is_delta else 100
    if is_sh:
        return ((doy + 182 - 1) % 365) + 1
    return doy


def crops_for_slot(
    slot: SeasonSlot,
    crops: dict[str, CropSpec],
    constraints: FarmConstraints,
    region_id: str | None = None,
) -> list[str]:
    """Filter crops eligible for a specific seasonal slot."""
    ids: list[str] = []
    is_zaid = slot.name in ("zaid", "summer_navarai", "bridge")
    is_indian_kharif = slot.name in ("kharif", "kharif_kuruvai") and region_id != "unvalidated_global"

    for c in crops.values():
        if c.id in constraints.exclude:
            continue
        if not constraints.has_livestock and c.group == "fodder":
            continue
        if slot.thermal not in c.season_type:
            continue
        # In Indian SW monsoon Kharif slots, sunflower suffers severe waterlogging/head-rot and is cultivated
        # as a Rabi/Spring crop instead (PAU Spring Sunflower Studies), whereas temperate/global summers retain warm sunflower.
        if is_indian_kharif and c.id == "sunflower":
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
    """Effective field occupancy duration (days) for calendar feasibility checking (aligned with fao56_runner)."""
    if crop_id == FALLOW or crop_id not in crops:
        return 0
    if crop_id == "rice_puddled":
        return 126  # Transplanted field occupancy (June 20 - Oct 24)
    if crop_id == "rice_short":
        return 104  # PR-126 transplanted field occupancy (June 22 - Oct 4)
    if crop_id == "rice_dsr":
        return 127  # Direct-seeded rice occupancy (June 10 - Oct 15)
    if crop_id == "basmati":
        return 118  # Transplanted July 8 - Nov 3
    if crop_id == "wheat":
        return 135  # Timely sown Rabi wheat (Nov 5 - Mar 20)
    if crop_id in ("moong", "urad"):
        return 60   # Summer Sathi Moong / Urad catch crop (Apr 10 - Jun 9)
    c = crops[crop_id]
    return round(0.5 * (c.duration_days[0] + c.duration_days[1]))


def is_valid(
    sequence: list[str],
    crops: dict[str, CropSpec],
    constraints: FarmConstraints,
    slots_per_year: int = 3,
    allow_double_rice: bool = False,
) -> bool:
    """Check agronomic & 365-day calendar constraints on a flat, cyclic sequence of crop IDs."""
    planted = [c for c in sequence if c != FALLOW]
    if not planted:
        return False

    if len(planted) > 1:
        for a, b in zip(planted, planted[1:] + planted[:1], strict=False):
            if a == b and not (allow_double_rice and a in ("rice_puddled", "rice_short", "rice_dsr")):
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
        # A 3-crop intensive annual cycle requires a short-duration Zaid legume/cover (<= 68d, e.g. summer moong/urad/dhaincha)
        # and at least one staple cereal crop in Kharif or Rabi
        if len(yr_planted) == 3:
            if _step_duration_days(yr_slice[2], crops) > 68:
                return False
            if not any(crops[cid].group == "cereal" for cid in yr_planted[:2] if cid in crops):
                return False

    return all(m in sequence for m in constraints.must_grow)


def _assign_step_practices(crop_id: str, prev_crop_id: str, season_index: int, is_vertisol: bool = False) -> list[str]:
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
        if is_vertisol and crop_id == "chickpea":
            return ["broad_bed_furrow", "zero_till", "residue_retained"]
        return ["zero_till", "residue_retained"]
    if crop_id in ("moong", "urad") and season_index == 2:
        return ["zero_till", "residue_retained"]
    if is_vertisol and crop_id in ("soybean", "cotton", "pigeon_pea", "sorghum", "maize", "groundnut"):
        return ["broad_bed_furrow", "residue_retained"]
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
    is_vertisol: bool = False,
    region_id: str | None = None,
) -> list[Rotation]:
    """Generate agronomically valid, diverse candidate rotations (1-year or multi-year alternating)."""
    per_slot = [crops_for_slot(s, crops, constraints, region_id=region_id) for s in seasons]
    slots_per_yr = len(seasons)
    is_delta = len(seasons) >= 2 and seasons[0].name == "kharif_kuruvai"
    is_sh = len(seasons) >= 1 and seasons[0].name == "sh_summer_wet"

    one_yr_seqs: list[list[str]] = []
    for combo in itertools.product(*per_slot):
        seq = list(combo)
        if not is_valid(seq, crops, constraints, slots_per_year=slots_per_yr, allow_double_rice=is_delta):
            continue
        one_yr_seqs.append(seq)
        if len(one_yr_seqs) >= max_candidates:
            break

    eff_years = max(1, min(int(constraints.rotation_years or 1), 6))
    out: list[Rotation] = []

    if eff_years == 1:
        for seq in one_yr_seqs:
            steps: list[RotationStep] = []
            for i, cid in enumerate(seq):
                prev_cid = seq[i - 1] if i > 0 else seq[-1]
                s_idx = i % slots_per_yr
                practices = _assign_step_practices(cid, prev_cid, s_idx, is_vertisol=is_vertisol)
                steps.append(
                    RotationStep(
                        year_index=0,
                        season_index=s_idx,
                        crop_id=cid,
                        sowing_doy=_default_sowing_doy(cid, s_idx, is_delta=is_delta, is_sh=is_sh),
                        practices=practices,
                    )
                )
            label = _format_rotation_label(seq, crops, slots_per_yr)
            out.append(Rotation(id=f"r{len(out):04d}", steps=steps, label=label))
        return out

    # Multi-year horizon (2..6 years): combine complementary 1-year sequences into alternating cycles
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
            if not is_valid(full_seq, crops, constraints, slots_per_year=slots_per_yr, allow_double_rice=is_delta):
                continue

            steps = []
            for i, cid in enumerate(full_seq):
                prev_cid = full_seq[i - 1] if i > 0 else full_seq[-1]
                s_idx = i % slots_per_yr
                practices = _assign_step_practices(cid, prev_cid, s_idx, is_vertisol=is_vertisol)
                steps.append(
                    RotationStep(
                        year_index=i // slots_per_yr,
                        season_index=s_idx,
                        crop_id=cid,
                        sowing_doy=_default_sowing_doy(cid, s_idx, is_delta=is_delta, is_sh=is_sh),
                        practices=practices,
                    )
                )
            lbl1 = _format_rotation_label(y1_seq, crops, slots_per_yr)
            lbl2 = _format_rotation_label(y2_seq, crops, slots_per_yr)
            label = f"Yr1: {lbl1} ⇄ Yr2: {lbl2}" if eff_years == 2 else f"{eff_years}-Yr Cycle: {lbl1} ⇄ {lbl2}"
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
            practices = _assign_step_practices(cid, prev_cid, s_idx, is_vertisol=is_vertisol)
            steps.append(
                RotationStep(
                    year_index=i // slots_per_yr,
                    season_index=s_idx,
                    crop_id=cid,
                    sowing_doy=_default_sowing_doy(cid, s_idx, is_delta=is_delta, is_sh=is_sh),
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
    """Determine seasonal slots for agro-climatic zones (North/South India and Southern Hemisphere)."""
    from .. import region_registry
    reg_cfg = region_registry.detect_region_config(profile.field.lat, profile.field.lon)
    if reg_cfg.hemisphere == "SH":
        return SH_TEMPERATE_SEASONS
    if reg_cfg.region_id in ("cauvery", "southern_hills", "west_coast", "islands") and profile.climate.frost_days_per_year == 0:
        return SOUTHERN_DELTA_SEASONS
    return PUNJAB_SEASONS


def derive_baseline_rotation(
    profile: FieldProfile,
    crops: dict[str, CropSpec] | None = None,
    years: int = 1,
    baseline_override: list[str] | None = None,
) -> Rotation:
    """Determine the baseline rotation for a field location.

    Precedence:
      1. Explicit farmer baseline confirmation (`baseline_override`).
      2. Observed satellite crop history (grouped into a single 1-year Kharif -> Rabi -> Zaid cycle).
      3. Regional agro-climatic zone benchmark.
    """
    from .. import region_registry
    lat = profile.field.lat
    lon = profile.field.lon
    burning = bool(profile.hazards.residue_burning_detected)
    reg_cfg = region_registry.detect_region_config(lat, lon)
    is_delta = reg_cfg.region_id in ("cauvery", "southern_hills", "west_coast", "islands") and profile.climate.frost_days_per_year == 0
    is_sh = reg_cfg.hemisphere == "SH"

    # 1. Farmer explicit baseline override
    if baseline_override and len(baseline_override) >= 1:
        clean_ids = [_normalize_crop_id(cid) for cid in baseline_override[:3] if cid]
        while len(clean_ids) < 3:
            clean_ids.append(FALLOW)
        steps = []
        for y in range(years):
            for s_idx, cid in enumerate(clean_ids):
                prac = ["burning", "residue_burnt"] if (burning and s_idx == 1 and clean_ids[0] == "rice_puddled") else (
                    ["puddling"] if cid == "rice_puddled" else []
                )
                steps.append(
                    RotationStep(
                        year_index=y,
                        season_index=s_idx,
                        crop_id=cid,
                        sowing_doy=_default_sowing_doy(cid, s_idx, is_delta=is_delta, is_sh=is_sh),
                        practices=prac,
                    )
                )
        label = _format_rotation_label(clean_ids, crops or {}, 3)
        return Rotation(id="farmer_confirmed_baseline", steps=steps, label=f"Confirmed: {label}", is_baseline=True)

    # 2. Observed satellite crop history — group into ONE 1-year cycle (season 0: Kharif, 1: Rabi, 2: Zaid)
    if profile.crop_history and len(profile.crop_history) >= 2:
        slot_map: dict[int, str] = {}
        # Iterate from oldest to newest so latest year's Kharif (0) and Rabi (1) win
        for h in profile.crop_history:
            cid = _normalize_crop_id(h.crop_id)
            if cid and cid != FALLOW and h.season_index in (0, 1, 2):
                slot_map[h.season_index] = cid
        if 0 in slot_map and 1 in slot_map:
            c0 = slot_map[0]
            c1 = slot_map[1]
            c2 = slot_map.get(2, FALLOW)
            if c0 in ("cotton", "pigeon_pea") and reg_cfg.region_id not in ("cauvery", "southern_hills"):
                c2 = FALLOW
            steps = []
            for y in range(years):
                p0 = ["puddling", "burning", "residue_burnt"] if (burning and c0 == "rice_puddled") else (["puddling"] if c0 == "rice_puddled" else ["conventional"])
                p1 = ["conventional", "burning", "residue_burnt"] if (burning and c0 == "rice_puddled") else (["puddling"] if c1 == "rice_puddled" else ["conventional"])
                steps.append(RotationStep(year_index=y, season_index=0, crop_id=c0, sowing_doy=_default_sowing_doy(c0, 0, is_delta=is_delta, is_sh=is_sh), practices=p0))
                steps.append(RotationStep(year_index=y, season_index=1, crop_id=c1, sowing_doy=_default_sowing_doy(c1, 1, is_delta=is_delta, is_sh=is_sh), practices=p1))
                steps.append(RotationStep(year_index=y, season_index=2, crop_id=c2, sowing_doy=_default_sowing_doy(c2, 2, is_delta=is_delta, is_sh=is_sh), practices=[]))
            label = _format_rotation_label([c0, c1, c2], crops or {}, 3)
            return Rotation(id="observed_baseline", steps=steps, label=label, is_baseline=True)

    # 3. Regional agro-climatic zone defaults loaded from packages/crop-kb/regions/zones.yaml
    base_cids = [_normalize_crop_id(c) for c in region_registry.get_baseline_rotation(lat, lon)]
    while len(base_cids) < 3:
        base_cids.append(FALLOW)
    c0, c1, c2 = base_cids[0], base_cids[1], base_cids[2]

    steps = []
    for y in range(years):
        p0 = ["puddling", "burning", "residue_burnt"] if (burning and c0 == "rice_puddled") else (["puddling"] if c0 == "rice_puddled" else [])
        p1 = ["conventional", "burning", "residue_burnt"] if (burning and c0 == "rice_puddled") else (["puddling"] if c1 == "rice_puddled" else [])
        steps.append(RotationStep(year_index=y, season_index=0, crop_id=c0, sowing_doy=_default_sowing_doy(c0, 0, is_delta=is_delta, is_sh=is_sh), practices=p0))
        steps.append(RotationStep(year_index=y, season_index=1, crop_id=c1, sowing_doy=_default_sowing_doy(c1, 1, is_delta=is_delta, is_sh=is_sh), practices=p1))
        steps.append(RotationStep(year_index=y, season_index=2, crop_id=c2, sowing_doy=_default_sowing_doy(c2, 2, is_delta=is_delta, is_sh=is_sh), practices=[]))

    label = _format_rotation_label([c0, c1, c2], crops or {}, 3)
    return Rotation(id=f"{reg_cfg.region_id}_baseline", steps=steps, label=label, is_baseline=True)
