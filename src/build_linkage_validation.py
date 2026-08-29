"""Create a frozen, reviewer-blind sample from accepted linkage pairs.

The visible CSV intentionally excludes scores, strata, confidence labels, and
matching strategy.  Hidden metadata is stored separately and must not be
joined until human verdicts are final.  This script never invents labels and
will not overwrite a reviewer file containing any verdict.
"""

import csv
import hashlib
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import MUSLIM_JSON_PATH, PROCESSED_DIR
from profile_mis import (
    ACCEPTANCE_SIMILARITY,
    CONTENT,
    build_tail_pairs,
    file_sha256,
    load_corpus,
    read_sheet,
)

REVIEW_CSV = PROCESSED_DIR / "linkage_validation_review.csv"
CLEAN_REVIEW_CSV = PROCESSED_DIR / "linkage_validation_human_review.csv"
HIDDEN_CSV = PROCESSED_DIR / "linkage_validation_hidden.csv"
META_JSON = PROCESSED_DIR / "linkage_validation_sampling.json"

SEED = 20260816
CONFIDENCE_LEVEL = 0.95
Z_95 = 1.959963984540054
ASSUMED_PRECISION = 0.99
TARGET_MARGIN = 0.01

REVIEW_COLUMNS = [
    "review_id",
    "our_idInBook",
    "mis_HadithNo",
    "our_text",
    "mis_text",
    "manual_verdict",
    "notes",
]

HIDDEN_COLUMNS = [
    "review_id",
    "population_index",
    "local_position",
    "mis_position",
    "our_chapterId",
    "mis_ChapterNo",
    "similarity",
    "quick_similarity",
    "candidate_count",
    "matching_strategy",
    "acceptance_threshold",
    "tail_signature",
]


class ReviewerSchemaError(RuntimeError):
    """The visible review file contains columns that can bias reviewers."""


def sample_size_for_proportion(
    population_size,
    assumed_precision=ASSUMED_PRECISION,
    margin=TARGET_MARGIN,
    z=Z_95,
):
    """Normal-approximation sizing with finite-population correction."""

    if population_size <= 0:
        raise ValueError("population_size must be positive")
    if not 0 < assumed_precision < 1:
        raise ValueError("assumed_precision must be between 0 and 1")
    if not 0 < margin < 1:
        raise ValueError("margin must be between 0 and 1")

    infinite_population = (
        z ** 2 * assumed_precision * (1 - assumed_precision) / margin ** 2
    )
    corrected = infinite_population / (
        1 + (infinite_population - 1) / population_size
    )
    return min(population_size, math.ceil(corrected))


