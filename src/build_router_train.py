"""Build `data/raw/router_train.jsonl` for training Router v3 (embedding classifier).

Combines:
  - `data/raw/chain_eval_dev.jsonl` (15 chain items)
  - `data/raw/synthetic_eval.jsonl` (224 text items)
  - ~150 newly generated varied Arabic chain paraphrases (Gemini Flash)
  - ~100 newly generated hard-negative text questions mentioning narrators
    (Gemini Flash, distinct prompt from build_router_fresh*.py)

Strictly excludes ALL questions and hadith IDs from `router_fresh.jsonl`,
`router_fresh2.jsonl`, `chain_eval_test.jsonl`, `golden.jsonl`, and does NOT
touch `holdout_draft.jsonl`. Records Flash API usage in `c5_api_ledger.json`.
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

CHAIN_DEV_PATH = RAW_DIR / "chain_eval_dev.jsonl"
CHAIN_TEST_PATH = RAW_DIR / "chain_eval_test.jsonl"
CHAIN_EVAL_PATH = RAW_DIR / "chain_eval.jsonl"
ROUTER_FRESH_PATH = RAW_DIR / "router_fresh.jsonl"
ROUTER_FRESH2_PATH = RAW_DIR / "router_fresh2.jsonl"
ROUTER_TRAIN_PATH = RAW_DIR / "router_train.jsonl"
LEDGER_PATH = PROCESSED_DIR / "c5_api_ledger.json"

FLASH_MODEL = "gemini-2.5-flash"
SEED = 20261117
_ARABIC_RE = re.compile(r"[\u0621-\u064a]{2,}")

# Third distinct prompt family for training generation via Gemini Flash.
_TRAIN_CHAIN_PROMPT = """أنت لغوي ومحدّث تساعد في بناء مجموعة تدريبية لتصنيف أسئلة المستخدمين حول **الأسانيد والرواة** في صحيح مسلم.
اكتب سؤالاً عربياً طبيعياً (بأسلوب متنوع غير نمطي) لكل بند أدناه يطلب المعلومة الإسنادية المحددة في النوع المطلوب:
- `who_narrated_companion`: السؤال عن الصحابي راوي الحديث رقم X (صياغات متنوعة جداً: عن أي صحابي، من نقل، إلى من ينسب، باسم أي صحابي، أي صحابي روى، حديث X من رواه من الصحابة، إلخ).
- `who_narrated_teacher`: السؤال عن شيخ الإمام مسلم المباشر في الحديث رقم X (أستاذه، معلمه، الشخص الذي سمع/تلقّى/أخذ عنه مسلم مباشرة، إلخ).
- `isnad_count`: السؤال عن عدد الأسانيد أو الطرق أو المخارج أو المسالك للحديث رقم X.
- `narrator_in_chain`: السؤال هل يمر/يظهر/يوجد/ورد/شارك الراوي المحدد في سند أو رواية الحديث رقم X.
- `topic_who_narrated`: السؤال عمّن روى أو ما سند الحديث المرتبط بالمضمون/المتن المذكور **دون ذكر أي رقم حديث**.

قواعد صارمة:
1. عند وجود `رقم الحديث` (الأنواع الأربعة الأولى)، أدرجه حرفياً في السؤال ولا تذكر اسم الصحابي/الشيخ الجوابي.
2. في `narrator_in_chain`، أدرج كلاً من رقم الحديث واسم الراوي المعطى.
3. في `topic_who_narrated`، يُمنع كتابة أي رقم حديث.
4. نوّع بدايات الأسئلة وأدوات الاستفهام (أريد، هل يمكن، من، عن أي، بكم، إلى من، أخبرني، تأكد...) تنويعاً واسعاً.

أخرج JSON فقط:
{{"items": [{{"idx": 1, "question": "..."}}, ...]}}

