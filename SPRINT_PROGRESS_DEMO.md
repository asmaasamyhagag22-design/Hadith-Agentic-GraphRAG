# Musnad Demo & Deployment Sprint Progress (`demo-app`)

Branch: `demo-app` (worktree `../sanad-demo`, branched from `origin/retrieval-upgrade`)

API Budget Cap: `<= 40 Pro`, `<= 40 Flash` (spent so far: `0 Pro`, `0 Flash`, `0 Embed`)

## Step Status
- [done] **Step 1 — Observational Trace Collector (`src/trace.py`)**:
  - Created `src/trace.py` (`TraceCollector`, `TraceEvent`) with zero overhead when `trace=None`.
  - Wired optional `trace=None` into `src/pipeline.py`, `src/retrieve.py`, `src/agent.py`, and `src/answer.py`.
  - Created `tests/test_trace.py` (5/5 passing).
- [done] **Step 2 — Professional Streamlit App (`app/`)**:
  - Added `.streamlit/config.toml`, `app/config.py`, `app/state.py`, `app/components.py`, `app/streamlit_app.py`.
  - Implemented Arabic RTL UI, 4 example buttons, "how it works" expander, horizontal sanad chips (Muslim's teacher to highlighted Companion + `+N طرق أخرى`), vocalised matn expanders, progressive live trace panel with `source: SQLite sanad graph` badges, total time & call counts, Advanced sidebar (`auto/on/off` and retrieval mode), `@st.cache_resource` warm-up, and friendly Arabic error card + details expander + logging.
  - Added `tests/test_app_ui.py` (AppTest + component tests).
  - Verified: `check_docs` 5/5, CI subset `301 passed, 26 deselected`, full `pytest` `327 passed`.
- [in_progress] **Step 3 — Replay Mode (`data/demo/recorded_runs.json`)**
- [pending] **Step 4 — Parallel HyDE + Query Embedding Latency Improvement**
- [pending] **Step 5 — 20-Question Live Playwright Self-Test & Findings**
- [pending] **Step 6 — Docker, AWS CDK (`infra/`), Usage Guard, Runbook & README**
- [pending] **Final Merge (`origin/retrieval-upgrade` -> `demo-app`) & Full Verification**
