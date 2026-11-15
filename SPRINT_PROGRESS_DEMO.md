# Musnad Demo & Deployment Sprint Progress (`demo-app`)

Branch: `demo-app` (worktree `../sanad-demo`, branched from `origin/retrieval-upgrade`)

API Budget Cap: `<= 40 Pro`, `<= 40 Flash` (base sprint: `40 Pro`, `39 Flash`, `103 Embed` — Step 3 `17P/8F/16E`, Step 4 `0P/15F/30E`, Step 5 router `0P/0F/24E`, Step 5 live `23P/16F/33E`) + Pre-deploy `run_03` re-record (`2 Pro`, `0 Flash`, `0 Embed`; total recorded: `42 Pro`, `39 Flash`, `103 Embed`)

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
- [done] **Step 5 — 20-Question Live Playwright Self-Test & Findings**:
  - Executed 20 brand-new natural Arabic questions (`text`, `chain`, `refusal`, `mixed`, `typos`, `colloquial`, `very_short`, `very_long`, verified non-overlapping with all 753 eval strings & 10 recorded runs) live via Playwright (`23 Pro, 16 Flash, 33 Embed`; 20/20 accurate & verified vs `muslim_chunks.json`/`sanad_graph.sqlite`, 0 console/page errors, 0 horizontal overflow on desktop & mobile).
  - Fixed 4 visual UI bugs caught from screenshots in `app/components.py` (collapsed sidebar RTL transform overlap, markdown-in-HTML numbered list border clipping & vertical gaps + bold/code rendering, Arabic status localization for unlinked hadiths, and trace `[ids]` bidi/plural grammar) + added unit test coverage in `tests/test_app_ui.py` (4/4).
  - Recorded all 20 results + 6 open quality/validator/latency findings (untouched per rules) in `docs/demo_findings.md` and `data/demo/step5_selftest_results.json`.
  - Verified: `check_docs` 5/5, CI subset `308 passed, 26 deselected`, full `pytest` `334 passed`.
- [done] **Step 6 — Docker, AWS CDK (`infra/`), Usage Guard, Runbook & README**:
  - Cloud runtime profile (`pyproject.toml` `[dependency-groups] cloud`, lazy heavy imports in `src/`) with `MUSNAD_CLOUD=1` disabling legacy fallback so API failures gracefully fall back to Replay (`src/pipeline.py`).
  - Multi-stage non-root `Dockerfile`, `.dockerignore`, `docker-compose.yml`: built `musnad-demo:latest` (`1112945584` bytes / `1.11GB` unpacked / `299MB` compressed, `uid=999(musnad)`), verified both Replay (`MUSNAD_DEMO_REPLAY=1`) and Cloud fallback (`MUSNAD_CLOUD=1`) modes via Docker + Playwright.
  - AWS CDK stack in `infra/` (`musnad_stack.py`, `app.py`, `cdk.json`): 2-AZ public VPC (`0` NAT gateways), ECR, ECS Fargate (`512/1024` configurable), ALB (sticky sessions, `/_stcore/health`, optional HTTPS/redirect), 14-day CloudWatch LogGroup, Secrets Manager, DynamoDB on-demand TTL table, least-privilege TaskRole, AWS Budgets alarm (`cdk.out/MusnadDemoStack.template.json` synthesized).
  - Atomic usage guard (`app/usage_guard.py` + `app/streamlit_app.py`) enforcing per-session, per-IP hourly, and global daily (`MUSNAD_DAILY_CAP`, default `200`) limits in DynamoDB or in-memory local backend.
  - Added `docs/deploy_aws.md` (GCP `Vertex AI User` SA + billing alert + ordered AWS Console/Terminal runbook), `README.md` (`## Live demo` + `### Deployment`), and 2x `docs/assets/demo-screenshot.png`.
- [done] **Final Merge (`origin/retrieval-upgrade` -> `demo-app`) & Full Verification**
  - `git fetch origin && git merge origin/retrieval-upgrade --no-edit` -> `Already up to date.` (`origin/retrieval-upgrade` at `2665785` is ancestor of `demo-app`).
  - Final post-merge checks: `uv run python infra/app.py`, `uv run python -m src.check_docs`, CI pytest subset, and full `pytest` suite.
- [done] **Pre-Deployment Fixes (`demo-app`)**:
  - **Finding #1 (`LOOSE_CITATION` newline fix)**: Restricted separator in `src/answer.py` (`_HSPACE = r"[^\S\r\n]"`) so numeric lists after `"مسلم:\n1."` never produce phantom citations (`tests/test_answer_validation.py`). Offline re-validation across all `741` saved outputs (`735` JSON rows across `e5_results.json`, `e5_simple_default_results.json`, `c5_dev_results.json`, `c5_golden_results.json`, `c5_chain_test_results.json`, `recorded_runs.json` + `6` `auto_smoke_cli.txt` blocks; `0` API calls) changed `1` item ONLY: `recorded_runs.json` `runs[2]` (`run_03_chain_id_7306`), where `loose_cited_ids` dropped from `{1, 7306}` to `{7306}` (`out_of_context_citation` -> `valid_answer`); `0` eval metrics in `EXPERIMENTS.md`/`README.md` changed. Re-recorded `run_03_chain_id_7306` cleanly (`2 Pro, 0 Flash, 0 Embed`, `regenerated=False`).
  - **Generation Timeout (`45 s` + 1 retry)**: Set default `GENERATE_TIMEOUT_MS=45000`, `MAX_TIMEOUT_RETRIES=1`, added `GenerationTimeoutError` and `run_model_call_with_timeout_and_retry` across `src/answer.py`, `src/agent.py`, `src/trace.py`, `app/state.py`, `app/components.py`, and `app/streamlit_app.py` (showing the Arabic retry message instead of replay on double timeout even when `MUSNAD_CLOUD=1`, and logging timeout retries without Pro double-counting). Verified in `tests/test_generation_timeout.py` and `tests/test_app_ui.py`.
  - **UI Polish & Docker Verification**: Added `.streamlit/config.toml` `[client] toolbarMode = "minimal"` (copied into `Dockerfile` and `docs/deploy_aws.md`), updated `.sanad-strip`/`.narrator-chip` in `app/components.py` to stay on one horizontal RTL scrolling line, rebuilt `musnad-demo:latest` (`1.11GB`), verified layout in Playwright (`deployVisible=False`, `chipTopSpread <= 1px`, `overflowX=0` on `run_05`, `7294`, and `7306`), and recaptured 2x `docs/assets/demo-screenshot.png`.
  - **Docs & Assets Cleanup**: Removed 4 unused `docs/assets/musnad-architecture-{final,v2}-{dark,light}.png` files (`git rm`) and shortened `README.md` line 3 to `"Arabic question answering over Sahih Muslim that cites the exact hadith, attaches its narrator chain from a SQLite graph, and refuses when the source is silent."`.
