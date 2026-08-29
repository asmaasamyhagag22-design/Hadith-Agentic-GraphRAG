"""Diagnose the MIS -> Itqan unmatched-name gap without resolving identities.

The Phase 2 deterministic tiers are immutable inputs here.  Broader
normalization, token containment, character n-grams, token overlap, edit
similarity, and relationship checks are diagnostic evidence only.
"""

import csv
import difflib
import hashlib
import itertools
import json
import math
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_linkage_validation_identity import normalize_narrow_identity
from build_narrator_candidates import NORMALIZER_VERSION, _id_sort
from config import PROCESSED_DIR
from profile_itqan import (
    ITQAN_DIR,
    PROFILE_FILES,
    canonical_id,
    file_sha256,
    load_profiles,
)
from profile_mis import EDGES, NODES, normalize_identifier, read_sheet


MILESTONE_VERSION = "narrator_unmatched_diagnostic_v1"
CENSUS_SEED = 2026081603
UNMATCHED_SAMPLE_SEED = 2026081604
TOP_N = 3
MIN_SUBSET_TOKENS = 2

BASE_AUDIT = PROCESSED_DIR / "narrator_candidate_audit.json"
BASE_CANDIDATES = PROCESSED_DIR / "narrator_resolution_candidates.jsonl"
FROZEN_REVIEW_117 = PROCESSED_DIR / "narrator_resolution_review.csv"

AUDIT_PATH = PROCESSED_DIR / "narrator_unmatched_audit.json"
PROFILE_PATH = PROCESSED_DIR / "narrator_unmatched_profiles.csv"
ABLATION_PATH = PROCESSED_DIR / "narrator_unmatched_normalization_ablation.csv"
DIAGNOSTIC_CANDIDATES_PATH = (
    PROCESSED_DIR / "narrator_unmatched_diagnostic_candidates.jsonl"
)

CENSUS_REVIEW_PATH = PROCESSED_DIR / "narrator_auto_resolved_census_review.csv"
CENSUS_HIDDEN_PATH = (
    PROCESSED_DIR / "narrator_auto_resolved_census_review_hidden.csv"
)
CENSUS_META_PATH = (
    PROCESSED_DIR / "narrator_auto_resolved_census_review_meta.json"
)

UNMATCHED_REVIEW_PATH = (
    PROCESSED_DIR / "narrator_unmatched_diagnostic_review.csv"
)
UNMATCHED_HIDDEN_PATH = (
    PROCESSED_DIR / "narrator_unmatched_diagnostic_review_hidden.csv"
)
UNMATCHED_META_PATH = (
    PROCESSED_DIR / "narrator_unmatched_diagnostic_review_meta.json"
)

AUTO_TIERS = {"EXACT_RESOLVED", "ALIAS_RESOLVED"}
ALLOWED_CENSUS_VERDICTS = (
    "correct", "wrong", "uncertain", "NEEDS_DOMAIN_EXPERT",
)
ALLOWED_DIAGNOSTIC_VERDICTS = (
    "same_person", "different_person", "plausible_but_uncertain",
    "no_candidate", "NEEDS_DOMAIN_EXPERT",
)

CENSUS_VISIBLE_COLUMNS = (
    "review_id", "mis_narrator_id", "mis_name", "itqan_profile_evidence_json",
    "reviewer_selected_itqan_id", "manual_verdict", "notes",
)
CENSUS_HIDDEN_COLUMNS = (
    "review_id", "mis_narrator_id", "provisional_tier",
    "provisional_resolved_itqan_id", "candidate_sources_json",
    "automatic_confidence",
)
UNMATCHED_VISIBLE_COLUMNS = (
    "review_id", "mis_narrator_id", "mis_name", "mis_short_name",
    "diagnostic_candidate_evidence_json", "reviewer_selected_itqan_id",
    "diagnostic_verdict", "notes",
)
UNMATCHED_HIDDEN_COLUMNS = (
    "review_id", "mis_narrator_id", "diagnostic_stratum",
    "diagnostic_methods_and_scores_json", "name_features_json",
    "token_diagnostics_json", "ablation_candidates_json",
)
PROFILE_COLUMNS = (
    "mis_narrator_id", "raw_name", "normalized_name", "short_name",
    "short_name_normalized", "short_name_candidate_profiles", "character_length",
    "token_count", "first_token", "last_token", "has_diacritics",
    "has_tatweel", "has_alif_variants", "has_ya", "has_alif_maqsura",
    "has_ta_marbuta", "has_ha", "has_hamza_forms", "has_bin",
    "has_ibn", "has_kunya_form", "has_structural_nisba_ending",
    "has_punctuation", "has_brackets", "has_digits", "has_latin",
    "has_other_script_letters", "has_repeated_whitespace",
    "has_unusual_unicode", "ablation_candidate_profiles",
    "mis_token_subset_profiles", "itqan_token_subset_profiles",
    "mis_ordered_subsequence_profiles", "itqan_ordered_subsequence_profiles",
    "same_first_token_profiles", "same_last_token_profiles",
    "diagnostic_candidate_profiles", "diagnostic_stratum",
    "top_character_candidate_length_direction", "relationship_supported_candidates",
)
ABLATION_COLUMNS = (
    "transformation", "population", "candidate_coverage", "unique_candidates",
    "ambiguous_candidates", "largest_collision", "incremental_vs_baseline",
    "previous_unique_to_ambiguous", "previous_unique_to_different_unique",
    "global_collision_keys", "global_profiles_in_collisions",
    "global_largest_collision", "new_global_collision_keys",
    "new_global_profiles_in_collisions", "used_for_resolution",
)

ARABIC_BLOCKS = (
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x0870, 0x089F),
    (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF),
)
ALIF_VARIANTS = set("أإآٱ")
HAMZA_FORMS = set("ءأإآؤئ")
KUNYA_TOKENS = {"أبو", "أبي", "ابو", "ابي"}
BRACKETS = set("()[]{}<>﴾﴿（）［］【】")
RELATIVE_ALIAS_FORMS = {
    "أبيه", "جده", "عمه", "أخيه", "مولاه", "أمه", "جدته", "خاله",
}
REPEATED_WHITESPACE = re.compile(r"\s{2,}")
STRUCTURAL_NISBA = re.compile(r"^ال.+(?:ي|ى|ية)$")

TRANSFORMATIONS = {
    "BASELINE_NARROW_CONTROL": (),
    "WHITESPACE_ALREADY_IN_BASELINE_CONTROL": (),
    "ALIF_VARIANTS_TO_BARE": ("alif",),
    "YA_MAQSURA_TO_YA": ("ya",),
    "TA_MARBUTA_TO_HA": ("ta",),
    "HAMZA_CARRIERS_TO_HAMZA": ("hamza",),
    "BIN_IBN_TO_BIN": ("bin",),
    "PUNCTUATION_REMOVAL": ("punctuation",),
    "ALIF_PLUS_YA": ("alif", "ya"),
    "ALIF_PLUS_BIN": ("alif", "bin"),
    "YA_PLUS_BIN": ("ya", "bin"),
    "ALIF_PLUS_YA_PLUS_BIN": ("alif", "ya", "bin"),
    "ALIF_PLUS_YA_PLUS_BIN_PLUS_PUNCTUATION": (
        "alif", "ya", "bin", "punctuation",
    ),
}


