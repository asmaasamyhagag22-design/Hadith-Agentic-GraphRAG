"""Audit occurrence-level ambiguity in accepted Sahih Muslim <-> MIS links.

The analysis uses the same narrow textual-identity normalization as the
frozen-sample audit.  It measures collisions and structural evidence but
never changes or creates a linkage and never performs entity resolution.
"""

import csv
import difflib
import hashlib
import itertools
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_linkage_validation_identity import (
    TATWEEL,
    WHITESPACE,
    normalize_narrow_identity,
    remove_arabic_combining_marks,
    sha256_file,
)
from build_linkage_validation import CLEAN_REVIEW_CSV, REVIEW_CSV
from config import MUSLIM_JSON_PATH, PROCESSED_DIR
from profile_mis import CONTENT, build_tail_pairs, file_sha256, load_corpus, read_sheet


REPORT_PATH = PROCESSED_DIR / "linkage_ambiguity_audit.json"
NONEXACT_REVIEW_PATH = PROCESSED_DIR / "linkage_non_exact_review.csv"
NONEXACT_REVIEW_COLUMNS = (
    "review_id",
    "our_idInBook",
    "mis_HadithNo",
    "our_text",
    "mis_text",
    "manual_verdict",
    "notes",
)
TRANSFORMATIONS = (
    "UNICODE_NFC",
    "DIACRITICS",
    "TATWEEL",
    "WHITESPACE",
)
TIMESTAMP_ARTIFACT = re.compile(
    r"^[\s\u200e\u200f\d:/.-]*[صم]?[\s\u200e\u200f\d:/.-]*$"
)


def _normalized_text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_arabic_letter(character):
    codepoint = ord(character)
    in_arabic_block = (
        0x0600 <= codepoint <= 0x06FF
        or 0x0750 <= codepoint <= 0x077F
        or 0x0870 <= codepoint <= 0x089F
        or 0x08A0 <= codepoint <= 0x08FF
    )
    return in_arabic_block and unicodedata.category(character).startswith("L")


def arabic_word_tokens(text):
    tokens = []
    current = []
    for character in normalize_narrow_identity(text):
        if _is_arabic_letter(character):
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def deterministic_text_delta(left, right):
    local_normalized = normalize_narrow_identity(left)
    mis_normalized = normalize_narrow_identity(right)
    local_words = arabic_word_tokens(left)
    mis_words = arabic_word_tokens(right)
    word_changes = []
    for tag, left_start, left_end, right_start, right_end in difflib.SequenceMatcher(
        None, local_words, mis_words, autojunk=False
    ).get_opcodes():
        if tag != "equal":
            word_changes.append({
                "operation": tag,
                "local_word_index": [left_start, left_end],
                "mis_word_index": [right_start, right_end],
                "local_words": local_words[left_start:left_end],
                "mis_words": mis_words[right_start:right_end],
            })

    character_changes = []
    for tag, left_start, left_end, right_start, right_end in difflib.SequenceMatcher(
        None, local_normalized, mis_normalized, autojunk=False
    ).get_opcodes():
        if tag != "equal":
            character_changes.append({
                "operation": tag,
                "local_character_index": [left_start, left_end],
                "mis_character_index": [right_start, right_end],
                "local_segment": local_normalized[left_start:left_end],
                "mis_segment": mis_normalized[right_start:right_end],
            })

    local_base_letters = "".join(local_words)
    mis_base_letters = "".join(mis_words)
    return {
        "arabic_word_sequence_equal": local_words == mis_words,
        "arabic_base_letter_sequence_equal": (
            local_base_letters == mis_base_letters
        ),
        "punctuation_or_spacing_only": (
            local_words == mis_words and local_normalized != mis_normalized
        ),
        "word_changes": word_changes,
        "character_changes": character_changes,
    }


