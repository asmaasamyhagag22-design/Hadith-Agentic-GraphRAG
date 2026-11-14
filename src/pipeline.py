"""
مسار الاسترجاع وإعادة الترتيب الموحّد — نفس الإعداد المقيس في
evaluate.py و answer_eval.py والـ CLI و smoke_test.py.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    API_TIMEOUT_MS,
    DOC_EXPANSIONS_G38_PATH,
    IDS_MATN,
    PROCESSED_CHUNKS_PATH,
    QUERIES_GEMINI001_CACHE_PATH,
    QUERIES_HYDE_G38_CACHE_PATH,
    VECTORS_EXPANSION_G38_GEMINI001,
    VECTORS_MATN,
    VECTORS_MATN_GEMINI001,
)
from experiment_variants import variant_text
from lexical import BM25Index
from rerank import DEFAULT_MODEL, DEFAULT_TOP_K_IN, RerankingRetriever
from retrieve import (
    HybridRetriever,
    Retriever,
    UpgradedRetriever,
    load_chunk_lookup,
)
from utils import MODEL_NAME

DEFAULT_MODE = "upgraded"
VALID_MODES = ("upgraded", "legacy")

VARIANT = "matn"
CANDIDATES = 50
RRF_K = 60
DENSE_WEIGHT = 1.0
BM25_WEIGHT = 1.0
RERANK_MODEL = DEFAULT_MODEL
TOP_K_IN = DEFAULT_TOP_K_IN
DEFAULT_K = 5

UPGRADED_WEIGHTS = (8.0, 2.0, 1.0, 1.0)
UPGRADED_HYDE_ALPHA = 0.7


def resolve_pipeline_mode(mode=None):
    """يحدد وضع المسار الفعّال (`upgraded` افتراضيًا، أو `legacy`)."""
    raw = mode if mode is not None else os.environ.get(
        "MUSNAD_RETRIEVAL_PIPELINE", DEFAULT_MODE
    )
    normalized = str(raw).strip().lower()
    if normalized not in VALID_MODES:
        raise ValueError(
            f"Unknown pipeline mode: {mode!r}. Expected one of {VALID_MODES}."
        )
    return normalized


def build_bm25(chunk_ids, variant, chunk_lookup):

    texts = [
        variant_text(chunk_lookup[chunk_id], variant)
        for chunk_id in chunk_ids
    ]

    bm25 = BM25Index(chunk_ids, texts)
    bm25.variant = variant

    return bm25


def build_legacy_pipeline(
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
    يبني المسار المحلي التوافقي (بدون API للاسترجاع):
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
    pipeline.mode = "legacy"

    return pipeline


def build_pipeline(
    mode=None,
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
    matn_vectors_path=VECTORS_MATN_GEMINI001,
    exp_vectors_path=VECTORS_EXPANSION_G38_GEMINI001,
    expansions_jsonl_path=DOC_EXPANSIONS_G38_PATH,
    query_cache_path=QUERIES_GEMINI001_CACHE_PATH,
    hyde_cache_path=QUERIES_HYDE_G38_CACHE_PATH,
    weights=UPGRADED_WEIGHTS,
    hyde_alpha=UPGRADED_HYDE_ALPHA,
    api_timeout_ms=API_TIMEOUT_MS,
    fallback_retriever=None,
):
    """
    نقطة بناء مسار الاسترجاع الموحّدة للنظام:
    - `mode="upgraded"` (الافتراضي): gemini-embedding-001 (3072d) + توسعات g38flash + HyDE (0.7:0.3)
      + 4-way RRF (8:2:1:1)، مع رجوع تلقائي للمسار المحلي `legacy` عند فشل أو انتهاء مهلة API.
    - `mode="legacy"`: المسار المحلي `multilingual-e5-base + BM25 + mmarco top-10`.
    """

    resolved_mode = resolve_pipeline_mode(mode)

    if chunk_lookup is None:
        chunk_lookup = load_chunk_lookup(chunks_path)

    def _legacy_factory():
        return build_legacy_pipeline(
            vectors_path=vectors_path,
            ids_path=ids_path,
            chunks_path=chunks_path,
            chunk_lookup=chunk_lookup,
            rerank_model=rerank_model,
            top_k_in=top_k_in,
            candidates=candidates,
            rrf_k=rrf_k,
            dense_weight=dense_weight,
            bm25_weight=bm25_weight,
        )

    if resolved_mode == "legacy":
        return _legacy_factory()

    pipeline = UpgradedRetriever.from_files(
        matn_vectors_path=matn_vectors_path,
        exp_vectors_path=exp_vectors_path,
        expansions_jsonl_path=expansions_jsonl_path,
        ids_path=ids_path,
        chunks_path=chunks_path,
        query_cache_path=query_cache_path,
        hyde_cache_path=hyde_cache_path,
        chunk_lookup=chunk_lookup,
        weights=weights,
        hyde_alpha=hyde_alpha,
        candidates=candidates,
        rrf_k=rrf_k,
        api_timeout_ms=api_timeout_ms,
        fallback_retriever=fallback_retriever,
        fallback_factory=None if fallback_retriever is not None else _legacy_factory,
    )
    pipeline.default_k = DEFAULT_K
    pipeline.mode = "upgraded"

    return pipeline


def pipeline_config(retriever, k=DEFAULT_K):
    """وصف كامل قابل للمقارنة لإعداد مسار الاسترجاع وإعادة الترتيب."""

    if isinstance(retriever, UpgradedRetriever):
        return {
            "mode": "upgraded",
            "embedding_model": "gemini-embedding-001",
            "index_type": "dot_product_3072d",
            "vectors_path": retriever.matn_vectors_path,
            "exp_vectors_path": retriever.exp_vectors_path,
            "expansions_jsonl_path": retriever.expansions_jsonl_path,
            "ids_path": retriever.ids_path,
            "ntotal": int(retriever.matn_vectors.shape[0]),
            "chunk_ids": list(retriever.chunk_ids),
            "bm25_matn_chunk_ids": list(retriever.bm25_matn.chunk_ids),
            "bm25_exp_chunk_ids": list(retriever.bm25_exp.chunk_ids),
            "candidates": retriever.candidates,
            "rrf_k": retriever.rrf_k,
            "weights": tuple(retriever.weights),
            "hyde_alpha": retriever.hyde_alpha,
            "api_timeout_ms": retriever.api_timeout_ms,
            "rerank_model": None,
            "k": k,
        }

    hybrid = retriever.base
    dense = hybrid.dense
    bm25 = hybrid.bm25

    return {
        "mode": "legacy",
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