def json_compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def write_csv(path, columns, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def is_arabic_block(character):
    codepoint = ord(character)
    return any(start <= codepoint <= end for start, end in ARABIC_BLOCKS)


def is_arabic_combining(character):
    return is_arabic_block(character) and unicodedata.category(character) in {"Mn", "Me"}


def raw_name_features(name):
    raw = str(name or "")
    normalized = normalize_narrow_identity(raw)
    tokens = normalized.split()
    last = tokens[-1] if tokens else ""
    punctuation = [ch for ch in raw if unicodedata.category(ch).startswith("P")]
    letters = [ch for ch in raw if unicodedata.category(ch).startswith("L")]
    other_script_letters = [ch for ch in letters if not is_arabic_block(ch)]
    allowed = []
    for character in raw:
        category = unicodedata.category(character)
        if (
            is_arabic_block(character)
            or character.isspace()
            or category.startswith("P")
            or category.startswith("N")
        ):
            continue
        allowed.append(character)
    return {
        "raw_name": raw,
        "normalized_name": normalized,
        "character_length": len(raw),
        "normalized_character_length": len(normalized),
        "token_count": len(tokens),
        "tokens": tokens,
        "first_token": tokens[0] if tokens else "",
        "last_token": last,
        "has_diacritics": any(is_arabic_combining(ch) for ch in raw),
        "has_tatweel": "ـ" in raw,
        "has_alif_variants": any(ch in ALIF_VARIANTS for ch in raw),
        "has_ya": "ي" in raw,
        "has_alif_maqsura": "ى" in raw,
        "has_ta_marbuta": "ة" in raw,
        "has_ha": "ه" in raw,
        "has_hamza_forms": any(ch in HAMZA_FORMS for ch in raw),
        "has_bin": "بن" in tokens,
        "has_ibn": "ابن" in tokens,
        "has_kunya_form": any(token in KUNYA_TOKENS for token in tokens),
        "has_structural_nisba_ending": bool(STRUCTURAL_NISBA.fullmatch(last)),
        "has_punctuation": bool(punctuation),
        "has_brackets": any(ch in BRACKETS for ch in raw),
        "has_digits": any(ch.isdigit() for ch in raw),
        "has_latin": any("LATIN" in unicodedata.name(ch, "") for ch in raw),
        "has_other_script_letters": bool(other_script_letters),
        "has_repeated_whitespace": bool(REPEATED_WHITESPACE.search(raw)),
        "has_unusual_unicode": bool(allowed),
        "unusual_codepoints": [
            {
                "character": ch,
                "codepoint": f"U+{ord(ch):04X}",
                "name": unicodedata.name(ch, "UNNAMED"),
                "category": unicodedata.category(ch),
            }
            for ch in sorted(set(allowed), key=ord)
        ],
    }


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def numeric_distribution(values):
    return {
        "minimum": min(values) if values else None,
        "p25": percentile(values, 0.25),
        "median": percentile(values, 0.5),
        "mean": sum(values) / len(values) if values else None,
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.9),
        "maximum": max(values) if values else None,
    }


def candidate_cardinality_distribution(values):
    buckets = Counter()
    for value in values:
        if value == 0:
            buckets["0"] += 1
        elif value == 1:
            buckets["1"] += 1
        elif value == 2:
            buckets["2"] += 1
        elif value <= 5:
            buckets["3-5"] += 1
        elif value <= 20:
            buckets["6-20"] += 1
        else:
            buckets[">20"] += 1
    positive = sorted(value for value in values if value > 0)
    return {
        "distribution": {
            key: buckets[key] for key in ("0", "1", "2", "3-5", "6-20", ">20")
        },
        "largest_candidate_group": max(values, default=0),
        "median_among_positive": percentile(positive, 0.5),
    }


def describe_names(names):
    features = [raw_name_features(name) for name in names]
    boolean_fields = [
        key for key in features[0]
        if key.startswith("has_")
    ] if features else []
    inventory = Counter("".join(str(name or "") for name in names))
    unusual = Counter()
    for feature in features:
        for entry in feature["unusual_codepoints"]:
            unusual[(entry["codepoint"], entry["character"], entry["name"], entry["category"])] += 1
    first = Counter(feature["first_token"] for feature in features if feature["first_token"])
    last = Counter(feature["last_token"] for feature in features if feature["last_token"])
    return {
        "population": len(features),
        "character_length": numeric_distribution(
            [feature["character_length"] for feature in features]
        ),
        "token_count": numeric_distribution(
            [feature["token_count"] for feature in features]
        ),
        "structural_features": {
            key: {
                "count": sum(feature[key] for feature in features),
                "rate": (
                    sum(feature[key] for feature in features) / len(features)
                    if features else None
                ),
            }
            for key in boolean_fields
        },
        "common_prefix_tokens": [
            {"token": token, "count": count} for token, count in first.most_common(20)
        ],
        "common_suffix_tokens": [
            {"token": token, "count": count} for token, count in last.most_common(20)
        ],
        "unicode_inventory_size": len(inventory),
        "unicode_inventory": [
            {
                "character": character,
                "codepoint": f"U+{ord(character):04X}",
                "name": unicodedata.name(character, "UNNAMED"),
                "category": unicodedata.category(character),
                "count": count,
            }
            for character, count in sorted(
                inventory.items(), key=lambda item: (-item[1], ord(item[0]))
            )
        ],
        "unusual_unicode_occurrences": [
            {
                "codepoint": key[0], "character": key[1], "name": key[2],
                "category": key[3], "record_occurrences": count,
            }
            for key, count in sorted(unusual.items())
        ],
    }


def apply_transform(name, operations):
    value = normalize_narrow_identity(name)
    for operation in operations:
        if operation == "alif":
            value = value.translate(str.maketrans({
                "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
            }))
        elif operation == "ya":
            value = value.replace("ى", "ي")
        elif operation == "ta":
            value = value.replace("ة", "ه")
        elif operation == "hamza":
            value = value.translate(str.maketrans({
                "أ": "ء", "إ": "ء", "آ": "ء", "ؤ": "ء", "ئ": "ء",
            }))
        elif operation == "bin":
            value = " ".join("بن" if token == "ابن" else token for token in value.split())
        elif operation == "punctuation":
            value = "".join(
                " " if unicodedata.category(ch).startswith("P") else ch
                for ch in value
            )
            value = " ".join(value.split())
        else:
            raise ValueError(f"Unknown transformation operation: {operation}")
    return value


