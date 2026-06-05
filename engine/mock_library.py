"""Scripted edits for offline (``--mock``) mode.

This is what makes the project reproducible without an API key: instead of
calling a real model, ``MockClient`` pulls *real, runnable* code from here.

* ``architecture(i)``  — the i-th rung of a structurally-improving ladder the
                         second loop (L2) climbs:
                             0:  NN + 2-opt
                             1:  NN + 2-opt + or-opt
                             2:  multi-start NN + 2-opt + or-opt
* ``refine(code)``     — what the ground loop (L1) gets: the same file with its
                         single tunable ``PARAM`` bumped by one. More sweeps /
                         segments / restarts => better, until it converges (and
                         the keep-or-revert gate then reverts the no-op tweak).

Every string below is a complete ``solution.py``. They share the same helper
functions so each reads like an incremental edit of the last — which is exactly
what a real model would produce.
"""
from __future__ import annotations

import re

_HELPERS = '''
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
'''.strip("\n")


_ARCH_TWO_OPT = f'''# HYPOTHESIS: nearest-neighbour construction refined by 2-opt local search
PARAM = 1  # tunable: number of 2-opt sweeps

{_HELPERS}


def solve(cities):
    order = _nearest_neighbour(cities, start=0)
    order = _two_opt(cities, order, PARAM)
    return order
'''


_ARCH_OR_OPT = f'''# HYPOTHESIS: NN + 2-opt, then or-opt segment moves to escape 2-opt local minima
PARAM = 1  # tunable: maximum or-opt segment length

{_HELPERS}


def solve(cities):
    order = _nearest_neighbour(cities, start=0)
    order = _two_opt(cities, order, 8)
    order = _or_opt(cities, order, PARAM)
    order = _two_opt(cities, order, 8)
    return order
'''


_ARCH_MULTISTART = f'''# HYPOTHESIS: multi-start NN + 2-opt + or-opt, keep the best tour over restarts
PARAM = 1  # tunable: number of restarts from different start cities

{_HELPERS}


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
'''


_LADDER = [_ARCH_TWO_OPT, _ARCH_OR_OPT, _ARCH_MULTISTART]

# How far the ground loop is allowed to push each PARAM before it stops helping.
_PARAM_CAP = 12

_PARAM_RE = re.compile(r"(?m)^PARAM = (\d+)(.*)$")
_HYPO_RE = re.compile(r"(?m)^# HYPOTHESIS:.*$")
_CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)


def architecture(i: int) -> str:
    """Return the i-th architecture (clamped to the last rung if we run past it)."""
    return _LADDER[min(i, len(_LADDER) - 1)]


def current_code_from_prompt(prompt: str) -> str:
    """Recover the current solution code that the L1 loop embedded in its prompt."""
    m = _CODE_BLOCK_RE.search(prompt)
    return (m.group(1).strip() if m else "")


def refine(code: str) -> str:
    """Bump the single tunable PARAM by one (the ground loop's only move). If it's
    already at the cap or there's no PARAM, return the code unchanged — which the
    keep-or-revert gate will then revert, ending refinement of this architecture."""
    m = _PARAM_RE.search(code)
    if not m:
        return code
    value = int(m.group(1))
    if value >= _PARAM_CAP:
        return code
    new_value = value + 1
    code = _PARAM_RE.sub(f"PARAM = {new_value}{m.group(2)}", code, count=1)
    code = _HYPO_RE.sub(f"# HYPOTHESIS: tuned PARAM to {new_value}", code, count=1)
    return code
