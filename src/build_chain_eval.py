"""Build ``data/raw/chain_eval.jsonl`` and stratified dev/test splits from SQLite.

All gold answers (narrator IDs, Arabic names, isnad counts, narrator presence
booleans, and unlinked/no-chain abstention flags) are computed deterministically
from ``sanad_graph.sqlite`` — never from any language model.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import RAW_DIR
from src.sanad_context import (
    LINKED_WITH_RECORDED_ISNAD,
    context_for_local_hadith,
    open_graph,
)
from src.sanad_graph import GRAPH_DB_PATH, get_narrator

CHAIN_EVAL_PATH = RAW_DIR / "chain_eval.jsonl"
CHAIN_EVAL_DEV_PATH = RAW_DIR / "chain_eval_dev.jsonl"
CHAIN_EVAL_TEST_PATH = RAW_DIR / "chain_eval_test.jsonl"


@dataclass(frozen=True)
class QuestionSpec:
    item_id: str
    split: str
    qtype: str
    question: str
    hadith_id: int
    requires_search: bool
    requires_isnad: bool = True
    target_role: str | None = None  # "companion" | "teacher" | None
    query_narrator_id: str | None = None
    expected_partial_abstain: bool = False
    grading_blocked: bool = False
    source: str = "graph"
    note: str = ""


_SPECS: tuple[QuestionSpec, ...] = (
    # ---- 1. who_narrated_companion (3 dev, 5 test) ----
    QuestionSpec(
        item_id="chain_comp_01",
        split="dev",
        qtype="who_narrated_companion",
        question="من الصحابي الذي روى حديث رقم 7296 عن النبي صلى الله عليه وسلم؟",
        hadith_id=7296,
        requires_search=False,
        target_role="companion",
    ),
    QuestionSpec(
        item_id="chain_comp_02",
        split="dev",
        qtype="who_narrated_companion",
        question="من روى الحديث رقم 7800 من الصحابة؟",
        hadith_id=7800,
        requires_search=False,
        target_role="companion",
    ),
    QuestionSpec(
        item_id="chain_comp_03",
        split="dev",
        qtype="who_narrated_companion",
        question="من الصحابي الذي روى الحديث رقم 9216 في صحيح مسلم؟",
        hadith_id=9216,
        requires_search=False,
        target_role="companion",
        note="Unlinked local hadith: must abstain cleanly.",
    ),
    QuestionSpec(
        item_id="chain_comp_04",
        split="test",
        qtype="who_narrated_companion",
        question="على لسان أي صحابي رُوي الحديث رقم 7448 في صحيح مسلم؟",
        hadith_id=7448,
        requires_search=False,
        target_role="companion",
    ),
    QuestionSpec(
        item_id="chain_comp_05",
        split="test",
        qtype="who_narrated_companion",
        question="من الصحابي راوي حديث 7652 في قاعدة البيانات؟",
        hadith_id=7652,
        requires_search=False,
        target_role="companion",
    ),
    QuestionSpec(
        item_id="chain_comp_06",
        split="test",
        qtype="who_narrated_companion",
        question="إلى أي صحابي ينتهي سند الحديث رقم 7950؟",
        hadith_id=7950,
        requires_search=False,
        target_role="companion",
    ),
    QuestionSpec(
        item_id="chain_comp_07",
        split="test",
        qtype="who_narrated_companion",
        question="من الصحابي الذي نقل حديث رقم 12400 عن رسول الله؟",
        hadith_id=12400,
        requires_search=False,
        target_role="companion",
    ),
    QuestionSpec(
        item_id="chain_comp_08",
        split="test",
        qtype="who_narrated_companion",
        question="من هو الصحابي الجليل في بداية سند الحديث رقم 11800؟",
        hadith_id=11800,
        requires_search=False,
        target_role="companion",
    ),
    # ---- 2. who_narrated_teacher (3 dev, 5 test) ----
    QuestionSpec(
        item_id="chain_teach_01",
        split="dev",
        qtype="who_narrated_teacher",
        question="من هو شيخ الإمام مسلم الذي روى عنه الحديث رقم 7502 مباشرة؟",
        hadith_id=7502,
        requires_search=False,
        target_role="teacher",
    ),
    QuestionSpec(
        item_id="chain_teach_02",
        split="dev",
        qtype="who_narrated_teacher",
        question="عمّن أخذ الإمام مسلم الحديث رقم 9450 في سنده؟",
        hadith_id=9450,
        requires_search=False,
        target_role="teacher",
    ),
    QuestionSpec(
        item_id="chain_teach_03",
        split="dev",
        qtype="who_narrated_teacher",
        question="من الراوي المباشر للإمام مسلم في حديث رقم 13920؟",
        hadith_id=13920,
        requires_search=False,
        target_role="teacher",
    ),
    QuestionSpec(
        item_id="chain_teach_04",
        split="test",
        qtype="who_narrated_teacher",
        question="من شيخ مسلم الذي يبدأ به إسناد الحديث رقم 9800؟",
        hadith_id=9800,
        requires_search=False,
        target_role="teacher",
    ),
    QuestionSpec(
        item_id="chain_teach_05",
        split="test",
        qtype="who_narrated_teacher",
        question="من روى الحديث رقم 10200 للإمام مسلم مباشرة؟",
        hadith_id=10200,
        requires_search=False,
        target_role="teacher",
    ),
    QuestionSpec(
        item_id="chain_teach_06",
        split="test",
        qtype="who_narrated_teacher",
        question="ما اسم شيخ الإمام مسلم في سند حديث رقم 10600؟",
        hadith_id=10600,
        requires_search=False,
        target_role="teacher",
    ),
    QuestionSpec(
        item_id="chain_teach_07",
        split="test",
        qtype="who_narrated_teacher",
        question="من هم شيوخ الإمام مسلم الذين روى عنهم الحديث رقم 9300 مباشرة؟",
        hadith_id=9300,
        requires_search=False,
        target_role="teacher",
    ),
    QuestionSpec(
        item_id="chain_teach_08",
        split="test",
        qtype="who_narrated_teacher",
        question="من هو شيخ الإمام مسلم الذي روى عنه الحديث رقم 8506 مباشرة؟",
        hadith_id=8506,
        requires_search=False,
        target_role="teacher",
        note="Unlinked local hadith: must abstain cleanly.",
    ),
    # ---- 3. isnad_count (3 dev, 5 test) ----
    QuestionSpec(
        item_id="chain_count_01",
        split="dev",
        qtype="isnad_count",
        question="كم عدد الأسانيد المسجلة للحديث رقم 14200 في قاعدة بيانات السند؟",
        hadith_id=14200,
        requires_search=False,
    ),
    QuestionSpec(
        item_id="chain_count_02",
        split="dev",
        qtype="isnad_count",
        question="كم طريقًا ورد بها إسناد الحديث رقم 9000؟",
        hadith_id=9000,
        requires_search=False,
    ),
    QuestionSpec(
        item_id="chain_count_03",
        split="dev",
        qtype="isnad_count",
        question="كم عدد الأسانيد المسجلة للحديث رقم 9263؟",
        hadith_id=9263,
        requires_search=False,
        note="Unlinked local hadith: must abstain cleanly.",
    ),
    QuestionSpec(
        item_id="chain_count_04",
        split="test",
        qtype="isnad_count",
        question="ما عدد الأسانيد المسجلة للحديث رقم 13707؟",
        hadith_id=13707,
        requires_search=False,
    ),
    QuestionSpec(
        item_id="chain_count_05",
        split="test",
        qtype="isnad_count",
        question="كم طريقًا إسناديًا مسجلًا لحديث رقم 9509؟",
        hadith_id=9509,
        requires_search=False,
    ),
    QuestionSpec(
        item_id="chain_count_06",
        split="test",
        qtype="isnad_count",
        question="كم عدد طرق السند للحديث رقم 8100؟",
        hadith_id=8100,
        requires_search=False,
    ),
    QuestionSpec(
        item_id="chain_count_07",
        split="test",
        qtype="isnad_count",
        question="كم إسنادًا للحديث رقم 7951 في قاعدة البيانات؟",
        hadith_id=7951,
        requires_search=False,
    ),
    QuestionSpec(
        item_id="chain_count_08",
        split="test",
        qtype="isnad_count",
        question="كم سلسلة إسناد موثقة للحديث رقم 10531؟",
        hadith_id=10531,
        requires_search=False,
    ),
    # ---- 4. narrator_in_chain (3 dev, 5 test) ----
    QuestionSpec(
        item_id="chain_in_01",
        split="dev",
        qtype="narrator_in_chain",
        question="هل ورد اسم ابن شهاب الزهري في سند الحديث رقم 8851؟",
        hadith_id=8851,
        requires_search=False,
        query_narrator_id="11013",
    ),
    QuestionSpec(
        item_id="chain_in_02",
        split="dev",
        qtype="narrator_in_chain",
        question="هل يظهر عروة بن الزبير في أي من أسانيد الحديث رقم 8500؟",
        hadith_id=8500,
        requires_search=False,
        query_narrator_id="10511",
    ),
    QuestionSpec(
        item_id="chain_in_03",
        split="dev",
        qtype="narrator_in_chain",
        question="هل شارك أبو هريرة في رواية الحديث رقم 13633؟",
        hadith_id=13633,
        requires_search=False,
        query_narrator_id="13",
    ),
    QuestionSpec(
        item_id="chain_in_04",
        split="test",
        qtype="narrator_in_chain",
        question="هل يظهر قتادة في أحد أسانيد الحديث رقم 7350؟",
        hadith_id=7350,
        requires_search=False,
        query_narrator_id="11019",
    ),
    QuestionSpec(
        item_id="chain_in_05",
        split="test",
        qtype="narrator_in_chain",
        question="هل ورد قتيبة بن سعيد في سلسلة إسناد الحديث رقم 7801؟",
        hadith_id=7801,
        requires_search=False,
        query_narrator_id="30367",
    ),
    QuestionSpec(
        item_id="chain_in_06",
        split="test",
        qtype="narrator_in_chain",
        question="هل يروي أنس بن مالك الحديث رقم 13634 في إسناده؟",
        hadith_id=13634,
        requires_search=False,
        query_narrator_id="19",
    ),
    QuestionSpec(
        item_id="chain_in_07",
        split="test",
        qtype="narrator_in_chain",
        question="هل وقع شعبة بن الحجاج في سند الحديث رقم 14560؟",
        hadith_id=14560,
        requires_search=False,
        query_narrator_id="20020",
    ),
    QuestionSpec(
        item_id="chain_in_08",
        split="test",
        qtype="narrator_in_chain",
        question="هل يظهر مالك بن أنس في سند الحديث رقم 9687؟",
        hadith_id=9687,
        requires_search=False,
        query_narrator_id="20001",
        note="Unlinked local hadith: must abstain cleanly.",
    ),
    # ---- 5. topic_who_narrated (3 dev, 5 test; includes the 3 golden narrator items) ----
    QuestionSpec(
        item_id="chain_topic_01",
        split="dev",
        qtype="topic_who_narrated",
        question="من هو الصحابي الذي روى حديث «كافل اليتيم أنا وهو كهاتين في الجنة»؟",
        hadith_id=14561,
        requires_search=True,
        target_role="companion",
        source="golden.jsonl",
        note="Golden narrator item #2.",
    ),
    QuestionSpec(
        item_id="chain_topic_02",
        split="dev",
        qtype="topic_who_narrated",
        question="من الصحابي الذي روى حديث «لا يؤمن أحدكم حتى يحب لأخيه ما يحب لنفسه»؟",
        hadith_id=7354,
        requires_search=True,
        target_role="companion",
    ),
    QuestionSpec(
        item_id="chain_topic_03",
        split="dev",
        qtype="topic_who_narrated",
        question="من هو الصحابي راوي حديث «إن الحلال بيّن وإن الحرام بيّن» في صحيح مسلم؟",
        hadith_id=11245,
        requires_search=True,
        target_role="companion",
    ),
    QuestionSpec(
        item_id="chain_topic_04",
        split="test",
        qtype="topic_who_narrated",
        question="من روى حديث «إنما الأعمال بالنية» وما حكم رواته؟",
        hadith_id=12068,
        requires_search=True,
        target_role="companion",
        expected_partial_abstain=True,
        source="golden.jsonl",
        note="Golden narrator item #1: narrator comes from graph; must abstain on grading.",
    ),
    QuestionSpec(
        item_id="chain_topic_05",
        split="test",
        qtype="topic_who_narrated",
        question="ما حكم الإمام ابن حجر على رواة سند حديث «الدين النصيحة»؟",
        hadith_id=7380,
        requires_search=True,
        requires_isnad=True,
        grading_blocked=True,
        source="golden.jsonl",
        note="Golden narrator item #3: Ibn Hajar grading unavailable in graph -> abstain.",
    ),
    QuestionSpec(
        item_id="chain_topic_06",
        split="test",
        qtype="topic_who_narrated",
        question="من روى عن النبي صلى الله عليه وسلم حديث «المسلم من سلم المسلمون من لسانه ويده»؟",
        hadith_id=7346,
        requires_search=True,
        target_role="companion",
    ),
    QuestionSpec(
        item_id="chain_topic_07",
        split="test",
        qtype="topic_who_narrated",
        question="من الصحابي الذي نقل حديث «بدأ الإسلام غريبًا وسيعود كما بدأ غريبًا»؟",
        hadith_id=7556,
        requires_search=True,
        target_role="companion",
    ),
    QuestionSpec(
        item_id="chain_topic_08",
        split="test",
        qtype="topic_who_narrated",
        question="من روى حديث «عجبًا لأمر المؤمن إن أمره كله خير» عن رسول الله؟",
        hadith_id=14591,
        requires_search=True,
        target_role="companion",
    ),
)


def _narrator_summary(n: dict[str, Any]) -> dict[str, str]:
    return {
        "narrator_id": str(n["narrator_id"]),
        "name_ar": str(n.get("name_ar") or ""),
        "name_ar_mapped": str(n.get("name_ar_mapped") or ""),
    }


def build_item_from_graph(conn: Any, spec: QuestionSpec) -> dict[str, Any]:
    ctx = context_for_local_hadith(conn, spec.hadith_id)
    has_chain = ctx["status"] == LINKED_WITH_RECORDED_ISNAD and ctx["isnad_count"] > 0

    all_narrators_by_id: dict[str, dict[str, str]] = {}
    companions_by_id: dict[str, dict[str, str]] = {}
    teachers_by_id: dict[str, dict[str, str]] = {}
    for isnad in ctx.get("isnads") or ():
        narrators = isnad.get("narrators") or ()
        if not narrators:
            continue
        for n in narrators:
            summary = _narrator_summary(n)
            all_narrators_by_id[summary["narrator_id"]] = summary
        c_sum = _narrator_summary(narrators[0])
        t_sum = _narrator_summary(narrators[-1])
        companions_by_id[c_sum["narrator_id"]] = c_sum
        teachers_by_id[t_sum["narrator_id"]] = t_sum

    expected_abstain = (not has_chain) or spec.grading_blocked
    expected_narrators: list[dict[str, str]] = []
    expected_count: int | None = None
    expected_bool: bool | None = None
    query_narrator: dict[str, str] | None = None

    if spec.query_narrator_id is not None:
        qn = get_narrator(conn, spec.query_narrator_id)
        query_narrator = _narrator_summary(qn)

    if not expected_abstain:
        if spec.target_role == "companion":
            expected_narrators = list(companions_by_id.values())
        elif spec.target_role == "teacher":
            expected_narrators = list(teachers_by_id.values())
        elif spec.qtype == "isnad_count":
            expected_count = int(ctx["isnad_count"])
        elif spec.qtype == "narrator_in_chain":
            assert spec.query_narrator_id is not None
            present = spec.query_narrator_id in all_narrators_by_id
            expected_bool = present
            if present and query_narrator is not None:
                expected_narrators = [query_narrator]

    return {
        "id": spec.item_id,
        "split": spec.split,
        "type": spec.qtype,
        "question": spec.question,
        "hadith_ids": [spec.hadith_id],
        "graph_status": ctx["status"],
        "isnad_count": int(ctx["isnad_count"]),
        "requires_search": spec.requires_search,
        "requires_isnad": spec.requires_isnad,
        "expected_abstain": expected_abstain,
        "expected_partial_abstain": spec.expected_partial_abstain,
        "expected_narrators": expected_narrators,
        "expected_count": expected_count,
        "expected_bool": expected_bool,
        "query_narrator": query_narrator,
        "allowed_narrators": list(all_narrators_by_id.values()),
        "source": spec.source,
        "note": spec.note,
    }


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_chain_eval_files(
    *,
    db_path: Path = GRAPH_DB_PATH,
    all_path: Path = CHAIN_EVAL_PATH,
    dev_path: Path = CHAIN_EVAL_DEV_PATH,
    test_path: Path = CHAIN_EVAL_TEST_PATH,
) -> dict[str, Any]:
    conn = open_graph(db_path)
    try:
        items = [build_item_from_graph(conn, spec) for spec in _SPECS]
    finally:
        conn.close()

    dev_items = [it for it in items if it["split"] == "dev"]
    test_items = [it for it in items if it["split"] == "test"]
    assert len(items) == 40
    assert len(dev_items) == 15
    assert len(test_items) == 25
    dev_ids = {hid for it in dev_items for hid in it["hadith_ids"]}
    test_ids = {hid for it in test_items for hid in it["hadith_ids"]}
    assert not (dev_ids & test_ids), f"Dev/Test hadith overlap: {dev_ids & test_ids}"

    for out_path, subset in ((all_path, items), (dev_path, dev_items), (test_path, test_items)):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            "\n".join(json.dumps(it, ensure_ascii=False) for it in subset) + "\n",
            encoding="utf-8",
        )

    return {
        "total": len(items),
        "dev_count": len(dev_items),
        "test_count": len(test_items),
        "all_sha256": _file_sha256(all_path),
        "dev_sha256": _file_sha256(dev_path),
        "test_sha256": _file_sha256(test_path),
    }


def main() -> None:
    if CHAIN_EVAL_TEST_PATH.exists():
        raise RuntimeError(
            f"Refusing to overwrite frozen split {CHAIN_EVAL_TEST_PATH}. "
            "chain_eval_test.jsonl is frozen after creation."
        )
    summary = write_chain_eval_files()
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
