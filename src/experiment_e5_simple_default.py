"""
Evaluate the simplified default Upgraded pipeline (1:0:0:0: dense matn + HyDE 0.7:0.3,
no BM25 and no expansion fields):
1. Retrieval metrics on dev (synthetic_eval, n=224) and golden (n=27).
2. 3 runs of answer_eval with gemini-4-argon on golden (n=30: 27 answerable + 3 refusal, k=5).
3. Uncached live end-to-end latency & per-query token/cost breakdown (n=20 golden answerable).
Saves all outputs to data/processed/e5_simple_default_results.json.
"""

import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))

import experiment_p4_simplicity_and_latency as p4_mod
from config import GOLDEN_PATH, PROCESSED_DIR, SYNTHETIC_EVAL_PATH
from evaluate import answerable, load_golden
from experiment_e0_gold_expansion import (
    GOLDEN_EXPANDED_PATH,
    SYNTHETIC_EXPANDED_PATH,
)
from experiment_e5_ablation_and_leakage import eval_fast
from experiment_e5_final_pipeline import (
    aggregate_runs,
    evaluate_answers_parallel,
    METRICS_SPEC,
    report,
    summarize_counter,
)
from pipeline import DEFAULT_K, build_pipeline

OUT_PATH = PROCESSED_DIR / "e5_simple_default_results.json"


def eval_simple_retrieval(retriever):
    datasets = {
        "golden_orig": answerable(load_golden(GOLDEN_PATH)),
        "golden_expanded": answerable(load_golden(GOLDEN_EXPANDED_PATH)),
        "synthetic_orig": answerable(load_golden(SYNTHETIC_EVAL_PATH)),
        "synthetic_expanded": answerable(load_golden(SYNTHETIC_EXPANDED_PATH)),
    }
    results = {}
    for ds_name, items in datasets.items():
        metrics, _, _ = eval_fast(retriever, items)
        assert not retriever.last_used_fallback, f"Unexpected fallback in {ds_name}"
        results[ds_name] = metrics
        print(
            f"[retrieval:{ds_name}] hit@1={metrics['hit@1']:.2%} ({metrics['hit@1_count']}/{metrics['n']}) "
            f"hit@3={metrics['hit@3']:.2%} ({metrics['hit@3_count']}/{metrics['n']}) "
            f"hit@5={metrics['hit@5']:.2%} ({metrics['hit@5_count']}/{metrics['n']}) "
            f"hit@10={metrics['hit@10']:.2%} ({metrics['hit@10_count']}/{metrics['n']}) "
            f"MRR={metrics['MRR']:.4f}",
            flush=True,
        )
    return results


def prefetch_chunks_no_fallback(retriever, items, k=DEFAULT_K):
    """Fetch top-k chunks once for all 30 answer_eval items, verifying live API path."""
    for item in items:
        for attempt in (1, 2, 3):
            retriever.search(item["question"], k=k)
            if not retriever.last_used_fallback:
                break
            print(
                f"  [retry {attempt}] fallback on uncached question, retrying...",
                flush=True,
            )
            retriever._dense_rank_cache.pop((item["question"], max(retriever.candidates, k)), None)
            time.sleep(2)
        assert not retriever.last_used_fallback, (
            f"Failed to retrieve without fallback for: {item['question']}"
        )


def main():
    payload = {}
    if OUT_PATH.exists():
        payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))

    retriever = build_pipeline(mode="upgraded")
    assert tuple(retriever.weights) == (1.0, 0.0, 0.0, 0.0)
    assert retriever.exp_vectors is None
    assert retriever.bm25_matn is None
    assert retriever.bm25_exp is None

    print("=== 1. Offline Retrieval Evaluation (1:0:0:0) ===", flush=True)
    payload["retrieval"] = eval_simple_retrieval(retriever)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== 2. Answer Eval (3 runs, gemini-4-argon, k=5) ===", flush=True)
    eval_items = [i for i in load_golden(GOLDEN_PATH) if i.get("type") != "narrator"]
    prefetch_chunks_no_fallback(retriever, eval_items, k=DEFAULT_K)

    runs = payload.get("answer_eval", {}).get("runs", [])
    while len(runs) < 3:
        run_idx = len(runs) + 1
        print(f"\n>>> answer_eval run {run_idx}/3 ...", flush=True)
        t0 = time.time()
        counter = evaluate_answers_parallel(retriever, eval_items, k=DEFAULT_K, model="gemini-4-argon")
        dt = time.time() - t0
        report(f"Upgraded 1:0:0:0 [gemini-4-argon] (run {run_idx}, {dt:.1f}s)", counter)
        s = summarize_counter(counter)
        s["elapsed_seconds"] = round(dt, 1)
        runs.append(s)
        payload["answer_eval"] = {
            "weights": list(retriever.weights),
            "generator": "gemini-4-argon",
            "num_runs": len(runs),
            "aggregate": aggregate_runs(runs),
            "runs": runs,
        }
        OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    agg = payload["answer_eval"]["aggregate"]
    print("\n=== Answer Eval 3-Run Aggregate (gemini-4-argon, 1:0:0:0) ===", flush=True)
    for m_id, _, _, _ in METRICS_SPEC:
        m = agg[m_id]
        print(
            f"  {m['label']:<48} mean={m['mean_rate']:.2%} "
            f"(hits={m['hits_per_run']}/{m['totals']}, sum={sum(m['hits_per_run'])}/{sum(m['totals'])}, "
            f"min-max={m['min_rate']:.1%}–{m['max_rate']:.1%})",
            flush=True,
        )

    if "live_latency_and_cost" not in payload:
        print("\n=== 3. Live Uncached Latency & Cost (n=20 golden answerable, 1:0:0:0) ===", flush=True)
        dev_items = answerable(load_golden(SYNTHETIC_EVAL_PATH))
        gold_items = answerable(load_golden(GOLDEN_PATH))
        orig_out = p4_mod.OUT_JSON_PATH
        p4_mod.OUT_JSON_PATH = PROCESSED_DIR / "_tmp_simple_latency.json"
        try:
            live_stats = p4_mod.measure_live_latency_and_cost(
                retriever,
                warmup_item=dev_items[0],
                eval_items=gold_items[:20],
                simplicity=None,
            )
        finally:
            if p4_mod.OUT_JSON_PATH.exists():
                p4_mod.OUT_JSON_PATH.unlink()
            p4_mod.OUT_JSON_PATH = orig_out

        payload["live_latency_and_cost"] = live_stats
        OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    ls = payload["live_latency_and_cost"]
    print("\n=== Live Latency Summary (1:0:0:0) ===", flush=True)
    for k_name, s in ls["latency_summary_ms"].items():
        print(
            f"  {k_name:<22} median={s['median']:.1f}ms p95={s['p95']:.1f}ms "
            f"mean={s['mean']:.1f}ms range=[{s['min']:.1f}, {s['max']:.1f}]",
            flush=True,
        )
    print("=== Live Cost Summary (1:0:0:0) ===", flush=True)
    for k_name, c in ls["cost_summary_usd"].items():
        print(f"  {k_name:<22} mean=${c['mean_usd']:.6f} median=${c['median_usd']:.6f}", flush=True)
    print(f"\nSaved complete results to {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
