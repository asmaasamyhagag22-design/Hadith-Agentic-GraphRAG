"""Calibrate what evidence could identify one historical narrator.

This module measures evidence.  It does not resolve identities.  No
`HistoricalNarrator` is created, no profile is merged, no MIS tier is changed,
and no grade is aggregated.

Three units stay distinct throughout:

* a namespaced source record,
* an Itqan profile (a generated record key), and
* a historical person (which has no canonical layer in this data).

The calibration is deliberately interpretable: no weighted score, no learned
model, no embedding similarity, and no LLM adjudication.  Every status is a
deterministic function of populated fields, and missing evidence stays
`UNKNOWN` rather than becoming a negative.

Because a false merge is far more expensive than an unresolved narrator, every
rule is measured by the damage it would do, never by the coverage it would add.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import ITQAN_DIR, PROCESSED_DIR
from audit_linkage_validation_identity import normalize_narrow_identity


EXPERT_REVIEW_PATH = PROCESSED_DIR / "historical_narrator_expert_review.csv"
DUPLICATION_CANDIDATES_PATH = PROCESSED_DIR / "itqan_profile_duplication_candidates.jsonl"
STRICT_TRIAGE_PATH = PROCESSED_DIR / "itqan_profile_duplication_strict_mechanical_triage.csv"
NARRATOR_81_PATH = PROCESSED_DIR / "narrator_81_target_data_risk.csv"
NARRATOR_890_PATH = PROCESSED_DIR / "narrator_890_target_data_risk.csv"

CALIBRATION_JSON = PROCESSED_DIR / "historical_identity_calibration.json"
CALIBRATION_CASES_CSV = PROCESSED_DIR / "historical_identity_calibration_cases.csv"
RULE_CANDIDATES_JSON = PROCESSED_DIR / "historical_identity_rule_candidates.json"

CALIBRATION_VERSION = "historical_identity_calibration_v1"

# `provenance.arsanad_id` equals the Itqan profile ID in every populated case,
# so it is row provenance and never an independent person key.  `global_id`
# and `provenance.kaggle_id` are two fields pointing at one Kaggle record.
NON_INDEPENDENT_NAMESPACES = {"arsanad:profile_row"}

# Reviewer columns stay blank.  The generator refuses to overwrite a filled one.
REVIEWER_COLUMNS = ("reviewer_verdict", "reviewer_notes")

CALIBRATION_COLUMNS = (
    "review_id",
    "source_review_id",
    "profile_a_id",
    "profile_b_id",
    "profile_a_name",
    "profile_b_name",
    "independent_evidence_count",
    "dependent_evidence_groups",
    "evidence_dependency_json",
    "shared_name_forms",
    "conflicting_name_forms",
    "death_evidence_a",
    "death_evidence_b",
    "death_relation",
    "kunya_relation",
    "nasab_relation",
    "city_relation",
    "tabaqa_generation_relation",
    "shared_teacher_count",
    "shared_student_count",
    "relational_evidence_state",
    "source_provenance_summary",
    "explicit_contradictions",
    "differing_fields",
    "unknown_fields",
    "chronology_check",
    "mechanical_status",
    "requires_domain_expert",
    "domain_expert_question",
    *REVIEWER_COLUMNS,
)

# ---------------------------------------------------------------------------
# evidence taxonomy — derived from the fields the corpus actually carries
# ---------------------------------------------------------------------------

EVIDENCE_TAXONOMY = {
    "A_IDENTITY_BEARING": {
        "definition": (
            "Evidence that could identify a historical person independently of "
            "the name representation being compared."
        ),
        "members": [],
        "measured_note": (
            "No field in Itqan v1.20 qualifies. `itqan_id` is a generated record "
            "key, `provenance.arsanad_id` equals it, classical `entry_id` is "
            "source-local, `gk_id` is assigned by Itqan's own fuzzy matching, and "
            "`unique_key` is derived from the name being compared."
        ),
    },
    "B_SUPPORTING": {
        "definition": (
            "Evidence compatible with one person but insufficient alone; it "
            "narrows candidates and never confirms identity."
        ),
        "members": [
            "full_name", "namings", "kunya", "nasab", "laqab", "city",
            "death", "tabaqat", "generation", "teachers", "students",
            "classical_sources",
        ],
    },
    "C_CONTRADICTING": {
        "definition": (
            "Evidence that blocks an automatic merge.  A contradiction is an "
            "explicit disagreement between two populated values, never an "
            "absence."
        ),
        "members": [
            "explicit_death_disagreement", "incompatible_generation",
            "incompatible_tabaqat", "relational_cycle",
        ],
    },
    "D_NON_INDEPENDENT": {
        "definition": (
            "Evidence that looks like several confirmations but descends from "
            "one record.  Counting it more than once manufactures confidence."
        ),
        "members": [
            "global_id == provenance.kaggle_id",
            "provenance.arsanad_id == itqan profile id",
            "classical grade mirrored into provenance.sources",
            "unique_key / uniqueness / confidence / id_score / id_flags "
            "(computed by Itqan from the same name evidence)",
            "all profile biography fields (no field-level source pointer exists)",
        ],
    },
    "E_UNKNOWN": {
        "definition": (
            "Missing evidence.  Never converted to FALSE and never treated as "
            "a difference."
        ),
        "members": ["any absent or empty field", "unavailable field-level provenance"],
    },
}


# ---------------------------------------------------------------------------
# refined future contract — described, deliberately not instantiated
# ---------------------------------------------------------------------------

HISTORICAL_NARRATOR_CONTRACT = {
    "instantiated": False,
    "layer": (
        "An identity layer above profiles. It never replaces an ItqanProfile, "
        "never replaces a source record, and never collapses a grade."
    ),
    "cardinality": (
        "one historical narrator -> many Itqan profiles -> many source records "
        "-> conflicting source-specific grading evidence, all preserved"
    ),
    "required_fields": {
        "historical_narrator_id": "opaque; never reuses an itqan_id",
        "canonical_display_name": "provenance-backed; display only, not a key",
        "identity_status": [
            "PROVISIONAL", "REVIEWED", "DOMAIN_EXPERT_CONFIRMED",
            "AMBIGUOUS", "QUARANTINED",
        ],
        "member_profile_assertions": (
            "per-profile membership carrying its own status, supporting and "
            "contradicting evidence IDs, and the review event that set it"
        ),
        "aliases": "raw name forms with provenance; never normalised away",
        "identity_evidence": "evidence records with dependency_group_id",
        "contradictions": "retained, never resolved by overwrite",
        "review_events": "append-only; who decided what, when, on what evidence",
        "provenance": "immutable links to source profiles and records",
    },
    "calibration_derived_requirements": [
        "every evidence item carries a dependency_group_id, because no field in "
        "v1.20 has field-level provenance and same-record evidence must never "
        "count twice",
        "membership is an assertion with its own status, not a foreign key, so a "
        "profile can be attached provisionally and detached without deletion",
        "singleton and unresolved narrators are valid terminal states; nothing "
        "forces a profile into a cluster",
        "a QUARANTINED state is required for profiles whose own record integrity "
        "is in doubt, distinct from AMBIGUOUS identity",
        "death evidence is a list of reported opinions with sources, never one "
        "canonical value",
    ],
    "forbidden": [
        "narrator.grade aggregation",
        "merged profile payloads",
        "deleting or rewriting source profiles",
        "forcing every profile into a cluster",
        "transitive identity propagation between narrators",
    ],
}


def filled(value):
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return str(value).strip().lower() not in {"", "-", "none", "null", "n/a", "غير معروف"}


def scalar_relation(first, second):
    """Three-state comparison of a descriptive field.

    Missing is UNKNOWN, never a difference.  A difference between two populated
    values is reported as `DIFFERENT`, not `CONTRADICTORY`: two records of one
    narrator may legitimately carry different kunya or nisba forms, and whether
    a given variation is incompatible is a rijal question rather than a string
    comparison.  Only death, which has parsed year intervals, can be called an
    explicit contradiction.
    """

    if not filled(first) or not filled(second):
        return "UNKNOWN"

    left = normalize_narrow_identity(str(first))
    right = normalize_narrow_identity(str(second))

    if not left or not right:
        return "UNKNOWN"

    return "CONSISTENT" if left == right else "DIFFERENT"


def death_relation(entry):
    """Classify reported death evidence for diagnostics only.

    Classical sources genuinely disagree about death years.  A gap is a
    data-quality signal and a merge blocker; it is never proof of two people.
    """

    if not entry:
        return "UNKNOWN"

    if entry.get("exact_equal_death_text"):
        return "SAME_REPORTED_DEATH"

    gap = entry.get("minimum_absolute_year_difference")

    if gap is None:
        return "UNKNOWN"

    if gap == 0:
        return "SAME_REPORTED_DEATH"
    if gap <= 5:
        return "SMALL_REPORTED_VARIATION"
    if gap <= 25:
        return "MATERIAL_REPORTED_VARIATION"

    return "EXTREME_REPORTED_VARIATION"


def evidence_dependency_groups(profile_evidence):
    """Group a profile's evidence by the record it descends from.

    Itqan v1.20 carries no field-level source pointer, so `full_name`, `death`,
    `kunya`, `nasab`, `city`, `tabaqat`, `generation`, `teachers` and
    `students` cannot be attributed to any particular record.  They therefore
    form a single group of unknown provenance rather than several independent
    confirmations.
    """

    groups = []

    for record in profile_evidence.get("source_records") or []:
        namespace = record.get("source_namespace")
        groups.append({
            "group_kind": "SOURCE_RECORD",
            "source_namespace": namespace,
            "source_record_id": record.get("source_record_id"),
            "field_paths": sorted(record.get("field_paths") or []),
            "independent": namespace not in NON_INDEPENDENT_NAMESPACES,
        })

    biography = sorted(
        field for field in
        ("full_name", "kunya", "nasab", "city", "death", "tabaqat",
         "generation", "teachers", "students", "namings")
        if filled(profile_evidence.get(field))
    )

    if biography:
        groups.append({
            "group_kind": "PROFILE_BIOGRAPHY",
            "source_namespace": "UNKNOWN_FIELD_LEVEL_PROVENANCE",
            "source_record_id": None,
            "field_paths": biography,
            "independent": False,
        })

    return groups


def independent_evidence(groups_a, groups_b):
    """Count corroborations that genuinely come from different records.

    Only source records survive, and only from namespaces that are not merely
    row provenance.  A biography group is never independent because its fields
    have no attributable origin.
    """

    def keys(groups):
        return {
            (group["source_namespace"], group["source_record_id"])
            for group in groups
            if group["independent"]
        }

    shared = keys(groups_a) & keys(groups_b)

    return {
        "independent_source_records_a": len(keys(groups_a)),
        "independent_source_records_b": len(keys(groups_b)),
        "shared_independent_source_records": len(shared),
        "shared_keys": sorted(f"{ns}:{rid}" for ns, rid in shared),
        "dependent_group_count": sum(
            1 for group in groups_a + groups_b if not group["independent"]
        ),
    }


def chronology_check(evidence_a, evidence_b, death_entry):
    """Mechanical impossibility only.

    Lifespans are never invented and a birth year is never inferred from a
    death year.  Absent an explicit generation or a relational cycle there is
    nothing a computer can call impossible.
    """

    a_id = str(evidence_a.get("itqan_profile_id"))
    b_id = str(evidence_b.get("itqan_profile_id"))

    teachers_a = {str(x) for x in (evidence_a.get("teachers") or [])}
    teachers_b = {str(x) for x in (evidence_b.get("teachers") or [])}

    if b_id in teachers_a and a_id in teachers_b:
        return "RELATIONAL_CYCLE_IMPOSSIBLE"

    generation = scalar_relation(
        evidence_a.get("generation"), evidence_b.get("generation")
    )

    if generation == "DIFFERENT":
        # Recorded as a difference only.  Ordering tabaqa names requires an
        # ordinal parser that does not exist here, so this is not called
        # impossible.
        return "DIFFERENT_GENERATION_NOT_ORDERED"

    if death_relation(death_entry) == "EXTREME_REPORTED_VARIATION":
        return "SUSPICIOUS_DEATH_SEPARATION_NOT_IMPOSSIBLE"

    return "NO_MECHANICAL_IMPOSSIBILITY_DETECTED"


def mechanical_status(relations, independence, chronology, unknown_count):
    """Assign a computer-safe status.

    `SAME_PERSON` and `DIFFERENT_PERSON` are never produced: no authoritative
    crosswalk exists in this data to justify either.
    """

    if chronology == "RELATIONAL_CYCLE_IMPOSSIBLE":
        return "MECHANICALLY_INCOMPATIBLE", False

    if relations.get("death") in ("EXTREME_REPORTED_VARIATION", "MATERIAL_REPORTED_VARIATION"):
        # An explicit numeric disagreement between parsed intervals.  Whether
        # that is two people or two accepted opinions about one is a rijal
        # question, not a database question.
        return "SOURCE_DATA_CONTRADICTION", True

    consistent = [field for field, state in relations.items() if state == "CONSISTENT"]
    differing = [field for field, state in relations.items() if state == "DIFFERENT"]

    if len(consistent) >= 3 and relations.get("death") == "SAME_REPORTED_DEATH" and not differing:
        # Everything populated agrees.  But all of it descends from one
        # unattributable biography, so this is compatibility, never confirmation.
        return "STRONGLY_COMPATIBLE_BUT_UNCONFIRMED", True

    if unknown_count >= 4 and not differing:
        return "INSUFFICIENT_EVIDENCE", False

    if differing:
        # Populated fields disagree without an explicit numeric contradiction:
        # exactly the variant-name question a specialist must answer.
        return "REQUIRES_DOMAIN_EXPERT", True

    if len(consistent) <= 1:
        return "INSUFFICIENT_EVIDENCE", False

    return "REQUIRES_DOMAIN_EXPERT", True


def domain_expert_question(status, relations):
    """State the question a rijal specialist would actually have to answer."""

    if status == "SOURCE_DATA_CONTRADICTION":
        if relations.get("death") in (
            "EXTREME_REPORTED_VARIATION", "MATERIAL_REPORTED_VARIATION"
        ):
            return (
                "Are these two accepted death opinions for one narrator, or two "
                "narrators sharing a name form?"
            )
        return "Do the disagreeing biographical fields describe one narrator?"

    if status == "STRONGLY_COMPATIBLE_BUT_UNCONFIRMED":
        return (
            "The records agree on every populated field. Is this one narrator "
            "recorded twice, or two narrators genuinely sharing name, kunya and "
            "death year?"
        )

    if status == "REQUIRES_DOMAIN_EXPERT":
        return "Does the abbreviated or variant name form refer to this narrator?"

    if status == "MECHANICALLY_INCOMPATIBLE":
        return "NONE — mechanically blocked, no expert time required"

    return "NONE — insufficient material for useful adjudication"


# ---------------------------------------------------------------------------
# blinded packet for future validation
# ---------------------------------------------------------------------------

# The 40-row calibration packet exposed `source_review_id`, and its Itqan
# profile IDs, both of which join straight into
# `itqan_profile_duplication_strict_mechanical_triage.csv` and its
# `assistant_mechanical_triage` column.  The label was never visible, but it
# was one join away.  Future packets carry an opaque ID and no join key at all.
IDENTIFIER_KEYS = {
    "itqan_profile_id", "profile_id", "profile_a_id", "profile_b_id",
    "itqan_profile_a_id", "itqan_profile_b_id", "group_id", "review_id",
    "source_review_id", "expert_review_id",
}

BLINDED_PACKET_CSV = PROCESSED_DIR / "historical_identity_expert_packet.csv"
BLINDED_PACKET_HIDDEN_CSV = PROCESSED_DIR / "historical_identity_expert_packet_hidden.csv"

# Recorded so the row order is reproducible and carries no signal.
BLINDED_PACKET_SEED = 20260830

BLINDED_VISIBLE_COLUMNS = (
    "opaque_review_id",
    "profile_a_evidence_json",
    "profile_b_evidence_json",
    "relevant_source_names_json",
    "source_specific_name_forms_json",
    "deaths_json",
    "kunyahs_json",
    "nasab_json",
    "teachers_students_json",
    "generation_tabaqa_json",
    "contradictions_json",
    "missing_information_json",
    "expert_verdict",
    "reviewer_notes",
)

BLINDED_HIDDEN_COLUMNS = (
    "opaque_review_id",
    "source_review_id",
    "itqan_profile_a_id",
    "itqan_profile_b_id",
    "mechanical_status",
    "requires_domain_expert",
)

# Anything the reviewer must not see, whether or not it is a join key.
LEAKING_COLUMNS = frozenset({
    "mechanical_status", "requires_domain_expert", "domain_expert_question",
    "assistant_mechanical_triage", "assistant_note", "rule_id", "status",
    "score", "confidence", "rank", "expected_answer", "stratum",
    "source_review_id", "itqan_profile_a_id", "itqan_profile_b_id",
})


def redact_identifiers(value):
    """Strip every join key from an evidence payload, at any depth."""

    if isinstance(value, dict):
        return {
            key: redact_identifiers(item)
            for key, item in value.items()
            if key not in IDENTIFIER_KEYS
        }

    if isinstance(value, list):
        return [redact_identifiers(item) for item in value]

    return value


def _redacted_json(raw):
    return json.dumps(redact_identifiers(json.loads(raw)), ensure_ascii=False, sort_keys=True)


def build_blinded_packet(expert_rows, calibrated, seed=BLINDED_PACKET_SEED):
    """Return (visible, hidden) rows for a future validation packet.

    The visible half carries an opaque ID, the evidence a specialist needs, and
    two blank reviewer columns.  It carries no profile ID, no source review ID,
    no mechanical status and no ordering signal.  The mapping lives only in the
    hidden half, which is never handed to the reviewer.
    """

    by_review = {row["review_id"]: row for row in calibrated}

    order = list(range(len(expert_rows)))
    random.Random(seed).shuffle(order)

    visible, hidden = [], []

    for position, index in enumerate(order, start=1):
        row = expert_rows[index]
        opaque = f"HIR-{position:06d}"
        diagnostic = by_review.get(row["expert_review_id"], {})

        visible.append({
            "opaque_review_id": opaque,
            "profile_a_evidence_json": _redacted_json(row["profile_a_full_evidence_json"]),
            "profile_b_evidence_json": _redacted_json(row["profile_b_full_evidence_json"]),
            "relevant_source_names_json": row["relevant_source_names_json"],
            "source_specific_name_forms_json": row["source_specific_name_forms_json"],
            "deaths_json": row["deaths_json"],
            "kunyahs_json": row["kunyahs_json"],
            "nasab_json": row["nasab_json"],
            "teachers_students_json": row["teachers_students_json"],
            "generation_tabaqa_json": row["generation_tabaqa_json"],
            "contradictions_json": _redacted_json(row["contradictions_json"]),
            "missing_information_json": row["missing_information_json"],
            "expert_verdict": "",
            "reviewer_notes": "",
        })

        hidden.append({
            "opaque_review_id": opaque,
            "source_review_id": row["source_review_id"],
            "itqan_profile_a_id": row["itqan_profile_a_id"],
            "itqan_profile_b_id": row["itqan_profile_b_id"],
            "mechanical_status": diagnostic.get("mechanical_status", ""),
            "requires_domain_expert": diagnostic.get("requires_domain_expert", ""),
        })

    return visible, hidden


def packet_leakage_report(visible_rows):
    """Name anything a reviewer could use to recover an automatic label."""

    columns = set(visible_rows[0]) if visible_rows else set()
    serialised = json.dumps(visible_rows, ensure_ascii=False)

    return {
        "leaking_columns_present": sorted(columns & LEAKING_COLUMNS),
        "identifier_keys_in_payloads": sorted(
            key for key in IDENTIFIER_KEYS if f'"{key}"' in serialised
        ),
        "reviewer_columns_blank": all(
            not row["expert_verdict"] and not row["reviewer_notes"]
            for row in visible_rows
        ),
        "residual_reidentification_vector": (
            "teacher/student profile-ID lists remain visible because they are "
            "evidence a specialist needs; recovering the pair from them would "
            "require corpus-wide matching, not a lookup"
        ),
    }


def load_expert_cases(path=EXPERT_REVIEW_PATH):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def calibrate_case(row):
    """Produce one structured diagnostic record.  No reviewer label is set."""

    evidence_a = json.loads(row["profile_a_full_evidence_json"])
    evidence_b = json.loads(row["profile_b_full_evidence_json"])
    contradictions = json.loads(row["contradictions_json"])
    missing = json.loads(row["missing_information_json"])

    deaths = contradictions.get("death_differences") or []
    death_entry = deaths[0] if deaths else None

    groups_a = evidence_dependency_groups(evidence_a)
    groups_b = evidence_dependency_groups(evidence_b)
    independence = independent_evidence(groups_a, groups_b)

    relations = {
        "name": scalar_relation(evidence_a.get("full_name"), evidence_b.get("full_name")),
        "kunya": scalar_relation(evidence_a.get("kunya"), evidence_b.get("kunya")),
        "nasab": scalar_relation(evidence_a.get("nasab"), evidence_b.get("nasab")),
        "city": scalar_relation(evidence_a.get("city"), evidence_b.get("city")),
        "tabaqat": scalar_relation(evidence_a.get("tabaqat"), evidence_b.get("tabaqat")),
        "generation": scalar_relation(evidence_a.get("generation"), evidence_b.get("generation")),
        "death": death_relation(death_entry),
    }

    teachers = {str(x) for x in (evidence_a.get("teachers") or [])} & \
               {str(x) for x in (evidence_b.get("teachers") or [])}
    students = {str(x) for x in (evidence_a.get("students") or [])} & \
               {str(x) for x in (evidence_b.get("students") or [])}

    has_relational = bool(
        (evidence_a.get("teachers") or evidence_a.get("students"))
        and (evidence_b.get("teachers") or evidence_b.get("students"))
    )

    relational_state = (
        "SHARED_NEIGHBOURHOOD" if (teachers or students)
        else "NO_OVERLAP_BOTH_POPULATED" if has_relational
        else "UNKNOWN"
    )

    chronology = chronology_check(evidence_a, evidence_b, death_entry)
    unknown_fields = sorted(field for field, state in relations.items() if state == "UNKNOWN")

    status, needs_expert = mechanical_status(
        relations, independence, chronology, len(unknown_fields)
    )

    # An explicit contradiction needs a mechanical check.  Only parsed death
    # intervals and relational cycles qualify; differing name forms do not.
    explicit = []

    if relations["death"] in ("MATERIAL_REPORTED_VARIATION", "EXTREME_REPORTED_VARIATION"):
        explicit.append(f"death={relations['death']}")

    if chronology == "RELATIONAL_CYCLE_IMPOSSIBLE":
        explicit.append("relational_cycle")

    differing = sorted(field for field, state in relations.items() if state == "DIFFERENT")

    provenance = Counter(
        group["source_namespace"] for group in groups_a + groups_b
    )

    return {
        "review_id": row["expert_review_id"],
        "source_review_id": row["source_review_id"],
        "profile_a_id": row["itqan_profile_a_id"],
        "profile_b_id": row["itqan_profile_b_id"],
        "profile_a_name": evidence_a.get("full_name") or "",
        "profile_b_name": evidence_b.get("full_name") or "",
        "independent_evidence_count": independence["shared_independent_source_records"],
        "dependent_evidence_groups": independence["dependent_group_count"],
        "evidence_dependency_json": json.dumps(
            {"profile_a": groups_a, "profile_b": groups_b, "independence": independence},
            ensure_ascii=False, sort_keys=True,
        ),
        "shared_name_forms": relations["name"] == "CONSISTENT",
        "conflicting_name_forms": relations["name"] == "CONTRADICTORY",
        "death_evidence_a": (death_entry or {}).get("profile_a_death") or "UNKNOWN",
        "death_evidence_b": (death_entry or {}).get("profile_b_death") or "UNKNOWN",
        "death_relation": relations["death"],
        "kunya_relation": relations["kunya"],
        "nasab_relation": relations["nasab"],
        "city_relation": relations["city"],
        "tabaqa_generation_relation": (
            f"tabaqat={relations['tabaqat']};generation={relations['generation']}"
        ),
        "shared_teacher_count": len(teachers),
        "shared_student_count": len(students),
        "relational_evidence_state": relational_state,
        "source_provenance_summary": json.dumps(dict(sorted(provenance.items())), ensure_ascii=False),
        "explicit_contradictions": ";".join(explicit) if explicit else "NONE",
        "differing_fields": ";".join(differing) if differing else "NONE",
        "unknown_fields": ";".join(unknown_fields) if unknown_fields else "NONE",
        "chronology_check": chronology,
        "mechanical_status": status,
        "requires_domain_expert": "YES" if needs_expert else "NO",
        "domain_expert_question": domain_expert_question(status, relations),
        "reviewer_verdict": "",
        "reviewer_notes": "",
    }


# ---------------------------------------------------------------------------
# rule candidates — research artifacts, not an executable resolver
# ---------------------------------------------------------------------------

def rule_definitions():
    """Every rule states what would have to be true, and what breaks it."""

    return [
        {
            "rule_id": "R-01",
            "description": (
                "Treat two profiles as one historical person when they share a "
                "stable upstream record key (kaggle:scholar_indx)."
            ),
            "evidence_required": ["shared upstream record key"],
            "independence_assumptions": [
                "the upstream key identifies a person, not a parsed record"
            ],
            "known_counterexamples": ["ITQ-DUP-0017"],
            "false_merge_risk": "HIGH",
            "abstention_behaviour": "abstains when no upstream key is shared",
            "status": "REJECTED",
            "rejection_reason": (
                "A shared source record proves one identifier was attached "
                "twice. ITQ-DUP-0017 attaches one classical entry to profiles "
                "whose deaths differ by 188 years."
            ),
        },
        {
            "rule_id": "R-02",
            "description": (
                "Treat two profiles as candidates for one person when every "
                "populated biographical field agrees and none contradicts."
            ),
            "evidence_required": [
                "equal narrow-normalized name", "equal reported death",
                "no contradictory kunya, nasab, city, tabaqat or generation",
            ],
            "independence_assumptions": [
                "NONE — the agreeing fields have no field-level provenance and "
                "may descend from one copied record"
            ],
            "known_counterexamples": [
                "1,569 groups audited as DISTINCT_PERSON_STRONGLY_SUPPORTED "
                "share an exact name representation"
            ],
            "false_merge_risk": "MEDIUM",
            "abstention_behaviour": "abstains on any contradiction or on missing death",
            "status": "NEEDS_MORE_EVIDENCE",
        },
        {
            "rule_id": "R-03",
            "description": (
                "Use Itqan's own identity fields (unique_key, uniqueness, "
                "confidence, id_score) as identity evidence."
            ),
            "evidence_required": ["equal unique_key"],
            "independence_assumptions": [
                "unique_key identifies a person independently of the name"
            ],
            "known_counterexamples": [
                "unique_key is name-derived; in 25.7% of name_unique profiles "
                "its name core does not match the profile's own full_name"
            ],
            "false_merge_risk": "HIGH",
            "abstention_behaviour": "n/a",
            "status": "REJECTED",
            "rejection_reason": (
                "Circular: computed from the same name evidence being compared, "
                "and demonstrably bound to a different name in a quarter of cases."
            ),
        },
        {
            "rule_id": "R-04",
            "description": (
                "Flag adjacent Itqan profile IDs carrying an identical name and "
                "identical reported death as a data-quality duplicate candidate."
            ),
            "evidence_required": [
                "|id_a - id_b| == 1", "equal name", "equal reported death"
            ],
            "independence_assumptions": [
                "adjacency reflects one insertion event, not a person claim"
            ],
            "known_counterexamples": [
                "adjacency is an artifact of build order and carries no "
                "historical meaning"
            ],
            "false_merge_risk": "LOW as a data-quality flag, HIGH if read as identity",
            "abstention_behaviour": "produces a review flag only, never an identity",
            "status": "SAFE_FOR_FURTHER_VALIDATION",
            "scope_note": (
                "This is a builder-integrity signal for investigation, not a "
                "historical-person claim."
            ),
        },
        {
            "rule_id": "R-05",
            "description": (
                "Treat an arsanad_restore stub whose populated fields all equal "
                "a classical profile as the same record restored twice."
            ),
            "evidence_required": [
                "one profile origin == arsanad_restore",
                "all fields populated on the stub agree with the classical profile",
            ],
            "independence_assumptions": [
                "the stub was derived from the classical record"
            ],
            "known_counterexamples": [
                "derivation direction is not recorded in v1.20"
            ],
            "false_merge_risk": "MEDIUM",
            "abstention_behaviour": "abstains when the stub contradicts any field",
            "status": "NEEDS_MORE_EVIDENCE",
        },
        {
            "rule_id": "R-06",
            "description": (
                "Use overlapping teacher/student neighbourhoods as supporting "
                "evidence for a candidate pair."
            ),
            "evidence_required": ["shared teacher or student profile references"],
            "independence_assumptions": [
                "the related profile IDs are themselves resolved identities"
            ],
            "known_counterexamples": [
                "related IDs are Itqan profile keys, which carry the same "
                "profile != person problem; using them recursively would "
                "propagate identity"
            ],
            "false_merge_risk": "HIGH if propagated, LOW as a single-hop signal",
            "abstention_behaviour": "supporting only; never sufficient alone",
            "status": "DOMAIN_EXPERT_REQUIRED",
            "scope_note": "Single-hop only. No bootstrapping, no transitive closure.",
        },
        {
            "rule_id": "R-07",
            "description": (
                "Treat exact narrow-normalized name equality alone as identity."
            ),
            "evidence_required": ["equal narrow-normalized canonical name"],
            "independence_assumptions": ["names are unique across narrators"],
            "known_counterexamples": [
                "9,631 duplicate canonical-name groups; classical Arabic "
                "onomastics reuse the same name across generations"
            ],
            "false_merge_risk": "SEVERE",
            "abstention_behaviour": "none — it never abstains",
            "status": "REJECTED",
            "rejection_reason": (
                "This is the collision driver the whole audit exists to avoid."
            ),
        },
    ]


def evaluate_rule_safety(rule_id, groups):
    """Measure what a rule would touch across known failure populations.

    These are proxy safety counts, not precision: no adjudicated historical
    identity labels exist, so no accuracy figure can be computed.
    """

    if rule_id in RULES_NOT_TESTABLE_ON_GROUPS:
        return {
            "rule_id": rule_id,
            "tested_on_group_population": False,
            "not_tested_reason": RULES_NOT_TESTABLE_ON_GROUPS[rule_id],
            "measurement_kind": "NOT_MEASURED_ON_THIS_POPULATION",
        }

    triggered = 0
    by_class = Counter()
    with_contradiction = 0

    for group in groups:
        if not rule_triggers(rule_id, group):
            continue
        triggered += 1
        by_class[group["conceptual_class"]] += 1
        if (group.get("contradictions") or {}).get("contradictory_pair_count"):
            with_contradiction += 1

    return {
        "rule_id": rule_id,
        "tested_on_group_population": True,
        "groups_triggered": triggered,
        "groups_abstained": len(groups) - triggered,
        "abstention_rate": round((len(groups) - triggered) / len(groups), 6) if groups else None,
        "triggered_on_strongly_distinct_sets": by_class.get("DISTINCT_PERSON_STRONGLY_SUPPORTED", 0),
        "triggered_on_strongly_duplicate_sets": by_class.get("DUPLICATE_PROFILE_STRONGLY_SUPPORTED", 0),
        "triggered_on_unresolved_sets": by_class.get("UNRESOLVED_PROFILE_MULTIPLICITY", 0),
        "triggered_on_groups_with_contradiction": with_contradiction,
        "measurement_kind": "PROXY_SAFETY_EXPOSURE_NOT_PRECISION",
    }


# A rule whose evidence is absent from the audited group payload cannot be
# exercised here.  Reporting it as "0 triggered" would read as "safe", so it is
# reported as untested instead.
RULES_NOT_TESTABLE_ON_GROUPS = {
    "R-03": (
        "unique_key / uniqueness / id_score are not carried in the duplication "
        "group payload; the rule was measured directly against the profile "
        "corpus instead."
    ),
}

NAME_GROUPINGS = ("NARROW_CANONICAL_NAME", "NARROW_EXACT_REPRESENTATION")


def _profile_origins(group):
    return {
        (profile.get("upstream_source_identifiers") or {}).get("origin")
        for profile in group.get("profiles") or []
    }


def _has_adjacent_ids(group):
    numeric = sorted(
        int(value) for value in group.get("itqan_profile_ids") or []
        if str(value).isdigit()
    )
    return any(second - first == 1 for first, second in zip(numeric, numeric[1:]))


def rule_triggers(rule_id, group):
    """Deterministic trigger predicate for a candidate rule on a group."""

    evidence = group.get("evidence") or {}
    contradictions = group.get("contradictions") or {}
    profiles = group.get("profiles") or []

    if rule_id == "R-01":
        return bool(evidence.get("shared_upstream_record_keys"))

    if rule_id == "R-02":
        if contradictions.get("contradictory_pair_count"):
            return False
        return bool(evidence.get("shared_death_values")) and \
            group.get("grouping_kind") in NAME_GROUPINGS

    if rule_id == "R-04":
        if not _has_adjacent_ids(group):
            return False
        names = {profile.get("normalized_canonical_name") for profile in profiles}
        deaths = {profile.get("death") for profile in profiles}
        return len(names) == 1 and len(deaths) == 1 and all(
            filled(death) for death in deaths
        )

    if rule_id == "R-05":
        if "arsanad_restore" not in _profile_origins(group):
            return False
        if contradictions.get("contradictory_pair_count"):
            return False
        names = {profile.get("normalized_canonical_name") for profile in profiles}
        return len(names) == 1

    if rule_id == "R-06":
        return bool(evidence.get("shared_teacher_profile_references")) or \
            bool(evidence.get("shared_student_profile_references"))

    if rule_id == "R-07":
        return group.get("grouping_kind") in NAME_GROUPINGS

    return False


def load_duplication_groups(path=DUPLICATION_CANDIDATES_PATH):
    groups = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                groups.append(json.loads(line))
    return groups


def _read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_rows(path, columns, rows, guard=()):
    """Write a CSV, refusing to discard any reviewer work already in it."""

    if guard and Path(path).exists():
        for existing in _read_csv(path):
            if any(existing.get(column, "").strip() for column in guard):
                raise SystemExit(
                    f"{Path(path).name} already contains reviewer verdicts; "
                    f"refusing to overwrite adjudicated work."
                )

    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_calibration_cases(rows, path=CALIBRATION_CASES_CSV):
    """Write the case artifact, refusing to discard reviewer work."""

    if Path(path).exists():
        for existing in _read_csv(path):
            if any(existing.get(column, "").strip() for column in REVIEWER_COLUMNS):
                raise SystemExit(
                    f"{Path(path).name} already contains reviewer verdicts; "
                    f"refusing to overwrite adjudicated work."
                )

    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CALIBRATION_COLUMNS))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in CALIBRATION_COLUMNS})


def main():
    cases = [calibrate_case(row) for row in load_expert_cases()]
    groups = load_duplication_groups()

    rules = rule_definitions()
    safety = {
        rule["rule_id"]: evaluate_rule_safety(rule["rule_id"], groups)
        for rule in rules
    }

    write_calibration_cases(cases)

    visible, hidden = build_blinded_packet(load_expert_cases(), cases)
    leakage = packet_leakage_report(visible)

    if leakage["leaking_columns_present"] or leakage["identifier_keys_in_payloads"]:
        raise SystemExit(f"blinded packet would leak: {leakage}")

    _write_rows(BLINDED_PACKET_CSV, BLINDED_VISIBLE_COLUMNS, visible, guard=REVIEWER_COLUMNS[:1] + ("reviewer_notes",))
    _write_rows(BLINDED_PACKET_HIDDEN_CSV, BLINDED_HIDDEN_COLUMNS, hidden)

    risk_81 = _read_csv(NARRATOR_81_PATH)
    risk_890 = _read_csv(NARRATOR_890_PATH)

    def risk_distribution(rows):
        return dict(sorted(Counter(row["data_quality_risk_class"] for row in rows).items()))

    calibration = {
        "calibration_version": CALIBRATION_VERSION,
        "central_rule": "source record != Itqan profile != historical person",
        "objective": "minimise false historical-person merges; abstention preferred",
        "inputs": {
            "historical_narrator_expert_review.csv": {
                "rows": len(cases),
                "sha256": file_sha256(EXPERT_REVIEW_PATH),
            },
            "itqan_profile_duplication_candidates.jsonl": {
                "groups": len(groups),
                "sha256": file_sha256(DUPLICATION_CANDIDATES_PATH),
            },
        },
        "evidence_taxonomy": EVIDENCE_TAXONOMY,
        "identity_bearing_evidence_found": False,
        "positive_anchor": {
            "searched": [
                "shared unique_key", "shared gk_id", "shared kaggle scholar_indx",
                "explicit cross-reference field",
            ],
            "found": False,
            "conclusion": "NO GOLD-STANDARD POSITIVE IDENTITY ANCHOR FOUND",
        },
        "mechanical_status_distribution": dict(sorted(
            Counter(case["mechanical_status"] for case in cases).items()
        )),
        "domain_expert_required": sum(
            1 for case in cases if case["requires_domain_expert"] == "YES"
        ),
        "death_relation_distribution": dict(sorted(
            Counter(case["death_relation"] for case in cases).items()
        )),
        "chronology_distribution": dict(sorted(
            Counter(case["chronology_check"] for case in cases).items()
        )),
        "independent_evidence": {
            "cases_with_shared_independent_source_record": sum(
                1 for case in cases if case["independent_evidence_count"] > 0
            ),
            "field_level_provenance_available": False,
            "independence_claim": "UNKNOWN for every profile biography field",
        },
        "historical_narrator_contract": HISTORICAL_NARRATOR_CONTRACT,
        "expert_packet_blinding": {
            "visible_artifact": BLINDED_PACKET_CSV.name,
            "hidden_mapping_artifact": BLINDED_PACKET_HIDDEN_CSV.name,
            "opaque_id_format": "HIR-000001",
            "shuffle_seed": BLINDED_PACKET_SEED,
            "previous_packet_weakness": (
                "the 40-row calibration packet exposed source_review_id and "
                "Itqan profile IDs, either of which joins to "
                "assistant_mechanical_triage in one step"
            ),
            "leakage_report": leakage,
        },
        "rule_safety": safety,
        "impact_on_frozen_81": risk_distribution(risk_81),
        "impact_on_short_name_890": risk_distribution(risk_890),
        "mutations": {
            "historical_narrator_instances": 0,
            "itqan_profiles": 0,
            "mis_tiers": 0,
            "source_attachments": 0,
            "grades_aggregated": 0,
            "reviewer_fields": 0,
        },
        "prohibited_outputs_not_created": [
            "historical_narrator_map.json", "merged_itqan_profiles.json",
        ],
        "gate_decision": "ENTITY-RESOLUTION GATE CLOSED",
    }

    with open(CALIBRATION_JSON, "w", encoding="utf-8") as handle:
        json.dump(calibration, handle, ensure_ascii=False, indent=1, sort_keys=True)

    with open(RULE_CANDIDATES_JSON, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "calibration_version": CALIBRATION_VERSION,
                "artifact_kind": "RESEARCH_RULE_CANDIDATES_NOT_A_RESOLVER",
                "no_rule_is_production": True,
                "rules": [{**rule, "safety": safety[rule["rule_id"]]} for rule in rules],
            },
            handle, ensure_ascii=False, indent=1, sort_keys=True,
        )

    print(f"cases calibrated        : {len(cases)}")
    for status, count in calibration["mechanical_status_distribution"].items():
        print(f"   {status:<38} {count}")
    print(f"domain expert required  : {calibration['domain_expert_required']}")
    print(f"positive anchor found   : {calibration['positive_anchor']['found']}")
    print(f"\nrule safety over {len(groups)} audited groups:")
    for rule in rules:
        entry = safety[rule["rule_id"]]
        if not entry.get("tested_on_group_population"):
            print(f"   {rule['rule_id']} {rule['status']:<28} NOT TESTED on this population")
            continue
        print(
            f"   {rule['rule_id']} {rule['status']:<28} "
            f"triggered={entry['groups_triggered']:<6} "
            f"on_strongly_distinct={entry['triggered_on_strongly_distinct_sets']:<5} "
            f"abstention={entry['abstention_rate']}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
