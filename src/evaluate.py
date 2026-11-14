"""
قياس جودة الاسترجاع على الـ golden dataset.

بيقيس الاسترجاع لوحده — من غير نداءات LLM — عشان يبقى
سريع ومجاني وقابل للتكرار. السؤال اللي بيجاوب عنه:
هل الحديث الصح ظهر في أول k نتيجة؟
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    GOLDEN_PATH,
    RETRIEVAL_PIPELINE,
    SYNTHETIC_EVAL_PATH,
    VECTORS_MATN_GEMINI001,
    VECTORS_PATH,
    IDS_PATH,
    VECTORS_MATN,
    IDS_MATN,
    VECTORS_MATN_WITH_TITLE,
    IDS_MATN_WITH_TITLE,
)
from retrieve import (
    Retriever,
    LexicalRetriever,
    HybridRetriever,
    load_chunk_lookup,
)
from pipeline import build_bm25, build_pipeline


DENSE_VARIANTS = [
    ("Dense: full (sanad+matn)", VECTORS_PATH, IDS_PATH, "full"),
    ("Dense: matn only", VECTORS_MATN, IDS_MATN, "matn"),
    (
        "Dense: chapter + matn",
        VECTORS_MATN_WITH_TITLE,
        IDS_MATN_WITH_TITLE,
        "chapter_matn",
    ),
]

K_VALUES = (1, 3, 5, 10)


def build_retrievers(rerankers=(), include_upgraded=False):
    """
    بترجع [(اسم, retriever)] — كل السطور اللي بتتقارن في
    الجدول. الـ BM25 والهجين مبنيين على صيغة الـ matn لأنها
    الفايزة في الجولة السابقة.

    rerankers: أسماء موديلات cross-encoder تتضاف كصفوف فوق
    الهجين. فاضية افتراضيًا لأن تحميلها غالي.
    """

    chunk_lookup = load_chunk_lookup()

    retrievers = []
    dense_by_variant = {}

    for name, vectors_path, ids_path, variant in DENSE_VARIANTS:

        dense = Retriever.from_files(
            vectors_path,
            ids_path,
            chunk_lookup=chunk_lookup,
        )

        dense_by_variant[variant] = dense
        retrievers.append((name, dense))

    matn_dense = dense_by_variant["matn"]

    bm25 = build_bm25(matn_dense.chunk_ids, "matn", chunk_lookup)

    hybrid = HybridRetriever(matn_dense, bm25)

    retrievers.append(
        ("BM25: matn only", LexicalRetriever(bm25, chunk_lookup))
    )
    retrievers.append(("Hybrid: dense + BM25", hybrid))

    for model_name in rerankers:

        from rerank import RerankingRetriever

        label = model_name.split("/")[-1]

        retrievers.append((
            f"Hybrid + {label}",
            RerankingRetriever(hybrid, model_name=model_name),
        ))

    if include_upgraded:
        retrievers.append((
            "Upgraded (E5)",
            build_pipeline(mode="upgraded", chunk_lookup=chunk_lookup),
        ))

    return retrievers


def load_golden(path=GOLDEN_PATH):

    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def answerable(golden):
    """
    أسئلة الرفض (اللي ملهاش إجابة في المصادر) مالهاش hit@k
    لأن مفيش حديث صح تدوّر عليه. بتتقاس في تقييم الإجابة
    مش في تقييم الاسترجاع، وبتتشال من المقام هنا عشان
    متنزّلش الأرقام غلط.
    """

    return [item for item in golden if item.get("answerable", True)]


def first_hit_rank(retriever, item, max_k):
    """
    بترجع مرتبة أول نتيجة صح (1-based) أو None لو مظهرش خالص.
    """

    expected = set(item["hadith_ids"])

    results = retriever.search(item["question"], k=max_k)

    for result in results:
        if result["hadith_id"] in expected:
            return result["rank"]

    return None


def evaluate(retriever, golden, k_values=K_VALUES):

    max_k = max(k_values)

    ranks = [
        first_hit_rank(retriever, item, max_k)
        for item in golden
    ]

    total = len(ranks)

    hits = {
        k: sum(1 for r in ranks if r is not None and r <= k) / total
        for k in k_values
    }

    # Mean Reciprocal Rank: بيفرّق بين «طلع أول واحد»
    # و«طلع خامس واحد»، وده الفرق اللي hit@5 لوحده بيخفيه.
    mrr = sum(1 / r for r in ranks if r is not None) / total

    return hits, mrr, ranks


# فوق العدد ده جدول المراتب سؤال بسؤال بيبقى ضوضاء
MAX_ROWS_FOR_DETAIL = 40

EVAL_SETS = {
    "golden": GOLDEN_PATH,
    "synthetic": SYNTHETIC_EVAL_PATH,
}


def main(eval_set="golden", rerankers=()):

    path = EVAL_SETS.get(eval_set)

    if path is None:
        raise ValueError(
            f"Unknown eval set '{eval_set}'. "
            f"Expected one of {sorted(EVAL_SETS)}."
        )

    all_items = load_golden(path)
    golden = answerable(all_items)

    by_type = {}

    for item in all_items:
        kind = item.get("type", "matn")
        by_type[kind] = by_type.get(kind, 0) + 1

    print(f"Eval set: {eval_set} ({path.name})")
    print(f"Questions: {len(all_items)}")

    for kind in sorted(by_type):
        print(f"  {kind:<10} {by_type[kind]}")

    if eval_set == "synthetic":
        print(
            "\n⚠ مولَّدة آليًا من المتون — بتحابي BM25 معجميًا.\n"
            "  للمقارنة النسبية بين الإعدادات، مش كأرقام مطلقة."
        )

    print(f"\nScored below (answerable only): {len(golden)}\n")

    header = (
        f"{'Retriever':<34}"
        + "".join(f"hit@{k:<6}" for k in K_VALUES)
        + "MRR      s/query"
    )

    print(header)
    print("-" * len(header))

    all_ranks = {}

    include_upgraded = (
        RETRIEVAL_PIPELINE == "upgraded" and VECTORS_MATN_GEMINI001.exists()
    )
    for name, retriever in build_retrievers(
        rerankers, include_upgraded=include_upgraded
    ):

        hits, mrr, ranks = evaluate(retriever, golden)
        all_ranks[name] = ranks

        row = f"{name:<34}"
        row += "".join(f"{hits[k]:<10.0%}" for k in K_VALUES)
        row += f"{mrr:<9.3f}"

        seconds = getattr(retriever, "seconds_per_query", None)
        row += f"{seconds:.2f}" if seconds else "-"

        print(row)

        truncated = getattr(retriever, "truncated", None)

        if truncated:
            print(
                f"{'':<34}({truncated}/{retriever.scored} documents "
                f"exceeded the 512-token limit)"
            )

    if len(golden) > MAX_ROWS_FOR_DETAIL:
        return

    print("\nRank of the correct hadith per question (- = not in top 10)\n")

    print(
        f"{'#':<3}{'Question':<42}"
        + "".join(f"{name[:13]:<15}" for name in all_ranks)
    )

    for i, item in enumerate(golden):

        question = item["question"]

        if len(question) > 40:
            question = question[:39] + "…"

        row = f"{i + 1:<3}{question:<42}"

        for name in all_ranks:
            rank = all_ranks[name][i]
            row += f"{rank if rank else '-':<15}"

        print(row)


if __name__ == "__main__":

    # الاستخدام: python -m src.evaluate [golden|synthetic] [model ...]
    args = sys.argv[1:]

    main(
        eval_set=args[0] if args else "golden",
        rerankers=args[1:],
    )
