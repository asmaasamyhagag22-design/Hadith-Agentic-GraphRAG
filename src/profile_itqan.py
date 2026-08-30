"""Profile every downloaded Itqan v1.20 JSON file before entity resolution.

The profiler measures fields and integrity only.  It does not match MIS names
to profiles, infer identities, or collapse source-specific gradings.
"""

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import ITQAN_DIR, PROCESSED_DIR
from utils import strip_diacritics

REPORT_PATH = PROCESSED_DIR / "itqan_profile.json"

PROFILE_FILES = [
    "profiles_companion",
    "profiles_reliable",
    "profiles_mostly_reliable",
    "profiles_weak",
    "profiles_abandoned",
    "profiles_fabricator",
    "profiles_unknown",
]

EMPTY = {"", "-", "none", "null", "n/a", "غير معروف"}
PROVENANCE_HINTS = (
    "source", "ref", "citation", "book", "page", "volume",
    "entry", "text", "origin", "provenance",
)

_ALEF = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه",
})
_NON_ARABIC = re.compile(r"[^ء-ي ]+")
_ARABIC = re.compile(r"[ء-ي]")


def normalize_name(text):
    text = strip_diacritics(str(text or "")).translate(_ALEF)
    return " ".join(_NON_ARABIC.sub(" ", text).split())


def filled(value):
    """Robust missingness predicate; in particular, None is never populated."""

    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return str(value).strip().lower() not in EMPTY


def canonical_id(value):
    if not filled(value) or isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_profiles():
    """Return all seven profile shards and record counts per shard."""

    records = []
    per_file = {}
    for name in PROFILE_FILES:
        path = ITQAN_DIR / f"{name}.json"
        if not path.exists():
            per_file[name] = "MISSING"
            continue
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        entries = list(data.values()) if isinstance(data, dict) else data
        if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
            raise ValueError(f"Expected profile objects in {path}")
        for entry in entries:
            entry["_file"] = name
        records.extend(entries)
        per_file[name] = len(entries)

    if not records:
        # Every shard missing means the download is absent or the paths are
        # wrong.  Returning an empty list here would let downstream audits
        # report "0 profiles" as though it were a measured population.
        raise FileNotFoundError(
            f"No Itqan profile shards found under {ITQAN_DIR}. "
            f"Expected {', '.join(name + '.json' for name in PROFILE_FILES)}. "
            f"See DATA_SOURCES.md for how to obtain them."
        )

    return records, per_file


def validate_all_json_files(per_file):
    """Fully parse every downloaded JSON and compare shard counts to manifest."""

    file_report = {}
    parsed_data = {}
    for path in sorted(ITQAN_DIR.glob("*.json")):
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        parsed_data[path.name] = data
        file_report[path.name] = {
            "parsed_completely": True,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
            "top_level_type": type(data).__name__,
            "top_level_entries": len(data) if isinstance(data, (dict, list)) else None,
        }

    manifest = parsed_data.get("manifest.json")
    manifest_checks = {
        "present": isinstance(manifest, dict),
        "version": manifest.get("version") if isinstance(manifest, dict) else None,
        "declared_total_profiles": manifest.get("total_profiles") if isinstance(manifest, dict) else None,
        "declared_total_variants": manifest.get("total_variants") if isinstance(manifest, dict) else None,
        "profile_count_mismatches": {},
    }
    if isinstance(manifest, dict):
        for entry in manifest.get("files", []):
            if entry.get("type") != "profiles":
                continue
            stem = Path(entry["name"]).stem
            actual = per_file.get(stem)
            if actual != entry.get("count"):
                manifest_checks["profile_count_mismatches"][stem] = {
                    "declared": entry.get("count"), "actual": actual,
                }

    return file_report, manifest_checks


def relationship_stats(records, field, known_ids):
    records_with_field = records_nonempty = invalid_type = 0
    total_references = null_references = missing_targets = duplicate_within_record = 0

    for record in records:
        if field not in record:
            continue
        records_with_field += 1
        values = record.get(field)
        if not isinstance(values, list):
            if filled(values):
                invalid_type += 1
            continue
        if values:
            records_nonempty += 1
        canonical = [canonical_id(value) for value in values]
        total_references += len(values)
        null_references += sum(value is None for value in canonical)
        valid = [value for value in canonical if value is not None]
        missing_targets += sum(value not in known_ids for value in valid)
        duplicate_within_record += len(valid) - len(set(valid))

    return {
        "records_with_field": records_with_field,
        "records_with_nonempty_list": records_nonempty,
        "total_references": total_references,
        "invalid_field_types": invalid_type,
        "null_references": null_references,
        "references_to_missing_profile_ids": missing_targets,
        "duplicate_references_within_record": duplicate_within_record,
    }


