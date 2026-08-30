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

from config import MUSLIM_JSON_PATH, PROCESSED_DIR
from profile_mis import CONTENT, EDGES, NODES

SCHEMA_VERSION = "sanad_chain_v1+local_link_v1"
BUILDER_VERSION = "build_sanad_graph_v2"

GRAPH_DB_PATH = PROCESSED_DIR / "sanad_graph.sqlite"
MANIFEST_PATH = PROCESSED_DIR / "sanad_graph_manifest.json"

FROZEN_LINKAGE_PATH = PROCESSED_DIR / "mis_linkage_accepted_v1.jsonl"

# The linkage is frozen upstream.  This build consumes it and never recomputes,
# rematches or extends it.
LINKAGE_VERSION = "mis_linkage_accepted_v1"

# Deliberately factual.  The frozen artifact records that a local hadith was
# matched to a MIS record by narrow-normalised text; it does not adjudicate
# that the two are the same historical hadith, so the status must not say so.
LINK_STATUS = "ACCEPTED_LINK_V1"
LINK_RELATION = "LINKS_TO_MIS_RECORD"

# The chain layer keeps its own identity even as tables are added around it.
CHAIN_TABLES = ("mis_narrator", "mis_hadith", "isnad", "transmission")
LOCAL_TABLES = ("local_hadith", "hadith_mis_link")

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

