"""Ground loop (L1): refine the current architecture, keep-if-better else revert.

This is the inner Karpathy-style loop. Given the current ``solution.py`` and the
history of what's been tried this cycle, it asks the proposer for a tuned version,
evaluates it in an isolated subprocess, and greedily keeps it only if it strictly
beats the best score seen so far in this cycle.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from engine.llm import extract_code

REPO = Path(__file__).resolve().parent.parent
SOLUTION = REPO / "task" / "solution.py"
TEMPLATE = REPO / "task" / "templates" / "solution_baseline.py"
EPS = 1e-9


def reset_solution_to_baseline() -> None:
    SOLUTION.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")


def hypothesis_of(code: str) -> str:
    first = code.strip().splitlines()[0] if code.strip() else ""
    return first.replace("# HYPOTHESIS:", "").strip() if "HYPOTHESIS" in first else "(no hypothesis)"


def evaluate(timeout: int = 60):
    """Run task/solution.py in a throwaway subprocess. Returns (fitness, detail, log)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "engine.eval_runner", tmp.name],
            cwd=str(REPO), capture_output=True, text=True, timeout=timeout,
        )
        fitness = float("inf")
        for line in proc.stdout.splitlines():
            if line.startswith("FITNESS="):
                try:
                    fitness = float(line.split("=", 1)[1])
                except ValueError:
                    pass
        detail = {}
        if os.path.getsize(tmp.name) > 0:
            detail = json.loads(Path(tmp.name).read_text(encoding="utf-8"))
        return fitness, detail, (proc.stdout + proc.stderr)
    except subprocess.TimeoutExpired:
        return float("inf"), {}, "TIMEOUT"
    finally:
        os.unlink(tmp.name)


def _build_user(recorder, cycle: int, current_code: str) -> str:
    return (
        f"Current architecture history (this cycle):\n{recorder.l1_history_text(cycle)}\n\n"
        f"Current solution.py:\n```python\n{current_code}\n```\n\n"
        "Propose a refined solution.py that lowers the fitness (shorter tours)."
    )


def run_ground_loop(client, l1_system, iters, recorder, cycle, start_fitness, start_detail, verbose=True):
    """Tune the architecture currently on disk for ``iters`` iterations.
    Returns (best_fitness, best_code, best_detail)."""
    best_fitness = start_fitness
    best_code = SOLUTION.read_text(encoding="utf-8")
    best_detail = start_detail
    recorder.add_experiment(cycle, 0, start_fitness, "installed", hypothesis_of(best_code), start_detail)

    for it in range(1, iters + 1):
        current_code = SOLUTION.read_text(encoding="utf-8")
        user = _build_user(recorder, cycle, current_code)
        new_code = extract_code(client.complete(l1_system, user, kind="l1"))
        SOLUTION.write_text(new_code, encoding="utf-8")
        fitness, detail, _ = evaluate()

        if fitness < best_fitness - EPS:
            best_fitness, best_code, best_detail = fitness, new_code, detail
            status = "kept"
        else:
            SOLUTION.write_text(best_code, encoding="utf-8")  # revert
            status = "failed" if fitness == float("inf") else "reverted"
        recorder.add_experiment(cycle, it, fitness, status, hypothesis_of(new_code), detail)
        if verbose:
            shown = "  fail" if fitness == float("inf") else f"{(1 - fitness) * 100:+6.2f}%"
            print(f"    [L1 {it}/{iters}] {shown}  {status:<8}  {hypothesis_of(new_code)}")

    SOLUTION.write_text(best_code, encoding="utf-8")  # leave the best on disk
    return best_fitness, best_code, best_detail
