"""
Build `data/raw/holdout_draft.jsonl` — 120 new paraphrased MSA holdout questions
for manual verification (NOT used in any experiment).

Composition (120 questions total):
- 75 paraphrased MSA single-hadith questions (disjoint from golden.jsonl and synthetic_eval.jsonl)
- 30 paraphrased MSA multi-hadith sibling questions (hadith clusters sharing the same Prophetic matn)
- 15 out-of-scope refusal questions (verified absent from all 7,459 hadiths in muslim.json via probe_terms / probe_terms_together)

Every answerable question includes `candidate_gold_ids` discovered via matn search
(combining normalized matn signature search, BM25 matn search, and dense `gemini-embedding-001`
matn search), plus `hadith_ids`, `matn` snippet, and `verified: false`.
"""

import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_eval_set import (
    _FOREIGN_SCRIPT,
    content_tokens,
    lexical_overlap,
    matn_signature,
)
from check_docs import canonical_hash
from config import GOLDEN_PATH, PROCESSED_DIR, RAW_DIR, SYNTHETIC_EVAL_PATH
from embed import indexable_chunks, load_chunks
from embed_vertex_e1 import embed_batches, l2_norm
from experiment_variants import variant_text
from lexical import BM25Index, tokenize
from retrieve import load_chunk_lookup
from utils import split_isnad_matn, strip_diacritics
from validate_golden import check_item, load_corpus_text, normalize

HOLDOUT_DRAFT_PATH = RAW_DIR / "holdout_draft.jsonl"
HOLDOUT_META_PATH = PROCESSED_DIR / "holdout_draft_meta.json"
SEED = 20261113
DRAFT_MODEL = "gemini-2.5-flash"

DRAFT_PROMPT = """أنت تكتب مسودة أسئلة معيارية (Holdout Set) لتقييم باحث في صحيح مسلم.
لكل متن حديث مرقّم أدناه، اكتب سؤالاً واحداً باللغة العربية الفصحى المعاصرة (MSA) المصاغة بأسلوب القارئ المعاصر، بحيث تكون إجابته في هذا المتن.

شروط صارمة:
1. أعد صياغة المعنى بمفردات عربية فصحى معاصرة (Paraphrased MSA) ولا تنسخ عبارات المتن التراثية حرفياً.
2. اجعل السؤال محدداً وواضح الموضوع بذاته (اذكر الباب أو الموضوع الشرعي صراحةً دون ضمائر مبهمة).
3. لا تذكر رقم الحديث ولا كلمة "الحديث" ولا "المتن" ولا أسماء الرواة.

أخرج JSON فقط بالصيغة التالية:
{"questions": [{"idx": 1, "question": "..."}, ...]}

المتون:
{docs}"""


