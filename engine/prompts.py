"""Load the L1 / L2 system prompts from ``prompts/*.md`` (single source of truth,
so the human-readable docs and the strings the model actually sees never drift)."""
from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "prompts"

L1_SYSTEM = (_DIR / "ground_loop.md").read_text(encoding="utf-8")
L2_SYSTEM = (_DIR / "second_loop.md").read_text(encoding="utf-8")
