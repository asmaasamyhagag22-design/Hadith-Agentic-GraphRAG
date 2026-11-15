"""Reusable minimalist RTL UI rendering helpers for the Musnad Streamlit application."""

from __future__ import annotations

import html
import re
from typing import Any

import streamlit as st

from app.usage_guard import UsageDecision

STAGE_LABELS: dict[str, tuple[str, str]] = {
    "router": ("🧭", "تحديد نوع السؤال"),
    "retrieval": ("🔎", "البحث في المتون"),
    "agent": ("🛠️", "الاستعلام الإسنادي"),
    "generation": ("✍️", "صياغة الإجابة"),
    "validation": ("🛡️", "التحقق من التوثيق"),
    "sanad": ("🔗", "إرفاق السند"),
}

_ROUTER_DECISION_AR: dict[str, str] = {
    "chain": "سؤال إسنادي",
    "text": "سؤال متني",
}

_ROUTER_SOURCE_AR: dict[str, str] = {
    "regex": "تعرّف رقمي مباشر",
    "classifier": "مصنّف المقاصد",
    "v2_fallback": "مصنّف احتياطي",
    "fallback": "تصنيف احتياطي",
}

_VALIDATION_AR: dict[str, str] = {
    "valid_answer": "إجابة موثّقة برقم الحديث",
    "valid_refusal": "امتناع منضبط عن الإجابة",
    "missing_citation": "غياب إحالة رقم الحديث",
    "out_of_context_citation": "إحالة خارج النتائج المسترجعة",
    "mixed_refusal": "امتناع مختلط بنص إضافي",
    "disallowed_narrators": "مراجعة أسماء الرواة",
    "validation_failed_after_retry": "تعذّر التوثيق بعد إعادة الصياغة",
    "model_refused": "عدم وجود إجابة في صحيح مسلم",
    "empty_retrieval": "لم يُعثر على نصوص مطابقة",
}

SANAD_STATUS_ARABIC_UI: dict[str, str] = {
    "VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK": "الحديث موثق محليًا ولا يوجد ربط مقبول بسند المسند بعد",
    "NO_RECORDED_ISNAD": "لا يوجد إسناد مسجّل في قاعدة البيانات",
    "LINKED_WITH_ZERO_ISNADS": "الحديث مربوط ولا توجد له طرق مسجّلة",
    "AMBIGUOUS_MIS_LINK": "توجد أكثر من مطابقة محتملة في قاعدة السند",
    "GRAPH_UNAVAILABLE": "تعذّر الوصول إلى قاعدة بيانات السند",
    "LINKED_WITH_RECORDED_ISNAD": "سند موثّق",
    "INVALID_LOCAL_HADITH_ID": "رقم الحديث غير موجود في قاعدة بيانات السند",
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Noto+Sans+Arabic:wght@400;500;600;700&display=swap');

html, body, .stApp {
    font-family: 'Noto Sans Arabic', 'Segoe UI', Tahoma, sans-serif;
    background-color: #FAF8F3;
    color: #1F1E1B;
}

/* Keep outer flex container LTR so Streamlit's native sidebar collapse transform (-300px)
   slides the collapsed sidebar offscreen cleanly instead of covering the RTL viewport. */
[data-testid="stAppViewContainer"] {
    direction: ltr;
    background-color: #FAF8F3;
}

[data-testid="stHeader"] {
    background: transparent !important;
}

[data-testid="stAppDeployButton"] {
    display: none !important;
}

[data-testid="InputInstructions"] {
    display: none !important;
}

[data-testid="stMain"],
.stMainBlockContainer {
    direction: rtl;
    text-align: right;
}

.stMainBlockContainer {
    max-width: 1080px !important;
    margin-inline: auto !important;
    padding: 1.75rem 1.75rem 2.25rem 1.75rem !important;
}

[data-testid="stSidebar"] {
    direction: rtl;
    text-align: right;
    background-color: #F4F1EA;
}

[data-testid="stSidebar"][data-collapsed="true"] {
    visibility: hidden !important;
    pointer-events: none !important;
    overflow: hidden !important;
}

.stApp textarea, .stApp input {
    direction: rtl;
    text-align: right;
    font-family: 'Noto Sans Arabic', 'Segoe UI', Tahoma, sans-serif;
}

.stApp [data-testid="stExpander"] summary {
    direction: rtl;
    text-align: right;
    font-weight: 600;
    color: #292722;
}

/* Top minimal header: product title + one single subtitle line */
.musnad-hero {
    max-width: 760px;
    margin: 0 auto 1.15rem auto;
    text-align: center;
    padding: 0.25rem 0;
}

.musnad-title {
    margin: 0 0 0.3rem 0;
    font-family: 'Amiri', 'Noto Sans Arabic', serif;
    font-size: 2.5rem;
    font-weight: 700;
    color: #154728;
    line-height: 1.2;
}

.musnad-subtitle {
    margin: 0;
    font-size: 1.02rem;
    color: #4E4B42;
    line-height: 1.6;
}

/* Centered query form */
.st-key-musnad_query_area {
    max-width: 760px;
    margin: 0 auto 0.25rem auto;
}

[data-testid="stForm"] {
    max-width: 760px;
    margin: 0 auto 0.2rem auto;
    padding: 0 !important;
    border: none !important;
    background: transparent !important;
}

[data-testid="stForm"] [data-testid="stTextInput"] input {
    min-height: 3.35rem;
    font-size: 1.03rem;
    padding: 0.7rem 1rem;
    border-radius: 14px;
    border: 1.5px solid #D5CFC2;
    background: #FFFFFF;
    color: #1F1E1B;
    box-shadow: 0 2px 10px rgba(21, 71, 40, 0.05);
}

[data-testid="stForm"] [data-testid="stTextInput"] input:focus {
    border-color: #175934;
    box-shadow: 0 0 0 3px rgba(23, 89, 52, 0.14);
}

[data-testid="stFormSubmitButton"] button {
    min-height: 3.35rem;
    border-radius: 14px;
    font-size: 1.03rem;
    font-weight: 700;
    background: #175934;
    border: 1px solid #175934;
    color: #FFFFFF;
}

[data-testid="stFormSubmitButton"] button:hover {
    background: #124628;
    border-color: #124628;
}

/* 4 compact example chips centered directly below query box */
.st-key-musnad_chips_row {
    max-width: 760px;
    margin: 0.15rem auto 1.15rem auto;
}

.st-key-musnad_chips_row [data-testid="stButton"] button {
    min-height: 2.15rem;
    padding: 0.22rem 0.65rem;
    border-radius: 999px;
    font-size: 0.84rem;
    font-weight: 500;
    background: #FFFFFF;
    border: 1px solid #DCD6C8;
    color: #35332D;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
    white-space: nowrap;
}

.st-key-musnad_chips_row [data-testid="stButton"] button:hover {
    border-color: #175934;
    color: #154728;
    background: #F4FAF6;
}

/* Results wrapper */
.st-key-musnad_results_area {
    max-width: 1020px;
    margin: 0.3rem auto 0 auto;
}

/* Live single progress line while answering */
.musnad-progress-line {
    max-width: 760px;
    margin: 0.5rem auto 1rem auto;
    padding: 0.65rem 1rem;
    border-radius: 999px;
    background: #F1F7F3;
    border: 1px solid #CBE3D4;
    color: #154728;
    font-size: 0.92rem;
    font-weight: 600;
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.55rem;
}

.musnad-progress-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #175934;
    display: inline-block;
    flex-shrink: 0;
}

