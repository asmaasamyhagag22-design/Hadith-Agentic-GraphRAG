import unittest

from src.analyze_narrator_unmatched import (
    CENSUS_VISIBLE_COLUMNS,
    UNMATCHED_VISIBLE_COLUMNS,
    apply_transform,
    build_census_review,
    build_token_indexes,
    build_unmatched_review,
    classify_stratum,
    raw_name_features,
    run_ablation,
    token_diagnostics,
)


class StructuralNameFeatureTests(unittest.TestCase):
    def test_raw_features_keep_orthographic_and_format_flags_separate(self):
        features = raw_name_features("  أَبُو بن فتى، (X)  ")
        self.assertTrue(features["has_diacritics"])
        self.assertTrue(features["has_alif_variants"])
        self.assertTrue(features["has_alif_maqsura"])
        self.assertTrue(features["has_bin"])
        self.assertTrue(features["has_punctuation"])
        self.assertTrue(features["has_brackets"])
        self.assertTrue(features["has_latin"])
        self.assertTrue(features["has_repeated_whitespace"])

    def test_transformations_are_controlled_and_composable(self):
        self.assertEqual(apply_transform("إبراهيم", ("alif",)), "ابراهيم")
        self.assertEqual(apply_transform("فتى", ("ya",)), "فتي")
        self.assertEqual(apply_transform("ابن زيد", ("bin",)), "بن زيد")
        self.assertEqual(
            apply_transform("إبن فتى،", ("alif", "bin", "ya", "punctuation")),
            "بن فتي",
        )


class AblationTests(unittest.TestCase):
    def test_ablation_never_assigns_a_resolution_and_measures_instability(self):
        representations = [
            {"profile_id": "1", "normalized": "علي", "tokens": ("علي",), "raw": "علي", "source": "canonical"},
            {"profile_id": "2", "normalized": "على", "tokens": ("على",), "raw": "على", "source": "canonical"},
            {"profile_id": "3", "normalized": "فتي", "tokens": ("فتي",), "raw": "فتي", "source": "canonical"},
        ]
        unmatched = [{"mis_narrator_id": "u", "raw_name": "فتى"}]
        auto = [{
            "mis_narrator_id": "a",
            "raw_name": "على",
            "provisional_resolved_itqan_id": "2",
        }]
        reports, candidates, ya = run_ablation(unmatched, auto, representations)
        self.assertEqual(candidates["u"]["YA_MAQSURA_TO_YA"], {"3"})
        self.assertEqual(reports["YA_MAQSURA_TO_YA"]["previous_unique_to_ambiguous"], 1)
        self.assertFalse(reports["YA_MAQSURA_TO_YA"]["used_for_resolution"])
        self.assertEqual(ya["unique_with_only_ya_maqsura_codepoint_difference"], 1)


class TokenDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.representations = [
            {
                "profile_id": "1",
                "normalized": "عبد الله بن زيد",
                "tokens": ("عبد", "الله", "بن", "زيد"),
                "raw": "عبد الله بن زيد",
                "source": "canonical",
            },
            {
                "profile_id": "2",
                "normalized": "زيد المدني",
                "tokens": ("زيد", "المدني"),
                "raw": "زيد المدني",
                "source": "alias",
            },
        ]
        self.by_profile = {
            "1": [self.representations[0]],
            "2": [self.representations[1]],
        }
        self.indexes = build_token_indexes(self.representations)

    def test_ordered_containment_is_population_diagnostic_only(self):
        contained = token_diagnostics(
            ("عبد", "الله", "بن"), self.indexes, self.by_profile
        )
        self.assertEqual(contained["mis_ordered_subsequence_profiles"], {"1"})
        containing = token_diagnostics(
            ("عبد", "الله", "بن", "زيد", "المدني"),
            self.indexes,
            self.by_profile,
        )
        self.assertIn("1", containing["itqan_ordered_subsequence_profiles"])

    def test_strata_do_not_claim_identity(self):
        feature = raw_name_features("عبد الله بن")
        empty = {
            "mis_ordered_subsequence_profiles": {"1"},
            "itqan_ordered_subsequence_profiles": set(),
            "mis_token_subset_profiles": {"1"},
            "itqan_token_subset_profiles": set(),
        }
        self.assertEqual(
            classify_stratum(feature, set(), set(), empty),
            "MIS_NAME_CONTAINED_IN_ITQAN_NAME",
        )

    def test_documented_short_name_exactness_has_descriptive_priority(self):
        empty = {
            "mis_ordered_subsequence_profiles": set(),
            "itqan_ordered_subsequence_profiles": set(),
            "mis_token_subset_profiles": set(),
            "itqan_token_subset_profiles": set(),
        }
        self.assertEqual(
            classify_stratum(raw_name_features("اسم كامل"), {"42"}, set(), empty),
            "DOCUMENTED_SHORT_NAME_UNIQUE_CANDIDATE",
        )
        self.assertEqual(
            classify_stratum(
                raw_name_features("اسم كامل"), {"42", "43"}, set(), empty
            ),
            "DOCUMENTED_SHORT_NAME_MULTIPLE_CANDIDATES",
        )


