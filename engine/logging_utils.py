"""Run recorder.

Owns the on-disk state for a run:
* ``state.json`` — the live snapshot the viewer polls. Besides the flat
  architecture/experiment records it carries a ``tree``: the same hierarchical
  shape the parent project (omnididdy) feeds its dashboard —
  ``origin → benchmark → second_loop → run → ground_container → ground_experiment`` —
  so the viewer can render an identical d3 lineage graph. Every node carries the
  full code block that produced it.
* ``results.tsv`` — a flat, Karpathy-style log: one row per experiment, ever.

It also renders the small history tables fed back into the proposer prompts —
the only "memory" this trimmed-down system has is this flat log.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

METRIC_NAME = "tour ratio"      # mean tour length / nearest-neighbour baseline
METRIC_FORMAT = ".4f"
METRIC_DIRECTION = "minimize"   # lower fitness is better
BASELINE_LOSS = 1.0             # the nearest-neighbour baseline scores exactly 1.0


def _improvement_pct(fitness: float):
    if fitness == float("inf"):
        return None
    return round((1.0 - fitness) * 100.0, 2)


def _safe(fitness: float):
    """JSON can't hold inf; represent a failed eval as the string 'inf'."""
    return "inf" if fitness == float("inf") else round(fitness, 4)


def _num(v):
    """Stored fitness -> JSON number or None (val_loss the viewer can format)."""
    if v is None or v == "inf" or v == float("inf"):
        return None
    return v


