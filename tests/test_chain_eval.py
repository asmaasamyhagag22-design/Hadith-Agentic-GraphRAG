"""Offline unit tests for narrator lexicon and deterministic chain evaluation."""

from __future__ import annotations

import json
import unittest

from src.build_chain_eval import (
    CHAIN_EVAL_DEV_PATH,
    CHAIN_EVAL_PATH,
    CHAIN_EVAL_TEST_PATH,
)
from src.chain_eval import (
    answer_matches_boolean,
    answer_matches_count,
    evaluate_chain_predictions,
    load_chain_eval,
    run_chain_eval,
    score_chain_item,
)
from src.config import GOLDEN_PATH
from src.sanad_names import NarratorLexicon, find_disallowed_narrators


SAMPLE_RECORDS = [
    {"narrator_id": "3", "name_ar": "عمر بن الخطاب بن نفيل", "name_ar_mapped": "عمر بن الخطاب بن نفيل"},
    {"narrator_id": "13", "name_ar": "أبو هريرة الدوسى", "name_ar_mapped": "أبو هريرة - عبد الرحمن بن صخر الدوسي"},
    {"narrator_id": "18", "name_ar": "عبد الله بن عمر بن الخطاب", "name_ar_mapped": "عبد الله بن عمر بن الخطاب"},
    {"narrator_id": "19", "name_ar": "أنس بن مالك بن النضر", "name_ar_mapped": "أنس بن مالك بن النضر"},
    {"narrator_id": "53", "name_ar": "عائشة بنت أبى بكر الصديق", "name_ar_mapped": "أمّ المؤمنين عائشة بنت أبي بكر الصديق"},
    {"narrator_id": "10950", "name_ar": "على بن عبد الله البارقى الأزدى", "name_ar_mapped": "علي بن عبد الله"},
    {"narrator_id": "20001", "name_ar": "مالك بن أنس الأصبحى", "name_ar_mapped": "مالك بن أنس بن مالك بن أبي عامر"},
    {"narrator_id": "20164", "name_ar": "عبد الله بن مسلمة بن قعنب القعنبى", "name_ar_mapped": "عبد الله بن مسلمة بن قعنب القعنبي"},
    {"narrator_id": "30201", "name_ar": "أبو بكر بن أبى شيبة", "name_ar_mapped": "أبو بكر بن أبي شيبة"},
    {"narrator_id": "30212", "name_ar": "محمد بن عبد الله بن نمير", "name_ar_mapped": "محمد بن عبد الله بن نمير"},
]


def _ctx(hadith_id: int, narrators: list[dict], isnad_count: int = 1, status: str = "LINKED_WITH_RECORDED_ISNAD") -> dict:
    return {
        "local_hadith_id": hadith_id,
        "status": status,
        "isnad_count": isnad_count,
        "isnads": [{"sanad_no": 1, "narrators": narrators}] if narrators else [],
    }


class SanadNamesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lex = NarratorLexicon.from_records(SAMPLE_RECORDS)

    def test_proclitics_and_allowed_subset(self) -> None:
        ctx = _ctx(12068, [SAMPLE_RECORDS[0], SAMPLE_RECORDS[7]])
        self.assertEqual(
            find_disallowed_narrators("روى الحديث عمر بن الخطاب [12068] عن طريق القعنبي.", [ctx], self.lex),
            [],
        )
        self.assertEqual(
            find_disallowed_narrators("روى الحديث عمر بن الخطاب وأبو هريرة [12068].", [ctx], self.lex),
            ["ابو هريرة"],
        )
        self.assertEqual(
            find_disallowed_narrators("لأبي هريرة وعائشة رواية في [12068].", [ctx], self.lex),
            ["ابو هريرة", "عائشة"],
        )

    def test_longest_span_avoids_nested_false_positive(self) -> None:
        ctx = _ctx(7296, [SAMPLE_RECORDS[2]])
        # Mentioning عبد الله بن عمر بن الخطاب must NOT trigger عمر بن الخطاب.
        self.assertEqual(
            find_disallowed_narrators("روى هذا الحديث عبد الله بن عمر بن الخطاب [7296].", [ctx], self.lex),
            [],
        )

    def test_ordinary_arabic_religious_phrases_do_not_false_trigger(self) -> None:
        text = "توكّل على الله كما بيّن نبي الله داود وعبد الله الصالح في صحيح مسلم."
        self.assertEqual(self.lex.find_mentions(text), [])

    def test_anonymous_mis_descriptions_do_not_false_trigger(self) -> None:
        records = [
            {"narrator_id": "NM_49", "name_ar": "من أدرك من الصحابة [ سهل بن أبى حثمة ]", "name_ar_mapped": "NotMapped-49"},
            {"narrator_id": "NM_26", "name_ar": "إحدى نسوة النبى [ حفصة أم المؤمنين ]", "name_ar_mapped": "NotMapped-26"},
            {"narrator_id": "NM_35", "name_ar": "أصحاب رسول الله [ سهل بن أبى حثمة ]", "name_ar_mapped": "NotMapped-35"},
            {"narrator_id": "56_1", "name_ar": "بعض أزواج النبى [ أم سلمة ]", "name_ar_mapped": "أم سلمة بنت أبي أمية"},
        ]
        lex = NarratorLexicon.from_records(records)
        prose = "روى هذا الحديث من الصحابة وأصحاب رسول الله وبعض أزواج النبي وإحدى نسوة النبي."
        self.assertEqual(lex.find_mentions(prose), [])


class ChainEvalScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lex = NarratorLexicon.from_records(SAMPLE_RECORDS)

    def test_companion_and_hallucination_rejection(self) -> None:
        item = {
            "id": "t_comp",
            "type": "who_narrated_companion",
            "question": "من الصحابي الذي روى حديث رقم 12068؟",
            "hadith_ids": [12068],
            "requires_search": False,
            "requires_isnad": True,
            "expected_abstain": False,
            "expected_narrators": [SAMPLE_RECORDS[0]],
        }
        ctx = _ctx(12068, [SAMPLE_RECORDS[0], SAMPLE_RECORDS[7]])

        good = score_chain_item(
            item,
            {
                "answer": "الصحابي الذي روى الحديث هو عمر بن الخطاب [12068].",
                "tool_calls": [{"name": "get_isnad", "args": {"hadith_id": 12068}, "result": ctx}],
            },
            lexicon=self.lex,
        )
        self.assertTrue(good["routing_correct"])
        self.assertTrue(good["answer_correct"])
        self.assertTrue(good["no_hallucinated_narrators"])

        # Missing get_isnad -> fails both routing and hallucination guard!
        ungrounded = score_chain_item(
            item,
            {
                "answer": "الصحابي هو عمر بن الخطاب [12068].",
                "tool_calls": [],
            },
            lexicon=self.lex,
        )
        self.assertFalse(ungrounded["routing_correct"])
        self.assertFalse(ungrounded["no_hallucinated_narrators"])
        self.assertFalse(ungrounded["answer_correct"])

        # Correct narrator + extra hallucinated narrator -> fails!
        extra_bad = score_chain_item(
            item,
            {
                "answer": "رواه عمر بن الخطاب وأبو هريرة [12068].",
                "tool_calls": [{"name": "get_isnad", "args": {"hadith_id": 12068}, "result": ctx}],
            },
            lexicon=self.lex,
        )
        self.assertFalse(extra_bad["no_hallucinated_narrators"])
        self.assertFalse(extra_bad["answer_correct"])

    def test_isnad_count_matching_ignores_citation_digits(self) -> None:
        self.assertTrue(answer_matches_count("للحديث [14200] إسناد واحد مسجل.", 1))
        self.assertTrue(answer_matches_count("ورد الحديث رقم 9509 عبر 5 أسانيد.", 5))
        self.assertTrue(answer_matches_count("له ٤ سلاسل إسناد موثقة.", 4))
        self.assertFalse(answer_matches_count("للحديث [14200] إسنادان اثنان.", 4))

    def test_narrator_in_chain_positive_and_negative(self) -> None:
        self.assertTrue(answer_matches_boolean("نعم، ورد مالك بن أنس في السند [14560].", True))
        self.assertTrue(answer_matches_boolean("لا، لم يرد الراوي المذكور في أسانيد الحديث [14560].", False))
        self.assertFalse(answer_matches_boolean("لا، لم يرد في السند.", True))

        item_neg = {
            "id": "t_neg",
            "type": "narrator_in_chain",
            "question": "هل ورد أبو هريرة في سند الحديث رقم 12068؟",
            "hadith_ids": [12068],
            "requires_search": False,
            "requires_isnad": True,
            "expected_abstain": False,
            "expected_bool": False,
            "expected_narrators": [],
        }
        ctx = _ctx(12068, [SAMPLE_RECORDS[0], SAMPLE_RECORDS[7]])
        clean_neg = score_chain_item(
            item_neg,
            {
                "answer": "لا، لم يرد الراوي المذكور في أسانيد الحديث [12068].",
                "tool_calls": [{"name": "get_isnad", "args": {"hadith_id": 12068}, "result": ctx}],
            },
            lexicon=self.lex,
        )
        self.assertTrue(clean_neg["answer_correct"])
        self.assertTrue(clean_neg["no_hallucinated_narrators"])

        echo_neg = score_chain_item(
            item_neg,
            {
                "answer": "لا، لم يرد أبو هريرة في سند [12068].",
                "tool_calls": [{"name": "get_isnad", "args": {"hadith_id": 12068}, "result": ctx}],
            },
            lexicon=self.lex,
        )
        self.assertFalse(echo_neg["no_hallucinated_narrators"])
        self.assertFalse(echo_neg["answer_correct"])

    def test_abstention_and_partial_grading_abstention(self) -> None:
        item_unlinked = {
            "id": "t_abst",
            "type": "who_narrated_companion",
            "question": "من الصحابي الذي روى الحديث رقم 9216؟",
            "hadith_ids": [9216],
            "requires_search": False,
            "requires_isnad": True,
            "expected_abstain": True,
            "expected_narrators": [],
        }
        ctx_empty = _ctx(9216, [], isnad_count=0, status="VALID_LOCAL_HADITH_BUT_NO_ACCEPTED_MIS_LINK")
        good_abst = score_chain_item(
            item_unlinked,
            {
                "answer": "الحديث [9216] لا يوجد له ربط مقبول أو إسناد مسجل في قاعدة بيانات السند.",
                "tool_calls": [{"name": "get_isnad", "args": {"hadith_id": 9216}, "result": ctx_empty}],
            },
            lexicon=self.lex,
        )
        self.assertTrue(good_abst["abstain_correct"])
        self.assertTrue(good_abst["answer_correct"])

        # Partial grading item (#1 golden)
        item_partial = {
            "id": "t_part",
            "type": "topic_who_narrated",
            "question": "من روى حديث «إنما الأعمال بالنية» وما حكم رواته؟",
            "hadith_ids": [12068],
            "requires_search": True,
            "requires_isnad": True,
            "expected_abstain": False,
            "expected_partial_abstain": True,
            "expected_narrators": [SAMPLE_RECORDS[0]],
        }
        ctx = _ctx(12068, [SAMPLE_RECORDS[0], SAMPLE_RECORDS[7]])
        good_part = score_chain_item(
            item_partial,
            {
                "answer": "رواه عمر بن الخطاب [12068]، ولا تتوفر أحكام الجرح والتعديل لرواته في قاعدة البيانات.",
                "tool_calls": [
                    {"name": "search_hadith", "args": {"query": "إنما الأعمال بالنية"}, "result": [{"hadith_id": 12068}]},
                    {"name": "get_isnad", "args": {"hadith_id": 12068}, "result": ctx},
                ],
            },
            lexicon=self.lex,
        )
        self.assertTrue(good_part["routing_correct"])
        self.assertTrue(good_part["answer_correct"])

        fabricated = score_chain_item(
            item_partial,
            {
                "answer": "رواه عمر بن الخطاب [12068] ورواته ثقات وإسناده صحيح.",
                "tool_calls": [
                    {"name": "search_hadith", "args": {"query": "إنما الأعمال بالنية"}, "result": [{"hadith_id": 12068}]},
                    {"name": "get_isnad", "args": {"hadith_id": 12068}, "result": ctx},
                ],
            },
            lexicon=self.lex,
        )
        self.assertFalse(fabricated["answer_correct"])

    def test_topic_routing_requires_search_and_isnad(self) -> None:
        item = {
            "id": "t_topic",
            "type": "topic_who_narrated",
            "question": "من روى حديث كافل اليتيم؟",
            "hadith_ids": [14561],
            "requires_search": True,
            "requires_isnad": True,
            "expected_abstain": False,
            "expected_narrators": [SAMPLE_RECORDS[1]],
        }
        ctx = _ctx(14561, [SAMPLE_RECORDS[1]])
        res = evaluate_chain_predictions(
            [item],
            [
                {
                    "answer": "رواه أبو هريرة [14561].",
                    "tool_calls": [
                        {"name": "search_hadith", "args": {"query": "كافل اليتيم"}, "result": [{"hadith_id": 14561}]},
                        {"name": "get_isnad", "args": {"hadith_id": 14561}, "result": ctx},
                    ],
                }
            ],
            lexicon=self.lex,
        )
        self.assertEqual(res["routing_accuracy"], 1.0)
        self.assertEqual(res["answer_accuracy"], 1.0)

        ran = run_chain_eval(
            lambda _q: {"answer": "المصادر المتاحة لا تجيب عن هذا السؤال", "tool_calls": []},
            [item],
            lexicon=self.lex,
        )
        self.assertEqual(ran["routing_correct"], 0)
        self.assertEqual(ran["answer_correct"], 0)
        self.assertIn("latency_median_ms", ran)


