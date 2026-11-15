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
from pydantic import BaseModel, ConfigDict, Field


class EconomicsCropConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    price_per_tonne: float = Field(..., ge=0.0)
    price_usd_per_tonne: float | None = Field(None, ge=0.0)
    cost_per_ha: float = Field(..., ge=0.0)
    labor_cost_per_ha: float = Field(0.0, ge=0.0)
    cost_usd_per_ha: float | None = Field(None, ge=0.0)
    market_risk: float = Field(0.10, ge=0.0, le=1.0)
    procurement_type: str = "mandi"
    sources: list[str] = Field(default_factory=list)


class EconomicsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    currency: str = "INR"
    currency_symbol: str | None = None
    usd_exchange_rate: float = Field(83.5, gt=0.0)
    ppp_spread_factor: float = Field(1.0, gt=0.0)
    cost_floor: float = Field(5000.0, ge=0.0)
    labor_floor: float = Field(1500.0, ge=0.0)
    state: str | None = None
    economics_basis: str = "local_verified"
    practice_adjustments: dict[str, dict[str, float]] = Field(default_factory=dict)
    crops: dict[str, EconomicsCropConfig] = Field(default_factory=dict)


_CURRENCY_SYMBOLS: dict[str, str] = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "BRL": "R$",
    "KES": "KSh",
    "AUD": "A$",
}

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
    """Return currency code and symbol based on region or validated global economics table."""
    if region in ("unvalidated_global", "biophysical_global"):
        return {"code": "USD", "symbol": "$"}
    econ = load_economics(region)
    code = str(econ.get("currency", "INR"))
    sym = str(econ.get("currency_symbol") or _CURRENCY_SYMBOLS.get(code, "₹"))
    return {"code": code, "symbol": sym}