def build_representations(profiles):
    representations = []
    by_profile = defaultdict(list)
    for profile in profiles:
        profile_id = canonical_id(profile.get("id"))
        names = [("canonical", profile.get("full_name"))]
        aliases = profile.get("namings")
        if isinstance(aliases, list):
            names.extend(("alias", value) for value in aliases)
        seen = set()
        for source, raw in names:
            raw = str(raw or "")
            normalized = normalize_narrow_identity(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            representation = {
                "profile_id": profile_id,
                "raw": raw,
                "normalized": normalized,
                "tokens": tuple(normalized.split()),
                "source": source,
            }
            representations.append(representation)
            by_profile[profile_id].append(representation)
    return representations, by_profile


def build_token_indexes(representations):
    token_profiles = defaultdict(set)
    first_profiles = defaultdict(set)
    last_profiles = defaultdict(set)
    token_set_profiles = defaultdict(set)
    sequence_profiles = defaultdict(set)
    prefix_profiles = defaultdict(set)
    suffix_profiles = defaultdict(set)
    for representation in representations:
        profile_id = representation["profile_id"]
        tokens = representation["tokens"]
        for token in set(tokens):
            token_profiles[token].add(profile_id)
        first_profiles[tokens[0]].add(profile_id)
        last_profiles[tokens[-1]].add(profile_id)
        token_set_profiles[frozenset(tokens)].add(profile_id)
        sequence_profiles[tokens].add(profile_id)
        folded = apply_transform(representation["normalized"], ("alif", "ya"))
        compact = folded.replace(" ", "")
        prefix_profiles[compact[:4]].add(profile_id)
        suffix_profiles[compact[-4:]].add(profile_id)
    return {
        "token_profiles": token_profiles,
        "first_profiles": first_profiles,
        "last_profiles": last_profiles,
        "token_set_profiles": token_set_profiles,
        "sequence_profiles": sequence_profiles,
        "prefix_profiles": prefix_profiles,
        "suffix_profiles": suffix_profiles,
    }


def is_subsequence(needle, haystack):
    iterator = iter(haystack)
    return all(any(item == candidate for candidate in iterator) for item in needle)


def token_diagnostics(tokens, indexes, representations_by_profile):
    token_tuple = tuple(tokens)
    token_set = set(tokens)
    postings = [indexes["token_profiles"].get(token, set()) for token in token_set]
    mis_subset_pool = set.intersection(*map(set, postings)) if postings else set()
    mis_subset = set()
    mis_ordered = set()
    for profile_id in mis_subset_pool:
        for representation in representations_by_profile[profile_id]:
            representation_set = set(representation["tokens"])
            if token_set <= representation_set:
                mis_subset.add(profile_id)
            if is_subsequence(token_tuple, representation["tokens"]):
                mis_ordered.add(profile_id)

    itqan_subset = set()
    unique_tokens = sorted(token_set)
    for size in range(MIN_SUBSET_TOKENS, len(unique_tokens)):
        for subset in itertools.combinations(unique_tokens, size):
            itqan_subset.update(indexes["token_set_profiles"].get(frozenset(subset), set()))

    itqan_ordered = set()
    positions = range(len(token_tuple))
    for size in range(MIN_SUBSET_TOKENS, len(token_tuple)):
        for selected in itertools.combinations(positions, size):
            sequence = tuple(token_tuple[index] for index in selected)
            itqan_ordered.update(indexes["sequence_profiles"].get(sequence, set()))

    return {
        "mis_token_subset_profiles": mis_subset,
        "itqan_token_subset_profiles": itqan_subset,
        "mis_ordered_subsequence_profiles": mis_ordered,
        "itqan_ordered_subsequence_profiles": itqan_ordered,
        "same_first_token_profiles": set(
            indexes["first_profiles"].get(token_tuple[0], set())
        ) if token_tuple else set(),
        "same_last_token_profiles": set(
            indexes["last_profiles"].get(token_tuple[-1], set())
        ) if token_tuple else set(),
    }


def ngrams(text, size=3):
    compact = f"^{text}$"
    if len(compact) <= size:
        return {compact}
    return {compact[index:index + size] for index in range(len(compact) - size + 1)}


@lru_cache(maxsize=32768)
def cached_ngrams(text):
    return frozenset(ngrams(text))


def jaccard(left, right):
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def best_profile_scores(query, profile_ids, representations_by_profile, method):
    query_tokens = set(query.split())
    query_ngrams = cached_ngrams(query)
    scored = []
    for profile_id in profile_ids:
        best = None
        for representation in representations_by_profile.get(profile_id, []):
            target = representation["normalized"]
            if method == "CHARACTER_TRIGRAM_JACCARD":
                score = jaccard(query_ngrams, cached_ngrams(target))
            elif method == "TOKEN_JACCARD":
                score = jaccard(query_tokens, set(representation["tokens"]))
            elif method == "SEQUENCE_MATCHER_RATIO":
                score = difflib.SequenceMatcher(
                    None, query, target, autojunk=False
                ).ratio()
            else:
                raise ValueError(method)
            key = (score, -abs(len(query) - len(target)), target)
            if best is None or key > best[0]:
                best = (key, representation)
        if best is not None:
            scored.append({
                "profile_id": profile_id,
                "score": best[0][0],
                "matched_representation": best[1],
            })
    scored.sort(key=lambda row: (-row["score"], _id_sort(row["profile_id"]), row["matched_representation"]["normalized"]))
    return scored


def relationship_flags(query_tokens, target_tokens):
    query = tuple(query_tokens)
    target = tuple(target_tokens)
    return {
        "same_first_token": bool(query and target and query[0] == target[0]),
        "same_last_token": bool(query and target and query[-1] == target[-1]),
        "mis_ordered_subsequence": is_subsequence(query, target),
        "itqan_ordered_subsequence": is_subsequence(target, query),
        "mis_token_set_subset": set(query) <= set(target),
        "itqan_token_set_subset": set(target) <= set(query),
    }


def discover_candidates(
    record, indexes, representations_by_profile, profiles_by_id,
    ablation_candidates, known_teacher_profiles, known_student_profiles,
    short_name, short_name_candidates,
):
    query = record["search_normalized_name"]
    tokens = query.split()
    postings = [
        (len(indexes["token_profiles"].get(token, set())), token)
        for token in set(tokens)
        if indexes["token_profiles"].get(token)
    ]
    postings.sort()
    token_pool = set()
    for _, token in postings[:2]:
        token_pool.update(indexes["token_profiles"][token])

    folded = apply_transform(query, ("alif", "ya")).replace(" ", "")
    prefix_pool = set(indexes["prefix_profiles"].get(folded[:4], set()))
    suffix_pool = set(indexes["suffix_profiles"].get(folded[-4:], set()))
    char_pool = prefix_pool & suffix_pool
    if not char_pool:
        char_pool = prefix_pool | suffix_pool
    if not char_pool:
        char_pool.update(indexes["first_profiles"].get(tokens[0], set()))
        char_pool.update(indexes["last_profiles"].get(tokens[-1], set()))
    if not token_pool:
        token_pool = set(char_pool)

    char_ranked = best_profile_scores(
        query, char_pool, representations_by_profile, "CHARACTER_TRIGRAM_JACCARD"
    )[:max(TOP_N, 10)]
    token_ranked = best_profile_scores(
        query, token_pool, representations_by_profile, "TOKEN_JACCARD"
    )[:max(TOP_N, 10)]
    edit_pool = {
        row["profile_id"] for row in char_ranked + token_ranked
    }
    edit_ranked = best_profile_scores(
        query, edit_pool, representations_by_profile, "SEQUENCE_MATCHER_RATIO"
    )[:TOP_N]
    rankings = {
        "CHARACTER_TRIGRAM_JACCARD": char_ranked[:TOP_N],
        "TOKEN_JACCARD": token_ranked[:TOP_N],
        "SEQUENCE_MATCHER_RATIO": edit_ranked,
    }

    merged = {}
    for method, ranked in rankings.items():
        for rank, row in enumerate(ranked, start=1):
            profile_id = row["profile_id"]
            entry = merged.setdefault(profile_id, {
                "diagnostic_label": "DIAGNOSTIC_CANDIDATE",
                "itqan_id": profile_id,
                "canonical_name": profiles_by_id[profile_id].get("full_name"),
                "matched_variants": set(),
                "methods": {},
            })
            entry["matched_variants"].add(row["matched_representation"]["raw"])
            entry["methods"][method] = {
                "rank": rank,
                "score": row["score"],
                "matched_representation": row["matched_representation"]["raw"],
                "matched_representation_source": row["matched_representation"]["source"],
            }

    for profile_id in sorted(short_name_candidates, key=_id_sort):
        exact_representations = [
            representation
            for representation in representations_by_profile[profile_id]
            if representation["normalized"] == short_name
        ]
        entry = merged.setdefault(profile_id, {
            "diagnostic_label": "DIAGNOSTIC_CANDIDATE",
            "itqan_id": profile_id,
            "canonical_name": profiles_by_id[profile_id].get("full_name"),
            "matched_variants": set(),
            "methods": {},
        })
        entry["matched_variants"].update(
            representation["raw"] for representation in exact_representations
        )
        entry["methods"]["MIS_DOCUMENTED_SHORT_NAME_EXACT"] = {
            "match_type": "NARROW_EXACT",
            "matched_representations": [
                {
                    "raw": representation["raw"],
                    "source": representation["source"],
                }
                for representation in exact_representations
            ],
            "score": None,
            "rank": None,
        }

    result = []
    for profile_id in sorted(merged, key=_id_sort):
        entry = merged[profile_id]
        best_representation = min(
            (
                representations_by_profile[profile_id]
            ),
            key=lambda rep: (
                -difflib.SequenceMatcher(None, query, rep["normalized"], autojunk=False).ratio(),
                rep["normalized"],
            ),
        )
        entry["matched_variants"] = sorted(entry["matched_variants"])
        entry["structural_relationships"] = relationship_flags(
            tokens, best_representation["tokens"]
        )
        entry["exact_under_diagnostic_transformations"] = sorted(
            transformation
            for transformation, profile_ids in ablation_candidates.items()
            if profile_id in profile_ids and transformation != "BASELINE_NARROW_CONTROL"
        )
        profile = profiles_by_id[profile_id]
        teacher_ids = {
            canonical_id(value) for value in profile.get("teachers", [])
        } if isinstance(profile.get("teachers"), list) else set()
        student_ids = {
            canonical_id(value) for value in profile.get("students", [])
        } if isinstance(profile.get("students"), list) else set()
        entry["teacher_support"] = "TRUE" if teacher_ids & known_teacher_profiles else "UNKNOWN"
        entry["student_support"] = "TRUE" if student_ids & known_student_profiles else "UNKNOWN"
        result.append(entry)

    method_top = {
        method: ranked[0]["profile_id"] if ranked else None
        for method, ranked in rankings.items()
    }
    return result, method_top


def public_profile(profile):
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


def ensure_frozen_csv_bundle(
    visible_path, visible_columns, visible_rows,
    hidden_path, hidden_columns, hidden_rows, meta_path, meta,
    human_columns,
):
    if visible_path.exists():
        columns, existing = read_csv(visible_path)
        if columns != visible_columns:
            raise RuntimeError(f"Refusing to overwrite {visible_path}: schema differs")
        stable_columns = tuple(column for column in visible_columns if column not in human_columns)
        expected = [
            {column: str(row.get(column, "")) for column in stable_columns}
            for row in visible_rows
        ]
        actual = [
            {column: str(row.get(column, "")) for column in stable_columns}
            for row in existing
        ]
        if actual != expected:
            raise RuntimeError(f"Refusing to overwrite {visible_path}: frozen rows differ")
        labels = sum(
            any(str(row.get(column, "")).strip() for column in human_columns)
            for row in existing
        )
        if not hidden_path.exists() or not meta_path.exists():
            raise RuntimeError(f"Incomplete frozen review bundle for {visible_path}")
        return {"action": "preserved", "human_inputs_present": labels}
    write_csv(visible_path, visible_columns, visible_rows)
    write_csv(hidden_path, hidden_columns, hidden_rows)
    write_json(meta_path, meta)
    return {"action": "created", "human_inputs_present": 0}


def build_census_review(auto_records, profiles_by_id):
    shuffled = sorted(auto_records, key=lambda row: _id_sort(row["mis_narrator_id"]))
    random.Random(CENSUS_SEED).shuffle(shuffled)
    visible = []
    hidden = []
    for number, record in enumerate(shuffled, start=1):
        candidate = record["candidates"][0]
        review_id = f"NER-CENSUS-{number:04d}"
        visible.append({
            "review_id": review_id,
            "mis_narrator_id": record["mis_narrator_id"],
            "mis_name": record["raw_name"],
            "itqan_profile_evidence_json": json_compact(
                public_profile(profiles_by_id[candidate["itqan_id"]])
            ),
            "reviewer_selected_itqan_id": "",
            "manual_verdict": "",
            "notes": "",
        })
        hidden.append({
            "review_id": review_id,
            "mis_narrator_id": record["mis_narrator_id"],
            "provisional_tier": record["provisional_tier"],
            "provisional_resolved_itqan_id": record["provisional_resolved_itqan_id"],
            "candidate_sources_json": json_compact(candidate["candidate_source"]),
            "automatic_confidence": candidate.get("itqan_identity_confidence"),
        })
    return visible, hidden


def classify_stratum(feature, short_name_candidates, ablation_union, token_report):
    if len(short_name_candidates) == 1:
        return "DOCUMENTED_SHORT_NAME_UNIQUE_CANDIDATE"
    if len(short_name_candidates) > 1:
        return "DOCUMENTED_SHORT_NAME_MULTIPLE_CANDIDATES"
    if len(ablation_union) == 1:
        return "NORMALIZATION_ONLY_UNIQUE_CANDIDATE"
    if len(ablation_union) > 1:
        return "MULTIPLE_NORMALIZATION_CANDIDATES"
    if token_report["mis_ordered_subsequence_profiles"]:
        return "MIS_NAME_CONTAINED_IN_ITQAN_NAME"
    if token_report["itqan_ordered_subsequence_profiles"]:
        return "ITQAN_NAME_CONTAINED_IN_MIS_NAME"
    if (
        token_report["mis_token_subset_profiles"]
        or token_report["itqan_token_subset_profiles"]
    ):
        return "TOKEN_SET_CONTAINMENT_WITH_ORDER_DIFFERENCE"
    if any(feature[key] for key in (
        "has_punctuation", "has_brackets", "has_digits", "has_latin",
        "has_other_script_letters", "has_repeated_whitespace", "has_unusual_unicode",
    )):
        return "FORMAT_OR_UNICODE_ANOMALY_WITHOUT_EXACT_CANDIDATE"
    return "NO_EXACT_STRUCTURAL_CANDIDATE"


def build_unmatched_review(records, profiles_by_id, seed=UNMATCHED_SAMPLE_SEED):
    by_stratum = defaultdict(list)
    for record in records:
        by_stratum[record["diagnostic_stratum"]].append(record)
    rng = random.Random(seed)
    selected = []
    allocation = {}
    for stratum in sorted(by_stratum):
        population = sorted(by_stratum[stratum], key=lambda row: _id_sort(row["mis_narrator_id"]))
        count = min(20, len(population))
        allocation[stratum] = count
        selected.extend(rng.sample(population, count))
    rng.shuffle(selected)

    visible = []
    hidden = []
    for number, record in enumerate(selected, start=1):
        review_id = f"NER-UNMATCHED-{number:04d}"
        public_candidates = []
        for candidate in record["diagnostic_candidates"]:
            public_candidates.append({
                "diagnostic_label": "DIAGNOSTIC_CANDIDATE",
                "itqan_id": candidate["itqan_id"],
                "canonical_name": candidate["canonical_name"],
                "relevant_raw_name_variants": candidate["matched_variants"],
                "kunya": profiles_by_id[candidate["itqan_id"]].get("kunya"),
                "nasab": profiles_by_id[candidate["itqan_id"]].get("nasab"),
                "death": profiles_by_id[candidate["itqan_id"]].get("death"),
            })
        visible.append({
            "review_id": review_id,
            "mis_narrator_id": record["mis_narrator_id"],
            "mis_name": record["raw_name"],
            "mis_short_name": record["short_name"],
            "diagnostic_candidate_evidence_json": json_compact(public_candidates),
            "reviewer_selected_itqan_id": "",
            "diagnostic_verdict": "",
            "notes": "",
        })
        hidden.append({
            "review_id": review_id,
            "mis_narrator_id": record["mis_narrator_id"],
            "diagnostic_stratum": record["diagnostic_stratum"],
            "diagnostic_methods_and_scores_json": json_compact([
                {
                    "itqan_id": candidate["itqan_id"],
                    "methods": candidate["methods"],
                    "structural_relationships": candidate["structural_relationships"],
                    "teacher_support": candidate["teacher_support"],
                    "student_support": candidate["student_support"],
                }
                for candidate in record["diagnostic_candidates"]
            ]),
            "name_features_json": json_compact(record["name_features"]),
            "token_diagnostics_json": json_compact(record["token_diagnostic_counts"]),
            "ablation_candidates_json": json_compact(record["ablation_candidate_ids"]),
        })
    return visible, hidden, {
        "stratum_populations": {
            stratum: len(rows) for stratum, rows in sorted(by_stratum.items())
        },
        "stratum_sample_allocation": allocation,
        "total_rows": len(visible),
    }


def run_ablation(unmatched, auto_records, representations):
    representations_by_profile = defaultdict(list)
    for representation in representations:
        representations_by_profile[representation["profile_id"]].append(representation)
    per_unmatched = {record["mis_narrator_id"]: {} for record in unmatched}
    reports = {}
    ya_details = {}

    for name, operations in TRANSFORMATIONS.items():
        transformed_index = defaultdict(set)
        transformed_base_keys = defaultdict(set)
        for representation in representations:
            key = apply_transform(representation["normalized"], operations)
            transformed_index[key].add(representation["profile_id"])
            transformed_base_keys[key].add(representation["normalized"])

        counts = []
        for record in unmatched:
            candidates = set(transformed_index.get(
                apply_transform(record["raw_name"], operations), set()
            ))
            per_unmatched[record["mis_narrator_id"]][name] = candidates
            counts.append(len(candidates))

        unique_to_ambiguous = unique_to_different = 0
        for record in auto_records:
            candidates = set(transformed_index.get(
                apply_transform(record["raw_name"], operations), set()
            ))
            if len(candidates) > 1:
                unique_to_ambiguous += 1
            elif len(candidates) == 1 and record["provisional_resolved_itqan_id"] not in candidates:
                unique_to_different += 1

        collision_keys = {
            key: profile_ids
            for key, profile_ids in transformed_index.items()
            if len(profile_ids) > 1
        }
        new_collision_keys = {
            key: profile_ids
            for key, profile_ids in collision_keys.items()
            if len(transformed_base_keys[key]) > 1
        }
        reports[name] = {
            "transformation": name,
            "operations": list(operations),
            "population": len(unmatched),
            "candidate_coverage": sum(count > 0 for count in counts),
            "unique_candidates": sum(count == 1 for count in counts),
            "ambiguous_candidates": sum(count > 1 for count in counts),
            "largest_collision": max(counts, default=0),
            "incremental_vs_baseline": sum(count > 0 for count in counts),
            "previous_unique_to_ambiguous": unique_to_ambiguous,
            "previous_unique_to_different_unique": unique_to_different,
            "global_collision_keys": len(collision_keys),
            "global_profiles_in_collisions": len(set().union(*collision_keys.values())) if collision_keys else 0,
            "global_largest_collision": max(map(len, collision_keys.values()), default=0),
            "new_global_collision_keys": len(new_collision_keys),
            "new_global_profiles_in_collisions": len(set().union(*new_collision_keys.values())) if new_collision_keys else 0,
            "used_for_resolution": False,
        }

        if name == "YA_MAQSURA_TO_YA":
            only_ya = additional = unique = ambiguous = 0
            for record in unmatched:
                candidates = per_unmatched[record["mis_narrator_id"]][name]
                if len(candidates) == 1:
                    unique += 1
                    profile_id = next(iter(candidates))
                    source = normalize_narrow_identity(record["raw_name"])
                    matches = [
                        representation["normalized"]
                        for representation in representations_by_profile[profile_id]
                        if apply_transform(representation["normalized"], operations)
                        == apply_transform(source, operations)
                    ]
                    pure = any(
                        len(source) == len(target)
                        and all(
                            left == right or {left, right} == {"ى", "ي"}
                            for left, right in zip(source, target)
                        )
                        for target in matches
                    )
                    only_ya += pure
                    additional += not pure
                elif len(candidates) > 1:
                    ambiguous += 1
            ya_details = {
                "unique_candidate_narrators": unique,
                "unique_with_only_ya_maqsura_codepoint_difference": only_ya,
                "unique_with_additional_character_or_token_differences": additional,
                "ambiguous_candidate_narrators": ambiguous,
                "previous_unique_to_ambiguous": unique_to_ambiguous,
                "global_collision_keys_after_fold": len(collision_keys),
                "new_global_collision_keys_introduced": len(new_collision_keys),
                "profiles_in_new_global_collisions": (
                    len(set().union(*new_collision_keys.values())) if new_collision_keys else 0
                ),
                "largest_global_collision_after_fold": max(
                    map(len, collision_keys.values()), default=0
                ),
                "used_for_resolution": False,
            }

    return reports, per_unmatched, ya_details


def main():
    required = (BASE_AUDIT, BASE_CANDIDATES, FROZEN_REVIEW_117)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing frozen Phase 2 inputs: {missing}")

    base_hash_before = file_sha256(BASE_CANDIDATES)
    review_117_hash_before = file_sha256(FROZEN_REVIEW_117)
    records = load_jsonl(BASE_CANDIDATES)
    tiers = Counter(record["provisional_tier"] for record in records)
    expected = {
        "EXACT_RESOLVED": 30, "ALIAS_RESOLVED": 51,
        "AMBIGUOUS": 10, "UNMATCHED": 2001,
    }
    if any(tiers[key] != value for key, value in expected.items()):
        raise RuntimeError(f"Frozen tier population changed: {dict(tiers)}")
    auto_records = [record for record in records if record["provisional_tier"] in AUTO_TIERS]
    unmatched = [record for record in records if record["provisional_tier"] == "UNMATCHED"]
    ambiguous = [record for record in records if record["provisional_tier"] == "AMBIGUOUS"]

    _, nodes = read_sheet(NODES)
    _, edges = read_sheet(EDGES)
    profiles, per_file = load_profiles()
    profiles_by_id = {
        canonical_id(profile.get("id")): profile for profile in profiles
    }
    representations, representations_by_profile = build_representations(profiles)
    indexes = build_token_indexes(representations)
    narrow_representation_index = defaultdict(set)
    for representation in representations:
        narrow_representation_index[representation["normalized"]].add(
            representation["profile_id"]
        )
    node_by_id = {
        normalize_identifier(node.get("NarratorID_Mapped")): node for node in nodes
    }

    ablation_reports, ablation_by_mis, ya_analysis = run_ablation(
        unmatched, auto_records, representations
    )

    resolved = {
        record["mis_narrator_id"]: record["provisional_resolved_itqan_id"]
        for record in auto_records
    }
    teachers = defaultdict(set)
    students = defaultdict(set)
    for edge in edges:
        source = normalize_identifier(edge.get("sourceNarratorID"))
        target = normalize_identifier(edge.get("targetNarratorID"))
        if source is not None and target is not None:
            students[source].add(target)
            teachers[target].add(source)

    detailed = []
    top_method_interpretability = defaultdict(Counter)
    directional = Counter()
    relational = Counter()
    for record in unmatched:
        feature = raw_name_features(record["raw_name"])
        node = node_by_id[record["mis_narrator_id"]]
        short_name = str(node.get("NarratorNameAr-Mapped") or "")
        short_name_normalized = normalize_narrow_identity(short_name)
        short_name_candidates = set(
            narrow_representation_index.get(short_name_normalized, set())
        )
        token_report = token_diagnostics(
            feature["tokens"], indexes, representations_by_profile
        )
        candidate_sets = ablation_by_mis[record["mis_narrator_id"]]
        ablation_union = set().union(*(
            profile_ids
            for name, profile_ids in candidate_sets.items()
            if name != "BASELINE_NARROW_CONTROL"
        ))
        known_teacher_profiles = {
            resolved[mis_id] for mis_id in teachers[record["mis_narrator_id"]]
            if mis_id in resolved
        }
        known_student_profiles = {
            resolved[mis_id] for mis_id in students[record["mis_narrator_id"]]
            if mis_id in resolved
        }
        diagnostic_candidates, method_top = discover_candidates(
            record, indexes, representations_by_profile, profiles_by_id,
            candidate_sets, known_teacher_profiles, known_student_profiles,
            short_name_normalized, short_name_candidates,
        )
        candidates_by_id = {
            candidate["itqan_id"]: candidate for candidate in diagnostic_candidates
        }
        for method, profile_id in method_top.items():
            if profile_id is None:
                top_method_interpretability[method]["NO_CANDIDATE"] += 1
                continue
            candidate = candidates_by_id[profile_id]
            relationships = candidate["structural_relationships"]
            if candidate["exact_under_diagnostic_transformations"]:
                top_method_interpretability[method]["EXACT_UNDER_ABLATION"] += 1
            if relationships["mis_ordered_subsequence"]:
                top_method_interpretability[method]["MIS_ORDERED_SUBSEQUENCE"] += 1
            if relationships["itqan_ordered_subsequence"]:
                top_method_interpretability[method]["ITQAN_ORDERED_SUBSEQUENCE"] += 1
            if relationships["same_first_token"]:
                top_method_interpretability[method]["SAME_FIRST_TOKEN"] += 1
            if relationships["same_last_token"]:
                top_method_interpretability[method]["SAME_LAST_TOKEN"] += 1
            if not (
                candidate["exact_under_diagnostic_transformations"]
                or relationships["mis_ordered_subsequence"]
                or relationships["itqan_ordered_subsequence"]
            ):
                top_method_interpretability[method]["NO_EXACT_STRUCTURAL_RELATION"] += 1

        char_top = method_top["CHARACTER_TRIGRAM_JACCARD"]
        length_direction = "NO_CANDIDATE"
        if char_top is not None:
            candidate = candidates_by_id[char_top]
            matched = candidate["methods"][
                "CHARACTER_TRIGRAM_JACCARD"
            ]["matched_representation"]
            mis_tokens = len(feature["tokens"])
            itqan_tokens = len(normalize_narrow_identity(matched).split())
            if mis_tokens < itqan_tokens:
                length_direction = "MIS_SHORTER"
            elif mis_tokens > itqan_tokens:
                length_direction = "MIS_LONGER"
            else:
                length_direction = "SAME_TOKEN_COUNT"
        directional[length_direction] += 1
        supported = sum(
            candidate["teacher_support"] == "TRUE"
            or candidate["student_support"] == "TRUE"
            for candidate in diagnostic_candidates
        )
        relational["narrators_with_any_supported_diagnostic_candidate"] += supported > 0
        relational["supported_diagnostic_candidate_rows"] += supported
        relational["narrators_with_resolved_teacher_anchors"] += bool(known_teacher_profiles)
        relational["narrators_with_resolved_student_anchors"] += bool(known_student_profiles)

        token_counts = {
            key: len(value) for key, value in token_report.items()
        }
        stratum = classify_stratum(
            feature, short_name_candidates, ablation_union, token_report
        )
        detailed.append({
            "mis_narrator_id": record["mis_narrator_id"],
            "raw_name": record["raw_name"],
            "normalized_name": record["search_normalized_name"],
            "short_name": short_name,
            "short_name_normalized": short_name_normalized,
            "short_name_candidate_ids": sorted(short_name_candidates, key=_id_sort),
            "short_name_candidate_profiles": len(short_name_candidates),
            "name_features": feature,
            "ablation_candidate_ids": {
                name: sorted(profile_ids, key=_id_sort)
                for name, profile_ids in candidate_sets.items()
                if profile_ids
            },
            "ablation_candidate_profiles": len(ablation_union),
            "token_diagnostic_counts": token_counts,
            "diagnostic_candidates": diagnostic_candidates,
            "diagnostic_candidate_profiles": len(diagnostic_candidates),
            "diagnostic_stratum": stratum,
            "top_character_candidate_length_direction": length_direction,
            "relationship_supported_candidates": supported,
        })

    census_visible, census_hidden = build_census_review(auto_records, profiles_by_id)
    census_meta = {
        "purpose": "Full census review of all frozen provisional deterministic auto-resolutions.",
        "population": len(auto_records),
        "sampling_method": "full census; randomized display order only",
        "seed": CENSUS_SEED,
        "allowed_verdicts": list(ALLOWED_CENSUS_VERDICTS),
        "base_candidates_sha256": base_hash_before,
        "normalizer_version": NORMALIZER_VERSION,
        "visible_columns": list(CENSUS_VISIBLE_COLUMNS),
        "hidden_columns": list(CENSUS_HIDDEN_COLUMNS),
        "manual_labels_at_generation": 0,
    }
    census_status = ensure_frozen_csv_bundle(
        CENSUS_REVIEW_PATH, CENSUS_VISIBLE_COLUMNS, census_visible,
        CENSUS_HIDDEN_PATH, CENSUS_HIDDEN_COLUMNS, census_hidden,
        CENSUS_META_PATH, census_meta,
        {"reviewer_selected_itqan_id", "manual_verdict", "notes"},
    )

    unmatched_visible, unmatched_hidden, unmatched_sample = build_unmatched_review(
        detailed, profiles_by_id
    )
    unmatched_meta = {
        "purpose": "Explore unmatched-name failure modes; not a precision sample and not resolver validation.",
        "population": len(unmatched),
        "sampling_method": "up to 20 deterministic random rows per descriptive failure stratum",
        "seed": UNMATCHED_SAMPLE_SEED,
        "allowed_verdicts": list(ALLOWED_DIAGNOSTIC_VERDICTS),
        "base_candidates_sha256": base_hash_before,
        "normalizer_version": NORMALIZER_VERSION,
        "visible_columns": list(UNMATCHED_VISIBLE_COLUMNS),
        "hidden_columns": list(UNMATCHED_HIDDEN_COLUMNS),
        "manual_labels_at_generation": 0,
        **unmatched_sample,
    }
    unmatched_status = ensure_frozen_csv_bundle(
        UNMATCHED_REVIEW_PATH, UNMATCHED_VISIBLE_COLUMNS, unmatched_visible,
        UNMATCHED_HIDDEN_PATH, UNMATCHED_HIDDEN_COLUMNS, unmatched_hidden,
        UNMATCHED_META_PATH, unmatched_meta,
        {"reviewer_selected_itqan_id", "diagnostic_verdict", "notes"},
    )

    profile_rows = []
    for record in detailed:
        feature = record["name_features"]
        token_counts = record["token_diagnostic_counts"]
        profile_rows.append({
            **{
                column: feature.get(column, "")
                for column in PROFILE_COLUMNS
                if column in feature and column != "tokens"
            },
            "mis_narrator_id": record["mis_narrator_id"],
            "raw_name": record["raw_name"],
            "normalized_name": record["normalized_name"],
            "short_name": record["short_name"],
            "short_name_normalized": record["short_name_normalized"],
            "short_name_candidate_profiles": record[
                "short_name_candidate_profiles"
            ],
            "ablation_candidate_profiles": record["ablation_candidate_profiles"],
            **token_counts,
            "diagnostic_candidate_profiles": record["diagnostic_candidate_profiles"],
            "diagnostic_stratum": record["diagnostic_stratum"],
            "top_character_candidate_length_direction": record[
                "top_character_candidate_length_direction"
            ],
            "relationship_supported_candidates": record[
                "relationship_supported_candidates"
            ],
        })
    write_csv(PROFILE_PATH, PROFILE_COLUMNS, profile_rows)
    write_csv(ABLATION_PATH, ABLATION_COLUMNS, [
        {column: report.get(column, "") for column in ABLATION_COLUMNS}
        for _, report in ablation_reports.items()
    ])
    with open(DIAGNOSTIC_CANDIDATES_PATH, "w", encoding="utf-8", newline="\n") as handle:
        for record in detailed:
            handle.write(json.dumps({
                "mis_narrator_id": record["mis_narrator_id"],
                "mis_name": record["raw_name"],
                "mis_short_name": record["short_name"],
                "mis_short_name_candidate_ids": record["short_name_candidate_ids"],
                "artifact_label": "DIAGNOSTIC_CANDIDATES_NOT_MATCHES",
                "diagnostic_stratum": record["diagnostic_stratum"],
                "candidates": record["diagnostic_candidates"],
            }, ensure_ascii=False, sort_keys=True) + "\n")

    mapped_field = [node.get("NarratorNameAr-Mapped") for node in nodes]
    complete_field = [node.get("NarratorNameAr") for node in nodes]
    mis_schema_name_semantics = {
        "paper_source": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11096860/",
        "paper_field_definition_NarratorNameAr": "Narrator Complete Name in Arabic Text",
        "paper_field_definition_NarratorNameAr_Mapped": "Narrator Short Name in Arabic Text",
        "documented_identity_mapping_process": (
            "Ihsan-Network narrator mentions were linked to Muslim-Scholars profiles "
            "using logical code, fuzzywuzzy, then manual mapping for remaining names."
        ),
        "actual_complete_name_nonblank": sum(bool(str(value or "").strip()) for value in complete_field),
        "actual_short_name_nonblank": sum(bool(str(value or "").strip()) for value in mapped_field),
        "narrow_equal_complete_and_short": sum(
            normalize_narrow_identity(left) == normalize_narrow_identity(right)
            for left, right in zip(complete_field, mapped_field)
        ),
        "short_has_fewer_tokens": sum(
            len(normalize_narrow_identity(short).split())
            < len(normalize_narrow_identity(complete).split())
            for complete, short in zip(complete_field, mapped_field)
        ),
        "diagnostic_name_field_used": "NarratorNameAr (documented complete name)",
        "source_name_form_before MIS mapping": "UNKNOWN from downloaded workbooks",
    }

    short_field_by_tier = {}
    for tier_name, tier_records in {
        "all_mis": records,
        "resolved_mis": auto_records,
        "ambiguous_mis": ambiguous,
        "unmatched_mis": unmatched,
    }.items():
        counts = []
        unique_same_as_frozen = unique_different_from_frozen = 0
        for record in tier_records:
            node = node_by_id[record["mis_narrator_id"]]
            short_name = normalize_narrow_identity(
                node.get("NarratorNameAr-Mapped")
            )
            candidates = set(narrow_representation_index.get(short_name, set()))
            counts.append(len(candidates))
            if len(candidates) == 1 and record.get("provisional_resolved_itqan_id"):
                if record["provisional_resolved_itqan_id"] in candidates:
                    unique_same_as_frozen += 1
                else:
                    unique_different_from_frozen += 1
        short_field_by_tier[tier_name] = {
            **candidate_cardinality_distribution(counts),
            "unique_same_as_frozen_resolution": unique_same_as_frozen,
            "unique_different_from_frozen_resolution": unique_different_from_frozen,
            "used_for_resolution": False,
        }

    namings_lists = [
        profile.get("namings") if isinstance(profile.get("namings"), list) else []
        for profile in profiles
    ]
    relative_alias_refs = Counter()
    for representation in representations:
        if representation["source"] == "alias" and representation["normalized"] in RELATIVE_ALIAS_FORMS:
            relative_alias_refs[representation["normalized"]] += 1
    itqan_semantics = {
        "upstream_source": "https://github.com/R3GENESI5/Itqan",
        "upstream_claim": (
            "Profiles expose a full name and name variants; the repository describes "
            "variants as spellings across manuscripts and the unified database as a merge "
            "of three structured datasets plus 22 parsed classical texts."
        ),
        "local_manifest_version": "1.20",
        "local_profile_rows": len(profiles),
        "local_manifest_declared_variants": 217762,
        "local_namings_items": sum(len(values) for values in namings_lists),
        "local_profiles_with_nonempty_namings": sum(bool(values) for values in namings_lists),
        "local_profile_level_unique_name_representations": len(representations),
        "relative_or_contextual_alias_forms": dict(relative_alias_refs),
        "all_known_aliases_completeness_guarantee_in_machine_readable_manifest": False,
        "source_specific_forms_omitted_from_namings": "UNKNOWN",
        "upstream_commit_for_local_snapshot": "UNKNOWN",
    }

    group_records = {
        "all_mis": records,
        "resolved_mis": auto_records,
        "ambiguous_mis": ambiguous,
        "unmatched_mis": unmatched,
    }
    name_distributions = {
        group: describe_names([record["raw_name"] for record in group_rows])
        for group, group_rows in group_records.items()
    }
    name_distributions["itqan_canonical_names"] = describe_names([
        profile.get("full_name") for profile in profiles
    ])
    name_distributions["itqan_profile_level_unique_representations"] = describe_names([
        representation["raw"] for representation in representations
    ])

    token_population = Counter()
    for record in detailed:
        for key, value in record["token_diagnostic_counts"].items():
            token_population[f"narrators_with_{key}"] += value > 0
        token_population["narrators_with_same_first_and_last_token_candidate"] += (
            record["token_diagnostic_counts"]["same_first_token_profiles"] > 0
            and record["token_diagnostic_counts"]["same_last_token_profiles"] > 0
        )
    token_cardinality = {
        key: candidate_cardinality_distribution([
            record["token_diagnostic_counts"][key] for record in detailed
        ])
        for key in (
            "mis_token_subset_profiles", "itqan_token_subset_profiles",
            "mis_ordered_subsequence_profiles", "itqan_ordered_subsequence_profiles",
            "same_first_token_profiles", "same_last_token_profiles",
        )
    }

    strata = Counter(record["diagnostic_stratum"] for record in detailed)
    artifact_specs = (
        (PROFILE_PATH, len(profile_rows), "csv"),
        (ABLATION_PATH, len(ablation_reports), "csv"),
        (DIAGNOSTIC_CANDIDATES_PATH, len(detailed), "jsonl"),
        (CENSUS_REVIEW_PATH, len(census_visible), "csv"),
        (CENSUS_HIDDEN_PATH, len(census_hidden), "csv"),
        (CENSUS_META_PATH, 1, "json"),
        (UNMATCHED_REVIEW_PATH, len(unmatched_visible), "csv"),
        (UNMATCHED_HIDDEN_PATH, len(unmatched_hidden), "csv"),
        (UNMATCHED_META_PATH, 1, "json"),
    )
    audit = {
        "phase": "Phase 2A unmatched-name representation-gap diagnostic",
        "version": MILESTONE_VERSION,
        "inputs": {
            "base_candidate_artifact": {
                "path": str(BASE_CANDIDATES),
                "sha256": base_hash_before,
                "rows": len(records),
                "frozen_tiers": expected,
            },
            "existing_frozen_117_review": {
                "path": str(FROZEN_REVIEW_117),
                "sha256": review_117_hash_before,
                "mutation_policy": "unchanged",
            },
            "mis_nodes_sha256": file_sha256(NODES),
            "mis_edges_sha256": file_sha256(EDGES),
            "itqan_profile_shards_sha256": hashlib.sha256("\n".join(
                f"{path.name}|{file_sha256(path)}"
                for path in sorted(ITQAN_DIR / f"{name}.json" for name in PROFILE_FILES)
            ).encode("utf-8")).hexdigest(),
            "itqan_profile_shard_rows": per_file,
            "script_sha256": file_sha256(Path(__file__)),
        },
        "frozen_tier_integrity": {
            "EXACT_RESOLVED": tiers["EXACT_RESOLVED"],
            "ALIAS_RESOLVED": tiers["ALIAS_RESOLVED"],
            "AMBIGUOUS": tiers["AMBIGUOUS"],
            "UNMATCHED": tiers["UNMATCHED"],
            "base_candidate_sha256_unchanged": file_sha256(BASE_CANDIDATES) == base_hash_before,
            "existing_117_review_sha256_unchanged": (
                file_sha256(FROZEN_REVIEW_117) == review_117_hash_before
            ),
        },
        "name_distributions": name_distributions,
        "normalization_ablation": ablation_reports,
        "ya_maqsura_analysis": ya_analysis,
        "token_structure_population": dict(token_population),
        "token_structure_candidate_cardinality": token_cardinality,
        "mis_documented_short_name_field_diagnostic": {
            "field": "NarratorNameAr-Mapped",
            "paper_semantics": "Narrator Short Name in Arabic Text",
            "candidate_lookup": "narrow exact over Itqan canonical names plus namings[]",
            "by_frozen_tier": short_field_by_tier,
            "used_for_resolution": False,
        },
        "directional_top_character_candidate": dict(directional),
        "diagnostic_candidate_discovery": {
            "population": len(detailed),
            "top_n_per_method": TOP_N,
            "methods": [
                "CHARACTER_TRIGRAM_JACCARD", "TOKEN_JACCARD",
                "SEQUENCE_MATCHER_RATIO", "MIS_DOCUMENTED_SHORT_NAME_EXACT",
            ],
            "documented_short_name_exact_method_is_ranked": False,
            "blocking": (
                "two rarest exact query tokens plus the intersection of four-character "
                "alif/ya-folded prefix and suffix blocks (union fallback); no recall "
                "claim is possible"
            ),
            "top_1_interpretable_relationships_by_method": {
                method: dict(counts)
                for method, counts in top_method_interpretability.items()
            },
            "artifact_label": "DIAGNOSTIC_CANDIDATE, never MATCH",
            "used_for_resolution": False,
        },
        "unmatched_failure_strata": {
            "rules_in_priority_order": [
                "DOCUMENTED_SHORT_NAME_UNIQUE_CANDIDATE: documented MIS short name is narrow-exact to exactly one Itqan profile representation",
                "DOCUMENTED_SHORT_NAME_MULTIPLE_CANDIDATES: documented MIS short name is narrow-exact to more than one Itqan profile representation",
                "NORMALIZATION_ONLY_UNIQUE_CANDIDATE: exactly one profile across diagnostic ablations",
                "MULTIPLE_NORMALIZATION_CANDIDATES: more than one profile across diagnostic ablations",
                "MIS_NAME_CONTAINED_IN_ITQAN_NAME: MIS token sequence is an exact ordered subsequence",
                "ITQAN_NAME_CONTAINED_IN_MIS_NAME: an Itqan sequence of at least two tokens is an exact ordered subsequence",
                "TOKEN_SET_CONTAINMENT_WITH_ORDER_DIFFERENCE: unordered token containment exists but ordered containment does not",
                "FORMAT_OR_UNICODE_ANOMALY_WITHOUT_EXACT_CANDIDATE: deterministic raw-format flag with no prior structural candidate",
                "NO_EXACT_STRUCTURAL_CANDIDATE: none of the preceding exact structural diagnostics applies",
            ],
            "population": dict(strata),
            "used_for_resolution": False,
        },
        "relational_support": {
            **dict(relational),
            "anchors": "only the frozen 81 provisional profiles",
            "unknown_is_not_false": True,
            "used_for_resolution": False,
            "circular_unresolved_anchors_used": False,
        },
        "dataset_documentation_findings": {
            "mis": mis_schema_name_semantics,
            "itqan": itqan_semantics,
        },
        "auto_resolved_census_review": {
            **census_meta,
            "artifact_status": {
                "human_inputs_present": census_status["human_inputs_present"]
            },
            "visible_path": str(CENSUS_REVIEW_PATH),
            "hidden_path": str(CENSUS_HIDDEN_PATH),
        },
        "unmatched_diagnostic_review": {
            **unmatched_meta,
            "artifact_status": {
                "human_inputs_present": unmatched_status["human_inputs_present"]
            },
            "visible_path": str(UNMATCHED_REVIEW_PATH),
            "hidden_path": str(UNMATCHED_HIDDEN_PATH),
        },
        "central_question_status": (
            "The population contains measurable orthographic and exact token-containment "
            "representation gaps, but ground truth is absent; genuine Itqan absence versus "
            "same-person alternative representation remains unresolved until diagnostic review."
        ),
        "prohibited_work_not_performed": [
            "resolver tier changes", "automatic fuzzy resolution", "weighted scoring",
            "ML/LLM identity adjudication", "final narrator map", "graph construction",
        ],
        "decision": "ENTITY-RESOLUTION GATE CLOSED",
    }
    audit["output_artifacts"] = {
        path.name: {
            "path": str(path), "format": file_format, "rows": rows,
            "sha256": file_sha256(path), "version": MILESTONE_VERSION,
            "generator_script_sha256": audit["inputs"]["script_sha256"],
        }
        for path, rows, file_format in artifact_specs
    }
    write_json(AUDIT_PATH, audit)

    if file_sha256(BASE_CANDIDATES) != base_hash_before:
        raise RuntimeError("Base candidate artifact changed during diagnostic run")
    if file_sha256(FROZEN_REVIEW_117) != review_117_hash_before:
        raise RuntimeError("Existing frozen 117-row review changed during diagnostic run")

    print("Narrator unmatched-name diagnostic")
    print(f"Frozen auto-resolved       : {len(auto_records)}")
    print(f"Frozen unmatched           : {len(unmatched)}")
    print(f"Failure strata             : {len(strata)}")
    print(f"Census review rows         : {len(census_visible)} ({census_status['action']})")
    print(f"Unmatched review rows      : {len(unmatched_visible)} ({unmatched_status['action']})")
    print(f"Audit                      : {AUDIT_PATH}")
    print("ENTITY-RESOLUTION GATE CLOSED")


if __name__ == "__main__":
    main()