def name_stats(records):
    normalized_names = [normalize_name(record.get("full_name")) for record in records]
    name_counts = Counter(name for name in normalized_names if name)

    variant_profiles = defaultdict(set)
    records_with_namings = total_raw = normalized_mentions = duplicate_within = 0
    profiles_in_collision = set()

    for index, record in enumerate(records):
        values = record.get("namings")
        if not isinstance(values, list) or not values:
            continue
        records_with_namings += 1
        total_raw += len(values)
        normalized = [normalize_name(value) for value in values]
        normalized = [value for value in normalized if value]
        normalized_mentions += len(normalized)
        duplicate_within += len(normalized) - len(set(normalized))
        for value in set(normalized):
            variant_profiles[value].add(index)

    for profile_indexes in variant_profiles.values():
        if len(profile_indexes) > 1:
            profiles_in_collision.update(profile_indexes)

    total = len(records)
    return {
        "arabic_full_names": {
            "records_with_arabic_script": sum(
                bool(_ARABIC.search(str(record.get("full_name") or "")))
                for record in records
            ),
            "distinct_normalized_names": len(name_counts),
            "normalized_names_shared_by_multiple_profiles": sum(
                count > 1 for count in name_counts.values()
            ),
            "profiles_in_colliding_normalized_names": sum(
                count for count in name_counts.values() if count > 1
            ),
            "max_profiles_sharing_one_normalized_name": max(name_counts.values(), default=0),
        },
        "namings": {
            "records_with_nonempty_namings": records_with_namings,
            "coverage": round(records_with_namings / max(total, 1), 6),
            "total_raw_variant_entries": total_raw,
            "nonempty_normalized_variant_mentions": normalized_mentions,
            "duplicate_normalized_variants_within_profile": duplicate_within,
            "distinct_normalized_variants": len(variant_profiles),
            "variants_pointing_to_multiple_profiles": sum(
                len(indexes) > 1 for indexes in variant_profiles.values()
            ),
            "profiles_touched_by_variant_collisions": len(profiles_in_collision),
        },
    }


def classical_source_stats(records):
    source_frequency = Counter()
    source_count_distribution = Counter()
    source_entry_ids = defaultdict(list)
    entry_fields = Counter()
    grade_categories = Counter()
    with_sources = invalid_sources = invalid_entries = 0
    entry_id_missing = source_count_mismatch = provenance_pair_mismatch = 0
    entries_total = blank_raw_unknown = 0

    for record in records:
        sources = record.get("classical_sources") or {}
        if not isinstance(sources, dict):
            invalid_sources += 1
            continue
        source_count_distribution[len(sources)] += 1
        if sources:
            with_sources += 1

        classical_pairs = set()
        for source, entry in sources.items():
            source_frequency[source] += 1
            entries_total += 1
            if not isinstance(entry, dict):
                invalid_entries += 1
                continue
            entry_fields.update(entry.keys())
            entry_id = canonical_id(entry.get("entry_id"))
            if entry_id is None:
                entry_id_missing += 1
            source_entry_ids[source].append(entry_id)
            grade = str(entry.get("grade_en") or "").strip()
            grade_categories[grade] += 1
            if grade == "unknown" and not filled(entry.get("grade_ar")):
                blank_raw_unknown += 1
            classical_pairs.add((source, entry_id))

        provenance = record.get("provenance") or {}
        if isinstance(provenance, dict):
            declared_count = provenance.get("source_count")
            if isinstance(declared_count, int) and declared_count != len(sources):
                source_count_mismatch += 1
            provenance_sources = provenance.get("sources") or []
            if isinstance(provenance_sources, list):
                provenance_pairs = {
                    (item.get("type"), canonical_id(item.get("entry_id")))
                    for item in provenance_sources if isinstance(item, dict)
                }
                if provenance_pairs != classical_pairs:
                    provenance_pair_mismatch += 1

    per_source = {}
    for source, ids in sorted(source_entry_ids.items()):
        valid = [value for value in ids if value is not None]
        counts = Counter(valid)
        per_source[source] = {
            "entries": len(ids),
            "entry_ids_present": len(valid),
            "distinct_entry_ids": len(counts),
            "reused_entry_ids": sum(count > 1 for count in counts.values()),
            "max_profiles_sharing_entry_id": max(counts.values(), default=0),
        }

    return {
        "profiles_with_sources": with_sources,
        "invalid_classical_sources_fields": invalid_sources,
        "invalid_source_entries": invalid_entries,
        "source_count_distribution": {str(key): value for key, value in sorted(source_count_distribution.items())},
        "distinct_sources": len(source_frequency),
        "source_frequency": dict(source_frequency.most_common()),
        "entries_total": entries_total,
        "fields_inside_source_entries": dict(entry_fields),
        "entry_ids_missing": entry_id_missing,
        "per_source_entry_id_consistency": per_source,
        "dataset_grade_categories": dict(grade_categories.most_common()),
        "unknown_category_with_blank_raw_grade": blank_raw_unknown,
        "provenance_source_count_mismatches": source_count_mismatch,
        "classical_vs_provenance_entry_pair_mismatches": provenance_pair_mismatch,
    }


