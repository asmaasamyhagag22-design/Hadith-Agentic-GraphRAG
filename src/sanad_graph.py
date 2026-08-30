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


class UnknownLocalHadithError(SanadGraphError):
    """No such local corpus hadith ID."""


class NoAcceptedMisLinkError(SanadGraphError):
    """The local hadith exists, but the frozen linkage accepted no MIS record.

    Distinct from an unknown ID: the hadith is real and in the corpus, and the
    missing layer is the linkage, not the hadith.
    """

    def __init__(self, message, local_id=None):
        super().__init__(message)
        self.local_id = local_id


# The exact layer a caller is missing, so a failure is diagnostic rather than
# an empty list.
STATUS_OK = "OK"
STATUS_NO_RECORDED_ISNAD = "VALID_LINKED_HADITH_WITH_NO_RECORDED_ISNAD"
STATUS_NO_ACCEPTED_LINK = "VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK"
STATUS_INVALID_LOCAL_ID = "INVALID_LOCAL_HADITH_ID"
STATUS_INVALID_MIS_RECORD = "INVALID_MIS_RECORD"


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


# ---------------------------------------------------------------------------
# local corpus -> frozen linkage -> MIS chain
# ---------------------------------------------------------------------------

def _local_row(connection, local_id):
    row = connection.execute(
        "SELECT local_id, id_in_book, book_id, chapter_id, chapter_ar, chapter_en "
        "FROM local_hadith WHERE local_id = ?",
        (int(local_id),),
    ).fetchone()

    if row is None:
        raise UnknownLocalHadithError(
            f"No local hadith with id {local_id!r}. This is a corpus id "
            f"(muslim.json 'id'), not idInBook."
        )

    return dict(row)


def _link_row(connection, local_id):
    return connection.execute(
        "SELECT mis_book_no, mis_hadith_no, link_status, link_relation, "
        "linkage_version, linkage_artifact_sha256, candidate_status, "
        "similarity, quick_similarity FROM hadith_mis_link WHERE local_id = ?",
        (int(local_id),),
    ).fetchone()


def get_local_hadith(connection, local_id):
    """One local corpus hadith, with whether the frozen linkage accepted a MIS record."""

    local = _local_row(connection, local_id)
    link = _link_row(connection, local_id)

    return {
        "local_hadith": local,
        "has_accepted_mis_link": link is not None,
        "status": STATUS_OK if link is not None else STATUS_NO_ACCEPTED_LINK,
        "recorded_in": "local corpus (Sahih Muslim)",
    }


def get_mis_record_for_local_hadith(connection, local_id):
    """Resolve a local hadith to its MIS record through the frozen linkage.

    The three layers stay visible in the result: the local hadith, the linkage
    that joins them, and the MIS record. The linkage is never made invisible.
    """

    local = _local_row(connection, local_id)
    link = _link_row(connection, local_id)

    if link is None:
        raise NoAcceptedMisLinkError(
            f"Local hadith {local_id} is in the corpus but the frozen linkage "
            f"accepted no MIS record for it.",
            local_id=int(local_id),
        )

    mis = _require_hadith(connection, link["mis_book_no"], link["mis_hadith_no"])

    return {
        "local_hadith": local,
        "linkage": dict(link),
        "mis_hadith": {**mis, "recorded_in": RECORDED_IN},
        "status": STATUS_OK,
    }


def get_isnads_for_local_hadith(connection, local_id):
    """The isnads recorded in MIS for a local hadith, kept separate."""

    resolved = get_mis_record_for_local_hadith(connection, local_id)
    mis = resolved["mis_hadith"]

    isnads = get_isnads_for_mis_hadith(connection, mis["book_no"], mis["hadith_no"])

    return {
        **resolved,
        "isnads": isnads["isnads"],
        "declared_sanad_count": isnads["declared_sanad_count"],
        "recorded_isnad_count": isnads["recorded_isnad_count"],
        "status": STATUS_OK if isnads["isnads"] else STATUS_NO_RECORDED_ISNAD,
    }


def get_ordered_chains_for_local_hadith(connection, local_id):
    """Every recorded chain of a local hadith, in order, narrator by narrator."""

    result = get_isnads_for_local_hadith(connection, local_id)
    mis = result["mis_hadith"]

    chains = [
        get_ordered_chain(connection, mis["book_no"], mis["hadith_no"], isnad["sanad_no"])
        for isnad in result["isnads"]
    ]

    return {**result, "chains": chains}


def get_local_hadith_for_mis_record(connection, book_no, hadith_no):
    """Reverse direction: which local hadith, if any, is linked to a MIS record."""

    mis = _require_hadith(connection, book_no, hadith_no)

    row = connection.execute(
        "SELECT local_id, id_in_book, link_status, linkage_version "
        "FROM hadith_mis_link WHERE mis_book_no = ? AND mis_hadith_no = ?",
        (str(book_no), str(hadith_no)),
    ).fetchone()

    return {
        "mis_hadith": {**mis, "recorded_in": RECORDED_IN},
        "linkage": dict(row) if row else None,
        "local_hadith": _local_row(connection, row["local_id"]) if row else None,
        "status": STATUS_OK if row else "VALID_MIS_RECORD_BUT_NO_ACCEPTED_LOCAL_LINK",
    }


def linkage_coverage(connection):
    """Coverage of the frozen accepted linkage. Coverage, not identity accuracy."""

    local_total = connection.execute("SELECT COUNT(*) FROM local_hadith").fetchone()[0]
    mis_total = connection.execute("SELECT COUNT(*) FROM mis_hadith").fetchone()[0]
    linked = connection.execute("SELECT COUNT(*) FROM hadith_mis_link").fetchone()[0]

    return {
        "local_total": local_total,
        "local_linked": linked,
        "local_unlinked": local_total - linked,
        "mis_total": mis_total,
        "mis_linked": linked,
        "mis_unlinked": mis_total - linked,
        "measurement_kind": "LINKAGE_COVERAGE_NOT_IDENTITY_ACCURACY",
    }


def graph_counts(connection):
    """Row counts, for verification and reporting."""

    return {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("mis_narrator", "mis_hadith", "isnad", "transmission",
                      "local_hadith", "hadith_mis_link")
    }
