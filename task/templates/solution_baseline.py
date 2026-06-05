# HYPOTHESIS: baseline nearest-neighbour construction
"""Gold-master baseline solution (FROZEN).

This file is the starting point for every run. The engine copies it into
``task/solution.py`` at launch; the loops then evolve ``solution.py``. This
template is never edited and also serves as the *reference* solver the harness
scores every candidate against.

Contract: expose ``solve(cities) -> list[int]`` returning a permutation of the
city indices (a tour). That's the entire interface the harness depends on.
"""
import math


def solve(cities):
    """Nearest-neighbour tour: start at city 0, always hop to the closest
    unvisited city. Simple, fast, and clearly improvable — which is the point."""
    n = len(cities)
    unvisited = set(range(1, n))
    order = [0]
    current = 0
    while unvisited:
        nxt = min(unvisited, key=lambda j: math.dist(cities[current], cities[j]))
        order.append(nxt)
        unvisited.discard(nxt)
        current = nxt
    return order
