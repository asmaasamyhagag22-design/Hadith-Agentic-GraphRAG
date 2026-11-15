# Musnad Demo & Deployment Sprint Progress (`demo-app`)

Branch: `demo-app` (worktree `../sanad-demo`, branched from `origin/retrieval-upgrade`)

API Budget Cap: `<= 40 Pro`, `<= 40 Flash` (spent so far: `17 Pro`, `8 Flash`, `16 Embed` — includes 1 Pro / 1 Flash / 2 Embed from aborted initial run_01 + 16 Pro / 7 Flash / 14 Embed across 10 recorded runs)

## Step Status
- [done] **Step 1 — Observational Trace Collector (`src/trace.py`)**:
  - `src/trace.py` (`TraceCollector`, `TraceEvent`) wired optionally across `src/pipeline.py`, `src/retrieve.py`, `src/agent.py`, `src/answer.py`, plus `tests/test_trace.py` (5/5).
- [done] **Step 2 — Professional Streamlit App (`app/`)**:
  - RTL Arabic UI (`app/config.py`, `app/state.py`, `app/components.py`, `app/streamlit_app.py`, `.streamlit/config.toml`), 4 examples, progressive live trace, horizontal narrator chips, `@st.cache_resource` warm-up, error handling + `tests/test_app_ui.py` (3/3).
- [done] **Step 3 — Replay Mode (`data/demo/recorded_runs.json`)**:
  - Recorded 10 real runs with full traces via `src/record_demo_runs.py` into `data/demo/recorded_runs.json` (2 text, 3 chain incl. topic chain, 1 refusal, 1 narrator, 3 choice).
  - Implemented `app/replay.py` and wired explicit `MUSNAD_DEMO_REPLAY=1`, missing credentials fallback, usage-cap hook, and cloud fallback with `"Recorded run — replayed"` banner and real step durations.
  - Added `tests/test_replay.py` (4/4).
  - Verified: `check_docs` 5/5, CI subset `305 passed, 26 deselected`, full `pytest` `331 passed`.
- [in_progress] **Step 4 — Parallel HyDE + Query Embedding Latency Improvement**
- [pending] **Step 5 — 20-Question Live Playwright Self-Test & Findings**
- [pending] **Step 6 — Docker, AWS CDK (`infra/`), Usage Guard, Runbook & README**
- [pending] **Final Merge (`origin/retrieval-upgrade` -> `demo-app`) & Full Verification**
