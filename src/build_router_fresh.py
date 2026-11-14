"""Generate a fresh unseen 30-question Arabic chain-intent set using Gemma 4.

Uses ``gemma-4-26b-a4b-it-maas`` (NOT Gemini) to generate 30 varied, natural
chain-intent questions grounded in distinct Sahih Muslim hadiths and narrators
from ``sanad_graph.sqlite`` that are disjoint from ``golden.jsonl``,
``synthetic_eval.jsonl``, and ``chain_eval.jsonl``.

Writes ``data/raw/router_fresh.jsonl`` and prints its SHA-256 without importing
or consulting ``src.router`` so the fresh set stays strictly uncontaminated.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from config import GOLDEN_PATH, PROCESSED_DIR, RAW_DIR, SYNTHETIC_EVAL_PATH
from embed import indexable_chunks, load_chunks
from sanad_context import LINKED_WITH_RECORDED_ISNAD, context_for_local_hadith, open_graph
from sanad_graph import GRAPH_DB_PATH
from utils import split_isnad_matn, strip_diacritics

ROUTER_FRESH_PATH = RAW_DIR / "router_fresh.jsonl"
CHAIN_EVAL_PATH = RAW_DIR / "chain_eval.jsonl"
GEMMA_MODEL = "gemma-4-26b-a4b-it-maas"
GEMMA_LOCATION = "global"
SEED = 20261115

_ARABIC_RE = re.compile(r"[\u0621-\u064a]{2,}")

_PROMPTS: dict[str, str] = {
    "who_narrated_companion": """أنت عالم حديث تصوغ أسئلة بحثية طبيعية ومتنوعة باللغة العربية لمستخدم يسأل عن **الصحابي الراوي** في صحيح مسلم.
لكل حديث أدناه (برقم الحديث واسم الباب)، اكتب سؤالاً واحداً يسأل عن الصحابي الذي روى ذلك الحديث، مع **تغيير الصياغة والأسلوب والأدوات الاستفهامية في كل سؤال** بصورة طبيعية (لا تكرّر القالب نفسه بين الأسئلة).

شروط:
1. يجب أن يتضمن كل سؤال رقم الحديث المعطى رقماً صريحاً كما هو.
2. لا تذكر اسم الصحابي نفسه في السؤال.
3. التنويع ضروري: غيّر التركيب النحوي وطريقة السؤال في جميع البنود الستة.
4. أخرج JSON فقط: {{"items": [{{"idx": 1, "question": "..."}}, ...]}}

البنود:
{items}""",
    "who_narrated_teacher": """أنت عالم حديث تصوغ أسئلة طبيعية ومتنوعة باللغة العربية لمستخدم يسأل عن **شيخ الإمام مسلم المباشر** (الراوي الذي روى عنه الإمام مسلم مباشرةً في سلسلة الإسناد).
لكل حديث أدناه، اكتب سؤالاً واحداً يسأل عن شيخ مسلم في هذا الحديث، مع **تغيير الصياغة والأسلوب في كل بند** (مرة بلفظ الشيخ، ومرة بالراوي المباشر، ومرة بسؤال عمّن سمع أو تلقّى أو أخذ عنه، وهكذا).

شروط:
1. يجب أن يتضمن كل سؤال رقم الحديث المعطى كما هو.
2. لا تذكر اسم الشيخ في السؤال.
3. أخرج JSON فقط: {{"items": [{{"idx": 1, "question": "..."}}, ...]}}

البنود:
{items}""",
    "isnad_count": """أنت عالم حديث تصوغ أسئلة طبيعية ومتنوعة باللغة العربية لمستخدم يسأل عن **عدد طرق الإسناد أو الأسانيد المسجلة** لحديث معين في صحيح مسلم.
لكل حديث أدناه، اكتب سؤالاً واحداً يسأل عن عدد الأسانيد أو الطرق، مع **تغيير الأسلوب والمفردات في كل سؤال** تنويعاً طبيعياً.

شروط:
1. يجب أن يتضمن كل سؤال رقم الحديث المعطى كما هو.
2. لا تذكر عدد الطرق نفسه.
3. أخرج JSON فقط: {{"items": [{{"idx": 1, "question": "..."}}, ...]}}

البنود:
{items}""",
    "narrator_in_chain": """أنت عالم حديث تصوغ أسئلة طبيعية ومتنوعة باللغة العربية لمستخدم يتحقق **هل ورد راوٍ معيّن ضمن رواة أو سند حديث محدد** في صحيح مسلم.
