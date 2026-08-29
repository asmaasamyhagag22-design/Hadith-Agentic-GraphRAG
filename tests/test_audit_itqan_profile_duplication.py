import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.audit_itqan_profile_duplication import (
    HIDDEN_REVIEW_COLUMNS,
    VISIBLE_REVIEW_COLUMNS,
    aggregate_suspected_profile_sets,
    build_exact_group_indexes,
    build_group_record,
    candidate_pair_pool,
    classify_pair,
    death_contradiction,
    file_hashes,
    logical_identity_keys,
    pair_evidence,
    profile_evidence,
    source_identifiers,
    stable_group_id,
    tri_state_equal,
    validate_recorded_artifact_hashes,
)


def indexes(profiles):
    return build_exact_group_indexes(profiles)


class ProvenanceExtractionTests(unittest.TestCase):
    def test_source_ids_are_preserved_as_separate_record_keys(self):
        profile = {
            "id": 12,
            "global_id": 34,
            "gk_id": "0056",
            "provenance": {
                "origin": "merged",
                "kaggle_id": 34,
                "arsanad_id": 12,
            },
        }
        extracted = source_identifiers(profile)
        self.assertEqual(extracted["itqan_profile_id"], "12")
        self.assertEqual(extracted["global_id"], "34")
        self.assertEqual(extracted["gk_id"], "0056")
        self.assertEqual(extracted["provenance_arsanad_id"], "12")
        self.assertIn(("KAGGLE_SCHOLAR_INDX", "34"), logical_identity_keys(profile))
        self.assertNotIn(("ARSANAD_PROFILE_ROW", "12"), logical_identity_keys(profile))

    def test_classical_source_id_and_grade_are_not_collapsed(self):
        profile = {
            "id": 1,
            "full_name": "زيد",
            "classical_sources": {
                "source_a": {
                    "entry_id": 7,
                    "grade_en": "reliable",
                    "grade_ar": "ثقة",
                },
                "source_b": {
                    "entry_id": 7,
                    "grade_en": "weak",
                    "grade_ar": "ضعيف",
                },
            },
        }
        evidence = profile_evidence(profile)
        self.assertEqual(len(evidence["classical_sources"]), 2)
        self.assertEqual(
            {entry["source"] for entry in evidence["classical_sources"]},
            {"source_a", "source_b"},
        )
        self.assertEqual(
            {entry["grade_en"] for entry in evidence["classical_sources"]},
            {"reliable", "weak"},
        )


class MissingAndContradictionTests(unittest.TestCase):
    def test_unknown_is_not_false(self):
        self.assertEqual(tri_state_equal(None, "زيد"), "UNKNOWN")
        self.assertEqual(death_contradiction(None, "100 هـ"), "UNKNOWN")
        self.assertEqual(tri_state_equal("زيد", "عمرو"), "FALSE")

    def test_death_contradiction_uses_explicit_tolerance(self):
        self.assertEqual(death_contradiction("100 هـ", "106 هـ"), "TRUE")
        self.assertEqual(death_contradiction("100 هـ", "105 هـ"), "FALSE")
        self.assertEqual(death_contradiction("100 هـ : 110 هـ", "114 هـ"), "FALSE")

    def test_shared_source_key_plus_contradiction_remains_unresolved(self):
        profiles = [
            {"id": 1, "full_name": "زيد", "death": "100 هـ", "global_id": 9},
            {"id": 2, "full_name": "زيد", "death": "200 هـ", "global_id": 9},
        ]
        evidence = pair_evidence(*profiles)
        self.assertTrue(evidence["shared_upstream_record_keys"])
        self.assertEqual(evidence["death_contradiction"], "TRUE")
        self.assertEqual(classify_pair(evidence), "UNRESOLVED_PROFILE_MULTIPLICITY")


