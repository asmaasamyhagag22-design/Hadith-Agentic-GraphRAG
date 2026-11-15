"""Tests for recorded demo replay mode (MUSNAD_DEMO_REPLAY, missing creds, usage cap)."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import load_config
from app.replay import (
    load_recorded_runs,
    match_recorded_run,
    resolve_replay_mode,
    serve_recorded_run,
)
import app.state as app_state


def _sample_recorded_payload(tmp_path: Path) -> Path:
    runs = [
        {
            "id": "run_text",
            "category": "text",
            "question": "ما فضل قيام شهر رمضان إيمانًا واحتسابًا؟",
            "result": {
                "answer": "من قام رمضان إيمانًا واحتسابًا غفر له ما تقدم من ذنبه (المصدر: صحيح مسلم، حديث رقم 759).",
                "raw": "...",
                "chunks": [
                    {
                        "rank": 1,
                        "hadith_id": 759,
                        "text": "مَنْ قَامَ رَمَضَانَ إِيمَانًا وَاحْتِسَابًا غُفِرَ لَهُ مَا تَقَدَّمَ مِنْ ذَنْبِهِ",
                        "metadata": {"chapter_arabic": "كتاب صلاة المسافرين"},
                    }
                ],
                "sanad": [],
                "sanad_error": None,
                "agent_used": False,
                "agent_fallback": False,
                "regenerated": False,
            },
            "trace": {
                "events": [
                    {
                        "stage": "router",
                        "timestamp": 1.0,
                        "duration_ms": 18.4,
                        "offset_ms": 18.4,
                        "data": {"decision": "text", "source": "classifier", "probability": 0.04},
                    },
                    {
                        "stage": "retrieval",
                        "timestamp": 2.0,
                        "duration_ms": 4120.5,
                        "offset_ms": 4138.9,
                        "data": {
                            "hyde_text": "حديث في قيام رمضان.",
                            "top5": [{"rank": 1, "hadith_id": 759, "chapter": "كتاب صلاة المسافرين"}],
                            "legacy_fallback": False,
                        },
                    },
                    {
                        "stage": "generation",
                        "timestamp": 3.0,
                        "duration_ms": 2250.0,
                        "offset_ms": 6388.9,
                        "data": {"model": "gemini-4-argon", "attempts": 1, "pro_calls": 1},
                    },
                ],
                "summary": {
                    "total_duration_ms": 6395.0,
                    "event_count": 3,
                    "stages": ["router", "retrieval", "generation"],
                    "call_counts": {
                        "pro_calls": 1,
                        "flash_calls": 1,
                        "embed_calls": 3,
                        "tool_calls": 0,
                        "sqlite_queries": 0,
                    },
                },
            },
        },
        {
            "id": "run_chain",
            "category": "chain",
            "question": "من هم رواة حديث رقم 7294 وما عدد أسانيده؟",
            "result": {
                "answer": "روى الحديث أبو بكر بن أبي شيبة عن عبد الله بن العباس (المصدر: صحيح مسلم، حديث رقم 7294).",
                "raw": "...",
                "chunks": [
                    {
                        "rank": 1,
                        "hadith_id": 7294,
                        "text": "حدثنا حجاج بن الشاعر...",
                        "metadata": {"chapter_arabic": "كتاب الإيمان"},
                    }
                ],
                "sanad": [
                    {
                        "hadith_id": 7294,
                        "status": "LINKED_WITH_RECORDED_ISNAD",
                        "isnad_count": 4,
                        "isnads": [
                            [
                                {"chain_position": 1, "name_ar_mapped": "عبد الله بن العباس"},
                                {"chain_position": 2, "name_ar_mapped": "أبو بكر بن أبي شيبة"},
                            ]
                        ],
                    }
                ],
                "sanad_error": None,
                "agent_used": True,
                "agent_fallback": False,
                "regenerated": False,
            },
            "trace": {
                "events": [
                    {
                        "stage": "router",
                        "timestamp": 1.0,
                        "duration_ms": 1.2,
                        "offset_ms": 1.2,
                        "data": {"decision": "chain", "source": "regex", "probability": 1.0},
                    },
                    {
                        "stage": "agent",
                        "timestamp": 2.0,
                        "duration_ms": 15.0,
                        "offset_ms": 16.2,
                        "data": {
                            "name": "get_isnad",
                            "arguments": {"hadith_id": 7294},
                            "returned_ids": [7294],
                            "isnad_count": 4,
                            "source": "SQLite sanad graph",
                        },
                    },
                ],
                "summary": {
                    "total_duration_ms": 1820.0,
                    "event_count": 2,
                    "stages": ["router", "agent"],
                    "call_counts": {
                        "pro_calls": 2,
                        "flash_calls": 0,
                        "embed_calls": 0,
                        "tool_calls": 1,
                        "sqlite_queries": 1,
                    },
                },
            },
        },
    ]
    out = tmp_path / "recorded_runs.json"
    out.write_text(json.dumps({"schema_version": 1, "runs": runs}, ensure_ascii=False), encoding="utf-8")
    return out


def test_resolve_replay_mode_triggers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GCP_SERVICE_ACCOUNT_JSON"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MUSNAD_DISABLE_ADC", "1")
    monkeypatch.setenv("MUSNAD_DEMO_REPLAY", "0")

    cfg = load_config()
    is_rep, reason = resolve_replay_mode(cfg)
    assert is_rep is True
    assert reason and "اعتمادات" in reason

    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    cfg_live = load_config()
    assert resolve_replay_mode(cfg_live) == (False, None)

    is_cap, cap_reason = resolve_replay_mode(cfg_live, usage_capped_reason="تم بلوغ الحد اليومي")
    assert is_cap is True
    assert cap_reason == "تم بلوغ الحد اليومي"

    monkeypatch.setenv("MUSNAD_DEMO_REPLAY", "1")
    cfg_flag = load_config()
    is_flag, flag_reason = resolve_replay_mode(cfg_flag)
    assert is_flag is True
    assert flag_reason and "MUSNAD_DEMO_REPLAY=1" in flag_reason


def test_match_and_serve_recorded_run_preserves_durations(tmp_path: Path):
    replay_file = _sample_recorded_payload(tmp_path)
    runs = load_recorded_runs(replay_file)
    assert len(runs) == 2

    # Normalized exact match (stripped alef/diacritics variant)
    matched, exact = match_recorded_run("ما فضل قيام شهر رمضان ايمانا واحتسابا", runs)
    assert exact is True
    assert matched is not None and matched["id"] == "run_text"

    # Closest fuzzy match
    fuzzy, exact_fuzzy = match_recorded_run("كم طريق حديث رقم 7294؟", runs)
    assert exact_fuzzy is False
    assert fuzzy is not None and fuzzy["id"] == "run_chain"

    seen: list[int] = []
    res, trace = serve_recorded_run(
        matched,
        on_progress=lambda evs: seen.append(len(evs)),
        pace=True,
        speed_scale=0.002,
        max_step_delay_s=0.01,
    )
    assert seen == [0, 1, 2, 3]
    assert res["answer"].startswith("من قام رمضان")
    assert trace["events"][1]["duration_ms"] == 4120.5
    assert trace["summary"]["total_duration_ms"] == 6395.0


def test_streamlit_app_replay_explicit_and_missing_creds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    replay_file = _sample_recorded_payload(tmp_path)
    monkeypatch.setenv("MUSNAD_REPLAY_PATH", str(replay_file))
    monkeypatch.setenv("MUSNAD_REPLAY_SPEED", "0")

    monkeypatch.setattr(
        app_state,
        "warm_up_resources",
        lambda cfg, mode, *, load_pipeline=True: {
            "router_ready": True,
            "sanad_ready": True,
            "pipeline_ready": False,
            "hadith_count": 5300,
            "pipeline": None,
            "matn_by_hadith_id": {},
            "error": None,
        },
    )
    monkeypatch.setattr(
        app_state,
        "answer_with_details",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("Live pipeline must not be called in replay mode")),
    )

    # 1) Explicit MUSNAD_DEMO_REPLAY=1
    monkeypatch.setenv("MUSNAD_DEMO_REPLAY", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"))
    at.run(timeout=30)
    chain_btn = next(b for b in at.button if "سؤال إسنادي" in b.label)
    chain_btn.click().run(timeout=30)
    assert not at.exception
    md = "\n".join(m.value for m in at.markdown)
    assert "Recorded run — replayed" in md
    assert "1.82 s" in md
    assert "عبد الله بن العباس" in md

    # 2) Automatic replay when no credentials exist
    monkeypatch.setenv("MUSNAD_DEMO_REPLAY", "0")
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GCP_SERVICE_ACCOUNT_JSON"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MUSNAD_DISABLE_ADC", "1")

    at_auto = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"))
    at_auto.run(timeout=30)
    text_btn = next(b for b in at_auto.button if "رمضان" in b.label)
    text_btn.click().run(timeout=30)
    assert not at_auto.exception
    md_auto = "\n".join(m.value for m in at_auto.markdown)
    assert "Recorded run — replayed" in md_auto
    assert "اعتمادات" in md_auto
    assert "4.12 s" in md_auto


def test_real_recorded_runs_json_valid_if_present():
    real_path = ROOT / "data" / "demo" / "recorded_runs.json"
    if not real_path.is_file():
        pytest.skip("recorded_runs.json not generated yet")
    runs = load_recorded_runs(real_path)
    assert len(runs) == 10
    categories = [r.get("category", "") for r in runs]
    assert sum(1 for c in categories if c == "text") >= 2
    assert any(c == "chain_topic" for c in categories)
    assert sum(1 for c in categories if str(c).startswith("chain")) >= 3
    assert any(c == "refusal" for c in categories)
    assert any(c == "narrator" for c in categories)
    for r in runs:
        assert r["result"]["answer"]
        events = r["trace"]["events"]
        assert len(events) >= 3
        assert all(float(ev["duration_ms"]) >= 0.0 for ev in events)
        assert float(r["trace"]["summary"]["total_duration_ms"]) > 0.0
