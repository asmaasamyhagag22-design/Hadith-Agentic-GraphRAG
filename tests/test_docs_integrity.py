import hashlib
import re
import unittest
from pathlib import Path

import pytest

from src.build_sanad_graph import (
    FROZEN_LINKAGE_PATH,
    GRAPH_DB_PATH,
    chain_canonical_hash,
    connect,
    full_canonical_hash,
)
from src.check_docs import (
    EXPERIMENTS,
    README,
    canonical_hash,
    denominator_problems,
    parse_canonical,
    prose_problems,
    recorded_hash,
    results_problems,
    section_problems,
)
from src.config import GOLDEN_PATH, MUSLIM_JSON_PATH, SYNTHETIC_EVAL_PATH

MIS_CHAIN_SHA256 = "496ccf1da21d2e849a94fb2d2e0d4ae66e3bfa549f4ce555f5cf2f4d490bfbce"
FULL_GRAPH_SHA256 = "c8818da00bf27f74750105ed6bf2d57e674c26e3dfe63b9ec8774c6a4d6e481c"
FROZEN_LINKAGE_SHA256 = (
    "9c3a48e7a0af4f0df1cd9250f49a90f343228b614587196fcf2fa6fbfa572c77"
)

ANSWER_EVAL = Path(__file__).resolve().parent.parent / "src" / "answer_eval.py"


def readme_text():
    return README.read_text(encoding="utf-8")


def experiments_text():
    return EXPERIMENTS.read_text(encoding="utf-8")


class CheckerPassesOnCurrentDocsTests(unittest.TestCase):
    """الفحص بيعدّي على التوثيق الحالي زي ما هو."""

    def test_current_documentation_passes_every_check(self):
        readme, experiments = readme_text(), experiments_text()

        self.assertEqual(results_problems(readme, experiments)[0], [])
        self.assertEqual(section_problems(experiments)[0], [])
        self.assertEqual(denominator_problems(experiments)[0], [])
        self.assertEqual(prose_problems(readme, experiments)[0], [])

    def test_the_checker_actually_inspects_something(self):
        readme, experiments = readme_text(), experiments_text()

        self.assertGreater(results_problems(readme, experiments)[1], 20)
        self.assertGreater(denominator_problems(experiments)[1], 10)


class CheckerRejectsMisattributionTests(unittest.TestCase):
    """رقم صحيح منسوب لمقياس غلط لازم يفشل."""

    def test_two_swapped_percentages_are_rejected(self):
        readme = readme_text()
        experiments = experiments_text()

        # Swap hit@1 between the two dense/BM25 rows: both values still exist
        # in the document, only their association changes.
        swapped = readme.replace(
            "| Dense only | 41% |", "| Dense only | 33% |"
        ).replace(
            "| BM25 only | 33% |", "| BM25 only | 41% |"
        )
        self.assertNotEqual(swapped, readme)

        problems, _ = results_problems(swapped, experiments)
        self.assertTrue(problems)
        self.assertTrue(any("hit@1" in problem for problem in problems))

    def test_a_renamed_metric_row_is_rejected_even_with_a_valid_number(self):
        original = readme_text()
        readme = original.replace("| Correct citation |", "| Citation accuracy |", 1)
        self.assertNotEqual(readme, original, "mutation was a no-op")

        problems, _ = results_problems(readme, experiments_text())

        self.assertTrue(problems)
        self.assertTrue(any("Citation_accuracy" in problem for problem in problems))

    def test_a_changed_value_is_rejected(self):
        original = readme_text()
        readme = original.replace("| Hybrid (RRF) | 44% |", "| Hybrid (RRF) | 56% |")
        self.assertNotEqual(readme, original, "mutation was a no-op")

        problems, _ = results_problems(readme, experiments_text())

        self.assertTrue(problems)

    def test_an_unrecorded_derived_percentage_in_prose_is_rejected(self):
        readme = readme_text() + "\nRelative gain: +75%.\n"

        problems, _ = prose_problems(readme, experiments_text())

        self.assertTrue(problems)
        self.assertTrue(any("75%" in problem for problem in problems))


