"""Frozen scoring harness.

The harness is the *trusted* half of the system — the loops never edit it. It
loads the TSP instances, runs a candidate ``solve`` function, checks the tour is
valid, and scores it.

Fitness = mean over instances of (candidate tour length / baseline tour length).
The baseline is the gold-master nearest-neighbour solver, so:

    fitness 1.000  ->  exactly as good as the baseline  (0% improvement)
    fitness 0.880  ->  12% shorter tours than the baseline

Lower is better. Reporting a *ratio* keeps instances of different sizes
comparable and makes "improvement %" = (1 - fitness) * 100 self-contained.
"""
from __future__ import annotations

import math
from pathlib import Path

from task.instances import make_instances

REPO = Path(__file__).resolve().parent.parent
_TEMPLATE = REPO / "task" / "templates" / "solution_baseline.py"


def tour_length(cities, order) -> float:
    n = len(order)
    return sum(math.dist(cities[order[i]], cities[order[(i + 1) % n]]) for i in range(n))


def is_valid_tour(order, n) -> bool:
    return len(order) == n and sorted(order) == list(range(n))


def _baseline_solve():
    """Load the gold-master solver from the template file (single source of truth
    for the reference, so it can never drift from the file the run starts from)."""
    ns: dict = {}
    exec(compile(_TEMPLATE.read_text(), str(_TEMPLATE), "exec"), ns)
    return ns["solve"]


# Reference baseline lengths, computed once per process.
_REFS: dict[str, float] | None = None


def baseline_lengths() -> dict[str, float]:
    global _REFS
    if _REFS is None:
        base = _baseline_solve()
        _REFS = {name: tour_length(cities, base(list(cities))) for name, cities in make_instances().items()}
    return _REFS


def score_solution(solve_fn):
    """Score a candidate ``solve`` function.

    Returns (fitness, per_instance, best_tour) where ``best_tour`` is the tour
    for the largest instance (used by the viewer to draw a picture). On an
    invalid tour, fitness is +inf so the loop reverts it.
    """
    instances = make_instances()
    refs = baseline_lengths()
    ratios: list[float] = []
    per: dict[str, dict] = {}
    showcase = None
    for name, cities in instances.items():
        order = solve_fn(list(cities))
        if not is_valid_tour(order, len(cities)):
            return float("inf"), {}, None
        length = tour_length(cities, order)
        ratio = length / refs[name]
        ratios.append(ratio)
        per[name] = {"length": round(length, 3), "ref": round(refs[name], 3), "ratio": round(ratio, 4)}
        # Showcase the biggest instance (last spec) — it's the most interesting to look at.
        showcase = {"name": name, "cities": cities, "order": order, "length": round(length, 3)}
    fitness = sum(ratios) / len(ratios)
    return fitness, per, showcase
