import unittest

from src.build_narrator_candidates import (
    HIDDEN_REVIEW_COLUMNS,
    VISIBLE_REVIEW_COLUMNS,
    build_name_indexes,
    candidate_csv_rows,
    build_review_sample,
    generate_candidates,
    id_normalization_audit,
    normalize_mis_id,
    provisional_tier,
    relationship_support,
)
from src.audit_linkage_validation_identity import normalize_narrow_identity


class IdentifierNormalizationTests(unittest.TestCase):
    def test_safe_mixed_storage_types(self):
        self.assertEqual(normalize_mis_id(123), "123")
        self.assertEqual(normalize_mis_id(" 123 "), "123")
        self.assertEqual(normalize_mis_id("abc"), "abc")
        self.assertEqual(normalize_mis_id("001"), "001")
        self.assertIsNone(normalize_mis_id(None))
        self.assertIsNone(normalize_mis_id("   "))

    def test_collision_after_normalization_is_reported(self):
        nodes = [
            {"NarratorID_Mapped": 123},
            {"NarratorID_Mapped": "123"},
        ]
        report = id_normalization_audit(nodes)
        self.assertIn("123", report["canonical_collisions"])
        self.assertEqual(report["cardinality_change"], 1)


class NameNormalizationTests(unittest.TestCase):
    def test_narrow_normalization_preserves_base_letter_distinctions(self):
        self.assertEqual(normalize_narrow_identity("زَيْـد"), "زيد")
        self.assertNotEqual(
            normalize_narrow_identity("أحمد"),
            normalize_narrow_identity("احمد"),
        )
        self.assertNotEqual(
            normalize_narrow_identity("فتى"),
            normalize_narrow_identity("فتي"),
        )


class CandidateGenerationTests(unittest.TestCase):
    def setUp(self):
        self.profiles = [
            {"id": 1, "full_name": "زيد", "namings": ["أبو زيد"]},
            {"id": 2, "full_name": "عمرو", "namings": ["أبو زيد"]},
            {"id": 3, "full_name": "خالد", "namings": ["أبو خالد"]},
        ]
        self.indexes = build_name_indexes(self.profiles)

    def test_exact_and_alias_collisions_are_preserved(self):
        nodes = [
            {
                "NarratorID_Mapped": 10,
                "NarratorNameAr": "زيد",
                "NarratorGeneration": "Follower",
                "Gender": "Male",
            },
            {
                "NarratorID_Mapped": 11,
                "NarratorNameAr": "أبو زيد",
                "NarratorGeneration": "Follower",
                "Gender": "Male",
            },
            {
                "NarratorID_Mapped": 12,
                "NarratorNameAr": "أبو خالد",
                "NarratorGeneration": "Follower",
                "Gender": "Male",
            },
        ]
        records, _ = generate_candidates(nodes, self.indexes)
        self.assertEqual(records[0]["provisional_tier"], "EXACT_RESOLVED")
        self.assertEqual(records[1]["provisional_tier"], "AMBIGUOUS")
        self.assertEqual(records[1]["candidate_count"], 2)
        self.assertEqual(records[2]["provisional_tier"], "ALIAS_RESOLVED")

    def test_tier_never_resolves_multiple_candidates(self):
        tier, profile_id = provisional_tier({"1"}, {"1"}, {"1", "2"})
        self.assertEqual(tier, "AMBIGUOUS")
        self.assertIsNone(profile_id)

    def test_candidate_generation_and_csv_projection_are_deterministic(self):
        nodes = [{
            "NarratorID_Mapped": " 10 ",
            "NarratorNameAr": "زَيْـد",
            "NarratorGeneration": None,
            "Gender": None,
        }]
        first, first_counts = generate_candidates(nodes, self.indexes)
        second, second_counts = generate_candidates(nodes, self.indexes)
        self.assertEqual(first, second)
        self.assertEqual(first_counts, second_counts)
        self.assertEqual(candidate_csv_rows(first), candidate_csv_rows(second))
        self.assertEqual(first[0]["provisional_tier"], "NORMALIZED_RESOLVED")


class FeatureSemanticsTests(unittest.TestCase):
    def test_missing_relationship_evidence_is_unknown_not_false(self):
        self.assertEqual(relationship_support({"1"}, set()), "UNKNOWN")
        self.assertEqual(relationship_support(set(), {"1"}), "UNKNOWN")
        self.assertEqual(relationship_support({"1"}, {"1"}), "TRUE")


class ReviewSamplingTests(unittest.TestCase):
    def test_sampling_is_reproducible_and_visible_rows_hide_auto_metadata(self):
        profiles = [
            {"id": index, "full_name": f"name-{index}", "namings": []}
            for index in range(1, 101)
        ]
        indexes = build_name_indexes(profiles)
        records = []
        for index in range(1, 101):
            records.append({
                "mis_narrator_id": str(index),
                "raw_name": f"name-{index}",
                "provisional_tier": (
                    "EXACT_RESOLVED" if index <= 50 else "ALIAS_RESOLVED"
                ),
                "provisional_resolved_itqan_id": str(index),
                "candidate_count": 1,
                "risk_flags": [],
                "candidates": [{
                    "itqan_id": str(index),
                    "candidate_source": ["canonical_exact"],
                    "itqan_identity_confidence": "high",
                }],
            })

        visible, hidden, meta = build_review_sample(records, indexes, seed=7)
        visible_again, hidden_again, _ = build_review_sample(records, indexes, seed=7)

        self.assertEqual(visible, visible_again)
        self.assertEqual(hidden, hidden_again)
        self.assertEqual(set(visible[0]), set(VISIBLE_REVIEW_COLUMNS))
        self.assertEqual(set(hidden[0]), set(HIDDEN_REVIEW_COLUMNS))
        self.assertNotIn("auto_tier", visible[0])
        self.assertNotIn("candidate_confidence", visible[0])
        self.assertTrue(all(not row["manual_verdict"] for row in visible))
        self.assertIn("NEEDS_DOMAIN_EXPERT", meta["allowed_manual_verdicts"])


if __name__ == "__main__":
    unittest.main()
