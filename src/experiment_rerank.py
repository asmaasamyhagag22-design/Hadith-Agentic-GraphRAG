"""
بوابة جدوى الـ reranker — تتشغّل قبل أي استثمار في المسار ده.

الفرضية اللي بتتاختبر: الـ cross-encoders المتعددة اللغات
متدربة على بحث ويب حديث، والحديث النبوي بلغة كلاسيكية وسجل
ديني — يعني خارج توزيع تدريبها. ممكن ما يتحسنش.

بتشغّل على عينة صغيرة وبتقيس حاجتين: هل hit@1 اتحرك،
وكام ثانية بياخد كل سؤال على CPU. لو الأولى لأ، النتيجة
السلبية دي تتكتب في EXPERIMENTS.md ونروح لمسار تاني.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluate import (
    build_retrievers,
    load_golden,
    answerable,
    evaluate,
    K_VALUES,
)
from rerank import RerankingRetriever, BGE

SAMPLE_SIZE = 10


def report(label, retriever, golden):

    hits, mrr, ranks = evaluate(retriever, golden)

    row = f"{label:<28}"
    row += "".join(f"{hits[k]:<10.0%}" for k in K_VALUES)
    row += f"{mrr:.3f}"

    if isinstance(retriever, RerankingRetriever):
        row += f"   {retriever.seconds_per_query:.1f}s/q"

    print(row)

    return ranks


def main(model_name=BGE, sample_size=SAMPLE_SIZE):

    golden = answerable(load_golden())[:sample_size]

    print(f"Feasibility gate — {sample_size} questions, model: {model_name}\n")

    retrievers = dict(build_retrievers())
    base = retrievers["Hybrid: dense + BM25"]

    header = (
        f"{'Retriever':<28}"
        + "".join(f"hit@{k:<6}" for k in K_VALUES)
        + "MRR"
    )

    print(header)
    print("-" * len(header))

    before = report("Hybrid (baseline)", base, golden)

    reranker = RerankingRetriever(base, model_name=model_name)

    after = report("Hybrid + reranker", reranker, golden)

    print(
        f"\nTruncated at {reranker.scored and 512}: "
        f"{reranker.truncated}/{reranker.scored} documents"
    )

    print("\nPer-question rank change (baseline -> reranked)\n")

    moved_up = moved_down = 0

    for item, was, now in zip(golden, before, after):

        if was == now:
            continue

        if now is not None and (was is None or now < was):
            moved_up += 1
        else:
            moved_down += 1

        print(
            f"  {was if was else '-':>3} -> {now if now else '-':<3} "
            f"{item['question']}"
        )

    print(f"\nimproved: {moved_up}   regressed: {moved_down}")


if __name__ == "__main__":
    main(*(sys.argv[1:] or []))
