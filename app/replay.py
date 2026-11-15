"""Recorded-run replay support for offline mode, missing credentials, or quota limits."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Callable

from app.config import AppConfig
from app.state import enrich_chunks_matn, has_live_credentials
from src.router import normalize_for_routing

REPLAY_BANNER_TEXT = "عرض مسجَّل مسبقًا (بدون اتصال)"


def load_recorded_runs(replay_path: Path) -> list[dict[str, Any]]:
    """Load recorded demo runs with full execution traces from disk."""
    path = Path(replay_path)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    runs = payload.get("runs") if isinstance(payload, dict) else payload
    if not isinstance(runs, list):
        return []
    return [dict(item) for item in runs if isinstance(item, dict) and item.get("result")]


def match_recorded_run(
    question: str,
    runs: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, bool]:
    """Find exact normalized question match, or best token-overlap match among recorded runs."""
    if not runs:
        return None, False

    q_norm = normalize_for_routing(question)
    if not q_norm:
        return runs[0], False

    for run in runs:
        if normalize_for_routing(str(run.get("question") or "")) == q_norm:
            return run, True

    q_tokens = set(q_norm.split())
    best_run = runs[0]
    best_score = -1.0
    for run in runs:
        r_norm = normalize_for_routing(str(run.get("question") or ""))
        r_tokens = set(r_norm.split())
        if not q_tokens or not r_tokens:
            score = 0.0
        else:
            inter = len(q_tokens & r_tokens)
            union = len(q_tokens | r_tokens)
            score = inter / union if union else 0.0
        # Slight tie-break boost when both share numeric/chain cues
        if ("رقم" in q_norm) == ("رقم" in r_norm):
            score += 0.05
        if score > best_score:
            best_score = score
            best_run = run

    return best_run, False


def resolve_replay_mode(
    config: AppConfig,
    *,
    usage_capped_reason: str | None = None,
) -> tuple[bool, str | None]:
    """Determine whether queries should use recorded replay mode and return pure Arabic banner copy."""
    if config.demo_replay:
        return True, REPLAY_BANNER_TEXT

    if usage_capped_reason:
        return True, REPLAY_BANNER_TEXT

    creds_ok, _ = has_live_credentials(config)
    if not creds_ok:
        return True, REPLAY_BANNER_TEXT

    return False, None


def make_replay_banner_reason(
    base_reason: str | None = None,
    *,
    matched_question: str | None = None,
    exact_match: bool = True,
) -> str:
    """Return the single concise Arabic replay banner text for the main UI."""
    del matched_question, exact_match  # kept for backward-compatible call signature
    return base_reason.strip() if base_reason and base_reason.strip() == REPLAY_BANNER_TEXT else REPLAY_BANNER_TEXT


def serve_recorded_run(
    run: dict[str, Any],
    *,
    matn_by_hadith_id: dict[int, str] | None = None,
    on_progress: Callable[[list[dict[str, Any]]], None] | None = None,
    pace: bool = True,
    speed_scale: float = 1.0,
    max_step_delay_s: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Replay a recorded run and its real step durations progressively."""
    trace_payload = dict(run.get("trace") or {})
    events = list(trace_payload.get("events") or [])
    summary = dict(trace_payload.get("summary") or {})

    if on_progress is not None:
        on_progress([])
        emitted: list[dict[str, Any]] = []
        for ev in events:
            if pace:
                dur_s = max(float(ev.get("duration_ms") or 0.0) / 1000.0, 0.0) * max(speed_scale, 0.0)
                if max_step_delay_s is not None:
                    dur_s = min(dur_s, max_step_delay_s)
                if dur_s > 0.0:
                    time.sleep(dur_s)
            emitted.append(dict(ev))
            on_progress(list(emitted))

    result = dict(run.get("result") or {})
    if matn_by_hadith_id and result.get("chunks"):
        result["chunks"] = enrich_chunks_matn(list(result["chunks"]), matn_by_hadith_id)

    reconstructed_trace = {
        "events": [dict(ev) for ev in events],
        "summary": summary,
    }
    return result, reconstructed_trace
