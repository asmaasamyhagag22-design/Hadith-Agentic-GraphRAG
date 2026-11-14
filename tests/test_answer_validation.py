import unittest
from unittest.mock import patch

from src.answer import (
    CORRECTION_MISSING_CITATION,
    CORRECTION_MIXED_REFUSAL,
    CORRECTION_OUT_OF_CONTEXT,
    MISSING_CITATION,
    MIXED_REFUSAL,
    OUT_OF_CONTEXT_CITATION,
    REFUSAL,
    VALID_ANSWER,
    VALID_REFUSAL,
    answer_with_details,
    cited_ids,
    loose_cited_ids,
    validate_answer,
)


class FakeRetriever:

    def __init__(self, chunks):
        self._chunks = chunks

    def search(self, question, k=5):
        return self._chunks[:k]


SAMPLE_CHUNKS = [
    {
        "chunk_id": "101",
        "hadith_id": 7354,
        "text": "لا يؤمن أحدكم حتى يحب لأخيه ما يحب لنفسه",
        "matn": "لا يؤمن أحدكم حتى يحب لأخيه ما يحب لنفسه",
        "rank": 1,
        "score": 0.95,
        "metadata": {"chapter_arabic": "كتاب الإيمان"},
    },
    {
        "chunk_id": "102",
        "hadith_id": 7355,
        "text": "لا يؤمن أحدكم حتى يحب لجاره ما يحب لنفسه",
        "matn": "لا يؤمن أحدكم حتى يحب لجاره ما يحب لنفسه",
        "rank": 2,
        "score": 0.90,
        "metadata": {"chapter_arabic": "كتاب الإيمان"},
    },
]


