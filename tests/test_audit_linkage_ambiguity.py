import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.audit_linkage_ambiguity import (
    NONEXACT_REVIEW_COLUMNS,
    arabic_word_tokens,
    classify_accepted_collisions,
    deterministic_text_delta,
    ensure_nonexact_review,
    enumerate_inversion_pairs,
    exact_rank_statistics,
    minimal_equalizing_transform_sets,
)


class CollisionClassificationTests(unittest.TestCase):
    def test_all_four_classes_are_counted_without_deduplication(self):
        corpus = [
            {"idInBook": 1, "arabic": "a"},
            {"idInBook": 2, "arabic": "b"},
            {"idInBook": 3, "arabic": "c"},
            {"idInBook": 4, "arabic": "c"},
            {"idInBook": 5, "arabic": "d"},
            {"idInBook": 6, "arabic": "d"},
        ]
        mis = [
            {"HadithNo": 10, "HadithText_GhairMushakkal": "a"},
            {"HadithNo": 11, "HadithText_GhairMushakkal": "b"},
            {"HadithNo": 12, "HadithText_GhairMushakkal": "b"},
            {"HadithNo": 13, "HadithText_GhairMushakkal": "c"},
            {"HadithNo": 14, "HadithText_GhairMushakkal": "d"},
            {"HadithNo": 15, "HadithText_GhairMushakkal": "d"},
        ]
        accepted = [
            {"our_text": "a", "mis_text": "a"},
            {"our_text": "b", "mis_text": "b"},
            {"our_text": "c", "mis_text": "c"},
            {"our_text": "d", "mis_text": "d"},
        ]

        summary, _, _, _ = classify_accepted_collisions(
            corpus, mis, accepted
        )

        self.assertEqual(
            {category: values["count"] for category, values in summary.items()},
            {
                "UNIQUE_UNIQUE": 1,
                "UNIQUE_MULTI": 1,
                "MULTI_UNIQUE": 1,
                "MULTI_MULTI": 1,
            },
        )


class ExactOrderingTests(unittest.TestCase):
    def test_reports_exact_single_inversion_and_pair(self):
        rows = [
            {
                "local_position": 1,
                "mis_position": 1,
                "our_idInBook": 1,
                "mis_HadithNo": 10,
            },
            {
                "local_position": 2,
                "mis_position": 3,
                "our_idInBook": 2,
                "mis_HadithNo": 12,
            },
            {
                "local_position": 3,
                "mis_position": 2,
                "our_idInBook": 3,
                "mis_HadithNo": 11,
            },
        ]

        statistics = exact_rank_statistics(rows, "mis_position")
        inversion_pairs = enumerate_inversion_pairs(rows, "mis_position")

        self.assertEqual(statistics["spearman_exact_fraction"], "1/2")
        self.assertEqual(statistics["kendall_tau_exact_fraction"], "1/3")
        self.assertEqual(statistics["inversion_count"], 1)
        self.assertTrue(inversion_pairs["enumerated"])
        self.assertEqual(len(inversion_pairs["pairs"]), 1)
        self.assertEqual(
            inversion_pairs["pairs"][0]["earlier_local_record"]["our_idInBook"],
            2,
        )
        self.assertEqual(
            inversion_pairs["pairs"][0]["later_local_record"]["our_idInBook"],
            3,
        )


class NormalizationDeltaTests(unittest.TestCase):
    def test_finds_minimal_combination_of_allowed_transforms(self):
        left = "حَـدَّثَنَا\nرَسُولُ اللَّهِ"
        right = "حدثنا رسول الله"

        minimal = minimal_equalizing_transform_sets(left, right)

        self.assertEqual(
            minimal,
            [("DIACRITICS", "TATWEEL", "WHITESPACE")],
        )

    def test_word_delta_preserves_base_letter_distinctions(self):
        self.assertEqual(arabic_word_tokens("أَحْمَدُ"), ["أحمد"])
        delta = deterministic_text_delta("أَحْمَدُ", "احمد")
        self.assertFalse(delta["arabic_word_sequence_equal"])
        self.assertFalse(delta["arabic_base_letter_sequence_equal"])

    def test_punctuation_only_delta_does_not_claim_word_change(self):
        delta = deterministic_text_delta("قال: نعم", "قال نعم")
        self.assertTrue(delta["arabic_word_sequence_equal"])
        self.assertTrue(delta["arabic_base_letter_sequence_equal"])
        self.assertTrue(delta["punctuation_or_spacing_only"])


class TargetedReviewSafetyTests(unittest.TestCase):
    def test_existing_human_label_is_preserved(self):
        rows = [{
            "review_id": "NONEXACT-001",
            "our_idInBook": 1,
            "mis_HadithNo": 2,
            "our_text": "ours",
            "mis_text": "mis",
            "manual_verdict": "",
            "notes": "",
        }]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            created = ensure_nonexact_review(path, rows)
            self.assertEqual(created["action"], "created")

            content = path.read_text(encoding="utf-8-sig")
            path.write_text(
                content.replace(",,\n", ",correct,checked\n"),
                encoding="utf-8-sig",
            )
            preserved = ensure_nonexact_review(path, rows)

            self.assertEqual(preserved["action"], "preserved")
            self.assertEqual(preserved["manual_labels_present"], 1)
            self.assertEqual(
                tuple(content.splitlines()[0].split(",")),
                NONEXACT_REVIEW_COLUMNS,
            )


if __name__ == "__main__":
    unittest.main()
