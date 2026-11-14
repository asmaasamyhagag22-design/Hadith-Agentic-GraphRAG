"""
Step 5 supplemental analysis:
1. Exact metric definitions & numerators/denominators on dev (n=224) and golden (n=27).
2. Full ablation table on dev (n=224) and golden (n=27):
   - Old pipeline (Hybrid + mmarco-mMiniLMv2-L12-H384-v1)
   - Old pipeline unreranked (Hybrid RRF 1:1)
   - New pipeline (Upgraded E5, RRF 8:2:1:1)
   - New pipeline without doc expansion (RRF 8:0:1:0 and 1:0:1:0)
   - New pipeline without HyDE (RRF 8:2:1:1, raw query)
   - New pipeline with equal RRF weights (RRF 1:1:1:1)
3. Complete RRF weight tuning grid on dev (n=224) and golden (n=27).
4. Deep leakage analysis on dev (n=224):
   - Item-level symmetric cosine similarity (gemini-embedding-001 3072d RETRIEVAL_QUERY)
     and chunk-level cosine similarity (RETRIEVAL_QUERY vs RETRIEVAL_DOCUMENT)
     between each dev query and the expansion texts of its GOLD hadith vs best NON-gold hadith.
   - Character 4-gram Jaccard (item-level and chunk-level) for GOLD vs best NON-gold hadith.
   - Near-duplicate count (cosine >= 0.90, plus >= 0.85 and >= 0.80) and separate dev gain
     for queries WITH vs WITHOUT a near-duplicate.
"""

import json
import pickle
import sys
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    GOLDEN_PATH,
    IDS_MATN,
    PROCESSED_DIR,
    SYNTHETIC_EVAL_PATH,
    VECTORS_MATN,
)
from embed_vertex_e1 import PrecomputedDenseRetriever, embed_batches, l2_norm
from experiment_e0_gold_expansion import (
    GOLDEN_EXPANDED_PATH,
    SYNTHETIC_EXPANDED_PATH,
)
from experiment_e1_dense_models import MultiRRFHybridRetriever
from experiment_e2_doc_expansion import PrecomputedBM25Retriever
from experiment_variants import variant_text
from lexical import BM25Index
from retrieve import load_chunk_lookup
from utils import strip_diacritics

OUT_JSON_PATH = PROCESSED_DIR / "e5_ablation_and_leakage.json"
ITEM_VECS_CACHE_PATH = PROCESSED_DIR / "leakage_item_vecs_gemini001.npz"


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def answerable(items):
    return [it for it in items if it.get("answerable", True)]


def eval_fast(retriever, items):
    """Compute hit@1, hit@3, hit@5, hit@10, recall@50 (hit@50), setR@50, MRR@10, MRR@50 with counts."""
    n = len(items)
    ranks10 = []
    ranks50 = []
    set_recalls50 = []

    for item in items:
        expected = set(item["hadith_ids"])
        res50 = retriever.search(item["question"], k=50)
        res10 = res50[:10]

        r10 = None
        for r in res10:
            if r["hadith_id"] in expected:
                r10 = r["rank"]
                break
        ranks10.append(r10)

        r50 = None
        found50 = set()
        for r in res50:
            if r["hadith_id"] in expected:
                found50.add(r["hadith_id"])
                if r50 is None:
                    r50 = r["rank"]
        ranks50.append(r50)
        set_recalls50.append(len(found50) / len(expected) if expected else 0.0)

    out = {"n": n}
    for k in (1, 3, 5, 10):
        c = sum(1 for r in ranks10 if r is not None and r <= k)
        out[f"hit@{k}_count"] = c
        out[f"hit@{k}"] = round(c / n, 4) if n else 0.0

    c50 = sum(1 for r in ranks50 if r is not None and r <= 50)
    out["recall@50_count"] = c50
    out["recall@50"] = round(c50 / n, 4) if n else 0.0
    out["setR@50"] = round(sum(set_recalls50) / n, 4) if n else 0.0
    out["MRR"] = (
        round(sum(1.0 / r for r in ranks10 if r is not None) / n, 4)
        if n
        else 0.0
    )
    out["MRR@50"] = (
        round(sum(1.0 / r for r in ranks50 if r is not None) / n, 4)
        if n
        else 0.0
    )
    return out, ranks10, ranks50