def accepted_population_hash(accepted):
    payload = "\n".join(
        f"{row['local_position']}|{row['mis_position']}|{row['similarity']:.6f}"
        for row in sorted(accepted, key=lambda item: item["local_position"])
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_sample_rows(accepted, sample_size, seed=SEED):
    rng = random.Random(seed)
    indexed = list(enumerate(accepted, start=1))
    sampled = rng.sample(indexed, sample_size)

    review_rows = []
    hidden_rows = []

    for review_number, (population_index, row) in enumerate(sampled, start=1):
        review_id = f"VAL-{review_number:04d}"
        review_rows.append({
            "review_id": review_id,
            "our_idInBook": row["our_idInBook"],
            "mis_HadithNo": row["mis_HadithNo"],
            "our_text": row["our_text"],
            "mis_text": row["mis_text"],
            "manual_verdict": "",
            "notes": "",
        })
        hidden_rows.append({
            "review_id": review_id,
            "population_index": population_index,
            "local_position": row["local_position"],
            "mis_position": row["mis_position"],
            "our_chapterId": row["our_chapterId"],
            "mis_ChapterNo": row["mis_ChapterNo"],
            "similarity": row["similarity"],
            "quick_similarity": row["quick_similarity"],
            "candidate_count": row["candidate_count"],
            "matching_strategy": "unique normalized 10-word tail",
            "acceptance_threshold": ACCEPTANCE_SIMILARITY,
            "tail_signature": row["tail_signature"],
        })

    return review_rows, hidden_rows


def _read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path, columns, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _stable_visible_pairs_hash(review_rows):
    payload = "\n".join(
        f"{row['review_id']}|{row['our_idInBook']}|{row['mis_HadithNo']}"
        for row in review_rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_safe_existing_review(review_rows):
    if not REVIEW_CSV.exists():
        return False

    with open(REVIEW_CSV, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        existing_columns = list(reader.fieldnames or [])
        existing = list(reader)

    labelled = [row for row in existing if row.get("manual_verdict", "").strip()]
    if labelled:
        raise RuntimeError(
            f"Refusing to overwrite {REVIEW_CSV}: {len(labelled)} rows have human labels."
        )

    if existing_columns != REVIEW_COLUMNS:
        unexpected = [
            column for column in existing_columns if column not in REVIEW_COLUMNS
        ]
        missing = [
            column for column in REVIEW_COLUMNS if column not in existing_columns
        ]
        details = []
        if unexpected:
            details.append(f"unexpected columns: {', '.join(unexpected)}")
        if missing:
            details.append(f"missing columns: {', '.join(missing)}")
        raise ReviewerSchemaError(
            f"Reviewer-facing schema changed in {REVIEW_CSV} "
            f"({'; '.join(details)}). Preserve the file for audit, but do not "
            "use it as a blind human-review artifact."
        )

    comparable_columns = [column for column in REVIEW_COLUMNS if column not in {
        "manual_verdict", "notes",
    }]
    existing_pairs = [
        {column: str(row.get(column, "")) for column in comparable_columns}
        for row in existing
    ]
    proposed_pairs = [
        {column: str(row.get(column, "")) for column in comparable_columns}
        for row in review_rows
    ]
    if existing_pairs != proposed_pairs:
        raise RuntimeError(
            f"A different unlabeled validation sample already exists at {REVIEW_CSV}. "
            "Move it to a development audit or remove it explicitly before freezing a new sample."
        )
    return True


def _ensure_clean_reviewer_export(review_rows):
    """Create a clean copy without overwriting labels or a different sample."""

    if not CLEAN_REVIEW_CSV.exists():
        _write_csv(CLEAN_REVIEW_CSV, REVIEW_COLUMNS, review_rows)
        return True

    with open(
        CLEAN_REVIEW_CSV, "r", encoding="utf-8-sig", newline=""
    ) as handle:
        reader = csv.DictReader(handle)
        existing_columns = list(reader.fieldnames or [])
        existing = list(reader)

    if existing_columns != REVIEW_COLUMNS:
        raise RuntimeError(
            f"Refusing to overwrite {CLEAN_REVIEW_CSV}: reviewer schema differs."
        )
    labelled = [row for row in existing if row.get("manual_verdict", "").strip()]
    if labelled:
        raise RuntimeError(
            f"Refusing to overwrite {CLEAN_REVIEW_CSV}: "
            f"{len(labelled)} rows have human labels."
        )
    existing_serialized = [
        {column: str(row.get(column, "")) for column in REVIEW_COLUMNS}
        for row in existing
    ]
    proposed_serialized = [
        {column: str(row.get(column, "")) for column in REVIEW_COLUMNS}
        for row in review_rows
    ]
    if existing_serialized != proposed_serialized:
        raise RuntimeError(
            f"Refusing to overwrite {CLEAN_REVIEW_CSV}: sample content differs."
        )
    return False


def main():
    corpus = load_corpus()
    _, mis = read_sheet(CONTENT)
    pairs = build_tail_pairs(corpus, mis)
    accepted = [row for row in pairs if row["accepted"]]

    sample_size = sample_size_for_proportion(len(accepted))
    review_rows, hidden_rows = build_sample_rows(accepted, sample_size)

    REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    schema_warning = None
    clean_export_created = False
    try:
        already_exists = _ensure_safe_existing_review(review_rows)
    except ReviewerSchemaError as error:
        schema_warning = str(error)
        clean_export_created = _ensure_clean_reviewer_export(review_rows)
        already_exists = True

    meta = {
        "purpose": "Estimate precision of the frozen accepted-link population.",
        "population_size": len(accepted),
        "population_sha256": accepted_population_hash(accepted),
        "sample_size": sample_size,
        "seed": SEED,
        "sampling_method": "simple random sample without replacement",
        "target_confidence_level": CONFIDENCE_LEVEL,
        "assumed_precision_for_sizing": ASSUMED_PRECISION,
        "target_margin_of_error_for_sizing": TARGET_MARGIN,
        "sizing_formula": (
            "ceil((z^2*p*(1-p)/e^2) / "
            "(1 + ((z^2*p*(1-p)/e^2)-1)/N))"
        ),
        "post_review_interval_method": (
            "two-sided 95% Wilson score interval; report numerator, denominator, "
            "wrong, correct, and uncertain counts separately"
        ),
        "acceptance_rule": (
            "unique normalized 10-word tail candidate and order-sensitive "
            f"full-text SequenceMatcher ratio >= {ACCEPTANCE_SIMILARITY:.2f}"
        ),
        "visible_columns": REVIEW_COLUMNS,
        "hidden_until_labels_are_final": [
            "similarity", "quick_similarity", "matching_strategy",
            "acceptance_threshold", "tail_signature", "positions", "chapters",
        ],
        "allowed_manual_verdicts": ["correct", "wrong", "uncertain"],
        "manual_labels_present_at_generation": 0,
        "visible_pair_order_sha256": _stable_visible_pairs_hash(review_rows),
        "source_files": {
            "muslim_sha256": file_sha256(MUSLIM_JSON_PATH),
            "mis_content_sha256": file_sha256(CONTENT),
        },
        "freeze_rule": (
            "Do not tune the matcher from these rows. If they are used for development, "
            "retire this sample and generate a new untouched validation sample."
        ),
    }

    if not already_exists:
        _write_csv(REVIEW_CSV, REVIEW_COLUMNS, review_rows)
        _write_csv(HIDDEN_CSV, HIDDEN_COLUMNS, hidden_rows)
        with open(META_JSON, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(meta, handle, ensure_ascii=False, indent=2)
        action = "Created and frozen"
    elif schema_warning:
        clean_action = "Created" if clean_export_created else "Preserved"
        action = "Schema-changed audit file preserved"
        print(f"Reviewer schema warning    : {schema_warning}")
        print(f"{clean_action} clean human export: {CLEAN_REVIEW_CSV}")
    else:
        action = "Existing identical unlabeled sample preserved"

    print(f"Accepted-link population : {len(accepted)}")
    print(f"Sample size              : {sample_size}")
    print(f"Seed                     : {SEED}")
    print(
        f"Assumption               : p={ASSUMED_PRECISION:.2f}, "
        f"95% confidence, +/-{TARGET_MARGIN:.1%}"
    )
    print(f"{action}: {REVIEW_CSV}")
    print(f"Hidden metadata          : {HIDDEN_CSV}")
    print(f"Sampling record          : {META_JSON}")
    print(
        "Manual labels remain blank; sample-based human precision is not measured."
    )


if __name__ == "__main__":
    main()
