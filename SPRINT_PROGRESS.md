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

### Phase B — Chain-question evaluation set & deterministic scorer (`807db8a`)
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

## Next Step
- **Phase C — Agent with tool calling (`C1`–`C5`)**:
  - **C1 (`src/agent.py`)**: `gemini-4-argon` with `search_hadith(query)` (default pipeline top-5: ids + matn + chapter) and `get_isnad(hadith_id)` (`sanad_context`), max 3 tool calls per question, deterministic execution, timeouts, fallback to non-agent path on failure.
  - **C2**: Extend `validate_answer` (cited hadith ids ⊆ tool-returned ids) + deterministic narrator-name check (`find_disallowed_narrators` against `get_isnad` results); invalid → regenerate once → refuse; then run Phase A sanad attachment.
  - **C3**: `MUSNAD_AGENT=on|off` (default `off` initially) wired through one unified entry point for CLI (`src/answer.py:main`), `src/answer_eval.py`, and `src/smoke_test.py`.
  - **C4**: Mocked tests in `tests/test_agent.py`.
  - **C5**: Evaluate on `chain_eval_dev.jsonl` (`15`), then 3× golden text (agent ON vs OFF) + 1 final frozen `chain_eval_test.jsonl` (`25`, agent ON vs non-agent pipeline), record in `EXPERIMENTS.md`, check Gate 1 thresholds.
- **Then**: Gate 1 check → Phase D (if default ON) + Gate 2 → Phase E (`docs/holdout_review.md`) + Gate 3.
