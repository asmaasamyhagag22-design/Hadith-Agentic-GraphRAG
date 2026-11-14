import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pytest

from src.build_sanad_graph import (
    FORBIDDEN_TABLES,
    GRAPH_DB_PATH,
    MANIFEST_PATH,
    assert_chain_layer_only,
    build,
    canonical_hash,
    connect,
    isnad_rows,
    parse_label,
    source_chains,
    stored_chains,
    transmission_rows,
    verify_chain_fidelity,
    verify_edge_fidelity,
    verify_sanad_counts,
    verify_structure,
)
from src.config import PROCESSED_DIR
from src.sanad_graph import (
    GraphNotBuiltError,
    UnknownHadithError,
    UnknownIsnadError,
    UnknownNarratorError,
    get_hadiths_for_narrator,
    get_isnads_for_mis_hadith,
    get_narrator,
    get_ordered_chain,
    get_predecessors_in_chain,
    get_successors_in_chain,
    graph_counts,
    open_graph,
)

FROZEN_LINKAGE = PROCESSED_DIR / "mis_linkage_accepted_v1.jsonl"
FROZEN_LINKAGE_SHA256 = (
    "9c3a48e7a0af4f0df1cd9250f49a90f343228b614587196fcf2fa6fbfa572c77"
)

EXPECTED_COUNTS = {
    "mis_narrator": 2092,
    "mis_hadith": 7748,
    "isnad": 14155,
    "transmission": 63642,
    "local_hadith": 7459,
    "hadith_mis_link": 7015,
}


def node(narrator_id, name, generation="Comp.(RA)"):
    return {
        "Label": f"L{narrator_id}", "NarratorID_Mapped": narrator_id,
        "NarratorNameAr": name, "NarratorNameAr-Mapped": name[:6],
        "NarratorNameEn-Mapped": f"N{narrator_id}", "Gender": "Male",
        "NarratorGeneration": generation,
    }


def hadith(book="2", number="1", sanad_count=1):
    return {
        "BookNo": book, "HadithNo": number, "ChapterNo": "1", "UnitNo": "1",
        "BookTitleEnAr": "Sahih Muslim", "ChapterTitleAr": "باب",
        "ChapterTitleEn": "Chapter", "UnitTitleAr": "وحدة",
        "SanadCount": sanad_count, "SanadWithNarratorsCount": "1=2",
    }


def edge(book, number, sanad, position, source, target, chapter="1", unit="1"):
    return {
        "BookNo": book, "HadithNo": number, "ChapterNo": chapter, "UnitNo": unit,
        "SanadNo": sanad, "sourceNarratorID": source, "targetNarratorID": target,
        "sourceNarratorNameEn": f"N{source}", "targetNarratorNameEn": f"N{target}",
        "sourceNarratorGen": "Comp_RA", "targetNarratorGen": "Follower_Tabi",
        "sourceNarratorGender": "Male", "targetNarratorGender": "Male",
        "intractionLabel": (
            f"B{int(book)}-H{int(number):04d}-C{int(chapter):02d}"
            f"-U{int(unit):02d}-S{int(sanad):02d}-i{position}"
        ),
    }


def local_corpus():
    """Three local hadiths; the third has no accepted MIS link."""

    return {
        "chapters": [{"id": 1, "arabic": "باب", "english": "Chapter"}],
        "hadiths": [
            {"id": 100, "idInBook": 1, "bookId": 2, "chapterId": 1},
            {"id": 101, "idInBook": 2, "bookId": 2, "chapterId": 1},
            {"id": 102, "idInBook": 3, "bookId": 2, "chapterId": 1},
        ],
    }


def accepted_links():
    return [
        {"our_idInBook": 1, "mis_HadithNo": 1, "accepted": True,
         "candidate_status": "unique", "similarity": 1.0, "quick_similarity": 1.0},
        {"our_idInBook": 2, "mis_HadithNo": 2, "accepted": True,
         "candidate_status": "unique", "similarity": 1.0, "quick_similarity": 1.0},
    ]