def classify_nonexact_exception(left, right):
    """Recognize only the six measured exception shapes in the 11-row census."""

    local = normalize_narrow_identity(left)
    mis = normalize_narrow_identity(right)
    changes = deterministic_text_delta(left, right)["character_changes"]

    if len(changes) == 1:
        change = changes[0]
        local_start, local_end = change["local_character_index"]
        mis_start, mis_end = change["mis_character_index"]
        local_segment = change["local_segment"]
        mis_segment = change["mis_segment"]

        if (
            change["operation"] == "delete"
            and local_start == 0
            and not mis_segment
            and local_segment.strip().endswith("ح")
            and local[local_end:] == mis
        ):
            return {
                "status": "DETERMINISTICALLY_SUPPORTED",
                "category": "LOCAL_LEADING_HA_TRANSITION_PREFIX",
                "evidence": (
                    "MIS text is the exact retained suffix after one local-only "
                    "leading segment ending in the standalone ح transition marker."
                ),
                "artifact_character_count": len(local_segment),
            }

        if (
            change["operation"] == "insert"
            and local_start == local_end
            and mis_start < mis_end
            and any(character.isdigit() for character in mis_segment)
            and TIMESTAMP_ARTIFACT.fullmatch(mis_segment)
            and mis[:mis_start] + mis[mis_end:] == local
        ):
            return {
                "status": "DETERMINISTICALLY_SUPPORTED",
                "category": "MIS_TIMESTAMP_INSERTION",
                "evidence": (
                    "Removing the complete MIS-only segment matching a numeric "
                    "time/date artifact character set makes the strings exact."
                ),
                "artifact_character_count": len(mis_segment),
            }

        if (
            change["operation"] == "insert"
            and mis_segment in {"\u200e", "\u200f"}
            and mis[:mis_start] + mis[mis_end:] == local
        ):
            return {
                "status": "DETERMINISTICALLY_SUPPORTED",
                "category": "MIS_BIDI_FORMAT_MARK",
                "evidence": "Removing the single MIS-only bidi format mark makes the strings exact.",
                "artifact_character_count": 1,
            }

        if (
            change["operation"] == "insert"
            and mis_segment == "،"
            and mis[:mis_start] + mis[mis_end:] == local
        ):
            return {
                "status": "DETERMINISTICALLY_SUPPORTED",
                "category": "MIS_ARABIC_COMMA",
                "evidence": "Removing the single MIS-only Arabic comma makes the strings exact.",
                "artifact_character_count": 1,
            }

        if (
            change["operation"] == "insert"
            and mis_segment.strip() == "ح"
            and mis[:mis_start] + mis[mis_end:] == local
        ):
            return {
                "status": "DETERMINISTICALLY_SUPPORTED",
                "category": "MIS_STANDALONE_HA_TRANSITION",
                "evidence": (
                    "Removing the one MIS-only standalone ح transition marker "
                    "makes the strings exact."
                ),
                "artifact_character_count": len(mis_segment),
            }

    if (
        changes
        and all(
            change["operation"] == "delete"
            and change["local_segment"] == "\\"
            and not change["mis_segment"]
            for change in changes
        )
        and local.replace("\\", "") == mis
    ):
        return {
            "status": "DETERMINISTICALLY_SUPPORTED",
            "category": "LOCAL_BACKSLASH_ARTIFACTS",
            "evidence": (
                "Removing every local-only literal backslash makes the strings exact."
            ),
            "artifact_character_count": len(changes),
        }

    return {
        "status": "UNRESOLVED",
        "category": "NO_NARROW_EXCEPTION_RULE_MATCHED",
        "evidence": (
            "The difference does not match any measured exception shape; no "
            "automatic record-identity conclusion is made."
        ),
        "artifact_character_count": None,
    }


def retained_text_after_exception(left, right):
    """Return the exact common text proved by a supported exception rule."""

    classification = classify_nonexact_exception(left, right)
    if classification["status"] != "DETERMINISTICALLY_SUPPORTED":
        return None
    local = normalize_narrow_identity(left)
    mis = normalize_narrow_identity(right)
    if classification["category"] in {
        "LOCAL_LEADING_HA_TRANSITION_PREFIX",
        "LOCAL_BACKSLASH_ARTIFACTS",
    }:
        return mis
    return local


def _decimal_fraction(value):
    with localcontext() as context:
        context.prec = 40
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def _inversion_count(values):
    def merge_count(items):
        if len(items) < 2:
            return items, 0
        middle = len(items) // 2
        left, left_count = merge_count(items[:middle])
        right, right_count = merge_count(items[middle:])
        merged = []
        left_index = right_index = split_count = 0
        while left_index < len(left) and right_index < len(right):
            if left[left_index] <= right[right_index]:
                merged.append(left[left_index])
                left_index += 1
            else:
                merged.append(right[right_index])
                right_index += 1
                split_count += len(left) - left_index
        merged.extend(left[left_index:])
        merged.extend(right[right_index:])
        return merged, left_count + right_count + split_count

    return merge_count(list(values))[1]


