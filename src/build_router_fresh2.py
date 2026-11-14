"""Generate `data/raw/router_fresh2.jsonl` with Gemma 4 (30 chain + 30 hard-negative text).

Uses ``gemma-4-26b-a4b-it-maas`` (NOT Gemini) with prompts entirely distinct from
``build_router_fresh.py`` and Sahih Muslim hadith IDs disjoint from ``golden.jsonl``,
``synthetic_eval.jsonl``, ``chain_eval.jsonl``, and ``router_fresh.jsonl``.

Does NOT import ``src.router`` so ``router_fresh2.jsonl`` stays blind until Step 1e.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
import time
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
ROUTER_FRESH2_PATH = RAW_DIR / "router_fresh2.jsonl"
CHAIN_EVAL_PATH = RAW_DIR / "chain_eval.jsonl"
GEMMA_MODEL = "gemma-4-26b-a4b-it-maas"
GEMMA_LOCATION = "global"
SEED = 20261116

_ARABIC_RE = re.compile(r"[\u0621-\u064a]{2,}")

# Entirely distinct prompt phrasing from build_router_fresh.py.
_CHAIN_PROMPTS: dict[str, str] = {
    "who_narrated_companion": """تخيّل قارئاً عادياً يبحث في تطبيق حديثي ويريد التعرّف على **الصحابي الجليل الذي يقف عند أصل الحديث** لكل بند مرقّم أدناه.
صُغ استفساراً عربياً واضحاً ومباشراً لكل حديث يطلب اسم ذلك الصحابي فقط (لا تذكر اسم الصحابي نفسه، واذكر رقم الحديث كما ورد).
تجنّب التكرار اللفظي بين الأسئلة الستة واستعمل أساليب استفسار متجددة (مثل: أريد معرفة...، من نقل عن النبي...، إلى أي صحابي ينسب...، أخبرني باسم الصحابي...).

أعد JSON بهذه البنية دون غيرها:
{{"records": [{{"idx": 1, "q": "..."}}, ...]}}

القائمة:
{items}""",
    "who_narrated_teacher": """مستخدم مهتم بعلم الأسانيد يريد معرفة **الشيخ المباشر الذي أخذ عنه الإمام مسلم** (أعلى راوٍ في الإسناد قبل الإمام مسلم) في الأحاديث التالية.
لكل بند أدناه، أعدّ سؤالاً عربياً سلساً يسأل عن ذلك الشيخ/الأستاذ المباشر لمسلم، مع ذكر رقم الحديث المرفق وبدون كشف اسم الراوي.
اجعل صياغة كل سؤال مختلفة التركيب عن بقية المجموعة.

أعد JSON فقط:
{{"records": [{{"idx": 1, "q": "..."}}, ...]}}

القائمة:
{items}""",
    "isnad_count": """باحث في طرق الرواية يراجع عدد الأسانيد المتعددة والمخارج المسجّلة لكل حديث أدناه في صحيح مسلم.
اكتب عن كل بند سؤالاً طبيعياً يستفسر فيه عن **كثرة أو عدد الأسانيد والطرق والمخارج** المثبتة لذلك الحديث (مع إثبات رقم الحديث وعدم ذكر العدد).
غيّر التراكيب والمفردات بين جميع الأسئلة الستة.

أعد JSON فقط:
{{"records": [{{"idx": 1, "q": "..."}}, ...]}}

القائمة:
{items}""",
    "narrator_in_chain": """باحث يفحص سلاسل الإسناد للتحقق من **وجود أو مشاركة راوٍ محدّد** داخل سند الحديث المذكور.
لكل بند يحمل رقم حديث واسم راوٍ، صُغ سؤالاً استفهامياً طبيعياً يسأل إن كان هذا الراوي مذكوراً ضمن رواة أو سلسلة إسناد ذلك الحديث.
نوّع صيغ التحقق من سؤال لآخر وأدرج رقم الحديث واسم الراوي بدقة.