def fixture():
    """Two MIS hadiths (the first with two chains), three local hadiths."""

    nodes = [node("1", "أ"), node("2", "ب", "Follower(Tabi')"),
             node("3", "ج", "Succ. (Taba' Tabi')"), node("4", "د")]
    content = [hadith("2", "1", 2), hadith("2", "2", 1)]
    edges = [
        edge("2", "1", "1", 1, "1", "2"),
        edge("2", "1", "1", 2, "2", "3"),
        edge("2", "1", "2", 1, "4", "2"),
        edge("2", "2", "1", 1, "1", "3"),
    ]
    return nodes, content, edges, local_corpus(), accepted_links(), "fixture-sha"


class SchemaTests(unittest.TestCase):
    """الجداول والقيود بتتعمل زي ما هي متعرّفة."""

    def test_build_creates_only_chain_layer_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "g.sqlite"
            build(path, *fixture())
            connection = connect(path)
            try:
                tables = assert_chain_layer_only(connection)
            finally:
                connection.close()

            self.assertEqual(sorted(tables), [
                "hadith_mis_link", "isnad", "local_hadith",
                "mis_hadith", "mis_narrator", "transmission",
            ])

    def test_foreign_keys_are_enabled_on_the_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "g.sqlite"
            build(path, *fixture())
            connection = connect(path)
            try:
                enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
            finally:
                connection.close()

            self.assertEqual(enabled, 1)

    def test_population_counts_match_the_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "g.sqlite"
            counts = build(path, *fixture())

            self.assertEqual(counts, {
                "mis_narrator": 4, "mis_hadith": 2, "isnad": 3, "transmission": 4,
                "local_hadith": 3, "hadith_mis_link": 2,
            })


class ConstraintTests(unittest.TestCase):
    """القيود بتترفض جوّه قاعدة البيانات، مش بالاختبارات بس."""

    def _built(self, directory):
        path = Path(directory) / "g.sqlite"
        build(path, *fixture())
        return connect(path)

    def test_duplicate_narrator_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = self._built(directory)
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO mis_narrator VALUES ('1','L','x',NULL,NULL,NULL,NULL)"
                    )
            finally:
                connection.close()

    def test_duplicate_hadith_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = self._built(directory)
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO mis_hadith VALUES "
                        "('2','1','1','1',NULL,NULL,NULL,NULL,1,NULL)"
                    )
            finally:
                connection.close()

    def test_duplicate_isnad_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = self._built(directory)
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("INSERT INTO isnad VALUES ('2','1','1',1,2)")
            finally:
                connection.close()

    def test_duplicate_step_position_within_an_isnad_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = self._built(directory)
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO transmission VALUES "
                        "('2','1','1',1,'1','2','DUP-LABEL')"
                    )
            finally:
                connection.close()

    def test_dangling_narrator_endpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = self._built(directory)
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO transmission VALUES "
                        "('2','1','1',9,'999','2','B2-H0001-C01-U01-S01-i9')"
                    )
            finally:
                connection.close()

    def test_transmission_without_its_isnad_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = self._built(directory)
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO transmission VALUES "
                        "('2','1','9',1,'1','2','B2-H0001-C01-U01-S09-i1')"
                    )
            finally:
                connection.close()

    def test_isnad_without_its_hadith_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = self._built(directory)
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("INSERT INTO isnad VALUES ('2','99','1',1,2)")
            finally:
                connection.close()

    def test_duplicate_source_label_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = self._built(directory)
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO transmission VALUES "
                        "('2','2','1',2,'1','2','B2-H0001-C01-U01-S01-i1')"
                    )
            finally:
                connection.close()


class SourceParsingTests(unittest.TestCase):
    """السطور بتتقرا من الملف الأصلي من غير تخمين."""

    def test_interaction_label_is_parsed_into_its_coordinates(self):
        parsed = parse_label("B2-H0289-C02-U43-S01-i3")

        self.assertEqual(parsed["book"], "2")
        self.assertEqual(parsed["hadith"], "0289")
        self.assertEqual(parsed["sanad"], "01")
        self.assertEqual(parsed["position"], "3")

    def test_unparseable_label_raises(self):
        with self.assertRaises(ValueError):
            parse_label("not-a-label")

    def test_label_disagreeing_with_the_sanad_column_raises(self):
        bad = edge("2", "1", "1", 1, "1", "2")
        bad["SanadNo"] = "7"

        with self.assertRaises(ValueError):
            transmission_rows([bad])

    def test_non_contiguous_chain_order_raises(self):
        rows = transmission_rows([
            edge("2", "1", "1", 1, "1", "2"),
            edge("2", "1", "1", 3, "2", "3"),
        ])

        with self.assertRaises(ValueError):
            isnad_rows(rows)


