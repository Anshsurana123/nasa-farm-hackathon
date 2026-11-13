"""Multi-objective NSGA-II sorting and priority-based selection from evaluated candidates. (TASK-O03, TASK-O04)

Each candidate carries objective values (all oriented so HIGHER IS BETTER):
    profit        : median net profit (₹/ha/yr)
    water_savings : negative annual irrigation demand (-irrigation_mm, scaled by GRACE groundwater urgency)
    soil_health   : USDA-NRCS composite soil health score (0–100 pts)
    low_risk      : CVaR-10 downside profit in severe drought years (₹/ha/yr)
    low_labour    : negative annual hired/imputed labour cost (-labor_cost_inr_per_ha in ₹/ha, where less negative = lower labour requirement)
    food_security : food and nutrition security index (0–1 scale)
Selection: normalise each objective to [0,1] across candidates, weighted sum with the
farmer's Priorities, then keep the top-k that are also mutually different
(diversity filter so the 3 cards are not near-duplicates).
"""

from __future__ import annotations

from collections.abc import Sequence

from terraloop_schemas import Priorities

OBJECTIVES = ("profit", "water_savings", "soil_health", "low_risk", "low_labour", "food_security")

# Minimum physical spread thresholds to prevent numerical noise from dominating min-max scaling
# when candidate metrics are closely clustered across an objective.
MIN_SPREADS: dict[str, float] = {
    "profit": 5000.0,         # ₹5,000 / ha
    "water_savings": 25.0,    # 25 mm irrigation
    "soil_health": 5.0,       # 5.0 points on 0-100 index
    "low_risk": 5000.0,       # ₹5,000 / ha CVaR
    "low_labour": 2000.0,     # ₹2,000 / ha labour cost
    "food_security": 0.10,    # 0.10 on 0-1 nutrition index
}


def pareto_front(
    candidates: list[dict[str, float]],
    keys: Sequence[str] | None = None,
) -> list[int]:
    """Indices of non-dominated candidates (higher is better on every active key)."""
    if not candidates:
        return []
    eval_keys = list(keys) if keys is not None else [k for k in OBJECTIVES if all(k in c for c in candidates)]
    if not eval_keys:
        return list(range(len(candidates)))
    front = []
    for i, a in enumerate(candidates):
        dominated = any(
            all(b[k] >= a[k] for k in eval_keys) and any(b[k] > a[k] for k in eval_keys)
            for j, b in enumerate(candidates)
            if j != i
        )
        if not dominated:
            front.append(i)
    return front


def weighted_scores(candidates: list[dict[str, float]], priorities: Priorities) -> list[float]:
    if not candidates:
        return []
    weights = priorities.model_dump()
    keys = [k for k in OBJECTIVES if weights.get(k, 0) > 0 and all(k in c for c in candidates)]
    total_w = sum(weights[k] for k in keys) or 1.0
    scores = [0.0] * len(candidates)
    for k in keys:
        vals = [c[k] for c in candidates]
        lo, hi = min(vals), max(vals)
        min_sp = MIN_SPREADS.get(k, 1.0)
        span = max(hi - lo, min_sp)
        for i, v in enumerate(vals):
            scores[i] += (weights[k] / total_w) * (v - lo) / span
    return scores


def _extract_primary_pair(label: str) -> tuple[str, str]:
    """Extract the primary (Kharif, Rabi) crop pair from a rotation label for structural diversity filtering."""
    sep = "→" if "→" in label else ">"
    parts = [p.strip().lower() for p in label.split(sep) if p.strip()]
    if len(parts) >= 2:
        return (parts[0], parts[1])
    if len(parts) == 1:
        return (parts[0], "")
    return (label.lower(), "")