أعد JSON فقط:
{{"records": [{{"idx": 1, "q": "..."}}, ...]}}

القائمة:
{items}""",
    "topic_who_narrated": """سائل يذكر مضمون حديث أو موضوعه الشرعي دون أن يحفظ رقمه، ويرغب في معرفة **من رواه من الصحابة أو ما سلسلة إسناده**.
لكل موضوع ومتن مختصر أدناه، اكتب سؤالاً طبيعياً يشير إلى قصة الحديث أو حكمه ويسأل عن الصحابي الراوي له أو عن إسناده، مع الامتناع التام عن كتابة أي رقم حديث.
احرص على تنويع أساليب الطرح بين البنود الستة.

أعد JSON فقط:
{{"records": [{{"idx": 1, "q": "..."}}, ...]}}

القائمة:
{items}""",
}

_HARD_NEGATIVE_TEXT_PROMPT = """أنت تصمّم أسئلة اختبارية صعبة (Hard Negatives) لتمييز **أسئلة الفهم والمعنى والحكم الشرعي** عن أسئلة السند والرواة.
لكل حديث أدناه (مع ذكر اسم الصحابي/الراوي المرافق ومقتطف المتن)، اكتب سؤالاً يسأل عن **المضمون أو الحكم الفقهي أو المعنى أو الحدث النبوي في المتن**، ولكن **اذكر اسم ذلك الصحابي أو الراوي صراحةً داخل السؤال مع ألفاظ مثل (قال / روى / نقل / أخبر / عن / حكى)** — على أن يبقى مطلوب السؤال الحقيقي هو **الفقه أو المعنى أو الفعل** وليس اسم الراوي ولا الإسناد ولا عدد الطرق!

أمثلة توجيهية للأسلوب المطلوب (لا تنسخها حرفياً):
- «ماذا قال أبو هريرة عن ثواب صيام رمضان؟»
- «ما الحكم الشرعي في الصدقة الذي روته عائشة رضي الله عنها؟»
- «كيف بيّن ابن عمر صفة صلاة السفر التي نقلها عن النبي؟»
- «لماذا حذّر أنس بن مالك في حديثه من تأخير الصلاة؟»

شروط صارمة:
1. يجب أن يرد اسم الراوي/الصحابي المعطى (أو اسمه الأول المشهور) صراحةً في نص السؤال.
2. يُمنع منعاً باتاً أن يكون المطلوب «من روى» أو «كم سنداً» أو «شيخ مسلم» أو «هل فلان في الإسناد»؛ المطلوب يجب أن يكون **متن الحديث ومعناه أو حكمه**.
3. يُمنع ذكر رقم الحديث.
4. نوّع الصياغات وأسماء الاستفهام (ماذا، ما، كيف، لماذا، متى، هل يجوز، بمَ...) عبر جميع البنود.

أعد JSON بهذه البنية دون غيرها:
{{"records": [{{"idx": 1, "q": "..."}}, ...]}}