def exact_rank_statistics(rows, position_key):
    """Return exact fractions and 40-digit decimals for unique position ranks."""

    ordered = sorted(rows, key=lambda row: row["local_position"])
    values = [row[position_key] for row in ordered]
    if len(values) != len(set(values)):
        raise ValueError(f"{position_key} contains ties; exact no-tie formula invalid")

    count = len(values)
    ranks = {
        value: rank
        for rank, value in enumerate(sorted(values), start=1)
    }
    squared_rank_delta = sum(
        (local_rank - ranks[value]) ** 2
        for local_rank, value in enumerate(values, start=1)
    )
    spearman = Fraction(
        count * (count * count - 1) - 6 * squared_rank_delta,
        count * (count * count - 1),
    )

    inversions = _inversion_count(values)
    comparable_pairs = count * (count - 1) // 2
    inversion_rate = Fraction(inversions, comparable_pairs)
    kendall = Fraction(comparable_pairs - 2 * inversions, comparable_pairs)

    return {
        "pairs": count,
        "spearman_exact_fraction": f"{spearman.numerator}/{spearman.denominator}",
        "spearman_decimal": _decimal_fraction(spearman),
        "kendall_tau_exact_fraction": f"{kendall.numerator}/{kendall.denominator}",
        "kendall_tau_decimal": _decimal_fraction(kendall),
        "inversion_count": inversions,
        "comparable_pairs": comparable_pairs,
        "inversion_rate_exact_fraction": (
            f"{inversion_rate.numerator}/{inversion_rate.denominator}"
        ),
        "inversion_rate_decimal": _decimal_fraction(inversion_rate),
        "squared_rank_delta": squared_rank_delta,
    }


def unwrap_mis_positions(accepted, mis_size):
    ordered = sorted(accepted, key=lambda row: row["local_position"])
    unwrapped = []
    rotations = []
    added = 0
    previous = None

    for row in ordered:
        raw_position = row["mis_position"]
        if previous is not None and raw_position - previous < -(mis_size / 2):
            added += mis_size
            rotations.append({
                "before": {
                    "our_idInBook": unwrapped[-1]["our_idInBook"],
                    "mis_HadithNo": unwrapped[-1]["mis_HadithNo"],
                    "local_position": unwrapped[-1]["local_position"],
                    "mis_position": unwrapped[-1]["mis_position"],
                },
                "after": {
                    "our_idInBook": row["our_idInBook"],
                    "mis_HadithNo": row["mis_HadithNo"],
                    "local_position": row["local_position"],
                    "mis_position": row["mis_position"],
                },
                "raw_jump": raw_position - previous,
            })
        annotated = dict(row)
        annotated["unwrapped_mis_position"] = raw_position + added
        unwrapped.append(annotated)
        previous = raw_position

    return unwrapped, rotations


def enumerate_inversion_pairs(rows, position_key, maximum=1000):
    ordered = sorted(rows, key=lambda row: row["local_position"])
    expected = _inversion_count(row[position_key] for row in ordered)
    if expected > maximum:
        return {
            "enumerated": False,
            "reason": f"{expected} inversions exceeds enumeration limit {maximum}",
            "pairs": [],
        }

    inversions = []
    for left_index, left in enumerate(ordered):
        for right in ordered[left_index + 1:]:
            if left[position_key] > right[position_key]:
                inversions.append({
                    "earlier_local_record": {
                        "our_idInBook": left["our_idInBook"],
                        "local_position": left["local_position"],
                        "mis_HadithNo": left["mis_HadithNo"],
                        "mis_position": left["mis_position"],
                        position_key: left[position_key],
                    },
                    "later_local_record": {
                        "our_idInBook": right["our_idInBook"],
                        "local_position": right["local_position"],
                        "mis_HadithNo": right["mis_HadithNo"],
                        "mis_position": right["mis_position"],
                        position_key: right[position_key],
                    },
                })
    if len(inversions) != expected:
        raise AssertionError("Enumerated inversion count does not match merge count")
    return {"enumerated": True, "pairs": inversions}


def _text_index(records, text_field, id_field):
    index = defaultdict(list)
    for position, record in enumerate(records, start=1):
        normalized = normalize_narrow_identity(record.get(text_field))
        index[normalized].append({
            "id": record.get(id_field),
            "position": position,
        })
    return index


def _index_cardinality(index):
    duplicate_groups = [records for records in index.values() if len(records) > 1]
    return {
        "distinct_normalized_texts": len(index),
        "duplicate_normalized_text_groups": len(duplicate_groups),
        "records_in_duplicate_normalized_text_groups": sum(
            len(records) for records in duplicate_groups
        ),
        "maximum_group_size": max((len(records) for records in index.values()), default=0),
        "blank_normalized_text_records": len(index.get("", [])),
    }


