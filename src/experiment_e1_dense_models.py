"""
E1 — Dense model comparison on Sahih Muslim (7,110 indexable matn chunks).

Compares:
1. intfloat/multilingual-e5-base (current baseline, dim=768)
2. BAAI/bge-m3 (dense dim=1024, sparse lexical weights, and dense+sparse hybrid)
3. Qwen/Qwen3-Embedding-0.6B (dim=1024, last-token pooling with query instruction)
4. Vertex gemini-embedding-001 (dim=768, dim=1536, dim=3072 via Matryoshka)

Note: 4B/8B models are skipped per protocol because torch.cuda.is_available() is False.
"""

import glob
import json
import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path

import faiss
import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import IDS_MATN, PROCESSED_DIR, VECTORS_MATN
from embed import indexable_chunks, load_chunks
from embed_vertex_e1 import PrecomputedDenseRetriever, ensure_vertex_embeddings, l2_norm
from evaluate import answerable, evaluate, load_golden
from experiment_e0_gold_expansion import (
    GOLDEN_EXPANDED_PATH,
    SYNTHETIC_EXPANDED_PATH,
    evaluate_with_recall50,
)
from experiment_variants import variant_text
from lexical import BM25Index, reciprocal_rank_fusion
from retrieve import HybridRetriever, LexicalRetriever, Retriever, load_chunk_lookup
from utils import strip_diacritics

torch.set_num_threads(4)