class ChainFidelityTests(unittest.TestCase):
    """السلسلة بتترجع بنفس الترتيب بالظبط."""

    def test_every_fixture_chain_reconstructs_exactly(self):
        nodes, content, edges, *rest = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "g.sqlite"
            build(path, nodes, content, edges, *rest)
            connection = connect(path)
            try:
                report = verify_chain_fidelity(connection, edges)
                self.assertEqual(report["mismatches"], 0)
                self.assertEqual(report["missing"], 0)
                self.assertEqual(report["extra"], 0)
                self.assertEqual(report["exact_matches"], 3)
            finally:
                connection.close()

    def test_a_corrupted_order_is_detected(self):
        nodes, content, edges, *rest = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "g.sqlite"
            build(path, nodes, content, edges, *rest)
            connection = connect(path)
            try:
                connection.execute(
                    "UPDATE transmission SET to_narrator_id = '4' "
                    "WHERE book_no='2' AND hadith_no='1' AND sanad_no='1' AND position=1"
                )
                connection.commit()

                self.assertEqual(
                    verify_chain_fidelity(connection, edges)["mismatches"], 1
                )
            finally:
                connection.close()

    def test_multiple_isnads_stay_separate(self):
        nodes, content, edges, *rest = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "g.sqlite"
            build(path, nodes, content, edges, *rest)
            connection = connect(path)
            try:
                chains = stored_chains(connection)
                self.assertIn(("2", "1", "1"), chains)
                self.assertIn(("2", "1", "2"), chains)
                self.assertNotEqual(chains[("2", "1", "1")], chains[("2", "1", "2")])
                self.assertEqual(verify_sanad_counts(connection)["mismatches"], 0)
            finally:
                connection.close()

    def test_declared_sanad_count_mismatch_is_reported_not_repaired(self):
        nodes, content, edges, *rest = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "g.sqlite"
            build(path, nodes, content, edges, *rest)
            connection = connect(path)
            try:
                connection.execute(
                    "UPDATE mis_hadith SET declared_sanad_count = 9 WHERE hadith_no='1'"
                )
                connection.commit()

                report = verify_sanad_counts(connection)
                self.assertEqual(report["mismatches"], 1)
            finally:
                connection.close()

    def test_edge_and_structure_reports_are_clean_for_the_fixture(self):
        nodes, content, edges, *rest = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "g.sqlite"
            build(path, nodes, content, edges, *rest)
            connection = connect(path)
            try:
                self.assertTrue(verify_edge_fidelity(connection, edges)["counts_match"])
                self.assertEqual(verify_structure(connection), {
                    "dangling_from_narrator": 0,
                    "dangling_to_narrator": 0,
                    "isnads_without_hadith": 0,
                    "broken_chain_transitions": 0,
                    "narrators_unused_by_any_edge": 0,
                })
            finally:
                connection.close()


