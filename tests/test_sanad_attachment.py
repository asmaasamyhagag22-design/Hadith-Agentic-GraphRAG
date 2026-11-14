import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.answer import (
    REFUSAL,
    SANAD_HEADER,
    answer_with_details,
    format_sanad_chain,
    format_sanad_section,
    main as answer_main,
)
from src.build_sanad_graph import build
from src.sanad_context import (
    LINKED_BUT_NO_RECORDED_ISNAD,
    LINKED_WITH_RECORDED_ISNAD,
    NO_ACCEPTED_MIS_LINK,
)
from src.sanad_graph import open_graph as real_open_graph
from tests.test_build_sanad_graph import fixture


class _FakeRetriever:
    def __init__(self, chunks):
        self._chunks = chunks

    def search(self, question, k=5):
        return self._chunks[:k]


FIXTURE_CHUNKS = [
    {
        "chunk_id": "100_0",
        "hadith_id": 100,
        "text": "متن الحديث الأول",
        "matn": "متن الحديث الأول",
        "rank": 1,
        "score": 0.9,
        "metadata": {"chapter_arabic": "كتاب الإيمان"},
    },
    {
        "chunk_id": "101_0",
        "hadith_id": 101,
        "text": "متن الحديث الثاني",
        "matn": "متن الحديث الثاني",
        "rank": 2,
        "score": 0.8,
        "metadata": {"chapter_arabic": "كتاب الإيمان"},
    },
    {
        "chunk_id": "102_0",
        "hadith_id": 102,
        "text": "متن الحديث الثالث",
        "matn": "متن الحديث الثالث",
        "rank": 3,
        "score": 0.7,
        "metadata": {"chapter_arabic": "كتاب الإيمان"},
    },
]


