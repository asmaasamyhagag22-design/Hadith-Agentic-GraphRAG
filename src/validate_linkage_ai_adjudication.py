"""Validate an aggregate AI adjudication against the frozen 11-row census.

The source report is recorded as AI-assisted provenance.  This validator
never writes to the manual_verdict or notes columns.
"""

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from .audit_linkage_ambiguity import (
    NONEXACT_REVIEW_PATH,
    REPORT_PATH as AMBIGUITY_REPORT_PATH,
    classify_nonexact_exception,
)
from .audit_linkage_validation_identity import sha256_file
from .config import PROCESSED_DIR


OUTPUT_PATH = PROCESSED_DIR / "linkage_non_exact_ai_adjudication.json"
COUNT_PATTERN = re.compile(r"^-\s*(correct|wrong|uncertain):\s*(\d+)\s*$", re.I | re.M)


def parse_ai_report(text):
    counts = {
        label.casefold(): int(value)
        for label, value in COUNT_PATTERN.findall(text)
    }
    required = {"correct", "wrong", "uncertain"}
    if set(counts) != required:
        raise ValueError("AI report must provide correct, wrong, and uncertain counts")
    ai_label_present = bool(
        re.search(r"assistant/AI-assisted adjudication", text, re.I)
        and re.search(r"not independent human validation", text, re.I)
    )
    if not ai_label_present:
        raise ValueError("AI report must explicitly disclaim independent human validation")
    return counts


def evaluate_gate(ambiguity_report, validation):
    accepted = ambiguity_report["accepted_links"]
    unique_unique = ambiguity_report["collision_classification"][
        "UNIQUE_UNIQUE"
    ]["count"]
    identity = ambiguity_report["full_accepted_exact_identity"]
    exact = identity["exact_normalized_pairs"]
    nonexact = identity["non_exact_pairs"]
    retained_core_unique = identity["non_exact_summary"][
        "retained_exception_core_unique_unique_pairs"
    ]
    ambiguous_collisions = ambiguity_report[
        "collision_groups_involved_in_accepted_links"
    ]["ambiguous"]
    supported = validation["deterministic_validation"]["supported"]
    unresolved = validation["deterministic_validation"]["unresolved"]

    open_conditions = {
        "all_accepted_links_unique_unique": unique_unique == accepted,
        "no_ambiguous_collision_groups": ambiguous_collisions == 0,
        "exact_plus_supported_exceptions_cover_all_accepted": (
            exact + supported == accepted and supported == nonexact
        ),
        "no_unresolved_exception_pairs": unresolved == 0,
        "all_exception_retained_cores_unique_unique": (
            retained_core_unique == nonexact
        ),
        "ai_aggregate_consistent_with_deterministic_census": validation[
            "aggregate_consistent"
        ],
    }
    return {
        "decision": (
            "GATE OPEN" if all(open_conditions.values()) else "GATE CLOSED"
        ),
        "conditions": open_conditions,
        "accepted_links": accepted,
        "narrow_normalized_exact_unique_links": exact,
        "deterministically_supported_exception_links": supported,
        "unique_unique_retained_exception_cores": retained_core_unique,
        "unresolved_links": accepted - exact - supported,
        "manual_validation_status": "NOT PERFORMED",
        "phase_transition_authorized": False,
        "phase_transition_note": (
            "This evidence decision does not authorize entity resolution or graph "
            "construction; wait for explicit user approval."
        ),
    }


def validate_report(
    report_path,
    review_path=NONEXACT_REVIEW_PATH,
    ambiguity_path=AMBIGUITY_REPORT_PATH,
):
    text = report_path.read_text(encoding="utf-8-sig")
    declared = parse_ai_report(text)
    with open(review_path, "r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    deterministic = []
    for row in rows:
        classification = classify_nonexact_exception(
            row.get("our_text", ""), row.get("mis_text", "")
        )
        deterministic.append({
            "review_id": row.get("review_id"),
            "our_idInBook": row.get("our_idInBook"),
            "mis_HadithNo": row.get("mis_HadithNo"),
            "ai_verdict": "correct" if declared == {
                "correct": len(rows), "wrong": 0, "uncertain": 0
            } else "aggregate_only",
            **classification,
        })

    manual_labels = sum(
        bool(row.get("manual_verdict", "").strip()) for row in rows
    )
    supported = sum(
        row["status"] == "DETERMINISTICALLY_SUPPORTED"
        for row in deterministic
    )
    declared_total = sum(declared.values())
    aggregate_consistent = (
        declared_total == len(rows)
        and declared == {"correct": len(rows), "wrong": 0, "uncertain": 0}
        and supported == len(rows)
    )
    result = {
        "audit_type": "AI-assisted adjudication provenance plus deterministic exception validation",
        "source_ai_report": {
            "path": str(report_path.resolve()),
            "sha256": sha256_file(report_path),
            "explicitly_not_independent_human_validation": True,
            "declared_counts": declared,
        },
        "targeted_review": {
            "path": str(review_path.resolve()),
            "sha256": sha256_file(review_path),
            "rows": len(rows),
            "manual_labels_present": manual_labels,
        },
        "deterministic_validation": {
            "supported": supported,
            "unresolved": len(rows) - supported,
            "categories": dict(Counter(row["category"] for row in deterministic)),
            "pairs": deterministic,
        },
        "aggregate_consistent": aggregate_consistent,
        "manual_columns_modified": False,
    }
    with open(ambiguity_path, "r", encoding="utf-8") as handle:
        ambiguity_report = json.load(handle)
    result["ambiguity_audit"] = {
        "path": str(ambiguity_path.resolve()),
        "sha256": sha256_file(ambiguity_path),
    }
    result["gate_evidence"] = evaluate_gate(ambiguity_report, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--review", type=Path, default=NONEXACT_REVIEW_PATH)
    parser.add_argument(
        "--ambiguity-audit", type=Path, default=AMBIGUITY_REPORT_PATH
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    result = validate_report(args.report, args.review, args.ambiguity_audit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print("Targeted linkage AI-adjudication validation")
    print(f"Declared counts          : {result['source_ai_report']['declared_counts']}")
    print(f"Deterministically supported: {result['deterministic_validation']['supported']}")
    print(f"Unresolved               : {result['deterministic_validation']['unresolved']}")
    print(f"Manual labels present    : {result['targeted_review']['manual_labels_present']}")
    print(f"Aggregate consistent     : {result['aggregate_consistent']}")
    print(f"Gate evidence            : {result['gate_evidence']['decision']}")
    print(f"Output                   : {args.output}")
    if not result["aggregate_consistent"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