لكل بند أدناه (يحتوي رقم الحديث واسم الراوي المطلوب التحقق منه)، اكتب سؤالاً استفهامياً طبيعياً يسأل عمّا إذا كان هذا الراوي موجوداً في سند الحديث أو روى فيه.

شروط:
1. يجب أن يتضمن السؤال كلاً من رقم الحديث المعطى واسم الراوي المعطى.
2. نوّع الصياغات والأفعال (ورد، ظهر، شارك، موجود، ضمن، بين، عبر...) بين البنود الستة.
3. أخرج JSON فقط: {{"items": [{{"idx": 1, "question": "..."}}, ...]}}

البنود:
{items}""",
    "topic_who_narrated": """أنت عالم حديث تصوغ أسئلة طبيعية ومتنوعة باللغة العربية لمستخدم يسأل **عن رواة أو سند حديث معروف بموضوعه أو متنه دون أن يذكر رقم الحديث**.
لكل متن وباب أدناه، اكتب سؤالاً واحداً طبيعياً يسأل عن الصحابي الذي رواه أو عن رواته أو إسناده مع الإشارة الواضحة إلى موضوع الحديث (دون ذكر رقم الحديث إطلاقاً).

شروط:
1. يُمنع ذكر أي رقم للحديث.
2. اجعل الموضوع واضحاً ومحدداً بما يكفي للبحث عن الحديث ثم معرفة راويه أو إسناده.
3. نوّع الصياغات والأسلوب في جميع البنود الستة.
4. أخرج JSON فقط: {{"items": [{{"idx": 1, "question": "..."}}, ...]}}

