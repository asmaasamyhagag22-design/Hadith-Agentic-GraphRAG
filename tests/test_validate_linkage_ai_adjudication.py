import unittest

from src.audit_linkage_ambiguity import (
    classify_nonexact_exception,
    retained_text_after_exception,
)
from src.validate_linkage_ai_adjudication import evaluate_gate, parse_ai_report


class ExceptionClassificationTests(unittest.TestCase):
    def test_measured_exception_shapes_are_supported(self):
        cases = [
            (
                "حدثنا زيد، ح قال المتن",
                "قال المتن",
                "LOCAL_LEADING_HA_TRANSITION_PREFIX",
            ),
            (
                "قال أول المتن",
                "قال ‎03:43 م ‎19/‎01/‎2003أول المتن",
                "MIS_TIMESTAMP_INSERTION",
            ),
            ("قال المتن", "قال‏ المتن", "MIS_BIDI_FORMAT_MARK"),
            ("قال المتن", "قال، المتن", "MIS_ARABIC_COMMA"),
            ("قال\\ المتن\\", "قال المتن", "LOCAL_BACKSLASH_ARTIFACTS"),
            (
                "قال المتن",
                "قال ح المتن",
                "MIS_STANDALONE_HA_TRANSITION",
            ),
        ]
        for local, mis, category in cases:
            with self.subTest(category=category):
                result = classify_nonexact_exception(local, mis)
                self.assertEqual(result["status"], "DETERMINISTICALLY_SUPPORTED")
                self.assertEqual(result["category"], category)
                self.assertIsNotNone(retained_text_after_exception(local, mis))

    def test_unrecognized_change_remains_unresolved(self):
        result = classify_nonexact_exception("قال زيد", "قال عمرو")
        self.assertEqual(result["status"], "UNRESOLVED")


class AdjudicationReportParsingTests(unittest.TestCase):
    def test_requires_counts_and_ai_not_human_label(self):
        report = """Result:
- correct: 11
- wrong: 0
- uncertain: 0
This is assistant/AI-assisted adjudication, not independent human validation.
"""
        self.assertEqual(
            parse_ai_report(report),
            {"correct": 11, "wrong": 0, "uncertain": 0},
        )

    def test_rejects_report_that_omits_methodological_label(self):
        with self.assertRaisesRegex(ValueError, "disclaim"):
            parse_ai_report("- correct: 11\n- wrong: 0\n- uncertain: 0\n")


class GateEvidenceTests(unittest.TestCase):
    def test_opens_only_when_exact_and_supported_links_cover_population(self):
        ambiguity = {
            "accepted_links": 5,
            "collision_classification": {"UNIQUE_UNIQUE": {"count": 5}},
            "full_accepted_exact_identity": {
                "exact_normalized_pairs": 4,
                "non_exact_pairs": 1,
                "non_exact_summary": {
                    "retained_exception_core_unique_unique_pairs": 1,
                },
            },
            "collision_groups_involved_in_accepted_links": {"ambiguous": 0},
        }
        validation = {
            "deterministic_validation": {"supported": 1, "unresolved": 0},
            "aggregate_consistent": True,
        }

        result = evaluate_gate(ambiguity, validation)

        self.assertEqual(result["decision"], "GATE OPEN")
        self.assertFalse(result["phase_transition_authorized"])

    def test_unresolved_exception_keeps_gate_closed(self):
        ambiguity = {
            "accepted_links": 5,
            "collision_classification": {"UNIQUE_UNIQUE": {"count": 5}},
            "full_accepted_exact_identity": {
                "exact_normalized_pairs": 4,
                "non_exact_pairs": 1,
                "non_exact_summary": {
                    "retained_exception_core_unique_unique_pairs": 1,
                },
            },
            "collision_groups_involved_in_accepted_links": {"ambiguous": 0},
        }
        validation = {
            "deterministic_validation": {"supported": 0, "unresolved": 1},
            "aggregate_consistent": False,
        }
        self.assertEqual(
            evaluate_gate(ambiguity, validation)["decision"],
            "GATE CLOSED",
        )


if __name__ == "__main__":
    unittest.main()
