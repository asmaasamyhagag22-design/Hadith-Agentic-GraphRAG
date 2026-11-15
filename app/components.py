"""Reusable RTL UI rendering helpers for the Musnad Streamlit application."""

from __future__ import annotations

import html
import re
from typing import Any

import streamlit as st

STAGE_LABELS: dict[str, tuple[str, str]] = {
    "router": ("🧭", "توجيه المسار"),
    "retrieval": ("🔎", "استرجاع المتون"),
    "agent": ("🛠️", "أداة الوكيل"),
    "generation": ("✍️", "صياغة الإجابة"),
    "validation": ("🛡️", "التحقق والتدقيق"),
    "sanad": ("🔗", "إرفاق السند الحتمي"),
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Noto+Sans+Arabic:wght@400;500;600;700&display=swap');

html, body, .stApp {
    font-family: 'Noto Sans Arabic', 'Segoe UI', Tahoma, sans-serif;
}

/* Keep outer flex layout LTR so Streamlit's native sidebar collapse transform (-300px)
   moves the collapsed sidebar offscreen left rather than sliding across the RTL page. */
[data-testid="stAppViewContainer"] {
    direction: ltr;
}

[data-testid="stMain"],
.stMainBlockContainer {
    direction: rtl;
    text-align: right;
}

[data-testid="stSidebar"] {
    direction: rtl;
    text-align: right;
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
}

.musnad-hero {
    background: linear-gradient(135deg, #154728 0%, #1F6338 60%, #264F36 100%);
    color: #FAF9F5;
    padding: 1.25rem 1.5rem;
    border-radius: 14px;
    border: 1px solid #2E7D4B;
    margin-bottom: 1rem;
    box-shadow: 0 4px 16px rgba(21, 71, 40, 0.12);
}

.musnad-hero h1 {
    margin: 0 0 0.35rem 0;
    font-size: 1.75rem;
    font-weight: 700;
    color: #FFFFFF;
}

.musnad-hero p {
    margin: 0;
    font-size: 0.96rem;
    color: #E7F3EC;
    line-height: 1.6;
}

.musnad-banner {
    padding: 0.7rem 1rem;
    border-radius: 10px;
    margin-bottom: 0.85rem;
    font-size: 0.92rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
}

.musnad-banner--replay {
    background: #FEF3C7;
    border: 1px solid #F59E0B;
    color: #78350F;
}

.musnad-banner--warmup {
    background: #ECFDF5;
    border: 1px solid #6EE7B7;
    color: #065F46;
}

.musnad-answer-card {
    background: #FFFFFF;
    border: 1px solid #E5E2D9;
    border-right: 5px solid #1B5E20;
    border-radius: 12px;
    padding: 1.15rem 1.25rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 8px rgba(28, 25, 23, 0.04);
}

.musnad-answer-card--refusal {
    border-right-color: #B45309;
    background: #FFFDF7;
}

.musnad-answer-body {
    font-family: 'Amiri', 'Noto Sans Arabic', serif;
    font-size: 1.22rem;
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
    padding-inline-start: 2.1rem;
    list-style-position: outside;
}

.musnad-answer-list li {
    margin-bottom: 0.35rem;
}

.musnad-answer-citation {
    margin-top: 0.6rem;
    font-size: 1.04rem;
    color: #166534;
    font-weight: 600;
}

.musnad-status-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-bottom: 0.65rem;
    align-items: center;
}

.musnad-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.18rem 0.62rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    line-height: 1.5;
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

.musnad-pill--db {
    direction: ltr;
    unicode-bidi: isolate;
    background: #EFF6FF;
    color: #1E40AF;
    border: 1px solid #BFDBFE;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.musnad-pill--extra {
    background: #F5F3FF;
    color: #5B21B6;
    border: 1px solid #DDD6FE;
}

.sanad-card {
    background: #FFFFFF;
    border: 1px solid #E5E2D9;
    border-radius: 12px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.85rem;
    min-width: 0;
    overflow: hidden;
}

.sanad-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 0.65rem;
}

.sanad-strip {
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    align-items: center;
    gap: 0.4rem;
    padding: 0.45rem 0.1rem 0.6rem 0.1rem;
    overflow-x: auto;
    overflow-y: hidden;
    direction: rtl;
    scrollbar-width: thin;
    scrollbar-color: #CBD5E1 transparent;
}