class CachedPrecomputedRerankedRetriever:
    """Uses saved e3_scores_mmarco.pkl to avoid running CPU cross-encoder again."""

    def __init__(self, base_hybrid, mmarco_scores, chunk_lookup, depth=10):
        self.base_hybrid = base_hybrid
        self.mmarco_scores = mmarco_scores
        self.chunk_lookup = chunk_lookup
        self.depth = depth

    def search(self, question, k=50):
        base_res = self.base_hybrid.search(question, k=max(k, self.depth))
        top_d = base_res[: self.depth]
        rest = base_res[self.depth :]
        q_scores = self.mmarco_scores.get(question, {})
        scored = sorted(
            top_d,
            key=lambda r: q_scores.get(str(r["chunk_id"]), -1e9),
            reverse=True,
        )
        combined = scored + rest
        out = []
        for idx, r in enumerate(combined[:k], start=1):
            rc = dict(r)
            rc["rank"] = idx
            out.append(rc)
        return out


def compute_char_4gram_jaccard(queries, exp_rows, gold_hids_per_query):
    """Fast inverted-index character 4-gram Jaccard for both item-level and chunk-level."""

    def grams_of(text):
        s = " ".join(strip_diacritics(text).split())
        if len(s) < 4:
            return {s} if s else set()
        return {s[i : i + 4] for i in range(len(s) - 3)}

    # Build chunk-level structures
    n_chunks = len(exp_rows)
    chunk_hids = np.array([r["hadith_id"] for r in exp_rows], dtype=np.int64)
    chunk_len = np.zeros(n_chunks, dtype=np.int32)
    chunk_inv = {}
    for c_idx, r in enumerate(exp_rows):
        gs = grams_of(r["expansion_text"])
        chunk_len[c_idx] = len(gs)
        for g in gs:
            chunk_inv.setdefault(g, []).append(c_idx)
    chunk_inv = {
        g: np.array(idxs, dtype=np.int32) for g, idxs in chunk_inv.items()
    }

    # Build item-level structures
    item_texts = []
    item_hids = []
    item_cids = []
    for r in exp_rows:
        h = r["hadith_id"]
        cid = str(r["chunk_id"])
        for it in r["items"]:
            item_texts.append(it)
            item_hids.append(h)
            item_cids.append(cid)

    n_items = len(item_texts)
    item_hids = np.array(item_hids, dtype=np.int64)
    item_len = np.zeros(n_items, dtype=np.int32)
    item_inv = {}
    for i_idx, it in enumerate(item_texts):
        gs = grams_of(it)
        item_len[i_idx] = len(gs)
        for g in gs:
            item_inv.setdefault(g, []).append(i_idx)
    item_inv = {
        g: np.array(idxs, dtype=np.int32) for g, idxs in item_inv.items()
    }

    gold_chunk_jacc = []
    nongold_chunk_jacc = []
    gold_item_jacc = []
    nongold_item_jacc = []
    top_nongold_item_indices_per_q = []

    for q, gold_hids in zip(queries, gold_hids_per_query):
        q_gs = grams_of(q)
        q_len = len(q_gs)

        # Chunk-level Jaccard
        c_inter = np.zeros(n_chunks, dtype=np.int32)
        for g in q_gs:
            idxs = chunk_inv.get(g)
            if idxs is not None:
                c_inter[idxs] += 1
        c_union = q_len + chunk_len - c_inter
        c_jacc = np.where(c_union > 0, c_inter / c_union, 0.0)
        c_gold_mask = np.isin(chunk_hids, list(gold_hids))
        gold_chunk_jacc.append(float(c_jacc[c_gold_mask].max()))
        nongold_chunk_jacc.append(float(c_jacc[~c_gold_mask].max()))

        # Item-level Jaccard
        i_inter = np.zeros(n_items, dtype=np.int32)
        for g in q_gs:
            idxs = item_inv.get(g)
            if idxs is not None:
                i_inter[idxs] += 1
        i_union = q_len + item_len - i_inter
        i_jacc = np.where(i_union > 0, i_inter / i_union, 0.0)
        i_gold_mask = np.isin(item_hids, list(gold_hids))
        gold_item_jacc.append(float(i_jacc[i_gold_mask].max()))
        nongold_item_jacc.append(float(i_jacc[~i_gold_mask].max()))

        # Keep top-15 non-gold items by Jaccard for candidate embedding
        ng_scores = np.where(~i_gold_mask, i_jacc, -1.0)
        top_ng = np.argpartition(-ng_scores, 15)[:15]
        top_nongold_item_indices_per_q.append(top_ng.tolist())

    return {
        "gold_chunk_jacc": np.array(gold_chunk_jacc),
        "nongold_chunk_jacc": np.array(nongold_chunk_jacc),
        "gold_item_jacc": np.array(gold_item_jacc),
        "nongold_item_jacc": np.array(nongold_item_jacc),
        "item_texts": item_texts,
        "item_hids": item_hids,
        "item_cids": item_cids,
        "top_nongold_item_indices_per_q": top_nongold_item_indices_per_q,
    }


