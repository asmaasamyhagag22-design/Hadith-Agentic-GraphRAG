import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pytest

from src.build_sanad_graph import (
    FORBIDDEN_TABLES,
    FROZEN_LINKAGE_PATH,
    GRAPH_DB_PATH,
    LINK_RELATION,
    LINK_STATUS,
    LINKAGE_VERSION,
    MANIFEST_PATH,
    assert_chain_layer_only,
    build,
    chain_canonical_hash,
    connect,
    coverage_report,
    full_canonical_hash,
    link_rows,
    local_hadith_rows,
    read_frozen_links,
    verify_link_fidelity,
)
from src.config import MUSLIM_JSON_PATH
from src.sanad_graph import (
    NoAcceptedMisLinkError,
    STATUS_NO_ACCEPTED_LINK,
    STATUS_OK,
    UnknownHadithError,
    UnknownLocalHadithError,
    get_isnads_for_local_hadith,
    get_local_hadith,
    get_local_hadith_for_mis_record,
    get_mis_record_for_local_hadith,
    get_ordered_chains_for_local_hadith,
    graph_counts,
    linkage_coverage,
    open_graph,
)
from tests.test_build_sanad_graph import accepted_links, fixture, local_corpus

FROZEN_LINKAGE_SHA256 = (
    "9c3a48e7a0af4f0df1cd9250f49a90f343228b614587196fcf2fa6fbfa572c77"
)
MIS_CHAIN_SHA256 = (
    "496ccf1da21d2e849a94fb2d2e0d4ae66e3bfa549f4ce555f5cf2f4d490bfbce"
)

LOCAL_TOTAL = 7459
ACCEPTED_LINKS = 7015
LOCAL_UNLINKED = 444
MIS_UNLINKED = 733


def built(directory, name="g.sqlite"):
    path = Path(directory) / name
    build(path, *fixture())
    return path


class LocalRowTests(unittest.TestCase):
    """السجل المحلي بيتحمّل كامل، مربوط أو غير مربوط."""

    def test_every_local_hadith_loads_including_unlinked(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(built(directory))
            try:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM local_hadith").fetchone()[0], 3
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM hadith_mis_link").fetchone()[0], 2
                )
                unlinked = connection.execute(
                    "SELECT local_id FROM local_hadith WHERE local_id NOT IN "
                    "(SELECT local_id FROM hadith_mis_link)"
                ).fetchall()
                self.assertEqual([row[0] for row in unlinked], [102])
            finally:
                connection.close()

    def test_local_rows_carry_the_identity_needed_to_join(self):
        rows = local_hadith_rows(local_corpus())

        self.assertEqual(len(rows), 3)
        for local_id, id_in_book, book_id, chapter_id, chapter_ar, chapter_en in rows:
            self.assertIsInstance(local_id, int)
            self.assertIsInstance(id_in_book, int)
            self.assertEqual(book_id, 2)
            self.assertEqual(chapter_id, 1)
            self.assertTrue(chapter_ar)

    def test_local_hadith_missing_identity_raises(self):
        corpus = {"chapters": [], "hadiths": [{"id": 1, "bookId": 2, "chapterId": 1}]}

        with self.assertRaises(ValueError):
            local_hadith_rows(corpus)

    def test_link_referencing_an_absent_local_hadith_raises(self):
        rows = local_hadith_rows(local_corpus())
        bad = [{"our_idInBook": 999, "mis_HadithNo": 1, "accepted": True,
                "candidate_status": "unique", "similarity": 1.0, "quick_similarity": 1.0}]

        with self.assertRaises(ValueError):
            link_rows(bad, rows, artifact_sha256="x")

    def test_non_accepted_rows_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "links.jsonl"
            path.write_text(
                json.dumps({"our_idInBook": 1, "mis_HadithNo": 1, "accepted": False}) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                read_frozen_links(path)


class LinkConstraintTests(unittest.TestCase):
    """قاعدة البيانات نفسها بترفض الربط المكرر أو المعلّق."""

    def test_duplicate_local_mapping_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(built(directory))
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO hadith_mis_link VALUES "
                        "(100,3,'2','2','ACCEPTED_LINK_V1','LINKS_TO_MIS_RECORD',"
                        "'v','sha','unique',1.0,1.0)"
                    )
            finally:
                connection.close()

    def test_duplicate_mis_mapping_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(built(directory))
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO hadith_mis_link VALUES "
                        "(102,3,'2','1','ACCEPTED_LINK_V1','LINKS_TO_MIS_RECORD',"
                        "'v','sha','unique',1.0,1.0)"
                    )
            finally:
                connection.close()

    def test_link_to_an_unknown_local_hadith_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(built(directory))
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO hadith_mis_link VALUES "
                        "(999,9,'2','2','ACCEPTED_LINK_V1','LINKS_TO_MIS_RECORD',"
                        "'v','sha','unique',1.0,1.0)"
                    )
            finally:
                connection.close()

    def test_link_to_an_unknown_mis_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(built(directory))
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO hadith_mis_link VALUES "
                        "(102,3,'2','99','ACCEPTED_LINK_V1','LINKS_TO_MIS_RECORD',"
                        "'v','sha','unique',1.0,1.0)"
                    )
            finally:
                connection.close()

    def test_a_status_other_than_the_frozen_one_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(built(directory))
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO hadith_mis_link VALUES "
                        "(102,3,'2','2','SAME_HISTORICAL_HADITH','LINKS_TO_MIS_RECORD',"
                        "'v','sha','unique',1.0,1.0)"
                    )
            finally:
                connection.close()