class DeterminismTests(unittest.TestCase):
    """نفس المدخلات = نفس البصمة المنطقية."""

    def test_two_builds_produce_the_same_canonical_hash(self):
        nodes, content, edges, *rest = fixture()
        digests = []

        with tempfile.TemporaryDirectory() as directory:
            for name in ("a.sqlite", "b.sqlite"):
                path = Path(directory) / name
                build(path, nodes, content, edges, *rest)
                connection = connect(path)
                try:
                    digests.append(canonical_hash(connection))
                finally:
                    connection.close()

        self.assertEqual(digests[0], digests[1])

    def test_a_changed_row_changes_the_canonical_hash(self):
        nodes, content, edges, *rest = fixture()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "g.sqlite"
            build(path, nodes, content, edges, *rest)
            connection = connect(path)
            try:
                before = canonical_hash(connection)
                connection.execute(
                    "UPDATE mis_narrator SET name_ar = 'changed' WHERE narrator_id='1'"
                )
                connection.commit()
                after = canonical_hash(connection)
            finally:
                connection.close()

        self.assertNotEqual(before, after)

    def test_build_is_independent_of_the_working_directory(self):
        import os

        nodes, content, edges, *rest = fixture()
        digests = []
        original = os.getcwd()

        try:
            with tempfile.TemporaryDirectory() as directory:
                for name in ("a.sqlite", "b.sqlite"):
                    os.chdir(original if name == "a.sqlite" else directory)
                    path = Path(directory) / name
                    build(path, nodes, content, edges, *rest)
                    connection = connect(path)
                    try:
                        digests.append(canonical_hash(connection))
                    finally:
                        connection.close()
                os.chdir(original)
        finally:
            os.chdir(original)

        self.assertEqual(digests[0], digests[1])