البنود:
{items}""",
}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _norm_question(text: str) -> str:
    clean = strip_diacritics(text or "")
    clean = re.sub(r"[^\w\u0621-\u064a\s]+", " ", clean)
    return " ".join(clean.split())


def _used_ids_and_questions() -> tuple[set[int], set[str]]:
    used_hids: set[int] = set()
    used_qs: set[str] = set()
    for path in (GOLDEN_PATH, SYNTHETIC_EVAL_PATH, CHAIN_EVAL_PATH):
        for row in _load_jsonl(path):
            q = str(row.get("question", ""))
            if q:
                used_qs.add(_norm_question(q))
            for hid in row.get("hadith_ids") or []:
                used_hids.add(int(hid))
    return used_hids, used_qs


def _short_narrator_name(full_name: str) -> str:
    """Trim noisy suffixes like '/ بن ...' for natural Arabic phrasing."""
    parts = [p.strip() for p in full_name.split("/") if p.strip()]
    return parts[0] if parts else full_name.strip()


def _collect_candidates(used_hids: set[int]) -> list[dict[str, Any]]:
    raw_chunks = load_chunks(PROCESSED_DIR / "muslim_chunks.json")
    idx_chunks = indexable_chunks(raw_chunks)
    matn_by_hid: dict[int, tuple[str, str]] = {}
    for c in idx_chunks:
        cid = str(c["id"])
        if not cid.endswith("_0"):
            continue
        hid = int(c["metadata"]["hadith_number"])
        if hid in used_hids:
            continue
        matn = " ".join(split_isnad_matn(c["text"]).split())
        chapter = str(c["metadata"].get("chapter_arabic", "")).strip()
        if len(matn) >= 120:
            matn_by_hid[hid] = (chapter, matn)

    candidates: list[dict[str, Any]] = []
    outside_narrators: list[str] = []
    with open_graph(GRAPH_DB_PATH) as conn:
        for hid in sorted(matn_by_hid):
            ctx = context_for_local_hadith(conn, hid)
            if ctx.get("status") != LINKED_WITH_RECORDED_ISNAD or not ctx.get("isnads"):
                continue
            chain0 = ctx["isnads"][0].get("narrators") or []
            if len(chain0) < 3:
                continue
            narrators = [
                _short_narrator_name(str(step.get("name_ar_mapped") or step.get("name_ar") or ""))
                for step in chain0
                if not str(step.get("narrator_id", "")).startswith(("NM_", "_"))
            ]
            narrators = [n for n in narrators if len(n) >= 4]
            if len(narrators) < 2:
                continue
            chapter, matn = matn_by_hid[hid]
            candidates.append(
                {
                    "hadith_id": hid,
                    "chapter": chapter,
                    "matn": matn,
                    "isnad_count": int(ctx["isnad_count"]),
                    "narrators": narrators,
                }
            )
            outside_narrators.extend(narrators)

    return candidates


def _generate_batch(
    client: genai.Client,
    qtype: str,
    batch: list[dict[str, Any]],
    used_qs: set[str],
) -> list[dict[str, Any]]:
    lines = []
    for i, item in enumerate(batch, start=1):
        if qtype == "narrator_in_chain":
            lines.append(
                f"{i}. رقم الحديث: {item['hadith_id']} | الباب: {item['chapter']} | الراوي المطلوب: {item['query_narrator']}"
            )
        elif qtype == "topic_who_narrated":
            snippet = strip_diacritics(item["matn"])[:260]
            lines.append(f"{i}. الباب: {item['chapter']} | مضمون المتن: {snippet}")
        else:
            lines.append(f"{i}. رقم الحديث: {item['hadith_id']} | الباب: {item['chapter']}")

    prompt = _PROMPTS[qtype].format(items="\n".join(lines))
    for attempt in range(4):
        resp = client.models.generate_content(
            model=GEMMA_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                response_mime_type="application/json",
            ),
        )
        raw = (resp.text or "{}").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        data = json.loads(raw)
        by_idx: dict[int, str] = {}
        for row in data.get("items", []):
            if isinstance(row, dict) and isinstance(row.get("idx"), int):
                by_idx[row["idx"]] = str(row.get("question", "")).strip()

        results = []
        ok = True
        for i, item in enumerate(batch, start=1):
            q = by_idx.get(i, "")
            norm_q = _norm_question(q)
            if len(q) < 12 or not _ARABIC_RE.search(q) or norm_q in used_qs:
                ok = False
                break
            if qtype != "topic_who_narrated" and str(item["hadith_id"]) not in q:
                ok = False
                break
            if qtype == "topic_who_narrated" and str(item["hadith_id"]) in q:
                ok = False
                break
            used_qs.add(norm_q)
            results.append(
                {
                    "type": qtype,
                    "question": q,
                    "hadith_ids": [item["hadith_id"]],
                    "query_narrator": item.get("query_narrator"),
                    "chapter": item["chapter"],
                    "generator_model": GEMMA_MODEL,
                    "expected_intent": "chain",
                }
            )
        if ok and len(results) == len(batch):
            return results
    raise RuntimeError(f"Failed to generate valid batch for {qtype!r} after retries")


def main() -> None:
    used_hids, used_qs = _used_ids_and_questions()
    candidates = _collect_candidates(used_hids)
    rng = random.Random(SEED)
    rng.shuffle(candidates)

    # Spread across different chapters for diversity.
    chosen: list[dict[str, Any]] = []
    seen_chapters: set[str] = set()
    for c in candidates:
        if c["chapter"] not in seen_chapters or len(chosen) >= 24:
            seen_chapters.add(c["chapter"])
            chosen.append(c)
        if len(chosen) == 30:
            break

    if len(chosen) < 30:
        raise RuntimeError(f"Only found {len(chosen)} eligible candidates")

    qtypes = [
        "who_narrated_companion",
        "who_narrated_teacher",
        "isnad_count",
        "narrator_in_chain",
        "topic_who_narrated",
    ]
    client = genai.Client(location=GEMMA_LOCATION)
    all_rows: list[dict[str, Any]] = []
    all_narrator_pool = sorted({n for c in chosen for n in c["narrators"]})

    idx_counter = 1
    for t_idx, qtype in enumerate(qtypes):
        batch = chosen[t_idx * 6 : (t_idx + 1) * 6]
        if qtype == "narrator_in_chain":
            for j, item in enumerate(batch):
                if j < 4:
                    # Pick an interior/middle narrator where available.
                    mid = item["narrators"][min(1, len(item["narrators"]) - 1)]
                    item["query_narrator"] = mid
                else:
                    outside = [n for n in all_narrator_pool if n not in item["narrators"]]
                    item["query_narrator"] = outside[j % len(outside)]
        generated = _generate_batch(client, qtype, batch, used_qs)
        for row in generated:
            row["id"] = f"router_fresh_{idx_counter:02d}"
            idx_counter += 1
            all_rows.append(row)

    ROUTER_FRESH_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ROUTER_FRESH_PATH.open("w", encoding="utf-8") as fh:
        for row in all_rows:
            ordered = {
                "id": row["id"],
                "type": row["type"],
                "question": row["question"],
                "hadith_ids": row["hadith_ids"],
                "query_narrator": row["query_narrator"],
                "chapter": row["chapter"],
                "generator_model": row["generator_model"],
                "expected_intent": row["expected_intent"],
            }
            fh.write(json.dumps(ordered, ensure_ascii=False) + "\n")

    digest = hashlib.sha256(ROUTER_FRESH_PATH.read_bytes()).hexdigest()
    print(f"Generated {len(all_rows)} fresh chain questions with {GEMMA_MODEL}")
    print(f"Path: {ROUTER_FRESH_PATH}")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    main()