def dist_summary(arr):
    arr = np.asarray(arr, dtype=np.float64)
    return {
        "min": round(float(arr.min()), 4),
        "p10": round(float(np.percentile(arr, 10)), 4),
        "p25": round(float(np.percentile(arr, 25)), 4),
        "median": round(float(np.median(arr)), 4),
        "mean": round(float(arr.mean()), 4),
        "std": round(float(arr.std()), 4),
        "p75": round(float(np.percentile(arr, 75)), 4),
        "p90": round(float(np.percentile(arr, 90)), 4),
        "max": round(float(arr.max()), 4),
        "count_ge_090": int((arr >= 0.90).sum()),
        "count_ge_085": int((arr >= 0.85).sum()),
        "count_ge_080": int((arr >= 0.80).sum()),
    }


def ensure_candidate_item_embeddings(candidate_texts):
    """Embed unique candidate expansion items with gemini-embedding-001 (RETRIEVAL_QUERY, 3072d)."""
    cached = {}
    if ITEM_VECS_CACHE_PATH.exists():
        data = np.load(ITEM_VECS_CACHE_PATH, allow_pickle=True)
        for t, v in zip(data["texts"], data["vecs"]):
            cached[str(t)] = v

    missing = [t for t in candidate_texts if t not in cached]
    if missing:
        print(
            f"Embedding {len(missing)} candidate expansion items with gemini-embedding-001 (RETRIEVAL_QUERY)...",
            flush=True,
        )
        client = genai.Client()
        clean_missing = [strip_diacritics(t) for t in missing]
        vecs = l2_norm(
            embed_batches(
                client,
                "gemini-embedding-001",
                clean_missing,
                "RETRIEVAL_QUERY",
            )
        )
        for t, v in zip(missing, vecs):
            cached[t] = v

        all_t = np.array(list(cached.keys()), dtype=object)
        all_v = np.array([cached[k] for k in all_t], dtype=np.float32)
        np.savez(ITEM_VECS_CACHE_PATH, texts=all_t, vecs=all_v)

    return cached


def analyze_leakage_for_model(
    model_tag,
    exp_rows,
    vec_exp_chunk,
    synth_orig,
    synth_exp,
    q_map_3072,
):
    queries = [it["question"] for it in synth_orig]
    gold_hids_orig = [set(it["hadith_ids"]) for it in synth_orig]
    gold_hids_exp = [set(it["hadith_ids"]) for it in synth_exp]

    # Use E0-expanded gold hadith set (which is a superset of original gold hadith)
    jacc_res = compute_char_4gram_jaccard(queries, exp_rows, gold_hids_exp)

    chunk_hids = np.array([r["hadith_id"] for r in exp_rows], dtype=np.int64)

    # 1. Chunk-level cosine (RETRIEVAL_QUERY vs RETRIEVAL_DOCUMENT)
    gold_chunk_cos = []
    nongold_chunk_cos = []
    top_nongold_chunk_indices_per_q = []

    for q, g_hids in zip(queries, gold_hids_exp):
        qv = q_map_3072[q]
        sims = vec_exp_chunk @ qv
        g_mask = np.isin(chunk_hids, list(g_hids))
        gold_chunk_cos.append(float(sims[g_mask].max()))
        nongold_chunk_cos.append(float(sims[~g_mask].max()))
        ng_sims = np.where(~g_mask, sims, -1.0)
        top_ng_c = np.argpartition(-ng_sims, 15)[:15]
        top_nongold_chunk_indices_per_q.append(top_ng_c.tolist())

    # 2. Gather candidate individual expansion items per query:
    #    - ALL items of ALL gold chunks (both orig and E0-expanded)
    #    - ALL items of top-15 non-gold chunks by chunk cosine
    #    - Top-15 non-gold items by 4-gram Jaccard
    item_texts = jacc_res["item_texts"]
    item_hids = jacc_res["item_hids"]

    # Map chunk index -> list of item indices
    chunk_to_item_idxs = []
    cursor = 0
    for r in exp_rows:
        k = len(r["items"])
        chunk_to_item_idxs.append(list(range(cursor, cursor + k)))
        cursor += k

    hid_to_item_idxs = {}
    for i_idx, h in enumerate(item_hids):
        hid_to_item_idxs.setdefault(int(h), []).append(i_idx)

    per_q_gold_item_idxs = []
    per_q_nongold_item_idxs = []
    needed_item_idxs = set()

    for q_i, g_hids in enumerate(gold_hids_exp):
        g_idxs = []
        for h in g_hids:
            g_idxs.extend(hid_to_item_idxs.get(int(h), []))
        per_q_gold_item_idxs.append(g_idxs)
        needed_item_idxs.update(g_idxs)

        ng_set = set(jacc_res["top_nongold_item_indices_per_q"][q_i])
        for c_idx in top_nongold_chunk_indices_per_q[q_i]:
            ng_set.update(chunk_to_item_idxs[c_idx])
        ng_list = sorted(ng_set)
        per_q_nongold_item_idxs.append(ng_list)
        needed_item_idxs.update(ng_list)

    unique_needed_texts = list(
        dict.fromkeys(item_texts[idx] for idx in sorted(needed_item_idxs))
    )
    text_to_vec = ensure_candidate_item_embeddings(unique_needed_texts)

    gold_item_cos = []
    nongold_item_cos = []
    best_gold_items = []
    best_nongold_items = []

    for q_i, q in enumerate(queries):
        qv = q_map_3072[q]
        g_idxs = per_q_gold_item_idxs[q_i]
        ng_idxs = per_q_nongold_item_idxs[q_i]

        g_vecs = np.array([text_to_vec[item_texts[idx]] for idx in g_idxs])
        g_sims = g_vecs @ qv
        best_g_pos = int(np.argmax(g_sims))
        gold_item_cos.append(float(g_sims[best_g_pos]))
        best_gold_items.append(item_texts[g_idxs[best_g_pos]])

        ng_vecs = np.array([text_to_vec[item_texts[idx]] for idx in ng_idxs])
        ng_sims = ng_vecs @ qv
        best_ng_pos = int(np.argmax(ng_sims))
        nongold_item_cos.append(float(ng_sims[best_ng_pos]))
        best_nongold_items.append(item_texts[ng_idxs[best_ng_pos]])

    gold_item_cos = np.array(gold_item_cos)
    nongold_item_cos = np.array(nongold_item_cos)
    gold_chunk_cos = np.array(gold_chunk_cos)
    nongold_chunk_cos = np.array(nongold_chunk_cos)

    return {
        "model": model_tag,
        "item_level_symmetric_cosine": {
            "gold": dist_summary(gold_item_cos),
            "best_non_gold": dist_summary(nongold_item_cos),
        },
        "chunk_level_asymmetric_cosine": {
            "gold": dist_summary(gold_chunk_cos),
            "best_non_gold": dist_summary(nongold_chunk_cos),
        },
        "item_level_char_4gram_jaccard": {
            "gold": dist_summary(jacc_res["gold_item_jacc"]),
            "best_non_gold": dist_summary(jacc_res["nongold_item_jacc"]),
        },
        "chunk_level_char_4gram_jaccard": {
            "gold": dist_summary(jacc_res["gold_chunk_jacc"]),
            "best_non_gold": dist_summary(jacc_res["nongold_chunk_jacc"]),
        },
        "gold_item_cos_per_q": gold_item_cos,
        "gold_chunk_cos_per_q": gold_chunk_cos,
        "gold_item_jacc_per_q": jacc_res["gold_item_jacc"],
        "best_gold_items": best_gold_items,
        "best_nongold_items": best_nongold_items,
    }