@functools.lru_cache(maxsize=24)
def load_economics(region_or_state: str | None = "punjab") -> dict:
    """Load state-specific Indian or global regional enterprise budget YAML file.

    When a verified regional/state file is available, loads local costs and crop prices with
    economics_basis="local_verified" (India) or "regional_verified" (global hubs). When unverified,
    falls back to punjab.yaml explicitly tagged with economics_basis="punjab_proxy" (Rule 8, WS-D).
    """
    raw = (region_or_state or "").strip()
    key = raw.lower().replace(" ", "_")

    if not key or key in ("unvalidated_global", "biophysical_global"):
        proxy_path = _DEFAULT_ECONOMICS_DIR / "punjab.yaml"
        if proxy_path.exists():
            data = yaml.safe_load(proxy_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = EconomicsConfig.model_validate(data).model_dump()
                data["economics_basis"] = "punjab_proxy"
                data["proxy_for"] = raw or key or "unvalidated_global"
                if key in ("unvalidated_global", "biophysical_global"):
                    data["currency"] = "USD"
                    data["currency_symbol"] = "$"
                return data
        return {
            "crops": {},
            "currency": "USD" if key in ("unvalidated_global", "biophysical_global") else "INR",
            "currency_symbol": "$" if key in ("unvalidated_global", "biophysical_global") else "₹",
            "economics_basis": "punjab_proxy",
        }

    # Aliases mapping verified zones/cities/districts to state/hub economics tables
    aliases = {
        "punjab_central": "punjab",
        "punjab_southwest": "punjab",
        "sangrur": "punjab",
        "ludhiana": "punjab",
        "bathinda": "punjab",
        "chandigarh": "punjab",
        "delhi": "haryana",
        "vidarbha": "maharashtra",
        "western_maharashtra": "maharashtra",
        "cauvery": "tamil_nadu",
        "thanjavur": "tamil_nadu",
        "puducherry": "tamil_nadu",
        "bundelkhand": "uttar_pradesh",
        "western_up": "uttar_pradesh",
        "us_corn_belt": "usa_iowa",
        "iowa": "usa_iowa",
        "usa": "usa_iowa",
        "united_states": "usa_iowa",
        "eu_maritime_west": "france",
        "beauce": "france",
        "brazil_cerrado": "brazil_mt",
        "mato_grosso": "brazil_mt",
        "east_africa_highlands": "kenya",
        "nakuru": "kenya",
        "australia_wheat_belt": "australia_nsw",
        "new_south_wales": "australia_nsw",
        "victoria": "australia_nsw",
        "south_australia": "australia_nsw",
        "western_australia": "australia_nsw",
    }
    key = aliases.get(key, key)

    path = _DEFAULT_ECONOMICS_DIR / f"{key}.yaml"
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = EconomicsConfig.model_validate(data).model_dump()
            if "economics_basis" not in data:
                data["economics_basis"] = "local_verified"
            return data

    # Transparent proxy fallback
    proxy_path = _DEFAULT_ECONOMICS_DIR / "punjab.yaml"
    if proxy_path.exists():
        data = yaml.safe_load(proxy_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = EconomicsConfig.model_validate(data).model_dump()
            data["economics_basis"] = "punjab_proxy"
            data["proxy_for"] = region_or_state
            return data

    return {"crops": {}, "currency": "INR", "currency_symbol": "₹", "economics_basis": "punjab_proxy"}


_GLOBAL_FAOSTAT_PROXY_USD: dict[str, dict[str, float | str]] = {
    "wheat_winter": {"price_usd_per_tonne": 225.0, "cost_usd_per_ha": 620.0, "labor_usd_per_ha": 110.0, "market_risk": 0.14},
    "wheat_spring": {"price_usd_per_tonne": 235.0, "cost_usd_per_ha": 580.0, "labor_usd_per_ha": 100.0, "market_risk": 0.14},
    "rapeseed_canola": {"price_usd_per_tonne": 490.0, "cost_usd_per_ha": 640.0, "labor_usd_per_ha": 95.0, "market_risk": 0.16},
    "rye_winter": {"price_usd_per_tonne": 185.0, "cost_usd_per_ha": 430.0, "labor_usd_per_ha": 85.0, "market_risk": 0.13},
    "triticale": {"price_usd_per_tonne": 195.0, "cost_usd_per_ha": 450.0, "labor_usd_per_ha": 90.0, "market_risk": 0.13},
    "oats": {"price_usd_per_tonne": 220.0, "cost_usd_per_ha": 440.0, "labor_usd_per_ha": 85.0, "market_risk": 0.14},
    "faba_bean": {"price_usd_per_tonne": 320.0, "cost_usd_per_ha": 480.0, "labor_usd_per_ha": 115.0, "market_risk": 0.15},
    "field_pea": {"price_usd_per_tonne": 295.0, "cost_usd_per_ha": 420.0, "labor_usd_per_ha": 95.0, "market_risk": 0.14},
    "lupin": {"price_usd_per_tonne": 310.0, "cost_usd_per_ha": 360.0, "labor_usd_per_ha": 80.0, "market_risk": 0.15},
    "alfalfa": {"price_usd_per_tonne": 165.0, "cost_usd_per_ha": 520.0, "labor_usd_per_ha": 140.0, "market_risk": 0.11},
    "crimson_clover_vetch": {"price_usd_per_tonne": 65.0, "cost_usd_per_ha": 190.0, "labor_usd_per_ha": 55.0, "market_risk": 0.10},
    "brachiaria_cover": {"price_usd_per_tonne": 45.0, "cost_usd_per_ha": 160.0, "labor_usd_per_ha": 45.0, "market_risk": 0.08},
    "sugar_beet": {"price_usd_per_tonne": 48.0, "cost_usd_per_ha": 1950.0, "labor_usd_per_ha": 340.0, "market_risk": 0.11},
    "cassava": {"price_usd_per_tonne": 85.0, "cost_usd_per_ha": 640.0, "labor_usd_per_ha": 250.0, "market_risk": 0.13},
    "sweet_potato": {"price_usd_per_tonne": 175.0, "cost_usd_per_ha": 980.0, "labor_usd_per_ha": 320.0, "market_risk": 0.15},
    "rice_upland": {"price_usd_per_tonne": 320.0, "cost_usd_per_ha": 480.0, "labor_usd_per_ha": 160.0, "market_risk": 0.14},
    "rice_japonica_temperate": {"price_usd_per_tonne": 410.0, "cost_usd_per_ha": 920.0, "labor_usd_per_ha": 220.0, "market_risk": 0.12},
}


def profit_per_ha(
    crop_id: str,
    yield_t_ha: float,
    practices: Sequence[str] = (),
    region: str = "punjab",
    currency: str | None = None,
    price_multiplier: float = 1.0,
    preceded_by_legume: bool = False,
    irrigation: str = "full",
) -> dict[str, float | str]:
    """Calculate gross revenue, cost of cultivation, labour cost, and net profit per hectare."""
    econ = load_economics(region)
    native_currency = str(econ.get("currency", "INR"))
    target_currency = currency or native_currency
    if region in ("unvalidated_global", "biophysical_global") and currency is None:
        target_currency = "USD"
    crops_map = econ.get("crops", {})
    crop_data = crops_map.get(crop_id)
    usd_rate = float(econ.get("usd_exchange_rate", 83.5))
    economics_basis = str(econ.get("economics_basis", "local_verified"))
    used_punjab_proxy = False
    used_faostat_usd_proxy = False

    if not crop_data:
        ref_econ = load_economics("punjab")
        ref_crops = ref_econ.get("crops", {})
        crop_data = ref_crops.get(crop_id)
        if crop_data:
            economics_basis = "punjab_proxy"
            used_punjab_proxy = True
        elif crop_id in _GLOBAL_FAOSTAT_PROXY_USD:
            crop_data = _GLOBAL_FAOSTAT_PROXY_USD[crop_id]
            economics_basis = "faostat_proxy"
            used_faostat_usd_proxy = True
        else:
            economics_basis = "punjab_proxy"
            used_punjab_proxy = True
    crop_data = crop_data or {}

    if used_faostat_usd_proxy:
        price_local = float(crop_data.get("price_usd_per_tonne", 250.0)) * usd_rate * float(price_multiplier)
        cost_local = float(crop_data.get("cost_usd_per_ha", 480.0)) * usd_rate
        labor_local = float(crop_data.get("labor_usd_per_ha", 120.0)) * usd_rate
    else:
        price_local = float(crop_data.get("price_per_tonne", 24000.0)) * float(price_multiplier)
        cost_local = float(crop_data.get("cost_per_ha", 28000.0))
        labor_local = float(crop_data.get("labor_cost_per_ha", round(cost_local * 0.30)))
        if used_punjab_proxy and native_currency != "INR":
            scale = usd_rate / 83.5
            price_local *= scale
            cost_local *= scale
            labor_local *= scale

    market_risk = float(crop_data.get("market_risk", 0.12))
    procurement_type = str(crop_data.get("procurement_type", "commodity_spot" if native_currency != "INR" else "nafed_pss"))

    if irrigation == "none":
        cost_local *= 0.62
        labor_local *= 0.72
    elif irrigation == "limited":
        cost_local *= 0.88
        labor_local *= 0.90

    padj = econ.get("practice_adjustments") or {}
    hz = padj.get("happy_seeder_zero_till", {})
    ds = padj.get("direct_seeded", {})
    bb = padj.get("broad_bed_furrow", {})
    lc = padj.get("legume_credit", {})
    inr_scale = (usd_rate / 83.5) if native_currency != "INR" else 1.0

    # Practice adjustments (YAML native currency when configured, else scaled Indian INR defaults)
    if any(p in practices for p in ("happy_seeder", "zero_till")):
        cost_local += float(hz.get("cost_delta", -2500.0 * inr_scale))
        labor_local += float(hz.get("labor_delta", -800.0 * inr_scale))
    elif "direct_seeded" in practices:
        cost_local += float(ds.get("cost_delta", -6000.0 * inr_scale))
        labor_local += float(ds.get("labor_delta", -4500.0 * inr_scale))
    if "broad_bed_furrow" in practices:
        labor_local += float(bb.get("labor_delta", -1000.0 * inr_scale))

    cost_floor = float(econ.get("cost_floor", 5000.0 * inr_scale))
    labor_floor = float(econ.get("labor_floor", 1500.0 * inr_scale))
    legume_cereal_set = (
        "wheat",
        "wheat_winter",
        "wheat_spring",
        "rice_puddled",
        "rice_short",
        "rice_dsr",
        "rice_japonica_temperate",
        "rice_upland",
        "maize",
        "barley",
        "oats",
        "triticale",
        "rapeseed_canola",
    )
    if preceded_by_legume and (crop_id in legume_cereal_set or (economics_basis == "regional_verified" and crop_id == "sorghum")):
        cost_local = max(cost_floor, cost_local + float(lc.get("cost_delta", -650.0 * inr_scale)))

    cost_local = max(cost_floor, cost_local)
    labor_local = max(labor_floor, labor_local)
    revenue_local = float(yield_t_ha) * price_local
    profit_local = revenue_local - cost_local

    if target_currency == "USD" and native_currency != "USD":
        return {
            "revenue_per_ha": round(revenue_local / usd_rate, 1),
            "cost_per_ha": round(cost_local / usd_rate, 1),
            "labor_cost_per_ha": round(labor_local / usd_rate, 1),
            "profit_per_ha": round(profit_local / usd_rate, 1),
            "market_risk": market_risk,
            "procurement_type": procurement_type,
            "currency": "USD",
            "economics_basis": economics_basis,
        }

    ndigits = 1 if native_currency != "INR" else 0
    return {
        "revenue_per_ha": round(revenue_local, ndigits),
        "cost_per_ha": round(cost_local, ndigits),
        "labor_cost_per_ha": round(labor_local, ndigits),
        "profit_per_ha": round(profit_local, ndigits),
        "market_risk": market_risk,
        "procurement_type": procurement_type,
        "currency": native_currency,
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

    # Vectorized moving-block bootstrap preserving the exact RNG draw stream
    max_start = n - block_len + 1
    blocks_arr = np.lib.stride_tricks.sliding_window_view(arr, block_len)
    all_chosen = rng.integers(0, max_start, size=(n_boot, n_blocks))
    samples = blocks_arr[all_chosen].reshape(n_boot, -1)[:, :n]
    q_vals = np.percentile(samples, alpha * 100.0, axis=1)
    tail_mask = samples <= q_vals[:, None]
    tail_counts = tail_mask.sum(axis=1)
    tail_sums = np.where(tail_mask, samples, 0.0).sum(axis=1)
    boot_cvars = np.where(tail_counts > 0, tail_sums / np.maximum(tail_counts, 1), q_vals)

    ci_low = float(round(float(np.percentile(boot_cvars, 5.0)), 1))
    ci_high = float(round(float(np.percentile(boot_cvars, 95.0)), 1))

    if ci_low > ci_high:
        ci_low, ci_high = ci_high, ci_low

    return ci_low, ci_high
