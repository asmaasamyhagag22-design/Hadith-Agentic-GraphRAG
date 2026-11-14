import sys
import os
import re
import threading
import time
from enum import Enum
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import QUESTIONS_PATH
from experiment_variants import variant_text
from sanad_context import (
    INVALID_LOCAL_HADITH_ID,
    LINKED_BUT_NO_RECORDED_ISNAD,
    NO_ACCEPTED_MIS_LINK,
    context_for_local_hadith,
    open_graph,
)

from google import genai
from google.genai import types

load_dotenv()

# موديل واحد ثابت. الحصص اليومية اللي كانت بتفرض التنقل
# بين الموديلات راحت مع Groq، والتنقل نفسه كان بيفسد
# المقارنات — أي رقم اتقاس على موديل مختلف مش قابل
# للمقارنة مع اللي قبله.
MODEL = "gemini-4-argon"

# صفر عشان النتايج تبقى قابلة للتكرار في التجارب، وعشان
# يوقف تسرّب حروف من لغات تانية اللي كان بيحصل مع الافتراضي.
TEMPERATURE = 0

REFUSAL = "المصادر المتاحة لا تجيب عن هذا السؤال"

# المصادقة عبر Vertex: GOOGLE_CLOUD_PROJECT و
# GOOGLE_CLOUD_LOCATION و GOOGLE_GENAI_USE_VERTEXAI في .env،
# والاعتماد على Application Default Credentials.
MAX_ATTEMPTS = 5
INITIAL_BACKOFF_SECONDS = 4
GENERATE_TIMEOUT_MS = int(os.environ.get("MUSNAD_GENERATE_TIMEOUT_MS", "180000"))

_client = None
_thread_clients = threading.local()
_RR_LOCATIONS = (
    "global",
    "us-central1",
    "us-east4",
    "us-west1",
    "europe-west4",
    "us-east1",
    "europe-west1",
)
_rr_counter = 0


def get_client(location=None):

    global _client

    http_opts = types.HttpOptions(timeout=GENERATE_TIMEOUT_MS) if GENERATE_TIMEOUT_MS else None

    if location == "global":
        client = getattr(_thread_clients, "global_client", None)
        if client is None:
            client = genai.Client(location="global", http_options=http_opts)
            _thread_clients.global_client = client
        return client

    if location is not None:
        regional = getattr(_thread_clients, "regional_clients", None)
        if regional is None:
            regional = {}
            _thread_clients.regional_clients = regional
        if location not in regional:
            regional[location] = genai.Client(location=location, http_options=http_opts)
        return regional[location]

    if _client is None:
        _client = genai.Client(http_options=http_opts)

    return _client


