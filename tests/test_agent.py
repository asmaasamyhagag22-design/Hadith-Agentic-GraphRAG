"""Offline unit tests for Phase C agent tool-calling, C2 validators, C3 flag, and fallback."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import src.answer as ans
from src.agent import MAX_TOOL_CALLS, run_agent
from src.pipeline import resolve_agent_enabled
from src.sanad_names import NarratorLexicon


def _fake_fc(name: str, **args):
    return SimpleNamespace(name=name, args=args)


def _fake_resp(*, text: str = "", function_calls: list | None = None):
    return SimpleNamespace(
        text=text,
        function_calls=function_calls or [],
        candidates=[SimpleNamespace(content=SimpleNamespace(role="model", parts=[]))],
    )


def _create_fixture_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE local_hadith (
                local_id INTEGER PRIMARY KEY,
                id_in_book INTEGER,
                book_id INTEGER,
                chapter_id INTEGER,
                chapter_ar TEXT,
                chapter_en TEXT
            );
            CREATE TABLE mis_narrator (
                narrator_id TEXT PRIMARY KEY,
                label TEXT,
                name_ar TEXT,
                name_ar_mapped TEXT,
                name_en_mapped TEXT,
                gender TEXT,
                generation TEXT
            );
            CREATE TABLE mis_hadith (
                book_no INTEGER,
                hadith_no INTEGER,
                chapter_no INTEGER,
                unit_no INTEGER,
                declared_sanad_count INTEGER,
                PRIMARY KEY (book_no, hadith_no)
            );
            CREATE TABLE hadith_mis_link (
                local_id INTEGER PRIMARY KEY,
                id_in_book INTEGER,
                mis_book_no INTEGER,
                mis_hadith_no INTEGER,
                link_status TEXT,
                link_relation TEXT,
                linkage_version TEXT,
                linkage_artifact_sha256 TEXT,
                candidate_status TEXT,
                similarity REAL,
                quick_similarity REAL
            );
            CREATE TABLE isnad (
                book_no INTEGER,
                hadith_no INTEGER,
                sanad_no INTEGER,
                step_count INTEGER,
                narrator_count INTEGER,
                PRIMARY KEY (book_no, hadith_no, sanad_no)
            );
            CREATE TABLE transmission (
                book_no INTEGER,
                hadith_no INTEGER,
                sanad_no INTEGER,
                position INTEGER,
                from_narrator_id TEXT,
                to_narrator_id TEXT,
                source_label TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO local_hadith VALUES (12068, 1, 33, 1, 'كتاب الإمارة', 'Leadership')"
        )
        conn.execute(
            "INSERT INTO mis_narrator VALUES ('3', 'Umar', 'عمر بن الخطاب بن نفيل', 'عمر بن الخطاب بن نفيل', 'Umar', 'M', 'Comp')"
        )
        conn.execute(
            "INSERT INTO mis_narrator VALUES ('20164', 'Qanabi', 'عبد الله بن مسلمة بن قعنب القعنبى', 'عبد الله بن مسلمة بن قعنب القعنبي', 'Qanabi', 'M', '3rd')"
        )
        conn.execute(
            "INSERT INTO mis_narrator VALUES ('13', 'Abu Huraira', 'أبو هريرة الدوسى', 'أبو هريرة - عبد الرحمن بن صخر الدوسي', 'Abu Huraira', 'M', 'Comp')"
        )
        conn.execute("INSERT INTO mis_hadith VALUES (1, 10, 1, 1, 1)")
        conn.execute(
            "INSERT INTO hadith_mis_link VALUES (12068, 1, 1, 10, 'ACCEPTED_LINK_V1', 'exact', 'v1', 'abc', 'ok', 1.0, 1.0)"
        )
        conn.execute("INSERT INTO isnad VALUES (1, 10, 1, 1, 2)")
        conn.execute("INSERT INTO transmission VALUES (1, 10, 1, 1, '3', '20164', 'src')")
        conn.commit()
    finally:
        conn.close()


SAMPLE_LEX = NarratorLexicon.from_records(
    [
        {"narrator_id": "3", "name_ar": "عمر بن الخطاب بن نفيل", "name_ar_mapped": "عمر بن الخطاب بن نفيل"},
        {"narrator_id": "20164", "name_ar": "عبد الله بن مسلمة بن قعنب القعنبى", "name_ar_mapped": "عبد الله بن مسلمة بن قعنب القعنبي"},
        {"narrator_id": "13", "name_ar": "أبو هريرة الدوسى", "name_ar_mapped": "أبو هريرة - عبد الرحمن بن صخر الدوسي"},
    ]
)


class _DummyRetriever:
    def search(self, query: str, k: int = 5):
        return [
            {
                "hadith_id": 12068,
                "text": "حدثنا القعنبي قال إنما الأعمال بالنية",
                "matn": "إنما الأعمال بالنية",
                "metadata": {"chapter_arabic": "كتاب الإمارة"},
            }
        ]


class AgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "sanad.sqlite"
        _create_fixture_db(self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_routing_to_search_hadith_and_sanad_attachment(self) -> None:
        turns = [
            _fake_resp(function_calls=[_fake_fc("search_hadith", query="الأعمال بالنية")]),
            _fake_resp(text="الأعمال تُحسب بالنيات (المصدر: صحيح مسلم، حديث رقم 12068)."),
        ]
        seen_allow_tools: list[bool] = []

        def fake_gen(_contents, *, allow_tools: bool):
            seen_allow_tools.append(allow_tools)
            return turns.pop(0)

        res = run_agent(
            "ما الحديث الذي يربط قبول الأعمال بالنية؟",
            _DummyRetriever(),
            sanad_db_path=self.db_path,
            generate_fn=fake_gen,
            lexicon=SAMPLE_LEX,
        )
        self.assertEqual([t["name"] for t in res["tool_calls"]], ["search_hadith"])
        self.assertEqual(seen_allow_tools, [True, True])
        self.assertFalse(res["regenerated"])
        self.assertEqual(len(res["sanad"]), 1)
        self.assertEqual(res["sanad"][0]["hadith_id"], 12068)
        self.assertEqual(
            [n["name_ar_mapped"] for n in res["sanad"][0]["isnads"][0]],
            ["عمر بن الخطاب بن نفيل", "عبد الله بن مسلمة بن قعنب القعنبي"],
        )

    def test_routing_to_get_isnad_only_and_topic_two_step(self) -> None:
        # 1) Named hadith ID -> get_isnad only
        turns_direct = [
            _fake_resp(function_calls=[_fake_fc("get_isnad", hadith_id=12068)]),
            _fake_resp(text="الصحابي الذي روى الحديث هو عمر بن الخطاب بن نفيل (المصدر: صحيح مسلم، حديث رقم 12068)."),
        ]
        res_direct = run_agent(
            "من الصحابي الذي روى حديث رقم 12068؟",
            _DummyRetriever(),
            sanad_db_path=self.db_path,
            generate_fn=lambda _c, *, allow_tools: turns_direct.pop(0),
            lexicon=SAMPLE_LEX,
        )
        self.assertEqual([t["name"] for t in res_direct["tool_calls"]], ["get_isnad"])
        self.assertFalse(res_direct["regenerated"])
        self.assertEqual(res_direct["sanad"][0]["hadith_id"], 12068)

        # 2) Topic chain question -> search_hadith then get_isnad
        turns_two = [
            _fake_resp(function_calls=[_fake_fc("search_hadith", query="إنما الأعمال بالنية")]),
            _fake_resp(function_calls=[_fake_fc("get_isnad", hadith_id=12068)]),
            _fake_resp(text="رواه عمر بن الخطاب بن نفيل (المصدر: صحيح مسلم، حديث رقم 12068)."),
        ]
        res_two = run_agent(
            "من روى حديث إنما الأعمال بالنية؟",
            _DummyRetriever(),
            sanad_db_path=self.db_path,
            generate_fn=lambda _c, *, allow_tools: turns_two.pop(0),
            lexicon=SAMPLE_LEX,
        )
        self.assertEqual([t["name"] for t in res_two["tool_calls"]], ["search_hadith", "get_isnad"])
        self.assertFalse(res_two["regenerated"])

    def test_tool_call_loop_limit_max_3(self) -> None:
        calls: list[bool] = []
        search_count = 0

        def counting_search(query: str, k: int):
            nonlocal search_count
            search_count += 1
            return [
                {
                    "hadith_id": 12068,
                    "matn": "إنما الأعمال بالنية",
                    "metadata": {"chapter_arabic": "كتاب الإمارة"},
                }
            ]

        def greedy_gen(_contents, *, allow_tools: bool):
            calls.append(allow_tools)
            if allow_tools:
                # Try 2 parallel calls per step -> total requested exceeds MAX_TOOL_CALLS (3).
                return _fake_resp(
                    function_calls=[
                        _fake_fc("search_hadith", query="نية"),
                        _fake_fc("search_hadith", query="أعمال"),
                    ]
                )
            return _fake_resp(text="خلاصة المتن (المصدر: صحيح مسلم، حديث رقم 12068).")

        res = run_agent(
            "سؤال عام",
            _DummyRetriever(),
            sanad_db_path=self.db_path,
            generate_fn=greedy_gen,
            search_fn=counting_search,
            lexicon=SAMPLE_LEX,
        )
        self.assertEqual(len(res["tool_calls"]), MAX_TOOL_CALLS)
        self.assertEqual(search_count, MAX_TOOL_CALLS)
        self.assertEqual(calls, [True, True, False])

    def test_id_subset_validation_regenerate_and_refuse(self) -> None:
        # Direct extended validate_answer check
        self.assertEqual(
            ans.validate_answer("(المصدر: صحيح مسلم، حديث رقم 9999)", {12068, 9999}, tool_ids={12068}),
            ans.OUT_OF_CONTEXT_CITATION,
        )
        self.assertEqual(
            ans.validate_answer("(المصدر: صحيح مسلم، حديث رقم 12068)", {12068}, tool_ids={12068}),
            ans.VALID_ANSWER,
        )

        # Regenerate succeeds on second attempt
        turns_fix = [
            _fake_resp(function_calls=[_fake_fc("search_hadith", query="نية")]),
            _fake_resp(text="الجواب (المصدر: صحيح مسلم، حديث رقم 9999)."),
            _fake_resp(text="الجواب (المصدر: صحيح مسلم، حديث رقم 12068)."),
        ]
        res_fix = run_agent(
            "ما حديث النية؟",
            _DummyRetriever(),
            sanad_db_path=self.db_path,
            generate_fn=lambda _c, *, allow_tools: turns_fix.pop(0),
            lexicon=SAMPLE_LEX,
        )
        self.assertTrue(res_fix["regenerated"])
        self.assertTrue(res_fix["invalid_citation_attempt"])
        self.assertIn("12068", res_fix["answer"])
        self.assertEqual(res_fix["sanad"][0]["hadith_id"], 12068)

        # Still invalid after 1 regeneration -> hard refusal
        turns_fail = [
            _fake_resp(function_calls=[_fake_fc("search_hadith", query="نية")]),
            _fake_resp(text="الجواب (المصدر: صحيح مسلم، حديث رقم 9999)."),
            _fake_resp(text="الجواب (المصدر: صحيح مسلم، حديث رقم 8888)."),
        ]
        res_fail = run_agent(
            "ما حديث النية؟",
            _DummyRetriever(),
            sanad_db_path=self.db_path,
            generate_fn=lambda _c, *, allow_tools: turns_fail.pop(0),
            lexicon=SAMPLE_LEX,
        )
        self.assertTrue(res_fail["regenerated"])
        self.assertEqual(res_fail["answer"], ans.REFUSAL)
        self.assertEqual(res_fail["sanad"], [])

    def test_narrator_name_validation_regenerate_and_refuse(self) -> None:
        # Bad narrator mentioned when get_isnad returned only Umar & Qanabi -> regenerate fixes it
        turns_fix = [
            _fake_resp(function_calls=[_fake_fc("get_isnad", hadith_id=12068)]),
            _fake_resp(text="رواه أبو هريرة (المصدر: صحيح مسلم، حديث رقم 12068)."),
            _fake_resp(text="رواه عمر بن الخطاب بن نفيل (المصدر: صحيح مسلم، حديث رقم 12068)."),
        ]
        res_fix = run_agent(
            "من روى حديث 12068؟",
            _DummyRetriever(),
            sanad_db_path=self.db_path,
            generate_fn=lambda _c, *, allow_tools: turns_fix.pop(0),
            lexicon=SAMPLE_LEX,
        )
        self.assertTrue(res_fix["regenerated"])
        self.assertEqual(res_fix["disallowed_narrators_attempt"], ["ابو هريرة"])
        self.assertIn("عمر بن الخطاب", res_fix["answer"])

        # Bad narrator mentioned WITHOUT calling get_isnad -> regenerate still mentions it -> refuse
        turns_refuse = [
            _fake_resp(function_calls=[_fake_fc("search_hadith", query="نية")]),
            _fake_resp(text="رواه عمر بن الخطاب بن نفيل (المصدر: صحيح مسلم، حديث رقم 12068)."),
            _fake_resp(text="رواه أبو هريرة (المصدر: صحيح مسلم، حديث رقم 12068)."),
        ]
        res_refuse = run_agent(
            "من روى حديث 12068؟",
            _DummyRetriever(),
            sanad_db_path=self.db_path,
            generate_fn=lambda _c, *, allow_tools: turns_refuse.pop(0),
            lexicon=SAMPLE_LEX,
        )
        self.assertTrue(res_refuse["regenerated"])
        self.assertEqual(res_refuse["answer"], ans.REFUSAL)
        self.assertEqual(res_refuse["sanad"], [])

    def test_fallback_on_tool_failure_and_timeout(self) -> None:
        fallback_payload = {
            "answer": "إجابة احتياطية (المصدر: صحيح مسلم، حديث رقم 12068)",
            "raw": "إجابة احتياطية (المصدر: صحيح مسلم، حديث رقم 12068)",
            "chunks": [{"hadith_id": 12068}],
            "sanad": [],
            "sanad_error": None,
            "invalid_citation_attempt": False,
            "missing_citation_attempt": False,
            "loose_out_of_context_attempt": False,
            "mixed_refusal_attempt": False,
            "regenerated": False,
            "rewritten": None,
            "retried": False,
        }

        def failing_search(_q: str, _k: int):
            raise RuntimeError("search service unavailable")

        turns_err = [_fake_resp(function_calls=[_fake_fc("search_hadith", query="نية")])]
        res_err = run_agent(
            "سؤال",
            _DummyRetriever(),
            sanad_db_path=self.db_path,
            generate_fn=lambda _c, *, allow_tools: turns_err.pop(0),
            search_fn=failing_search,
            lexicon=SAMPLE_LEX,
            fallback_fn=lambda: fallback_payload,
        )
        self.assertTrue(res_err["agent_fallback"])
        self.assertIn("RuntimeError", res_err["fallback_reason"])
        self.assertEqual(res_err["answer"], fallback_payload["answer"])

        def slow_isnad(_hid: int):
            time.sleep(0.25)
            return {}

        turns_to = [_fake_resp(function_calls=[_fake_fc("get_isnad", hadith_id=12068)])]
        res_to = run_agent(
            "من روى 12068؟",
            _DummyRetriever(),
            sanad_db_path=self.db_path,
            tool_timeout_s=0.05,
            generate_fn=lambda _c, *, allow_tools: turns_to.pop(0),
            isnad_fn=slow_isnad,
            lexicon=SAMPLE_LEX,
            fallback_fn=lambda: fallback_payload,
        )
        self.assertTrue(res_to["agent_fallback"])
        self.assertIn("TimeoutError", res_to["fallback_reason"])

    def test_feature_flag_and_answer_with_details_routing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(resolve_agent_enabled())
        with patch.dict(os.environ, {"MUSNAD_AGENT": "on"}):
            self.assertTrue(resolve_agent_enabled())
        with patch.dict(os.environ, {"MUSNAD_AGENT": "off"}):
            self.assertFalse(resolve_agent_enabled())
        with self.assertRaises(ValueError):
            resolve_agent_enabled("maybe")

        dummy_agent_result = {
            "answer": "إجابة وكيل (المصدر: صحيح مسلم، حديث رقم 12068)",
            "raw": "إجابة وكيل (المصدر: صحيح مسلم، حديث رقم 12068)",
            "chunks": [{"hadith_id": 12068}],
            "sanad": [],
            "sanad_error": None,
            "invalid_citation_attempt": False,
            "missing_citation_attempt": False,
            "loose_out_of_context_attempt": False,
            "mixed_refusal_attempt": False,
            "regenerated": False,
            "rewritten": None,
            "retried": False,
        }
        with patch.dict(os.environ, {"MUSNAD_AGENT": "on"}):
            with patch("src.agent.run_agent", return_value=dummy_agent_result) as mock_agent:
                out = ans.answer_with_details("سؤال؟", _DummyRetriever())
                mock_agent.assert_called_once()
                self.assertEqual(out["answer"], dummy_agent_result["answer"])

                # C3: answer_eval and smoke_test also go through the same answer_with_details entry point
                import src.answer_eval as answer_eval
                import src.smoke_test as smoke_test

                counter = answer_eval.evaluate_answers(
                    _DummyRetriever(),
                    [{"question": "سؤال؟", "hadith_ids": [12068], "answerable": True}],
                )
                self.assertEqual(len(counter.rows), 1)
                self.assertEqual(mock_agent.call_count, 2)

                st_answer = smoke_test.step_answer(_DummyRetriever())
                self.assertEqual(st_answer, dummy_agent_result["answer"])
                self.assertEqual(mock_agent.call_count, 3)


if __name__ == "__main__":
    unittest.main()