class ValidateAnswerTests(unittest.TestCase):

    def test_answer_with_no_citation_returns_missing_citation(self):
        answer = "من شروط كمال الإيمان أن يحب المرء لأخيه ما يحب لنفسه."
        self.assertEqual(validate_answer(answer, {7354, 7355}), MISSING_CITATION)

    def test_cited_number_outside_context_returns_out_of_context(self):
        answer = (
            "يحب المرء لأخيه ما يحب لنفسه "
            "(المصدر: صحيح مسلم، حديث رقم 999)"
        )
        self.assertEqual(
            validate_answer(answer, {7354, 7355}),
            OUT_OF_CONTEXT_CITATION,
        )

    def test_loose_hadith_reference_outside_context_returns_out_of_context(self):
        for snippet in (
            "كما ورد في حديث 999 عن النبي ﷺ.",
            "الدليل في حديث رقم: 999.",
            "رواه الإمام في (مسلم 999).",
            "مسلم، 999",
            "رواه في (صحيح مسلم، 999).",
            "رواه في (صحيح مسلم، رقم 999).",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(999, loose_cited_ids(snippet))
                self.assertEqual(
                    validate_answer(snippet, {7354, 7355}),
                    OUT_OF_CONTEXT_CITATION,
                )

    def test_loose_in_context_reference_without_required_format_is_missing_citation(self):
        answer = "ورد ذلك في حديث 7354 ومسلم 7355."
        self.assertEqual(validate_answer(answer, {7354, 7355}), MISSING_CITATION)

    def test_arabic_indic_digits_inside_and_outside_context(self):
        valid = "يحب لأخيه ما يحب لنفسه (المصدر: صحيح مسلم، حديث رقم ٧٣٥٤)"
        self.assertEqual(cited_ids(valid), {7354})
        self.assertEqual(validate_answer(valid, {7354}), VALID_ANSWER)

        out_strict = "يحب لأخيه ما يحب لنفسه (المصدر: صحيح مسلم، حديث رقم ٩٩٩)"
        self.assertEqual(
            validate_answer(out_strict, {7354}),
            OUT_OF_CONTEXT_CITATION,
        )

        out_loose = "كما جاء في حديث ٩٩٩."
        self.assertEqual(loose_cited_ids(out_loose), {999})
        self.assertEqual(
            validate_answer(out_loose, {7354}),
            OUT_OF_CONTEXT_CITATION,
        )

    def test_exact_refusal_returns_valid_refusal(self):
        self.assertEqual(validate_answer(REFUSAL, {7354}), VALID_REFUSAL)
        self.assertEqual(
            validate_answer(f"  \n{REFUSAL}\n  ", {7354}),
            VALID_REFUSAL,
        )

    def test_refusal_with_at_most_one_trailing_punctuation_returns_valid_refusal(self):
        for punct in (".", "؟", "!"):
            with self.subTest(punct=punct):
                self.assertEqual(
                    validate_answer(f"{REFUSAL}{punct}", {7354}),
                    VALID_REFUSAL,
                )
                self.assertEqual(
                    validate_answer(f"  {REFUSAL}{punct}\n ", {7354}),
                    VALID_REFUSAL,
                )

        for multi_punct in ("..", "؟؟", "!!", ".!", "؟."):
            with self.subTest(multi_punct=multi_punct):
                self.assertEqual(
                    validate_answer(f"{REFUSAL}{multi_punct}", {7354}),
                    MIXED_REFUSAL,
                )

    def test_refusal_followed_by_answer_returns_mixed_refusal(self):
        mixed = (
            f"{REFUSAL}\n"
            "ولكن يُذكر في باب الإيمان أن يحب لأخيه ما يحب لنفسه "
            "(المصدر: صحيح مسلم، حديث رقم 7354)"
        )
        self.assertEqual(validate_answer(mixed, {7354}), MIXED_REFUSAL)

        mixed_with_citation = f"{REFUSAL} (حديث رقم 7354)"
        self.assertEqual(
            validate_answer(mixed_with_citation, {7354}),
            MIXED_REFUSAL,
        )

    def test_valid_answer_with_one_and_several_in_context_citations(self):
        single = (
            "شرط كمال الإيمان أن يحب لأخيه ما يحب لنفسه "
            "(المصدر: صحيح مسلم، حديث رقم 7354)"
        )
        self.assertEqual(validate_answer(single, {7354, 7355}), VALID_ANSWER)

        multiple = (
            "يحب لأخيه ولجاره ما يحب لنفسه "
            "(المصدر: صحيح مسلم، حديث رقم 7354، وحديث رقم 7355)"
        )
        self.assertEqual(validate_answer(multiple, {7354, 7355}), VALID_ANSWER)

    def test_non_hadith_numbers_in_prose_are_valid(self):
        plain_number = (
            "الوتر ركعة واحدة أو 3 ركعات من آخر الليل "
            "(المصدر: صحيح مسلم، حديث رقم 7354)"
        )
        self.assertEqual(validate_answer(plain_number, {7354}), VALID_ANSWER)

        non_hadith_raqam = (
            "الشرط رقم 2 من شروط البيع مذكور هنا "
            "(المصدر: صحيح مسلم، حديث رقم 7354)"
        )
        self.assertEqual(
            validate_answer(non_hadith_raqam, {7354}),
            VALID_ANSWER,
        )


class AnswerRetryFlowTests(unittest.TestCase):

    def test_valid_first_time_does_not_retry(self):
        retriever = FakeRetriever(SAMPLE_CHUNKS)
        valid_reply = (
            "أن يحب لأخيه ما يحب لنفسه (المصدر: صحيح مسلم، حديث رقم 7354)"
        )

        with patch("src.answer.generate", return_value=valid_reply) as mock_gen:
            details = answer_with_details("ما شرط كمال الإيمان؟", retriever)

        self.assertEqual(mock_gen.call_count, 1)
        self.assertEqual(details["answer"], valid_reply)
        self.assertFalse(details["regenerated"])
        self.assertFalse(details["invalid_citation_attempt"])
        self.assertFalse(details["missing_citation_attempt"])
        self.assertFalse(details["loose_out_of_context_attempt"])
        self.assertFalse(details["mixed_refusal_attempt"])

    def test_valid_refusal_first_time_does_not_retry(self):
        retriever = FakeRetriever(SAMPLE_CHUNKS)

        with patch("src.answer.generate", return_value=REFUSAL) as mock_gen:
            details = answer_with_details("سؤال خارج السياق؟", retriever)

        self.assertEqual(mock_gen.call_count, 1)
        self.assertEqual(details["answer"], REFUSAL)
        self.assertFalse(details["regenerated"])
        self.assertFalse(details["invalid_citation_attempt"])
        self.assertFalse(details["missing_citation_attempt"])

    def test_missing_citation_then_valid_returns_second_answer(self):
        retriever = FakeRetriever(SAMPLE_CHUNKS)
        first = "أن يحب لأخيه ما يحب لنفسه."
        second = "أن يحب لأخيه ما يحب لنفسه (المصدر: صحيح مسلم، حديث رقم 7354)"

        with patch("src.answer.generate", side_effect=[first, second]) as mock_gen:
            details = answer_with_details("ما شرط كمال الإيمان؟", retriever)

        self.assertEqual(mock_gen.call_count, 2)
        self.assertEqual(mock_gen.call_args_list[1].args[0], CORRECTION_MISSING_CITATION)
        self.assertEqual(details["answer"], second)
        self.assertEqual(details["raw"], first)
        self.assertTrue(details["regenerated"])
        self.assertFalse(details["invalid_citation_attempt"])
        self.assertTrue(details["missing_citation_attempt"])
        self.assertFalse(details["loose_out_of_context_attempt"])
        self.assertFalse(details["mixed_refusal_attempt"])

    def test_out_of_context_then_valid_returns_second_answer(self):
        retriever = FakeRetriever(SAMPLE_CHUNKS)
        first = "أن يحب لأخيه ما يحب لنفسه (المصدر: صحيح مسلم، حديث رقم 999)"
        second = "أن يحب لأخيه ما يحب لنفسه (المصدر: صحيح مسلم، حديث رقم 7354)"

        with patch("src.answer.generate", side_effect=[first, second]) as mock_gen:
            details = answer_with_details("ما شرط كمال الإيمان؟", retriever)

        self.assertEqual(mock_gen.call_count, 2)
        self.assertEqual(mock_gen.call_args_list[1].args[0], CORRECTION_OUT_OF_CONTEXT)
        self.assertEqual(details["answer"], second)
        self.assertTrue(details["regenerated"])
        self.assertTrue(details["invalid_citation_attempt"])
        self.assertFalse(details["missing_citation_attempt"])
        self.assertFalse(details["loose_out_of_context_attempt"])

    def test_loose_out_of_context_sets_loose_flag_not_strict_invalid_flag(self):
        retriever = FakeRetriever(SAMPLE_CHUNKS)
        first = "كما جاء في حديث 999 عن المحبة."
        second = "أن يحب لأخيه ما يحب لنفسه (المصدر: صحيح مسلم، حديث رقم 7354)"

        with patch("src.answer.generate", side_effect=[first, second]) as mock_gen:
            details = answer_with_details("ما شرط كمال الإيمان؟", retriever)

        self.assertEqual(mock_gen.call_count, 2)
        self.assertEqual(mock_gen.call_args_list[1].args[0], CORRECTION_OUT_OF_CONTEXT)
        self.assertEqual(details["answer"], second)
        self.assertFalse(details["invalid_citation_attempt"])
        self.assertTrue(details["loose_out_of_context_attempt"])
        self.assertFalse(details["missing_citation_attempt"])

    def test_mixed_refusal_then_valid_refusal(self):
        retriever = FakeRetriever(SAMPLE_CHUNKS)
        first = f"{REFUSAL} ولكن أظن الجواب كذا."
        second = REFUSAL

        with patch("src.answer.generate", side_effect=[first, second]) as mock_gen:
            details = answer_with_details("سؤال غير موجود؟", retriever)

        self.assertEqual(mock_gen.call_count, 2)
        self.assertEqual(mock_gen.call_args_list[1].args[0], CORRECTION_MIXED_REFUSAL)
        self.assertEqual(details["answer"], REFUSAL)
        self.assertTrue(details["regenerated"])
        self.assertTrue(details["mixed_refusal_attempt"])

    def test_invalid_twice_returns_refusal(self):
        retriever = FakeRetriever(SAMPLE_CHUNKS)
        first = "إجابة بلا مصدر."
        second = "إجابة برقم خارج السياق (المصدر: صحيح مسلم، حديث رقم 999)"

        with patch("src.answer.generate", side_effect=[first, second]) as mock_gen:
            details = answer_with_details("ما شرط كمال الإيمان؟", retriever)

        self.assertEqual(mock_gen.call_count, 2)
        self.assertEqual(details["answer"], REFUSAL)
        self.assertEqual(details["raw"], first)
        self.assertTrue(details["regenerated"])
        self.assertTrue(details["missing_citation_attempt"])


if __name__ == "__main__":
    unittest.main()