def generate(prompt, system_instruction=None, history=(), model=MODEL):
    """
    نداء واحد لـ Gemini مع انتظار متصاعد.

    history: أدوار سابقة كـ (role, text) — بتستخدم في
    إعادة التوليد بعد استشهاد غلط.
    """
    global _rr_counter

    contents = [
        types.Content(role=role, parts=[types.Part(text=text)])
        for role, text in history
    ]

    contents.append(
        types.Content(role="user", parts=[types.Part(text=prompt)])
    )

    is_global_model = model.startswith("gemini-3") or model.startswith("gemini-4")

    if is_global_model:
        config = types.GenerateContentConfig(
            temperature=TEMPERATURE,
            system_instruction=system_instruction,
            thinking_config=types.ThinkingConfig(thinking_level="LOW"),
        )
    else:
        config = types.GenerateContentConfig(
            temperature=TEMPERATURE,
            system_instruction=system_instruction,
        )

    delay = INITIAL_BACKOFF_SECONDS

    for attempt in range(MAX_ATTEMPTS):

        try:
            if is_global_model:
                client = get_client(location="global")
            elif _client is not None:
                client = _client
            else:
                loc = _RR_LOCATIONS[_rr_counter % len(_RR_LOCATIONS)]
                _rr_counter += 1
                client = get_client(location=loc)

            response = client.models.generate_content(
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

# إشارات غير منضبطة لرقم حديث (مثل: "حديث 999"، "حديث رقم: 999"، "مسلم 999"، "مسلم، 999"، "مسلم، رقم 999")
LOOSE_CITATION = re.compile(
    r"(?:حديث(?:\s*رقم)?|مسلم(?:\s*[،,])?(?:\s*رقم)?)\s*[:\s]*(\d+)"
)

_DIGIT = re.compile(r"\d")
_VALID_REFUSAL = re.compile(rf"^{re.escape(REFUSAL)}[.؟!]?$")


class ValidationResult(Enum):
    VALID_ANSWER = "valid_answer"
    VALID_REFUSAL = "valid_refusal"
    MISSING_CITATION = "missing_citation"
    OUT_OF_CONTEXT_CITATION = "out_of_context_citation"
    MIXED_REFUSAL = "mixed_refusal"


VALID_ANSWER = ValidationResult.VALID_ANSWER
VALID_REFUSAL = ValidationResult.VALID_REFUSAL
MISSING_CITATION = ValidationResult.MISSING_CITATION
OUT_OF_CONTEXT_CITATION = ValidationResult.OUT_OF_CONTEXT_CITATION
MIXED_REFUSAL = ValidationResult.MIXED_REFUSAL

CORRECTION_OUT_OF_CONTEXT = (
    "الرقم الذي ذكرته غير موجود في السياق. "
    "أعد الإجابة مستشهدًا برقم من أرقام الأحاديث المعروضة فقط، "
    "أو اكتب جملة الرفض وحدها إن لم تكن الإجابة موجودة."
)

CORRECTION = CORRECTION_OUT_OF_CONTEXT

CORRECTION_MISSING_CITATION = (
    "إجابتك لم تتضمن استشهادًا برقم الحديث بالصيغة المطلوبة. "
    "أعد الإجابة واختم برقم الحديث من السياق بهذا الشكل: "
    "(المصدر: صحيح مسلم، حديث رقم XXXX)، "
    "أو اكتب جملة الرفض وحدها إن لم تكن الإجابة موجودة."
)

CORRECTION_MIXED_REFUSAL = (
    "لقد جمعت بين جملة الرفض وكلام آخر. "
    f'إما أن تكتب جملة الرفض وحدها دون أي إضافة أو أرقام: "{REFUSAL}"، '
    "وإما أن تجيب من السياق مستشهدًا برقم الحديث بالصيغة المطلوبة."
)

CORRECTIONS = {
    OUT_OF_CONTEXT_CITATION: CORRECTION_OUT_OF_CONTEXT,
    MISSING_CITATION: CORRECTION_MISSING_CITATION,
    MIXED_REFUSAL: CORRECTION_MIXED_REFUSAL,
}


def cited_ids(answer):

    return {int(match) for match in CITATION.findall(answer)}


def loose_cited_ids(answer):

    return {int(match) for match in LOOSE_CITATION.findall(answer)}


def validate_answer(answer, context_ids, *, tool_ids=None):
    """
    فحص صافي لمخرَج الموديل:
    - الرفض صالح فقط إذا طابق جملة الرفض حرفيًا بعد إزالة الفراغات وخلا من الأرقام.
    - جمع جملة الرفض مع أي نص أو رقم آخر يُعدّ رفضًا مختلطًا.
    - أي رقم حديث (بصيغة رسمية أو حرة، بأرقام عربية أو هندية) خارج السياق أو
      خارج مخرجات أدوات هذا الطلب (عند تمرير tool_ids) يُرفض.
    - أي إجابة غير رافضة لا تحوي استشهادًا بالصيغة المطلوبة تُرفض لغياب المصدر.
    """

    stripped = (answer or "").strip()
    allowed_ids = set(context_ids)
    if tool_ids is not None:
        allowed_ids &= set(tool_ids)

    if _VALID_REFUSAL.fullmatch(stripped) and not _DIGIT.search(stripped):
        return VALID_REFUSAL

    if REFUSAL in stripped:
        return MIXED_REFUSAL

    strict_ids = cited_ids(stripped)
    loose_ids = loose_cited_ids(stripped)

    if (strict_ids | loose_ids) - allowed_ids:
        return OUT_OF_CONTEXT_CITATION

    if not strict_ids:
        return MISSING_CITATION

    return VALID_ANSWER


def validate_narrator_names(answer, isnad_results=(), *, lexicon=None, db_path=None):
    """Return any narrator names in ``answer`` absent from ``get_isnad`` results."""
    from sanad_graph import GraphNotBuiltError
    try:
        from src.sanad_graph import GraphNotBuiltError as SrcGraphNotBuiltError
        from src.sanad_names import NarratorLexicon, find_disallowed_narrators, load_narrator_lexicon
    except ImportError:
        SrcGraphNotBuiltError = GraphNotBuiltError
        from sanad_names import NarratorLexicon, find_disallowed_narrators, load_narrator_lexicon

    active_lex = lexicon
    if active_lex is None:
        try:
            active_lex = load_narrator_lexicon(str(db_path) if db_path is not None else None)
        except (GraphNotBuiltError, SrcGraphNotBuiltError, FileNotFoundError):
            active_lex = NarratorLexicon({})
    return find_disallowed_narrators(answer or "", isnad_results or (), active_lex)


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


SANAD_HEADER = "السند (من قاعدة بيانات السند):"

SANAD_STATUS_ARABIC = {
    NO_ACCEPTED_MIS_LINK: "لا يوجد ربط مقبول لهذا الحديث في قاعدة بيانات السند.",
    LINKED_BUT_NO_RECORDED_ISNAD: "الحديث مرتبط في قاعدة البيانات ولكن لا يوجد له إسناد مسجّل.",
    INVALID_LOCAL_HADITH_ID: "رقم الحديث غير موجود في قاعدة بيانات السند.",
}

_last_answer_details = threading.local()


def ordered_cited_ids(answer):
    """Return strictly cited hadith IDs in order of first appearance, deduplicated."""

    seen = set()
    ordered = []
    for match in CITATION.findall(answer or ""):
        hid = int(match)
        if hid not in seen:
            seen.add(hid)
            ordered.append(hid)
    return ordered


def attach_sanad(hadith_ids, db_path=None):
    """Fetch recorded sanad chains from SQLite for each cited hadith ID.

    Opens one DB connection per request. Keeps exact sanad_context status for
    unlinked hadiths or hadiths without a recorded isnad, and returns
    ([], error_text) if the graph is missing or a query fails.
    """

    if not hadith_ids:
        return [], None

    conn = None
    try:
        conn = open_graph() if db_path is None else open_graph(db_path)
        entries = []
        for hid in hadith_ids:
            ctx = context_for_local_hadith(conn, hid)
            isnads = [
                [
                    {
                        "chain_position": narrator["chain_position"],
                        "name_ar_mapped": narrator["name_ar_mapped"],
                    }
                    for narrator in isnad["narrators"]
                ]
                for isnad in ctx.get("isnads", [])
            ]
            entries.append(
                {
                    "hadith_id": hid,
                    "status": ctx["status"],
                    "isnad_count": ctx["isnad_count"],
                    "isnads": isnads,
                }
            )
        return entries, None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"
    finally:
        if conn is not None:
            conn.close()


def format_sanad_chain(chain):
    """Format one chain from Muslim's teacher down to the Companion, joined with ' ← '."""

    ordered = sorted(chain, key=lambda n: n["chain_position"], reverse=True)
    return " ← ".join(
        n.get("name_ar_mapped") or n.get("name_ar") or ""
        for n in ordered
    )


def format_sanad_section(sanad, sanad_error=None):
    """Format the CLI sanad display block under the answer."""

    if not sanad and not sanad_error:
        return ""

    lines = [SANAD_HEADER]
    if sanad_error:
        lines.append(f"- تعذّر قراءة قاعدة بيانات السند ({sanad_error})")
        return "\n".join(lines)

    for entry in sanad:
        hid = entry["hadith_id"]
        isnads = entry.get("isnads") or []
        if isnads:
            chain_text = format_sanad_chain(isnads[0])
            extra = max(0, entry.get("isnad_count", len(isnads)) - 1)
            extra_text = f" (+{extra} طرق أخرى)" if extra > 0 else ""
            lines.append(f"- حديث رقم {hid}: {chain_text}{extra_text}")
        else:
            status = entry.get("status", "")
            status_ar = SANAD_STATUS_ARABIC.get(
                status, f"لا يوجد إسناد مسجّل ({status})."
            )
            lines.append(f"- حديث رقم {hid}: {status_ar}")
    return "\n".join(lines)


def _resolve_use_agent(retriever, use_agent=None):
    """Resolve whether to execute via tool-calling agent or legacy single-pass RAG."""
    if use_agent is not None:
        return bool(use_agent)
    env_val = os.environ.get("MUSNAD_AGENT", "").strip()
    if env_val:
        try:
            from src.pipeline import resolve_agent_enabled
        except ImportError:
            from pipeline import resolve_agent_enabled
        return resolve_agent_enabled(env_val)
    return bool(getattr(retriever, "agent_enabled", False))


def _call_agent(question, retriever, **kwargs):
    try:
        from src.agent import run_agent
    except ImportError:
        from agent import run_agent
    return run_agent(question, retriever, **kwargs)


def answer_with_details(
    question,
    retriever,
    k=5,
    enforce_citations=True,
    self_correct=False,
    model=MODEL,
    sanad_db_path=None,
    use_agent=None,
):
    """
    بترجع dict فيه الإجابة النهائية **والمحاولة الخام**.

    القياس بيحصل على المحاولة الخام: لو قِسنا بعد التصفية
    هتطلع صفر أخطاء دايمًا بحكم البناء، وده رقم بلا معنى.
    """

    if _resolve_use_agent(retriever, use_agent=use_agent):
        return _call_agent(
            question,
            retriever,
            k=k,
            enforce_citations=enforce_citations,
            model=model,
            sanad_db_path=sanad_db_path,
            fallback_fn=lambda: answer_with_details(
                question,
                retriever,
                k=k,
                enforce_citations=enforce_citations,
                self_correct=self_correct,
                model=model,
                sanad_db_path=sanad_db_path,
                use_agent=False,
            ),
        )

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
            "sanad": [],
            "sanad_error": None,
            "invalid_citation_attempt": False,
            "missing_citation_attempt": False,
            "loose_out_of_context_attempt": False,
            "mixed_refusal_attempt": False,
            "regenerated": False,
            "rewritten": rewritten,
            "retried": retried,
        }

    context_ids = {chunk["hadith_id"] for chunk in chunks}

    system_instruction = build_system_prompt(format_context(chunks))

    raw = generate(question, system_instruction=system_instruction, model=model)

    status = validate_answer(raw, context_ids)
    invalid = bool(cited_ids(raw) - context_ids)
    missing_citation = status == MISSING_CITATION
    loose_out_of_context = bool(
        (loose_cited_ids(raw) - cited_ids(raw)) - context_ids
    )
    mixed_refusal = status == MIXED_REFUSAL

    answer = raw
    regenerated = False
    final_status = status

    if status not in (VALID_ANSWER, VALID_REFUSAL) and enforce_citations:

        # مرة واحدة بس. لو فشل تاني بنرفض — إجابة بلا مصدر
        # في المجال ده أسوأ من الاعتراف بعدم المعرفة.
        regenerated = True

        answer = generate(
            CORRECTIONS[status],
            system_instruction=system_instruction,
            history=[("user", question), ("model", raw)],
            model=model,
        )

        final_status = validate_answer(answer, context_ids)
        if final_status not in (
            VALID_ANSWER,
            VALID_REFUSAL,
        ):
            answer = REFUSAL
            final_status = VALID_REFUSAL

    sanad = []
    sanad_error = None
    if final_status == VALID_ANSWER:
        sanad, sanad_error = attach_sanad(
            ordered_cited_ids(answer), db_path=sanad_db_path
        )

    return {
        "answer": answer,
        "raw": raw,
        "chunks": chunks,
        "sanad": sanad,
        "sanad_error": sanad_error,
        "invalid_citation_attempt": invalid,
        "missing_citation_attempt": missing_citation,
        "loose_out_of_context_attempt": loose_out_of_context,
        "mixed_refusal_attempt": mixed_refusal,
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
    _last_answer_details.details = details

    return details["answer"], details["chunks"]


DEFAULT_K = 5


def build_pipeline():

    from pipeline import build_pipeline as _build_pipeline

    return _build_pipeline()


def load_questions(path=QUESTIONS_PATH):

    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def format_retrieved_chunk(chunk):

    chapter = (chunk.get("metadata") or {}).get("chapter_arabic", "")
    score = chunk.get("score")
    score_text = (
        f" | rerank score: {score:.4f}" if score is not None else ""
    )

    return (
        f"Rank: {chunk['rank']} | "
        f"Hadith ID: {chunk['hadith_id']} | "
        f"Chapter: {chapter}"
        f"{score_text}"
    )


def main():

    retriever = build_pipeline()

    for question in load_questions():

        print("=" * 80)
        print(question)

        _last_answer_details.details = None
        answer, chunks = answer_question(question, retriever, k=DEFAULT_K)
        details = getattr(_last_answer_details, "details", None)
        _last_answer_details.details = None

        print("\nAnswer:")
        print(answer)

        if details is not None:
            sanad = details.get("sanad", [])
            sanad_error = details.get("sanad_error")
        else:
            context_ids = {chunk["hadith_id"] for chunk in chunks}
            if validate_answer(answer, context_ids) == VALID_ANSWER:
                sanad, sanad_error = attach_sanad(ordered_cited_ids(answer))
            else:
                sanad, sanad_error = [], None

        sanad_block = format_sanad_section(sanad, sanad_error=sanad_error)
        if sanad_block:
            print(f"\n{sanad_block}")

        print("\nRetrieved Hadiths:")

        for chunk in chunks:
            print(format_retrieved_chunk(chunk))


if __name__ == "__main__":
    main()
