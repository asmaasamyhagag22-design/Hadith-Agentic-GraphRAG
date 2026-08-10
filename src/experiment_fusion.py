"""
مسح بارامترات الدمج: حجم قايمة المرشحين، وأوزان RRF.

بيتشغّل على المجموعة الكبيرة لأن الفروق هنا صغيرة —
على 27 سؤال فرق نقطتين = نص سؤال، يعني ضوضاء خالصة.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SYNTHETIC_EVAL_PATH
from evaluate import (
    build_retrievers,
    load_golden,
    answerable,
    evaluate,
    K_VALUES,
)

CANDIDATE_SIZES = (25, 50, 100, 200)

# (وزن الدلالي، وزن BM25)
WEIGHTS = (
    (1.0, 1.0),
    (1.5, 1.0),
    (1.0, 1.5),
    (1.0, 2.0),
    (2.0, 1.0),
)


def row(label, hits, mrr):

    line = f"{label:<26}"
    line += "".join(f"{hits[k]:<10.0%}" for k in K_VALUES)
    line += f"{mrr:.3f}"

    return line


def header(title):

    text = (
        f"{title:<26}"
        + "".join(f"hit@{k:<6}" for k in K_VALUES)
        + "MRR"
    )

    print("\n" + text)
    print("-" * len(text))


def main():

    golden = answerable(load_golden(SYNTHETIC_EVAL_PATH))

    print(f"Fusion sweep on {len(golden)} generated questions")

    hybrid = dict(build_retrievers())["Hybrid: dense + BM25"]

    baseline = (hybrid.candidates, hybrid.dense_weight, hybrid.bm25_weight)

    header("candidates")

    for size in CANDIDATE_SIZES:

        hybrid.candidates = size
        hybrid.dense_weight, hybrid.bm25_weight = 1.0, 1.0

        hits, mrr, _ = evaluate(hybrid, golden)

        print(row(str(size), hits, mrr))

    hybrid.candidates = baseline[0]

    header("dense : bm25 weights")

    for dense_weight, bm25_weight in WEIGHTS:

        hybrid.dense_weight = dense_weight
        hybrid.bm25_weight = bm25_weight

        hits, mrr, _ = evaluate(hybrid, golden)

        print(row(f"{dense_weight} : {bm25_weight}", hits, mrr))


if __name__ == "__main__":
    main()
