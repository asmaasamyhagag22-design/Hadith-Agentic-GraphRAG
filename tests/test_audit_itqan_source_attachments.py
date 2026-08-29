import copy
import unittest

from src.audit_itqan_source_attachments import (
    EXPERT_REVIEW_COLUMNS,
    SOURCE_RISK_COLUMNS,
    attachment_risk_category,
    build_source_key_index,
    compare_group_fields,
    compare_scalar_values,
    death_pair_differences,
    multiplicity_bucket,
    namespaced_source_records,
    profile_risk_class,
    source_group_audit,
    source_namespace_metrics,
    source_risk_csv_rows,
)


class NamespacedSourceKeyTests(unittest.TestCase):
    def test_namespaces_prevent_numeric_id_collision(self):
        profile = {
            "id": 1,
            "global_id": 7,
            "gk_id": 7,
            "provenance": {"kaggle_id": 7, "arsanad_id": 1},
            "classical_sources": {
                "taqrib": {"entry_id": 7, "grade_en": "reliable", "grade_ar": "ثقة"}
            },
        }
        records = namespaced_source_records(profile)
        self.assertIn(("kaggle:scholar_indx", "7"), records)
        self.assertIn(("gk:top_level_id", "7"), records)
        self.assertIn(("classical:taqrib", "7"), records)
        self.assertEqual(len([key for key in records if key[1] == "7"]), 3)

    def test_global_id_and_provenance_alias_are_one_attachment(self):
        profile = {
            "id": 1,
            "global_id": 9,
            "provenance": {"kaggle_id": 9},
        }
        records = namespaced_source_records(profile)
        record = records[("kaggle:scholar_indx", "9")]
        self.assertEqual(
            record["field_paths"], ["global_id", "provenance.kaggle_id"]
        )

    def test_source_specific_records_and_grades_are_preserved_exactly(self):
        source_entry = {"entry_id": 5, "grade_en": "weak", "grade_ar": "ضعيف"}
        profile = {
            "id": 1,
            "classical_sources": {"source_a": copy.deepcopy(source_entry)},
        }
        records = namespaced_source_records(profile)
        payload = records[("classical:source_a", "5")]["source_record_payload"]
        self.assertEqual(payload["grade_en"], "weak")
        self.assertEqual(payload["grade_ar"], "ضعيف")


class MultiplicityTests(unittest.TestCase):
    def setUp(self):
        self.profiles = [
            {"id": 1, "global_id": 9, "full_name": "زيد"},
            {"id": 2, "global_id": 9, "full_name": "عمرو"},
            {"id": 3, "global_id": 10, "full_name": "خالد"},
        ]

    def test_duplicate_source_key_detection_and_multiplicity(self):
        index, _ = build_source_key_index(self.profiles)
        self.assertEqual(set(index[("kaggle:scholar_indx", "9")]), {"1", "2"})
        self.assertEqual(multiplicity_bucket(2), "exactly_2")
        metrics = source_namespace_metrics(index)["kaggle:scholar_indx"]
        self.assertEqual(metrics["unique_source_record_keys"], 2)
        self.assertEqual(metrics["keys_attached_to_2_profiles"], 1)
        self.assertEqual(metrics["keys_attached_to_exactly_1_profile"], 1)
        self.assertEqual(metrics["largest_multiplicity"], 2)

    def test_report_generation_is_deterministic(self):
        index, _ = build_source_key_index(self.profiles)
        by_id = {str(profile["id"]): profile for profile in self.profiles}
        group = source_group_audit(
            ("kaggle:scholar_indx", "9"),
            index[("kaggle:scholar_indx", "9")],
            by_id,
        )
        self.assertEqual(source_risk_csv_rows([group]), source_risk_csv_rows([group]))


class ThreeStateAndContradictionTests(unittest.TestCase):
    def test_missing_is_unknown_not_consistent_or_contradictory(self):
        self.assertEqual(compare_scalar_values([None, "زيد"]), "UNKNOWN")
        self.assertEqual(compare_scalar_values(["زيد", "زيد"]), "CONSISTENT")
        self.assertEqual(compare_scalar_values(["زيد", "عمرو"]), "CONTRADICTORY")

    def test_contradiction_extraction_is_field_specific(self):
        profiles = [
            {"id": 1, "full_name": "زيد", "death": "100 هـ", "kunya": None},
            {"id": 2, "full_name": "عمرو", "death": "200 هـ", "kunya": "أبو زيد"},
        ]
        comparisons = compare_group_fields(profiles)
        self.assertEqual(comparisons["canonical_name"], "CONTRADICTORY")
        self.assertEqual(comparisons["death"], "CONTRADICTORY")
        self.assertEqual(comparisons["kunya"], "UNKNOWN")
        self.assertEqual(
            attachment_risk_category(comparisons),
            "SOURCE_KEY_MULTIPROFILE_WITH_BIOGRAPHIC_CONTRADICTION",
        )

    def test_death_spread_retains_raw_difference_and_descriptive_bucket(self):
        profiles = [
            {"id": 1, "death": "339 هـ"},
            {"id": 2, "death": "151 هـ"},
        ]
        difference = death_pair_differences(profiles)[0]
        self.assertEqual(difference["minimum_absolute_year_difference"], 188)
        self.assertEqual(difference["maximum_absolute_year_difference"], 188)
        self.assertEqual(
            difference["descriptive_bucket"], "LARGE_DIFFERENCE_OVER_25"
        )


class SafetyTests(unittest.TestCase):
    def test_source_audit_does_not_mutate_profiles(self):
        profiles = [{
            "id": 1,
            "global_id": 9,
            "classical_sources": {
                "taqrib": {"entry_id": 2, "grade_en": "reliable"}
            },
        }]
        before = copy.deepcopy(profiles)
        build_source_key_index(profiles)
        self.assertEqual(profiles, before)

    def test_risk_classification_is_deterministic_and_not_identity_verdict(self):
        self.assertEqual(
            profile_risk_class(True, True, False), "MULTIPLE_RISKS"
        )
        self.assertEqual(
            profile_risk_class(False, False, False), "LOW_TARGET_DATA_RISK"
        )
        for value in (
            profile_risk_class(True, False, False),
            profile_risk_class(False, True, False),
            profile_risk_class(False, False, True),
        ):
            self.assertNotIn("SAME_PERSON", value)
            self.assertNotIn("DIFFERENT_PERSON", value)

    def test_expert_visible_schema_has_no_automatic_label_leakage(self):
        columns = set(EXPERT_REVIEW_COLUMNS)
        for forbidden in (
            "assistant_mechanical_triage", "auto_duplicate_label",
            "model_score", "algorithmic_confidence", "expected_answer",
        ):
            self.assertNotIn(forbidden, columns)
        self.assertIn("expert_verdict", columns)

    def test_source_risk_schema_has_no_historical_person_verdict(self):
        columns = set(SOURCE_RISK_COLUMNS)
        self.assertNotIn("same_person", {column.lower() for column in columns})
        self.assertNotIn("different_person", {column.lower() for column in columns})
        self.assertIn("attachment_risk_category", columns)


if __name__ == "__main__":
    unittest.main()
