"""Zero-API confusion-matrix evaluation for the deterministic Arabic intent router.

Evaluates ``src.router.classify_intent`` across:
  - data/raw/golden.jsonl (33 items: 3 'narrator' -> chain, 30 other -> text)
  - data/raw/synthetic_eval.jsonl (224 items: all text)
  - data/raw/chain_eval_dev.jsonl (15 items: all chain)
  - data/raw/chain_eval_test.jsonl (25 items: all chain, frozen test split)

Does NOT read or touch data/raw/holdout_draft.jsonl and makes 0 model/API calls.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.router import RouteIntent, classify_intent, matched_chain_rule

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = PROJECT_ROOT / "data" / "raw" / "golden.jsonl"
SYNTHETIC_PATH = PROJECT_ROOT / "data" / "raw" / "synthetic_eval.jsonl"
CHAIN_DEV_PATH = PROJECT_ROOT / "data" / "raw" / "chain_eval_dev.jsonl"
CHAIN_TEST_PATH = PROJECT_ROOT / "data" / "raw" / "chain_eval_test.jsonl"
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "router_eval_results.json"


@dataclass(frozen=True)
class EvalDatasetSpec:
    name: str
    path: Path
    kind: str  # "golden", "all_text", "all_chain"


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
    raise ValueError(f"Unknown dataset kind: {kind!r}")


def evaluate_dataset(spec: EvalDatasetSpec) -> dict[str, Any]:
    rows = _load_jsonl(spec.path)
    tp = fp = tn = fn = 0
    expected_chain = 0
    expected_text = 0
    misrouted: list[dict[str, Any]] = []
    rule_counts: dict[str, int] = {}

    for idx, row in enumerate(rows, start=1):
        question = str(row["question"])
        expected = _expected_intent(row, spec.kind)
        rule = matched_chain_rule(question)
        predicted: RouteIntent = classify_intent(question)

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
                    "matched_rule": rule,
                    "question": question,
                }
            )

    n = len(rows)
    return {
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
        "chain_accuracy": (tp / expected_chain) if expected_chain else None,
        "text_accuracy": (tn / expected_text) if expected_text else None,
        "rule_hits": dict(sorted(rule_counts.items())),
        "misrouted_count": len(misrouted),
        "misrouted": misrouted,
    }


def evaluate_all() -> dict[str, Any]:
    specs = [
        EvalDatasetSpec("golden", GOLDEN_PATH, "golden"),
        EvalDatasetSpec("synthetic_eval", SYNTHETIC_PATH, "all_text"),
        EvalDatasetSpec("chain_eval_dev", CHAIN_DEV_PATH, "all_chain"),
        EvalDatasetSpec("chain_eval_test", CHAIN_TEST_PATH, "all_chain"),
    ]
    results = [evaluate_dataset(spec) for spec in specs]
    by_name = {r["name"]: r for r in results}

    total_n = sum(r["n"] for r in results)
    total_tp = sum(r["tp_chain"] for r in results)
    total_fn = sum(r["fn_chain_as_text"] for r in results)
    total_tn = sum(r["tn_text"] for r in results)
    total_fp = sum(r["fp_text_as_chain"] for r in results)
    total_correct = total_tp + total_tn
    total_chain = sum(r["expected_chain"] for r in results)
    total_text = sum(r["expected_text"] for r in results)

    gates = {
        "golden_100pct": by_name["golden"]["accuracy"] == 1.0,
        "chain_dev_100pct": by_name["chain_eval_dev"]["accuracy"] == 1.0,
        "chain_test_100pct": by_name["chain_eval_test"]["accuracy"] == 1.0,
        "synthetic_ge_99pct": (by_name["synthetic_eval"]["text_accuracy"] or 0.0) >= 0.99,
        "zero_misroutes_all_sets": (total_fn + total_fp) == 0,
    }
    gates["passed_step4_threshold"] = (
        gates["golden_100pct"]
        and gates["chain_test_100pct"]
        and gates["synthetic_ge_99pct"]
    )

    return {
        "api_calls": {"pro": 0, "flash": 0, "embed": 0},
        "datasets": results,
        "pooled": {
            "n": total_n,
            "expected_chain": total_chain,
            "expected_text": total_text,
            "tp_chain": total_tp,
            "fn_chain_as_text": total_fn,
            "tn_text": total_tn,
            "fp_text_as_chain": total_fp,
            "accuracy": total_correct / total_n if total_n else 0.0,
            "chain_accuracy": total_tp / total_chain if total_chain else 0.0,
            "text_accuracy": total_tn / total_text if total_text else 0.0,
        },
        "gates": gates,
    }


def main() -> None:
    report = evaluate_all()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Router Confusion Matrix Summary (0 API calls)")
    print("=" * 72)
    for ds in report["datasets"]:
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
        print(
            f"- {ds['name']} (n={ds['n']}): "
            f"overall={ds['tp_chain'] + ds['tn_text']}/{ds['n']} ({ds['accuracy']*100:.2f}%) | "
            f"TP={ds['tp_chain']} FN={ds['fn_chain_as_text']} TN={ds['tn_text']} FP={ds['fp_text_as_chain']} | "
            f"chain={chain_acc} | text={text_acc}"
        )
        if ds["misrouted"]:
            print(f"  MISROUTED in {ds['name']} ({len(ds['misrouted'])}):")
            for item in ds["misrouted"]:
                print(
                    f"    [{item['id']}] exp={item['expected']} pred={item['predicted']} "
                    f"rule={item['matched_rule']} q={item['question']}"
                )

    p = report["pooled"]
    print(
        f"- POOLED (n={p['n']}): {p['tp_chain'] + p['tn_text']}/{p['n']} ({p['accuracy']*100:.2f}%) | "
        f"TP={p['tp_chain']} FN={p['fn_chain_as_text']} TN={p['tn_text']} FP={p['fp_text_as_chain']}"
    )
    print(f"Gates: {report['gates']}")
    print(f"Saved: {OUT_PATH}")


if __name__ == "__main__":
    main()
