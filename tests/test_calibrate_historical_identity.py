import copy
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.calibrate_historical_identity import (
    BLINDED_PACKET_SEED,
    BLINDED_VISIBLE_COLUMNS,
    CALIBRATION_CASES_CSV,
    IDENTIFIER_KEYS,
    LEAKING_COLUMNS,
    PROCESSED_DIR,
    EVIDENCE_TAXONOMY,
    HISTORICAL_NARRATOR_CONTRACT,
    NARRATOR_81_PATH,
    REVIEWER_COLUMNS,
    RULES_NOT_TESTABLE_ON_GROUPS,
    build_blinded_packet,
    calibrate_case,
    death_relation,
    evaluate_rule_safety,
    evidence_dependency_groups,
    independent_evidence,
    packet_leakage_report,
    redact_identifiers,
    rule_definitions,
    rule_triggers,
    scalar_relation,
    write_calibration_cases,
)

FROZEN_LINKAGE = PROCESSED_DIR / "mis_linkage_accepted_v1.jsonl"
FROZEN_TIERS_PATH = PROCESSED_DIR / "narrator_resolution_candidates.csv"
FROZEN_LINKAGE_SHA256 = (
    "9c3a48e7a0af4f0df1cd9250f49a90f343228b614587196fcf2fa6fbfa572c77"
)
FROZEN_TIERS = {
    "UNMATCHED": 2001,
    "EXACT_RESOLVED": 30,
    "ALIAS_RESOLVED": 51,
    "AMBIGUOUS": 10,
}


def profile(**overrides):
    base = {
        "itqan_profile_id": "1",
        "full_name": "محمد بن النضر",
        "kunya": "أبو بكر",
        "nasab": "العامري",
        "city": "أصبهان",
        "death": "291 هـ",
        "tabaqat": None,
        "generation": None,
        "teachers": [],
        "students": [],
        "source_records": [],
    }
    base.update(overrides)
    return base


def case_row(evidence_a, evidence_b, contradictions=None, missing=None):
    return {
        "expert_review_id": "ITQ-EXPERT-TEST",
        "source_review_id": "ITQ-DUP-TEST",
        "itqan_profile_a_id": evidence_a["itqan_profile_id"],
        "itqan_profile_b_id": evidence_b["itqan_profile_id"],
        "profile_a_full_evidence_json": json.dumps(evidence_a, ensure_ascii=False),
        "profile_b_full_evidence_json": json.dumps(evidence_b, ensure_ascii=False),
        "contradictions_json": json.dumps(
            contradictions or {"death_differences": [], "fields": []}, ensure_ascii=False
        ),
        "missing_information_json": json.dumps(missing or {}, ensure_ascii=False),
    }


class MissingEvidenceTests(unittest.TestCase):
    """الناقص يفضل UNKNOWN — ما يتحوّلش لاختلاف."""

    def test_missing_value_is_unknown_not_a_difference(self):
        self.assertEqual(scalar_relation(None, "أبو بكر"), "UNKNOWN")
        self.assertEqual(scalar_relation("", "أبو بكر"), "UNKNOWN")
        self.assertEqual(scalar_relation("-", "أبو بكر"), "UNKNOWN")
        self.assertEqual(scalar_relation(None, None), "UNKNOWN")

    def test_absent_death_evidence_is_unknown(self):
        self.assertEqual(death_relation(None), "UNKNOWN")
        self.assertEqual(death_relation({}), "UNKNOWN")
        self.assertEqual(
            death_relation({"minimum_absolute_year_difference": None}), "UNKNOWN"
        )

    def test_populated_difference_is_not_called_a_contradiction(self):
        # A different kunya form is a difference; whether it is incompatible is
        # a rijal question, so the mechanical layer must not assert it.
        self.assertEqual(scalar_relation("أبو بكر", "أبو عبد الله"), "DIFFERENT")


