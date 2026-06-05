"""Ultra-simple live viewer.

A single Flask process that serves one HTML page and one JSON endpoint. The page
polls ``/api/state`` and redraws the architecture/experiment tree plus a picture
of the best tour found so far. It always reads the most recently modified run, so
you can start it once and leave it open across runs.

    python viewer/server.py     ->     http://localhost:5005
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RUNS = REPO / "runs"

app = Flask(__name__, static_folder=str(HERE))


def _latest_state() -> dict:
    states = sorted(RUNS.glob("*/state.json"), key=os.path.getmtime)
    if not states:
        return {"empty": True, "architectures": [], "best_improvement_pct": 0.0,
                "best_tour": None, "task": "no runs yet — run:  python run.py --mock"}
    data = json.loads(states[-1].read_text(encoding="utf-8"))
    data["run"] = states[-1].parent.name
    return data


@app.route("/")
def index():
    return send_from_directory(str(HERE), "index.html")


@app.route("/api/state")
def state():
    return jsonify(_latest_state())


if __name__ == "__main__":
    print("auto-onion viewer  ->  http://localhost:5005")
    app.run(host="127.0.0.1", port=5005, debug=False)
