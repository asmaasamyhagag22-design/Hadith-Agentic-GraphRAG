"""
Profile Multi-IsnadSet and measure the Sahih Muslim <-> MIS linkage gate.

This module does not construct a graph.  It measures three separate claims:

* whether numeric equality is a valid join (it is tested, never assumed),
* how much of the local corpus receives a unique text-derived candidate, and
* whether accepted pairs have defensible global cardinality and ordering.

Candidate generation and similarity both use hadith text, so the acceptance
criterion is automated textual corroboration, not independent ground truth.
"""

import difflib
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import MIS_DIR, MUSLIM_JSON_PATH, PROCESSED_DIR
from utils import split_isnad_matn, strip_diacritics

CONTENT = MIS_DIR / "1_Hadith_SahihMuslim_HadithContent.xlsx"
NODES = MIS_DIR / "2_Hadith_SahihMuslim_Narrators_Nodes_for_Graph.xlsx"
EDGES = MIS_DIR / "3_Hadith_SahihMuslim_Isnad_Edges_for_Graph.xlsx"

REPORT_PATH = PROCESSED_DIR / "mis_linkage.json"
LINKS_PATH = PROCESSED_DIR / "mis_linkage_pairs.jsonl"

_ALEF = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه",
})
_NON_ARABIC = re.compile(r"[^ء-ي]+")
_ORDER_LABEL = re.compile(r"-H(?P<hadith>\d+)-.*-S(?P<sanad>\d+)-i(?P<order>\d+)$")

FINGERPRINT_WORDS = 10
ACCEPTANCE_SIMILARITY = 0.90


def normalize(text):
    text = strip_diacritics(str(text or "")).translate(_ALEF)
    return " ".join(_NON_ARABIC.sub(" ", text).split())


def normalize_identifier(value):
    """Canonical string form that safely merges Excel int/str identifiers."""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            return str(int(value))
    text = str(value).strip()
    return text or None


def fingerprint(text):
    return " ".join(normalize(text).split()[:FINGERPRINT_WORDS])


def head_signature(text):
    return fingerprint(text)


def matn_signature(text):
    return fingerprint(split_isnad_matn(str(text or "")))


def tail_signature(text):
    words = normalize(text).split()
    return " ".join(words[-FINGERPRINT_WORDS:])


def similarity(ours, theirs):
    """Order-sensitive full SequenceMatcher ratio over normalized words."""

    return round(
        difflib.SequenceMatcher(
            None,
            normalize(ours).split(),
            normalize(theirs).split(),
            autojunk=False,
        ).ratio(),
        6,
    )


def quick_similarity(ours, theirs):
    """Historical upper bound, retained only to quantify the old-score bias."""

    return round(
        difflib.SequenceMatcher(
            None,
            normalize(ours).split(),
            normalize(theirs).split(),
            autojunk=False,
        ).quick_ratio(),
        6,
    )


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_sheet(path):
    """Return (columns, rows) after fully parsing the workbook's active sheet."""
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)

    try:
        raw_columns = next(rows)
    except StopIteration as error:
        workbook.close()
        raise ValueError(f"Empty workbook: {path}") from error

    columns = [str(column) for column in raw_columns]
    if len(columns) != len(set(columns)):
        workbook.close()
        raise ValueError(f"Duplicate columns in {path}: {columns}")

    records = [dict(zip(columns, row)) for row in rows]
    workbook.close()
    return columns, records


