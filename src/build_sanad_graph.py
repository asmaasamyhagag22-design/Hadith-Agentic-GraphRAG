"""Build the deterministic MIS sanad chain graph.

This is the chain layer only: MIS hadiths, their isnads, the MIS narrators, and
the ordered transmission steps between them.  No Itqan profile, source record,
grading, candidate identity link or historical-person layer is created here, and
the build refuses to finish if any of those appear.

Everything is read from the frozen MIS workbooks and written to a gitignored
SQLite file.  SQLite is used for its constraints rather than for SQL: the
invariants that matter — unique keys, valid endpoints, one isnad per hadith,
unique position within a chain — are enforced by the database, not by tests
alone.

The identity a chain carries is *MIS narrator identity*.  It is not a canonical
historical-person identity, and nothing here should be read as one.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import openpyxl

from config import PROCESSED_DIR
from profile_mis import CONTENT, EDGES, NODES

SCHEMA_VERSION = "sanad_chain_v1"
BUILDER_VERSION = "build_sanad_graph_v1"

GRAPH_DB_PATH = PROCESSED_DIR / "sanad_graph.sqlite"
MANIFEST_PATH = PROCESSED_DIR / "sanad_graph_manifest.json"

# B2-H0001-C01-U01-S01-i1 — book, hadith, chapter, unit, sanad, position.
LABEL = re.compile(
    r"^B(?P<book>\d+)-H(?P<hadith>\d+)-C(?P<chapter>\d+)"
    r"-U(?P<unit>\d+)-S(?P<sanad>\d+)-i(?P<position>\d+)$"
)

# Tables that must not exist in the chain layer.  Guarded so entity-resolution
# work cannot leak into the graph without the build failing loudly.
FORBIDDEN_TABLES = (
    "itqan_profile", "source_record", "historical_narrator",
    "candidate_profile", "grading", "narrator_grade",
)

DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE mis_narrator (
    narrator_id     TEXT PRIMARY KEY NOT NULL,
    label           TEXT,
    name_ar         TEXT NOT NULL,
    name_ar_mapped  TEXT,
    name_en_mapped  TEXT,
    gender          TEXT,
    generation      TEXT,
    CHECK (length(narrator_id) > 0),
    CHECK (length(name_ar) > 0)
);

CREATE TABLE mis_hadith (
    book_no                     TEXT NOT NULL,
    hadith_no                   TEXT NOT NULL,
    chapter_no                  TEXT NOT NULL,
    unit_no                     TEXT NOT NULL,
    book_title                  TEXT,
    chapter_title_ar            TEXT,
    chapter_title_en            TEXT,
    unit_title_ar               TEXT,
    declared_sanad_count        INTEGER NOT NULL,
    declared_sanad_narrators    TEXT,
    PRIMARY KEY (book_no, hadith_no),
    CHECK (declared_sanad_count >= 0)
);

CREATE TABLE isnad (
    book_no         TEXT NOT NULL,
    hadith_no       TEXT NOT NULL,
    sanad_no        TEXT NOT NULL,
    step_count      INTEGER NOT NULL,
    narrator_count  INTEGER NOT NULL,
    PRIMARY KEY (book_no, hadith_no, sanad_no),
    FOREIGN KEY (book_no, hadith_no)
        REFERENCES mis_hadith (book_no, hadith_no),
    CHECK (step_count >= 1),
    CHECK (narrator_count = step_count + 1)
);

CREATE TABLE transmission (
    book_no             TEXT NOT NULL,
    hadith_no           TEXT NOT NULL,
    sanad_no            TEXT NOT NULL,
    position            INTEGER NOT NULL,
    from_narrator_id    TEXT NOT NULL,
    to_narrator_id      TEXT NOT NULL,
    source_label        TEXT NOT NULL UNIQUE,
    PRIMARY KEY (book_no, hadith_no, sanad_no, position),
    FOREIGN KEY (book_no, hadith_no, sanad_no)
        REFERENCES isnad (book_no, hadith_no, sanad_no),
    FOREIGN KEY (from_narrator_id) REFERENCES mis_narrator (narrator_id),
    FOREIGN KEY (to_narrator_id)   REFERENCES mis_narrator (narrator_id),
    CHECK (position >= 1)
);

CREATE INDEX idx_transmission_from ON transmission (from_narrator_id);
CREATE INDEX idx_transmission_to   ON transmission (to_narrator_id);
CREATE INDEX idx_isnad_hadith      ON isnad (book_no, hadith_no);
"""


