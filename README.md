# مُسنَد · Musnad

**The upgraded default reached 100% hit@5 on 27 hand-verified questions and averaged 96% correct citations across three runs with `gemini-4-argon`.**

Grounded Arabic question answering over Sahih Muslim, backed by a deterministic transmission-chain (sanad) graph.

> «مُسنَد» بيجاوب على أسئلة من صحيح مسلم برقم الحديث ونص المتن، وبيرفض لما الإجابة مش موجودة في المصدر، وبيقدر يعرض سلسلة رواة الحديث اللي رجع.

[![Tests](https://github.com/asmaasamyhagag22-design/Hadith-Agentic-GraphRAG/actions/workflows/tests.yml/badge.svg)](https://github.com/asmaasamyhagag22-design/Hadith-Agentic-GraphRAG/actions/workflows/tests.yml)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)

---

## Demo

Output captured from `python -m src.answer` with the default `upgraded` pipeline on two golden questions from `data/raw/questions.txt`.

```text
================================================================================
ما جزاء من صام رمضان إيماناً واحتساباً؟

Answer:
جزاء من صام رمضان إيماناً واحتساباً أن يُغفر له ما تقدم من ذنبه، كما قال رسول الله صلى الله عليه وسلم: "مَنْ صَامَ رَمَضَانَ إِيمَانًا وَاحْتِسَابًا غُفِرَ لَهُ مَا تَقَدَّمَ مِنْ ذَنْبِهِ".

(المصدر: صحيح مسلم، حديث رقم 8950)

Retrieved Hadiths:
Rank: 1 | Hadith ID: 8950 | Chapter: كتاب صلاة المسافرين وقصرها
Rank: 2 | Hadith ID: 8948 | Chapter: كتاب صلاة المسافرين وقصرها
Rank: 3 | Hadith ID: 9867 | Chapter: كتاب الصيام
Rank: 4 | Hadith ID: 9868 | Chapter: كتاب الصيام
Rank: 5 | Hadith ID: 8949 | Chapter: كتاب صلاة المسافرين وقصرها
================================================================================
ما هو فضل قراءة سورة الكهف يوم الجمعة؟

Answer:
المصادر المتاحة لا تجيب عن هذا السؤال

Retrieved Hadiths:
Rank: 1 | Hadith ID: 9195 | Chapter: كتاب الجمعة
Rank: 2 | Hadith ID: 9052 | Chapter: كتاب صلاة المسافرين وقصرها
Rank: 3 | Hadith ID: 9181 | Chapter: كتاب الجمعة
Rank: 4 | Hadith ID: 9203 | Chapter: كتاب الجمعة
Rank: 5 | Hadith ID: 9200 | Chapter: كتاب الجمعة
```

---

## Architecture

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/musnad-architecture-dark.png">
  <img alt="Musnad system architecture" src="docs/assets/musnad-architecture-light.png">
</picture>

The steps below describe the current request path.

### Request lifecycle

1. **Query normalisation and HyDE blending (default `upgraded` mode)** — Strip Arabic diacritics (`strip_diacritics`), generate a short hypothetical Sahih Muslim *matn* with `gemini-3.8-flash` (`location="global"`, `thinking_level="LOW"`, `temperature=0`), embed both query and HyDE text with `gemini-embedding-001` (`3072d`, `RETRIEVAL_QUERY`), and blend `0.7 * q + 0.3 * HyDE_q` (`src/retrieve.py`).
2. **Dense matn retrieval (`1:0:0:0`)** — Search the `gemini-embedding-001` (`3072d`, `RETRIEVAL_DOCUMENT`) dot-product index over 7,110 diacritic-stripped matn chunks (`460` reference-only follow-ups excluded from `7,570` total chunks) directly by inner product (`src/retrieve.py`, `src/pipeline.py`). The default path uses no BM25, no document expansion fields, and no cross-encoder reranking.
3. **Automatic retrieval fallback** — A failed or timed-out HyDE or embedding request switches that query to `legacy` retrieval. The same path can be selected with `MUSNAD_RETRIEVAL_PIPELINE=legacy` and uses local dense search (`intfloat/multilingual-e5-base`), BM25, RRF fusion (`rrf_k = 60`), and a cross-encoder (`src/pipeline.py`, `src/rerank.py`).
4. **Context assembly and generation** — Format the top `k = 5` chunks with vocalised matn, `hadith_id`, and `chapter_arabic` (`format_context`), then call `gemini-4-argon` via Vertex AI (`location="global"`, `thinking_level="LOW"`, `temperature = 0`) (`src/answer.py`).
5. **Citation validation and single retry** — `validate_answer` checks that the reply is either a valid refusal (`REFUSAL` with at most one trailing `.`, `؟`, or `!`) or contains at least one strict citation (`حديث رقم XXXX`) with every strict and loose hadith number inside the retrieved `context_ids`. On `MISSING_CITATION`, `OUT_OF_CONTEXT_CITATION`, or `MIXED_REFUSAL`, regenerate once with `CORRECTIONS[status]`; if the retry is still invalid, return `REFUSAL`.
6. **Sanad graph lookup (read-only API)** — Any retrieved chunk or `hadith_id` can be passed to `context_for_retrieval_result` / `context_for_local_hadith` (`src/sanad_context.py`) to resolve its recorded isnads in `sanad_graph.sqlite` through the frozen 1:1 linkage.

---

## Results

**Upgraded retrieval reached 85% hit@1, 100% hit@5, 100% hit@10 and 0.926 MRR** on the 27 hand-verified answerable questions. With `gemini-4-argon`, it averaged **96.3% correct citations** (`78/81`), **0%** out-of-context citation attempts (`0/90`), **3.7%** false refusals (`3/81`), **3.3%** wrong in-context citations (`3/90`), and **6/9** (`66.7%`) correct refusals across three runs. On the 224-query development set, retrieval reached **41%** `hit@1`, **73%** `hit@5`, **84%** `hit@10` and **0.545** MRR.

On `n = 20` uncached queries (`k = 5`), end-to-end latency was `12.55 s` median (`17.97 s` p95) — with HyDE generation (`4.00 s` median out of `7.52 s` retrieval) dominating retrieval time — at `$0.0042` mean cost per query (`$0.00053` retrieval + `$0.00368` generation at introductory rates; `$0.0079` standard).

`golden.jsonl` contains 33 hand-written questions, including 27 answerable questions for retrieval and 3 refusal cases for answer evaluation. The development set (`synthetic_eval.jsonl`) contains 224 generated known-item queries used to select the configuration. Full methodology and denominators are in [`EXPERIMENTS.md`](EXPERIMENTS.md).

**Retrieval, hand-verified set (n = 27)**

| Pipeline | hit@1 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|
| **Upgraded (HyDE + Gemini-001)** | **85%** | **100%** | **100%** | **0.926** |
| Hybrid + rerank (baseline) | 56% | 81% | 85% | 0.665 |
| Hybrid (RRF) | 44% | 74% | 85% | 0.565 |
| Dense only | 41% | 59% | 63% | 0.493 |
| BM25 only | 33% | 63% | 67% | 0.464 |

Configuration tuned on the dev set; held-out evaluation in progress.

**Retrieval, development set (n = 224)**

| Pipeline | hit@1 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|
| **Upgraded (HyDE + Gemini-001)** | **41%** | **73%** | **84%** | **0.545** |
| Hybrid + rerank (baseline) | 27% | 41% | 44% | 0.330 |
| Hybrid (RRF) | 18% | 37% | 44% | 0.256 |
| Dense only | 14% | 26% | 32% | 0.189 |

**Answer quality (27 answerable + 3 unanswerable questions)**

| Pipeline | Correct citation | Invalid citation attempts (raw) | Missing citation attempts (raw) | Non-gold citation from context | False refusals | Correct refusals |
|---|---|---|---|---|---|---|
| **Upgraded (3-run mean)** | **96%** | **0%** | **0%** | **3.3%** | **4%** | **6/9** |
| Hybrid + rerank (baseline, 3-run mean) | 81% | 0% | 0% | 8% | 0% | 3/3 |
| Hybrid (RRF) | 63% | 0% | 0% | 23% | 0% | 3/3 |

With `gemini-4-argon` over `1:0:0:0`, wrong in-context citations were **3.3%** (`3/90`, vs **7%** with `gemini-2.5-pro`, **8%** on the legacy `Hybrid + rerank` baseline, and **23%** on `Hybrid (RRF)`). In all three runs, the generator cited a retrieved night-prayer hadith on the Taraweeh refusal test (`2/3` per run = `6/9`) and abstained on one answerable fasting question (`26/27` per run) even with the gold hadith at rank 2 in context. Citation validation blocks citations outside the retrieved evidence. A wrong hadith chosen from within it can pass validation.

---

## Engineering decisions

| Decision | Alternative considered | Evidence |
|---|---|---|
| `gemini-embedding-001` (`3072d`) + HyDE query blending (`0.7*q + 0.3*HyDE_q`) | Keeping `intfloat/multilingual-e5-base` (`768d`), `BAAI/bge-m3`, or `Qwen3-Embedding-0.6B` | The embedding model was the primary bottleneck: switching dense `matn` to `gemini-embedding-001` alone raised dev `hit@10` from `31.7%` to `80.8%` (`recall@50` `43.8%` → `93.8%`, `MRR` `0.189` → `0.556`) and golden `hit@10` from `63.0%` to `92.6%` (`MRR` `0.493` → `0.790`); adding `gemini-3.8-flash` HyDE (`1:0:0:0`) reached `83.9%` dev `hit@10` (`40.6%` `hit@1`, `0.545` `MRR`) and `100.0%` golden `hit@5`/`hit@10` (`0.926` `MRR`) ([EXPERIMENTS §23](EXPERIMENTS.md#23-التجربة-e1--مقارنة-نماذج-التضمين-الكثيف-والهجين-dense--densesparse), [§28](EXPERIMENTS.md#28-التجربة-step-4--إعادة-تشغيل-e2-وe4-بأحدث-نموذج-flash-متاح-gemini-38-flash-وفحص-النماذج-غير-gemini), [§29](EXPERIMENTS.md#29-التجربة-الخامسة-e5--خط-أنابيب-الاسترجاع-النهائي-تعريف-المقاييس-جدول-الاستئصال-ablation-شبكة-ضبط-أوزان-rrf-وتقييم-الإجابات-answer_eval)) |
| Dense `matn` + HyDE alone (`1:0:0:0`), dropping BM25 and expansion fields | 4-way RRF (`8:2:1:1`) with BM25 and `gemini-3.8-flash` doc expansions, or `8:0:1:0` | 4-way fusion (8:2:1:1) was not significantly better than dense + HyDE (McNemar p >= 0.39), so the simpler pipeline ships. Across 224 dev queries, `1:0:0:0` reached `83.9%` `hit@10` (`85.3%` for `8:2:1:1`, `p = 0.6072`) with higher `hit@1` (`40.6%` vs `37.5%`) and `MRR` (`0.545` vs `0.528`), matching `8:2:1:1` on `golden` (`100.0%` `hit@5`/`hit@10`, `0.926` `MRR`) without BM25 or expansion artifacts ([EXPERIMENTS §29](EXPERIMENTS.md#29-التجربة-الخامسة-e5--خط-أنابيب-الاسترجاع-النهائي-تعريف-المقاييس-جدول-الاستئصال-ablation-شبكة-ضبط-أوزان-rrf-وتقييم-الإجابات-answer_eval)) |
| Cross-encoder removed in upgraded mode | Keeping `mmarco-mMiniLMv2`, `bge-reranker-v2-m3`, or `Qwen3-Reranker-0.6B` at depths 10/30/50 | Against stronger dense candidates, all three cross-encoders hurt dev `hit@10` at depths `30`/`50` (`79.9%` → `67.9%`–`75.4%`) and lowered golden `MRR` (`0.790` → `0.652`–`0.778` at depth 10); removing the reranker reaches `83.9%` dev `hit@10` (`85.3%` with 4-way RRF) and `100.0%` golden `hit@5`/`hit@10` with zero CPU reranking latency ([EXPERIMENTS §25](EXPERIMENTS.md#25-التجربة-e3--مقارنة-معيدات-الترتيب-cross-encoder-rerankers-وعمق-المرشحين-10--30--50), [§29](EXPERIMENTS.md#29-التجربة-الخامسة-e5--خط-أنابيب-الاسترجاع-النهائي-تعريف-المقاييس-جدول-الاستئصال-ablation-شبكة-ضبط-أوزان-rrf-وتقييم-الإجابات-answer_eval)) |
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
# 1. Documentation & dataset hash gate
uv run python -m src.check_docs

# 2. Automated test suite (full suite with local data, or CI clean-checkout subset)
uv run pytest
uv run pytest -m "not requires_data and not requires_model and not requires_api"

# 3. Ground-truth verification gate on golden.jsonl
uv run python -m src.validate_golden

# 4. Retrieval evaluation (default upgraded mode, or set MUSNAD_RETRIEVAL_PIPELINE=legacy)
uv run python -m src.evaluate golden cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
uv run python -m src.evaluate synthetic cross-encoder/mmarco-mMiniLMv2-L12-H384-v1

# 5. End-to-end answer evaluation (calls Gemini 4 Argon via Vertex AI; consumes quota)
uv run python -m src.answer_eval
```

---

## Quickstart

```bash
uv sync
```

Configure Vertex AI Application Default Credentials and set these values in `.env`. Set `MUSNAD_RETRIEVAL_PIPELINE=legacy` for local retrieval. The answer generator still uses Vertex AI.

```ini
GOOGLE_GENAI_USE_VERTEXAI=True
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
# MUSNAD_RETRIEVAL_PIPELINE=upgraded  # default
```

Build the chunk store, local dense indexes and SQLite sanad graph if they are missing.

```bash
uv run python -m src.ingest && uv run python -m src.experiment_variants
uv run python -m src.build_sanad_graph
```

The default `1:0:0:0` retrieval mode only needs `vectors_matn_gemini001_3072.npy` in `data/processed/`. These embeddings are built using Vertex AI. Set `MUSNAD_API_TIMEOUT_MS` in the shell to change the retrieval API timeout from its default of 15,000 ms. [Matn embeddings](EXPERIMENTS.md#23-التجربة-e1--مقارنة-نماذج-التضمين-الكثيف-والهجين-dense--densesparse)

Run the verification gates, retrieval evaluation, smoke test and CLI question answering.

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
├── pipeline.py                # pipeline factory with upgraded retrieval as the default
├── answer.py                  # Gemini 4 Argon generation, citation validator, single retry, CLI
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

- **Sanad-attached answers** — Every cited hadith is returned with its transmission chain, pulled deterministically from the graph (never generated by the model).
- **Agent with tool calling** — `gemini-4-argon` chooses between `search_hadith` (text) and `get_isnad` (chain) tools, max 3 calls; the citation validator checks every cited id against ids returned by tools.
- **Chain-question evaluation** — A set of narrator/chain questions whose answers are verified directly against the graph database, reporting routing accuracy and answer accuracy.
- **Held-out evaluation** — 120 questions written by a non-Gemini model, hand-reviewed, frozen before the final run.
- **Latency** — Parallelise HyDE with the raw-query embedding and test a lighter HyDE model (current end-to-end median `12.55 s` in [`EXPERIMENTS.md`](EXPERIMENTS.md#7-تطبيق-قاعدة-البساطة-على-المسار-الافتراضي-1000-دون-bm25-أو-توسيع-وثائق)).

---

## Scope and limitations

- **Sahih Muslim only** — The corpus covers the 7,459 hadiths of Sahih Muslim (`muslim.json`); hadiths recorded only in other collections (e.g., Sahih al-Bukhari) are out of scope and refused.
- **Research aid, not a fatwa authority** — Musnad surfaces recorded texts with their hadith numbers and transmission chains for verification; it does not issue religious rulings.
- **In-context citation errors** — `validate_answer` checks that cited hadith numbers belong to the retrieved context. In the upgraded `1:0:0:0` evaluation with `gemini-4-argon`, `3/90` responses across three runs cited a non-gold hadith from that context (`3.3%`).
- **Narrator gradings are not linked yet** — `sanad_graph.sqlite` records MIS narrator identities and transmission chains for `7,015` linked hadiths (`444` local hadiths remain unlinked); classical critic gradings (*al-jarḥ wa-l-taʿdīl*) remain gated until historical narrator entity resolution is validated.