def subset_metrics_from_ranks(ranks10, ranks50, mask):
    idxs = [i for i, m in enumerate(mask) if m]
    n = len(idxs)
    if n == 0:
        return {"n": 0}
    out = {"n": n}
    for k in (1, 3, 5, 10):
        c = sum(1 for i in idxs if ranks10[i] is not None and ranks10[i] <= k)
        out[f"hit@{k}_count"] = c
        out[f"hit@{k}"] = round(c / n, 4)
    c50 = sum(1 for i in idxs if ranks50[i] is not None and ranks50[i] <= 50)
    out["recall@50_count"] = c50
    out["recall@50"] = round(c50 / n, 4)
    out["MRR"] = round(
        sum(1.0 / ranks10[i] for i in idxs if ranks10[i] is not None) / n, 4
    )
    return out


def main():
    chunk_lookup = load_chunk_lookup()
    with open(IDS_MATN, "r", encoding="utf-8") as f:
        chunk_ids = [str(cid) for cid in json.load(f)]

    golden_orig = answerable(load_jsonl(GOLDEN_PATH))
    golden_exp = answerable(load_jsonl(GOLDEN_EXPANDED_PATH))
    synth_orig = answerable(load_jsonl(SYNTHETIC_EVAL_PATH))
    synth_exp = answerable(load_jsonl(SYNTHETIC_EXPANDED_PATH))

    all_questions = list(
        dict.fromkeys([it["question"] for it in golden_orig + synth_orig])
    )

    # Load expansions
    exp_g38 = load_jsonl(PROCESSED_DIR / "doc_expansions_g38flash.jsonl")
    exp_g25 = load_jsonl(PROCESSED_DIR / "doc_expansions.jsonl")
    exp_g38_by_cid = {
        str(r["chunk_id"]): r["expansion_text"] for r in exp_g38
    }
    exp_g38_texts = [exp_g38_by_cid[cid] for cid in chunk_ids]

    # Load vectors
    g001_matn_3072 = np.load(PROCESSED_DIR / "vectors_matn_gemini001_3072.npy")
    g001_exp_g38_3072 = np.load(
        PROCESSED_DIR / "vectors_expansion_g38flash_gemini001_3072.npy"
    )
    g001_exp_g25_3072 = np.load(
        PROCESSED_DIR / "vectors_expansion_gemini001_3072.npy"
    )

    q_npz = np.load(PROCESSED_DIR / "queries_gemini001.npz", allow_pickle=True)
    q_list = list(q_npz["questions"])
    v3072_q = q_npz["vec3072"]
    q_idx = {str(q): i for i, q in enumerate(q_list)}
    v_orig_q3072 = l2_norm(np.array([v3072_q[q_idx[q]] for q in all_questions]))
    map_orig_3072 = {q: v_orig_q3072[i] for i, q in enumerate(all_questions)}

    h_npz = np.load(
        PROCESSED_DIR / "queries_hyde_g38flash_gemini001.npz", allow_pickle=True
    )
    h_q_list = list(h_npz["questions"])
    h_v_query = h_npz["vec_query_3072"]
    h_idx = {str(q): i for i, q in enumerate(h_q_list)}
    v_hyde_q3072 = l2_norm(
        np.array([h_v_query[h_idx[q]] for q in all_questions])
    )
    v_blend70_q3072 = l2_norm(0.7 * v_orig_q3072 + 0.3 * v_hyde_q3072)
    map_blend70_3072 = {
        q: v_blend70_q3072[i] for i, q in enumerate(all_questions)
    }

    # Build base retrievers
    dense_matn_raw = PrecomputedDenseRetriever(
        g001_matn_3072, chunk_ids, chunk_lookup, map_orig_3072
    )
    dense_exp_raw = PrecomputedDenseRetriever(
        g001_exp_g38_3072, chunk_ids, chunk_lookup, map_orig_3072
    )
    dense_matn_hyde = PrecomputedDenseRetriever(
        g001_matn_3072, chunk_ids, chunk_lookup, map_blend70_3072
    )
    dense_exp_hyde = PrecomputedDenseRetriever(
        g001_exp_g38_3072, chunk_ids, chunk_lookup, map_blend70_3072
    )

    bm25_matn_idx = BM25Index(
        chunk_ids, [variant_text(chunk_lookup[cid], "matn") for cid in chunk_ids]
    )
    bm25_exp_idx = BM25Index(chunk_ids, exp_g38_texts)
    bm25_matn = PrecomputedBM25Retriever(
        bm25_matn_idx, chunk_lookup, all_questions
    )
    bm25_exp = PrecomputedBM25Retriever(
        bm25_exp_idx, chunk_lookup, all_questions
    )

    # Legacy e5-base + BM25 + mmarco (cached per query for fast stratified evaluation)
    legacy_cache_path = PROCESSED_DIR / "legacy_top50_cache.pkl"
    if legacy_cache_path.exists():
        with open(legacy_cache_path, "rb") as f:
            legacy_cache = pickle.load(f)
    else:
        from rerank import DEFAULT_MODEL, MAX_LENGTH, document_for_reranking
        from sentence_transformers import CrossEncoder
        from utils import get_model

        print("Computing legacy Hybrid and Hybrid+mmarco top-50 per query (batched)...", flush=True)
        e5_vecs = l2_norm(np.load(VECTORS_MATN))
        q_e5_vecs = get_model().encode(
            [f"query: {strip_diacritics(q)}" for q in all_questions],
            normalize_embeddings=True,
            batch_size=64,
            show_progress_bar=False,
        )
        q_e5_map = {q: q_e5_vecs[i] for i, q in enumerate(all_questions)}
        fast_e5_dense = PrecomputedDenseRetriever(
            e5_vecs, chunk_ids, chunk_lookup, q_e5_map
        )
        fast_leg_hybrid = MultiRRFHybridRetriever(
            [fast_e5_dense, bm25_matn], [1.0, 1.0], 50
        )

        with open(PROCESSED_DIR / "e3_scores_mmarco.pkl", "rb") as f:
            mm_saved = pickle.load(f)

        ce = None
        legacy_cache = {"hybrid": {}, "mmarco": {}}
        missing_pairs = []
        missing_keys = []
        for q in all_questions:
            hyb_res = fast_leg_hybrid.search(q, k=50)
            legacy_cache["hybrid"][q] = hyb_res
            for r in hyb_res[:10]:
                cid = str(r["chunk_id"])
                if (q, cid) not in mm_saved:
                    missing_keys.append((q, cid))
                    missing_pairs.append(
                        (strip_diacritics(q), document_for_reranking(chunk_lookup[cid]))
                    )

        if missing_pairs:
            print(f"Scoring {len(missing_pairs)} missing mmarco pairs...", flush=True)
            ce = CrossEncoder(DEFAULT_MODEL, max_length=MAX_LENGTH)
            new_scores = ce.predict(missing_pairs, batch_size=64, show_progress_bar=False)
            for k_pair, sc in zip(missing_keys, new_scores):
                mm_saved[k_pair] = float(sc)

        for q in all_questions:
            hyb_res = legacy_cache["hybrid"][q]
            top10 = sorted(
                hyb_res[:10],
                key=lambda r: mm_saved[(q, str(r["chunk_id"]))],
                reverse=True,
            )
            combined = top10 + hyb_res[10:]
            reranked = []
            for idx, r in enumerate(combined, start=1):
                rc = dict(r)
                rc["rank"] = idx
                reranked.append(rc)
            legacy_cache["mmarco"][q] = reranked

        with open(legacy_cache_path, "wb") as f:
            pickle.dump(legacy_cache, f)

    class CachedDictRetriever:
        def __init__(self, q_dict):
            self.q_dict = q_dict

        def search(self, question, k=50):
            return self.q_dict[question][:k]

    old_hybrid_unreranked = CachedDictRetriever(legacy_cache["hybrid"])
    old_hybrid_mmarco = CachedDictRetriever(legacy_cache["mmarco"])

    # 1. Ablation configurations
    ablation_configs = [
        ("Old pipeline: Hybrid (e5-large + BM25 1:1) + mmarco (d=10)", old_hybrid_mmarco),
        ("Old pipeline (unreranked): Hybrid (e5-large + BM25 1:1)", old_hybrid_unreranked),
        (
            "New pipeline (Upgraded E5): Dense_matn_HyDE + Dense_exp_HyDE + BM25_matn + BM25_exp (8:2:1:1)",
            MultiRRFHybridRetriever(
                [dense_matn_hyde, dense_exp_hyde, bm25_matn, bm25_exp],
                [8.0, 2.0, 1.0, 1.0],
                50,
            ),
        ),
        (
            "New pipeline WITHOUT doc expansion: Dense_matn_HyDE + BM25_matn (8:0:1:0 = 8:1)",
            MultiRRFHybridRetriever([dense_matn_hyde, bm25_matn], [8.0, 1.0], 50),
        ),
        (
            "New pipeline WITHOUT doc expansion (equal 1:1): Dense_matn_HyDE + BM25_matn (1:0:1:0 = 1:1)",
            MultiRRFHybridRetriever([dense_matn_hyde, bm25_matn], [1.0, 1.0], 50),
        ),
        (
            "New pipeline WITHOUT doc expansion (E1 3:1): Dense_matn_HyDE + BM25_matn (3:0:1:0 = 3:1)",
            MultiRRFHybridRetriever([dense_matn_hyde, bm25_matn], [3.0, 1.0], 50),
        ),
        (
            "New pipeline WITHOUT HyDE: Dense_matn + Dense_exp + BM25_matn + BM25_exp (8:2:1:1, raw query)",
            MultiRRFHybridRetriever(
                [dense_matn_raw, dense_exp_raw, bm25_matn, bm25_exp],
                [8.0, 2.0, 1.0, 1.0],
                50,
            ),
        ),
        (
            "New pipeline WITHOUT doc expansion & WITHOUT HyDE: Dense_matn + BM25_matn (8:0:1:0 = 8:1, raw query)",
            MultiRRFHybridRetriever([dense_matn_raw, bm25_matn], [8.0, 1.0], 50),
        ),
        (
            "New pipeline WITHOUT doc expansion & WITHOUT HyDE (E1 3:1): Dense_matn + BM25_matn (3:0:1:0 = 3:1, raw query)",
            MultiRRFHybridRetriever([dense_matn_raw, bm25_matn], [3.0, 1.0], 50),
        ),
        (
            "New pipeline with EQUAL RRF weights (1:1:1:1): Dense_matn_HyDE + Dense_exp_HyDE + BM25_matn + BM25_exp (1:1:1:1)",
            MultiRRFHybridRetriever(
                [dense_matn_hyde, dense_exp_hyde, bm25_matn, bm25_exp],
                [1.0, 1.0, 1.0, 1.0],
                50,
            ),
        ),
        (
            "New pipeline with EQUAL RRF weights & WITHOUT HyDE (1:1:1:1, raw query)",
            MultiRRFHybridRetriever(
                [dense_matn_raw, dense_exp_raw, bm25_matn, bm25_exp],
                [1.0, 1.0, 1.0, 1.0],
                50,
            ),
        ),
    ]

    datasets = {
        "dev_orig": synth_orig,
        "dev_expanded": synth_exp,
        "golden_orig": golden_orig,
        "golden_expanded": golden_exp,
    }

    ablation_results = {ds: {} for ds in datasets}
    dev_ranks_by_cfg = {}

    print("=== Running Ablation Configurations ===")
    for cfg_name, ret in ablation_configs:
        for ds_name, items in datasets.items():
            metrics, r10, r50 = eval_fast(ret, items)
            ablation_results[ds_name][cfg_name] = metrics
            if ds_name in ("dev_orig", "dev_expanded"):
                dev_ranks_by_cfg[(ds_name, cfg_name)] = (r10, r50)
        m_dev = ablation_results["dev_orig"][cfg_name]
        m_gold = ablation_results["golden_orig"][cfg_name]
        print(
            f"{cfg_name:<88} | DEV hit@1={m_dev['hit@1']:.1%} hit@5={m_dev['hit@5']:.1%} hit@10={m_dev['hit@10']:.1%} MRR={m_dev['MRR']:.3f} "
            f"| GOLD hit@1={m_gold['hit@1']:.1%} hit@5={m_gold['hit@5']:.1%} hit@10={m_gold['hit@10']:.1%} MRR={m_gold['MRR']:.3f}",
            flush=True,
        )

    # 2. Complete RRF weight tuning grid on dev and golden
    weight_grid = [
        ("1:0:0:0 (Dense_matn only)", [1.0, 0.0, 0.0, 0.0]),
        ("0:1:0:0 (Dense_exp only)", [0.0, 1.0, 0.0, 0.0]),
        ("0:0:1:0 (BM25_matn only)", [0.0, 0.0, 1.0, 0.0]),
        ("0:0:0:1 (BM25_exp only)", [0.0, 0.0, 0.0, 1.0]),
        ("0:0:1:1 (BM25_matn + BM25_exp)", [0.0, 0.0, 1.0, 1.0]),
        ("1:0:1:0 (Dense_matn + BM25_matn 1:1)", [1.0, 0.0, 1.0, 0.0]),
        ("2:0:1:0 (Dense_matn + BM25_matn 2:1)", [2.0, 0.0, 1.0, 0.0]),
        ("3:0:1:0 (Dense_matn + BM25_matn 3:1)", [3.0, 0.0, 1.0, 0.0]),
        ("8:0:1:0 (Dense_matn + BM25_matn 8:1)", [8.0, 0.0, 1.0, 0.0]),
        ("1:1:0:0 (Dense_matn + Dense_exp 1:1)", [1.0, 1.0, 0.0, 0.0]),
        ("2:1:0:0 (Dense_matn + Dense_exp 2:1)", [2.0, 1.0, 0.0, 0.0]),
        ("1:0:0:1 (Dense_matn + BM25_exp 1:1)", [1.0, 0.0, 0.0, 1.0]),
        ("2:0:0:1 (Dense_matn + BM25_exp 2:1)", [2.0, 0.0, 0.0, 1.0]),
        ("3:0:0:1 (Dense_matn + BM25_exp 3:1)", [3.0, 0.0, 0.0, 1.0]),
        ("2:0:1:1 (Dense_matn + BM25_matn + BM25_exp 2:1:1)", [2.0, 0.0, 1.0, 1.0]),
        ("3:0:1:1 (Dense_matn + BM25_matn + BM25_exp 3:1:1)", [3.0, 0.0, 1.0, 1.0]),
        ("1:1:1:1 (Equal 4-way RRF)", [1.0, 1.0, 1.0, 1.0]),
        ("2:1:1:1 (4-way RRF)", [2.0, 1.0, 1.0, 1.0]),
        ("3:1:1:1 (4-way RRF)", [3.0, 1.0, 1.0, 1.0]),
        ("4:1:1:1 (4-way RRF)", [4.0, 1.0, 1.0, 1.0]),
        ("4:2:1:1 (4-way RRF)", [4.0, 2.0, 1.0, 1.0]),
        ("6:2:1:1 (4-way RRF)", [6.0, 2.0, 1.0, 1.0]),
        ("8:2:1:1 (4-way RRF — chosen on dev)", [8.0, 2.0, 1.0, 1.0]),
        ("10:2:1:1 (4-way RRF)", [10.0, 2.0, 1.0, 1.0]),
    ]

    tuning_results = {"with_hyde_blend70": {}, "without_hyde_raw_query": {}}
    print("\n=== Running RRF Weight Tuning Grid (With HyDE & Without HyDE) ===")
    for mode_key, d_m, d_e in [
        ("with_hyde_blend70", dense_matn_hyde, dense_exp_hyde),
        ("without_hyde_raw_query", dense_matn_raw, dense_exp_raw),
    ]:
        for w_label, w_vec in weight_grid:
            active_rets = []
            active_ws = []
            for r_obj, w_val in zip([d_m, d_e, bm25_matn, bm25_exp], w_vec):
                if w_val > 0:
                    active_rets.append(r_obj)
                    active_ws.append(w_val)
            ret = (
                active_rets[0]
                if len(active_rets) == 1
                else MultiRRFHybridRetriever(active_rets, active_ws, 50)
            )
            tuning_results[mode_key][w_label] = {}
            for ds_name, items in datasets.items():
                m, _, _ = eval_fast(ret, items)
                tuning_results[mode_key][w_label][ds_name] = m

    # 3. Leakage Analysis
    print("\n=== Running Leakage Similarity & Near-Duplicate Analysis ===")
    leak_g38 = analyze_leakage_for_model(
        "gemini-3.8-flash",
        exp_g38,
        g001_exp_g38_3072,
        synth_orig,
        synth_exp,
        map_orig_3072,
    )
    leak_g25 = analyze_leakage_for_model(
        "gemini-2.5-flash",
        exp_g25,
        g001_exp_g25_3072,
        synth_orig,
        synth_exp,
        map_orig_3072,
    )

    # Compute dev gain stratified by near-duplicate status at thresholds 0.90, 0.85, 0.80
    stratified_gains = {}
    for leak_obj in (leak_g38, leak_g25):
        m_tag = leak_obj["model"]
        stratified_gains[m_tag] = {}
        item_cos = leak_obj["gold_item_cos_per_q"]
        for thresh_label, thresh in [
            ("item_cos_ge_0.90", 0.90),
            ("item_cos_ge_0.85", 0.85),
            ("item_cos_ge_0.80", 0.80),
        ]:
            mask_dup = item_cos >= thresh
            mask_nondup = ~mask_dup
            stratified_gains[m_tag][thresh_label] = {
                "threshold": thresh,
                "near_duplicate_count": int(mask_dup.sum()),
                "non_duplicate_count": int(mask_nondup.sum()),
                "dev_orig": {},
                "dev_expanded": {},
            }
            for ds_name in ("dev_orig", "dev_expanded"):
                for cfg_name, _ in ablation_configs:
                    r10, r50 = dev_ranks_by_cfg[(ds_name, cfg_name)]
                    stratified_gains[m_tag][thresh_label][ds_name][cfg_name] = {
                        "with_near_duplicate": subset_metrics_from_ranks(
                            r10, r50, mask_dup
                        ),
                        "without_near_duplicate": subset_metrics_from_ranks(
                            r10, r50, mask_nondup
                        ),
                    }

    # Inspect examples of near-duplicates (cosine >= 0.90) for transparency
    g38_dup_examples = []
    for idx, cos_val in enumerate(leak_g38["gold_item_cos_per_q"]):
        if cos_val >= 0.90:
            g38_dup_examples.append({
                "query_idx": idx,
                "question": synth_orig[idx]["question"],
                "gold_hadith_ids": synth_orig[idx]["hadith_ids"],
                "best_gold_expansion_item": leak_g38["best_gold_items"][idx],
                "item_cosine": round(float(cos_val), 4),
                "item_4gram_jaccard": round(
                    float(leak_g38["gold_item_jacc_per_q"][idx]), 4
                ),
            })

    g25_dup_examples = []
    for idx, cos_val in enumerate(leak_g25["gold_item_cos_per_q"]):
        if cos_val >= 0.90:
            g25_dup_examples.append({
                "query_idx": idx,
                "question": synth_orig[idx]["question"],
                "gold_hadith_ids": synth_orig[idx]["hadith_ids"],
                "best_gold_expansion_item": leak_g25["best_gold_items"][idx],
                "item_cosine": round(float(cos_val), 4),
                "item_4gram_jaccard": round(
                    float(leak_g25["gold_item_jacc_per_q"][idx]), 4
                ),
            })

    # Clean numpy arrays before JSON serialization
    for leak_obj in (leak_g38, leak_g25):
        for k in [
            "gold_item_cos_per_q",
            "gold_chunk_cos_per_q",
            "gold_item_jacc_per_q",
            "best_gold_items",
            "best_nongold_items",
        ]:
             leak_obj.pop(k, None)

    out_payload = {
        "ablation": ablation_results,
        "tuning_grid": tuning_results,
        "leakage": {
            "gemini-3.8-flash": leak_g38,
            "gemini-2.5-flash": leak_g25,
            "stratified_dev_gains": stratified_gains,
            "g38_near_duplicate_examples_ge_090": g38_dup_examples,
            "g25_near_duplicate_examples_ge_090": g25_dup_examples,
        },
    }

    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(out_payload, f, ensure_ascii=False, indent=2)
    print(f"\nSaved full ablation, tuning, and leakage analysis -> {OUT_JSON_PATH}")


if __name__ == "__main__":
    main()
