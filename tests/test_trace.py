"""Tests for observational execution tracing across router, retrieval, agent, generation, validation, and sanad."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest
from google.genai import types

import src.answer as answer_mod
from src.answer import REFUSAL, answer_with_details
from src.build_sanad_graph import DDL, LINK_RELATION, LINK_STATUS, LOCAL_DDL
from src.pipeline import resolve_agent_enabled
from src.trace import TraceCollector


def _build_temp_sanad_db(db_path: Path) -> Path:
    """Create a minimal valid MIS sanad SQLite database for deterministic tests."""
    conn = sqlite3.connect(db_path)
    conn.executescript(DDL)
    conn.executescript(LOCAL_DDL)
    conn.executemany(
        """
        INSERT INTO mis_narrator (
            narrator_id, label, name_ar, name_ar_mapped, name_en_mapped, gender, generation
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("N1", "أبو هريرة", "أبو هريرة", "أبو هريرة", "Abu Huraira", "M", "Companion"),
            ("N2", "قتيبة بن سعيد", "قتيبة بن سعيد", "قتيبة بن سعيد", "Qutaiba", "M", "Teacher"),
        ],
    )
    conn.execute(
        """
        INSERT INTO mis_hadith (
            book_no, hadith_no, chapter_no, unit_no, book_title,
            chapter_title_ar, chapter_title_en, unit_title_ar,
            declared_sanad_count, declared_sanad_narrators
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("1", "1", "1", "1", "الإيمان", "باب الإيمان", "Faith", "الإيمان", 1, "أبو هريرة -> قتيبة بن سعيد"),
    )
    conn.execute(
        """
        INSERT INTO isnad (book_no, hadith_no, sanad_no, step_count, narrator_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("1", "1", "1", 1, 2),
    )
    conn.execute(
        """
        INSERT INTO transmission (
            book_no, hadith_no, sanad_no, position, from_narrator_id, to_narrator_id, source_label
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("1", "1", "1", 1, "N1", "N2", "B1-H0001-C01-U01-S01-i1"),
    )
    conn.execute(
        """
        INSERT INTO local_hadith (local_id, id_in_book, book_id, chapter_id, chapter_ar, chapter_en)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, 1, 1, 1, "باب الإيمان", "Faith"),
    )
    conn.execute(
        """
        INSERT INTO hadith_mis_link (
            local_id, id_in_book, mis_book_no, mis_hadith_no,
            link_status, link_relation, linkage_version, linkage_artifact_sha256,
            candidate_status, similarity, quick_similarity
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, 1, "1", "1", LINK_STATUS, LINK_RELATION, "mis_linkage_accepted_v1", "0" * 64, "accepted", 1.0, 1.0),
    )
    conn.commit()
    conn.close()
    return db_path


class _DummyRetriever:
    """Minimal retriever compatible with UpgradedRetriever trace metadata."""

    def __init__(
        self,
        *,
        chunks: list[dict] | None = None,
        hyde_text: str | None = "حديث عن الإيمان والنية.",
        used_fallback: bool = False,
        call_stats: dict | None = None,
        query_vec_cache: dict | None = None,
        agent_mode: str = "auto",
    ):
        self.chunks = (
            [
                {
                    "rank": 1,
                    "hadith_id": 1,
                    "text": "حدثنا قتيبة عن أبي هريرة: حديث تجريبي رقم 1",
                    "matn": "حديث تجريبي رقم 1",
                    "metadata": {"chapter_arabic": "باب الإيمان"},
                },
                {
                    "rank": 2,
                    "hadith_id": 2,
                    "text": "حدثنا محمد: حديث تجريبي رقم 2",
                    "matn": "حديث تجريبي رقم 2",
                    "metadata": {"chapter_arabic": "باب الصلاة"},
                },
            ]
            if chunks is None
            else chunks
        )
        self.hyde_text = hyde_text
        self.used_fallback = used_fallback
        self.call_stats = (
            {"flash_calls": 1, "embed_calls": 2} if call_stats is None else call_stats
        )
        self.query_vec_cache = query_vec_cache if query_vec_cache is not None else {}
        self.agent_mode = agent_mode
        self.last_hyde_text = None
        self.last_used_fallback = False
        self.last_call_stats = None

    def get_query_embedding(self, query: str):
        return self.query_vec_cache.get(query)

    def search(self, query: str, k: int = 5):
        self.last_hyde_text = self.hyde_text
        self.last_used_fallback = self.used_fallback
        self.last_call_stats = dict(self.call_stats)
        return list(self.chunks[:k])


def _fn_call_response(name: str, args: dict):
    fc = types.FunctionCall(name=name, args=args)
    content = types.Content(role="model", parts=[types.Part(function_call=fc)])
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=content)]
    )


def _text_response(text: str):
    content = types.Content(role="model", parts=[types.Part.from_text(text=text)])
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=content)]
    )


def test_identical_outputs_with_and_without_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Tracing must be purely observational on both text and agent paths."""
    db_path = _build_temp_sanad_db(tmp_path / "sanad.sqlite")
    retriever = _DummyRetriever()

    # 1) Text path
    monkeypatch.setattr(
        answer_mod,
        "generate",
        lambda *args, **kwargs: "الإجابة النصية الموثقة (المصدر: صحيح مسلم، حديث رقم 1).",
    )
    without_text = answer_with_details(
        "ما معنى هذا الحديث؟",
        retriever,
        use_agent=False,
        sanad_db_path=db_path,
    )
    text_trace = TraceCollector()
    with_text = answer_with_details(
        "ما معنى هذا الحديث؟",
        retriever,
        use_agent=False,
        sanad_db_path=db_path,
        trace=text_trace,
    )
    assert with_text == without_text

    # 2) Chain / agent path
    def _mock_agent(question, ret, **kwargs):
        calls = 0

        def _gen(contents, *, allow_tools):
            nonlocal calls
            calls += 1
            if calls == 1:
                return _fn_call_response("get_isnad", {"hadith_id": 1})
            return _text_response(
                "روى الحديث قتيبة بن سعيد عن أبو هريرة (المصدر: صحيح مسلم، حديث رقم 1)."
            )

        from src.agent import run_agent

        return run_agent(
            question,
            ret,
            sanad_db_path=kwargs["sanad_db_path"],
            fallback_fn=kwargs["fallback_fn"],
            generate_fn=_gen,
            trace=kwargs.get("trace"),
        )

    monkeypatch.setattr(answer_mod, "_call_agent", _mock_agent)
    without_chain = answer_with_details(
        "من روى حديث رقم 1؟",
        retriever,
        use_agent=True,
        sanad_db_path=db_path,
    )
    chain_trace = TraceCollector()
    with_chain = answer_with_details(
        "من روى حديث رقم 1؟",
        retriever,
        use_agent=True,
        sanad_db_path=db_path,
        trace=chain_trace,
    )
    assert with_chain == without_chain


def test_text_path_event_sequence_and_router_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Text path emits router -> retrieval -> generation -> validation -> sanad with required fields."""
    db_path = _build_temp_sanad_db(tmp_path / "sanad.sqlite")
    q = "ما حكم إخلاص النية في العبادة؟"
    # Populate query_vec_cache with unit vector matching default embedding dim in router_weights.npz
    from src.router import load_router_weights

    weights = load_router_weights()
    assert weights is not None
    w = weights["weights"]
    dummy_vec = (-w / max(float(np.linalg.norm(w)), 1e-8)).astype(np.float32)
    retriever = _DummyRetriever(query_vec_cache={q: dummy_vec})

    monkeypatch.setattr(
        answer_mod,
        "generate",
        lambda *args, **kwargs: "النية شرط في قبول العمل (المصدر: صحيح مسلم، حديث رقم 1).",
    )

    trace = TraceCollector()
    details = answer_with_details(q, retriever, sanad_db_path=db_path, trace=trace)
    assert details["sanad"] and details["sanad"][0]["hadith_id"] == 1
    assert trace.stages() == ["router", "retrieval", "generation", "validation", "sanad"]

    for ev in trace.events:
        assert isinstance(ev.timestamp, float) and ev.timestamp > 0
        assert ev.duration_ms >= 0.0

    router_ev, ret_ev, gen_ev, val_ev, sanad_ev = trace.events
    assert router_ev.data["decision"] == "text"
    assert router_ev.data["source"] == "classifier"
    assert isinstance(router_ev.data["probability"], float)

    assert ret_ev.data["hyde_text"] == "حديث عن الإيمان والنية."
    assert ret_ev.data["legacy_fallback"] is False
    assert ret_ev.data["top5"] == [
        {"rank": 1, "hadith_id": 1, "chapter": "باب الإيمان"},
        {"rank": 2, "hadith_id": 2, "chapter": "باب الصلاة"},
    ]

    assert gen_ev.data["model"] == answer_mod.MODEL
    assert gen_ev.data["attempts"] == 1
    assert val_ev.data["status"] == "valid_answer"
    assert val_ev.data["retry_reason"] is None
    assert val_ev.data["refusal_reason"] is None

    assert sanad_ev.data["hadith_id"] == 1
    assert sanad_ev.data["status"] == "LINKED_WITH_RECORDED_ISNAD"
    assert sanad_ev.data["isnad_count"] == 1
    assert sanad_ev.data["ms"] >= 0.0

    summary = trace.summary()
    assert summary["call_counts"]["pro_calls"] == 1
    assert summary["call_counts"]["flash_calls"] == 1
    assert summary["call_counts"]["embed_calls"] == 2
    assert summary["call_counts"]["sqlite_queries"] == 1

    # Also verify regex and v2 fallback sources from router
    t_regex = TraceCollector()
    assert resolve_agent_enabled("auto", question="من روى حديث رقم 1؟", retriever=retriever, trace=t_regex) is True
    assert t_regex.events[0].data["source"] == "regex"
    assert t_regex.events[0].data["decision"] == "chain"

    t_v2 = TraceCollector()
    no_embed_retriever = _DummyRetriever(query_vec_cache={})
    assert resolve_agent_enabled("auto", question="سؤال بدون متجه", retriever=no_embed_retriever, trace=t_v2) is False
    assert t_v2.events[0].data["source"] == "v2 fallback"


def test_chain_path_direct_and_topic_event_sequences(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Chain path records direct get_isnad or search_hadith + get_isnad tool calls cleanly."""
    db_path = _build_temp_sanad_db(tmp_path / "sanad.sqlite")
    retriever = _DummyRetriever()

    # 1) Direct ID chain (router regex -> get_isnad -> generation -> validation -> sanad)
    def _direct_agent(question, ret, **kwargs):
        step = 0

        def _gen(contents, *, allow_tools):
            nonlocal step
            step += 1
            if step == 1:
                return _fn_call_response("get_isnad", {"hadith_id": 1})
            return _text_response(
                "روى الحديث قتيبة بن سعيد عن أبو هريرة (المصدر: صحيح مسلم، حديث رقم 1)."
            )

        from src.agent import run_agent

        return run_agent(
            question,
            ret,
            sanad_db_path=kwargs["sanad_db_path"],
            fallback_fn=kwargs["fallback_fn"],
            generate_fn=_gen,
            trace=kwargs.get("trace"),
        )

    monkeypatch.setattr(answer_mod, "_call_agent", _direct_agent)
    t_direct = TraceCollector()
    answer_with_details("من روى حديث رقم 1؟", retriever, sanad_db_path=db_path, trace=t_direct)
    assert t_direct.stages() == ["router", "agent", "generation", "validation", "sanad"]
    assert t_direct.events[0].data["source"] == "regex"
    assert t_direct.events[0].data["decision"] == "chain"
    assert t_direct.events[1].data["name"] == "get_isnad"
    assert t_direct.events[1].data["arguments"] == {"hadith_id": 1}
    assert t_direct.events[1].data["returned_ids"] == [1]
    assert t_direct.events[1].data["agent_fallback"] is False
    assert t_direct.events[1].data["source"] == "SQLite sanad graph"

    # 2) Topic chain (search_hadith -> retrieval + agent -> get_isnad -> generation -> validation -> sanad)
    def _topic_agent(question, ret, **kwargs):
        step = 0

        def _gen(contents, *, allow_tools):
            nonlocal step
            step += 1
            if step == 1:
                return _fn_call_response("search_hadith", {"query": "الإيمان"})
            if step == 2:
                return _fn_call_response("get_isnad", {"hadith_id": 1})
            return _text_response(
                "إسناد الحديث: قتيبة بن سعيد عن أبو هريرة (المصدر: صحيح مسلم، حديث رقم 1)."
            )

        from src.agent import run_agent

        return run_agent(
            question,
            ret,
            sanad_db_path=kwargs["sanad_db_path"],
            fallback_fn=kwargs["fallback_fn"],
            generate_fn=_gen,
            trace=kwargs.get("trace"),
        )

    monkeypatch.setattr(answer_mod, "_call_agent", _topic_agent)
    t_topic = TraceCollector()
    answer_with_details(
        "من روى حديث الإيمان؟", retriever, use_agent=True, sanad_db_path=db_path, trace=t_topic
    )
    assert t_topic.stages() == [
        "router",
        "retrieval",
        "agent",
        "agent",
        "generation",
        "validation",
        "sanad",
    ]
    assert t_topic.events[2].data["name"] == "search_hadith"
    assert t_topic.events[2].data["returned_ids"] == [1, 2]
    assert t_topic.events[3].data["name"] == "get_isnad"
    assert t_topic.events[3].data["returned_ids"] == [1]
    summary = t_topic.summary()
    assert summary["call_counts"]["tool_calls"] == 2
    assert summary["call_counts"]["pro_calls"] == 3
    assert summary["call_counts"]["sqlite_queries"] == 2


def test_refusal_and_retry_event_sequences(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Refusal paths (empty retrieval, model refusal, failed retry) record exact reasons without sanad."""
    db_path = _build_temp_sanad_db(tmp_path / "sanad.sqlite")

    # 1) Empty retrieval refusal
    empty_ret = _DummyRetriever(chunks=[])
    t_empty = TraceCollector()
    res_empty = answer_with_details(
        "سؤال خارج الصحيح", empty_ret, use_agent=False, sanad_db_path=db_path, trace=t_empty
    )
    assert res_empty["answer"] == REFUSAL
    assert t_empty.stages() == ["router", "retrieval", "validation"]
    assert t_empty.events[-1].data["status"] == "valid_refusal"
    assert t_empty.events[-1].data["refusal_reason"] == "empty_retrieval"

    # 2) Model refuses directly
    ret = _DummyRetriever()
    monkeypatch.setattr(answer_mod, "generate", lambda *args, **kwargs: REFUSAL)
    t_ref = TraceCollector()
    res_ref = answer_with_details(
        "ما حكم التشفير الكمي؟", ret, use_agent=False, sanad_db_path=db_path, trace=t_ref
    )
    assert res_ref["answer"] == REFUSAL
    assert t_ref.stages() == ["router", "retrieval", "generation", "validation"]
    assert t_ref.events[-1].data["status"] == "valid_refusal"
    assert t_ref.events[-1].data["refusal_reason"] == "model_refused"
    assert t_ref.events[-1].data["retry_reason"] is None

    # 3) Missing citation -> single retry -> still invalid -> forced refusal
    monkeypatch.setattr(
        answer_mod, "generate", lambda *args, **kwargs: "إجابة بدون أي رقم حديث."
    )
    t_retry = TraceCollector()
    res_retry = answer_with_details(
        "ما معنى الحديث؟", ret, use_agent=False, sanad_db_path=db_path, trace=t_retry
    )
    assert res_retry["answer"] == REFUSAL
    assert t_retry.stages() == ["router", "retrieval", "generation", "validation"]
    assert t_retry.events[2].data["attempts"] == 2
    assert t_retry.events[3].data["status"] == "valid_refusal"
    assert t_retry.events[3].data["retry_reason"] == "missing_citation"
    assert t_retry.events[3].data["refusal_reason"] == "validation_failed_after_retry"


def test_fallbacks_live_callback_and_serialization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Legacy retrieval fallback, agent fallback, live on_event callback, and JSON round-trip."""
    db_path = _build_temp_sanad_db(tmp_path / "sanad.sqlite")

    # 1) Legacy fallback flag on retrieval
    fb_ret = _DummyRetriever(used_fallback=True, call_stats={"flash_calls": 0, "embed_calls": 0})
    monkeypatch.setattr(
        answer_mod,
        "generate",
        lambda *args, **kwargs: "جواب نصي (المصدر: صحيح مسلم، حديث رقم 1).",
    )
    t_legacy = TraceCollector()
    answer_with_details("سؤال", fb_ret, use_agent=False, sanad_db_path=db_path, trace=t_legacy)
    assert t_legacy.events[1].data["legacy_fallback"] is True

    # 2) Agent fallback -> records agent(agent_fallback=True) then falls back without duplicate router
    def _failing_agent(question, ret, **kwargs):
        from src.agent import run_agent

        def _boom(contents, *, allow_tools):
            raise RuntimeError("simulated agent timeout")

        return run_agent(
            question,
            ret,
            sanad_db_path=kwargs["sanad_db_path"],
            fallback_fn=kwargs["fallback_fn"],
            generate_fn=_boom,
            trace=kwargs.get("trace"),
        )

    monkeypatch.setattr(answer_mod, "_call_agent", _failing_agent)
    streamed: list[str] = []
    t_agent_fb = TraceCollector(on_event=lambda ev: streamed.append(ev.stage))
    res = answer_with_details(
        "من روى حديث رقم 1؟",
        _DummyRetriever(),
        sanad_db_path=db_path,
        trace=t_agent_fb,
    )
    assert res["agent_fallback"] is True
    expected_stages = ["router", "agent", "retrieval", "generation", "validation", "sanad"]
    assert streamed == expected_stages
    assert t_agent_fb.stages() == expected_stages
    assert t_agent_fb.events[1].data["agent_fallback"] is True
    assert "RuntimeError: simulated agent timeout" in t_agent_fb.events[1].data["fallback_reason"]

    # 3) Round-trip serialization
    t_agent_fb.finish()
    payload = t_agent_fb.to_dict()
    restored = TraceCollector.from_dict(payload)
    assert restored.stages() == expected_stages
    assert restored.summary()["call_counts"] == t_agent_fb.summary()["call_counts"]
    assert restored.events[1].data["agent_fallback"] is True