OUT_OF_SCOPE_CANDIDATES = [
    {
        "question": "ما هو دعاء القنوت في صلاة الوتر الذي علّمه النبي للحسن بن علي؟",
        "probe_terms_together": ["القنوت", "الوتر"],
        "note": "حديث دعاء القنوت في الوتر (اللهم اهدني فيمن هديت) في السنن وليس في صحيح مسلم؛ لا تجتمع لفظتا القنوت والوتر في أي حديث في مسلم.",
    },
    {
        "question": "ما حكم إخراج زكاة عروض التجارة وما نصابها في السنة؟",
        "probe_terms_together": ["عروض", "التجارة"],
        "note": "مصطلح عروض التجارة لا يرد في متون صحيح مسلم.",
    },
    {
        "question": "ما هو الدعاء المأثور عند رؤية الهلال في أول الشهر؟",
        "probe_terms_together": ["اللهم", "أهله", "بالأمن"],
        "note": "حديث دعاء رؤية الهلال (اللهم أهله علينا بالأمن والإيمان) في الترمذي والدارمي ولا وجود له في صحيح مسلم.",
    },
    {
        "question": "ما حكم سجود الشكر عند تجدد النعم أو اندفاع النقم؟",
        "probe_terms_together": ["سجود", "الشكر"],
        "note": "سجود الشكر وارد في السنن ولا يرد في صحيح مسلم.",
    },
    {
        "question": "ما هي شروط صحة عقد المضاربة وتوزيع الربح بين رب المال والمضارب؟",
        "probe_terms": ["المضاربة"],
        "note": "لفظ المضاربة غير وارد في صحيح مسلم.",
    },
    {
        "question": "ما هو فضل صيام الأيام البيض بالتسمية الصريحة (الأيام البيض) في الحديث؟",
        "probe_terms_together": ["الأيام", "البيض"],
        "note": "تسمية «الأيام البيض» واردة في السنن ولا تجتمع هاتان اللفظتان في صحيح مسلم.",
    },
    {
        "question": "ما هو كفارة المجلس التي تُقال عند القيام من المجلس؟",
        "probe_terms_together": ["سبحانك", "أستغفرك", "المجلس"],
        "note": "حديث كفارة المجلس في السنن والترمذي وليس في صحيح مسلم.",
    },
    {
        "question": "ما حكم صلاة التسابيح وكيفيتها في السنة النبوية؟",
        "probe_terms": ["التسابيح"],
        "note": "حديث صلاة التسابيح في السنن ولا وجود للفظ التسابيح في صحيح مسلم.",
    },
    {
        "question": "ما هو الدعاء الوارد عند لبس الثوب الجديد؟",
        "probe_terms_together": ["الحمد", "كساني", "الثوب"],
        "note": "دعاء لبس الثوب الجديد (الحمد لله الذي كساني هذا الثوب) في السنن وليس في صحيح مسلم.",
    },
    {
        "question": "ما حكم الجمع بين الصلاتين بسبب البرد الشديد أو الجليد؟",
        "probe_terms": ["الجليد"],
        "note": "لفظ الجليد غير وارد في صحيح مسلم.",
    },
    {
        "question": "ما هو نص دعاء الاستفتاح «سبحانك اللهم وبحمدك وتبارك اسمك وتعالى جدك»؟",
        "probe_terms_together": ["وتبارك", "اسمك", "وتعالى", "جدك"],
        "note": "في صحيح مسلم يرد ذلك من قول عمر رضي الله عنه موقوفاً بصيغة أخرى، ولا تجتمع هذه الألفاظ الأربعة في حديث واحد في مسلم.",
    },
    {
        "question": "ما حكم بيع العربون في المعاملات المالية؟",
        "probe_terms": ["العربون"],
        "note": "حديث بيع العربون في السنن وموطأ مالك، ولفظ العربون غائب تماماً عن صحيح مسلم.",
    },
    {
        "question": "ما حكم زكاة الحلي المعدّ للاستعمال الشخصي للمرأة؟",
        "probe_terms_together": ["زكاة", "الحلي"],
        "note": "لا تجتمع لفظتا زكاة والحلي في أي حديث في صحيح مسلم.",
    },
    {
        "question": "ما هو فضل قراءة سورة الملك قبل النوم للوقاية من عذاب القبر؟",
        "probe_terms_together": ["سورة", "الملك", "القبر"],
        "note": "حديث فضل سورة الملك للوقاية من عذاب القبر في السنن والمسند ولا يرد في صحيح مسلم.",
    },
    {
        "question": "ما حكم التورق المصرفي أو بيع التورق في الفقه النبوي؟",
        "probe_terms": ["التورق"],
        "note": "مصطلح التورق لا وجود له في صحيح مسلم.",
    },
]


def load_used_hadith_ids_and_questions():
    used_hids = set()
    used_qs = set()
    for path in (GOLDEN_PATH, SYNTHETIC_EVAL_PATH):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    used_qs.add(row["question"].strip())
                    for hid in row.get("hadith_ids", []):
                        used_hids.add(int(hid))
    return used_hids, used_qs


def find_sibling_clusters(idx_chunks, used_hids):
    """
    Find groups of 2..6 indexable hadiths (disjoint from used_hids) that share
    the same normalized 7-word matn signature (or identical normalized matn).
    """
    by_sig = defaultdict(list)
    matns = {}
    for c in idx_chunks:
        cid = str(c["id"])
        if not cid.endswith("_0"):
            continue
        hid = int(c["metadata"]["hadith_number"])
        matn = split_isnad_matn(c["text"])
        matns[hid] = (c, matn)
        toks = tokenize(matn)
        if len(toks) < 10 or not (100 <= len(matn) <= 850):
            continue
        sig = " ".join(toks[:7])
        by_sig[sig].append(hid)

    clusters = []
    for sig, hids in by_sig.items():
        unique_hids = sorted(set(hids))
        if 2 <= len(unique_hids) <= 6 and not (set(unique_hids) & used_hids):
            primary_hid = unique_hids[0]
            c, matn = matns[primary_hid]
            clusters.append((unique_hids, c, matn))

    return clusters


