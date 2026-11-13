"""
Embed indexable matn chunks and evaluation queries with Vertex AI embedding models:
- gemini-embedding-001 (dim=3072 and Matryoshka dim=768)
- text-multilingual-embedding-002 (dim=768)
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import faiss
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import IDS_MATN, PROCESSED_DIR, VECTORS_MATN
from embed import indexable_chunks, load_chunks
from evaluate import answerable, evaluate, load_golden
from experiment_e0_gold_expansion import (
    GOLDEN_EXPANDED_PATH,
    SYNTHETIC_EXPANDED_PATH,
    evaluate_with_recall50,
)
from experiment_variants import variant_text
from lexical import BM25Index
from retrieve import HybridRetriever, LexicalRetriever, load_chunk_lookup
from utils import strip_diacritics


class PrecomputedDenseRetriever:
    """FAISS IndexFlatIP retriever backed by precomputed document and query vectors."""

    def __init__(self, doc_vectors, chunk_ids, chunk_lookup, query_vec_map):
        self.index = faiss.IndexFlatIP(doc_vectors.shape[1])
        self.index.add(np.ascontiguousarray(doc_vectors, dtype=np.float32))
        self.chunk_ids = [str(cid) for cid in chunk_ids]
        self.chunk_lookup = chunk_lookup
        self.query_vec_map = query_vec_map

    def search(self, question, k=5):
        q_vec = self.query_vec_map[question].reshape(1, -1)
        scores, indices = self.index.search(q_vec, k)
        results = []
        for rank, idx in enumerate(indices[0]):
            if idx < 0:
                continue
            chunk_id = self.chunk_ids[idx]
            chunk = self.chunk_lookup.get(chunk_id)
            if chunk is None:
                continue
            results.append({
                "rank": rank + 1,
                "score": float(scores[0][rank]),
                "chunk_id": chunk["id"],
                "hadith_id": chunk["metadata"]["hadith_number"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
            })
        return results


def l2_norm(x):
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return (x / np.maximum(norms, 1e-12)).astype(np.float32)


def embed_batches(client, model, texts, task_type, dim=None, batch_size=200):
    safe_texts = [t if t.strip() else " " for t in texts]
    batches = [
        (b_idx, safe_texts[start : start + batch_size])
        for b_idx, start in enumerate(range(0, len(safe_texts), batch_size))
    ]
    results = [None] * len(batches)

    def worker(item):
        b_idx, batch = item
        cfg = (
            types.EmbedContentConfig(task_type=task_type, output_dimensionality=dim)
            if dim is not None
            else types.EmbedContentConfig(task_type=task_type)
        )
        for attempt in range(5):
            try:
                resp = client.models.embed_content(
                    model=model, contents=batch, config=cfg
                )
                vecs = np.array(
                    [e.values for e in resp.embeddings], dtype=np.float32
                )
                return b_idx, vecs
            except Exception:
                time.sleep(2 * (attempt + 1))
                if attempt == 4:
                    raise

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        for b_idx, vecs in ex.map(worker, batches):
            results[b_idx] = vecs
    arr = np.vstack(results)
    print(
        f"  {model} ({task_type}) shape={arr.shape} in {time.time() - t0:.1f}s "
        f"({len(batches)} calls)"
    )
    return arr


def ensure_vertex_embeddings(doc_texts, all_questions, q_texts):
    g001_3072_path = PROCESSED_DIR / "vectors_matn_gemini001_3072.npy"
    g001_768_path = PROCESSED_DIR / "vectors_matn_gemini001_768.npy"
    g001_q_path = PROCESSED_DIR / "queries_gemini001.npz"

    if not (g001_3072_path.exists() and g001_768_path.exists() and g001_q_path.exists()):
        client = genai.Client()
        print("Embedding gemini-embedding-001...")
        doc_g001 = embed_batches(
            client, "gemini-embedding-001", doc_texts, "RETRIEVAL_DOCUMENT"
        )
        q_g001 = embed_batches(
            client, "gemini-embedding-001", q_texts, "RETRIEVAL_QUERY"
        )
        np.save(g001_3072_path, l2_norm(doc_g001))
        np.save(g001_768_path, l2_norm(doc_g001[:, :768]))
        np.savez(
            g001_q_path,
            questions=np.array(all_questions, dtype=object),
            vec3072=l2_norm(q_g001),
            vec768=l2_norm(q_g001[:, :768]),
        )


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

    ensure_vertex_embeddings(doc_texts, all_questions, q_texts)

    # Load saved vectors
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

    # Also load baseline e5-base
    from retrieve import Retriever
    e5_dense = Retriever.from_files(VECTORS_MATN, IDS_MATN, chunk_lookup=chunk_lookup)

    bm25_texts = [variant_text(chunk_lookup[cid], "matn") for cid in chunk_ids]
    bm25 = BM25Index(chunk_ids, bm25_texts)

    ret_g001_768 = PrecomputedDenseRetriever(
        g001_768, chunk_ids, chunk_lookup, q_map_g001_768
    )
    ret_g001_1536 = PrecomputedDenseRetriever(
        g001_1536, chunk_ids, chunk_lookup, q_map_g001_1536
    )
    ret_g001_3072 = PrecomputedDenseRetriever(
        g001_3072, chunk_ids, chunk_lookup, q_map_g001_3072
    )

    models = [
        ("Dense: multilingual-e5-base (768)", e5_dense),
        ("Dense: gemini-embedding-001 (768)", ret_g001_768),
        ("Dense: gemini-embedding-001 (1536)", ret_g001_1536),
        ("Dense: gemini-embedding-001 (3072)", ret_g001_3072),
        ("BM25: matn only", LexicalRetriever(bm25, chunk_lookup)),
        ("Hybrid (c=50): e5-base + BM25", HybridRetriever(e5_dense, bm25, candidates=50)),
        ("Hybrid (c=50): gemini-001 (768) + BM25", HybridRetriever(ret_g001_768, bm25, candidates=50)),
        ("Hybrid (c=50): gemini-001 (1536) + BM25", HybridRetriever(ret_g001_1536, bm25, candidates=50)),
        ("Hybrid (c=50): gemini-001 (3072) + BM25", HybridRetriever(ret_g001_3072, bm25, candidates=50)),
        ("Hybrid (c=100): e5-base + BM25", HybridRetriever(e5_dense, bm25, candidates=100)),
        ("Hybrid (c=100): gemini-001 (768) + BM25", HybridRetriever(ret_g001_768, bm25, candidates=100)),
        ("Hybrid (c=100): gemini-001 (1536) + BM25", HybridRetriever(ret_g001_1536, bm25, candidates=100)),
        ("Hybrid (c=100): gemini-001 (3072) + BM25", HybridRetriever(ret_g001_3072, bm25, candidates=100)),
    ]

    for ds_name, items in [
        ("synthetic_eval_expanded (n=224)", synth_items),
        ("golden_expanded (n=27)", golden_items),
    ]:
        print(f"\n=== {ds_name} ===")
        print(
            f"{'Configuration':<44} {'hit@1':<7} {'hit@3':<7} {'hit@5':<7} "
            f"{'hit@10':<7} {'recall@50':<10} {'setR@50':<8} {'MRR@10':<7} {'MRR@50':<7}"
        )
        print("-" * 112)
        for name, ret in models:
            hits10, mrr10, _ = evaluate(ret, items, k_values=(1, 3, 5, 10))
            hits50, mrr50, set_r50, _ = evaluate_with_recall50(ret, items)
            print(
                f"{name:<44} "
                f"{hits10[1]:<7.1%} {hits10[3]:<7.1%} {hits10[5]:<7.1%} "
                f"{hits10[10]:<7.1%} {hits50[50]:<10.1%} {set_r50:<8.1%} "
                f"{mrr10:<7.3f} {mrr50:<7.3f}"
            )


if __name__ == "__main__":
    main()