def select_top(
    candidates: list[dict[str, float]],
    labels: list[str],
    priorities: Priorities,
    k: int = 3,
    crop_pairs: Sequence[tuple[str, ...]] | None = None,
) -> list[int]:
    """Return indices of the top-k Pareto-optimal, structurally distinct candidates.

    Two passes:
      1. Enforce distinct (Kharif, Rabi) primary crop pairs AND distinct Kharif crop families/archetypes
         so the Top 3 recommendations offer genuinely different farm strategies.
      2. If fewer than k candidates satisfy strict pair diversity, relax to distinct labels.
    """
    if not candidates:
        return []
    weights = priorities.model_dump()
    active_keys = [k for k in OBJECTIVES if weights.get(k, 0.0) > 0 and all(k in c for c in candidates)]
    if not active_keys:
        active_keys = [k for k in OBJECTIVES if all(k in c for c in candidates)]
    front = set(pareto_front(candidates, keys=active_keys))
    scores = weighted_scores(candidates, priorities)
    nsga2_pool = set(nsga2_select(candidates, k=min(len(candidates), max(k * 3, 6)), keys=active_keys))

    # Priority-driven viability filter:
    # Solvency requirement (P50 >= 0) is maintained, while relative floors on profit and soil health
    # scale strictly with the farmer's normalized priority weights, preventing water-saving or
    # climate-resilient rotations from being blocked when the farmer does not prioritize profit.
    total_w = sum(weights.get(obj, 0.0) for obj in OBJECTIVES) or 1.0
    norm_profit = weights.get("profit", 0.0) / total_w
    norm_soil = weights.get("soil_health", 0.0) / total_w

    if len(candidates) >= 10:
        profits = [c.get("profit", 0.0) for c in candidates]
        soils = [c.get("soil_health", 0.0) for c in candidates]
        max_profit = max(profits) if profits else 0.0
        med_soil = sorted(soils)[len(soils) // 2] if soils else 0.0
        has_positive_profit = max_profit > 0.0

        if norm_profit > 0.10 and has_positive_profit:
            p_floor = min(0.75, 0.35 + 0.40 * norm_profit) * max_profit
        elif has_positive_profit:
            p_floor = 0.0  # Basic solvency floor (no financial loss)
        else:
            p_floor = -float("inf")

        if norm_soil > 0.10:
            s_floor = med_soil * min(1.0, 0.50 + 0.50 * norm_soil)
        else:
            s_floor = 0.0

        viable = {
            i
            for i, c in enumerate(candidates)
            if c.get("profit", 0.0) >= p_floor and c.get("soil_health", 0.0) >= s_floor
        }
        if len(viable) < k:
            viable = {
                i
                for i, c in enumerate(candidates)
                if c.get("profit", 0.0) >= (0.0 if has_positive_profit else -float("inf"))
            }
        if len(viable) < k:
            viable = set(range(len(candidates)))
    else:
        viable = set(range(len(candidates)))

    order = sorted(
        range(len(candidates)),
        key=lambda i: (i in viable, i in front, round(scores[i], 6), i in nsga2_pool),
        reverse=True,
    )

    chosen: list[int] = []
    seen_pairs: set[tuple[str, ...]] = set()
    seen_kharif: list[str] = []

    def _get_pair(idx: int) -> tuple[str, ...]:
        if crop_pairs and idx < len(crop_pairs):
            return tuple(crop_pairs[idx])
        return _extract_primary_pair(labels[idx])

    max_score = max(scores) if scores else 1.0
    min_viable_score = max_score * 0.60

    # Pass 1: Require distinct Kharif crop AND distinct (Kharif, Rabi) pair among viable Pareto candidates
    # that remain competitive with farmer priority weights (score >= 0.60 * max_score)
    for i in order:
        if i not in viable or scores[i] < min_viable_score:
            continue
        pair = _get_pair(i)
        if pair not in seen_pairs and pair[0] not in seen_kharif:
            chosen.append(i)
            seen_pairs.add(pair)
            seen_kharif.append(pair[0])
        if len(chosen) == k:
            return chosen

    # Pass 2: Allow same Kharif if Rabi crop differs, still enforcing viable + 0.60 score competitiveness
    for i in order:
        if i in chosen or i not in viable or scores[i] < min_viable_score:
            continue
        pair = _get_pair(i)
        if pair not in seen_pairs and all(labels[i] != labels[j] for j in chosen):
            chosen.append(i)
            seen_pairs.add(pair)
        if len(chosen) == k:
            return chosen

    # Pass 3: Viable + 0.60 score competitive candidates with distinct full rotation labels
    for i in order:
        if i in chosen or i not in viable or scores[i] < min_viable_score:
            continue
        if all(labels[i] != labels[j] for j in chosen):
            chosen.append(i)
        if len(chosen) == k:
            return chosen

    # Pass 4: Fallback if fewer than k viable candidates satisfied 0.60 floor (order preserves viable & score priority)
    for i in order:
        if i not in chosen and all(labels[i] != labels[j] for j in chosen):
            chosen.append(i)
        if len(chosen) == k:
            break
    return chosen


def fast_non_dominated_sort(
    candidates: list[dict[str, float]], keys: list[str] | None = None
) -> list[list[int]]:
    """Deb et al. (2002) Fast Non-Dominated Sorting Algorithm (TASK-O03).

    Partitions candidate indices into non-dominated Pareto fronts: [F_1, F_2, ...].
    Higher objective value is better for all keys.
    """
    if not candidates:
        return []
    if keys is None:
        keys = [k for k in OBJECTIVES if all(k in c for c in candidates)]

    n = len(candidates)
    domination_count = [0] * n  # number of candidates that dominate candidate i
    dominated_solutions = [[] for _ in range(n)]  # solutions dominated by candidate i
    fronts: list[list[int]] = [[]]

    for p in range(n):
        for q in range(n):
            if p == q:
                continue
            # Check if p dominates q
            p_dominates_q = all(candidates[p][k] >= candidates[q][k] for k in keys) and any(
                candidates[p][k] > candidates[q][k] for k in keys
            )
            # Check if q dominates p
            q_dominates_p = all(candidates[q][k] >= candidates[p][k] for k in keys) and any(
                candidates[q][k] > candidates[p][k] for k in keys
            )
            if p_dominates_q:
                dominated_solutions[p].append(q)
            elif q_dominates_p:
                domination_count[p] += 1

        if domination_count[p] == 0:
            fronts[0].append(p)

    i = 0
    while len(fronts[i]) > 0:
        next_front = []
        for p in fronts[i]:
            for q in dominated_solutions[p]:
                domination_count[q] -= 1
                if domination_count[q] == 0:
                    next_front.append(q)
        i += 1
        fronts.append(next_front)

    return [f for f in fronts if f]


def crowding_distance(
    candidates: list[dict[str, float]], front: list[int], keys: list[str] | None = None
) -> dict[int, float]:
    """Deb et al. (2002) Crowding Distance Assignment (TASK-O03)."""
    if not front:
        return {}
    if keys is None:
        keys = [k for k in OBJECTIVES if all(k in c for c in candidates)]

    distances = {idx: 0.0 for idx in front}
    front_len = len(front)
    if front_len <= 2:
        return {idx: float("inf") for idx in front}

    for k in keys:
        sorted_front = sorted(front, key=lambda idx: candidates[idx][k])
        distances[sorted_front[0]] = float("inf")
        distances[sorted_front[-1]] = float("inf")
        k_min = candidates[sorted_front[0]][k]
        k_max = candidates[sorted_front[-1]][k]
        span = k_max - k_min
        if span > 0:
            for i in range(1, front_len - 1):
                prev_val = candidates[sorted_front[i - 1]][k]
                next_val = candidates[sorted_front[i + 1]][k]
                distances[sorted_front[i]] += (next_val - prev_val) / span

    return distances


def nsga2_select(
    candidates: list[dict[str, float]],
    k: int = 3,
    keys: list[str] | None = None,
) -> list[int]:
    """NSGA-II multi-objective selection operator (TASK-O03).

    Sorts candidates across Pareto fronts and breaks ties using crowding distance.
    Returns indices of the top-k individuals.
    """
    if len(candidates) <= k:
        return list(range(len(candidates)))

    fronts = fast_non_dominated_sort(candidates, keys=keys)
    selected: list[int] = []

    for front in fronts:
        if len(selected) + len(front) <= k:
            selected.extend(front)
        else:
            remaining = k - len(selected)
            cd = crowding_distance(candidates, front, keys=keys)
            sorted_by_cd = sorted(front, key=lambda idx: cd[idx], reverse=True)
            selected.extend(sorted_by_cd[:remaining])
            break

    return selected


def annotate_pareto_metrics(candidates: list[dict[str, float]]) -> list[dict[str, float]]:
    """Compute NSGA-II non-dominated front rank (1 = Pareto front) and crowding distance per candidate."""
    if not candidates:
        return []
    fronts = fast_non_dominated_sort(candidates)
    out = [dict(c) for c in candidates]
    for rank_idx, front in enumerate(fronts, start=1):
        cd_map = crowding_distance(candidates, front)
        for c_idx in front:
            out[c_idx]["pareto_front"] = float(rank_idx)
            raw_cd = cd_map.get(c_idx, 0.0)
            out[c_idx]["crowding_distance"] = 99.0 if raw_cd == float("inf") else round(float(raw_cd), 3)
    return out