def classify_accepted_collisions(corpus, mis, accepted):
    local_index = _text_index(corpus, "arabic", "idInBook")
    mis_index = _text_index(mis, "HadithText_GhairMushakkal", "HadithNo")
    counts = Counter()
    annotated = []

    for row in accepted:
        local_key = normalize_narrow_identity(row["our_text"])
        mis_key = normalize_narrow_identity(row["mis_text"])
        local_count = len(local_index[local_key])
        mis_count = len(mis_index[mis_key])
        category = (
            ("UNIQUE" if local_count == 1 else "MULTI")
            + "_"
            + ("UNIQUE" if mis_count == 1 else "MULTI")
        )
        counts[category] += 1
        item = dict(row)
        item.update({
            "local_normalized_text": local_key,
            "mis_normalized_text": mis_key,
            "normalized_text_exact": local_key == mis_key,
            "local_normalized_text_count": local_count,
            "mis_normalized_text_count": mis_count,
            "collision_class": category,
        })
        annotated.append(item)

    total = len(accepted)
    ordered_categories = (
        "UNIQUE_UNIQUE",
        "UNIQUE_MULTI",
        "MULTI_UNIQUE",
        "MULTI_MULTI",
    )
    summary = {
        category: {
            "count": counts[category],
            "percentage": (counts[category] * 100 / total) if total else 0,
        }
        for category in ordered_categories
    }
    return summary, annotated, local_index, mis_index


def _anchor_summary(row):
    if row is None:
        return None
    return {
        "our_idInBook": row["our_idInBook"],
        "mis_HadithNo": row["mis_HadithNo"],
        "local_position": row["local_position"],
        "mis_position": row["mis_position"],
        "unwrapped_mis_position": row["unwrapped_mis_position"],
        "collision_class": row["collision_class"],
        "normalized_text_exact": row["normalized_text_exact"],
    }


def nonexact_structural_neighborhoods(annotated_accepted, mis_size):
    unwrapped, _ = unwrap_mis_positions(annotated_accepted, mis_size)
    ordered = sorted(unwrapped, key=lambda row: row["local_position"])
    results = {}

    for index, row in enumerate(ordered):
        if row["normalized_text_exact"]:
            continue
        previous = next(
            (
                ordered[candidate]
                for candidate in range(index - 1, -1, -1)
                if ordered[candidate]["normalized_text_exact"]
                and ordered[candidate]["collision_class"] == "UNIQUE_UNIQUE"
            ),
            None,
        )
        following = next(
            (
                ordered[candidate]
                for candidate in range(index + 1, len(ordered))
                if ordered[candidate]["normalized_text_exact"]
                and ordered[candidate]["collision_class"] == "UNIQUE_UNIQUE"
            ),
            None,
        )
        bracketed = bool(
            previous
            and following
            and previous["unwrapped_mis_position"]
            < row["unwrapped_mis_position"]
            < following["unwrapped_mis_position"]
        )
        local_gaps = (
            [
                row["local_position"] - previous["local_position"],
                following["local_position"] - row["local_position"],
            ]
            if previous and following
            else None
        )
        mis_gaps = (
            [
                row["unwrapped_mis_position"]
                - previous["unwrapped_mis_position"],
                following["unwrapped_mis_position"]
                - row["unwrapped_mis_position"],
            ]
            if previous and following
            else None
        )
        offsets = (
            [
                previous["unwrapped_mis_position"]
                - previous["local_position"],
                row["unwrapped_mis_position"] - row["local_position"],
                following["unwrapped_mis_position"]
                - following["local_position"],
            ]
            if previous and following
            else None
        )
        results[row["local_position"]] = {
            "previous_unique_exact_anchor": _anchor_summary(previous),
            "next_unique_exact_anchor": _anchor_summary(following),
            "anchors_bracket_pair_in_unwrapped_order": bracketed,
            "local_gaps_to_anchors": local_gaps,
            "mis_gaps_to_anchors": mis_gaps,
            "gap_pattern_identical": local_gaps == mis_gaps,
            "constant_unwrapped_position_offset": (
                bool(offsets) and len(set(offsets)) == 1
            ),
            "interpretation": (
                "Order and unique-exact neighbors are corroboration only; they do "
                "not convert a non-exact text pair into deterministic identity."
            ),
        }
    return results


