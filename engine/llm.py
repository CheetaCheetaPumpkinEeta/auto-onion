"""LLM clients behind one tiny provider-neutral interface.

Three things live here:

* ``LLMClient``      — the interface both loops call: ``complete(system, user, kind)``.
* ``AnthropicClient``— real Claude calls via the official SDK (needs ANTHROPIC_API_KEY).
* ``ClaudeCLIClient``— real Claude via the local ``claude`` CLI; uses your existing
                       Claude Code login, so no API key is needed.
* ``MockClient``     — a deterministic, offline stand-in that returns *real, runnable*
                       code edits from a scripted library, so the whole two-loop
                       system can be demonstrated with zero API keys and zero cost.

``kind`` is "l2" (propose a new architecture) or "l1" (refine the current one).
The real client ignores it except to nudge temperature; the mock uses it to
decide whether to hand out the next architecture or a parameter tweak.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile

_CODE_BLOCK = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """Pull the first ```python fenced block out of an LLM reply; if there's no
    fence, assume the whole reply is code."""
    m = _CODE_BLOCK.search(text)
    return (m.group(1) if m else text).strip()


class LLMClient:
    def complete(self, system: str, user: str, kind: str = "l1") -> str:
        raise NotImplementedError


class AnthropicClient(LLMClient):
    """Real Claude. Provider-neutral in spirit: swap this class for an
    OpenAI-compatible one and nothing else in the engine changes."""

    def __init__(self, model: str):
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise SystemExit(
                "The 'anthropic' package is required for live mode.\n"
                "  pip install anthropic   (and set ANTHROPIC_API_KEY)\n"
                "Or run offline with:  python run.py --mock"
            ) from e
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("Set ANTHROPIC_API_KEY, or run offline with:  python run.py --mock")
        self._client = anthropic.Anthropic()
        self.model = model

    def complete(self, system: str, user: str, kind: str = "l1") -> str:
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0.7 if kind == "l2" else 0.4,
            # Cache the (static) system prompt across calls — cheap polish, real savings.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in msg.content if block.type == "text")


class ClaudeCLIClient(LLMClient):
    """Live mode through the local ``claude`` CLI (Claude Code).

    Uses your existing Claude Code login, so no ANTHROPIC_API_KEY is required —
    this is how the parent project (omnididdy) drives Claude. The CLI runs in
    print mode from an empty temp directory, so it behaves as a pure code
    generator with no project context or filesystem detours.
    """

    def __init__(self, model: str, timeout: int = 600):
        self.model = model
        self.timeout = timeout
        # Run in the repo root (stable). A temp dir can be cleaned mid-run ->
        # NotADirectoryError kills a long run; --disallowedTools keeps the CLI
        # from touching files here.
        self._cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def complete(self, system: str, user: str, kind: str = "l1") -> str:
        prompt = f"{system}\n\n---\n\n{user}"
        # --disallowedTools forces a pure text reply (no agentic file writes that
        # would leave stdout empty). Retry once on an empty reply.
        # --strict-mcp-config: do NOT load the user's MCP servers (each call would
        # otherwise spawn node MCP-server processes that never get reaped — they
        # pile up and stall a long unattended run). --disallowedTools: pure text out.
        cmd = (f"claude --print --model {self.model} --strict-mcp-config "
               '--disallowedTools "Write,Edit,MultiEdit,Bash,Read,Glob,Grep,WebFetch,WebSearch,Task,NotebookEdit,TodoWrite"')
        for _ in range(2):
            try:
                proc = subprocess.run(
                    cmd, input=prompt, capture_output=True, text=True,
                    timeout=self.timeout, shell=True, cwd=self._cwd,
                )
            except subprocess.TimeoutExpired:
                return ""
            out = (proc.stdout or "").strip()
            if out:
                return out
        return ""


class MockClient(LLMClient):
    """Deterministic offline stand-in. For L2 it walks a scripted ladder of
    genuinely-better TSP architectures; for L1 it bumps the current architecture's
    one tunable ``PARAM`` constant. The edits are real Python that really runs —
    the mock fakes the *creativity*, not the *mechanism*."""

    def __init__(self):
        from engine import mock_library

        self._lib = mock_library
        self._l2_index = 0  # how many architectures handed out so far

    def complete(self, system: str, user: str, kind: str = "l1") -> str:
        if kind == "l2":
            code = self._lib.architecture(self._l2_index)
            self._l2_index += 1
            return f"```python\n{code}\n```"
        # L1: tweak the current solution, which the loop passes inside `user`.
        current = self._lib.current_code_from_prompt(user)
        return f"```python\n{self._lib.refine(current)}\n```"
