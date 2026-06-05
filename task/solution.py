# HYPOTHESIS: tuned PARAM to 3
PARAM = 3  # tunable: number of restarts from different start cities

import math


def _length(cities, order):
    n = len(order)
    return sum(math.dist(cities[order[i]], cities[order[(i + 1) % n]]) for i in range(n))


def _nearest_neighbour(cities, start=0):
    n = len(cities)
    unvisited = set(range(n))
    unvisited.discard(start)
    order = [start]
    current = start
    while unvisited:
        nxt = min(unvisited, key=lambda j: math.dist(cities[current], cities[j]))
        order.append(nxt)
        unvisited.discard(nxt)
        current = nxt
    return order


def _two_opt(cities, order, sweeps):
    order = order[:]
    n = len(order)
    for _ in range(sweeps):
        improved = False
        for i in range(n - 1):
            a, b = order[i], order[i + 1]
            for k in range(i + 2, n):
                c, d = order[k], order[(k + 1) % n]
                if d == a:
                    continue
                before = math.dist(cities[a], cities[b]) + math.dist(cities[c], cities[d])
                after = math.dist(cities[a], cities[c]) + math.dist(cities[b], cities[d])
                if after < before - 1e-10:
                    order[i + 1:k + 1] = order[i + 1:k + 1][::-1]
                    b = order[i + 1]
                    improved = True
        if not improved:
            break
    return order


def _or_opt(cities, order, max_seg):
    order = order[:]
    best = _length(cities, order)
    improving = True
    while improving:
        improving = False
        n = len(order)
        for seg in range(1, max_seg + 1):
            for i in range(n - seg + 1):
                segment = order[i:i + seg]
                rest = order[:i] + order[i + seg:]
                for j in range(len(rest) + 1):
                    candidate = rest[:j] + segment + rest[j:]
                    cand_len = _length(cities, candidate)
                    if cand_len < best - 1e-10:
                        order, best, improving = candidate, cand_len, True
                        break
                if improving:
                    break
            if improving:
                break
    return order


def solve(cities):
    n = len(cities)
    best_order, best_len = None, float("inf")
    for start in range(min(PARAM, n)):
        order = _nearest_neighbour(cities, start=start)
        order = _two_opt(cities, order, 8)
        order = _or_opt(cities, order, 2)
        order = _two_opt(cities, order, 8)
        length = _length(cities, order)
        if length < best_len:
            best_order, best_len = order, length
    return best_order