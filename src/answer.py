import sys
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import QUESTIONS_PATH
from retrieve import Retriever
from experiment_variants import variant_text

from google import genai
from google.genai import types

load_dotenv()

# موديل واحد ثابت. الحصص اليومية اللي كانت بتفرض التنقل
# بين الموديلات راحت مع Groq، والتنقل نفسه كان بيفسد
# المقارنات — أي رقم اتقاس على موديل مختلف مش قابل
# للمقارنة مع اللي قبله.
MODEL = "gemini-2.5-pro"

# صفر عشان النتايج تبقى قابلة للتكرار في التجارب، وعشان
# يوقف تسرّب حروف من لغات تانية اللي كان بيحصل مع الافتراضي.
TEMPERATURE = 0

REFUSAL = "المصادر المتاحة لا تجيب عن هذا السؤال"

# المصادقة عبر Vertex: GOOGLE_CLOUD_PROJECT و
# GOOGLE_CLOUD_LOCATION و GOOGLE_GENAI_USE_VERTEXAI في .env،
# والاعتماد على Application Default Credentials.
MAX_ATTEMPTS = 5
INITIAL_BACKOFF_SECONDS = 4

_client = None


def get_client():

    global _client

    if _client is None:
        _client = genai.Client()

    return _client


def generate(prompt, system_instruction=None, history=(), model=MODEL):
    """
    نداء واحد لـ Gemini مع انتظار متصاعد.

    history: أدوار سابقة كـ (role, text) — بتستخدم في
    إعادة التوليد بعد استشهاد غلط.
    """

    contents = [
        types.Content(role=role, parts=[types.Part(text=text)])
        for role, text in history
    ]

    contents.append(
        types.Content(role="user", parts=[types.Part(text=prompt)])
    )

    config = types.GenerateContentConfig(
        temperature=TEMPERATURE,
        system_instruction=system_instruction,
    )

    delay = INITIAL_BACKOFF_SECONDS

    for attempt in range(MAX_ATTEMPTS):

        try:
            response = get_client().models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            return (response.text or "").strip()

        except Exception:

            if attempt == MAX_ATTEMPTS - 1:
                raise

            time.sleep(delay)
            delay *= 2

    return ""


def build_system_prompt(context_text):

    return f"""
أنت مساعد افتراضي متخصص في شرح وتفسير الأحاديث النبوية.

المهمة:
أجب اعتمادًا على الأحاديث الموجودة في السياق فقط.

السياق:
{context_text}

التعليمات:

1. استخدم المعلومات الموجودة في السياق فقط.
2. لا تخترع معلومات، ولا تستشهد برقم حديث غير موجود في السياق.
3. أجب بالعربية الفصحى فقط.

4. إذا وجدت الإجابة في السياق:
   اذكرها، ثم اختم برقم الحديث بهذا الشكل:
   (المصدر: صحيح مسلم، حديث رقم XXXX)
   على أن يكون الرقم منقولًا حرفيًا من حقل Hadith ID في السياق.

5. إذا لم تجد الإجابة في السياق:
   اكتب هذه الجملة وحدها ولا تضف أي شيء بعدها،
   ولا تذكر أي مصدر أو رقم حديث:
   "{REFUSAL}"
"""


def format_context(relevant_chunks):
    """
    المتن بس، بتشكيله، مع رقم الحديث والباب.

    قبل كده كنا بنبعت chunk['text'] كامل بالسند — سلسلة
    رواة طولها مئات الحروف مالهاش علاقة بالسؤال، بتاكل
    نافذة السياق وبتشوّش الموديل. والـ metadata كانت
    بتتطبع كـ dict خام فيه حقول مالهاش لازمة هنا.
    """

    blocks = []

    for chunk in relevant_chunks:

        metadata = chunk["metadata"]

        blocks.append(
            f"[حديث رقم {chunk['hadith_id']} — {metadata['chapter_arabic']}]\n"
            f"{variant_text(chunk, 'matn')}"
        )

    return "\n\n".join(blocks)


# الصيغة مفروضة في build_system_prompt
CITATION = re.compile(r"حديث\s*رقم\s*[:\s]*(\d+)")

CORRECTION = (
    "الرقم الذي ذكرته غير موجود في السياق. "
    "أعد الإجابة مستشهدًا برقم من أرقام الأحاديث المعروضة فقط، "
    "أو اكتب جملة الرفض وحدها إن لم تكن الإجابة موجودة."
)


def cited_ids(answer):

    return {int(match) for match in CITATION.findall(answer)}


