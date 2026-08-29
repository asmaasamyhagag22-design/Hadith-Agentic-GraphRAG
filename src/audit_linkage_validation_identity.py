"""Reproduce a narrow textual-identity audit of the linkage review sample.

This audit is deliberately separate from human precision validation.  It
does not edit the reviewer CSV and never treats an automated result as a
manual verdict.
"""

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path


TATWEEL = "\u0640"
WHITESPACE = re.compile(r"\s+")

# Combining marks in Unicode Arabic blocks.  NFC is applied first so that
# decomposed hamza/madda spellings which have a precomposed base letter are
# preserved as that base letter rather than accidentally reduced to alif.
ARABIC_MARK_BLOCKS = (
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x0870, 0x089F),
    (0x08A0, 0x08FF),
)

DEFAULT_REVIEW = Path("data/processed/linkage_validation_review.csv")
DEFAULT_OUTPUT = Path("data/processed/linkage_validation_ai_identity_audit.json")


def _is_arabic_combining_mark(character):
    codepoint = ord(character)
    in_arabic_block = any(
        start <= codepoint <= end for start, end in ARABIC_MARK_BLOCKS
    )
    return in_arabic_block and unicodedata.category(character) in {"Mn", "Me"}


def remove_arabic_combining_marks(text):
    """Remove only Unicode combining marks located in Arabic blocks."""

    return "".join(
        character
        for character in text
        if not _is_arabic_combining_mark(character)
    )


def normalize_narrow_identity(text):
    """Apply only NFC, Arabic-mark/tatweel removal, and whitespace folding."""

    normalized = unicodedata.normalize("NFC", str(text or ""))
    normalized = remove_arabic_combining_marks(normalized).replace(TATWEEL, "")
    normalized = WHITESPACE.sub(" ", normalized).strip()
    return unicodedata.normalize("NFC", normalized)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_rows(rows):
    raw_equal = 0
    normalized_equal = 0
    mismatched_review_ids = []
    human_verdicts_present = 0
    notes_present = 0
    supplied_ai_verdict_disagreements = 0

    for row_number, row in enumerate(rows, start=1):
        our_text = row.get("our_text", "")
        mis_text = row.get("mis_text", "")
        raw_match = our_text == mis_text
        normalized_match = (
            normalize_narrow_identity(our_text)
            == normalize_narrow_identity(mis_text)
        )

        raw_equal += raw_match
        normalized_equal += normalized_match
        if not normalized_match:
            mismatched_review_ids.append(
                row.get("review_id") or f"row-{row_number}"
            )

        human_verdicts_present += bool(row.get("manual_verdict", "").strip())
        notes_present += bool(row.get("notes", "").strip())

        supplied = row.get("ai_verdict", "").strip().casefold()
        if supplied and (supplied == "correct") != normalized_match:
            supplied_ai_verdict_disagreements += 1

    total = len(rows)
    return {
        "rows_reviewed": total,
        "raw_strings_exactly_equal": raw_equal,
        "exact_after_narrow_normalization": normalized_equal,
        "needs_manual_adjudication_after_computational_check": (
            total - normalized_equal
        ),
        "mismatched_review_ids": mismatched_review_ids,
        "manual_verdicts_present": human_verdicts_present,
        "notes_present": notes_present,
        "supplied_ai_verdict_disagreements": supplied_ai_verdict_disagreements,
    }


def audit_file(review_path):
    with open(review_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        required = {"review_id", "our_text", "mis_text"}
        missing = sorted(required - set(columns))
        if missing:
            raise ValueError(f"Missing required review columns: {', '.join(missing)}")
        rows = list(reader)

    result = audit_rows(rows)
    result.update({
        "audit_type": "AI/computational textual-identity audit; not human validation",
        "review_file": str(review_path),
        "review_file_sha256": sha256_file(review_path),
        "review_columns": columns,
        "normalization": {
            "unicode": "NFC before and after mark removal",
            "removed": [
                "tatweel U+0640",
                "Unicode Mn/Me combining marks in Arabic blocks",
            ],
            "whitespace": "collapse Unicode whitespace runs and trim edges",
            "not_removed_or_substituted": [
                "Arabic base letters",
                "words",
                "punctuation",
            ],
        },
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = audit_file(args.review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print("Linkage validation computational identity audit")
    print(f"Rows reviewed                    : {result['rows_reviewed']}")
    print(f"Raw strings exactly equal        : {result['raw_strings_exactly_equal']}")
    print(
        "Exact after narrow normalization: "
        f"{result['exact_after_narrow_normalization']}"
    )
    print(
        "Computational mismatches          : "
        f"{result['needs_manual_adjudication_after_computational_check']}"
    )
    print(f"Human verdicts present           : {result['manual_verdicts_present']}")
    print(f"Audit record                     : {args.output}")
    print("This is not human precision validation.")


if __name__ == "__main__":
    main()
