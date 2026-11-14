# Musnad Autonomous Sprint Progress

- **Branch**: `retrieval-upgrade` (never push to `main`)
- **Baseline commit**: `354c01a` (`docs: update README roadmap and document target architecture assets`)
- **Budget used**: `434 / 500` Pro-class calls, `110 / 800` Flash-class calls (`218` Embed calls; tracked in `data/processed/c5_api_ledger.json`)

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

### Phase C1–C4 — Agent, C2 validators, MUSNAD_AGENT flag, and unit tests (`96f4cbb`, progress commit `59e2443`)
- **C1 (`src/agent.py`)**: `gemini-4-argon` with `search_hadith(query)` (default pipeline top-5: ids + matn + chapter) and `get_isnad(hadith_id)` (`sanad_context` ordered lists + companion/teacher anchors), `MAX_TOOL_CALLS = 3`, thread-pool non-blocking tool timeout, deterministic fallback to non-agent `answer_with_details` on model/tool/timeout failure.
- **C2 (`src/answer.py`, `src/agent.py`)**: Extended `validate_answer(..., tool_ids=...)` for cited-ID subset enforcement plus `validate_narrator_names` (`find_disallowed_narrators` against returned `get_isnad` chains); invalid → regenerate once → refuse; then Phase A `attach_sanad()` attaches verified SQLite chains.
- **C3 (`src/pipeline.py`, `src/answer.py`)**: `MUSNAD_AGENT=on|off` (default `off`) resolved in `build_pipeline` (`agent_enabled`) and `answer_with_details` (`_resolve_use_agent`), routing CLI (`main`), `answer_eval`, and `smoke_test` through one unified entry point.
- **C4 (`tests/test_agent.py`)**: 7 offline unit tests covering routing (`search_hadith`, `get_isnad`, 2-step topic resolution), max-3 tool-call loop cap, ID-subset and narrator-name regenerate→refuse validators, timeout/error fallback, and `MUSNAD_AGENT` flag across `answer_with_details`, `answer_eval`, and `smoke_test`.
- **Verification**: `tests/test_agent.py` `7 passed`, full pytest `307 passed, 35 subtests passed`, CI marker pytest `281 passed, 26 deselected`, `check_docs` green (`0` API calls used).

### Phase C5 — Live evaluation & Gate 1 check (`8031c8e`)
- **Fixes prior to live runs (`src/agent.py`, `src/sanad_names.py`, tests)**:
  - Routed `gemini-3*`/`gemini-4*` tool-calling agent requests through `get_client(location="global")` with transient retry backoff (verified via `test_global_location_client_used_for_argon`).
  - Expanded `_NON_PERSON_PREFIXES` in `src/sanad_names.py` so anonymous `NM_*`/`_*` MIS descriptions (`"من الصحابة"`, `"بعض أزواج النبي"`, `"أصحاب رسول الله"`, `"إحدى نسوة النبي"`) do not trigger false-positive disallowed-narrator regenerations (verified via `test_anonymous_mis_descriptions_do_not_false_trigger`).
- **`chain_eval_dev.jsonl` (`n=15`, `agent_on`, `c5_dev_results.json`)**: Routing `15/15` (`100.0%`), Answer `14/15` (`93.3%`; 1 sibling-ID citation difference `11242` vs `11245` on `chain_topic_03`), Hallucinated narrators `0/15`, Abstention `2/2` (`100.0%`), Median `9,587.6 ms`, p95 `51,108.4 ms`.
- **`golden.jsonl` text (`n=30`: `27` answerable + `3` refusal; 3 runs each, `c5_golden_results.json`)**:
  - `OFF`: Correct citation `26.0/27` (`96.3%`), False refusals `1.0/27` (`3.7%`), Correct refusals `3.0/3` (`100.0%`), Pooled median `4,906.0 ms`, p95 `25,074.3 ms` (`98` Pro, `4` Flash).
  - `ON`: Correct citation `27.0/27` (`100.0%`), False refusals `0.0/27` (`0.0%`), Correct refusals `1.67/3` (`55.6%`; `[1,2,2]`), Pooled median `17,326.3 ms`, p95 `29,167.4 ms` (`181` Pro, `57` Flash; `1/90` live timeout fallback succeeded).