البنود:
{items}"""

_TRAIN_HARD_NEG_PROMPT = """أنت تساعد في بناء أمثلة تدريبية صعبة (**Hard-Negative Text Questions**) تمثل مستخدمين يسألون عن **المعنى أو الحكم الفقهي أو تفاصيل القصة النبوية** رغم ذكرهم اسم الصحابي/الراوي أو فعل الرواية في صيغة السؤال.
لكل بند أدناه، اكتب سؤالاً طبيعياً يستفهم عن **المضمون الفقهي أو العقيدي أو اللفظ النبوي أو القصة** المذكورة في المتن، مع إدراج اسم الصحابي/الراوي المعطى في سياق السؤال (مثل: في حديث أبي هريرة...، ماذا استنبط ابن عباس في مسألة...، بمَ أجاب النبي في الرواية التي نقلها أنس...، ما الحكمة من النهي المذكور في حديث رقم X عن جابر...).

شروط صارمة:
1. أدرج اسم الصحابي/الراوي المعطى (أو شهرته/كنيته) في نص السؤال.
2. إذا وُجد توجيه `اذكر_الرقم=نعم` فاذكر رقم الحديث المرفق في السؤال رغم كونه سؤال مضمون/فقه؛ وإذا كان `لا` فلا تذكر أي رقم.
3. اجعل الهدف الحقيقي للسؤال **المحتوى أو الحكم أو الشرح** لا معرفة اسم الراوي ولا عدد الطرق ولا فحص الإسناد.

أخرج JSON فقط:
{{"items": [{{"idx": 1, "question": "..."}}, ...]}}

البنود:
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


def _protected_sets() -> tuple[set[int], set[str], set[str]]:
    """Collect hadith IDs & normalized questions from ALL eval splits to prevent leakage."""
    exclude_hids: set[int] = set()
    forbidden_eval_qs: set[str] = set()
    all_seen_qs: set[str] = set()
    for path in (GOLDEN_PATH, SYNTHETIC_EVAL_PATH, CHAIN_EVAL_PATH, ROUTER_FRESH_PATH, ROUTER_FRESH2_PATH):
        for row in _load_jsonl(path):
            q = str(row.get("question", ""))
            if q:
                nq = _norm_question(q)
                all_seen_qs.add(nq)
                if path in (GOLDEN_PATH, CHAIN_TEST_PATH, ROUTER_FRESH_PATH, ROUTER_FRESH2_PATH):
                    forbidden_eval_qs.add(nq)
            for hid in row.get("hadith_ids") or []:
                exclude_hids.add(int(hid))
    for path in (CHAIN_TEST_PATH, ROUTER_FRESH_PATH, ROUTER_FRESH2_PATH):
        for row in _load_jsonl(path):
            q = str(row.get("question", ""))
            if q:
                forbidden_eval_qs.add(_norm_question(q))
    return exclude_hids, forbidden_eval_qs, all_seen_qs


def _clean_narrator_name(full_name: str) -> str:
    parts = [p.strip() for p in full_name.split("/") if p.strip()]
    base = parts[0] if parts else full_name.strip()
    return base.split(",")[0].strip()


def _collect_disjoint_candidates(exclude_hids: set[int]) -> list[dict[str, Any]]:
    raw_chunks = load_chunks(PROCESSED_DIR / "muslim_chunks.json")
    idx_chunks = indexable_chunks(raw_chunks)
    matn_by_hid: dict[int, tuple[str, str]] = {}
    for c in idx_chunks:
        cid = str(c["id"])
        if not cid.endswith("_0"):
            continue
        hid = int(c["metadata"]["hadith_number"])
        if hid in exclude_hids:
            continue
        matn = " ".join(split_isnad_matn(c["text"]).split())
        chapter = str(c["metadata"].get("chapter_arabic", "")).strip()
        if 110 <= len(matn) <= 950:
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


def _bump_flash_ledger(calls: int) -> dict[str, Any]:
    ledger = {"pro_calls": 0, "flash_calls": 0, "embed_calls": 0, "pro_cap": 500, "flash_cap": 800, "history": []}
    if LEDGER_PATH.exists():
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    if ledger["flash_calls"] + calls > ledger.get("flash_cap", 800):
        raise RuntimeError(f"Flash budget exceeded: {ledger['flash_calls']} + {calls}")
    ledger["flash_calls"] += calls
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ledger