.narrator-chip {
    display: inline-flex;
    flex-direction: column;
    align-items: flex-start;
    flex: 0 0 auto;
    white-space: nowrap;
    padding: 0.4rem 0.72rem;
    border-radius: 10px;
    background: #F8F7F2;
    border: 1px solid #D6D3C8;
    font-size: 0.86rem;
    color: #292524;
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
    box-shadow: 0 1px 6px rgba(217, 119, 6, 0.18);
}

.narrator-chip-role {
    font-size: 0.68rem;
    font-weight: 600;
    opacity: 0.82;
    margin-bottom: 0.1rem;
}

.sanad-arrow {
    flex: 0 0 auto;
    color: #78716C;
    font-weight: 700;
    font-size: 1rem;
    padding: 0 0.15rem;
}

.matn-box {
    font-family: 'Amiri', 'Noto Sans Arabic', serif;
    font-size: 1.16rem;
    line-height: 2.0;
    color: #1C1917;
    background: #FCFBF8;
    padding: 0.85rem 1rem;
    border-radius: 8px;
    border: 1px solid #EAE6DC;
    white-space: pre-wrap;
}

.trace-card {
    background: #FFFFFF;
    border: 1px solid #E5E2D9;
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
    margin-bottom: 0.55rem;
}

.trace-card-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 0.35rem;
}

.trace-stage-title {
    font-weight: 700;
    font-size: 0.9rem;
    color: #1C1917;
}

.trace-dur-pill {
    direction: ltr;
    unicode-bidi: isolate;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.76rem;
    background: #F5F5F4;
    border: 1px solid #E7E5E4;
    padding: 0.1rem 0.5rem;
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
    margin-top: 0.65rem;
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
    direction: ltr;
    unicode-bidi: isolate;
    font-weight: 700;
    font-size: 0.95rem;
    color: #154728;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.musnad-error-card {
    background: #FEF2F2;
    border: 1px solid #FCA5A5;
    border-right: 5px solid #DC2626;
    border-radius: 10px;
    padding: 0.95rem 1.1rem;
    color: #7F1D1D;
    margin-bottom: 0.75rem;
}
</style>
"""


def inject_rtl_styles() -> None:
    """Inject global RTL typography and scholarly card styles."""
    st.markdown(_CSS, unsafe_allow_html=True)


def format_duration_ms(duration_ms: float | int | None) -> str:
    """Format millisecond duration concisely for trace badges."""
    val = float(duration_ms or 0.0)
    if val >= 1000.0:
        return f"{val / 1000.0:.2f} s"
    return f"{val:.1f} ms"


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
            role_label = f"الطبقة {pos}" if pos > 0 else "راوٍ"
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
    """Render top RTL hero banner."""
    st.markdown(
        f"""
        <div class="musnad-hero">
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_how_it_works() -> None:
    """Render concise Arabic 'how it works' expander."""
    with st.expander("كيف يعمل مُسنَد؟", expanded=False):
        st.markdown(
            """
1. **موجّه المسار (`Intent Router v3`)**: يفرز السؤال تلقائيًا بين الأسئلة المتنية/الفقهية وأسئلة الرواة والأسانيد.
2. **الاسترجاع الهجين المُحسَّن (`HyDE + Gemini Embeddings`)**: يوسّع السؤال المتني دلاليًا ويبحث في متون *صحيح مسلم* الموثّقة.
3. **وكيل السند الحتمي (`Tool Agent + MIS Sanad Graph`)**: لأسئلة الرواة والسلاسل، يستعلم الوكيل مباشرة من قاعدة بيانات **SQLite** للأسانيد، مع التحقق الصارم من عدم ذكر أي راوٍ غير وارد في السند.
4. **التحقق وإرفاق السند**: تُفحَص كل إحالة (`المصدر: صحيح مسلم، حديث رقم ...`) وتُربط سلاسل الرواة حتميًا من شيخ الإمام مسلم حتى الصحابي الجليل، أو يمتنع النظام بنص صريح إذا لم تكفِ المصادر.
            """.strip()
        )


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_SPAN_RE = re.compile(r"`([^`]+)`")
_ORDERED_LIST_RE = re.compile(r"^\d+[\.\)]\s+(.*)$")
_BULLET_LIST_RE = re.compile(r"^[-*•]\s+(.*)$")
_CITATION_LINE_RE = re.compile(r"^\(المصدر:\s*.+\)$")