/* Concise Arabic replay banner */
.musnad-replay-line {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.45rem;
    max-width: 1020px;
    margin: 0 auto 0.65rem auto;
    padding: 0.48rem 0.9rem;
    border-radius: 10px;
    background: #FFFBEB;
    border: 1px solid #FCD34D;
    color: #78350F;
    font-size: 0.86rem;
    font-weight: 600;
    text-align: center;
}

/* Unified Single Answer Card (Answer + Source Line + Sanad Chips) */
.musnad-answer-card {
    background: #FFFFFF;
    border: 1px solid #E5DFD2;
    border-right: 4px solid #175934;
    border-radius: 14px;
    padding: 1.2rem 1.35rem;
    margin-bottom: 0.8rem;
    box-shadow: 0 2px 12px rgba(28, 25, 23, 0.04);
}

.musnad-answer-card--refusal {
    border-right-color: #B45309;
    background: #FFFDF8;
}

.musnad-answer-body {
    font-family: 'Amiri', 'Noto Sans Arabic', serif;
    font-size: 1.2rem;
    line-height: 1.9;
    color: #1C1917;
    white-space: normal;
}

.musnad-answer-para {
    margin: 0 0 0.55rem 0;
}

.musnad-answer-para:last-child {
    margin-bottom: 0;
}

.musnad-answer-list {
    margin: 0.35rem 0 0.65rem 0;
    padding-inline-start: 2.0rem;
    list-style-position: outside;
}

.musnad-answer-list li {
    margin-bottom: 0.32rem;
}

.musnad-answer-citation {
    color: #166534;
    font-weight: 600;
}

.musnad-source-line {
    margin-top: 0.75rem;
    padding: 0.42rem 0.78rem;
    border-radius: 8px;
    background: #F4F9F5;
    border: 1px solid #D3E8DA;
    color: #154728;
    font-size: 0.92rem;
    font-weight: 600;
    display: inline-block;
}

