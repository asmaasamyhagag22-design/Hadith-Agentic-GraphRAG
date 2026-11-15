# Musnad Demo & Deployment Sprint Progress (`demo-app`)

Branch: `demo-app` (worktree `../sanad-demo`, branched from `origin/retrieval-upgrade`)

API Budget Cap: `<= 40 Pro`, `<= 40 Flash` (spent so far: `17 Pro`, `23 Flash`, `46 Embed` — `17 Pro / 8 Flash / 16 Embed` in Step 3 + `0 Pro / 15 Flash / 30 Embed` in Step 4; remaining: `23 Pro`, `17 Flash`)

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
- [done] **Step 4 — Parallel HyDE + Query Embedding Latency Improvement**:
  - Updated `src/retrieve.py` (`UpgradedRetriever._blended_query_vector`) to run HyDE generation+embedding concurrently with raw-query embedding using `ThreadPoolExecutor` and isolated `genai.Client` instances.
  - Verified byte-identical vectors (`np.array_equal`), retrieved IDs, and `format_context` outputs + true `Barrier(2)` concurrency in `tests/test_parallel_hyde.py` (2/2).
  - Measured live uncached latency on `n=15` golden questions (`live_latency_and_cost.records[:15]` via `src/measure_parallel_hyde.py`): median `7587.98 ms -> 6148.29 ms` (`-1439.69 ms`, `-19.0%`), p95 `9995.12 ms -> 7590.15 ms` (`-2404.97 ms`, `-24.1%`). Recorded in `EXPERIMENTS.md` (`## 35.`) and `README.md`.
  - Verified: `check_docs` 5/5, CI subset `307 passed, 26 deselected`, full `pytest` `333 passed`.
- [in_progress] **Step 5 — 20-Question Live Playwright Self-Test & Findings**
- [pending] **Step 6 — Docker, AWS CDK (`infra/`), Usage Guard, Runbook & README**
- [pending] **Final Merge (`origin/retrieval-upgrade` -> `demo-app`) & Full Verification**
