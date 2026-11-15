# Musnad Demo & Deployment Sprint Progress (`demo-app`)

Branch: `demo-app` (worktree `../sanad-demo`, branched from `origin/retrieval-upgrade`)

API Budget Cap: `<= 40 Pro`, `<= 40 Flash` (spent so far: `0 Pro`, `0 Flash`, `0 Embed`)

## Step Status
- [done] **Step 1 — Observational Trace Collector (`src/trace.py`)**:
  - Created `src/trace.py` (`TraceCollector`, `TraceEvent`) with zero overhead when `trace=None`.
  - Wired optional `trace=None` into `src/pipeline.py`, `src/retrieve.py`, `src/agent.py`, and `src/answer.py`.
  - Created `tests/test_trace.py` (identical outputs with/without trace, text/chain/topic/refusal/retry/fallback sequences, live `on_event`, round-trip serialization).
  - Verified: CI subset `298 passed, 26 deselected`, full `pytest` `324 passed`, `check_docs` 5/5 passed.
- [in_progress] **Step 2 — Professional Streamlit App (`app/`)**
- [pending] **Step 3 — Replay Mode (`data/demo/recorded_runs.json`)**
- [pending] **Step 4 — Parallel HyDE + Query Embedding Latency Improvement**
- [pending] **Step 5 — 20-Question Live Playwright Self-Test & Findings**
- [pending] **Step 6 — Docker, AWS CDK (`infra/`), Usage Guard, Runbook & README**
- [pending] **Final Merge (`origin/retrieval-upgrade` -> `demo-app`) & Full Verification**
