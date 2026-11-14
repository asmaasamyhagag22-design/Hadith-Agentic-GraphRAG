"""
E4 — HyDE query embedding (Hypothetical Document Embeddings / pseudo-matn generation).

Generates a hypothetical Prophetic hadith matn (pseudo-matn) in classical Arabic
for each of the 251 evaluation queries (224 dev + 27 golden) using `gemini-2.5-flash`
(`temperature=0`, `thinking_budget=0`), embeds the pseudo-matns with
`gemini-embedding-001`, and evaluates:
1. Standalone HyDE dense retrieval (`RETRIEVAL_DOCUMENT` and `RETRIEVAL_QUERY` embeddings)
2. Interpolated Query + HyDE embeddings (`alpha * v_query + (1 - alpha) * v_hyde`)
3. RRF fusion of the E2 4-field retriever with HyDE dense and BM25 channels
4. E2 + HyDE combined with the E3 cross-encoder reranker.
"""

import json
import pickle
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_docs import canonical_hash
from config import PROCESSED_DIR
from embed import indexable_chunks, load_chunks
from embed_vertex_e1 import PrecomputedDenseRetriever, embed_batches, l2_norm
from evaluate import answerable, evaluate, load_golden
from experiment_e0_gold_expansion import (
    GOLDEN_EXPANDED_PATH,
    SYNTHETIC_EXPANDED_PATH,
    evaluate_with_recall50,
)
from experiment_e1_dense_models import MultiRRFHybridRetriever
from experiment_e2_doc_expansion import (
    DOC_EXPANSIONS_PATH,
    PRICE_INPUT_PER_1M,
    PRICE_OUTPUT_PER_1M,
    PrecomputedBM25Retriever,
)
from experiment_e3_rerankers import (
    evaluate_pool_with_scores,
    load_merged_scores,
    pair_mcnemar,
)
from experiment_variants import variant_text
from lexical import BM25Index
from retrieve import load_chunk_lookup
from utils import strip_diacritics

HYDE_MODEL = "gemini-2.5-flash"
HYDE_QUERIES_PATH = PROCESSED_DIR / "hyde_queries.jsonl"
HYDE_META_PATH = PROCESSED_DIR / "hyde_queries_meta.json"
HYDE_VECS_PATH = PROCESSED_DIR / "queries_hyde_gemini001.npz"
E4_RESULTS_PATH = PROCESSED_DIR / "e4_results.json"

HYDE_PROMPT = """أنت خبير في متون صحيح مسلم.
لكل سؤال مرقّم أدناه، اكتب متن حديث نبوي افتراضي موجز (من جملة إلى ثلاث جمل فقط) باللغة العربية التراثية الفصيحة يحاكي أسلوب متون صحيح مسلم ويجيب مباشرة عن السؤال.
شروط صارمة:
1. اكتب المتن فقط دون إسناد ودون أسماء رواة ودون ذكر رقم حديث.
2. استخدم الألفاظ النبوية والشرعية الكلاسيكية المتوقعة في صحيح مسلم لهذا الموضوع.

أخرج JSON فقط بالصيغة التالية:
{"items": [{"idx": 1, "pseudo_matn": "..."}, ...]}

الأسئلة:
{questions}"""


