"""Arabic intent classifier for Musnad query routing (v2 regex + v3 embedding classifier).

Classifies incoming Arabic questions into ``"chain"`` (narrator, isnad, chain
count, companion/teacher attribution, or narrator membership) or ``"text"``
(hadith content, jurisprudence, or meaning):

- **v2**: Deterministic Arabic linguistic regexes derived from hadith-sciences
  terminology (`0` API calls).
- **v3** (selected by Step 1d pre-registered rule): `v2` chain fast path, plus
  L2-regularized Logistic Regression over the 3072-d `gemini-embedding-001`
  `RETRIEVAL_QUERY` vector (reusing `UpgradedRetriever.query_vec_cache` so text
  queries incur `0` extra embedding API calls). Falls back transparently to
  `v2` whenever no embedding or weights artifact is available.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np

RouteIntent = Literal["chain", "text"]

ROUTER_WEIGHTS_PATH = Path(__file__).resolve().parent / "router_weights.npz"
DEFAULT_ROUTER_VERSION = "v3"
ROUTER_VERSION_ENV_VAR = "MUSNAD_ROUTER_VERSION"

_DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u0640\u200c-\u200f]")
_ALEF_RE = re.compile(r"[أإآٱ]")
_PUNCT_RE = re.compile(r"[^\w\u0621-\u064a\s]+")
_WHITESPACE_RE = re.compile(r"\s+")

_END = r"(?![\u0621-\u064a])"
_START = r"(?<![\u0621-\u064a])"

# General Arabic linguistic rules for isnad/narrator intent (v2).
# Each tuple is (rule_name, compiled_pattern).
_CHAIN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "explicit_isnad_or_sanad_term",
        re.compile(
            rf"{_START}(?:"
            r"[وفبلك]?(?:ال)?اسناد(?:ا|ه|ها|هما|هم)?|"
            r"[وفبلك]?(?:ال)?اسانيد(?:ه|ها|هما|هم)?|"
            r"[وفبلك]?سنده|"
            r"للاسنا?د|للاسانيد|للسند|"
            r"(?:في|من|عن|ضمن|ما|كم|اذكر|بين)\s+(?:ال)?سند|"
            r"سند\s+(?:(?:ال)?حديث|هذا\s+الحديث|مسلم|الروا[ةه]|صحيح)|"
            r"سلسل[ةه]\s+(?:ال)?(?:سند|اسناد|اسانيد|روا[ةه]|(?:ال)?حديث)|"
            r"سلاسل\s+(?:ال)?(?:سند|اسناد|اسانيد|روا[ةه]|(?:ال)?حديث)"
            rf"){_END}"
        ),
    ),
    (
        "isnad_or_route_count",
        re.compile(
            rf"{_START}(?:"
            r"(?:كم|ما)\s+(?:عدد\s+)?(?:(?:ال)?اسانيد|(?:ال)?طرق|طرقا|طريقا|(?:ال)?سلاسل|سلسل[ةه]|اسنادا)|"
            r"عدد\s+(?:(?:ال)?اسانيد|طرق\s+(?:(?:ال)?حديث|(?:ال)?رواي[ةه]|هذا)|(?:ال)?سلاسل)|"
            r"كم\s+طريقا?\s+(?:ورد|وردت|روي|ثبت|جاء|له|لها|للحديث|لحديث)|"
            r"(?:(?:ال)?طرق|طرق\s+(?:(?:ال)?حديث|الرواي[ةه]))\s+(?:(?:ال)?مسجل[ةه]|(?:ال)?وارد[ةه]|المتعددة)"
            rf"){_END}"
        ),
    ),
    (
        "narrators_or_grading_query",
        re.compile(
            rf"{_START}(?:"
            r"رواته|رواتها|"
            r"(?:(?:ال)?رواة)\s+(?:(?:ال)?حديث|هذا|السند|الاسناد|الاسانيد)|"
            r"حكم\s+(?:رواته|رواة)|"
            r"(?:من|ما\s+اسماء|اذكر|سم)\s+(?:هم\s+)?(?:(?:ال)?رواة)"
            rf"){_END}"
        ),
    ),
    (
        "muslim_teacher_query",
        re.compile(
            rf"{_START}(?:"
            r"(?:شيخ|شيوخ|اساتذة)\s+(?:الامام\s+)?مسلم|"
            r"(?:عمن|عن\s+من|ممن)\s+(?:اخذ|رو[ىي]|سمع|تلق[ىي]|حدث)\s+(?:عنه\s+)?(?:الامام\s+)?مسلم|"
            r"(?:(?:ال)?راوي|الشيخ)\s+المباشر\s+(?:للامام\s+|ل)?مسلم|"
            r"(?:اخذ|تلق[ىي]|سمع)\s+(?:الامام\s+)?مسلم\s+(?:عنه|(?:ال)?حديث|هذا)"
            rf"){_END}"
        ),
    ),
    (
        "who_narrated_hadith",
        re.compile(
            rf"{_START}(?:"
            r"(?:من|ما\s+اسم|اي|سم)\s+(?:هو\s+|هي\s+|هم\s+|الذي\s+|التي\s+|الذين\s+)?(?:راوي|الراوي|ناقل)\s+(?:(?:ال)?حديث|هذا|عن)|"
            r"(?:من|اي)\s+(?:هو\s+|هي\s+|الذي\s+|التي\s+)?(?:رو[ىي]|روت|رواه|روته|يروي|تروي|نقل|نقلت)\s+(?:(?:ال)?حديث|هذا\s+(?:ال)?حديث|عن\s+(?:النبي|رسول)|في\s+صحيح)|"
            r"(?:(?:ال)?صحابي(?:[ةه])?\s+)راوي\s+(?:(?:ال)?حديث|هذا)|"
            r"(?:من|ما\s+اسم)\s+(?:هو\s+|هي\s+)?(?:ال)?صحابي(?:[ةه])?\b.*?(?:رو[ىي]|روت|يروي|تروي|رواه|روته|نقل|نقلت|تلق[ىي]|سند|اسناد|اسانيد|طرق|حديث\s*رقم|الحديث\s*رقم|لحديث|لهذا\s+الحديث)"
            rf"){_END}"
        ),
    ),
    (
        "narrator_membership_in_chain",
        re.compile(
            rf"{_START}(?:"
            r"هل\s+.*?(?:في|ضمن|من|بين|عبر)\s+(?:[وفبلك]?سند\b|سند[ها]?|[وفبلك]?(?:ال)?اسناد|[وفبلك]?(?:ال)?اسانيد|طرق\s+(?:(?:ال)?حديث|(?:ال)?رواي[ةه]|هذا)|احد\s+اسانيد|اي\s+(?:من\s+)?اسانيد|سلسل[ةه]|رواة)|"
            r"هل\s+(?:شارك|شاركت|رو[ىي]|روت|يروي|تروي|ظهر|ظهرت|يظهر|تظهر|ورد|وردت|يرد|ترد|وقع|وقعت|ذ?كر)\s+.*?(?:في\s+رواي[ةه]\s+(?:(?:ال)?حديث|هذا)|(?:(?:ال)?حديث)\s+رقم\s+\d+|في\s+(?:احد\s+)?(?:سند|اسناد|اسانيد|طرق))|"
            r"هل\s+\S+(?:\s+\S+){0,5}\s+(?:من|ضمن|احد|من\s+بين)\s+(?:رواة|شيوخ|اسانيد)\s+(?:(?:ال)?حديث|هذا|مسلم)"
            rf"){_END}"
        ),
    ),
)


def normalize_for_routing(text: str) -> str:
    """Normalize Arabic diacritics, alefs, and punctuation for rule matching."""
    cleaned = _DIACRITICS_RE.sub("", text or "")
    cleaned = _ALEF_RE.sub("ا", cleaned)
    cleaned = _PUNCT_RE.sub(" ", cleaned)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def matched_chain_rule(question: str) -> str | None:
    """Return the first matching v2 chain rule name for ``question``, else None."""
    norm = normalize_for_routing(question)
    if not norm:
        return None
    for rule_name, pattern in _CHAIN_RULES:
        if pattern.search(norm):
            return rule_name
    return None


def classify_intent_v2(question: str) -> RouteIntent:
    """Pure rule-based classifier (v2) with 0 API calls."""
    return "chain" if matched_chain_rule(question) is not None else "text"


@lru_cache(maxsize=1)
def load_router_weights(weights_path: Path = ROUTER_WEIGHTS_PATH) -> dict[str, Any] | None:
    """Load pre-trained L2 logistic regression parameters if present on disk."""
    if not weights_path.exists():
        return None
    data = np.load(weights_path, allow_pickle=True)
    meta_raw = data["metadata"][0] if "metadata" in data else "{}"
    meta = json.loads(str(meta_raw)) if meta_raw else {}
    return {
        "weights": np.asarray(data["weights"], dtype=np.float32),
        "intercept": float(data["intercept"][0]),
        "threshold": float(data["threshold"][0]),
        "metadata": meta,
    }


def predict_chain_probability(
    embedding: Any,
    *,
    model: dict[str, Any] | None = None,
) -> float:
    """Compute sigmoid probability of ``chain`` intent from a 3072-d query vector."""
    loaded = model if model is not None else load_router_weights()
    if loaded is None:
        raise RuntimeError("Router v3 weights artifact not found")
    vec = np.asarray(embedding, dtype=np.float32).reshape(-1)
    weights = loaded["weights"]
    if vec.shape != weights.shape:
        raise ValueError(f"Expected embedding shape {weights.shape}, got {vec.shape}")
    norm = float(np.linalg.norm(vec))
    if norm > 0.0:
        vec = vec / norm
    logit = float(np.dot(vec, weights) + loaded["intercept"])
    clipped = max(-50.0, min(50.0, logit))
    return 1.0 / (1.0 + math.exp(-clipped))


def _resolve_embedding(
    question: str,
    *,
    embedding: Any = None,
    retriever: Any = None,
    embedding_provider: Callable[[str], Any] | None = None,
) -> Any:
    if embedding is not None:
        return embedding
    if embedding_provider is not None:
        try:
            return embedding_provider(question)
        except Exception:
            return None
    if retriever is not None and callable(getattr(retriever, "get_query_embedding", None)):
        try:
            return retriever.get_query_embedding(question)
        except Exception:
            return None
    return None


def classify_intent_with_trace(
    question: str,
    *,
    embedding: Any = None,
    retriever: Any = None,
    embedding_provider: Callable[[str], Any] | None = None,
    version: str | None = None,
    weights_path: Path = ROUTER_WEIGHTS_PATH,
) -> dict[str, Any]:
    """Classify intent while returning decision path, probability, and latency_ms."""
    t0 = time.perf_counter()
    rule = matched_chain_rule(question)
    if rule is not None:
        return {
            "intent": "chain",
            "path": "v2_fast_path",
            "matched_rule": rule,
            "probability": 1.0,
            "latency_ms": (time.perf_counter() - t0) * 1000.0,
        }

    eff_version = (version or os.environ.get(ROUTER_VERSION_ENV_VAR, DEFAULT_ROUTER_VERSION)).strip().lower()
    if eff_version == "v2":
        return {
            "intent": "text",
            "path": "v2_rule_miss",
            "matched_rule": None,
            "probability": None,
            "latency_ms": (time.perf_counter() - t0) * 1000.0,
        }

    model = load_router_weights(weights_path)
    vec = _resolve_embedding(
        question,
        embedding=embedding,
        retriever=retriever,
        embedding_provider=embedding_provider,
    )
    if model is None or vec is None:
        return {
            "intent": "text",
            "path": "v2_fallback_no_embedding",
            "matched_rule": None,
            "probability": None,
            "latency_ms": (time.perf_counter() - t0) * 1000.0,
        }

    try:
        prob = predict_chain_probability(vec, model=model)
    except Exception:
        return {
            "intent": "text",
            "path": "v2_fallback_invalid_embedding",
            "matched_rule": None,
            "probability": None,
            "latency_ms": (time.perf_counter() - t0) * 1000.0,
        }

    intent: RouteIntent = "chain" if prob >= model["threshold"] else "text"
    return {
        "intent": intent,
        "path": "v3_logreg",
        "matched_rule": None,
        "probability": prob,
        "threshold": model["threshold"],
        "latency_ms": (time.perf_counter() - t0) * 1000.0,
    }


def classify_intent(
    question: str,
    *,
    embedding: Any = None,
    retriever: Any = None,
    embedding_provider: Callable[[str], Any] | None = None,
    version: str | None = None,
    weights_path: Path = ROUTER_WEIGHTS_PATH,
) -> RouteIntent:
    """Classify a question as ``'chain'`` or ``'text'`` using Router v3 (or v2 fallback)."""
    trace = classify_intent_with_trace(
        question,
        embedding=embedding,
        retriever=retriever,
        embedding_provider=embedding_provider,
        version=version,
        weights_path=weights_path,
    )
    return trace["intent"]
