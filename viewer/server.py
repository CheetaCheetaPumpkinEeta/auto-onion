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
    """Launch a simple two-loop run (offline mock TSP) in the background and
    return its run name so the page can follow it live."""
    body = request.get_json(silent=True) or {}
    name = "run-" + time.strftime("%Y%m%d-%H%M%S")
    cmd = [sys.executable, str(REPO / "run.py"), "--mock",
           "--run-dir", f"runs/{name}",
           "--cycles", str(int(body.get("cycles", 3))),
           "--l1-iters", str(int(body.get("l1_iters", 4)))]
    subprocess.Popen(cmd, cwd=str(REPO),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return jsonify({"run": name})


if __name__ == "__main__":
    print("auto-onion dashboard  ->  http://localhost:5005")
    app.run(host="127.0.0.1", port=5005, debug=False)
