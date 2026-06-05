"""Import a real two-loop run into an auto-onion viewer ``state.json``.

auto-onion's bundled runnable benchmark is TSP (``python run.py --mock``). The
*engine* — the two nested loops — is benchmark-agnostic, and it's a faithful,
trimmed reimplementation of a larger research system (omnididdy). This script
lets the viewer display a **real** run of that engine on a harder benchmark by
reading the run's on-disk artifacts directly (plain JSON / TSV — no dependency on
the parent project) and emitting auto-onion's hierarchical ``state.json`` tree:

    origin -> benchmark -> second_loop -> run (architecture) -> ground_container
              -> ground_experiment (parameter-tuning step)

Each architecture (run) node carries its full ``solution`` code; kept experiments
carry their checkpoint code, so the viewer's code panel works exactly as it does
for a native auto-onion run.

Usage:
    python scripts/import_run.py --bench <path-to-benchmark> --out runs/demo --task "..."
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_tsv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        cells = ln.split("\t")
        rows.append({header[i]: (cells[i] if i < len(cells) else "") for i in range(len(header))})
    return rows


def _fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _pretty(arch_class: str, fallback: str) -> str:
    if not arch_class:
        return fallback
    return arch_class.replace("_", " ").title()


def _experiment_code(run_dir: Path, eid: int, exp: dict) -> str:
    """Kept experiments snapshot their code to logs/checkpoints/{eid:04d}_{loss}.py."""
    cp = run_dir / "logs" / "checkpoints"
    if cp.exists():
        for f in cp.glob(f"{eid:04d}_*.py"):
            try:
                return f.read_text(encoding="utf-8")
            except Exception:
                pass
    snap = exp.get("code_snapshot")
    if isinstance(snap, str) and "def solve" in snap:
        return snap
    return ""


def _build_experiments(run_dir: Path) -> tuple[list[dict], float | None]:
    """Return (root experiment nodes, run best_loss) for one run, with the
    parent_id lineage preserved (kept attempts extend the spine; reverted ones
    are dead-end leaves)."""
    ge_dir = run_dir / "logs" / "ground_experiments"
    raw = []
    if ge_dir.exists():
        for f in sorted(ge_dir.glob("*.json")):
            d = _read_json(f)
            if d:
                raw.append(d)
    nodes_by_eid: dict[int, dict] = {}
    order: list[int] = []
    best = None
    for e in raw:
        eid = int(e.get("experiment_id", e.get("trial_id", 0)) or 0)
        training = e.get("training") or {}
        val = _fnum(training.get("val_loss"))
        improved = bool(e.get("improved"))
        decision = e.get("decision", "")
        status = "skipped" if decision == "skipped" else ("kept" if improved else "reverted")
        node = {
            "name": f"exp-{eid}",
            "type": "ground_experiment",
            "id": f"{run_dir.name}-e{eid}",
            "iter": eid,
            "val_loss": val,
            "improved": improved,
            "status": status,
            "hypothesis": (e.get("llm_output") or {}).get("hypothesis", "") or "(no description)",
            "code": _experiment_code(run_dir, eid, e),
            "_parent_eid": int(e.get("parent_id", 0) or 0),
            "children": [],
        }
        nodes_by_eid[eid] = node
        order.append(eid)
        if improved and val is not None and (best is None or val < best):
            best = val
    roots: list[dict] = []
    for eid in order:
        n = nodes_by_eid[eid]
        pid = n.pop("_parent_eid")
        if pid in nodes_by_eid and pid != eid:
            nodes_by_eid[pid]["children"].append(n)
        else:
            roots.append(n)
    if best is None:  # no kept experiment — fall back to the best value seen
        vals = [nodes_by_eid[e]["val_loss"] for e in order if nodes_by_eid[e]["val_loss"] is not None]
        best = min(vals) if vals else None
    return roots, best, len(raw)


def main() -> None:
    ap = argparse.ArgumentParser(description="Import a real run into an auto-onion state.json")
    ap.add_argument("--bench", required=True, help="path to the benchmark dir (with runs/ + second_loop_log/)")
    ap.add_argument("--out", default="runs/demo", help="output run dir (relative to repo root)")
    ap.add_argument("--task", default=None, help="task label shown in the viewer header")
    ap.add_argument("--metric-format", default=".2f")
    args = ap.parse_args()

    bench = Path(args.bench).resolve()
    sl_rows = {int(r["id"]): r for r in _read_tsv(bench / "second_loop_log" / "results.tsv") if r.get("id", "").isdigit()}

    # Collect runs, keyed by their second-loop cycle (run-0000 = baseline, cycle 0).
    runs_by_cycle: dict[int, dict] = {}
    for rd in sorted((bench / "runs").iterdir()):
        if not rd.is_dir() or rd.name.startswith("_"):
            continue
        tag = _read_json(rd / "logs" / "cycle_tag.json") or {}
        cycle = int(tag.get("second_loop_cycle", 0) or 0)
        # Skip in-progress cycle runs (a cycle with no verdict in the L2 log yet).
        if cycle > 0 and cycle not in sl_rows:
            continue
        exps, best, total = _build_experiments(rd)
        sl = sl_rows.get(cycle, {})
        solution = rd / "solution" / "main.py"
        code = solution.read_text(encoding="utf-8") if solution.exists() else ""
        runs_by_cycle[cycle] = {
            "dir": rd, "cycle": cycle, "best": best, "exps": exps, "total": total, "tag": tag, "sl": sl, "code": code,
            "status": sl.get("status", "kept" if cycle == 0 else "reverted"),
            "parent_cycle": int(sl.get("parent_id", 0) or 0),
            "arch": _pretty(sl.get("arch_class", ""), "baseline"),
            "hypothesis": tag.get("hypothesis") or sl.get("hypothesis", "") or "baseline",
        }

    baseline_loss = runs_by_cycle.get(0, {}).get("best")
    losses = [r["best"] for r in runs_by_cycle.values() if r["best"] is not None]
    best_overall = min(losses) if losses else None
    best_pct = None
    if baseline_loss not in (None, 0) and best_overall is not None:
        best_pct = round((baseline_loss - best_overall) / abs(baseline_loss) * 100, 2)

    def run_node(r: dict) -> dict:
        cycle = r["cycle"]
        rank = "baseline" if cycle == 0 else ("green" if r["status"] == "kept" else "red")
        ground = {
            "name": "ground", "type": "ground_container", "id": f"ground-{cycle}",
            "total_experiments": r["total"], "best_loss": r["best"], "children": r["exps"],
        }
        return {
            "name": "baseline" if cycle == 0 else r["arch"],
            "type": "run", "id": f"run-{cycle}", "run_rank": rank,
            "best_loss": r["best"], "baseline_loss": baseline_loss,
            "total_experiments": r["total"], "hypothesis": r["hypothesis"],
            "code": r["code"], "metric_format": args.metric_format, "children": [ground],
        }

    # Nest runs by their second-loop parent cycle (kept advances the trunk).
    node_by_cycle = {c: run_node(r) for c, r in runs_by_cycle.items()}
    second_children: list[dict] = []
    for cycle in sorted(runs_by_cycle):
        r = runs_by_cycle[cycle]
        if cycle == 0:
            second_children.append(node_by_cycle[cycle])
        else:
            parent = node_by_cycle.get(r["parent_cycle"])
            (parent["children"] if parent else node_by_cycle[0]["children"]).append(node_by_cycle[cycle])

    second_loop = {"name": "second loop proposer", "type": "second_loop",
                   "total_runs": len(runs_by_cycle), "best_loss": best_overall, "children": second_children}
    benchmark = {"name": bench.name, "type": "benchmark", "metric_format": args.metric_format,
                 "metric_direction": "minimize", "best_loss": best_overall, "baseline_loss": baseline_loss,
                 "children": [second_loop]}
    tree = {"name": "origin", "type": "origin", "children": [benchmark]}

    task = args.task or f"{bench.name} — real two-loop run (lower is better)"
    state = {
        "task": task, "status": "done", "metric_format": args.metric_format, "metric_direction": "minimize",
        "best_fitness": best_overall, "best_improvement_pct": best_pct,
        "source": f"real run imported from {bench.name} (parent engine, omnididdy)",
        "tree": tree,
    }
    out_dir = (HERE / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"wrote {out_dir / 'state.json'}")
    print(f"  benchmark: {bench.name}  | runs: {len(runs_by_cycle)}  | baseline_loss={baseline_loss}  best={best_overall}  ({best_pct}% better)")
    for c in sorted(runs_by_cycle):
        r = runs_by_cycle[c]
        print(f"  cycle {c}: {r['arch']:<26} {r['status']:<9} best={r['best']}  ({r['total']} exps)")


if __name__ == "__main__":
    main()
