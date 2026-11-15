"""Optional observational trace collector for Musnad request pipelines.

Disabled by default (`trace=None`) so existing callers and evaluations incur
zero overhead and produce byte-identical outputs. When enabled, router,
retrieval, agent, generation, validation, and sanad attachment emit structured
``TraceEvent`` records with timestamps and stage durations.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TraceEvent:
    """Single observational trace event emitted during a query."""

    stage: str
    timestamp: float
    duration_ms: float
    offset_ms: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "offset_ms": self.offset_ms,
            "data": dict(self.data),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TraceEvent:
        return cls(
            stage=str(payload["stage"]),
            timestamp=float(payload["timestamp"]),
            duration_ms=float(payload["duration_ms"]),
            offset_ms=float(payload.get("offset_ms", 0.0)),
            data=dict(payload.get("data") or {}),
        )


class TraceCollector:
    """Thread-safe observational trace collector with optional live callback."""

    def __init__(self, on_event: Callable[[TraceEvent], None] | None = None) -> None:
        self._lock = threading.Lock()
        self.started_at: float = time.time()
        self._t0: float = time.perf_counter()
        self.events: list[TraceEvent] = []
        self.on_event = on_event
        self.finished_duration_ms: float | None = None

    def elapsed_ms(self) -> float:
        """Total elapsed wall-clock milliseconds since collector creation (or finish)."""
        if self.finished_duration_ms is not None:
            return self.finished_duration_ms
        return round((time.perf_counter() - self._t0) * 1000.0, 3)

    def finish(self) -> float:
        """Freeze and return the total duration in milliseconds."""
        self.finished_duration_ms = round((time.perf_counter() - self._t0) * 1000.0, 3)
        return self.finished_duration_ms

    def record(
        self,
        stage: str,
        *,
        duration_ms: float = 0.0,
        timestamp: float | None = None,
        offset_ms: float | None = None,
        **data: Any,
    ) -> TraceEvent:
        """Append a ``TraceEvent`` and invoke ``on_event`` if configured."""
        ts = time.time() if timestamp is None else float(timestamp)
        off = (
            (time.perf_counter() - self._t0) * 1000.0
            if offset_ms is None
            else float(offset_ms)
        )
        event = TraceEvent(
            stage=stage,
            timestamp=ts,
            duration_ms=round(float(duration_ms), 3),
            offset_ms=round(off, 3),
            data=data,
        )
        with self._lock:
            self.events.append(event)
            cb = self.on_event
        if cb is not None:
            cb(event)
        return event

    def record_router(
        self,
        *,
        decision: str,
        source: str,
        probability: float | None = None,
        duration_ms: float = 0.0,
        **extra: Any,
    ) -> TraceEvent:
        return self.record(
            "router",
            duration_ms=duration_ms,
            decision=decision,
            source=source,
            probability=probability,
            **extra,
        )

    def record_retrieval(
        self,
        *,
        hyde_text: str | None,
        top5: list[dict[str, Any]],
        legacy_fallback: bool = False,
        duration_ms: float = 0.0,
        **extra: Any,
    ) -> TraceEvent:
        return self.record(
            "retrieval",
            duration_ms=duration_ms,
            hyde_text=hyde_text,
            top5=list(top5),
            legacy_fallback=bool(legacy_fallback),
            **extra,
        )

    def record_agent_tool(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
        returned_ids: list[int],
        duration_ms: float = 0.0,
        **extra: Any,
    ) -> TraceEvent:
        return self.record(
            "agent",
            duration_ms=duration_ms,
            name=name,
            arguments=dict(arguments),
            returned_ids=list(returned_ids),
            agent_fallback=False,
            **extra,
        )

    def record_agent_fallback(
        self,
        *,
        fallback_reason: str,
        duration_ms: float = 0.0,
        **extra: Any,
    ) -> TraceEvent:
        return self.record(
            "agent",
            duration_ms=duration_ms,
            name=None,
            arguments=None,
            returned_ids=[],
            agent_fallback=True,
            fallback_reason=fallback_reason,
            **extra,
        )

    def record_generation(
        self,
        *,
        model: str,
        attempts: int,
        duration_ms: float = 0.0,
        **extra: Any,
    ) -> TraceEvent:
        return self.record(
            "generation",
            duration_ms=duration_ms,
            model=model,
            attempts=int(attempts),
            **extra,
        )

    def record_validation(
        self,
        *,
        status: str,
        retry_reason: str | None = None,
        refusal_reason: str | None = None,
        duration_ms: float = 0.0,
        **extra: Any,
    ) -> TraceEvent:
        return self.record(
            "validation",
            duration_ms=duration_ms,
            status=status,
            retry_reason=retry_reason,
            refusal_reason=refusal_reason,
            **extra,
        )

    def record_sanad(
        self,
        *,
        hadith_id: int | None,
        status: str,
        isnad_count: int,
        ms: float,
        duration_ms: float | None = None,
        **extra: Any,
    ) -> TraceEvent:
        dur = ms if duration_ms is None else duration_ms
        return self.record(
            "sanad",
            duration_ms=dur,
            hadith_id=hadith_id,
            status=status,
            isnad_count=int(isnad_count),
            ms=round(float(ms), 3),
            **extra,
        )

    def stages(self) -> list[str]:
        """Return ordered list of event stage names."""
        with self._lock:
            return [ev.stage for ev in self.events]

    def summary(self) -> dict[str, Any]:
        """Summarize total latency and API/tool/DB call counts."""
        with self._lock:
            events = list(self.events)
        pro_calls = 0
        flash_calls = 0
        embed_calls = 0
        tool_calls = 0
        sqlite_queries = 0
        for ev in events:
            d = ev.data
            if ev.stage == "router":
                embed_calls += int(d.get("embed_calls") or 0)
            elif ev.stage == "retrieval":
                flash_calls += int(d.get("flash_calls") or 0)
                embed_calls += int(d.get("embed_calls") or 0)
            elif ev.stage == "agent":
                if d.get("name"):
                    tool_calls += 1
                if d.get("name") == "get_isnad":
                    sqlite_queries += 1
                if d.get("agent_fallback"):
                    pro_calls += int(d.get("pro_calls") or 0)
            elif ev.stage == "generation":
                pro_calls += int(d.get("pro_calls") or d.get("attempts") or 0)
            elif ev.stage == "sanad" and d.get("status") != "error":
                sqlite_queries += 1
        return {
            "total_duration_ms": self.elapsed_ms(),
            "event_count": len(events),
            "stages": [ev.stage for ev in events],
            "call_counts": {
                "pro_calls": pro_calls,
                "flash_calls": flash_calls,
                "embed_calls": embed_calls,
                "tool_calls": tool_calls,
                "sqlite_queries": sqlite_queries,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            events = [ev.to_dict() for ev in self.events]
        return {
            "started_at": self.started_at,
            "total_duration_ms": self.elapsed_ms(),
            "events": events,
            "summary": self.summary(),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TraceCollector:
        collector = cls()
        collector.started_at = float(payload.get("started_at", collector.started_at))
        total_ms = payload.get("total_duration_ms")
        if total_ms is not None:
            collector.finished_duration_ms = float(total_ms)
        collector.events = [
            TraceEvent.from_dict(ev) for ev in (payload.get("events") or ())
        ]
        return collector