class CheckerRejectsDenominatorProblemsTests(unittest.TestCase):
    """النسبة من غير مقام، أو بمقام غلط، لازم تتمسك."""

    def test_a_rate_without_a_denominator_is_rejected(self):
        original = experiments_text()
        experiments = original.replace("Correct_citation=63%@27", "Correct_citation=63%", 1)
        self.assertNotEqual(experiments, original, "mutation was a no-op")

        problems, _ = denominator_problems(experiments)

        self.assertTrue(problems)
        self.assertTrue(any("denominator" in problem for problem in problems))

    def test_the_answer_metrics_do_not_all_share_one_denominator(self):
        # The defect being guarded: a single "30 questions" heading over metrics
        # computed on 27, 30, 20/22 and 3.
        canonical = parse_canonical(experiments_text())
        denominators = {
            denominator
            for (table, _), record in canonical.items() if table == "answer_quality"
            for _, (_, denominator) in record["metrics"].items() if denominator
        }

        self.assertIn("27", denominators)
        self.assertIn("30", denominators)
        self.assertGreaterEqual(len(denominators), 3)

    def test_correct_citation_is_recorded_over_answerable_questions(self):
        canonical = parse_canonical(experiments_text())
        for (table, _), record in canonical.items():
            if table == "answer_quality":
                self.assertEqual(record["metrics"]["Correct_citation"][1], "27")


class CheckerRejectsWrongSectionTests(unittest.TestCase):
    """قيمة منسوبة لقسم مش فيها لازم تفشل."""

    def test_a_value_attributed_to_the_wrong_section_is_rejected(self):
        # Point the reranked row at the hybrid section; the value 0.665 lives
        # in section 6, not section 5.
        experiments = experiments_text().replace(
            "retrieval_golden | hybrid_rerank | Hybrid + rerank (baseline) | dataset=golden.jsonl n=27 section=6",
            "retrieval_golden | hybrid_rerank | Hybrid + rerank (baseline) | dataset=golden.jsonl n=27 section=5",
        )

        self.assertNotEqual(experiments, experiments_text(), "mutation was a no-op")

        problems, _ = section_problems(experiments)

        self.assertTrue(problems)
        self.assertTrue(any("0.665" in problem for problem in problems))

    def test_a_record_declaring_no_section_is_rejected(self):
        original = experiments_text()
        experiments = original.replace(
            "dataset=golden.jsonl n=27 section=5 | hit@1=41%",
            "dataset=golden.jsonl n=27 | hit@1=41%", 1,
        )
        self.assertNotEqual(experiments, original, "mutation was a no-op")

        problems, _ = section_problems(experiments)

        self.assertTrue(problems)


class ScopeHeaderTests(unittest.TestCase):
    """رأس المستند ما يقدرش يقول إن الجراف مش مبني."""

    def test_header_does_not_declare_the_graph_unbuilt(self):
        header = experiments_text().split("## نسخة القياس")[0]

        # The graph, the bridge and the context surface are measured in 17-19.
        self.assertNotIn("غير مبنية", header)

    def test_header_names_both_the_built_and_the_unbuilt_layers(self):
        header = experiments_text().split("## نسخة القياس")[0]

        self.assertIn("مبني فعلًا", header)
        self.assertIn("مش مبني", header)
        # identity and agents must still be listed as absent
        self.assertIn("LangGraph", header)

    def test_the_document_still_contains_the_measured_graph_sections(self):
        experiments = experiments_text()

        self.assertIn("## 17.", experiments)
        self.assertIn("## 18.", experiments)
        self.assertIn("## 19.", experiments)


class HistoricalIdentityUnitTests(unittest.TestCase):
    """1,524 و1,569 لازم يبانوا كوحدتين مختلفتين."""

    def test_both_figures_appear_with_their_units_distinguished(self):
        experiments = experiments_text()

        self.assertIn("1,524", experiments)
        self.assertIn("1,569", experiments)
        self.assertIn("grouping records", experiments)
        self.assertIn("unique profile-ID sets", experiments)

    def test_the_rule_table_reports_records_and_sets_separately(self):
        experiments = experiments_text()

        self.assertIn("triggered records", experiments)
        self.assertIn("triggered sets", experiments)
        self.assertRegex(experiments, r"19,253 \| 19,036")
        self.assertRegex(experiments, r"\*\*1,569\*\* \| \*\*1,524\*\*")


