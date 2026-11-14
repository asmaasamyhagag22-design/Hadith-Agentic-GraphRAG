"""Phase C5 live evaluation harness for the tool-calling Musnad agent.

Measures:
1. ``chain_eval_dev.jsonl`` (n=15) routing accuracy, answer accuracy, hallucinated
   narrators, abstention accuracy, and latency during development.
2. Golden text questions (n=30; 3 runs each) with ``MUSNAD_AGENT`` ON vs OFF
   (correct citation, false refusals, correct refusals, raw violations, median/p95 latency).
3. Frozen ``chain_eval_test.jsonl`` (n=25; ONE final run) agent ON vs OFF.

Tracks every live Pro-class (``gemini-4-argon``) and Flash-class (``gemini-3.8-flash``)
API call persistently in ``data/processed/c5_api_ledger.json`` and aborts BEFORE
exceeding the sprint budget (500 Pro, 800 Flash).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from google.genai.models import Models

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))

import src.answer as ans_mod
import src.answer_eval as answer_eval_mod
from src.build_chain_eval import CHAIN_EVAL_DEV_PATH, CHAIN_EVAL_TEST_PATH
from src.chain_eval import (
    evaluate_chain_predictions,
    format_chain_report,
    load_chain_eval,
    score_chain_item,
)
from src.config import GOLDEN_PATH, PROCESSED_DIR
from src.evaluate import load_golden
from src.pipeline import DEFAULT_K, build_pipeline
from src.retrieve import UpgradedRetriever
from src.sanad_names import load_narrator_lexicon

PRO_BUDGET_CAP = 500
FLASH_BUDGET_CAP = 800

EXPECTED_DEV_SHA256 = "ee90b7fa0eed67aee18927254e4dc894ae4fa37d531e2d16bd0c539ec3f92057"
EXPECTED_TEST_SHA256 = "7cb399587827dddee45ed5af083407f21d04056fd4dcee7f9cb8931777c39025"

LEDGER_PATH = PROCESSED_DIR / "c5_api_ledger.json"
DEV_RESULTS_PATH = PROCESSED_DIR / "c5_dev_results.json"
GOLDEN_RESULTS_PATH = PROCESSED_DIR / "c5_golden_results.json"
TEST_RESULTS_PATH = PROCESSED_DIR / "c5_chain_test_results.json"


class BudgetExceededError(RuntimeError):
    """Raised before making an API call that would exceed the sprint budget."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_ledger() -> dict[str, Any]:
    if LEDGER_PATH.exists():
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return {
        "pro_calls": 0,
        "flash_calls": 0,
        "embed_calls": 0,
        "pro_cap": PRO_BUDGET_CAP,
        "flash_cap": FLASH_BUDGET_CAP,
        "history": [],
    }


