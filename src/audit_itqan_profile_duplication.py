"""Audit Itqan profile-record multiplicity without merging historical people.

This module keeps three concepts separate:

* an Itqan profile ID (a generated record key),
* an upstream/source record identifier, and
* a historical narrator identity (not present as a canonical layer here).

Only exact, deterministic evidence is used.  Missing evidence is UNKNOWN.  No
fuzzy matching, weighted score, identity assignment, profile merge, or graph
construction is performed.
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_linkage_validation_identity import normalize_narrow_identity
from build_narrator_candidates import _id_sort
from config import PROCESSED_DIR
from profile_itqan import (
    ITQAN_DIR,
    PROFILE_FILES,
    canonical_id,
    file_sha256,
    filled,
    load_profiles,
)


AUDIT_VERSION = "itqan_internal_identity_duplication_audit_v1"
UPSTREAM_COMMIT = "199d870da5b726356b4a8dbaa096140cffb7d0ab"
REVIEW_SEED = 2026081605
DEATH_CONTRADICTION_TOLERANCE_YEARS = 5

AUDIT_PATH = PROCESSED_DIR / "itqan_profile_duplication_audit.json"
CANDIDATES_PATH = PROCESSED_DIR / "itqan_profile_duplication_candidates.jsonl"
STRICT_CASES_PATH = PROCESSED_DIR / "itqan_strict_triage_profile_audit.jsonl"
REVIEW_PATH = PROCESSED_DIR / "itqan_profile_duplication_review.csv"
REVIEW_HIDDEN_PATH = PROCESSED_DIR / "itqan_profile_duplication_review_hidden.csv"
REVIEW_META_PATH = PROCESSED_DIR / "itqan_profile_duplication_review_meta.json"

BASE_AUDIT = PROCESSED_DIR / "narrator_candidate_audit.json"
BASE_CANDIDATES = PROCESSED_DIR / "narrator_resolution_candidates.jsonl"
UNMATCHED_AUDIT = PROCESSED_DIR / "narrator_unmatched_audit.json"
UNMATCHED_CANDIDATES = (
    PROCESSED_DIR / "narrator_unmatched_diagnostic_candidates.jsonl"
)
STRICT_TRIAGE = PROCESSED_DIR / "narrator_unmatched_strict_triage.csv"
STRICT_TRIAGE_EXPECTED_SHA256 = (
    "4e6c35df36a2861a76f3f59edadfb86a642db2370f57f6fd99ca6477a9ed39df"
)

FROZEN_INPUTS = (
    PROCESSED_DIR / "mis_linkage_accepted_v1.jsonl",
    BASE_AUDIT,
    BASE_CANDIDATES,
    PROCESSED_DIR / "narrator_resolution_candidates.csv",
    PROCESSED_DIR / "narrator_resolution_review.csv",
    PROCESSED_DIR / "narrator_resolution_review_hidden.csv",
    PROCESSED_DIR / "narrator_resolution_review_sampling.json",
    UNMATCHED_AUDIT,
    UNMATCHED_CANDIDATES,
    PROCESSED_DIR / "narrator_unmatched_profiles.csv",
    PROCESSED_DIR / "narrator_unmatched_diagnostic_review.csv",
    PROCESSED_DIR / "narrator_unmatched_diagnostic_review_hidden.csv",
    PROCESSED_DIR / "narrator_unmatched_diagnostic_review_meta.json",
    STRICT_TRIAGE,
)

CONCEPTUAL_CLASSES = (
    "DUPLICATE_PROFILE_STRONGLY_SUPPORTED",
    "DISTINCT_PERSON_STRONGLY_SUPPORTED",
    "UNRESOLVED_PROFILE_MULTIPLICITY",
)

ALLOWED_REVIEW_VERDICTS = (
    "SAME_PERSON",
    "DIFFERENT_PERSON",
    "UNCERTAIN",
    "NEEDS_DOMAIN_EXPERT",
)

VISIBLE_REVIEW_COLUMNS = (
    "review_id",
    "group_id",
    "itqan_profile_a_id",
    "profile_a_evidence_json",
    "itqan_profile_b_id",
    "profile_b_evidence_json",
    "shared_mechanical_evidence_json",
    "reviewer_verdict",
    "notes",
)

HIDDEN_REVIEW_COLUMNS = (
    "review_id",
    "sampling_stratum",
    "automatic_conceptual_class",
    "candidate_status",
    "deterministic_grouping_reasons_json",
    "contradictions_json",
    "sampling_seed",
)

STRICT_TRIAGE_TARGET_LABELS = {
    "MULTI_PROFILE_DUPLICATION_SUSPECTED",
    "MULTI_PROFILE_TRUE_PERSON_AMBIGUITY",
    "MULTI_PROFILE_MIXED_UNCERTAIN",
}

RELATIVE_OR_CONTEXT_ALIASES = {
    "أبيه", "أبي", "أبوه", "جده", "جدي", "عمه", "أخيه", "أمه",
    "مولاه", "جدته", "خاله", "شيخه", "ابنه", "بنيه", "رجل",
}

_DEATH_YEAR = re.compile(r"(?<!\d)(\d{1,4})(?!\d)")


def json_compact(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def write_jsonl(path, values):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json_compact(value))
            handle.write("\n")


def write_csv(path, columns, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def file_hashes(paths):
    return {
        str(path): file_sha256(path)
        for path in paths
        if path.exists()
    }


def validate_recorded_artifact_hashes(audit_paths):
    """Verify prior audit outputs against their own frozen recorded hashes."""

    checked = {}
    for audit_path in audit_paths:
        with open(audit_path, "r", encoding="utf-8") as handle:
            audit = json.load(handle)
        for name, metadata in audit.get("output_artifacts", {}).items():
            if not isinstance(metadata, dict) or not metadata.get("sha256"):
                continue
            path = Path(metadata.get("path") or (PROCESSED_DIR / name))
            if not path.exists():
                raise FileNotFoundError(f"Frozen artifact is missing: {path}")
            actual = file_sha256(path)
            expected = metadata["sha256"]
            if actual != expected:
                raise RuntimeError(
                    f"Frozen artifact hash mismatch for {path}: {actual} != {expected}"
                )
            checked[str(path)] = actual
    return checked


def stable_group_id(grouping_kind, normalized_key, profile_ids):
    """Generate an order-independent, reproducible record-group ID."""

    ids = sorted({str(value) for value in profile_ids}, key=_id_sort)
    payload = json_compact([grouping_kind, normalized_key, ids])
    return "ITQ-GRP-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def tri_state_equal(left, right, normalizer=lambda value: str(value).strip()):
    """Return TRUE/FALSE/UNKNOWN; missing is never treated as false."""

    if not filled(left) or not filled(right):
        return "UNKNOWN"
    return "TRUE" if normalizer(left) == normalizer(right) else "FALSE"


def death_interval(value):
    """Extract a conservative Hijri interval, or None for unknown text."""

    if not filled(value):
        return None
    years = [
        int(match)
        for match in _DEATH_YEAR.findall(str(value))
        if 1 <= int(match) <= 1500
    ]
    if not years:
        return None
    return min(years), max(years)


def death_contradiction(left, right, tolerance=DEATH_CONTRADICTION_TOLERANCE_YEARS):
    """Return TRUE only for non-overlapping death ranges separated by > tolerance."""

    first = death_interval(left)
    second = death_interval(right)
    if first is None or second is None:
        return "UNKNOWN"
    separated = first[1] + tolerance < second[0] or second[1] + tolerance < first[0]
    return "TRUE" if separated else "FALSE"


def normalized_field(value):
    return normalize_narrow_identity(value) if filled(value) else ""


def source_identifiers(profile):
    """Extract source record IDs without promoting any to a person identity."""

    provenance = profile.get("provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    values = {
        "itqan_profile_id": canonical_id(profile.get("id")),
        "global_id": canonical_id(profile.get("global_id")),
        "gk_id": canonical_id(profile.get("gk_id")),
        "provenance_kaggle_id": canonical_id(provenance.get("kaggle_id")),
        "provenance_gk_id": canonical_id(provenance.get("gk_id")),
        "provenance_arsanad_id": canonical_id(provenance.get("arsanad_id")),
        "origin": provenance.get("origin") if filled(provenance.get("origin")) else None,
    }
    return values


def logical_identity_keys(profile):
    """Return upstream record-link keys, never an Itqan/historical-person key."""

    identifiers = source_identifiers(profile)
    keys = set()
    kaggle = identifiers["global_id"] or identifiers["provenance_kaggle_id"]
    if kaggle is not None:
        keys.add(("KAGGLE_SCHOLAR_INDX", kaggle))
    gk_id = identifiers["gk_id"] or identifiers["provenance_gk_id"]
    if gk_id is not None:
        keys.add(("GK_RECORD_ID", gk_id))
    # provenance.arsanad_id is retained in output, but the shipped v1.20 data
    # makes it equal to the Itqan profile ID.  It is therefore not used as an
    # independent shared identity key.
    return keys


def classical_source_entries(profile):
    sources = profile.get("classical_sources")
    if not isinstance(sources, dict):
        return []
    entries = []
    for source, value in sorted(sources.items()):
        entry = value if isinstance(value, dict) else {}
        entries.append({
            "source": source,
            "entry_id": canonical_id(entry.get("entry_id")),
            "grade_en": entry.get("grade_en"),
            "grade_ar": entry.get("grade_ar"),
        })
    return entries


def classical_source_keys(profile):
    return {
        (entry["source"], entry["entry_id"])
        for entry in classical_source_entries(profile)
        if entry["entry_id"] is not None
    }


def canonical_relationship_ids(profile, field):
    values = profile.get(field)
    if not isinstance(values, list):
        return set()
    return {value for value in map(canonical_id, values) if value is not None}


def profile_evidence(profile, include_relationship_ids=False):
    aliases = profile.get("namings")
    aliases = aliases if isinstance(aliases, list) else []
    teachers = canonical_relationship_ids(profile, "teachers")
    students = canonical_relationship_ids(profile, "students")
    result = {
        "itqan_profile_id": canonical_id(profile.get("id")),
        "canonical_name": profile.get("full_name"),
        "normalized_canonical_name": normalized_field(profile.get("full_name")),
        "aliases": aliases,
        "upstream_source_identifiers": source_identifiers(profile),
        "classical_sources": classical_source_entries(profile),
        "kunya": profile.get("kunya"),
        "nasab": profile.get("nasab"),
        "death": profile.get("death"),
        "city": profile.get("city"),
        "teacher_count": len(teachers),
        "student_count": len(students),
    }
    if include_relationship_ids:
        result["teacher_profile_ids"] = sorted(teachers, key=_id_sort)
        result["student_profile_ids"] = sorted(students, key=_id_sort)
    return result


def pair_evidence(left, right):
    left_keys = logical_identity_keys(left)
    right_keys = logical_identity_keys(right)
    shared_identity = sorted(left_keys & right_keys)
    shared_classical = sorted(classical_source_keys(left) & classical_source_keys(right))
    shared_teachers = sorted(
        canonical_relationship_ids(left, "teachers")
        & canonical_relationship_ids(right, "teachers"),
        key=_id_sort,
    )
    shared_students = sorted(
        canonical_relationship_ids(left, "students")
        & canonical_relationship_ids(right, "students"),
        key=_id_sort,
    )
    left_representations = {
        normalized_field(left.get("full_name")),
        *[
            normalized_field(value)
            for value in (left.get("namings") or [])
            if filled(value)
        ],
    }
    right_representations = {
        normalized_field(right.get("full_name")),
        *[
            normalized_field(value)
            for value in (right.get("namings") or [])
            if filled(value)
        ],
    }
    left_representations.discard("")
    right_representations.discard("")
    return {
        "profile_ids": [
            canonical_id(left.get("id")), canonical_id(right.get("id"))
        ],
        "shared_exact_representations": sorted(left_representations & right_representations),
        "shared_upstream_record_keys": [
            {"key_type": key_type, "value": value}
            for key_type, value in shared_identity
        ],
        "shared_classical_source_entries": [
            {"source": source, "entry_id": entry_id}
            for source, entry_id in shared_classical
        ],
        "kunya_equal": tri_state_equal(left.get("kunya"), right.get("kunya"), normalized_field),
        "nasab_equal": tri_state_equal(left.get("nasab"), right.get("nasab"), normalized_field),
        "death_equal": tri_state_equal(left.get("death"), right.get("death"), normalized_field),
        "death_contradiction": death_contradiction(left.get("death"), right.get("death")),
        "city_equal": tri_state_equal(left.get("city"), right.get("city"), normalized_field),
        "shared_teacher_profile_ids": shared_teachers,
        "shared_student_profile_ids": shared_students,
    }


def classify_pair(evidence):
    """Apply explicit rules with conflicts taking precedence over assertions."""

    shared_identity = bool(evidence["shared_upstream_record_keys"])
    shared_source_entry = bool(evidence["shared_classical_source_entries"])
    contradiction = evidence["death_contradiction"] == "TRUE"
    if shared_identity and not contradiction:
        return "DUPLICATE_PROFILE_STRONGLY_SUPPORTED"
    if contradiction and not shared_identity and not shared_source_entry:
        return "DISTINCT_PERSON_STRONGLY_SUPPORTED"
    return "UNRESOLVED_PROFILE_MULTIPLICITY"


def profile_representations(profile):
    canonical = normalized_field(profile.get("full_name"))
    values = defaultdict(set)
    if canonical:
        values[canonical].add("canonical")
    aliases = profile.get("namings")
    if isinstance(aliases, list):
        for alias in aliases:
            normalized = normalized_field(alias)
            if normalized:
                values[normalized].add("alias")
    return values


def build_exact_group_indexes(profiles):
    canonical_index = defaultdict(set)
    representation_index = defaultdict(set)
    representation_sources = defaultdict(lambda: defaultdict(set))
    by_id = {}
    for profile in profiles:
        profile_id = canonical_id(profile.get("id"))
        if profile_id is None:
            continue
        by_id[profile_id] = profile
        canonical = normalized_field(profile.get("full_name"))
        if canonical:
            canonical_index[canonical].add(profile_id)
        for representation, sources in profile_representations(profile).items():
            representation_index[representation].add(profile_id)
            representation_sources[representation][profile_id].update(sources)
    return by_id, canonical_index, representation_index, representation_sources


def duplicate_value_groups(profile_ids, profiles_by_id, extractor):
    values = defaultdict(list)
    for profile_id in profile_ids:
        for value in extractor(profiles_by_id[profile_id]):
            values[value].append(profile_id)
    return {
        value: sorted(ids, key=_id_sort)
        for value, ids in values.items()
        if len(ids) > 1
    }


def contradiction_summary(profile_ids, profiles_by_id, example_limit=30):
    dated = [
        profile_id
        for profile_id in profile_ids
        if death_interval(profiles_by_id[profile_id].get("death")) is not None
    ]
    count = 0
    examples = []
    involved = set()
    for left_id, right_id in itertools.combinations(dated, 2):
        left = profiles_by_id[left_id]
        right = profiles_by_id[right_id]
        if death_contradiction(left.get("death"), right.get("death")) != "TRUE":
            continue
        count += 1
        involved.update((left_id, right_id))
        if len(examples) < example_limit:
            examples.append({
                "profile_a_id": left_id,
                "profile_a_death": left.get("death"),
                "profile_b_id": right_id,
                "profile_b_death": right.get("death"),
                "rule": f"non-overlapping parsed death ranges separated by more than {DEATH_CONTRADICTION_TOLERANCE_YEARS} years",
            })
    state = "UNKNOWN" if len(dated) < 2 else ("TRUE" if count else "FALSE")
    return {
        "death_contradiction": state,
        "contradictory_pair_count": count,
        "contradictory_profile_ids": sorted(involved, key=_id_sort),
        "examples": examples,
        "examples_truncated": count > len(examples),
    }


def build_group_record(
    normalized_key,
    profile_ids,
    profiles_by_id,
    canonical_index,
    representation_sources,
):
    profile_ids = sorted(profile_ids, key=_id_sort)
    canonical_ids = canonical_index.get(normalized_key, set()) & set(profile_ids)
    canonical_group = len(canonical_ids) > 1
    grouping_kind = "NARROW_CANONICAL_NAME" if canonical_group else "NARROW_EXACT_REPRESENTATION"
    group_id = stable_group_id(grouping_kind, normalized_key, profile_ids)

    shared_identity = duplicate_value_groups(
        profile_ids, profiles_by_id, logical_identity_keys
    )
    shared_classical = duplicate_value_groups(
        profile_ids, profiles_by_id, classical_source_keys
    )
    shared_kunya = duplicate_value_groups(
        profile_ids,
        profiles_by_id,
        lambda profile: {normalized_field(profile.get("kunya"))}
        if normalized_field(profile.get("kunya")) else set(),
    )
    shared_nasab = duplicate_value_groups(
        profile_ids,
        profiles_by_id,
        lambda profile: {normalized_field(profile.get("nasab"))}
        if normalized_field(profile.get("nasab")) else set(),
    )
    shared_death = duplicate_value_groups(
        profile_ids,
        profiles_by_id,
        lambda profile: {normalized_field(profile.get("death"))}
        if normalized_field(profile.get("death")) else set(),
    )
    shared_city = duplicate_value_groups(
        profile_ids,
        profiles_by_id,
        lambda profile: {normalized_field(profile.get("city"))}
        if normalized_field(profile.get("city")) else set(),
    )
    shared_teachers = duplicate_value_groups(
        profile_ids,
        profiles_by_id,
        lambda profile: canonical_relationship_ids(profile, "teachers"),
    )
    shared_students = duplicate_value_groups(
        profile_ids,
        profiles_by_id,
        lambda profile: canonical_relationship_ids(profile, "students"),
    )
    contradictions = contradiction_summary(profile_ids, profiles_by_id)

    contextual = normalized_key in {
        normalized_field(value) for value in RELATIVE_OR_CONTEXT_ALIASES
    }
    identity_bearing_representation = (
        canonical_group
        or (not contextual and len(normalized_key.split()) >= 3)
    )
    direct_source_overlap = bool(shared_identity or shared_classical)
    canonical_composite = canonical_group and any((
        shared_kunya, shared_nasab, shared_death, shared_city,
        shared_teachers, shared_students,
    ))
    alias_composite = (
        identity_bearing_representation
        and not canonical_group
        and (
            (shared_death and any((shared_kunya, shared_nasab, shared_city)))
            or (shared_kunya and shared_nasab)
            or (shared_teachers and shared_students)
        )
    )
    contradictory_identity_bearing = (
        identity_bearing_representation
        and contradictions["contradictory_pair_count"] > 0
    )
    candidate_status = (
        "POSSIBLE_DUPLICATE_PROFILE"
        if direct_source_overlap or canonical_composite or alias_composite
        or contradictory_identity_bearing
        else "SAME_NAME_ONLY"
    )

    if len(profile_ids) == 2:
        conceptual_class = classify_pair(pair_evidence(
            profiles_by_id[profile_ids[0]], profiles_by_id[profile_ids[1]]
        ))
        if (
            conceptual_class == "DISTINCT_PERSON_STRONGLY_SUPPORTED"
            and not identity_bearing_representation
        ):
            conceptual_class = "UNRESOLVED_PROFILE_MULTIPLICITY"
    elif shared_identity and not contradictions["contradictory_pair_count"]:
        # A group-wide strong class requires one upstream record key shared by
        # every profile, not just by an arbitrary subset.
        group_wide_key = any(len(ids) == len(profile_ids) for ids in shared_identity.values())
        conceptual_class = (
            "DUPLICATE_PROFILE_STRONGLY_SUPPORTED"
            if group_wide_key else "UNRESOLVED_PROFILE_MULTIPLICITY"
        )
    else:
        conceptual_class = "UNRESOLVED_PROFILE_MULTIPLICITY"

    reasons = [
        "EXACT_NARROW_NORMALIZED_CANONICAL_NAME"
        if canonical_group else "EXACT_NARROW_NORMALIZED_CANONICAL_OR_ALIAS_REPRESENTATION"
    ]
    reason_map = (
        (shared_identity, "SHARED_UPSTREAM_RECORD_KEY"),
        (shared_classical, "SHARED_CLASSICAL_SOURCE_ENTRY_REFERENCE"),
        (shared_kunya, "EXACT_NONEMPTY_KUNYA_EQUALITY"),
        (shared_nasab, "EXACT_NONEMPTY_NASAB_EQUALITY"),
        (shared_death, "EXACT_NONEMPTY_DEATH_TEXT_EQUALITY"),
        (shared_city, "EXACT_NONEMPTY_CITY_EQUALITY"),
        (shared_teachers, "SHARED_TEACHER_PROFILE_REFERENCE"),
        (shared_students, "SHARED_STUDENT_PROFILE_REFERENCE"),
    )
    reasons.extend(label for evidence, label in reason_map if evidence)
    if contextual:
        reasons.append("NON_IDENTITY_BEARING_CONTEXTUAL_ALIAS")

    profiles = [profiles_by_id[profile_id] for profile_id in profile_ids]
    missing_fields = {
        field: sum(not filled(profile.get(field)) for profile in profiles)
        for field in ("kunya", "nasab", "death", "city", "teachers", "students", "classical_sources")
    }
    source_origins = Counter(
        source_identifiers(profile).get("origin") or "UNKNOWN"
        for profile in profiles
    )
    evidence = {
        "shared_upstream_record_keys": [
            {
                "key_type": key[0],
                "value": key[1],
                "profile_ids": ids,
            }
            for key, ids in sorted(shared_identity.items())
        ],
        "shared_classical_source_entries": [
            {"source": key[0], "entry_id": key[1], "profile_ids": ids}
            for key, ids in sorted(shared_classical.items())
        ],
        "shared_kunya_values": shared_kunya,
        "shared_nasab_values": shared_nasab,
        "shared_death_values": shared_death,
        "shared_city_values": shared_city,
        "shared_teacher_profile_references": shared_teachers,
        "shared_student_profile_references": shared_students,
    }
    return {
        "group_id": group_id,
        "grouping_kind": grouping_kind,
        "normalized_grouping_key": normalized_key,
        "itqan_profile_ids": profile_ids,
        "group_size": len(profile_ids),
        "canonical_profile_ids_for_key": sorted(canonical_ids, key=_id_sort),
        "representation_sources_by_profile": {
            profile_id: sorted(representation_sources[normalized_key][profile_id])
            for profile_id in profile_ids
        },
        "candidate_status": candidate_status,
        "identity_bearing_representation": identity_bearing_representation,
        "conceptual_class": conceptual_class,
        "deterministic_grouping_reasons": reasons,
        "source_origin_distribution": dict(sorted(source_origins.items())),
        "evidence": evidence,
        "contradictions": contradictions,
        "missing_evidence_counts": missing_fields,
    }


def build_upstream_key_index(profiles):
    index = defaultdict(set)
    for profile in profiles:
        profile_id = canonical_id(profile.get("id"))
        if profile_id is None:
            continue
        for key in logical_identity_keys(profile):
            index[key].add(profile_id)
    return index


def build_upstream_key_group(key, profile_ids, profiles_by_id):
    """Build a candidate group from a duplicated upstream record key."""

    profile_ids = sorted(profile_ids, key=_id_sort)
    key_type, key_value = key
    grouping_key = f"{key_type}:{key_value}"
    group_id = stable_group_id("SHARED_UPSTREAM_RECORD_KEY", grouping_key, profile_ids)
    contradictions = contradiction_summary(profile_ids, profiles_by_id)
    shared_classical = duplicate_value_groups(
        profile_ids, profiles_by_id, classical_source_keys
    )
    shared_teachers = duplicate_value_groups(
        profile_ids,
        profiles_by_id,
        lambda profile: canonical_relationship_ids(profile, "teachers"),
    )
    shared_students = duplicate_value_groups(
        profile_ids,
        profiles_by_id,
        lambda profile: canonical_relationship_ids(profile, "students"),
    )
    profiles = [profiles_by_id[profile_id] for profile_id in profile_ids]
    conceptual_class = (
        "UNRESOLVED_PROFILE_MULTIPLICITY"
        if contradictions["contradictory_pair_count"]
        else "DUPLICATE_PROFILE_STRONGLY_SUPPORTED"
    )
    missing_fields = {
        field: sum(not filled(profile.get(field)) for profile in profiles)
        for field in (
            "kunya", "nasab", "death", "city", "teachers", "students",
            "classical_sources",
        )
    }
    return {
        "group_id": group_id,
        "grouping_kind": "SHARED_UPSTREAM_RECORD_KEY",
        "normalized_grouping_key": None,
        "upstream_grouping_key": {"key_type": key_type, "value": key_value},
        "itqan_profile_ids": profile_ids,
        "group_size": len(profile_ids),
        "canonical_profile_ids_for_key": [],
        "representation_sources_by_profile": {
            profile_id: [] for profile_id in profile_ids
        },
        "candidate_status": "POSSIBLE_DUPLICATE_PROFILE",
        "identity_bearing_representation": False,
        "conceptual_class": conceptual_class,
        "deterministic_grouping_reasons": ["SHARED_UPSTREAM_RECORD_KEY"],
        "source_origin_distribution": dict(Counter(
            source_identifiers(profile).get("origin") or "UNKNOWN"
            for profile in profiles
        )),
        "evidence": {
            "shared_upstream_record_keys": [{
                "key_type": key_type,
                "value": key_value,
                "profile_ids": profile_ids,
            }],
            "shared_classical_source_entries": [
                {"source": item[0], "entry_id": item[1], "profile_ids": ids}
                for item, ids in sorted(shared_classical.items())
            ],
            "shared_kunya_values": {},
            "shared_nasab_values": {},
            "shared_death_values": {},
            "shared_city_values": {},
            "shared_teacher_profile_references": shared_teachers,
            "shared_student_profile_references": shared_students,
        },
        "contradictions": contradictions,
        "missing_evidence_counts": missing_fields,
    }


def group_size_distribution(groups):
    counts = Counter(len(ids) for ids in groups.values() if len(ids) > 1)
    return {str(size): counts[size] for size in sorted(counts)}


def source_id_audit(profiles):
    field_extractors = {
        "global_id": lambda profile: canonical_id(profile.get("global_id")),
        "top_level_gk_id": lambda profile: canonical_id(profile.get("gk_id")),
        "provenance_arsanad_id": lambda profile: source_identifiers(profile)["provenance_arsanad_id"],
        "provenance_gk_id": lambda profile: source_identifiers(profile)["provenance_gk_id"],
    }
    report = {}
    for field, extractor in field_extractors.items():
        values = defaultdict(list)
        for profile in profiles:
            value = extractor(profile)
            if value is not None:
                values[value].append(canonical_id(profile.get("id")))
        collisions = {key: ids for key, ids in values.items() if len(ids) > 1}
        report[field] = {
            "profiles_with_value": sum(len(ids) for ids in values.values()),
            "unique_values": len(values),
            "duplicate_value_groups": len(collisions),
            "profiles_in_duplicate_value_groups": sum(len(ids) for ids in collisions.values()),
            "largest_duplicate_value_group": max(map(len, collisions.values()), default=0),
        }

    arsanad_equal = 0
    arsanad_total = 0
    global_matches_provenance = 0
    global_total = 0
    for profile in profiles:
        identifiers = source_identifiers(profile)
        if identifiers["provenance_arsanad_id"] is not None:
            arsanad_total += 1
            arsanad_equal += (
                identifiers["provenance_arsanad_id"] == identifiers["itqan_profile_id"]
            )
        if identifiers["global_id"] is not None:
            global_total += 1
            global_matches_provenance += (
                identifiers["global_id"] == identifiers["provenance_kaggle_id"]
            )
    report["semantic_checks"] = {
        "provenance_arsanad_id_present": arsanad_total,
        "provenance_arsanad_id_equals_itqan_profile_id": arsanad_equal,
        "global_id_present": global_total,
        "global_id_equals_provenance_kaggle_id": global_matches_provenance,
    }

    classical_values = defaultdict(list)
    for profile in profiles:
        profile_id = canonical_id(profile.get("id"))
        for key in classical_source_keys(profile):
            classical_values[key].append(profile_id)
    classical_collisions = {
        key: ids for key, ids in classical_values.items() if len(ids) > 1
    }
    report["classical_source_entry_keys"] = {
        "unique_source_entry_keys": len(classical_values),
        "shared_source_entry_groups": len(classical_collisions),
        "profiles_in_shared_source_entry_groups": len({
            profile_id
            for ids in classical_collisions.values()
            for profile_id in ids
        }),
        "memberships_in_shared_source_entry_groups": sum(
            len(ids) for ids in classical_collisions.values()
        ),
        "largest_shared_source_entry_group": max(
            map(len, classical_collisions.values()), default=0
        ),
        "identity_interpretation": "source-local references only; parser IDs are not globally unique historical-person keys",
    }
    return report


def profile_group_memberships(group_records):
    suspected = defaultdict(set)
    contradictory = defaultdict(set)
    by_class = defaultdict(lambda: defaultdict(set))
    for group in group_records:
        if group["candidate_status"] != "POSSIBLE_DUPLICATE_PROFILE":
            continue
        group_id = group["group_id"]
        for profile_id in group["itqan_profile_ids"]:
            suspected[profile_id].add(group_id)
            by_class[group["conceptual_class"]][profile_id].add(group_id)
        for profile_id in group["contradictions"]["contradictory_profile_ids"]:
            contradictory[profile_id].add(group_id)
    return suspected, contradictory, by_class


def aggregate_suspected_profile_sets(group_records):
    """Collapse multiple exact keys that nominate the identical profile set.

    The JSONL retains every deterministic grouping key.  Metrics use unique
    profile sets so a pair sharing several aliases and one upstream key is not
    counted several times as several possible historical-identity problems.
    """

    grouped = defaultdict(list)
    for group in group_records:
        if group["candidate_status"] == "POSSIBLE_DUPLICATE_PROFILE":
            grouped[tuple(group["itqan_profile_ids"])].append(group)
    output = []
    for profile_ids, records in grouped.items():
        shared_upstream = any(
            len(item.get("profile_ids", [])) == len(profile_ids)
            for record in records
            for item in record["evidence"]["shared_upstream_record_keys"]
        )
        shared_classical = any(
            len(item.get("profile_ids", [])) == len(profile_ids)
            for record in records
            for item in record["evidence"]["shared_classical_source_entries"]
        )
        contradictory_ids = {
            profile_id
            for record in records
            for profile_id in record["contradictions"]["contradictory_profile_ids"]
        }
        contradiction = bool(contradictory_ids)
        classes = {record["conceptual_class"] for record in records}
        if shared_upstream and not contradiction:
            conceptual_class = "DUPLICATE_PROFILE_STRONGLY_SUPPORTED"
        elif (
            len(profile_ids) == 2
            and "DISTINCT_PERSON_STRONGLY_SUPPORTED" in classes
            and not shared_upstream
            and not shared_classical
        ):
            conceptual_class = "DISTINCT_PERSON_STRONGLY_SUPPORTED"
        else:
            conceptual_class = "UNRESOLVED_PROFILE_MULTIPLICITY"
        output.append({
            "group_id": stable_group_id("UNIQUE_PROFILE_SET", "", profile_ids),
            "itqan_profile_ids": list(profile_ids),
            "candidate_status": "POSSIBLE_DUPLICATE_PROFILE",
            "conceptual_class": conceptual_class,
            "source_group_ids": sorted(record["group_id"] for record in records),
            "evidence": {
                "shared_upstream_record_keys": shared_upstream,
                "shared_classical_source_entries": shared_classical,
            },
            "contradictions": {
                "contradictory_pair_count": max(
                    record["contradictions"]["contradictory_pair_count"]
                    for record in records
                ),
                "contradictory_profile_ids": sorted(contradictory_ids, key=_id_sort),
            },
        })
    return sorted(output, key=lambda group: group["group_id"])


def audit_provisional_81(group_records):
    rows = load_jsonl(BASE_CANDIDATES)
    frozen = [
        row for row in rows
        if row.get("provisional_tier") in {"EXACT_RESOLVED", "ALIAS_RESOLVED"}
    ]
    suspected, contradictory, by_class = profile_group_memberships(group_records)
    details = []
    for row in frozen:
        profile_id = canonical_id(row.get("provisional_resolved_itqan_id"))
        details.append({
            "mis_narrator_id": row.get("mis_narrator_id"),
            "provisional_tier": row.get("provisional_tier"),
            "itqan_profile_id": profile_id,
            "suspected_duplicate_group_ids": sorted(suspected.get(profile_id, set())),
            "contradictory_evidence_group_ids": sorted(contradictory.get(profile_id, set())),
            "conceptual_classes": sorted(
                class_name for class_name, memberships in by_class.items()
                if profile_id in memberships
            ),
        })
    return {
        "population": len(frozen),
        "frozen_tiers": dict(Counter(row["provisional_tier"] for row in frozen)),
        "targeting_audit_singleton_profiles": sum(
            not row["suspected_duplicate_group_ids"] for row in details
        ),
        "targeting_suspected_duplicate_groups": sum(
            bool(row["suspected_duplicate_group_ids"]) for row in details
        ),
        "with_conflicting_profile_evidence": sum(
            bool(row["contradictory_evidence_group_ids"]) for row in details
        ),
        "status_mutations": 0,
        "details": details,
    }


def exact_short_unique_targets():
    rows = load_jsonl(UNMATCHED_CANDIDATES)
    selected = []
    for row in rows:
        ids = [canonical_id(value) for value in row.get("mis_short_name_candidate_ids", [])]
        ids = [value for value in ids if value is not None]
        if len(ids) == 1:
            selected.append({
                "mis_narrator_id": row.get("mis_narrator_id"),
                "itqan_profile_id": ids[0],
            })
    return selected


def audit_short_name_890(group_records):
    rows = exact_short_unique_targets()
    suspected, contradictory, by_class = profile_group_memberships(group_records)
    details = []
    for row in rows:
        profile_id = row["itqan_profile_id"]
        classes = sorted(
            class_name for class_name, memberships in by_class.items()
            if profile_id in memberships
        )
        details.append({
            **row,
            "suspected_duplicate_group_ids": sorted(suspected.get(profile_id, set())),
            "conceptual_classes": classes,
            "contradictory_evidence_group_ids": sorted(contradictory.get(profile_id, set())),
        })
    return {
        "population": len(rows),
        "target_profiles_audit_singleton": sum(
            not row["suspected_duplicate_group_ids"] for row in details
        ),
        "target_profiles_in_suspected_duplicate_groups": sum(
            bool(row["suspected_duplicate_group_ids"]) for row in details
        ),
        "target_profiles_in_strongly_supported_duplicate_groups": sum(
            "DUPLICATE_PROFILE_STRONGLY_SUPPORTED" in row["conceptual_classes"]
            for row in details
        ),
        "target_profiles_in_strongly_supported_distinct_groups": sum(
            "DISTINCT_PERSON_STRONGLY_SUPPORTED" in row["conceptual_classes"]
            for row in details
        ),
        "target_profiles_in_unresolved_groups": sum(
            "UNRESOLVED_PROFILE_MULTIPLICITY" in row["conceptual_classes"]
            for row in details
        ),
        "target_profiles_with_conflicting_evidence": sum(
            bool(row["contradictory_evidence_group_ids"]) for row in details
        ),
        "promotions": 0,
        "details": details,
    }


def mis_relevant_audit(group_records):
    current_rows = load_jsonl(BASE_CANDIDATES)
    exact_by_mis = defaultdict(set)
    for row in current_rows:
        mis_id = str(row.get("mis_narrator_id"))
        for candidate in row.get("candidates", []):
            profile_id = canonical_id(candidate.get("itqan_id"))
            if profile_id is not None:
                exact_by_mis[mis_id].add(profile_id)
    for row in load_jsonl(UNMATCHED_CANDIDATES):
        mis_id = str(row.get("mis_narrator_id"))
        for value in row.get("mis_short_name_candidate_ids", []):
            profile_id = canonical_id(value)
            if profile_id is not None:
                exact_by_mis[mis_id].add(profile_id)

    candidate_profiles = {value for values in exact_by_mis.values() for value in values}
    group_by_id = {group["group_id"]: group for group in group_records}
    suspected, _, _ = profile_group_memberships(group_records)
    touched_ids = {
        group_id
        for profile_id in candidate_profiles
        for group_id in suspected.get(profile_id, set())
    }
    touched = [group_by_id[group_id] for group_id in touched_ids]
    groups_by_class = Counter(group["conceptual_class"] for group in touched)
    narrators_by_class = Counter()
    narrators_with_any = 0
    for profile_ids in exact_by_mis.values():
        classes = {
            group_by_id[group_id]["conceptual_class"]
            for profile_id in profile_ids
            for group_id in suspected.get(profile_id, set())
        }
        if classes:
            narrators_with_any += 1
        for class_name in classes:
            narrators_by_class[class_name] += 1
    return {
        "mis_population": len(current_rows),
        "mis_narrators_with_any_current_or_exact_short_candidate": sum(
            bool(values) for values in exact_by_mis.values()
        ),
        "distinct_itqan_candidate_profiles": len(candidate_profiles),
        "suspected_internal_groups_touched": len(touched),
        "suspected_internal_groups_by_class": dict(groups_by_class),
        "mis_narrators_touching_any_suspected_internal_group": narrators_with_any,
        "mis_narrators_touching_groups_by_class": dict(narrators_by_class),
        "interpretation": "Counts are diagnostic group exposure, not MIS-to-person resolutions.",
    }


def strict_triage_case_audit(profiles_by_id):
    with open(STRICT_TRIAGE, "r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    output = []
    for row in rows:
        diagnostic_label = row.get("assistant_triage", "")
        if diagnostic_label not in STRICT_TRIAGE_TARGET_LABELS:
            continue
        profile_ids = [
            value for value in row.get("visible_exact_short_itqan_ids", "").split("|")
            if value
        ]
        missing_ids = [value for value in profile_ids if value not in profiles_by_id]
        pair_records = []
        for left_id, right_id in itertools.combinations(profile_ids, 2):
            if left_id not in profiles_by_id or right_id not in profiles_by_id:
                continue
            evidence = pair_evidence(profiles_by_id[left_id], profiles_by_id[right_id])
            pair_records.append({
                "profile_a_id": left_id,
                "profile_b_id": right_id,
                "conceptual_class": classify_pair(evidence),
                "evidence": evidence,
            })
        classes = Counter(pair["conceptual_class"] for pair in pair_records)
        if len(classes) == 1 and pair_records:
            case_class = next(iter(classes))
        else:
            case_class = "UNRESOLVED_PROFILE_MULTIPLICITY"
        missing_evidence = {
            field: [
                profile_id for profile_id in profile_ids
                if profile_id in profiles_by_id
                and not filled(profiles_by_id[profile_id].get(field))
            ]
            for field in ("kunya", "nasab", "death", "city", "teachers", "students", "classical_sources")
        }
        output.append({
            "review_id": row.get("review_id"),
            "mis_narrator_id": row.get("mis_narrator_id"),
            "mis_name": row.get("mis_name"),
            "mis_short_name": row.get("mis_short_name"),
            "diagnostic_selector_label_not_ground_truth": diagnostic_label,
            "candidate_itqan_profile_ids": profile_ids,
            "missing_profile_ids": missing_ids,
            "profiles": [
                profile_evidence(profiles_by_id[profile_id], include_relationship_ids=True)
                for profile_id in profile_ids if profile_id in profiles_by_id
            ],
            "pair_audits": pair_records,
            "case_conceptual_class": case_class,
            "missing_evidence_by_field": missing_evidence,
            "reviewer_fields_preserved": {
                "reviewer_selected_itqan_id": row.get("reviewer_selected_itqan_id", ""),
                "diagnostic_verdict": row.get("diagnostic_verdict", ""),
                "notes": row.get("notes", ""),
            },
        })
    return output


def candidate_pair_pool(group_records, profiles_by_id, mis_profile_ids):
    pools = defaultdict(list)
    seen_by_pool = defaultdict(set)

    def add(stratum, group, left_id, right_id):
        if left_id == right_id:
            return
        ordered = tuple(sorted((left_id, right_id), key=_id_sort))
        key = (group["group_id"], ordered)
        if key in seen_by_pool[stratum]:
            return
        seen_by_pool[stratum].add(key)
        pools[stratum].append((group, *ordered))

    for group in group_records:
        ids = group["itqan_profile_ids"]
        # Adjacent pairs keep large groups bounded; small groups are exhaustive.
        pairs = list(itertools.combinations(ids, 2)) if len(ids) <= 12 else list(zip(ids, ids[1:]))
        if len(ids) > 12:
            pairs.append((ids[0], ids[-1]))
        for left_id, right_id in pairs:
            evidence = pair_evidence(profiles_by_id[left_id], profiles_by_id[right_id])
            if group["grouping_kind"] == "NARROW_CANONICAL_NAME":
                add("SAME_CANONICAL_NAME", group, left_id, right_id)
                if evidence["kunya_equal"] == "TRUE":
                    add("SAME_NAME_AND_KUNYA", group, left_id, right_id)
                if evidence["death_equal"] == "TRUE":
                    add("SAME_NAME_AND_DEATH", group, left_id, right_id)
            if evidence["shared_upstream_record_keys"] or evidence["shared_classical_source_entries"]:
                add("SOURCE_OVERLAP", group, left_id, right_id)
            if evidence["death_contradiction"] == "TRUE":
                add("APPARENT_CONTRADICTION", group, left_id, right_id)
            if group["group_size"] >= 20:
                add("LARGE_COLLISION_GROUP", group, left_id, right_id)
            if left_id in mis_profile_ids or right_id in mis_profile_ids:
                add("MIS_RELEVANT", group, left_id, right_id)
    return pools


def frozen_review_guard(path):
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if any(row.get("reviewer_verdict", "").strip() or row.get("notes", "").strip() for row in rows):
        raise RuntimeError(
            f"Refusing to overwrite reviewer-entered values in frozen artifact: {path}"
        )


def build_review_artifact(group_records, profiles_by_id, seed=REVIEW_SEED, per_stratum=20):
    current = load_jsonl(BASE_CANDIDATES)
    mis_profile_ids = {
        canonical_id(candidate.get("itqan_id"))
        for row in current
        for candidate in row.get("candidates", [])
        if canonical_id(candidate.get("itqan_id")) is not None
    }
    mis_profile_ids.update(row["itqan_profile_id"] for row in exact_short_unique_targets())
    pools = candidate_pair_pool(group_records, profiles_by_id, mis_profile_ids)
    rng = random.Random(seed)
    visible = []
    hidden = []
    selected_pairs = set()
    counts = Counter()
    stratum_order = (
        "SOURCE_OVERLAP",
        "APPARENT_CONTRADICTION",
        "SAME_NAME_AND_KUNYA",
        "SAME_NAME_AND_DEATH",
        "LARGE_COLLISION_GROUP",
        "MIS_RELEVANT",
        "SAME_CANONICAL_NAME",
    )
    for stratum in stratum_order:
        pool = list(pools.get(stratum, []))
        rng.shuffle(pool)
        for group, left_id, right_id in pool:
            pair_key = tuple(sorted((left_id, right_id), key=_id_sort))
            if pair_key in selected_pairs:
                continue
            selected_pairs.add(pair_key)
            counts[stratum] += 1
            review_id = f"ITQ-DUP-{len(visible) + 1:04d}"
            pair = pair_evidence(profiles_by_id[left_id], profiles_by_id[right_id])
            visible.append({
                "review_id": review_id,
                "group_id": group["group_id"],
                "itqan_profile_a_id": left_id,
                "profile_a_evidence_json": json_compact(profile_evidence(profiles_by_id[left_id])),
                "itqan_profile_b_id": right_id,
                "profile_b_evidence_json": json_compact(profile_evidence(profiles_by_id[right_id])),
                "shared_mechanical_evidence_json": json_compact({
                    key: value for key, value in pair.items()
                    if key not in {"profile_ids", "death_contradiction"}
                }),
                "reviewer_verdict": "",
                "notes": "",
            })
            hidden.append({
                "review_id": review_id,
                "sampling_stratum": stratum,
                "automatic_conceptual_class": group["conceptual_class"],
                "candidate_status": group["candidate_status"],
                "deterministic_grouping_reasons_json": json_compact(group["deterministic_grouping_reasons"]),
                "contradictions_json": json_compact(group["contradictions"]),
                "sampling_seed": seed,
            })
            if counts[stratum] >= per_stratum:
                break
    return visible, hidden, {
        "artifact_version": AUDIT_VERSION,
        "question": "Do these profiles appear to represent the same historical narrator?",
        "allowed_reviewer_verdicts": list(ALLOWED_REVIEW_VERDICTS),
        "sampling_seed": seed,
        "target_per_stratum": per_stratum,
        "sampled_per_stratum": dict(counts),
        "visible_rows": len(visible),
        "hidden_rows": len(hidden),
        "visible_columns": list(VISIBLE_REVIEW_COLUMNS),
        "hidden_columns": list(HIDDEN_REVIEW_COLUMNS),
        "metadata_leakage_policy": {
            "automatic_duplicate_label_visible": False,
            "candidate_score_visible": False,
            "grouping_confidence_visible": False,
            "algorithmic_rank_visible": False,
        },
        "reviewer_fields_initialized_blank": True,
        "freeze_policy": "generator refuses to overwrite nonblank reviewer_verdict or notes",
    }


def identity_semantics_evidence():
    base = f"https://github.com/R3GENESI5/Itqan/blob/{UPSTREAM_COMMIT}"
    return {
        "upstream_repository": "https://github.com/R3GENESI5/Itqan",
        "audited_commit": UPSTREAM_COMMIT,
        "findings": [
            {
                "question": "How is an Itqan profile ID created?",
                "status": "CONFIRMED",
                "answer": "The current builder retains foundation row IDs and allocates sequential new IDs for unmatched parsed source entries; it is a generated profile-record key.",
                "evidence": f"{base}/src/build_rijal_database.py",
            },
            {
                "question": "Can one profile contain multiple classical sources?",
                "status": "CONFIRMED",
                "answer": "Matched parsed entries enrich one profile through classical_sources keyed by source.",
                "evidence": f"{base}/src/build_rijal_database.py",
            },
            {
                "question": "What merge logic is used during the current build?",
                "status": "CONFIRMED",
                "answer": "Exact normalized-name matching is followed by unique four-token or three-token prefix fallback; unmatched entries become new profiles.",
                "evidence": f"{base}/src/build_rijal_database.py",
            },
            {
                "question": "Is there separate profile deduplication logic?",
                "status": "CONFIRMED",
                "answer": "A separate union-find deduplication script uses deterministic but heuristic name/death/kunya/city rules and can absorb profile IDs.",
                "evidence": f"{base}/src/dedup_narrators.py",
            },
            {
                "question": "Are source-specific IDs retained?",
                "status": "CONFIRMED",
                "answer": "Kaggle scholar_indx is retained as global_id; classical entries retain source-local entry_id values; provenance fields retain additional record references.",
                "evidence": f"{base}/src/integrate_kaggle_narrators.py",
            },
            {
                "question": "Are classical entry IDs globally unique person IDs?",
                "status": "CONFIRMED",
                "answer": "No. The parser creates source-local entry IDs and indexes, and measured collisions show the same source/entry key on many profiles.",
                "evidence": f"{base}/src/parse_rijal_v2.py",
            },
            {
                "question": "Does Itqan expose an official canonical historical-person identity layer?",
                "status": "UNKNOWN",
                "answer": "No separate canonical-person identifier or crosswalk covering all profiles was found in the audited documentation, code, manifest, or profile schema.",
                "evidence": f"{base}/README.md",
            },
            {
                "question": "What does the README intend profiles to represent?",
                "status": "INFERRED",
                "answer": "The README describes a unified narrator database, suggesting person-oriented intent, but the build and residual data do not guarantee one profile per historical person.",
                "evidence": f"{base}/README.md",
            },
        ],
        "repository_data_code_discrepancies": [
            "The checked-in v1.20 profiles contain provenance/id_score/confidence/unique_key fields that the audited current build script does not construct.",
            "The checked-in manifest is v1.20, while the audited current builder writes a 3.0 manifest.",
            "The repository dedup log lists absorbed IDs that remain present in the shipped v1.20 shards; the log is not proof that those merges were applied to this snapshot.",
        ],
    }


def candidate_artifact_record(group, profiles_by_id):
    """Expand one compact in-memory group into the required JSONL schema."""

    return {
        **group,
        "canonical_names": [
            profiles_by_id[profile_id].get("full_name")
            for profile_id in group["itqan_profile_ids"]
        ],
        "normalized_names": [
            normalized_field(profiles_by_id[profile_id].get("full_name"))
            for profile_id in group["itqan_profile_ids"]
        ],
        "profiles": [
            profile_evidence(profiles_by_id[profile_id])
            for profile_id in group["itqan_profile_ids"]
        ],
        "artifact_label": "DUPLICATION_CANDIDATE_NOT_A_MERGE",
        # No canonical_person_id is emitted: this milestone is an audit.
    }


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    recorded_frozen_hashes = validate_recorded_artifact_hashes(
        (BASE_AUDIT, UNMATCHED_AUDIT)
    )
    strict_hash = file_sha256(STRICT_TRIAGE)
    if strict_hash != STRICT_TRIAGE_EXPECTED_SHA256:
        raise RuntimeError(
            f"Strict-triage artifact hash mismatch: {strict_hash} != "
            f"{STRICT_TRIAGE_EXPECTED_SHA256}"
        )
    before_hashes = file_hashes(FROZEN_INPUTS)
    profiles, per_file = load_profiles()
    profiles_by_id, canonical_index, representation_index, representation_sources = (
        build_exact_group_indexes(profiles)
    )
    if len(profiles) != 115735:
        raise ValueError(f"Expected 115735 Itqan profiles, found {len(profiles)}")

    group_records = []
    with open(CANDIDATES_PATH, "w", encoding="utf-8", newline="\n") as handle:
        for normalized_key in sorted(representation_index):
            profile_ids = representation_index[normalized_key]
            if len(profile_ids) < 2:
                continue
            group = build_group_record(
                normalized_key,
                profile_ids,
                profiles_by_id,
                canonical_index,
                representation_sources,
            )
            group_records.append(group)
            handle.write(json_compact(candidate_artifact_record(group, profiles_by_id)))
            handle.write("\n")

        upstream_key_index = build_upstream_key_index(profiles)
        for key in sorted(upstream_key_index):
            profile_ids = upstream_key_index[key]
            if len(profile_ids) < 2:
                continue
            group = build_upstream_key_group(key, profile_ids, profiles_by_id)
            group_records.append(group)
            handle.write(json_compact(candidate_artifact_record(group, profiles_by_id)))
            handle.write("\n")

    strict_cases = strict_triage_case_audit(profiles_by_id)
    write_jsonl(STRICT_CASES_PATH, strict_cases)

    frozen_review_guard(REVIEW_PATH)
    visible, hidden, review_meta = build_review_artifact(group_records, profiles_by_id)
    write_csv(REVIEW_PATH, VISIBLE_REVIEW_COLUMNS, visible)
    write_csv(REVIEW_HIDDEN_PATH, HIDDEN_REVIEW_COLUMNS, hidden)
    review_meta["strict_triage_input_sha256"] = file_sha256(STRICT_TRIAGE)
    review_meta["visible_sha256"] = file_sha256(REVIEW_PATH)
    review_meta["hidden_sha256"] = file_sha256(REVIEW_HIDDEN_PATH)
    write_json(REVIEW_META_PATH, review_meta)

    canonical_collisions = {
        key: ids for key, ids in canonical_index.items() if len(ids) > 1
    }
    representation_collisions = {
        key: ids for key, ids in representation_index.items() if len(ids) > 1
    }
    suspected_grouping_keys = [
        group for group in group_records
        if group["candidate_status"] == "POSSIBLE_DUPLICATE_PROFILE"
    ]
    suspected = aggregate_suspected_profile_sets(group_records)
    class_counts = Counter(group["conceptual_class"] for group in suspected)
    profiles_in_suspected = {
        profile_id for group in suspected for profile_id in group["itqan_profile_ids"]
    }
    profiles_in_representation_collisions = {
        profile_id
        for ids in representation_collisions.values()
        for profile_id in ids
    }

    strict_class_counts = Counter(
        row["case_conceptual_class"] for row in strict_cases
    )
    origins = Counter(
        source_identifiers(profile).get("origin") or "UNKNOWN"
        for profile in profiles
    )
    before_after = file_hashes(FROZEN_INPUTS)
    if before_hashes != before_after:
        raise RuntimeError("A frozen Phase-2 input artifact changed during the audit")

    audit = {
        "audit_version": AUDIT_VERSION,
        "phase": "Phase 2 Itqan internal identity / duplication audit",
        "gate_decision": "ENTITY-RESOLUTION GATE CLOSED",
        "identity_semantics": identity_semantics_evidence(),
        "method": {
            "normalization": "Unicode NFC + Arabic combining marks/tatweel removal + whitespace collapse; no Arabic base-letter substitution",
            "candidate_generation": [
                "exact narrow-normalized canonical-name collisions",
                "exact narrow-normalized canonical-plus-namings collisions",
                "exact upstream record-key overlap",
                "exact classical source-entry overlap retained as source-local evidence",
                "exact biographical/relationship field overlap",
            ],
            "candidate_status_rule": "POSSIBLE_DUPLICATE_PROFILE requires a shared upstream/source key, or an identity-bearing exact representation with explicit composite/contradictory evidence. Canonical-name groups permit one exact nonmissing biographical/relationship overlap; alias-only groups require at least three tokens plus a conjunction of exact fields. Contextual relative aliases are excluded unless they share a source key. Otherwise SAME_NAME_ONLY.",
            "strong_duplicate_rule": "two profiles share an actual upstream record key and have no parsed death contradiction; for larger groups the same key must cover every member",
            "strong_distinct_rule": "exactly two profiles have death ranges separated by more than five years and share neither an upstream record key nor a classical source-entry reference",
            "conflict_rule": "shared record/source evidence plus death contradiction remains UNRESOLVED_PROFILE_MULTIPLICITY",
            "missing_value_rule": "UNKNOWN != FALSE",
            "prohibited": [
                "fuzzy merge", "weighted score", "ML/LLM adjudication",
                "canonical person ID creation", "profile mutation", "graph construction",
            ],
        },
        "inputs": {
            "itqan_manifest": json.load(open(ITQAN_DIR / "manifest.json", encoding="utf-8")),
            "profile_shards": per_file,
            "profile_shards_combined_sha256": hashlib.sha256(
                "\n".join(
                    f"{name}|{file_sha256(ITQAN_DIR / (name + '.json'))}"
                    for name in PROFILE_FILES
                ).encode("utf-8")
            ).hexdigest(),
            "frozen_phase_2_sha256_before_and_after": before_after,
            "frozen_phase_2_recorded_hashes_verified": recorded_frozen_hashes,
            "strict_triage_sha256": file_sha256(STRICT_TRIAGE),
            "strict_triage_reviewer_fields_modified": False,
        },
        "global_metrics": {
            "total_profiles": len(profiles),
            "source_origin_distribution": dict(origins),
            "distinct_nonempty_narrow_canonical_names": len(canonical_index),
            "singleton_narrow_canonical_name_groups": sum(
                len(ids) == 1 for ids in canonical_index.values()
            ),
            "profiles_with_unique_narrow_canonical_name": sum(
                len(ids) == 1 for ids in canonical_index.values()
            ),
            "duplicate_narrow_canonical_name_groups": len(canonical_collisions),
            "profiles_in_duplicate_narrow_canonical_name_groups": sum(
                len(ids) for ids in canonical_collisions.values()
            ),
            "canonical_group_size_distribution": group_size_distribution(canonical_index),
            "largest_canonical_groups": [
                {"normalized_name": key, "profiles": len(ids)}
                for key, ids in sorted(
                    canonical_collisions.items(), key=lambda item: (-len(item[1]), item[0])
                )[:20]
            ],
            "distinct_exact_canonical_plus_alias_representations": len(representation_index),
            "duplicate_exact_canonical_plus_alias_groups": len(representation_collisions),
            "profiles_in_any_exact_representation_collision": len(profiles_in_representation_collisions),
            "representation_collision_memberships": sum(
                len(ids) for ids in representation_collisions.values()
            ),
            "representation_group_size_distribution": group_size_distribution(representation_index),
            "largest_representation_groups": [
                {"normalized_representation": key, "profiles": len(ids)}
                for key, ids in sorted(
                    representation_collisions.items(), key=lambda item: (-len(item[1]), item[0])
                )[:20]
            ],
            "same_name_only_grouping_keys": sum(
                group["candidate_status"] == "SAME_NAME_ONLY" for group in group_records
            ),
            "suspected_duplicate_profile_grouping_keys": len(suspected_grouping_keys),
            "suspected_duplicate_profile_groups": len(suspected),
            "profiles_in_suspected_duplicate_profile_groups": len(profiles_in_suspected),
            "suspected_groups_by_conceptual_class": dict(class_counts),
            "groups_with_strong_provenance_support": class_counts["DUPLICATE_PROFILE_STRONGLY_SUPPORTED"],
            "groups_with_strong_contradictory_evidence": sum(
                group["contradictions"]["contradictory_pair_count"] > 0
                for group in suspected
            ),
            "unresolved_suspected_groups": class_counts["UNRESOLVED_PROFILE_MULTIPLICITY"],
        },
        "source_identifier_metrics": source_id_audit(profiles),
        "mis_relevant_metrics": mis_relevant_audit(suspected),
        "strict_triage_case_metrics": {
            "cases_audited": len(strict_cases),
            "input_selector_labels": dict(Counter(
                row["diagnostic_selector_label_not_ground_truth"] for row in strict_cases
            )),
            "resulting_case_classes": dict(strict_class_counts),
            "human_ground_truth_claimed": False,
        },
        "impact_on_frozen_81": audit_provisional_81(suspected),
        "impact_on_exact_short_unique_890": audit_short_name_890(suspected),
        "target_entity_model": {
            "model_a_mis_to_itqan_profile": "UNSUPPORTED_AS_ONE_TO_ONE_IDENTITY_TARGET",
            "model_b_mis_to_historical_narrator_to_itqan_profiles": "REQUIRED_FOR_FUTURE_DESIGN",
            "model_c_mis_to_canonical_itqan_identity_to_source_records": "UNSUPPORTED_NO_CANONICAL_ITQAN_IDENTITY_FOUND",
            "historical_narrator_layer_created": False,
            "source_specific_gradings_collapsed": False,
        },
        "output_artifacts": {
            str(CANDIDATES_PATH): {"sha256": file_sha256(CANDIDATES_PATH), "rows": len(group_records)},
            str(STRICT_CASES_PATH): {"sha256": file_sha256(STRICT_CASES_PATH), "rows": len(strict_cases)},
            str(REVIEW_PATH): {"sha256": file_sha256(REVIEW_PATH), "rows": len(visible)},
            str(REVIEW_HIDDEN_PATH): {"sha256": file_sha256(REVIEW_HIDDEN_PATH), "rows": len(hidden)},
            str(REVIEW_META_PATH): {"sha256": file_sha256(REVIEW_META_PATH), "rows": 1},
        },
    }
    write_json(AUDIT_PATH, audit)
    print(json.dumps({
        "gate": audit["gate_decision"],
        "global_metrics": audit["global_metrics"],
        "mis_relevant_metrics": audit["mis_relevant_metrics"],
        "impact_on_frozen_81": {
            key: value for key, value in audit["impact_on_frozen_81"].items()
            if key != "details"
        },
        "impact_on_exact_short_unique_890": {
            key: value for key, value in audit["impact_on_exact_short_unique_890"].items()
            if key != "details"
        },
        "strict_triage_case_metrics": audit["strict_triage_case_metrics"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
