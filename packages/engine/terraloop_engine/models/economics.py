"""Agricultural economics & gross margins. (TASK-M08, Global Extensions)

Provides crop-specific price, cost of cultivation, and net operating margins
calibrated against regional agricultural economics budgets (UC Davis for California,
ISU Ag Decision Maker for US Corn Belt, Tegemeo/ICRISAT for East Africa,
CACP/PAU for Punjab, and World Bank/FAOSTAT globally).
"""

from __future__ import annotations

import functools
from collections.abc import Sequence
from pathlib import Path

import yaml

_DEFAULT_ECONOMICS_DIR = Path(__file__).resolve().parents[3] / "crop-kb" / "economics"


def detect_region(lat: float, lon: float) -> str:
    """Dynamically deduce geographic economic region from coordinates."""
    # California / US Pacific
    if (32.0 <= lat <= 42.5) and (-125.0 <= lon <= -114.0):
        return "california"
    # US Corn Belt / Midwest
    if (36.0 <= lat <= 49.0) and (-105.0 <= lon <= -80.0):
        return "us_cornbelt"
    # East Africa (Kenya, Tanzania, Uganda, Ethiopia)
    if (-15.0 <= lat <= 12.0) and (25.0 <= lon <= 52.0):
        return "east_africa"
    # South Asia / Indo-Gangetic Plain / Punjab
    if (20.0 <= lat <= 35.0) and (68.0 <= lon <= 90.0):
        return "punjab"
    # Default to global benchmark economics
    return "global"


def get_currency_info(region: str) -> dict[str, str]:
    """Get currency code and display symbol for a region."""
    if region == "punjab":
        return {"code": "INR", "symbol": "₹"}
    return {"code": "USD", "symbol": "$"}


@functools.lru_cache(maxsize=8)
def load_economics(region: str = "global") -> dict:
    """Load regional economics YAML file with global fallback."""
    path = _DEFAULT_ECONOMICS_DIR / f"{region}.yaml"
    if not path.exists():
        # Fall back to global benchmark
        path = _DEFAULT_ECONOMICS_DIR / "global.yaml"
    if not path.exists():
        # Fallback to punjab if global file missing
        path = _DEFAULT_ECONOMICS_DIR / "punjab.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def profit_per_ha(
    crop_id: str,
    yield_t_ha: float,
    practices: Sequence[str] = (),
    region: str = "punjab",
    currency: str | None = None,
) -> dict[str, float]:
    """Calculate gross margin / net operating profit per hectare.

    Args:
        crop_id: Crop identifier matching crop KB.
        yield_t_ha: Crop yield in tonnes per hectare.
        practices: Management practices (e.g. 'no_till', 'residue_retained', 'burning').
        region: Geographic region for prices/costs ('california', 'us_cornbelt', 'east_africa', 'punjab', 'global').
        currency: 'USD' or 'INR' (defaults to regional currency).

    Returns:
        dict with revenue_per_ha, cost_per_ha, profit_per_ha, currency.
    """
    econ = load_economics(region)
    crop_data = econ.get("crops", {}).get(crop_id)
    usd_rate = econ.get("usd_exchange_rate", 1.0 if region != "punjab" else 83.0)

    if not crop_data:
        # Fallback to global economics file if crop missing in regional budget
        global_econ = load_economics("global")
        crop_data = global_econ.get("crops", {}).get(crop_id)

    if not crop_data:
        # Generic heuristic for uncatalogued crop
        price_usd = 300.0
        cost_usd = 450.0
    else:
        price_usd = crop_data.get("price_usd_per_tonne", crop_data.get("price_per_tonne", 300.0))
        cost_usd = crop_data.get("cost_usd_per_ha", crop_data.get("cost_per_ha", 450.0))

    # Practice-based adjustments to operating costs
    # Zero-till / direct-seeding saves tractor fuel and land preparation passes
    if "no_till" in practices or "zero_till" in practices or "direct_seeded" in practices:
        cost_usd *= 0.90  # ~10% operational savings

    # Machinery surcharge for straw-management machinery (Happy Seeder / Mulcher)
    if "residue_retained" in practices and ("wheat" in crop_id or "rice" in crop_id or "maize" in crop_id):
        cost_usd += 18.0  # ~$18 / ha equipment pass

    revenue_usd = round(yield_t_ha * price_usd, 2)
    net_profit_usd = round(revenue_usd - cost_usd, 2)

    # Determine output currency
    target_currency = currency.upper() if currency else ("INR" if region == "punjab" else "USD")

    if target_currency == "INR":
        rate = usd_rate if usd_rate > 1.0 else 83.0
        return {
            "revenue_per_ha": round(revenue_usd * rate, 0),
            "cost_per_ha": round(cost_usd * rate, 0),
            "profit_per_ha": round(net_profit_usd * rate, 0),
            "currency": "INR",
        }

    return {
        "revenue_per_ha": revenue_usd,
        "cost_per_ha": round(cost_usd, 2),
        "profit_per_ha": net_profit_usd,
        "currency": "USD",
    }