def save_ledger(ledger: dict[str, Any]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def _summarize_latency(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "p95": None, "min": None, "max": None}
    arr = np.asarray(values, dtype=np.float64)
    return {
        "n": len(values),
        "mean": round(float(np.mean(arr)), 2),
        "median": round(float(np.median(arr)), 2),
        "p95": round(float(np.percentile(arr, 95)), 2),
        "min": round(float(np.min(arr)), 2),
        "max": round(float(np.max(arr)), 2),
    }


class ApiInstrument:
    """Monkeypatches google-genai Models to count Pro/Flash/Embed calls with hard budget stop."""

    def __init__(self, ledger: dict[str, Any], *, stage: str):
        self.ledger = ledger
        self.stage = stage
        self._orig_gen = None
        self._orig_embed = None
        self._orig_search = None
        self.reset_query_counters()

    def reset_query_counters(self) -> None:
        self.q_pro = 0
        self.q_flash = 0
        self.q_embed = 0
        self.q_retrieval_ms = 0.0
        self.q_api_errors: list[str] = []

    def _classify_model(self, model_name: str) -> str:
        low = model_name.lower()
        if "flash" in low:
            return "flash"
        if "argon" in low or "pro" in low:
            return "pro"
        return "other"

    def _ret_classes(self) -> list[Any]:
        classes: list[Any] = [UpgradedRetriever]
        alt_mod = sys.modules.get("retrieve")
        alt_cls = getattr(alt_mod, "UpgradedRetriever", None) if alt_mod is not None else None
        if alt_cls is not None and alt_cls not in classes:
            classes.append(alt_cls)
        return classes

    def __enter__(self) -> "ApiInstrument":
        self._orig_gen = Models.generate_content
        self._orig_embed = Models.embed_content
        self._orig_searches = [(cls, cls.search) for cls in self._ret_classes()]
        orig_search_by_cls = dict(self._orig_searches)
        inst = self

        def wrapped_gen(models_self, *args, **kwargs):
            model_name = str(
                kwargs.get("model") if "model" in kwargs else (args[0] if args else "")
            )
            bucket = inst._classify_model(model_name)
            if bucket == "pro":
                if inst.ledger["pro_calls"] >= PRO_BUDGET_CAP:
                    raise BudgetExceededError(
                        f"Pro budget reached: {inst.ledger['pro_calls']}/{PRO_BUDGET_CAP}"
                    )
                inst.ledger["pro_calls"] += 1
                inst.q_pro += 1
            elif bucket == "flash":
                if inst.ledger["flash_calls"] >= FLASH_BUDGET_CAP:
                    raise BudgetExceededError(
                        f"Flash budget reached: {inst.ledger['flash_calls']}/{FLASH_BUDGET_CAP}"
                    )
                inst.ledger["flash_calls"] += 1
                inst.q_flash += 1
            save_ledger(inst.ledger)
            try:
                return inst._orig_gen(models_self, *args, **kwargs)
            except Exception as exc:
                inst.q_api_errors.append(f"{model_name}: {type(exc).__name__}: {exc}")
                raise

        def wrapped_embed(models_self, *args, **kwargs):
            inst.ledger["embed_calls"] += 1
            inst.q_embed += 1
            save_ledger(inst.ledger)
            return inst._orig_embed(models_self, *args, **kwargs)

        def wrapped_search(ret_self, question, k=5):
            t0 = time.perf_counter()
            orig = orig_search_by_cls[type(ret_self)]
            try:
                return orig(ret_self, question, k=k)
            finally:
                inst.q_retrieval_ms += (time.perf_counter() - t0) * 1000.0

        Models.generate_content = wrapped_gen
        Models.embed_content = wrapped_embed
        for cls, _ in self._orig_searches:
            cls.search = wrapped_search
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._orig_gen is not None:
            Models.generate_content = self._orig_gen
        if self._orig_embed is not None:
            Models.embed_content = self._orig_embed
        for cls, orig in getattr(self, "_orig_searches", ()):
            cls.search = orig


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_existing(path: Path) -> dict[str, Any] | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _run_chain_dataset(
    *,
    items: list[dict[str, Any]],
    mode_label: str,
    agent_on: bool,
    pipeline: Any,
    lexicon: Any,
    out_path: Path,
    ledger: dict[str, Any],
    dataset_name: str,
    dataset_sha256: str,
    force: bool = False,
) -> dict[str, Any]:
    existing = _load_existing(out_path) or {
        "dataset": dataset_name,
        "dataset_sha256": dataset_sha256,
        "n": len(items),
        "runs": {},
    }
    if not force and mode_label in existing.get("runs", {}):
        run_data = existing["runs"][mode_label]
        if len(run_data.get("records", [])) >= len(items):
            print(f"[{dataset_name} / {mode_label}] Already complete ({len(items)}/{len(items)}), reusing saved file.")
            return existing

    run_state = existing.setdefault("runs", {}).setdefault(
        mode_label,
        {"agent_enabled": agent_on, "records": []},
    )
    if force:
        run_state["records"] = []
    done_ids = {r["id"] for r in run_state["records"]}

    with ApiInstrument(ledger, stage=f"{dataset_name}:{mode_label}") as inst:
        for idx, item in enumerate(items, start=1):
            if item["id"] in done_ids:
                continue
            inst.reset_query_counters()
            t0 = time.perf_counter()
            details = ans_mod.answer_with_details(
                item["question"],
                pipeline,
                k=DEFAULT_K,
                use_agent=agent_on,
            )
            dt_ms = (time.perf_counter() - t0) * 1000.0
            scored = score_chain_item(item, details, lexicon=lexicon)
            if isinstance(scored.get("cited_ids"), set):
                scored["cited_ids"] = sorted(scored["cited_ids"])
            scored["latency_ms"] = round(dt_ms, 2)
            scored["retrieval_ms"] = round(inst.q_retrieval_ms, 2)
            scored["pro_calls"] = inst.q_pro
            scored["flash_calls"] = inst.q_flash
            scored["embed_calls"] = inst.q_embed
            scored["raw"] = details.get("raw", "")
            scored["regenerated"] = bool(details.get("regenerated", False))
            scored["agent_fallback"] = bool(details.get("agent_fallback", False))
            scored["fallback_reason"] = details.get("fallback_reason")
            scored["tool_calls_summary"] = [
                {"name": tc.get("name"), "args": tc.get("args")}
                for tc in (details.get("tool_calls") or ())
            ]
            scored["sanad_count"] = len(details.get("sanad") or ())
            run_state["records"].append(scored)

            records = run_state["records"]
            run_state["summary"] = _summarize_scored_chain_records(records)
            _save_json(out_path, existing)
            print(
                f"  [{dataset_name} {mode_label}] {idx}/{len(items)} {item['id']} "
                f"route={scored['routing_correct']} ans={scored['answer_correct']} "
                f"pro={inst.q_pro} flash={inst.q_flash} {dt_ms:.0f}ms"
            )
    return existing


def _summarize_scored_chain_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    routing_hits = sum(1 for r in records if r["routing_correct"])
    answer_hits = sum(1 for r in records if r["answer_correct"])
    halluc_hits = sum(1 for r in records if not r["no_hallucinated_narrators"])
    abstain_items = [r for r in records if r.get("expected_abstain")]
    abstain_hits = sum(1 for r in abstain_items if r.get("abstain_correct"))
    partial_items = [r for r in records if r.get("expected_partial_abstain")]
    partial_hits = sum(1 for r in partial_items if r.get("partial_abstain_correct"))
    by_type: dict[str, dict[str, Any]] = {}
    for r in records:
        qt = r["type"]
        bucket = by_type.setdefault(qt, {"n": 0, "routing_hits": 0, "answer_hits": 0})
        bucket["n"] += 1
        bucket["routing_hits"] += int(bool(r["routing_correct"]))
        bucket["answer_hits"] += int(bool(r["answer_correct"]))
    for bucket in by_type.values():
        bn = bucket["n"]
        bucket["routing_accuracy"] = round(bucket["routing_hits"] / bn, 4) if bn else None
        bucket["answer_accuracy"] = round(bucket["answer_hits"] / bn, 4) if bn else None

    return {
        "n": n,
        "routing_hits": routing_hits,
        "routing_accuracy": round(routing_hits / n, 4) if n else None,
        "answer_hits": answer_hits,
        "answer_accuracy": round(answer_hits / n, 4) if n else None,
        "hallucinated_narrator_cases": halluc_hits,
        "abstention_hits": abstain_hits,
        "abstention_total": len(abstain_items),
        "abstention_accuracy": round(abstain_hits / len(abstain_items), 4) if abstain_items else None,
        "partial_abstain_hits": partial_hits,
        "partial_abstain_total": len(partial_items),
        "regenerated_count": sum(1 for r in records if r.get("regenerated")),
        "fallback_count": sum(1 for r in records if r.get("agent_fallback")),
        "pro_calls_total": sum(int(r.get("pro_calls", 0)) for r in records),
        "flash_calls_total": sum(int(r.get("flash_calls", 0)) for r in records),
        "latency_ms": _summarize_latency([float(r["latency_ms"]) for r in records]),
        "by_type": by_type,
    }


def _summarize_golden_run(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ans_rows = [r for r in rows if r["answerable"]]
    ref_rows = [r for r in rows if r["refusal_test"]]
    gold_in_ctx = [r for r in rows if r["gold_in_context"]]
    return {
        "n": len(rows),
        "answerable_n": len(ans_rows),
        "refusal_n": len(ref_rows),
        "correct_citation_hits": sum(1 for r in ans_rows if r["correct_citation"]),
        "correct_citation_rate": round(sum(1 for r in ans_rows if r["correct_citation"]) / len(ans_rows), 4),
        "false_refusal_hits": sum(1 for r in gold_in_ctx if r["refused"]),
        "false_refusal_on_ans_hits": sum(1 for r in ans_rows if r["refused"]),
        "false_refusal_rate": round(sum(1 for r in gold_in_ctx if r["refused"]) / len(gold_in_ctx), 4) if gold_in_ctx else None,
        "correct_refusal_hits": sum(1 for r in ref_rows if r["refused"]),
        "correct_refusal_rate": round(sum(1 for r in ref_rows if r["refused"]) / len(ref_rows), 4) if ref_rows else None,
        "wrong_citation_hits": sum(1 for r in rows if r["wrong_citation"]),
        "invalid_citation_hits": sum(1 for r in rows if r["invalid_citation"]),
        "missing_citation_hits": sum(1 for r in rows if r["missing_citation"]),
        "disallowed_narrators_hits": sum(1 for r in rows if r.get("disallowed_narrators_attempt")),
        "regenerated_hits": sum(1 for r in rows if r["regenerated"]),
        "fallback_hits": sum(1 for r in rows if r.get("agent_fallback")),
        "gold_in_context_hits": len(gold_in_ctx),
        "pro_calls_total": sum(int(r.get("pro_calls", 0)) for r in rows),
        "flash_calls_total": sum(int(r.get("flash_calls", 0)) for r in rows),
        "cache_hit_queries": sum(1 for r in rows if r.get("retrieval_ms", 0.0) < 50.0 and r.get("search_called", True)),
        "latency_ms": _summarize_latency([float(r["latency_ms"]) for r in rows]),
        "generation_plus_agent_ms": _summarize_latency([float(r["latency_ms"]) - float(r.get("retrieval_ms", 0.0)) for r in rows]),
    }


def _aggregate_golden_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    summaries = [r["summary"] for r in runs]
    all_latencies = [float(row["latency_ms"]) for r in runs for row in r["rows"]]
    all_gen_latencies = [
        float(row["latency_ms"]) - float(row.get("retrieval_ms", 0.0))
        for r in runs
        for row in r["rows"]
    ]
    return {
        "num_runs": len(runs),
        "correct_citation_mean_hits": round(float(np.mean([s["correct_citation_hits"] for s in summaries])), 4),
        "correct_citation_mean_rate": round(float(np.mean([s["correct_citation_rate"] for s in summaries])), 4),
        "correct_citation_hits_per_run": [s["correct_citation_hits"] for s in summaries],
        "false_refusal_mean_hits": round(float(np.mean([s["false_refusal_on_ans_hits"] for s in summaries])), 4),
        "false_refusal_hits_per_run": [s["false_refusal_on_ans_hits"] for s in summaries],
        "false_refusal_gold_ctx_mean_hits": round(float(np.mean([s["false_refusal_hits"] for s in summaries])), 4),
        "false_refusal_gold_ctx_mean_rate": round(float(np.mean([s["false_refusal_rate"] for s in summaries])), 4),
        "correct_refusal_mean_hits": round(float(np.mean([s["correct_refusal_hits"] for s in summaries])), 4),
        "correct_refusal_mean_rate": round(float(np.mean([s["correct_refusal_rate"] for s in summaries])), 4),
        "correct_refusal_hits_per_run": [s["correct_refusal_hits"] for s in summaries],
        "invalid_citation_total_hits": sum(s["invalid_citation_hits"] for s in summaries),
        "regenerated_total_hits": sum(s["regenerated_hits"] for s in summaries),
        "fallback_total_hits": sum(s["fallback_hits"] for s in summaries),
        "cache_hit_queries_total": sum(s["cache_hit_queries"] for s in summaries),
        "pro_calls_total": sum(s["pro_calls_total"] for s in summaries),
        "flash_calls_total": sum(s["flash_calls_total"] for s in summaries),
        "run_median_latencies_ms": [s["latency_ms"]["median"] for s in summaries],
        "pooled_latency_ms": _summarize_latency(all_latencies),
        "pooled_generation_plus_agent_ms": _summarize_latency(all_gen_latencies),
    }


def run_golden_eval(
    *,
    pipeline: Any,
    ledger: dict[str, Any],
    num_runs: int = 3,
    force: bool = False,
) -> dict[str, Any]:
    all_items = load_golden(GOLDEN_PATH)
    items = [it for it in all_items if it.get("type") != "narrator"]
    data = _load_existing(GOLDEN_RESULTS_PATH) or {
        "dataset": str(GOLDEN_PATH),
        "n_text": len(items),
        "num_runs": num_runs,
        "modes": {"off": {"runs": []}, "on": {"runs": []}},
    }
    if force:
        data["modes"] = {"off": {"runs": []}, "on": {"runs": []}}

    for mode_key, agent_flag in (("off", False), ("on", True)):
        mode_bucket = data["modes"][mode_key]
        while len(mode_bucket["runs"]) < num_runs:
            mode_bucket["runs"].append({"run_index": len(mode_bucket["runs"]) + 1, "rows": []})

        for r_idx in range(num_runs):
            run_obj = mode_bucket["runs"][r_idx]
            rows = run_obj["rows"]
            if len(rows) >= len(items) and "summary" in run_obj:
                print(f"[golden / {mode_key} run {r_idx + 1}/{num_runs}] Already complete, skipping.")
                continue
            done_indices = {r["index"] for r in rows}
            with ApiInstrument(ledger, stage=f"golden:{mode_key}:run{r_idx+1}") as inst:
                for q_idx, item in enumerate(items, start=1):
                    if q_idx in done_indices:
                        continue
                    inst.reset_query_counters()
                    t0 = time.perf_counter()
                    details = ans_mod.answer_with_details(
                        item["question"],
                        pipeline,
                        k=DEFAULT_K,
                        use_agent=agent_flag,
                    )
                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    answer = details["answer"]
                    raw = details["raw"]
                    chunks = details["chunks"]
                    context_ids = {int(c["hadith_id"]) for c in chunks}
                    gold_ids = {int(x) for x in item.get("hadith_ids", [])}
                    cited = ans_mod.cited_ids(answer)
                    refused = answer_eval_mod.is_refusal(answer)
                    tool_names = [tc.get("name") for tc in (details.get("tool_calls") or ())]
                    row = {
                        "index": q_idx,
                        "question": item["question"],
                        "answerable": item.get("answerable", True),
                        "refusal_test": item.get("type") == "refusal",
                        "gold_ids": sorted(gold_ids),
                        "gold_in_context": bool(gold_ids & context_ids),
                        "refused": refused,
                        "cited_ids": sorted(cited),
                        "wrong_citation": bool(cited and cited <= context_ids and not (cited & gold_ids)),
                        "correct_citation": bool(cited & gold_ids),
                        "invalid_citation": bool(details.get("invalid_citation_attempt")),
                        "missing_citation": bool(details.get("missing_citation_attempt")),
                        "loose_out_of_context": bool(details.get("loose_out_of_context_attempt")),
                        "mixed_refusal": bool(details.get("mixed_refusal_attempt")),
                        "disallowed_narrators_attempt": list(details.get("disallowed_narrators_attempt") or ()),
                        "regenerated": bool(details.get("regenerated")),
                        "agent_used": bool(details.get("agent_used", False)),
                        "agent_fallback": bool(details.get("agent_fallback", False)),
                        "fallback_reason": details.get("fallback_reason"),
                        "search_called": ("search_hadith" in tool_names) if agent_flag else True,
                        "tool_calls": [
                            {"name": tc.get("name"), "args": tc.get("args")}
                            for tc in (details.get("tool_calls") or ())
                        ],
                        "sanad_count": len(details.get("sanad") or ()),
                        "latency_ms": round(dt_ms, 2),
                        "retrieval_ms": round(inst.q_retrieval_ms, 2),
                        "pro_calls": inst.q_pro,
                        "flash_calls": inst.q_flash,
                        "embed_calls": inst.q_embed,
                        "answer": answer,
                        "raw": raw,
                    }
                    rows.append(row)
                    run_obj["summary"] = _summarize_golden_run(rows)
                    _save_json(GOLDEN_RESULTS_PATH, data)
                    print(
                        f"  [golden {mode_key} r{r_idx+1}] {q_idx}/{len(items)} "
                        f"corr={row['correct_citation']} ref={row['refused']} "
                        f"pro={inst.q_pro} flash={inst.q_flash} {dt_ms:.0f}ms"
                    )
        mode_bucket["aggregate"] = _aggregate_golden_runs(mode_bucket["runs"])
        _save_json(GOLDEN_RESULTS_PATH, data)
    return data


def compute_gate1_status() -> dict[str, Any]:
    golden = _load_existing(GOLDEN_RESULTS_PATH)
    test = _load_existing(TEST_RESULTS_PATH)
    out: dict[str, Any] = {"ready": bool(golden and test), "checks": {}}
    if golden:
        off_agg = golden["modes"]["off"].get("aggregate", {})
        on_agg = golden["modes"]["on"].get("aggregate", {})
        off_cit = off_agg.get("correct_citation_mean_hits", 0.0)
        on_cit = on_agg.get("correct_citation_mean_hits", 0.0)
        off_ref = off_agg.get("correct_refusal_mean_hits", 0.0)
        on_ref = on_agg.get("correct_refusal_mean_hits", 0.0)
        off_med = (off_agg.get("pooled_latency_ms") or {}).get("median")
        on_med = (on_agg.get("pooled_latency_ms") or {}).get("median")
        out["checks"]["golden_citation_drop"] = round(off_cit - on_cit, 4)
        out["checks"]["golden_citation_fail"] = (off_cit - on_cit) > 1.0
        out["checks"]["golden_refusal_drop"] = round(off_ref - on_ref, 4)
        out["checks"]["golden_refusal_fail"] = (off_ref - on_ref) > 1.0
        if off_med and on_med:
            ratio = on_med / off_med
            out["checks"]["latency_ratio_pooled_median"] = round(ratio, 4)
            out["checks"]["latency_rise_pct"] = round((ratio - 1.0) * 100.0, 2)
            out["checks"]["latency_fail"] = ratio > 1.5
    if test:
        on_sum = (test.get("runs", {}).get("agent_on") or {}).get("summary", {})
        acc = on_sum.get("answer_accuracy")
        out["checks"]["chain_test_answer_accuracy"] = acc
        out["checks"]["chain_test_acc_fail"] = (acc is not None) and (acc < 0.80)
    checks = out["checks"]
    out["gate1_stop_triggered"] = any(
        bool(checks.get(k))
        for k in (
            "golden_citation_fail",
            "golden_refusal_fail",
            "chain_test_acc_fail",
            "latency_fail",
        )
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase C5 Musnad agent evaluation.")
    parser.add_argument(
        "--stage",
        choices=("dev", "golden", "test", "summary"),
        required=True,
    )
    parser.add_argument("--force", action="store_true", help="Re-run even if saved results exist.")
    args = parser.parse_args()

    ledger = load_ledger()
    print(
        f"Budget before stage={args.stage}: "
        f"Pro={ledger['pro_calls']}/{PRO_BUDGET_CAP}, "
        f"Flash={ledger['flash_calls']}/{FLASH_BUDGET_CAP}"
    )

    if args.stage == "summary":
        for label, path in (("dev", DEV_RESULTS_PATH), ("golden", GOLDEN_RESULTS_PATH), ("test", TEST_RESULTS_PATH)):
            d = _load_existing(path)
            print(f"\n=== {label} ({path}) ===")
            if not d:
                print("  missing")
                continue
            if "runs" in d:
                for k, v in d["runs"].items():
                    print(f"  {k}:", json.dumps(v.get("summary"), ensure_ascii=False))
            elif "modes" in d:
                for k, v in d["modes"].items():
                    print(f"  {k}:", json.dumps(v.get("aggregate"), ensure_ascii=False))
        print("\n=== Gate 1 Status ===")
        print(json.dumps(compute_gate1_status(), ensure_ascii=False, indent=2))
        return

    pipeline = build_pipeline(mode="upgraded", agent="off")
    lexicon = load_narrator_lexicon()

    if args.stage == "dev":
        dev_sha = sha256_file(CHAIN_EVAL_DEV_PATH)
        assert dev_sha == EXPECTED_DEV_SHA256, f"dev sha mismatch: {dev_sha}"
        dev_items = load_chain_eval(CHAIN_EVAL_DEV_PATH)
        res = _run_chain_dataset(
            items=dev_items,
            mode_label="agent_on",
            agent_on=True,
            pipeline=pipeline,
            lexicon=lexicon,
            out_path=DEV_RESULTS_PATH,
            ledger=ledger,
            dataset_name="chain_eval_dev",
            dataset_sha256=dev_sha,
            force=args.force,
        )
        summary = res["runs"]["agent_on"]["summary"]
        print("\nDEV SUMMARY:", json.dumps(summary, ensure_ascii=False, indent=2))
        print("\nDEV FAILURES:")
        for r in res["runs"]["agent_on"]["records"]:
            if not (r["routing_correct"] and r["answer_correct"]):
                print(f"  {r['id']} ({r['type']}): route={r['routing_correct']} ans={r['answer_correct']} reasons={r['failure_reasons']} tools={r['tool_calls_summary']}")
                print(f"    answer: {r['answer'][:220]}")

    elif args.stage == "golden":
        res = run_golden_eval(pipeline=pipeline, ledger=ledger, num_runs=3, force=args.force)
        print("\nGOLDEN AGGREGATE:")
        print("  OFF:", json.dumps(res["modes"]["off"]["aggregate"], ensure_ascii=False, indent=2))
        print("  ON:", json.dumps(res["modes"]["on"]["aggregate"], ensure_ascii=False, indent=2))

    elif args.stage == "test":
        test_sha = sha256_file(CHAIN_EVAL_TEST_PATH)
        assert test_sha == EXPECTED_TEST_SHA256, f"FROZEN chain_eval_test sha mismatch: {test_sha}"
        test_items = load_chain_eval(CHAIN_EVAL_TEST_PATH)
        _run_chain_dataset(
            items=test_items,
            mode_label="agent_off",
            agent_on=False,
            pipeline=pipeline,
            lexicon=lexicon,
            out_path=TEST_RESULTS_PATH,
            ledger=ledger,
            dataset_name="chain_eval_test",
            dataset_sha256=test_sha,
            force=False,
        )
        res = _run_chain_dataset(
            items=test_items,
            mode_label="agent_on",
            agent_on=True,
            pipeline=pipeline,
            lexicon=lexicon,
            out_path=TEST_RESULTS_PATH,
            ledger=ledger,
            dataset_name="chain_eval_test",
            dataset_sha256=test_sha,
            force=False,
        )
        print("\nFROZEN TEST SUMMARY:")
        for k in ("agent_off", "agent_on"):
            print(f"  {k}:", json.dumps(res["runs"][k]["summary"], ensure_ascii=False, indent=2))

    ledger = load_ledger()
    print(
        f"\nBudget after stage={args.stage}: "
        f"Pro={ledger['pro_calls']}/{PRO_BUDGET_CAP}, "
        f"Flash={ledger['flash_calls']}/{FLASH_BUDGET_CAP}, "
        f"Embed={ledger['embed_calls']}"
    )


if __name__ == "__main__":
    main()
