"""Musnad (مُسنَد) Streamlit web interface."""

from __future__ import annotations

from pathlib import Path
import os
import sys

import streamlit as st

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.components import (
    inject_rtl_styles,
    render_answer_panel,
    render_error_card,
    render_hero,
    render_how_it_works,
    render_trace_panel_html,
)
from app.config import DEFAULT_EXAMPLES, AppConfig, load_config
from app.replay import (
    load_recorded_runs,
    make_replay_banner_reason,
    match_recorded_run,
    resolve_replay_mode,
    serve_recorded_run,
)
from app.state import (
    bootstrap_environment,
    configure_logging,
    execute_live_query,
    format_error_details,
    has_live_credentials,
    init_session_state,
    logger,
    resolve_use_agent_override,
    warm_up_resources,
)
from src.answer import REFUSAL


def _select_example_callback(question: str) -> None:
    """Populate question input and trigger execution on the same rerun."""
    st.session_state["question_input"] = question
    st.session_state["pending_question"] = question


def _render_sidebar(
    config: AppConfig,
    warm_status: dict,
    *,
    is_replay: bool = False,
    replay_reason: str | None = None,
) -> tuple[str, str]:
    """Render Advanced settings sidebar and return (agent_mode, retrieval_mode)."""
    with st.sidebar:
        st.header("الإعدادات المتقدمة")
        agent_options = ["auto", "on", "off"]
        agent_labels = {
            "auto": "auto — توجيه ذكي تلقائي",
            "on": "on — تفعيل الوكيل دائمًا",
            "off": "off — مسار المتون فقط",
        }
        current_agent = st.session_state.get("agent_mode", config.agent_mode)
        if current_agent not in agent_options:
            current_agent = "auto"
        agent_mode = st.selectbox(
            "وضع الوكيل الإسنادي",
            options=agent_options,
            index=agent_options.index(current_agent),
            format_func=lambda opt: agent_labels.get(opt, opt),
            key="agent_mode",
        )

        retrieval_options = ["upgraded", "legacy"]
        retrieval_labels = {
            "upgraded": "upgraded — Gemini + HyDE (افتراضي)",
            "legacy": "legacy — E5 + BM25 + CrossEncoder (محلي)",
        }
        current_ret = st.session_state.get("retrieval_mode", config.pipeline_mode)
        if config.cloud_mode or current_ret not in retrieval_options:
            current_ret = "upgraded"
            st.session_state["retrieval_mode"] = "upgraded"

        retrieval_mode = st.selectbox(
            "مسار الاسترجاع",
            options=retrieval_options,
            index=retrieval_options.index(current_ret),
            format_func=lambda opt: retrieval_labels.get(opt, opt),
            disabled=config.cloud_mode,
            key="retrieval_mode",
        )
        if config.cloud_mode:
            st.caption("الوضع السحابي مفعّل (`MUSNAD_CLOUD=1`): المسار المحلي `legacy` معطّل.")

        st.divider()
        st.subheader("حالة المنظومة")
        creds_ok, creds_source = has_live_credentials(config)
        st.markdown(
            f"- **وضع التشغيل:** {'عرض مسجّل (Replay)' if is_replay else 'مباشر (Live)'}\n"
            f"- **الأوزان (Router v3):** {'جاهزة' if warm_status.get('router_ready') else 'غير متوفرة'}\n"
            f"- **قاعدة بيانات السند:** {'جاهزة' if warm_status.get('sanad_ready') else 'غير متوفرة'} "
            f"({warm_status.get('hadith_count', 0)} حديث)\n"
            f"- **فهرس المتون:** {'جاهز' if warm_status.get('pipeline_ready') else 'وضع مسجّل / غير محمّل'}\n"
            f"- **الاعتمادات الحية:** {'متوفرة (' + creds_source + ')' if creds_ok else 'غير متوفرة'}"
        )
        if is_replay and replay_reason:
            st.info(f"Recorded run — replayed: {replay_reason}")
    return agent_mode, retrieval_mode


