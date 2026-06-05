"""Subprocess entry point that evaluates the current ``task/solution.py``.

The loops never import the (LLM-edited) solution into their own process — a bad
edit could hang or crash. Instead each evaluation runs *here*, in a throwaway
subprocess with a timeout, and communicates back through stdout + a JSON file.

The candidate is loaded by exec'ing its source (``harness.load_solve``), not by
``import``, so Python's bytecode cache can't serve a stale solution between rapid
edits — see the note in ``harness.load_solve``.

Usage:  python -m engine.eval_runner <out_json_path>
Prints: FITNESS=<float>   and writes the full result dict to <out_json_path>.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from engine import harness

SOLUTION = Path(__file__).resolve().parent.parent / "task" / "solution.py"


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else None
    solve = harness.load_solve(SOLUTION)  # exec from source — no import cache, no stale .pyc

    fitness, per_instance, showcase = harness.score_solution(solve)
    print(f"FITNESS={fitness}")
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"fitness": fitness, "per_instance": per_instance, "showcase": showcase}, f)


if __name__ == "__main__":
    main()