class EvidenceDependenceTests(unittest.TestCase):
    """الأدلة اللي من نفس المصدر ما تتعدّش مرتين."""

    def test_biography_fields_form_one_dependency_group(self):
        groups = evidence_dependency_groups(profile())
        biography = [g for g in groups if g["group_kind"] == "PROFILE_BIOGRAPHY"]

        self.assertEqual(len(biography), 1)
        self.assertFalse(biography[0]["independent"])
        self.assertIn("full_name", biography[0]["field_paths"])
        self.assertIn("death", biography[0]["field_paths"])

    def test_row_provenance_namespace_is_never_independent(self):
        groups = evidence_dependency_groups(profile(source_records=[
            {"source_namespace": "arsanad:profile_row", "source_record_id": "1",
             "field_paths": ["provenance.arsanad_id"]},
        ]))

        self.assertTrue(all(not group["independent"] for group in groups))

    def test_shared_independent_record_is_counted_once_not_per_field(self):
        record = {
            "source_namespace": "classical:taqrib", "source_record_id": "5024",
            "field_paths": ["classical_sources.taqrib.grade_ar",
                            "classical_sources.taqrib.grade_en"],
        }
        groups_a = evidence_dependency_groups(profile(source_records=[record]))
        groups_b = evidence_dependency_groups(
            profile(itqan_profile_id="2", source_records=[copy.deepcopy(record)])
        )

        result = independent_evidence(groups_a, groups_b)

        self.assertEqual(result["shared_independent_source_records"], 1)

    def test_row_provenance_does_not_create_shared_independent_evidence(self):
        groups_a = evidence_dependency_groups(profile(source_records=[
            {"source_namespace": "arsanad:profile_row", "source_record_id": "7",
             "field_paths": []},
        ]))
        groups_b = evidence_dependency_groups(profile(
            itqan_profile_id="2",
            source_records=[{"source_namespace": "arsanad:profile_row",
                             "source_record_id": "7", "field_paths": []}],
        ))

        self.assertEqual(
            independent_evidence(groups_a, groups_b)["shared_independent_source_records"], 0
        )


class ContradictionPreservationTests(unittest.TestCase):
    """الاختلاف في الوفاة يتحفظ ولا يتصلح."""

    def test_death_variation_is_graded_not_collapsed(self):
        self.assertEqual(
            death_relation({"exact_equal_death_text": True}), "SAME_REPORTED_DEATH"
        )
        self.assertEqual(
            death_relation({"minimum_absolute_year_difference": 3}),
            "SMALL_REPORTED_VARIATION",
        )
        self.assertEqual(
            death_relation({"minimum_absolute_year_difference": 20}),
            "MATERIAL_REPORTED_VARIATION",
        )
        self.assertEqual(
            death_relation({"minimum_absolute_year_difference": 188}),
            "EXTREME_REPORTED_VARIATION",
        )

    def test_both_reported_deaths_survive_into_the_case_record(self):
        row = case_row(
            profile(death="339 هـ"),
            profile(itqan_profile_id="2", death="151 هـ"),
            contradictions={"death_differences": [{
                "profile_a_death": "339 هـ", "profile_b_death": "151 هـ",
                "minimum_absolute_year_difference": 188,
                "exact_equal_death_text": False,
            }], "fields": []},
        )
        record = calibrate_case(row)

        self.assertEqual(record["death_evidence_a"], "339 هـ")
        self.assertEqual(record["death_evidence_b"], "151 هـ")
        self.assertEqual(record["death_relation"], "EXTREME_REPORTED_VARIATION")
        self.assertEqual(record["mechanical_status"], "SOURCE_DATA_CONTRADICTION")

    def test_extreme_death_separation_is_not_called_impossible(self):
        row = case_row(
            profile(death="339 هـ"),
            profile(itqan_profile_id="2", death="151 هـ"),
            contradictions={"death_differences": [{
                "minimum_absolute_year_difference": 188,
                "exact_equal_death_text": False,
            }], "fields": []},
        )

        self.assertEqual(
            calibrate_case(row)["chronology_check"],
            "SUSPICIOUS_DEATH_SEPARATION_NOT_IMPOSSIBLE",
        )


