"""
قياس أخطاء الإجابة — مش الاسترجاع.

`evaluate.py` بيقول هل الحديث الصح وصل للسياق. الملف ده
بيقول إيه اللي حصل بعد كده: هل استشهد برقم مش موجود؟ هل
رفض وهو شايف الإجابة؟ هل رفض في السؤال اللي مالوش إجابة؟

**حساب المقاييس** هنا برمجي بالكامل — مفيش حَكَم LLM —
فهو محتوم ومتكرر ومجاني.

**تشغيل التقييم نفسه مش مجاني.** الملف ده بينادي مولّد
الإجابة (Gemini عبر Vertex) لكل سؤال في كل إعداد، فبيستهلك
حصة وتكلفة. الجزء المجاني هو تحويل المخرَج لأرقام، مش
إنتاج المخرَج.

ملاحظة على التصميم: `invalid_citation_attempts` بتتقاس على
**مخرَج الموديل الخام** قبل أي تصفية. لو قِسناها بعد
التصفية هتطلع صفر دايمًا بحكم البناء، وده رقم بلا معنى.
"""

import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import GOLDEN_PATH
from evaluate import load_golden, build_retrievers
from rerank import DEFAULT_MODEL
from answer import (
    answer_with_details,
    cited_ids,
    validate_answer,
    REFUSAL,
    VALID_ANSWER,
    VALID_REFUSAL,
)

DEFAULT_K = 5
DEFAULT_RERANKERS = (DEFAULT_MODEL,)


def is_refusal(answer):

    return REFUSAL.split("لا تجيب")[0].strip() in answer or REFUSAL in answer


class Counter:

    def __init__(self):
        self.rows = []

    def add(self, **kwargs):
        self.rows.append(kwargs)

    def rate(self, key, among=None):

        rows = [r for r in self.rows if among is None or r.get(among)]

        if not rows:
            return None, 0, 0

        hits = sum(1 for r in rows if r.get(key))
        return hits / len(rows), hits, len(rows)


def evaluate_answers(
    retriever,
    items,
    k=DEFAULT_K,
    enforce_citations=True,
    self_correct=False,
):

    counter = Counter()

    for idx, item in enumerate(items, start=1):

        details = answer_with_details(
            item["question"],
            retriever,
            k=k,
            enforce_citations=enforce_citations,
            self_correct=self_correct,
        )

        answer = details["answer"]
        raw = details["raw"]
        chunks = details["chunks"]

        context_ids = {c["hadith_id"] for c in chunks}
        gold_ids = set(item.get("hadith_ids", []))

        cited = cited_ids(answer)
        refused = is_refusal(answer)

        old_invalid = bool(cited_ids(raw) - context_ids)
        raw_status = validate_answer(raw, context_ids)
        new_invalid = raw_status not in (VALID_ANSWER, VALID_REFUSAL)
        loophole = (not old_invalid) and new_invalid

        counter.add(
            index=idx,
            question=item["question"],
            answerable=item.get("answerable", True),
            refusal_test=item.get("type") == "refusal",
            gold_in_context=bool(gold_ids & context_ids),
            refused=refused,
            cited_anything=bool(cited),
            # على المحاولة الخام قبل التصفية — ده الرقم
            # اللي بيقيس تحسّن حقيقي
            invalid_citation=details["invalid_citation_attempt"],
            missing_citation=details["missing_citation_attempt"],
            loose_out_of_context=details["loose_out_of_context_attempt"],
            mixed_refusal=details["mixed_refusal_attempt"],
            loophole=loophole,
            raw_status=raw_status.value,
            regenerated=details["regenerated"],
            # استشهاد بحديث موجود في السياق لكنه مش الصح
            wrong_citation=bool(cited and cited <= context_ids
                                and not (cited & gold_ids)),
            correct_citation=bool(cited & gold_ids),
            answer=answer,
            raw=raw,
            retried=details.get("retried", False),
        )

    return counter


def report(label, counter):

    print(f"\n{label}")
    print("-" * len(label))

    metrics = [
        ("invalid citation attempts", "invalid_citation", None),
        ("missing citation attempts", "missing_citation", None),
        ("loose out-of-context attempts", "loose_out_of_context", None),
        ("mixed refusal attempts", "mixed_refusal", None),
        ("wrong citation (in context)", "wrong_citation", None),
        ("correct citation", "correct_citation", "answerable"),
        ("false refusal (gold was there)", "refused", "gold_in_context"),
        ("refusal on refusal tests", "refused", "refusal_test"),
        ("cited a source while refusing", "cited_anything", "refused"),
    ]

    for name, key, among in metrics:

        rate, hits, total = counter.rate(key, among)

        if rate is None:
            print(f"  {name:<32} n/a")
            continue

        print(f"  {name:<32} {rate:>5.0%}   ({hits}/{total} questions)")

    loopholes = [r for r in counter.rows if r["loophole"]]
    regenerated = sum(1 for r in counter.rows if r["regenerated"])
    calls = len(counter.rows) + regenerated
    print(f"  {'loophole cases (old pass, new fail)':<32} {len(loopholes)}/{len(counter.rows)}")
    print(f"  {'regenerated (retried once)':<32} {regenerated}/{len(counter.rows)}")
    print(f"  {'gemini calls used':<32} {calls}")


def main(k=DEFAULT_K, rerankers=DEFAULT_RERANKERS, include_crag=False):
    """
    بيقارن نفس المولّد على إعدادات استرجاع مختلفة — السؤال
    اللي بيجاوب عنه: هل تحسين الاسترجاع بيتحوّل فعلاً
    لإجابات أصح، ولا الطبقة اللغوية هي عنق الزجاجة؟
    """

    items = load_golden(GOLDEN_PATH)

    # أسئلة الرواة مالهاش إجابة نصية دلوقتي — بتتقاس
    # في أسبوع 2 لما الجراف يشتغل.
    items = [i for i in items if i.get("type") != "narrator"]

    from answer import MODEL

    print(f"Answer evaluation — {len(items)} questions, k={k}")
    print(f"Generator: {MODEL}")

    wanted = ["Hybrid: dense + BM25"] + [
        f"Hybrid + {name.split('/')[-1]}" for name in rerankers
    ]

    retrievers = dict(build_retrievers(rerankers))

    configurations = [(label, retrievers[label], False) for label in wanted]

    if include_crag:
        configurations.append(
            (f"{wanted[-1]} + CRAG", retrievers[wanted[-1]], True)
        )

    for label, retriever, self_correct in configurations:

        counter = evaluate_answers(
            retriever, items, k=k, self_correct=self_correct
        )

        report(label, counter)

        if self_correct:
            retried = sum(1 for r in counter.rows if r["retried"])
            print(f"  {'rewrote and retried':<32} {retried} questions")

        for row in counter.rows:
            if row["invalid_citation"]:
                print(f"\n  invented a citation: #{row['index']} {row['question']}")
                print(f"    {row['raw'][:200]}")
            if row["loophole"]:
                print(
                    f"\n  loophole caught ({row['raw_status']}): "
                    f"#{row['index']} {row['question']}"
                )
                print(f"    raw   : {row['raw']}")
                print(f"    final : {row['answer']}")


if __name__ == "__main__":

    args = sys.argv[1:]

    main(
        k=int(args[0]) if args else DEFAULT_K,
        rerankers=args[1:] if len(args) > 1 else DEFAULT_RERANKERS,
    )