def generate_hyde_pseudo_matns(all_questions):
    existing = {}
    if HYDE_QUERIES_PATH.exists():
        with open(HYDE_QUERIES_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if row.get("pseudo_matn"):
                        existing[row["question"]] = row

    missing = [q for q in all_questions if q not in existing]
    if not missing:
        print(f"All {len(all_questions)} HyDE pseudo-matns cached at {HYDE_QUERIES_PATH}")
        meta = {}
        if HYDE_META_PATH.exists():
            with open(HYDE_META_PATH, "r", encoding="utf-8") as f:
                meta = json.load(f)
        return [existing[q] for q in all_questions], meta

    print(f"Generating HyDE pseudo-matns for {len(missing)}/{len(all_questions)} questions...")
    client = genai.Client()
    lock = threading.Lock()
    stats = {
        "api_calls": 0,
        "prompt_tokens": 0,
        "candidates_tokens": 0,
        "total_tokens": 0,
    }
    t0 = time.time()
    batch_size = 15
    batches = [
        missing[start : start + batch_size]
        for start in range(0, len(missing), batch_size)
    ]

    def call_batch(sub):
        q_str = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(sub))
        prompt = HYDE_PROMPT.replace("{questions}", q_str)
        for attempt in range(5):
            try:
                resp = client.models.generate_content(
                    model=HYDE_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
                with lock:
                    stats["api_calls"] += 1
                    um = resp.usage_metadata
                    if um:
                        stats["prompt_tokens"] += um.prompt_token_count or 0
                        stats["candidates_tokens"] += um.candidates_token_count or 0
                        stats["total_tokens"] += um.total_token_count or 0
                data = json.loads(resp.text or "{}")
                by_idx = {}
                for entry in data.get("items", []):
                    if isinstance(entry, dict) and isinstance(entry.get("idx"), int):
                        pm = " ".join(str(entry.get("pseudo_matn", "")).split())
                        if pm:
                            by_idx[entry["idx"]] = pm
                if len(by_idx) == len(sub):
                    return [by_idx[i + 1] for i in range(len(sub))]
            except Exception:
                time.sleep(2 * (attempt + 1))
        return None

    def process_batch(batch):
        res = call_batch(batch)
        if res is None:
            res = []
            for q in batch:
                single = call_batch([q])
                res.append(single[0] if single else q)
        with lock:
            for q, pm in zip(batch, res):
                existing[q] = {"question": q, "pseudo_matn": pm}

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(process_batch, batches))

    ordered = [existing[q] for q in all_questions]
    HYDE_QUERIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HYDE_QUERIES_PATH, "w", encoding="utf-8", newline="\n") as f:
        for row in ordered:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    cost_in = (stats["prompt_tokens"] / 1_000_000) * PRICE_INPUT_PER_1M
    cost_out = (stats["candidates_tokens"] / 1_000_000) * PRICE_OUTPUT_PER_1M
    meta = {
        "model": HYDE_MODEL,
        "api_calls": stats["api_calls"],
        "prompt_tokens": stats["prompt_tokens"],
        "candidates_tokens": stats["candidates_tokens"],
        "total_tokens": stats["total_tokens"],
        "estimated_cost_usd": round(cost_in + cost_out, 4),
        "elapsed_seconds": round(time.time() - t0, 1),
        "sha256": canonical_hash(HYDE_QUERIES_PATH),
    }
    with open(HYDE_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Saved HyDE queries -> {HYDE_QUERIES_PATH} (hash `{meta['sha256']}`)")
    return ordered, meta


def ensure_hyde_embeddings(all_questions, pseudo_matns):
    if HYDE_VECS_PATH.exists():
        data = np.load(HYDE_VECS_PATH, allow_pickle=True)
        return data["vec_doc_3072"], data["vec_query_3072"]

    client = genai.Client()
    clean_pseudos = [strip_diacritics(p) for p in pseudo_matns]
    print("Embedding HyDE pseudo-matns (RETRIEVAL_DOCUMENT & RETRIEVAL_QUERY)...")
    v_doc = l2_norm(
        embed_batches(client, "gemini-embedding-001", clean_pseudos, "RETRIEVAL_DOCUMENT")
    )
    v_query = l2_norm(
        embed_batches(client, "gemini-embedding-001", clean_pseudos, "RETRIEVAL_QUERY")
    )
    np.savez(
        HYDE_VECS_PATH,
        questions=np.array(all_questions, dtype=object),
        vec_doc_3072=v_doc,
        vec_query_3072=v_query,
    )
    return v_doc, v_query


class MappedBM25Retriever:
    """BM25 retriever that maps each original question to its HyDE text."""

    def __init__(self, bm25_index, chunk_lookup, q_to_text, max_k=100):
        self.chunk_lookup = chunk_lookup
        self.chunk_ids = bm25_index.chunk_ids
        self.cache = {
            q: bm25_index.ranked_ids(text, k=max_k)
            for q, text in q_to_text.items()
        }

    def ranked_ids(self, question, k=50):
        return self.cache[question][:k]

    def search(self, question, k=5):
        results = []
        for rank, chunk_id in enumerate(self.cache[question][:k], start=1):
            chunk = self.chunk_lookup.get(chunk_id)
            if chunk is None:
                continue
            results.append({
                "rank": rank,
                "score": None,
                "chunk_id": chunk["id"],
                "hadith_id": chunk["metadata"]["hadith_number"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
            })
        return results


def main():
    all_chunks = load_chunks()
    idx_chunks = indexable_chunks(all_chunks)
    chunk_ids = [str(c["id"]) for c in idx_chunks]
    chunk_lookup = load_chunk_lookup()

    golden_items = answerable(load_golden(GOLDEN_EXPANDED_PATH))
    synth_items = answerable(load_golden(SYNTHETIC_EXPANDED_PATH))
    all_questions = list(
        dict.fromkeys([it["question"] for it in golden_items + synth_items])
    )

    hyde_rows, meta = generate_hyde_pseudo_matns(all_questions)
    pseudo_matns = [r["pseudo_matn"] for r in hyde_rows]
    q_to_pseudo = {r["question"]: r["pseudo_matn"] for r in hyde_rows}
    q_to_concat = {
        r["question"]: f"{r['question']} {r['pseudo_matn']}" for r in hyde_rows
    }

    v_hyde_doc, v_hyde_query = ensure_hyde_embeddings(all_questions, pseudo_matns)

    g001_3072 = np.load(PROCESSED_DIR / "vectors_matn_gemini001_3072.npy")
    exp_v3072 = np.load(PROCESSED_DIR / "vectors_expansion_gemini001_3072.npy")
    g001_q = np.load(PROCESSED_DIR / "queries_gemini001.npz", allow_pickle=True)
    q_list = list(g001_q["questions"])
    v3072_q = g001_q["vec3072"]
    q_idx = {q: i for i, q in enumerate(q_list)}
    v_orig_q = np.array([v3072_q[q_idx[q]] for q in all_questions])

    # Build query vector maps
    map_orig = {q: v_orig_q[i] for i, q in enumerate(all_questions)}
    map_hyde_doc = {q: v_hyde_doc[i] for i, q in enumerate(all_questions)}
    map_hyde_q = {q: v_hyde_query[i] for i, q in enumerate(all_questions)}

    v_blend_50_q = l2_norm(0.5 * v_orig_q + 0.5 * v_hyde_query)
    v_blend_70_q = l2_norm(0.7 * v_orig_q + 0.3 * v_hyde_query)
    v_blend_80_q = l2_norm(0.8 * v_orig_q + 0.2 * v_hyde_query)
    v_blend_70_d = l2_norm(0.7 * v_orig_q + 0.3 * v_hyde_doc)

    map_blend_50_q = {q: v_blend_50_q[i] for i, q in enumerate(all_questions)}
    map_blend_70_q = {q: v_blend_70_q[i] for i, q in enumerate(all_questions)}
    map_blend_80_q = {q: v_blend_80_q[i] for i, q in enumerate(all_questions)}
    map_blend_70_d = {q: v_blend_70_d[i] for i, q in enumerate(all_questions)}

    # Retrievers
    dense_matn_orig = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_orig)
    dense_exp_orig = PrecomputedDenseRetriever(exp_v3072, chunk_ids, chunk_lookup, map_orig)

    dense_matn_hyde_doc = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_hyde_doc)
    dense_matn_hyde_q = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_hyde_q)
    dense_matn_blend50 = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_blend_50_q)
    dense_matn_blend70 = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_blend_70_q)
    dense_matn_blend80 = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_blend_80_q)
    dense_matn_blend70d = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_blend_70_d)

    dense_exp_blend70 = PrecomputedDenseRetriever(exp_v3072, chunk_ids, chunk_lookup, map_blend_70_q)

    expansions_by_cid = {}
    with open(DOC_EXPANSIONS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                expansions_by_cid[str(row["chunk_id"])] = row["expansion_text"]
    expansion_texts = [expansions_by_cid[cid] for cid in chunk_ids]

    bm25_matn_raw = BM25Index(
        chunk_ids, [variant_text(chunk_lookup[cid], "matn") for cid in chunk_ids]
    )
    bm25_exp_raw = BM25Index(chunk_ids, expansion_texts)
    bm25_matn = PrecomputedBM25Retriever(bm25_matn_raw, chunk_lookup, all_questions)
    bm25_exp = PrecomputedBM25Retriever(bm25_exp_raw, chunk_lookup, all_questions)
    bm25_matn_hyde = MappedBM25Retriever(bm25_matn_raw, chunk_lookup, q_to_pseudo)
    bm25_matn_concat = MappedBM25Retriever(bm25_matn_raw, chunk_lookup, q_to_concat)

    e2_best = MultiRRFHybridRetriever(
        [dense_matn_orig, dense_exp_orig, bm25_matn, bm25_exp],
        weights=[2.0, 1.0, 1.0, 1.0],
        candidates=50,
    )

    configs = [
        # Baselines (E1 and E2 winners)
        ("E1: Dense gemini-001 (3072, query only)", dense_matn_orig),
        ("E2 Best: Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)", e2_best),
        # Pure HyDE dense
        ("E4: HyDE pseudo-matn only (RETRIEVAL_DOCUMENT -> Dense_m)", dense_matn_hyde_doc),
        ("E4: HyDE pseudo-matn only (RETRIEVAL_QUERY -> Dense_m)", dense_matn_hyde_q),
        ("E4: BM25_matn (HyDE pseudo-matn only)", bm25_matn_hyde),
        ("E4: BM25_matn (query + HyDE pseudo-matn)", bm25_matn_concat),
        # Query + HyDE vector interpolation on Dense_matn
        ("E4: Dense_m (0.5*query + 0.5*HyDE_q)", dense_matn_blend50),
        ("E4: Dense_m (0.7*query + 0.3*HyDE_q)", dense_matn_blend70),
        ("E4: Dense_m (0.8*query + 0.2*HyDE_q)", dense_matn_blend80),
        ("E4: Dense_m (0.7*query + 0.3*HyDE_doc)", dense_matn_blend70d),
        # E2 + HyDE RRF fusions
        (
            "E4: E2 (2:1:1:1) + Dense_m(HyDE_q) (w=0.5)",
            MultiRRFHybridRetriever(
                [dense_matn_orig, dense_exp_orig, bm25_matn, bm25_exp, dense_matn_hyde_q],
                weights=[2.0, 1.0, 1.0, 1.0, 0.5],
                candidates=50,
            ),
        ),
        (
            "E4: E2 (2:1:1:1) + Dense_m(HyDE_q) (w=1.0)",
            MultiRRFHybridRetriever(
                [dense_matn_orig, dense_exp_orig, bm25_matn, bm25_exp, dense_matn_hyde_q],
                weights=[2.0, 1.0, 1.0, 1.0, 1.0],
                candidates=50,
            ),
        ),
        (
            "E4: E2 (2:1:1:1) + Dense_m(HyDE_doc) (w=0.5)",
            MultiRRFHybridRetriever(
                [dense_matn_orig, dense_exp_orig, bm25_matn, bm25_exp, dense_matn_hyde_doc],
                weights=[2.0, 1.0, 1.0, 1.0, 0.5],
                candidates=50,
            ),
        ),
        (
            "E4: E2 (2:1:1:1) + Dense_m(HyDE_q) + BM25_m(HyDE) (0.5:0.5)",
            MultiRRFHybridRetriever(
                [
                    dense_matn_orig,
                    dense_exp_orig,
                    bm25_matn,
                    bm25_exp,
                    dense_matn_hyde_q,
                    bm25_matn_hyde,
                ],
                weights=[2.0, 1.0, 1.0, 1.0, 0.5, 0.5],
                candidates=50,
            ),
        ),
        (
            "E4: E2 with blended query vector (0.7*q + 0.3*HyDE_q) (2:1:1:1)",
            MultiRRFHybridRetriever(
                [dense_matn_blend70, dense_exp_blend70, bm25_matn, bm25_exp],
                weights=[2.0, 1.0, 1.0, 1.0],
                candidates=50,
            ),
        ),
        (
            "E4: E2 with blended Dense_m (0.8*q + 0.2*HyDE_q) (2:1:1:1)",
            MultiRRFHybridRetriever(
                [dense_matn_blend80, dense_exp_orig, bm25_matn, bm25_exp],
                weights=[2.0, 1.0, 1.0, 1.0],
                candidates=50,
            ),
        ),
    ]

    summary = {"meta": meta, "results": {}}
    for ds_name, items in [
        ("synthetic_eval_expanded", synth_items),
        ("golden_expanded", golden_items),
    ]:
        summary["results"][ds_name] = {}
        print(f"\n=== {ds_name} (n={len(items)}) ===")
        print(
            f"{'Configuration':<64} {'hit@1':<7} {'hit@3':<7} {'hit@5':<7} "
            f"{'hit@10':<7} {'recall@50':<10} {'setR@50':<8} {'MRR@10':<7} {'MRR@50':<7}"
        )
        print("-" * 132)
        for name, ret in configs:
            hits10, mrr10, _ = evaluate(ret, items, k_values=(1, 3, 5, 10))
            hits50, mrr50, set_r50, _ = evaluate_with_recall50(ret, items)
            summary["results"][ds_name][name] = {
                "hit@1": round(hits10[1], 4),
                "hit@3": round(hits10[3], 4),
                "hit@5": round(hits10[5], 4),
                "hit@10": round(hits10[10], 4),
                "recall@50": round(hits50[50], 4),
                "hits50_count": int(round(hits50[50] * len(items))),
                "setR@50": round(set_r50, 4),
                "MRR@10": round(mrr10, 4),
                "MRR@50": round(mrr50, 4),
            }
            print(
                f"{name:<64} "
                f"{hits10[1]:<7.1%} {hits10[3]:<7.1%} {hits10[5]:<7.1%} "
                f"{hits10[10]:<7.1%} {hits50[50]:<10.1%} {set_r50:<8.1%} "
                f"{mrr10:<7.3f} {mrr50:<7.3f}"
            )

    with open(E4_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSaved E4 results -> {E4_RESULTS_PATH}")


if __name__ == "__main__":
    main()
