"""Deterministic read access to the MIS sanad chain graph.

Every answer here is *as recorded in MIS*.  The narrator identity is a MIS
narrator identity: it is not a canonical historical person, it carries no
grading, and it is not linked to any Itqan profile.  Questions about a
narrator's biography or gradings are not answerable from this layer and are not
offered by it.

There is no model, no ranking and no inference in this module.  Every function
is a direct query with a deterministic order.

Absence is reported precisely.  An unknown identifier raises; a known record
with nothing recorded returns an empty result.  A caller can therefore always
tell "no such narrator" from "this narrator has no recorded transmissions".
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_sanad_graph import GRAPH_DB_PATH

RECORDED_IN = "MIS"


class SanadGraphError(Exception):
    """Base class for lookups the graph cannot answer."""


class GraphNotBuiltError(SanadGraphError):
    """The SQLite graph has not been built yet."""


class UnknownNarratorError(SanadGraphError):
    """No such MIS narrator ID."""


class UnknownHadithError(SanadGraphError):
    """No such MIS hadith."""


class UnknownIsnadError(SanadGraphError):
    """The hadith exists but has no isnad with that sanad number."""


def open_graph(db_path=GRAPH_DB_PATH):
    """Open the graph read-only-ish, with foreign keys enforced."""

    path = Path(db_path)

    if not path.exists():
        raise GraphNotBuiltError(
            f"No sanad graph at {path}. Build it with "
            f"`python -m src.build_sanad_graph`."
        )

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def _narrator_row(connection, narrator_id):
    row = connection.execute(
        "SELECT narrator_id, label, name_ar, name_ar_mapped, name_en_mapped, "
        "gender, generation FROM mis_narrator WHERE narrator_id = ?",
        (str(narrator_id),),
    ).fetchone()

    if row is None:
        raise UnknownNarratorError(
            f"No MIS narrator with ID {narrator_id!r}."
        )

    return dict(row)


def _require_hadith(connection, book_no, hadith_no):
    row = connection.execute(
        "SELECT book_no, hadith_no, chapter_no, unit_no, declared_sanad_count "
        "FROM mis_hadith WHERE book_no = ? AND hadith_no = ?",
        (str(book_no), str(hadith_no)),
    ).fetchone()

    if row is None:
        raise UnknownHadithError(
            f"No MIS hadith for book {book_no!r}, hadith {hadith_no!r}."
        )

    return dict(row)


def get_narrator(connection, narrator_id):
    """Return one MIS narrator record.  Raises if the ID is not in MIS."""

    return {**_narrator_row(connection, narrator_id), "recorded_in": RECORDED_IN}


def get_mis_hadith(connection, book_no, hadith_no):
    """Return one MIS hadith record with its declared sanad count."""

    return {**_require_hadith(connection, book_no, hadith_no),
            "recorded_in": RECORDED_IN}


def get_isnads_for_mis_hadith(connection, book_no, hadith_no):
    """Return every recorded isnad of one hadith, kept separate.

    Chain variants are never merged: each row is one independently addressable
    sanad.  An empty list means the hadith exists with no recorded isnad, which
    is distinct from the hadith being unknown (that raises).
    """

    hadith = _require_hadith(connection, book_no, hadith_no)

    rows = connection.execute(
        "SELECT sanad_no, step_count, narrator_count FROM isnad "
        "WHERE book_no = ? AND hadith_no = ? ORDER BY CAST(sanad_no AS INTEGER)",
        (str(book_no), str(hadith_no)),
    ).fetchall()

    return {
        "book_no": hadith["book_no"],
        "hadith_no": hadith["hadith_no"],
        "declared_sanad_count": hadith["declared_sanad_count"],
        "recorded_isnad_count": len(rows),
        "isnads": [dict(row) for row in rows],
        "recorded_in": RECORDED_IN,
    }


def get_ordered_chain(connection, book_no, hadith_no, sanad_no):
    """Reconstruct one isnad in recorded order.

    Returns both the narrator sequence and the transmission steps.  Direction
    is `from_narrator_id -> to_narrator_id`, which MIS records as the direction
    of transmission: the earlier narrator to the one who received from them.
    """

    _require_hadith(connection, book_no, hadith_no)

    steps = connection.execute(
        "SELECT position, from_narrator_id, to_narrator_id, source_label "
        "FROM transmission WHERE book_no = ? AND hadith_no = ? AND sanad_no = ? "
        "ORDER BY position",
        (str(book_no), str(hadith_no), str(sanad_no)),
    ).fetchall()

    if not steps:
        raise UnknownIsnadError(
            f"MIS hadith {book_no}/{hadith_no} has no isnad {sanad_no!r}."
        )

    sequence = [steps[0]["from_narrator_id"]] + [row["to_narrator_id"] for row in steps]

    narrators = [
        {"chain_position": position, **_narrator_row(connection, narrator_id)}
        for position, narrator_id in enumerate(sequence, start=1)
    ]

    return {
        "book_no": str(book_no),
        "hadith_no": str(hadith_no),
        "sanad_no": str(sanad_no),
        "narrator_count": len(narrators),
        "step_count": len(steps),
        "narrators": narrators,
        "steps": [dict(row) for row in steps],
        "recorded_in": RECORDED_IN,
    }


def get_hadiths_for_narrator(connection, narrator_id):
    """Every isnad occurrence of one MIS narrator, with its chain coordinates.

    An empty list means the narrator is in MIS but appears in no transmission,
    which is distinct from an unknown ID (that raises).
    """

    narrator = _narrator_row(connection, narrator_id)

    rows = connection.execute(
        "SELECT DISTINCT book_no, hadith_no, sanad_no FROM ("
        "  SELECT book_no, hadith_no, sanad_no FROM transmission"
        "   WHERE from_narrator_id = ?"
        "  UNION"
        "  SELECT book_no, hadith_no, sanad_no FROM transmission"
        "   WHERE to_narrator_id = ?"
        ") ORDER BY book_no, CAST(hadith_no AS INTEGER), CAST(sanad_no AS INTEGER)",
        (str(narrator_id), str(narrator_id)),
    ).fetchall()

    return {
        "narrator_id": narrator["narrator_id"],
        "name_ar": narrator["name_ar"],
        "name_ar_mapped": narrator["name_ar_mapped"],
        "occurrence_count": len(rows),
        "occurrences": [dict(row) for row in rows],
        "recorded_in": RECORDED_IN,
    }


def get_predecessors_in_chain(connection, narrator_id, book_no, hadith_no, sanad_no):
    """Narrators this one received from, **within one named isnad**.

    Scoped deliberately.  One occurrence in one chain is not a general claim
    about who taught whom; aggregating across chains is a separate question and
    is not answered here.
    """

    return _neighbours(
        connection, narrator_id, book_no, hadith_no, sanad_no,
        matched="to_narrator_id", returned="from_narrator_id", role="predecessors",
    )


def get_successors_in_chain(connection, narrator_id, book_no, hadith_no, sanad_no):
    """Narrators who received from this one, **within one named isnad**."""

    return _neighbours(
        connection, narrator_id, book_no, hadith_no, sanad_no,
        matched="from_narrator_id", returned="to_narrator_id", role="successors",
    )


def _neighbours(connection, narrator_id, book_no, hadith_no, sanad_no,
                matched, returned, role):
    narrator = _narrator_row(connection, narrator_id)

    present = connection.execute(
        "SELECT COUNT(*) FROM transmission "
        "WHERE book_no = ? AND hadith_no = ? AND sanad_no = ?",
        (str(book_no), str(hadith_no), str(sanad_no)),
    ).fetchone()[0]

    if not present:
        _require_hadith(connection, book_no, hadith_no)
        raise UnknownIsnadError(
            f"MIS hadith {book_no}/{hadith_no} has no isnad {sanad_no!r}."
        )

    rows = connection.execute(
        f"SELECT position, {returned} AS narrator_id FROM transmission "
        f"WHERE book_no = ? AND hadith_no = ? AND sanad_no = ? AND {matched} = ? "
        f"ORDER BY position",
        (str(book_no), str(hadith_no), str(sanad_no), str(narrator_id)),
    ).fetchall()

    return {
        "narrator_id": narrator["narrator_id"],
        "book_no": str(book_no),
        "hadith_no": str(hadith_no),
        "sanad_no": str(sanad_no),
        "scope": "single isnad occurrence",
        role: [
            {"step_position": row["position"],
             **_narrator_row(connection, row["narrator_id"])}
            for row in rows
        ],
        "recorded_in": RECORDED_IN,
    }


def graph_counts(connection):
    """Row counts, for verification and reporting."""

    return {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("mis_narrator", "mis_hadith", "isnad", "transmission")
    }