# A local hadith is not a MIS hadith.  The accepted mapping happens to be 1:1
# today, which is not a reason to store them in one row: they are different
# identities from different corpora, joined by a frozen, revisable artifact.
LOCAL_DDL = """
CREATE TABLE local_hadith (
    local_id     INTEGER PRIMARY KEY NOT NULL,
    id_in_book   INTEGER NOT NULL UNIQUE,
    book_id      INTEGER NOT NULL,
    chapter_id   INTEGER NOT NULL,
    chapter_ar   TEXT,
    chapter_en   TEXT,
    CHECK (local_id > 0),
    CHECK (id_in_book > 0)
);

CREATE TABLE hadith_mis_link (
    local_id                INTEGER PRIMARY KEY NOT NULL,
    id_in_book              INTEGER NOT NULL UNIQUE,
    mis_book_no             TEXT NOT NULL,
    mis_hadith_no           TEXT NOT NULL,
    link_status             TEXT NOT NULL,
    link_relation           TEXT NOT NULL,
    linkage_version         TEXT NOT NULL,
    linkage_artifact_sha256 TEXT NOT NULL,
    candidate_status        TEXT NOT NULL,
    similarity              REAL NOT NULL,
    quick_similarity        REAL NOT NULL,
    UNIQUE (mis_book_no, mis_hadith_no),
    FOREIGN KEY (local_id)   REFERENCES local_hadith (local_id),
    FOREIGN KEY (id_in_book) REFERENCES local_hadith (id_in_book),
    FOREIGN KEY (mis_book_no, mis_hadith_no)
        REFERENCES mis_hadith (book_no, hadith_no),
    CHECK (link_status = 'ACCEPTED_LINK_V1'),
    CHECK (link_relation = 'LINKS_TO_MIS_RECORD')
);

CREATE INDEX idx_link_mis ON hadith_mis_link (mis_book_no, mis_hadith_no);
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


def read_local_corpus(path=None):
    with open(path or MUSLIM_JSON_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_frozen_links(path=FROZEN_LINKAGE_PATH):
    """Load the frozen accepted linkage.  Accepted rows only, never rebuilt."""

    rows = []

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))

    rejected = [row for row in rows if not row.get("accepted")]

    if rejected:
        raise ValueError(
            f"{Path(path).name} contains {len(rejected)} non-accepted rows; "
            f"this build consumes accepted links only."
        )

    return rows


def local_hadith_rows(corpus):
    """One row per local hadith, linked or not.

    The Arabic text is deliberately not stored: it is 7.2 MB the retrieval
    layer already owns, and the graph needs identity, not content.
    """

    chapters = {
        chapter.get("id"): chapter for chapter in corpus.get("chapters") or []
    }

    rows = []

    for hadith in corpus.get("hadiths") or []:
        local_id = hadith.get("id")
        id_in_book = hadith.get("idInBook")
        book_id = hadith.get("bookId")
        chapter_id = hadith.get("chapterId")

        if local_id is None or id_in_book is None or book_id is None or chapter_id is None:
            raise ValueError(f"Local hadith missing source identity: {hadith!r}")

        chapter = chapters.get(chapter_id) or {}

        rows.append((
            int(local_id),
            int(id_in_book),
            int(book_id),
            int(chapter_id),
            text(chapter.get("arabic")),
            text(chapter.get("english")),
        ))

    return sorted(rows)


def link_rows(links, local_rows, artifact_sha256, mis_book_no="2"):
    """Turn frozen accepted links into rows keyed to both identities.

    The artifact stores the local side as `our_idInBook` and the MIS side as
    `mis_HadithNo`.  The graph keys local hadiths by their corpus `id`, so the
    local id is resolved through `id_in_book`, which is unique on both sides.
    """

    by_id_in_book = {row[1]: row[0] for row in local_rows}
    rows = []

    for link in links:
        id_in_book = link.get("our_idInBook")
        mis_hadith_no = link.get("mis_HadithNo")

        if id_in_book is None or mis_hadith_no is None:
            raise ValueError(f"Accepted link missing an endpoint: {link!r}")

        local_id = by_id_in_book.get(int(id_in_book))

        if local_id is None:
            raise ValueError(
                f"Accepted link references idInBook {id_in_book}, which is not "
                f"in the local corpus."
            )

        rows.append((
            local_id,
            int(id_in_book),
            str(mis_book_no),
            str(mis_hadith_no),
            LINK_STATUS,
            LINK_RELATION,
            LINKAGE_VERSION,
            artifact_sha256,
            str(link.get("candidate_status")),
            float(link.get("similarity")),
            float(link.get("quick_similarity")),
        ))

    return sorted(rows)


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def connect(db_path):
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def build(db_path, nodes=None, content=None, edges=None,
          corpus=None, links=None, linkage_sha256=None):
    """Create and populate the graph from frozen inputs.

    A clean rebuild is the only supported path: the chain layer, the local
    corpus and the frozen linkage are loaded together, never patched into an
    existing file.  Returns the row counts.
    """

    nodes = read_sheet(NODES) if nodes is None else nodes
    content = read_sheet(CONTENT) if content is None else content
    edges = read_sheet(EDGES) if edges is None else edges

    narrators = narrator_rows(nodes)
    hadiths = hadith_rows(content)
    transmissions = transmission_rows(edges)
    isnads = isnad_rows(transmissions)

    if corpus is None:
        corpus = read_local_corpus()

    if links is None:
        links = read_frozen_links()
        linkage_sha256 = linkage_sha256 or file_sha256(FROZEN_LINKAGE_PATH)

    locals_ = local_hadith_rows(corpus)
    accepted = link_rows(links, locals_, artifact_sha256=linkage_sha256 or "")

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

        connection.executescript(LOCAL_DDL)

        connection.executemany(
            "INSERT INTO local_hadith VALUES (?,?,?,?,?,?)", locals_
        )
        connection.executemany(
            "INSERT INTO hadith_mis_link VALUES (?,?,?,?,?,?,?,?,?,?,?)", accepted
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
        "local_hadith": len(locals_),
        "hadith_mis_link": len(accepted),
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


LOCAL_QUERIES = (
    ("local_hadith",
     "SELECT local_id, id_in_book, book_id, chapter_id, chapter_ar, chapter_en "
     "FROM local_hadith ORDER BY local_id"),
    ("hadith_mis_link",
     "SELECT local_id, id_in_book, mis_book_no, mis_hadith_no, link_status, "
     "link_relation, linkage_version, linkage_artifact_sha256, candidate_status, "
     "similarity, quick_similarity FROM hadith_mis_link ORDER BY local_id"),
)


def _canonical_hash(connection, queries, tables):
    """Hash the logical contents of a named set of tables, not the file.

    The schema is filtered to the same tables, so a layer keeps its identity
    when other tables are added beside it.  The file format carries page
    layout and other non-semantic variation, so two correct builds need not be
    byte-identical; ordered rows plus schema is what "the same graph" means.
    """

    digest = hashlib.sha256()

    placeholders = ",".join("?" * len(tables))
    schema = connection.execute(
        f"SELECT type, name, sql FROM sqlite_master WHERE tbl_name IN ({placeholders}) "
        f"ORDER BY type, name",
        tuple(sorted(tables)),
    ).fetchall()

    digest.update(json.dumps(schema, ensure_ascii=False, sort_keys=True).encode("utf-8"))

    for table, query in queries:
        digest.update(f"\n#{table}\n".encode("utf-8"))
        for row in connection.execute(query):
            digest.update(json.dumps(row, ensure_ascii=False).encode("utf-8"))
            digest.update(b"\n")

    return digest.hexdigest()


def chain_canonical_hash(connection):
    """Identity of the MIS chain layer alone.  Unchanged by later layers."""

    return _canonical_hash(connection, CANONICAL_QUERIES, CHAIN_TABLES)


def full_canonical_hash(connection):
    """Identity of the whole graph: chain layer plus local corpus and linkage."""

    return _canonical_hash(
        connection, CANONICAL_QUERIES + LOCAL_QUERIES, CHAIN_TABLES + LOCAL_TABLES
    )


# The chain hash is what earlier milestones pinned, so the original name keeps
# pointing at it rather than silently becoming a different number.
canonical_hash = chain_canonical_hash


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


def verify_link_fidelity(connection, links):
    """Compare every frozen accepted mapping against what was stored."""

    expected = {
        (int(link["our_idInBook"]), str(link["mis_HadithNo"])) for link in links
    }

    actual = {
        (row[0], row[1]) for row in connection.execute(
            "SELECT id_in_book, mis_hadith_no FROM hadith_mis_link"
        )
    }

    local_ids = [row[0] for row in connection.execute(
        "SELECT local_id FROM hadith_mis_link")]
    mis_keys = [(row[0], row[1]) for row in connection.execute(
        "SELECT mis_book_no, mis_hadith_no FROM hadith_mis_link")]

    dangling_local = connection.execute(
        "SELECT COUNT(*) FROM hadith_mis_link l LEFT JOIN local_hadith h "
        "ON l.local_id = h.local_id WHERE h.local_id IS NULL"
    ).fetchone()[0]

    dangling_mis = connection.execute(
        "SELECT COUNT(*) FROM hadith_mis_link l LEFT JOIN mis_hadith m "
        "ON l.mis_book_no = m.book_no AND l.mis_hadith_no = m.hadith_no "
        "WHERE m.hadith_no IS NULL"
    ).fetchone()[0]

    return {
        "accepted_source_links": len(links),
        "stored_links": len(local_ids),
        "exact_matches": len(expected & actual),
        "missing": len(expected - actual),
        "extra": len(actual - expected),
        "duplicate_local_endpoints": len(local_ids) - len(set(local_ids)),
        "duplicate_mis_endpoints": len(mis_keys) - len(set(mis_keys)),
        "dangling_local_endpoints": dangling_local,
        "dangling_mis_endpoints": dangling_mis,
    }


def coverage_report(connection):
    """Linkage coverage on both sides.  Coverage, never identity accuracy."""

    local_total = connection.execute("SELECT COUNT(*) FROM local_hadith").fetchone()[0]
    mis_total = connection.execute("SELECT COUNT(*) FROM mis_hadith").fetchone()[0]
    linked = connection.execute("SELECT COUNT(*) FROM hadith_mis_link").fetchone()[0]

    return {
        "local_total": local_total,
        "local_linked": linked,
        "local_unlinked": local_total - linked,
        "local_linked_pct": round(100 * linked / local_total, 2) if local_total else None,
        "mis_total": mis_total,
        "mis_linked": linked,
        "mis_unlinked": mis_total - linked,
        "mis_linked_pct": round(100 * linked / mis_total, 2) if mis_total else None,
        "measurement_kind": "LINKAGE_COVERAGE_NOT_IDENTITY_ACCURACY",
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
    corpus = read_local_corpus()
    links = read_frozen_links()
    linkage_sha = file_sha256(FROZEN_LINKAGE_PATH)

    counts = build(GRAPH_DB_PATH, nodes, content, edges, corpus, links, linkage_sha)

    connection = connect(GRAPH_DB_PATH)

    try:
        chain = verify_chain_fidelity(connection, edges)
        sanad = verify_sanad_counts(connection)
        edge = verify_edge_fidelity(connection, edges)
        structure = verify_structure(connection)
        linkage = verify_link_fidelity(connection, links)
        coverage = coverage_report(connection)
        direction = generation_direction_report(connection)
        digest = chain_canonical_hash(connection)
        full_digest = full_canonical_hash(connection)
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
        and linkage["missing"] == 0 and linkage["extra"] == 0
        and linkage["stored_links"] == linkage["accepted_source_links"]
        and linkage["duplicate_local_endpoints"] == 0
        and linkage["duplicate_mis_endpoints"] == 0
        and linkage["dangling_local_endpoints"] == 0
        and linkage["dangling_mis_endpoints"] == 0
    )

    manifest = {
        "canonical": {
            "schema_version": SCHEMA_VERSION,
            "builder_version": BUILDER_VERSION,
            # The MIS-only identity earlier milestones pinned. Unchanged by the
            # local layer, and kept under its original key so history is not lost.
            "canonical_graph_sha256": digest,
            "mis_chain_sha256": digest,
            "full_graph_sha256": full_digest,
            "row_counts": counts,
            "source_files": {
                path.name: file_sha256(path) for path in (NODES, CONTENT, EDGES)
            },
            "local_corpus": {
                "path": MUSLIM_JSON_PATH.name,
                "sha256": file_sha256(MUSLIM_JSON_PATH),
                "rows": counts["local_hadith"],
            },
            "frozen_linkage": {
                "path": FROZEN_LINKAGE_PATH.name,
                "sha256": linkage_sha,
                "version": LINKAGE_VERSION,
                "accepted_rows": counts["hadith_mis_link"],
                "status": LINK_STATUS,
                "relation": LINK_RELATION,
            },
            "tables": tables,
        },
        "verification": {
            "chain_fidelity": chain,
            "sanad_count_fidelity": sanad,
            "edge_fidelity": edge,
            "structure": structure,
            "linkage_fidelity": linkage,
            "coverage": coverage,
            "generation_direction": direction,
            "acceptance": "PASS" if passed else "FAIL",
        },
        "scope": {
            "layer": "MIS chain layer + local corpus and frozen accepted linkage",
            "identity_semantics": "MIS narrator identity, not historical person; "
                                  "local and MIS hadiths remain distinct records",
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
    print(f"linkage        : {linkage['exact_matches']:,} exact, "
          f"{linkage['missing']} missing, {linkage['extra']} extra, "
          f"dup_local={linkage['duplicate_local_endpoints']}, "
          f"dup_mis={linkage['duplicate_mis_endpoints']}, "
          f"dangling={linkage['dangling_local_endpoints']}/{linkage['dangling_mis_endpoints']}")
    print(f"coverage       : local {coverage['local_linked']:,}/{coverage['local_total']:,} "
          f"({coverage['local_linked_pct']}%), MIS {coverage['mis_linked']:,}/"
          f"{coverage['mis_total']:,} ({coverage['mis_linked_pct']}%)")
    print(f"direction      : {direction}")
    print(f"MIS chain hash : {digest}")
    print(f"full graph hash: {full_digest}")
    print(f"\nACCEPTANCE: {'PASS' if passed else 'FAIL'}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
