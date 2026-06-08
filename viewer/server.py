"""Dashboard server.

A single Flask process that serves the lineage-graph dashboard and a small API:
  GET  /api/runs            list runs (bundled demos + your own)
  GET  /api/state?run=NAME  one run's tree (the graph polls this)
  POST /api/run             launch a fresh two-loop run (mock TSP) and return its name

The page has a Run button (kick off the engine, watch the graph build live) and a
Demo button (load a bundled real-engine run instantly).

    python viewer/server.py     ->     http://localhost:5005
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RUNS = REPO / "runs"

app = Flask(__name__, static_folder=str(HERE))


def _run_dirs() -> list[Path]:
    return [p.parent for p in RUNS.glob("*/state.json")]


def _order_key(d: Path):
    # Demos first (alphabetical), then your own runs newest-first.
    is_demo = d.name.startswith("demo-")
    mtime = os.path.getmtime(d / "state.json")
    return (0, d.name) if is_demo else (1, -mtime)


def _default_run(dirs: list[Path]) -> Path | None:
    # If a real run is actively building, default to it so a live run shows up
    # immediately; otherwise a demo (already-run tree) for graders/reviewers.
    now = time.time()
    for d in sorted((x for x in dirs if not x.name.startswith("demo-")),
                    key=lambda x: -os.path.getmtime(x / "state.json")):
        try:
            st = json.loads((d / "state.json").read_text(encoding="utf-8"))
            if st.get("status") == "running" and now - os.path.getmtime(d / "state.json") < 1800:
                return d
        except Exception:
            pass
    return sorted(dirs, key=_order_key)[0] if dirs else None


def _load(d: Path) -> dict:
    data = json.loads((d / "state.json").read_text(encoding="utf-8"))
    data["run"] = d.name
    return data


@app.route("/")
def index():
    return send_from_directory(str(HERE), "index.html")


@app.route("/api/runs")
def runs():
    dirs = sorted(_run_dirs(), key=_order_key)
    items = []
    for d in dirs:
        try:
            data = json.loads((d / "state.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        items.append({"run": d.name, "task": data.get("task", ""),
                      "best": data.get("best_improvement_pct"),
                      "demo": d.name.startswith("demo-")})
    default = _default_run(dirs)
    return jsonify({"runs": items, "default": default.name if default else None})


@app.route("/api/state")
def state():
    dirs = _run_dirs()
    want = request.args.get("run")
    if want:
        target = next((d for d in dirs if d.name == want), None)
        if target is None:  # a just-launched run whose state.json hasn't appeared yet
            return jsonify({"empty": True, "tree": None, "best_improvement_pct": None,
                            "run": want, "task": "starting…"})
        return jsonify(_load(target))
    target = _default_run(dirs)
    if target is None:
        return jsonify({"empty": True, "tree": None, "best_improvement_pct": 0.0,
                        "task": "no runs yet — press Run"})
    return jsonify(_load(target))


@app.route("/api/run", methods=["POST"])
def run():
    """Actually run the two loops live with real LLMs — a bigger model (L2)
    makes the architectural changes, a smaller model (L1) tunes the parameters.
    Uses the local ``claude`` CLI (your Claude Code login; no API key needed).
    Runs in the background; the page follows the tree as it builds."""
    body = request.get_json(silent=True) or {}
    name = "run-" + time.strftime("%Y%m%d-%H%M%S")
    cmd = [sys.executable, str(REPO / "run.py"),
           "--l2-model", body.get("l2_model", "sonnet"),   # bigger model: architecture (L2)
           "--l1-model", body.get("l1_model", "haiku"),    # smaller model: tuning (L1)
           "--backend", "cli",
           "--run-dir", f"runs/{name}",
           "--cycles", str(int(body.get("cycles", 3))),
           "--l1-iters", str(int(body.get("l1_iters", 2)))]
    subprocess.Popen(cmd, cwd=str(REPO),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return jsonify({"run": name})


if __name__ == "__main__":
    print("auto-onion dashboard  ->  http://localhost:5005")
    app.run(host="127.0.0.1", port=5005, debug=False)
