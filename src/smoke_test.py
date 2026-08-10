"""
فحص دخان للمسار الكامل — من الاستيراد للرفض.

الفحص الساكن (استيراد الوحدات) مش بيكشف أعطال وقت التشغيل.
ده بيمشي على السلسلة الحقيقية خطوة خطوة ويقف عند أول عطل.

بيستهلك نداءين للموديل (إجابة + رفض).
"""

import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ANSWERABLE = "ما حكم صيام يوم عاشوراء؟"
UNANSWERABLE = "كم عدد ركعات صلاة التراويح؟"

_results = []


def check(name):
    """ديكوريتر بيسجّل نجاح/فشل كل خطوة من غير ما يخفي السبب."""

    def wrap(fn):

        def run(*args):

            try:
                value = fn(*args)
                _results.append((name, True, ""))
                return value

            except Exception as error:
                _results.append((name, False, f"{type(error).__name__}: {error}"))
                traceback.print_exc()
                raise SystemExit(1)

        return run

    return wrap


@check("imports")
def step_imports():

    import ingest, embed, utils, lexical, retrieve, rerank  # noqa: F401
    import answer, evaluate, answer_eval, validate_golden  # noqa: F401
    import build_eval_set, chroma_ingest, debug_query  # noqa: F401
    import experiment_variants, experiment_retrieval  # noqa: F401
    import experiment_rerank, experiment_fusion  # noqa: F401

    return 16


@check("chunks on disk")
def step_chunks():

    from embed import load_chunks, indexable_chunks

    chunks = load_chunks()
    indexable = indexable_chunks(chunks)

    assert indexable, "no indexable chunks — run `python -m src.ingest` first"

    return len(chunks), len(indexable)


@check("index loads and ids align")
def step_index():

    from evaluate import build_retrievers

    retrievers = dict(build_retrievers())

    hybrid = retrievers["Hybrid: dense + BM25"]

    # الـ Retriever بيرمي ValueError لو الفهرس والـ ids مش متطابقين
    assert hybrid.dense.index.ntotal == len(hybrid.dense.chunk_ids)

    return retrievers, hybrid.dense.index.ntotal


@check("retrieval returns hadiths")
def step_retrieve(hybrid):

    results = hybrid.search(ANSWERABLE, k=5)

    assert len(results) == 5, f"expected 5 results, got {len(results)}"
    assert all(r["hadith_id"] for r in results)

    return [r["hadith_id"] for r in results]


@check("reranking reorders")
def step_rerank(hybrid):

    from rerank import RerankingRetriever

    reranked = RerankingRetriever(hybrid).search(ANSWERABLE, k=5)

    assert len(reranked) == 5
    assert reranked[0]["score"] is not None, "reranker produced no score"

    return [r["hadith_id"] for r in reranked]


@check("generation cites only from context")
def step_answer(hybrid):

    from answer import answer_with_details, cited_ids

    details = answer_with_details(ANSWERABLE, hybrid, k=5)

    context_ids = {c["hadith_id"] for c in details["chunks"]}

    assert details["answer"], "empty answer"
    assert not (cited_ids(details["answer"]) - context_ids), \
        "answer cites a hadith that was not in context"

    return details["answer"]


@check("refuses when the answer is absent")
def step_refusal(hybrid):

    from answer import answer_with_details, cited_ids, REFUSAL

    details = answer_with_details(UNANSWERABLE, hybrid, k=5)

    answer = details["answer"]

    assert REFUSAL in answer, f"expected a refusal, got: {answer[:120]}"
    assert not cited_ids(answer), "cited a source while refusing"

    return answer


def main():

    print("Smoke test — full pipeline\n")

    modules = step_imports()
    print(f"  modules imported            {modules}")

    total, indexable = step_chunks()
    print(f"  chunks / indexable          {total} / {indexable}")

    retrievers, vectors = step_index()
    hybrid = retrievers["Hybrid: dense + BM25"]
    print(f"  vectors in index            {vectors}")

    print(f"  retrieved                   {step_retrieve(hybrid)}")
    print(f"  reranked                    {step_rerank(hybrid)}")

    answer = step_answer(hybrid)
    print(f"  answered                    {answer.splitlines()[0][:60]}…")

    refusal = step_refusal(hybrid)
    print(f"  refused                     {refusal[:60]}")

    failed = [r for r in _results if not r[1]]

    print(f"\n{len(_results) - len(failed)}/{len(_results)} steps passed")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
