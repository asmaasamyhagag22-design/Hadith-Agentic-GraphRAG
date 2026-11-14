"""
مسار الاسترجاع وإعادة الترتيب الموحّد — نفس الإعداد المقيس في
evaluate.py و answer_eval.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    IDS_MATN,
    PROCESSED_CHUNKS_PATH,
    VECTORS_MATN,
)
from experiment_variants import variant_text
from lexical import BM25Index
from rerank import DEFAULT_MODEL, DEFAULT_TOP_K_IN, RerankingRetriever
from retrieve import HybridRetriever, Retriever, load_chunk_lookup
from utils import MODEL_NAME

VARIANT = "matn"
CANDIDATES = 50
RRF_K = 60
DENSE_WEIGHT = 1.0
BM25_WEIGHT = 1.0
RERANK_MODEL = DEFAULT_MODEL
TOP_K_IN = DEFAULT_TOP_K_IN
DEFAULT_K = 5


def build_bm25(chunk_ids, variant, chunk_lookup):

    texts = [
        variant_text(chunk_lookup[chunk_id], variant)
        for chunk_id in chunk_ids
    ]

    bm25 = BM25Index(chunk_ids, texts)
    bm25.variant = variant

    return bm25


def build_pipeline(
    vectors_path=VECTORS_MATN,
    ids_path=IDS_MATN,
    chunks_path=PROCESSED_CHUNKS_PATH,
    chunk_lookup=None,
    rerank_model=RERANK_MODEL,
    top_k_in=TOP_K_IN,
    candidates=CANDIDATES,
    rrf_k=RRF_K,
    dense_weight=DENSE_WEIGHT,
    bm25_weight=BM25_WEIGHT,
):
    """
    يبني مسار الإنتاج المقيس بالظبط:
    - بحث دلالي على المتن فقط (multilingual-e5-base + FAISS IndexFlatIP)
    - BM25 على المتن فقط
    - دمج هجين بالـ RRF (candidates=50, rrf_k=60, أوزان متساوية)
    - إعادة ترتيب بـ mmarco-mMiniLMv2-L12-H384-v1 على أول 10 مرشحين
    """

    if chunk_lookup is None:
        chunk_lookup = load_chunk_lookup(chunks_path)

    matn_dense = Retriever.from_files(
        vectors_path=vectors_path,
        ids_path=ids_path,
        chunks_path=chunks_path,
        chunk_lookup=chunk_lookup,
    )

    bm25 = build_bm25(matn_dense.chunk_ids, VARIANT, chunk_lookup)

    hybrid = HybridRetriever(
        matn_dense,
        bm25,
        candidates=candidates,
        rrf_k=rrf_k,
        dense_weight=dense_weight,
        bm25_weight=bm25_weight,
    )

    pipeline = RerankingRetriever(
        hybrid,
        model_name=rerank_model,
        top_k_in=top_k_in,
        chunk_lookup=chunk_lookup,
    )
    pipeline.default_k = DEFAULT_K

    return pipeline


def pipeline_config(retriever, k=DEFAULT_K):
    """وصف كامل قابل للمقارنة لإعداد مسار الاسترجاع وإعادة الترتيب."""

    hybrid = retriever.base
    dense = hybrid.dense
    bm25 = hybrid.bm25

    return {
        "embedding_model": MODEL_NAME,
        "index_type": type(dense.index).__name__,
        "vectors_path": dense.vectors_path,
        "ids_path": dense.ids_path,
        "ntotal": dense.index.ntotal,
        "chunk_ids": list(dense.chunk_ids),
        "bm25_variant": getattr(bm25, "variant", None),
        "bm25_chunk_ids": list(bm25.chunk_ids),
        "candidates": hybrid.candidates,
        "rrf_k": hybrid.rrf_k,
        "dense_weight": hybrid.dense_weight,
        "bm25_weight": hybrid.bm25_weight,
        "rerank_model": retriever.model_name,
        "top_k_in": retriever.top_k_in,
        "k": k,
    }
