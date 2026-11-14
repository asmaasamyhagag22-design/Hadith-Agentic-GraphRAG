"""Measure Phase A sanad attachment coverage and latency on saved answer_eval outputs.

Consumes the saved raw outputs from `data/processed/e5_simple_default_results.json`
with zero new LLM calls.
"""

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from answer import attach_sanad, ordered_cited_ids
from config import PROCESSED_DIR
from sanad_context import LINKED_WITH_RECORDED_ISNAD

SOURCE_RESULTS_PATH = PROCESSED_DIR / "e5_simple_default_results.json"
OUT_PATH = PROCESSED_DIR / "sanad_attachment_eval.json"


def measure_attachment(source_path=SOURCE_RESULTS_PATH):
    data = json.loads(Path(source_path).read_text(encoding="utf-8"))
    runs = data["answer_eval"]["runs"]

    # Warm OS page cache once before timing per-request SQLite attachment.
    attach_sanad([8950])

    all_latencies_ms = []
    all_cited_ids = []
    all_attached_ids = []
    unattached_details = []
    per_run = []
    total_requests = 0
    total_cited_requests = 0
    total_refusal_requests = 0

    for run_idx, run in enumerate(runs, start=1):
        run_cited = 0
        run_attached = 0
        run_cited_reqs = 0
        run_full_reqs = 0
        run_latencies = []

        for row in run["rows"]:
            total_requests += 1
            ids = ordered_cited_ids(row["answer"])
            if not ids:
                total_refusal_requests += 1
                continue

            total_cited_requests += 1
            run_cited_reqs += 1
            t0 = time.perf_counter()
            sanad, err = attach_sanad(ids)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            if err is not None:
                raise RuntimeError(f"Unexpected sanad_error during measurement: {err}")

            run_latencies.append(dt_ms)
            all_latencies_ms.append(dt_ms)

            row_all_attached = True
            for entry in sanad:
                hid = entry["hadith_id"]
                run_cited += 1
                all_cited_ids.append(hid)
                if entry["isnad_count"] >= 1 and entry["status"] == LINKED_WITH_RECORDED_ISNAD:
                    run_attached += 1
                    all_attached_ids.append(hid)
                else:
                    row_all_attached = False
                    unattached_details.append(
                        {
                            "run": run_idx,
                            "question": row["question"],
                            "hadith_id": hid,
                            "status": entry["status"],
                        }
                    )
            if row_all_attached:
                run_full_reqs += 1

        per_run.append(
            {
                "run": run_idx,
                "cited_requests": run_cited_reqs,
                "requests_all_cited_attached": run_full_reqs,
                "cited_hadiths": run_cited,
                "attached_hadiths": run_attached,
                "coverage": round(run_attached / run_cited, 4) if run_cited else 0.0,
                "median_latency_ms": round(statistics.median(run_latencies), 3) if run_latencies else 0.0,
            }
        )

    sorted_lat = sorted(all_latencies_ms)
    p95_idx = min(len(sorted_lat) - 1, int(0.95 * len(sorted_lat)))
    unique_cited = set(all_cited_ids)
    unique_attached = set(all_attached_ids)

    return {
        "source_artifact": str(source_path),
        "llm_calls_used": 0,
        "num_runs": len(runs),
        "total_requests": total_requests,
        "total_cited_requests": total_cited_requests,
        "total_refusal_requests": total_refusal_requests,
        "cited_hadith_occurrences": len(all_cited_ids),
        "attached_hadith_occurrences": len(all_attached_ids),
        "attachment_coverage": round(len(all_attached_ids) / len(all_cited_ids), 4),
        "unique_cited_hadiths": len(unique_cited),
        "unique_attached_hadiths": len(unique_attached),
        "unique_attachment_coverage": round(len(unique_attached) / len(unique_cited), 4),
        "median_latency_ms": round(statistics.median(all_latencies_ms), 3),
        "p95_latency_ms": round(sorted_lat[p95_idx], 3),
        "min_latency_ms": round(min(all_latencies_ms), 3),
        "max_latency_ms": round(max(all_latencies_ms), 3),
        "per_run": per_run,
        "unattached_details": unattached_details,
    }


def main():
    summary = measure_attachment()
    OUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Source: {summary['source_artifact']} (0 new LLM calls)")
    print(
        f"Cited hadith attachment coverage (3 runs): "
        f"{summary['attached_hadith_occurrences']}/{summary['cited_hadith_occurrences']} "
        f"({summary['attachment_coverage']:.1%}, exact {summary['attachment_coverage']:.2%})"
    )
    print(
        f"Unique cited hadiths with >=1 recorded chain: "
        f"{summary['unique_attached_hadiths']}/{summary['unique_cited_hadiths']} "
        f"({summary['unique_attachment_coverage']:.2%})"
    )
    print(
        f"Median attachment latency ({summary['total_cited_requests']} cited requests): "
        f"{summary['median_latency_ms']:.3f} ms "
        f"(p95={summary['p95_latency_ms']:.3f} ms, range=[{summary['min_latency_ms']:.3f}, {summary['max_latency_ms']:.3f}])"
    )
    for r in summary["per_run"]:
        print(
            f"  Run {r['run']}: {r['attached_hadiths']}/{r['cited_hadiths']} "
            f"({r['coverage']:.1%}), median={r['median_latency_ms']:.3f} ms"
        )
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
