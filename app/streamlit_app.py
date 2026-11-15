"""Musnad (مُسنَد) minimalist Arabic RTL Streamlit web interface."""

from __future__ import annotations

from dataclasses import replace
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
    render_footer,
    render_hero,
    render_live_progress_html,
    render_trace_panel_html,
)
from app.config import DEFAULT_EXAMPLES, AppConfig, load_config
from app.replay import (
    REPLAY_BANNER_TEXT,
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
    init_session_state,
    logger,
    resolve_use_agent_override,
    warm_up_resources,
)
from app.usage_guard import (
    UsageDecision,
    acquire_usage_slot,
    get_streamlit_client_ip,
    peek_usage_limits,
)
from src.answer import REFUSAL, GenerationTimeoutError


def _select_example_callback(question: str) -> None:
    """Fill the question box and mark the example for immediate submission."""
    st.session_state["question_input"] = question
    st.session_state["pending_question"] = question


def _render_sidebar(config: AppConfig) -> tuple[str, str]:
    """Render collapsed-by-default Advanced settings sidebar and return (agent_mode, retrieval_mode)."""
    with st.sidebar:
        st.header("إعدادات متقدمة")
        agent_options = ["auto", "on", "off"]
        agent_labels = {
            "auto": "توجيه ذكي تلقائي (موصى به)",
            "on": "تفعيل وكيل السند دائمًا",
            "off": "البحث في المتون فقط",
        }
        current_agent = st.session_state.get("agent_mode", config.agent_mode)
        if current_agent not in agent_options:
            current_agent = "auto"
        agent_mode = st.selectbox(
            "وضع الإجابة",
            options=agent_options,
            index=agent_options.index(current_agent),
            format_func=lambda opt: agent_labels.get(opt, opt),
            key="agent_mode",
        )

        retrieval_options = ["upgraded", "legacy"]
        retrieval_labels = {
            "upgraded": "الاسترجاع الدلالي المُحسَّن (افتراضي)",
            "legacy": "الاسترجاع المحلي التقليدي",
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
            st.caption("في التشغيل السحابي يقتصر المسار على الاسترجاع الدلالي المُحسَّن.")
    return agent_mode, retrieval_mode


def _render_result_with_trace(
    result: dict,
    trace_dict: dict | None,
    *,
    replay_reason: str | None,
) -> None:
    """Render the single unified Answer Card, used hadiths expander, and trace expander."""
    with st.container(key="musnad_results_area"):
        render_answer_panel(
            result,
            refusal_text=REFUSAL,
            replay_reason=replay_reason,
        )
        events = list((trace_dict or {}).get("events") or [])
        summary = (trace_dict or {}).get("summary")
        if events or summary:
            with st.expander("كيف وصل النظام للإجابة؟", expanded=False):
                st.markdown(
                    render_trace_panel_html(events, summary, in_progress=False),
                    unsafe_allow_html=True,
                )


def main() -> None:
    """Entry point for minimalist RTL Streamlit UI."""
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

    # 1. Above the fold: title + one short line ONLY
    render_hero(config.app_title, config.app_subtitle)

    session_live_count = int(st.session_state.get("live_query_count", 0))
    client_ip = get_streamlit_client_ip()
    usage_peek = peek_usage_limits(
        config,
        session_count=session_live_count,
        client_ip=client_ip,
    )
    st.session_state["usage_status"] = usage_peek
    usage_capped_reason = usage_peek.banner_reason if not usage_peek.allowed else None
    is_replay, base_replay_reason = resolve_replay_mode(
        config,
        usage_capped_reason=usage_capped_reason,
    )

    selected_retrieval = (
        "upgraded"
        if config.cloud_mode
        else str(st.session_state.get("retrieval_mode", config.pipeline_mode))
    )
    should_load_pipeline = not is_replay
    if not st.session_state.get("warmed_up"):
        with st.spinner("جاري تجهيز فهرس صحيح مسلم وقاعدة السند…"):
            warm_status = warm_up_resources(
                config, selected_retrieval, load_pipeline=should_load_pipeline
            )
        st.session_state["warmed_up"] = True
    else:
        warm_status = warm_up_resources(
            config, selected_retrieval, load_pipeline=should_load_pipeline
        )

    agent_mode, _ = _render_sidebar(config)

    if warm_status.get("error") is not None and st.session_state.get("last_result") is None and not is_replay:
        friendly, details = format_error_details(warm_status["error"])
        render_error_card(
            "تعذّر تهيئة ملفات الفهرس عند بدء التشغيل، يرجى التحقق من الإعدادات.",
            details or friendly,
        )

    # 2. Large centered question box with Enter submit + prominent "اسأل" button
    with st.container(key="musnad_query_area"):
        with st.form("query_form", clear_on_submit=False, border=False):
            q_col, btn_col = st.columns([5.2, 1], gap="small")
            with q_col:
                question_text = st.text_input(
                    "سؤالك",
                    key="question_input",
                    placeholder="اكتب سؤالك هنا… مثال: من روى حديث الدين النصيحة؟",
                    label_visibility="collapsed",
                )
            with btn_col:
                submit_clicked = st.form_submit_button(
                    "اسأل",
                    type="primary",
                    use_container_width=True,
                )

    # 3. Four compact example chips under the question box (click = fill + submit)
    with st.container(key="musnad_chips_row"):
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

    pending_q = st.session_state.pop("pending_question", None)
    active_question = pending_q if pending_q is not None else (question_text if submit_clicked else None)

    if active_question is not None:
        cleaned = active_question.strip()
        if not cleaned:
            st.info("يرجى كتابة سؤال أولًا قبل الضغط على اسأل.")
        else:
            st.session_state["last_question"] = cleaned
            st.session_state["last_error"] = None
            st.session_state["last_replay_reason"] = None

            pipeline = warm_status.get("pipeline")
            matn_map = warm_status.get("matn_by_hadith_id") or {}
            progress_slot = st.empty()

            def _on_progress_step(events_snapshot: list[dict]) -> None:
                progress_slot.markdown(
                    render_live_progress_html(events_snapshot),
                    unsafe_allow_html=True,
                )

            def _run_replay_flow(reason_prefix: str | None) -> None:
                recorded_runs = load_recorded_runs(config.replay_path)
                matched, exact = match_recorded_run(cleaned, recorded_runs)
                if matched is None:
                    progress_slot.empty()
                    msg = "لا تتوفر عروض مسجّلة في الوقت الحالي."
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
                try:
                    speed = float(os.getenv("MUSNAD_REPLAY_SPEED", "1.0"))
                except ValueError:
                    speed = 1.0

                result, trace_dict = serve_recorded_run(
                    matched,
                    matn_by_hadith_id=matn_map,
                    on_progress=_on_progress_step,
                    pace=speed > 0.0,
                    speed_scale=speed,
                )
                progress_slot.empty()
                st.session_state["last_result"] = result
                st.session_state["last_trace"] = trace_dict
                st.session_state["last_replay_reason"] = full_reason
                _render_result_with_trace(
                    result,
                    trace_dict,
                    replay_reason=full_reason,
                )

            usage_blocked_reason: str | None = None
            decision: UsageDecision | None = None
            if not is_replay and pipeline is not None:
                decision = acquire_usage_slot(
                    config,
                    session_count=session_live_count,
                    client_ip=client_ip,
                )
                st.session_state["usage_status"] = decision
                if not decision.allowed:
                    usage_blocked_reason = REPLAY_BANNER_TEXT

            if is_replay or usage_blocked_reason is not None:
                _run_replay_flow(usage_blocked_reason or base_replay_reason or REPLAY_BANNER_TEXT)
            elif pipeline is None:
                progress_slot.empty()
                err = warm_status.get("error") or RuntimeError("Retrieval pipeline is not initialized.")
                logger.error("Pipeline unavailable for question execution: %s", err)
                friendly, details = format_error_details(err)
                st.session_state["last_result"] = None
                st.session_state["last_trace"] = None
                st.session_state["last_error"] = (friendly, details)
                render_error_card(friendly, details)
            else:
                st.session_state["live_query_count"] = session_live_count + 1
                if decision is not None:
                    st.session_state["usage_status"] = replace(
                        decision,
                        session_count=session_live_count + 1,
                    )
                result, trace_dict, err = execute_live_query(
                    cleaned,
                    pipeline,
                    top_k=config.top_k,
                    use_agent=resolve_use_agent_override(agent_mode),
                    sanad_db_path=config.sanad_db_path,
                    matn_by_hadith_id=matn_map,
                    on_progress=_on_progress_step,
                )
                progress_slot.empty()

                if err is not None or result is None:
                    if config.cloud_mode and not isinstance(err, GenerationTimeoutError):
                        logger.warning(
                            "Cloud API execution failed (%s); falling back to replay mode.",
                            type(err).__name__ if err else "EmptyResult",
                        )
                        recorded_runs = load_recorded_runs(config.replay_path)
                        matched, exact = match_recorded_run(cleaned, recorded_runs)
                        if matched is not None:
                            cloud_reason = make_replay_banner_reason(
                                REPLAY_BANNER_TEXT,
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
                            _render_result_with_trace(
                                replay_res,
                                replay_trace,
                                replay_reason=cloud_reason,
                            )
                        else:
                            friendly, details = format_error_details(
                                err or RuntimeError("Cloud generation failed.")
                            )
                            st.session_state["last_result"] = None
                            st.session_state["last_trace"] = trace_dict
                            st.session_state["last_error"] = (friendly, details)
                            render_error_card(friendly, details)
                    else:
                        friendly, details = format_error_details(
                            err or RuntimeError("Unexpected empty query result.")
                        )
                        st.session_state["last_result"] = None
                        st.session_state["last_trace"] = trace_dict
                        st.session_state["last_error"] = (friendly, details)
                        render_error_card(friendly, details)
                        events = list((trace_dict or {}).get("events") or [])
                        summary = (trace_dict or {}).get("summary")
                        if events or summary:
                            with st.container(key="musnad_results_area"):
                                with st.expander("كيف وصل النظام للإجابة؟", expanded=False):
                                    st.markdown(
                                        render_trace_panel_html(events, summary, in_progress=False),
                                        unsafe_allow_html=True,
                                    )
                else:
                    st.session_state["last_result"] = result
                    st.session_state["last_trace"] = trace_dict
                    st.session_state["session_query_count"] += 1
                    _render_result_with_trace(
                        result,
                        trace_dict,
                        replay_reason=None,
                    )
    elif st.session_state.get("last_error") is not None or st.session_state.get("last_result") is not None:
        last_err = st.session_state.get("last_error")
        if last_err is not None:
            friendly, details = last_err
            render_error_card(friendly, details)
        elif st.session_state.get("last_result") is not None:
            _render_result_with_trace(
                st.session_state["last_result"],
                st.session_state.get("last_trace"),
                replay_reason=st.session_state.get("last_replay_reason"),
            )

    # 7. Usage limits in a quiet small footer line
    render_footer(
        st.session_state.get("usage_status"),
        session_limit=config.session_limit,
        ip_hourly_limit=config.ip_hourly_limit,
        daily_cap=config.daily_cap,
        is_replay=is_replay and st.session_state.get("last_result") is None,
    )


if __name__ == "__main__":
    main()