SANAD_STATUS_ARABIC_UI: dict[str, str] = {
    "VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK": "الحديث موثق محليًا ولا يوجد ربط مقبول بسند المسند بعد",
    "NO_RECORDED_ISNAD": "لا يوجد إسناد مسجّل في قاعدة البيانات",
    "LINKED_WITH_ZERO_ISNADS": "الحديث مربوط ولا توجد له طرق مسجّلة",
    "AMBIGUOUS_MIS_LINK": "توجد أكثر من مطابقة محتملة في قاعدة السند",
    "GRAPH_UNAVAILABLE": "تعذّر الوصول إلى قاعدة بيانات السند",
}


def _format_inline_markdown_html(text: str) -> str:
    """Escape HTML safely and render **bold** and `code` spans without CommonMark leaks."""
    escaped = html.escape(text)
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    return _CODE_SPAN_RE.sub(r'<code dir="ltr">\1</code>', escaped)


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


def render_sanad_chain_html(sanad_entry: dict[str, Any]) -> str:
    """Build escaped HTML card with horizontal narrator chips from Muslim's teacher to Companion."""
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
    source_badge = '<span class="musnad-pill musnad-pill--db">source: SQLite sanad graph</span>'

    if not isnads:
        status_ar = SANAD_STATUS_ARABIC_UI.get(
            status, status or "لا يوجد إسناد مسجل في قاعدة البيانات"
        )
        return (
            f'<div class="sanad-card">'
            f'<div class="sanad-card-header">'
            f'<strong>سند حديث رقم {hadith_id}</strong>'
            f'<div class="musnad-status-row">{source_badge}</div>'
            f'</div>'
            f'<div class="trace-detail">الحالة: {html.escape(status_ar)}</div>'
            f'</div>'
        )

    chips_ordered = format_narrator_chain_for_display(isnads[0])
    chip_parts: list[str] = []
    for idx, chip in enumerate(chips_ordered):
        if idx > 0:
            chip_parts.append('<span class="sanad-arrow" aria-hidden="true">←</span>')
        cls = "narrator-chip"
        if chip["role"] == "companion":
            cls += " narrator-chip--companion"
        elif chip["role"] == "teacher":
            cls += " narrator-chip--teacher"
        chip_parts.append(
            f'<span class="{cls}">'
            f'<span class="narrator-chip-role">{html.escape(chip["role_label"])}</span>'
            f'<span>{html.escape(chip["name"])}</span>'
            f'</span>'
        )

    return (
        f'<div class="sanad-card">'
        f'<div class="sanad-card-header">'
        f'<strong>سند حديث رقم {hadith_id} (من شيخ مسلم إلى الصحابي)</strong>'
        f'<div class="musnad-status-row">{extra_html}{source_badge}</div>'
        f'</div>'
        f'<div class="sanad-strip">{"".join(chip_parts)}</div>'
        f'</div>'
    )


