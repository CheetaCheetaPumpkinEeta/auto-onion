"""Ultra-simple live viewer.

A single Flask process that serves one HTML page and a small JSON API. The page
polls ``/api/state`` and redraws the lineage graph. A run-picker lets you switch
between the bundled real-engine demos (``runs/demo-*``) and your own runs.

    python viewer/server.py     ->     http://localhost:5005
"""
from __future__ import annotations

import json
import os
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
    target = next((d for d in dirs if d.name == want), None) if want else None
    if target is None:
        target = _default_run(dirs)
    if target is None:
        return jsonify({"empty": True, "tree": None, "best_improvement_pct": 0.0,
                        "task": "no runs yet — run:  python run.py --mock"})
    return jsonify(_load(target))


if __name__ == "__main__":
    print("auto-onion viewer  ->  http://localhost:5005")
    app.run(host="127.0.0.1", port=5005, debug=False)
