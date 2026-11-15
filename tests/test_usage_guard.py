"""Tests for session, per-IP hourly, and global daily usage caps."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import boto3
from moto import mock_aws
from streamlit.testing.v1 import AppTest

from app.config import AppConfig, load_config
from app.usage_guard import (
    DynamoUsageBackend,
    InMemoryUsageBackend,
    acquire_usage_slot,
    daily_counter_key,
    extract_client_ip,
    ip_hourly_counter_key,
    peek_usage_limits,
    resolve_usage_backend,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _cfg(**overrides: object) -> AppConfig:
    defaults: dict[str, object] = {
        "session_limit": 2,
        "ip_hourly_limit": 3,
        "daily_cap": 5,
        "usage_table": "",
        "demo_replay": False,
        "cloud_mode": False,
        "replay_path": REPO_ROOT / "data" / "demo" / "recorded_runs.json",
    }
    defaults.update(overrides)
    return replace(load_config(), **defaults)  # type: ignore[arg-type]


def test_extract_client_ip_prioritizes_x_forwarded_for() -> None:
    ip = extract_client_ip(
        headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1", "Host": "example.com"},
        ip_address="10.0.0.2",
    )
    assert ip == "203.0.113.9"

    assert extract_client_ip(headers={"x-forwarded-for": "  "}, ip_address="198.51.100.4") == "198.51.100.4"
    assert extract_client_ip(headers={}, ip_address=None) == "unknown"


def test_counter_key_formats_and_ttl() -> None:
    dt = datetime(2026, 11, 15, 14, 35, 0, tzinfo=timezone.utc)
    d_key, d_exp = daily_counter_key(dt)
    ip_key, ip_exp = ip_hourly_counter_key("198.51.100.7", dt)

    assert d_key == "DAILY#2026-11-15"
    assert d_exp == int(dt.timestamp()) + 2 * 86400
    assert ip_key == "IP#198.51.100.7#2026-11-15T14"
    assert ip_exp == int(dt.timestamp()) + 2 * 3600


def test_in_memory_backend_session_ip_daily_and_ttl_rollover() -> None:
    now_holder = [datetime(2026, 11, 15, 10, 0, 0, tzinfo=timezone.utc)]
    backend = InMemoryUsageBackend(now_fn=lambda: int(now_holder[0].timestamp()))
    cfg = _cfg(session_limit=2, ip_hourly_limit=2, daily_cap=3)

    # Peek should not mutate counts
    peek0 = peek_usage_limits(cfg, session_count=0, client_ip="1.1.1.1", backend=backend, now=now_holder[0])
    assert peek0.allowed is True
    assert peek0.daily_count == 0
    assert peek0.ip_hourly_count == 0

    # Acquire two slots for IP 1.1.1.1 (session 0 -> 1)
    d1 = acquire_usage_slot(cfg, session_count=0, client_ip="1.1.1.1", backend=backend, now=now_holder[0])
    d2 = acquire_usage_slot(cfg, session_count=1, client_ip="1.1.1.1", backend=backend, now=now_holder[0])
    assert d1.allowed is True and d1.daily_count == 1 and d1.ip_hourly_count == 1
    assert d2.allowed is True and d2.daily_count == 2 and d2.ip_hourly_count == 2

    # Session cap blocks third in same session
    d_sess = acquire_usage_slot(cfg, session_count=2, client_ip="1.1.1.1", backend=backend, now=now_holder[0])
    assert d_sess.allowed is False
    assert d_sess.reason_code == "session_limit"
    assert "العرض المسجّل" in (d_sess.banner_reason or "")

    # New session on SAME IP still blocked by per-IP hourly limit (and must NOT burn daily slot!)
    d_ip = acquire_usage_slot(cfg, session_count=0, client_ip="1.1.1.1", backend=backend, now=now_holder[0])
    assert d_ip.allowed is False
    assert d_ip.reason_code == "ip_hourly_limit"
    assert d_ip.daily_count == 2  # untouched

    # Different IP takes 3rd daily slot, 4th global blocked by daily_cap
    d3 = acquire_usage_slot(cfg, session_count=0, client_ip="2.2.2.2", backend=backend, now=now_holder[0])
    assert d3.allowed is True and d3.daily_count == 3
    d_daily = acquire_usage_slot(cfg, session_count=0, client_ip="3.3.3.3", backend=backend, now=now_holder[0])
    assert d_daily.allowed is False
    assert d_daily.reason_code == "daily_cap"

    # Advance clock 2 days + 1s: TTL expires counters cleanly
    now_holder[0] = datetime(2026, 11, 17, 10, 0, 1, tzinfo=timezone.utc)
    d_reset = acquire_usage_slot(cfg, session_count=0, client_ip="1.1.1.1", backend=backend, now=now_holder[0])
    assert d_reset.allowed is True
    assert d_reset.daily_count == 1
    assert d_reset.ip_hourly_count == 1


@mock_aws
def test_dynamo_backend_atomic_caps_and_ttl(monkeypatch) -> None:
    monkeypatch.setattr("app.usage_guard._LOCAL_BACKEND", InMemoryUsageBackend())
    ddb = boto3.client("dynamodb", region_name="us-east-1")
    table_name = "musnad-usage-test"
    ddb.create_table(
        TableName=table_name,
        KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.update_time_to_live(
        TableName=table_name,
        TimeToLiveSpecification={"Enabled": True, "AttributeName": "expires_at"},
    )

    cfg = _cfg(session_limit=10, ip_hourly_limit=2, daily_cap=3, usage_table=table_name)
    backend = DynamoUsageBackend(table_name, region_name="us-east-1", client=ddb)
    now = datetime(2026, 11, 15, 16, 0, 0, tzinfo=timezone.utc)

    # Acquire 2 slots from IP A -> allowed
    r1 = acquire_usage_slot(cfg, session_count=0, client_ip="192.0.2.10", backend=backend, now=now)
    r2 = acquire_usage_slot(cfg, session_count=1, client_ip="192.0.2.10", backend=backend, now=now)
    assert r1.allowed and r2.allowed
    assert r2.daily_count == 2 and r2.ip_hourly_count == 2

    # 3rd slot from IP A blocked at ip_hourly_limit=2
    r3_ip = acquire_usage_slot(cfg, session_count=2, client_ip="192.0.2.10", backend=backend, now=now)
    assert r3_ip.allowed is False
    assert r3_ip.reason_code == "ip_hourly_limit"

    # IP B takes remaining 3rd daily slot
    r3_other = acquire_usage_slot(cfg, session_count=0, client_ip="192.0.2.20", backend=backend, now=now)
    assert r3_other.allowed and r3_other.daily_count == 3

    # IP C fails cleanly at daily_cap=3 via DynamoDB ConditionalCheckFailedException
    r4_daily = acquire_usage_slot(cfg, session_count=0, client_ip="192.0.2.30", backend=backend, now=now)
    assert r4_daily.allowed is False
    assert r4_daily.reason_code == "daily_cap"
    assert r4_daily.daily_count == 3

    # Inspect raw DynamoDB item to verify TTL attribute & exact counter
    d_key, _ = daily_counter_key(now)
    item = ddb.get_item(TableName=table_name, Key={"pk": {"S": d_key}})["Item"]
    assert int(item["count"]["N"]) == 3
    assert int(item["expires_at"]["N"]) > int(now.timestamp())
    assert item["counter_kind"]["S"] == "daily_global"

    # Missing table degrades gracefully to in-memory guard rather than crashing
    broken_backend = DynamoUsageBackend("does-not-exist", region_name="us-east-1", client=ddb)
    res_fallback = acquire_usage_slot(cfg, session_count=0, client_ip="192.0.2.40", backend=broken_backend, now=now)
    assert res_fallback.allowed is True


def test_resolve_usage_backend_switches_on_table_env() -> None:
    assert isinstance(resolve_usage_backend(_cfg(usage_table="")), InMemoryUsageBackend)
    assert isinstance(resolve_usage_backend(_cfg(usage_table="my-table")), DynamoUsageBackend)


def test_streamlit_switches_to_replay_when_session_or_daily_cap_hit(monkeypatch) -> None:
    local_backend = InMemoryUsageBackend()
    monkeypatch.setattr("app.usage_guard._LOCAL_BACKEND", local_backend)
    monkeypatch.setenv("MUSNAD_DEMO_REPLAY", "0")
    monkeypatch.setenv("MUSNAD_REPLAY_SPEED", "0")
    monkeypatch.setenv("MUSNAD_SESSION_LIMIT", "1")
    monkeypatch.setenv("MUSNAD_IP_HOURLY_LIMIT", "10")
    monkeypatch.setenv("MUSNAD_DAILY_CAP", "2")
    monkeypatch.setenv("MUSNAD_USAGE_TABLE", "")

    calls: list[str] = []

    def _fake_warm_up(config, retrieval_mode, load_pipeline=True):
        return {
            "router_ready": True,
            "sanad_ready": True,
            "hadith_count": 7563,
            "pipeline_ready": True,
            "pipeline": object(),
            "matn_by_hadith_id": {7306: "حدثنا يحيى..."},
            "error": None,
        }

    def _fake_execute_live(
        question,
        pipeline,
        *,
        top_k=5,
        use_agent=None,
        sanad_db_path=None,
        matn_by_hadith_id=None,
        on_progress=None,
    ):
        calls.append(question)
        return (
            {
                "answer": "إجابة حية موثقة.",
                "cited_ids": [7306],
                "valid": True,
                "mode": "chain",
                "route_reason": "agent",
                "chunks": [],
                "sanads": {},
            },
            {"events": [], "summary": {"total_ms": 100.0, "api_calls": 1, "tool_calls": 0}},
            None,
        )

    fake_run = {
        "id": "r1",
        "category": "chain",
        "question": "ما أسانيد حديث رقم 7306؟",
        "result": {
            "answer": "إجابة مسجلة موثقة.",
            "cited_ids": [7306],
            "valid": True,
            "mode": "chain",
            "route_reason": "agent",
            "chunks": [],
            "sanads": {},
        },
        "trace": {"events": [], "summary": {"total_ms": 50.0, "api_calls": 1, "tool_calls": 0}},
    }

    monkeypatch.setattr("app.state.warm_up_resources", _fake_warm_up)
    monkeypatch.setattr("app.state.execute_live_query", _fake_execute_live)
    monkeypatch.setattr("app.state.has_live_credentials", lambda cfg: (True, "mock"))
    monkeypatch.setattr("app.replay.has_live_credentials", lambda cfg: (True, "mock"))
    monkeypatch.setattr("app.replay.load_recorded_runs", lambda _p: [fake_run])

    def _submit(app: AppTest, q: str) -> None:
        app.text_area(key="question_input").set_value(q)
        submit = [b for b in app.button if "اسأل" in b.label][0]
        submit.click()
        app.run()

    # Run 1: Live slot 1/1 succeeds
    at = AppTest.from_file(str(REPO_ROOT / "app" / "streamlit_app.py"))
    at.run()
    assert not at.exception
    _submit(at, "سؤال حي أول")
    assert not at.exception
    assert len(calls) == 1
    assert at.session_state["live_query_count"] == 1

    # Run 2 in same session: session limit (1) reached -> automatic replay banner & zero extra live call
    _submit(at, "سؤال ثانٍ يتجاوز حد الجلسة")
    assert not at.exception
    assert len(calls) == 1  # NOT incremented!
    assert "Recorded run — replayed" in " ".join(x.value for x in at.info)

    # Fresh session when global daily cap (2) is reached after 1 more fresh query
    at2 = AppTest.from_file(str(REPO_ROOT / "app" / "streamlit_app.py"))
    at2.run()
    _submit(at2, "سؤال حي ثانٍ يستهلك السقف اليومي")
    assert len(calls) == 2

    at3 = AppTest.from_file(str(REPO_ROOT / "app" / "streamlit_app.py"))
    at3.run()
    assert "Recorded run — replayed" in " ".join(x.value for x in at3.info)
    _submit(at3, "سؤال بعد نفاد السقف اليومي")
    assert not at3.exception
    assert len(calls) == 2