def main() -> None:
    """Entry point for Streamlit UI."""
    config = load_config()
    configure_logging(config.log_level)
    bootstrap_environment(config)

    st.set_page_config(
        page_title=config.app_title,
        page_icon="📜",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    init_session_state(config)
    inject_rtl_styles()

    render_hero(config.app_title, config.app_subtitle)
    render_how_it_works()

    is_replay, base_replay_reason = resolve_replay_mode(config)

    # Warm-up cached resources cleanly on first load
    selected_retrieval = (
        "upgraded"
        if config.cloud_mode
        else str(st.session_state.get("retrieval_mode", config.pipeline_mode))
    )
    should_load_pipeline = not is_replay
    if not st.session_state.get("warmed_up"):
        with st.spinner("جاري تهيئة الفهارس وقاعدة بيانات السند للمرة الأولى..."):
            warm_status = warm_up_resources(
                config, selected_retrieval, load_pipeline=should_load_pipeline
            )
        st.session_state["warmed_up"] = True
        if warm_status.get("error") is None and (warm_status.get("pipeline_ready") or is_replay):
            st.markdown(
                f"""
                <div class="musnad-banner musnad-banner--warmup">
                    <span>تمت تهيئة المنظومة وقاعدة بيانات السند ({warm_status.get('hadith_count', 0)} حديثًا).</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        warm_status = warm_up_resources(
            config, selected_retrieval, load_pipeline=should_load_pipeline
        )

    agent_mode, retrieval_mode = _render_sidebar(
        config, warm_status, is_replay=is_replay, replay_reason=base_replay_reason
    )

    if is_replay and base_replay_reason:
        st.info(f"ℹ️ **Recorded run — replayed**: {base_replay_reason}")

    if warm_status.get("error") is not None and st.session_state.get("last_result") is None and not is_replay:
        friendly, details = format_error_details(warm_status["error"])
        render_error_card(
            "تعذّر تهيئة بعض ملفات الفهرس عند بدء التشغيل، يرجى التحقق من المسارات.",
            details or friendly,
        )

    st.markdown("#### أمثلة سريعة")
    ex_cols = st.columns(len(DEFAULT_EXAMPLES), gap="small")
    for col, ex in zip(ex_cols, DEFAULT_EXAMPLES):
        with col:
            st.button(
                ex.label,
                key=f"example_{ex.key}",
                use_container_width=True,
                on_click=_select_example_callback,
                args=(ex.question,),
            )

    question_text = st.text_area(
        "سؤالك في صحيح مسلم",
        key="question_input",
        height=92,
        placeholder="مثال: ما فضل قيام شهر رمضان؟ أو: ما أسانيد حديث رقم 7306 ومن الصحابي الذي رواه؟",
    )
    submit_clicked = st.button("اسأل مُسنَد", type="primary", use_container_width=False)

    pending_q = st.session_state.pop("pending_question", None)
    active_question = pending_q if pending_q is not None else (question_text if submit_clicked else None)

    if active_question is not None:
        cleaned = active_question.strip()
        if not cleaned:
            st.info("يرجى كتابة سؤال أولًا قبل بدء البحث.")
        else:
            st.session_state["last_question"] = cleaned
            st.session_state["last_error"] = None
            st.session_state["last_replay_reason"] = None

            pipeline = warm_status.get("pipeline")
            matn_map = warm_status.get("matn_by_hadith_id") or {}

            def _run_replay_flow(reason_prefix: str) -> None:
                recorded_runs = load_recorded_runs(config.replay_path)
                matched, exact = match_recorded_run(cleaned, recorded_runs)
                if matched is None:
                    msg = "لا تتوفر عروض مسجّلة في ملف recorded_runs.json حاليًا."
                    logger.error("No recorded runs available at %s", config.replay_path)
                    st.session_state["last_result"] = None
                    st.session_state["last_trace"] = None
                    st.session_state["last_error"] = (msg, str(config.replay_path))
                    render_error_card(msg, str(config.replay_path))
                    return

                full_reason = make_replay_banner_reason(
                    reason_prefix,
                    matched_question=str(matched.get("question") or ""),
                    exact_match=exact,
                )
                col_answer, col_trace = st.columns([3, 2], gap="large")
                with col_answer:
                    answer_slot = st.empty()
                    answer_slot.info("⏳ جاري تشغيل العرض المسجّل بخطواته الزمنية الفعلية…")
                with col_trace:
                    st.markdown("### التتبع المباشر لمراحل التنفيذ")
                    trace_slot = st.empty()

                def _on_replay_progress(events_snapshot: list[dict]) -> None:
                    trace_slot.markdown(
                        render_trace_panel_html(events_snapshot, None, in_progress=True),
                        unsafe_allow_html=True,
                    )

                try:
                    speed = float(os.getenv("MUSNAD_REPLAY_SPEED", "1.0"))
                except ValueError:
                    speed = 1.0

                result, trace_dict = serve_recorded_run(
                    matched,
                    matn_by_hadith_id=matn_map,
                    on_progress=_on_replay_progress,
                    pace=speed > 0.0,
                    speed_scale=speed,
                )
                st.session_state["last_result"] = result
                st.session_state["last_trace"] = trace_dict
                st.session_state["last_replay_reason"] = full_reason
                answer_slot.empty()
                with col_answer:
                    render_answer_panel(
                        result,
                        refusal_text=REFUSAL,
                        replay_reason=full_reason,
                    )
                trace_slot.markdown(
                    render_trace_panel_html(
                        list(trace_dict.get("events") or []),
                        trace_dict.get("summary"),
                        in_progress=False,
                    ),
                    unsafe_allow_html=True,
                )

            if is_replay:
                _run_replay_flow(base_replay_reason or "عرض مسجّل.")
            elif pipeline is None:
                err = warm_status.get("error") or RuntimeError("Retrieval pipeline is not initialized.")
                logger.error("Pipeline unavailable for question execution: %s", err)
                friendly, details = format_error_details(err)
                st.session_state["last_result"] = None
                st.session_state["last_trace"] = None
                st.session_state["last_error"] = (friendly, details)
                render_error_card(friendly, details)
            else:
                col_answer, col_trace = st.columns([3, 2], gap="large")
                with col_answer:
                    answer_slot = st.empty()
                    answer_slot.info("⏳ جاري تحليل السؤال واسترجاع المتون والأسانيد الموثّقة…")
                with col_trace:
                    st.markdown("### التتبع المباشر لمراحل التنفيذ")
                    trace_slot = st.empty()

                def _on_trace_progress(events_snapshot: list[dict]) -> None:
                    trace_slot.markdown(
                        render_trace_panel_html(events_snapshot, None, in_progress=True),
                        unsafe_allow_html=True,
                    )

                result, trace_dict, err = execute_live_query(
                    cleaned,
                    pipeline,
                    top_k=config.top_k,
                    use_agent=resolve_use_agent_override(agent_mode),
                    sanad_db_path=config.sanad_db_path,
                    matn_by_hadith_id=matn_map,
                    on_progress=_on_trace_progress,
                )

                if err is not None or result is None:
                    answer_slot.empty()
                    if config.cloud_mode:
                        logger.warning(
                            "Cloud API execution failed (%s); falling back to replay mode.",
                            type(err).__name__ if err else "EmptyResult",
                        )
                        recorded_runs = load_recorded_runs(config.replay_path)
                        matched, exact = match_recorded_run(cleaned, recorded_runs)
                        if matched is not None:
                            cloud_reason = make_replay_banner_reason(
                                "تعذّر الاتصال بخدمة التوليد السحابية مؤقتًا، لذا تم التحويل تلقائيًا إلى العرض المسجّل.",
                                matched_question=str(matched.get("question") or ""),
                                exact_match=exact,
                            )
                            replay_res, replay_trace = serve_recorded_run(
                                matched,
                                matn_by_hadith_id=matn_map,
                                on_progress=None,
                                pace=False,
                            )
                            st.session_state["last_result"] = replay_res
                            st.session_state["last_trace"] = replay_trace
                            st.session_state["last_replay_reason"] = cloud_reason
                            with col_answer:
                                render_answer_panel(
                                    replay_res,
                                    refusal_text=REFUSAL,
                                    replay_reason=cloud_reason,
                                )
                            trace_slot.markdown(
                                render_trace_panel_html(
                                    list(replay_trace.get("events") or []),
                                    replay_trace.get("summary"),
                                    in_progress=False,
                                ),
                                unsafe_allow_html=True,
                            )
                        else:
                            friendly, details = format_error_details(
                                err or RuntimeError("Cloud generation failed.")
                            )
                            st.session_state["last_result"] = None
                            st.session_state["last_trace"] = trace_dict
                            st.session_state["last_error"] = (friendly, details)
                            with col_answer:
                                render_error_card(friendly, details)
                    else:
                        friendly, details = format_error_details(
                            err or RuntimeError("Unexpected empty query result.")
                        )
                        st.session_state["last_result"] = None
                        st.session_state["last_trace"] = trace_dict
                        st.session_state["last_error"] = (friendly, details)
                        with col_answer:
                            render_error_card(friendly, details)
                        with col_trace:
                            trace_slot.markdown(
                                render_trace_panel_html(
                                    list((trace_dict or {}).get("events") or []),
                                    (trace_dict or {}).get("summary"),
                                    in_progress=False,
                                ),
                                unsafe_allow_html=True,
                            )
                else:
                    st.session_state["last_result"] = result
                    st.session_state["last_trace"] = trace_dict
                    st.session_state["session_query_count"] += 1
                    answer_slot.empty()
                    with col_answer:
                        render_answer_panel(
                            result,
                            refusal_text=REFUSAL,
                            replay_reason=None,
                        )
                    trace_slot.markdown(
                        render_trace_panel_html(
                            list((trace_dict or {}).get("events") or []),
                            (trace_dict or {}).get("summary"),
                            in_progress=False,
                        ),
                        unsafe_allow_html=True,
                    )
    elif st.session_state.get("last_error") is not None or st.session_state.get("last_result") is not None:
        col_answer, col_trace = st.columns([3, 2], gap="large")
        with col_answer:
            last_err = st.session_state.get("last_error")
            if last_err is not None:
                friendly, details = last_err
                render_error_card(friendly, details)
            elif st.session_state.get("last_result") is not None:
                render_answer_panel(
                    st.session_state["last_result"],
                    refusal_text=REFUSAL,
                    replay_reason=st.session_state.get("last_replay_reason"),
                )
        with col_trace:
            last_trace = st.session_state.get("last_trace")
            if last_trace is not None:
                st.markdown("### التتبع المباشر لمراحل التنفيذ")
                st.markdown(
                    render_trace_panel_html(
                        list(last_trace.get("events") or []),
                        last_trace.get("summary"),
                        in_progress=False,
                    ),
                    unsafe_allow_html=True,
                )


if __name__ == "__main__":
    main()