class AnswerEvalCostWordingTests(unittest.TestCase):
    """ما ينفعش يقول إن التقييم كله مجاني وهو بينادي المولّد."""

    def test_module_calls_the_generator(self):
        source = ANSWER_EVAL.read_text(encoding="utf-8")

        self.assertIn("answer_with_details", source)

    def test_docstring_does_not_call_the_whole_evaluation_free(self):
        source = ANSWER_EVAL.read_text(encoding="utf-8")
        docstring = source.split('"""')[1]

        self.assertNotIn("فهي\nمجانية ومتكررة", docstring)
        # it must say the run itself costs quota
        self.assertIn("مش مجاني", docstring)
        self.assertIn("Vertex", docstring)


class QueryExpansionClaimTests(unittest.TestCase):
    """توسيع الاستعلام فرضية، مش نتيجة مقيسة."""

    def test_readme_does_not_present_query_expansion_as_the_next_measured_step(self):
        readme = readme_text()

        self.assertNotIn("The immediate next retrieval step is query expansion", readme)

    def test_readme_marks_query_expansion_as_an_unvalidated_hypothesis(self):
        experiments = experiments_text()
        window = experiments[experiments.find("Query expansion"):][:400]

        self.assertIn("hypothesis", window.lower())
        self.assertIn("unvalidated", window.lower())

    def test_the_unretrievable_cases_have_provenance(self):
        experiments = experiments_text()

        # the three question ids and the depth actually measured
        for expected in ("9679", "7466", "depth 50"):
            self.assertIn(expected, experiments)


class RefusalClaimTests(unittest.TestCase):
    """الرفض ما بيمنعش الاستشهاد الغلط من داخل السياق."""

    def test_readme_no_longer_claims_refusal_prevents_the_failure(self):
        readme = readme_text()

        self.assertNotIn(
            "refusal behaviour is what keeps that from becoming a fabricated answer",
            readme,
        )

    def test_readme_separates_out_of_context_from_wrong_in_context(self):
        readme = readme_text().lower()

        self.assertIn("outside the retrieved evidence", readme)
        self.assertIn("wrong hadith chosen from within it", readme)

    def test_the_wrong_in_context_rate_is_stated_where_the_claim_is_made(self):
        readme = readme_text()
        start = readme.find("**Answer quality")
        end = readme.find("\n---\n", start)
        window = readme[start:end]

        self.assertIn("1%", window)
        self.assertIn("7%", window)
        self.assertIn("8%", window)
        self.assertIn("23%", window)
        self.assertIn("wrong hadith chosen from within it", window)


class FrozenIdentityTests(unittest.TestCase):
    """ولا بصمة مجمّدة اتغيرت."""

    def test_evaluation_dataset_hashes_are_unchanged(self):
        experiments = experiments_text()

        for path, expected in (
            (GOLDEN_PATH, "a7ec05f48ec0491a"),
            (SYNTHETIC_EVAL_PATH, "4bec52d5a56a8fc8"),
            (MUSLIM_JSON_PATH, "63a99e46155dc6e9"),
        ):
            self.assertEqual(canonical_hash(path), expected, path.name)
            self.assertEqual(recorded_hash(experiments, path.name), expected, path.name)

    @pytest.mark.requires_data
    @unittest.skipUnless(FROZEN_LINKAGE_PATH.exists(), "linkage artifact not present")
    def test_frozen_linkage_is_unchanged(self):
        digest = hashlib.sha256(FROZEN_LINKAGE_PATH.read_bytes()).hexdigest()

        self.assertEqual(digest, FROZEN_LINKAGE_SHA256)

    @pytest.mark.requires_data
    @unittest.skipUnless(GRAPH_DB_PATH.exists(), "sanad graph not built")
    def test_graph_hashes_are_unchanged(self):
        connection = connect(GRAPH_DB_PATH)
        try:
            self.assertEqual(chain_canonical_hash(connection), MIS_CHAIN_SHA256)
            self.assertEqual(full_canonical_hash(connection), FULL_GRAPH_SHA256)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