class QueryApiTests(unittest.TestCase):
    """الاستعلامات بترجع الترتيب والمصدر، وبتفرّق بين الغياب والخطأ."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.path = Path(self._directory.name) / "g.sqlite"
        build(self.path, *fixture())
        self.connection = open_graph(self.path)

    def tearDown(self):
        self.connection.close()
        self._directory.cleanup()

    def test_ordered_chain_returns_narrators_in_recorded_order(self):
        chain = get_ordered_chain(self.connection, "2", "1", "1")

        self.assertEqual([n["narrator_id"] for n in chain["narrators"]], ["1", "2", "3"])
        self.assertEqual([n["chain_position"] for n in chain["narrators"]], [1, 2, 3])
        self.assertEqual(chain["step_count"], 2)
        self.assertEqual(chain["narrator_count"], 3)

    def test_chain_results_preserve_identity_and_provenance(self):
        narrator = get_ordered_chain(self.connection, "2", "1", "1")["narrators"][0]

        for field in ("narrator_id", "name_ar", "name_ar_mapped", "generation"):
            self.assertIn(field, narrator)

    def test_results_declare_that_they_are_as_recorded_in_mis(self):
        self.assertEqual(
            get_ordered_chain(self.connection, "2", "1", "1")["recorded_in"], "MIS"
        )
        self.assertEqual(get_narrator(self.connection, "1")["recorded_in"], "MIS")

    def test_isnads_of_one_hadith_are_returned_separately(self):
        result = get_isnads_for_mis_hadith(self.connection, "2", "1")

        self.assertEqual(result["recorded_isnad_count"], 2)
        self.assertEqual(result["declared_sanad_count"], 2)
        self.assertEqual([i["sanad_no"] for i in result["isnads"]], ["1", "2"])

    def test_neighbours_are_scoped_to_one_isnad(self):
        first = get_successors_in_chain(self.connection, "1", "2", "1", "1")
        other = get_successors_in_chain(self.connection, "1", "2", "2", "1")

        self.assertEqual([n["narrator_id"] for n in first["successors"]], ["2"])
        self.assertEqual([n["narrator_id"] for n in other["successors"]], ["3"])
        self.assertEqual(first["scope"], "single isnad occurrence")

    def test_predecessors_follow_the_recorded_direction(self):
        result = get_predecessors_in_chain(self.connection, "2", "2", "1", "1")

        self.assertEqual([n["narrator_id"] for n in result["predecessors"]], ["1"])

    def test_narrator_occurrences_carry_chain_coordinates(self):
        result = get_hadiths_for_narrator(self.connection, "2")

        self.assertEqual(result["occurrence_count"], 2)
        for occurrence in result["occurrences"]:
            self.assertEqual(
                sorted(occurrence), ["book_no", "hadith_no", "sanad_no"]
            )

    def test_unknown_narrator_raises_rather_than_returning_empty(self):
        with self.assertRaises(UnknownNarratorError):
            get_narrator(self.connection, "999")
        with self.assertRaises(UnknownNarratorError):
            get_hadiths_for_narrator(self.connection, "999")

    def test_unknown_hadith_raises(self):
        with self.assertRaises(UnknownHadithError):
            get_isnads_for_mis_hadith(self.connection, "2", "99")

    def test_unknown_isnad_of_a_known_hadith_raises_its_own_error(self):
        with self.assertRaises(UnknownIsnadError):
            get_ordered_chain(self.connection, "2", "2", "9")

    def test_known_narrator_with_no_transmissions_returns_an_empty_result(self):
        # Distinguishable from an unknown ID, which raises.
        self.connection.execute(
            "INSERT INTO mis_narrator VALUES ('77','L','ه',NULL,NULL,NULL,NULL)"
        )
        self.connection.commit()

        result = get_hadiths_for_narrator(self.connection, "77")

        self.assertEqual(result["occurrence_count"], 0)
        self.assertEqual(result["occurrences"], [])

    def test_missing_database_raises_a_specific_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(GraphNotBuiltError):
                open_graph(Path(directory) / "absent.sqlite")


@pytest.mark.requires_data
class BuiltGraphTests(unittest.TestCase):
    """على قاعدة البيانات المبنية فعلاً. بتتخطى لو مش موجودة."""

    @unittest.skipUnless(GRAPH_DB_PATH.exists(), "sanad graph not built")
    def test_full_population_counts(self):
        connection = open_graph()
        try:
            self.assertEqual(graph_counts(connection), EXPECTED_COUNTS)
        finally:
            connection.close()

    @unittest.skipUnless(GRAPH_DB_PATH.exists(), "sanad graph not built")
    def test_every_stored_chain_is_contiguous_and_continuous(self):
        connection = connect(GRAPH_DB_PATH)
        try:
            chains = stored_chains(connection)
            self.assertEqual(len(chains), EXPECTED_COUNTS["isnad"])

            for key, steps in chains.items():
                positions = [step[0] for step in steps]
                self.assertEqual(positions, list(range(1, len(steps) + 1)), key)
                for first, second in zip(steps, steps[1:]):
                    self.assertEqual(first[2], second[1], key)
        finally:
            connection.close()

    @unittest.skipUnless(GRAPH_DB_PATH.exists(), "sanad graph not built")
    def test_structure_and_sanad_counts_are_clean(self):
        connection = connect(GRAPH_DB_PATH)
        try:
            self.assertEqual(verify_structure(connection), {
                "dangling_from_narrator": 0,
                "dangling_to_narrator": 0,
                "isnads_without_hadith": 0,
                "broken_chain_transitions": 0,
                "narrators_unused_by_any_edge": 0,
            })
            self.assertEqual(verify_sanad_counts(connection)["mismatches"], 0)
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

    @unittest.skipUnless(MANIFEST_PATH.exists(), "manifest not built")
    def test_manifest_records_a_passing_build(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(manifest["verification"]["acceptance"], "PASS")
        self.assertEqual(manifest["canonical"]["row_counts"], EXPECTED_COUNTS)

        chain = manifest["verification"]["chain_fidelity"]
        self.assertEqual(chain["exact_matches"], EXPECTED_COUNTS["isnad"])
        self.assertEqual(chain["mismatches"], 0)
        self.assertEqual(chain["missing"], 0)
        self.assertEqual(chain["extra"], 0)

        self.assertFalse(manifest["scope"]["itqan_attached"])
        self.assertFalse(manifest["scope"]["historical_narrator_created"])
        self.assertEqual(manifest["scope"]["gradings_stored"], 0)


@pytest.mark.requires_data
class FrozenArtifactTests(unittest.TestCase):
    """بناء الجراف ما مسّش أي حاجة مجمّدة."""

    @unittest.skipUnless(FROZEN_LINKAGE.exists(), "linkage artifact not present")
    def test_frozen_linkage_is_unchanged_and_readable(self):
        import hashlib

        digest = hashlib.sha256(FROZEN_LINKAGE.read_bytes()).hexdigest()
        self.assertEqual(digest, FROZEN_LINKAGE_SHA256)

        rows = [
            json.loads(line)
            for line in FROZEN_LINKAGE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(rows), 7015)


if __name__ == "__main__":
    unittest.main()
