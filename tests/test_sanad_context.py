import ast
import hashlib
import tempfile
import unittest
from pathlib import Path

import pytest

from src.build_sanad_graph import (
    FROZEN_LINKAGE_PATH,
    GRAPH_DB_PATH,
    build,
    chain_canonical_hash,
    connect,
    full_canonical_hash,
)
from src.sanad_context import (
    BASIS,
    CONTEXT_STATUSES,
    INVALID_LOCAL_HADITH_ID,
    LINKED_BUT_NO_RECORDED_ISNAD,
    LINKED_WITH_RECORDED_ISNAD,
    MissingRetrievalIdentifierError,
    NO_ACCEPTED_MIS_LINK,
    context_for_local_hadith,
    context_for_retrieval_result,
    retrieval_identifier,
)
from src.sanad_graph import open_graph
from tests.test_build_sanad_graph import fixture

MIS_CHAIN_SHA256 = (
    "496ccf1da21d2e849a94fb2d2e0d4ae66e3bfa549f4ce555f5cf2f4d490bfbce"
)
FULL_GRAPH_SHA256 = (
    "c8818da00bf27f74750105ed6bf2d57e674c26e3dfe63b9ec8774c6a4d6e481c"
)
FROZEN_LINKAGE_SHA256 = (
    "9c3a48e7a0af4f0df1cd9250f49a90f343228b614587196fcf2fa6fbfa572c77"
)

CONTEXT_MODULE = Path(__file__).resolve().parent.parent / "src" / "sanad_context.py"


