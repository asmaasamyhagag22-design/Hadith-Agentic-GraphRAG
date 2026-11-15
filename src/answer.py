import argparse
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import contextmanager
import logging
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
MAX_TIMEOUT_RETRIES = 1
INITIAL_BACKOFF_SECONDS = 4
TIMEOUT_RETRY_BACKOFF_SECONDS = 1.0
GENERATE_TIMEOUT_MS = int(os.environ.get("MUSNAD_GENERATE_TIMEOUT_MS", "45000"))
GENERATION_TIMEOUT_MESSAGE = (
    "استغرقت خدمة التوليد وقتًا أطول من المهلة المحددة (45 ثانية) ولم تكتمل بعد إعادة المحاولة. "
    "يُرجى إعادة المحاولة مرة أخرى بعد قليل."
)

_logger = logging.getLogger("musnad.answer")
_client = None
_thread_clients = threading.local()
_generation_trace_ctx = threading.local()
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


class GenerationTimeoutError(TimeoutError):
    """Raised when a generation model call exceeds the per-call deadline on both attempts."""

    def __init__(
        self,
        message: str = GENERATION_TIMEOUT_MESSAGE,
        *,
        timeout_s: float | None = None,
        attempts: int = 2,
        model: str = MODEL,
    ) -> None:
        super().__init__(message)
        self.timeout_s = (
            GENERATE_TIMEOUT_MS / 1000.0 if timeout_s is None else float(timeout_s)
        )
        self.attempts = int(attempts)
        self.model = model


@contextmanager
def _generation_trace_context(trace=None):
    prev = getattr(_generation_trace_ctx, "current", None)
    state = {"trace": trace, "timeout_retries": 0, "calls": 0}
    _generation_trace_ctx.current = state
    try:
        yield state
    finally:
        _generation_trace_ctx.current = prev


_TIMEOUT_MSG_RE = re.compile(
    r"\b(?:timed out|deadline[_ ]exceeded|gateway timeout|request timeout|504)\b",
    re.IGNORECASE,
)


def is_timeout_exception(exc: Exception) -> bool:
    """Return True when ``exc`` represents an HTTP/RPC or deadline timeout."""
    if isinstance(exc, TimeoutError):
        return True
    if any(
        "timeout" in cls.__name__.lower() or "deadline" in cls.__name__.lower()
        for cls in type(exc).__mro__
    ):
        return True
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code == 504:
        return True
    if isinstance(exc, (TypeError, ValueError, AttributeError, KeyError, RuntimeError)):
        return False
    return bool(_TIMEOUT_MSG_RE.search(str(exc)))


