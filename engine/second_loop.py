"""Second loop (L2): architecture search by post-tuning ceiling.

The outer loop. Each cycle it asks the (stronger) proposer for a *structurally
new* solver, installs it, then hands it to the ground loop for a full tuning
pass. The architecture is judged by the **best fitness it reaches after tuning**
and greedily kept only if that ceiling beats the incumbent's. This is the whole
idea in one line: *the second layer compares optimized versions.*

No memory beyond the flat history table: reverted architectures are dropped, not
archived. (The parent project, omnididdy, keeps a diversity-preserving archive;
this trimmed version deliberately does not — see the README.)
"""
from __future__ import annotations

from engine.ground_loop import (
    EPS,
    SOLUTION,
    evaluate,
    hypothesis_of,
    reset_solution_to_baseline,
    run_ground_loop,
)
from engine.llm import extract_code


def _build_user(recorder, incumbent_code: str) -> str:
    return (
        f"Architectures tried so far (best score reached after tuning):\n"
        f"{recorder.l2_history_text()}\n\n"
        f"Current best architecture (the one to beat):\n```python\n{incumbent_code}\n```\n\n"
        "Propose a structurally different solution.py that can reach a lower ceiling."
    )


def run_second_loop(l2_client, l1_client, l2_system, l1_system, cycles, l1_iters, recorder, verbose=True):
    # ---- cycle 0: the baseline, tuned, as the starting incumbent ----
    reset_solution_to_baseline()
    base_fit, base_detail, _ = evaluate()
    recorder.start_architecture(0, "baseline (nearest-neighbour)", code=SOLUTION.read_text(encoding="utf-8"), l1_budget=l1_iters)
    if verbose:
        print(f"[L2 cycle 0] baseline installed  ->  {(1 - base_fit) * 100:+.2f}%   (tuning...)")
    incumbent_fit, incumbent_code, _ = run_ground_loop(
        l1_client, l1_system, l1_iters, recorder, 0, base_fit, base_detail, verbose
    )
    incumbent_name = "baseline (nearest-neighbour)"
    recorder.finish_architecture(0, "kept", incumbent_fit)
    if verbose:
        print(f"[L2 cycle 0] baseline ceiling  ->  {(1 - incumbent_fit) * 100:+.2f}%\n")

    # ---- cycles 1..N: propose a new architecture, tune it, compare ceilings ----
    for c in range(1, cycles + 1):
        user = _build_user(recorder, incumbent_code)
        arch_code = extract_code(l2_client.complete(l2_system, user, kind="l2"))
        SOLUTION.write_text(arch_code, encoding="utf-8")
        install_fit, install_detail, _ = evaluate()
        name = hypothesis_of(arch_code)
        recorder.start_architecture(c, name, code=arch_code, l1_budget=l1_iters)
        if verbose:
            shown = "fail" if install_fit == float("inf") else f"{(1 - install_fit) * 100:+.2f}%"
            print(f"[L2 cycle {c}] proposed: {name}\n             install -> {shown}   (tuning...)")

        if install_fit == float("inf"):  # broken architecture — don't waste a tuning pass
            recorder.add_experiment(c, 0, install_fit, "failed", name, {}, code=arch_code)
            recorder.finish_architecture(c, "reverted", install_fit)
            SOLUTION.write_text(incumbent_code, encoding="utf-8")
            if verbose:
                print(f"[L2 cycle {c}] reverted (invalid solution)\n")
            continue

        tuned_fit, tuned_code, _ = run_ground_loop(
            l1_client, l1_system, l1_iters, recorder, c, install_fit, install_detail, verbose
        )
        if tuned_fit < incumbent_fit - EPS:
            incumbent_fit, incumbent_code, incumbent_name = tuned_fit, tuned_code, name
            recorder.finish_architecture(c, "kept", tuned_fit)
            verdict = "KEPT (new best)"
        else:
            SOLUTION.write_text(incumbent_code, encoding="utf-8")
            recorder.finish_architecture(c, "reverted", tuned_fit)
            verdict = "reverted (ceiling didn't beat incumbent)"
        if verbose:
            print(f"[L2 cycle {c}] ceiling {(1 - tuned_fit) * 100:+.2f}%  ->  {verdict}\n")

    recorder.done()
    return incumbent_fit, incumbent_code, incumbent_name