class NoIdentityVerdictTests(unittest.TestCase):
    """المخرج ما يحتويش حكم هوية تاريخية."""

    def test_no_case_status_asserts_a_historical_person_verdict(self):
        allowed = {
            "MECHANICALLY_INCOMPATIBLE", "STRONGLY_COMPATIBLE_BUT_UNCONFIRMED",
            "INSUFFICIENT_EVIDENCE", "SOURCE_DATA_CONTRADICTION",
            "REQUIRES_DOMAIN_EXPERT",
        }
        record = calibrate_case(case_row(profile(), profile(itqan_profile_id="2")))

        self.assertIn(record["mechanical_status"], allowed)
        self.assertNotIn("SAME_PERSON", record["mechanical_status"])
        self.assertNotIn("DIFFERENT_PERSON", record["mechanical_status"])

    def test_reviewer_fields_are_generated_blank(self):
        record = calibrate_case(case_row(profile(), profile(itqan_profile_id="2")))

        for column in REVIEWER_COLUMNS:
            self.assertEqual(record[column], "")

    def test_generator_refuses_to_overwrite_reviewer_verdicts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.csv"
            record = calibrate_case(case_row(profile(), profile(itqan_profile_id="2")))

            write_calibration_cases([record], path)
            adjudicated = dict(record, reviewer_verdict="SAME_HISTORICAL_PERSON")
            write_calibration_cases([adjudicated], path)

            with self.assertRaises(SystemExit):
                write_calibration_cases([record], path)

    def test_identity_bearing_evidence_category_is_empty(self):
        # Nothing in v1.20 identifies a person independently of the name.
        self.assertEqual(EVIDENCE_TAXONOMY["A_IDENTITY_BEARING"]["members"], [])


class NoHistoricalNarratorTests(unittest.TestCase):
    """طبقة الهوية موصوفة، مش متبنية."""

    def test_contract_is_described_but_not_instantiated(self):
        self.assertFalse(HISTORICAL_NARRATOR_CONTRACT["instantiated"])

    def test_contract_forbids_grade_aggregation_and_merging(self):
        forbidden = " ".join(HISTORICAL_NARRATOR_CONTRACT["forbidden"])

        self.assertIn("grade", forbidden)
        self.assertIn("merged profile payloads", forbidden)

    def test_contract_supports_abstention_states(self):
        statuses = HISTORICAL_NARRATOR_CONTRACT["required_fields"]["identity_status"]

        self.assertIn("AMBIGUOUS", statuses)
        self.assertIn("QUARANTINED", statuses)
        self.assertIn("PROVISIONAL", statuses)


class NoMutationTests(unittest.TestCase):
    """القراءة ما بتغيّرش أي بروفايل أو درجة."""

    def test_calibration_does_not_mutate_the_input_evidence(self):
        evidence_a = profile()
        evidence_b = profile(itqan_profile_id="2")
        before = copy.deepcopy((evidence_a, evidence_b))

        calibrate_case(case_row(evidence_a, evidence_b))

        self.assertEqual((evidence_a, evidence_b), before)

    def test_grades_are_never_aggregated_into_the_case_record(self):
        record = calibrate_case(case_row(
            profile(source_records=[{
                "source_namespace": "classical:taqrib", "source_record_id": "5024",
                "field_paths": ["classical_sources.taqrib.grade_ar"],
            }]),
            profile(itqan_profile_id="2"),
        ))

        self.assertNotIn("grade", record)
        self.assertNotIn("narrator_grade", record)


