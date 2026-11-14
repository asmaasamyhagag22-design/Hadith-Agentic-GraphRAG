"""
E3 — Reranker + candidate depth (10 / 30 / 50) comparison & paired McNemar test.

Compares three cross-encoder rerankers on top of the best E2 retriever
(`E2 (3072): Dense_m + Dense_e + BM25_m + BM25_e (2:1:1:1)`, plus E1 dense):
1. `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (`mmarco`)
2. `BAAI/bge-reranker-v2-m3` (`bge`)
3. `Qwen/Qwen3-Reranker-0.6B` (`qwen3`, using its official `AutoModelForCausalLM`
   yes/no logit scorer with lossless query-prefix KV caching)

Evaluates depths `top_k_in` in {10, 30, 50} on `synthetic_eval_expanded.jsonl`
(dev, n=224) and `golden_expanded.jsonl` (n=27), and runs exact two-sided
paired McNemar tests on dev (`hit@1` and `hit@5`) to decide which reranker
and depth to keep.
"""

import argparse
import json
import math
import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import CrossEncoder
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import IDS_MATN, PROCESSED_DIR, VECTORS_MATN
from embed import indexable_chunks, load_chunks
from embed_vertex_e1 import PrecomputedDenseRetriever
from evaluate import answerable, load_golden
from experiment_e0_gold_expansion import (
    GOLDEN_EXPANDED_PATH,
    SYNTHETIC_EXPANDED_PATH,
)
from experiment_e1_dense_models import MultiRRFHybridRetriever
from experiment_e2_doc_expansion import (
    DOC_EXPANSIONS_PATH,
    PrecomputedBM25Retriever,
)
from experiment_variants import variant_text
from lexical import BM25Index
from rerank import MAX_LENGTH, MMARCO, document_for_reranking
from retrieve import HybridRetriever, Retriever, load_chunk_lookup

BGE_SNAPSHOT = (
    "/mnt/data/hf_cache/models--BAAI--bge-reranker-v2-m3/"
    "snapshots/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
)
QWEN3_SNAPSHOT = (
    "/home/asmaa/.cache/huggingface/hub/models--Qwen--Qwen3-Reranker-0.6B/"
    "snapshots/e61197ed45024b0ed8a2d74b80b4d909f1255473"
)

CANDIDATES_CACHE_PATH = PROCESSED_DIR / "e3_candidate_pools.pkl"
RESULTS_JSON_PATH = PROCESSED_DIR / "e3_results.json"

QWEN3_PREFIX = (
    "<|im_start|>system\nJudge whether the Document meets the requirements "
    "based on the Query and the Instruct provided. Note that the answer can "
    'only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
)
QWEN3_SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
QWEN3_INSTRUCT = (
    "Given a web search query, retrieve relevant passages that answer the query"
)


