"""
Step 5 — Final Retrieval Pipeline (E5) evaluation and multi-run `answer_eval`.

1. Evaluates the chosen E5 retrieval pipeline (`UpgradedRetriever`:
   `gemini-embedding-001` 3072d + `gemini-3.8-flash` E2 doc expansion +
   `gemini-3.8-flash` E4 HyDE blended query vector `0.7*q + 0.3*HyDE_q` +
   4-way RRF `8:2:1:1`, no cross-encoder reranker) against the legacy
   pipelines (`Dense only`, `BM25 only`, `Hybrid (RRF)`, `Hybrid + mmarco`)
   on `golden.jsonl` (n=27), `synthetic_eval.jsonl` (n=224),
   `golden_expanded.jsonl` (n=27), and `synthetic_eval_expanded.jsonl` (n=224).
2. Runs `answer_eval` on `golden.jsonl` (30 questions: 27 answerable + 3 refusal, k=5):
   - Old pipeline (`Hybrid + mmarco-mMiniLMv2-L12-H384-v1`, `gemini-2.5-pro`): 3 runs
   - Old un-reranked (`Hybrid: dense + BM25`, `gemini-2.5-pro`): 1 run
   - New pipeline (`Upgraded (E5)`, `gemini-2.5-pro`): 3 runs
   - New pipeline (`Upgraded (E5)`, `gemini-3.1-pro-preview`): 1 run
   - New pipeline (`Upgraded (E5)`, `gemini-4-argon`): 1 run
   Computes mean and min-max across the 3 runs and saves full results to
   `data/processed/e5_results.json`.
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from answer import (
    MODEL,
    REFUSAL,
    VALID_ANSWER,
    VALID_REFUSAL,
    answer_with_details,
    cited_ids,
    validate_answer,
)
from answer_eval import Counter, is_refusal, report
from config import GOLDEN_PATH, PROCESSED_DIR, SYNTHETIC_EVAL_PATH
from evaluate import answerable, build_retrievers, evaluate, load_golden
from experiment_e0_gold_expansion import (
    GOLDEN_EXPANDED_PATH,
    SYNTHETIC_EXPANDED_PATH,
)
from experiment_step4_newer_llm import eval_retriever_dict
from rerank import DEFAULT_MODEL

E5_RESULTS_PATH = PROCESSED_DIR / "e5_results.json"
MAX_WORKERS = 7

METRICS_SPEC = [
    ("correct_citation", "Correct citation", "correct_citation", "answerable"),
    (
        "invalid_citation",
        "Invalid citation attempts (measured before filtering)",
        "invalid_citation",
        None,
    ),
    (
        "missing_citation",
        "Missing citation attempts (raw output)",
        "missing_citation",
        None,
    ),
    (
        "wrong_citation",
        "Cited a non-gold hadith from the context",
        "wrong_citation",
        None,
    ),
    ("false_refusal", "False refusals", "refused", "gold_in_context"),
    ("refusal_tests", "Correct refusals", "refused", "refusal_test"),
    ("gold_in_context", "Gold hadith in top-5 context", "gold_in_context", "answerable"),
]


_PRE_CHUNKS_CACHE = {}


def evaluate_answers_parallel(retriever, items, k=5, model=MODEL):
    """Run answer_with_details across all 30 golden items (preserving order)."""
    # Pre-fetch chunks sequentially once per retriever so CrossEncoder/FAISS is not repeated across runs
    cache_key = (id(retriever), k)
    if cache_key not in _PRE_CHUNKS_CACHE:
        _PRE_CHUNKS_CACHE[cache_key] = [
            retriever.search(item["question"], k=k) for item in items
        ]
    pre_chunks = _PRE_CHUNKS_CACHE[cache_key]

    def run_one(args):
        idx, item, chunks = args

        class _PreChunkRetriever:
            def search(self, q, k=5):
                return chunks

        details = answer_with_details(
            item["question"],
            _PreChunkRetriever(),
            k=k,
            enforce_citations=True,
            self_correct=False,
            model=model,
        )
        answer = details["answer"]
        raw = details["raw"]
        context_ids = {c["hadith_id"] for c in chunks}
        gold_ids = set(item.get("hadith_ids", []))
        cited = cited_ids(answer)
        refused = is_refusal(answer)
        old_invalid = bool(cited_ids(raw) - context_ids)
        raw_status = validate_answer(raw, context_ids)
        new_invalid = raw_status not in (VALID_ANSWER, VALID_REFUSAL)
        loophole = (not old_invalid) and new_invalid

        return dict(
            index=idx,
            question=item["question"],
            answerable=item.get("answerable", True),
            refusal_test=item.get("type") == "refusal",
            gold_in_context=bool(gold_ids & context_ids),
            refused=refused,
            cited_anything=bool(cited),
            invalid_citation=details["invalid_citation_attempt"],
            missing_citation=details["missing_citation_attempt"],
            loose_out_of_context=details["loose_out_of_context_attempt"],
            mixed_refusal=details["mixed_refusal_attempt"],
            loophole=loophole,
            raw_status=raw_status.value,
            regenerated=details["regenerated"],
            wrong_citation=bool(
                cited and cited <= context_ids and not (cited & gold_ids)
            ),
            correct_citation=bool(cited & gold_ids),
            answer=answer,
            raw=raw,
            retried=details.get("retried", False),
        )

    counter = Counter()
    tasks = [
        (idx, item, pre_chunks[idx - 1])
        for idx, item in enumerate(items, start=1)
    ]
    workers = 2 if (model.startswith("gemini-3") or model.startswith("gemini-4")) else MAX_WORKERS
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for row in ex.map(run_one, tasks):
            counter.add(**row)
    return counter


def summarize_counter(counter):
    summary = {}
    for metric_id, label, key, among in METRICS_SPEC:
        rate, hits, total = counter.rate(key, among)
        summary[metric_id] = {
            "label": label,
            "rate": round(rate, 4) if rate is not None else None,
            "hits": hits,
            "total": total,
        }
    regenerated = sum(1 for r in counter.rows if r["regenerated"])
    summary["regenerated"] = regenerated
    summary["gemini_calls_used"] = len(counter.rows) + regenerated
    summary["rows"] = counter.rows
    return summary


def aggregate_runs(run_summaries):
    agg = {}
    for metric_id, label, _, _ in METRICS_SPEC:
        rates = [r[metric_id]["rate"] for r in run_summaries]
        hits = [r[metric_id]["hits"] for r in run_summaries]
        totals = [r[metric_id]["total"] for r in run_summaries]
        agg[metric_id] = {
            "label": label,
            "mean_rate": round(sum(rates) / len(rates), 4),
            "min_rate": round(min(rates), 4),
            "max_rate": round(max(rates), 4),
            "mean_hits": round(sum(hits) / len(hits), 2),
            "min_hits": min(hits),
            "max_hits": max(hits),
            "mean_total": round(sum(totals) / len(totals), 2),
            "totals": totals,
            "hits_per_run": hits,
            "rates_per_run": rates,
        }
    agg["total_calls"] = sum(r["gemini_calls_used"] for r in run_summaries)
    return agg


def eval_retrieval_all(retrievers_dict):
    datasets = {
        "golden_orig": answerable(load_golden(GOLDEN_PATH)),
        "golden_expanded": answerable(load_golden(GOLDEN_EXPANDED_PATH)),
        "synthetic_orig": answerable(load_golden(SYNTHETIC_EVAL_PATH)),
        "synthetic_expanded": answerable(load_golden(SYNTHETIC_EXPANDED_PATH)),
    }
    out = {}
    ret_top50_cache = {}
    for ds_name, items in datasets.items():
        out[ds_name] = {}
        print(f"\n=== E5 Retrieval Evaluation on {ds_name} (n={len(items)}) ===")
        for name, ret in retrievers_dict.items():
            # Only evaluate Upgraded (E5) here; legacy retrievers are already recorded in e0_results.json
            if name != "Upgraded (E5)" and "golden" not in ds_name:
                continue
            if name not in ret_top50_cache:
                ret_top50_cache[name] = {}
            q_cache = ret_top50_cache[name]

            class _CachedRet:
                def search(self, q, k=50):
                    if (q, k) not in q_cache:
                        if (q, 50) in q_cache and k <= 50:
                            q_cache[(q, k)] = q_cache[(q, 50)][:k]
                        else:
                            q_cache[(q, k)] = ret.search(q, k=k)
                    return q_cache[(q, k)]

            c_ret = _CachedRet()
            m50 = eval_retriever_dict(c_ret, items)
            hits, mrr, _ = evaluate(c_ret, items)
            out[ds_name][name] = {
                "hit@1": round(hits[1], 4),
                "hit@3": round(hits[3], 4),
                "hit@5": round(hits[5], 4),
                "hit@10": round(hits[10], 4),
                "MRR": round(mrr, 4),
                "recall@50": m50["recall@50"],
                "hits50_count": m50["hits50_count"],
                "setR@50": m50["setR@50"],
                "MRR@50": m50["MRR@50"],
            }
            print(
                f"{name:<42} hit@1={hits[1]:.1%} hit@3={hits[3]:.1%} "
                f"hit@5={hits[5]:.1%} hit@10={hits[10]:.1%} "
                f"recall@50={m50['recall@50']:.1%} ({m50['hits50_count']}) MRR={mrr:.3f}",
                flush=True,
            )
    return out


def main():
    if E5_RESULTS_PATH.exists():
        with open(E5_RESULTS_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = {}

    retrievers = dict(build_retrievers(rerankers=(DEFAULT_MODEL,), include_upgraded=True))
    selected_retrievers = {
        "Dense: matn only": retrievers["Dense: matn only"],
        "BM25: matn only": retrievers["BM25: matn only"],
        "Hybrid: dense + BM25": retrievers["Hybrid: dense + BM25"],
        "Hybrid + mmarco-mMiniLMv2-L12-H384-v1": retrievers[
            "Hybrid + mmarco-mMiniLMv2-L12-H384-v1"
        ],
        "Upgraded (E5)": retrievers["Upgraded (E5)"],
    }

    if "retrieval" not in existing:
        existing["retrieval"] = eval_retrieval_all(selected_retrievers)
        with open(E5_RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

    all_golden = load_golden(GOLDEN_PATH)
    eval_items = [i for i in all_golden if i.get("type") != "narrator"]

    if "answer_eval_runs" not in existing:
        existing["answer_eval_runs"] = {}

    run_plan = [
        (
            "old_hybrid_mmarco_g25pro",
            "Hybrid + mmarco-mMiniLMv2-L12-H384-v1",
            "gemini-2.5-pro",
            3,
        ),
        ("new_upgraded_e5_g25pro", "Upgraded (E5)", "gemini-2.5-pro", 3),
        (
            "new_upgraded_e5_g31pro",
            "Upgraded (E5)",
            "gemini-3.1-pro-preview",
            1,
        ),
        ("new_upgraded_e5_g4argon", "Upgraded (E5)", "gemini-4-argon", 1),
    ]

    for key, ret_name, gen_model, num_runs in run_plan:
        runs = existing["answer_eval_runs"].get(key, {}).get("runs", [])
        retriever = selected_retrievers[ret_name]
        while len(runs) < num_runs:
            run_idx = len(runs) + 1
            print(
                f"\n>>> Running answer_eval [{key}] ({ret_name} | generator={gen_model}) "
                f"run {run_idx}/{num_runs} ...",
                flush=True,
            )
            t0 = time.time()
            counter = evaluate_answers_parallel(
                retriever, eval_items, k=5, model=gen_model
            )
            dt = time.time() - t0
            report(f"{ret_name} [{gen_model}] (run {run_idx}, {dt:.1f}s)", counter)
            s = summarize_counter(counter)
            s["elapsed_seconds"] = round(dt, 1)
            runs.append(s)
            existing["answer_eval_runs"][key] = {
                "retriever": ret_name,
                "generator": gen_model,
                "num_runs": len(runs),
                "aggregate": aggregate_runs(runs),
                "runs": runs,
            }
            with open(E5_RESULTS_PATH, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)

    print("\n=== E5 Answer Eval Aggregate Summary (Mean and Min-Max) ===")
    for key, info in existing["answer_eval_runs"].items():
        agg = info["aggregate"]
        print(
            f"\n[{key}] retriever={info['retriever']} | generator={info['generator']} "
            f"| runs={info['num_runs']} | total_calls={agg['total_calls']}"
        )
        for m_id, _, _, _ in METRICS_SPEC:
            m = agg[m_id]
            print(
                f"  {m['label']:<52} mean={m['mean_rate']:.1%} "
                f"(min={m['min_rate']:.1%}, max={m['max_rate']:.1%}) "
                f"| hits={m['hits_per_run']} / {m['totals'][0]}"
            )


if __name__ == "__main__":
    main()
