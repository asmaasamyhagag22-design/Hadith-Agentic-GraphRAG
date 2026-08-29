"""Audit Itqan source-specific grading disagreement and citation capability."""

import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import PROCESSED_DIR
from profile_itqan import canonical_id, filled, load_profiles

REPORT_PATH = PROCESSED_DIR / "grading_audit.json"


def grading_disagreement(records):
    """Measure raw wording and Itqan-category variation on explicit denominators.

    ``unknown`` with a blank Arabic grade is kept in the dataset-wide category
    audit, but excluded from the like-for-like comparison of substantive source
    verdicts.  Otherwise missing wording would be misreported as a critic's
    disagreement.
    """

    multi_source = 0
    raw_eligible = raw_differs = 0
    category_all_eligible = category_all_differs = 0
    category_substantive_eligible = category_substantive_differs = 0
    unknown_blank_entries = 0

    source_counts = Counter()
    normalized_vocabulary = Counter()
    raw_vocabulary = Counter()
    substantive_conflict_pairs = Counter()

    for record in records:
        sources = record.get("classical_sources") or {}
        if not isinstance(sources, dict):
            continue

        source_counts[len(sources)] += 1
        entries = [entry for entry in sources.values() if isinstance(entry, dict)]

        for entry in entries:
            category = str(entry.get("grade_en") or "").strip()
            raw = str(entry.get("grade_ar") or "").strip()
            normalized_vocabulary[category] += 1
            if raw:
                raw_vocabulary[raw] += 1
            if category == "unknown" and not filled(entry.get("grade_ar")):
                unknown_blank_entries += 1

        if len(entries) < 2:
            continue
        multi_source += 1

        raw_values = {
            str(entry.get("grade_ar") or "").strip()
            for entry in entries if filled(entry.get("grade_ar"))
        }
        if len([entry for entry in entries if filled(entry.get("grade_ar"))]) >= 2:
            raw_eligible += 1
            if len(raw_values) > 1:
                raw_differs += 1

        all_categories = {
            str(entry.get("grade_en") or "").strip()
            for entry in entries if filled(entry.get("grade_en"))
        }
        if len([entry for entry in entries if filled(entry.get("grade_en"))]) >= 2:
            category_all_eligible += 1
            if len(all_categories) > 1:
                category_all_differs += 1

        substantive_categories = {
            str(entry.get("grade_en") or "").strip()
            for entry in entries
            if filled(entry.get("grade_ar")) and filled(entry.get("grade_en"))
        }
        substantive_count = sum(
            filled(entry.get("grade_ar")) and filled(entry.get("grade_en"))
            for entry in entries
        )
        if substantive_count >= 2:
            category_substantive_eligible += 1
            if len(substantive_categories) > 1:
                category_substantive_differs += 1
                for left, right in itertools.combinations(sorted(substantive_categories), 2):
                    substantive_conflict_pairs[f"{left} vs {right}"] += 1

    return {
        "profiles_with_multiple_sources": multi_source,
        "raw_arabic_wording": {
            "eligible_profiles_with_at_least_two_nonblank_raw_grades": raw_eligible,
            "wording_differs": raw_differs,
            "rate": round(raw_differs / max(raw_eligible, 1), 6),
            "interpretation": "Lexical variation; not necessarily scholarly category disagreement.",
        },
        "itqan_category_all_source_entries": {
            "eligible_profiles": category_all_eligible,
            "category_differs": category_all_differs,
            "rate": round(category_all_differs / max(category_all_eligible, 1), 6),
            "includes_unknown_with_blank_raw_grade": True,
            "interpretation": (
                "Dataset-category variation, not a clean critic-disagreement rate, "
                "because blank source grades are represented as unknown."
            ),
        },
        "itqan_category_substantive_source_entries": {
            "eligible_profiles_with_at_least_two_nonblank_raw_grades": category_substantive_eligible,
            "category_differs": category_substantive_differs,
            "rate": round(
                category_substantive_differs / max(category_substantive_eligible, 1), 6
            ),
            "interpretation": (
                "Like-for-like comparison using Itqan's supplied grade_en categories "
                "only where the source entry also contains a raw Arabic grade."
            ),
        },
        "unknown_category_with_blank_raw_grade_entries": unknown_blank_entries,
        "normalized_vocabulary": dict(normalized_vocabulary.most_common()),
        "distinct_nonblank_raw_arabic_verdicts": len(raw_vocabulary),
        "most_common_raw_verdicts": dict(raw_vocabulary.most_common(10)),
        "sources_per_profile": {str(key): value for key, value in sorted(source_counts.items())},
        "most_common_substantive_category_conflicts": dict(
            substantive_conflict_pairs.most_common(10)
        ),
        "taxonomy_status": (
            "grade_en is an Itqan-supplied seven-category field. The downloaded "
            "manifest does not document a scholarly equivalence mapping for every raw phrase."
        ),
    }


def entry_id_audit(records):
    per_source = defaultdict(list)
    field_counts = Counter()

    for record in records:
        sources = record.get("classical_sources") or {}
        if not isinstance(sources, dict):
            continue
        for source, entry in sources.items():
            if not isinstance(entry, dict):
                continue
            field_counts.update(entry.keys())
            per_source[source].append(canonical_id(entry.get("entry_id")))

    per_source_report = {}
    for source, ids in sorted(per_source.items()):
        valid = [value for value in ids if value is not None]
        counts = Counter(valid)
        per_source_report[source] = {
            "entries": len(ids),
            "entry_ids_present": len(valid),
            "distinct_entry_ids": len(counts),
            "reused_entry_ids": sum(count > 1 for count in counts.values()),
            "max_profiles_sharing_one_entry_id": max(counts.values(), default=0),
        }

    fields = sorted(field_counts)
    has_print_locator = any(
        field.lower() in {"volume", "page", "vol", "pg", "edition"}
        for field in fields
    )

    return {
        "fields_inside_each_source_entry": fields,
        "field_frequency": dict(field_counts),
        "has_volume_page_or_edition_field": has_print_locator,
        "per_source": per_source_report,
        "semantics": {
            "confirmed": (
                "entry_id is stored under a named Itqan classical-source entry and "
                "is repeated for multiple profiles in several sources."
            ),
            "unknown": (
                "The downloaded shards do not provide a dereference table or a "
                "printed-edition volume/page mapping for entry_id."
            ),
            "strongest_honest_statement": (
                "According to the named source entry represented in Itqan, narrator X "
                "is recorded as [verdict] (Itqan entry_id Y)."
            ),
            "unsupported_statement": (
                "Directly cited from a specific printed volume/page of the classical work."
            ),
        },
    }


def main():
    records, _ = load_profiles()
    if not records:
        print("Itqan profiles not found.")
        return 1

    report = {
        "records": len(records),
        "disagreement": grading_disagreement(records),
        "entry_id": entry_id_audit(records),
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nSaved -> {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
