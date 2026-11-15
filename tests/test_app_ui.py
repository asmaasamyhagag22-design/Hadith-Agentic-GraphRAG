"""Offline UI and component tests for the Musnad Streamlit application."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.components import (
    extra_routes_label,
    format_live_progress_line,
    format_narrator_chain_for_display,
    render_answer_card_html,
    render_sanad_chain_html,
    render_trace_panel_html,
)
from app.config import DEFAULT_EXAMPLES, load_config
import app.state as app_state


def test_config_reads_env_vars(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MUSNAD_APP_TITLE", "اختبار مسند")
    monkeypatch.setenv("MUSNAD_PIPELINE_MODE", "legacy")
    monkeypatch.setenv("MUSNAD_AGENT_MODE", "on")
    monkeypatch.setenv("MUSNAD_TOP_K", "7")
    monkeypatch.setenv("MUSNAD_DEMO_REPLAY", "true")
    monkeypatch.setenv("MUSNAD_DAILY_CAP", "150")
    cfg = load_config()
    assert cfg.app_title == "اختبار مسند"
    assert cfg.pipeline_mode == "legacy"
    assert cfg.agent_mode == "on"
    assert cfg.top_k == 7
    assert cfg.demo_replay is True
    assert cfg.daily_cap == 150

    monkeypatch.setenv("MUSNAD_CLOUD", "1")
    cloud_cfg = load_config()
    assert cloud_cfg.cloud_mode is True
    assert cloud_cfg.pipeline_mode == "upgraded"


def test_sanad_chip_ordering_extra_routes_and_trace_badges():
    chain = [
        {"chain_position": 1, "name_ar_mapped": "أبو هريرة"},
        {"chain_position": 2, "name_ar_mapped": "الأعرج"},
        {"chain_position": 3, "name_ar_mapped": "أبو الزناد"},
        {"chain_position": 4, "name_ar_mapped": "قتيبة بن سعيد"},
    ]
    ordered = format_narrator_chain_for_display(chain)
    assert [item["name"] for item in ordered] == [
        "قتيبة بن سعيد",
        "أبو الزناد",
        "الأعرج",
        "أبو هريرة",
    ]
    assert ordered[0]["role"] == "teacher"
    assert ordered[-1]["role"] == "companion"

    assert extra_routes_label(4, 1) == "+3 طرق أخرى"
    assert extra_routes_label(1, 1) == ""

    sanad_html = render_sanad_chain_html(
        {
            "hadith_id": 7306,
            "status": "LINKED_WITH_RECORDED_ISNAD",
            "isnad_count": 4,
            "isnads": [chain],
        }
    )
    assert "narrator-chip--companion" in sanad_html
    assert "+3 طرق أخرى" in sanad_html
    assert "source: SQLite sanad graph" not in sanad_html
    assert sanad_html.index("قتيبة بن سعيد") < sanad_html.index("أبو هريرة")

    assert format_live_progress_line([]) == "تحديد نوع السؤال…"
    assert format_live_progress_line([{"stage": "router"}]) == "تحديد نوع السؤال… البحث…"
    assert (
        format_live_progress_line([{"stage": "router"}, {"stage": "retrieval"}])
        == "تحديد نوع السؤال… البحث… صياغة الإجابة…"
    )
    assert (
        format_live_progress_line(
            [{"stage": "router"}, {"stage": "retrieval"}, {"stage": "generation"}]
        )
        == "تحديد نوع السؤال… البحث… صياغة الإجابة… إرفاق السند"
    )
    in_progress_html = render_trace_panel_html([], None, in_progress=True)
    assert "تحديد نوع السؤال…" in in_progress_html

    events = [
        {
            "stage": "router",
            "duration_ms": 12.5,
            "data": {"decision": "chain", "source": "regex", "probability": 1.0},
        },
        {
            "stage": "agent",
            "duration_ms": 42.0,
            "data": {
                "name": "get_isnad",
                "arguments": {"hadith_id": 7306},
                "returned_ids": [7306],
                "isnad_count": 4,
                "source": "SQLite sanad graph",
            },
        },
        {
            "stage": "sanad",
            "duration_ms": 3.1,
            "data": {
                "hadith_id": 7306,
                "status": "LINKED_WITH_RECORDED_ISNAD",
                "isnad_count": 4,
                "ms": 3.1,
            },
        },
    ]
    summary = {
        "total_duration_ms": 1250.0,
        "call_counts": {
            "pro_calls": 2,
            "flash_calls": 0,
            "embed_calls": 0,
            "tool_calls": 1,
            "sqlite_queries": 2,
        },
    }
    trace_html = render_trace_panel_html(events, summary, in_progress=False)
    assert trace_html.count('<span class="musnad-pill musnad-pill--ok">قاعدة بيانات السند</span>') == 2
    assert "source: SQLite sanad graph" not in trace_html
    assert "1.25 ثانية" in trace_html
    assert "12.5 مللي ثانية" in trace_html


def test_unified_answer_card_contains_answer_source_and_sanad():
    card_html = render_answer_card_html(
        {
            "answer": "روى الحديث أبو بكر بن أبي شيبة عن ابن عباس.\n\n(المصدر: صحيح مسلم، حديث رقم 7306)",
            "sanad": [
                {
                    "hadith_id": 7306,
                    "status": "LINKED_WITH_RECORDED_ISNAD",
                    "isnad_count": 2,
                    "isnads": [
                        [
                            {"chain_position": 1, "name_ar_mapped": "عبد الله بن العباس"},
                            {"chain_position": 2, "name_ar_mapped": "أبو بكر بن أبي شيبة"},
                        ],
                        [
                            {"chain_position": 1, "name_ar_mapped": "عبد الله بن العباس"},
                            {"chain_position": 2, "name_ar_mapped": "إسحاق بن راهويه"},
                        ],
                    ],
                }
            ],
        },
        refusal_text="لا يتضمن صحيح مسلم نصًا صريحًا يجيب عن هذا السؤال.",
    )
    assert card_html.count('class="musnad-answer-card"') == 1
    assert "musnad-source-line" in card_html
    assert "المصدر: صحيح مسلم، حديث رقم 7306" in card_html
    assert "narrator-chip--companion" in card_html
    assert "عرض بقية الطرق" in card_html


def test_streamlit_app_example_and_error_handling(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """Test minimal landing layout, example chip fill+submit, single answer card, and error handling."""
    assert len(DEFAULT_EXAMPLES) == 4
    from app.usage_guard import InMemoryUsageBackend

    monkeypatch.setattr("app.usage_guard._LOCAL_BACKEND", InMemoryUsageBackend())

    def _fake_warm_up(config, retrieval_mode, *, load_pipeline=True):
        return {
            "router_ready": True,
            "sanad_ready": True,
            "pipeline_ready": True,
            "hadith_count": 5300,
            "pipeline": object(),
            "matn_by_hadith_id": {7306: "متن مشكول كامل للحديث رقم 7306."},
            "error": None,
        }

    def _fake_answer_success(
        question: str,
        retriever: Any,
        *,
        k: int = 5,
        sanad_db_path: Any = None,
        use_agent: bool | None = None,
        trace: Any = None,
    ):
        if trace is not None:
            trace.record_router(decision="chain", source="regex", probability=1.0, duration_ms=4.0)
            trace.record_agent_tool(
                name="get_isnad",
                arguments={"hadith_id": 7306},
                returned_ids=[7306],
                duration_ms=8.0,
                status="LINKED_WITH_RECORDED_ISNAD",
                isnad_count=4,
                source="SQLite sanad graph",
            )
            trace.record_generation(model="gemini-4-argon", attempts=1, duration_ms=100.0, pro_calls=2)
            trace.record_validation(status="valid_answer", duration_ms=1.0)
            trace.record_sanad(
                hadith_id=7306,
                status="LINKED_WITH_RECORDED_ISNAD",
                isnad_count=4,
                ms=2.0,
            )
        return {
            "answer": "روى الحديث أبو بكر بن أبي شيبة عن عبد الله بن العباس.\n\n(المصدر: صحيح مسلم، حديث رقم 7306)",
            "raw": "...",
            "chunks": [
                {
                    "rank": 1,
                    "hadith_id": 7306,
                    "text": "",
                    "metadata": {"chapter_arabic": "كتاب الإيمان"},
                }
            ],
            "sanad": [
                {
                    "hadith_id": 7306,
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
        }

    monkeypatch.setenv("GEMINI_API_KEY", "test-dummy-key")
    monkeypatch.setattr(app_state, "warm_up_resources", _fake_warm_up)
    monkeypatch.setattr(app_state, "answer_with_details", _fake_answer_success)

    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"))
    at.run(timeout=30)
    assert not at.exception
    assert len(at.button) >= 5  # 4 example chips + 1 form submit
    assert len(at.text_input) == 1
    assert "اكتب سؤالك هنا… مثال: من روى حديث الدين النصيحة؟" == at.text_input[0].placeholder
    assert len(at.sidebar.selectbox) == 2

    initial_md = "\n".join(m.value for m in at.markdown)
    assert "مُسنَد" in initial_md
    assert "اسأل عن أي حديث في صحيح مسلم، وستحصل على الحديث وسنده من المصدر." in initial_md
    assert "MUSNAD_" not in initial_md
    assert "حدود الاستخدام المباشر:" in initial_md
    assert len(at.expander) == 0  # Nothing else above or below fold before asking

    # Click chain example chip cleanly -> fills input + submits
    chain_btn = next(b for b in at.button if "سند حديث" in b.label)
    chain_btn.click().run(timeout=30)
    assert not at.exception
    assert at.text_input[0].value == "من هم رواة حديث رقم 7294 وما عدد أسانيده؟"

    markdown_blob = "\n".join(m.value for m in at.markdown)
    assert "7306" in markdown_blob
    assert "+3 طرق أخرى" in markdown_blob
    assert "عبد الله بن العباس" in markdown_blob
    # Pure Arabic UI: no English technical badges or raw enum names in main flow
    assert "source: SQLite sanad graph" not in markdown_blob
    assert "valid_answer" not in markdown_blob
    assert "LINKED_WITH_RECORDED_ISNAD" not in markdown_blob

    exp_labels = [exp.label for exp in at.expander]
    assert "الأحاديث المستخدمة" in exp_labels
    assert "كيف وصل النظام للإجابة؟" in exp_labels
    expander_texts = "\n".join(m.value for exp in at.expander for m in exp.markdown)
    assert "متن مشكول كامل للحديث رقم 7306" in expander_texts

    # Simulate API failure: app must NOT crash, must show friendly message + details + log line
    def _fake_answer_error(*args, **kwargs):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(app_state, "answer_with_details", _fake_answer_error)
    caplog.clear()
    with caplog.at_level(logging.ERROR, logger="musnad"):
        at.text_input[0].set_value("سؤال يسبب خطأ")
        submit_btn = next(b for b in at.button if b.label == "اسأل")
        submit_btn.click().run(timeout=30)

    assert not at.exception
    err_markdown = "\n".join(m.value for m in at.markdown)
    assert "تعذّر إتمام البحث حاليًا" in err_markdown
    assert any("Error during live query execution" in rec.message for rec in caplog.records)


def test_step5_ui_fixes_markdown_lists_status_localization_and_bidi():
    from app.components import format_answer_body_html, _CSS

    raw_answer = (
        "السلسلة:\n\n"
        "1. **قتيبة بن سعيد**\n"
        "2. مالك بن أنس <script>alert(1)</script>\n\n"
        "- نقطة فرعية\n\n"
        "(المصدر: صحيح مسلم، حديث رقم 7285)"
    )
    rendered = format_answer_body_html(raw_answer)
    assert '<ol class="musnad-answer-list">' in rendered
    assert "<strong>قتيبة بن سعيد</strong>" in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "<script>" not in rendered
    assert 'class="musnad-answer-para musnad-answer-citation"' in rendered

    unlinked_html = render_sanad_chain_html(
        {
            "hadith_id": 9139,
            "status": "VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK",
            "isnad_count": 0,
            "isnads": [],
        }
    )
    assert "VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK" not in unlinked_html
    assert "الحديث موثق محليًا ولا يوجد ربط مقبول بسند المسند بعد" in unlinked_html

    trace_html = render_trace_panel_html(
        [
            {
                "stage": "retrieval",
                "duration_ms": 120.0,
                "data": {"top5": [{"hadith_id": 9142}, {"hadith_id": 9138}], "hyde_text": "نص", "legacy_fallback": False},
            },
            {
                "stage": "sanad",
                "duration_ms": 1.2,
                "data": {"hadith_id": 9142, "status": "LINKED_WITH_RECORDED_ISNAD", "isnad_count": 1, "ms": 1.2},
            },
        ],
        summary=None,
        in_progress=False,
    )
    assert "9142، 9138" in trace_html
    assert "إسناد واحد" in trace_html
    assert "LINKED_WITH_RECORDED_ISNAD" not in trace_html
    assert '[data-testid="stSidebar"][data-collapsed="true"]' in _CSS
    assert '[data-testid="stAppViewContainer"]' in _CSS


def test_sanad_strip_single_line_rtl_and_minimal_toolbar_config():
    from app.components import _CSS

    sanad_strip_rule = _CSS.split(".sanad-strip {", 1)[1].split("}", 1)[0]
    assert "flex-wrap: nowrap" in sanad_strip_rule
    assert "overflow-x: auto" in sanad_strip_rule
    assert "direction: rtl" in sanad_strip_rule

    chip_rule = _CSS.split(".narrator-chip {", 1)[1].split("}", 1)[0]
    assert "flex: 0 0 auto" in chip_rule
    assert "white-space: nowrap" in chip_rule

    assert '[data-testid="InputInstructions"]' in _CSS

    config_toml = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'toolbarMode = "minimal"' in config_toml


def test_timeout_error_shows_arabic_retry_message_even_in_cloud_mode(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    from app.usage_guard import InMemoryUsageBackend
    from src.answer import GenerationTimeoutError

    monkeypatch.setattr("app.usage_guard._LOCAL_BACKEND", InMemoryUsageBackend())

    def _fake_warm_up(config, retrieval_mode, *, load_pipeline=True):
        return {
            "router_ready": True,
            "sanad_ready": True,
            "pipeline_ready": True,
            "hadith_count": 5300,
            "pipeline": object(),
            "matn_by_hadith_id": {},
            "error": None,
        }

    def _fake_timeout_answer(*args, **kwargs):
        trace = kwargs.get("trace")
        if trace is not None:
            trace.record(
                "generation",
                duration_ms=45000.0,
                model="gemini-4-argon",
                attempts=1,
                pro_calls=0,
                event_kind="timeout_retry",
                timed_out=True,
                timeout_s=45.0,
            )
            trace.record_generation(
                model="gemini-4-argon",
                attempts=2,
                duration_ms=90000.0,
                pro_calls=2,
                timeout_retries=1,
                timed_out=True,
                timeout_s=45.0,
                status="timeout",
            )
        raise GenerationTimeoutError()

    monkeypatch.setenv("MUSNAD_CLOUD", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-dummy-key")
    monkeypatch.setattr(app_state, "warm_up_resources", _fake_warm_up)
    monkeypatch.setattr(app_state, "answer_with_details", _fake_timeout_answer)

    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"))
    at.run(timeout=30)
    assert not at.exception

    caplog.clear()
    with caplog.at_level(logging.ERROR, logger="musnad"):
        at.text_input[0].set_value("سؤال تتجاوز مهلة التوليد")
        submit_btn = next(b for b in at.button if b.label == "اسأل")
        submit_btn.click().run(timeout=30)

    assert not at.exception
    markdown_blob = "\n".join(m.value for m in at.markdown)
    assert "45 ثانية" in markdown_blob
    assert "إعادة المحاولة" in markdown_blob
    assert "انتهت مهلة التوليد" in markdown_blob
    assert any("Error during live query execution" in rec.message for rec in caplog.records)
