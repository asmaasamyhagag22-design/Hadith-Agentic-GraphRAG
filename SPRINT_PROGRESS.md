# Musnad Autonomous Sprint Progress

- **Branch**: `retrieval-upgrade` (never push to `main`)
- **Baseline commit**: `354c01a` (`docs: update README roadmap and document target architecture assets`)
- **Budget used**: `0 / 500` Pro-class calls, `0 / 800` Flash-class calls

## Completed Steps

### Phase A — Sanad-attached answers (`99d6d63`)
- **A1/A3 (`src/answer.py`)**:
  - After `validate_answer` returns `VALID_ANSWER`, `answer_with_details` calls `attach_sanad(ordered_cited_ids(answer), db_path=sanad_db_path)` using a single `open_graph()` connection per request (closed in `try/finally`).
  - Adds `"sanad": [{hadith_id, status, isnad_count, isnads: [[{chain_position, name_ar_mapped}]]}]` and `"sanad_error": None | str`. Refusals and invalid answers get `[]` and `None`. Preserves exact `sanad_context` statuses (`LINKED_WITH_RECORDED_ISNAD`, `LINKED_BUT_NO_RECORDED_ISNAD`, `VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK`, `INVALID_LOCAL_HADITH_ID`). Returns answers cleanly with `"sanad_error"` set if graph missing or query fails.
  - CLI (`src/answer.py:main`) prints `"السند (من قاعدة بيانات السند):"` via `format_sanad_section` / `format_sanad_chain`, first chain per cited hadith + `"(+N طرق أخرى)"` when `isnad_count > 1`, or plain Arabic status when no recorded chain exists. `_last_answer_details` (`threading.local()`) preserves `answer_question()`'s 2-tuple signature for backwards compatibility.
- **A2 (Chain direction verified)**:
  - `sanad_graph.py:get_ordered_chain` orders `chain_position` `1..N` (`from_narrator_id -> to_narrator_id` = Companion → Muslim's teacher). `"sanad"` stores recorded `1..N` order; CLI reverses descending (`chain_position` `N..1`) joined with `" ← "`.
- **A4 (`tests/test_sanad_attachment.py`)**:
  - 8 offline unit tests covering single/multiple citations (single DB connection + deduplication), unlinked hadith, linked hadith with no recorded isnad, refusals & retries, graph unavailable/failure, and chain order + CLI formatting.
- **A5 (`src/measure_sanad_attachment.py`, `EXPERIMENTS.md` Section 30 + `canonical-results`)**:
  - Measured on saved 3-run `data/processed/e5_simple_default_results.json` (`0` new LLM calls):
    - Citation-level attachment coverage: `211/220` (`95.9%`, exact `95.91%`; runs: `69/72`, `72/75`, `70/73`)
    - Unique cited hadith coverage: `74/76` (`97.4%`, exact `97.37%`; unlinked: `7358`, `7360`)
    - Median attachment latency: `2.226 ms` (`p95 = 3.444 ms`, range `0.983–4.125 ms`)
- **Verification**: Full pytest `291 passed`, CI marker pytest `265 passed, 26 deselected`, `check_docs` green.

## Next Step
- **Phase B — Chain-question evaluation set & deterministic evaluator**:
  - **B1/B2**: Query `sanad_graph.sqlite` and `data/raw/muslim.json` to select ~40 hadiths and build `data/raw/chain_eval.jsonl` (`who_narrated_companion`, `who_narrated_teacher`, `isnad_count`, `narrator_in_chain`, `topic_who_narrated`, including the 3 `narrator` items from `data/raw/golden.jsonl`, plus abstention cases), split stratified into `data/raw/chain_eval_dev.jsonl` (`15`) and `data/raw/chain_eval_test.jsonl` (`25`), freeze test split, record SHA-256 hashes in `EXPERIMENTS.md`.
  - **B3**: Implement `src/chain_eval.py` (deterministic scoring for routing, answer correctness, zero hallucinated narrator names, abstention) + offline tests (`tests/test_chain_eval.py`).
- **Then**: Phase C (`src/agent.py`, C2 validators, `MUSNAD_AGENT`, mocked tests, C5 dev/golden/test eval & Gate 1 check), Phase D (if default ON, Gate 2), Phase E (`docs/holdout_review.md`, Gate 3).
