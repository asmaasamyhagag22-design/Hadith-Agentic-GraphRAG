"""Session state, resource caching, credential bootstrap, and live execution helpers."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import traceback
from typing import Any, Callable

import streamlit as st
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.config import AppConfig
from src.answer import REFUSAL, answer_with_details
from src.pipeline import build_pipeline
from src.retrieve import load_chunk_lookup
from src.router import load_router_weights
from src.sanad_context import open_graph
from src.trace import TraceCollector

logger = logging.getLogger("musnad.app")

_CREDENTIALS_BOOTSTRAPPED = False


def configure_logging(level: str = "INFO") -> None:
    """Configure application logging cleanly without exposing secrets."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger("musnad")
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(numeric)


def bootstrap_environment(config: AppConfig) -> None:
    """Load local .env (if present) and materialize GCP SA JSON env var if provided."""
    global _CREDENTIALS_BOOTSTRAPPED
    if not _CREDENTIALS_BOOTSTRAPPED:
        env_file = _ROOT / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)
        _CREDENTIALS_BOOTSTRAPPED = True
    ensure_gcp_credentials_file(config)


def ensure_gcp_credentials_file(config: AppConfig) -> str | None:
    """Write GCP_SERVICE_ACCOUNT_JSON to a restrictive temp file when needed for google-genai."""
    existing = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if existing and Path(existing).is_file():
        return existing

    raw_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw_json:
        return None

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.error("GCP_SERVICE_ACCOUNT_JSON environment variable is not valid JSON.")
        return None

    target_dir = Path(tempfile.gettempdir()) / "musnad_creds"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "gcp_service_account.json"
    target_path.write_text(raw_json, encoding="utf-8")
    os.chmod(target_path, 0o600)

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(target_path)
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
    if isinstance(parsed, dict) and parsed.get("project_id"):
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", str(parsed["project_id"]))
    if config.gcp_project and not os.getenv("GOOGLE_CLOUD_PROJECT"):
        os.environ["GOOGLE_CLOUD_PROJECT"] = config.gcp_project
    if config.gcp_location and not os.getenv("GOOGLE_CLOUD_LOCATION"):
        os.environ["GOOGLE_CLOUD_LOCATION"] = config.gcp_location
    return str(target_path)


def has_live_credentials(config: AppConfig | None = None) -> tuple[bool, str]:
    """Check whether Gemini/Vertex credentials exist in the runtime environment."""
    if os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_API_KEY", "").strip():
        return True, "api_key"

    sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if sa_path and Path(sa_path).is_file():
        return True, "service_account_file"

    if os.getenv("GCP_SERVICE_ACCOUNT_JSON", "").strip():
        if config is not None:
            path = ensure_gcp_credentials_file(config)
            if path:
                return True, "service_account_env"
        else:
            return True, "service_account_env"

    if os.getenv("MUSNAD_DISABLE_ADC", "").strip().lower() in {"1", "true", "yes"}:
        return False, "missing_credentials"

    project = (
        os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        or os.getenv("GCP_PROJECT", "").strip()
        or (config.gcp_project if config is not None else "")
    )
    if project:
        try:
            import google.auth

            creds, _ = google.auth.default()
            if creds is not None:
                return True, "adc"
        except Exception:
            pass

    return False, "missing_credentials"


def build_matn_index(chunk_lookup: dict[str, dict[str, Any]]) -> dict[int, str]:
    """Index combined vocalised matn text by local hadith ID."""
    grouped: dict[int, list[tuple[str, str]]] = {}
    for cid, chunk in chunk_lookup.items():
        meta = chunk.get("metadata") or {}
        raw_pid = meta.get("parent_id") or meta.get("id_in_book")
        if raw_pid is None:
            continue
        try:
            hid = int(raw_pid)
        except (TypeError, ValueError):
            continue
        text = str(chunk.get("text") or "").strip()
        if text:
            grouped.setdefault(hid, []).append((str(cid), text))

    out: dict[int, str] = {}
    for hid, parts in grouped.items():
        parts.sort(key=lambda pair: pair[0])
        out[hid] = "\n".join(text for _, text in parts)
    return out


def enrich_chunks_matn(
    chunks: list[dict[str, Any]],
    matn_by_hadith_id: dict[int, str],
) -> list[dict[str, Any]]:
    """Fill missing vocalised matn text for direct get_isnad chunk records."""
    enriched: list[dict[str, Any]] = []
    for chunk in chunks:
        item = dict(chunk)
        current_text = str(item.get("text") or item.get("matn") or "").strip()
        if not current_text and item.get("hadith_id") is not None:
            try:
                hid = int(item["hadith_id"])
            except (TypeError, ValueError):
                hid = None
            if hid is not None and hid in matn_by_hadith_id:
                item["text"] = matn_by_hadith_id[hid]
        enriched.append(item)
    return enriched


@st.cache_resource(show_spinner=False)
def get_cached_router_weights(weights_path_str: str) -> dict[str, Any] | None:
    """Load and cache router v3 weights across reruns."""
    return load_router_weights(Path(weights_path_str))


