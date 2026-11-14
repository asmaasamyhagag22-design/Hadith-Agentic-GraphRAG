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

    import ingest, embed, utils, lexical, retrieve, rerank, pipeline  # noqa: F401
    import answer, evaluate, answer_eval, validate_golden  # noqa: F401
    import build_eval_set, chroma_ingest, debug_query  # noqa: F401
    import experiment_variants, experiment_retrieval  # noqa: F401
    import experiment_rerank, experiment_fusion  # noqa: F401

    return 17


@check("chunks on disk")
def step_chunks():

    from embed import load_chunks, indexable_chunks

    chunks = load_chunks()
    indexable = indexable_chunks(chunks)

    assert indexable, "no indexable chunks — run `python -m src.ingest` first"

    return len(chunks), len(indexable)


@check("index loads and ids align")
def step_index():

    from pipeline import build_pipeline
    from retrieve import UpgradedRetriever

    pipeline = build_pipeline()
    if isinstance(pipeline, UpgradedRetriever):
        assert pipeline.matn_vectors.shape[0] == len(pipeline.chunk_ids)
        return pipeline, int(pipeline.matn_vectors.shape[0])

    hybrid = pipeline.base

    # الـ Retriever بيرمي ValueError لو الفهرس والـ ids مش متطابقين
    assert hybrid.dense.index.ntotal == len(hybrid.dense.chunk_ids)

    return pipeline, hybrid.dense.index.ntotal


@check("retrieval returns hadiths")
def step_retrieve(pipeline):

    from pipeline import DEFAULT_K
    from retrieve import UpgradedRetriever

    if isinstance(pipeline, UpgradedRetriever):
        results = pipeline.search(ANSWERABLE, k=DEFAULT_K)
    else:
        results = pipeline.base.search(ANSWERABLE, k=DEFAULT_K)

    assert len(results) == DEFAULT_K, f"expected {DEFAULT_K} results, got {len(results)}"
    assert all(r["hadith_id"] for r in results)

    return [r["hadith_id"] for r in results]


@check("reranking / fusion returns top-k")
def step_rerank(pipeline):

    from pipeline import DEFAULT_K
    from retrieve import UpgradedRetriever

    reranked = pipeline.search(ANSWERABLE, k=DEFAULT_K)

    assert len(reranked) == DEFAULT_K
    if not isinstance(pipeline, UpgradedRetriever) or pipeline.last_used_fallback:
        assert reranked[0]["score"] is not None, "reranker produced no score"

    return [r["hadith_id"] for r in reranked]


@check("generation cites only from context")
def step_answer(pipeline):

    from answer import answer_with_details, cited_ids
    from pipeline import DEFAULT_K

    details = answer_with_details(ANSWERABLE, pipeline, k=DEFAULT_K)

    context_ids = {c["hadith_id"] for c in details["chunks"]}

    assert details["answer"], "empty answer"
    assert not (cited_ids(details["answer"]) - context_ids), \
        "answer cites a hadith that was not in context"

    return details["answer"]


@check("refuses when the answer is absent")
def step_refusal(pipeline):

    from answer import answer_with_details, cited_ids, REFUSAL
    from pipeline import DEFAULT_K

    details = answer_with_details(UNANSWERABLE, pipeline, k=DEFAULT_K)

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

    pipeline, vectors = step_index()
    print(f"  vectors in index            {vectors}")

    print(f"  retrieved                   {step_retrieve(pipeline)}")
    print(f"  reranked                    {step_rerank(pipeline)}")

    answer = step_answer(pipeline)
    print(f"  answered                    {answer.splitlines()[0][:60]}…")

    refusal = step_refusal(pipeline)
    print(f"  refused                     {refusal[:60]}")

    failed = [r for r in _results if not r[1]]

    print(f"\n{len(_results) - len(failed)}/{len(_results)} steps passed")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
