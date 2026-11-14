"""Government Agricultural Scheme Knowledge Base Loader & Matcher (WS-E).

Loads central and state schemes from ``packages/crop-kb/schemes/*.yaml``.
Zero hardcoded scheme names or ₹ amounts in Python or TSX.
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMES_DIR = REPO_ROOT / "packages" / "crop-kb" / "schemes"


@functools.lru_cache(maxsize=1)
def load_all_schemes() -> dict[str, list[dict]]:
    """Load all schemes from YAML files grouped by state/category."""
    if not SCHEMES_DIR.exists():
        # Fallback if installed as package
        pkg_dir = Path(__file__).resolve().parent / "crop_kb" / "schemes"
        target_dir = pkg_dir if pkg_dir.exists() else SCHEMES_DIR
    else:
        target_dir = SCHEMES_DIR

    schemes_by_source: dict[str, list[dict]] = {}
    if not target_dir.exists():
        log.warning("Schemes directory not found at %s", target_dir)
        return schemes_by_source

    for yml in target_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "schemes" in data:
                schemes_by_source[yml.stem] = data["schemes"]
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to load scheme YAML %s: %s", yml, exc)

    return schemes_by_source


def _scheme_title(scheme: dict[str, Any], language: str) -> str:
    """Return scheme display title localized for 'hi'/'pa' with English fallback."""
    if language in ("hi", "pa"):
        localized = scheme.get(f"display_title_{language}")
        if isinstance(localized, str) and localized.strip():
            return localized
    return str(scheme.get("display_title", scheme["name"]))


def get_matching_schemes(
    state: str | None,
    planted_crops: set[str],
    practices: set[str],
    urea_bags_saved: float = 0.0,
    region_id: str | None = None,
    language: str = "en",
) -> list[str]:
    """Return matching central and state government agricultural scheme display titles."""
    if not state:
        return []

    lang = language if language in ("en", "hi", "pa") else "en"
    all_schemes = load_all_schemes()
    matched_titles: list[str] = []
    matched_ids: set[str] = set()

    # 1. State schemes (only if state is determined and matches)
    state_key_map = {
        "haryana": "haryana",
        "punjab": "punjab",
        "maharashtra": "maharashtra",
        "tamil nadu": "tamil_nadu",
        "uttar pradesh": "uttar_pradesh",
    }
    target_key = state_key_map.get(state.lower().strip())
    if target_key and target_key in all_schemes:
        for s in all_schemes[target_key]:
            if _is_scheme_eligible(s, planted_crops, practices, urea_bags_saved, region_id=region_id):
                sid = str(s.get("id", ""))
                if sid:
                    matched_ids.add(sid)
                matched_titles.append(_scheme_title(s, lang))

    # 2. Central schemes (Indian national schemes only when in India)
    central = all_schemes.get("central", [])
    for s in central:
        # Don't duplicate mechanization if state CRM already matched
        if s.get("id") == "smam_mechanization" and (
            "crm_punjab" in matched_ids or "up_crm_mechanization" in matched_ids
        ):
            continue
        if _is_scheme_eligible(s, planted_crops, practices, urea_bags_saved, region_id=region_id):
            matched_titles.append(_scheme_title(s, lang))

    return matched_titles


def _is_scheme_eligible(
    scheme: dict,
    planted_crops: set[str],
    practices: set[str],
    urea_bags_saved: float,
    region_id: str | None = None,
) -> bool:
    eligible_zones = set(scheme.get("eligible_zones") or [])
    if eligible_zones and region_id and region_id not in eligible_zones:
        return False
    # Check trigger on urea saved
    if "trigger_min_urea_bags_saved" in scheme and urea_bags_saved < float(scheme["trigger_min_urea_bags_saved"]):
        return False

    # Check ineligible crops (e.g. Mera Pani forbids puddled paddy)
    ineligible_crops = set(scheme.get("ineligible_crops") or [])
    if ineligible_crops and (planted_crops & ineligible_crops):
        return False

    # Check ineligible practices (e.g. CRM forbids residue burning)
    ineligible_practices = set(scheme.get("ineligible_practices") or [])
    if ineligible_practices and (practices & ineligible_practices):
        return False

    # Check eligible crops
    eligible_crops = set(scheme.get("eligible_crops") or [])
    crops_matched = bool(planted_crops & eligible_crops) if eligible_crops else True

    # Check eligible practices
    eligible_practices = set(scheme.get("eligible_practices") or [])
    practices_matched = bool(practices & eligible_practices) if eligible_practices else True

    # If scheme specified both, requires both or whichever is non-empty
    if eligible_crops and eligible_practices:
        return crops_matched or practices_matched
    if eligible_crops:
        return crops_matched
    if eligible_practices:
        return practices_matched

    # If neither specified (e.g. purely urea trigger), return True
    return True