- **Frozen `chain_eval_test.jsonl` (`n=25`, 1 final run, `c5_chain_test_results.json`, sha256 verified)**:
  - `OFF`: Routing `0/25` (`0.0%`), Answer `3/25` (`12.0%`; `0/22` answerable + `3/3` blind refusals), Median `11,033.5 ms`, p95 `16,778.9 ms` (`25` Pro, `25` Flash).
  - `ON`: Routing `25/25` (`100.0%`), Answer `25/25` (`100.0%`), Hallucinated narrators `0/25`, Abstention `3/3` (`100.0%`), Median `8,560.4 ms`, p95 `50,520.4 ms` (`59` Pro, `5` Flash).
- **Documentation & Verification**: Added canonical rows and Section 32 (and fixed `## 31.` heading syntax) in `EXPERIMENTS.md`. Full pytest `309 passed, 35 subtests passed`, CI marker pytest `283 passed, 26 deselected`, `check_docs` all 5 checks passed.
- **⛔ GATE 1 STATUS**: Resolved by user decision (Option 1, simplified): keep agent prompt (`AGENT_SYSTEM_INSTRUCTION`) and single-turn text path unchanged; add deterministic Arabic router + `MUSNAD_AGENT=auto` composition.

### Gate 1 Resolution Step 1–2 — Deterministic Arabic router & `auto` composition (`ea9c282`)
- **Router (`src/router.py`)**: Added deterministic zero-API Arabic intent classifier (`classify_intent`, `matched_chain_rule`, `normalize_for_routing`) based purely on general Arabic hadith-sciences linguistic cues (committed prior to computing any routing evaluation metric; `holdout_draft.jsonl` untouched).
- **Composition (`src/pipeline.py`, `src/answer.py`)**: Extended `MUSNAD_AGENT` modes to `auto|on|off` (keeping `DEFAULT_AGENT_MODE="off"` until routing evaluation + 3+3 live smoke check pass). In `auto`, `chain` queries dispatch to unchanged `src/agent.py`, and `text` queries dispatch to unchanged single-turn RAG + Phase A `attach_sanad()`.
- **Verification (`tests/test_router.py`)**: `4 passed, 23 subtests passed`; full pytest `313 passed, 58 subtests passed`; CI marker pytest `287 passed, 26 deselected`; `check_docs` green (`0` API calls).

### Gate 1 Resolution Step 3 — Zero-API Routing Evaluation & ⛔ STOP (`src/evaluate_router.py`, `EXPERIMENTS.md` §33)
- **Evaluated committed router (`ea9c282`) with `0` API calls (`data/processed/router_eval_results.json`)**:
  - `golden.jsonl` (`n=33`): `32/33` (`97.0%`; `chain 2/3` `66.7%`, `text 30/30` `100.0%`; misrouted `golden_033` `chain→text`)
  - `synthetic_eval.jsonl` (`n=224`): `223/224` (`99.6%`; `text 223/224`; misrouted `synthetic_eval_134` `text→chain`)
  - `chain_eval_dev.jsonl` (`n=15`): `15/15` (`100.0%`; `chain 15/15`)
  - `chain_eval_test.jsonl` (`n=25`, frozen): `22/25` (`88.0%`; `chain 22/25`; misrouted `chain_comp_04`, `chain_count_06`, `chain_topic_05`)
  - Pooled (`n=297`): `292/297` (`98.3%`; `TP=39, FN=4, TN=253, FP=1`).
- **⛔ STOP TRIGGERED**: Stopped immediately without modifying `src/router.py` on the test split, without running the 3+3 live smoke test, and keeping `DEFAULT_AGENT_MODE = "off"`.

## Next Step (Blocked at ⛔ Router Gate)
- Waiting for user decision on how to handle the `chain_eval_test` / `golden` / `synthetic_eval` misroutes (e.g., fix general Arabic regex bugs in `src/router.py` without looking at further test items / evaluate vs switch to 1-shot Flash router / re-run Gate decision) before enabling `auto`, doing Phase D2, and preparing Phase E (`docs/holdout_review.md`).