class SparseRetriever:
    """Inverted-index retriever over BGE-M3 learned sparse lexical weights."""

    def __init__(self, doc_sparse_list, chunk_ids, chunk_lookup, query_sparse_map):
        self.chunk_ids = [str(cid) for cid in chunk_ids]
        self.chunk_lookup = chunk_lookup
        self.query_sparse_map = query_sparse_map
        self.postings = defaultdict(list)
        for doc_idx, weights in enumerate(doc_sparse_list):
            for tid, w in weights.items():
                if w > 0:
                    self.postings[tid].append((doc_idx, float(w)))

    def score_all(self, question):
        q_weights = self.query_sparse_map[question]
        scores = np.zeros(len(self.chunk_ids), dtype=np.float32)
        for tid, qw in q_weights.items():
            if qw <= 0:
                continue
            for doc_idx, dw in self.postings.get(tid, ()):
                scores[doc_idx] += qw * dw
        return scores

    def search(self, question, k=5):
        scores = self.score_all(question)
        top_indices = np.argsort(-scores)[:k]
        results = []
        for rank, idx in enumerate(top_indices, start=1):
            chunk_id = self.chunk_ids[int(idx)]
            chunk = self.chunk_lookup.get(chunk_id)
            if chunk is None:
                continue
            results.append({
                "rank": rank,
                "score": float(scores[idx]),
                "chunk_id": chunk["id"],
                "hadith_id": chunk["metadata"]["hadith_number"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
            })
        return results


class BGEM3DenseSparseLinearRetriever:
    """BGE-M3 native linear combination: score = dense_score + sparse_weight * sparse_score."""

    def __init__(
        self,
        doc_vectors,
        sparse_retriever,
        chunk_ids,
        chunk_lookup,
        query_vec_map,
        sparse_weight=0.3,
    ):
        self.doc_vectors = np.ascontiguousarray(doc_vectors, dtype=np.float32)
        self.sparse_retriever = sparse_retriever
        self.chunk_ids = [str(cid) for cid in chunk_ids]
        self.chunk_lookup = chunk_lookup
        self.query_vec_map = query_vec_map
        self.sparse_weight = sparse_weight

    def search(self, question, k=5):
        q_vec = self.query_vec_map[question]
        dense_scores = self.doc_vectors @ q_vec
        sparse_scores = self.sparse_retriever.score_all(question)
        total_scores = dense_scores + self.sparse_weight * sparse_scores
        top_indices = np.argsort(-total_scores)[:k]
        results = []
        for rank, idx in enumerate(top_indices, start=1):
            chunk_id = self.chunk_ids[int(idx)]
            chunk = self.chunk_lookup.get(chunk_id)
            if chunk is None:
                continue
            results.append({
                "rank": rank,
                "score": float(total_scores[idx]),
                "chunk_id": chunk["id"],
                "hadith_id": chunk["metadata"]["hadith_number"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
            })
        return results


class MultiRRFHybridRetriever:
    """General RRF retriever fusing arbitrary rank-producing retrievers."""

    def __init__(self, retrievers, weights=None, candidates=50, rrf_k=60):
        self.retrievers = retrievers
        self.weights = weights or [1.0] * len(retrievers)
        self.candidates = candidates
        self.rrf_k = rrf_k
        self.chunk_lookup = retrievers[0].chunk_lookup

    def search(self, question, k=5):
        rank_lists = []
        for ret in self.retrievers:
            if hasattr(ret, "ranked_ids"):
                rank_lists.append(ret.ranked_ids(question, k=self.candidates))
            else:
                rank_lists.append([
                    str(r["chunk_id"])
                    for r in ret.search(question, k=self.candidates)
                ])
        fused = reciprocal_rank_fusion(
            rank_lists, k=self.rrf_k, weights=self.weights
        )
        results = []
        for rank, chunk_id in enumerate(fused[:k], start=1):
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


def encode_bge_m3(doc_texts, all_questions, q_texts, batch_size=16, max_length=256):
    dense_path = PROCESSED_DIR / "vectors_matn_bgem3_1024.npy"
    sparse_path = PROCESSED_DIR / "sparse_matn_bgem3.pkl"
    q_path = PROCESSED_DIR / "queries_bgem3.pkl"

    if dense_path.exists() and sparse_path.exists() and q_path.exists():
        print("Loading cached BAAI/bge-m3 embeddings...")
        doc_dense = np.load(dense_path)
        with open(sparse_path, "rb") as f:
            doc_sparse = pickle.load(f)
        with open(q_path, "rb") as f:
            q_data = pickle.load(f)
        return doc_dense, doc_sparse, q_data["dense_map"], q_data["sparse_map"]

    bge_dir = glob.glob("/mnt/data/hf_cache/models--BAAI--bge-m3/snapshots/*")[0]
    print(f"Encoding BAAI/bge-m3 from {bge_dir} ...")
    tok = AutoTokenizer.from_pretrained(bge_dir)
    model = AutoModel.from_pretrained(bge_dir, dtype=torch.float32)
    model.eval()

    sparse_linear = torch.nn.Linear(1024, 1)
    sparse_state = torch.load(
        f"{bge_dir}/sparse_linear.pt", map_location="cpu", weights_only=True
    )
    sparse_linear.load_state_dict(sparse_state)
    sparse_linear.eval()

    unused_tokens = {
        tok.cls_token_id,
        tok.eos_token_id,
        tok.pad_token_id,
        tok.unk_token_id,
    }

    def run_texts(texts, label):
        unique_texts = list(dict.fromkeys(texts))
        # Sort unique texts by character length to minimize padding
        order = sorted(range(len(unique_texts)), key=lambda i: len(unique_texts[i]))
        sorted_texts = [unique_texts[i] for i in order]

        sorted_dense = np.zeros((len(sorted_texts), 1024), dtype=np.float32)
        sorted_sparse = [None] * len(sorted_texts)

        t0 = time.time()
        with torch.inference_mode():
            for start in range(0, len(sorted_texts), batch_size):
                batch = [
                    t if t.strip() else " "
                    for t in sorted_texts[start : start + batch_size]
                ]
                inp = tok(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=max_length,
                    return_tensors="pt",
                )
                out = model(**inp).last_hidden_state
                cls_vecs = F.normalize(out[:, 0], p=2, dim=-1).cpu().numpy()
                sorted_dense[start : start + len(batch)] = cls_vecs

                tw = torch.relu(sparse_linear(out)).squeeze(-1).cpu().numpy()
                input_ids = inp["input_ids"].cpu().numpy()
                for b_i in range(len(batch)):
                    w_dict = {}
                    for pos, tid in enumerate(input_ids[b_i]):
                        tid_int = int(tid)
                        if tid_int in unused_tokens:
                            continue
                        w = float(tw[b_i, pos])
                        if w > w_dict.get(tid_int, 0.0):
                            w_dict[tid_int] = w
                    sorted_sparse[start + b_i] = w_dict

                done = min(start + batch_size, len(sorted_texts))
                if done % 800 == 0 or done == len(sorted_texts):
                    elapsed = time.time() - t0
                    rate = done / max(elapsed, 1e-6)
                    eta = (len(sorted_texts) - done) / max(rate, 1e-6)
                    print(
                        f"  [bge-m3 {label}] {done}/{len(sorted_texts)} "
                        f"({elapsed:.1f}s elapsed, ETA {eta:.1f}s)",
                        flush=True,
                    )

        # Map back to original texts
        text_to_idx = {unique_texts[orig_i]: rank_i for rank_i, orig_i in enumerate(order)}
        full_dense = np.zeros((len(texts), 1024), dtype=np.float32)
        full_sparse = [None] * len(texts)
        for i, t in enumerate(texts):
            s_i = text_to_idx[t]
            full_dense[i] = sorted_dense[s_i]
            full_sparse[i] = sorted_sparse[s_i]
        return full_dense, full_sparse

    doc_dense, doc_sparse = run_texts(doc_texts, "docs")
    q_dense, q_sparse = run_texts(q_texts, "queries")

    dense_map = {q: q_dense[i] for i, q in enumerate(all_questions)}
    sparse_map = {q: q_sparse[i] for i, q in enumerate(all_questions)}

    np.save(dense_path, doc_dense)
    with open(sparse_path, "wb") as f:
        pickle.dump(doc_sparse, f)
    with open(q_path, "wb") as f:
        pickle.dump({"dense_map": dense_map, "sparse_map": sparse_map}, f)

    return doc_dense, doc_sparse, dense_map, sparse_map


def encode_qwen3_06b(doc_texts, all_questions, q_texts, batch_size=16, max_length=256):
    dense_path = PROCESSED_DIR / "vectors_matn_qwen3_06b_1024.npy"
    q_path = PROCESSED_DIR / "queries_qwen3_06b.npz"

    if dense_path.exists() and q_path.exists():
        print("Loading cached Qwen3-Embedding-0.6B embeddings...")
        doc_dense = np.load(dense_path)
        q_npz = np.load(q_path, allow_pickle=True)
        q_list = list(q_npz["questions"])
        q_vecs = q_npz["vecs"]
        return doc_dense, {q: q_vecs[i] for i, q in enumerate(q_list)}

    qwen_dir = glob.glob(
        "/mnt/data/hf_cache/models--Qwen--Qwen3-Embedding-0.6B/snapshots/*"
    )[0]
    print(f"Encoding Qwen3-Embedding-0.6B from {qwen_dir} ...")
    tok = AutoTokenizer.from_pretrained(qwen_dir, padding_side="left")
    model = AutoModel.from_pretrained(qwen_dir, dtype=torch.float32)
    model.eval()

    query_prefix = (
        "Instruct: Given a web search query, retrieve relevant passages "
        "that answer the query\nQuery:"
    )

    def last_token_pool(last_hidden_states, attention_mask):
        left_padding = attention_mask[:, -1].sum() == attention_mask.shape[0]
        if left_padding:
            return last_hidden_states[:, -1]
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size_curr = last_hidden_states.shape[0]
        return last_hidden_states[
            torch.arange(batch_size_curr, device=last_hidden_states.device),
            sequence_lengths,
        ]

    def run_texts(texts, label):
        unique_texts = list(dict.fromkeys(texts))
        order = sorted(range(len(unique_texts)), key=lambda i: len(unique_texts[i]))
        sorted_texts = [unique_texts[i] for i in order]
        sorted_dense = np.zeros((len(sorted_texts), 1024), dtype=np.float32)

        t0 = time.time()
        with torch.inference_mode():
            for start in range(0, len(sorted_texts), batch_size):
                batch = [
                    t if t.strip() else " "
                    for t in sorted_texts[start : start + batch_size]
                ]
                inp = tok(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=max_length,
                    return_tensors="pt",
                )
                out = model(**inp)
                pooled = last_token_pool(
                    out.last_hidden_state, inp["attention_mask"]
                )
                vecs = F.normalize(pooled, p=2, dim=-1).cpu().numpy()
                sorted_dense[start : start + len(batch)] = vecs

                done = min(start + batch_size, len(sorted_texts))
                if done % 800 == 0 or done == len(sorted_texts):
                    elapsed = time.time() - t0
                    rate = done / max(elapsed, 1e-6)
                    eta = (len(sorted_texts) - done) / max(rate, 1e-6)
                    print(
                        f"  [qwen3-0.6B {label}] {done}/{len(sorted_texts)} "
                        f"({elapsed:.1f}s elapsed, ETA {eta:.1f}s)",
                        flush=True,
                    )

        text_to_idx = {unique_texts[orig_i]: rank_i for rank_i, orig_i in enumerate(order)}
        full_dense = np.zeros((len(texts), 1024), dtype=np.float32)
        for i, t in enumerate(texts):
            full_dense[i] = sorted_dense[text_to_idx[t]]
        return full_dense

    doc_dense = run_texts(doc_texts, "docs")
    instruct_queries = [f"{query_prefix}{q}" for q in q_texts]
    q_dense = run_texts(instruct_queries, "queries")

    np.save(dense_path, doc_dense)
    np.savez(
        q_path,
        questions=np.array(all_questions, dtype=object),
        vecs=q_dense,
    )
    return doc_dense, {q: q_dense[i] for i, q in enumerate(all_questions)}


def main():
    print(f"CUDA available: {torch.cuda.is_available()} (skipping 4B/8B models per protocol)")
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

    # 1. Vertex Gemini embeddings
    ensure_vertex_embeddings(doc_texts, all_questions, q_texts)
    g001_3072 = np.load(PROCESSED_DIR / "vectors_matn_gemini001_3072.npy")
    g001_1536 = l2_norm(g001_3072[:, :1536])
    g001_768 = np.load(PROCESSED_DIR / "vectors_matn_gemini001_768.npy")
    g001_q = np.load(PROCESSED_DIR / "queries_gemini001.npz", allow_pickle=True)
    q_list_g001 = list(g001_q["questions"])
    vec3072_q = g001_q["vec3072"]
    vec1536_q = l2_norm(vec3072_q[:, :1536])
    vec768_q = g001_q["vec768"]
    q_map_g001_3072 = {q: vec3072_q[i] for i, q in enumerate(q_list_g001)}
    q_map_g001_1536 = {q: vec1536_q[i] for i, q in enumerate(q_list_g001)}
    q_map_g001_768 = {q: vec768_q[i] for i, q in enumerate(q_list_g001)}

    # 2. BAAI/bge-m3 (dense + sparse)
    bge_dense_vecs, bge_sparse_list, bge_q_dense, bge_q_sparse = encode_bge_m3(
        doc_texts, all_questions, q_texts
    )

    # 3. Qwen/Qwen3-Embedding-0.6B
    qwen_dense_vecs, qwen_q_dense = encode_qwen3_06b(
        doc_texts, all_questions, q_texts
    )

    # 4. Baseline multilingual-e5-base + BM25
    e5_dense = Retriever.from_files(VECTORS_MATN, IDS_MATN, chunk_lookup=chunk_lookup)
    bm25_texts = [variant_text(chunk_lookup[cid], "matn") for cid in chunk_ids]
    bm25 = BM25Index(chunk_ids, bm25_texts)
    bm25_ret = LexicalRetriever(bm25, chunk_lookup)

    ret_bge_dense = PrecomputedDenseRetriever(
        bge_dense_vecs, chunk_ids, chunk_lookup, bge_q_dense
    )
    ret_bge_sparse = SparseRetriever(
        bge_sparse_list, chunk_ids, chunk_lookup, bge_q_sparse
    )
    ret_bge_linear = BGEM3DenseSparseLinearRetriever(
        bge_dense_vecs,
        ret_bge_sparse,
        chunk_ids,
        chunk_lookup,
        bge_q_dense,
        sparse_weight=0.3,
    )
    ret_bge_rrf = MultiRRFHybridRetriever(
        [ret_bge_dense, ret_bge_sparse], weights=[1.0, 1.0], candidates=50
    )

    ret_qwen = PrecomputedDenseRetriever(
        qwen_dense_vecs, chunk_ids, chunk_lookup, qwen_q_dense
    )
    ret_g001_768 = PrecomputedDenseRetriever(
        g001_768, chunk_ids, chunk_lookup, q_map_g001_768
    )
    ret_g001_1536 = PrecomputedDenseRetriever(
        g001_1536, chunk_ids, chunk_lookup, q_map_g001_1536
    )
    ret_g001_3072 = PrecomputedDenseRetriever(
        g001_3072, chunk_ids, chunk_lookup, q_map_g001_3072
    )

    configs = [
        # Single-model / model-family comparison
        ("Dense: multilingual-e5-base (768)", e5_dense),
        ("Dense: BAAI/bge-m3 dense (1024)", ret_bge_dense),
        ("Sparse: BAAI/bge-m3 lexical", ret_bge_sparse),
        ("BGE-M3: dense + sparse (linear 1:0.3)", ret_bge_linear),
        ("BGE-M3: dense + sparse (RRF c=50)", ret_bge_rrf),
        ("Dense: Qwen3-Embedding-0.6B (1024)", ret_qwen),
        ("Dense: gemini-embedding-001 (768)", ret_g001_768),
        ("Dense: gemini-embedding-001 (1536)", ret_g001_1536),
        ("Dense: gemini-embedding-001 (3072)", ret_g001_3072),
        ("BM25: matn only", bm25_ret),
        # Hybrid (Dense + BM25, RRF c=50, equal weights)
        ("Hybrid (1:1, c=50): e5-base + BM25", HybridRetriever(e5_dense, bm25, candidates=50)),
        ("Hybrid (1:1, c=50): bge-m3 dense + BM25", HybridRetriever(ret_bge_dense, bm25, candidates=50)),
        ("Hybrid (1:1, c=50): bge-m3 (d+s) + BM25", MultiRRFHybridRetriever([ret_bge_dense, ret_bge_sparse, bm25], weights=[1.0, 1.0, 1.0], candidates=50)),
        ("Hybrid (1:1, c=50): Qwen3-0.6B + BM25", HybridRetriever(ret_qwen, bm25, candidates=50)),
        ("Hybrid (1:1, c=50): gemini-001 (768) + BM25", HybridRetriever(ret_g001_768, bm25, candidates=50)),
        ("Hybrid (1:1, c=50): gemini-001 (1536) + BM25", HybridRetriever(ret_g001_1536, bm25, candidates=50)),
        ("Hybrid (1:1, c=50): gemini-001 (3072) + BM25", HybridRetriever(ret_g001_3072, bm25, candidates=50)),
        # Weighted RRF for gemini-001 + BM25
        ("Hybrid (2:1, c=50): gemini-001 (768) + BM25", HybridRetriever(ret_g001_768, bm25, candidates=50, dense_weight=2.0, bm25_weight=1.0)),
        ("Hybrid (3:1, c=50): gemini-001 (768) + BM25", HybridRetriever(ret_g001_768, bm25, candidates=50, dense_weight=3.0, bm25_weight=1.0)),
        ("Hybrid (2:1, c=50): gemini-001 (1536) + BM25", HybridRetriever(ret_g001_1536, bm25, candidates=50, dense_weight=2.0, bm25_weight=1.0)),
        ("Hybrid (3:1, c=50): gemini-001 (1536) + BM25", HybridRetriever(ret_g001_1536, bm25, candidates=50, dense_weight=3.0, bm25_weight=1.0)),
        ("Hybrid (2:1, c=50): gemini-001 (3072) + BM25", HybridRetriever(ret_g001_3072, bm25, candidates=50, dense_weight=2.0, bm25_weight=1.0)),
        ("Hybrid (3:1, c=50): gemini-001 (3072) + BM25", HybridRetriever(ret_g001_3072, bm25, candidates=50, dense_weight=3.0, bm25_weight=1.0)),
    ]

    summary = {}
    for ds_name, items in [
        ("synthetic_eval_expanded", synth_items),
        ("golden_expanded", golden_items),
    ]:
        summary[ds_name] = {}
        print(f"\n=== {ds_name} (n={len(items)}) ===")
        print(
            f"{'Configuration':<45} {'hit@1':<7} {'hit@3':<7} {'hit@5':<7} "
            f"{'hit@10':<7} {'recall@50':<10} {'setR@50':<8} {'MRR@10':<7} {'MRR@50':<7}"
        )
        print("-" * 114)
        for name, ret in configs:
            hits10, mrr10, _ = evaluate(ret, items, k_values=(1, 3, 5, 10))
            hits50, mrr50, set_r50, _ = evaluate_with_recall50(ret, items)
            summary[ds_name][name] = {
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
                f"{name:<45} "
                f"{hits10[1]:<7.1%} {hits10[3]:<7.1%} {hits10[5]:<7.1%} "
                f"{hits10[10]:<7.1%} {hits50[50]:<10.1%} {set_r50:<8.1%} "
                f"{mrr10:<7.3f} {mrr50:<7.3f}"
            )

    out_json = PROCESSED_DIR / "e1_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSaved E1 results -> {out_json}")


if __name__ == "__main__":
    main()
