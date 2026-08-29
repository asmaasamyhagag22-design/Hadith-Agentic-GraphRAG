"""Build conservative MIS narrator -> Itqan profile candidates.

This is a candidate and evidence audit, not a final identity map.  It uses no
fuzzy matching, learned scoring, LLM judgment, or graph construction.
"""

import csv
import hashlib
import json
import math
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_linkage_validation_identity import normalize_narrow_identity
from config import PROCESSED_DIR
from profile_itqan import (
    ITQAN_DIR,
    PROFILE_FILES,
    canonical_id,
    file_sha256,
    filled,
    load_profiles,
)
from profile_mis import EDGES, NODES, normalize_identifier, read_sheet


NORMALIZER_VERSION = "narrow_arabic_name_v1_nfc_marks_tatweel_whitespace"
SEED = 2026081602
CONFIDENCE_LEVEL = 0.95
ASSUMED_PRECISION = 0.99
TARGET_MARGIN = 0.01
Z_95 = 1.959963984540054

SOURCE_LINKAGE = PROCESSED_DIR / "mis_linkage_pairs.jsonl"
FROZEN_LINKAGE = PROCESSED_DIR / "mis_linkage_accepted_v1.jsonl"
FROZEN_LINKAGE_META = PROCESSED_DIR / "mis_linkage_accepted_v1.json"

AUDIT_PATH = PROCESSED_DIR / "narrator_candidate_audit.json"
CANDIDATES_PATH = PROCESSED_DIR / "narrator_resolution_candidates.jsonl"
CANDIDATES_CSV_PATH = PROCESSED_DIR / "narrator_resolution_candidates.csv"
FEATURES_PATH = PROCESSED_DIR / "narrator_candidate_features.csv"
COLLISION_PATH = PROCESSED_DIR / "narrator_collision_report.json"
REVIEW_PATH = PROCESSED_DIR / "narrator_resolution_review.csv"
REVIEW_HIDDEN_PATH = PROCESSED_DIR / "narrator_resolution_review_hidden.csv"
REVIEW_META_PATH = PROCESSED_DIR / "narrator_resolution_review_sampling.json"

VISIBLE_REVIEW_COLUMNS = (
    "review_id",
    "mis_narrator_id",
    "mis_name",
    "candidate_profiles_json",
    "reviewer_selected_itqan_id",
    "manual_verdict",
    "notes",
)

HIDDEN_REVIEW_COLUMNS = (
    "review_id",
    "mis_narrator_id",
    "evaluation_roles",
    "auto_tier",
    "auto_resolved_itqan_id",
    "candidate_count",
    "candidate_sources_json",
    "candidate_confidence_json",
    "risk_flags",
    "precision_inclusion_probability",
)

FEATURE_COLUMNS = (
    "mis_narrator_id",
    "mis_name",
    "itqan_id",
    "itqan_name",
    "canonical_exact",
    "normalized_exact",
    "alias_exact",
    "kunya_match",
    "nasab_match",
    "laqab_match",
    "death_match",
    "tabaqa_match",
    "city_match",
    "generation_match",
    "teacher_support",
    "student_support",
    "candidate_count",
    "itqan_identity_confidence",
    "provisional_tier",
)

CANDIDATE_COLUMNS = (
    "mis_narrator_id",
    "mis_position",
    "raw_name",
    "search_normalized_name",
    "mis_gender",
    "mis_generation",
    "raw_canonical_candidate_count",
    "normalized_canonical_candidate_count",
    "alias_candidate_count",
    "candidate_count",
    "canonical_vs_alias_conflict",
    "provisional_tier",
    "provisional_resolved_itqan_id",
    "risk_flags_json",
    "candidates_json",
)

BIOGRAPHICAL_FIELDS = (
    "kunya",
    "nasab",
    "laqab",
    "death",
    "tabaqat",
    "city",
    "generation",
)

AUTO_TIERS = (
    "EXACT_RESOLVED",
    "NORMALIZED_RESOLVED",
    "ALIAS_RESOLVED",
)


def stable_hash(path):
    return file_sha256(path)


