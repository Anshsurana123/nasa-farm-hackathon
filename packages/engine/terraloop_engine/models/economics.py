"""Indian Agricultural Economics, MSP Procurement & Gross Margins. (TASK-M08, WS-D)

Provides crop-specific Minimum Support Price (MSP) / Mandi realizations, cost of
cultivation (A2+FL), labour requirements, and market price volatility calibrated
against CACP Price Policy Reports (2024-25) and State Agricultural Universities / ICAR.
"""

from __future__ import annotations

import functools
import os
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]


def _resolve_economics_dir() -> Path:
    if env := os.environ.get("TERRALOOP_ECONOMICS"):
        return Path(env)
    dev = REPO_ROOT / "packages" / "crop-kb" / "economics"
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
    """Return currency code and symbol based on region."""
    if region == "unvalidated_global":
        return {"code": "USD", "symbol": "$"}
    return {"code": "INR", "symbol": "₹"}


@functools.lru_cache(maxsize=16)
def load_economics(region_or_state: str = "punjab") -> dict:
    """Load state-specific or regional Indian CACP economics YAML file.

    When a state file is available, loads verified local A2+FL costs and MSPs with
    economics_basis="local_verified". When unverified, falls back to punjab.yaml
    explicitly tagged with economics_basis="punjab_proxy" (Rule 8, WS-D).
    """
    key = (region_or_state or "punjab").lower().replace(" ", "_").strip()

    # Aliases
    aliases = {
        "punjab_central": "punjab",
        "punjab_southwest": "punjab",
        "vidarbha": "maharashtra",
        "cauvery": "tamil_nadu",
        "bundelkhand": "uttar_pradesh",
    }
    key = aliases.get(key, key)

    path = _DEFAULT_ECONOMICS_DIR / f"{key}.yaml"
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if "economics_basis" not in data:
                data["economics_basis"] = "local_verified"
            return data

    # Transparent proxy fallback
    proxy_path = _DEFAULT_ECONOMICS_DIR / "punjab.yaml"
    if proxy_path.exists():
        data = yaml.safe_load(proxy_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["economics_basis"] = "punjab_proxy"
            data["proxy_for"] = region_or_state
            return data

    return {"crops": {}, "currency": "INR", "economics_basis": "punjab_proxy"}


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
        region: Economic table identifier or state (e.g. 'punjab', 'maharashtra', 'tamil_nadu').
        currency: 'INR' (default) or 'USD'.
        price_multiplier: Realized market price factor (1.0 = median MSP/mandi price).
        preceded_by_legume: True if preceding season fixed biological nitrogen (saves ~1.4 bags Urea/ha).
        irrigation: Irrigation regime ('full', 'limited', or 'none'). Rainfed dryland regimes
            incur lower irrigation pumping and input costs per CACP dryland state budgets.

    Returns:
        dict with revenue_per_ha, cost_per_ha, labor_cost_per_ha, profit_per_ha,
        market_risk, procurement_type, currency, economics_basis.
    """
    econ = load_economics(region)
    crop_data = econ.get("crops", {}).get(crop_id, {})
    usd_rate = float(econ.get("usd_exchange_rate", 83.5))
    economics_basis = econ.get("economics_basis", "local_verified")

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
        labor_inr *= 0.90

    # Practice adjustments
    if any(p in practices for p in ("happy_seeder", "zero_till")):
        # Saves 2-3 preparatory tractor tillage passes (~Rs 2,500/ha)
        cost_inr -= 2500.0
        labor_inr -= 800.0
    elif "direct_seeded" in practices:
        # Saves land soaking rauni puddling, laser leveling & nursery manual transplanting (~Rs 6,000/ha)
        cost_inr -= 6000.0
        labor_inr -= 4500.0

    # Biological Nitrogen credit: succeeding cereal saves 25 kg N/ha (~Rs 650/ha fertilizer cost)
    if preceded_by_legume and crop_id in ("wheat", "rice_puddled", "rice_short", "rice_dsr", "maize", "barley"):
        cost_inr = max(5000.0, cost_inr - 650.0)

    cost_inr = max(5000.0, cost_inr)
    labor_inr = max(1500.0, labor_inr)
    revenue_inr = float(yield_t_ha) * price_inr
    profit_inr = revenue_inr - cost_inr

    if currency == "USD":
        return {
            "revenue_per_ha": round(revenue_inr / usd_rate, 1),
            "cost_per_ha": round(cost_inr / usd_rate, 1),
            "labor_cost_per_ha": round(labor_inr / usd_rate, 1),
            "profit_per_ha": round(profit_inr / usd_rate, 1),
            "market_risk": market_risk,
            "procurement_type": procurement_type,
            "currency": "USD",
            "economics_basis": economics_basis,
        }

    return {
        "revenue_per_ha": round(revenue_inr, 0),
        "cost_per_ha": round(cost_inr, 0),
        "labor_cost_per_ha": round(labor_inr, 0),
        "profit_per_ha": round(profit_inr, 0),
        "market_risk": market_risk,
        "procurement_type": procurement_type,
        "currency": "INR",
        "economics_basis": economics_basis,
    }


def cvar(profits: Sequence[float], alpha: float = 0.10) -> float:
    """Compute empirical Conditional Value at Risk (expected shortfall in worst alpha tail)."""
    arr = np.asarray(profits, dtype=float)
    if len(arr) == 0:
        return 0.0
    q_val = float(np.percentile(arr, alpha * 100.0))
    tail = arr[arr <= q_val]
    return float(round(float(np.mean(tail)) if len(tail) > 0 else q_val, 1))


def cvar_bootstrap_ci(
    profits: Sequence[float],
    alpha: float = 0.10,
    n_boot: int = 200,
    block_len: int = 3,
    seed: int = 42,
) -> tuple[float, float]:
    """Compute moving-block bootstrap 5th and 95th percentile confidence interval of CVaR_alpha (Issue 14 / WS-I5).

    Args:
        profits: Sequence of multi-member annual profit outcomes.
        alpha: Downside tail quantile fraction (default 0.10 for CVaR_10).
        n_boot: Number of bootstrap iterations (default 200).
        block_len: Moving block length in years to preserve serial autocorrelation.
        seed: Deterministic random seed for reproducibility.

    Returns:
        (cvar_ci_low, cvar_ci_high) as 5th and 95th percentile bounds.
    """
    arr = np.asarray(profits, dtype=float)
    n = len(arr)
    if n == 0:
        return 0.0, 0.0
    if n <= 3:
        p_alpha = float(np.percentile(arr, alpha * 100.0))
        worst = arr[arr <= p_alpha]
        val = float(np.mean(worst)) if len(worst) > 0 else p_alpha
        return round(val, 1), round(val, 1)

    rng = np.random.default_rng(seed)
    block_len = max(1, min(block_len, n))
    n_blocks = int(np.ceil(n / block_len))

    # All possible contiguous overlapping blocks of length block_len
    max_start = n - block_len + 1
    blocks = [arr[i : i + block_len] for i in range(max_start)]

    boot_cvars: list[float] = []
    for _ in range(n_boot):
        chosen_indices = rng.integers(0, len(blocks), size=n_blocks)
        sample = np.concatenate([blocks[i] for i in chosen_indices])[:n]
        q_val = float(np.percentile(sample, alpha * 100.0))
        tail = sample[sample <= q_val]
        cvar_b = float(np.mean(tail)) if len(tail) > 0 else q_val
        boot_cvars.append(cvar_b)

    ci_low = float(round(float(np.percentile(boot_cvars, 5.0)), 1))
    ci_high = float(round(float(np.percentile(boot_cvars, 95.0)), 1))

    if ci_low > ci_high:
        ci_low, ci_high = ci_high, ci_low

    return ci_low, ci_high
