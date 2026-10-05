"""Priority-based selection from evaluated candidates. (TASK-O04 implemented, O03 pending)

Each candidate carries objective values (all oriented so HIGHER IS BETTER):
    profit        : median profit per ha
    water_savings : negative irrigation mm (or -groundwater draw)
    soil_health   : soil health score 0-100
    low_risk      : CVaR-10 profit (worst 10% mean)
    low_labour    : negative labour days
    food_security : staple calories
Selection: normalise each objective to [0,1] across candidates, weighted sum with the
farmer's Priorities, then keep the top-k that are also mutually different
(diversity filter so the 3 cards are not near-duplicates).
"""

from __future__ import annotations

from terraloop_schemas import Priorities

OBJECTIVES = ("profit", "water_savings", "soil_health", "low_risk", "low_labour", "food_security")


def pareto_front(candidates: list[dict[str, float]]) -> list[int]:
    """Indices of non-dominated candidates (higher is better on every key present)."""
    keys = [k for k in OBJECTIVES if all(k in c for c in candidates)]
    front = []
    for i, a in enumerate(candidates):
        dominated = any(
            all(b[k] >= a[k] for k in keys) and any(b[k] > a[k] for k in keys)
            for j, b in enumerate(candidates)
            if j != i
        )
        if not dominated:
            front.append(i)
    return front


def weighted_scores(candidates: list[dict[str, float]], priorities: Priorities) -> list[float]:
    weights = priorities.model_dump()
    keys = [k for k in OBJECTIVES if weights.get(k, 0) > 0 and all(k in c for c in candidates)]
    total_w = sum(weights[k] for k in keys) or 1.0
    scores = [0.0] * len(candidates)
    for k in keys:
        vals = [c[k] for c in candidates]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        for i, v in enumerate(vals):
            scores[i] += (weights[k] / total_w) * (v - lo) / span
    return scores


def select_top(
    candidates: list[dict[str, float]],
    labels: list[str],
    priorities: Priorities,
    k: int = 3,
) -> list[int]:
    """Return indices of the top-k Pareto-optimal, mutually distinct candidates."""
    front = set(pareto_front(candidates))
    scores = weighted_scores(candidates, priorities)
    order = sorted(range(len(candidates)), key=lambda i: (i in front, scores[i]), reverse=True)
    chosen: list[int] = []
    for i in order:
        if all(labels[i] != labels[j] for j in chosen):
            chosen.append(i)
        if len(chosen) == k:
            break
    return chosen
