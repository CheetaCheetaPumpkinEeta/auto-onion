"""auto-onion entry point.

Runs the two-loop self-improving code search over the TSP substrate.

    python run.py --mock            # offline, deterministic, no API key (recommended first run)
    python run.py                   # live Claude (needs: pip install anthropic + ANTHROPIC_API_KEY)
    python run.py --cycles 4 --l1-iters 5

Watch it live in the viewer:  python viewer/server.py  ->  http://localhost:5005
"""
from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from engine.logging_utils import Recorder
from engine.prompts import L1_SYSTEM, L2_SYSTEM
from engine.second_loop import run_second_loop

REPO = Path(__file__).resolve().parent
TASK_LABEL = "Travelling Salesman - mean tour length vs nearest-neighbour baseline (lower is better)"


def main() -> None:
    ap = argparse.ArgumentParser(description="Two-loop self-improving code search (auto-onion).")
    ap.add_argument("--mock", action="store_true",
                    help="run offline with scripted edits (no API key, fully reproducible)")
    ap.add_argument("--cycles", type=int, default=3, help="number of L2 architecture cycles")
    ap.add_argument("--l1-iters", type=int, default=4, help="L1 refinement iterations per architecture")
    ap.add_argument("--l2-model", default="claude-opus-4-8", help="model for the architecture proposer")
    ap.add_argument("--l1-model", default="claude-sonnet-4-6", help="model for the refinement proposer")
    ap.add_argument("--backend", choices=["auto", "api", "cli"], default="auto",
                    help="live LLM backend: 'api' (anthropic SDK + ANTHROPIC_API_KEY), "
                         "'cli' (local claude CLI / Claude Code login), or 'auto' (api if a key is set, else cli)")
    ap.add_argument("--run-dir", default=None, help="output directory (default: runs/<timestamp>)")
    args = ap.parse_args()

    if args.mock:
        from engine.llm import MockClient
        shared = MockClient()  # one instance: it tracks how far up the ladder L2 has climbed
        l2_client = l1_client = shared
        mode = "MOCK (offline, scripted edits)"
    else:
        backend = args.backend
        if backend == "auto":
            backend = "api" if os.environ.get("ANTHROPIC_API_KEY") else "cli"
        if backend == "api":
            from engine.llm import AnthropicClient
            l2_client = AnthropicClient(args.l2_model)
            l1_client = AnthropicClient(args.l1_model)
        else:
            from engine.llm import ClaudeCLIClient
            l2_client = ClaudeCLIClient(args.l2_model)
            l1_client = ClaudeCLIClient(args.l1_model)
        mode = f"LIVE/{backend} (L2={args.l2_model}, L1={args.l1_model})"

    run_dir = Path(args.run_dir) if args.run_dir else REPO / "runs" / time.strftime("%Y%m%d-%H%M%S")
    recorder = Recorder(run_dir, TASK_LABEL)

    print("=" * 72)
    print(f"auto-onion  |  mode: {mode}")
    print(f"task: {TASK_LABEL}")
    print(f"budget: {args.cycles} architecture cycles x {args.l1_iters} refinement iters")
    print(f"run dir: {run_dir}")
    print("=" * 72 + "\n")

    best_fit, best_code, best_name = run_second_loop(
        l2_client, l1_client, L2_SYSTEM, L1_SYSTEM, args.cycles, args.l1_iters, recorder
    )

    print("=" * 72)
    print(f"DONE.  best improvement over baseline: {(1 - best_fit) * 100:+.2f}%")
    print(f"winning architecture: {best_name}")
    print(f"results: {run_dir / 'results.tsv'}")
    print(f"view it: python viewer/server.py  ->  http://localhost:5005")
    print("=" * 72)


if __name__ == "__main__":
    main()