def inspect_collision_groups(
    annotated_accepted,
    local_index,
    mis_index,
    mis_size,
):
    unwrapped, _ = unwrap_mis_positions(annotated_accepted, mis_size)
    groups = defaultdict(list)
    for row in unwrapped:
        if (
            row["normalized_text_exact"]
            and (
                row["local_normalized_text_count"] > 1
                or row["mis_normalized_text_count"] > 1
            )
        ):
            groups[row["local_normalized_text"]].append(row)

    ordered_accepted = sorted(unwrapped, key=lambda row: row["local_position"])
    record_index = {
        row["local_position"]: index
        for index, row in enumerate(ordered_accepted)
    }
    results = []

    for normalized_text, pairings in groups.items():
        local_records = local_index[normalized_text]
        mis_records = mis_index[normalized_text]
        group_positions = {row["local_position"] for row in pairings}
        neighbor_evidence = []

        for pairing in sorted(pairings, key=lambda row: row["local_position"]):
            accepted_index = record_index[pairing["local_position"]]
            previous = next(
                (
                    ordered_accepted[index]
                    for index in range(accepted_index - 1, -1, -1)
                    if ordered_accepted[index]["local_position"] not in group_positions
                ),
                None,
            )
            following = next(
                (
                    ordered_accepted[index]
                    for index in range(accepted_index + 1, len(ordered_accepted))
                    if ordered_accepted[index]["local_position"] not in group_positions
                ),
                None,
            )
            anchors_unique_exact = all(
                anchor is not None
                and anchor["collision_class"] == "UNIQUE_UNIQUE"
                and anchor["normalized_text_exact"]
                for anchor in (previous, following)
            )
            bracketed = bool(
                previous
                and following
                and previous["unwrapped_mis_position"]
                < pairing["unwrapped_mis_position"]
                < following["unwrapped_mis_position"]
            )
            neighbor_evidence.append({
                "pair": {
                    "our_idInBook": pairing["our_idInBook"],
                    "mis_HadithNo": pairing["mis_HadithNo"],
                    "local_position": pairing["local_position"],
                    "mis_position": pairing["mis_position"],
                },
                "previous_unique_exact_anchor": _anchor_summary(previous),
                "next_unique_exact_anchor": _anchor_summary(following),
                "anchors_are_unique_exact": anchors_unique_exact,
                "anchors_bracket_pair_in_unwrapped_order": bracketed,
            })

        complete_bijection = (
            len(pairings) == len(local_records) == len(mis_records)
            and len({row["local_position"] for row in pairings}) == len(local_records)
            and len({row["mis_position"] for row in pairings}) == len(mis_records)
        )
        order_preserving = all(
            left["unwrapped_mis_position"] < right["unwrapped_mis_position"]
            for left, right in zip(
                sorted(pairings, key=lambda row: row["local_position"]),
                sorted(pairings, key=lambda row: row["local_position"])[1:],
            )
        )
        neighbors_corroborate = bool(neighbor_evidence) and all(
            evidence["anchors_are_unique_exact"]
            and evidence["anchors_bracket_pair_in_unwrapped_order"]
            for evidence in neighbor_evidence
        )
        structurally_resolved = (
            complete_bijection and order_preserving and neighbors_corroborate
        )
        classification = (
            "STRUCTURALLY_RESOLVED" if structurally_resolved else "AMBIGUOUS"
        )
        evidence = (
            "Complete one-to-one coverage of both duplicate groups, the only "
            "order-preserving pairing, and bracketing unique-exact neighbors."
            if structurally_resolved
            else "At least one required condition is absent: complete bijection, "
            "unique order-preserving correspondence, or bracketing unique-exact "
            "neighbor evidence. No automatic occurrence resolution is made."
        )

        results.append({
            "normalized_text_sha256": _normalized_text_hash(normalized_text),
            "normalized_character_count": len(normalized_text),
            "local_group_size": len(local_records),
            "mis_group_size": len(mis_records),
            "local_records": [
                {"our_idInBook": row["id"], "local_position": row["position"]}
                for row in local_records
            ],
            "mis_records": [
                {"mis_HadithNo": row["id"], "mis_position": row["position"]}
                for row in mis_records
            ],
            "accepted_pairings": [
                {
                    "our_idInBook": row["our_idInBook"],
                    "mis_HadithNo": row["mis_HadithNo"],
                    "local_position": row["local_position"],
                    "mis_position": row["mis_position"],
                    "unwrapped_mis_position": row["unwrapped_mis_position"],
                }
                for row in sorted(pairings, key=lambda row: row["local_position"])
            ],
            "complete_bijection": complete_bijection,
            "order_provides_unique_correspondence": (
                complete_bijection and order_preserving
            ),
            "neighboring_records_corroborate": neighbors_corroborate,
            "multiple_pairings_remain_equally_defensible": not structurally_resolved,
            "neighbor_evidence": neighbor_evidence,
            "classification": classification,
            "evidence": evidence,
        })

    return sorted(results, key=lambda row: row["normalized_text_sha256"])


def apply_transform_subset(text, transformations):
    value = str(text or "")
    selected = set(transformations)
    if "UNICODE_NFC" in selected:
        value = unicodedata.normalize("NFC", value)
    if "DIACRITICS" in selected:
        value = remove_arabic_combining_marks(value)
    if "TATWEEL" in selected:
        value = value.replace(TATWEEL, "")
    if "WHITESPACE" in selected:
        value = WHITESPACE.sub(" ", value).strip()
    if "UNICODE_NFC" in selected:
        value = unicodedata.normalize("NFC", value)
    return value