class SanadAttachmentTests(unittest.TestCase):
    """اختبارات إلحاق السند بالإجابة وعرضه في الـ CLI."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "sanad_fixture.sqlite"
        build(self.db_path, *fixture())
        self.retriever = _FakeRetriever(FIXTURE_CHUNKS)

    def tearDown(self):
        self._tmp.cleanup()

    def test_single_citation_attaches_sanad_with_one_connection(self):
        reply = "الجواب الصحيح (المصدر: صحيح مسلم، حديث رقم 101)"
        open_calls = 0

        def tracking_open():
            nonlocal open_calls
            open_calls += 1
            return real_open_graph(self.db_path)

        with (
            patch("src.answer.generate", return_value=reply),
            patch("src.answer.open_graph", side_effect=tracking_open),
        ):
            details = answer_with_details("سؤال؟", self.retriever)

        self.assertEqual(open_calls, 1)
        self.assertIsNone(details["sanad_error"])
        self.assertEqual(len(details["sanad"]), 1)
        entry = details["sanad"][0]
        self.assertEqual(entry["hadith_id"], 101)
        self.assertEqual(entry["status"], LINKED_WITH_RECORDED_ISNAD)
        self.assertEqual(entry["isnad_count"], 1)
        self.assertEqual(
            entry["isnads"],
            [
                [
                    {"chain_position": 1, "name_ar_mapped": "أ"},
                    {"chain_position": 2, "name_ar_mapped": "ج"},
                ]
            ],
        )

    def test_several_citations_deduplicated_in_one_connection(self):
        reply = (
            "ورد ذلك في حديث رقم 100 وحديث رقم 101، "
            "ومرة أخرى (المصدر: صحيح مسلم، حديث رقم 100)"
        )
        open_calls = 0

        def tracking_open():
            nonlocal open_calls
            open_calls += 1
            return real_open_graph(self.db_path)

        with (
            patch("src.answer.generate", return_value=reply),
            patch("src.answer.open_graph", side_effect=tracking_open),
        ):
            details = answer_with_details("سؤال؟", self.retriever)

        self.assertEqual(open_calls, 1)
        self.assertIsNone(details["sanad_error"])
        self.assertEqual([e["hadith_id"] for e in details["sanad"]], [100, 101])
        self.assertEqual(details["sanad"][0]["isnad_count"], 2)
        self.assertEqual(details["sanad"][1]["isnad_count"], 1)

        cli_block = format_sanad_section(details["sanad"], details["sanad_error"])
        self.assertIn(SANAD_HEADER, cli_block)
        self.assertIn("حديث رقم 100: ج ← ب ← أ (+1 طرق أخرى)", cli_block)
        self.assertIn("حديث رقم 101: ج ← أ", cli_block)
        self.assertNotIn("حديث رقم 101: ج ← أ (+", cli_block)

    def test_unlinked_hadith_preserves_status_without_inventing_chain(self):
        reply = "النص (المصدر: صحيح مسلم، حديث رقم 102)"

        with patch("src.answer.generate", return_value=reply):
            details = answer_with_details(
                "سؤال؟", self.retriever, sanad_db_path=self.db_path
            )

        self.assertIsNone(details["sanad_error"])
        self.assertEqual(
            details["sanad"],
            [
                {
                    "hadith_id": 102,
                    "status": NO_ACCEPTED_MIS_LINK,
                    "isnad_count": 0,
                    "isnads": [],
                }
            ],
        )

        cli_block = format_sanad_section(details["sanad"])
        self.assertIn(SANAD_HEADER, cli_block)
        self.assertIn("حديث رقم 102:", cli_block)
        self.assertIn("لا يوجد ربط مقبول", cli_block)

    def test_linked_hadith_without_recorded_isnad_preserves_status(self):
        conn = real_open_graph(self.db_path)
        try:
            conn.execute("DELETE FROM transmission WHERE hadith_no = '2'")
            conn.execute("DELETE FROM isnad WHERE hadith_no = '2'")
            conn.commit()
        finally:
            conn.close()

        reply = "النص (المصدر: صحيح مسلم، حديث رقم 101)"

        with patch("src.answer.generate", return_value=reply):
            details = answer_with_details(
                "سؤال؟", self.retriever, sanad_db_path=self.db_path
            )

        self.assertIsNone(details["sanad_error"])
        self.assertEqual(
            details["sanad"],
            [
                {
                    "hadith_id": 101,
                    "status": LINKED_BUT_NO_RECORDED_ISNAD,
                    "isnad_count": 0,
                    "isnads": [],
                }
            ],
        )

        cli_block = format_sanad_section(details["sanad"])
        self.assertIn(SANAD_HEADER, cli_block)
        self.assertIn("حديث رقم 101:", cli_block)
        self.assertIn("لا يوجد له إسناد مسجّل", cli_block)

    def test_refusal_and_failed_answers_get_empty_sanad_and_skip_db(self):
        with patch("src.answer.open_graph") as mock_open:
            empty_details = answer_with_details("سؤال؟", _FakeRetriever([]))
        self.assertEqual(empty_details["answer"], REFUSAL)
        self.assertEqual(empty_details["sanad"], [])
        self.assertIsNone(empty_details["sanad_error"])
        mock_open.assert_not_called()

        with (
            patch("src.answer.generate", return_value=REFUSAL),
            patch("src.answer.open_graph") as mock_open,
        ):
            refusal_details = answer_with_details("سؤال؟", self.retriever)
        self.assertEqual(refusal_details["sanad"], [])
        self.assertIsNone(refusal_details["sanad_error"])
        mock_open.assert_not_called()

        with (
            patch(
                "src.answer.generate",
                side_effect=["إجابة بلا مصدر", "إجابة برقم حديث رقم 999"],
            ),
            patch("src.answer.open_graph") as mock_open,
        ):
            failed_details = answer_with_details("سؤال؟", self.retriever)
        self.assertEqual(failed_details["answer"], REFUSAL)
        self.assertEqual(failed_details["sanad"], [])
        mock_open.assert_not_called()

        with (
            patch("src.answer.generate", return_value="إجابة بلا مصدر"),
            patch("src.answer.open_graph") as mock_open,
        ):
            unenforced_details = answer_with_details(
                "سؤال؟", self.retriever, enforce_citations=False
            )
        self.assertEqual(unenforced_details["sanad"], [])
        mock_open.assert_not_called()

        self.assertEqual(format_sanad_section([]), "")

    def test_retry_that_becomes_valid_attaches_sanad(self):
        with patch(
            "src.answer.generate",
            side_effect=[
                "إجابة بلا مصدر",
                "الإجابة بعد التصحيح (المصدر: صحيح مسلم، حديث رقم 101)",
            ],
        ):
            details = answer_with_details(
                "سؤال؟", self.retriever, sanad_db_path=self.db_path
            )

        self.assertTrue(details["regenerated"])
        self.assertEqual(len(details["sanad"]), 1)
        self.assertEqual(details["sanad"][0]["hadith_id"], 101)

    def test_graph_missing_or_query_failure_returns_answer_and_sets_sanad_error(self):
        reply = "الإجابة (المصدر: صحيح مسلم، حديث رقم 101)"
        missing_db = Path(self._tmp.name) / "absent.sqlite"

        with patch("src.answer.generate", return_value=reply):
            details = answer_with_details(
                "سؤال؟", self.retriever, sanad_db_path=missing_db
            )

        self.assertEqual(details["answer"], reply)
        self.assertEqual(details["sanad"], [])
        self.assertIn("GraphNotBuiltError", details["sanad_error"])

        fake_conn = MagicMock()
        with (
            patch("src.answer.generate", return_value=reply),
            patch("src.answer.open_graph", return_value=fake_conn),
            patch(
                "src.answer.context_for_local_hadith",
                side_effect=sqlite3.OperationalError("database is locked"),
            ),
        ):
            err_details = answer_with_details("سؤال؟", self.retriever)

        self.assertEqual(err_details["answer"], reply)
        self.assertEqual(err_details["sanad"], [])
        self.assertIn("OperationalError", err_details["sanad_error"])
        fake_conn.close.assert_called_once()

        cli_block = format_sanad_section(
            err_details["sanad"], err_details["sanad_error"]
        )
        self.assertIn(SANAD_HEADER, cli_block)
        self.assertIn("OperationalError", cli_block)

    def test_chain_order_prints_from_muslims_teacher_to_companion_and_cli_prints_block(self):
        reply = "الجواب (المصدر: صحيح مسلم، حديث رقم 100)"
        with patch("src.answer.generate", return_value=reply):
            details = answer_with_details(
                "سؤال؟", self.retriever, sanad_db_path=self.db_path
            )

        chain = details["sanad"][0]["isnads"][0]
        self.assertEqual([n["chain_position"] for n in chain], [1, 2, 3])
        self.assertEqual(format_sanad_chain(chain), "ج ← ب ← أ")

        printed = []
        with (
            patch("src.answer.build_pipeline", return_value=self.retriever),
            patch("src.answer.load_questions", return_value=["سؤال تجريبي؟"]),
            patch("src.answer.generate", return_value=reply),
            patch("src.answer.open_graph", side_effect=lambda: real_open_graph(self.db_path)),
            patch("builtins.print", side_effect=lambda *args: printed.append(" ".join(str(a) for a in args))),
        ):
            answer_main()

        output = "\n".join(printed)
        self.assertIn(SANAD_HEADER, output)
        self.assertIn("حديث رقم 100: ج ← ب ← أ (+1 طرق أخرى)", output)
        self.assertLess(output.index("Answer:"), output.index(SANAD_HEADER))
        self.assertLess(output.index(SANAD_HEADER), output.index("Retrieved Hadiths:"))


if __name__ == "__main__":
    unittest.main()
