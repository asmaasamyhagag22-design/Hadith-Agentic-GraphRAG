"""Audit Itqan source-record attachments separately from person identity.

Track A measures namespaced source-record multiplicity and visible attachment
contradictions.  Track B defines an evidence/provenance contract and prepares a
blinded expert sample without creating historical-person identities.  No source
attachment, profile, MIS tier, reviewer field, or graph data is mutated.
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import random
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_itqan_profile_duplication import (
    BASE_AUDIT,
    BASE_CANDIDATES,
    ITQAN_DIR,
    PROFILE_FILES,
    UNMATCHED_AUDIT,
    UNMATCHED_CANDIDATES,
    _id_sort,
    aggregate_suspected_profile_sets,
    canonical_id,
    classical_source_entries,
    death_interval,
    file_hashes,
    file_sha256,
    filled,
    json_compact,
    load_jsonl,
    load_profiles,
    normalized_field,
    source_identifiers,
    validate_recorded_artifact_hashes,
    write_csv,
    write_json,
)
from config import PROCESSED_DIR


AUDIT_VERSION = "itqan_source_attachment_identity_evidence_v1"
REVIEW_SEED = 2026081606

STRICT_MECHANICAL_TRIAGE = (
    PROCESSED_DIR / "itqan_profile_duplication_strict_mechanical_triage.csv"
)
STRICT_MECHANICAL_TRIAGE_SHA256 = (
    "6f1c71da72b65ee6d80d55e7eff5f076e1e0cc7551c8766aae5d0a1f1a0d8deb"
)
PRIOR_DUPLICATION_AUDIT = PROCESSED_DIR / "itqan_profile_duplication_audit.json"
PRIOR_DUPLICATION_CANDIDATES = (
    PROCESSED_DIR / "itqan_profile_duplication_candidates.jsonl"
)
PRIOR_REVIEW = PROCESSED_DIR / "itqan_profile_duplication_review.csv"
PRIOR_REVIEW_HIDDEN = (
    PROCESSED_DIR / "itqan_profile_duplication_review_hidden.csv"
)
PRIOR_REVIEW_META = PROCESSED_DIR / "itqan_profile_duplication_review_meta.json"
PRIOR_STRICT_CASES = PROCESSED_DIR / "itqan_strict_triage_profile_audit.jsonl"

SOURCE_AUDIT_PATH = PROCESSED_DIR / "itqan_source_attachment_audit.json"
SOURCE_RISK_PATH = PROCESSED_DIR / "itqan_source_attachment_risk_cases.csv"
IDENTITY_MODEL_PATH = PROCESSED_DIR / "itqan_identity_evidence_model.json"
PROFILE_RISK_PATH = PROCESSED_DIR / "itqan_profile_data_quality_risk.csv"
TARGET_81_RISK_PATH = PROCESSED_DIR / "narrator_81_target_data_risk.csv"
TARGET_890_RISK_PATH = PROCESSED_DIR / "narrator_890_target_data_risk.csv"
DUAL_AXIS_140_PATH = PROCESSED_DIR / "itqan_140_dual_axis_diagnostic.csv"
EXPERT_REVIEW_PATH = PROCESSED_DIR / "historical_narrator_expert_review.csv"
EXPERT_REVIEW_META_PATH = (
    PROCESSED_DIR / "historical_narrator_expert_review_meta.json"
)

FROZEN_INPUTS = (
    PROCESSED_DIR / "mis_linkage_accepted_v1.jsonl",
    BASE_AUDIT,
    BASE_CANDIDATES,
    UNMATCHED_AUDIT,
    UNMATCHED_CANDIDATES,
    PRIOR_DUPLICATION_AUDIT,
    PRIOR_DUPLICATION_CANDIDATES,
    PRIOR_REVIEW,
    PRIOR_REVIEW_HIDDEN,
    PRIOR_REVIEW_META,
    PRIOR_STRICT_CASES,
    STRICT_MECHANICAL_TRIAGE,
)

SOURCE_RISK_COLUMNS = (
    "risk_priority",
    "attachment_risk_category",
    "source_namespace",
    "source_record_id",
    "source_key_json",
    "multiplicity",
    "attached_itqan_profile_ids",
    "profile_names",
    "death_values",
    "kunyahs",
    "nasab_values",
    "cities",
    "tabaqat_values",
    "generation_values",
    "contradiction_fields",
    "missing_fields",
    "field_comparisons_json",
    "death_pair_differences_json",
    "source_records_by_profile_json",
    "mechanical_risk_reason",
)

PROFILE_RISK_COLUMNS = (
    "itqan_profile_id",
    "profile_name",
    "source_record_attachment_count",
    "duplicated_source_key_count",
    "duplicated_upstream_key_count",
    "duplicated_classical_source_key_count",
    "max_duplicated_source_key_multiplicity",
    "source_attachment_contradiction_group_count",
    "suspected_profile_set_count",
    "profile_set_contradiction_count",
    "source_specific_grade_disagreement",
    "shares_duplicated_upstream_key",
    "shares_duplicated_classical_source_entry",
    "biographic_contradiction_exposure",
    "data_quality_risk_class",
    "duplicated_source_keys_json",
    "suspected_profile_set_ids_json",
)

TARGET_RISK_COLUMNS = (
    "mis_narrator_id",
    "candidate_basis",
    "target_itqan_profile_id",
    "target_profile_name",
    "source_record_attachment_count",
    "duplicated_source_key_count",
    "duplicated_upstream_key_count",
    "duplicated_classical_source_key_count",
    "source_attachment_contradiction_group_count",
    "suspected_profile_set_count",
    "profile_set_contradiction_count",
    "shares_duplicated_upstream_key",
    "shares_duplicated_classical_source_entry",
    "biographic_contradiction_exposure",
    "data_quality_risk_class",
    "duplicated_source_keys_json",
    "suspected_profile_set_ids_json",
)

DUAL_AXIS_COLUMNS = (
    "review_id",
    "itqan_profile_a_id",
    "itqan_profile_b_id",
    "profile_identity_question",
    "source_attachment_quality_question",
    "shared_source_namespace_count",
    "shared_source_keys_json",
    "explicit_mechanical_contradictions_json",
    "missing_information_json",
    "source_strict_triage_sha256",
)

EXPERT_REVIEW_COLUMNS = (
    "expert_review_id",
    "source_review_id",
    "itqan_profile_a_id",
    "profile_a_full_evidence_json",
    "itqan_profile_b_id",
    "profile_b_full_evidence_json",
    "relevant_source_names_json",
    "source_specific_name_forms_json",
    "deaths_json",
    "kunyahs_json",
    "nasab_json",
    "teachers_students_json",
    "generation_tabaqa_json",
    "contradictions_json",
    "missing_information_json",
    "expert_verdict",
    "notes",
)

ALLOWED_EXPERT_VERDICTS = (
    "SAME_HISTORICAL_PERSON",
    "DIFFERENT_HISTORICAL_PERSON",
    "UNCERTAIN",
    "INSUFFICIENT_SOURCE_EVIDENCE",
)

ATTACHMENT_CATEGORIES = (
    "SOURCE_KEY_SINGLETON",
    "SOURCE_KEY_MULTIPROFILE_NO_VISIBLE_CONTRADICTION",
    "SOURCE_KEY_MULTIPROFILE_WITH_BIOGRAPHIC_CONTRADICTION",
    "SOURCE_KEY_MULTIPROFILE_INSUFFICIENT_EVIDENCE",
)

PROFILE_RISK_CLASSES = (
    "LOW_TARGET_DATA_RISK",
    "SOURCE_ATTACHMENT_RISK",
    "PROFILE_MULTIPLICITY_RISK",
    "BIOGRAPHIC_CONTRADICTION_RISK",
    "MULTIPLE_RISKS",
)

SCALAR_COMPARISON_FIELDS = (
    "canonical_name",
    "kunya",
    "nasab",
    "death",
    "city",
    "tabaqat",
    "generation",
)


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def namespaced_source_records(profile):
    """Return exact source records without conflating namespaces or aliases."""

    profile_id = canonical_id(profile.get("id"))
    provenance = profile.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    records = {}

    def add(namespace, value, field_paths, payload):
        record_id = canonical_id(value)
        if record_id is None:
            return
        key = (namespace, record_id)
        existing = records.get(key)
        if existing is None:
            records[key] = {
                "source_namespace": namespace,
                "source_record_id": record_id,
                "profile_id": profile_id,
                "field_paths": sorted(set(field_paths)),
                "source_record_payload": deepcopy(payload),
            }
        else:
            existing["field_paths"] = sorted(
                set(existing["field_paths"]) | set(field_paths)
            )

    global_id = canonical_id(profile.get("global_id"))
    provenance_kaggle = canonical_id(provenance.get("kaggle_id"))
    for value in {global_id, provenance_kaggle} - {None}:
        paths = []
        if value == global_id:
            paths.append("global_id")
        if value == provenance_kaggle:
            paths.append("provenance.kaggle_id")
        add(
            "kaggle:scholar_indx",
            value,
            paths,
            {
                "kaggle_id": value,
                "kaggle_name": provenance.get("kaggle_name"),
                "kaggle_grade": provenance.get("kaggle_grade"),
            },
        )

    add(
        "gk:top_level_id",
        profile.get("gk_id"),
        ["gk_id"],
        {"gk_id": canonical_id(profile.get("gk_id")), "match_method": profile.get("gk_match_method")},
    )
    add(
        "gk:provenance_id",
        provenance.get("gk_id"),
        ["provenance.gk_id"],
        {"gk_id": canonical_id(provenance.get("gk_id")), "origin": provenance.get("origin")},
    )
    add(
        "arsanad:profile_row",
        provenance.get("arsanad_id"),
        ["provenance.arsanad_id"],
        {"arsanad_id": canonical_id(provenance.get("arsanad_id")), "origin": provenance.get("origin")},
    )

    for entry in classical_source_entries(profile):
        source = entry["source"]
        add(
            f"classical:{source}",
            entry["entry_id"],
            [f"classical_sources.{source}.entry_id"],
            entry,
        )
    return records


def build_source_key_index(profiles):
    index = defaultdict(dict)
    profile_record_counts = Counter()
    for profile in profiles:
        records = namespaced_source_records(profile)
        profile_id = canonical_id(profile.get("id"))
        profile_record_counts[profile_id] = len(records)
        for key, record in records.items():
            index[key][profile_id] = record
    return index, profile_record_counts


def multiplicity_bucket(count):
    if count == 1:
        return "exactly_1"
    if count == 2:
        return "exactly_2"
    if count <= 5:
        return "3_to_5"
    return "more_than_5"


def source_namespace_metrics(source_index):
    grouped = defaultdict(list)
    for (namespace, _record_id), records in source_index.items():
        grouped[namespace].append(len(records))
    output = {}
    for namespace in sorted(grouped):
        multiplicities = grouped[namespace]
        buckets = Counter(multiplicity_bucket(value) for value in multiplicities)
        duplicated_profiles = {
            profile_id
            for (candidate_namespace, _), records in source_index.items()
            if candidate_namespace == namespace and len(records) > 1
            for profile_id in records
        }
        output[namespace] = {
            "populated_key_attachments": sum(multiplicities),
            "unique_source_record_keys": len(multiplicities),
            "keys_attached_to_exactly_1_profile": buckets["exactly_1"],
            "keys_attached_to_2_profiles": buckets["exactly_2"],
            "keys_attached_to_3_to_5_profiles": buckets["3_to_5"],
            "keys_attached_to_more_than_5_profiles": buckets["more_than_5"],
            "largest_multiplicity": max(multiplicities, default=0),
            "profiles_touched_by_duplicated_keys": len(duplicated_profiles),
        }
    return output


def _scalar_value(profile, field):
    if field == "canonical_name":
        return profile.get("full_name")
    return profile.get(field)


def compare_scalar_values(values):
    """Compare exact nonmissing values with UNKNOWN preserved."""

    present = [normalized_field(value) for value in values if filled(value)]
    present = [value for value in present if value]
    missing = len(values) - len(present)
    if len(present) < 2:
        return "UNKNOWN"
    if len(set(present)) > 1:
        return "CONTRADICTORY"
    if missing:
        return "UNKNOWN"
    return "CONSISTENT"


def compare_set_values(value_sets):
    populated = [set(values) for values in value_sets if values]
    if len(populated) < 2:
        return "UNKNOWN"
    shared = set.intersection(*populated)
    if shared and len(populated) == len(value_sets):
        return "CONSISTENT"
    # Disjoint alias/relationship lists are incomplete evidence, not a
    # historical contradiction.
    return "UNKNOWN"


def aliases_for(profile):
    values = profile.get("namings")
    if not isinstance(values, list):
        return set()
    return {normalized_field(value) for value in values if normalized_field(value)}


def relationship_ids(profile, field):
    values = profile.get(field)
    if not isinstance(values, list):
        return set()
    return {value for value in map(canonical_id, values) if value is not None}


def compare_group_fields(profiles):
    comparisons = {
        field: compare_scalar_values([_scalar_value(profile, field) for profile in profiles])
        for field in SCALAR_COMPARISON_FIELDS
    }
    comparisons["aliases"] = compare_set_values([aliases_for(profile) for profile in profiles])
    comparisons["teachers"] = compare_set_values([
        relationship_ids(profile, "teachers") for profile in profiles
    ])
    comparisons["students"] = compare_set_values([
        relationship_ids(profile, "students") for profile in profiles
    ])
    return comparisons


def parsed_death_years(value):
    interval = death_interval(value)
    if interval is None:
        return None
    return interval


def death_difference_bucket(minimum_difference, exact_text=False):
    if exact_text:
        return "EXACT_EQUAL_DEATH_TEXT"
    if minimum_difference == 0:
        return "OVERLAPPING_OR_ZERO_YEAR_DIFFERENCE"
    if minimum_difference <= 5:
        return "SMALL_DIFFERENCE_1_TO_5"
    if minimum_difference <= 25:
        return "MODERATE_DIFFERENCE_6_TO_25"
    return "LARGE_DIFFERENCE_OVER_25"


def death_pair_differences(profiles):
    output = []
    for left, right in itertools.combinations(profiles, 2):
        left_value = left.get("death")
        right_value = right.get("death")
        left_interval = parsed_death_years(left_value)
        right_interval = parsed_death_years(right_value)
        if left_interval is None or right_interval is None:
            continue
        exact_text = normalized_field(left_value) == normalized_field(right_value)
        if left_interval[1] < right_interval[0]:
            minimum = right_interval[0] - left_interval[1]
        elif right_interval[1] < left_interval[0]:
            minimum = left_interval[0] - right_interval[1]
        else:
            minimum = 0
        maximum = max(
            abs(left_interval[0] - right_interval[1]),
            abs(right_interval[0] - left_interval[1]),
        )
        output.append({
            "profile_a_id": canonical_id(left.get("id")),
            "profile_a_death": left_value,
            "profile_a_parsed_interval": list(left_interval),
            "profile_b_id": canonical_id(right.get("id")),
            "profile_b_death": right_value,
            "profile_b_parsed_interval": list(right_interval),
            "exact_equal_death_text": exact_text,
            "minimum_absolute_year_difference": minimum,
            "maximum_absolute_year_difference": maximum,
            "descriptive_bucket": death_difference_bucket(minimum, exact_text),
        })
    return output


def missing_field_counts(profiles):
    output = {}
    fields = (
        "full_name", "namings", "kunya", "nasab", "death", "city",
        "tabaqat", "generation", "teachers", "students",
    )
    for field in fields:
        missing = sum(not filled(profile.get(field)) for profile in profiles)
        if missing:
            output[field] = missing
    return output


def attachment_risk_category(comparisons):
    contradictions = [
        field for field, relation in comparisons.items()
        if relation == "CONTRADICTORY"
    ]
    known = [
        field for field, relation in comparisons.items()
        if relation != "UNKNOWN"
    ]
    if contradictions:
        return "SOURCE_KEY_MULTIPROFILE_WITH_BIOGRAPHIC_CONTRADICTION"
    if not known:
        return "SOURCE_KEY_MULTIPROFILE_INSUFFICIENT_EVIDENCE"
    return "SOURCE_KEY_MULTIPROFILE_NO_VISIBLE_CONTRADICTION"


def source_group_audit(key, records, profiles_by_id):
    namespace, record_id = key
    profile_ids = sorted(records, key=_id_sort)
    profiles = [profiles_by_id[profile_id] for profile_id in profile_ids]
    comparisons = compare_group_fields(profiles)
    contradictions = sorted(
        field for field, value in comparisons.items()
        if value == "CONTRADICTORY"
    )
    missing = missing_field_counts(profiles)
    death_differences = death_pair_differences(profiles)
    category = attachment_risk_category(comparisons)
    reasons = [f"SOURCE_RECORD_ATTACHED_TO_{len(profile_ids)}_PROFILES"]
    if contradictions:
        reasons.append("EXPLICIT_POPULATED_FIELD_DISAGREEMENT:" + "|".join(contradictions))
    if any(
        item["descriptive_bucket"] == "LARGE_DIFFERENCE_OVER_25"
        for item in death_differences
    ):
        reasons.append("LARGE_DESCRIPTIVE_DEATH_YEAR_SPREAD_OVER_25")
    if not contradictions and all(value == "UNKNOWN" for value in comparisons.values()):
        reasons.append("INSUFFICIENT_COMPARABLE_BIOGRAPHIC_FIELDS")
    return {
        "source_namespace": namespace,
        "source_record_id": record_id,
        "source_key": [namespace, record_id],
        "multiplicity": len(profile_ids),
        "attached_itqan_profile_ids": profile_ids,
        "profile_names": [profile.get("full_name") for profile in profiles],
        "death_values": [profile.get("death") for profile in profiles],
        "kunyahs": [profile.get("kunya") for profile in profiles],
        "nasab_values": [profile.get("nasab") for profile in profiles],
        "cities": [profile.get("city") for profile in profiles],
        "tabaqat_values": [profile.get("tabaqat") for profile in profiles],
        "generation_values": [profile.get("generation") for profile in profiles],
        "field_comparisons": comparisons,
        "contradiction_fields": contradictions,
        "missing_fields": missing,
        "death_pair_differences": death_differences,
        "source_records_by_profile": {
            profile_id: records[profile_id] for profile_id in profile_ids
        },
        "attachment_risk_category": category,
        "mechanical_risk_reasons": reasons,
    }


def risk_sort_key(group):
    category_order = {
        "SOURCE_KEY_MULTIPROFILE_WITH_BIOGRAPHIC_CONTRADICTION": 0,
        "SOURCE_KEY_MULTIPROFILE_INSUFFICIENT_EVIDENCE": 1,
        "SOURCE_KEY_MULTIPROFILE_NO_VISIBLE_CONTRADICTION": 2,
    }
    max_death = max(
        (item["minimum_absolute_year_difference"] for item in group["death_pair_differences"]),
        default=-1,
    )
    return (
        category_order[group["attachment_risk_category"]],
        -max_death,
        -len(group["contradiction_fields"]),
        -group["multiplicity"],
        group["source_namespace"],
        _id_sort(group["source_record_id"]),
    )


def source_risk_csv_rows(groups):
    rows = []
    for priority, group in enumerate(sorted(groups, key=risk_sort_key), start=1):
        rows.append({
            "risk_priority": priority,
            "attachment_risk_category": group["attachment_risk_category"],
            "source_namespace": group["source_namespace"],
            "source_record_id": group["source_record_id"],
            "source_key_json": json_compact(group["source_key"]),
            "multiplicity": group["multiplicity"],
            "attached_itqan_profile_ids": "|".join(group["attached_itqan_profile_ids"]),
            "profile_names": json_compact(group["profile_names"]),
            "death_values": json_compact(group["death_values"]),
            "kunyahs": json_compact(group["kunyahs"]),
            "nasab_values": json_compact(group["nasab_values"]),
            "cities": json_compact(group["cities"]),
            "tabaqat_values": json_compact(group["tabaqat_values"]),
            "generation_values": json_compact(group["generation_values"]),
            "contradiction_fields": "|".join(group["contradiction_fields"]),
            "missing_fields": json_compact(group["missing_fields"]),
            "field_comparisons_json": json_compact(group["field_comparisons"]),
            "death_pair_differences_json": json_compact(group["death_pair_differences"]),
            "source_records_by_profile_json": json_compact(group["source_records_by_profile"]),
            "mechanical_risk_reason": "|".join(group["mechanical_risk_reasons"]),
        })
    return rows


def load_suspected_profile_sets():
    raw = []
    with open(PRIOR_DUPLICATION_CANDIDATES, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if value.get("candidate_status") != "POSSIBLE_DUPLICATE_PROFILE":
                continue
            raw.append({
                "group_id": value["group_id"],
                "itqan_profile_ids": value["itqan_profile_ids"],
                "candidate_status": value["candidate_status"],
                "conceptual_class": value["conceptual_class"],
                "evidence": value["evidence"],
                "contradictions": value["contradictions"],
            })
    return aggregate_suspected_profile_sets(raw)


def profile_set_memberships(suspected_sets):
    memberships = defaultdict(set)
    contradictions = defaultdict(set)
    for group in suspected_sets:
        for profile_id in group["itqan_profile_ids"]:
            memberships[profile_id].add(group["group_id"])
        for profile_id in group["contradictions"]["contradictory_profile_ids"]:
            contradictions[profile_id].add(group["group_id"])
    return memberships, contradictions


def source_group_memberships(source_groups):
    memberships = defaultdict(list)
    for group in source_groups:
        for profile_id in group["attached_itqan_profile_ids"]:
            memberships[profile_id].append(group)
    return memberships


def profile_risk_class(source_risk, profile_multiplicity, contradiction):
    risks = []
    if source_risk:
        risks.append("SOURCE_ATTACHMENT_RISK")
    if profile_multiplicity:
        risks.append("PROFILE_MULTIPLICITY_RISK")
    if contradiction:
        risks.append("BIOGRAPHIC_CONTRADICTION_RISK")
    if not risks:
        return "LOW_TARGET_DATA_RISK"
    if len(risks) > 1:
        return "MULTIPLE_RISKS"
    return risks[0]


def source_specific_grade_disagreement(profile):
    grades = {
        str(entry.get("grade_en") or "").strip()
        for entry in classical_source_entries(profile)
        if str(entry.get("grade_en") or "").strip() not in {"", "unknown"}
    }
    return len(grades) > 1


def build_profile_risk_rows(
    profiles,
    profile_record_counts,
    duplicated_source_memberships,
    suspected_memberships,
    profile_set_contradictions,
):
    rows = []
    lookup = {}
    for profile in sorted(profiles, key=lambda value: _id_sort(canonical_id(value.get("id")))):
        profile_id = canonical_id(profile.get("id"))
        source_groups = duplicated_source_memberships.get(profile_id, [])
        source_keys = [group["source_key"] for group in source_groups]
        upstream_count = sum(
            not group["source_namespace"].startswith("classical:")
            for group in source_groups
        )
        classical_count = sum(
            group["source_namespace"].startswith("classical:")
            for group in source_groups
        )
        source_contradictions = sum(bool(group["contradiction_fields"]) for group in source_groups)
        suspected_ids = suspected_memberships.get(profile_id, set())
        set_contradictions = profile_set_contradictions.get(profile_id, set())
        contradiction = bool(source_contradictions or set_contradictions)
        risk = profile_risk_class(bool(source_groups), bool(suspected_ids), contradiction)
        row = {
            "itqan_profile_id": profile_id,
            "profile_name": profile.get("full_name"),
            "source_record_attachment_count": profile_record_counts.get(profile_id, 0),
            "duplicated_source_key_count": len(source_groups),
            "duplicated_upstream_key_count": upstream_count,
            "duplicated_classical_source_key_count": classical_count,
            "max_duplicated_source_key_multiplicity": max(
                (group["multiplicity"] for group in source_groups), default=0
            ),
            "source_attachment_contradiction_group_count": source_contradictions,
            "suspected_profile_set_count": len(suspected_ids),
            "profile_set_contradiction_count": len(set_contradictions),
            "source_specific_grade_disagreement": source_specific_grade_disagreement(profile),
            "shares_duplicated_upstream_key": upstream_count > 0,
            "shares_duplicated_classical_source_entry": classical_count > 0,
            "biographic_contradiction_exposure": contradiction,
            "data_quality_risk_class": risk,
            "duplicated_source_keys_json": json_compact(sorted(source_keys)),
            "suspected_profile_set_ids_json": json_compact(sorted(suspected_ids)),
        }
        rows.append(row)
        lookup[profile_id] = row
    return rows, lookup


def target_risk_projection(mis_id, basis, profile_id, profile_risk_lookup):
    risk = profile_risk_lookup[profile_id]
    return {
        "mis_narrator_id": mis_id,
        "candidate_basis": basis,
        "target_itqan_profile_id": profile_id,
        "target_profile_name": risk["profile_name"],
        **{
            column: risk[column]
            for column in TARGET_RISK_COLUMNS
            if column in risk
        },
    }


def build_81_target_rows(profile_risk_lookup):
    output = []
    for row in load_jsonl(BASE_CANDIDATES):
        tier = row.get("provisional_tier")
        if tier not in {"EXACT_RESOLVED", "ALIAS_RESOLVED"}:
            continue
        profile_id = canonical_id(row.get("provisional_resolved_itqan_id"))
        output.append(target_risk_projection(
            row.get("mis_narrator_id"), tier, profile_id, profile_risk_lookup
        ))
    return sorted(output, key=lambda row: _id_sort(str(row["mis_narrator_id"])))


def build_890_target_rows(profile_risk_lookup):
    output = []
    for row in load_jsonl(UNMATCHED_CANDIDATES):
        profile_ids = [
            canonical_id(value) for value in row.get("mis_short_name_candidate_ids", [])
            if canonical_id(value) is not None
        ]
        if len(profile_ids) != 1:
            continue
        output.append(target_risk_projection(
            row.get("mis_narrator_id"),
            "EXACT_SHORT_NAME_UNIQUE_DIAGNOSTIC_NOT_RESOLUTION",
            profile_ids[0],
            profile_risk_lookup,
        ))
    return sorted(output, key=lambda row: _id_sort(str(row["mis_narrator_id"])))


def identity_question_label(mechanical_triage):
    mapping = {
        "EXPLICIT_DEATH_DISAGREEMENT_NO_SHARED_RECORD": "CANDIDATE_IDENTITY_WITH_CONTRADICTORY_DEATH_EVIDENCE",
        "INSUFFICIENT_FOR_HISTORICAL_PERSON_IDENTITY": "IDENTITY_EVIDENCE_INSUFFICIENT",
        "BIOGRAPHICALLY_COMPATIBLE_BUT_UNPROVEN": "IDENTITY_BIOGRAPHICALLY_COMPATIBLE_UNPROVEN",
        "SOURCE_RECORD_DUPLICATION_NO_EXPLICIT_DEATH_CONFLICT": "IDENTITY_UNRESOLVED_SOURCE_OVERLAP_NOT_INDEPENDENT",
        "RELATIONALLY_COMPATIBLE_BUT_UNPROVEN": "IDENTITY_RELATIONALLY_COMPATIBLE_UNPROVEN",
        "SOURCE_RECORD_DUPLICATION_WITH_EXPLICIT_DEATH_CONFLICT": "IDENTITY_UNRESOLVED_CONFLICTING_ATTACHMENT",
    }
    return mapping[mechanical_triage]


def source_quality_label(source_relation, death_relation):
    if source_relation == "NO_SHARED_SOURCE_RECORD_KEY":
        return "NO_DUPLICATED_SOURCE_RECORD_IN_PAIR"
    if death_relation == "FALSE":
        return "DUPLICATED_SOURCE_RECORD_WITH_EXPLICIT_DEATH_CONFLICT"
    return "DUPLICATED_SOURCE_RECORD_NO_EXPLICIT_DEATH_CONFLICT"


def shared_source_keys(left, right):
    left_records = namespaced_source_records(left)
    right_records = namespaced_source_records(right)
    return sorted(left_records.keys() & right_records.keys())


def build_dual_axis_rows(strict_rows, profiles_by_id):
    output = []
    for row in strict_rows:
        left = profiles_by_id[row["itqan_profile_a_id"]]
        right = profiles_by_id[row["itqan_profile_b_id"]]
        shared = shared_source_keys(left, right)
        contradiction_fields = [
            field.replace("_field_relation", "")
            for field in (
                "death_field_relation", "kunya_field_relation",
                "nasab_field_relation", "city_field_relation",
            )
            if row.get(field) == "FALSE"
        ]
        missing = [
            field.replace("_field_relation", "")
            for field in (
                "death_field_relation", "kunya_field_relation",
                "nasab_field_relation", "city_field_relation",
            )
            if row.get(field) == "UNKNOWN"
        ]
        output.append({
            "review_id": row["review_id"],
            "itqan_profile_a_id": row["itqan_profile_a_id"],
            "itqan_profile_b_id": row["itqan_profile_b_id"],
            "profile_identity_question": identity_question_label(row["assistant_mechanical_triage"]),
            "source_attachment_quality_question": source_quality_label(
                row["mechanical_source_relation"], row["death_field_relation"]
            ),
            "shared_source_namespace_count": len(shared),
            "shared_source_keys_json": json_compact(shared),
            "explicit_mechanical_contradictions_json": json_compact(contradiction_fields),
            "missing_information_json": json_compact(missing),
            "source_strict_triage_sha256": STRICT_MECHANICAL_TRIAGE_SHA256,
        })
    return output


def expert_profile_evidence(profile):
    provenance = profile.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    return {
        "itqan_profile_id": canonical_id(profile.get("id")),
        "full_name": profile.get("full_name"),
        "namings": profile.get("namings") if isinstance(profile.get("namings"), list) else [],
        "kunya": profile.get("kunya"),
        "nasab": profile.get("nasab"),
        "death": profile.get("death"),
        "city": profile.get("city"),
        "tabaqat": profile.get("tabaqat"),
        "generation": profile.get("generation"),
        "teachers": sorted(relationship_ids(profile, "teachers"), key=_id_sort),
        "students": sorted(relationship_ids(profile, "students"), key=_id_sort),
        "source_records": list(namespaced_source_records(profile).values()),
        "source_specific_name_forms": {
            "kaggle_name": provenance.get("kaggle_name"),
            "classical_entry_name_forms": "UNKNOWN_FIELD_LEVEL_PROVENANCE_UNAVAILABLE",
        },
    }


def expert_review_guard(path):
    if not path.exists():
        return
    _, rows = read_csv(path)
    if any(row.get("expert_verdict", "").strip() or row.get("notes", "").strip() for row in rows):
        raise RuntimeError(f"Refusing to overwrite expert labels in {path}")


def build_expert_review(strict_rows, profiles_by_id):
    candidates = []
    for row in strict_rows:
        triage = row["assistant_mechanical_triage"]
        if triage in {
            "BIOGRAPHICALLY_COMPATIBLE_BUT_UNPROVEN",
            "RELATIONALLY_COMPATIBLE_BUT_UNPROVEN",
        }:
            candidates.append((0, 0, row))
        elif triage == "EXPLICIT_DEATH_DISAGREEMENT_NO_SHARED_RECORD":
            left = profiles_by_id[row["itqan_profile_a_id"]]
            right = profiles_by_id[row["itqan_profile_b_id"]]
            differences = death_pair_differences([left, right])
            spread = max(
                (item["minimum_absolute_year_difference"] for item in differences),
                default=-1,
            )
            candidates.append((1, -spread, row))
    compatible = sorted(
        (item for item in candidates if item[0] == 0),
        key=lambda item: item[2]["review_id"],
    )
    death_cases = sorted(
        (item for item in candidates if item[0] == 1),
        key=lambda item: (item[1], item[2]["review_id"]),
    )[:12]
    selected = compatible + death_cases
    rows = []
    for index, (_kind, _spread, source_row) in enumerate(selected, start=1):
        left = profiles_by_id[source_row["itqan_profile_a_id"]]
        right = profiles_by_id[source_row["itqan_profile_b_id"]]
        left_evidence = expert_profile_evidence(left)
        right_evidence = expert_profile_evidence(right)
        source_names = sorted({
            record["source_namespace"]
            for evidence in (left_evidence, right_evidence)
            for record in evidence["source_records"]
        })
        comparisons = compare_group_fields([left, right])
        contradictions = sorted(
            field for field, relation in comparisons.items()
            if relation == "CONTRADICTORY"
        )
        missing = missing_field_counts([left, right])
        rows.append({
            "expert_review_id": f"ITQ-EXPERT-{index:04d}",
            "source_review_id": source_row["review_id"],
            "itqan_profile_a_id": source_row["itqan_profile_a_id"],
            "profile_a_full_evidence_json": json_compact(left_evidence),
            "itqan_profile_b_id": source_row["itqan_profile_b_id"],
            "profile_b_full_evidence_json": json_compact(right_evidence),
            "relevant_source_names_json": json_compact(source_names),
            "source_specific_name_forms_json": json_compact({
                "profile_a": left_evidence["source_specific_name_forms"],
                "profile_b": right_evidence["source_specific_name_forms"],
            }),
            "deaths_json": json_compact([left.get("death"), right.get("death")]),
            "kunyahs_json": json_compact([left.get("kunya"), right.get("kunya")]),
            "nasab_json": json_compact([left.get("nasab"), right.get("nasab")]),
            "teachers_students_json": json_compact({
                "profile_a_teachers": left_evidence["teachers"],
                "profile_a_students": left_evidence["students"],
                "profile_b_teachers": right_evidence["teachers"],
                "profile_b_students": right_evidence["students"],
            }),
            "generation_tabaqa_json": json_compact({
                "profile_a_generation": left.get("generation"),
                "profile_a_tabaqat": left.get("tabaqat"),
                "profile_b_generation": right.get("generation"),
                "profile_b_tabaqat": right.get("tabaqat"),
            }),
            "contradictions_json": json_compact({
                "fields": contradictions,
                "death_differences": death_pair_differences([left, right]),
            }),
            "missing_information_json": json_compact(missing),
            "expert_verdict": "",
            "notes": "",
        })
    return rows


def identity_evidence_model(source_metrics, dependency_metrics):
    return {
        "artifact_version": AUDIT_VERSION,
        "artifact_type": "SCHEMA_AND_EVIDENCE_CONTRACT_ONLY_NO_IDENTITIES",
        "central_separation": [
            "source_record_identity",
            "itqan_profile_identity",
            "historical_narrator_identity",
        ],
        "evidence_categories": {
            "IDENTITY_BEARING_STRONGER": [
                "stable upstream person identifier only when its person semantics and attachment integrity are independently confirmed",
                "independently corroborated source crosswalk",
                "compatible full biography corroborated by independent provenance",
            ],
            "SUPPORTING_NOT_DECISIVE": [
                "normalized name", "aliases", "kunya", "nasab", "city",
                "generation", "death", "teachers", "students",
                "shared source reference",
            ],
            "CONTRADICTING_REQUIRES_REVIEW": [
                "incompatible death evidence", "incompatible generations",
                "teacher/student chronology conflict", "materially different biographies",
            ],
            "MISSING": "UNKNOWN",
        },
        "evidence_record_contract": {
            "evidence_id": "required stable opaque ID",
            "field": "required",
            "value": "required raw value; never silently canonicalized",
            "source_namespace": "required or UNKNOWN",
            "source_record_id": "required when traceable, otherwise UNKNOWN",
            "itqan_profile_id": "required",
            "parser_or_builder": "required or UNKNOWN",
            "provenance_status": ["DIRECT_SOURCE_RECORD", "PROFILE_LEVEL_ONLY", "DERIVED", "UNKNOWN"],
            "dependency_group_id": "required; evidence copied from one record shares one dependency group",
            "review_status": ["UNREVIEWED", "MECHANICALLY_VERIFIED", "EXPERT_REVIEWED", "DISPUTED"],
        },
        "dependency_rules": [
            "fields copied from one source record are one correlated evidence unit",
            "global_id and provenance.kaggle_id are aliases of one Kaggle record linkage, not independent evidence",
            "classical_sources and provenance.sources references to the same source/entry are one record",
            "profile-level name/death/kunya fields have UNKNOWN field-level source dependency in v1.20",
            "missing field-level provenance must never be promoted to independent corroboration",
        ],
        "measured_source_namespaces": source_metrics,
        "provenance_dependency_summary": dependency_metrics,
        "future_historical_narrator_contract": {
            "historical_narrator_id": "opaque ID assigned only after the layer is authorized",
            "canonical_display_name": "display value with evidence references; not source truth",
            "identity_status": [
                "PROVISIONAL", "REVIEWED", "DOMAIN_EXPERT_CONFIRMED",
                "AMBIGUOUS", "QUARANTINED",
            ],
            "member_profile_assertions": [{
                "itqan_profile_id": "required",
                "membership_status": ["PROPOSED", "ACCEPTED", "REJECTED", "QUARANTINED"],
                "supporting_evidence_ids": [],
                "contradiction_evidence_ids": [],
                "review_event_ids": [],
            }],
            "aliases": [{"value": "raw alias", "evidence_ids": []}],
            "evidence": "evidence_record_contract[]",
            "contradictions": [{"evidence_ids": [], "resolution_status": "UNRESOLVED"}],
            "review_events": [{
                "review_status": "required",
                "reviewer_role": "mechanical reviewer or domain expert",
                "verdict": "required",
                "timestamp": "required",
            }],
            "source_profile_links": "immutable references to Itqan profiles and their source records",
            "forbidden_fields": ["aggregated_grade", "merged_profile_payload"],
        },
        "contract_invariants": [
            "source profiles are never absorbed or deleted",
            "source-specific grades remain immutable",
            "singleton historical entities are allowed",
            "unresolved and quarantined groups are allowed",
            "no profile is forced into a cluster",
        ],
        "instances_created": 0,
    }


def dependency_summary(profiles):
    multi_classical = 0
    global_alias_equal = 0
    global_alias_conflict = 0
    profile_fields_with_field_level_source = 0
    for profile in profiles:
        if len(classical_source_entries(profile)) > 1:
            multi_classical += 1
        identifiers = source_identifiers(profile)
        global_id = identifiers["global_id"]
        provenance_id = identifiers["provenance_kaggle_id"]
        if global_id is not None and provenance_id is not None:
            if global_id == provenance_id:
                global_alias_equal += 1
            else:
                global_alias_conflict += 1
    return {
        "profiles_with_multiple_classical_source_records": multi_classical,
        "global_id_equals_provenance_kaggle_id": global_alias_equal,
        "global_id_conflicts_with_provenance_kaggle_id": global_alias_conflict,
        "profile_fields_with_explicit_field_level_source_pointer": profile_fields_with_field_level_source,
        "traceable_direct_evidence": [
            "classical source-specific entry IDs and grades",
            "Kaggle record ID/name/grade in provenance",
            "GK record field IDs with namespace kept separate",
        ],
        "unknown_dependency_fields": [
            "full_name", "namings", "kunya", "nasab", "death", "city",
            "tabaqat", "generation", "teachers", "students",
        ],
        "independence_claim": "UNKNOWN for profile-level fields without field-level provenance",
    }


def target_summary(rows):
    risk_counts = Counter(row["data_quality_risk_class"] for row in rows)
    return {
        "population": len(rows),
        "risk_class_distribution": {
            value: risk_counts[value] for value in PROFILE_RISK_CLASSES
        },
        "structurally_clean_low_target_data_risk": sum(
            row["data_quality_risk_class"] == "LOW_TARGET_DATA_RISK"
            for row in rows
        ),
        "with_duplicated_source_attachment": sum(
            int(row["duplicated_source_key_count"]) > 0 for row in rows
        ),
        "with_suspected_profile_multiplicity": sum(
            int(row["suspected_profile_set_count"]) > 0 for row in rows
        ),
        "with_biographic_contradiction_exposure": sum(
            bool(row["biographic_contradiction_exposure"]) for row in rows
        ),
        "sharing_duplicated_upstream_key": sum(
            bool(row["shares_duplicated_upstream_key"]) for row in rows
        ),
        "sharing_duplicated_classical_source_entry": sum(
            bool(row["shares_duplicated_classical_source_entry"]) for row in rows
        ),
        "status_or_mapping_mutations": 0,
    }


def output_hash(path, rows):
    return {"path": str(path.resolve()), "rows": rows, "sha256": file_sha256(path)}


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    strict_hash = file_sha256(STRICT_MECHANICAL_TRIAGE)
    if strict_hash != STRICT_MECHANICAL_TRIAGE_SHA256:
        raise RuntimeError(
            f"Strict mechanical triage changed: {strict_hash} != {STRICT_MECHANICAL_TRIAGE_SHA256}"
        )
    recorded_hashes = validate_recorded_artifact_hashes(
        (BASE_AUDIT, UNMATCHED_AUDIT, PRIOR_DUPLICATION_AUDIT)
    )
    before_hashes = file_hashes(FROZEN_INPUTS)

    profiles, per_file = load_profiles()
    profiles_by_id = {
        canonical_id(profile.get("id")): profile for profile in profiles
    }
    if len(profiles) != 115735 or len(profiles_by_id) != 115735:
        raise ValueError("Expected 115,735 distinct Itqan profiles")

    source_index, profile_record_counts = build_source_key_index(profiles)
    namespace_metrics = source_namespace_metrics(source_index)
    duplicated_groups = [
        source_group_audit(key, records, profiles_by_id)
        for key, records in sorted(source_index.items())
        if len(records) > 1
    ]
    source_rows = source_risk_csv_rows(duplicated_groups)
    write_csv(SOURCE_RISK_PATH, SOURCE_RISK_COLUMNS, source_rows)

    suspected_sets = load_suspected_profile_sets()
    suspected_memberships, profile_set_contradictions = profile_set_memberships(
        suspected_sets
    )
    duplicated_source_memberships = source_group_memberships(duplicated_groups)
    profile_rows, profile_risk_lookup = build_profile_risk_rows(
        profiles,
        profile_record_counts,
        duplicated_source_memberships,
        suspected_memberships,
        profile_set_contradictions,
    )
    write_csv(PROFILE_RISK_PATH, PROFILE_RISK_COLUMNS, profile_rows)

    target_81_rows = build_81_target_rows(profile_risk_lookup)
    target_890_rows = build_890_target_rows(profile_risk_lookup)
    if len(target_81_rows) != 81 or len(target_890_rows) != 890:
        raise ValueError(
            f"Frozen target populations changed: 81={len(target_81_rows)}, 890={len(target_890_rows)}"
        )
    write_csv(TARGET_81_RISK_PATH, TARGET_RISK_COLUMNS, target_81_rows)
    write_csv(TARGET_890_RISK_PATH, TARGET_RISK_COLUMNS, target_890_rows)

    _, strict_rows = read_csv(STRICT_MECHANICAL_TRIAGE)
    if any(row["reviewer_verdict"].strip() or row["notes"].strip() for row in strict_rows):
        raise RuntimeError("Strict mechanical triage unexpectedly contains reviewer labels")
    dual_axis_rows = build_dual_axis_rows(strict_rows, profiles_by_id)
    write_csv(DUAL_AXIS_140_PATH, DUAL_AXIS_COLUMNS, dual_axis_rows)

    expert_review_guard(EXPERT_REVIEW_PATH)
    expert_rows = build_expert_review(strict_rows, profiles_by_id)
    write_csv(EXPERT_REVIEW_PATH, EXPERT_REVIEW_COLUMNS, expert_rows)
    expert_meta = {
        "artifact_version": AUDIT_VERSION,
        "question": "Do the two profiles represent the same historical narrator?",
        "allowed_expert_verdicts": list(ALLOWED_EXPERT_VERDICTS),
        "rows": len(expert_rows),
        "selection": {
            "all_biographically_compatible_but_unproven": 25,
            "all_relationally_compatible_but_unproven": 3,
            "largest_raw_death_gap_without_shared_source_record": 12,
            "mechanical_source_attachment_only_cases_excluded": True,
            "insufficient_evidence_cases_excluded": True,
        },
        "visible_columns": list(EXPERT_REVIEW_COLUMNS),
        "automatic_label_visible": False,
        "model_score_visible": False,
        "algorithmic_confidence_visible": False,
        "expected_answer_visible": False,
        "reviewer_fields_initialized_blank": True,
        "freeze_policy": "generator refuses to overwrite nonblank expert_verdict or notes",
        "source_strict_triage_sha256": strict_hash,
        "visible_sha256": file_sha256(EXPERT_REVIEW_PATH),
    }
    write_json(EXPERT_REVIEW_META_PATH, expert_meta)

    dependency_metrics = dependency_summary(profiles)
    evidence_model = identity_evidence_model(namespace_metrics, dependency_metrics)
    write_json(IDENTITY_MODEL_PATH, evidence_model)

    category_counts = Counter(
        group["attachment_risk_category"] for group in duplicated_groups
    )
    category_counts["SOURCE_KEY_SINGLETON"] = len(source_index) - len(duplicated_groups)
    death_bucket_counts = Counter(
        item["descriptive_bucket"]
        for group in duplicated_groups
        for item in group["death_pair_differences"]
    )
    raw_minimum_differences = Counter(
        item["minimum_absolute_year_difference"]
        for group in duplicated_groups
        for item in group["death_pair_differences"]
    )
    duplicated_profiles = {
        profile_id
        for group in duplicated_groups
        for profile_id in group["attached_itqan_profile_ids"]
    }
    contradiction_profiles = {
        profile_id
        for group in duplicated_groups
        if group["contradiction_fields"]
        for profile_id in group["attached_itqan_profile_ids"]
    }
    profile_risk_counts = Counter(
        row["data_quality_risk_class"] for row in profile_rows
    )
    critical_groups = [
        group for group in duplicated_groups
        if "2695" in group["attached_itqan_profile_ids"]
        and "70395" in group["attached_itqan_profile_ids"]
    ]

    after_hashes = file_hashes(FROZEN_INPUTS)
    if before_hashes != after_hashes:
        raise RuntimeError("A frozen Phase-2 artifact changed during generation")

    audit = {
        "audit_version": AUDIT_VERSION,
        "gate_decision": "ENTITY-RESOLUTION GATE CLOSED",
        "central_rule": "source records != Itqan profiles != historical narrators",
        "tracks": {
            "track_a": "source-record attachment integrity",
            "track_b": "historical-person identity evidence contract without identities",
        },
        "source_key_semantics": {
            "namespace_required": True,
            "namespaces_not_mixed": True,
            "kaggle_global_and_provenance_aliases_deduplicated": True,
            "classical_key_shape": ["classical:<source>", "entry_id"],
            "gk_top_level_and_provenance_kept_separate": "semantics equivalence UNKNOWN",
            "arsanad_profile_row_interpretation": "profile-row provenance, not cross-profile person identity",
        },
        "inputs": {
            "itqan_profiles": len(profiles),
            "profile_shards": per_file,
            "strict_mechanical_triage_rows": len(strict_rows),
            "strict_mechanical_triage_sha256": strict_hash,
            "strict_reviewer_fields_modified": False,
            "recorded_prior_artifact_hashes_verified": recorded_hashes,
            "frozen_artifact_hashes_before_and_after": after_hashes,
        },
        "source_key_multiplicity_by_namespace": namespace_metrics,
        "global_source_attachment_metrics": {
            "total_namespaced_source_record_keys": len(source_index),
            "total_source_record_attachments": sum(len(records) for records in source_index.values()),
            "duplicated_source_record_keys": len(duplicated_groups),
            "profiles_touched_by_duplicated_source_keys": len(duplicated_profiles),
            "profiles_touched_by_attachment_contradictions": len(contradiction_profiles),
            "attachment_risk_category_distribution": {
                value: category_counts[value] for value in ATTACHMENT_CATEGORIES
            },
            "profile_data_quality_risk_distribution": {
                value: profile_risk_counts[value] for value in PROFILE_RISK_CLASSES
            },
        },
        "death_difference_audit": {
            "thresholds_are_descriptive_not_historical_identity_rules": True,
            "pairwise_bucket_distribution": dict(death_bucket_counts),
            "raw_minimum_year_difference_distribution": {
                str(key): raw_minimum_differences[key]
                for key in sorted(raw_minimum_differences)
            },
            "difference_definition": "minimum gap between parsed death-year intervals; maximum endpoint difference also retained per pair",
        },
        "critical_itq_dup_0017_class": {
            "matched_source_groups": critical_groups,
            "interpretation": "shared classical record attachment is suspicious; no same-person inference",
        },
        "high_risk_attachment_cases": [
            {
                "risk_priority": index,
                "source_key": group["source_key"],
                "multiplicity": group["multiplicity"],
                "profile_ids": group["attached_itqan_profile_ids"],
                "profile_names": group["profile_names"],
                "death_values": group["death_values"],
                "contradiction_fields": group["contradiction_fields"],
                "death_pair_differences": group["death_pair_differences"],
                "mechanical_risk_reasons": group["mechanical_risk_reasons"],
            }
            for index, group in enumerate(
                sorted(duplicated_groups, key=risk_sort_key)[:20], start=1
            )
        ],
        "dependency_summary": dependency_metrics,
        "impact_on_frozen_81": target_summary(target_81_rows),
        "impact_on_short_name_890": target_summary(target_890_rows),
        "dual_axis_140": {
            "rows": len(dual_axis_rows),
            "identity_question_distribution": dict(Counter(
                row["profile_identity_question"] for row in dual_axis_rows
            )),
            "source_attachment_quality_distribution": dict(Counter(
                row["source_attachment_quality_question"] for row in dual_axis_rows
            )),
            "historical_person_verdicts_created": 0,
        },
        "expert_review": expert_meta,
        "prohibited_outputs_not_created": [
            "historical_narrator_map.json",
            "merged_itqan_profiles.json",
        ],
        "mutations": {
            "itqan_profiles": 0,
            "source_attachments": 0,
            "mis_tiers": 0,
            "reviewer_fields": 0,
            "historical_narrator_instances": 0,
            "graph_nodes_or_edges": 0,
        },
        "output_artifacts": {},
    }
    write_json(SOURCE_AUDIT_PATH, audit)
    audit["output_artifacts"] = {
        SOURCE_RISK_PATH.name: output_hash(SOURCE_RISK_PATH, len(source_rows)),
        IDENTITY_MODEL_PATH.name: output_hash(IDENTITY_MODEL_PATH, 1),
        PROFILE_RISK_PATH.name: output_hash(PROFILE_RISK_PATH, len(profile_rows)),
        TARGET_81_RISK_PATH.name: output_hash(TARGET_81_RISK_PATH, len(target_81_rows)),
        TARGET_890_RISK_PATH.name: output_hash(TARGET_890_RISK_PATH, len(target_890_rows)),
        DUAL_AXIS_140_PATH.name: output_hash(DUAL_AXIS_140_PATH, len(dual_axis_rows)),
        EXPERT_REVIEW_PATH.name: output_hash(EXPERT_REVIEW_PATH, len(expert_rows)),
        EXPERT_REVIEW_META_PATH.name: output_hash(EXPERT_REVIEW_META_PATH, 1),
    }
    write_json(SOURCE_AUDIT_PATH, audit)

    print(json.dumps({
        "gate": audit["gate_decision"],
        "global_source_attachment_metrics": audit["global_source_attachment_metrics"],
        "death_difference_audit": audit["death_difference_audit"]["pairwise_bucket_distribution"],
        "impact_on_frozen_81": audit["impact_on_frozen_81"],
        "impact_on_short_name_890": audit["impact_on_short_name_890"],
        "dual_axis_140": audit["dual_axis_140"],
        "expert_review_rows": len(expert_rows),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