def _call_flash_json(client: genai.Client, prompt: str) -> tuple[dict[str, Any], int]:
    calls = 0
    for attempt in range(6):
        try:
            resp = client.models.generate_content(
                model=FLASH_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.65,
                    response_mime_type="application/json",
                ),
            )
            calls += 1
            raw = (resp.text or "{}").strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
            return json.loads(raw), calls
        except Exception as exc:
            msg = str(exc)
            if any(k in msg for k in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")):
                wait = min(30, 4 * (attempt + 1))
                print(f"[flash retry {attempt + 1}/6 waiting {wait}s]")
                time.sleep(wait)
                continue
            if attempt >= 3:
                raise
            time.sleep(2)
    raise RuntimeError("Flash JSON generation exhausted retries")


def _name_hit(name: str, question: str) -> bool:
    norm_q = re.sub(r"[أإآٱ]", "ا", strip_diacritics(question or ""))
    norm_n = re.sub(r"[أإآٱ]", "ا", strip_diacritics(name or ""))
    stop = {"بن", "ابن", "ابنة", "بنت", "ابو", "ابا", "ابي", "ام", "المؤمنين", "عبد"}
    tokens = [t for t in _norm_question(norm_n).split() if t not in stop and len(t) >= 3]
    return any(tok in norm_q for tok in tokens)


def main() -> None:
    exclude_hids, forbidden_eval_qs, all_seen_qs = _protected_sets()
    candidates = _collect_disjoint_candidates(exclude_hids)
    rng = random.Random(SEED)
    rng.shuffle(candidates)

    if len(candidates) < 260:
        raise RuntimeError(f"Expected >= 260 disjoint candidates, found {len(candidates)}")

    chain_pool = candidates[:150]
    hardneg_pool = candidates[150:250]
    all_narrators = sorted({n for c in chain_pool for n in c["narrators"]})

    client = genai.Client()
    total_flash_calls = 0

    rows: list[dict[str, Any]] = []
    # Base split items specified by Step 1b: chain_eval_dev (15) + synthetic_eval (224).
    for row in _load_jsonl(CHAIN_DEV_PATH):
        rows.append(
            {
                "id": row["id"],
                "type": row["type"],
                "question": row["question"],
                "hadith_ids": row.get("hadith_ids", []),
                "expected_intent": "chain",
                "source": "chain_eval_dev",
            }
        )
    for idx, row in enumerate(_load_jsonl(SYNTHETIC_EVAL_PATH), start=1):
        rows.append(
            {
                "id": f"synthetic_eval_{idx:03d}",
                "type": row.get("type", "matn"),
                "question": row["question"],
                "hadith_ids": row.get("hadith_ids", []),
                "expected_intent": "text",
                "source": "synthetic_eval",
            }
        )

    qtypes = [
        "who_narrated_companion",
        "who_narrated_teacher",
        "isnad_count",
        "narrator_in_chain",
        "topic_who_narrated",
    ]
    c_num = 1
    batch_size = 15
    for start in range(0, len(chain_pool), batch_size):
        batch = chain_pool[start : start + batch_size]
        prompt_lines = []
        meta = []
        for i, item in enumerate(batch, start=1):
            qtype = qtypes[(start + i - 1) % len(qtypes)]
            qn = None
            if qtype == "narrator_in_chain":
                if i % 3 != 0:
                    qn = item["narrators"][min(1, len(item["narrators"]) - 1)]
                else:
                    out = [n for n in all_narrators if n not in item["narrators"]]
                    qn = out[(start + i) % len(out)]
                prompt_lines.append(
                    f"{i}. النوع={qtype} | رقم الحديث={item['hadith_id']} | الباب={item['chapter']} | الراوي={qn}"
                )
            elif qtype == "topic_who_narrated":
                snippet = strip_diacritics(item["matn"])[:240]
                prompt_lines.append(f"{i}. النوع={qtype} | الباب={item['chapter']} | المتن={snippet}")
            else:
                prompt_lines.append(f"{i}. النوع={qtype} | رقم الحديث={item['hadith_id']} | الباب={item['chapter']}")
            meta.append((qtype, item, qn))

        prompt = _TRAIN_CHAIN_PROMPT.format(items="\n".join(prompt_lines))
        for _attempt in range(3):
            data, calls = _call_flash_json(client, prompt)
            total_flash_calls += calls
            by_idx = {
                int(r["idx"]): str(r.get("question", "")).strip()
                for r in data.get("items", [])
                if isinstance(r, dict) and isinstance(r.get("idx"), int)
            }
            accepted_batch = []
            for i, (qtype, item, qn) in enumerate(meta, start=1):
                q = by_idx.get(i, "")
                nq = _norm_question(q)
                if len(q) < 10 or not _ARABIC_RE.search(q) or nq in all_seen_qs:
                    continue
                if qtype != "topic_who_narrated" and str(item["hadith_id"]) not in q:
                    continue
                if qtype == "topic_who_narrated" and str(item["hadith_id"]) in q:
                    continue
                all_seen_qs.add(nq)
                accepted_batch.append(
                    {
                        "id": f"train_chain_{c_num:03d}",
                        "type": qtype,
                        "question": q,
                        "hadith_ids": [item["hadith_id"]],
                        "expected_intent": "chain",
                        "source": f"generated_{FLASH_MODEL}",
                    }
                )
                c_num += 1
            if accepted_batch:
                rows.extend(accepted_batch)
                break

    h_num = 1
    hn_batch_size = 20
    for start in range(0, len(hardneg_pool), hn_batch_size):
        batch = hardneg_pool[start : start + hn_batch_size]
        prompt_lines = []
        meta = []
        for i, item in enumerate(batch, start=1):
            include_id = (start + i) % 4 == 0
            snippet = strip_diacritics(item["matn"])[:250]
            prompt_lines.append(
                f"{i}. الصحابي/الراوي={item['companion']} | اذكر_الرقم={'نعم (' + str(item['hadith_id']) + ')' if include_id else 'لا'} | "
                f"الباب={item['chapter']} | المتن={snippet}"
            )
            meta.append((include_id, item))
        prompt = _TRAIN_HARD_NEG_PROMPT.format(items="\n".join(prompt_lines))
        for _attempt in range(3):
            data, calls = _call_flash_json(client, prompt)
            total_flash_calls += calls
            by_idx = {
                int(r["idx"]): str(r.get("question", "")).strip()
                for r in data.get("items", [])
                if isinstance(r, dict) and isinstance(r.get("idx"), int)
            }
            accepted_batch = []
            for i, (include_id, item) in enumerate(meta, start=1):
                q = by_idx.get(i, "")
                nq = _norm_question(q)
                if len(q) < 10 or not _ARABIC_RE.search(q) or nq in all_seen_qs:
                    continue
                if not _name_hit(item["companion"], q):
                    continue
                if not include_id and str(item["hadith_id"]) in q:
                    continue
                all_seen_qs.add(nq)
                accepted_batch.append(
                    {
                        "id": f"train_hardneg_{h_num:03d}",
                        "type": "hard_negative_text",
                        "question": q,
                        "hadith_ids": [item["hadith_id"]],
                        "expected_intent": "text",
                        "source": f"generated_{FLASH_MODEL}",
                    }
                )
                h_num += 1
            if accepted_batch:
                rows.extend(accepted_batch)
                break

    # Final leakage safety assertion for newly generated rows against ALL eval sets.
    for row in rows:
        if row["source"] in ("chain_eval_dev", "synthetic_eval"):
            continue
        nq = _norm_question(row["question"])
        if nq in forbidden_eval_qs:
            raise RuntimeError(f"Leakage detected against protected eval set: {row['id']}")

    ROUTER_TRAIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ROUTER_TRAIN_PATH.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    ledger = _bump_flash_ledger(total_flash_calls)
    digest = hashlib.sha256(ROUTER_TRAIN_PATH.read_bytes()).hexdigest()
    n_chain = sum(1 for r in rows if r["expected_intent"] == "chain")
    n_text = sum(1 for r in rows if r["expected_intent"] == "text")
    print(f"Wrote {len(rows)} rows to {ROUTER_TRAIN_PATH} (chain={n_chain}, text={n_text})")
    print(f"Generated new items: chain={c_num - 1}, hardneg_text={h_num - 1}")
    print(f"SHA256: {digest}")
    print(f"Flash calls added: {total_flash_calls} (ledger Flash={ledger['flash_calls']}/{ledger['flash_cap']})")


if __name__ == "__main__":
    main()
