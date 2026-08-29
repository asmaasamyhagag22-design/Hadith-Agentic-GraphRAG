import unittest

from src.audit_gradings import grading_disagreement


class GradingDisagreementTests(unittest.TestCase):
    def test_blank_unknown_is_not_counted_as_substantive_critic_verdict(self):
        records = [
            {
                "classical_sources": {
                    "a": {"grade_ar": "", "grade_en": "unknown"},
                    "b": {"grade_ar": "ثقة", "grade_en": "reliable"},
                }
            },
            {
                "classical_sources": {
                    "a": {"grade_ar": "ضعيف", "grade_en": "weak"},
                    "b": {"grade_ar": "ثقة", "grade_en": "reliable"},
                }
            },
        ]
        result = grading_disagreement(records)
        self.assertEqual(result["itqan_category_all_source_entries"]["category_differs"], 2)
        self.assertEqual(
            result["itqan_category_substantive_source_entries"]["eligible_profiles_with_at_least_two_nonblank_raw_grades"],
            1,
        )
        self.assertEqual(
            result["itqan_category_substantive_source_entries"]["category_differs"],
            1,
        )
        self.assertEqual(result["unknown_category_with_blank_raw_grade_entries"], 1)


if __name__ == "__main__":
    unittest.main()
