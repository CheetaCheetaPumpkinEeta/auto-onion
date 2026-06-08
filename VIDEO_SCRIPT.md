# auto-onion — demo video script

**Repo:** https://github.com/CheetaCheetaPumpkinEeta/auto-onion
**Track:** Automation / Agent Systems · aim for ~3–4 min (10 min is the cap)
**Dashboard:** `python viewer/server.py` → http://localhost:5005

> Format below: the **requirement** (what the video must cover, from the rubric),
> then **what to say** (bullets), with `[SHOW …]` cues for the live demo. Repo link
> is at the end.
>
> **On-camera safety net:** the dashboard's **ℹ How it works** button shows the same
> diagram + Q1–Q4 answers on-screen — open it if you want the talking points visible
> while you record. Everything below maps 1:1 to that page.

---

### Q1 — Why did you build this?  · *Problem & Insight (3 pts)*
*Requirement: name a real bottleneck + a compelling, original motivation.*
- Improving any solver or model is a slow human loop: **think of an idea → code it → measure it → keep or throw it out → repeat.** The bottleneck is the **human in that loop**.
- My insight: that loop is mechanical enough to hand to an LLM — but a *single* loop plateaus (it only tweaks parameters). The fix is **two loops**: an inner loop **tunes**, an outer loop proposes a **structurally new** approach and judges it by its **tuned ceiling**. (Layered search → the name "**onion**.")

### Q2 — How does it work?  · *Execution & Technical Work (5 pts)*
*Requirement: explain the agent system + show the artifact working.*
- *[SHOW the dashboard]* Two LLM loops edit **one file**, scored by a **frozen harness** they can't touch:
  - **Ground loop (L1):** a **smaller model (Haiku)** tunes parameters — keep-if-better, else **revert** (each candidate runs in a sandboxed subprocess).
  - **Second loop (L2):** a **bigger model (Sonnet)** proposes a **structurally different** architecture, judged by the best score it reaches **after** tuning — *"compare optimized versions, not first drafts."*
- *[SHOW ★ Demo → set-cover]* A real engine run: greedy **26%** gap → **ILP** → **Lagrangian relaxation** = **55% better**, with a **tabu-search** branch **reverted** by the gate. Click any node → the **hypothesis** it tried and the **result**.
- *[SHOW ▶ Run the system]* This **actually runs it live** — Sonnet proposes, Haiku tunes, the tree builds in real time, driven by the local Claude CLI (no API key).

### Evaluation & evidence  · *(3 pts)*
*Requirement: validate claims / show limitations.*
- **Reproducible:** `python run.py --mock` is deterministic — **+17.07%** every run, no API key. (I even caught and fixed a real stale-bytecode nondeterminism bug getting there.)
- **Real runs:** the set-cover / max-cut demos are **genuine engine output** (imported from my larger parent project; disclosed in the README).
- **Honest limits:** the search is **greedy with no long-term memory**; the hard-benchmark trees were produced by the parent engine and imported.

### Q3 — Use cases / impact
- Anything with a **fitness signal**: solvers, heuristics, ML-training code, GPU kernels, even prompts.
- Lets **one person run automated R&D** that used to need a team — the "scale yourself" idea, made concrete.

### Q4 — What would you add?
- The **memory** I deliberately trimmed: an archive of rejected ideas + **diversity-driven** search, so it *explores* instead of just hill-climbing.
- A clean **benchmark abstraction** to plug in more substrates — e.g. **CIFAR** image classification — behind the same two loops.

### Close — disclosure & credit  · *Process, Integrity & Disclosure (2 pts)*
- Built with **disclosed** AI assistance (Claude Code); the offline demo has **zero AI calls**, so it's reproducible. It's a clean, trimmed **reimplementation of my larger project, omnididdy**, cited throughout.

---

**Repo:** https://github.com/CheetaCheetaPumpkinEeta/auto-onion
