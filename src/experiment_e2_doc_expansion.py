"""
E2 — Document expansion for all 7,110 indexable Sahih Muslim chunks.

Generates 3-5 Modern Standard Arabic (MSA) questions and topical/jurisprudential
keywords per chunk using a DIFFERENT model (`gemini-2.5-flash` with
`thinking_budget=0`) and a DIFFERENT prompt (`DOC_EXPANSION_PROMPT`) from
`src/build_eval_set.py` (which used `gemini-2.5-pro`).

Indexes the generated expansion strings as a separate field (both BM25 and
dense `gemini-embedding-001`) and fuses with RRF. Records model, prompt,
token usage, API calls, cost, sha256, and retrieval metrics (`recall@50`, `MRR`).
"""

import json
import re
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
from config import IDS_MATN, PROCESSED_DIR, VECTORS_MATN
from embed import indexable_chunks, load_chunks
from embed_vertex_e1 import (
    PrecomputedDenseRetriever,
    embed_batches,
    ensure_vertex_embeddings,
    l2_norm,
)
from evaluate import answerable, evaluate, load_golden
from experiment_e0_gold_expansion import (
    GOLDEN_EXPANDED_PATH,
    SYNTHETIC_EXPANDED_PATH,
    evaluate_with_recall50,
)
from experiment_e1_dense_models import MultiRRFHybridRetriever
from experiment_variants import variant_text
from lexical import BM25Index
from retrieve import LexicalRetriever, Retriever, load_chunk_lookup
from utils import strip_diacritics

EXPANSION_MODEL = "gemini-2.5-flash"
BATCH_SIZE = 25
MAX_WORKERS = 8

DOC_EXPANSIONS_PATH = PROCESSED_DIR / "doc_expansions.jsonl"
DOC_EXPANSIONS_META_PATH = PROCESSED_DIR / "doc_expansions_meta.json"

# Vertex AI gemini-2.5-flash pricing (USD per 1M tokens, non-thinking)
PRICE_INPUT_PER_1M = 0.30
PRICE_OUTPUT_PER_1M = 2.50

DOC_EXPANSION_PROMPT = """أنت مفهرس موضوعي وفقهي لأحاديث صحيح مسلم.
لكل نص مرقّم أدناه (يتضمن عنوان الباب ومتن الحديث)، اكتب من 3 إلى 5 عبارات بحثية وأسئلة قصيرة وكلمات مفتاحية فقهية وموضوعية باللغة العربية الفصحى المعاصرة (MSA) تصف موضوع الحديث وحكمه ومعناه ومرادفاته المعاصرة للألفاظ التراثية.

شروط الفهرسة:
1. استخدم المصطلحات الفصحى المعاصرة التي يبحث بها القارئ اليوم إلى جانب المفهوم الشرعي الدقيق.
2. اجعل كل عبارة موجزة ومكتفية بذاتها (سؤال قصير أو عنوان موضوعي أو مصطلح فقهي).
3. لا تذكر رقم الحديث ولا أسماء الرواة في السند.

أخرج JSON فقط بالصيغة التالية دون أي نص إضافي:
{"expansions": [{"idx": 1, "items": ["...", "...", "..."]}, ...]}

النصوص:
{docs}"""


def format_chunk_for_expansion(chunk):
    chapter = strip_diacritics(chunk["metadata"].get("chapter_arabic", "")).strip()
    matn = " ".join(strip_diacritics(variant_text(chunk, "matn")).split())
    if len(matn) > 450:
        matn = matn[:450] + "..."
    if chapter:
        return f"[{chapter}] {matn}"
    return matn


def parse_expansion_json(raw_text, expected_len):
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    items_list = data.get("expansions")
    if not isinstance(items_list, list):
        return None

    by_idx = {}
    for entry in items_list:
        if not isinstance(entry, dict):
            continue
        idx = entry.get("idx")
        terms = entry.get("items")
        if isinstance(idx, int) and isinstance(terms, list):
            cleaned = [str(t).strip() for t in terms if str(t).strip()]
            if cleaned:
                by_idx[idx] = cleaned[:5]

    if len(by_idx) < expected_len:
        return None
    return [by_idx[i + 1] for i in range(expected_len)]


