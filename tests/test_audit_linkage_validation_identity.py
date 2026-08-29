import unittest

from src.audit_linkage_validation_identity import (
    audit_rows,
    normalize_narrow_identity,
)


class NarrowIdentityNormalizationTests(unittest.TestCase):
    def test_removes_diacritics_tatweel_and_folds_whitespace(self):
        left = "حَـدَّثَنَا\n  رَسُولُ اللَّهِ"
        right = "حدثنا رسول الله"
        self.assertEqual(
            normalize_narrow_identity(left),
            normalize_narrow_identity(right),
        )

    def test_does_not_normalize_arabic_base_letters(self):
        distinct_pairs = [
            ("أحمد", "احمد"),
            ("إلى", "الي"),
            ("على", "علي"),
            ("رحمة", "رحمه"),
        ]
        for left, right in distinct_pairs:
            with self.subTest(left=left, right=right):
                self.assertNotEqual(
                    normalize_narrow_identity(left),
                    normalize_narrow_identity(right),
                )

    def test_does_not_remove_punctuation_or_words(self):
        self.assertNotEqual(
            normalize_narrow_identity("قال: نعم"),
            normalize_narrow_identity("قال نعم"),
        )
        self.assertNotEqual(
            normalize_narrow_identity("قال نعم"),
            normalize_narrow_identity("نعم"),
        )

    def test_nfc_preserves_decomposed_hamza_as_a_base_letter(self):
        self.assertEqual(normalize_narrow_identity("ا\u0654حمد"), "أحمد")
        self.assertNotEqual(
            normalize_narrow_identity("ا\u0654حمد"),
            normalize_narrow_identity("احمد"),
        )


class IdentityAuditTests(unittest.TestCase):
    def test_counts_matches_without_creating_human_labels(self):
        rows = [
            {
                "review_id": "VAL-0001",
                "our_text": "حَدَّثَنَا",
                "mis_text": "حدثنا",
                "manual_verdict": "",
                "notes": "",
                "ai_verdict": "correct",
            },
            {
                "review_id": "VAL-0002",
                "our_text": "قال: نعم",
                "mis_text": "قال نعم",
                "manual_verdict": "",
                "notes": "",
                "ai_verdict": "wrong",
            },
        ]

        result = audit_rows(rows)

        self.assertEqual(result["rows_reviewed"], 2)
        self.assertEqual(result["raw_strings_exactly_equal"], 0)
        self.assertEqual(result["exact_after_narrow_normalization"], 1)
        self.assertEqual(
            result["needs_manual_adjudication_after_computational_check"], 1
        )
        self.assertEqual(result["mismatched_review_ids"], ["VAL-0002"])
        self.assertEqual(result["manual_verdicts_present"], 0)
        self.assertEqual(result["supplied_ai_verdict_disagreements"], 0)


if __name__ == "__main__":
    unittest.main()