def find_single_candidates(idx_chunks, used_hids):
    by_sig = defaultdict(list)
    matns = {}
    for c in idx_chunks:
        cid = str(c["id"])
        if not cid.endswith("_0"):
            continue
        hid = int(c["metadata"]["hadith_number"])
        matn = split_isnad_matn(c["text"])
        matns[hid] = (c, matn)
        toks = tokenize(matn)
        if len(toks) < 10 or not (130 <= len(matn) <= 800):
            continue
        sig = " ".join(toks[:8])
        by_sig[sig].append(hid)

    singles = []
    for sig, hids in by_sig.items():
        if len(hids) == 1 and hids[0] not in used_hids:
            hid = hids[0]
            c, matn = matns[hid]
            singles.append(([hid], c, matn))
    return singles


def generate_questions_for_pool(client, pool, target_count):
    """
    Generate paraphrased MSA questions in batches of 15, filtering by lexical
    overlap <= 0.55, no foreign script, and >= 4 content tokens.
    """
    accepted = []
    api_calls = 0
    batch_size = 15

    for start in range(0, len(pool), batch_size):
        if len(accepted) >= target_count:
            break
        batch = pool[start : start + batch_size]
        docs_lines = []
        for i, (hids, chunk, matn) in enumerate(batch):
            chapter = strip_diacritics(
                chunk["metadata"].get("chapter_arabic", "")
            ).strip()
            clean_m = " ".join(strip_diacritics(matn).split())
            docs_lines.append(f"{i + 1}. [{chapter}] {clean_m}")

        prompt = DRAFT_PROMPT.replace("{docs}", "\n\n".join(docs_lines))
        parsed_qs = {}
        for attempt in range(4):
            try:
                resp = client.models.generate_content(
                    model=DRAFT_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )
                api_calls += 1
                data = json.loads(resp.text or "{}")
                for entry in data.get("questions", []):
                    if isinstance(entry, dict) and isinstance(entry.get("idx"), int):
                        parsed_qs[entry["idx"]] = str(entry.get("question", "")).strip()
                if parsed_qs:
                    break
            except Exception:
                time.sleep(2 * (attempt + 1))

        for i, (hids, chunk, matn) in enumerate(batch):
            if len(accepted) >= target_count:
                break
            q = parsed_qs.get(i + 1, "")
            if not q or "SKIP" in q.upper():
                continue
            if _FOREIGN_SCRIPT.search(q):
                continue
            if len(content_tokens(q)) < 4:
                continue
            ov = lexical_overlap(q, matn)
            if ov > 0.55:
                continue
            accepted.append((q, hids, chunk, matn, round(ov, 3)))

    return accepted, api_calls