def _invoke_with_wall_timeout(fn, timeout_s: float | None, model: str):
    if timeout_s is None or timeout_s <= 0:
        return fn()
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(fn)
        return future.result(timeout=timeout_s)
    except FutureTimeoutError as exc:
        raise TimeoutError(
            f"Model generation call to {model} timed out after {timeout_s:.1f}s"
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def run_model_call_with_timeout_and_retry(
    invoke_once,
    *,
    model: str,
    timeout_s: float | None = None,
    max_timeout_retries: int = MAX_TIMEOUT_RETRIES,
    max_transient_attempts: int = MAX_ATTEMPTS,
    transient_retry_predicate=None,
    initial_backoff_s: float = INITIAL_BACKOFF_SECONDS,
    timeout_backoff_s: float | None = None,
    trace=None,
    ctx_state: dict | None = None,
):
    """Execute one logical model turn with a per-call timeout and single timeout retry."""
    eff_timeout_s = (
        float(timeout_s)
        if timeout_s is not None
        else (GENERATE_TIMEOUT_MS / 1000.0 if GENERATE_TIMEOUT_MS > 0 else None)
    )
    if timeout_backoff_s is not None:
        eff_timeout_backoff = float(timeout_backoff_s)
    elif eff_timeout_s is not None:
        eff_timeout_backoff = min(float(TIMEOUT_RETRY_BACKOFF_SECONDS), eff_timeout_s)
    else:
        eff_timeout_backoff = float(TIMEOUT_RETRY_BACKOFF_SECONDS)

    active_ctx = (
        ctx_state if ctx_state is not None else getattr(_generation_trace_ctx, "current", None)
    )
    active_trace = trace if trace is not None else (active_ctx.get("trace") if active_ctx else None)

    timeout_failures = 0
    transient_failures = 0
    delay = float(initial_backoff_s)
    total_calls = 0

    while True:
        total_calls += 1
        if active_ctx is not None:
            active_ctx["calls"] = int(active_ctx.get("calls", 0)) + 1
        t_call0 = time.perf_counter()
        try:
            return _invoke_with_wall_timeout(invoke_once, eff_timeout_s, model)
        except Exception as exc:
            call_ms = (time.perf_counter() - t_call0) * 1000.0
            if is_timeout_exception(exc):
                if timeout_failures < max_timeout_retries:
                    timeout_failures += 1
                    if active_ctx is not None:
                        active_ctx["timeout_retries"] = (
                            int(active_ctx.get("timeout_retries", 0)) + 1
                        )
                    _logger.warning(
                        "Generation call timed out after %.1fs (attempt %d, retrying once): %s",
                        eff_timeout_s or 0.0,
                        total_calls,
                        exc,
                    )
                    if active_trace is not None:
                        active_trace.record(
                            "generation",
                            duration_ms=call_ms,
                            model=model,
                            attempts=total_calls,
                            pro_calls=0,
                            event_kind="timeout_retry",
                            timeout_s=eff_timeout_s,
                            timed_out=True,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    if eff_timeout_backoff > 0:
                        time.sleep(eff_timeout_backoff)
                    continue

                _logger.error(
                    "Generation call timed out twice after %.1fs (%d attempts): %s",
                    eff_timeout_s or 0.0,
                    total_calls,
                    exc,
                )
                raise GenerationTimeoutError(
                    GENERATION_TIMEOUT_MESSAGE,
                    timeout_s=eff_timeout_s or 0.0,
                    attempts=total_calls,
                    model=model,
                ) from exc

            should_retry = (
                transient_retry_predicate(exc)
                if transient_retry_predicate is not None
                else True
            )
            transient_failures += 1
            if not should_retry or transient_failures >= max_transient_attempts:
                raise
            time.sleep(delay)
            delay *= 2


def get_client(location=None, *, timeout_ms=None):

    global _client

    resolved_timeout_ms = GENERATE_TIMEOUT_MS if timeout_ms is None else int(timeout_ms)
    http_opts = types.HttpOptions(timeout=resolved_timeout_ms) if resolved_timeout_ms else None

    if location == "global":
        client = getattr(_thread_clients, "global_client", None)
        if client is None or (timeout_ms is not None):
            client = genai.Client(location="global", http_options=http_opts)
            if timeout_ms is None:
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


def generate(
    prompt,
    system_instruction=None,
    history=(),
    model=MODEL,
    *,
    timeout_s=None,
):
    """
    نداء واحد لـ Gemini مع مهلة 45 ثانية وإعادة محاولة واحدة عند انتهاء المهلة،
    وانتظار متصاعد للأخطاء العابرة الأخرى.

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

    rr_lock = threading.Lock()
    timeout_ms_override = int(round(float(timeout_s) * 1000)) if timeout_s is not None else None

    def _invoke_once():
        if is_global_model:
            client = get_client(location="global", timeout_ms=timeout_ms_override)
        elif _client is not None:
            client = _client
        else:
            with rr_lock:
                loc = _RR_LOCATIONS[_rr_counter % len(_RR_LOCATIONS)]
                _rr_counter += 1
            client = get_client(location=loc, timeout_ms=timeout_ms_override)

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        return (response.text or "").strip()

    return run_model_call_with_timeout_and_retry(
        _invoke_once,
        model=model,
        timeout_s=timeout_s,
    )


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

_HSPACE = r"[^\S\r\n]"
# إشارات غير منضبطة لرقم حديث (مثل: "حديث 999"، "حديث رقم: 999"، "مسلم 999"، "مسلم، 999"، "مسلم، رقم 999")
# تقتصر الفواصل على الفراغ الأفقي أو النقطتين أو الفاصلة العربية دون عبور الأسطر حتى لا تلتقط ترقيم القوائم.
LOOSE_CITATION = re.compile(
    rf"(?:حديث(?:{_HSPACE}*رقم)?|مسلم(?:{_HSPACE}*[،,])?(?:{_HSPACE}*رقم)?)(?:{_HSPACE}|[:،])*(\d+)"
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


def attach_sanad(hadith_ids, db_path=None, trace=None):
    """Fetch recorded sanad chains from SQLite for each cited hadith ID.

    Opens one DB connection per request. Keeps exact sanad_context status for
    unlinked hadiths or hadiths without a recorded isnad, and returns
    ([], error_text) if the graph is missing or a query fails.
    """

    if not hadith_ids:
        return [], None

    conn = None
    t_open0 = time.perf_counter() if trace is not None else 0.0
    try:
        conn = open_graph() if db_path is None else open_graph(db_path)
        entries = []
        for hid in hadith_ids:
            t_h0 = time.perf_counter() if trace is not None else 0.0
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
            if trace is not None:
                hid_ms = (time.perf_counter() - t_h0) * 1000.0
                trace.record_sanad(
                    hadith_id=hid,
                    status=ctx["status"],
                    isnad_count=ctx["isnad_count"],
                    ms=hid_ms,
                    source="SQLite sanad graph",
                )
        return entries, None
    except Exception as exc:
        err_text = f"{type(exc).__name__}: {exc}"
        if trace is not None:
            err_ms = (time.perf_counter() - t_open0) * 1000.0
            trace.record_sanad(
                hadith_id=None,
                status="error",
                isnad_count=0,
                ms=err_ms,
                error=err_text,
                source="SQLite sanad graph",
            )
        return [], err_text
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


def _resolve_agent_enabled_fn():
    try:
        from src.pipeline import resolve_agent_enabled
    except ImportError:
        from pipeline import resolve_agent_enabled
    return resolve_agent_enabled


def _resolve_use_agent(retriever, use_agent=None, question=None, trace=None):
    """Resolve whether to execute via tool-calling agent or legacy single-pass RAG."""
    if use_agent is not None:
        if isinstance(use_agent, bool):
            if trace is not None:
                trace.record_router(
                    decision="chain" if use_agent else "text",
                    source="override",
                    probability=None,
                    duration_ms=0.0,
                    mode="on" if use_agent else "off",
                )
            return use_agent
        fn = _resolve_agent_enabled_fn()
        if trace is not None:
            return fn(use_agent, question=question, retriever=retriever, trace=trace)
        return fn(use_agent, question=question, retriever=retriever)
    env_val = os.environ.get("MUSNAD_AGENT", "").strip()
    if env_val:
        fn = _resolve_agent_enabled_fn()
        if trace is not None:
            return fn(env_val, question=question, retriever=retriever, trace=trace)
        return fn(env_val, question=question, retriever=retriever)
    if hasattr(retriever, "agent_mode"):
        fn = _resolve_agent_enabled_fn()
        if trace is not None:
            return fn(getattr(retriever, "agent_mode"), question=question, retriever=retriever, trace=trace)
        return fn(getattr(retriever, "agent_mode"), question=question, retriever=retriever)
    enabled = bool(getattr(retriever, "agent_enabled", False))
    if trace is not None:
        trace.record_router(
            decision="chain" if enabled else "text",
            source="override",
            probability=None,
            duration_ms=0.0,
            mode="on" if enabled else "off",
        )
    return enabled


def _call_agent(question, retriever, **kwargs):
    try:
        from src.agent import run_agent
    except ImportError:
        from agent import run_agent
    return run_agent(question, retriever, **kwargs)


def _format_trace_top5(chunks):
    return [
        {
            "rank": chunk.get("rank", idx + 1),
            "hadith_id": int(chunk["hadith_id"]),
            "chapter": (chunk.get("metadata") or {}).get("chapter_arabic", ""),
        }
        for idx, chunk in enumerate((chunks or [])[:5])
    ]


def answer_with_details(
    question,
    retriever,
    k=5,
    enforce_citations=True,
    self_correct=False,
    model=MODEL,
    sanad_db_path=None,
    use_agent=None,
    trace=None,
    _skip_router_trace=False,
):
    """
    بترجع dict فيه الإجابة النهائية **والمحاولة الخام**.

    القياس بيحصل على المحاولة الخام: لو قِسنا بعد التصفية
    هتطلع صفر أخطاء دايمًا بحكم البناء، وده رقم بلا معنى.
    """

    active_trace_for_router = None if _skip_router_trace else trace
    if _resolve_use_agent(
        retriever,
        use_agent=use_agent,
        question=question,
        trace=active_trace_for_router,
    ):
        agent_kwargs = dict(
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
                trace=trace,
                _skip_router_trace=True,
            ),
        )
        if trace is not None:
            agent_kwargs["trace"] = trace
        return _call_agent(question, retriever, **agent_kwargs)

    rewritten = None
    retried = False

    t_ret0 = time.perf_counter() if trace is not None else 0.0
    if self_correct:
        chunks, rewritten, retried = retrieve_with_self_correction(
            question, retriever, k
        )
    else:
        chunks = retriever.search(question, k=k)
    if trace is not None:
        ret_ms = (time.perf_counter() - t_ret0) * 1000.0
        call_stats = getattr(retriever, "last_call_stats", None) or {}
        trace.record_retrieval(
            hyde_text=getattr(retriever, "last_hyde_text", None),
            top5=_format_trace_top5(chunks),
            legacy_fallback=bool(getattr(retriever, "last_used_fallback", False)),
            duration_ms=ret_ms,
            **call_stats,
        )

    if not chunks:
        if trace is not None:
            trace.record_validation(
                status=VALID_REFUSAL.value,
                retry_reason=None,
                refusal_reason="empty_retrieval",
                duration_ms=0.0,
            )
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

    t_gen0 = time.perf_counter() if trace is not None else 0.0
    gen_ms = 0.0
    val_ms = 0.0
    regenerated = False

    with _generation_trace_context(trace) as gen_ctx:
        try:
            raw = generate(question, system_instruction=system_instruction, model=model)
            if trace is not None:
                gen_ms = (time.perf_counter() - t_gen0) * 1000.0

            t_val0 = time.perf_counter() if trace is not None else 0.0
            status = validate_answer(raw, context_ids)
            invalid = bool(cited_ids(raw) - context_ids)
            missing_citation = status == MISSING_CITATION
            loose_out_of_context = bool(
                (loose_cited_ids(raw) - cited_ids(raw)) - context_ids
            )
            mixed_refusal = status == MIXED_REFUSAL
            if trace is not None:
                val_ms = (time.perf_counter() - t_val0) * 1000.0

            answer = raw
            final_status = status

            if status not in (VALID_ANSWER, VALID_REFUSAL) and enforce_citations:

                # مرة واحدة بس. لو فشل تاني بنرفض — إجابة بلا مصدر
                # في المجال ده أسوأ من الاعتراف بعدم المعرفة.
                regenerated = True

                t_regen0 = time.perf_counter() if trace is not None else 0.0
                answer = generate(
                    CORRECTIONS[status],
                    system_instruction=system_instruction,
                    history=[("user", question), ("model", raw)],
                    model=model,
                )
                if trace is not None:
                    gen_ms += (time.perf_counter() - t_regen0) * 1000.0

                t_val1 = time.perf_counter() if trace is not None else 0.0
                final_status = validate_answer(answer, context_ids)
                if final_status not in (
                    VALID_ANSWER,
                    VALID_REFUSAL,
                ):
                    answer = REFUSAL
                    final_status = VALID_REFUSAL
                if trace is not None:
                    val_ms += (time.perf_counter() - t_val1) * 1000.0
        except GenerationTimeoutError as exc:
            if trace is not None:
                timeout_retries = max(1, int(gen_ctx.get("timeout_retries", 0)))
                attempts_made = max(int(gen_ctx.get("calls", 0)), exc.attempts)
                trace.record_generation(
                    model=model,
                    attempts=attempts_made,
                    duration_ms=(time.perf_counter() - t_gen0) * 1000.0,
                    pro_calls=attempts_made,
                    timeout_retries=timeout_retries,
                    timed_out=True,
                    timeout_s=exc.timeout_s,
                    status="timeout",
                    error=f"{type(exc).__name__}: {exc}",
                )
            raise

    if trace is not None:
        timeout_retries = int(gen_ctx.get("timeout_retries", 0))
        base_calls = 2 if regenerated else 1
        gen_extra = (
            {"timeout_retries": timeout_retries} if timeout_retries > 0 else {}
        )
        trace.record_generation(
            model=model,
            attempts=base_calls + timeout_retries,
            duration_ms=gen_ms,
            pro_calls=base_calls + timeout_retries,
            regenerated=regenerated,
            **gen_extra,
        )
        refusal_reason = None
        if final_status == VALID_REFUSAL:
            refusal_reason = (
                "validation_failed_after_retry" if regenerated else "model_refused"
            )
        trace.record_validation(
            status=final_status.value,
            retry_reason=status.value if regenerated else None,
            refusal_reason=refusal_reason,
            duration_ms=val_ms,
        )

    sanad = []
    sanad_error = None
    if final_status == VALID_ANSWER:
        sanad, sanad_error = attach_sanad(
            ordered_cited_ids(answer),
            db_path=sanad_db_path,
            trace=trace,
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
    trace=None,
):

    kwargs = dict(
        k=k,
        enforce_citations=enforce_citations,
        self_correct=self_correct,
    )
    if trace is not None:
        kwargs["trace"] = trace
    details = answer_with_details(question, retriever, **kwargs)
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
    rank = chunk.get("rank")
    rank_text = f"Rank: {rank} | " if rank is not None else ""
    score = chunk.get("score")
    score_text = (
        f" | rerank score: {score:.4f}" if score is not None else ""
    )

    return (
        f"{rank_text}"
        f"Hadith ID: {chunk['hadith_id']} | "
        f"Chapter: {chapter}"
        f"{score_text}"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Musnad Sahih Muslim CLI")
    parser.add_argument(
        "-q",
        "--question",
        action="append",
        dest="questions",
        help="Question(s) to answer directly instead of reading QUESTIONS_PATH.",
    )
    parser.add_argument(
        "--questions-file",
        default=None,
        help="Optional path to a newline-delimited questions file.",
    )
    args = parser.parse_args([] if argv is None else argv)

    retriever = build_pipeline()
    if args.questions:
        questions = [q.strip() for q in args.questions if q.strip()]
    elif args.questions_file:
        questions = load_questions(Path(args.questions_file))
    else:
        questions = load_questions()

    for question in questions:

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
    main(sys.argv[1:])