class Recorder:
    def __init__(self, run_dir: Path, task_label: str):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.run_dir / "state.json"
        self.tsv_path = self.run_dir / "results.tsv"
        self.state = {
            "task": task_label,
            "status": "running",
            "metric_name": METRIC_NAME,
            "metric_format": METRIC_FORMAT,
            "metric_direction": METRIC_DIRECTION,
            "best_fitness": float("inf"),
            "best_improvement_pct": 0.0,
            "architectures": [],
        }
        self.tsv_path.write_text("level\tcycle\titer\tfitness\timprovement_pct\tstatus\thypothesis\n", encoding="utf-8")
        self._flush()

    # ---- mutation -------------------------------------------------------
    def start_architecture(self, cycle: int, name: str, code: str, l1_budget: int | None = None) -> None:
        self.state["architectures"].append(
            {
                "cycle": cycle,
                "name": name,
                "status": "running",
                "best_fitness": float("inf"),
                "improvement_pct": None,
                "l1_budget": l1_budget,   # planned refinement iters (install excluded)
                "code": code,
                "experiments": [],
            }
        )
        self._flush()

    def add_experiment(self, cycle: int, iteration: int, fitness: float, status: str,
                       hypothesis: str, detail: dict | None = None, code: str = "") -> None:
        arch = self._arch(cycle)
        imp = _improvement_pct(fitness)
        arch["experiments"].append(
            {"iter": iteration, "fitness": _safe(fitness), "improvement_pct": imp,
             "status": status, "hypothesis": hypothesis, "code": code}
        )
        if fitness < self.state["best_fitness"]:
            self.state["best_fitness"] = fitness
            self.state["best_improvement_pct"] = imp
        self._append_tsv("L1" if cycle or iteration else "L0", cycle, iteration, fitness, status, hypothesis)
        self._flush()

    def finish_architecture(self, cycle: int, status: str, best_fitness: float) -> None:
        arch = self._arch(cycle)
        arch["status"] = status
        arch["best_fitness"] = _safe(best_fitness)
        arch["improvement_pct"] = _improvement_pct(best_fitness)
        self._append_tsv("L2", cycle, "", best_fitness, status, arch["name"])
        self._flush()

    def done(self) -> None:
        self.state["status"] = "done"
        self._flush()

    # ---- prompt history -------------------------------------------------
    def l1_history_text(self, cycle: int) -> str:
        arch = self._arch(cycle)
        rows = ["iter  fitness   improvement  status     hypothesis"]
        for e in arch["experiments"]:
            imp = "  fail " if e["improvement_pct"] is None else f"{e['improvement_pct']:+6.2f}%"
            rows.append(f"{e['iter']:>4}  {e['fitness']:>7}  {imp:>11}  {e['status']:<9}  {e['hypothesis']}")
        return "\n".join(rows)

    def l2_history_text(self) -> str:
        rows = ["cycle  ceiling(improvement)  status     architecture"]
        for a in self.state["architectures"]:
            imp = "  fail " if a["improvement_pct"] is None else f"{a['improvement_pct']:+6.2f}%"
            rows.append(f"{a['cycle']:>5}  {imp:>19}  {a['status']:<9}  {a['name']}")
        return "\n".join(rows)

    # ---- lineage tree (omnididdy-shaped) --------------------------------
    def _experiment_nodes(self, arch: dict) -> list[dict]:
        """Build the ground_experiment lineage for one architecture: the install
        node (iter 0) is the root; each refinement parents to the best node so
        far (the spine), so kept attempts extend the trunk and reverted ones
        hang off as dead-end leaves."""
        cycle = arch["cycle"]
        roots: list[dict] = []
        spine: dict | None = None
        for e in arch["experiments"]:
            it = e["iter"]
            if it == 0:  # the install — colour it by the architecture's fate
                if arch["status"] == "running":
                    status, improved = "running", False
                else:
                    kept = arch["status"] == "kept" or cycle == 0
                    status, improved = ("kept" if kept else "reverted"), kept
            else:        # a refinement attempt
                improved = e["status"] == "kept"
                status = e["status"] if e["status"] in ("kept", "reverted", "running") else "reverted"
            node = {
                "name": f"exp-{cycle:02d}.{it}",
                "type": "ground_experiment",
                "id": f"{cycle}.{it}",
                "val_loss": _num(e["fitness"]),
                "improved": improved,
                "status": status,
                "hypothesis": e["hypothesis"],
                "code": e.get("code", ""),
                "metric_format": METRIC_FORMAT,
                "metric_direction": METRIC_DIRECTION,
                "baseline_loss": BASELINE_LOSS,
                "children": [],
            }
            if it == 0:
                roots.append(node)
                spine = node
            else:
                (spine or node)["children"].append(node)
                if improved:
                    spine = node
        return roots

    def _build_tree(self) -> dict:
        runs_children: list[dict] = []
        trunk = runs_children
        for arch in self.state["architectures"]:
            cycle = arch["cycle"]
            best = _num(arch.get("best_fitness"))
            # refinement experiments completed = total minus the iter-0 install
            refines_done = max(0, len(arch["experiments"]) - 1)
            l1_budget = arch.get("l1_budget")
            ground = {
                "name": "ground", "type": "ground_container",
                "id": f"ground-{cycle:04d}",
                "total_experiments": len(arch["experiments"]),
                "l1_budget": l1_budget,
                "refines_done": refines_done,
                "best_loss": best,
                "children": self._experiment_nodes(arch),
            }
            if cycle == 0:
                run_rank = "baseline"
            elif arch["status"] == "running":
                run_rank = "running"
            elif arch["status"] == "kept":
                run_rank = "green"
            else:
                run_rank = "red"
            run = {
                "name": ("baseline" if cycle == 0 else arch["name"]),
                "type": "run",
                "id": f"run-{cycle:04d}",
                "run_rank": run_rank,
                "active": arch["status"] == "running",
                "best_loss": best,
                "baseline_loss": BASELINE_LOSS,
                "total_experiments": len(arch["experiments"]),
                "l1_budget": l1_budget,
                "refines_done": refines_done,
                "improvement_pct": arch.get("improvement_pct"),
                "hypothesis": arch["name"],
                "code": arch.get("code", ""),
                "metric_name": METRIC_NAME,
                "metric_format": METRIC_FORMAT,
                "metric_direction": METRIC_DIRECTION,
                "children": [ground],
            }
            trunk.append(run)
            if cycle == 0 or arch["status"] == "kept":  # kept architecture advances the trunk
                trunk = run["children"]

        second_loop = {
            "name": "second loop proposer", "type": "second_loop",
            "total_runs": len(self.state["architectures"]),
            "best_loss": _num(self.state["best_fitness"]),
            "children": runs_children,
        }
        benchmark = {
            "name": "tsp", "type": "benchmark",
            "metric_name": METRIC_NAME, "metric_format": METRIC_FORMAT,
            "metric_direction": METRIC_DIRECTION,
            "best_loss": _num(self.state["best_fitness"]), "baseline_loss": BASELINE_LOSS,
            "children": [second_loop],
        }
        return {"name": "origin", "type": "origin", "children": [benchmark]}

    # ---- internals ------------------------------------------------------
    def _arch(self, cycle: int) -> dict:
        for a in reversed(self.state["architectures"]):
            if a["cycle"] == cycle:
                return a
        raise KeyError(f"no architecture for cycle {cycle}")

    def _append_tsv(self, level, cycle, iteration, fitness, status, hypothesis) -> None:
        imp = "" if _improvement_pct(fitness) is None else f"{_improvement_pct(fitness)}"
        with self.tsv_path.open("a", encoding="utf-8") as f:
            f.write(f"{level}\t{cycle}\t{iteration}\t{_safe(fitness)}\t{imp}\t{status}\t{hypothesis}\n")

    def _flush(self) -> None:
        self.state["tree"] = self._build_tree()
        tmp = self.state_path.with_name(self.state_path.name + ".tmp")
        tmp.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        os.replace(tmp, self.state_path)  # atomic rename — readers never see a partial file
