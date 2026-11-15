"""Benchmark uncached retrieval latency (median & p95) on 15 golden queries after parallel HyDE.

Compares against the paired n=15 sequential baseline extracted from
data/processed/e5_simple_default_results.json (`live_latency_and_cost.records[:15]`)
while staying strictly within the Flash + Embed API budget (<= 15 Flash calls, 0 Pro calls).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any

from dotenv import load_dotenv
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluate import answerable, load_golden
from src.pipeline import build_pipeline

BASELINE_PATH = ROOT / "data" / "processed" / "e5_simple_default_results.json"
GOLDEN_PATH = ROOT / "data" / "raw" / "golden.jsonl"
OUTPUT_PATH = ROOT / "data" / "demo" / "parallel_hyde_latency_n15.json"
LEDGER_PATH = ROOT / "data" / "demo" / "api_budget_ledger.json"


def _load_golden_by_question() -> dict[str, set[int]]:
    gold: dict[str, set[int]] = {}
    for row in answerable(load_golden(GOLDEN_PATH)):
        ids = row.get("hadith_ids") or []
        gold[row["question"]] = {int(x) for x in ids}
    return gold


def _update_budget_ledger(flash: int, embed: int) -> None:
    if LEDGER_PATH.is_file():
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    else:
        ledger = {"budget_caps": {"pro": 40, "flash": 40}, "used": {"pro": 0, "flash": 0, "embed": 0}, "runs": []}
    ledger["used"]["flash"] += flash
    ledger["used"]["embed"] += embed
    ledger["runs"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": "Step 4: parallel HyDE n=15 uncached retrieval latency",
            "pro": 0,
            "flash": flash,
            "embed": embed,
        }
    )
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    before_records = list(baseline["live_latency_and_cost"]["records"][:15])
    assert len(before_records) == 15

    gold_map = _load_golden_by_question()
    retriever = build_pipeline(mode="upgraded")

    after_records: list[dict[str, Any]] = []
    hits_1 = 0
    hits_3 = 0
    hits_5 = 0
    mrrs: list[float] = []
    flash_calls = 0
    embed_calls = 0

    for idx, base in enumerate(before_records, start=1):
        q = base["question"]
        # Clear caches before each timed call to measure uncached live retrieval
        retriever.query_vec_cache.pop(q, None)
        retriever.hyde_vec_cache.pop(q, None)
        retriever.hyde_text_cache.pop(q, None)
        if hasattr(retriever, "_dense_rank_cache"):
            retriever._dense_rank_cache.clear()

        t0 = time.perf_counter()
        chunks = retriever.search(q, k=5)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        stats = dict(getattr(retriever, "last_call_stats", None) or {})
        flash_calls += int(stats.get("flash_calls", 0))
        embed_calls += int(stats.get("embed_calls", 0))

        ret_ids = [int(c["hadith_id"]) for c in chunks]
        rel = gold_map[q]
        rank = next((i + 1 for i, hid in enumerate(ret_ids) if hid in rel), None)
        if rank is not None and rank <= 1:
            hits_1 += 1
        if rank is not None and rank <= 3:
            hits_3 += 1
        if rank is not None and rank <= 5:
            hits_5 += 1
        mrrs.append(1.0 / rank if rank is not None else 0.0)

        after_records.append(
            {
                "idx": idx,
                "question": q,
                "before_retrieval_ms": round(float(base["retrieval_ms"]), 2),
                "after_retrieval_ms": round(elapsed_ms, 2),
                "delta_ms": round(elapsed_ms - float(base["retrieval_ms"]), 2),
                "used_fallback": bool(getattr(retriever, "last_used_fallback", False)),
                "retrieved_ids": ret_ids,
            }
        )
        print(
            f"[{idx:2d}/15] before={base['retrieval_ms']:.1f}ms -> after={elapsed_ms:.1f}ms "
            f"(delta={elapsed_ms - base['retrieval_ms']:+.1f}ms, fallback={retriever.last_used_fallback})"
        )

    before_vals = [float(r["retrieval_ms"]) for r in before_records]
    after_vals = [float(r["after_retrieval_ms"]) for r in after_records]

    summary = {
        "n": 15,
        "dataset": "golden.jsonl (first 15 answerable queries from live_latency_and_cost)",
        "before_sequential_ms": {
            "median": round(float(np.median(before_vals)), 2),
            "p95": round(float(np.percentile(before_vals, 95)), 2),
            "mean": round(float(np.mean(before_vals)), 2),
            "min": round(float(np.min(before_vals)), 2),
            "max": round(float(np.max(before_vals)), 2),
        },
        "after_parallel_ms": {
            "median": round(float(np.median(after_vals)), 2),
            "p95": round(float(np.percentile(after_vals, 95)), 2),
            "mean": round(float(np.mean(after_vals)), 2),
            "min": round(float(np.min(after_vals)), 2),
            "max": round(float(np.max(after_vals)), 2),
        },
        "speedup_ms": {
            "median_saved_ms": round(float(np.median(before_vals) - np.median(after_vals)), 2),
            "p95_saved_ms": round(float(np.percentile(before_vals, 95) - np.percentile(after_vals, 95)), 2),
        },
        "retrieval_quality_n15": {
            "hit@1": f"{hits_1}/15 ({hits_1 / 15 * 100:.2f}%)",
            "hit@3": f"{hits_3}/15 ({hits_3 / 15 * 100:.2f}%)",
            "hit@5": f"{hits_5}/15 ({hits_5 / 15 * 100:.2f}%)",
            "mrr": round(float(np.mean(mrrs)), 4),
        },
        "api_calls_used": {
            "pro_calls": 0,
            "flash_calls": flash_calls,
            "embed_calls": embed_calls,
        },
        "fallback_count": sum(1 for r in after_records if r["used_fallback"]),
        "records": after_records,
    }
    OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _update_budget_ledger(flash_calls, embed_calls)
    print(json.dumps({k: v for k, v in summary.items() if k != "records"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
