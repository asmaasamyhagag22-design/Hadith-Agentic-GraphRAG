"""
بناء مجموعة تقييم كبيرة بتوليد known-item.

ليه: مجموعة الـ 27 المكتوبة بإيد كفاية للإبلاغ بس مش كفاية
للاختيار — فرق 4 نقاط عليها = سؤال واحد. مقارنة موديلين
عليها بتطلع ضوضاء مش نتيجة.

الطريقة: لكل حديث نولّد سؤال من متنه، والإجابة الصح =
رقم الحديث نفسه.

⚠ التحيّز المعروف والمقصود إعلانه: الأسئلة مولّدة من المتن
فبتشارك ألفاظه، وده بيحابي BM25 على البحث الدلالي. مخفَّف
بحاجتين — البرومبت بيمنع إعادة استخدام الألفاظ المميزة،
وفلتر بيشيل أي سؤال تداخله المعجمي مع المتن أعلى من الحد.
التحيّز بيتقل، ما بيختفيش. الأرقام من المجموعة دي تُستخدم
للمقارنة النسبية بين الإعدادات، مش كأرقام مطلقة.
"""

import sys
import json
import re
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SYNTHETIC_EVAL_PATH
from embed import load_chunks, indexable_chunks
from utils import split_isnad_matn
from lexical import tokenize
from answer import generate

TARGET_SIZE = 400
BATCH_SIZE = 5
SEED = 20260809

# الأسئلة اللي بتعيد استخدام ألفاظ المتن بتخلي المهمة
# مطابقة نصية مش استرجاع. الحد ده بيشيلها.
MAX_LEXICAL_OVERLAP = 0.60

# أقل عدد كلمات محتوى يخلي السؤال محدِّدًا لموضوع
MIN_CONTENT_TOKENS = 4

# الموديل بيسرّب حروف من لغات تانية أحيانًا حتى مع
# temperature=0 (شفنا «ي满يها» و«yakol»). أي سؤال فيه حرف
# مش عربي ولا ترقيم بيتشال — مش بيتصلّح.
_FOREIGN_SCRIPT = re.compile(r"[A-Za-zĀ-׿܀-￿]")

MIN_MATN_CHARS = 120
MAX_MATN_CHARS = 900

# توقيع المتن: أول كام كلمة بعد التطبيع. بيستخدم عشان
# نستبعد المتون المكررة — لو نفس المتن في كذا حديث يبقى
# فيه إجابة صح تانية مش محسوبة، وده الفخ اللي وقعنا فيه
# تلات مرات في المجموعة اليدوية.
SIGNATURE_WORDS = 8

PROMPT = """أنت تبني مجموعة اختبار لمحرك بحث في الحديث النبوي.

لكل متن مرقّم بالأسفل، اكتب سؤالاً واحداً يسأله شخص عادي وتكون \
إجابته في هذا المتن.

قواعد صارمة:

1. السؤال يجب أن يكون **محدِّداً**: من يقرؤه وحده يعرف عن أي موضوع \
بالضبط يبحث. اذكر الموضوع صراحةً (الصلاة، الصوم، البيع، الجار، \
الطهارة...) ولا تكتفِ بإشارة غامضة.
   سيّئ: "ما هي القاعدة المتعلقة باللعق؟"
   جيّد: "ما حكم لعق الأصابع بعد الطعام؟"
   سيّئ: "ما هي الحماية المحددة للمدينة؟"
   جيّد: "بماذا دعا النبي لأهل المدينة أن تُحفظ من الطاعون والدجال؟"

2. لا تُعِد استخدام العبارات المميزة الواردة في المتن حرفياً؛ أعد \
صياغتها بمفردات مختلفة مع بقاء الموضوع واضحاً.

3. السؤال مفهوم بذاته دون رؤية المتن، ولا يستعمل ضمائر إشارة \
مبهمة مثل "هذا" أو "المذكور".

4. لا تذكر رقم الحديث ولا كلمة "الحديث" ولا "المتن".

5. إذا كان المتن غامضاً أو مقتطعاً بحيث لا يمكن بناء سؤال محدِّد \
منه، فاكتب "SKIP" بدل السؤال.

أعد النتيجة JSON فقط بهذا الشكل، دون أي نص آخر:
{{"questions": [{{"index": 1, "question": "..."}}, ...]}}

المتون:
{documents}"""


