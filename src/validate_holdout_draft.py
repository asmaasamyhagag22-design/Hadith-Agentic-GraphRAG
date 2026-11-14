"""
Structural validation of `data/raw/holdout_draft.jsonl` (no API calls, no retrieval).

The holdout is NOT used by any experiment. This script only checks that the
draft is well-formed so it can go to manual review:

1. exactly 120 rows: 75 single_hadith + 30 sibling_hadiths + 15 out_of_scope_refusal
2. questions are unique and disjoint from golden.jsonl and synthetic_eval.jsonl
3. every answerable row has hadith_ids that exist in the corpus and a non-empty
   candidate_gold_ids list that contains its hadith_ids
4. answerable source hadiths are disjoint from golden / synthetic gold ids
5. every refusal row has probe terms and passes `validate_golden.check_item`
   (probe_terms absent from the whole corpus; probe_terms_together never
   co-occur in one hadith), re-checked here independently
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import GOLDEN_PATH, RAW_DIR, SYNTHETIC_EVAL_PATH
from validate_golden import check_item, load_corpus_text, normalize

HOLDOUT_DRAFT_PATH = RAW_DIR / "holdout_draft.jsonl"
EXPECTED = {"single_hadith": 75, "sibling_hadiths": 30, "out_of_scope_refusal": 15}


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def validate(rows, corpus, all_text, golden, synth):
    problems = []
    counts = Counter(r.get("category") for r in rows)
    if len(rows) != 120:
        problems.append(f"expected 120 rows, got {len(rows)}")
    if dict(counts) != EXPECTED:
        problems.append(f"category counts {dict(counts)} != {EXPECTED}")

    questions = [r["question"] for r in rows]
    if len(set(questions)) != len(questions):
        problems.append("duplicate questions in draft")
    used_q = {i["question"] for i in golden + synth}
    overlap = [q for q in questions if q in used_q]
    if overlap:
        problems.append(f"{len(overlap)} questions also in golden/synthetic")

    used_ids = {h for i in golden + synth for h in i.get("hadith_ids", [])}
    for r in rows:
        q = r["question"][:50]
        if r.get("answerable"):
            hids = r.get("hadith_ids") or []
            cands = r.get("candidate_gold_ids") or []
            if not hids:
                problems.append(f"no hadith_ids: {q}")
            if not cands:
                problems.append(f"empty candidate_gold_ids: {q}")
            if not set(hids) <= set(cands):
                problems.append(f"hadith_ids not in candidate_gold_ids: {q}")
            missing = [h for h in hids + cands if h not in corpus]
            if missing:
                problems.append(f"ids not in corpus {missing}: {q}")
            if set(hids) & used_ids:
                problems.append(f"source hadith reused from golden/synthetic: {q}")
        else:
            if r.get("hadith_ids") or r.get("candidate_gold_ids"):
                problems.append(f"refusal row has ids: {q}")
            if not (r.get("probe_terms") or r.get("probe_terms_together")):
                problems.append(f"refusal row has no probe terms: {q}")
            _, item_problems = check_item(r, corpus, all_text)
            problems.extend(f"{q}: {p}" for p in item_problems)
            for term in r.get("probe_terms", []):
                if normalize(term) in all_text:
                    problems.append(f"{q}: probe term '{term}' found in corpus")
            together = [normalize(t) for t in r.get("probe_terms_together", [])]
            if together and any(all(t in text for t in together) for text in corpus.values()):
                problems.append(f"{q}: probe_terms_together co-occur in a hadith")
    return problems, counts


def main():
    rows = load_jsonl(HOLDOUT_DRAFT_PATH)
    corpus = load_corpus_text()
    all_text = "\n".join(corpus.values())
    problems, counts = validate(
        rows, corpus, all_text, load_jsonl(GOLDEN_PATH), load_jsonl(SYNTHETIC_EVAL_PATH)
    )
    sizes = [len(r["candidate_gold_ids"]) for r in rows if r.get("answerable")]
    print(f"rows={len(rows)} categories={dict(counts)}")
    print(
        f"candidate_gold_ids per answerable row: min={min(sizes)} "
        f"max={max(sizes)} mean={sum(sizes) / len(sizes):.1f}"
    )
    if problems:
        print(f"FAILED ({len(problems)} problems)")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("OK — holdout draft is structurally valid")


if __name__ == "__main__":
    main()