def build_or_load_candidate_pools():
    if CANDIDATES_CACHE_PATH.exists():
        with open(CANDIDATES_CACHE_PATH, "rb") as f:
            return pickle.load(f)

    all_chunks = load_chunks()
    idx_chunks = indexable_chunks(all_chunks)
    chunk_ids = [str(c["id"]) for c in idx_chunks]
    chunk_lookup = load_chunk_lookup()

    golden_items = answerable(load_golden(GOLDEN_EXPANDED_PATH))
    synth_items = answerable(load_golden(SYNTHETIC_EXPANDED_PATH))
    all_questions = list(
        dict.fromkeys([it["question"] for it in golden_items + synth_items])
    )

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

    g001_3072 = np.load(PROCESSED_DIR / "vectors_matn_gemini001_3072.npy")
    exp_v3072 = np.load(PROCESSED_DIR / "vectors_expansion_gemini001_3072.npy")
    g001_q = np.load(PROCESSED_DIR / "queries_gemini001.npz", allow_pickle=True)
    q_list = list(g001_q["questions"])
    v3072_q = g001_q["vec3072"]
    q_map_3072 = {q: v3072_q[i] for i, q in enumerate(q_list)}

    dense_matn_3072 = PrecomputedDenseRetriever(
        g001_3072, chunk_ids, chunk_lookup, q_map_3072
    )
    dense_exp_3072 = PrecomputedDenseRetriever(
        exp_v3072, chunk_ids, chunk_lookup, q_map_3072
    )

    e2_4field = MultiRRFHybridRetriever(
        [dense_matn_3072, dense_exp_3072, bm25_matn, bm25_exp],
        weights=[2.0, 1.0, 1.0, 1.0],
        candidates=50,
    )
    e2_2field = MultiRRFHybridRetriever(
        [dense_matn_3072, dense_exp_3072],
        weights=[1.0, 1.0],
        candidates=50,
    )

    pools = {
        "E2_4field_2_1_1_1": {},
        "E2_2field_1_1": {},
        "E1_dense_3072": {},
    }
    unique_pairs = set()
    for q in all_questions:
        c_4f = e2_4field.search(q, k=50)
        c_2f = e2_2field.search(q, k=50)
        c_e1 = dense_matn_3072.search(q, k=50)
        pools["E2_4field_2_1_1_1"][q] = c_4f
        pools["E2_2field_1_1"][q] = c_2f
        pools["E1_dense_3072"][q] = c_e1
        for c in c_4f:
            unique_pairs.add((q, str(c["chunk_id"])))
        for c in c_2f:
            unique_pairs.add((q, str(c["chunk_id"])))
        for c in c_e1:
            unique_pairs.add((q, str(c["chunk_id"])))

    doc_texts = {
        cid: document_for_reranking(chunk_lookup[cid]) for cid in chunk_ids
    }
    payload = {
        "pools": pools,
        "unique_pairs": sorted(unique_pairs),
        "doc_texts": doc_texts,
    }
    with open(CANDIDATES_CACHE_PATH, "wb") as f:
        pickle.dump(payload, f)
    print(
        f"Saved candidate pools ({len(unique_pairs)} unique pairs across 3 base retrievers) "
        f"-> {CANDIDATES_CACHE_PATH}"
    )
    return payload


def load_cross_encoder(reranker_key, threads=4):
    torch.set_num_threads(threads)
    if reranker_key == "mmarco":
        return CrossEncoder(
            MMARCO, max_length=MAX_LENGTH, local_files_only=True
        )
    if reranker_key == "bge":
        return CrossEncoder(
            BGE_SNAPSHOT,
            max_length=MAX_LENGTH,
            model_kwargs={"dtype": torch.float32},
        )
    raise ValueError(f"Use score_qwen3_shard for qwen3, got: {reranker_key}")