GRADE_PROMPT = """قيّم مدى صلة الأحاديث التالية بالسؤال.

السؤال: {question}

الأحاديث:
{context}

أجب برقم واحد فقط من 1 إلى 5، دون أي كلام آخر:
5 = فيها إجابة مباشرة وواضحة للسؤال
3 = فيها ما يتعلق بالموضوع دون إجابة صريحة
1 = لا علاقة لها بالسؤال"""

REWRITE_PROMPT = """أعد صياغة هذا السؤال بألفاظ أقرب إلى لغة \
الحديث النبوي، مع الحفاظ على معناه.

اكتب السؤال المعاد صياغته فقط، دون أي كلام آخر.

السؤال: {question}"""

MIN_USEFUL_GRADE = 3

_GRADE = re.compile(r"[1-5]")


def grade_context(question, chunks):
    """تقييم ذاتي للمسترجَع — فكرة CRAG. بيرجع 1..5."""

    if not chunks:
        return 1

    reply = generate(GRADE_PROMPT.format(
        question=question,
        context=format_context(chunks),
    ))

    match = _GRADE.search(reply)

    return int(match.group(0)) if match else MIN_USEFUL_GRADE


def rewrite_question(question):

    return generate(REWRITE_PROMPT.format(question=question)) or question


def retrieve_with_self_correction(question, retriever, k):
    """
    بيدوّر، بيقيّم، ولو ضعيف بيعيد الصياغة ويدوّر **مرة
    واحدة بس**. لو فضل ضعيف بيرجع لا شيء عشان الطبقة اللي
    فوق ترفض.

    بيزوّد نداءين لكل سؤال — لازم يتقاس مقابل عدمه، مش
    يتفترض إنه بيحسّن.
    """

    chunks = retriever.search(question, k=k)

    if grade_context(question, chunks) >= MIN_USEFUL_GRADE:
        return chunks, question, False

    rewritten = rewrite_question(question)

    retried = retriever.search(rewritten, k=k)

    if grade_context(question, retried) >= MIN_USEFUL_GRADE:
        return retried, rewritten, True

    return [], rewritten, True


def answer_with_details(
    question,
    retriever,
    k=5,
    enforce_citations=True,
    self_correct=False,
):
    """
    بترجع dict فيه الإجابة النهائية **والمحاولة الخام**.

    القياس بيحصل على المحاولة الخام: لو قِسنا بعد التصفية
    هتطلع صفر أخطاء دايمًا بحكم البناء، وده رقم بلا معنى.
    """

    rewritten = None
    retried = False

    if self_correct:
        chunks, rewritten, retried = retrieve_with_self_correction(
            question, retriever, k
        )
    else:
        chunks = retriever.search(question, k=k)

    if not chunks:
        return {
            "answer": REFUSAL,
            "raw": REFUSAL,
            "chunks": [],
            "invalid_citation_attempt": False,
            "regenerated": False,
            "rewritten": rewritten,
            "retried": retried,
        }

    context_ids = {chunk["hadith_id"] for chunk in chunks}

    system_instruction = build_system_prompt(format_context(chunks))

    raw = generate(question, system_instruction=system_instruction)

    invalid = bool(cited_ids(raw) - context_ids)

    answer = raw
    regenerated = False

    if invalid and enforce_citations:

        # مرة واحدة بس. لو فشل تاني بنرفض — إجابة بلا مصدر
        # في المجال ده أسوأ من الاعتراف بعدم المعرفة.
        regenerated = True

        answer = generate(
            CORRECTION,
            system_instruction=system_instruction,
            history=[("user", question), ("model", raw)],
        )

        if cited_ids(answer) - context_ids:
            answer = REFUSAL

    return {
        "answer": answer,
        "raw": raw,
        "chunks": chunks,
        "invalid_citation_attempt": invalid,
        "regenerated": regenerated,
        "rewritten": rewritten,
        "retried": retried,
    }


def answer_question(
    question,
    retriever,
    k=5,
    enforce_citations=True,
    self_correct=False,
):

    details = answer_with_details(
        question,
        retriever,
        k=k,
        enforce_citations=enforce_citations,
        self_correct=self_correct,
    )

    return details["answer"], details["chunks"]


def load_questions(path=QUESTIONS_PATH):

    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def main():

    retriever = Retriever.from_files()

    for question in load_questions():

        print("=" * 80)
        print(question)

        answer, chunks = answer_question(question, retriever)

        print("\nAnswer:")
        print(answer)

        print("\nRetrieved Chunks:")

        for chunk in chunks:

            print(
                f"Rank: {chunk['rank']} | "
                f"Chunk ID: {chunk['chunk_id']} | "
                f"Hadith ID: {chunk['hadith_id']} | "
                f"Score: {chunk['score']:.4f}"
            )


if __name__ == "__main__":
    main()
