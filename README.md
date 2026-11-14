# مُسنَد · Musnad

**Grounded Arabic question answering over Sahih Muslim, backed by a deterministic transmission-chain (sanad) graph.**

> «مُسنَد» بيجاوب على أسئلة من صحيح مسلم برقم الحديث ونص المتن، وبيرفض لما الإجابة مش موجودة في المصدر، وبيقدر يعرض سلسلة رواة الحديث اللي رجع.

[![Tests](https://github.com/asmaasamyhagag22-design/Hadith-Agentic-GraphRAG/actions/workflows/tests.yml/badge.svg)](https://github.com/asmaasamyhagag22-design/Hadith-Agentic-GraphRAG/actions/workflows/tests.yml)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)

---

## Demo

Real output of the default `upgraded` pipeline (`uv run python -m src.answer`) on one answerable golden question and one golden refusal question:

```text
================================================================================
ما جزاء من صام رمضان إيماناً واحتساباً؟

Answer:
جزاء من صام رمضان إيماناً واحتساباً هو أن يُغفر له ما تقدم من ذنبه.
(المصدر: صحيح مسلم، حديث رقم 8950)

Retrieved Hadiths:
Rank: 1 | Hadith ID: 8950 | Chapter: كتاب صلاة المسافرين وقصرها
Rank: 2 | Hadith ID: 8948 | Chapter: كتاب صلاة المسافرين وقصرها
Rank: 3 | Hadith ID: 8951 | Chapter: كتاب صلاة المسافرين وقصرها
Rank: 4 | Hadith ID: 9868 | Chapter: كتاب الصيام
Rank: 5 | Hadith ID: 9919 | Chapter: كتاب الصيام
================================================================================
ما هو فضل قراءة سورة الكهف يوم الجمعة؟

Answer:
المصادر المتاحة لا تجيب عن هذا السؤال

Retrieved Hadiths:
Rank: 1 | Hadith ID: 9052 | Chapter: كتاب صلاة المسافرين وقصرها
Rank: 2 | Hadith ID: 9195 | Chapter: كتاب الجمعة
Rank: 3 | Hadith ID: 9181 | Chapter: كتاب الجمعة
Rank: 4 | Hadith ID: 9200 | Chapter: كتاب الجمعة
Rank: 5 | Hadith ID: 9199 | Chapter: كتاب الجمعة
```

---

## Architecture

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/musnad-architecture-dark.png">
  <img alt="Musnad system architecture" src="docs/assets/musnad-architecture-light.png">
</picture>

> *Note: The static diagram above illustrates the local offline baseline (`MUSNAD_RETRIEVAL_PIPELINE=legacy`). In the default `upgraded` mode (`src/pipeline.py`), retrieval replaces `multilingual-e5-base` and cross-encoder reranking with `gemini-3.8-flash` HyDE + `gemini-embedding-001` (`3072d`) + 4-way weighted RRF (`8 : 2 : 1 : 1`), falling back automatically to `legacy` if an API call fails or times out.*

### Request lifecycle

1. **Query normalisation and HyDE blending (default `upgraded` mode)** — Strip Arabic diacritics (`strip_diacritics`), generate a short hypothetical Sahih Muslim *matn* with `gemini-3.8-flash` (`location="global"`, `thinking_level="LOW"`, `temperature=0`), embed both query and HyDE text with `gemini-embedding-001` (`3072d`, `RETRIEVAL_QUERY`), and blend `0.7 * q + 0.3 * HyDE_q` (`src/retrieve.py`).
2. **4-way dense + BM25 retrieval over matn and expansions** — Search `gemini-embedding-001` (`3072d`, `RETRIEVAL_DOCUMENT`) dot-product indexes and Okapi BM25 (`BM25Index`) over 7,110 diacritic-stripped matn chunks (`460` reference-only follow-ups excluded from `7,570` total chunks) and their `gemini-3.8-flash` document expansions, taking the top `candidates = 50` from each signal (`src/retrieve.py`, `src/lexical.py`).
3. **Weighted Reciprocal Rank Fusion** — Merge the four rank lists (`Dense_matn_HyDE : Dense_exp_HyDE : BM25_matn : BM25_exp`) with `rrf_k = 60` and dev-tuned weights `8 : 2 : 1 : 1`, without cross-encoder reranking (`src/retrieve.py`, `src/pipeline.py`).
4. **Offline baseline and automatic fallback (`legacy`)** — Setting `MUSNAD_RETRIEVAL_PIPELINE=legacy` (or an automatic fallback triggered if the HyDE/embedding Vertex AI call fails or times out past `MUSNAD_API_TIMEOUT_MS`) runs `intfloat/multilingual-e5-base` (`FAISS IndexFlatIP`) + `BM25Index` (equal `1.0 : 1.0` RRF) followed by `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` over `top_k_in = 10` candidates (`src/rerank.py`).
5. **Context assembly and generation** — Format the top `k = 5` chunks with vocalised matn, `hadith_id`, and `chapter_arabic` (`format_context`), then call `gemini-2.5-pro` via Vertex AI at `temperature = 0` (`src/answer.py`).
6. **Citation validation and single retry** — `validate_answer` checks that the reply is either a valid refusal (`REFUSAL` with at most one trailing `.`, `؟`, or `!`) or contains at least one strict citation (`حديث رقم XXXX`) with every strict and loose hadith number inside the retrieved `context_ids`. On `MISSING_CITATION`, `OUT_OF_CONTEXT_CITATION`, or `MIXED_REFUSAL`, regenerate once with `CORRECTIONS[status]`; if the retry is still invalid, return `REFUSAL`.
7. **Sanad graph lookup (read-only API)** — Any retrieved chunk or `hadith_id` can be passed to `context_for_retrieval_result` / `context_for_local_hadith` (`src/sanad_context.py`) to resolve its recorded isnads in `sanad_graph.sqlite` through the frozen 1:1 linkage.

---

## Results

**Default pipeline (`Upgraded`: HyDE + Gemini-001 + RRF):** **85%** `hit@1`, **100%** `hit@5`, **100%** `hit@10`, and **0.926** MRR on the hand-verified golden set (`n = 27`); **38%** `hit@1`, **74%** `hit@5`, **85%** `hit@10`, and **0.528** MRR on the 224-query development set; **96%** correct citation (`26.0/27` 3-run mean), **0%** invalid out-of-context citation attempts (`0/30`), **0%** false refusals (`0/27`), and **2/3** correct refusals end to end.

`golden.jsonl` (33 hand-written, corpus-verified questions) is used for reporting, whereas `synthetic_eval.jsonl` (224 generated known-item queries) is used strictly for configuration selection; `Hybrid + rerank` and earlier `e5-base` / `BM25` rows serve as local offline baselines (`MUSNAD_RETRIEVAL_PIPELINE=legacy`). Full methodology, per-metric denominators, and all negative results are in [`EXPERIMENTS.md`](EXPERIMENTS.md).

**Retrieval, hand-verified set (n = 27)**

| Pipeline | hit@1 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|
| **Upgraded (HyDE + Gemini-001 + RRF)** | **85%** | **100%** | **100%** | **0.926** |
| Hybrid + rerank | 56% | 81% | 85% | 0.665 |
| Hybrid (RRF) | 44% | 74% | 85% | 0.565 |
| Dense only | 41% | 59% | 63% | 0.493 |
| BM25 only | 33% | 63% | 67% | 0.464 |

Configuration tuned on the dev set; held-out evaluation in progress.

**Retrieval, development set (n = 224)**

| Pipeline | hit@1 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|
| **Upgraded (HyDE + Gemini-001 + RRF)** | **38%** | **74%** | **85%** | **0.528** |
| Hybrid + rerank (baseline) | 27% | 41% | 44% | 0.330 |
| Hybrid (RRF) | 18% | 37% | 44% | 0.256 |
| Dense only | 14% | 26% | 32% | 0.189 |

**Answer quality (27 answerable + 3 unanswerable questions)**

| Metric | **Upgraded (3-run mean)** | Hybrid + rerank (baseline) | Hybrid |
|---|---|---|---|
| Correct citation | **96%** | 81% | 63% |
| Invalid citation attempts (measured before filtering) | **0%** | 0% | 0% |
| Missing citation attempts (raw output) | **0%** | 0% | 0% |
| Cited a non-gold hadith from the context | **7%** | 10% | 23% |
| False refusals | **0%** | 0% | 0% |
| Correct refusals | **2/3** | 3/3 | 3/3 |

Improving retrieval translated directly into better answers: upgrading retrieval brought the gold hadith into the top-5 context for all `27/27` answerable questions (`22` → `27` over the `Hybrid + rerank` baseline, which itself gained `2` over `Hybrid`'s `20`), raising correct citation from `63%` (`Hybrid`) and `81%` (`Hybrid + rerank`) to `96%` while reducing non-gold in-context citations from `23%` and `10%` to `7%` (for the third unanswerable question on Surat al-Kahf on Friday, upgraded retrieval surfaces Sahih Muslim hadith `#9842` on the first ten verses of al-Kahf, so the model cites `#9842` to clarify scope rather than emitting the bare refusal string). Citation enforcement blocks citations outside the retrieved evidence; it does not by itself catch a wrong hadith chosen from within it.

---

## Engineering decisions

| Decision | Alternative considered | Evidence |
|---|---|---|
| `gemini-embedding-001` (`3072d`) + HyDE query blending (`0.7*q + 0.3*HyDE_q`) | Keeping `intfloat/multilingual-e5-base` (`768d`), `BAAI/bge-m3`, or `Qwen3-Embedding-0.6B` | The embedding model was the primary bottleneck: switching dense `matn` to `gemini-embedding-001` alone raised dev `hit@10` from `31.7%` to `80.8%` (`recall@50` `43.8%` → `93.8%`, `MRR` `0.189` → `0.556`) and golden `hit@10` from `63.0%` to `92.6%` (`MRR` `0.493` → `0.790`); adding `gemini-3.8-flash` HyDE reached `85.3%` dev `hit@10` and `100.0%` golden `hit@5`/`hit@10` (`MRR` `0.926`) ([EXPERIMENTS §23](EXPERIMENTS.md#23-التجربة-e1--مقارنة-نماذج-التضمين-الكثيف-والهجين-dense--densesparse), [§28](EXPERIMENTS.md#28-التجربة-step-4--إعادة-تشغيل-e2-وe4-بأحدث-نموذج-flash-متاح-gemini-38-flash-وفحص-النماذج-غير-gemini)) |
| Minimal doc expansion weight (`8 : 2 : 1 : 1` RRF) | Dropping expansion (`8 : 0 : 1 : 0`) or equal `1 : 1 : 1 : 1` RRF | Keeping `gemini-3.8-flash` document expansions (`$2.48` one-time cost) at small weight `2` vs `8` matn added ~`0.9` pp on dev `hit@10` (`84.4%` → `85.3%`, with dev `hit@1` `39.7%` → `37.5%`) and raised golden `hit@1` from `81.5%` to `85.2%` (`MRR` `0.901` → `0.926`), while dropping expansions (`8 : 0 : 1 : 0`) already keeps `84.4%` dev `hit@10` and `100.0%` golden `hit@5`/`hit@10` ([EXPERIMENTS §24](EXPERIMENTS.md#24-التجربة-e2--توسيع-الوثائق-بالأسئلة-والكلمات-المفتاحية-المعاصرة-document-expansion), [§28](EXPERIMENTS.md#28-التجربة-step-4--إعادة-تشغيل-e2-وe4-بأحدث-نموذج-flash-متاح-gemini-38-flash-وفحص-النماذج-غير-gemini), [§29](EXPERIMENTS.md#29-التجربة-الخامسة-e5--خط-أنابيب-الاسترجاع-النهائي-تعريف-المقاييس-جدول-الاستئصال-ablation-شبكة-ضبط-أوزان-rrf-وتقييم-الإجابات-answer_eval)) |
| Cross-encoder removed in upgraded mode | Keeping `mmarco-mMiniLMv2`, `bge-reranker-v2-m3`, or `Qwen3-Reranker-0.6B` at depths 10/30/50 | Against stronger dense candidates, all three cross-encoders hurt dev `hit@10` at depths `30`/`50` (`79.9%` → `67.9%`–`75.4%`) and lowered golden `MRR` (`0.790` → `0.652`–`0.778` at depth 10); removing the reranker reaches `85.3%` dev `hit@10` and `100.0%` golden `hit@5`/`hit@10` with zero CPU reranking latency ([EXPERIMENTS §25](EXPERIMENTS.md#25-التجربة-e3--مقارنة-معيدات-الترتيب-cross-encoder-rerankers-وعمق-المرشحين-10--30--50), [§29](EXPERIMENTS.md#29-التجربة-الخامسة-e5--خط-أنابيب-الاسترجاع-النهائي-تعريف-المقاييس-جدول-الاستئصال-ablation-شبكة-ضبط-أوزان-rrf-وتقييم-الإجابات-answer_eval)) |
| Matn-only representation in the index | Full chunk (`sanad + matn`) or `chapter + matn` | Removing isnad noise raised golden MRR from `0.316` to `0.493` (`hit@1` `22%` → `41%`); prefixing chapter titles pulled adjacent hadiths from the same chapter and lowered golden MRR to `0.436` ([EXPERIMENTS §1](EXPERIMENTS.md#1-صيغة-تمثيل-الوثيقة)) |
| Strip diacritics in the index, keep vocalised text for display | Indexing vocalised Arabic text directly | Vocalised Arabic inflated `multilingual-e5-base` token counts `3.59×` (92,305 vs 25,676) and fragmented words into characters; stripping raised MRR from `0.368` to `0.429` and reduced chunks from 10,046 to 7,570 ([EXPERIMENTS §2](EXPERIMENTS.md#2-التشكيل)) |
| Reciprocal Rank Fusion on ranks (`rrf_k = 60`, `1.0 : 1.0`) | Raw score combination or tuned RRF weights / pool sizes | Cosine and BM25 scores sit on incompatible scales; rank fusion raised golden `hit@5` from `59%` (dense) and `63%` (BM25) to `74%` (`0.565` MRR), while sweeping candidate pools (25–200) and weights on 224 dev queries showed no gain over defaults ([EXPERIMENTS §5](EXPERIMENTS.md#5-البحث-الهجين), [§7](EXPERIMENTS.md#7-ضبط-بارامترات-الدمج--نتيجة-سلبية)) |
| Rerank depth `top_k_in = 10` | Reranking top 20 or top 50 fused candidates | Across `top_k_in` ∈ {10, 20, 50}, `hit@1` stayed unchanged at `15/27` (`56%`) while `hit@5` dropped from `22/27` (`81%`) at depth 10 to `21/27` at depth 20 and `20/27` at depth 50 ([EXPERIMENTS §6](EXPERIMENTS.md#6-إعادة-الترتيب-reranker), [§20.D](EXPERIMENTS.md#d--the-reranker-depth-claim-was-wrong)) |
| `mmarco-mMiniLMv2-L12` (33M) over `bge-reranker-v2-m3` (568M) | Shipping the 17× larger `bge-reranker-v2-m3` | Paired McNemar test found an exact 11–11 tie on `hit@1` across 224 dev queries (`p = 1.000`) and no significant difference on golden (`p = 0.250`), at `0.51`–`0.58` s/query vs `3.0`–`6.2` s/query on CPU ([EXPERIMENTS §6](EXPERIMENTS.md#اختيار-الموديل--اختبار-mcnemar-المزدوج)) |
| Deterministic citation enforcement in code | Relying on system-prompt instructions alone | `validate_answer` catches missing citations, strict or loose out-of-context numbers, and mixed refusals, triggering one targeted regeneration before refusing (`0%` invalid citation attempts) ([EXPERIMENTS §9](EXPERIMENTS.md#9-جودة-الإجابة), [§21](EXPERIMENTS.md#21-إغلاق-ثغرة-التحقق-من-الاستشهاد-وإعادة-القياس)) |
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

| Artifact | Records | Scored | SHA-256 (first 16 hex) |
|---|---:|---:|---|
| `data/raw/golden.jsonl` | 33 (27 matn · 3 refusal · 3 narrator) | 27 retrieval / 30 answer | `a7ec05f48ec0491a` |
| `data/raw/synthetic_eval.jsonl` | 224 | 224 | `4bec52d5a56a8fc8` |
| `data/raw/muslim.json` | 7,459 hadiths | — | `63a99e46155dc6e9` |
| `data/processed/mis_linkage_accepted_v1.jsonl` | 7,015 accepted 1:1 links | — | `9c3a48e7a0af4f0d` |
| `sanad_graph.sqlite` (MIS chain layer) | 2,092 narrators · 14,155 isnads · 63,642 edges | — | `496ccf1da21d2e84` |
| `sanad_graph.sqlite` (full graph with local link layer) | + 7,459 local hadiths · 7,015 links | — | `c8818da00bf27f74` |

Re-run the quality gates and evaluations:

```bash
# 1. Documentation & dataset hash gate (checks all 37 table cells, denominators, prose figures, and SHA-256 hashes)
uv run python -m src.check_docs

# 2. Automated test suite (full suite with local data, or CI clean-checkout subset)
uv run pytest
uv run pytest -m "not requires_data and not requires_model and not requires_api"

# 3. Ground-truth verification gate on golden.jsonl
uv run python -m src.validate_golden

# 4. Retrieval evaluation (default upgraded mode, or set MUSNAD_RETRIEVAL_PIPELINE=legacy)
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

Configure Vertex AI Application Default Credentials in `.env` (optional `MUSNAD_RETRIEVAL_PIPELINE=legacy` forces the offline local baseline; `upgraded` is the default and falls back to `legacy` automatically if an API call fails or times out):

```ini
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
# MUSNAD_RETRIEVAL_PIPELINE=upgraded  # default ("legacy" for offline baseline)
# MUSNAD_API_TIMEOUT_MS=15000         # API timeout before automatic fallback to legacy
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
├── retrieve.py, rerank.py     # Retriever, HybridRetriever, UpgradedRetriever (with legacy fallback), CrossEncoder RerankingRetriever
├── pipeline.py                # canonical pipeline factory (build_pipeline: upgraded default, legacy baseline)
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