def main():
    corpus = load_corpus_text()
    all_text = "\n".join(corpus.values())

    all_chunks = load_chunks()
    idx_chunks = indexable_chunks(all_chunks)
    chunk_ids = [str(c["id"]) for c in idx_chunks]
    chunk_lookup = load_chunk_lookup()

    used_hids, used_qs = load_used_hadith_ids_and_questions()
    rng = random.Random(SEED)

    sibling_pool = find_sibling_clusters(idx_chunks, used_hids)
    single_pool = find_single_candidates(idx_chunks, used_hids)
    rng.shuffle(sibling_pool)
    rng.shuffle(single_pool)
    print(
        f"Available pools (disjoint from golden & synthetic): "
        f"{len(single_pool)} single-hadith, {len(sibling_pool)} sibling clusters"
    )

    client = genai.Client()
    print("Generating 75 single-hadith paraphrased MSA questions...")
    single_accepted, calls_single = generate_questions_for_pool(
        client, single_pool, 75
    )
    print(
        f"  Got {len(single_accepted)}/75 single questions (calls={calls_single})"
    )

    print("Generating 30 sibling-cluster paraphrased MSA questions...")
    sibling_accepted, calls_sibling = generate_questions_for_pool(
        client, sibling_pool, 30
    )
    print(
        f"  Got {len(sibling_accepted)}/30 sibling questions (calls={calls_sibling})"
    )

    # Run matn search (BM25 + gemini-embedding-001 matn & expansion + signature match)
    # to populate `candidate_gold_ids` for all 105 answerable questions
    print("Running matn search (BM25 + gemini-embedding-001) to find candidate_gold_ids...")
    bm25_matn = BM25Index(
        chunk_ids, [variant_text(chunk_lookup[cid], "matn") for cid in chunk_ids]
    )
    g001_3072 = np.load(PROCESSED_DIR / "vectors_matn_gemini001_3072.npy")
    exp_v3072 = np.load(PROCESSED_DIR / "vectors_expansion_gemini001_3072.npy")

    ans_items = single_accepted + sibling_accepted
    ans_qs = [strip_diacritics(x[0]) for x in ans_items]
    q_vecs = l2_norm(
        embed_batches(client, "gemini-embedding-001", ans_qs, "RETRIEVAL_QUERY")
    )
    embed_calls = 1

    # Also build 6-word signature index across all 7,110 indexable chunks
    sig6_map = defaultdict(list)
    for c in idx_chunks:
        hid = int(c["metadata"]["hadith_number"])
        m_toks = tokenize(split_isnad_matn(c["text"]))
        if len(m_toks) >= 6:
            sig6_map[" ".join(m_toks[:6])].append(hid)

    rows = []

    for idx, (q, seed_hids, chunk, matn, ov) in enumerate(ans_items):
        category = "single_hadith" if idx < len(single_accepted) else "sibling_hadiths"
        qv = q_vecs[idx]
        scores_m = g001_3072 @ qv
        scores_e = exp_v3072 @ qv
        top_m_idx = np.argsort(-scores_m)[:15]
        top_e_idx = np.argsort(-scores_e)[:10]
        bm25_cids = bm25_matn.ranked_ids(q, k=10)

        # Combine seed_hids + signature matches + top matn search hits
        cand_hids = []
        for h in seed_hids:
            if h not in cand_hids:
                cand_hids.append(int(h))

        m_toks = tokenize(matn)
        if len(m_toks) >= 6:
            for sh in sig6_map.get(" ".join(m_toks[:6]), []):
                if sh not in cand_hids:
                    cand_hids.append(int(sh))

        for i_m in top_m_idx[:8]:
            hid_m = int(chunk_lookup[chunk_ids[int(i_m)]]["metadata"]["hadith_number"])
            if hid_m not in cand_hids:
                cand_hids.append(hid_m)
        for i_e in top_e_idx[:5]:
            hid_e = int(chunk_lookup[chunk_ids[int(i_e)]]["metadata"]["hadith_number"])
            if hid_e not in cand_hids:
                cand_hids.append(hid_e)
        for bcid in bm25_cids[:5]:
            hid_b = int(chunk_lookup[bcid]["metadata"]["hadith_number"])
            if hid_b not in cand_hids:
                cand_hids.append(hid_b)

        # Extract clean matn snippet whose first 5 normalized words appear in corpus[seed_hids[0]]
        clean_matn = " ".join(strip_diacritics(matn).split())
        snippet_words = clean_matn.split()[:14]
        snippet = " ".join(snippet_words)

        row = {
            "question": q,
            "type": "matn",
            "category": category,
            "answerable": True,
            "hadith_ids": sorted(set(int(h) for h in seed_hids)),
            "candidate_gold_ids": cand_hids[:12],
            "matn": snippet,
            "lexical_overlap": ov,
            "verified": False,
            "note": (
                f"مسودة ({category}) — candidate_gold_ids مستخرجة ببحث المتن "
                f"(توقيع المتن + gemini-embedding-001 + BM25) للمراجعة اليدوية."
            ),
        }
        _, problems = check_item(row, corpus, all_text)
        if problems:
            raise RuntimeError(f"Validation failed on draft row {q}: {problems}")
        rows.append(row)

    # Add 15 verified out-of-scope refusal questions
    for ref in OUT_OF_SCOPE_CANDIDATES:
        row = {
            "question": ref["question"],
            "type": "refusal",
            "category": "out_of_scope_refusal",
            "answerable": False,
            "hadith_ids": [],
            "candidate_gold_ids": [],
            "matn": "",
            "verified": False,
            "note": ref["note"],
        }
        if "probe_terms" in ref:
            row["probe_terms"] = ref["probe_terms"]
        if "probe_terms_together" in ref:
            row["probe_terms_together"] = ref["probe_terms_together"]

        _, problems = check_item(row, corpus, all_text)
        if problems:
            raise RuntimeError(f"Validation failed on refusal row {row['question']}: {problems}")
        rows.append(row)

    assert len(rows) == 120, f"Expected 120 rows, got {len(rows)}"

    HOLDOUT_DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HOLDOUT_DRAFT_PATH, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    digest = canonical_hash(HOLDOUT_DRAFT_PATH)
    meta = {
        "path": str(HOLDOUT_DRAFT_PATH),
        "total_questions": len(rows),
        "single_hadith_count": len(single_accepted),
        "sibling_hadiths_count": len(sibling_accepted),
        "out_of_scope_refusal_count": len(OUT_OF_SCOPE_CANDIDATES),
        "flash_api_calls": calls_single + calls_sibling,
        "embed_api_calls": embed_calls,
        "sha256": digest,
    }
    with open(HOLDOUT_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(
        f"Saved 120 holdout draft questions -> {HOLDOUT_DRAFT_PATH} (sha256 `{digest}`)"
    )
    print(f"Meta: {json.dumps(meta, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
