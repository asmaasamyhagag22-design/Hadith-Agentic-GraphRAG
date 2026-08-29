import unittest

from src.profile_mis import (
    mapping_integrity,
    normalize_identifier,
    ordering_diagnostics,
    quick_similarity,
    similarity,
)


class IdentifierTests(unittest.TestCase):
    def test_mixed_identifier_types_normalize_safely(self):
        self.assertEqual(normalize_identifier(12), "12")
        self.assertEqual(normalize_identifier(12.0), "12")
        self.assertEqual(normalize_identifier(" 12 "), "12")
        self.assertIsNone(normalize_identifier(None))
        self.assertIsNone(normalize_identifier(""))


class SimilarityTests(unittest.TestCase):
    def test_true_ratio_is_not_quick_ratio_upper_bound(self):
        ours = "ا ب ج د"
        theirs = "د ج ب ا"
        self.assertLess(similarity(ours, theirs), quick_similarity(ours, theirs))


class IntegrityTests(unittest.TestCase):
    def test_cardinality_is_measured_without_forcing_one_to_one(self):
        pairs = [
            {
                "local_position": 1, "mis_position": 1, "accepted": True,
                "candidate_status": "unique", "quick_similarity": 1.0,
                "our_idInBook": 1, "mis_HadithNo": 1,
            },
            {
                "local_position": 2, "mis_position": 1, "accepted": True,
                "candidate_status": "unique", "quick_similarity": 1.0,
                "our_idInBook": 2, "mis_HadithNo": 1,
            },
            {
                "local_position": 3, "mis_position": 3, "accepted": False,
                "candidate_status": "unique", "quick_similarity": 0.5,
                "our_idInBook": 3, "mis_HadithNo": 3,
            },
        ]
        result = mapping_integrity(pairs, corpus_size=3, mis_size=3)
        self.assertEqual(result["accepted_pairs"], 2)
        self.assertEqual(result["many_to_one_mis_records"], 1)
        self.assertEqual(result["one_to_one_mappings"], 0)
        self.assertEqual(result["local_unmatched_under_acceptance_rule"], 1)

    def test_collection_rotation_is_reported_not_used_as_a_link_rule(self):
        accepted = [
            {"local_position": 1, "mis_position": 3, "our_idInBook": 1, "mis_HadithNo": 3},
            {"local_position": 2, "mis_position": 4, "our_idInBook": 2, "mis_HadithNo": 4},
            {"local_position": 3, "mis_position": 1, "our_idInBook": 3, "mis_HadithNo": 1},
            {"local_position": 4, "mis_position": 2, "our_idInBook": 4, "mis_HadithNo": 2},
        ]
        result = ordering_diagnostics(accepted, mis_size=4)
        self.assertEqual(len(result["detected_collection_rotations"]), 1)
        self.assertEqual(
            result["rotation_unwrapped_order"]["spearman_rank_correlation"],
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