@st.cache_resource(show_spinner=False)
def get_cached_sanad_info(db_path_str: str) -> dict[str, Any]:
    """Verify SQLite sanad graph readiness and cache summary metadata."""
    db_path = Path(db_path_str)
    if not db_path.exists():
        return {"ready": False, "db_path": str(db_path), "hadith_count": 0}
    conn = open_graph(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM local_hadith").fetchone()
        hadith_count = int(row["cnt"]) if row else 0
    finally:
        conn.close()
    return {"ready": True, "db_path": str(db_path), "hadith_count": hadith_count}


@st.cache_resource(show_spinner=False)
def get_cached_chunk_bundle(chunks_path_str: str) -> dict[str, Any]:
    """Load and cache processed Sahih Muslim chunks and matn lookup."""
    chunks_path = Path(chunks_path_str)
    if not chunks_path.exists():
        return {"chunk_lookup": {}, "matn_by_hadith_id": {}}
    lookup = load_chunk_lookup(chunks_path)
    return {
        "chunk_lookup": lookup,
        "matn_by_hadith_id": build_matn_index(lookup),
    }


@st.cache_resource(show_spinner=False)
def get_cached_pipeline(mode: str, chunks_path_str: str) -> Any:
    """Build and cache retrieval pipeline (vectors, caches, and router weights)."""
    bundle = get_cached_chunk_bundle(chunks_path_str)
    chunk_lookup = bundle["chunk_lookup"] or None
    return build_pipeline(
        mode=mode,
        chunks_path=Path(chunks_path_str),
        chunk_lookup=chunk_lookup,
    )


def warm_up_resources(
    config: AppConfig,
    retrieval_mode: str,
    *,
    load_pipeline: bool = True,
) -> dict[str, Any]:
    """Initialize cached indexes, graph readiness check, and router weights."""
    status: dict[str, Any] = {
        "router_ready": False,
        "sanad_ready": False,
        "pipeline_ready": False,
        "hadith_count": 0,
        "pipeline": None,
        "matn_by_hadith_id": {},
        "error": None,
    }
    try:
        weights = get_cached_router_weights(str(config.router_weights_path))
        status["router_ready"] = weights is not None

        sanad_info = get_cached_sanad_info(str(config.sanad_db_path))
        status["sanad_ready"] = bool(sanad_info.get("ready"))
        status["hadith_count"] = int(sanad_info.get("hadith_count") or 0)

        bundle = get_cached_chunk_bundle(str(config.chunks_path))
        status["matn_by_hadith_id"] = bundle["matn_by_hadith_id"]

        if load_pipeline:
            pipeline = get_cached_pipeline(retrieval_mode, str(config.chunks_path))
            status["pipeline"] = pipeline
            status["pipeline_ready"] = pipeline is not None
    except Exception as exc:
        logger.exception("Warm-up resource initialization failed")
        status["error"] = exc
    return status


def init_session_state(config: AppConfig) -> None:
    """Populate default Streamlit session state keys cleanly."""
    defaults: dict[str, Any] = {
        "question_input": "",
        "pending_question": None,
        "agent_mode": config.agent_mode,
        "retrieval_mode": config.pipeline_mode,
        "last_question": None,
        "last_result": None,
        "last_trace": None,
        "last_replay_reason": None,
        "last_error": None,
        "warmed_up": False,
        "session_query_count": 0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def resolve_use_agent_override(agent_mode: str) -> bool | None:
    """Convert UI agent mode selector ('auto'/'on'/'off') to answer_with_details arg."""
    if agent_mode == "on":
        return True
    if agent_mode == "off":
        return False
    return None


def execute_live_query(
    question: str,
    retriever: Any,
    *,
    top_k: int,
    use_agent: bool | None,
    sanad_db_path: Path,
    matn_by_hadith_id: dict[int, str],
    on_progress: Callable[[list[dict[str, Any]]], None] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any], Exception | None]:
    """Run answer_with_details in a worker thread while streaming trace events to UI."""
    event_q: queue.Queue = queue.Queue()
    trace = TraceCollector(on_event=event_q.put)
    collected: list[dict[str, Any]] = []
    outcome: dict[str, Any] = {"result": None, "error": None}
    done = threading.Event()

    def _worker() -> None:
        try:
            outcome["result"] = answer_with_details(
                question,
                retriever,
                k=top_k,
                sanad_db_path=sanad_db_path,
                use_agent=use_agent,
                trace=trace,
            )
        except Exception as exc:
            outcome["error"] = exc
        finally:
            trace.finish()
            done.set()

    if on_progress is not None:
        on_progress([])

    thread = threading.Thread(target=_worker, name="musnad-query-worker", daemon=True)
    thread.start()

    while not done.is_set() or not event_q.empty():
        updated = False
        try:
            ev = event_q.get(timeout=0.08)
            collected.append(ev.to_dict())
            updated = True
        except queue.Empty:
            pass
        while not event_q.empty():
            try:
                ev = event_q.get_nowait()
                collected.append(ev.to_dict())
                updated = True
            except queue.Empty:
                break
        if updated and on_progress is not None:
            on_progress(list(collected))

    thread.join()
    trace_dict = trace.to_dict()

    if outcome["error"] is not None:
        exc = outcome["error"]
        logger.exception("Error during live query execution", exc_info=exc)
        return None, trace_dict, exc

    result = dict(outcome["result"] or {})
    if not result.get("answer"):
        result["answer"] = REFUSAL
    if result.get("chunks"):
        result["chunks"] = enrich_chunks_matn(result["chunks"], matn_by_hadith_id)
    return result, trace_dict, None


def format_error_details(exc: Exception) -> tuple[str, str]:
    """Return a friendly Arabic error message and technical details string."""
    if isinstance(exc, TimeoutError):
        friendly = (
            "استغرقت خدمة التوليد وقتًا أطول من المهلة المحددة (45 ثانية) ولم تكتمل بعد إعادة المحاولة. "
            "يُرجى إعادة المحاولة مرة أخرى بعد قليل."
        )
    else:
        friendly = (
            "تعذّر إتمام البحث حاليًا بسبب خلل مؤقت في الاتصال أو خدمة التوليد. "
            "يمكنك المحاولة مجددًا أو التبديل إلى الوضع المحلي/المسجّل."
        )
    details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    return friendly, details
