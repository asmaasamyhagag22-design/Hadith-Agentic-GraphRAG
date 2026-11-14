"""Offline unit tests for deterministic Arabic routing and auto|on|off composition."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import src.answer as ans
from src.pipeline import resolve_agent_enabled, resolve_agent_mode
from src.router import classify_intent, matched_chain_rule


class _TextPipelineDummy:
    agent_mode = "auto"
    agent_enabled = False

    def search(self, query: str, k: int = 5):
        return [
            {
                "hadith_id": 8950,
                "rank": 1,
                "text": "حدثنا زيد قال رسول الله صلى الله عليه وسلم نص تجريبي",
                "matn": "نص تجريبي في صحيح مسلم",
                "metadata": {"chapter_arabic": "كتاب الإيمان"},
            }
        ]


def _create_sanad_fixture(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
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
        conn.execute("INSERT INTO local_hadith VALUES (8950, 1, 1, 1, 'كتاب الإيمان', 'Faith')")
        conn.execute(
            "INSERT INTO mis_narrator VALUES ('13', 'Abu Huraira', 'أبو هريرة الدوسي', 'أبو هريرة الدوسي', 'Abu Huraira', 'M', 'Comp')"
        )
        conn.execute(
            "INSERT INTO mis_narrator VALUES ('30022', 'Zuhayr', 'زهير بن حرب', 'زهير بن حرب', 'Zuhayr', 'M', '3rd')"
        )
        conn.execute("INSERT INTO mis_hadith VALUES (1, 10, 1, 1, 1)")
        conn.execute(
            "INSERT INTO hadith_mis_link VALUES (8950, 1, 1, 10, 'ACCEPTED_LINK_V1', 'exact', 'v1', 'abc', 'ok', 1.0, 1.0)"
        )
        conn.execute("INSERT INTO isnad VALUES (1, 10, 1, 1, 2)")
        conn.execute("INSERT INTO transmission VALUES (1, 10, 1, 1, '13', '30022', 'src')")
        conn.commit()
    finally:
        conn.close()


class RouterClassifierTests(unittest.TestCase):
    def test_chain_questions_with_or_without_id(self) -> None:
        chain_prompts = [
            "من الصحابي الذي روى حديث رقم 5120؟",
            "من الصحابية التي روت هذا الحديث عن النبي؟",
            "من هو شيخ الإمام مسلم في الحديث رقم 6011؟",
            "عمّن أخذ الإمام مسلم الحديث رقم 7100؟",
            "من الراوي المباشر لمسلم في حديث رقم 8400؟",
            "كم عدد الأسانيد المسجلة للحديث رقم 6500؟",
            "كم طريقًا ورد بها إسناد الحديث رقم 9102؟",
            "هل ورد اسم الزهري في سند الحديث رقم 7001؟",
            "هل شارك مالك بن أنس في رواية الحديث رقم 8002؟",
            "هل يظهر قتادة ضمن رواة حديث رقم 8300؟",
            "من روى حديث بني الإسلام على خمس في صحيح مسلم؟",
            "من هو الصحابي راوي حديث الدين المعاملة؟",
            "اذكر رواة الحديث رقم 9015 وحكم رواته.",
            "ما سلسلة إسناد حديث بدء الوحي؟",
        ]
        for q in chain_prompts:
            with self.subTest(q=q):
                self.assertEqual(classify_intent(q), "chain", f"Missed rule: {q}")
                self.assertIsNotNone(matched_chain_rule(q))

    def test_general_arabic_text_questions_stay_text(self) -> None:
        text_prompts = [
            "ما حكم الوضوء بعد أكل لحم الإبل؟",
            "كم عدد ركعات صلاة الضحى؟",
            "من هو المفلس يوم القيامة كما بيّن النبي؟",
            "ماذا حدث عندما فتح المسلمون مكة؟",
            "هل ورد في الحديث النهي عن الغضب؟",
            "ما فضل ذكر الله كما روي في صحيح مسلم؟",
            "من الصحابي الذي سأل النبي عن علامات الساعة في القصة؟",
            "كيف يؤدي المسلم صلاة الاستسقاء؟",
            "ما عقوبة الغش في البيع والمعاملات؟",
        ]
        for q in text_prompts:
            with self.subTest(q=q):
                self.assertEqual(classify_intent(q), "text", f"False trigger rule={matched_chain_rule(q)}: {q}")


class AgentModeCompositionTests(unittest.TestCase):
    def test_resolve_agent_mode_supports_auto_on_off(self) -> None:
        self.assertEqual(resolve_agent_mode("auto"), "auto")
        self.assertEqual(resolve_agent_mode("ON"), "on")
        self.assertEqual(resolve_agent_mode("off"), "off")
        self.assertEqual(resolve_agent_mode(True), "on")
        self.assertEqual(resolve_agent_mode(False), "off")
        with self.assertRaises(ValueError):
            resolve_agent_mode("invalid")

        self.assertTrue(resolve_agent_enabled("auto", question="كم عدد الأسانيد للحديث رقم 5120؟"))
        self.assertFalse(resolve_agent_enabled("auto", question="ما حكم الصيام يوم الاثنين؟"))
        self.assertFalse(resolve_agent_enabled("auto"))

    def test_auto_mode_dispatches_text_to_rag_with_sanad_and_chain_to_agent(self) -> None:
        retriever = _TextPipelineDummy()
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sanad.sqlite"
            _create_sanad_fixture(db_path)

            text_reply = "الحكم مذكور في الحديث (المصدر: صحيح مسلم، حديث رقم 8950)"
            fake_agent_out = {
                "answer": "روى الحديث أبو هريرة (المصدر: صحيح مسلم، حديث رقم 8950)",
                "raw": "روى الحديث أبو هريرة (المصدر: صحيح مسلم، حديث رقم 8950)",
                "chunks": [{"hadith_id": 8950}],
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

            with patch.dict(os.environ, {"MUSNAD_AGENT": "auto"}):
                with (
                    patch("src.answer.generate", return_value=text_reply) as mock_gen,
                    patch("src.agent.run_agent", return_value=fake_agent_out) as mock_agent,
                ):
                    text_out = ans.answer_with_details(
                        "ما فضل الصدقة في صحيح مسلم؟",
                        retriever,
                        sanad_db_path=db_path,
                    )
                    self.assertEqual(mock_gen.call_count, 1)
                    self.assertEqual(mock_agent.call_count, 0)
                    self.assertEqual(len(text_out["sanad"]), 1)
                    self.assertEqual(text_out["sanad"][0]["hadith_id"], 8950)

                    chain_out = ans.answer_with_details(
                        "من الصحابي الذي روى الحديث رقم 8950؟",
                        retriever,
                        sanad_db_path=db_path,
                    )
                    self.assertEqual(mock_gen.call_count, 1)
                    self.assertEqual(mock_agent.call_count, 1)
                    self.assertEqual(chain_out["answer"], fake_agent_out["answer"])


if __name__ == "__main__":
    unittest.main()
