"""
قياس أخطاء الإجابة — مش الاسترجاع.

`evaluate.py` بيقول هل الحديث الصح وصل للسياق. الملف ده
بيقول إيه اللي حصل بعد كده: هل استشهد برقم مش موجود؟ هل
رفض وهو شايف الإجابة؟ هل رفض في السؤال اللي مالوش إجابة؟

كل المقاييس هنا محسوبة برمجيًا — مفيش حَكَم LLM — فهي
مجانية ومتكررة وقابلة للتشغيل في كل جولة.

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
from answer import answer_with_details, cited_ids, REFUSAL

DEFAULT_K = 5


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
            return None, 0

        return sum(1 for r in rows if r.get(key)) / len(rows), len(rows)


def evaluate_answers(retriever, items, k=DEFAULT_K, enforce_citations=True):

    counter = Counter()

    for item in items:

        details = answer_with_details(
            item["question"],
            retriever,
            k=k,
            enforce_citations=enforce_citations,
        )

        answer = details["answer"]
        chunks = details["chunks"]

        context_ids = {c["hadith_id"] for c in chunks}
        gold_ids = set(item.get("hadith_ids", []))

        cited = cited_ids(answer)
        refused = is_refusal(answer)

        counter.add(
            question=item["question"],
            answerable=item.get("answerable", True),
            refusal_test=item.get("type") == "refusal",
            gold_in_context=bool(gold_ids & context_ids),
            refused=refused,
            cited_anything=bool(cited),
            # على المحاولة الخام قبل التصفية — ده الرقم
            # اللي بيقيس تحسّن حقيقي
            invalid_citation=details["invalid_citation_attempt"],
            # استشهاد بحديث موجود في السياق لكنه مش الصح
            wrong_citation=bool(cited and cited <= context_ids
                                and not (cited & gold_ids)),
            correct_citation=bool(cited & gold_ids),
            answer=answer,
            raw=details["raw"],
        )

    return counter


def report(label, counter):

    print(f"\n{label}")
    print("-" * len(label))

    metrics = [
        ("invalid citation attempts", "invalid_citation", None),
        ("wrong citation (in context)", "wrong_citation", None),
        ("correct citation", "correct_citation", "answerable"),
        ("false refusal (gold was there)", "refused", "gold_in_context"),
        ("refusal on refusal tests", "refused", "refusal_test"),
        ("cited a source while refusing", "cited_anything", "refused"),
    ]

    for name, key, among in metrics:

        rate, total = counter.rate(key, among)

        if rate is None:
            print(f"  {name:<32} n/a")
            continue

        print(f"  {name:<32} {rate:>5.0%}   ({total} questions)")


def main(k=DEFAULT_K):

    items = load_golden(GOLDEN_PATH)

    # أسئلة الرواة مالهاش إجابة نصية دلوقتي — بتتقاس
    # في أسبوع 2 لما الجراف يشتغل.
    items = [i for i in items if i.get("type") != "narrator"]

    retrievers = dict(build_retrievers())

    retriever = retrievers["Hybrid: dense + BM25"]

    from answer import MODEL

    print(f"Answer evaluation — {len(items)} questions, k={k}")
    print(f"Generator: {MODEL}")

    counter = evaluate_answers(retriever, items, k=k)

    report("Hybrid retrieval", counter)

    print("\nAnswers that cited something not in context:\n")

    for row in counter.rows:
        if row["invalid_citation"]:
            print(f"  • {row['question']}")
            print(f"    {row['answer'][:160]}\n")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_K)