def text(value):
    """Normalise a spreadsheet cell to a stable string, or None when empty."""

    if value is None:
        return None

    stripped = str(value).strip()

    return stripped or None


def read_sheet(path):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        worksheet = workbook[workbook.sheetnames[0]]
        rows = worksheet.iter_rows(values_only=True)
        header = list(next(rows))
        return [
            dict(zip(header, row))
            for row in rows
            if any(cell is not None for cell in row)
        ]
    finally:
        workbook.close()


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_label(value):
    """Split an intractionLabel, refusing anything that does not match."""

    match = LABEL.match(str(value).strip())

    if not match:
        raise ValueError(f"Unparseable MIS interaction label: {value!r}")

    return match.groupdict()


# ---------------------------------------------------------------------------
# source -> rows
# ---------------------------------------------------------------------------

def narrator_rows(nodes):
    rows = []

    for node in nodes:
        narrator_id = text(node.get("NarratorID_Mapped"))
        name_ar = text(node.get("NarratorNameAr"))

        if not narrator_id or not name_ar:
            raise ValueError(f"MIS narrator node missing id or name: {node!r}")

        rows.append((
            narrator_id,
            text(node.get("Label")),
            name_ar,
            text(node.get("NarratorNameAr-Mapped")),
            text(node.get("NarratorNameEn-Mapped")),
            text(node.get("Gender")),
            text(node.get("NarratorGeneration")),
        ))

    return sorted(rows)


def hadith_rows(content):
    rows = []

    for record in content:
        book_no = text(record.get("BookNo"))
        hadith_no = text(record.get("HadithNo"))
        chapter_no = text(record.get("ChapterNo"))
        unit_no = text(record.get("UnitNo"))
        declared = text(record.get("SanadCount"))

        if not all((book_no, hadith_no, chapter_no, unit_no, declared)):
            raise ValueError(f"MIS hadith missing source identity: {record!r}")

        rows.append((
            book_no,
            hadith_no,
            chapter_no,
            unit_no,
            text(record.get("BookTitleEnAr")),
            text(record.get("ChapterTitleAr")),
            text(record.get("ChapterTitleEn")),
            text(record.get("UnitTitleAr")),
            int(declared),
            text(record.get("SanadWithNarratorsCount")),
        ))

    return sorted(rows)


def transmission_rows(edges):
    """One row per MIS edge, keyed by its chain and position."""

    rows = []

    for edge in edges:
        parsed = parse_label(edge.get("intractionLabel"))

        book_no = text(edge.get("BookNo"))
        hadith_no = text(edge.get("HadithNo"))
        sanad_no = text(edge.get("SanadNo"))
        from_id = text(edge.get("sourceNarratorID"))
        to_id = text(edge.get("targetNarratorID"))

        if not all((book_no, hadith_no, sanad_no, from_id, to_id)):
            raise ValueError(f"MIS edge missing source identity: {edge!r}")

        # The label repeats the chain coordinates; disagreement means the
        # source is internally inconsistent and must not be silently accepted.
        if parsed["sanad"].lstrip("0") != sanad_no.lstrip("0"):
            raise ValueError(
                f"Label sanad {parsed['sanad']} disagrees with SanadNo "
                f"{sanad_no} in {edge.get('intractionLabel')!r}"
            )

        rows.append((
            book_no,
            hadith_no,
            sanad_no,
            int(parsed["position"]),
            from_id,
            to_id,
            str(edge.get("intractionLabel")).strip(),
        ))

    return sorted(rows, key=lambda row: (row[0], row[1], row[2], row[3]))


