"""
Step P4 evaluation:
1. Offline McNemar statistical simplicity check comparing:
   - 1:0:0:0 (Dense_matn_HyDE only)
   - 8:0:1:0 (Dense_matn_HyDE + BM25_matn, no document expansion)
   - 8:2:1:1 (Full Upgraded 4-way RRF)
   across dev (n=224) and golden (n=27) for hit@1, hit@3, hit@5, and hit@10.
2. Live uncached end-to-end latency (median, p95, min, max, stage breakdown)
   and token/cost breakdown per query using the default Upgraded pipeline
   + gemini-4-argon generator.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google.genai.models import Models

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))

import answer as ans_mod
from config import (
    GOLDEN_PATH,
    PROCESSED_DIR,
    SYNTHETIC_EVAL_PATH,
)
from experiment_e3_rerankers import pair_mcnemar
from experiment_e5_ablation_and_leakage import answerable, eval_fast, load_jsonl
from experiment_step4_newer_llm import (
    G38_PRICE_INPUT_PER_1M,
    G38_PRICE_OUTPUT_PER_1M,
)
from pipeline import DEFAULT_K, build_pipeline
from retrieve import UpgradedRetriever

OUT_JSON_PATH = PROCESSED_DIR / "p4_results.json"

EMBED_PRICE_INPUT_PER_1M = 0.15
ARGON_INTRO_INPUT_PER_1M = 2.00
ARGON_INTRO_OUTPUT_PER_1M = 10.00
ARGON_STD_INPUT_PER_1M = 4.00
ARGON_STD_OUTPUT_PER_1M = 20.00

SIMPLICITY_CONFIGS = [
    ("1:0:0:0", (1.0, 0.0, 0.0, 0.0)),
    ("8:0:1:0", (8.0, 0.0, 1.0, 0.0)),
    ("8:2:1:1", (8.0, 2.0, 1.0, 1.0)),
]

SIMPLICITY_PAIRS = [
    ("8:2:1:1", "8:0:1:0"),
    ("8:0:1:0", "1:0:0:0"),
    ("8:2:1:1", "1:0:0:0"),
]


def _make_weighted_retriever(base_ret, weights):
    return UpgradedRetriever(
        matn_vectors=base_ret.matn_vectors,
        exp_vectors=base_ret.exp_vectors,
        bm25_matn=base_ret.bm25_matn,
        bm25_exp=base_ret.bm25_exp,
        chunk_ids=base_ret.chunk_ids,
        chunk_lookup=base_ret.chunk_lookup,
        query_vec_cache=base_ret.query_vec_cache,
        hyde_vec_cache=base_ret.hyde_vec_cache,
        weights=weights,
        hyde_alpha=base_ret.hyde_alpha,
        candidates=base_ret.candidates,
        rrf_k=base_ret.rrf_k,
        api_timeout_ms=None,
    )


def run_mcnemar_simplicity_check(base_ret, dev_items, gold_items):
    """Evaluate 1:0:0:0, 8:0:1:0, and 8:2:1:1 offline and run pairwise McNemar."""
    metrics_by_ds = {"dev": {}, "golden": {}}
    ranks_by_ds = {"dev": {}, "golden": {}}

    for label, weights in SIMPLICITY_CONFIGS:
        ret = _make_weighted_retriever(base_ret, weights)
        for ds_name, items in (("dev", dev_items), ("golden", gold_items)):
            m, r10, _ = eval_fast(ret, items)
            assert not ret.last_used_fallback, (
                f"Unexpected fallback in offline eval ({label}, {ds_name})"
            )
            metrics_by_ds[ds_name][label] = m
            ranks_by_ds[ds_name][label] = r10

    mcnemar_by_ds = {"dev": {}, "golden": {}}
    for ds_name in ("dev", "golden"):
        for name_a, name_b in SIMPLICITY_PAIRS:
            pair_key = f"{name_a}_vs_{name_b}"
            mcnemar_by_ds[ds_name][pair_key] = {}
            for k in (1, 3, 5, 10):
                res = pair_mcnemar(
                    ranks_by_ds[ds_name][name_a],
                    ranks_by_ds[ds_name][name_b],
                    k,
                )
                mcnemar_by_ds[ds_name][pair_key][f"hit@{k}"] = res

    return {
        "metrics": metrics_by_ds,
        "mcnemar": mcnemar_by_ds,
    }


def _summarize_series(values):
    if not values:
        return {"n": 0, "mean": 0.0, "median": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
    arr = np.asarray(values, dtype=np.float64)
    return {
        "n": int(len(arr)),
        "mean": round(float(np.mean(arr)), 2),
        "median": round(float(np.median(arr)), 2),
        "p95": round(float(np.percentile(arr, 95)), 2),
        "min": round(float(np.min(arr)), 2),
        "max": round(float(np.max(arr)), 2),
    }


def _extract_usage_dict(usage_meta):
    if usage_meta is None:
        return {"prompt": 0, "candidates": 0, "thoughts": 0, "total": 0}
    return {
        "prompt": int(getattr(usage_meta, "prompt_token_count", 0) or 0),
        "candidates": int(getattr(usage_meta, "candidates_token_count", 0) or 0),
        "thoughts": int(getattr(usage_meta, "thoughts_token_count", 0) or 0),
        "total": int(getattr(usage_meta, "total_token_count", 0) or 0),
    }


def _usd_cost_for_trace(trace):
    ok_embeds = [c for c in trace["embed_calls"] if not c.get("error")]
    ok_gens = [c for c in trace["gen_calls"] if not c.get("error")]

    emb_tokens = sum(c["tokens"] for c in ok_embeds)
    hyde_in = sum(c["prompt"] for c in ok_gens if c["role"] == "hyde")
    hyde_out = sum(
        c["candidates"] + c["thoughts"] for c in ok_gens if c["role"] == "hyde"
    )
    argon_in = sum(c["prompt"] for c in ok_gens if c["role"] == "answer")
    argon_out = sum(
        c["candidates"] + c["thoughts"] for c in ok_gens if c["role"] == "answer"
    )

    emb_usd = (emb_tokens / 1_000_000.0) * EMBED_PRICE_INPUT_PER_1M
    hyde_usd = (
        (hyde_in / 1_000_000.0) * G38_PRICE_INPUT_PER_1M
        + (hyde_out / 1_000_000.0) * G38_PRICE_OUTPUT_PER_1M
    )
    argon_intro_usd = (
        (argon_in / 1_000_000.0) * ARGON_INTRO_INPUT_PER_1M
        + (argon_out / 1_000_000.0) * ARGON_INTRO_OUTPUT_PER_1M
    )
    argon_std_usd = (
        (argon_in / 1_000_000.0) * ARGON_STD_INPUT_PER_1M
        + (argon_out / 1_000_000.0) * ARGON_STD_OUTPUT_PER_1M
    )
    return {
        "embed_tokens": int(emb_tokens),
        "hyde_prompt_tokens": int(hyde_in),
        "hyde_output_plus_thoughts_tokens": int(hyde_out),
        "argon_prompt_tokens": int(argon_in),
        "argon_output_plus_thoughts_tokens": int(argon_out),
        "retrieval_usd": emb_usd + hyde_usd,
        "embed_usd": emb_usd,
        "hyde_usd": hyde_usd,
        "generation_intro_usd": argon_intro_usd,
        "generation_std_usd": argon_std_usd,
        "total_intro_usd": emb_usd + hyde_usd + argon_intro_usd,
        "total_std_usd": emb_usd + hyde_usd + argon_std_usd,
    }


def _build_live_summary(records, warmup_record, fallback_events):
    latency_summary = {
        key: _summarize_series([r[key] for r in records])
        for key in (
            "e2e_ms",
            "retrieval_ms",
            "generation_stage_ms",
            "query_embed_ms",
            "hyde_gen_ms",
            "hyde_embed_ms",
            "local_rrf_ms",
        )
    }

    token_summary = {}
    if records:
        for key in (
            "embed_tokens",
            "hyde_prompt_tokens",
            "hyde_output_plus_thoughts_tokens",
            "argon_prompt_tokens",
            "argon_output_plus_thoughts_tokens",
        ):
            vals = [r["costs"][key] for r in records]
            token_summary[key] = {
                "mean": round(float(np.mean(vals)), 2),
                "median": round(float(np.median(vals)), 2),
                "min": int(min(vals)),
                "max": int(max(vals)),
                "total": int(sum(vals)),
            }

    cost_summary = {}
    if records:
        for key in (
            "embed_usd",
            "hyde_usd",
            "retrieval_usd",
            "generation_intro_usd",
            "generation_std_usd",
            "total_intro_usd",
            "total_std_usd",
        ):
            vals = [r["costs"][key] for r in records]
            cost_summary[key] = {
                "mean_usd": round(float(np.mean(vals)), 6),
                "median_usd": round(float(np.median(vals)), 6),
                "total_usd": round(float(sum(vals)), 6),
            }

    return {
        "model": ans_mod.MODEL,
        "k": DEFAULT_K,
        "n": len(records),
        "regenerated_count": sum(1 for r in records if r["regenerated"]),
        "fallback_events_count": len(fallback_events),
        "fallback_events": fallback_events,
        "warmup": warmup_record,
        "latency_summary_ms": latency_summary,
        "token_summary": token_summary,
        "cost_summary_usd": cost_summary,
        "pricing_rates_per_1m_tokens": {
            "gemini-embedding-001_input": EMBED_PRICE_INPUT_PER_1M,
            "gemini-3.8-flash_input": G38_PRICE_INPUT_PER_1M,
            "gemini-3.8-flash_output_incl_thoughts": G38_PRICE_OUTPUT_PER_1M,
            "gemini-4-argon_intro_input": ARGON_INTRO_INPUT_PER_1M,
            "gemini-4-argon_intro_output_incl_thoughts": ARGON_INTRO_OUTPUT_PER_1M,
            "gemini-4-argon_std_input": ARGON_STD_INPUT_PER_1M,
            "gemini-4-argon_std_output_incl_thoughts": ARGON_STD_OUTPUT_PER_1M,
        },
        "records": records,
    }


def _save_payload(simplicity, live_stats):
    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {"simplicity": simplicity, "live_latency_and_cost": live_stats},
            f,
            ensure_ascii=False,
            indent=2,
        )


def measure_live_latency_and_cost(base_ret, warmup_item, eval_items, simplicity):
    """
    Run 1 untimed warmup query + N uncached end-to-end queries via
    UpgradedRetriever + answer_with_details(k=DEFAULT_K, model=ans_mod.MODEL).
    Saves incrementally to p4_results.json after every query.
    """
    live_ret = UpgradedRetriever(
        matn_vectors=base_ret.matn_vectors,
        exp_vectors=base_ret.exp_vectors,
        bm25_matn=base_ret.bm25_matn,
        bm25_exp=base_ret.bm25_exp,
        chunk_ids=base_ret.chunk_ids,
        chunk_lookup=base_ret.chunk_lookup,
        query_vec_cache={},
        hyde_vec_cache={},
        weights=base_ret.weights,
        hyde_alpha=base_ret.hyde_alpha,
        candidates=base_ret.candidates,
        rrf_k=base_ret.rrf_k,
        api_timeout_ms=base_ret.api_timeout_ms,
        fallback_retriever=base_ret.fallback_retriever,
        fallback_factory=base_ret.fallback_factory,
    )

    orig_search = UpgradedRetriever.search
    orig_embed = Models.embed_content
    orig_gen = Models.generate_content

    active_trace = {}

    def wrapped_search(self, question, k=5):
        t0 = time.perf_counter()
        active_trace["in_search"] = True
        try:
            return orig_search(self, question, k=k)
        finally:
            active_trace["in_search"] = False
            active_trace["retrieval_ms"] = (time.perf_counter() - t0) * 1000.0

    def wrapped_embed(self, *args, **kwargs):
        t0 = time.perf_counter()
        label = (
            "query_embed"
            if not any(
                c["label"] == "query_embed" and not c.get("error")
                for c in active_trace["embed_calls"]
            )
            else "hyde_embed"
        )
        try:
            resp = orig_embed(self, *args, **kwargs)
        except Exception as exc:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            active_trace["embed_calls"].append(
                {"label": label, "ms": dt_ms, "tokens": 0, "chars": 0, "error": str(exc)}
            )
            raise
        dt_ms = (time.perf_counter() - t0) * 1000.0
        emb = resp.embeddings[0]
        tok = float(getattr(getattr(emb, "statistics", None), "token_count", 0.0) or 0.0)
        chars = int(getattr(getattr(resp, "metadata", None), "billable_character_count", 0) or 0)
        active_trace["embed_calls"].append(
            {"label": label, "ms": dt_ms, "tokens": int(round(tok)), "chars": chars}
        )
        return resp

    def wrapped_gen(self, *args, **kwargs):
        t0 = time.perf_counter()
        model_name = kwargs.get("model") if "model" in kwargs else (args[0] if args else "")
        role = "hyde" if active_trace.get("in_search") else "answer"
        try:
            resp = orig_gen(self, *args, **kwargs)
        except Exception as exc:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            active_trace["gen_calls"].append(
                {"role": role, "model": str(model_name), "ms": dt_ms, "error": str(exc)}
            )
            raise
        dt_ms = (time.perf_counter() - t0) * 1000.0
        usage = _extract_usage_dict(getattr(resp, "usage_metadata", None))
        active_trace["gen_calls"].append(
            {"role": role, "model": str(model_name), "ms": dt_ms, **usage}
        )
        return resp

    UpgradedRetriever.search = wrapped_search
    Models.embed_content = wrapped_embed
    Models.generate_content = wrapped_gen

    def attempt_once(item):
        live_ret.query_vec_cache.clear()
        live_ret.hyde_vec_cache.clear()
        live_ret._dense_rank_cache.clear()
        active_trace.clear()
        active_trace["embed_calls"] = []
        active_trace["gen_calls"] = []
        active_trace["retrieval_ms"] = 0.0
        active_trace["in_search"] = False

        t0 = time.perf_counter()
        out = ans_mod.answer_with_details(item["question"], live_ret, k=DEFAULT_K)
        e2e_ms = (time.perf_counter() - t0) * 1000.0

        retrieval_ms = active_trace["retrieval_ms"]
        generation_stage_ms = e2e_ms - retrieval_ms

        if live_ret.last_used_fallback:
            return None, {
                "question": item["question"],
                "e2e_ms": round(e2e_ms, 2),
                "retrieval_ms": round(retrieval_ms, 2),
                "generation_stage_ms": round(generation_stage_ms, 2),
                "embed_calls": active_trace["embed_calls"],
                "gen_calls": active_trace["gen_calls"],
            }

        ok_q_embs = [
            c["ms"]
            for c in active_trace["embed_calls"]
            if c["label"] == "query_embed" and not c.get("error")
        ]
        ok_h_embs = [
            c["ms"]
            for c in active_trace["embed_calls"]
            if c["label"] == "hyde_embed" and not c.get("error")
        ]
        query_embed_ms = ok_q_embs[-1] if ok_q_embs else 0.0
        hyde_embed_ms = ok_h_embs[-1] if ok_h_embs else 0.0
        hyde_gen_ms = sum(c["ms"] for c in active_trace["gen_calls"] if c["role"] == "hyde")
        answer_gen_ms = sum(c["ms"] for c in active_trace["gen_calls"] if c["role"] == "answer")
        local_rrf_ms = retrieval_ms - (
            sum(c["ms"] for c in active_trace["embed_calls"]) + hyde_gen_ms
        )

        costs = _usd_cost_for_trace(active_trace)
        return {
            "question": item["question"],
            "answerable": item.get("answerable", True),
            "regenerated": out["regenerated"],
            "e2e_ms": round(e2e_ms, 2),
            "retrieval_ms": round(retrieval_ms, 2),
            "generation_stage_ms": round(generation_stage_ms, 2),
            "query_embed_ms": round(query_embed_ms, 2),
            "hyde_gen_ms": round(hyde_gen_ms, 2),
            "hyde_embed_ms": round(hyde_embed_ms, 2),
            "local_rrf_ms": round(local_rrf_ms, 2),
            "answer_gen_api_ms": round(answer_gen_ms, 2),
            "num_answer_gen_calls": sum(
                1 for c in active_trace["gen_calls"] if c["role"] == "answer"
            ),
            "gen_calls": active_trace["gen_calls"],
            "embed_calls": active_trace["embed_calls"],
            "costs": costs,
        }, None

    records = []
    fallback_events = []
    warmup_record = None
    try:
        warmup_record, warmup_fb = attempt_once(warmup_item)
        if warmup_fb is not None:
            fallback_events.append({"phase": "warmup", **warmup_fb})
            time.sleep(3)
            warmup_record, _ = attempt_once(warmup_item)
        if warmup_record:
            print(
                f"[Warmup] e2e={warmup_record['e2e_ms']:.1f}ms retrieval={warmup_record['retrieval_ms']:.1f}ms",
                flush=True,
            )

        for idx, item in enumerate(eval_items, start=1):
            rec, fb = attempt_once(item)
            if fb is not None:
                fallback_events.append({"query_idx": idx, "attempt": 1, **fb})
                print(
                    f"[{idx:02d}/{len(eval_items)}] transient API fallback recorded "
                    f"(ret={fb['retrieval_ms']:.1f}ms), retrying live measurement once...",
                    flush=True,
                )
                time.sleep(3)
                rec, fb2 = attempt_once(item)
                if fb2 is not None:
                    fallback_events.append({"query_idx": idx, "attempt": 2, **fb2})
                    print(
                        f"[{idx:02d}/{len(eval_items)}] retry also fell back; skipping live API sample.",
                        flush=True,
                    )
                    _save_payload(
                        simplicity,
                        _build_live_summary(records, warmup_record, fallback_events),
                    )
                    continue

            records.append(rec)
            err_note = ""
            n_errs = sum(1 for c in rec["gen_calls"] + rec["embed_calls"] if c.get("error"))
            if n_errs:
                err_note = f" [retries={n_errs}]"
            print(
                f"[{idx:02d}/{len(eval_items)}] e2e={rec['e2e_ms']:.1f}ms "
                f"(ret={rec['retrieval_ms']:.1f}ms: q_emb={rec['query_embed_ms']:.1f} "
                f"hyde={rec['hyde_gen_ms']:.1f} h_emb={rec['hyde_embed_ms']:.1f} "
                f"rrf={rec['local_rrf_ms']:.1f} | gen={rec['generation_stage_ms']:.1f}ms) | "
                f"tok=(emb={rec['costs']['embed_tokens']}, "
                f"hyde={rec['costs']['hyde_prompt_tokens']}/{rec['costs']['hyde_output_plus_thoughts_tokens']}, "
                f"argon={rec['costs']['argon_prompt_tokens']}/{rec['costs']['argon_output_plus_thoughts_tokens']}){err_note}",
                flush=True,
            )
            _save_payload(
                simplicity,
                _build_live_summary(records, warmup_record, fallback_events),
            )
    finally:
        UpgradedRetriever.search = orig_search
        Models.embed_content = orig_embed
        Models.generate_content = orig_gen

    return _build_live_summary(records, warmup_record, fallback_events)


def main():
    dev_items = answerable(load_jsonl(SYNTHETIC_EVAL_PATH))
    gold_items = answerable(load_jsonl(GOLDEN_PATH))
    base_ret = build_pipeline(mode="upgraded")

    print("=== Part A: McNemar simplicity check (1:0:0:0 vs 8:0:1:0 vs 8:2:1:1) ===", flush=True)
    simplicity = run_mcnemar_simplicity_check(base_ret, dev_items, gold_items)
    for ds_name in ("dev", "golden"):
        print(f"\n[{ds_name}] Metrics:", flush=True)
        for cfg_name, m in simplicity["metrics"][ds_name].items():
            print(
                f"  {cfg_name}: hit@1={m['hit@1']:.2%} ({m['hit@1_count']}/{m['n']}), "
                f"hit@3={m['hit@3']:.2%} ({m['hit@3_count']}/{m['n']}), "
                f"hit@5={m['hit@5']:.2%} ({m['hit@5_count']}/{m['n']}), "
                f"hit@10={m['hit@10']:.2%} ({m['hit@10_count']}/{m['n']}), MRR={m['MRR']:.4f}",
                flush=True,
            )
        print(f"[{ds_name}] McNemar pairwise:", flush=True)
        for pair_key, by_k in simplicity["mcnemar"][ds_name].items():
            parts = []
            for k_str in ("hit@1", "hit@5", "hit@10"):
                r = by_k[k_str]
                parts.append(f"{k_str}: {r['a_only']} vs {r['b_only']} (p={r['p_value']:.4f})")
            print(f"  {pair_key}: " + " | ".join(parts), flush=True)

    _save_payload(simplicity, None)

    print("\n=== Part B: Live uncached latency & cost per query (n=20 golden answerable) ===", flush=True)
    warmup_item = dev_items[0]
    eval_items = gold_items[:20]
    live_stats = measure_live_latency_and_cost(base_ret, warmup_item, eval_items, simplicity)

    print("\n=== Summary Latency (ms) ===", flush=True)
    for k_name, s in live_stats["latency_summary_ms"].items():
        print(
            f"  {k_name}: median={s['median']:.1f}ms, p95={s['p95']:.1f}ms, "
            f"mean={s['mean']:.1f}ms, range=[{s['min']:.1f}, {s['max']:.1f}] (n={s['n']})",
            flush=True,
        )
    print("\n=== Summary Cost (USD / query) ===", flush=True)
    for k_name, c in live_stats["cost_summary_usd"].items():
        print(
            f"  {k_name}: mean=${c['mean_usd']:.6f}, median=${c['median_usd']:.6f}, total=${c['total_usd']:.6f}",
            flush=True,
        )
    print(f"\nFallback events observed: {live_stats['fallback_events_count']}", flush=True)
    print(f"Saved P4 results to {OUT_JSON_PATH}", flush=True)


if __name__ == "__main__":
    main()