def minimal_equalizing_transform_sets(left, right):
    if left == right:
        return [tuple()]
    for size in range(1, len(TRANSFORMATIONS) + 1):
        matches = []
        for selected in itertools.combinations(TRANSFORMATIONS, size):
            if apply_transform_subset(left, selected) == apply_transform_subset(
                right, selected
            ):
                matches.append(selected)
        if matches:
            return matches
    return []


def normalization_delta(rows):
    categories = Counter()
    transformation_in_every_minimal_set = Counter()
    raw_equal = fully_equal = unresolved = 0
    pairs_with_newline = 0
    nonremoved_sequence_mismatches = 0
    arabic_word_sequence_mismatches = 0
    arabic_base_letter_sequence_mismatches = 0

    for row in rows:
        left = row.get("our_text", "")
        right = row.get("mis_text", "")
        raw_equal += left == right
        fully_equal += normalize_narrow_identity(left) == normalize_narrow_identity(right)
        minimal_sets = minimal_equalizing_transform_sets(left, right)
        if not minimal_sets:
            unresolved += 1
            categories["NO_ALLOWED_TRANSFORM_SET_MAKES_EQUAL"] += 1
            continue

        labels = [
            "+".join(selected) if selected else "RAW_EQUAL"
            for selected in minimal_sets
        ]
        categories[" OR ".join(labels)] += 1
        required = set.intersection(*(set(selected) for selected in minimal_sets))
        transformation_in_every_minimal_set.update(required)
        if "WHITESPACE" in required and ("\n" in left or "\n" in right):
            pairs_with_newline += 1

        left_nonremoved = "".join(normalize_narrow_identity(left).split())
        right_nonremoved = "".join(normalize_narrow_identity(right).split())
        nonremoved_sequence_mismatches += left_nonremoved != right_nonremoved
        delta = deterministic_text_delta(left, right)
        arabic_word_sequence_mismatches += not delta["arabic_word_sequence_equal"]
        arabic_base_letter_sequence_mismatches += not delta[
            "arabic_base_letter_sequence_equal"
        ]

    return {
        "pairs": len(rows),
        "raw_equal": raw_equal,
        "fully_narrow_normalized_equal": fully_equal,
        "not_equal_under_allowed_transformations": unresolved,
        "minimal_transform_set_counts": dict(sorted(categories.items())),
        "pairs_where_transform_is_in_every_minimal_set": {
            name: transformation_in_every_minimal_set[name]
            for name in TRANSFORMATIONS
        },
        "whitespace_required_and_newline_present": pairs_with_newline,
        "pairs_with_nonremoved_character_sequence_mismatch": (
            nonremoved_sequence_mismatches
        ),
        "pairs_with_arabic_word_sequence_mismatch": (
            arabic_word_sequence_mismatches
        ),
        "pairs_with_arabic_base_letter_sequence_mismatch": (
            arabic_base_letter_sequence_mismatches
        ),
        "interpretation": (
            "Minimal sets are found exhaustively over the four allowed transforms. "
            "The normalizer substitutes no base letters and removes no words or "
            "punctuation."
        ),
    }


def _read_review(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_nonexact_review_rows(annotated_accepted):
    rows = []
    for number, row in enumerate(
        (row for row in annotated_accepted if not row["normalized_text_exact"]),
        start=1,
    ):
        rows.append({
            "review_id": f"NONEXACT-{number:03d}",
            "our_idInBook": row["our_idInBook"],
            "mis_HadithNo": row["mis_HadithNo"],
            "our_text": row["our_text"],
            "mis_text": row["mis_text"],
            "manual_verdict": "",
            "notes": "",
        })
    return rows


def ensure_nonexact_review(path, proposed_rows):
    if not path.exists():
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=NONEXACT_REVIEW_COLUMNS)
            writer.writeheader()
            writer.writerows(proposed_rows)
        return {"action": "created", "manual_labels_present": 0}

    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = tuple(reader.fieldnames or ())
        existing = list(reader)
    if columns != NONEXACT_REVIEW_COLUMNS:
        raise RuntimeError(f"Refusing to overwrite {path}: schema differs")
    labelled = sum(bool(row.get("manual_verdict", "").strip()) for row in existing)
    comparable = tuple(
        column
        for column in NONEXACT_REVIEW_COLUMNS
        if column not in {"manual_verdict", "notes"}
    )
    existing_pairs = [
        {column: str(row.get(column, "")) for column in comparable}
        for row in existing
    ]
    proposed_pairs = [
        {column: str(row.get(column, "")) for column in comparable}
        for row in proposed_rows
    ]
    if existing_pairs != proposed_pairs:
        raise RuntimeError(f"Refusing to overwrite {path}: pair set differs")
    return {"action": "preserved", "manual_labels_present": labelled}


