"""Confusion-matrix and overhead-latency evaluation for Musnad Arabic intent routers (v2 vs v3).

Evaluates ``v2`` (deterministic regexes, 0 API calls) and ``v3`` (v2 chain fast path
+ L2 Logistic Regression on ``gemini-embedding-001`` query vectors) across:
  - data/raw/router_fresh2.jsonl (60 items: 30 chain + 30 hard-negative text — HEADLINE)
  - data/raw/golden.jsonl (33 items: 3 'narrator' -> chain, 30 other -> text)
  - data/raw/synthetic_eval.jsonl (224 items: all text)
  - data/raw/chain_eval_dev.jsonl (15 items: all chain)
  - data/raw/chain_eval_test.jsonl (25 items: all chain, frozen test split)
  - data/raw/router_fresh.jsonl (30 items: all chain, labeled 'seen during design')

Does NOT read or touch data/raw/holdout_draft.jsonl and makes 0 Pro/Flash calls
(uses cached/batched gemini-embedding-001 vectors for evaluation only).
"""

from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from src.router import DEFAULT_ROUTER_VERSION, RouteIntent, classify_intent_with_trace, load_router_weights
from src.train_router import ensure_embeddings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = PROJECT_ROOT / "data" / "raw" / "golden.jsonl"
SYNTHETIC_PATH = PROJECT_ROOT / "data" / "raw" / "synthetic_eval.jsonl"
CHAIN_DEV_PATH = PROJECT_ROOT / "data" / "raw" / "chain_eval_dev.jsonl"
CHAIN_TEST_PATH = PROJECT_ROOT / "data" / "raw" / "chain_eval_test.jsonl"
ROUTER_FRESH_PATH = PROJECT_ROOT / "data" / "raw" / "router_fresh.jsonl"
ROUTER_FRESH2_PATH = PROJECT_ROOT / "data" / "raw" / "router_fresh2.jsonl"
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "router_eval_results.json"


@dataclass(frozen=True)
class EvalDatasetSpec:
    name: str
    path: Path
    kind: str  # "golden", "all_text", "all_chain", "row_expected"
    note: str = ""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _expected_intent(row: dict[str, Any], kind: str) -> RouteIntent:
    if kind == "all_chain":
        return "chain"
    if kind == "all_text":
        return "text"
    if kind == "golden":
        return "chain" if row.get("type") == "narrator" else "text"
    if kind == "row_expected":
        val = str(row.get("expected_intent", "")).strip()
        if val not in ("chain", "text"):
            raise ValueError(f"Invalid row expected_intent={val!r}")
        return val  # type: ignore[return-value]
    raise ValueError(f"Unknown dataset kind: {kind!r}")