def isnad_rows(transmissions):
    """Derive one isnad per distinct chain, with its measured step count."""

    steps = defaultdict(list)

    for row in transmissions:
        steps[(row[0], row[1], row[2])].append(row[3])

    rows = []

    for key, positions in steps.items():
        ordered = sorted(positions)

        if ordered != list(range(1, len(ordered) + 1)):
            raise ValueError(f"Chain {key} has a non-contiguous order: {ordered}")

        rows.append((*key, len(ordered), len(ordered) + 1))

    return sorted(rows)


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def connect(db_path):
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def build(db_path, nodes=None, content=None, edges=None):
    """Create and populate the chain graph.  Returns the row counts."""

    nodes = read_sheet(NODES) if nodes is None else nodes
    content = read_sheet(CONTENT) if content is None else content
    edges = read_sheet(EDGES) if edges is None else edges

    narrators = narrator_rows(nodes)
    hadiths = hadith_rows(content)
    transmissions = transmission_rows(edges)
    isnads = isnad_rows(transmissions)

    path = Path(db_path)

    if path.exists():
        path.unlink()

    path.parent.mkdir(parents=True, exist_ok=True)

    connection = connect(path)

    try:
        connection.executescript(DDL)

        connection.executemany(
            "INSERT INTO mis_narrator VALUES (?,?,?,?,?,?,?)", narrators
        )
        connection.executemany(
            "INSERT INTO mis_hadith VALUES (?,?,?,?,?,?,?,?,?,?)", hadiths
        )
        connection.executemany(
            "INSERT INTO isnad VALUES (?,?,?,?,?)", isnads
        )
        connection.executemany(
            "INSERT INTO transmission VALUES (?,?,?,?,?,?,?)", transmissions
        )

        connection.commit()

        violations = connection.execute("PRAGMA foreign_key_check").fetchall()

        if violations:
            raise ValueError(f"Foreign key violations after build: {violations[:5]}")

        assert_chain_layer_only(connection)
    finally:
        connection.close()

    return {
        "mis_narrator": len(narrators),
        "mis_hadith": len(hadiths),
        "isnad": len(isnads),
        "transmission": len(transmissions),
    }


def assert_chain_layer_only(connection):
    """Fail if anything beyond the chain layer reached the database."""

    tables = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }

    leaked = tables & set(FORBIDDEN_TABLES)

    if leaked:
        raise ValueError(f"Chain layer must not contain {sorted(leaked)}")

    return sorted(tables)


# ---------------------------------------------------------------------------
# canonical identity
# ---------------------------------------------------------------------------

CANONICAL_QUERIES = (
    ("mis_narrator",
     "SELECT narrator_id, label, name_ar, name_ar_mapped, name_en_mapped, "
     "gender, generation FROM mis_narrator ORDER BY narrator_id"),
    ("mis_hadith",
     "SELECT book_no, hadith_no, chapter_no, unit_no, book_title, "
     "chapter_title_ar, chapter_title_en, unit_title_ar, declared_sanad_count, "
     "declared_sanad_narrators FROM mis_hadith ORDER BY book_no, hadith_no"),
    ("isnad",
     "SELECT book_no, hadith_no, sanad_no, step_count, narrator_count "
     "FROM isnad ORDER BY book_no, hadith_no, sanad_no"),
    ("transmission",
     "SELECT book_no, hadith_no, sanad_no, position, from_narrator_id, "
     "to_narrator_id, source_label FROM transmission "
     "ORDER BY book_no, hadith_no, sanad_no, position"),
)


def canonical_hash(connection):
    """Hash the logical contents, not the SQLite file.

    The file format carries page layout and other non-semantic variation, so
    two correct builds need not be byte-identical.  This hashes ordered rows
    plus the schema, which is what "the same graph" actually means.
    """

    digest = hashlib.sha256()

    schema = connection.execute(
        "SELECT type, name, sql FROM sqlite_master ORDER BY type, name"
    ).fetchall()

    digest.update(json.dumps(schema, ensure_ascii=False, sort_keys=True).encode("utf-8"))

    for table, query in CANONICAL_QUERIES:
        digest.update(f"\n#{table}\n".encode("utf-8"))
        for row in connection.execute(query):
            digest.update(json.dumps(row, ensure_ascii=False).encode("utf-8"))
            digest.update(b"\n")

    return digest.hexdigest()


# ---------------------------------------------------------------------------
# fidelity verification against the source
# ---------------------------------------------------------------------------