class ContextTests(unittest.TestCase):
    """طبقة تركيب فقط: بتجمّع قراءات موجودة وما بتضيفش استدلال."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        path = Path(self._directory.name) / "g.sqlite"
        build(path, *fixture())
        self.connection = open_graph(path)

    def tearDown(self):
        self.connection.close()
        self._directory.cleanup()

    def test_linked_hadith_with_multiple_isnads_keeps_them_separate(self):
        result = context_for_local_hadith(self.connection, 100)

        self.assertEqual(result["status"], LINKED_WITH_RECORDED_ISNAD)
        self.assertEqual(result["isnad_count"], 2)
        self.assertEqual([i["sanad_no"] for i in result["isnads"]], ["1", "2"])
        self.assertNotEqual(result["isnads"][0]["narrators"],
                            result["isnads"][1]["narrators"])

    def test_linked_hadith_with_one_isnad(self):
        result = context_for_local_hadith(self.connection, 101)

        self.assertEqual(result["status"], LINKED_WITH_RECORDED_ISNAD)
        self.assertEqual(result["isnad_count"], 1)
        self.assertEqual(result["mis_hadith"]["hadith_no"], "2")

    def test_narrators_are_returned_in_recorded_chain_order(self):
        isnad = context_for_local_hadith(self.connection, 100)["isnads"][0]

        self.assertEqual([n["chain_position"] for n in isnad["narrators"]], [1, 2, 3])
        self.assertEqual([n["narrator_id"] for n in isnad["narrators"]], ["1", "2", "3"])

    def test_every_provenance_layer_is_present(self):
        result = context_for_local_hadith(self.connection, 100)

        self.assertEqual(result["local_hadith"]["local_id"], 100)
        self.assertEqual(result["linkage"]["link_status"], "ACCEPTED_LINK_V1")
        self.assertEqual(result["linkage"]["link_relation"], "LINKS_TO_MIS_RECORD")
        self.assertTrue(result["linkage"]["linkage_artifact_sha256"])
        self.assertEqual(result["mis_hadith"]["book_no"], "2")
        self.assertEqual(result["basis"], BASIS)

    def test_narrator_records_carry_mis_identity_and_both_name_forms(self):
        narrator = context_for_local_hadith(self.connection, 100)["isnads"][0]["narrators"][0]

        for field in ("narrator_id", "name_ar", "name_ar_mapped", "generation"):
            self.assertIn(field, narrator)

    def test_unlinked_local_hadith_keeps_its_record_and_names_the_gap(self):
        result = context_for_local_hadith(self.connection, 102)

        self.assertEqual(result["status"], NO_ACCEPTED_MIS_LINK)
        self.assertEqual(result["local_hadith"]["local_id"], 102)
        self.assertIsNone(result["linkage"])
        self.assertIsNone(result["mis_hadith"])
        self.assertEqual(result["isnads"], [])
        self.assertTrue(result["detail"])

    def test_invalid_local_id_is_its_own_status_not_an_empty_answer(self):
        result = context_for_local_hadith(self.connection, 99999)

        self.assertEqual(result["status"], INVALID_LOCAL_HADITH_ID)
        self.assertIsNone(result["local_hadith"])
        self.assertEqual(result["requested_local_id"], 99999)

    def test_linked_hadith_with_no_recorded_isnad_is_distinguishable(self):
        self.connection.execute("DELETE FROM transmission WHERE hadith_no = '1'")
        self.connection.execute("DELETE FROM isnad WHERE hadith_no = '1'")
        self.connection.commit()

        result = context_for_local_hadith(self.connection, 100)

        self.assertEqual(result["status"], LINKED_BUT_NO_RECORDED_ISNAD)
        self.assertIsNotNone(result["linkage"])
        self.assertIsNotNone(result["mis_hadith"])
        self.assertEqual(result["isnads"], [])

    def test_the_four_outcomes_are_all_distinct(self):
        self.connection.execute("DELETE FROM transmission WHERE hadith_no = '2'")
        self.connection.execute("DELETE FROM isnad WHERE hadith_no = '2'")
        self.connection.commit()

        statuses = {
            context_for_local_hadith(self.connection, local_id)["status"]
            for local_id in (100, 101, 102, 99999)
        }

        self.assertEqual(len(statuses), 4)
        self.assertTrue(statuses <= set(CONTEXT_STATUSES))

    def test_no_itqan_or_historical_identity_field_appears(self):
        import json

        blob = json.dumps(context_for_local_hadith(self.connection, 100), ensure_ascii=False)

        for banned in ("itqan", "historical_narrator", "grade", "grading",
                       "candidate_profile"):
            self.assertNotIn(banned, blob.lower())


class RetrievalAdapterTests(unittest.TestCase):
    """بيقرأ نتيجة استرجاع واحدة زي ما هي، من غير ما يعيد الاسترجاع."""

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        path = Path(self._directory.name) / "g.sqlite"
        build(path, *fixture())
        self.connection = open_graph(path)

    def tearDown(self):
        self.connection.close()
        self._directory.cleanup()

    def test_reads_the_field_retrieve_actually_exposes(self):
        self.assertEqual(retrieval_identifier({"hadith_id": 100, "rank": 1}), 100)

    def test_reads_the_chunk_metadata_field_name_too(self):
        self.assertEqual(retrieval_identifier({"hadith_number": 101}), 101)
        self.assertEqual(retrieval_identifier({"metadata": {"hadith_number": 101}}), 101)

    def test_an_unrecognised_result_shape_raises_rather_than_guessing(self):
        with self.assertRaises(MissingRetrievalIdentifierError):
            retrieval_identifier({"text": "…", "score": 0.9})

    def test_adapter_enriches_one_result_and_passes_its_provenance_through(self):
        result = context_for_retrieval_result(
            self.connection, {"hadith_id": 100, "rank": 3, "score": 0.42}
        )

        self.assertEqual(result["status"], LINKED_WITH_RECORDED_ISNAD)
        self.assertEqual(result["retrieval"]["rank"], 3)
        self.assertEqual(result["retrieval"]["score"], 0.42)
        self.assertEqual(result["retrieval"]["local_id_field_used"], "hadith_id")

    def test_adapter_does_not_reorder_or_choose_between_results(self):
        results = [{"hadith_id": 102, "rank": 1}, {"hadith_id": 100, "rank": 2}]
        enriched = [context_for_retrieval_result(self.connection, r) for r in results]

        # Order and rank survive; the unlinked result is not dropped or demoted.
        self.assertEqual([e["retrieval"]["rank"] for e in enriched], [1, 2])
        self.assertEqual(enriched[0]["status"], NO_ACCEPTED_MIS_LINK)
        self.assertEqual(enriched[1]["status"], LINKED_WITH_RECORDED_ISNAD)


class NoModelDependencyTests(unittest.TestCase):
    """السطح ده ما بيستوردش موديل ولا شبكة."""

    def test_module_imports_only_stdlib_and_the_graph_reader(self):
        tree = ast.parse(CONTEXT_MODULE.read_text(encoding="utf-8"))
        imported = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        self.assertEqual(imported, {"__future__", "sys", "pathlib", "sanad_graph"})

    def test_module_mentions_no_model_or_network_library(self):
        source = CONTEXT_MODULE.read_text(encoding="utf-8").lower()

        for banned in ("torch", "transformers", "faiss", "genai", "requests",
                       "urllib", "openai", "langgraph"):
            self.assertNotIn(banned, source)

    def test_no_agent_or_routing_construct_is_defined(self):
        tree = ast.parse(CONTEXT_MODULE.read_text(encoding="utf-8"))
        names = {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }

        for banned in ("route", "router", "plan", "agent", "classify", "decide"):
            self.assertFalse(
                any(banned in name.lower() for name in names),
                f"{banned!r} appears in {sorted(names)}",
            )


@pytest.mark.requires_data
class FrozenIdentityTests(unittest.TestCase):
    """السطح الجديد ما غيّرش أي بصمة مجمّدة."""

    @unittest.skipUnless(GRAPH_DB_PATH.exists(), "sanad graph not built")
    def test_chain_and_full_graph_hashes_are_unchanged(self):
        connection = connect(GRAPH_DB_PATH)
        try:
            self.assertEqual(chain_canonical_hash(connection), MIS_CHAIN_SHA256)
            self.assertEqual(full_canonical_hash(connection), FULL_GRAPH_SHA256)
        finally:
            connection.close()

    @unittest.skipUnless(FROZEN_LINKAGE_PATH.exists(), "linkage artifact not present")
    def test_frozen_linkage_is_unchanged(self):
        digest = hashlib.sha256(FROZEN_LINKAGE_PATH.read_bytes()).hexdigest()

        self.assertEqual(digest, FROZEN_LINKAGE_SHA256)

    @unittest.skipUnless(GRAPH_DB_PATH.exists(), "sanad graph not built")
    def test_the_surface_reports_the_frozen_linkage_artifact_it_used(self):
        connection = open_graph()
        try:
            linked = connection.execute(
                "SELECT local_id FROM hadith_mis_link LIMIT 1"
            ).fetchone()[0]
            result = context_for_local_hadith(connection, linked)
        finally:
            connection.close()

        self.assertEqual(
            result["linkage"]["linkage_artifact_sha256"], FROZEN_LINKAGE_SHA256
        )


if __name__ == "__main__":
    unittest.main()
