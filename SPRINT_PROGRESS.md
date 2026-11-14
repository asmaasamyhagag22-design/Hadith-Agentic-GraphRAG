# Musnad Autonomous Sprint Progress

- **Branch**: `retrieval-upgrade` (never push to `main`)
- **Baseline commit**: `354c01a` (`docs: update README roadmap and document target architecture assets`)
- **Budget used**: `0 / 500` Pro-class calls, `0 / 800` Flash-class calls

## Completed Steps

### Phase A — Sanad-attached answers (`99d6d63`, progress commit `da9bd23`)
- **A1/A3 (`src/answer.py`)**: Single-connection `attach_sanad()` attaches `sanad` & `sanad_error` on `VALID_ANSWER`; `format_sanad_section()` prints Muslim's teacher down to Companion (`" ← "`) and `"(+N طرق أخرى)"` or plain Arabic status in CLI (`main()`).
- **A2**: Verified `get_ordered_chain()` returns `1..N` (Companion → teacher); CLI reverses to teacher → Companion.
- **A4 (`tests/test_sanad_attachment.py`)**: 8 offline unit tests covering all cases.
- **A5 (`src/measure_sanad_attachment.py`, `EXPERIMENTS.md` §30)**: Citation coverage `211/220` (`95.9%`), unique hadith coverage `74/76` (`97.4%`), median latency `2.226 ms`, p95 `3.444 ms` (`0` LLM calls).

### Phase B — Chain-question evaluation set & deterministic scorer (`807db8a`, progress commit `16a961b`)
- **B1/B2 (`src/build_chain_eval.py`, `EXPERIMENTS.md` §31)**:
  - Built `data/raw/chain_eval.jsonl` (`40` items, all gold answers computed directly from `sanad_graph.sqlite`, `0` LLM calls; all `40` hadith IDs unique; includes the 3 `narrator` items from `data/raw/golden.jsonl`).
  - Stratified split (`5` types × `8` each → `3 dev / 5 test` per type; zero hadith-ID overlap between splits):
    - `data/raw/chain_eval_dev.jsonl` (`15` items, sha256 `ee90b7fa0eed67aee18927254e4dc894ae4fa37d531e2d16bd0c539ec3f92057`)
    - `data/raw/chain_eval_test.jsonl` (`25` items, **FROZEN**, sha256 `7cb399587827dddee45ed5af083407f21d04056fd4dcee7f9cb8931777c39025`)
    - `data/raw/chain_eval.jsonl` (`40` items, sha256 `4458c4c58547e39694e2662b649f90b00c5a862b26b205f5d526e5c97e175c43`)
- **B3 (`src/sanad_names.py`, `src/chain_eval.py`, `tests/test_chain_eval.py`)**:
  - Longest-span normalized `mis_narrator` lexicon (`NarratorLexicon`) with Arabic proclitic handling (`و/ف/ب/ل/ك`) and kunya inflections (`أبو/أبا/أبي`).
  - Deterministic scorer checking routing (`get_isnad` / `search_hadith`), zero out-of-chain narrator names, expected narrators/counts/booleans, full abstention (`isnad_count=0` & grading-blocked `7380`), and partial grading abstention (`12068`).
- **Verification**: Full pytest `300 passed`, CI marker pytest `274 passed, 26 deselected`, `check_docs` green.

### Phase C1–C4 — Agent, C2 validators, MUSNAD_AGENT flag, and unit tests (`96f4cbb`)
- **C1 (`src/agent.py`)**: `gemini-4-argon` with `search_hadith(query)` (default pipeline top-5: ids + matn + chapter) and `get_isnad(hadith_id)` (`sanad_context` ordered lists + companion/teacher anchors), `MAX_TOOL_CALLS = 3`, thread-pool non-blocking tool timeout, deterministic fallback to non-agent `answer_with_details` on model/tool/timeout failure.
- **C2 (`src/answer.py`, `src/agent.py`)**: Extended `validate_answer(..., tool_ids=...)` for cited-ID subset enforcement plus `validate_narrator_names` (`find_disallowed_narrators` against returned `get_isnad` chains); invalid → regenerate once → refuse; then Phase A `attach_sanad()` attaches verified SQLite chains.
- **C3 (`src/pipeline.py`, `src/answer.py`)**: `MUSNAD_AGENT=on|off` (default `off`) resolved in `build_pipeline` (`agent_enabled`) and `answer_with_details` (`_resolve_use_agent`), routing CLI (`main`), `answer_eval`, and `smoke_test` through one unified entry point.
- **C4 (`tests/test_agent.py`)**: 7 offline unit tests covering routing (`search_hadith`, `get_isnad`, 2-step topic resolution), max-3 tool-call loop cap, ID-subset and narrator-name regenerate→refuse validators, timeout/error fallback, and `MUSNAD_AGENT` flag across `answer_with_details`, `answer_eval`, and `smoke_test`.
- **Verification**: `tests/test_agent.py` `7 passed`, full pytest `307 passed, 35 subtests passed`, CI marker pytest `281 passed, 26 deselected`, `check_docs` green (`0` API calls used).

## Next Step
- **Phase C5 — Live evaluation (`dev` tuning → `golden` 3× ON vs OFF → frozen `chain_eval_test` ON vs OFF)**:
  - Build `src/experiment_c5_agent.py` with exact Pro/Flash API call tracking and budget guardrails (`<= 500` Pro, `<= 800` Flash).
  - Run `chain_eval_dev.jsonl` (`15`) first to verify live prompt/tool behavior before touching `golden` or `chain_eval_test.jsonl`.
  - Run 3× golden text (`ON` vs `OFF`, `n=30` each) and 1 final frozen `chain_eval_test.jsonl` (`n=25`, `ON` vs `OFF`), record everything in `EXPERIMENTS.md`, and check Gate 1 thresholds.
- **Then**: Gate 1 decision (`DEFAULT_AGENT_MODE = "on"` if passed) → Phase D + Gate 2 → Phase E (`docs/holdout_review.md`) + Gate 3.
