"""
E0 — Equivalent-matn gold expansion.

Deterministic rule: a hadith counts as gold if its normalised matn (using the
same normalisation as the index) is identical to the normalised matn of a
listed gold hadith.

Produces derived evaluation files under data/processed/ without touching
data/raw/golden.jsonl or data/raw/synthetic_eval.jsonl, and measures baseline
retrieval metrics (hit@1, hit@3, hit@5, hit@10, hit@50/recall@50, MRR) before
and after expansion.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_docs import canonical_hash
from config import GOLDEN_PATH, PROCESSED_DIR, SYNTHETIC_EVAL_PATH
from embed import indexable_chunks, load_chunks
from evaluate import answerable, build_retrievers, evaluate, load_golden
from experiment_variants import variant_text
from lexical import tokenize
from rerank import DEFAULT_MODEL
from utils import strip_diacritics

GOLDEN_EXPANDED_PATH = PROCESSED_DIR / "golden_expanded.jsonl"
SYNTHETIC_EXPANDED_PATH = PROCESSED_DIR / "synthetic_eval_expanded.jsonl"

K_VALUES_E0 = (1, 3, 5, 10, 50)


def normalise_dense_matn(chunk):
    """Exact normalisation used when building the dense matn index."""
    return " ".join(strip_diacritics(variant_text(chunk, "matn")).split())


def normalise_lexical_matn(chunk):
    """Exact token normalisation used when building the BM25 matn index."""
    return " ".join(tokenize(variant_text(chunk, "matn")))


def build_equivalence_maps(chunks):
    dense_groups = {}
    lexical_groups = {}
    hadith_to_dense = {}
    hadith_to_lexical = {}

    for chunk in chunks:
        hid = chunk["metadata"]["hadith_number"]
        d_key = normalise_dense_matn(chunk)
        l_key = normalise_lexical_matn(chunk)

        if d_key:
            dense_groups.setdefault(d_key, set()).add(hid)
            hadith_to_dense.setdefault(hid, set()).add(d_key)
        if l_key:
            lexical_groups.setdefault(l_key, set()).add(hid)
            hadith_to_lexical.setdefault(hid, set()).add(l_key)

    return dense_groups, lexical_groups, hadith_to_dense, hadith_to_lexical


def expand_dataset(items, dense_groups, lexical_groups, hadith_to_dense, hadith_to_lexical):
    expanded_items = []
    changed_dense = 0
    changed_union = 0

    for item in items:
        row = dict(item)
        orig_ids = list(item.get("hadith_ids", []))
        orig_set = set(orig_ids)

        dense_eq = set(orig_set)
        union_eq = set(orig_set)

        for hid in orig_ids:
            for d_key in hadith_to_dense.get(hid, ()):
                dense_eq |= dense_groups.get(d_key, set())
                union_eq |= dense_groups.get(d_key, set())
            for l_key in hadith_to_lexical.get(hid, ()):
                union_eq |= lexical_groups.get(l_key, set())

        if dense_eq != orig_set:
            changed_dense += 1
        if union_eq != orig_set:
            changed_union += 1

        row["hadith_ids"] = sorted(union_eq) if union_eq != orig_set else orig_ids
        expanded_items.append(row)

    return expanded_items, changed_dense, changed_union


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def evaluate_with_recall50(retriever, golden_items):
    hits, mrr, ranks = evaluate(retriever, golden_items, k_values=K_VALUES_E0)
    # Also compute macro set-recall@50 across multi-gold items
    recalls_50 = []
    for item in golden_items:
        expected = set(item["hadith_ids"])
        results = retriever.search(item["question"], k=50)
        found = {r["hadith_id"] for r in results} & expected
        recalls_50.append(len(found) / len(expected) if expected else 0.0)
    set_recall_50 = sum(recalls_50) / len(recalls_50)
    return hits, mrr, set_recall_50, ranks


def main():
    all_chunks = load_chunks()
    idx_chunks = indexable_chunks(all_chunks)

    dense_groups, lexical_groups, h_dense, h_lex = build_equivalence_maps(idx_chunks)

    multi_dense = {k: sorted(v) for k, v in dense_groups.items() if len(v) > 1}
    multi_lexical = {k: sorted(v) for k, v in lexical_groups.items() if len(v) > 1}

    print(f"Indexable chunks: {len(idx_chunks)}")
    print(f"Equivalent-matn groups (>1 hadith_id) under dense norm  : {len(multi_dense)}")
    print(f"Equivalent-matn groups (>1 hadith_id) under BM25 norm   : {len(multi_lexical)}")

    golden_orig = load_golden(GOLDEN_PATH)
    synth_orig = load_golden(SYNTHETIC_EVAL_PATH)

    golden_exp, g_changed_dense, g_changed_union = expand_dataset(
        golden_orig, dense_groups, lexical_groups, h_dense, h_lex
    )
    synth_exp, s_changed_dense, s_changed_union = expand_dataset(
        synth_orig, dense_groups, lexical_groups, h_dense, h_lex
    )

    write_jsonl(GOLDEN_EXPANDED_PATH, golden_exp)
    write_jsonl(SYNTHETIC_EXPANDED_PATH, synth_exp)

    print(f"\ngolden.jsonl         changed (dense={g_changed_dense}, union={g_changed_union}) -> {GOLDEN_EXPANDED_PATH.name} (hash `{canonical_hash(GOLDEN_EXPANDED_PATH)}`)")
    print(f"synthetic_eval.jsonl changed (dense={s_changed_dense}, union={s_changed_union}) -> {SYNTHETIC_EXPANDED_PATH.name} (hash `{canonical_hash(SYNTHETIC_EXPANDED_PATH)}`)")

    retrievers = dict(build_retrievers([DEFAULT_MODEL]))
    wanted = [
        "Dense: matn only",
        "BM25: matn only",
        "Hybrid: dense + BM25",
        f"Hybrid + {DEFAULT_MODEL.split('/')[-1]}",
    ]

    for ds_label, items in [
        ("golden (n=27)", answerable(golden_exp)),
        ("synthetic_eval (n=224)", answerable(synth_exp)),
    ]:
        print(f"\n=== {ds_label} ===")
        print(f"{'Retriever':<38} {'hit@1':<8} {'hit@3':<8} {'hit@5':<8} {'hit@10':<8} {'hit@50':<8} {'setR@50':<8} {'MRR@10':<8}")
        print("-" * 102)
        for name in wanted:
            ret = retrievers[name]
            hits10, mrr10, _ = evaluate(ret, items, k_values=(1, 3, 5, 10))
            hits50, mrr50, set_r50, _ = evaluate_with_recall50(ret, items)
            print(
                f"{name:<38} "
                f"{hits10[1]:<8.1%} {hits10[3]:<8.1%} {hits10[5]:<8.1%} "
                f"{hits10[10]:<8.1%} {hits50[50]:<8.1%} {set_r50:<8.1%} {mrr10:<8.3f}"
            )


if __name__ == "__main__":
    main()
