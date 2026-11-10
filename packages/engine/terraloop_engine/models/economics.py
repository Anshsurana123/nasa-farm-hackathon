"""Indian Agricultural Economics, MSP Procurement & Gross Margins. (TASK-M08)

Provides crop-specific Minimum Support Price (MSP) / Mandi realizations, cost of
cultivation (A2+FL), labour requirements, and market price volatility calibrated
against CACP Price Policy Reports (2024-25) and PAU / ICAR Farm Management Studies.
"""

from __future__ import annotations

import functools
import os
from collections.abc import Sequence
from pathlib import Path

import yaml


def _resolve_economics_dir() -> Path:
    if env := os.environ.get("TERRALOOP_ECONOMICS"):
        return Path(env)
    dev = Path(__file__).resolve().parents[3] / "crop-kb" / "economics"
    if dev.exists():
        return dev
    for base in [Path.cwd(), *Path.cwd().parents]:
        cand = base / "packages" / "crop-kb" / "economics"
        if cand.exists():
            return cand
    return dev


_DEFAULT_ECONOMICS_DIR = _resolve_economics_dir()


def detect_region(lat: float, lon: float) -> str:
    """Identify Indian agro-economic zone via unified RegionRegistry."""
    from .. import region_registry
    return region_registry.detect_region_config(lat, lon).region_id


def detect_agro_zone(lat: float, lon: float) -> str:
    """Classify coordinates into one of India's major agro-climatic zones (ICAR / Planning Commission)."""
    from .. import region_registry
    return region_registry.detect_region_config(lat, lon).agro_zone


def get_currency_info(region: str = "punjab") -> dict[str, str]:
    """Return Indian Rupee currency code and symbol."""
    return {"code": "INR", "symbol": "₹"}


@functools.lru_cache(maxsize=4)
def load_economics(region: str = "punjab") -> dict:
    """Load Indian CACP/PAU economics YAML file."""
    path = _DEFAULT_ECONOMICS_DIR / "punjab.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def profit_per_ha(
    crop_id: str,
    yield_t_ha: float,
    practices: Sequence[str] = (),
    region: str = "punjab",
    currency: str | None = "INR",
    price_multiplier: float = 1.0,
    preceded_by_legume: bool = False,
    irrigation: str = "full",
) -> dict[str, float | str]:
    """Calculate gross revenue, cost of cultivation, labour cost, and net profit per hectare.

    Args:
        crop_id: Crop identifier matching crop KB.
        yield_t_ha: Harvested yield in tonnes per hectare.
        practices: Management practices ('no_till', 'zero_till', 'happy_seeder', 'direct_seeded', 'residue_retained').
        region: Economic table identifier (default 'punjab' CACP/MSP).
        currency: 'INR' (default) or 'USD'.
        price_multiplier: Realized market price factor (1.0 = median MSP/mandi price).
        preceded_by_legume: True if preceding season fixed biological nitrogen (saves ~1.2 bags Urea/ha).
        irrigation: Irrigation regime ('full', 'limited', or 'none'). Rainfed dryland regimes
            incur lower irrigation pumping and input costs per CACP dryland state budgets.

    Returns:
        dict with revenue_per_ha, cost_per_ha, labor_cost_per_ha, profit_per_ha,
        market_risk, procurement_type, currency.
    """
    econ = load_economics(region)
    crop_data = econ.get("crops", {}).get(crop_id, {})
    usd_rate = float(econ.get("usd_exchange_rate", 83.5))

    price_inr = float(crop_data.get("price_per_tonne", 24000.0)) * float(price_multiplier)
    cost_inr = float(crop_data.get("cost_per_ha", 28000.0))
    labor_inr = float(crop_data.get("labor_cost_per_ha", round(cost_inr * 0.30)))
    market_risk = float(crop_data.get("market_risk", 0.12))
    procurement_type = str(crop_data.get("procurement_type", "nafed_pss"))

    if irrigation == "none":
        # CACP rainfed dryland state A2+FL cost vs high-input irrigated Punjab A2+FL cost
        cost_inr *= 0.62
        labor_inr *= 0.72
    elif irrigation == "limited":
        cost_inr *= 0.88
        labor_inr *= 0.92

    # Practice-based adjustments to operating & labour costs (PAU Farm Management budgets)
    if any(p in ("no_till", "zero_till", "happy_seeder", "direct_seeded") for p in practices):
        # Saves 3-4 tillage/puddling tractor passes (~Rs 3,800/ha diesel) and transplanting labour
        cost_inr *= 0.90
        labor_inr *= 0.82

    if "happy_seeder" in practices:
        # Custom hiring charge for Happy Seeder / Super Seeder (~Rs 1,500/ha net after diesel savings)
        cost_inr += 1500.0

    # Biological nitrogen credit from preceding legume saves ~25-30 kg N/ha (~Rs 1,200/ha in Urea/fertilizer)
    if preceded_by_legume and crop_id not in ("moong", "urad", "chickpea", "lentil", "pigeon_pea", "soybean", "groundnut", "dhaincha", "berseem"):
        cost_inr = max(5000.0, cost_inr - 1200.0)

    revenue_inr = round(yield_t_ha * price_inr, 0)
    cost_inr = round(cost_inr, 0)
    labor_inr = round(labor_inr, 0)
    net_profit_inr = round(revenue_inr - cost_inr, 0)

    target_currency = (currency or "INR").upper()
    if target_currency == "USD":
        return {
            "revenue_per_ha": round(revenue_inr / usd_rate, 2),
            "cost_per_ha": round(cost_inr / usd_rate, 2),
            "labor_cost_per_ha": round(labor_inr / usd_rate, 2),
            "profit_per_ha": round(net_profit_inr / usd_rate, 2),
            "market_risk": market_risk,
            "procurement_type": procurement_type,
            "currency": "USD",
        }

    return {
        "revenue_per_ha": revenue_inr,
        "cost_per_ha": cost_inr,
        "labor_cost_per_ha": labor_inr,
        "profit_per_ha": net_profit_inr,
        "market_risk": market_risk,
        "procurement_type": procurement_type,
        "currency": "INR",
    }
