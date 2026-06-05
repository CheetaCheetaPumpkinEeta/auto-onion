"""Run recorder.

Owns the on-disk state for a run:
* ``state.json`` — the live snapshot the viewer polls (architectures, experiments,
  best tour so far). Rewritten after every experiment so the viewer is always live.
* ``results.tsv`` — a flat, Karpathy-style log: one row per experiment, ever.

It also renders the small history tables that get fed back into the proposer
prompts — the only "memory" this trimmed-down system has is this flat log.
"""
from __future__ import annotations

import json
from pathlib import Path


def _improvement_pct(fitness: float):
    if fitness == float("inf"):
        return None
    return round((1.0 - fitness) * 100.0, 2)


class Recorder:
    def __init__(self, run_dir: Path, task_label: str):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.run_dir / "state.json"
        self.tsv_path = self.run_dir / "results.tsv"
        self.state = {
            "task": task_label,
            "status": "running",
            "best_fitness": float("inf"),
            "best_improvement_pct": 0.0,
            "best_tour": None,
            "architectures": [],
        }
        self.tsv_path.write_text("level\tcycle\titer\tfitness\timprovement_pct\tstatus\thypothesis\n", encoding="utf-8")
        self._flush()

    # ---- mutation -------------------------------------------------------
    def start_architecture(self, cycle: int, name: str, code: str) -> None:
        self.state["architectures"].append(
            {
                "cycle": cycle,
                "name": name,
                "status": "running",
                "best_fitness": float("inf"),
                "improvement_pct": None,
                "code": code,
                "experiments": [],
            }
        )
        self._flush()

    def add_experiment(self, cycle: int, iteration: int, fitness: float, status: str,
                       hypothesis: str, detail: dict | None = None) -> None:
        arch = self._arch(cycle)
        imp = _improvement_pct(fitness)
        arch["experiments"].append(
            {"iter": iteration, "fitness": _safe(fitness), "improvement_pct": imp,
             "status": status, "hypothesis": hypothesis}
        )
        # Track the global best tour for the viewer's picture.
        if fitness < self.state["best_fitness"]:
            self.state["best_fitness"] = fitness
            self.state["best_improvement_pct"] = imp
            showcase = (detail or {}).get("showcase")
            if showcase:
                self.state["best_tour"] = showcase
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

    # ---- lineage graph --------------------------------------------------
    def _build_nodes(self) -> list[dict]:
        """Derive the parent_id lineage graph the viewer draws.

        The graph is a tree: a *spine* of kept nodes (the trunk the search
        actually followed) with every reverted attempt hanging off it as a
        dead-end leaf. An architecture's install node (iter 0) parents to the
        incumbent's best node at the time it was proposed; each refinement
        parents to the best node so far within its cycle. This is the same
        parent_id lineage idea the full system (omnididdy) renders.
        """
        nodes: list[dict] = []
        trunk_tip = None          # id of the current incumbent's best node
        best_id, best_fit = None, float("inf")
        for arch in self.state["architectures"]:
            cycle = arch["cycle"]
            spine = None          # best node so far *within* this cycle
            cycle_best_id, cycle_best_fit = None, float("inf")
            for e in arch["experiments"]:
                it = e["iter"]
                nid = f"c{cycle}_i{it}"
                fit = e["fitness"]
                fitf = float("inf") if fit == "inf" else float(fit)
                if it == 0:       # the architecture's install IS the architecture node
                    kind = "baseline" if cycle == 0 else "arch"
                    parent = trunk_tip
                    status = arch["status"]          # green/red = kept/reverted at L2
                    label = arch["name"]
                    spine = nid
                else:             # an L1 refinement attempt
                    kind = "exp"
                    parent = spine
                    status = e["status"]
                    label = e["hypothesis"]
                    if e["status"] == "kept":
                        spine = nid
                nodes.append({"id": nid, "parent": parent, "kind": kind, "label": label,
                              "status": status, "improvement_pct": e["improvement_pct"],
                              "fitness": fit, "cycle": cycle, "iter": it})
                if fitf < cycle_best_fit:
                    cycle_best_fit, cycle_best_id = fitf, nid
                if fitf < best_fit:
                    best_fit, best_id = fitf, nid
            # a kept architecture (or the baseline) advances the trunk
            if (arch["status"] == "kept" or cycle == 0) and cycle_best_id is not None:
                trunk_tip = cycle_best_id
        for n in nodes:
            n["is_best"] = n["id"] == best_id
        return nodes

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
        self.state["nodes"] = self._build_nodes()
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")


def _safe(fitness: float):
    """JSON can't hold inf; represent a failed eval as the string 'inf'."""
    return "inf" if fitness == float("inf") else round(fitness, 4)