def source_chains(edges):
    """Rebuild ordered chains straight from the workbook, for comparison."""

    chains = defaultdict(list)

    for edge in edges:
        parsed = parse_label(edge.get("intractionLabel"))
        key = (text(edge["BookNo"]), text(edge["HadithNo"]), text(edge["SanadNo"]))
        chains[key].append((
            int(parsed["position"]),
            text(edge["sourceNarratorID"]),
            text(edge["targetNarratorID"]),
        ))

    return {key: sorted(steps) for key, steps in chains.items()}


def stored_chains(connection):
    chains = defaultdict(list)

    for row in connection.execute(
        "SELECT book_no, hadith_no, sanad_no, position, from_narrator_id, "
        "to_narrator_id FROM transmission "
        "ORDER BY book_no, hadith_no, sanad_no, position"
    ):
        chains[(row[0], row[1], row[2])].append((row[3], row[4], row[5]))

    return dict(chains)


def verify_chain_fidelity(connection, edges):
    """Compare every reconstructed chain against the source, step by step."""

    expected = source_chains(edges)
    actual = stored_chains(connection)

    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    mismatched = sorted(
        key for key in set(expected) & set(actual)
        if expected[key] != actual[key]
    )

    return {
        "source_chains": len(expected),
        "stored_chains": len(actual),
        "exact_matches": len(set(expected) & set(actual)) - len(mismatched),
        "mismatches": len(mismatched),
        "missing": len(missing),
        "extra": len(extra),
        "examples": {
            "mismatched": mismatched[:3],
            "missing": missing[:3],
            "extra": extra[:3],
        },
    }


def verify_sanad_counts(connection):
    """Declared SanadCount must equal the number of stored isnads."""

    rows = connection.execute(
        "SELECT h.book_no, h.hadith_no, h.declared_sanad_count, "
        "       (SELECT COUNT(*) FROM isnad i "
        "        WHERE i.book_no = h.book_no AND i.hadith_no = h.hadith_no) "
        "FROM mis_hadith h ORDER BY h.book_no, h.hadith_no"
    ).fetchall()

    mismatches = [row for row in rows if row[2] != row[3]]

    return {
        "hadiths_checked": len(rows),
        "mismatches": len(mismatches),
        "examples": mismatches[:3],
    }


def verify_edge_fidelity(connection, edges):
    stored = connection.execute("SELECT COUNT(*) FROM transmission").fetchone()[0]
    labels = connection.execute(
        "SELECT COUNT(DISTINCT source_label) FROM transmission"
    ).fetchone()[0]

    return {
        "source_edges": len(edges),
        "stored_transmissions": stored,
        "distinct_source_labels": labels,
        "counts_match": stored == len(edges) == labels,
    }


def verify_structure(connection):
    """Structural invariants the schema cannot express as constraints."""

    dangling_from = connection.execute(
        "SELECT COUNT(*) FROM transmission t LEFT JOIN mis_narrator n "
        "ON t.from_narrator_id = n.narrator_id WHERE n.narrator_id IS NULL"
    ).fetchone()[0]

    dangling_to = connection.execute(
        "SELECT COUNT(*) FROM transmission t LEFT JOIN mis_narrator n "
        "ON t.to_narrator_id = n.narrator_id WHERE n.narrator_id IS NULL"
    ).fetchone()[0]

    orphan_isnads = connection.execute(
        "SELECT COUNT(*) FROM isnad i LEFT JOIN mis_hadith h "
        "ON i.book_no = h.book_no AND i.hadith_no = h.hadith_no "
        "WHERE h.hadith_no IS NULL"
    ).fetchone()[0]

    broken = 0
    for steps in stored_chains(connection).values():
        for first, second in zip(steps, steps[1:]):
            if first[2] != second[1]:
                broken += 1

    unused = connection.execute(
        "SELECT COUNT(*) FROM mis_narrator n WHERE NOT EXISTS ("
        "  SELECT 1 FROM transmission t WHERE t.from_narrator_id = n.narrator_id"
        "     OR t.to_narrator_id = n.narrator_id)"
    ).fetchone()[0]

    return {
        "dangling_from_narrator": dangling_from,
        "dangling_to_narrator": dangling_to,
        "isnads_without_hadith": orphan_isnads,
        "broken_chain_transitions": broken,
        "narrators_unused_by_any_edge": unused,
    }


