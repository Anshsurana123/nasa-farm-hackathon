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
    if not candidates:
        return []
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
    if not candidates:
        return []
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
) -> list[int]:
    """Return indices of the top-k Pareto-optimal, structurally distinct candidates.

    Two passes:
      1. Enforce distinct (Kharif, Rabi) primary crop pairs AND distinct Kharif crop families/archetypes
         so the Top 3 recommendations offer genuinely different farm strategies.
      2. If fewer than k candidates satisfy strict pair diversity, relax to distinct labels.
    """
    if not candidates:
        return []
    front = set(pareto_front(candidates))
    scores = weighted_scores(candidates, priorities)

    # Identify candidates that maintain economically viable farm income (>= 65% of max candidate profit)
    # and respectable soil health (>= median soil health) when selecting from a full catalog (>=10 candidates)
    if len(candidates) >= 10:
        profits = [c.get("profit", 0.0) for c in candidates]
        soils = [c.get("soil_health", 0.0) for c in candidates]
        max_profit = max(profits) if profits else 0.0
        med_soil = sorted(soils)[len(soils) // 2] if soils else 0.0
        viable = {
            i
            for i, c in enumerate(candidates)
            if c.get("profit", 0.0) >= 0.65 * max_profit and c.get("soil_health", 0.0) >= med_soil
        }
        if len(viable) < k:
            viable = set(range(len(candidates)))
    else:
        viable = set(range(len(candidates)))

    order = sorted(
        range(len(candidates)),
        key=lambda i: (i in viable, i in front, scores[i]),
        reverse=True,
    )

    chosen: list[int] = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_kharif: list[str] = []

    # Pass 1: Require distinct Kharif crop AND distinct (Kharif, Rabi) pair among viable Pareto candidates
    for i in order:
        if i not in viable:
            continue
        pair = _extract_primary_pair(labels[i])
        if pair not in seen_pairs and pair[0] not in seen_kharif:
            chosen.append(i)
            seen_pairs.add(pair)
            seen_kharif.append(pair[0])
        if len(chosen) == k:
            return chosen

    # Pass 2: Allow same Kharif if Rabi crop differs (distinct (Kharif, Rabi) pair)
    for i in order:
        if i in chosen:
            continue
        pair = _extract_primary_pair(labels[i])
        if pair not in seen_pairs and all(labels[i] != labels[j] for j in chosen):
            chosen.append(i)
            seen_pairs.add(pair)
        if len(chosen) == k:
            return chosen

    # Pass 3: Fallback to distinct full labels
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