class ExactGroupingTests(unittest.TestCase):
    def setUp(self):
        self.profiles = [
            {"id": 3, "full_name": "زَيْـد بن عمرو", "namings": ["أبو زيد"]},
            {"id": 1, "full_name": "زيد بن عمرو", "namings": ["زيد"]},
            {"id": 2, "full_name": "خالد", "namings": ["أبو زيد"]},
        ]

    def test_duplicate_normalized_name_grouping_is_exact_and_reproducible(self):
        first = indexes(self.profiles)
        second = indexes(list(reversed(self.profiles)))
        self.assertEqual(first[1], second[1])
        self.assertEqual(first[2], second[2])
        self.assertEqual(first[1]["زيد بن عمرو"], {"1", "3"})
        self.assertEqual(first[2]["أبو زيد"], {"2", "3"})

    def test_stable_group_id_is_order_independent_and_key_sensitive(self):
        first = stable_group_id("kind", "زيد", ["10", "2"])
        second = stable_group_id("kind", "زيد", ["2", "10", "2"])
        changed = stable_group_id("kind", "عمرو", ["2", "10"])
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)

    def test_group_record_is_deterministic(self):
        by_id, canonical, representations, sources = indexes(self.profiles)
        first = build_group_record(
            "زيد بن عمرو", representations["زيد بن عمرو"],
            by_id, canonical, sources,
        )
        second = build_group_record(
            "زيد بن عمرو", set(reversed(sorted(representations["زيد بن عمرو"]))),
            by_id, canonical, sources,
        )
        self.assertEqual(first, second)

    def test_multiple_keys_for_same_profile_set_are_not_double_counted(self):
        group = {
            "group_id": "a",
            "itqan_profile_ids": ["1", "2"],
            "candidate_status": "POSSIBLE_DUPLICATE_PROFILE",
            "conceptual_class": "DUPLICATE_PROFILE_STRONGLY_SUPPORTED",
            "evidence": {
                "shared_upstream_record_keys": [{"value": "9"}],
                "shared_classical_source_entries": [],
            },
            "contradictions": {
                "contradictory_pair_count": 0,
                "contradictory_profile_ids": [],
            },
        }
        duplicate_key = {**group, "group_id": "b"}
        aggregated = aggregate_suspected_profile_sets([group, duplicate_key])
        self.assertEqual(len(aggregated), 1)
        self.assertEqual(aggregated[0]["source_group_ids"], ["a", "b"])


class ReviewArtifactTests(unittest.TestCase):
    def test_pair_pool_has_no_self_pairs(self):
        profiles = [
            {"id": 1, "full_name": "زيد", "kunya": "أبو زيد"},
            {"id": 2, "full_name": "زيد", "kunya": "أبو زيد"},
        ]
        by_id, canonical, representations, sources = indexes(profiles)
        group = build_group_record(
            "زيد", representations["زيد"], by_id, canonical, sources
        )
        pools = candidate_pair_pool([group], by_id, {"1"})
        pairs = [item[1:] for values in pools.values() for item in values]
        self.assertTrue(pairs)
        self.assertTrue(all(left != right for left, right in pairs))

    def test_visible_schema_has_no_automatic_metadata_leakage(self):
        visible = set(VISIBLE_REVIEW_COLUMNS)
        hidden = set(HIDDEN_REVIEW_COLUMNS)
        for forbidden in (
            "automatic_conceptual_class", "candidate_score",
            "grouping_confidence", "algorithmic_rank", "sampling_stratum",
        ):
            self.assertNotIn(forbidden, visible)
        self.assertIn("automatic_conceptual_class", hidden)
        self.assertNotIn("confidence", profile_evidence({"id": 1, "confidence": "A"}))


class FrozenArtifactTests(unittest.TestCase):
    def test_hash_audit_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frozen.txt"
            path.write_text("immutable\n", encoding="utf-8")
            before = file_hashes([path])
            after = file_hashes([path])
            self.assertEqual(before, after)
            self.assertEqual(path.read_text(encoding="utf-8"), "immutable\n")

    def test_recorded_frozen_hash_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frozen = root / "frozen.txt"
            frozen.write_text("immutable\n", encoding="utf-8")
            expected = hashlib.sha256(frozen.read_bytes()).hexdigest()
            audit = root / "audit.json"
            audit.write_text(json.dumps({
                "output_artifacts": {
                    "frozen.txt": {"path": str(frozen), "sha256": expected}
                }
            }), encoding="utf-8")
            self.assertEqual(
                validate_recorded_artifact_hashes([audit]),
                {str(frozen): expected},
            )
            frozen.write_text("changed\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                validate_recorded_artifact_hashes([audit])


if __name__ == "__main__":
    unittest.main()
