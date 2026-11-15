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

UPGRADED_WEIGHTS = (1.0, 0.0, 0.0, 0.0)
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


DEFAULT_AGENT_MODE = "auto"
AGENT_ENV_VAR = "MUSNAD_AGENT"


def resolve_agent_mode(agent=None):
    """Resolve agent routing mode: ``'auto'``, ``'on'``, or ``'off'``."""
    raw = agent if agent is not None else os.environ.get(AGENT_ENV_VAR, DEFAULT_AGENT_MODE)
    if isinstance(raw, bool):
        return "on" if raw else "off"
    normalized = str(raw).strip().lower()
    if normalized == "":
        normalized = DEFAULT_AGENT_MODE
    if normalized == "auto":
        return "auto"
    if normalized in ("on", "true", "1", "yes"):
        return "on"
    if normalized in ("off", "false", "0", "no"):
        return "off"
    raise ValueError(
        f"Invalid {AGENT_ENV_VAR} value {raw!r}; expected 'auto', 'on', or 'off'."
    )


def _router_source_from_path(path: str) -> str:
    if path in ("v2_fast_path", "v2_rule_miss"):
        return "regex"
    if path == "v3_logreg":
        return "classifier"
    return "v2 fallback"


def resolve_agent_enabled(agent=None, question=None, retriever=None, trace=None):
    """Resolve whether agent tool-calling is active (evaluating ``auto`` via router)."""
    mode = resolve_agent_mode(agent)
    if trace is None:
        if mode == "on":
            return True
        if mode == "off":
            return False
        if question is None:
            return False
        try:
            from src.router import classify_intent
        except ImportError:
            from router import classify_intent
        return classify_intent(question, retriever=retriever) == "chain"

    if mode == "on":
        trace.record_router(
            decision="chain",
            source="override",
            probability=None,
            duration_ms=0.0,
            mode=mode,
        )
        return True
    if mode == "off":
        trace.record_router(
            decision="text",
            source="override",
            probability=None,
            duration_ms=0.0,
            mode=mode,
        )
        return False
    if question is None:
        trace.record_router(
            decision="text",
            source="no_question",
            probability=None,
            duration_ms=0.0,
            mode=mode,
        )
        return False
    try:
        from src.router import classify_intent_with_trace
    except ImportError:
        from router import classify_intent_with_trace
    q_cache = getattr(retriever, "query_vec_cache", None)
    was_cached = isinstance(q_cache, dict) and question in q_cache
    res = classify_intent_with_trace(question, retriever=retriever)
    embed_calls = (
        1 if isinstance(q_cache, dict) and not was_cached and question in q_cache else 0
    )
    trace.record_router(
        decision=res["intent"],
        source=_router_source_from_path(res.get("path", "")),
        probability=res.get("probability"),
        duration_ms=res.get("latency_ms", 0.0),
        path=res.get("path"),
        matched_rule=res.get("matched_rule"),
        mode=mode,
        embed_calls=embed_calls,
    )
    return res["intent"] == "chain"


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
    agent=None,
):
    """
    نقطة بناء مسار الاسترجاع الموحّدة للنظام:
    - `mode="upgraded"` (الافتراضي): gemini-embedding-001 (3072d) للمتن + HyDE (0.7:0.3)
      بأوزان (1:0:0:0) دون BM25 أو توسيع وثائق، مع رجوع تلقائي للمسار المحلي `legacy` عند فشل أو انتهاء مهلة API.
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

    agent_mode = resolve_agent_mode(agent)
    agent_enabled = resolve_agent_enabled(agent)

    if resolved_mode == "legacy":
        legacy_pipeline = _legacy_factory()
        legacy_pipeline.agent_mode = agent_mode
        legacy_pipeline.agent_enabled = agent_enabled
        return legacy_pipeline

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
    pipeline.agent_mode = agent_mode
    pipeline.agent_enabled = agent_enabled

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
            "bm25_matn_chunk_ids": (
                list(retriever.bm25_matn.chunk_ids)
                if retriever.bm25_matn is not None
                else None
            ),
            "bm25_exp_chunk_ids": (
                list(retriever.bm25_exp.chunk_ids)
                if retriever.bm25_exp is not None
                else None
            ),
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
