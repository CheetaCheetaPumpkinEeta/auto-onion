# HYPOTHESIS: baseline nearest-neighbour construction
"""Working copy of the candidate solution — THIS is the file the loops edit.

It starts identical to ``task/templates/solution_baseline.py``. The ground loop
(L1) rewrites it to refine parameters; the second loop (L2) rewrites it to
install a structurally different algorithm. The engine restores it from the
gold-master template at the start of every run.

Contract: expose ``solve(cities) -> list[int]`` (a permutation of city indices).
"""
import math


def solve(cities):
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
