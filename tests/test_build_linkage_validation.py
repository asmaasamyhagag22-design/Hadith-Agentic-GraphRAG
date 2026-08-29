import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.build_linkage_validation import (
    HIDDEN_COLUMNS,
    REVIEW_COLUMNS,
    ReviewerSchemaError,
    _ensure_clean_reviewer_export,
    _ensure_safe_existing_review,
    build_sample_rows,
    sample_size_for_proportion,
)


class SampleDesignTests(unittest.TestCase):
    def test_size_uses_finite_population_correction(self):
        size = sample_size_for_proportion(7015, assumed_precision=0.99, margin=0.01)
        self.assertGreater(size, 300)
        self.assertLess(size, 380)

    def test_visible_review_rows_hide_matcher_metadata(self):
        accepted = [
            {
                "local_position": index,
                "mis_position": index + 10,
                "our_idInBook": index,
                "mis_HadithNo": index + 10,
                "our_chapterId": 1,
                "mis_ChapterNo": 2,
                "similarity": 0.99,
                "quick_similarity": 1.0,
                "candidate_count": 1,
                "tail_signature": f"sig-{index}",
                "our_text": f"ours-{index}",
                "mis_text": f"mis-{index}",
            }
            for index in range(1, 11)
        ]
        visible, hidden = build_sample_rows(accepted, sample_size=4, seed=7)
        self.assertEqual(set(visible[0]), set(REVIEW_COLUMNS))
        self.assertEqual(set(hidden[0]), set(HIDDEN_COLUMNS))
        self.assertNotIn("similarity", visible[0])
        self.assertTrue(all(not row["manual_verdict"] for row in visible))
        visible_again, _ = build_sample_rows(accepted, sample_size=4, seed=7)
        self.assertEqual(visible, visible_again)

    def test_existing_review_rejects_appended_ai_columns(self):
        with TemporaryDirectory() as directory:
            review_path = Path(directory) / "review.csv"
            review_path.write_text(
                ",".join(REVIEW_COLUMNS + ["ai_verdict"]) + "\n"
                + "VAL-0001,1,2,ours,mis,,,correct\n",
                encoding="utf-8-sig",
            )
            proposed = [{column: "" for column in REVIEW_COLUMNS}]

            with patch(
                "src.build_linkage_validation.REVIEW_CSV", review_path
            ):
                with self.assertRaisesRegex(
                    ReviewerSchemaError, "unexpected columns: ai_verdict"
                ):
                    _ensure_safe_existing_review(proposed)

    def test_clean_export_is_separate_and_idempotent(self):
        rows = [{column: "" for column in REVIEW_COLUMNS}]
        rows[0].update({
            "review_id": "VAL-0001",
            "our_idInBook": 1,
            "mis_HadithNo": 102,
            "our_text": "ours",
            "mis_text": "mis",
        })

        with TemporaryDirectory() as directory:
            clean_path = Path(directory) / "human-review.csv"
            with patch(
                "src.build_linkage_validation.CLEAN_REVIEW_CSV", clean_path
            ):
                self.assertTrue(_ensure_clean_reviewer_export(rows))
                self.assertFalse(_ensure_clean_reviewer_export(rows))

            header = clean_path.read_text(encoding="utf-8-sig").splitlines()[0]
            self.assertEqual(header, ",".join(REVIEW_COLUMNS))


if __name__ == "__main__":
    unittest.main()