class ReviewArtifactTests(unittest.TestCase):
    def test_census_contains_every_input_and_hides_selection_metadata(self):
        records = []
        profiles = {}
        for index in range(1, 82):
            profile_id = str(index)
            profiles[profile_id] = {
                "id": profile_id,
                "full_name": f"name {index}",
                "namings": [],
                "confidence": "high",
            }
            records.append({
                "mis_narrator_id": profile_id,
                "raw_name": f"name {index}",
                "provisional_tier": "EXACT_RESOLVED",
                "provisional_resolved_itqan_id": profile_id,
                "candidates": [{
                    "itqan_id": profile_id,
                    "candidate_source": ["canonical_exact"],
                    "itqan_identity_confidence": "high",
                }],
            })
        visible, hidden = build_census_review(records, profiles)
        self.assertEqual(len(visible), 81)
        self.assertEqual(set(visible[0]), set(CENSUS_VISIBLE_COLUMNS))
        self.assertNotIn("provisional_tier", visible[0])
        self.assertNotIn("automatic_confidence", visible[0])
        self.assertTrue(all(not row["manual_verdict"] for row in visible))
        self.assertEqual(len(hidden), 81)

    def test_unmatched_sample_is_reproducible_and_hides_scores_and_strata(self):
        profiles = {"1": {"id": "1", "full_name": "زيد", "kunya": "", "nasab": "", "death": ""}}
        candidate = {
            "diagnostic_label": "DIAGNOSTIC_CANDIDATE",
            "itqan_id": "1",
            "canonical_name": "زيد",
            "matched_variants": ["زيد"],
            "methods": {"TOKEN_JACCARD": {"rank": 1, "score": 0.5}},
            "structural_relationships": {},
            "teacher_support": "UNKNOWN",
            "student_support": "UNKNOWN",
        }
        records = [{
            "mis_narrator_id": str(index),
            "raw_name": f"name {index}",
            "short_name": f"short {index}",
            "diagnostic_stratum": "NO_EXACT_STRUCTURAL_CANDIDATE",
            "diagnostic_candidates": [candidate],
            "name_features": {},
            "token_diagnostic_counts": {},
            "ablation_candidate_ids": {},
        } for index in range(30)]
        first = build_unmatched_review(records, profiles, seed=9)
        second = build_unmatched_review(records, profiles, seed=9)
        self.assertEqual(first, second)
        visible = first[0]
        self.assertEqual(set(visible[0]), set(UNMATCHED_VISIBLE_COLUMNS))
        self.assertNotIn("diagnostic_stratum", visible[0])
        self.assertNotIn("score", visible[0]["diagnostic_candidate_evidence_json"])
        self.assertTrue(all(not row["diagnostic_verdict"] for row in visible))


if __name__ == "__main__":
    unittest.main()
