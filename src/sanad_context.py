"""One deterministic read-only surface from a hadith to its recorded sanad.

This composes reads that already exist in `sanad_graph`.  It adds no capability:
no search, no scoring, no inference, no ranking, no identity reasoning, and no
model of any kind.  A caller hands it one identifier and receives one structured
answer.

Every result means exactly this and nothing more:

    according to the accepted local <-> MIS linkage, and the sanad recorded in
    MIS for the linked record

It is not a canonical historical chain, and the narrators in it are MIS narrator
identities, not adjudicated historical persons.

The point of the surface is that a caller does not need to know the table joins
— not that it should stop knowing why an answer is missing.  Traversal can stop
at three different layers, and each one is reported by name rather than as an
empty list, so the caller can tell an unknown hadith from a real hadith with no
linkage from a linked hadith with no recorded chain.

Deciding *whether* to call this, on which hadith, and what to do with the
answer, is the caller's business and is deliberately not modelled here.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sanad_graph import (  # noqa: E402
    NoAcceptedMisLinkError,
    UnknownLocalHadithError,
    get_local_hadith,
    get_ordered_chains_for_local_hadith,
    open_graph,
)

# Where traversal stopped, always named.
LINKED_WITH_RECORDED_ISNAD = "LINKED_WITH_RECORDED_ISNAD"
LINKED_BUT_NO_RECORDED_ISNAD = "LINKED_BUT_NO_RECORDED_ISNAD"
NO_ACCEPTED_MIS_LINK = "VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK"
INVALID_LOCAL_HADITH_ID = "INVALID_LOCAL_HADITH_ID"

CONTEXT_STATUSES = (
    LINKED_WITH_RECORDED_ISNAD,
    LINKED_BUT_NO_RECORDED_ISNAD,
    NO_ACCEPTED_MIS_LINK,
    INVALID_LOCAL_HADITH_ID,
)

BASIS = (
    "as recorded in MIS for the record joined by the accepted local<->MIS "
    "linkage; MIS narrator identities, not adjudicated historical persons"
)

# `retrieve.py` exposes the corpus id as `hadith_id`; the chunk metadata it is
# built from calls the same value `hadith_number`.  Both are accepted, and
# nothing else is guessed at.
RETRIEVAL_ID_FIELDS = ("hadith_id", "hadith_number")

# Passed through untouched when present, so a caller keeps its own retrieval
# provenance.  These are never read, compared or reinterpreted here.
RETRIEVAL_PASSTHROUGH = ("rank", "score", "chunk_id")


class MissingRetrievalIdentifierError(ValueError):
    """A retrieval result carried no field this surface knows how to read."""


def _empty(local_hadith=None, status=INVALID_LOCAL_HADITH_ID, detail=None, requested=None):
    return {
        "status": status,
        "detail": detail,
        "requested_local_id": requested,
        "local_hadith": local_hadith,
        "linkage": None,
        "mis_hadith": None,
        "isnads": [],
        "isnad_count": 0,
        "basis": BASIS,
    }


def context_for_local_hadith(connection, local_id):
    """Everything recorded for one local hadith, down to its ordered chains.

    Returns a result for all four outcomes rather than raising: this is the
    composition surface, and a caller branching on `status` should not also
    have to catch two exception types.  `sanad_graph` keeps raising, so the
    precise API underneath is unchanged.
    """

    try:
        chains = get_ordered_chains_for_local_hadith(connection, local_id)
    except UnknownLocalHadithError as error:
        return _empty(status=INVALID_LOCAL_HADITH_ID, detail=str(error), requested=local_id)
    except NoAcceptedMisLinkError as error:
        # The hadith is real; the linkage is what is missing, so the local
        # record is still returned.
        local = get_local_hadith(connection, local_id)["local_hadith"]
        return _empty(
            local_hadith=local,
            status=NO_ACCEPTED_MIS_LINK,
            detail=str(error),
            requested=local_id,
        )

    isnads = [
        {
            "sanad_no": chain["sanad_no"],
            "narrator_count": chain["narrator_count"],
            "step_count": chain["step_count"],
            # Exactly the narrator records `sanad_graph` returns — MIS narrator
            # id, both name forms, generation and chain position.  Not restated
            # under second names.
            "narrators": chain["narrators"],
        }
        for chain in chains["chains"]
    ]

    return {
        "status": LINKED_WITH_RECORDED_ISNAD if isnads else LINKED_BUT_NO_RECORDED_ISNAD,
        "detail": None,
        "requested_local_id": local_id,
        "local_hadith": chains["local_hadith"],
        "linkage": chains["linkage"],
        "mis_hadith": chains["mis_hadith"],
        "isnads": isnads,
        "isnad_count": len(isnads),
        "declared_sanad_count": chains.get("declared_sanad_count"),
        "basis": BASIS,
    }


def retrieval_identifier(result):
    """Read the local corpus id out of one retrieval result.

    Accepts the two field names the pipeline actually uses and nothing else;
    an unrecognised shape is an error rather than a guess.
    """

    for field in RETRIEVAL_ID_FIELDS:
        if isinstance(result, dict) and result.get(field) is not None:
            return result[field]

    metadata = result.get("metadata") if isinstance(result, dict) else None

    if isinstance(metadata, dict):
        for field in RETRIEVAL_ID_FIELDS:
            if metadata.get(field) is not None:
                return metadata[field]

    raise MissingRetrievalIdentifierError(
        f"Retrieval result carries none of {RETRIEVAL_ID_FIELDS}; "
        f"cannot resolve it to a local hadith without guessing."
    )


def context_for_retrieval_result(connection, result):
    """Enrich one retrieval result with its recorded sanad context.

    One result in, one result out.  Retrieval is not re-run, ranking is not
    touched, no result is chosen over another, and no judgement is made about
    whether the lookup was worth doing — the caller decided that already.
    """

    local_id = retrieval_identifier(result)
    context = context_for_local_hadith(connection, local_id)

    passthrough = {
        field: result[field]
        for field in RETRIEVAL_PASSTHROUGH
        if isinstance(result, dict) and field in result
    }

    return {
        **context,
        "retrieval": {"local_id_field_used": _field_used(result), **passthrough},
    }


def _field_used(result):
    for field in RETRIEVAL_ID_FIELDS:
        if isinstance(result, dict) and result.get(field) is not None:
            return field

    metadata = result.get("metadata") if isinstance(result, dict) else None

    if isinstance(metadata, dict):
        for field in RETRIEVAL_ID_FIELDS:
            if metadata.get(field) is not None:
                return f"metadata.{field}"

    return None


__all__ = [
    "BASIS",
    "CONTEXT_STATUSES",
    "INVALID_LOCAL_HADITH_ID",
    "LINKED_BUT_NO_RECORDED_ISNAD",
    "LINKED_WITH_RECORDED_ISNAD",
    "MissingRetrievalIdentifierError",
    "NO_ACCEPTED_MIS_LINK",
    "context_for_local_hadith",
    "context_for_retrieval_result",
    "open_graph",
    "retrieval_identifier",
]