def generation_direction_report(connection):
    """Measure, do not enforce.

    MIS records `source -> target` as teacher -> student.  Generation labels
    agree overwhelmingly, but not universally: a small number of steps run from
    a later generation to an earlier one.  An elder narrating from a junior is a
    recognised occurrence in transmission, so these are preserved as recorded
    rather than corrected.
    """

    rank = {
        "Comp.(RA)": 0,
        "Follower(Tabi')": 1,
        "Succ. (Taba' Tabi')": 2,
        "3rd Century AH": 3,
    }

    counts = Counter()

    for from_gen, to_gen in connection.execute(
        "SELECT f.generation, t2.generation FROM transmission t "
        "JOIN mis_narrator f  ON f.narrator_id  = t.from_narrator_id "
        "JOIN mis_narrator t2 ON t2.narrator_id = t.to_narrator_id"
    ):
        first, second = rank.get(from_gen), rank.get(to_gen)

        if first is None or second is None:
            counts["unranked"] += 1
        elif first < second:
            counts["earlier_to_later"] += 1
        elif first == second:
            counts["same_generation"] += 1
        else:
            counts["later_to_earlier"] += 1

    return dict(counts)


def main():
    nodes = read_sheet(NODES)
    content = read_sheet(CONTENT)
    edges = read_sheet(EDGES)

    counts = build(GRAPH_DB_PATH, nodes, content, edges)

    connection = connect(GRAPH_DB_PATH)

    try:
        chain = verify_chain_fidelity(connection, edges)
        sanad = verify_sanad_counts(connection)
        edge = verify_edge_fidelity(connection, edges)
        structure = verify_structure(connection)
        direction = generation_direction_report(connection)
        digest = canonical_hash(connection)
        tables = assert_chain_layer_only(connection)
    finally:
        connection.close()

    passed = (
        chain["mismatches"] == 0 and chain["missing"] == 0 and chain["extra"] == 0
        and sanad["mismatches"] == 0
        and edge["counts_match"]
        and structure["dangling_from_narrator"] == 0
        and structure["dangling_to_narrator"] == 0
        and structure["isnads_without_hadith"] == 0
        and structure["broken_chain_transitions"] == 0
    )

    manifest = {
        "canonical": {
            "schema_version": SCHEMA_VERSION,
            "builder_version": BUILDER_VERSION,
            "canonical_graph_sha256": digest,
            "row_counts": counts,
            "source_files": {
                path.name: file_sha256(path) for path in (NODES, CONTENT, EDGES)
            },
            "tables": tables,
        },
        "verification": {
            "chain_fidelity": chain,
            "sanad_count_fidelity": sanad,
            "edge_fidelity": edge,
            "structure": structure,
            "generation_direction": direction,
            "acceptance": "PASS" if passed else "FAIL",
        },
        "scope": {
            "layer": "MIS chain layer only",
            "identity_semantics": "MIS narrator identity, not historical person",
            "itqan_attached": False,
            "historical_narrator_created": False,
            "gradings_stored": 0,
        },
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=1, sort_keys=True)

    print(f"database  : {GRAPH_DB_PATH}")
    print(f"size      : {GRAPH_DB_PATH.stat().st_size:,} bytes")
    for table, count in counts.items():
        print(f"  {table:<16} {count:,}")
    print(f"\nchain fidelity : {chain['exact_matches']:,} exact, "
          f"{chain['mismatches']} mismatched, {chain['missing']} missing, "
          f"{chain['extra']} extra")
    print(f"sanad counts   : {sanad['hadiths_checked']:,} checked, "
          f"{sanad['mismatches']} mismatches")
    print(f"edges          : {edge['stored_transmissions']:,} stored, "
          f"counts_match={edge['counts_match']}")
    print(f"structure      : {structure}")
    print(f"direction      : {direction}")
    print(f"canonical hash : {digest}")
    print(f"\nACCEPTANCE: {'PASS' if passed else 'FAIL'}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