def score_qwen3_shard(shard=0, num_shards=1, threads=4):
    """
    Score Qwen3-Reranker-0.6B using its official CausalLM yes/no logit difference
    (`logits[:, -1, yes_id] - logits[:, -1, no_id]`) with lossless query-prefix
    KV caching (`base_kv.crop(prefix_len)` across the 50 candidate docs per query).
    """
    torch.set_num_threads(threads)
    payload = build_or_load_candidate_pools()
    doc_texts = payload["doc_texts"]
    pool = payload["pools"]["E2_4field_2_1_1_1"]
    all_questions = list(pool.keys())
    shard_questions = all_questions[shard::num_shards]

    out_path = PROCESSED_DIR / f"e3_scores_qwen3_s{shard}_of_{num_shards}.pkl"
    scores = {}
    if out_path.exists():
        with open(out_path, "rb") as f:
            scores = pickle.load(f)

    todo_qs = [
        q
        for q in shard_questions
        if any((q, str(c["chunk_id"])) not in scores for c in pool[q])
    ]
    print(
        f"[qwen3 shard {shard}/{num_shards}] "
        f"total_qs={len(shard_questions)}, todo_qs={len(todo_qs)}"
    )
    if not todo_qs:
        return out_path

    tok = AutoTokenizer.from_pretrained(QWEN3_SNAPSHOT)
    model = AutoModelForCausalLM.from_pretrained(
        QWEN3_SNAPSHOT, dtype=torch.float32
    ).eval()
    true_id = tok.convert_tokens_to_ids("yes")
    false_id = tok.convert_tokens_to_ids("no")
    prefix_ids = tok.encode(QWEN3_PREFIX, add_special_tokens=False)
    suffix_ids = tok.encode(QWEN3_SUFFIX, add_special_tokens=False)

    # Pre-tokenize unique candidate docs in this shard once
    needed_cids = {
        str(c["chunk_id"]) for q in todo_qs for c in pool[q]
    }
    doc_tok_cache = {
        cid: tok.encode(" " + doc_texts[cid], add_special_tokens=False)
        for cid in needed_cids
    }

    t0 = time.perf_counter()
    for q_i, q in enumerate(todo_qs, start=1):
        q_head_ids = prefix_ids + tok.encode(
            f"<Instruct>: {QWEN3_INSTRUCT}\n<Query>: {q}\n<Document>:",
            add_special_tokens=False,
        )
        prefix_len = len(q_head_ids)
        max_doc_len = max(16, MAX_LENGTH - prefix_len - len(suffix_ids))

        with torch.no_grad():
            pref_out = model(
                input_ids=torch.tensor([q_head_ids]), use_cache=True
            )
            base_kv = pref_out.past_key_values

            for c in pool[q]:
                cid = str(c["chunk_id"])
                pair = (q, cid)
                if pair in scores:
                    continue
                base_kv.crop(prefix_len)
                tail = doc_tok_cache[cid][:max_doc_len] + suffix_ids
                out = model(
                    input_ids=torch.tensor([tail]),
                    past_key_values=base_kv,
                    logits_to_keep=1,
                )
                logits = out.logits[0, -1]
                scores[pair] = float(logits[true_id] - logits[false_id])

        if q_i % 5 == 0 or q_i == len(todo_qs):
            with open(out_path, "wb") as f:
                pickle.dump(scores, f)
            elapsed = time.perf_counter() - t0
            rate_q = q_i / elapsed if elapsed > 0 else 0
            eta_m = ((len(todo_qs) - q_i) / rate_q) / 60 if rate_q > 0 else 0
            print(
                f"  [qwen3 s{shard}] {q_i}/{len(todo_qs)} queries "
                f"({q_i/len(todo_qs):.1%}) | {rate_q*50:.1f} pairs/s | "
                f"elapsed={elapsed:.1f}s | ETA={eta_m:.1f}m",
                flush=True,
            )

    return out_path


def score_shard(reranker_key, shard=0, num_shards=1, threads=4, primary_only=True):
    if reranker_key == "qwen3":
        return score_qwen3_shard(
            shard=shard, num_shards=num_shards, threads=threads
        )

    payload = build_or_load_candidate_pools()
    doc_texts = payload["doc_texts"]
    if primary_only:
        primary_pairs = []
        seen = set()
        for q, cands in payload["pools"]["E2_4field_2_1_1_1"].items():
            for c in cands:
                pair = (q, str(c["chunk_id"]))
                if pair not in seen:
                    seen.add(pair)
                    primary_pairs.append(pair)
        all_pairs = primary_pairs
    else:
        all_pairs = payload["unique_pairs"]

    all_pairs_sorted = sorted(
        all_pairs, key=lambda p: len(p[0]) + len(doc_texts[p[1]])
    )
    shard_pairs = all_pairs_sorted[shard::num_shards]

    out_path = PROCESSED_DIR / f"e3_scores_{reranker_key}_s{shard}_of_{num_shards}.pkl"
    scores = {}
    if out_path.exists():
        with open(out_path, "rb") as f:
            scores = pickle.load(f)

    todo = [p for p in shard_pairs if p not in scores]
    print(
        f"[{reranker_key} shard {shard}/{num_shards}] "
        f"total={len(shard_pairs)}, cached={len(scores)}, todo={len(todo)}"
    )
    if not todo:
        return out_path

    ce = load_cross_encoder(reranker_key, threads=threads)
    batch_size = 16
    chunk_step = 320
    t0 = time.perf_counter()

    for start in range(0, len(todo), chunk_step):
        sub = todo[start : start + chunk_step]
        inputs = [(q, doc_texts[cid]) for q, cid in sub]
        preds = ce.predict(inputs, batch_size=batch_size, show_progress_bar=False)
        for pair, sc in zip(sub, preds):
            scores[pair] = float(sc)

        with open(out_path, "wb") as f:
            pickle.dump(scores, f)

        done = start + len(sub)
        elapsed = time.perf_counter() - t0
        rate = done / elapsed if elapsed > 0 else 0
        eta = (len(todo) - done) / rate if rate > 0 else 0
        print(
            f"  [{reranker_key} s{shard}] {done}/{len(todo)} "
            f"({done/len(todo):.1%}) | {rate:.1f} pairs/s | "
            f"elapsed={elapsed:.1f}s | ETA={eta/60:.1f}m",
            flush=True,
        )

    return out_path