def load_corpus():
    with open(MUSLIM_JSON_PATH, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data["hadiths"]


def numeric_linkage(corpus, mis):
    """Test idInBook == HadithNo and corroborate every numeric pair by text."""

    by_number = defaultdict(list)
    for record in mis:
        by_number[normalize_identifier(record.get("HadithNo"))].append(record)

    present = agree = disagree = ambiguous_number = 0

    for hadith in corpus:
        candidates = by_number.get(normalize_identifier(hadith.get("idInBook")), [])
        if not candidates:
            continue
        present += 1
        if len(candidates) != 1:
            ambiguous_number += 1
            continue

        ours = fingerprint(hadith.get("arabic"))
        theirs = fingerprint(candidates[0].get("HadithText_GhairMushakkal"))
        if ours and ours == theirs:
            agree += 1
        else:
            disagree += 1

    return {
        "corpus_records": len(corpus),
        "mis_records": len(mis),
        "number_present_in_mis": present,
        "ambiguous_duplicate_mis_numbers": ambiguous_number,
        "text_agrees_at_same_number": agree,
        "text_disagrees_at_same_number": disagree,
        "agreement_rate_over_corpus": round(agree / max(len(corpus), 1), 6),
        "decision": "REJECT numeric equality as a join",
    }


def link_by(corpus, mis, signature, label):
    index = defaultdict(list)
    for record in mis:
        key = signature(record.get("HadithText_GhairMushakkal"))
        if key:
            index[key].append(record)

    unique = ambiguous = unmatched = 0
    offsets = Counter()

    for hadith in corpus:
        candidates = index.get(signature(hadith.get("arabic")), [])
        if not candidates:
            unmatched += 1
        elif len(candidates) == 1:
            unique += 1
            mis_id = candidates[0].get("HadithNo")
            local_id = hadith.get("idInBook")
            if isinstance(mis_id, int) and isinstance(local_id, int):
                offsets[mis_id - local_id] += 1
        else:
            ambiguous += 1

    return {
        "strategy": label,
        "unique_match": unique,
        "ambiguous_match": ambiguous,
        "unmatched": unmatched,
        "unique_match_rate": round(unique / max(len(corpus), 1), 6),
        "mis_signatures": len(index),
        "mis_colliding_signatures": sum(1 for value in index.values() if len(value) > 1),
        "distinct_number_offsets": len(offsets),
    }


def text_linkage(corpus, mis):
    return [
        link_by(corpus, mis, head_signature, "head of raw text (diagnostic)"),
        link_by(corpus, mis, matn_signature, "head of extracted matn"),
        link_by(corpus, mis, tail_signature, "tail of raw text"),
    ]


def build_tail_pairs(corpus, mis, threshold=ACCEPTANCE_SIMILARITY):
    """Build one row per local record without enforcing global 1:1 mapping."""

    index = defaultdict(list)
    for mis_position, record in enumerate(mis, start=1):
        key = tail_signature(record.get("HadithText_GhairMushakkal"))
        if key:
            index[key].append((mis_position, record))

    pairs = []
    for local_position, hadith in enumerate(corpus, start=1):
        key = tail_signature(hadith.get("arabic"))
        candidates = index.get(key, [])

        row = {
            "local_position": local_position,
            "our_idInBook": hadith.get("idInBook"),
            "our_chapterId": hadith.get("chapterId"),
            "tail_signature": key,
            "candidate_count": len(candidates),
            "candidate_status": (
                "unmatched" if not candidates
                else "ambiguous" if len(candidates) > 1
                else "unique"
            ),
            "accepted": False,
            "similarity": None,
            "quick_similarity": None,
            "mis_position": None,
            "mis_HadithNo": None,
            "mis_ChapterNo": None,
            "our_text": hadith.get("arabic", ""),
            "mis_text": "",
        }

        if len(candidates) == 1:
            mis_position, record = candidates[0]
            score = similarity(row["our_text"], record.get("HadithText_GhairMushakkal"))
            quick_score = quick_similarity(
                row["our_text"], record.get("HadithText_GhairMushakkal")
            )
            row.update({
                "similarity": score,
                "quick_similarity": quick_score,
                "mis_position": mis_position,
                "mis_HadithNo": record.get("HadithNo"),
                "mis_ChapterNo": record.get("ChapterNo"),
                "mis_text": record.get("HadithText_GhairMushakkal") or "",
                "accepted": score >= threshold,
            })

        pairs.append(row)

    return pairs


def _rankdata(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average = (start + 1 + end) / 2
        for index in order[start:end]:
            ranks[index] = average
        start = end
    return ranks


def _pearson(left, right):
    if len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_ss = sum((x - left_mean) ** 2 for x in left)
    right_ss = sum((y - right_mean) ** 2 for y in right)
    denominator = math.sqrt(left_ss * right_ss)
    return numerator / denominator if denominator else None


def _inversion_count(values):
    """Count strict inversions in O(n log n); equal positions are ties."""

    def merge_count(items):
        if len(items) < 2:
            return items, 0
        middle = len(items) // 2
        left, left_count = merge_count(items[:middle])
        right, right_count = merge_count(items[middle:])
        merged = []
        i = j = count = 0
        while i < len(left) and j < len(right):
            if left[i] <= right[j]:
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                j += 1
                count += len(left) - i
        merged.extend(left[i:])
        merged.extend(right[j:])
        return merged, left_count + right_count + count

    return merge_count(list(values))[1]


def _percentile(values, probability):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def _rank_order_statistics(local_positions, mis_positions):
    spearman = _pearson(_rankdata(local_positions), _rankdata(mis_positions))
    inversions = _inversion_count(mis_positions)
    total_pairs = len(mis_positions) * (len(mis_positions) - 1) // 2
    tie_pairs = sum(
        count * (count - 1) // 2
        for count in Counter(mis_positions).values()
    )
    comparable = total_pairs - tie_pairs
    concordant = comparable - inversions
    denominator = math.sqrt(total_pairs * comparable) if comparable else 0
    kendall_tau_b = ((concordant - inversions) / denominator) if denominator else None
    return {
        "spearman_rank_correlation": spearman,
        "kendall_tau_b": kendall_tau_b,
        "inversion_count": inversions,
        "inversion_rate_excluding_ties": inversions / comparable if comparable else None,
        "tied_mis_position_pairs": tie_pairs,
    }


def ordering_diagnostics(accepted, mis_size):
    ordered = sorted(accepted, key=lambda row: row["local_position"])
    local_positions = [row["local_position"] for row in ordered]
    mis_positions = [row["mis_position"] for row in ordered]

    jumps = [right - left for left, right in zip(mis_positions, mis_positions[1:])]
    absolute_jumps = [abs(value) for value in jumps]

    # A single collection-level rotation is a common edition-layout effect:
    # one edition can put the introduction first and another last.  Measure
    # it, but never use it to create or overwrite a text link.
    unwrapped = []
    added = 0
    wraps = []
    previous = None
    for row, position in zip(ordered, mis_positions):
        if previous is not None and position - previous < -(mis_size / 2):
            added += mis_size
            wraps.append({
                "before_our_idInBook": ordered[len(unwrapped) - 1]["our_idInBook"],
                "before_mis_HadithNo": ordered[len(unwrapped) - 1]["mis_HadithNo"],
                "after_our_idInBook": row["our_idInBook"],
                "after_mis_HadithNo": row["mis_HadithNo"],
                "raw_jump": position - previous,
            })
        unwrapped.append(position + added)
        previous = position

    return {
        "pairs": len(ordered),
        "raw_order": _rank_order_statistics(local_positions, mis_positions),
        "detected_collection_rotations": wraps,
        "rotation_unwrapped_order": _rank_order_statistics(local_positions, unwrapped),
        "backward_adjacent_jumps": sum(1 for jump in jumps if jump < 0),
        "absolute_adjacent_jump": {
            "median": _percentile(absolute_jumps, 0.50),
            "p90": _percentile(absolute_jumps, 0.90),
            "p99": _percentile(absolute_jumps, 0.99),
            "max": max(absolute_jumps) if absolute_jumps else None,
            "over_25": sum(1 for value in absolute_jumps if value > 25),
            "over_100": sum(1 for value in absolute_jumps if value > 100),
        },
        "interpretation": (
            "Raw ordering includes collection-level rotations. The unwrapped "
            "diagnostic measures those rotations but does not change accepted pairs."
        ),
    }


def mapping_integrity(pairs, corpus_size, mis_size):
    accepted = [row for row in pairs if row["accepted"]]
    local_counts = Counter(row["local_position"] for row in accepted)
    mis_counts = Counter(row["mis_position"] for row in accepted)
    pair_counts = Counter(
        (row["local_position"], row["mis_position"])
        for row in accepted
    )

    one_to_many = {key: count for key, count in local_counts.items() if count > 1}
    many_to_one = {key: count for key, count in mis_counts.items() if count > 1}

    quick_accepted = [
        row for row in pairs
        if row["candidate_status"] == "unique"
        and row["quick_similarity"] >= ACCEPTANCE_SIMILARITY
    ]

    return {
        "acceptance_rule": (
            f"unique {FINGERPRINT_WORDS}-word normalized tail candidate and "
            f"order-sensitive full-text SequenceMatcher ratio >= {ACCEPTANCE_SIMILARITY:.2f}"
        ),
        "accepted_pairs": len(accepted),
        "accepted_coverage_of_local_corpus": round(len(local_counts) / corpus_size, 6),
        "one_to_one_mappings": sum(
            1 for row in accepted
            if local_counts[row["local_position"]] == 1
            and mis_counts[row["mis_position"]] == 1
        ),
        "one_to_many_local_records": len(one_to_many),
        "one_to_many_pairs_involved": sum(one_to_many.values()),
        "many_to_one_mis_records": len(many_to_one),
        "many_to_one_pairs_involved": sum(many_to_one.values()),
        "duplicate_accepted_pairs": sum(count - 1 for count in pair_counts.values()),
        "local_unmatched_under_acceptance_rule": corpus_size - len(local_counts),
        "mis_unmatched_under_acceptance_rule": mis_size - len(mis_counts),
        "historical_quick_ratio_comparison": {
            "quick_ratio_accepted_pairs": len(quick_accepted),
            "true_ratio_accepted_pairs": len(accepted),
            "quick_ratio_only_pairs": sum(
                1 for row in quick_accepted if not row["accepted"]
            ),
            "finding": (
                "quick_ratio is an upper bound and was not a valid acceptance score; "
                "the true ratio is now used"
            ),
        },
        "ordering": ordering_diagnostics(accepted, mis_size),
    }


def _identifier_profile(values):
    normalized = [normalize_identifier(value) for value in values]
    raw_by_normalized = defaultdict(set)
    for raw, canonical in zip(values, normalized):
        if canonical is not None:
            raw_by_normalized[canonical].add(f"{type(raw).__name__}:{raw!r}")
    return {
        "raw_python_types": dict(Counter(type(value).__name__ for value in values)),
        "null_after_normalization": sum(value is None for value in normalized),
        "unique_normalized": len({value for value in normalized if value is not None}),
        "normalized_ids_with_mixed_raw_representations": sum(
            len(raw_values) > 1 for raw_values in raw_by_normalized.values()
        ),
    }


def profile_nodes(records):
    ids = [record.get("NarratorID_Mapped") for record in records]
    canonical = [normalize_identifier(value) for value in ids]
    id_counts = Counter(value for value in canonical if value is not None)
    generations = Counter(record.get("NarratorGeneration") for record in records)
    return {
        "records": len(records),
        "identifier_profile": _identifier_profile(ids),
        "duplicate_normalized_ids": sum(count > 1 for count in id_counts.values()),
        "unique_arabic_names": len({normalize(record.get("NarratorNameAr")) for record in records}),
        "generations": dict(generations.most_common()),
        "gender": dict(Counter(record.get("Gender") for record in records)),
    }


def profile_edges(records, nodes, content):
    node_ids = {
        normalize_identifier(record.get("NarratorID_Mapped"))
        for record in nodes
    } - {None}
    content_ids = {
        normalize_identifier(record.get("HadithNo"))
        for record in content
    } - {None}

    source_values = [record.get("sourceNarratorID") for record in records]
    target_values = [record.get("targetNarratorID") for record in records]
    edge_hadith_ids = [normalize_identifier(record.get("HadithNo")) for record in records]

    chains = defaultdict(list)
    labels = []
    label_parse_failures = label_hadith_mismatches = label_sanad_mismatches = 0

    for record in records:
        hadith = normalize_identifier(record.get("HadithNo"))
        sanad = normalize_identifier(record.get("SanadNo"))
        label = str(record.get("intractionLabel") or "")
        labels.append(label)
        match = _ORDER_LABEL.search(label)
        if not match:
            label_parse_failures += 1
            continue
        if normalize_identifier(int(match.group("hadith"))) != hadith:
            label_hadith_mismatches += 1
        if normalize_identifier(int(match.group("sanad"))) != sanad:
            label_sanad_mismatches += 1
        chains[(hadith, sanad)].append(int(match.group("order")))

    non_contiguous = duplicate_orders = 0
    for orders in chains.values():
        unique = sorted(set(orders))
        if len(unique) != len(orders):
            duplicate_orders += 1
        if unique != list(range(1, max(unique, default=0) + 1)):
            non_contiguous += 1

    sanad_sets = defaultdict(set)
    for record in records:
        sanad_sets[normalize_identifier(record.get("HadithNo"))].add(
            normalize_identifier(record.get("SanadNo"))
        )

    declared_sanads = {
        normalize_identifier(record.get("HadithNo")): record.get("SanadCount")
        for record in content
    }
    declared_mismatches = sum(
        declared_sanads.get(hadith) != len({value for value in sanads if value is not None})
        for hadith, sanads in sanad_sets.items()
    )

    source_ids = {normalize_identifier(value) for value in source_values} - {None}
    target_ids = {normalize_identifier(value) for value in target_values} - {None}
    edge_hadith_set = set(edge_hadith_ids) - {None}

    return {
        "records": len(records),
        "hadiths_covered": len(edge_hadith_set),
        "source_identifier_profile": _identifier_profile(source_values),
        "target_identifier_profile": _identifier_profile(target_values),
        "source_ids_missing_from_nodes": len(source_ids - node_ids),
        "target_ids_missing_from_nodes": len(target_ids - node_ids),
        "edge_hadith_ids_missing_from_content": len(edge_hadith_set - content_ids),
        "content_hadith_ids_without_edges": len(content_ids - edge_hadith_set),
        "order_labels": {
            "parsed": len(records) - label_parse_failures,
            "parse_failures": label_parse_failures,
            "duplicate_labels": sum(count - 1 for count in Counter(labels).values() if count > 1),
            "hadith_mismatches": label_hadith_mismatches,
            "sanad_mismatches": label_sanad_mismatches,
            "chains_with_duplicate_order": duplicate_orders,
            "chains_with_non_contiguous_order": non_contiguous,
        },
        "distinct_chains": len(chains),
        "max_sanads_for_one_hadith": max((len(values) for values in sanad_sets.values()), default=0),
        "hadiths_with_multiple_sanads": sum(len(values) > 1 for values in sanad_sets.values()),
        "content_sanad_count_mismatches": declared_mismatches,
    }


def _public_pair(row):
    return {
        key: value
        for key, value in row.items()
        if key not in {"our_text", "mis_text"}
    }


def main():
    corpus = load_corpus()
    content_columns, content = read_sheet(CONTENT)
    node_columns, nodes = read_sheet(NODES)
    edge_columns, edges = read_sheet(EDGES)

    pairs = build_tail_pairs(corpus, content)
    accepted = [row for row in pairs if row["accepted"]]

    report = {
        "inputs": {
            "muslim": {"path": str(MUSLIM_JSON_PATH), "sha256": file_sha256(MUSLIM_JSON_PATH)},
            "mis_content": {"path": str(CONTENT), "sha256": file_sha256(CONTENT)},
            "mis_nodes": {"path": str(NODES), "sha256": file_sha256(NODES)},
            "mis_edges": {"path": str(EDGES), "sha256": file_sha256(EDGES)},
        },
        "schemas": {
            "content": content_columns,
            "nodes": node_columns,
            "edges": edge_columns,
        },
        "numeric_linkage": numeric_linkage(corpus, content),
        "text_candidate_generation": text_linkage(corpus, content),
        "tail_candidate_status": dict(Counter(row["candidate_status"] for row in pairs)),
        "mapping_integrity": mapping_integrity(pairs, len(corpus), len(content)),
        "narrator_nodes": profile_nodes(nodes),
        "isnad_edges": profile_edges(edges, nodes, content),
        "limitations": [
            "Tail candidate generation and full-text similarity are correlated textual evidence.",
            "Occurrence-level textual collisions and non-exact accepted pairs are audited separately by audit_linkage_ambiguity.",
            "Ordering diagnostics corroborate but never overwrite text-derived pairs.",
        ],
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    with open(LINKS_PATH, "w", encoding="utf-8", newline="\n") as handle:
        for row in accepted:
            handle.write(json.dumps(_public_pair(row), ensure_ascii=False) + "\n")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nAccepted pairs -> {LINKS_PATH} ({len(accepted)} rows)")
    print(f"Report         -> {REPORT_PATH}")


if __name__ == "__main__":
    main()
