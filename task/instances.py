"""Deterministic TSP problem instances.

Self-contained and fully reproducible: the city coordinates are generated
from fixed random seeds, so every run on every machine sees the exact same
problems. No external data files, no licensing concerns.

A TSP instance is just a list of (x, y) points. A *solution* is a tour: a
permutation of the city indices visiting each city exactly once.
"""
from __future__ import annotations

import random

# (name, number of cities, RNG seed)
INSTANCE_SPECS = [
    ("inst_a", 15, 1),
    ("inst_b", 25, 2),
    ("inst_c", 40, 3),
]


def make_instances() -> dict[str, list[tuple[float, float]]]:
    """Return {name: [(x, y), ...]} for every instance, deterministically."""
    instances: dict[str, list[tuple[float, float]]] = {}
    for name, n, seed in INSTANCE_SPECS:
        rng = random.Random(seed)
        instances[name] = [(rng.uniform(0.0, 100.0), rng.uniform(0.0, 100.0)) for _ in range(n)]
    return instances