def _latency_summary(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        return {"median_ms": 0.0, "p95_ms": 0.0, "mean_ms": 0.0}
    arr = np.asarray(latencies_ms, dtype=np.float64)
    return {
        "median_ms": float(statistics.median(latencies_ms)),
        "p95_ms": float(np.percentile(arr, 95)),
        "mean_ms": float(np.mean(arr)),
    }


def evaluate_dataset(
    spec: EvalDatasetSpec,
    *,
    version: str = DEFAULT_ROUTER_VERSION,
    emb_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = _load_jsonl(spec.path)
    tp = fp = tn = fn = 0
    expected_chain = 0
    expected_text = 0
    misrouted: list[dict[str, Any]] = []
    rule_counts: dict[str, int] = {}
    path_counts: dict[str, int] = {}
    latencies_ms: list[float] = []

    for idx, row in enumerate(rows, start=1):
        question = str(row["question"])
        expected = _expected_intent(row, spec.kind)
        emb = emb_cache.get(question) if emb_cache is not None else None
        trace = classify_intent_with_trace(question, embedding=emb, version=version)
        predicted: RouteIntent = trace["intent"]
        rule = trace.get("matched_rule")
        route_path = str(trace.get("path", ""))
        latencies_ms.append(float(trace.get("latency_ms", 0.0)))

        if route_path:
            path_counts[route_path] = path_counts.get(route_path, 0) + 1
        if rule is not None:
            rule_counts[rule] = rule_counts.get(rule, 0) + 1

        if expected == "chain":
            expected_chain += 1
            if predicted == "chain":
                tp += 1
            else:
                fn += 1
        else:
            expected_text += 1
            if predicted == "text":
                tn += 1
            else:
                fp += 1

        if predicted != expected:
            misrouted.append(
                {
                    "index": idx,
                    "id": row.get("id", f"{spec.name}_{idx:03d}"),
                    "type": row.get("type"),
                    "expected": expected,
                    "predicted": predicted,
                    "path": route_path,
                    "matched_rule": rule,
                    "probability": trace.get("probability"),
                    "question": question,
                }
            )

    n = len(rows)
    chain_acc = (tp / expected_chain) if expected_chain else None
    text_acc = (tn / expected_text) if expected_text else None
    bal_acc = (
        0.5 * (chain_acc + text_acc)
        if (chain_acc is not None and text_acc is not None)
        else None
    )
    out: dict[str, Any] = {
        "name": spec.name,
        "path": str(spec.path.relative_to(PROJECT_ROOT)),
        "sha256": _sha256(spec.path),
        "n": n,
        "expected_chain": expected_chain,
        "expected_text": expected_text,
        "tp_chain": tp,
        "fn_chain_as_text": fn,
        "tn_text": tn,
        "fp_text_as_chain": fp,
        "accuracy": (tp + tn) / n if n else 0.0,
        "chain_accuracy": chain_acc,
        "text_accuracy": text_acc,
        "balanced_accuracy": bal_acc,
        "latency_ms": _latency_summary(latencies_ms),
        "path_hits": dict(sorted(path_counts.items())),
        "rule_hits": dict(sorted(rule_counts.items())),
        "misrouted_count": len(misrouted),
        "misrouted": misrouted,
        "_latencies_ms": latencies_ms,
    }
    if spec.note:
        out["note"] = spec.note
    return out


def _evaluate_version(
    version: str,
    specs: list[EvalDatasetSpec],
    emb_cache: dict[str, Any] | None,
) -> dict[str, Any]:
    raw_results = [evaluate_dataset(spec, version=version, emb_cache=emb_cache) for spec in specs]
    all_latencies: list[float] = []
    results: list[dict[str, Any]] = []
    for ds in raw_results:
        all_latencies.extend(ds.pop("_latencies_ms", []))
        results.append(ds)

    by_name = {r["name"]: r for r in results}
    total_n = sum(r["n"] for r in results)
    total_tp = sum(r["tp_chain"] for r in results)
    total_fn = sum(r["fn_chain_as_text"] for r in results)
    total_tn = sum(r["tn_text"] for r in results)
    total_fp = sum(r["fp_text_as_chain"] for r in results)
    total_correct = total_tp + total_tn
    total_chain = sum(r["expected_chain"] for r in results)
    total_text = sum(r["expected_text"] for r in results)

    chain_acc = total_tp / total_chain if total_chain else 0.0
    text_acc = total_tn / total_text if total_text else 0.0
    pooled = {
        "n": total_n,
        "expected_chain": total_chain,
        "expected_text": total_text,
        "tp_chain": total_tp,
        "fn_chain_as_text": total_fn,
        "tn_text": total_tn,
        "fp_text_as_chain": total_fp,
        "accuracy": total_correct / total_n if total_n else 0.0,
        "chain_accuracy": chain_acc,
        "text_accuracy": text_acc,
        "balanced_accuracy": 0.5 * (chain_acc + text_acc),
        "latency_ms": _latency_summary(all_latencies),
    }

    fresh2 = by_name.get("router_fresh2")
    fresh = by_name.get("router_fresh")
    gates = {
        "golden_100pct": by_name["golden"]["accuracy"] == 1.0,
        "chain_dev_100pct": by_name["chain_eval_dev"]["accuracy"] == 1.0,
        "chain_test_100pct": by_name["chain_eval_test"]["accuracy"] == 1.0,
        "synthetic_ge_99pct": (by_name["synthetic_eval"]["text_accuracy"] or 0.0) >= 0.99,
        "fresh_chain_ge_85pct": (fresh["chain_accuracy"] or 0.0) >= 0.85 if fresh else None,
        "fresh2_balanced_ge_85pct": (fresh2["balanced_accuracy"] or 0.0) >= 0.85 if fresh2 else None,
        "zero_misroutes_all_sets": (total_fn + total_fp) == 0,
    }
    return {
        "version": version,
        "datasets": results,
        "pooled": pooled,
        "gates": gates,
    }


def evaluate_all() -> dict[str, Any]:
    specs: list[EvalDatasetSpec] = []
    if ROUTER_FRESH2_PATH.exists():
        specs.append(EvalDatasetSpec("router_fresh2", ROUTER_FRESH2_PATH, "row_expected", note="unseen fresh 30+30 headline"))
    specs.extend(
        [
            EvalDatasetSpec("golden", GOLDEN_PATH, "golden"),
            EvalDatasetSpec("synthetic_eval", SYNTHETIC_PATH, "all_text"),
            EvalDatasetSpec("chain_eval_dev", CHAIN_DEV_PATH, "all_chain"),
            EvalDatasetSpec("chain_eval_test", CHAIN_TEST_PATH, "all_chain", note="frozen test split"),
        ]
    )
    if ROUTER_FRESH_PATH.exists():
        specs.append(EvalDatasetSpec("router_fresh", ROUTER_FRESH_PATH, "all_chain", note="seen during design"))

    all_questions = [
        str(row["question"])
        for spec in specs
        for row in _load_jsonl(spec.path)
    ]
    emb_cache, embed_calls = ensure_embeddings(all_questions)
    # Warm cached weights once so reported median/p95 reflects steady-state request overhead.
    weights = load_router_weights()
    threshold = weights["threshold"] if weights is not None else None

    v2_report = _evaluate_version("v2", specs, emb_cache)
    v3_report = _evaluate_version("v3", specs, emb_cache)
    headline = v3_report if DEFAULT_ROUTER_VERSION == "v3" else v2_report

    return {
        "headline_version": DEFAULT_ROUTER_VERSION,
        "threshold": threshold,
        "api_calls": {"pro": 0, "flash": 0, "embed": embed_calls},
        "versions": {
            "v2": v2_report,
            "v3": v3_report,
        },
        "datasets": headline["datasets"],
        "pooled": headline["pooled"],
        "gates": headline["gates"],
    }


def _print_version_block(title: str, ver_report: dict[str, Any]) -> None:
    print(f"\n[{title}] (pooled router overhead median={ver_report['pooled']['latency_ms']['median_ms']:.4f} ms, p95={ver_report['pooled']['latency_ms']['p95_ms']:.4f} ms)")
    print("-" * 88)
    for ds in ver_report["datasets"]:
        chain_acc = (
            f"{ds['tp_chain']}/{ds['expected_chain']} ({ds['chain_accuracy']*100:.1f}%)"
            if ds["expected_chain"]
            else "n/a"
        )
        text_acc = (
            f"{ds['tn_text']}/{ds['expected_text']} ({ds['text_accuracy']*100:.1f}%)"
            if ds["expected_text"]
            else "n/a"
        )
        bal_str = f" | bal={ds['balanced_accuracy']*100:.2f}%" if ds["balanced_accuracy"] is not None else ""
        note_str = f" [{ds['note']}]" if ds.get("note") else ""
        print(
            f"- {ds['name']}{note_str} (n={ds['n']}): "
            f"overall={ds['tp_chain'] + ds['tn_text']}/{ds['n']} ({ds['accuracy']*100:.2f}%)"
            f"{bal_str} | TP={ds['tp_chain']} FN={ds['fn_chain_as_text']} "
            f"TN={ds['tn_text']} FP={ds['fp_text_as_chain']} | "
            f"chain={chain_acc} | text={text_acc} | "
            f"med={ds['latency_ms']['median_ms']:.4f}ms"
        )
        if ds["misrouted"]:
            print(f"  MISROUTED in {ds['name']} ({len(ds['misrouted'])}):")
            for item in ds["misrouted"]:
                print(
                    f"    [{item['id']}] exp={item['expected']} pred={item['predicted']} "
                    f"path={item['path']} prob={item['probability']} q={item['question']}"
                )
    p = ver_report["pooled"]
    print(
        f"- POOLED (n={p['n']}): {p['tp_chain'] + p['tn_text']}/{p['n']} ({p['accuracy']*100:.2f}%) | "
        f"bal={p['balanced_accuracy']*100:.2f}% | TP={p['tp_chain']} FN={p['fn_chain_as_text']} "
        f"TN={p['tn_text']} FP={p['fp_text_as_chain']}"
    )


def main() -> None:
    report = evaluate_all()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"Router Evaluation (headline={report['headline_version']}, "
        f"pro=0, flash=0, new_embed_calls={report['api_calls']['embed']})"
    )
    print("=" * 88)
    _print_version_block("v2 (regex only)", report["versions"]["v2"])
    _print_version_block(f"v3 (v2 fast path + logreg, thresh={report['threshold']})", report["versions"]["v3"])
    print(f"\nHeadline gates: {report['gates']}")
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