def combined_file_hash(paths):
    payload = "\n".join(
        f"{path.name}|{stable_hash(path)}" for path in sorted(paths)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_mis_id(value):
    """Normalize storage type without coercing arbitrary/zero-padded strings."""

    return normalize_identifier(value)


def id_normalization_audit(nodes):
    canonical_to_raw = defaultdict(list)
    null_rows = []
    for row_number, node in enumerate(nodes, start=1):
        raw = node.get("NarratorID_Mapped")
        canonical = normalize_mis_id(raw)
        if canonical is None:
            null_rows.append(row_number)
        else:
            canonical_to_raw[canonical].append(
                {"type": type(raw).__name__, "repr": repr(raw), "row": row_number}
            )
    collisions = {
        key: values
        for key, values in canonical_to_raw.items()
        if len(values) > 1
    }
    return {
        "rows": len(nodes),
        "raw_python_types": dict(Counter(
            type(node.get("NarratorID_Mapped")).__name__ for node in nodes
        )),
        "null_after_normalization": len(null_rows),
        "unique_after_normalization": len(canonical_to_raw),
        "cardinality_change": len(nodes) - len(canonical_to_raw) - len(null_rows),
        "canonical_collisions": collisions,
    }


def _id_sort(value):
    text = str(value)
    return (0, int(text), text) if text.isdigit() else (1, text)


def build_name_indexes(profiles):
    by_id = {}
    raw_canonical = defaultdict(set)
    normalized_canonical = defaultdict(set)
    normalized_alias = defaultdict(set)

    for profile in profiles:
        profile_id = canonical_id(profile.get("id"))
        if profile_id is None:
            continue
        by_id[profile_id] = profile
        raw_name = str(profile.get("full_name") or "")
        normalized_name = normalize_narrow_identity(raw_name)
        if raw_name:
            raw_canonical[raw_name].add(profile_id)
        if normalized_name:
            normalized_canonical[normalized_name].add(profile_id)
        aliases = profile.get("namings")
        if isinstance(aliases, list):
            for alias in aliases:
                normalized = normalize_narrow_identity(alias)
                if normalized:
                    normalized_alias[normalized].add(profile_id)

    return {
        "profiles_by_id": by_id,
        "raw_canonical": raw_canonical,
        "normalized_canonical": normalized_canonical,
        "normalized_alias": normalized_alias,
    }


def candidate_size_bucket(count):
    if count == 0:
        return "0"
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    if count <= 5:
        return "3-5"
    return ">5"


def size_distribution(counts):
    buckets = Counter(candidate_size_bucket(count) for count in counts)
    return {
        key: buckets[key] for key in ("0", "1", "2", "3-5", ">5")
    }


def provisional_tier(raw_candidates, normalized_candidates, alias_candidates):
    all_candidates = raw_candidates | normalized_candidates | alias_candidates
    if not all_candidates:
        return "UNMATCHED", None
    if len(all_candidates) > 1:
        return "AMBIGUOUS", None
    candidate = next(iter(all_candidates))
    if candidate in raw_candidates:
        return "EXACT_RESOLVED", candidate
    if candidate in normalized_candidates:
        return "NORMALIZED_RESOLVED", candidate
    return "ALIAS_RESOLVED", candidate


def _public_profile(profile):
    return {
        "itqan_id": canonical_id(profile.get("id")),
        "canonical_profile_name": profile.get("full_name"),
        "namings": profile.get("namings") if isinstance(profile.get("namings"), list) else [],
        "kunya": profile.get("kunya"),
        "nasab": profile.get("nasab"),
        "laqab": profile.get("laqab"),
        "death": profile.get("death"),
        "tabaqat": profile.get("tabaqat"),
        "generation": profile.get("generation"),
        "city": profile.get("city"),
    }


def generate_candidates(nodes, indexes):
    records = []
    raw_counts = []
    normalized_counts = []
    alias_counts = []
    union_counts = []

    for position, node in enumerate(nodes, start=1):
        narrator_id = normalize_mis_id(node.get("NarratorID_Mapped"))
        raw_name = str(node.get("NarratorNameAr") or "")
        normalized_name = normalize_narrow_identity(raw_name)
        raw_candidates = set(indexes["raw_canonical"].get(raw_name, set()))
        normalized_candidates = set(
            indexes["normalized_canonical"].get(normalized_name, set())
        )
        alias_candidates = set(
            indexes["normalized_alias"].get(normalized_name, set())
        )
        union = raw_candidates | normalized_candidates | alias_candidates
        tier, resolved_id = provisional_tier(
            raw_candidates, normalized_candidates, alias_candidates
        )

        candidates = []
        for profile_id in sorted(union, key=_id_sort):
            sources = []
            if profile_id in raw_candidates:
                sources.append("canonical_exact")
            if profile_id in normalized_candidates:
                sources.append("normalized_canonical")
            if profile_id in alias_candidates:
                sources.append("alias")
            profile = indexes["profiles_by_id"][profile_id]
            candidates.append({
                "itqan_id": profile_id,
                "candidate_source": sources,
                "itqan_name": profile.get("full_name"),
                "supporting_fields": {
                    field: profile.get(field) for field in BIOGRAPHICAL_FIELDS
                },
                "itqan_identity_confidence": profile.get("confidence"),
                "features": {},
            })

        normalized_tokens = normalized_name.split()
        risk_flags = []
        if len(normalized_tokens) <= 2:
            risk_flags.append("SHORT_NAME")
        if any(
            token in {"أبو", "أبي", "ابو", "ابي", "ابن", "بن"}
            for token in normalized_tokens
        ):
            risk_flags.append("COMMON_KUNYA_NASAB_FORM")
        if len(union) > 1 or len(normalized_candidates) > 1 or len(alias_candidates) > 1:
            risk_flags.append("REPEATED_OR_COLLIDING_NAME")

        records.append({
            "mis_position": position,
            "mis_narrator_id": narrator_id,
            "raw_name": raw_name,
            "search_normalized_name": normalized_name,
            "mis_generation": node.get("NarratorGeneration"),
            "mis_gender": node.get("Gender"),
            "raw_canonical_candidate_count": len(raw_candidates),
            "normalized_canonical_candidate_count": len(normalized_candidates),
            "alias_candidate_count": len(alias_candidates),
            "candidate_count": len(union),
            "canonical_vs_alias_conflict": bool(
                normalized_candidates
                and alias_candidates
                and normalized_candidates != alias_candidates
            ),
            "provisional_tier": tier,
            "provisional_resolved_itqan_id": resolved_id,
            "risk_flags": risk_flags,
            "candidates": candidates,
        })
        raw_counts.append(len(raw_candidates))
        normalized_counts.append(len(normalized_candidates))
        alias_counts.append(len(alias_candidates))
        union_counts.append(len(union))

    return records, {
        "raw_candidate_counts": raw_counts,
        "normalized_candidate_counts": normalized_counts,
        "alias_candidate_counts": alias_counts,
        "union_candidate_counts": union_counts,
    }


def _relationship_set(profile, field):
    values = profile.get(field)
    if not isinstance(values, list):
        return set()
    return {
        value for value in (canonical_id(item) for item in values)
        if value is not None
    }


def relationship_support(related_resolved_ids, profile_relationship_ids):
    """TRUE means explicit support; non-support remains UNKNOWN, never FALSE."""

    if related_resolved_ids and profile_relationship_ids & related_resolved_ids:
        return "TRUE"
    return "UNKNOWN"


def add_candidate_features(records, edges, indexes):
    by_mis_id = {record["mis_narrator_id"]: record for record in records}
    resolved = {
        record["mis_narrator_id"]: record["provisional_resolved_itqan_id"]
        for record in records
        if record["provisional_tier"] in AUTO_TIERS
    }
    teachers = defaultdict(set)
    students = defaultdict(set)
    for edge in edges:
        source = normalize_mis_id(edge.get("sourceNarratorID"))
        target = normalize_mis_id(edge.get("targetNarratorID"))
        if source is None or target is None:
            continue
        students[source].add(target)
        teachers[target].add(source)

    feature_rows = []
    for record in records:
        known_teacher_profiles = {
            resolved[mis_id] for mis_id in teachers[record["mis_narrator_id"]]
            if mis_id in resolved
        }
        known_student_profiles = {
            resolved[mis_id] for mis_id in students[record["mis_narrator_id"]]
            if mis_id in resolved
        }
        record["relationship_context"] = {
            "mis_teacher_neighbors": len(teachers[record["mis_narrator_id"]]),
            "mis_student_neighbors": len(students[record["mis_narrator_id"]]),
            "resolved_teacher_profile_anchors": len(known_teacher_profiles),
            "resolved_student_profile_anchors": len(known_student_profiles),
        }
        for candidate in record["candidates"]:
            profile = indexes["profiles_by_id"][candidate["itqan_id"]]
            candidate_teachers = _relationship_set(profile, "teachers")
            candidate_students = _relationship_set(profile, "students")
            sources = set(candidate["candidate_source"])
            features = {
                "canonical_exact": "TRUE" if "canonical_exact" in sources else "FALSE",
                "normalized_exact": "TRUE" if "normalized_canonical" in sources else "FALSE",
                "alias_exact": "TRUE" if "alias" in sources else "FALSE",
                "kunya_match": "UNKNOWN",
                "nasab_match": "UNKNOWN",
                "laqab_match": "UNKNOWN",
                "death_match": "UNKNOWN",
                "tabaqa_match": "UNKNOWN",
                "city_match": "UNKNOWN",
                "generation_match": "UNKNOWN",
                "teacher_support": relationship_support(
                    known_teacher_profiles, candidate_teachers
                ),
                "student_support": relationship_support(
                    known_student_profiles, candidate_students
                ),
            }
            candidate["features"] = features
            feature_rows.append({
                "mis_narrator_id": record["mis_narrator_id"],
                "mis_name": record["raw_name"],
                "itqan_id": candidate["itqan_id"],
                "itqan_name": candidate["itqan_name"],
                **features,
                "candidate_count": record["candidate_count"],
                "itqan_identity_confidence": candidate["itqan_identity_confidence"],
                "provisional_tier": record["provisional_tier"],
            })

    return feature_rows, {
        "mis_edge_interpretation": (
            "sourceNarratorID=teacher/earlier; targetNarratorID=student/later"
        ),
        "mis_narrators_with_teacher_neighbors": sum(bool(teachers[key]) for key in by_mis_id),
        "mis_narrators_with_student_neighbors": sum(bool(students[key]) for key in by_mis_id),
        "mis_narrators_with_resolved_teacher_anchors": sum(
            bool(record["relationship_context"]["resolved_teacher_profile_anchors"])
            for record in records
        ),
        "mis_narrators_with_resolved_student_anchors": sum(
            bool(record["relationship_context"]["resolved_student_profile_anchors"])
            for record in records
        ),
        "resolved_neighbor_profiles_available": len(resolved),
    }


def ambiguous_evidence_coverage(records, indexes):
    ambiguous = [record for record in records if record["provisional_tier"] == "AMBIGUOUS"]
    field_report = {}
    for field in BIOGRAPHICAL_FIELDS:
        narrator_any = narrator_all = discriminating = candidate_rows_filled = 0
        candidate_rows = 0
        for record in ambiguous:
            values = []
            filled_flags = []
            for candidate in record["candidates"]:
                profile = indexes["profiles_by_id"][candidate["itqan_id"]]
                value = profile.get(field)
                present = filled(value)
                filled_flags.append(present)
                candidate_rows += 1
                candidate_rows_filled += present
                if present:
                    values.append(normalize_narrow_identity(value))
            narrator_any += any(filled_flags)
            narrator_all += bool(filled_flags) and all(filled_flags)
            discriminating += len(set(values)) >= 2

        mis_available = (
            sum(
                record["mis_generation"] not in {None, "", "NotMapped"}
                for record in ambiguous
            )
            if field == "generation"
            else 0
        )
        field_report[field] = {
            "ambiguous_narrators": len(ambiguous),
            "mis_side_available": mis_available,
            "itqan_available_for_any_candidate": narrator_any,
            "itqan_available_for_all_candidates": narrator_all,
            "itqan_candidate_rows_filled": candidate_rows_filled,
            "itqan_candidate_rows_total": candidate_rows,
            "itqan_values_differ_between_candidates": discriminating,
            "usable_candidate_discriminating_rate": 0,
            "contradiction_rate": None,
            "comparison_status": (
                "NO_VALIDATED_CROSSWALK"
                if field == "generation" and mis_available
                else "MIS_FIELD_UNAVAILABLE"
            ),
        }

    teacher_states = Counter()
    student_states = Counter()
    ambiguous_with_teacher_support = ambiguous_with_student_support = 0
    ambiguous_with_unique_supported_candidate = 0
    candidate_rows_with_teacher_records = candidate_rows_with_student_records = 0
    for record in ambiguous:
        teacher_true = sum(
            candidate["features"]["teacher_support"] == "TRUE"
            for candidate in record["candidates"]
        )
        student_true = sum(
            candidate["features"]["student_support"] == "TRUE"
            for candidate in record["candidates"]
        )
        ambiguous_with_teacher_support += teacher_true > 0
        ambiguous_with_student_support += student_true > 0
        supported_union = {
            candidate["itqan_id"]
            for candidate in record["candidates"]
            if candidate["features"]["teacher_support"] == "TRUE"
            or candidate["features"]["student_support"] == "TRUE"
        }
        ambiguous_with_unique_supported_candidate += len(supported_union) == 1
        for candidate in record["candidates"]:
            teacher_states[candidate["features"]["teacher_support"]] += 1
            student_states[candidate["features"]["student_support"]] += 1
            profile = indexes["profiles_by_id"][candidate["itqan_id"]]
            candidate_rows_with_teacher_records += bool(
                _relationship_set(profile, "teachers")
            )
            candidate_rows_with_student_records += bool(
                _relationship_set(profile, "students")
            )

    return {
        "ambiguous_narrators": len(ambiguous),
        "biographical_fields": field_report,
        "relationship_support": {
            "teacher_feature_states": dict(teacher_states),
            "student_feature_states": dict(student_states),
            "ambiguous_narrators_with_any_teacher_support": ambiguous_with_teacher_support,
            "ambiguous_narrators_with_any_student_support": ambiguous_with_student_support,
            "ambiguous_narrators_with_exactly_one_supported_candidate": (
                ambiguous_with_unique_supported_candidate
            ),
            "ambiguous_narrators_with_resolved_teacher_anchors": sum(
                bool(record["relationship_context"]["resolved_teacher_profile_anchors"])
                for record in ambiguous
            ),
            "ambiguous_narrators_with_resolved_student_anchors": sum(
                bool(record["relationship_context"]["resolved_student_profile_anchors"])
                for record in ambiguous
            ),
            "candidate_rows_with_teacher_records": candidate_rows_with_teacher_records,
            "candidate_rows_with_student_records": candidate_rows_with_student_records,
            "resolution_effect": (
                "NONE: TRUE is supporting evidence and UNKNOWN is not contradiction; "
                "no composite tier is assigned without labelled validation."
            ),
        },
    }


def _alternative_normalizer(name, transformation):
    value = normalize_narrow_identity(name)
    if transformation == "ALIF_FOLD":
        return value.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"}))
    if transformation == "YA_MAQSURA_FOLD":
        return value.replace("ى", "ي")
    if transformation == "TA_MARBUTA_FOLD":
        return value.replace("ة", "ه")
    raise ValueError(f"Unknown transformation: {transformation}")


def alternative_normalization_experiments(records, profiles):
    unmatched = [record for record in records if record["provisional_tier"] == "UNMATCHED"]
    results = {}
    for transformation in ("ALIF_FOLD", "YA_MAQSURA_FOLD", "TA_MARBUTA_FOLD"):
        index = defaultdict(set)
        for profile in profiles:
            profile_id = canonical_id(profile.get("id"))
            names = [profile.get("full_name")]
            aliases = profile.get("namings")
            if isinstance(aliases, list):
                names.extend(aliases)
            for name in names:
                normalized = _alternative_normalizer(name, transformation)
                if normalized:
                    index[normalized].add(profile_id)
        counts = [
            len(index.get(_alternative_normalizer(record["raw_name"], transformation), set()))
            for record in unmatched
        ]
        results[transformation] = {
            "population": len(unmatched),
            "candidate_size_distribution": size_distribution(counts),
            "new_unique_candidates": sum(count == 1 for count in counts),
            "new_ambiguous_candidates": sum(count > 1 for count in counts),
            "largest_candidate_group": max(counts, default=0),
            "used_for_resolution": False,
        }
    return results


def collision_report(records):
    canonical_counts = [record["normalized_canonical_candidate_count"] for record in records]
    alias_counts = [record["alias_candidate_count"] for record in records]
    union_counts = [record["candidate_count"] for record in records]
    conflicts = [record for record in records if record["canonical_vs_alias_conflict"]]
    return {
        "population": len(records),
        "canonical_name_candidates": {
            "distribution": size_distribution(canonical_counts),
            "largest_collision_group": max(canonical_counts, default=0),
        },
        "alias_candidates": {
            "distribution": size_distribution(alias_counts),
            "largest_collision_group": max(alias_counts, default=0),
        },
        "combined_candidates": {
            "distribution": size_distribution(union_counts),
            "largest_collision_group": max(union_counts, default=0),
        },
        "canonical_vs_alias_conflicts": {
            "narrators": len(conflicts),
            "mis_narrator_ids": [record["mis_narrator_id"] for record in conflicts],
        },
        "ambiguous_groups": [
            {
                "mis_narrator_id": record["mis_narrator_id"],
                "mis_name": record["raw_name"],
                "candidate_count": record["candidate_count"],
                "candidate_ids": [candidate["itqan_id"] for candidate in record["candidates"]],
                "candidate_sources": {
                    candidate["itqan_id"]: candidate["candidate_source"]
                    for candidate in record["candidates"]
                },
            }
            for record in records if record["provisional_tier"] == "AMBIGUOUS"
        ],
    }


def sample_size_for_proportion(population, precision=ASSUMED_PRECISION, margin=TARGET_MARGIN):
    if population <= 0:
        return 0
    infinite = Z_95 ** 2 * precision * (1 - precision) / margin ** 2
    corrected = infinite / (1 + (infinite - 1) / population)
    return min(population, math.ceil(corrected))


def stratified_allocation(tier_populations, target, minimum_per_tier=30):
    nonempty = {tier: count for tier, count in tier_populations.items() if count}
    allocation = {
        tier: min(count, minimum_per_tier) for tier, count in nonempty.items()
    }
    if sum(allocation.values()) > target:
        allocation = {tier: 0 for tier in nonempty}
    while sum(allocation.values()) < target:
        eligible = {
            tier: count - allocation[tier]
            for tier, count in nonempty.items()
            if allocation[tier] < count
        }
        if not eligible:
            break
        tier = max(
            eligible,
            key=lambda key: (
                eligible[key] / nonempty[key],
                eligible[key],
                key,
            ),
        )
        allocation[tier] += 1
    return allocation


def build_review_sample(records, indexes, seed=SEED):
    rng = random.Random(seed)
    by_tier = defaultdict(list)
    for record in records:
        by_tier[record["provisional_tier"]].append(record)
    auto_population = sum(len(by_tier[tier]) for tier in AUTO_TIERS)
    target = sample_size_for_proportion(auto_population)
    tier_populations = {tier: len(by_tier[tier]) for tier in AUTO_TIERS}
    allocation = stratified_allocation(tier_populations, target)

    selected = {}
    inclusion_probability = {}

    def add(record, role):
        entry = selected.setdefault(record["mis_narrator_id"], {
            "record": record,
            "roles": set(),
        })
        entry["roles"].add(role)

    for tier, sample_count in allocation.items():
        population = sorted(by_tier[tier], key=lambda row: _id_sort(row["mis_narrator_id"]))
        sampled = rng.sample(population, sample_count)
        probability = sample_count / len(population)
        for record in sampled:
            add(record, f"PRECISION_{tier}")
            inclusion_probability[record["mis_narrator_id"]] = probability

    for record in by_tier["AMBIGUOUS"]:
        bucket = candidate_size_bucket(record["candidate_count"])
        add(record, f"DIAGNOSTIC_AMBIGUOUS_{bucket}")

    unmatched_population = sorted(
        by_tier["UNMATCHED"], key=lambda row: _id_sort(row["mis_narrator_id"])
    )
    for record in rng.sample(unmatched_population, min(30, len(unmatched_population))):
        add(record, "DIAGNOSTIC_UNMATCHED")

    for risk_flag in ("SHORT_NAME", "COMMON_KUNYA_NASAB_FORM", "REPEATED_OR_COLLIDING_NAME"):
        pool = [record for record in records if risk_flag in record["risk_flags"]]
        not_selected = [
            record for record in pool if record["mis_narrator_id"] not in selected
        ]
        for record in rng.sample(not_selected, min(10, len(not_selected))):
            add(record, f"DIAGNOSTIC_{risk_flag}")

    selected_items = list(selected.values())
    rng.shuffle(selected_items)
    visible_rows = []
    hidden_rows = []
    for number, item in enumerate(selected_items, start=1):
        record = item["record"]
        review_id = f"NER-{number:04d}"
        public_candidates = [
            _public_profile(indexes["profiles_by_id"][candidate["itqan_id"]])
            for candidate in record["candidates"]
        ]
        visible_rows.append({
            "review_id": review_id,
            "mis_narrator_id": record["mis_narrator_id"],
            "mis_name": record["raw_name"],
            "candidate_profiles_json": json.dumps(
                public_candidates, ensure_ascii=False, separators=(",", ":")
            ),
            "reviewer_selected_itqan_id": "",
            "manual_verdict": "",
            "notes": "",
        })
        hidden_rows.append({
            "review_id": review_id,
            "mis_narrator_id": record["mis_narrator_id"],
            "evaluation_roles": "|".join(sorted(item["roles"])),
            "auto_tier": record["provisional_tier"],
            "auto_resolved_itqan_id": record["provisional_resolved_itqan_id"] or "",
            "candidate_count": record["candidate_count"],
            "candidate_sources_json": json.dumps({
                candidate["itqan_id"]: candidate["candidate_source"]
                for candidate in record["candidates"]
            }, ensure_ascii=False, sort_keys=True),
            "candidate_confidence_json": json.dumps({
                candidate["itqan_id"]: candidate["itqan_identity_confidence"]
                for candidate in record["candidates"]
            }, ensure_ascii=False, sort_keys=True),
            "risk_flags": "|".join(record["risk_flags"]),
            "precision_inclusion_probability": inclusion_probability.get(
                record["mis_narrator_id"], ""
            ),
        })

    meta = {
        "purpose": (
            "Estimate false-merge risk of provisional deterministic unique tiers; "
            "diagnostic rows study ambiguity and unmatched failure modes separately."
        ),
        "auto_resolved_population": auto_population,
        "auto_precision_sample_size": target,
        "confidence_level": CONFIDENCE_LEVEL,
        "assumed_precision_for_sizing": ASSUMED_PRECISION,
        "target_margin_for_sizing": TARGET_MARGIN,
        "sampling_method": (
            "tier-stratified random sampling without replacement; use tier inclusion "
            "probabilities for overall weighted estimates"
        ),
        "tier_populations": tier_populations,
        "tier_sample_allocation": allocation,
        "seed": seed,
        "diagnostic_rows_are_not_part_of_precision_denominator": True,
        "total_visible_rows_after_deduplication": len(visible_rows),
        "visible_columns": list(VISIBLE_REVIEW_COLUMNS),
        "hidden_columns": list(HIDDEN_REVIEW_COLUMNS),
        "allowed_manual_verdicts": [
            "correct", "wrong", "uncertain", "NEEDS_DOMAIN_EXPERT"
        ],
        "manual_labels_present_at_generation": 0,
    }
    return visible_rows, hidden_rows, meta


def _write_csv(path, columns, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def candidate_csv_rows(records):
    """Flatten one candidate-set record per MIS narrator without losing detail."""
    rows = []
    for record in records:
        rows.append({
            column: record.get(column, "")
            for column in CANDIDATE_COLUMNS
            if column not in {"risk_flags_json", "candidates_json"}
        } | {
            "risk_flags_json": json.dumps(
                record["risk_flags"], ensure_ascii=False, sort_keys=True
            ),
            "candidates_json": json.dumps(
                record["candidates"], ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ),
        })
    return rows


def ensure_review_artifacts(visible_rows, hidden_rows, meta):
    if REVIEW_PATH.exists():
        columns, existing = _read_csv(REVIEW_PATH)
        if columns != VISIBLE_REVIEW_COLUMNS:
            raise RuntimeError(f"Refusing to overwrite {REVIEW_PATH}: schema differs")
        labelled = sum(
            bool(row.get("manual_verdict", "").strip())
            or bool(row.get("reviewer_selected_itqan_id", "").strip())
            for row in existing
        )
        stable_columns = tuple(
            column for column in VISIBLE_REVIEW_COLUMNS
            if column not in {"manual_verdict", "notes", "reviewer_selected_itqan_id"}
        )
        existing_stable = [
            {column: str(row.get(column, "")) for column in stable_columns}
            for row in existing
        ]
        proposed_stable = [
            {column: str(row.get(column, "")) for column in stable_columns}
            for row in visible_rows
        ]
        if existing_stable != proposed_stable:
            raise RuntimeError(
                f"Refusing to overwrite {REVIEW_PATH}: frozen sample differs"
            )
        return {"action": "preserved", "human_inputs_present": labelled}

    _write_csv(REVIEW_PATH, VISIBLE_REVIEW_COLUMNS, visible_rows)
    _write_csv(REVIEW_HIDDEN_PATH, HIDDEN_REVIEW_COLUMNS, hidden_rows)
    with open(REVIEW_META_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return {"action": "created", "human_inputs_present": 0}


def freeze_linkage():
    if not SOURCE_LINKAGE.exists():
        raise FileNotFoundError(f"Missing accepted linkage artifact: {SOURCE_LINKAGE}")
    source_hash = stable_hash(SOURCE_LINKAGE)
    if FROZEN_LINKAGE.exists():
        frozen_hash = stable_hash(FROZEN_LINKAGE)
        if frozen_hash != source_hash:
            raise RuntimeError(
                "Frozen linkage differs from current accepted linkage; do not retune "
                "the linkage during narrator resolution."
            )
        action = "preserved"
    else:
        shutil.copyfile(SOURCE_LINKAGE, FROZEN_LINKAGE)
        frozen_hash = stable_hash(FROZEN_LINKAGE)
        action = "created"
    rows = sum(1 for line in FROZEN_LINKAGE.open("r", encoding="utf-8") if line.strip())
    if rows != 7015:
        raise RuntimeError(f"Expected 7015 frozen linkage rows, found {rows}")
    meta = {
        "version": "hadith_mis_linkage_v1",
        "rows": rows,
        "sha256": frozen_hash,
        "source_path": str(SOURCE_LINKAGE),
        "frozen_path": str(FROZEN_LINKAGE),
        "mutation_policy": "immutable input during narrator entity resolution",
    }
    with open(FROZEN_LINKAGE_META, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return {**meta, "action": action}


def main():
    linkage_freeze = freeze_linkage()
    _, nodes = read_sheet(NODES)
    _, edges = read_sheet(EDGES)
    profiles, per_file = load_profiles()

    id_audit = id_normalization_audit(nodes)
    if id_audit["null_after_normalization"] or id_audit["canonical_collisions"]:
        raise RuntimeError("Unsafe MIS narrator ID normalization; inspect audit")

    indexes = build_name_indexes(profiles)
    records, baseline_counts = generate_candidates(nodes, indexes)
    feature_rows, relationship_population = add_candidate_features(
        records, edges, indexes
    )
    collisions = collision_report(records)
    evidence = ambiguous_evidence_coverage(records, indexes)
    alternative = alternative_normalization_experiments(records, profiles)

    tier_counts = Counter(record["provisional_tier"] for record in records)
    raw_distribution = size_distribution(baseline_counts["raw_candidate_counts"])
    normalized_distribution = size_distribution(
        baseline_counts["normalized_candidate_counts"]
    )
    canonical_unique_ids = {
        record["mis_narrator_id"] for record in records
        if record["normalized_canonical_candidate_count"] == 1
    }
    alias_stage = [
        record for record in records
        if record["mis_narrator_id"] not in canonical_unique_ids
    ]
    alias_stage_distribution = size_distribution(
        [record["alias_candidate_count"] for record in alias_stage]
    )

    itqan_files = [ITQAN_DIR / f"{name}.json" for name in PROFILE_FILES]
    manifest_path = ITQAN_DIR / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    review_rows, hidden_rows, review_meta = build_review_sample(records, indexes)
    review_meta.update({
        "normalizer_version": NORMALIZER_VERSION,
        "mis_nodes_sha256": stable_hash(NODES),
        "mis_edges_sha256": stable_hash(EDGES),
        "itqan_profile_shards_sha256": combined_file_hash(itqan_files),
        "frozen_linkage_sha256": linkage_freeze["sha256"],
    })
    review_status = ensure_review_artifacts(review_rows, hidden_rows, review_meta)

    audit = {
        "phase": "Narrator Entity Resolution — Phase 2 candidate audit",
        "inputs": {
            "mis_nodes": {"path": str(NODES), "sha256": stable_hash(NODES), "rows": len(nodes)},
            "mis_edges": {"path": str(EDGES), "sha256": stable_hash(EDGES), "rows": len(edges)},
            "itqan": {
                "manifest_version": manifest.get("version"),
                "profile_rows": len(profiles),
                "profile_shards": per_file,
                "combined_profile_shards_sha256": combined_file_hash(itqan_files),
                "manifest_sha256": stable_hash(manifest_path),
            },
            "frozen_hadith_linkage": {
                key: value for key, value in linkage_freeze.items() if key != "action"
            },
            "script_sha256": stable_hash(Path(__file__)),
        },
        "normalization": {
            "version": NORMALIZER_VERSION,
            "transformations": [
                "Unicode NFC", "Arabic-block combining-mark removal",
                "tatweel removal", "whitespace collapse",
            ],
            "letter_substitutions": [],
            "canonical_source_values_mutated": False,
        },
        "mis_id_normalization": id_audit,
        "baseline_a_raw_exact": {
            "candidate_size_distribution": raw_distribution,
            "unique_resolution_rate_before_alias_conflict_check": (
                raw_distribution["1"] / len(records)
            ),
        },
        "baseline_b_narrow_normalized_canonical": {
            "candidate_size_distribution": normalized_distribution,
            "unique_resolution_rate_before_alias_conflict_check": (
                normalized_distribution["1"] / len(records)
            ),
            "incremental_unique_over_raw": (
                normalized_distribution["1"] - raw_distribution["1"]
            ),
        },
        "baseline_c_alias_on_non_unique_canonical": {
            "population": len(alias_stage),
            "candidate_size_distribution": alias_stage_distribution,
            "alias_unique_without_any_canonical_candidate": sum(
                record["provisional_tier"] == "ALIAS_RESOLVED"
                for record in records
            ),
            "canonical_vs_alias_conflicts_all_mis": collisions[
                "canonical_vs_alias_conflicts"
            ]["narrators"],
        },
        "provisional_resolution_tiers": {
            **{tier: tier_counts[tier] for tier in (
                "EXACT_RESOLVED", "NORMALIZED_RESOLVED", "ALIAS_RESOLVED",
                "COMPOSITE_RESOLVED", "AMBIGUOUS", "UNMATCHED", "QUARANTINED",
            )},
            "auto_resolved_total": sum(tier_counts[tier] for tier in AUTO_TIERS),
            "auto_resolution_coverage": (
                sum(tier_counts[tier] for tier in AUTO_TIERS) / len(records)
            ),
            "ambiguity_rate": tier_counts["AMBIGUOUS"] / len(records),
            "unmatched_rate": tier_counts["UNMATCHED"] / len(records),
        },
        "collision_report": collisions,
        "biographical_and_relationship_evidence": {
            **evidence,
            "relationship_population": relationship_population,
            "itqan_confidence_used_to_choose_identity": False,
        },
        "experimental_letter_folds": alternative,
        "review_design": {
            **review_meta,
            "artifact_status": {
                "human_inputs_present": review_status["human_inputs_present"],
            },
            "review_path": str(REVIEW_PATH),
            "hidden_path": str(REVIEW_HIDDEN_PATH),
            "metadata_path": str(REVIEW_META_PATH),
        },
        "decision": (
            "ENTITY-RESOLUTION GATE CLOSED: candidate tiers are provisional and "
            "require labelled false-merge evaluation."
        ),
        "prohibited_work_not_performed": [
            "fuzzy matching", "weighted scoring", "ML/LLM adjudication",
            "final production identity map", "graph construction",
        ],
    }

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COLLISION_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(collisions, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    with open(CANDIDATES_PATH, "w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    _write_csv(CANDIDATES_CSV_PATH, CANDIDATE_COLUMNS, candidate_csv_rows(records))
    _write_csv(FEATURES_PATH, FEATURE_COLUMNS, feature_rows)

    output_specs = (
        (CANDIDATES_PATH, len(records), "jsonl"),
        (CANDIDATES_CSV_PATH, len(records), "csv"),
        (COLLISION_PATH, len(collisions["ambiguous_groups"]), "json"),
        (FEATURES_PATH, len(feature_rows), "csv"),
        (REVIEW_PATH, len(review_rows), "csv"),
        (REVIEW_HIDDEN_PATH, len(hidden_rows), "csv"),
        (REVIEW_META_PATH, 1, "json"),
    )
    audit["output_artifacts"] = {
        path.name: {
            "path": str(path),
            "format": file_format,
            "rows": rows,
            "sha256": stable_hash(path),
            "normalizer_version": NORMALIZER_VERSION,
            "generator_script_sha256": audit["inputs"]["script_sha256"],
        }
        for path, rows, file_format in output_specs
    }
    with open(AUDIT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    print("Narrator candidate audit")
    print(f"MIS narrators             : {len(records)}")
    for tier in (
        "EXACT_RESOLVED", "NORMALIZED_RESOLVED", "ALIAS_RESOLVED",
        "COMPOSITE_RESOLVED", "AMBIGUOUS", "UNMATCHED", "QUARANTINED",
    ):
        print(f"{tier:<26}: {tier_counts[tier]}")
    print(f"Candidate feature rows    : {len(feature_rows)}")
    print(f"Review rows               : {len(review_rows)} ({review_status['action']})")
    print(f"Frozen linkage SHA-256    : {linkage_freeze['sha256']}")
    print(f"Audit                     : {AUDIT_PATH}")
    print("ENTITY-RESOLUTION GATE CLOSED")


if __name__ == "__main__":
    main()