def profile(records, manifest_checks, file_report):
    total = len(records)
    fields = Counter()
    for record in records:
        fields.update(key for key in record if key != "_file")

    coverage = {
        field: sum(filled(record.get(field)) for record in records)
        for field in fields
    }

    ids = [canonical_id(record.get("id")) for record in records]
    valid_ids = [value for value in ids if value is not None]
    id_counts = Counter(valid_ids)
    known_ids = set(valid_ids)

    names = name_stats(records)
    manifest_variants = manifest_checks.get("declared_total_variants")
    by_name_entries = file_report.get("by_name.json", {}).get("top_level_entries")
    names["variant_count_reconciliation"] = {
        "manifest_declared_total_variants": manifest_variants,
        "raw_namings_entries_in_profile_shards": names["namings"]["total_raw_variant_entries"],
        "by_name_top_level_entries": by_name_entries,
        "status": (
            "DISCREPANCY: manifest count is not the sum of namings[] entries"
            if manifest_variants != names["namings"]["total_raw_variant_entries"]
            else "MATCH"
        ),
    }

    provenance_fields = [
        field for field in fields
        if any(hint in field.lower() for hint in PROVENANCE_HINTS)
    ]

    return {
        "records": total,
        "fields_present": dict(fields),
        "field_fill_rate": {
            field: {"filled": count, "rate": round(count / max(total, 1), 6)}
            for field, count in sorted(coverage.items())
        },
        "identifiers": {
            "unique_ids": len(id_counts),
            "null_or_blank_ids": total - len(valid_ids),
            "duplicate_ids": sum(count > 1 for count in id_counts.values()),
            "max_records_sharing_one_id": max(id_counts.values(), default=0),
            "raw_python_types": dict(Counter(type(record.get("id")).__name__ for record in records)),
        },
        "names": names,
        "biographical_coverage": {
            field: coverage.get(field, 0)
            for field in (
                "kunya", "nasab", "laqab", "death", "tabaqat", "generation", "city"
            )
        },
        "relationships": {
            "teachers": relationship_stats(records, "teachers", known_ids),
            "students": relationship_stats(records, "students", known_ids),
        },
        "grading": {
            "grade_en_filled": coverage.get("grade_en", 0),
            "grade_ar_filled": coverage.get("grade_ar", 0),
            "dhahabi_filled": coverage.get("dhahabi", 0),
            "aggregate_grade_values": dict(Counter(
                str(record.get("grade_en") or "").strip() for record in records
            ).most_common()),
        },
        "identity_confidence": {
            "uniqueness": dict(Counter(
                str(record.get("uniqueness")) for record in records
            ).most_common()),
            "confidence": dict(Counter(
                str(record.get("confidence")) for record in records
            ).most_common()),
        },
        "classical_sources": classical_source_stats(records),
        "provenance_fields_found": provenance_fields,
    }


def main():
    records, per_file = load_profiles()
    if not records:
        print("No Itqan profile files found — download them first.")
        return 1

    file_report, manifest_checks = validate_all_json_files(per_file)
    report = {
        "files": per_file,
        "json_validation": file_report,
        "manifest_checks": manifest_checks,
        "profile": profile(records, manifest_checks, file_report),
        "limitations": [
            "The downloaded manifest documents dataset version/counts but not printed edition volume/page locators.",
            "Name and alias collisions are measured; no entity-resolution decision is made.",
            "Dataset grade_en categories are preserved as supplied and are not a new scholarly equivalence map.",
        ],
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    summary = {
        "records": report["profile"]["records"],
        "all_json_files_parsed": all(
            item["parsed_completely"] for item in file_report.values()
        ),
        "manifest": manifest_checks,
        "identifiers": report["profile"]["identifiers"],
        "namings": report["profile"]["names"]["namings"],
        "variant_reconciliation": report["profile"]["names"]["variant_count_reconciliation"],
        "relationships": report["profile"]["relationships"],
        "classical_sources": {
            key: report["profile"]["classical_sources"][key]
            for key in (
                "profiles_with_sources", "entries_total", "entry_ids_missing",
                "provenance_source_count_mismatches",
                "classical_vs_provenance_entry_pair_mismatches",
            )
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved -> {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