class RuleSafetyTests(unittest.TestCase):
    """القواعد قابلة للتكرار، ومقاسة على مجموعات الفشل المعروفة."""

    @staticmethod
    def group(**overrides):
        base = {
            "conceptual_class": "UNRESOLVED_PROFILE_MULTIPLICITY",
            "grouping_kind": "NARROW_CANONICAL_NAME",
            "itqan_profile_ids": ["10", "11"],
            "contradictions": {"contradictory_pair_count": 0},
            "evidence": {},
            "profiles": [
                {"normalized_canonical_name": "محمد", "death": "291 هـ",
                 "upstream_source_identifiers": {"origin": "classical"}},
                {"normalized_canonical_name": "محمد", "death": "291 هـ",
                 "upstream_source_identifiers": {"origin": "classical"}},
            ],
        }
        base.update(overrides)
        return base

    def test_rule_candidates_are_deterministic(self):
        self.assertEqual(rule_definitions(), rule_definitions())

        group = self.group()
        first = {rule["rule_id"]: rule_triggers(rule["rule_id"], group)
                 for rule in rule_definitions()}
        second = {rule["rule_id"]: rule_triggers(rule["rule_id"], group)
                  for rule in rule_definitions()}

        self.assertEqual(first, second)

    def test_name_only_rule_triggers_on_strongly_distinct_sets(self):
        # R-07 is the collision driver; the safety measurement must expose it.
        distinct = self.group(conceptual_class="DISTINCT_PERSON_STRONGLY_SUPPORTED")
        result = evaluate_rule_safety("R-07", [distinct])

        self.assertEqual(result["triggered_on_strongly_distinct_sets"], 1)

    def test_contradiction_groups_cannot_become_automatic_positive_identities(self):
        contradicted = self.group(
            evidence={"shared_death_values": {"291 هـ": ["10", "11"]}},
            contradictions={"contradictory_pair_count": 3},
        )

        self.assertFalse(rule_triggers("R-02", contradicted))
        self.assertFalse(rule_triggers("R-05", contradicted))

    def test_adjacent_id_rule_requires_populated_death(self):
        missing_death = self.group(profiles=[
            {"normalized_canonical_name": "محمد", "death": "-",
             "upstream_source_identifiers": {"origin": "classical"}},
            {"normalized_canonical_name": "محمد", "death": "-",
             "upstream_source_identifiers": {"origin": "classical"}},
        ])

        self.assertFalse(rule_triggers("R-04", missing_death))
        self.assertTrue(rule_triggers("R-04", self.group()))

    def test_untestable_rule_is_reported_as_untested_not_as_zero_triggers(self):
        result = evaluate_rule_safety("R-03", [self.group()])

        self.assertFalse(result["tested_on_group_population"])
        self.assertNotIn("groups_triggered", result)
        self.assertIn("R-03", RULES_NOT_TESTABLE_ON_GROUPS)

    def test_every_rejected_rule_records_why(self):
        for rule in rule_definitions():
            if rule["status"] == "REJECTED":
                self.assertTrue(rule.get("rejection_reason"))

    def test_no_rule_is_marked_production(self):
        allowed = {
            "SAFE_FOR_FURTHER_VALIDATION", "NEEDS_MORE_EVIDENCE",
            "REJECTED", "DOMAIN_EXPERT_REQUIRED",
        }

        for rule in rule_definitions():
            self.assertIn(rule["status"], allowed)