class LinkFidelityTests(unittest.TestCase):
    """كل ربط مقبول اتخزّن زي ما هو بالظبط."""

    def test_fixture_links_reproduce_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(built(directory))
            try:
                report = verify_link_fidelity(connection, accepted_links())

                self.assertEqual(report["exact_matches"], 2)
                self.assertEqual(report["missing"], 0)
                self.assertEqual(report["extra"], 0)
                self.assertEqual(report["duplicate_local_endpoints"], 0)
                self.assertEqual(report["duplicate_mis_endpoints"], 0)
                self.assertEqual(report["dangling_local_endpoints"], 0)
                self.assertEqual(report["dangling_mis_endpoints"], 0)
            finally:
                connection.close()

    def test_a_removed_link_is_detected_as_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(built(directory))
            try:
                connection.execute("DELETE FROM hadith_mis_link WHERE local_id = 100")
                connection.commit()

                report = verify_link_fidelity(connection, accepted_links())
                self.assertEqual(report["missing"], 1)
            finally:
                connection.close()

    def test_coverage_counts_both_sides_and_is_not_called_accuracy(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(built(directory))
            try:
                report = coverage_report(connection)

                self.assertEqual(report["local_total"], 3)
                self.assertEqual(report["local_linked"], 2)
                self.assertEqual(report["local_unlinked"], 1)
                self.assertEqual(report["mis_unlinked"], 0)
                self.assertEqual(
                    report["measurement_kind"],
                    "LINKAGE_COVERAGE_NOT_IDENTITY_ACCURACY",
                )
            finally:
                connection.close()


class HashSeparationTests(unittest.TestCase):
    """طبقة السند بتحتفظ بهويتها بعد إضافة الطبقة المحلية."""

    def test_chain_hash_ignores_the_local_layer(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(built(directory))
            try:
                before = chain_canonical_hash(connection)
                connection.execute("DELETE FROM hadith_mis_link")
                connection.execute("DELETE FROM local_hadith")
                connection.commit()

                self.assertEqual(chain_canonical_hash(connection), before)
            finally:
                connection.close()

    def test_full_hash_reacts_to_the_local_layer(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = connect(built(directory))
            try:
                before = full_canonical_hash(connection)
                connection.execute("DELETE FROM hadith_mis_link WHERE local_id = 100")
                connection.commit()

                self.assertNotEqual(full_canonical_hash(connection), before)
            finally:
                connection.close()

    def test_two_builds_agree_on_both_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            digests = []
            for name in ("a.sqlite", "b.sqlite"):
                connection = connect(built(directory, name))
                try:
                    digests.append(
                        (chain_canonical_hash(connection), full_canonical_hash(connection))
                    )
                finally:
                    connection.close()

            self.assertEqual(digests[0], digests[1])


class QueryApiTests(unittest.TestCase):
    """الاستعلام بيوضّح الطبقات الثلاثة وبيفرّق بين أنواع الغياب."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.path = built(self._directory.name)
        self.connection = open_graph(self.path)

    def tearDown(self):
        self.connection.close()
        self._directory.cleanup()

    def test_linked_local_hadith_resolves_to_its_mis_record(self):
        result = get_mis_record_for_local_hadith(self.connection, 100)

        self.assertEqual(result["local_hadith"]["local_id"], 100)
        self.assertEqual(result["mis_hadith"]["hadith_no"], "1")
        self.assertEqual(result["linkage"]["link_status"], LINK_STATUS)
        self.assertEqual(result["linkage"]["link_relation"], LINK_RELATION)
        self.assertEqual(result["linkage"]["linkage_version"], LINKAGE_VERSION)

    def test_the_linkage_layer_is_never_invisible(self):
        result = get_isnads_for_local_hadith(self.connection, 100)

        self.assertIn("local_hadith", result)
        self.assertIn("linkage", result)
        self.assertIn("mis_hadith", result)
        self.assertIn("isnads", result)

    def test_linked_local_hadith_returns_ordered_chains(self):
        result = get_ordered_chains_for_local_hadith(self.connection, 100)

        self.assertEqual(len(result["chains"]), 2)
        first = result["chains"][0]
        self.assertEqual([n["narrator_id"] for n in first["narrators"]], ["1", "2", "3"])
        self.assertEqual([n["chain_position"] for n in first["narrators"]], [1, 2, 3])

    def test_unlinked_local_hadith_is_valid_but_raises_on_traversal(self):
        plain = get_local_hadith(self.connection, 102)
        self.assertFalse(plain["has_accepted_mis_link"])
        self.assertEqual(plain["status"], STATUS_NO_ACCEPTED_LINK)

        with self.assertRaises(NoAcceptedMisLinkError) as caught:
            get_mis_record_for_local_hadith(self.connection, 102)

        self.assertEqual(caught.exception.local_id, 102)

    def test_invalid_local_id_is_distinct_from_an_unlinked_one(self):
        with self.assertRaises(UnknownLocalHadithError):
            get_local_hadith(self.connection, 99999)

        self.assertEqual(get_local_hadith(self.connection, 102)["status"],
                         STATUS_NO_ACCEPTED_LINK)

    def test_invalid_mis_record_raises_its_own_error(self):
        with self.assertRaises(UnknownHadithError):
            get_local_hadith_for_mis_record(self.connection, "2", "99")

    def test_reverse_lookup_reports_an_unlinked_mis_record(self):
        connection = self.connection
        connection.execute("DELETE FROM hadith_mis_link WHERE mis_hadith_no = '1'")
        connection.commit()

        result = get_local_hadith_for_mis_record(connection, "2", "1")

        self.assertIsNone(result["linkage"])
        self.assertEqual(
            result["status"], "VALID_MIS_RECORD_BUT_NO_ACCEPTED_LOCAL_LINK"
        )

    def test_linked_hadith_with_no_recorded_isnad_is_its_own_status(self):
        connection = self.connection
        connection.execute("DELETE FROM transmission WHERE hadith_no = '1'")
        connection.execute("DELETE FROM isnad WHERE hadith_no = '1'")
        connection.commit()

        result = get_isnads_for_local_hadith(connection, 100)

        self.assertEqual(result["isnads"], [])
        self.assertEqual(result["status"], "VALID_LINKED_HADITH_WITH_NO_RECORDED_ISNAD")
        self.assertNotEqual(result["status"], STATUS_OK)


@pytest.mark.requires_data
class BuiltGraphTests(unittest.TestCase):
    """على قاعدة البيانات المبنية فعلاً. بتتخطى لو مش موجودة."""

    @unittest.skipUnless(GRAPH_DB_PATH.exists(), "sanad graph not built")
    def test_full_population_and_coverage(self):
        connection = open_graph()
        try:
            counts = graph_counts(connection)
            self.assertEqual(counts["local_hadith"], LOCAL_TOTAL)
            self.assertEqual(counts["hadith_mis_link"], ACCEPTED_LINKS)

            coverage = linkage_coverage(connection)
            self.assertEqual(coverage["local_unlinked"], LOCAL_UNLINKED)
            self.assertEqual(coverage["mis_unlinked"], MIS_UNLINKED)
        finally:
            connection.close()

    @unittest.skipUnless(GRAPH_DB_PATH.exists(), "sanad graph not built")
    def test_accepted_linkage_is_strictly_one_to_one(self):
        connection = connect(GRAPH_DB_PATH)
        try:
            rows = connection.execute(
                "SELECT COUNT(*), COUNT(DISTINCT local_id), "
                "COUNT(DISTINCT mis_book_no || '/' || mis_hadith_no) FROM hadith_mis_link"
            ).fetchone()

            self.assertEqual(rows[0], ACCEPTED_LINKS)
            self.assertEqual(rows[1], ACCEPTED_LINKS)
            self.assertEqual(rows[2], ACCEPTED_LINKS)
        finally:
            connection.close()

    @unittest.skipUnless(GRAPH_DB_PATH.exists(), "sanad graph not built")
    def test_mis_chain_hash_is_unchanged_by_the_local_layer(self):
        connection = connect(GRAPH_DB_PATH)
        try:
            self.assertEqual(chain_canonical_hash(connection), MIS_CHAIN_SHA256)
        finally:
            connection.close()

    @unittest.skipUnless(GRAPH_DB_PATH.exists(), "sanad graph not built")
    def test_full_linkage_fidelity_against_the_frozen_artifact(self):
        connection = connect(GRAPH_DB_PATH)
        try:
            report = verify_link_fidelity(connection, read_frozen_links())

            self.assertEqual(report["accepted_source_links"], ACCEPTED_LINKS)
            self.assertEqual(report["stored_links"], ACCEPTED_LINKS)
            self.assertEqual(report["exact_matches"], ACCEPTED_LINKS)
            self.assertEqual(report["missing"], 0)
            self.assertEqual(report["extra"], 0)
            self.assertEqual(report["duplicate_local_endpoints"], 0)
            self.assertEqual(report["duplicate_mis_endpoints"], 0)
            self.assertEqual(report["dangling_local_endpoints"], 0)
            self.assertEqual(report["dangling_mis_endpoints"], 0)
        finally:
            connection.close()

    @unittest.skipUnless(GRAPH_DB_PATH.exists(), "sanad graph not built")
    def test_no_itqan_or_historical_narrator_contamination(self):
        connection = connect(GRAPH_DB_PATH)
        try:
            tables = assert_chain_layer_only(connection)
            for forbidden in FORBIDDEN_TABLES:
                self.assertNotIn(forbidden, tables)

            columns = set()
            for table in tables:
                for row in connection.execute(f"PRAGMA table_info({table})"):
                    columns.add(row[1].lower())

            for banned in ("itqan_id", "itqan_profile_id", "grade", "grading",
                           "historical_narrator_id"):
                self.assertNotIn(banned, columns)
        finally:
            connection.close()

    @unittest.skipUnless(
        GRAPH_DB_PATH.exists() and (MUSLIM_JSON_PATH.parent.parent
                                    / "processed" / "muslim_chunks.json").exists(),
        "graph or chunks not built",
    )
    def test_every_retrieval_chunk_identifier_resolves_to_a_local_hadith(self):
        chunks_path = MUSLIM_JSON_PATH.parent.parent / "processed" / "muslim_chunks.json"
        chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
        identifiers = {chunk["metadata"]["hadith_number"] for chunk in chunks}

        connection = connect(GRAPH_DB_PATH)
        try:
            known = {row[0] for row in connection.execute("SELECT local_id FROM local_hadith")}
            linked = {row[0] for row in connection.execute(
                "SELECT local_id FROM hadith_mis_link")}
        finally:
            connection.close()

        self.assertEqual(identifiers - known, set())
        self.assertEqual(len(identifiers & linked), ACCEPTED_LINKS)
        self.assertEqual(len(identifiers - linked), LOCAL_UNLINKED)

    @unittest.skipUnless(MANIFEST_PATH.exists(), "manifest not built")
    def test_manifest_records_both_hashes_and_the_linkage_provenance(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        canonical = manifest["canonical"]

        self.assertEqual(canonical["mis_chain_sha256"], MIS_CHAIN_SHA256)
        self.assertEqual(canonical["canonical_graph_sha256"], MIS_CHAIN_SHA256)
        self.assertNotEqual(canonical["full_graph_sha256"], MIS_CHAIN_SHA256)

        linkage = canonical["frozen_linkage"]
        self.assertEqual(linkage["sha256"], FROZEN_LINKAGE_SHA256)
        self.assertEqual(linkage["accepted_rows"], ACCEPTED_LINKS)
        self.assertEqual(linkage["status"], LINK_STATUS)
        self.assertEqual(linkage["relation"], LINK_RELATION)
        self.assertEqual(canonical["local_corpus"]["rows"], LOCAL_TOTAL)

    @unittest.skipUnless(FROZEN_LINKAGE_PATH.exists(), "linkage artifact not present")
    def test_frozen_linkage_artifact_is_unchanged(self):
        digest = hashlib.sha256(FROZEN_LINKAGE_PATH.read_bytes()).hexdigest()

        self.assertEqual(digest, FROZEN_LINKAGE_SHA256)


class PathIndependenceTests(unittest.TestCase):
    """البناء ما بيعتمدش على مجلد التشغيل."""

    def test_build_is_independent_of_the_working_directory(self):
        original = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                connection = connect(built(directory, "a.sqlite"))
                try:
                    from_here = (chain_canonical_hash(connection),
                                 full_canonical_hash(connection))
                finally:
                    connection.close()

                os.chdir(directory)
                connection = connect(built(directory, "b.sqlite"))
                try:
                    from_elsewhere = (chain_canonical_hash(connection),
                                      full_canonical_hash(connection))
                finally:
                    connection.close()
                os.chdir(original)

            self.assertEqual(from_here, from_elsewhere)
        finally:
            os.chdir(original)


if __name__ == "__main__":
    unittest.main()
