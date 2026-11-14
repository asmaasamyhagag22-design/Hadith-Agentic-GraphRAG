# مُسنَد · Musnad

**Grounded Arabic question answering over Sahih Muslim, backed by a deterministic transmission-chain (sanad) graph.**

> «مُسنَد» بيجاوب على أسئلة من صحيح مسلم برقم الحديث ونص المتن، وبيرفض لما الإجابة مش موجودة في المصدر، وبيقدر يعرض سلسلة رواة الحديث اللي رجع.

[![Tests](https://github.com/asmaasamyhagag22-design/Hadith-Agentic-GraphRAG/actions/workflows/tests.yml/badge.svg)](https://github.com/asmaasamyhagag22-design/Hadith-Agentic-GraphRAG/actions/workflows/tests.yml)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)

---

## Demo

Real output of `uv run python -m src.answer` on one answerable golden question and one golden refusal question:

```text
================================================================================
ما جزاء من صام رمضان إيماناً واحتساباً؟

Answer:
جزاء من صام رمضان إيماناً واحتساباً أن يُغفر له ما تقدم من ذنبه.
(المصدر: صحيح مسلم، حديث رقم 8950)

Retrieved Hadiths:
Rank: 1 | Hadith ID: 8950 | Chapter: كتاب صلاة المسافرين وقصرها | rerank score: 0.7367
Rank: 2 | Hadith ID: 8948 | Chapter: كتاب صلاة المسافرين وقصرها | rerank score: -2.4623
Rank: 3 | Hadith ID: 8949 | Chapter: كتاب صلاة المسافرين وقصرها | rerank score: -3.5978
Rank: 4 | Hadith ID: 9823 | Chapter: كتاب الصيام | rerank score: -4.1154
Rank: 5 | Hadith ID: 9769 | Chapter: كتاب الصيام | rerank score: -4.6486
================================================================================
ما هو فضل قراءة سورة الكهف يوم الجمعة؟

Answer:
المصادر المتاحة لا تجيب عن هذا السؤال

Retrieved Hadiths:
Rank: 1 | Hadith ID: 9195 | Chapter: كتاب الجمعة | rerank score: -2.8054
Rank: 2 | Hadith ID: 9181 | Chapter: كتاب الجمعة | rerank score: -2.9952
Rank: 3 | Hadith ID: 9200 | Chapter: كتاب الجمعة | rerank score: -3.0003
Rank: 4 | Hadith ID: 9163 | Chapter: كتاب الجمعة | rerank score: -3.1959
Rank: 5 | Hadith ID: 9146 | Chapter: كتاب الجمعة | rerank score: -3.6841
```

---

## Architecture

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/musnad-architecture-dark.png">
  <img alt="Musnad system architecture" src="docs/assets/musnad-architecture-light.png">
</picture>

### Request lifecycle

1. **Query normalisation** — Strip Arabic diacritics (`strip_diacritics`, prefixed with `"query: "`) for dense encoding, and normalise Alef/Ya/Ta-Marbuta forms with `ال`-prefix stripping (`_MIN_STEM_LENGTH = 4`) for lexical tokenisation (`src/utils.py`, `src/lexical.py`).
2. **Dense matn retrieval** — Encode the query with `intfloat/multilingual-e5-base` and search a FAISS `IndexFlatIP` index over 7,110 matn-only chunks (`vectors_matn.npy`; 460 reference-only follow-ups excluded from 7,570 total chunks), returning the top `candidates = 50` (`src/retrieve.py`).
3. **Lexical matn retrieval** — Score the same 7,110 matn chunks with Okapi BM25 (`BM25Index`) and return the top `candidates = 50` (`src/lexical.py`).
4. **Reciprocal Rank Fusion** — Merge the dense and BM25 rank lists (`HybridRetriever`) using `rrf_k = 60` and equal weights (`1.0 : 1.0`) (`src/retrieve.py`).
5. **Cross-encoder reranking** — Re-score the top `top_k_in = 10` fused candidates against the query with `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (`max_length = 512`) over diacritic-stripped matn and select the top `k = 5` (`src/rerank.py`, assembled in `src/pipeline.py`).
6. **Context assembly and generation** — Format the `k = 5` chunks with vocalised matn, `hadith_id`, and `chapter_arabic` (`format_context`), then call `gemini-2.5-pro` via Vertex AI at `temperature = 0` (`src/answer.py`).
7. **Citation validation and single retry** — `validate_answer` checks that the reply is either a valid refusal (`REFUSAL` with at most one trailing `.`, `؟`, or `!`) or contains at least one strict citation (`حديث رقم XXXX`) with every strict and loose hadith number inside the retrieved `context_ids`. On `MISSING_CITATION`, `OUT_OF_CONTEXT_CITATION`, or `MIXED_REFUSAL`, regenerate once with `CORRECTIONS[status]`; if the retry is still invalid, return `REFUSAL`.
8. **Sanad graph lookup (read-only API)** — Any retrieved chunk or `hadith_id` can be passed to `context_for_retrieval_result` / `context_for_local_hadith` (`src/sanad_context.py`) to resolve its recorded isnads in `sanad_graph.sqlite` through the frozen 1:1 linkage.

---

## Results

**Shipped pipeline (`Hybrid + rerank`):** **56%** `hit@1`, **81%** `hit@5`, **85%** `hit@10`, and **0.665** MRR on the hand-verified golden set (`n = 27`); **27%** `hit@1`, **41%** `hit@5`, and **0.330** MRR on the 224-query development set; **81%** correct citation (`22/27`), **0%** invalid out-of-context citation attempts (`0/30`), **0%** false refusals (`0/22`), and **3/3** correct refusals end to end.

`golden.jsonl` (33 hand-written, corpus-verified questions) is used for reporting, whereas `synthetic_eval.jsonl` (224 generated known-item queries) is used strictly for configuration selection; full methodology, per-metric denominators, and all negative results are in [`EXPERIMENTS.md`](EXPERIMENTS.md).

**Retrieval, hand-verified set (n = 27)**

| Pipeline | hit@1 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|
| **Hybrid + rerank** | **56%** | **81%** | 85% | **0.665** |
| Hybrid (RRF) | 44% | 74% | 85% | 0.565 |
| Dense only | 41% | 59% | 63% | 0.493 |
| BM25 only | 33% | 63% | 67% | 0.464 |

**Retrieval, development set (n = 224)**

| Pipeline | hit@1 | hit@5 | MRR |
|---|---|---|---|
| **Hybrid + rerank** | **27%** | **41%** | **0.330** |
| Hybrid (RRF) | 18% | 37% | 0.256 |
| Dense only | 14% | 26% | 0.189 |

**Answer quality (27 answerable + 3 unanswerable questions)**

| Metric | Hybrid | **Hybrid + rerank** |
|---|---|---|
| Correct citation | 63% | **81%** |
| Invalid citation attempts (measured before filtering) | 0% | **0%** |
| Missing citation attempts (raw output) | 0% | **0%** |
| Cited a non-gold hadith from the context | 23% | **10%** |
| False refusals | 0% | **0%** |
| Correct refusals | 3/3 | **3/3** |

Improving retrieval translated directly into better answers: reranking brought the gold hadith into the top-5 context for two additional questions (`20` → `22` of `27`) and raised correct citation from 63% to 81% while reducing non-gold in-context citations from 23% to 10%. Citation enforcement blocks citations outside the retrieved evidence; it does not by itself catch a wrong hadith chosen from within it.

---

## Engineering decisions

| Decision | Alternative considered | Evidence |
|---|---|---|
| Matn-only representation in the index | Full chunk (`sanad + matn`) or `chapter + matn` | Removing isnad noise raised golden MRR from `0.316` to `0.493` (`hit@1` `22%` → `41%`); prefixing chapter titles pulled adjacent hadiths from the same chapter and lowered golden MRR to `0.436` ([EXPERIMENTS §1](EXPERIMENTS.md#1-صيغة-تمثيل-الوثيقة)) |
| Strip diacritics in the index, keep vocalised text for display | Indexing vocalised Arabic text directly | Vocalised Arabic inflated `multilingual-e5-base` token counts `3.59×` (92,305 vs 25,676) and fragmented words into characters; stripping raised MRR from `0.368` to `0.429` and reduced chunks from 10,046 to 7,570 ([EXPERIMENTS §2](EXPERIMENTS.md#2-التشكيل)) |
| Reciprocal Rank Fusion on ranks (`rrf_k = 60`, `1.0 : 1.0`) | Raw score combination or tuned RRF weights / pool sizes | Cosine and BM25 scores sit on incompatible scales; rank fusion raised golden `hit@5` from `59%` (dense) and `63%` (BM25) to `74%` (`0.565` MRR), while sweeping candidate pools (25–200) and weights on 224 dev queries showed no gain over defaults ([EXPERIMENTS §5](EXPERIMENTS.md#5-البحث-الهجين), [§7](EXPERIMENTS.md#7-ضبط-بارامترات-الدمج--نتيجة-سلبية)) |
| Rerank depth `top_k_in = 10` | Reranking top 20 or top 50 fused candidates | Across `top_k_in` ∈ {10, 20, 50}, `hit@1` stayed unchanged at `15/27` (`56%`) while `hit@5` dropped from `22/27` (`81%`) at depth 10 to `21/27` at depth 20 and `20/27` at depth 50 ([EXPERIMENTS §6](EXPERIMENTS.md#6-إعادة-الترتيب-reranker), [§20.D](EXPERIMENTS.md#d--the-reranker-depth-claim-was-wrong)) |
| `mmarco-mMiniLMv2-L12` (33M) over `bge-reranker-v2-m3` (568M) | Shipping the 17× larger `bge-reranker-v2-m3` | Paired McNemar test found an exact 11–11 tie on `hit@1` across 224 dev queries (`p = 1.000`) and no significant difference on golden (`p = 0.250`), at `0.51`–`0.58` s/query vs `3.0`–`6.2` s/query on CPU ([EXPERIMENTS §6](EXPERIMENTS.md#اختيار-الموديل--اختبار-mcnemar-المزدوج)) |
| Deterministic citation enforcement in code | Relying on system-prompt instructions alone | `validate_answer` catches missing citations, strict or loose out-of-context numbers, and mixed refusals, triggering one targeted regeneration before refusing (`0%` invalid citation attempts, `1/30` mixed-refusal loophole caught and repaired) ([EXPERIMENTS §9](EXPERIMENTS.md#9-جودة-الإجابة), [§21](EXPERIMENTS.md#21-إغلاق-ثغرة-التحقق-من-الاستشهاد-وإعادة-القياس)) |
| CRAG self-correction disabled by default | LLM context grading + query rewrite before generation | Enabling CRAG left correct citation unchanged at `81%` (`22/27`) while tripling LLM calls from 1 to 3 per question ([EXPERIMENTS §9](EXPERIMENTS.md#هل-تحسين-الاسترجاع-يتحوّل-لإجابات-أصح)) |
| Deterministic refusal over web/parametric fallback | Answering from model weights or external search when context lacks the answer | Returning `REFUSAL` achieved `3/3` on unanswerable refusal tests and `0%` false refusals when the gold hadith was in context ([EXPERIMENTS §9](EXPERIMENTS.md#9-جودة-الإجابة), [§21](EXPERIMENTS.md#21-إغلاق-ثغرة-التحقق-من-الاستشهاد-وإعادة-القياس)) |

---

## Sanad graph

Built deterministically from the frozen MIS workbooks and accepted linkage artifact into SQLite (`data/processed/sanad_graph.sqlite`, rebuild time `9.0` s, `13.8` MB) via `src/build_sanad_graph.py`.

| Graph entity / metric | Count | Notes |
|---|---:|---|
| MIS narrators (`mis_narrator`) | 2,092 | Collision-free MIS narrator IDs with Arabic/English mapped names and generation |
| MIS hadiths (`mis_hadith`) | 7,748 | `0` mismatches between declared `SanadCount` and stored isnads |
| Ordered isnads (`isnad`) | 14,155 | Rebuilt step-by-step against source: `14,155` exact, `0` mismatched |
| Directed transmissions (`transmission`) | 63,642 | `from_narrator_id → to_narrator_id` with contiguous position check constraints |
| Local corpus hadiths (`local_hadith`) | 7,459 | Keyed by `local_id` (7,278–14,736) and `id_in_book` (1–7,459) |
| Verified 1:1 links (`hadith_mis_link`) | 7,015 | `94.05%` of local corpus (`7,004` narrow-normalised exact unique + `11` unique with bounded deterministic deltas; `444` unlinked local hadiths explicitly reported) |

Query the recorded chains for any local `hadith_id` or retrieval chunk through the read-only composition surface in `src/sanad_context.py` (`0.816` ms median latency):

```python
from src.sanad_context import open_graph, context_for_local_hadith, context_for_retrieval_result

with open_graph() as conn:
    ctx = context_for_local_hadith(conn, 8950)
    print(ctx["status"], ctx["isnad_count"])
    for narrator in ctx["isnads"][0]["narrators"]:
        print(narrator["chain_position"], narrator["name_ar_mapped"], narrator["generation"])
```

Classical narrator gradings (*al-jarḥ wa-l-taʿdīl*) and biographical records from Itqan are intentionally excluded from the database and gated on specialist-validated historical narrator identity resolution ([`SANAD_GRAPH_READINESS.md`](SANAD_GRAPH_READINESS.md), [`EXPERIMENTS.md` §17–19](EXPERIMENTS.md#17-mis-sanad-chain-graph-milestone-1)).

---

## Evaluation & reproducibility

Every evaluation dataset and graph build is pinned by a canonical SHA-256 digest in [`EXPERIMENTS.md`](EXPERIMENTS.md):

| Artifact | Records | Scored | Canonical SHA-256 |
|---|---:|---:|---|
| `data/raw/golden.jsonl` | 33 (27 matn · 3 refusal · 3 narrator) | 27 retrieval / 30 answer | `a7ec05f48ec0491a` |
| `data/raw/synthetic_eval.jsonl` | 224 | 224 | `4bec52d5a56a8fc8` |
| `data/raw/muslim.json` | 7,459 hadiths | — | `63a99e46155dc6e9` |
| `data/processed/mis_linkage_accepted_v1.jsonl` | 7,015 accepted 1:1 links | — | `9c3a48e7a0af4f0df1cd9250f49a90f343228b614587196fcf2fa6fbfa572c77` |
| `sanad_graph.sqlite` (MIS chain layer) | 2,092 narrators · 14,155 isnads · 63,642 edges | — | `496ccf1da21d2e849a94fb2d2e0d4ae66e3bfa549f4ce555f5cf2f4d490bfbce` |
| `sanad_graph.sqlite` (full graph with local link layer) | + 7,459 local hadiths · 7,015 links | — | `c8818da00bf27f74750105ed6bf2d57e674c26e3dfe63b9ec8774c6a4d6e481c` |

Re-run the quality gates and evaluations:

```bash
# 1. Documentation & dataset hash gate (checks all 37 table cells, denominators, prose figures, and SHA-256 hashes)
uv run python -m src.check_docs

# 2. Automated test suite (full suite with local data, or CI clean-checkout subset)
uv run pytest
uv run pytest -m "not requires_data and not requires_model and not requires_api"

# 3. Ground-truth verification gate on golden.jsonl
uv run python -m src.validate_golden

# 4. Retrieval evaluation (golden and synthetic sets, with cross-encoder reranking)
uv run python -m src.evaluate golden cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
uv run python -m src.evaluate synthetic cross-encoder/mmarco-mMiniLMv2-L12-H384-v1

# 5. End-to-end answer evaluation (calls Gemini 2.5 Pro via Vertex AI; consumes quota)
uv run python -m src.answer_eval
```

---

## Quickstart

```bash
uv sync
```

Configure Vertex AI Application Default Credentials in `.env`:

```ini
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

If `data/processed/` is not yet built on your machine, build the chunk store, dense variant indexes, and SQLite sanad graph once:

```bash
uv run python -m src.ingest && uv run python -m src.experiment_variants
uv run python -m src.build_sanad_graph
```

Run the verification gates, retrieval evaluation, smoke test, and CLI question answering:

```bash
uv run python -m src.validate_golden
uv run python -m src.evaluate golden cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
uv run python -m src.smoke_test
uv run python -m src.answer
uv run python -m src.check_docs
uv run pytest
```

---

## Project structure

```text
.github/workflows/
└── tests.yml                  # CI: uv sync, pytest (clean-checkout markers), check_docs
docs/assets/
├── musnad-architecture-light.png
└── musnad-architecture-dark.png
src/
├── config.py                  # project-root-relative paths for raw and processed artifacts
├── ingest.py, utils.py        # corpus chunking, Arabic normalisation, isnad/matn split
├── embed.py, lexical.py       # e5 dense embeddings, Arabic BM25, Reciprocal Rank Fusion
├── retrieve.py, rerank.py     # Retriever, HybridRetriever, and CrossEncoder RerankingRetriever
├── pipeline.py                # single canonical retrieval+rerank pipeline (build_pipeline)
├── answer.py                  # Gemini 2.5 Pro generation, citation validator, single retry, CLI
├── evaluate.py, answer_eval.py, validate_golden.py, smoke_test.py
├── build_sanad_graph.py, sanad_graph.py, sanad_context.py
├── check_docs.py              # verifies README tables, prose figures, and dataset hashes against EXPERIMENTS.md
└── experiment_*.py, audit_*.py, build_*.py, calibrate_*.py
tests/                         # unit, graph-fidelity, linkage, pipeline, and docs-integrity tests
EXPERIMENTS.md                 # canonical metrics registry, experiment logs, and dataset hashes
SANAD_GRAPH_READINESS.md       # linkage and narrator-identity readiness audit
```

---

## Roadmap

- **Query router and sanad path** — Deterministic/agentic router dispatching text questions to `src/pipeline.py` and transmission-chain questions ("who narrated this hadith?") to `src/sanad_context.py`.
- **Claim-level verification** — Structured output binding each sentence to a specific `hadith_id` and supporting span in the retrieved matn to eliminate wrong in-context citations.
- **Blind held-out test set** — A separate human-verified evaluation set untouched during prompt and retrieval iteration.
- **HTTP API and request tracing** — FastAPI endpoint exposing answer, retrieved chunks, validation status, and sanad context with per-stage latency telemetry.

---

## Scope and limitations

- **Sahih Muslim only** — The corpus covers the 7,459 hadiths of Sahih Muslim (`muslim.json`); hadiths recorded only in other collections (e.g., Sahih al-Bukhari) are out of scope and refused.
- **Research aid, not a fatwa authority** — Musnad surfaces recorded texts with their hadith numbers and transmission chains for verification; it does not issue religious rulings.
- **In-context wrong citations are not caught by regex validation** — `validate_answer` guarantees cited hadith numbers come from the retrieved context (`0%` out-of-context citations), but the generator still cites a non-gold hadith from within the retrieved top-5 context on `10%` of evaluated questions (`3/30`).
- **Narrator gradings are not linked yet** — `sanad_graph.sqlite` records MIS narrator identities and transmission chains for `7,015` linked hadiths (`444` local hadiths remain unlinked); classical critic gradings (*al-jarḥ wa-l-taʿdīl*) remain gated until historical narrator entity resolution is validated.