/* Integrated Sanad Section inside the Answer Card */
.musnad-sanad-section {
    margin-top: 0.95rem;
    padding-top: 0.85rem;
    border-top: 1px solid #EFECE3;
}

.musnad-sanad-block + .musnad-sanad-block {
    margin-top: 0.8rem;
    padding-top: 0.7rem;
    border-top: 1px dashed #ECE7DC;
}

.sanad-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-bottom: 0.48rem;
    font-size: 0.9rem;
    color: #3F3D36;
}

.musnad-status-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: center;
}

.musnad-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.14rem 0.56rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    line-height: 1.45;
}

.musnad-pill--ok {
    background: #DCFCE7;
    color: #166534;
    border: 1px solid #86EFAC;
}

.musnad-pill--warn {
    background: #FEF3C7;
    color: #92400E;
    border: 1px solid #FCD34D;
}

.musnad-pill--extra {
    background: #F5F3FF;
    color: #5B21B6;
    border: 1px solid #DDD6FE;
}

/* Compact Narrator Chain Strip: all visible on one line at 1440 px */
.sanad-strip {
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    align-items: stretch;
    gap: 0.26rem;
    padding: 0.25rem 0;
    overflow-x: auto;
    overflow-y: hidden;
    direction: rtl;
    scrollbar-width: thin;
    scrollbar-color: #CBD5E1 transparent;
}

.narrator-chip {
    display: inline-flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
    flex: 0 0 auto;
    white-space: nowrap;
    padding: 0.28rem 0.56rem;
    border-radius: 9px;
    background: #F8F7F2;
    border: 1px solid #DCD7CA;
    font-size: 0.77rem;
    line-height: 1.3;
    color: #292524;
}

@media (min-width: 900px) {
    .narrator-chip {
        flex: 0 1 auto;
        white-space: normal;
        max-width: 162px;
        text-align: right;
    }
}

.narrator-chip--teacher {
    background: #F0FDF4;
    border-color: #86EFAC;
}

.narrator-chip--companion {
    background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
    border: 2px solid #D97706;
    color: #78350F;
    font-weight: 700;
    box-shadow: 0 1px 5px rgba(217, 119, 6, 0.16);
}

.narrator-chip-role {
    font-size: 0.62rem;
    font-weight: 700;
    opacity: 0.85;
    margin-bottom: 0.06rem;
}

.sanad-arrow {
    flex: 0 0 auto;
    align-self: center;
    color: #78716C;
    font-weight: 700;
    font-size: 0.84rem;
    padding: 0 0.04rem;
}

.sanad-extra-details {
    margin-top: 0.45rem;
    font-size: 0.84rem;
    color: #44403C;
}

.sanad-extra-details summary {
    cursor: pointer;
    font-weight: 600;
    color: #154728;
    list-style-position: inside;
}

.sanad-extra-route {
    margin: 0.35rem 0 0 0;
    padding: 0.38rem 0.6rem;
    background: #FAF8F3;
    border-radius: 8px;
    line-height: 1.6;
}

/* Matn cards inside collapsed "الأحاديث المستخدمة" expander */
.matn-item {
    margin-bottom: 0.8rem;
}

.matn-item:last-child {
    margin-bottom: 0;
}

.matn-item-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: #154728;
    margin-bottom: 0.3rem;
}

.matn-box {
    font-family: 'Amiri', 'Noto Sans Arabic', serif;
    font-size: 1.12rem;
    line-height: 1.95;
    color: #1C1917;
    background: #FCFBF8;
    padding: 0.78rem 0.95rem;
    border-radius: 8px;
    border: 1px solid #EAE6DC;
    white-space: pre-wrap;
}

/* Arabic trace timeline inside collapsed "كيف وصل النظام للإجابة؟" expander */
.trace-card {
    background: #FFFFFF;
    border: 1px solid #E5E2D9;
    border-radius: 10px;
    padding: 0.65rem 0.85rem;
    margin-bottom: 0.5rem;
}

.trace-card-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 0.3rem;
}

.trace-stage-title {
    font-weight: 700;
    font-size: 0.88rem;
    color: #1C1917;
}

.trace-dur-pill {
    font-size: 0.76rem;
    background: #F5F5F4;
    border: 1px solid #E7E5E4;
    padding: 0.08rem 0.52rem;
    border-radius: 999px;
    color: #44403C;
}

.trace-detail {
    font-size: 0.83rem;
    color: #44403C;
    line-height: 1.55;
    word-break: break-word;
}

.trace-summary-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.45rem;
    margin-top: 0.6rem;
}

.trace-metric {
    background: #F8F7F2;
    border: 1px solid #E5E2D9;
    border-radius: 8px;
    padding: 0.45rem 0.55rem;
    text-align: center;
}

