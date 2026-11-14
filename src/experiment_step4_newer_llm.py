"""
Step 4 — Re-run E2 (Document Expansion) and E4 (HyDE) with the newest GA Flash-class
model available in this Vertex project (`gemini-3.8-flash` on the `global` endpoint),
with prompts unchanged and the lowest supported thinking setting that returns valid
JSON (`thinking_level="LOW"`, as `MINIMAL` returns HTTP 400 on `gemini-3.8-flash`).

Compares `gemini-2.5-flash` vs `gemini-3.8-flash` side by side on both
`synthetic_eval_expanded.jsonl` (dev, n=224) and `golden_expanded.jsonl` (n=27),
recording API calls, input/output/thought tokens, and cost.
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
from config import PROCESSED_DIR
from embed import indexable_chunks, load_chunks
from embed_vertex_e1 import (
    PrecomputedDenseRetriever,
    embed_batches,
    l2_norm,
)
from evaluate import answerable, evaluate, load_golden
from experiment_e0_gold_expansion import (
    GOLDEN_EXPANDED_PATH,
    SYNTHETIC_EXPANDED_PATH,
    evaluate_with_recall50,
)
from experiment_e1_dense_models import MultiRRFHybridRetriever
from experiment_e2_doc_expansion import (
    DOC_EXPANSION_PROMPT,
    PrecomputedBM25Retriever,
    format_chunk_for_expansion,
)
from experiment_e4_hyde import HYDE_PROMPT, MappedBM25Retriever
from experiment_variants import variant_text
from lexical import BM25Index
from retrieve import load_chunk_lookup
from utils import strip_diacritics

NEW_FLASH_MODEL = "gemini-3.8-flash"
NEW_FLASH_LOCATION = "global"
THINKING_LEVEL = "LOW"

# Vertex AI gemini-3.8-flash pricing per 1M tokens (2026 promotional GA rate: $0.75 in / $3.75 out)
G38_PRICE_INPUT_PER_1M = 0.75
G38_PRICE_OUTPUT_PER_1M = 3.75

BATCH_SIZE_E2 = 25
MAX_WORKERS_E2 = 10

DOC_EXP_G38_PATH = PROCESSED_DIR / "doc_expansions_g38flash.jsonl"
DOC_EXP_G38_META_PATH = PROCESSED_DIR / "doc_expansions_g38flash_meta.json"
VECS_EXP_G38_3072_PATH = PROCESSED_DIR / "vectors_expansion_g38flash_gemini001_3072.npy"
VECS_EXP_G38_768_PATH = PROCESSED_DIR / "vectors_expansion_g38flash_gemini001_768.npy"

HYDE_G38_PATH = PROCESSED_DIR / "hyde_queries_g38flash.jsonl"
HYDE_G38_META_PATH = PROCESSED_DIR / "hyde_queries_g38flash_meta.json"
HYDE_G38_VECS_PATH = PROCESSED_DIR / "queries_hyde_g38flash_gemini001.npz"

STEP4_RESULTS_PATH = PROCESSED_DIR / "step4_results.json"


def parse_partial_expansion_json(raw_text):
    """Return {idx (1-based): [terms...]} from model JSON output."""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    items_list = data.get("expansions")
    if not isinstance(items_list, list):
        return {}
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
    return by_idx


def generate_e2_g38flash(idx_chunks):
    existing = {}
    if DOC_EXP_G38_PATH.exists():
        with open(DOC_EXP_G38_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if row.get("items") and len(row["items"]) >= 2:
                        existing[str(row["chunk_id"])] = row

    missing_chunks = [c for c in idx_chunks if str(c["id"]) not in existing]
    if not missing_chunks:
        print(f"All {len(idx_chunks)} g38flash expansions cached at {DOC_EXP_G38_PATH}")
        with open(DOC_EXP_G38_META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return [existing[str(c["id"])] for c in idx_chunks], meta

    print(
        f"Generating E2 expansions for {len(missing_chunks)}/{len(idx_chunks)} chunks "
        f"with {NEW_FLASH_MODEL} (location={NEW_FLASH_LOCATION}, thinking_level={THINKING_LEVEL})..."
    )
    client = genai.Client(location=NEW_FLASH_LOCATION)
    batches = [
        (b_i, missing_chunks[start : start + BATCH_SIZE_E2])
        for b_i, start in enumerate(range(0, len(missing_chunks), BATCH_SIZE_E2))
    ]

    lock = threading.Lock()
    stats = {
        "api_calls": 0,
        "prompt_tokens": 0,
        "candidates_tokens": 0,
        "thoughts_tokens": 0,
        "total_tokens": 0,
        "done_batches": 0,
    }
    t0 = time.time()

    def call_sub(sub_batch):
        docs_str = "\n".join(
            f"{i + 1}. {format_chunk_for_expansion(c)}"
            for i, c in enumerate(sub_batch)
        )
        prompt = DOC_EXPANSION_PROMPT.replace("{docs}", docs_str)
        for attempt in range(5):
            try:
                resp = client.models.generate_content(
                    model=NEW_FLASH_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(
                            thinking_level=THINKING_LEVEL
                        ),
                    ),
                )
                with lock:
                    stats["api_calls"] += 1
                    um = resp.usage_metadata
                    if um:
                        stats["prompt_tokens"] += um.prompt_token_count or 0
                        stats["candidates_tokens"] += um.candidates_token_count or 0
                        stats["thoughts_tokens"] += um.thoughts_token_count or 0
                        stats["total_tokens"] += um.total_token_count or 0
                by_idx = parse_partial_expansion_json(resp.text or "")
                if by_idx:
                    return by_idx
            except Exception:
                time.sleep(2 * (attempt + 1))
        return {}

    def process_batch(item):
        b_i, batch = item
        resolved = {}
        by_idx = call_sub(batch)
        for i, c in enumerate(batch):
            if (i + 1) in by_idx:
                resolved[str(c["id"])] = by_idx[i + 1]

        rem = [c for c in batch if str(c["id"]) not in resolved]
        if rem:
            by_idx2 = call_sub(rem)
            for i, c in enumerate(rem):
                if (i + 1) in by_idx2:
                    resolved[str(c["id"])] = by_idx2[i + 1]

        rem2 = [c for c in batch if str(c["id"]) not in resolved]
        for c in rem2:
            by_idx3 = call_sub([c])
            if 1 in by_idx3:
                resolved[str(c["id"])] = by_idx3[1]
            else:
                ch = strip_diacritics(c["metadata"].get("chapter_arabic", "")).strip()
                resolved[str(c["id"])] = [ch] if ch else ["حديث نبوي"]

        rows = []
        for c in batch:
            terms = resolved[str(c["id"])]
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
            if done_b % 20 == 0 or done_b == len(batches):
                elapsed = time.time() - t0
                print(
                    f"  [E2 {NEW_FLASH_MODEL}] batches {done_b}/{len(batches)} "
                    f"| chunks {len(existing)}/{len(idx_chunks)} "
                    f"| calls={stats['api_calls']} "
                    f"| elapsed={elapsed:.1f}s",
                    flush=True,
                )
            if done_b % 40 == 0:
                with open(DOC_EXP_G38_PATH, "w", encoding="utf-8", newline="\n") as ck_f:
                    for ck_row in existing.values():
                        ck_f.write(json.dumps(ck_row, ensure_ascii=False) + "\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS_E2) as ex:
        list(ex.map(process_batch, batches))

    ordered = [existing[str(c["id"])] for c in idx_chunks]
    with open(DOC_EXP_G38_PATH, "w", encoding="utf-8", newline="\n") as f:
        for row in ordered:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    cost_in = (stats["prompt_tokens"] / 1_000_000) * G38_PRICE_INPUT_PER_1M
    out_plus_thoughts = stats["candidates_tokens"] + stats["thoughts_tokens"]
    cost_out = (out_plus_thoughts / 1_000_000) * G38_PRICE_OUTPUT_PER_1M
    meta = {
        "model": NEW_FLASH_MODEL,
        "location": NEW_FLASH_LOCATION,
        "thinking_level": THINKING_LEVEL,
        "batch_size": BATCH_SIZE_E2,
        "api_calls": stats["api_calls"],
        "prompt_tokens": stats["prompt_tokens"],
        "candidates_tokens": stats["candidates_tokens"],
        "thoughts_tokens": stats["thoughts_tokens"],
        "total_tokens": stats["total_tokens"],
        "estimated_cost_usd": round(cost_in + cost_out, 4),
        "elapsed_seconds": round(time.time() - t0, 1),
        "sha256": canonical_hash(DOC_EXP_G38_PATH),
    }
    with open(DOC_EXP_G38_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Saved E2 g38flash -> {DOC_EXP_G38_PATH} (hash `{meta['sha256']}`)")
    print(f"E2 g38flash meta: {json.dumps(meta, ensure_ascii=False)}")
    return ordered, meta


def ensure_e2_g38_vectors(expansion_texts):
    if not (VECS_EXP_G38_3072_PATH.exists() and VECS_EXP_G38_768_PATH.exists()):
        client = genai.Client()
        print("Embedding g38flash expansion field with gemini-embedding-001...")
        vecs = embed_batches(
            client,
            "gemini-embedding-001",
            [strip_diacritics(t) for t in expansion_texts],
            "RETRIEVAL_DOCUMENT",
        )
        np.save(VECS_EXP_G38_3072_PATH, l2_norm(vecs))
        np.save(VECS_EXP_G38_768_PATH, l2_norm(vecs[:, :768]))
    v3072 = np.load(VECS_EXP_G38_3072_PATH)
    v1536 = l2_norm(v3072[:, :1536])
    v768 = np.load(VECS_EXP_G38_768_PATH)
    return v768, v1536, v3072


def generate_e4_g38flash(all_questions):
    existing = {}
    if HYDE_G38_PATH.exists():
        with open(HYDE_G38_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if row.get("pseudo_matn") and row["pseudo_matn"] != row["question"]:
                        existing[row["question"]] = row

    missing = [q for q in all_questions if q not in existing]
    if not missing:
        print(f"All {len(all_questions)} g38flash HyDE pseudo-matns cached at {HYDE_G38_PATH}")
        with open(HYDE_G38_META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return [existing[q] for q in all_questions], meta

    print(
        f"Generating E4 HyDE pseudo-matns for {len(missing)}/{len(all_questions)} questions "
        f"with {NEW_FLASH_MODEL} (location={NEW_FLASH_LOCATION}, thinking_level={THINKING_LEVEL})..."
    )
    client = genai.Client(location=NEW_FLASH_LOCATION)
    lock = threading.Lock()
    stats = {
        "api_calls": 0,
        "prompt_tokens": 0,
        "candidates_tokens": 0,
        "thoughts_tokens": 0,
        "total_tokens": 0,
    }
    t0 = time.time()
    batch_size = 15
    batches = [
        missing[start : start + batch_size]
        for start in range(0, len(missing), batch_size)
    ]

    def call_sub(sub):
        q_str = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(sub))
        prompt = HYDE_PROMPT.replace("{questions}", q_str)
        for attempt in range(5):
            try:
                resp = client.models.generate_content(
                    model=NEW_FLASH_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(
                            thinking_level=THINKING_LEVEL
                        ),
                    ),
                )
                with lock:
                    stats["api_calls"] += 1
                    um = resp.usage_metadata
                    if um:
                        stats["prompt_tokens"] += um.prompt_token_count or 0
                        stats["candidates_tokens"] += um.candidates_token_count or 0
                        stats["thoughts_tokens"] += um.thoughts_token_count or 0
                        stats["total_tokens"] += um.total_token_count or 0
                raw = resp.text or "{}"
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    m = re.search(r"\{.*\}", raw, re.DOTALL)
                    data = json.loads(m.group(0)) if m else {}
                by_idx = {}
                for entry in data.get("items", []):
                    if isinstance(entry, dict) and isinstance(entry.get("idx"), int):
                        pm = " ".join(str(entry.get("pseudo_matn", "")).split())
                        if pm:
                            by_idx[entry["idx"]] = pm
                if by_idx:
                    return by_idx
            except Exception:
                time.sleep(2 * (attempt + 1))
        return {}

    def process_batch(batch):
        resolved = {}
        by_idx = call_sub(batch)
        for i, q in enumerate(batch):
            if (i + 1) in by_idx:
                resolved[q] = by_idx[i + 1]
        rem = [q for q in batch if q not in resolved]
        if rem:
            by_idx2 = call_sub(rem)
            for i, q in enumerate(rem):
                if (i + 1) in by_idx2:
                    resolved[q] = by_idx2[i + 1]
        for q in batch:
            if q not in resolved:
                b3 = call_sub([q])
                resolved[q] = b3.get(1, q)
        with lock:
            for q in batch:
                existing[q] = {"question": q, "pseudo_matn": resolved[q]}

    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(process_batch, batches))

    ordered = [existing[q] for q in all_questions]
    with open(HYDE_G38_PATH, "w", encoding="utf-8", newline="\n") as f:
        for row in ordered:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    cost_in = (stats["prompt_tokens"] / 1_000_000) * G38_PRICE_INPUT_PER_1M
    out_plus_thoughts = stats["candidates_tokens"] + stats["thoughts_tokens"]
    cost_out = (out_plus_thoughts / 1_000_000) * G38_PRICE_OUTPUT_PER_1M
    meta = {
        "model": NEW_FLASH_MODEL,
        "location": NEW_FLASH_LOCATION,
        "thinking_level": THINKING_LEVEL,
        "api_calls": stats["api_calls"],
        "prompt_tokens": stats["prompt_tokens"],
        "candidates_tokens": stats["candidates_tokens"],
        "thoughts_tokens": stats["thoughts_tokens"],
        "total_tokens": stats["total_tokens"],
        "estimated_cost_usd": round(cost_in + cost_out, 4),
        "elapsed_seconds": round(time.time() - t0, 1),
        "sha256": canonical_hash(HYDE_G38_PATH),
    }
    with open(HYDE_G38_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Saved E4 g38flash -> {HYDE_G38_PATH} (hash `{meta['sha256']}`)")
    print(f"E4 g38flash meta: {json.dumps(meta, ensure_ascii=False)}")
    return ordered, meta


def ensure_e4_g38_vectors(all_questions, pseudo_matns):
    if HYDE_G38_VECS_PATH.exists():
        data = np.load(HYDE_G38_VECS_PATH, allow_pickle=True)
        return data["vec_doc_3072"], data["vec_query_3072"]

    client = genai.Client()
    clean_pseudos = [strip_diacritics(p) for p in pseudo_matns]
    print("Embedding g38flash HyDE pseudo-matns (RETRIEVAL_DOCUMENT & RETRIEVAL_QUERY)...")
    v_doc = l2_norm(
        embed_batches(client, "gemini-embedding-001", clean_pseudos, "RETRIEVAL_DOCUMENT")
    )
    v_query = l2_norm(
        embed_batches(client, "gemini-embedding-001", clean_pseudos, "RETRIEVAL_QUERY")
    )
    np.savez(
        HYDE_G38_VECS_PATH,
        questions=np.array(all_questions, dtype=object),
        vec_doc_3072=v_doc,
        vec_query_3072=v_query,
    )
    return v_doc, v_query


def eval_retriever_dict(ret, items):
    hits10, mrr10, _ = evaluate(ret, items, k_values=(1, 3, 5, 10))
    hits50, mrr50, set_r50, _ = evaluate_with_recall50(ret, items)
    return {
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

    exp_rows, e2_meta = generate_e2_g38flash(idx_chunks)
    exp_texts = [r["expansion_text"] for r in exp_rows]
    _, exp_v1536, exp_v3072 = ensure_e2_g38_vectors(exp_texts)

    hyde_rows, e4_meta = generate_e4_g38flash(all_questions)
    pseudo_matns = [r["pseudo_matn"] for r in hyde_rows]
    q_to_pseudo = {r["question"]: r["pseudo_matn"] for r in hyde_rows}
    q_to_concat = {
        r["question"]: f"{r['question']} {r['pseudo_matn']}" for r in hyde_rows
    }
    v_hyde_doc, v_hyde_query = ensure_e4_g38_vectors(all_questions, pseudo_matns)

    g001_3072 = np.load(PROCESSED_DIR / "vectors_matn_gemini001_3072.npy")
    g001_1536 = l2_norm(g001_3072[:, :1536])
    g001_q = np.load(PROCESSED_DIR / "queries_gemini001.npz", allow_pickle=True)
    q_list = list(g001_q["questions"])
    v3072_q = g001_q["vec3072"]
    v1536_q = l2_norm(v3072_q[:, :1536])
    q_idx = {q: i for i, q in enumerate(q_list)}
    v_orig_q3072 = np.array([v3072_q[q_idx[q]] for q in all_questions])
    v_orig_q1536 = np.array([v1536_q[q_idx[q]] for q in all_questions])

    map_orig_3072 = {q: v_orig_q3072[i] for i, q in enumerate(all_questions)}
    map_orig_1536 = {q: v_orig_q1536[i] for i, q in enumerate(all_questions)}
    map_hyde_doc = {q: v_hyde_doc[i] for i, q in enumerate(all_questions)}
    map_hyde_q = {q: v_hyde_query[i] for i, q in enumerate(all_questions)}

    v_blend_50_q = l2_norm(0.5 * v_orig_q3072 + 0.5 * v_hyde_query)
    v_blend_70_q = l2_norm(0.7 * v_orig_q3072 + 0.3 * v_hyde_query)
    v_blend_80_q = l2_norm(0.8 * v_orig_q3072 + 0.2 * v_hyde_query)
    map_blend_50_q = {q: v_blend_50_q[i] for i, q in enumerate(all_questions)}
    map_blend_70_q = {q: v_blend_70_q[i] for i, q in enumerate(all_questions)}
    map_blend_80_q = {q: v_blend_80_q[i] for i, q in enumerate(all_questions)}

    dense_matn_3072 = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_orig_3072)
    dense_matn_1536 = PrecomputedDenseRetriever(g001_1536, chunk_ids, chunk_lookup, map_orig_1536)
    dense_exp_3072 = PrecomputedDenseRetriever(exp_v3072, chunk_ids, chunk_lookup, map_orig_3072)
    dense_exp_1536 = PrecomputedDenseRetriever(exp_v1536, chunk_ids, chunk_lookup, map_orig_1536)

    dense_matn_hyde_doc = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_hyde_doc)
    dense_matn_hyde_q = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_hyde_q)
    dense_matn_blend50 = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_blend_50_q)
    dense_matn_blend70 = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_blend_70_q)
    dense_matn_blend80 = PrecomputedDenseRetriever(g001_3072, chunk_ids, chunk_lookup, map_blend_80_q)
    dense_exp_blend70 = PrecomputedDenseRetriever(exp_v3072, chunk_ids, chunk_lookup, map_blend_70_q)

    bm25_matn_raw = BM25Index(
        chunk_ids, [variant_text(chunk_lookup[cid], "matn") for cid in chunk_ids]
    )
    bm25_exp_raw = BM25Index(chunk_ids, exp_texts)
    bm25_matn = PrecomputedBM25Retriever(bm25_matn_raw, chunk_lookup, all_questions)
    bm25_exp = PrecomputedBM25Retriever(bm25_exp_raw, chunk_lookup, all_questions)
    bm25_matn_hyde = MappedBM25Retriever(bm25_matn_raw, chunk_lookup, q_to_pseudo)
    bm25_matn_concat = MappedBM25Retriever(bm25_matn_raw, chunk_lookup, q_to_concat)

    e2_configs = [
        ("BM25: doc_expansion field only (g38flash)", bm25_exp),
        (
            "BM25: matn + doc_expansion (RRF 1:1, g38flash)",
            MultiRRFHybridRetriever([bm25_matn, bm25_exp], [1.0, 1.0], 50),
        ),
        ("Dense: doc_expansion gemini-001 (1536) only (g38flash)", dense_exp_1536),
        ("Dense: doc_expansion gemini-001 (3072) only (g38flash)", dense_exp_3072),
        (
            "E2 (1536, g38flash): Dense_matn + Dense_exp (1:1)",
            MultiRRFHybridRetriever([dense_matn_1536, dense_exp_1536], [1.0, 1.0], 50),
        ),
        (
            "E2 (3072, g38flash): Dense_matn + Dense_exp (1:1)",
            MultiRRFHybridRetriever([dense_matn_3072, dense_exp_3072], [1.0, 1.0], 50),
        ),
        (
            "E2 (1536, g38flash): Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)",
            MultiRRFHybridRetriever(
                [dense_matn_1536, dense_exp_1536, bm25_matn, bm25_exp],
                [2.0, 1.0, 1.0, 1.0],
                50,
            ),
        ),
        (
            "E2 (3072, g38flash): Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)",
            MultiRRFHybridRetriever(
                [dense_matn_3072, dense_exp_3072, bm25_matn, bm25_exp],
                [2.0, 1.0, 1.0, 1.0],
                50,
            ),
        ),
        (
            "E2 (3072, g38flash): Dense_m + Dense_e + BM25_m + BM25_e (3:1:1:1)",
            MultiRRFHybridRetriever(
                [dense_matn_3072, dense_exp_3072, bm25_matn, bm25_exp],
                [3.0, 1.0, 1.0, 1.0],
                50,
            ),
        ),
        (
            "E2 (3072, g38flash): Dense_m + Dense_e + BM25_m + BM25_e (8:2:1:1)",
            MultiRRFHybridRetriever(
                [dense_matn_3072, dense_exp_3072, bm25_matn, bm25_exp],
                [8.0, 2.0, 1.0, 1.0],
                50,
            ),
        ),
    ]

    e4_configs = [
        ("E4 (g38flash): HyDE pseudo-matn only (RETRIEVAL_DOCUMENT -> Dense_m)", dense_matn_hyde_doc),
        ("E4 (g38flash): HyDE pseudo-matn only (RETRIEVAL_QUERY -> Dense_m)", dense_matn_hyde_q),
        ("E4 (g38flash): BM25_matn (HyDE pseudo-matn only)", bm25_matn_hyde),
        ("E4 (g38flash): BM25_matn (query + HyDE pseudo-matn)", bm25_matn_concat),
        ("E4 (g38flash): Dense_m (0.5*query + 0.5*HyDE_q)", dense_matn_blend50),
        ("E4 (g38flash): Dense_m (0.7*query + 0.3*HyDE_q)", dense_matn_blend70),
        ("E4 (g38flash): Dense_m (0.8*query + 0.2*HyDE_q)", dense_matn_blend80),
        (
            "E4 (g38flash): E2_g38 (2:1:1:1) + Dense_m(HyDE_q) (w=0.5)",
            MultiRRFHybridRetriever(
                [dense_matn_3072, dense_exp_3072, bm25_matn, bm25_exp, dense_matn_hyde_q],
                [2.0, 1.0, 1.0, 1.0, 0.5],
                50,
            ),
        ),
        (
            "E4 (g38flash): E2_g38 (2:1:1:1) + Dense_m(HyDE_q) (w=1.0)",
            MultiRRFHybridRetriever(
                [dense_matn_3072, dense_exp_3072, bm25_matn, bm25_exp, dense_matn_hyde_q],
                [2.0, 1.0, 1.0, 1.0, 1.0],
                50,
            ),
        ),
        (
            "E4 (g38flash): E2_g38 with blended query vector (0.7*q + 0.3*HyDE_q) (2:1:1:1)",
            MultiRRFHybridRetriever(
                [dense_matn_blend70, dense_exp_blend70, bm25_matn, bm25_exp],
                [2.0, 1.0, 1.0, 1.0],
                50,
            ),
        ),
        (
            "E4 (g38flash): E2_g38 with blended query vector (0.7*q + 0.3*HyDE_q) (8:2:1:1)",
            MultiRRFHybridRetriever(
                [dense_matn_blend70, dense_exp_blend70, bm25_matn, bm25_exp],
                [8.0, 2.0, 1.0, 1.0],
                50,
            ),
        ),
    ]

    summary = {
        "e2_meta": e2_meta,
        "e4_meta": e4_meta,
        "e2_results": {"synthetic_eval_expanded": {}, "golden_expanded": {}},
        "e4_results": {"synthetic_eval_expanded": {}, "golden_expanded": {}},
    }

    for ds_name, items in [
        ("synthetic_eval_expanded", synth_items),
        ("golden_expanded", golden_items),
    ]:
        print(f"\n=== Step 4 E2 ({NEW_FLASH_MODEL}) on {ds_name} (n={len(items)}) ===")
        for name, ret in e2_configs:
            m = eval_retriever_dict(ret, items)
            summary["e2_results"][ds_name][name] = m
            print(
                f"{name:<62} hit@1={m['hit@1']:.1%} hit@3={m['hit@3']:.1%} "
                f"hit@5={m['hit@5']:.1%} hit@10={m['hit@10']:.1%} "
                f"recall@50={m['recall@50']:.1%} ({m['hits50_count']}) MRR@10={m['MRR@10']:.3f}"
            )

        print(f"\n=== Step 4 E4 ({NEW_FLASH_MODEL}) on {ds_name} (n={len(items)}) ===")
        for name, ret in e4_configs:
            m = eval_retriever_dict(ret, items)
            summary["e4_results"][ds_name][name] = m
            print(
                f"{name:<68} hit@1={m['hit@1']:.1%} hit@3={m['hit@3']:.1%} "
                f"hit@5={m['hit@5']:.1%} hit@10={m['hit@10']:.1%} "
                f"recall@50={m['recall@50']:.1%} ({m['hits50_count']}) MRR@10={m['MRR@10']:.3f}"
            )

    with open(STEP4_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSaved Step 4 results -> {STEP4_RESULTS_PATH}")


if __name__ == "__main__":
    main()
