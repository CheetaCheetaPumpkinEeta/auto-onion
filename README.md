# frontier-loop

**A self-improving code search: two nested loops where an LLM rewrites its own
solver, keeps what works, and climbs a benchmark — no human in the loop.**

*CS 153 — The One-Person Frontier Lab.* `frontier-loop` is a minimal, from-scratch
distillation of the two-tier optimization engine from my larger research project,
[omnididdy](#acknowledgements--citations). It strips that system down to its
essential mechanism so the idea is legible in ~600 lines of pure-Python you can
read in one sitting and run with zero API keys.

https://github.com/USER/frontier-loop  ·  demo video: *(link)*

---

## 1. The problem & the insight

Improving a solution to a hard problem — a solver, a model, a heuristic — is
usually a slow human loop: *think of an idea → implement it → measure it → keep or
throw it away → repeat.* The bottleneck is **the human in that loop.** Frontier
labs scale it with armies of researchers. A single person can't.

**The insight:** that loop is mechanical enough to hand to an LLM. But a *single*
loop of "ask the model to improve the code" plateaus fast — it tinkers with
parameters and never tries a genuinely different idea. The fix is **two loops**:

> An inner loop **tunes** the current approach to its ceiling. An outer loop
> proposes a **structurally new** approach and judges it *by the ceiling it
> reaches after tuning* — comparing optimized versions, not first drafts.

That is the whole product. It's the same shape used by recent LLM-driven program
search systems (FunSearch, AlphaEvolve), reduced to its smallest honest form.

---

## 2. How it works

The system improves a single editable file, `task/solution.py`, against a **frozen,
trusted harness** it is never allowed to touch. The substrate here is the
**Travelling Salesman Problem** (chosen because it's pure-Python, deterministic,
and *visual* — you can watch the tour straighten out).

```
                          ┌──────────────────────────────────────────────┐
   SECOND LOOP (L2)       │  propose a STRUCTURALLY NEW solution.py       │
   architecture search    │  (NN → 2-opt → or-opt → multi-start → …)      │
   "compare optimized     └───────────────────┬──────────────────────────┘
    versions"                                  │ install
                                               ▼
                          ┌──────────────────────────────────────────────┐
   GROUND LOOP (L1)       │  for a few iterations:                        │
   parameter refinement   │    ask for a tuned solution.py                │
   (Karpathy-style)       │    run harness in a sandboxed subprocess      │
                          │    keep if strictly better, else REVERT       │
                          └───────────────────┬──────────────────────────┘
                                              │ returns the architecture's
                                              ▼ CEILING (best score after tuning)
                          ┌──────────────────────────────────────────────┐
                          │  L2 keeps the new architecture only if its    │
                          │  ceiling beats the incumbent's. Greedy.       │
                          └──────────────────────────────────────────────┘
```

**Ground loop (L1) — `engine/ground_loop.py`.** The inner, Karpathy-style loop.
It shows the proposer the current code plus a flat history of what's been tried,
gets a tuned `solution.py`, runs it through the harness **in a throwaway
subprocess** (so a buggy or infinite-looping edit can't take the system down), and
**keeps the edit only if it strictly lowers the score, otherwise reverts.**

**Second loop (L2) — `engine/second_loop.py`.** The outer loop. Each cycle it asks
a (stronger) proposer for a *structurally different* algorithm, installs it, and
hands it to the ground loop for a full tuning pass. The architecture is scored by
the **best fitness it reaches after tuning** — its ceiling — and is greedily kept
only if that beats the incumbent. *This is the line "the second layer compares
optimized versions."*

**Fitness — `engine/harness.py`.** For each TSP instance, tour length ÷ the
nearest-neighbour baseline's length, averaged across instances. `1.00` = baseline,
`0.85` = 15 % shorter. Lower is better; improvement % = `(1 − fitness) × 100`.
Reporting a ratio keeps differently-sized instances comparable and makes the
result self-contained (no external optimal-tour tables needed).

**The proposer — `engine/llm.py`.** One tiny provider-neutral interface,
`complete(system, user, kind)`, with two implementations:
- `AnthropicClient` — real Claude (Opus for L2 architecture, Sonnet for L1 tuning).
- `MockClient` — a **deterministic offline** stand-in that returns *real, runnable*
  code from a scripted ladder (`engine/mock_library.py`). It fakes the model's
  *creativity*, not the *mechanism* — the loops, gating, subprocess sandbox, and
  scoring are identical in both modes. This is what makes the project reproducible
  by anyone, instantly, with no API key and no cost.

---

## 3. Quickstart

```bash
# 1. Run the whole two-loop system offline (no API key, ~20s, fully deterministic):
python run.py --mock

# 2. Watch it live in the viewer (separate terminal):
pip install flask
python viewer/server.py        # -> http://localhost:5005

# 3. Run it for real with Claude:
pip install anthropic
export ANTHROPIC_API_KEY=sk-...        # PowerShell: $env:ANTHROPIC_API_KEY="sk-..."
python run.py                          # L2=Opus, L1=Sonnet by default

# Knobs:
python run.py --mock --cycles 4 --l1-iters 5
```

The **engine has no dependencies** — `python run.py --mock` runs on a bare Python
3.10+ install. `flask` is only for the viewer; `anthropic` only for live mode.

---

## 4. What it actually does (example run)

`python run.py --mock`, abridged:

```
[L2 cycle 0] baseline installed  ->  +0.00%   (tuning...)
    [L1 1/4]  +0.00%  reverted  baseline nearest-neighbour      <- gate correctly rejects a no-op
[L2 cycle 1] proposed: nearest-neighbour refined by 2-opt
    [L1 1/4] +14.45%  kept      tuned PARAM to 2                 <- L1 tunes the new architecture
    [L1 2/4] +14.45%  reverted  tuned PARAM to 3                 <- and stops when it plateaus
[L2 cycle 1] ceiling +14.45%  ->  KEPT (new best)
[L2 cycle 2] proposed: NN + 2-opt + or-opt
[L2 cycle 2] ceiling +15.19%  ->  KEPT (new best)
[L2 cycle 3] proposed: multi-start NN + 2-opt + or-opt
[L2 cycle 3] ceiling +16.61%  ->  KEPT (new best)

DONE.  best improvement over baseline: +16.61%
winning architecture: multi-start NN + 2-opt + or-opt, keep the best tour over restarts
```

The outer loop discovered a clear ladder of *shapes* — construction → local search
→ metaheuristic — each one tuned to its ceiling before being compared, ending
**16.6 % shorter** than the nearest-neighbour baseline. The viewer renders this as
a tree (green = kept, red = reverted) next to a live drawing of the best tour.

---

## 5. Repo layout

```
run.py                          entry point (--mock / live, --cycles, --l1-iters)
engine/
  second_loop.py                L2: architecture search by post-tuning ceiling
  ground_loop.py                L1: keep-or-revert refinement + subprocess sandbox
  harness.py                    FROZEN scorer (tour length vs baseline)
  eval_runner.py                runs a candidate in an isolated subprocess
  llm.py                        provider-neutral client: Anthropic + deterministic Mock
  mock_library.py               scripted, runnable TSP architectures for offline mode
  logging_utils.py              writes state.json (viewer) + results.tsv (flat log)
  prompts.py                    loads the system prompts
prompts/
  second_loop.md                L2 system prompt (also reads as method documentation)
  ground_loop.md                L1 system prompt
task/
  solution.py                   THE EDITABLE FILE — the loops rewrite this
  templates/solution_baseline.py gold-master baseline (frozen reference)
  instances.py                  deterministic, seeded TSP instances
viewer/
  server.py                     ~30-line Flask app: serves the page + /api/state
  index.html                    one self-contained page: tree + live tour canvas
runs/<timestamp>/               per-run state.json + results.tsv
```

---

## 6. Evaluation & evidence

- **It works end-to-end, reproducibly.** `python run.py --mock` is deterministic
  (seeded instances, scripted edits) and reaches **+16.61 %** every time on any
  machine — so the claim "the two loops find and keep real improvements" is
  verifiable in 20 seconds without an API key.
- **The gates are real, not cosmetic.** The trace shows the ground loop *reverting*
  edits that don't help (the baseline's no-op tweaks; a 2-opt sweep past
  convergence), and the second loop comparing **tuned ceilings**, not first drafts.
- **The harness is trustworthy by construction.** Candidates run in a sandboxed
  subprocess with a timeout; every tour is validated as a true permutation before
  scoring, so an invalid or hung solution scores `+inf` and is reverted rather than
  corrupting the result.
- **Live mode is a genuine test of generality.** Swapping `MockClient` for
  `AnthropicClient` changes *nothing* in the engine — same loops, same gates — so a
  successful live run is evidence the mechanism isn't tied to the scripted ladder.

**Safety note.** In **live** mode the system executes model-generated Python on
your machine (in a timed subprocess, but without filesystem/network sandboxing) —
that's intrinsic to "an LLM rewrites its own solver." Run it in a throwaway
environment if that matters to you. Offline `--mock` mode executes only the
scripted code in this repo.

**Honest limitations.** The search is *greedy* (no archive of rejected ideas, no
backtracking — see §7). The mock ladder is short by design, so offline mode
demonstrates the mechanism rather than open-ended discovery; real exploration
needs live mode. TSP is a friendly substrate (cheap, deterministic) — noisier or
slower objectives would need replay/variance handling that this trimmed version
omits.

---

## 7. What's deliberately left out (and where it lives)

This is a **trimmed** version. Its parent, omnididdy, adds the machinery this one
intentionally drops, most importantly **memory**: omnididdy keeps a
diversity-preserving *archive* of every architecture tried (kept **and** rejected),
samples the best + most-divergent "stepping stones" back into each prompt, scores
proposals for novelty, and manages all of it across a **branching tree** of edits.
`frontier-loop` keeps only a flat history and greedily follows a single trunk —
exactly "two layers of keep-or-revert search," no more. The clean separation here
(frozen harness vs editable solution, provider-neutral LLM interface) is the same
contract omnididdy uses, kept deliberately small.

---

## 8. AI usage disclosure

This project was built with heavy, disclosed use of AI coding tools. I (the author)
designed the system, chose the two-loop architecture and the TSP substrate, decided
the fitness/gating scheme, and directed and reviewed the implementation; **Claude
Code (Claude Opus 4.x)** wrote much of the code under that direction. The system
*also* uses Claude at **runtime** as the proposer in live mode (`--` without
`--mock`). The offline `--mock` mode contains no AI calls — it's scripted Python so
the project is reproducible without credentials. All design decisions, limitations,
and the choice of what to trim from the parent project are my own.

---

## 9. Acknowledgements & citations

- **omnididdy** — my larger research project, from which this distills the two-tier
  loop. `frontier-loop` is a clean, minimal **rewrite** (no code copied) focused on
  the core mechanism. The "frozen harness + editable solution" contract, the
  provider-neutral LLM boundary, and the L1/L2 split all originate there.
- **Karpathy-style autonomous research** — the inner keep-or-revert loop that reads
  a flat experiment log and decides what to try next is modelled on Andrej
  Karpathy's description of autonomous-research loops.
- **LLM-driven program search lineage** — the broader idea of an LLM proposing code
  edits scored by a fitness function, kept evolutionarily:
  - Romera-Paredes et al., *"Mathematical discoveries from program search with large
    language models" (FunSearch)*, Nature 2024.
  - Novikov et al. / DeepMind, *AlphaEvolve* (2025).
  - *ShinkaEvolve* — archive + novelty-driven evolutionary code search.
- **TSP heuristics** used in the architecture ladder are classical: nearest-neighbour
  construction, 2-opt (Croes, 1958), or-opt (Or, 1976), and multi-start.

## 10. License

MIT — see [LICENSE](LICENSE).
