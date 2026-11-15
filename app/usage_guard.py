"""Session, per-IP hourly, and global daily usage caps backed by DynamoDB or memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import os
import threading
from typing import Any, Mapping, Protocol

from app.config import AppConfig

logger = logging.getLogger("musnad.usage_guard")


@dataclass(frozen=True)
class UsageDecision:
    """Outcome of checking or acquiring live-query quota."""

    allowed: bool
    reason_code: str | None = None
    banner_reason: str | None = None
    session_count: int = 0
    ip_hourly_count: int = 0
    daily_count: int = 0


class UsageCounterBackend(Protocol):
    """Protocol for atomic increment-with-cap and read-only inspection."""

    def get_count(self, key: str) -> int: ...

    def increment_if_under(self, key: str, cap: int, *, expires_at: int, kind: str) -> tuple[bool, int]: ...


class InMemoryUsageBackend:
    """Thread-safe local counter store with TTL expiration (for offline/non-AWS runs)."""

    def __init__(self, *, now_fn: Any = None) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[int, int]] = {}  # key -> (count, expires_at)
        self._now_fn = now_fn or (lambda: int(datetime.now(timezone.utc).timestamp()))

    def _prune_if_expired(self, key: str, now_ts: int) -> None:
        entry = self._entries.get(key)
        if entry is not None and entry[1] <= now_ts:
            del self._entries[key]

    def get_count(self, key: str) -> int:
        now_ts = int(self._now_fn())
        with self._lock:
            self._prune_if_expired(key, now_ts)
            entry = self._entries.get(key)
            return int(entry[0]) if entry is not None else 0

    def increment_if_under(self, key: str, cap: int, *, expires_at: int, kind: str) -> tuple[bool, int]:
        now_ts = int(self._now_fn())
        with self._lock:
            self._prune_if_expired(key, now_ts)
            current = self._entries.get(key, (0, expires_at))[0]
            if current >= cap:
                return False, int(current)
            updated = current + 1
            self._entries[key] = (updated, int(expires_at))
            return True, int(updated)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


class DynamoUsageBackend:
    """Atomic DynamoDB counter store keyed by partition key ``pk`` with TTL ``expires_at``."""

    def __init__(
        self,
        table_name: str,
        *,
        region_name: str | None = None,
        client: Any = None,
    ) -> None:
        self.table_name = table_name
        self.region_name = (
            region_name
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or "us-east-1"
        )
        self._client = client

    def _ddb_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("dynamodb", region_name=self.region_name)
        return self._client

    def get_count(self, key: str) -> int:
        resp = self._ddb_client().get_item(
            TableName=self.table_name,
            Key={"pk": {"S": key}},
            ConsistentRead=True,
        )
        item = resp.get("Item") or {}
        raw_cnt = (item.get("count") or {}).get("N")
        if raw_cnt is None:
            return 0
        try:
            return int(raw_cnt)
        except (TypeError, ValueError):
            return 0

    def increment_if_under(self, key: str, cap: int, *, expires_at: int, kind: str) -> tuple[bool, int]:
        from botocore.exceptions import ClientError

        try:
            resp = self._ddb_client().update_item(
                TableName=self.table_name,
                Key={"pk": {"S": key}},
                UpdateExpression=(
                    "SET #cnt = if_not_exists(#cnt, :zero) + :one, "
                    "#ttl = if_not_exists(#ttl, :exp), "
                    "#kind = :kind"
                ),
                ConditionExpression="attribute_not_exists(#cnt) OR #cnt < :cap",
                ExpressionAttributeNames={
                    "#cnt": "count",
                    "#ttl": "expires_at",
                    "#kind": "counter_kind",
                },
                ExpressionAttributeValues={
                    ":zero": {"N": "0"},
                    ":one": {"N": "1"},
                    ":cap": {"N": str(int(cap))},
                    ":exp": {"N": str(int(expires_at))},
                    ":kind": {"S": kind},
                },
                ReturnValues="UPDATED_NEW",
            )
            new_cnt = int((resp.get("Attributes") or {}).get("count", {}).get("N", 1))
            return True, new_cnt
        except ClientError as exc:
            code = (exc.response or {}).get("Error", {}).get("Code", "")
            if code == "ConditionalCheckFailedException":
                return False, self.get_count(key)
            raise


_LOCAL_BACKEND = InMemoryUsageBackend()


def get_local_backend() -> InMemoryUsageBackend:
    """Return the process-wide in-memory counter backend."""
    return _LOCAL_BACKEND


def resolve_usage_backend(config: AppConfig) -> UsageCounterBackend:
    """Use DynamoDB when MUSNAD_USAGE_TABLE is set, else thread-safe in-memory counters."""
    table_name = (config.usage_table or "").strip()
    if table_name:
        return DynamoUsageBackend(table_name)
    return _LOCAL_BACKEND


def extract_client_ip(
    headers: Mapping[str, Any] | None = None,
    ip_address: str | None = None,
) -> str:
    """Extract client IP prioritizing X-Forwarded-For first hop, then st.context.ip_address."""
    if headers:
        for key, value in headers.items():
            if str(key).strip().lower() == "x-forwarded-for" and value:
                first = str(value).split(",")[0].strip()
                if first:
                    return first
    if ip_address and str(ip_address).strip():
        return str(ip_address).strip()
    return "unknown"


def get_streamlit_client_ip() -> str:
    """Read client IP safely from Streamlit runtime context when available."""
    try:
        import streamlit as st

        ctx = getattr(st, "context", None)
        if ctx is None:
            return "unknown"
        headers = getattr(ctx, "headers", None)
        ip_addr = getattr(ctx, "ip_address", None)
        return extract_client_ip(headers=headers, ip_address=ip_addr)
    except Exception:
        return "unknown"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def daily_counter_key(now: datetime | None = None) -> tuple[str, int]:
    """Return ('DAILY#YYYY-MM-DD', ttl_epoch_seconds)."""
    dt = (now or _utc_now()).astimezone(timezone.utc)
    key = f"DAILY#{dt.strftime('%Y-%m-%d')}"
    exp = int((dt + timedelta(days=2)).timestamp())
    return key, exp


def ip_hourly_counter_key(client_ip: str, now: datetime | None = None) -> tuple[str, int]:
    """Return ('IP#<ip>#YYYY-MM-DDTHH', ttl_epoch_seconds)."""
    dt = (now or _utc_now()).astimezone(timezone.utc)
    safe_ip = (client_ip or "unknown").strip() or "unknown"
    key = f"IP#{safe_ip}#{dt.strftime('%Y-%m-%dT%H')}"
    exp = int((dt + timedelta(hours=2)).timestamp())
    return key, exp


def _cap_message(reason_code: str, limit: int) -> str:
    if reason_code == "session_limit":
        return (
            f"وصلت هذه الجلسة إلى الحد الأقصى للاستفسارات الحية ({limit} استفسارًا)، "
            "لذا تم التحويل تلقائيًا إلى وضع العرض المسجّل."
        )
    if reason_code == "ip_hourly_limit":
        return (
            f"تم بلوغ الحد الساعي لاستخدام الشبكة الحالية ({limit} استفسارًا/ساعة)، "
            "لذا تم التحويل تلقائيًا إلى وضع العرض المسجّل."
        )
    return (
        f"تم بلوغ السقف اليومي العام للاستخدام الحي ({limit} استفسارًا/اليوم)، "
        "لذا تم التحويل تلقائيًا إلى وضع العرض المسجّل."
    )


def peek_usage_limits(
    config: AppConfig,
    *,
    session_count: int,
    client_ip: str | None = None,
    backend: UsageCounterBackend | None = None,
    now: datetime | None = None,
) -> UsageDecision:
    """Check whether any cap is already reached without incrementing counters."""
    resolved_ip = client_ip or get_streamlit_client_ip()
    store = backend or resolve_usage_backend(config)
    d_key, _ = daily_counter_key(now)
    ip_key, _ = ip_hourly_counter_key(resolved_ip, now)

    try:
        daily_cnt = store.get_count(d_key)
        ip_cnt = store.get_count(ip_key)
    except Exception as exc:
        logger.warning("Usage counter lookup failed (%s); using local fallback.", type(exc).__name__)
        daily_cnt = _LOCAL_BACKEND.get_count(d_key)
        ip_cnt = _LOCAL_BACKEND.get_count(ip_key)

    if session_count >= config.session_limit:
        return UsageDecision(
            allowed=False,
            reason_code="session_limit",
            banner_reason=_cap_message("session_limit", config.session_limit),
            session_count=session_count,
            ip_hourly_count=ip_cnt,
            daily_count=daily_cnt,
        )
    if ip_cnt >= config.ip_hourly_limit:
        return UsageDecision(
            allowed=False,
            reason_code="ip_hourly_limit",
            banner_reason=_cap_message("ip_hourly_limit", config.ip_hourly_limit),
            session_count=session_count,
            ip_hourly_count=ip_cnt,
            daily_count=daily_cnt,
        )
    if daily_cnt >= config.daily_cap:
        return UsageDecision(
            allowed=False,
            reason_code="daily_cap",
            banner_reason=_cap_message("daily_cap", config.daily_cap),
            session_count=session_count,
            ip_hourly_count=ip_cnt,
            daily_count=daily_cnt,
        )
    return UsageDecision(
        allowed=True,
        session_count=session_count,
        ip_hourly_count=ip_cnt,
        daily_count=daily_cnt,
    )


def acquire_usage_slot(
    config: AppConfig,
    *,
    session_count: int,
    client_ip: str | None = None,
    backend: UsageCounterBackend | None = None,
    now: datetime | None = None,
) -> UsageDecision:
    """Atomically reserve one live query slot across session, per-IP hourly, and daily caps."""
    resolved_ip = client_ip or get_streamlit_client_ip()
    store = backend or resolve_usage_backend(config)
    d_key, d_exp = daily_counter_key(now)
    ip_key, ip_exp = ip_hourly_counter_key(resolved_ip, now)

    if session_count >= config.session_limit:
        peek = peek_usage_limits(
            config,
            session_count=session_count,
            client_ip=resolved_ip,
            backend=store,
            now=now,
        )
        return peek

    def _acquire_with(active_store: UsageCounterBackend) -> UsageDecision:
        # Check global daily cap BEFORE taking an IP slot so a depleted daily pool stays clean,
        # then atomically increment daily first only after verifying IP availability.
        cur_ip = active_store.get_count(ip_key)
        if cur_ip >= config.ip_hourly_limit:
            cur_daily = active_store.get_count(d_key)
            return UsageDecision(
                allowed=False,
                reason_code="ip_hourly_limit",
                banner_reason=_cap_message("ip_hourly_limit", config.ip_hourly_limit),
                session_count=session_count,
                ip_hourly_count=cur_ip,
                daily_count=cur_daily,
            )

        daily_ok, new_daily = active_store.increment_if_under(
            d_key,
            config.daily_cap,
            expires_at=d_exp,
            kind="daily_global",
        )
        if not daily_ok:
            return UsageDecision(
                allowed=False,
                reason_code="daily_cap",
                banner_reason=_cap_message("daily_cap", config.daily_cap),
                session_count=session_count,
                ip_hourly_count=cur_ip,
                daily_count=new_daily,
            )

        ip_ok, new_ip = active_store.increment_if_under(
            ip_key,
            config.ip_hourly_limit,
            expires_at=ip_exp,
            kind="ip_hourly",
        )
        if not ip_ok:
            return UsageDecision(
                allowed=False,
                reason_code="ip_hourly_limit",
                banner_reason=_cap_message("ip_hourly_limit", config.ip_hourly_limit),
                session_count=session_count,
                ip_hourly_count=new_ip,
                daily_count=new_daily,
            )

        return UsageDecision(
            allowed=True,
            session_count=session_count,
            ip_hourly_count=new_ip,
            daily_count=new_daily,
        )

    try:
        return _acquire_with(store)
    except Exception as exc:
        logger.warning(
            "Usage backend %s failed (%s); falling back to local memory guard.",
            type(store).__name__,
            type(exc).__name__,
        )
        return _acquire_with(_LOCAL_BACKEND)