def load_merged_scores(reranker_key):
    merged = {}
    for p in sorted(PROCESSED_DIR.glob(f"e3_scores_{reranker_key}_s*.pkl")):
        with open(p, "rb") as f:
            merged.update(pickle.load(f))
    single = PROCESSED_DIR / f"e3_scores_{reranker_key}.pkl"
    if single.exists():
        with open(single, "rb") as f:
            merged.update(pickle.load(f))
    with open(single, "wb") as f:
        pickle.dump(merged, f)
    return merged


def mcnemar_exact_p(b, c):
    """Exact two-sided binomial McNemar p-value."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def evaluate_pool_with_scores(pool_by_q, scores_dict, items, top_k_in=50):
    """
    Evaluate reranked top_k_in candidates (or un-reranked when scores_dict is None).
    Returns metrics dict and per-question first-hit rank list.
    """
    k_values = (1, 3, 5, 10, 50)
    hits = {k: 0 for k in k_values}
    set_recalls_50 = []
    reciprocal_ranks_10 = []
    reciprocal_ranks_50 = []
    ranks = []

    for item in items:
        q = item["question"]
        expected = set(item["hadith_ids"])
        candidates = list(pool_by_q[q])

        if scores_dict is not None:
            head = candidates[:top_k_in]
            tail = candidates[top_k_in:]
            order = sorted(
                range(len(head)),
                key=lambda i: float(scores_dict[(q, str(head[i]["chunk_id"]))]),
                reverse=True,
            )
            reranked_head = [head[i] for i in order]
            full_list = reranked_head + tail
            eval_top = reranked_head
        else:
            full_list = candidates[:50]
            eval_top = candidates[:top_k_in]

        returned_top = [r["hadith_id"] for r in eval_top]
        returned_50 = [r["hadith_id"] for r in full_list[:50]]

        first_hit_top = next(
            (i + 1 for i, h in enumerate(returned_top) if h in expected),
            None,
        )
        first_hit_50 = next(
            (i + 1 for i, h in enumerate(returned_50) if h in expected),
            None,
        )
        ranks.append(first_hit_top)

        for k in (1, 3, 5, 10):
            if first_hit_top is not None and first_hit_top <= k:
                hits[k] += 1
        if first_hit_50 is not None and first_hit_50 <= 50:
            hits[50] += 1

        found_50 = len(expected & set(returned_50[:50]))
        set_recalls_50.append(found_50 / len(expected) if expected else 0.0)
        reciprocal_ranks_10.append(
            1.0 / first_hit_top
            if (first_hit_top is not None and first_hit_top <= 10)
            else 0.0
        )
        reciprocal_ranks_50.append(
            1.0 / first_hit_50 if first_hit_50 is not None else 0.0
        )

    total = len(items)
    return (
        {
            "hit@1": round(hits[1] / total, 4),
            "hit@3": round(hits[3] / total, 4),
            "hit@5": round(hits[5] / total, 4),
            "hit@10": round(hits[10] / total, 4),
            "recall@50": round(hits[50] / total, 4),
            "hits1_count": hits[1],
            "hits5_count": hits[5],
            "hits10_count": hits[10],
            "hits50_count": hits[50],
            "setR@50": round(sum(set_recalls_50) / total, 4),
            "MRR@10": round(sum(reciprocal_ranks_10) / total, 4),
            "MRR@50": round(sum(reciprocal_ranks_50) / total, 4),
        },
        ranks,
    )


def pair_mcnemar(ranks_a, ranks_b, k):
    a_only = 0
    b_only = 0
    both = 0
    neither = 0
    for ra, rb in zip(ranks_a, ranks_b):
        ha = ra is not None and ra <= k
        hb = rb is not None and rb <= k
        if ha and hb:
            both += 1
        elif ha and not hb:
            a_only += 1
        elif hb and not ha:
            b_only += 1
        else:
            neither += 1
    return {
        "k": k,
        "a_only": a_only,
        "b_only": b_only,
        "both": both,
        "neither": neither,
        "p_value": round(mcnemar_exact_p(a_only, b_only), 4),
    }


def measure_latency_and_truncation(payload):
    """Measure seconds_per_query at depths 10, 30, 50 on a 3-question sample."""
    doc_texts = payload["doc_texts"]
    pool = payload["pools"]["E2_4field_2_1_1_1"]
    sample_qs = list(pool.keys())[:3]
    stats = {}

    for r_key in ("mmarco", "bge"):
        ce = load_cross_encoder(r_key, threads=4)
        tok = ce.tokenizer
        trunc = 0
        scored = 0
        for q, cands in pool.items():
            for c in cands:
                scored += 1
                doc = doc_texts[str(c["chunk_id"])]
                if len(tok(doc, truncation=False)["input_ids"]) > MAX_LENGTH:
                    trunc += 1

        latencies = {}
        for depth in (10, 30, 50):
            times = []
            for q in sample_qs:
                cands = pool[q][:depth]
                pairs = [(q, doc_texts[str(c["chunk_id"])]) for c in cands]
                t0 = time.perf_counter()
                _ = ce.predict(
                    pairs,
                    batch_size=16 if r_key == "mmarco" else 4,
                    show_progress_bar=False,
                )
                times.append(time.perf_counter() - t0)
            latencies[str(depth)] = round(sum(times) / len(times), 2)

        stats[r_key] = {
            "seconds_per_query": latencies,
            "truncated": trunc,
            "scored": scored,
        }
        print(f"Latency & truncation [{r_key}]: {stats[r_key]}")

    # Qwen3 latency & truncation
    tok = AutoTokenizer.from_pretrained(QWEN3_SNAPSHOT)
    model = AutoModelForCausalLM.from_pretrained(
        QWEN3_SNAPSHOT, dtype=torch.float32
    ).eval()
    true_id = tok.convert_tokens_to_ids("yes")
    false_id = tok.convert_tokens_to_ids("no")
    prefix_ids = tok.encode(QWEN3_PREFIX, add_special_tokens=False)
    suffix_ids = tok.encode(QWEN3_SUFFIX, add_special_tokens=False)

    trunc = 0
    scored = 0
    for q, cands in pool.items():
        for c in cands:
            scored += 1
            doc = doc_texts[str(c["chunk_id"])]
            if len(tok.encode(doc, add_special_tokens=False)) > MAX_LENGTH:
                trunc += 1

    latencies = {}
    for depth in (10, 30, 50):
        times = []
        for q in sample_qs:
            cands = pool[q][:depth]
            t0 = time.perf_counter()
            q_head_ids = prefix_ids + tok.encode(
                f"<Instruct>: {QWEN3_INSTRUCT}\n<Query>: {q}\n<Document>:",
                add_special_tokens=False,
            )
            prefix_len = len(q_head_ids)
            max_doc_len = max(16, MAX_LENGTH - prefix_len - len(suffix_ids))
            with torch.no_grad():
                pref_out = model(
                    input_ids=torch.tensor([q_head_ids]), use_cache=True
                )
                base_kv = pref_out.past_key_values
                for c in cands:
                    base_kv.crop(prefix_len)
                    d_ids = tok.encode(
                        " " + doc_texts[str(c["chunk_id"])],
                        add_special_tokens=False,
                    )[:max_doc_len]
                    _ = model(
                        input_ids=torch.tensor([d_ids + suffix_ids]),
                        past_key_values=base_kv,
                        logits_to_keep=1,
                    )
            times.append(time.perf_counter() - t0)
        latencies[str(depth)] = round(sum(times) / len(times), 2)

    stats["qwen3"] = {
        "seconds_per_query": latencies,
        "truncated": trunc,
        "scored": scored,
    }
    print(f"Latency & truncation [qwen3]: {stats['qwen3']}")
    return stats


def run_evaluation():
    payload = build_or_load_candidate_pools()
    pool = payload["pools"]["E2_4field_2_1_1_1"]

    scores_by_model = {
        "mmarco": load_merged_scores("mmarco"),
        "bge": load_merged_scores("bge"),
        "qwen3": load_merged_scores("qwen3"),
    }

    golden_items = answerable(load_golden(GOLDEN_EXPANDED_PATH))
    synth_items = answerable(load_golden(SYNTHETIC_EXPANDED_PATH))

    summary = {"results": {}, "mcnemar_dev": {}, "mcnemar_golden": {}}
    ranks_store = {"synthetic_eval_expanded": {}, "golden_expanded": {}}

    for ds_name, items in [
        ("synthetic_eval_expanded", synth_items),
        ("golden_expanded", golden_items),
    ]:
        summary["results"][ds_name] = {}
        print(f"\n=== {ds_name} (n={len(items)}) ===")
        print(
            f"{'Configuration':<48} {'hit@1':<7} {'hit@3':<7} {'hit@5':<7} "
            f"{'hit@10':<7} {'recall@50':<10} {'MRR@10':<7} {'MRR@50':<7}"
        )
        print("-" * 108)

        base_m, base_r = evaluate_pool_with_scores(pool, None, items, top_k_in=50)
        base_label = "E2 Base (2:1:1:1, no rerank)"
        summary["results"][ds_name][base_label] = base_m
        ranks_store[ds_name][base_label] = base_r
        print(
            f"{base_label:<48} "
            f"{base_m['hit@1']:<7.1%} {base_m['hit@3']:<7.1%} {base_m['hit@5']:<7.1%} "
            f"{base_m['hit@10']:<7.1%} {base_m['recall@50']:<10.1%} "
            f"{base_m['MRR@10']:<7.3f} {base_m['MRR@50']:<7.3f}"
        )

        e1_m, e1_r = evaluate_pool_with_scores(
            payload["pools"]["E1_dense_3072"], None, items, top_k_in=50
        )
        e1_label = "E1 Dense gemini-001 (3072, no rerank)"
        summary["results"][ds_name][e1_label] = e1_m
        ranks_store[ds_name][e1_label] = e1_r
        print(
            f"{e1_label:<48} "
            f"{e1_m['hit@1']:<7.1%} {e1_m['hit@3']:<7.1%} {e1_m['hit@5']:<7.1%} "
            f"{e1_m['hit@10']:<7.1%} {e1_m['recall@50']:<10.1%} "
            f"{e1_m['MRR@10']:<7.3f} {e1_m['MRR@50']:<7.3f}"
        )

        for r_key, r_title in [
            ("mmarco", "mmarco-mMiniLMv2"),
            ("bge", "bge-reranker-v2-m3"),
            ("qwen3", "Qwen3-Reranker-0.6B"),
        ]:
            for depth in (10, 30, 50):
                label = f"E2 + {r_title} (top {depth})"
                m, r = evaluate_pool_with_scores(
                    pool, scores_by_model[r_key], items, top_k_in=depth
                )
                summary["results"][ds_name][label] = m
                ranks_store[ds_name][label] = r
                print(
                    f"{label:<48} "
                    f"{m['hit@1']:<7.1%} {m['hit@3']:<7.1%} {m['hit@5']:<7.1%} "
                    f"{m['hit@10']:<7.1%} {m['recall@50']:<10.1%} "
                    f"{m['MRR@10']:<7.3f} {m['MRR@50']:<7.3f}"
                )

    comparisons = [
        # Against current default reranker setting: mmarco (top 10)
        ("E2 + mmarco-mMiniLMv2 (top 30)", "E2 + mmarco-mMiniLMv2 (top 10)"),
        ("E2 + mmarco-mMiniLMv2 (top 50)", "E2 + mmarco-mMiniLMv2 (top 10)"),
        ("E2 + bge-reranker-v2-m3 (top 10)", "E2 + mmarco-mMiniLMv2 (top 10)"),
        ("E2 + bge-reranker-v2-m3 (top 30)", "E2 + mmarco-mMiniLMv2 (top 10)"),
        ("E2 + bge-reranker-v2-m3 (top 50)", "E2 + mmarco-mMiniLMv2 (top 10)"),
        ("E2 + Qwen3-Reranker-0.6B (top 10)", "E2 + mmarco-mMiniLMv2 (top 10)"),
        ("E2 + Qwen3-Reranker-0.6B (top 30)", "E2 + mmarco-mMiniLMv2 (top 10)"),
        ("E2 + Qwen3-Reranker-0.6B (top 50)", "E2 + mmarco-mMiniLMv2 (top 10)"),
        # Same-depth pairwise comparisons
        ("E2 + bge-reranker-v2-m3 (top 30)", "E2 + mmarco-mMiniLMv2 (top 30)"),
        ("E2 + bge-reranker-v2-m3 (top 50)", "E2 + mmarco-mMiniLMv2 (top 50)"),
        ("E2 + bge-reranker-v2-m3 (top 10)", "E2 + Qwen3-Reranker-0.6B (top 10)"),
        ("E2 + bge-reranker-v2-m3 (top 30)", "E2 + Qwen3-Reranker-0.6B (top 30)"),
        ("E2 + bge-reranker-v2-m3 (top 50)", "E2 + Qwen3-Reranker-0.6B (top 50)"),
        ("E2 + Qwen3-Reranker-0.6B (top 30)", "E2 + mmarco-mMiniLMv2 (top 30)"),
        ("E2 + Qwen3-Reranker-0.6B (top 50)", "E2 + mmarco-mMiniLMv2 (top 50)"),
        # Depth comparisons within each reranker
        ("E2 + bge-reranker-v2-m3 (top 30)", "E2 + bge-reranker-v2-m3 (top 10)"),
        ("E2 + bge-reranker-v2-m3 (top 50)", "E2 + bge-reranker-v2-m3 (top 30)"),
        ("E2 + bge-reranker-v2-m3 (top 50)", "E2 + bge-reranker-v2-m3 (top 10)"),
        ("E2 + Qwen3-Reranker-0.6B (top 30)", "E2 + Qwen3-Reranker-0.6B (top 10)"),
        ("E2 + Qwen3-Reranker-0.6B (top 50)", "E2 + Qwen3-Reranker-0.6B (top 30)"),
        ("E2 + Qwen3-Reranker-0.6B (top 50)", "E2 + Qwen3-Reranker-0.6B (top 10)"),
        ("E2 + mmarco-mMiniLMv2 (top 50)", "E2 + mmarco-mMiniLMv2 (top 30)"),
        # Against un-reranked E2 Base (2:1:1:1) and E1 Dense (3072)
        ("E2 + mmarco-mMiniLMv2 (top 10)", "E2 Base (2:1:1:1, no rerank)"),
        ("E2 + mmarco-mMiniLMv2 (top 30)", "E2 Base (2:1:1:1, no rerank)"),
        ("E2 + mmarco-mMiniLMv2 (top 50)", "E2 Base (2:1:1:1, no rerank)"),
        ("E2 + bge-reranker-v2-m3 (top 10)", "E2 Base (2:1:1:1, no rerank)"),
        ("E2 + bge-reranker-v2-m3 (top 30)", "E2 Base (2:1:1:1, no rerank)"),
        ("E2 + bge-reranker-v2-m3 (top 50)", "E2 Base (2:1:1:1, no rerank)"),
        ("E2 + Qwen3-Reranker-0.6B (top 10)", "E2 Base (2:1:1:1, no rerank)"),
        ("E2 + Qwen3-Reranker-0.6B (top 30)", "E2 Base (2:1:1:1, no rerank)"),
        ("E2 + Qwen3-Reranker-0.6B (top 50)", "E2 Base (2:1:1:1, no rerank)"),
        ("E2 + bge-reranker-v2-m3 (top 30)", "E1 Dense gemini-001 (3072, no rerank)"),
        ("E2 + bge-reranker-v2-m3 (top 50)", "E1 Dense gemini-001 (3072, no rerank)"),
        ("E2 + Qwen3-Reranker-0.6B (top 30)", "E1 Dense gemini-001 (3072, no rerank)"),
        ("E2 + Qwen3-Reranker-0.6B (top 50)", "E1 Dense gemini-001 (3072, no rerank)"),
    ]

    print("\n=== Paired McNemar Tests on Dev (n=224) ===")
    for a, b in comparisons:
        key = f"{a} vs {b}"
        summary["mcnemar_dev"][key] = {
            "hit@1": pair_mcnemar(
                ranks_store["synthetic_eval_expanded"][a],
                ranks_store["synthetic_eval_expanded"][b],
                1,
            ),
            "hit@5": pair_mcnemar(
                ranks_store["synthetic_eval_expanded"][a],
                ranks_store["synthetic_eval_expanded"][b],
                5,
            ),
        }
        summary["mcnemar_golden"][key] = {
            "hit@1": pair_mcnemar(
                ranks_store["golden_expanded"][a],
                ranks_store["golden_expanded"][b],
                1,
            ),
            "hit@5": pair_mcnemar(
                ranks_store["golden_expanded"][a],
                ranks_store["golden_expanded"][b],
                5,
            ),
        }
        m1 = summary["mcnemar_dev"][key]["hit@1"]
        m5 = summary["mcnemar_dev"][key]["hit@5"]
        print(
            f"  {key:<78} | "
            f"hit@1: {m1['a_only']:>2} vs {m1['b_only']:<2} (p={m1['p_value']:.4f}) | "
            f"hit@5: {m5['a_only']:>2} vs {m5['b_only']:<2} (p={m5['p_value']:.4f})"
        )

    summary["latency_and_truncation"] = measure_latency_and_truncation(payload)

    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSaved E3 results -> {RESULTS_JSON_PATH}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prep", action="store_true")
    parser.add_argument("--reranker", choices=["mmarco", "bge", "qwen3"])
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--evaluate", action="store_true")
    args = parser.parse_args()

    if args.prep:
        build_or_load_candidate_pools()
    elif args.reranker:
        score_shard(
            args.reranker,
            shard=args.shard,
            num_shards=args.num_shards,
            threads=args.threads,
        )
    elif args.evaluate:
        run_evaluation()
    else:
        build_or_load_candidate_pools()
        for r in ("mmarco", "qwen3", "bge"):
            score_shard(r, shard=0, num_shards=1, threads=4)
        run_evaluation()


if __name__ == "__main__":
    main()