.trace-metric-label {
    font-size: 0.72rem;
    color: #57534E;
}

.trace-metric-value {
    font-weight: 700;
    font-size: 0.92rem;
    color: #154728;
}

.musnad-error-card {
    background: #FEF2F2;
    border: 1px solid #FCA5A5;
    border-right: 4px solid #DC2626;
    border-radius: 10px;
    padding: 0.9rem 1.05rem;
    color: #7F1D1D;
    margin: 0.5rem auto 0.75rem auto;
    max-width: 760px;
}

.musnad-footer {
    max-width: 760px;
    margin: 1.5rem auto 0 auto;
    padding-top: 0.75rem;
    border-top: 1px solid #ECE7DC;
    text-align: center;
    font-size: 0.78rem;
    color: #6B675E;
    line-height: 1.6;
}

/* Mobile 375 px adaptations */
@media (max-width: 640px) {
    .stMainBlockContainer {
        padding: 1rem 0.75rem 1.75rem 0.75rem !important;
    }

    .musnad-hero {
        margin-bottom: 0.85rem;
    }

    .musnad-title {
        font-size: 1.95rem;
    }

    .musnad-subtitle {
        font-size: 0.92rem;
    }

    .st-key-musnad_chips_row [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 0.4rem !important;
    }

    .st-key-musnad_chips_row [data-testid="stColumn"] {
        flex: 1 1 calc(50% - 0.4rem) !important;
        min-width: calc(50% - 0.4rem) !important;
        width: auto !important;
    }

    .musnad-answer-card {
        padding: 0.95rem 1rem;
    }

    .musnad-answer-body {
        font-size: 1.12rem;
    }

    .trace-summary-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
</style>
"""


def inject_rtl_styles() -> None:
    """Inject global RTL typography and scholarly card styles."""
    st.markdown(_CSS, unsafe_allow_html=True)


def format_duration_ms(duration_ms: float | int | None) -> str:
    """Format millisecond duration cleanly in Arabic."""
    val = float(duration_ms or 0.0)
    if val >= 1000.0:
        return f"{val / 1000.0:.2f} ثانية"
    return f"{val:.1f} مللي ثانية"


def format_live_progress_line(events: list[dict[str, Any]]) -> str:
    """Build single-line Arabic step-by-step progress text from live events."""
    seen = {str(ev.get("stage") or "") for ev in events}
    if any(s in seen for s in ("generation", "validation", "sanad")):
        return "تحديد نوع السؤال… البحث… صياغة الإجابة… إرفاق السند"
    if "retrieval" in seen or "agent" in seen:
        return "تحديد نوع السؤال… البحث… صياغة الإجابة…"
    if "router" in seen:
        return "تحديد نوع السؤال… البحث…"
    return "تحديد نوع السؤال…"


def render_live_progress_html(events: list[dict[str, Any]]) -> str:
    """Render concise single-line Arabic progress indicator while answering."""
    text = format_live_progress_line(events)
    return (
        f'<div class="musnad-progress-line" role="status" aria-live="polite">'
        f'<span class="musnad-progress-dot" aria-hidden="true"></span>'
        f'<span>{html.escape(text)}</span>'
        f'</div>'
    )


def format_narrator_chain_for_display(
    chain: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Order narrators from Muslim's teacher to the Companion (chain_position=1)."""
    if not chain:
        return []
    ordered = sorted(
        chain,
        key=lambda n: int(n.get("chain_position") or 0),
        reverse=True,
    )
    items: list[dict[str, Any]] = []
    for idx, node in enumerate(ordered):
        pos = int(node.get("chain_position") or 0)
        name = str(
            node.get("name_ar_mapped")
            or node.get("name_ar")
            or node.get("label")
            or "راوٍ غير مسمّى"
        )
        if pos == 1:
            role = "companion"
            role_label = "الصحابي"
        elif idx == 0:
            role = "teacher"
            role_label = "شيخ مسلم"
        else:
            role = "narrator"
            role_label = f"الطبقة {pos}" if pos > 0 else ""
        items.append(
            {
                "name": name,
                "chain_position": pos,
                "role": role,
                "role_label": role_label,
            }
        )
    return items


def extra_routes_label(isnad_count: int, shown_count: int = 1) -> str:
    """Return Arabic badge label '+N طرق أخرى' when multiple chains exist."""
    extra = max(int(isnad_count or 0) - int(shown_count or 1), 0)
    if extra <= 0:
        return ""
    return f"+{extra} طرق أخرى"


def render_hero(title: str, subtitle: str) -> None:
    """Render minimal top header with product name and one short subtitle line."""
    st.markdown(
        f"""
        <header class="musnad-hero">
            <h1 class="musnad-title">{html.escape(title)}</h1>
            <p class="musnad-subtitle">{html.escape(subtitle)}</p>
        </header>
        """,
        unsafe_allow_html=True,
    )


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_SPAN_RE = re.compile(r"`([^`]+)`")
_ORDERED_LIST_RE = re.compile(r"^\d+[\.\)]\s+(.*)$")
_BULLET_LIST_RE = re.compile(r"^[-*•]\s+(.*)$")
_CITATION_LINE_RE = re.compile(r"^\(المصدر:\s*(.+)\)$")


def _format_inline_markdown_html(text: str) -> str:
    """Escape HTML safely and render **bold** and inline spans without CommonMark leaks."""
    escaped = html.escape(text)
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    return _CODE_SPAN_RE.sub(r"<span>\1</span>", escaped)


def _format_isnad_count_ar(cnt: int) -> str:
    if cnt == 1:
        return "إسناد واحد"
    if cnt == 2:
        return "إسنادان"
    if 3 <= cnt <= 10:
        return f"{cnt} أسانيد"
    return f"{cnt} إسنادًا"


def format_answer_body_html(answer: str) -> str:
    """Convert answer text (paragraphs, markdown lists, bold, citations) into clean RTL HTML."""
    lines = [ln.strip() for ln in (answer or "").replace("\r\n", "\n").splitlines()]
    blocks: list[str] = []
    list_kind: str | None = None
    list_items: list[str] = []

    def _flush_list() -> None:
        nonlocal list_kind, list_items
        if list_kind and list_items:
            tag = "ol" if list_kind == "ol" else "ul"
            inner = "".join(f"<li>{_format_inline_markdown_html(it)}</li>" for it in list_items)
            blocks.append(f'<{tag} class="musnad-answer-list">{inner}</{tag}>')
        list_kind = None
        list_items = []

    for ln in lines:
        if not ln:
            _flush_list()
            continue
        m_ol = _ORDERED_LIST_RE.match(ln)
        m_ul = _BULLET_LIST_RE.match(ln)
        if m_ol:
            if list_kind not in (None, "ol"):
                _flush_list()
            list_kind = "ol"
            list_items.append(m_ol.group(1).strip())
        elif m_ul:
            if list_kind not in (None, "ul"):
                _flush_list()
            list_kind = "ul"
            list_items.append(m_ul.group(1).strip())
        else:
            _flush_list()
            cls = (
                "musnad-answer-para musnad-answer-citation"
                if _CITATION_LINE_RE.match(ln)
                else "musnad-answer-para"
            )
            blocks.append(f'<p class="{cls}">{_format_inline_markdown_html(ln)}</p>')

    _flush_list()
    return "".join(blocks) if blocks else f'<p class="musnad-answer-para">{html.escape(answer)}</p>'


def _extract_answer_and_source(
    answer: str,
    result: dict[str, Any],
    *,
    is_refusal: bool,
) -> tuple[str, str]:
    """Separate trailing standalone citation line into a clean Arabic source line."""
    lines = (answer or "").replace("\r\n", "\n").splitlines()
    while lines and not lines[-1].strip():
        lines.pop()

    source_line = ""
    if lines:
        last = lines[-1].strip()
        m_full = _CITATION_LINE_RE.match(last)
        if m_full:
            source_line = f"المصدر: {m_full.group(1).strip()}"
            lines.pop()
            while lines and not lines[-1].strip():
                lines.pop()
        elif last.startswith("المصدر:"):
            source_line = last
            lines.pop()
            while lines and not lines[-1].strip():
                lines.pop()

    if not source_line and not is_refusal:
        inline_match = re.search(r"\(المصدر:\s*([^()]+)\)\s*[.؟!]?\s*$", answer or "")
        if inline_match:
            source_line = f"المصدر: {inline_match.group(1).strip()}"
        else:
            sanad_ids = [
                str(entry.get("hadith_id"))
                for entry in (result.get("sanad") or [])
                if entry.get("hadith_id") is not None
            ]
            if sanad_ids:
                source_line = f"المصدر: صحيح مسلم، حديث رقم {', '.join(sanad_ids)}"

    body_text = "\n".join(lines).strip() or answer.strip()
    return body_text, source_line


def render_sanad_chain_html(
    sanad_entry: dict[str, Any],
    *,
    compact_header: bool = True,
) -> str:
    """Build compact escaped Arabic sanad strip from Muslim's teacher to Companion."""
    hadith_id = html.escape(str(sanad_entry.get("hadith_id", "؟")))
    status = str(sanad_entry.get("status") or "")
    isnads = list(sanad_entry.get("isnads") or [])
    isnad_count = int(sanad_entry.get("isnad_count") or len(isnads) or 0)
    extra_lbl = extra_routes_label(max(isnad_count, len(isnads)), shown_count=1)

    extra_html = (
        f'<span class="musnad-pill musnad-pill--extra">{html.escape(extra_lbl)}</span>'
        if extra_lbl
        else ""
    )
    heading = "سند الحديث" if compact_header else f"سند حديث رقم {hadith_id}"

    if not isnads:
        status_ar = SANAD_STATUS_ARABIC_UI.get(
            status, "لا يوجد إسناد مسجّل في قاعدة البيانات"
        )
        return (
            f'<div class="musnad-sanad-block">'
            f'<div class="sanad-card-header">'
            f'<strong>{html.escape(heading)}</strong>'
            f'</div>'
            f'<div class="trace-detail">{html.escape(status_ar)}</div>'
            f'</div>'
        )

    chips_ordered = format_narrator_chain_for_display(isnads[0])
    chip_parts: list[str] = []
    for idx, chip in enumerate(chips_ordered):
        if idx > 0:
            chip_parts.append('<span class="sanad-arrow" aria-hidden="true">←</span>')
        cls = "narrator-chip"
        role_html = ""
        if chip["role"] == "companion":
            cls += " narrator-chip--companion"
            role_html = '<span class="narrator-chip-role">الصحابي</span>'
        elif chip["role"] == "teacher":
            cls += " narrator-chip--teacher"
            role_html = '<span class="narrator-chip-role">شيخ مسلم</span>'
        chip_parts.append(
            f'<span class="{cls}" title="{html.escape(chip["name"])}">'
            f'{role_html}'
            f'<span>{html.escape(chip["name"])}</span>'
            f'</span>'
        )

    extra_routes_html = ""
    if len(isnads) > 1:
        route_lines: list[str] = []
        for r_idx, route in enumerate(isnads[1:], start=2):
            ordered = format_narrator_chain_for_display(route)
            names = " ← ".join(html.escape(item["name"]) for item in ordered)
            route_lines.append(
                f'<div class="sanad-extra-route"><strong>الطريق {r_idx}:</strong> {names}</div>'
            )
        summary_txt = f"عرض بقية الطرق ({extra_lbl})" if extra_lbl else f"عرض بقية الطرق ({len(isnads) - 1})"
        extra_routes_html = (
            f'<details class="sanad-extra-details">'
            f'<summary>{html.escape(summary_txt)}</summary>'
            f'{"".join(route_lines)}'
            f'</details>'
        )

    return (
        f'<div class="musnad-sanad-block">'
        f'<div class="sanad-card-header">'
        f'<strong>{html.escape(heading)}</strong>'
        f'<div class="musnad-status-row">{extra_html}</div>'
        f'</div>'
        f'<div class="sanad-strip">{"".join(chip_parts)}</div>'
        f'{extra_routes_html}'
        f'</div>'
    )


def render_answer_card_html(
    result: dict[str, Any],
    *,
    refusal_text: str,
) -> str:
    """Build ONE unified card HTML containing the answer, source line, and compact narrator strip."""
    answer = str(result.get("answer") or refusal_text)
    is_refusal = answer.strip() == refusal_text.strip()
    body_text, source_line = _extract_answer_and_source(answer, result, is_refusal=is_refusal)

    body_html = format_answer_body_html(body_text)
    source_html = (
        f'<div class="musnad-source-line">{html.escape(source_line)}</div>'
        if source_line
        else ""
    )

    sanad_entries = list(result.get("sanad") or [])
    sanad_html = ""
    if sanad_entries:
        multi = len(sanad_entries) > 1
        blocks = "".join(
            render_sanad_chain_html(entry, compact_header=not multi)
            for entry in sanad_entries
        )
        sanad_html = f'<div class="musnad-sanad-section">{blocks}</div>'

    card_cls = "musnad-answer-card musnad-answer-card--refusal" if is_refusal else "musnad-answer-card"
    refusal_pill = (
        '<div class="musnad-status-row"><span class="musnad-pill musnad-pill--warn">لا تتوفر إجابة صريحة في صحيح مسلم</span></div>'
        if is_refusal
        else ""
    )

    return (
        f'<div class="{card_cls}">'
        f'{refusal_pill}'
        f'<div class="musnad-answer-body">{body_html}</div>'
        f'{source_html}'
        f'{sanad_html}'
        f'</div>'
    )


def render_answer_panel(
    result: dict[str, Any],
    *,
    refusal_text: str,
    replay_reason: str | None = None,
) -> None:
    """Render concise Arabic replay notice, unified Answer Card, and collapsed hadiths expander."""
    if replay_reason:
        st.markdown(
            '<div class="musnad-replay-line">عرض مسجَّل مسبقًا (بدون اتصال)</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        render_answer_card_html(result, refusal_text=refusal_text),
        unsafe_allow_html=True,
    )

    if result.get("sanad_error"):
        st.caption("تعذّر إرفاق سلسلة السند في هذا الطلب.")

    chunks = list(result.get("chunks") or [])
    if chunks:
        with st.expander("الأحاديث المستخدمة", expanded=False):
            for idx, chunk in enumerate(chunks, start=1):
                hid = html.escape(str(chunk.get("hadith_id", "؟")))
                meta = chunk.get("metadata") or {}
                chapter = html.escape(
                    str(meta.get("chapter_arabic") or meta.get("chapter_ar") or "غير مبوّب")
                )
                matn = str(chunk.get("text") or chunk.get("matn") or "").strip()
                st.markdown(
                    f'<div class="matn-item">'
                    f'<div class="matn-item-title">{idx}. حديث رقم {hid} — {chapter}</div>'
                    + (
                        f'<div class="matn-box">{html.escape(matn)}</div>'
                        if matn
                        else '<div class="trace-detail">تم الوصول لهذا الحديث مباشرة برقم الحديث.</div>'
                    )
                    + '</div>',
                    unsafe_allow_html=True,
                )


def _summarize_trace_event(stage: str, data: dict[str, Any]) -> str:
    """Build pure-Arabic step description for the collapsed trace timeline."""
    if stage == "router":
        raw_dec = str(data.get("decision") or "")
        raw_src = str(data.get("source") or "")
        decision = _ROUTER_DECISION_AR.get(raw_dec, "مسار الإجابة")
        source = _ROUTER_SOURCE_AR.get(raw_src, "التوجيه التلقائي")
        prob = data.get("probability")
        prob_str = f" | نسبة السند: {prob:.0%}" if isinstance(prob, (int, float)) else ""
        return html.escape(f"المسار: {decision} | الآلية: {source}{prob_str}")

    if stage == "retrieval":
        top5 = data.get("top5") or []
        ids_str = "، ".join(str(item.get("hadith_id")) for item in top5) or "لا يوجد"
        hyde = str(data.get("hyde_text") or "").strip()
        hyde_snippet = (hyde[:110] + "…") if len(hyde) > 110 else hyde
        parts = [f"الأحاديث المسترجعة: {html.escape(ids_str)}"]
        if hyde_snippet:
            parts.append(f"صياغة بحثية مساعدة: {html.escape(hyde_snippet)}")
        if data.get("legacy_fallback"):
            parts.append("تم التحويل لمسار الاسترجاع المحلي")
        return "<br/>".join(parts)

    if stage == "agent":
        if data.get("agent_fallback"):
            return "تعذّر مسار الوكيل الإسنادي وتم التحويل إلى البحث المباشر في المتون."
        tool_name = str(data.get("name") or "")
        args = data.get("arguments") or {}
        returned = data.get("returned_ids") or []
        if tool_name == "get_isnad":
            hid = args.get("hadith_id") or (returned[0] if returned else "؟")
            cnt = int(data.get("isnad_count", 0) or 0)
            return html.escape(
                f"الاستعلام من قاعدة بيانات السند عن حديث رقم {hid} ({_format_isnad_count_ar(cnt)})"
            )
        if tool_name == "search_hadith":
            query = str(args.get("query") or "").strip()
            ids_str = "، ".join(str(x) for x in returned) or "لا يوجد"
            return html.escape(
                f"البحث في متون صحيح مسلم عن: «{query}» — أُعيدت الأحاديث: {ids_str}"
            )
        return html.escape(f"استعلام مساعد أعاد {len(returned)} نتائج")

    if stage == "generation":
        attempts = int(data.get("attempts") or 1)
        timeout_s = data.get("timeout_s")
        timeout_label = f"{float(timeout_s):g} ثانية" if isinstance(timeout_s, (int, float)) else "45 ثانية"
        if data.get("event_kind") == "timeout_retry":
            return html.escape(
                f"انتهت مهلة التوليد بعد {timeout_label} في المحاولة الأولى — جاري إعادة المحاولة…"
            )
        if data.get("timed_out"):
            return html.escape(
                f"انتهت مهلة التوليد بعد {timeout_label} في المحاولتين ({attempts} محاولات) — يُرجى إعادة المحاولة."
            )
        if data.get("timeout_retries"):
            return html.escape(
                f"عدد المحاولات: {attempts} (نجحت بعد إعادة محاولة انتهاء المهلة)"
            )
        return html.escape(f"عدد المحاولات: {attempts}")

    if stage == "validation":
        raw_status = str(data.get("status") or "")
        status_ar = _VALIDATION_AR.get(raw_status, "تم الفحص")
        pieces = [f"النتيجة: {status_ar}"]
        if data.get("retry_reason"):
            r_raw = str(data["retry_reason"])
            pieces.append(f"سبب إعادة الصياغة: {_VALIDATION_AR.get(r_raw, 'تدقيق الإحالة')}")
        if data.get("refusal_reason"):
            ref_raw = str(data["refusal_reason"])
            pieces.append(f"السبب: {_VALIDATION_AR.get(ref_raw, 'عدم كفاية المصدر')}")
        return html.escape(" | ".join(pieces))

    if stage == "sanad":
        hid = data.get("hadith_id")
        status = str(data.get("status") or "")
        status_ar = SANAD_STATUS_ARABIC_UI.get(status, "سند موثّق")
        cnt = int(data.get("isnad_count", 0) or 0)
        return html.escape(f"حديث {hid}: {status_ar} | {_format_isnad_count_ar(cnt)}")

    return "خطوة تنفيذية"


def render_trace_panel_html(
    events: list[dict[str, Any]],
    summary: dict[str, Any] | None = None,
    *,
    in_progress: bool = False,
) -> str:
    """Build pure-Arabic HTML timeline for the collapsed 'كيف وصل النظام للإجابة؟' expander."""
    if in_progress:
        return render_live_progress_html(events)

    blocks: list[str] = []
    for ev in events:
        stage = str(ev.get("stage") or "")
        data = dict(ev.get("data") or {})
        icon, title_ar = STAGE_LABELS.get(stage, ("•", "مرحلة تنفيذ"))
        dur_str = format_duration_ms(ev.get("duration_ms"))
        detail_html = _summarize_trace_event(stage, data)
        is_chain_db = stage == "sanad" or (stage == "agent" and data.get("name") == "get_isnad")
        db_badge = (
            '<span class="musnad-pill musnad-pill--ok">قاعدة بيانات السند</span>'
            if is_chain_db
            else ""
        )
        blocks.append(
            f'<div class="trace-card">'
            f'<div class="trace-card-head">'
            f'<span class="trace-stage-title">{icon} {html.escape(title_ar)}</span>'
            f'<div class="musnad-status-row">{db_badge}<span class="trace-dur-pill">{html.escape(dur_str)}</span></div>'
            f'</div>'
            f'<div class="trace-detail">{detail_html}</div>'
            f'</div>'
        )

    if summary:
        total_ms = format_duration_ms(summary.get("total_duration_ms"))
        counts = dict(summary.get("call_counts") or {})
        metrics = [
            ("الزمن الكلي", total_ms),
            ("استدعاءات الصياغة", str(counts.get("pro_calls", 0))),
            ("استدعاءات البحث", str(counts.get("flash_calls", 0))),
            ("التضمين", str(counts.get("embed_calls", 0))),
            ("الأدوات", str(counts.get("tool_calls", 0))),
            ("استعلامات السند", str(counts.get("sqlite_queries", 0))),
        ]
        metric_cards = "".join(
            f'<div class="trace-metric">'
            f'<div class="trace-metric-label">{html.escape(lbl)}</div>'
            f'<div class="trace-metric-value">{html.escape(val)}</div>'
            f'</div>'
            for lbl, val in metrics
        )
        blocks.append(f'<div class="trace-summary-grid">{metric_cards}</div>')

    return "\n".join(blocks)


def render_error_card(friendly_message: str, details_text: str) -> None:
    """Display friendly Arabic error banner and collapsed technical details."""
    st.markdown(
        f"""
        <div class="musnad-error-card">
            <strong>تنبيه:</strong> {html.escape(friendly_message)}
        </div>
        """,
        unsafe_allow_html=True,
    )
    if details_text:
        with st.expander("تفاصيل إضافية", expanded=False):
            st.code(details_text, language="text")


def render_footer(
    usage_status: UsageDecision | None,
    *,
    session_limit: int,
    ip_hourly_limit: int,
    daily_cap: int,
    is_replay: bool = False,
) -> None:
    """Render quiet compact Arabic footer line showing usage limits."""
    parts: list[str] = []
    if is_replay:
        parts.append("عرض مسجَّل مسبقًا (بدون اتصال)")
    if isinstance(usage_status, UsageDecision):
        parts.append(
            f"حدود الاستخدام المباشر: الجلسة {usage_status.session_count}/{session_limit} · "
            f"الساعة {usage_status.ip_hourly_count}/{ip_hourly_limit} · "
            f"اليومي {usage_status.daily_count}/{daily_cap}"
        )
    else:
        parts.append(
            f"حدود الاستخدام المباشر: {session_limit} للجلسة · {ip_hourly_limit} في الساعة · {daily_cap} يوميًا"
        )
    st.markdown(
        f'<footer class="musnad-footer">{html.escape(" | ".join(parts))}</footer>',
        unsafe_allow_html=True,
    )