def build_report(corpus, mis, accepted, review_rows, review_path):
    collision_summary, annotated, local_index, mis_index = (
        classify_accepted_collisions(corpus, mis, accepted)
    )
    exact_pairs = [row for row in annotated if row["normalized_text_exact"]]
    nonexact_neighborhoods = nonexact_structural_neighborhoods(
        annotated, len(mis)
    )
    non_exact = [
        {
            "our_idInBook": row["our_idInBook"],
            "mis_HadithNo": row["mis_HadithNo"],
            "local_position": row["local_position"],
            "mis_position": row["mis_position"],
            "local_normalized_text_sha256": _normalized_text_hash(
                row["local_normalized_text"]
            ),
            "mis_normalized_text_sha256": _normalized_text_hash(
                row["mis_normalized_text"]
            ),
            "deterministic_text_delta": deterministic_text_delta(
                row["our_text"], row["mis_text"]
            ),
            "deterministic_exception_adjudication": classify_nonexact_exception(
                row["our_text"], row["mis_text"]
            ),
            "structural_neighborhood": nonexact_neighborhoods[
                row["local_position"]
            ],
        }
        for row in annotated
        if not row["normalized_text_exact"]
    ]
    annotated_by_local_position = {
        row["local_position"]: row for row in annotated
    }
    exception_core_by_position = {}
    for detail in non_exact:
        source = annotated_by_local_position[detail["local_position"]]
        core = retained_text_after_exception(
            source["our_text"], source["mis_text"]
        )
        exception_core_by_position[detail["local_position"]] = core

    for detail in non_exact:
        source = annotated_by_local_position[detail["local_position"]]
        core = exception_core_by_position[detail["local_position"]]
        if core is None:
            detail["retained_core"] = {
                "available": False,
                "unique_unique": False,
            }
            continue

        local_effective_count = len(local_index.get(core, [])) + sum(
            other_core == core
            and annotated_by_local_position[other_position][
                "local_normalized_text"
            ] != core
            for other_position, other_core in exception_core_by_position.items()
        )
        mis_effective_count = len(mis_index.get(core, [])) + sum(
            other_core == core
            and annotated_by_local_position[other_position][
                "mis_normalized_text"
            ] != core
            for other_position, other_core in exception_core_by_position.items()
        )
        detail["retained_core"] = {
            "available": True,
            "sha256": _normalized_text_hash(core),
            "character_count": len(core),
            "effective_local_occurrences": local_effective_count,
            "effective_mis_occurrences": mis_effective_count,
            "unique_unique": local_effective_count == mis_effective_count == 1,
        }
    non_exact_summary = {
        "arabic_word_sequence_equal": sum(
            row["deterministic_text_delta"]["arabic_word_sequence_equal"]
            for row in non_exact
        ),
        "arabic_word_sequence_different": sum(
            not row["deterministic_text_delta"]["arabic_word_sequence_equal"]
            for row in non_exact
        ),
        "punctuation_or_spacing_only": sum(
            row["deterministic_text_delta"]["punctuation_or_spacing_only"]
            for row in non_exact
        ),
        "bracketed_by_unique_exact_neighbors": sum(
            row["structural_neighborhood"][
                "anchors_bracket_pair_in_unwrapped_order"
            ]
            for row in non_exact
        ),
        "identical_neighbor_gap_pattern_and_constant_offset": sum(
            row["structural_neighborhood"]["gap_pattern_identical"]
            and row["structural_neighborhood"][
                "constant_unwrapped_position_offset"
            ]
            for row in non_exact
        ),
        "deterministically_supported_exception_pairs": sum(
            row["deterministic_exception_adjudication"]["status"]
            == "DETERMINISTICALLY_SUPPORTED"
            for row in non_exact
        ),
        "unresolved_exception_pairs": sum(
            row["deterministic_exception_adjudication"]["status"]
            != "DETERMINISTICALLY_SUPPORTED"
            for row in non_exact
        ),
        "retained_exception_core_unique_unique_pairs": sum(
            row["retained_core"]["unique_unique"] for row in non_exact
        ),
        "retained_exception_core_collision_pairs": sum(
            not row["retained_core"]["unique_unique"] for row in non_exact
        ),
        "deterministic_exception_categories": dict(Counter(
            row["deterministic_exception_adjudication"]["category"]
            for row in non_exact
        )),
    }
    collision_groups = inspect_collision_groups(
        annotated, local_index, mis_index, len(mis)
    )
    unwrapped, rotations = unwrap_mis_positions(annotated, len(mis))

    return {
        "audit_type": (
            "Deterministic narrow-normalized textual and record-ambiguity audit"
        ),
        "inputs": {
            "local_corpus": {
                "records": len(corpus),
                "path": str(MUSLIM_JSON_PATH),
                "sha256": file_sha256(MUSLIM_JSON_PATH),
            },
            "mis_content": {
                "records": len(mis),
                "path": str(CONTENT),
                "sha256": file_sha256(CONTENT),
            },
            "review_sample": {
                "records": len(review_rows),
                "path": str(review_path),
                "sha256": sha256_file(review_path),
            },
        },
        "normalization": (
            "Exactly normalize_narrow_identity: Unicode NFC; remove Arabic-block "
            "Mn/Me combining marks and U+0640 tatweel; collapse whitespace; final "
            "NFC. No base-letter substitution or punctuation/word removal."
        ),
        "accepted_links": len(accepted),
        "full_corpus_normalized_text_cardinality": {
            "local": _index_cardinality(local_index),
            "mis": _index_cardinality(mis_index),
        },
        "collision_classification": collision_summary,
        "full_accepted_exact_identity": {
            "exact_normalized_pairs": len(exact_pairs),
            "non_exact_pairs": len(non_exact),
            "non_exact_summary": non_exact_summary,
            "non_exact_pair_details": non_exact,
        },
        "collision_groups_involved_in_accepted_links": {
            "total": len(collision_groups),
            "structurally_resolved": sum(
                row["classification"] == "STRUCTURALLY_RESOLVED"
                for row in collision_groups
            ),
            "ambiguous": sum(
                row["classification"] == "AMBIGUOUS"
                for row in collision_groups
            ),
            "groups": collision_groups,
        },
        "ordering_precision": {
            "raw": exact_rank_statistics(unwrapped, "mis_position"),
            "detected_collection_rotations": rotations,
            "rotation_unwrapped": exact_rank_statistics(
                unwrapped, "unwrapped_mis_position"
            ),
            "rotation_unwrapped_inversion_pairs": enumerate_inversion_pairs(
                unwrapped, "unwrapped_mis_position"
            ),
            "ordering_used_to_change_links": False,
        },
        "sample_normalization_delta": normalization_delta(review_rows),
        "limitations": [
            "Textual identity alone cannot distinguish duplicate occurrences.",
            "Structural evidence is audited only for duplicate normalized-text "
            "groups involved in accepted links.",
            "This audit does not establish narrator identity and creates no graph.",
        ],
    }