الأحاديث:
{items}"""


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
    for path in (GOLDEN_PATH, SYNTHETIC_EVAL_PATH, CHAIN_EVAL_PATH, ROUTER_FRESH_PATH):
        for row in _load_jsonl(path):
            q = str(row.get("question", ""))
            if q:
                used_qs.add(_norm_question(q))
            for hid in row.get("hadith_ids") or []:
                used_hids.add(int(hid))
    return used_hids, used_qs


def _clean_narrator_name(full_name: str) -> str:
    parts = [p.strip() for p in full_name.split("/") if p.strip()]
    base = parts[0] if parts else full_name.strip()
    return base.split(",")[0].strip()


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
        if 130 <= len(matn) <= 900:
            matn_by_hid[hid] = (chapter, matn)

    candidates: list[dict[str, Any]] = []
    with open_graph(GRAPH_DB_PATH) as conn:
        for hid in sorted(matn_by_hid):
            ctx = context_for_local_hadith(conn, hid)
            if ctx.get("status") != LINKED_WITH_RECORDED_ISNAD or not ctx.get("isnads"):
                continue
            chain0 = ctx["isnads"][0].get("narrators") or []
            if len(chain0) < 3:
                continue
            narrators = [
                _clean_narrator_name(str(step.get("name_ar_mapped") or step.get("name_ar") or ""))
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
                    "companion": narrators[0],
                    "narrators": narrators,
                }
            )
    return candidates


def _name_hit(name: str, question: str) -> bool:
    norm_q = strip_diacritics(question or "")
    norm_q = re.sub(r"[أإآٱ]", "ا", norm_q)
    norm_n = strip_diacritics(name or "")
    norm_n = re.sub(r"[أإآٱ]", "ا", norm_n)
    stop = {"بن", "ابن", "ابنة", "بنت", "ابو", "ابا", "ابي", "ام", "المؤمنين", "عبد"}
    tokens = [t for t in _norm_question(norm_n).split() if t not in stop and len(t) >= 3]
    return any(tok in norm_q for tok in tokens)


def _call_gemma_json(client: genai.Client, prompt: str) -> dict[str, Any]:
    for attempt in range(7):
        try:
            resp = client.models.generate_content(
                model=GEMMA_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.45,
                    response_mime_type="application/json",
                ),
            )
            raw = (resp.text or "{}").strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
            time.sleep(2.5)
            return json.loads(raw)
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg or "UNAVAILABLE" in msg:
                wait = min(45, 5 * (attempt + 1))
                print(f"[gemma retry {attempt + 1}/7 after transient error: waiting {wait}s]")
                time.sleep(wait)
                continue
            if attempt >= 3:
                raise
            time.sleep(3)
    raise RuntimeError("Gemma JSON generation exhausted transient retries")


def _generate_chain_batch(
    client: genai.Client,
    qtype: str,
    batch: list[dict[str, Any]],
    used_qs: set[str],
) -> list[dict[str, Any]]:
    lines = []
    for i, item in enumerate(batch, start=1):
        if qtype == "narrator_in_chain":
            lines.append(
                f"{i}. رقم الحديث: {item['hadith_id']} | الباب: {item['chapter']} | الراوي: {item['query_narrator']}"
            )
        elif qtype == "topic_who_narrated":
            snippet = strip_diacritics(item["matn"])[:260]
            lines.append(f"{i}. الباب: {item['chapter']} | المتن: {snippet}")
        else:
            lines.append(f"{i}. رقم الحديث: {item['hadith_id']} | الباب: {item['chapter']}")

    prompt = _CHAIN_PROMPTS[qtype].format(items="\n".join(lines))
    for _attempt in range(5):
        data = _call_gemma_json(client, prompt)
        by_idx = {
            int(row["idx"]): str(row.get("q", "")).strip()
            for row in data.get("records", [])
            if isinstance(row, dict) and isinstance(row.get("idx"), int)
        }
        results = []
        valid = True
        for i, item in enumerate(batch, start=1):
            q = by_idx.get(i, "")
            nq = _norm_question(q)
            if len(q) < 12 or not _ARABIC_RE.search(q) or nq in used_qs:
                valid = False
                break
            if qtype != "topic_who_narrated" and str(item["hadith_id"]) not in q:
                valid = False
                break
            if qtype == "topic_who_narrated" and str(item["hadith_id"]) in q:
                valid = False
                break
            results.append((nq, q, item))
        if valid and len(results) == len(batch):
            out = []
            for nq, q, item in results:
                used_qs.add(nq)
                out.append(
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
            return out
    raise RuntimeError(f"Failed generating chain batch {qtype!r}")


def _generate_hard_negative_batch(
    client: genai.Client,
    batch: list[dict[str, Any]],
    used_qs: set[str],
) -> list[dict[str, Any]]:
    lines = []
    for i, item in enumerate(batch, start=1):
        snippet = strip_diacritics(item["matn"])[:280]
        lines.append(
            f"{i}. الصحابي/الراوي: {item['companion']} | الباب: {item['chapter']} | المتن: {snippet}"
        )
    prompt = _HARD_NEGATIVE_TEXT_PROMPT.format(items="\n".join(lines))
    for _attempt in range(5):
        data = _call_gemma_json(client, prompt)
        by_idx = {
            int(row["idx"]): str(row.get("q", "")).strip()
            for row in data.get("records", [])
            if isinstance(row, dict) and isinstance(row.get("idx"), int)
        }
        results = []
        valid = True
        for i, item in enumerate(batch, start=1):
            q = by_idx.get(i, "")
            nq = _norm_question(q)
            if (
                len(q) < 12
                or not _ARABIC_RE.search(q)
                or nq in used_qs
                or str(item["hadith_id"]) in q
                or not _name_hit(item["companion"], q)
            ):
                valid = False
                break
            results.append((nq, q, item))
        if valid and len(results) == len(batch):
            out = []
            for nq, q, item in results:
                used_qs.add(nq)
                out.append(
                    {
                        "type": "hard_negative_text",
                        "question": q,
                        "hadith_ids": [item["hadith_id"]],
                        "query_narrator": item["companion"],
                        "chapter": item["chapter"],
                        "generator_model": GEMMA_MODEL,
                        "expected_intent": "text",
                    }
                )
            return out
    raise RuntimeError("Failed generating hard-negative batch")


def main() -> None:
    used_hids, used_qs = _used_ids_and_questions()
    candidates = _collect_candidates(used_hids)
    rng = random.Random(SEED)
    rng.shuffle(candidates)

    if len(candidates) < 60:
        raise RuntimeError(f"Only {len(candidates)} disjoint candidates available")

    chain_pool = candidates[:30]
    text_pool = candidates[30:60]
    all_narrator_pool = sorted({n for c in chain_pool for n in c["narrators"]})

    client = genai.Client(location=GEMMA_LOCATION)
    rows: list[dict[str, Any]] = []

    qtypes = [
        "who_narrated_companion",
        "who_narrated_teacher",
        "isnad_count",
        "narrator_in_chain",
        "topic_who_narrated",
    ]
    c_idx = 1
    for t_idx, qtype in enumerate(qtypes):
        batch = chain_pool[t_idx * 6 : (t_idx + 1) * 6]
        if qtype == "narrator_in_chain":
            for j, item in enumerate(batch):
                if j < 4:
                    item["query_narrator"] = item["narrators"][min(1, len(item["narrators"]) - 1)]
                else:
                    outside = [n for n in all_narrator_pool if n not in item["narrators"]]
                    item["query_narrator"] = outside[j % len(outside)]
        generated = _generate_chain_batch(client, qtype, batch, used_qs)
        for row in generated:
            row["id"] = f"router_fresh2_chain_{c_idx:02d}"
            c_idx += 1
            rows.append(row)

    t_idx = 1
    for start in range(0, 30, 10):
        batch = text_pool[start : start + 10]
        generated = _generate_hard_negative_batch(client, batch, used_qs)
        for row in generated:
            row["id"] = f"router_fresh2_hardneg_{t_idx:02d}"
            t_idx += 1
            rows.append(row)

    ROUTER_FRESH2_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ROUTER_FRESH2_PATH.open("w", encoding="utf-8") as fh:
        for row in rows:
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

    digest = hashlib.sha256(ROUTER_FRESH2_PATH.read_bytes()).hexdigest()
    print(f"Generated {len(rows)} rows (30 chain + 30 hard-negative text) with {GEMMA_MODEL}")
    print(f"Path: {ROUTER_FRESH2_PATH}")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    main()