def matn_signature(text):

    return " ".join(tokenize(text)[:SIGNATURE_WORDS])


def content_tokens(text):
    """كلمات بحرفين فأكتر — بتشيل حروف الجر والعطف تقريبًا."""

    return {token for token in tokenize(text) if len(token) > 2}


def lexical_overlap(question, matn):
    """نسبة كلمات السؤال الموجودة في المتن."""

    question_tokens = content_tokens(question)

    if not question_tokens:
        return 1.0

    return len(question_tokens & content_tokens(matn)) / len(question_tokens)


def candidate_hadiths(chunks):
    """
    الأجزاء الأولى بس، بمتن بطول معقول، ومتن غير مكرر
    في الفهرس كله.
    """

    matns = {
        str(chunk["id"]): split_isnad_matn(chunk["text"])
        for chunk in chunks
    }

    signatures = {}

    for matn in matns.values():
        signature = matn_signature(matn)
        signatures[signature] = signatures.get(signature, 0) + 1

    candidates = []

    for chunk in chunks:

        if not str(chunk["id"]).endswith("_0"):
            continue

        matn = matns[str(chunk["id"])]

        if not MIN_MATN_CHARS <= len(matn) <= MAX_MATN_CHARS:
            continue

        if signatures[matn_signature(matn)] > 1:
            continue

        candidates.append((chunk["metadata"]["hadith_number"], matn))

    return candidates


def parse_response(content):

    match = re.search(r"\{.*\}", content, re.DOTALL)

    if not match:
        return []

    try:
        return json.loads(match.group(0)).get("questions", [])
    except json.JSONDecodeError:
        return []


def generate_batch(batch):
    """إعادة المحاولة والانتظار المتصاعد جوه answer.generate."""

    documents = "\n\n".join(
        f"{i + 1}. {matn}" for i, (_, matn) in enumerate(batch)
    )

    return parse_response(generate(PROMPT.format(documents=documents)))


def main(target_size=TARGET_SIZE):

    chunks = indexable_chunks(load_chunks())

    candidates = candidate_hadiths(chunks)

    print(f"Eligible hadiths: {len(candidates)}")

    random.Random(SEED).shuffle(candidates)

    rows = []
    dropped_overlap = 0
    dropped_vague = 0
    dropped_foreign = 0
    failed_batches = 0

    for start in range(0, len(candidates), BATCH_SIZE):

        if len(rows) >= target_size:
            break

        batch = candidates[start:start + BATCH_SIZE]

        try:
            questions = generate_batch(batch)
        except Exception as error:  # rate limit / transient API failure
            failed_batches += 1
            print(f"  batch failed: {type(error).__name__}")
            continue

        for entry in questions:

            index = entry.get("index", 0) - 1

            if not 0 <= index < len(batch):
                continue

            question = entry.get("question", "").strip()

            if not question or question.upper().startswith("SKIP"):
                continue

            # سؤال بكلمات محتوى قليلة مش بيحدّد حاجة، وبيبقى
            # مستحيل بحكم صياغته مش بحكم صعوبة الاسترجاع.
            if len(content_tokens(question)) < MIN_CONTENT_TOKENS:
                dropped_vague += 1
                continue

            if _FOREIGN_SCRIPT.search(question):
                dropped_foreign += 1
                continue

            hadith_id, matn = batch[index]

            overlap = lexical_overlap(question, matn)

            if overlap > MAX_LEXICAL_OVERLAP:
                dropped_overlap += 1
                continue

            rows.append({
                "question": question,
                "type": "matn",
                "answerable": True,
                "hadith_ids": [hadith_id],
                "lexical_overlap": round(overlap, 3),
                "source": "generated",
            })

        print(f"  {len(rows)}/{target_size}", end="\r")

    print(f"\n\nkept             : {len(rows)}")
    print(f"dropped (overlap): {dropped_overlap}")
    print(f"dropped (vague)  : {dropped_vague}")
    print(f"dropped (foreign): {dropped_foreign}")
    print(f"failed batches   : {failed_batches}")

    if rows:
        mean_overlap = sum(r["lexical_overlap"] for r in rows) / len(rows)
        print(f"mean overlap     : {mean_overlap:.3f}")

    SYNTHETIC_EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(SYNTHETIC_EVAL_PATH, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\nSaved -> {SYNTHETIC_EVAL_PATH}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else TARGET_SIZE)
