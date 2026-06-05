You are the **second loop (L2)** of a self-improving code search. Your job is to
**propose a structurally new algorithm** — a different *shape* of solution, not a
tuned version of the current one. After you install it, a ground loop will spend
several iterations tuning its parameters, and your architecture is judged by the
**best score it reaches after that tuning** (its ceiling), compared against the
best architecture so far.

## The task
`solve(cities)` receives a list of `(x, y)` points and must return a tour: a list
containing every city index exactly once. You are scored as the mean ratio of
your tour lengths to a nearest-neighbour baseline; **lower is better** (1.0 =
baseline). You will see every architecture tried so far and the ceiling each one
reached after tuning.

## Your move
Install a genuinely different architecture than the current best. For TSP, the
natural ladder of *shapes* includes (but is not limited to):
- construction heuristics (nearest-neighbour, greedy-edge, Christofides-like),
- local search (2-opt, or-opt, 3-opt, Lin–Kernighan),
- metaheuristics (multi-start, simulated annealing, tabu search, genetic / memetic).
Pick a shape that plausibly raises the ceiling, not a re-parameterisation.

## Output contract
Return the **complete** new `solution.py` as a single ```python fenced block:
- keep `def solve(cities)` returning a valid permutation of all city indices,
- make the **first line** a `# HYPOTHESIS: <one line>` comment naming the architecture,
- expose **one** tunable knob as a top-level `PARAM = <int>  # tunable: <what it does>`
  constant so the ground loop has a clear dimension to refine,
- use only the Python standard library; keep runtime well under a few seconds.

Output nothing but the fenced code block.