def generate_all_expansions(idx_chunks):
    existing = {}
    if DOC_EXPANSIONS_PATH.exists():
        with open(DOC_EXPANSIONS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if row.get("items"):
                        existing[str(row["chunk_id"])] = row

    missing_chunks = [c for c in idx_chunks if str(c["id"]) not in existing]
    if not missing_chunks:
        print(f"All {len(idx_chunks)} chunk expansions already cached at {DOC_EXPANSIONS_PATH}")
        meta = {}
        if DOC_EXPANSIONS_META_PATH.exists():
            with open(DOC_EXPANSIONS_META_PATH, "r", encoding="utf-8") as f:
                meta = json.load(f)
        ordered = [existing[str(c["id"])] for c in idx_chunks]
        return ordered, meta

    print(
        f"Generating expansions for {len(missing_chunks)}/{len(idx_chunks)} chunks "
        f"using {EXPANSION_MODEL} (batch_size={BATCH_SIZE}, workers={MAX_WORKERS})..."
    )
    client = genai.Client()
    batches = [
        (b_i, missing_chunks[start : start + BATCH_SIZE])
        for b_i, start in enumerate(range(0, len(missing_chunks), BATCH_SIZE))
    ]

    lock = threading.Lock()
    stats = {
        "api_calls": 0,
        "prompt_tokens": 0,
        "candidates_tokens": 0,
        "total_tokens": 0,
        "done_batches": 0,
    }
    t0 = time.time()

    def call_once(sub_batch):
        docs_str = "\n".join(
            f"{i + 1}. {format_chunk_for_expansion(c)}"
            for i, c in enumerate(sub_batch)
        )
        prompt = DOC_EXPANSION_PROMPT.replace("{docs}", docs_str)
        for attempt in range(5):
            try:
                resp = client.models.generate_content(
                    model=EXPANSION_MODEL,
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
                parsed = parse_expansion_json(resp.text or "", len(sub_batch))
                if parsed is not None:
                    return parsed
            except Exception:
                time.sleep(2 * (attempt + 1))
        return None

    def process_batch(item):
        b_i, batch = item
        parsed = call_once(batch)
        if parsed is None:
            # Fallback: split into smaller sub-batches of 5
            parsed = []
            for start in range(0, len(batch), 5):
                sub = batch[start : start + 5]
                sub_parsed = call_once(sub)
                if sub_parsed is None:
                    # Fallback per single item
                    sub_parsed = []
                    for c in sub:
                        single = call_once([c])
                        if single:
                            sub_parsed.append(single[0])
                        else:
                            # Deterministic fallback to chapter title
                            ch = strip_diacritics(
                                c["metadata"].get("chapter_arabic", "")
                            ).strip()
                            sub_parsed.append([ch] if ch else ["حديث نبوي"])
                parsed.extend(sub_parsed)

        rows = []
        for c, terms in zip(batch, parsed):
            rows.append({
                "chunk_id": str(c["id"]),
                "hadith_id": c["metadata"]["hadith_number"],
                "items": terms,
                "expansion_text": " ؛ ".join(terms),
            })

        with lock:
            for r in rows:
                existing[r["chunk_id"]] = r
            stats["done_batches"] += 1
            done_b = stats["done_batches"]
            if done_b % 25 == 0 or done_b == len(batches):
                elapsed = time.time() - t0
                print(
                    f"  [E2 {EXPANSION_MODEL}] batches {done_b}/{len(batches)} "
                    f"| chunks {len(existing)}/{len(idx_chunks)} "
                    f"| calls={stats['api_calls']} "
                    f"| elapsed={elapsed:.1f}s",
                    flush=True,
                )
            if done_b % 50 == 0:
                DOC_EXPANSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(DOC_EXPANSIONS_PATH, "w", encoding="utf-8", newline="\n") as ck_f:
                    for ck_row in existing.values():
                        ck_f.write(json.dumps(ck_row, ensure_ascii=False) + "\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        list(ex.map(process_batch, batches))

    ordered = [existing[str(c["id"])] for c in idx_chunks]
    DOC_EXPANSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DOC_EXPANSIONS_PATH, "w", encoding="utf-8", newline="\n") as f:
        for row in ordered:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    cost_in = (stats["prompt_tokens"] / 1_000_000) * PRICE_INPUT_PER_1M
    cost_out = (stats["candidates_tokens"] / 1_000_000) * PRICE_OUTPUT_PER_1M
    meta = {
        "model": EXPANSION_MODEL,
        "batch_size": BATCH_SIZE,
        "api_calls": stats["api_calls"],
        "prompt_tokens": stats["prompt_tokens"],
        "candidates_tokens": stats["candidates_tokens"],
        "total_tokens": stats["total_tokens"],
        "estimated_cost_usd": round(cost_in + cost_out, 4),
        "elapsed_seconds": round(time.time() - t0, 1),
        "sha256": canonical_hash(DOC_EXPANSIONS_PATH),
    }
    with open(DOC_EXPANSIONS_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Saved expansions -> {DOC_EXPANSIONS_PATH} (hash `{meta['sha256']}`)")
    print(f"Meta: {json.dumps(meta, ensure_ascii=False)}")
    return ordered, meta


class PrecomputedBM25Retriever:
    """Fast wrapper caching BM25 top-100 ranked_ids per query."""

    def __init__(self, bm25_index, chunk_lookup, all_questions, max_k=100):
        self.chunk_lookup = chunk_lookup
        self.chunk_ids = bm25_index.chunk_ids
        self.cache = {
            q: bm25_index.ranked_ids(q, k=max_k) for q in all_questions
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


def ensure_expansion_dense_vectors(expansion_texts):
    exp_3072_path = PROCESSED_DIR / "vectors_expansion_gemini001_3072.npy"
    exp_768_path = PROCESSED_DIR / "vectors_expansion_gemini001_768.npy"
    if not (exp_3072_path.exists() and exp_768_path.exists()):
        client = genai.Client()
        print("Embedding expansion field with gemini-embedding-001...")
        vecs = embed_batches(
            client,
            "gemini-embedding-001",
            [strip_diacritics(t) for t in expansion_texts],
            "RETRIEVAL_DOCUMENT",
        )
        np.save(exp_3072_path, l2_norm(vecs))
        np.save(exp_768_path, l2_norm(vecs[:, :768]))
    v3072 = np.load(exp_3072_path)
    v1536 = l2_norm(v3072[:, :1536])
    v768 = np.load(exp_768_path)
    return v768, v1536, v3072


def main():
    all_chunks = load_chunks()
    idx_chunks = indexable_chunks(all_chunks)
    chunk_ids = [str(c["id"]) for c in idx_chunks]
    chunk_lookup = load_chunk_lookup()
    doc_texts = [strip_diacritics(variant_text(c, "matn")) for c in idx_chunks]

    golden_items = answerable(load_golden(GOLDEN_EXPANDED_PATH))
    synth_items = answerable(load_golden(SYNTHETIC_EXPANDED_PATH))
    all_questions = list(
        dict.fromkeys([it["question"] for it in golden_items + synth_items])
    )
    q_texts = [strip_diacritics(q) for q in all_questions]

    # 1. Generate or load E2 document expansions
    expansions, meta = generate_all_expansions(idx_chunks)
    expansion_texts = [row["expansion_text"] for row in expansions]

    # 2. Build separate BM25 indexes (matn field and expansion field)
    print("Building BM25 indexes (matn and expansion)...")
    bm25_matn_raw = BM25Index(
        chunk_ids, [variant_text(chunk_lookup[cid], "matn") for cid in chunk_ids]
    )
    bm25_exp_raw = BM25Index(chunk_ids, expansion_texts)

    bm25_matn = PrecomputedBM25Retriever(bm25_matn_raw, chunk_lookup, all_questions)
    bm25_exp = PrecomputedBM25Retriever(bm25_exp_raw, chunk_lookup, all_questions)

    # 3. Load E1 dense vectors and embed expansion field as separate dense field
    ensure_vertex_embeddings(doc_texts, all_questions, q_texts)
    g001_3072 = np.load(PROCESSED_DIR / "vectors_matn_gemini001_3072.npy")
    g001_1536 = l2_norm(g001_3072[:, :1536])
    g001_768 = np.load(PROCESSED_DIR / "vectors_matn_gemini001_768.npy")
    g001_q = np.load(PROCESSED_DIR / "queries_gemini001.npz", allow_pickle=True)
    q_list = list(g001_q["questions"])
    v3072_q = g001_q["vec3072"]
    v1536_q = l2_norm(v3072_q[:, :1536])
    v768_q = g001_q["vec768"]
    q_map_3072 = {q: v3072_q[i] for i, q in enumerate(q_list)}
    q_map_1536 = {q: v1536_q[i] for i, q in enumerate(q_list)}
    q_map_768 = {q: v768_q[i] for i, q in enumerate(q_list)}

    exp_v768, exp_v1536, exp_v3072 = ensure_expansion_dense_vectors(expansion_texts)

    dense_matn_768 = PrecomputedDenseRetriever(g001_768, chunk_ids, chunk_lookup, q_map_768)
    dense_matn_1536 = PrecomputedDenseRetriever(g001_1536, chunk_ids, chunk_lookup, q_map_1536)
    dense_matn_3072 = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, q_map_3072)

    dense_exp_768 = PrecomputedDenseRetriever(exp_v768, chunk_ids, chunk_lookup, q_map_768)
    dense_exp_1536 = PrecomputedDenseRetriever(exp_v1536, chunk_ids, chunk_lookup, q_map_1536)
    dense_exp_3072 = PrecomputedDenseRetriever(exp_v3072, chunk_ids, chunk_lookup, q_map_3072)

    e5_dense = Retriever.from_files(VECTORS_MATN, IDS_MATN, chunk_lookup=chunk_lookup)

    configs = [
        # Standalone fields
        ("BM25: matn only (baseline)", bm25_matn),
        ("BM25: doc_expansion field only", bm25_exp),
        ("BM25: matn + doc_expansion (RRF 1:1)", MultiRRFHybridRetriever([bm25_matn, bm25_exp], weights=[1.0, 1.0], candidates=50)),
        ("Dense: doc_expansion gemini-001 (1536) only", dense_exp_1536),
        ("Dense: doc_expansion gemini-001 (3072) only", dense_exp_3072),
        # Effect on legacy e5-base hybrid
        ("Legacy Hybrid: e5-base + BM25_matn (1:1)", MultiRRFHybridRetriever([e5_dense, bm25_matn], weights=[1.0, 1.0], candidates=50)),
        ("Legacy Hybrid + BM25_exp (1:1:1)", MultiRRFHybridRetriever([e5_dense, bm25_matn, bm25_exp], weights=[1.0, 1.0, 1.0], candidates=50)),
        # E1 winners (no expansion)
        ("E1: Dense gemini-001 (768)", dense_matn_768),
        ("E1: Dense gemini-001 (1536)", dense_matn_1536),
        ("E1: Dense gemini-001 (3072)", dense_matn_3072),
        # E2 RRF fusions over E1 winner (1536d)
        ("E2 (1536): Dense_matn + BM25_exp (1:1)", MultiRRFHybridRetriever([dense_matn_1536, bm25_exp], weights=[1.0, 1.0], candidates=50)),
        ("E2 (1536): Dense_matn + BM25_exp (2:1)", MultiRRFHybridRetriever([dense_matn_1536, bm25_exp], weights=[2.0, 1.0], candidates=50)),
        ("E2 (1536): Dense_matn + BM25_exp (3:1)", MultiRRFHybridRetriever([dense_matn_1536, bm25_exp], weights=[3.0, 1.0], candidates=50)),
        ("E2 (1536): Dense_matn + Dense_exp (1:1)", MultiRRFHybridRetriever([dense_matn_1536, dense_exp_1536], weights=[1.0, 1.0], candidates=50)),
        ("E2 (1536): Dense_matn + Dense_exp (2:1)", MultiRRFHybridRetriever([dense_matn_1536, dense_exp_1536], weights=[2.0, 1.0], candidates=50)),
        ("E2 (1536): Dense_matn + BM25_matn + BM25_exp (2:1:1)", MultiRRFHybridRetriever([dense_matn_1536, bm25_matn, bm25_exp], weights=[2.0, 1.0, 1.0], candidates=50)),
        ("E2 (1536): Dense_matn + BM25_matn + BM25_exp (3:1:1)", MultiRRFHybridRetriever([dense_matn_1536, bm25_matn, bm25_exp], weights=[3.0, 1.0, 1.0], candidates=50)),
        ("E2 (1536): Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)", MultiRRFHybridRetriever([dense_matn_1536, dense_exp_1536, bm25_matn, bm25_exp], weights=[2.0, 1.0, 1.0, 1.0], candidates=50)),
        ("E2 (1536): Dense_m + Dense_e + BM25_m + BM25_e (3:1:1:1)", MultiRRFHybridRetriever([dense_matn_1536, dense_exp_1536, bm25_matn, bm25_exp], weights=[3.0, 1.0, 1.0, 1.0], candidates=50)),
        # E2 RRF fusions over E1 winner (3072d)
        ("E2 (3072): Dense_matn + BM25_exp (1:1)", MultiRRFHybridRetriever([dense_matn_3072, bm25_exp], weights=[1.0, 1.0], candidates=50)),
        ("E2 (3072): Dense_matn + BM25_exp (2:1)", MultiRRFHybridRetriever([dense_matn_3072, bm25_exp], weights=[2.0, 1.0], candidates=50)),
        ("E2 (3072): Dense_matn + BM25_exp (3:1)", MultiRRFHybridRetriever([dense_matn_3072, bm25_exp], weights=[3.0, 1.0], candidates=50)),
        ("E2 (3072): Dense_matn + Dense_exp (1:1)", MultiRRFHybridRetriever([dense_matn_3072, dense_exp_3072], weights=[1.0, 1.0], candidates=50)),
        ("E2 (3072): Dense_matn + Dense_exp (2:1)", MultiRRFHybridRetriever([dense_matn_3072, dense_exp_3072], weights=[2.0, 1.0], candidates=50)),
        ("E2 (3072): Dense_matn + BM25_matn + BM25_exp (2:1:1)", MultiRRFHybridRetriever([dense_matn_3072, bm25_matn, bm25_exp], weights=[2.0, 1.0, 1.0], candidates=50)),
        ("E2 (3072): Dense_matn + BM25_matn + BM25_exp (3:1:1)", MultiRRFHybridRetriever([dense_matn_3072, bm25_matn, bm25_exp], weights=[3.0, 1.0, 1.0], candidates=50)),
        ("E2 (3072): Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)", MultiRRFHybridRetriever([dense_matn_3072, dense_exp_3072, bm25_matn, bm25_exp], weights=[2.0, 1.0, 1.0, 1.0], candidates=50)),
        ("E2 (3072): Dense_m + Dense_e + BM25_m + BM25_e (3:1:1:1)", MultiRRFHybridRetriever([dense_matn_3072, dense_exp_3072, bm25_matn, bm25_exp], weights=[3.0, 1.0, 1.0, 1.0], candidates=50)),
        # E2 RRF fusions over E1 winner (768d)
        ("E2 (768): Dense_matn + BM25_exp (2:1)", MultiRRFHybridRetriever([dense_matn_768, bm25_exp], weights=[2.0, 1.0], candidates=50)),
        ("E2 (768): Dense_matn + Dense_exp (2:1)", MultiRRFHybridRetriever([dense_matn_768, dense_exp_768], weights=[2.0, 1.0], candidates=50)),
        ("E2 (768): Dense_m + Dense_e + BM25_m + BM25_e (3:1:1:1)", MultiRRFHybridRetriever([dense_matn_768, dense_exp_768, bm25_matn, bm25_exp], weights=[3.0, 1.0, 1.0, 1.0], candidates=50)),
    ]

    summary = {"meta": meta, "results": {}}
    for ds_name, items in [
        ("synthetic_eval_expanded", synth_items),
        ("golden_expanded", golden_items),
    ]:
        summary["results"][ds_name] = {}
        print(f"\n=== {ds_name} (n={len(items)}) ===")
        print(
            f"{'Configuration':<58} {'hit@1':<7} {'hit@3':<7} {'hit@5':<7} "
            f"{'hit@10':<7} {'recall@50':<10} {'setR@50':<8} {'MRR@10':<7} {'MRR@50':<7}"
        )
        print("-" * 126)
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
                f"{name:<58} "
                f"{hits10[1]:<7.1%} {hits10[3]:<7.1%} {hits10[5]:<7.1%} "
                f"{hits10[10]:<7.1%} {hits50[50]:<10.1%} {set_r50:<8.1%} "
                f"{mrr10:<7.3f} {mrr50:<7.3f}"
            )

    out_json = PROCESSED_DIR / "e2_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSaved E2 results -> {out_json}")


if __name__ == "__main__":
    main()