class ChainEvalDatasetStructureTests(unittest.TestCase):
    def test_splits_stratification_and_golden_inclusion(self) -> None:
        all_items = load_chain_eval(CHAIN_EVAL_PATH)
        dev_items = load_chain_eval(CHAIN_EVAL_DEV_PATH)
        test_items = load_chain_eval(CHAIN_EVAL_TEST_PATH)

        self.assertEqual(len(all_items), 40)
        self.assertEqual(len(dev_items), 15)
        self.assertEqual(len(test_items), 25)
        self.assertEqual({it["id"] for it in dev_items} | {it["id"] for it in test_items}, {it["id"] for it in all_items})

        dev_ids = {hid for it in dev_items for hid in it["hadith_ids"]}
        test_ids = {hid for it in test_items for hid in it["hadith_ids"]}
        self.assertFalse(dev_ids & test_ids)

        for split_items, expected_per_type in ((dev_items, 3), (test_items, 5)):
            counts: dict[str, int] = {}
            for it in split_items:
                counts[it["type"]] = counts.get(it["type"], 0) + 1
            self.assertEqual(len(counts), 5)
            for qtype, cnt in counts.items():
                self.assertEqual(cnt, expected_per_type, f"Type {qtype} count mismatch")

        with GOLDEN_PATH.open("r", encoding="utf-8") as fh:
            golden_narrators = [
                json.loads(line)["question"]
                for line in fh
                if line.strip() and json.loads(line).get("type") == "narrator"
            ]
        all_questions = {it["question"] for it in all_items}
        for q in golden_narrators:
            self.assertIn(q, all_questions)


if __name__ == "__main__":
    unittest.main()