class BlindedPacketTests(unittest.TestCase):
    """الحزمة المستقبلية ما تسمحش بالوصول للتصنيف الآلي."""

    @staticmethod
    def expert_rows(count=3):
        rows = []
        for index in range(count):
            evidence_a = profile(itqan_profile_id=str(100 + index))
            evidence_b = profile(itqan_profile_id=str(200 + index))
            row = case_row(evidence_a, evidence_b)
            row["expert_review_id"] = f"ITQ-EXPERT-{index:04d}"
            row["source_review_id"] = f"ITQ-DUP-{index:04d}"
            row.update({
                "relevant_source_names_json": "[]",
                "source_specific_name_forms_json": "{}",
                "deaths_json": '["291 هـ","291 هـ"]',
                "kunyahs_json": '["أبو بكر","أبو بكر"]',
                "nasab_json": '["العامري","العامري"]',
                "teachers_students_json": "{}",
                "generation_tabaqa_json": "{}",
            })
            rows.append(row)
        return rows

    def packet(self):
        rows = self.expert_rows()
        calibrated = [calibrate_case(row) for row in rows]
        return build_blinded_packet(rows, calibrated)

    def test_visible_rows_use_opaque_sequential_ids(self):
        visible, _ = self.packet()
        ids = [row["opaque_review_id"] for row in visible]

        self.assertEqual(ids, ["HIR-000001", "HIR-000002", "HIR-000003"])
        self.assertEqual(len(set(ids)), len(ids))

    def test_visible_packet_exposes_no_join_key_to_the_labelled_triage(self):
        visible, _ = self.packet()
        blob = json.dumps(visible, ensure_ascii=False)

        for token in ("ITQ-DUP", "ITQ-EXPERT", "itqan_profile_id",
                      "source_review_id", "itqan_profile_a_id"):
            self.assertNotIn(token, blob)

    def test_visible_columns_carry_no_automatic_label_or_score(self):
        self.assertEqual(set(BLINDED_VISIBLE_COLUMNS) & LEAKING_COLUMNS, set())

    def test_redaction_strips_identifiers_at_any_depth(self):
        payload = {
            "death": "291 هـ",
            "itqan_profile_id": "2527",
            "records": [{"source_record_id": "1", "profile_id": "2527", "grade": "ثقة"}],
        }
        redacted = redact_identifiers(payload)

        self.assertNotIn("itqan_profile_id", redacted)
        self.assertNotIn("profile_id", redacted["records"][0])
        self.assertEqual(redacted["death"], "291 هـ")
        self.assertEqual(redacted["records"][0]["grade"], "ثقة")

    def test_redaction_keeps_the_evidence_a_specialist_needs(self):
        visible, _ = self.packet()
        payload = json.loads(visible[0]["profile_a_evidence_json"])

        for field in ("full_name", "kunya", "nasab", "city", "death"):
            self.assertIn(field, payload)

    def test_reviewer_fields_are_blank_in_the_visible_packet(self):
        visible, _ = self.packet()

        for row in visible:
            self.assertEqual(row["expert_verdict"], "")
            self.assertEqual(row["reviewer_notes"], "")

    def test_hidden_mapping_covers_every_visible_row(self):
        visible, hidden = self.packet()

        self.assertEqual(
            {row["opaque_review_id"] for row in visible},
            {row["opaque_review_id"] for row in hidden},
        )
        for row in hidden:
            self.assertTrue(row["itqan_profile_a_id"])
            self.assertTrue(row["source_review_id"])

    def test_leakage_report_is_clean_for_the_blinded_packet(self):
        visible, _ = self.packet()
        report = packet_leakage_report(visible)

        self.assertEqual(report["leaking_columns_present"], [])
        self.assertEqual(report["identifier_keys_in_payloads"], [])
        self.assertTrue(report["reviewer_columns_blank"])

    def test_leakage_report_detects_an_introduced_label(self):
        visible, _ = self.packet()
        leaked = [dict(row, mechanical_status="STRONGLY_COMPATIBLE") for row in visible]

        self.assertIn("mechanical_status",
                      packet_leakage_report(leaked)["leaking_columns_present"])

    def test_row_order_is_deterministic_under_the_recorded_seed(self):
        rows = self.expert_rows(5)
        calibrated = [calibrate_case(row) for row in rows]

        first, _ = build_blinded_packet(rows, calibrated, seed=BLINDED_PACKET_SEED)
        second, _ = build_blinded_packet(rows, calibrated, seed=BLINDED_PACKET_SEED)

        self.assertEqual(first, second)

    def test_shuffle_decouples_position_from_source_order(self):
        rows = self.expert_rows(12)
        calibrated = [calibrate_case(row) for row in rows]
        _, hidden = build_blinded_packet(rows, calibrated, seed=BLINDED_PACKET_SEED)

        source_order = [row["source_review_id"] for row in hidden]
        self.assertNotEqual(source_order, sorted(source_order))


class FrozenStateTests(unittest.TestCase):
    """الحالة المجمّدة ما اتغيّرتش. بتتخطى لو البيانات مش موجودة."""

    @unittest.skipUnless(FROZEN_LINKAGE.exists(), "linkage artifact not present")
    def test_frozen_linkage_is_unchanged(self):
        digest = hashlib.sha256(FROZEN_LINKAGE.read_bytes()).hexdigest()

        self.assertEqual(digest, FROZEN_LINKAGE_SHA256)

    @unittest.skipUnless(FROZEN_TIERS_PATH.exists(), "narrator candidates not present")
    def test_frozen_provisional_tiers_are_unchanged(self):
        counts = {}
        with open(FROZEN_TIERS_PATH, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                tier = row["provisional_tier"]
                counts[tier] = counts.get(tier, 0) + 1

        self.assertEqual(counts, FROZEN_TIERS)

    @unittest.skipUnless(NARRATOR_81_PATH.exists(), "81 risk artifact not present")
    def test_frozen_81_population_is_unchanged(self):
        with open(NARRATOR_81_PATH, encoding="utf-8-sig", newline="") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 81)

    @unittest.skipUnless(CALIBRATION_CASES_CSV.exists(), "calibration cases not built")
    def test_published_calibration_cases_carry_no_reviewer_labels(self):
        with open(CALIBRATION_CASES_CSV, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 40)
        for row in rows:
            for column in REVIEWER_COLUMNS:
                self.assertEqual(row[column], "")


if __name__ == "__main__":
    unittest.main()