def main():
    corpus = load_corpus()
    _, mis = read_sheet(CONTENT)
    accepted = [
        row for row in build_tail_pairs(corpus, mis)
        if row["accepted"]
    ]
    review_path = CLEAN_REVIEW_CSV if CLEAN_REVIEW_CSV.exists() else REVIEW_CSV
    review_rows = _read_review(review_path)
    report = build_report(corpus, mis, accepted, review_rows, review_path)

    _, annotated, _, _ = classify_accepted_collisions(corpus, mis, accepted)
    proposed_nonexact_review = build_nonexact_review_rows(annotated)
    review_status = ensure_nonexact_review(
        NONEXACT_REVIEW_PATH, proposed_nonexact_review
    )
    report["targeted_nonexact_review"] = {
        "purpose": (
            "Complete census review of accepted pairs that are not equal under "
            "the narrow normalization; no scores or hidden metadata exposed."
        ),
        "path": str(NONEXACT_REVIEW_PATH),
        "rows": len(proposed_nonexact_review),
        "sha256": sha256_file(NONEXACT_REVIEW_PATH),
        "manual_labels_present": review_status["manual_labels_present"],
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print("Linkage ambiguity audit")
    print(f"Accepted links             : {report['accepted_links']}")
    for category, values in report["collision_classification"].items():
        print(
            f"{category:<26}: {values['count']} "
            f"({values['percentage']:.6f}%)"
        )
    identity = report["full_accepted_exact_identity"]
    print(f"Exact narrow-normalized    : {identity['exact_normalized_pairs']}")
    print(f"Non-exact                  : {identity['non_exact_pairs']}")
    groups = report["collision_groups_involved_in_accepted_links"]
    print(f"Collision groups involved  : {groups['total']}")
    print(f"Ambiguous collision groups : {groups['ambiguous']}")
    order = report["ordering_precision"]["rotation_unwrapped"]
    print(f"Unwrapped Spearman         : {order['spearman_decimal']}")
    print(f"Unwrapped Kendall tau      : {order['kendall_tau_decimal']}")
    print(f"Unwrapped inversions       : {order['inversion_count']}")
    print(
        "Targeted non-exact review  : "
        f"{report['targeted_nonexact_review']['rows']} rows "
        f"({review_status['action']})"
    )
    print(f"Report                     : {REPORT_PATH}")


if __name__ == "__main__":
    main()