def render_answer_panel(
    result: dict[str, Any],
    *,
    refusal_text: str,
    replay_reason: str | None = None,
) -> None:
    """Render replay banner (if active), answer card, horizontal sanad chips, and retrieved matns."""
    if replay_reason:
        st.markdown(
            f'<div class="musnad-banner musnad-banner--replay">'
            f'<strong>Recorded run — replayed</strong>'
            f'<span>{_format_inline_markdown_html(replay_reason)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    answer = str(result.get("answer") or refusal_text)
    is_refusal = answer.strip() == refusal_text.strip()

    pills: list[str] = []
    if is_refusal:
        pills.append('<span class="musnad-pill musnad-pill--warn">امتناع منضبط عن الإجابة</span>')
    else:
        pills.append('<span class="musnad-pill musnad-pill--ok">إجابة موثّقة من صحيح مسلم</span>')

    if result.get("agent_used"):
        pills.append('<span class="musnad-pill musnad-pill--db">مسار الوكيل الإسنادي</span>')
    if result.get("agent_fallback"):
        pills.append('<span class="musnad-pill musnad-pill--warn">تحويل احتياطي لمسار المتون</span>')
    if result.get("regenerated"):
        pills.append('<span class="musnad-pill musnad-pill--warn">تمت إعادة الصياغة بعد فحص التوثيق</span>')

    card_cls = "musnad-answer-card musnad-answer-card--refusal" if is_refusal else "musnad-answer-card"
    body_html = format_answer_body_html(answer)
    st.markdown(
        f'<div class="{card_cls}">'
        f'<div class="musnad-status-row">{"".join(pills)}</div>'
        f'<div class="musnad-answer-body">{body_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    sanad_entries = list(result.get("sanad") or [])
    if sanad_entries:
        st.markdown("### سلاسل الإسناد الموثّقة")
        for entry in sanad_entries:
            st.markdown(render_sanad_chain_html(entry), unsafe_allow_html=True)
            isnads = list(entry.get("isnads") or [])
            if len(isnads) > 1:
                hid = entry.get("hadith_id", "؟")
                with st.expander(f"عرض بقية طرق حديث رقم {hid} ({len(isnads)} طرق مسجلة)", expanded=False):
                    for route_idx, route in enumerate(isnads[1:], start=2):
                        ordered = format_narrator_chain_for_display(route)
                        names = " ← ".join(item["name"] for item in ordered)
                        st.markdown(f"**الطريق {route_idx}:** {names}")
    elif result.get("sanad_error"):
        st.warning(f"تعذّر إرفاق السند الحتمي: {result['sanad_error']}")

    chunks = list(result.get("chunks") or [])
    if chunks:
        st.markdown("### الأحاديث المسترجعة")
        for idx, chunk in enumerate(chunks, start=1):
            hid = chunk.get("hadith_id", "؟")
            meta = chunk.get("metadata") or {}
            chapter = meta.get("chapter_arabic") or meta.get("chapter_ar") or "غير مبوّب"
            rank = chunk.get("rank", idx)
            matn = str(chunk.get("text") or chunk.get("matn") or "").strip()
            with st.expander(f"[{rank}] حديث رقم {hid} — {chapter}", expanded=False):
                if matn:
                    st.markdown(
                        f'<div class="matn-box">{html.escape(matn)}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("تم الوصول لهذا الحديث مباشرة عبر رقم الحديث في جدول السند.")


def _summarize_trace_event(stage: str, data: dict[str, Any]) -> tuple[str, bool]:
    """Build concise Arabic description + SQLite chain badge flag for one trace event."""
    show_sqlite_badge = False
    if stage == "router":
        decision = data.get("decision") or "—"
        source = data.get("source") or "—"
        prob = data.get("probability")
        prob_str = f" | احتمال السند: {prob:.3f}" if isinstance(prob, (int, float)) else ""
        return f"القرار: {decision} | المصدر: {source}{prob_str}", False

    if stage == "retrieval":
        top5 = data.get("top5") or []
        ids_str = ", ".join(str(item.get("hadith_id")) for item in top5) or "لا يوجد"
        hyde = str(data.get("hyde_text") or "").strip()
        hyde_snippet = (hyde[:110] + "…") if len(hyde) > 110 else hyde
        parts = [f'أعلى 5 أحاديث: <code dir="ltr">[{html.escape(ids_str)}]</code>']
        if hyde_snippet:
            parts.append(f"HyDE: {html.escape(hyde_snippet)}")
        if data.get("legacy_fallback"):
            parts.append(html.escape("⚠️ تحويل لمسار الاسترجاع المحلي (legacy_fallback)"))
        return "<br/>".join(parts), False

    if stage == "agent":
        if data.get("agent_fallback"):
            reason = data.get("fallback_reason") or "غير محدد"
            return html.escape(f"⚠️ تعذّر الوكيل وتم التحويل الاحتياطي: {reason}"), False
        tool_name = str(data.get("name") or "")
        args = data.get("arguments") or {}
        returned = data.get("returned_ids") or []
        if tool_name == "get_isnad":
            show_sqlite_badge = True
            cnt = int(data.get("isnad_count", 0) or 0)
            return (
                f'الأداة: <code dir="ltr">get_isnad({html.escape(str(args))})</code> → '
                f'أُعيد: <code dir="ltr">{html.escape(str(returned))}</code> | '
                f'عدد الأسانيد: {html.escape(_format_isnad_count_ar(cnt))}',
                show_sqlite_badge,
            )
        return (
            f'الأداة: <code dir="ltr">{html.escape(tool_name)}({html.escape(str(args))})</code> → '
            f'أُعيد: <code dir="ltr">{html.escape(str(returned))}</code>',
            False,
        )

    if stage == "generation":
        model = data.get("model") or "—"
        attempts = data.get("attempts") or 1
        timeout_s = data.get("timeout_s")
        timeout_label = f"{float(timeout_s):g} ث" if isinstance(timeout_s, (int, float)) else "45 ث"
        if data.get("event_kind") == "timeout_retry":
            return (
                html.escape(
                    f"⏱️ انتهت مهلة التوليد ({model}) بعد {timeout_label} في المحاولة الأولى — جاري إعادة المحاولة مرة واحدة…"
                ),
                False,
            )
        if data.get("timed_out"):
            return (
                html.escape(
                    f"⏱️ انتهت مهلة التوليد ({model}) بعد {timeout_label} في المحاولتين ({attempts} محاولات) — يُرجى إعادة المحاولة."
                ),
                False,
            )
        if data.get("timeout_retries"):
            return (
                html.escape(
                    f"النموذج: {model} | عدد المحاولات: {attempts} (نجحت بعد إعادة محاولة انتهاء المهلة)"
                ),
                False,
            )
        return html.escape(f"النموذج: {model} | عدد المحاولات: {attempts}"), False

    if stage == "validation":
        status = data.get("status") or "—"
        pieces = [f"الحالة: {status}"]
        if data.get("retry_reason"):
            pieces.append(f"سبب الإعادة: {data['retry_reason']}")
        if data.get("refusal_reason"):
            pieces.append(f"سبب الامتناع: {data['refusal_reason']}")
        return html.escape(" | ".join(pieces)), False

    if stage == "sanad":
        show_sqlite_badge = True
        hid = data.get("hadith_id")
        status = str(data.get("status") or "—")
        status_ar = SANAD_STATUS_ARABIC_UI.get(status, status)
        cnt = int(data.get("isnad_count", 0) or 0)
        ms = data.get("ms")
        ms_str = f" | {ms} ms" if ms is not None else ""
        return (
            html.escape(f"حديث {hid}: {status_ar} | {_format_isnad_count_ar(cnt)}{ms_str}"),
            show_sqlite_badge,
        )

    return html.escape(str(data)), False


def render_trace_panel_html(
    events: list[dict[str, Any]],
    summary: dict[str, Any] | None = None,
    *,
    in_progress: bool = False,
) -> str:
    """Build full HTML for the progressive execution trace panel."""
    blocks: list[str] = []

    if in_progress and not events:
        blocks.append(
            '<div class="trace-card"><div class="trace-stage-title">⏳ جاري بدء التوجيه والبحث…</div>'
            '<div class="trace-detail">يتم تجهيز الطلب وإرسال مراحل التنفيذ فور ورودها.</div></div>'
        )

    for ev in events:
        stage = str(ev.get("stage") or "")
        data = dict(ev.get("data") or {})
        icon, title_ar = STAGE_LABELS.get(stage, ("•", stage))
        dur_str = format_duration_ms(ev.get("duration_ms"))
        detail_html, is_chain_db = _summarize_trace_event(stage, data)
        db_badge = (
            '<span class="musnad-pill musnad-pill--db">source: SQLite sanad graph</span>'
            if is_chain_db
            else ""
        )
        blocks.append(
            f'<div class="trace-card">'
            f'<div class="trace-card-head">'
            f'<span class="trace-stage-title">{icon} {html.escape(title_ar)} <code>{html.escape(stage)}</code></span>'
            f'<div class="musnad-status-row" style="margin-bottom:0">{db_badge}<span class="trace-dur-pill">{html.escape(dur_str)}</span></div>'
            f'</div>'
            f'<div class="trace-detail">{detail_html}</div>'
            f'</div>'
        )

    if in_progress and events:
        blocks.append(
            '<div class="trace-card"><div class="trace-detail">⏳ بانتظار المرحلة التالية…</div></div>'
        )

    if summary:
        total_ms = format_duration_ms(summary.get("total_duration_ms"))
        counts = dict(summary.get("call_counts") or {})
        metrics = [
            ("الزمن الكلي", total_ms),
            ("Pro", str(counts.get("pro_calls", 0))),
            ("Flash", str(counts.get("flash_calls", 0))),
            ("Embeddings", str(counts.get("embed_calls", 0))),
            ("Tools", str(counts.get("tool_calls", 0))),
            ("SQLite", str(counts.get("sqlite_queries", 0))),
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
        with st.expander("تفاصيل الخطأ (Details)", expanded=False):
            st.code(details_text, language="text")
