"""Tool-calling agent over Sahih Muslim text retrieval and the MIS Sanad Graph.

Uses ``gemini-4-argon`` with two deterministic tools bounded to at most 3 tool
calls per request:
- ``search_hadith(query)`` -> top-5 results from the default retrieval pipeline
  (``hadith_id``, ``matn``, ``chapter``).
- ``get_isnad(hadith_id)`` -> ``sanad_context.context_for_local_hadith`` output
  from SQLite.

Validates every cited hadith ID against IDs returned by tools in the request,
validates every mentioned narrator name against ``get_isnad`` results in the
request, regenerates once on failure, refuses if still invalid, attaches
deterministic sanad chains (Phase A), and falls back cleanly to the non-agent
pipeline on error or timeout.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any, Callable

from google.genai import types

from src.config import API_TIMEOUT_MS
from src.experiment_variants import variant_text
from src.sanad_context import (
    INVALID_LOCAL_HADITH_ID,
    LINKED_WITH_RECORDED_ISNAD,
    context_for_local_hadith,
    open_graph,
)
from src.sanad_graph import GRAPH_DB_PATH, GraphNotBuiltError
from src.sanad_names import NarratorLexicon, find_disallowed_narrators, load_narrator_lexicon

MAX_TOOL_CALLS = 3
DEFAULT_TOOL_TIMEOUT_S = API_TIMEOUT_MS / 1000.0
EMPTY_LEXICON = NarratorLexicon({})

AGENT_SYSTEM_INSTRUCTION = """أنت مساعد بحث حديثي متخصص في «صحيح مسلم» ومتصل بقاعدة بيانات السند الموثقة.

لديك أداتان فقط:
1. `search_hadith(query)`: للبحث الدلالي في متون صحيح مسلم وإرجاع أعلى 5 أحاديث (`hadith_id`, `chapter`, `matn`).
2. `get_isnad(hadith_id)`: للاستعلام من قاعدة بيانات السند عن أسانيد حديث محدد (`hadith_id`). تعيد الحالات الدقيقة وعدد الأسانيد `isnad_count` وسلاسل الرواة مرتبةً بحيث:
   - `chain_position = 1` (`companion_pos_1`) هو الصحابي الجليل في بداية السند من جهة النبي صلى الله عليه وسلم.
   - آخر موضع في السلسلة (`muslim_teacher_last`) هو شيخ الإمام مسلم المباشر الذي روى عنه الحديث.

قواعد التوجيه الصارمة (الحد الأقصى 3 استدعاءات للأدوات في الطلب):
1. الأسئلة النصية / الفقهية العامة (دون سؤال عن الرواة أو الإسناد): استدعِ `search_hadith` مرة واحدة بصياغة عربية واضحة، ثم أجب مباشرة من المتون العائدة دون استدعاء `get_isnad`.
2. أسئلة السند والرواة التي تذكر رقم الحديث في السؤال (مثل «حديث رقم 7296»): استدعِ `get_isnad(hadith_id)` مباشرةً بالرقم المذكور دون استدعاء `search_hadith`.
3. أسئلة السند التي تصف الحديث بموضوعه أو طرف متنه دون ذكر رقمه (مثل «من روى حديث كافل اليتيم»): استدعِ `search_hadith` أولًا لتحديد `hadith_id`، ثم استدعِ `get_isnad(hadith_id)` للحديث المطابق.

قواعد الصدق والتوثيق الصارمة:
1. أجب بالعربية الفصحى فقط وبإيجاز واضح.
2. لا تكتب أي اسم راوٍ أو صحابي أو شيخ إسناد في إجابتك ما لم يرد نصًا في مخرجات `get_isnad` لهذا الطلب. عند الإجابة عن الأسئلة الفقهية والمتنية عبر `search_hadith` فقط، اشرح الحكم أو المعنى أو انقل المتن دون تسمية رواة أو صحابة.
3. إذا سُئلت: «هل ورد الراوي X في سند حديث رقم N؟» ولم يكن X موجودًا في أسانيد `get_isnad` العائدة، فأجب بوضوح: «لا، لم يرد الراوي المذكور في أسانيد هذا الحديث (المصدر: صحيح مسلم، حديث رقم N)» دون تكرار اسم X غير الموجود في السند.
4. إذا أعادت `get_isnad` حالة غير مرتبطة أو `isnad_count == 0`، فلا تخمّن أي راوٍ ولا عدد، وصرّح بأنه لا يوجد لهذا الحديث إسناد مسجل في قاعدة بيانات السند مع الاستشهاد برقمه `(المصدر: صحيح مسلم، حديث رقم N)`.
5. لا تخترع أحكام جرح وتعديل (`ثقة`، `صدوق`، `ضعيف`، `إسناده صحيح`، أو حكم ابن حجر). إذا طُلب منك الراوي مع حكم رواته فأجب بالرواة العائدين من `get_isnad` مع التصريح بأن أحكام الجرح والتعديل غير متوفرة في قاعدة البيانات. وإذا طُلب حكم ابن حجر أو الجرح والتعديل وحده، اذكر أن أحكام الجرح والتعديل غير متوفرة في قاعدة البيانات ولا تختلق حكمًا.
6. إذا لم تجد الإجابة في نتائج الأدوات نهائيًا، اكتب هذه العبارة حرفيًا وحدها دون أي نص أو رقم حديث:
"المصادر المتاحة لا تجيب عن هذا السؤال"
7. في غير حالة الرفض التام، يجب أن تستشهد برقم كل حديث اعتمدت عليه بالصيغة:
   (المصدر: صحيح مسلم، حديث رقم XXXX)
   ولا تستشهد أبدًا بأي رقم حديث لم ترجعه أدوات هذا الطلب."""


def _search_hadith_declaration() -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name="search_hadith",
        description=(
            "Search Sahih Muslim hadiths by Arabic text or topic using the default retrieval pipeline. "
            "Returns top 5 matching hadiths with hadith_id, chapter, and matn (hadith body without isnad)."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Arabic search query describing the hadith text or topic.",
                }
            },
            "required": ["query"],
        },
    )


def _get_isnad_declaration() -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name="get_isnad",
        description=(
            "Look up recorded isnad chains and linkage status for a local Sahih Muslim hadith_id "
            "in the verified SQLite Sanad Graph. Returns status, isnad_count, and ordered chains where "
            "chain_position=1 is the Companion (first narrator) and the last position is Muslim's direct teacher."
        ),
        parameters_json_schema={
            "type": "object",
            "properties": {
                "hadith_id": {
                    "type": "integer",
                    "description": "Local Sahih Muslim hadith ID (e.g. 7296 or 12068).",
                }
            },
            "required": ["hadith_id"],
        },
    )


def build_agent_tools() -> types.Tool:
    """Build Gemini tool declaration bundle for the Musnad agent."""
    return types.Tool(
        function_declarations=[
            _search_hadith_declaration(),
            _get_isnad_declaration(),
        ]
    )


def _chunk_matn(chunk: dict[str, Any]) -> str:
    if "text" in chunk:
        return variant_text(chunk, "matn")
    return str(chunk.get("matn") or "")


def _format_isnad_for_model(ctx: dict[str, Any]) -> dict[str, Any]:
    """Return a concise, LLM-friendly projection of ``sanad_context``."""
    compact_chains = []
    for ch in ctx.get("isnads") or ():
        narrators = ch.get("narrators") or ()
        compact_chains.append(
            {
                "sanad_no": ch.get("sanad_no"),
                "companion_pos_1": narrators[0].get("name_ar_mapped") if narrators else None,
                "muslim_teacher_last": narrators[-1].get("name_ar_mapped") if narrators else None,
                "narrators": [
                    {
                        "chain_position": n.get("chain_position"),
                        "narrator_id": n.get("narrator_id"),
                        "name_ar_mapped": n.get("name_ar_mapped"),
                    }
                    for n in narrators
                ],
            }
        )
    local_meta = ctx.get("local_hadith") or {}
    return {
        "hadith_id": ctx.get("local_hadith_id"),
        "status": ctx.get("status"),
        "isnad_count": ctx.get("isnad_count", 0),
        "chapter": local_meta.get("chapter_ar"),
        "isnads": compact_chains,
    }


def _run_with_timeout(fn: Callable[[], Any], timeout_s: float) -> Any:
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(fn)
        return future.result(timeout=timeout_s)
    except FutureTimeoutError as exc:
        raise TimeoutError(f"Tool execution timed out after {timeout_s:.1f}s") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _extract_response_parts(response: Any) -> tuple[list[Any], str, Any]:
    """Safely extract (function_calls, visible_text, candidate_content) from a response."""
    function_calls = list(getattr(response, "function_calls", None) or ())
    candidate_content = None
    candidates = getattr(response, "candidates", None) or ()
    text_pieces: list[str] = []
    if candidates:
        candidate_content = getattr(candidates[0], "content", None)
        if candidate_content is not None:
            for part in getattr(candidate_content, "parts", None) or ():
                part_text = getattr(part, "text", None)
                is_thought = bool(getattr(part, "thought", False))
                if part_text and not is_thought:
                    text_pieces.append(part_text)
    if text_pieces:
        text = "".join(text_pieces).strip()
    elif not function_calls:
        text = str(getattr(response, "text", None) or "").strip()
    else:
        text = ""
    return function_calls, text, candidate_content


def _coerce_hadith_id(raw_id: Any) -> int:
    if isinstance(raw_id, bool):
        raise ValueError(f"Invalid hadith_id boolean: {raw_id!r}")
    if isinstance(raw_id, (int, float)):
        return int(raw_id)
    if isinstance(raw_id, str) and raw_id.strip().isdigit():
        return int(raw_id.strip())
    raise ValueError(f"Invalid hadith_id: {raw_id!r}")


def _resolve_lexicon(
    lexicon: NarratorLexicon | None,
    sanad_db_path: Path | str | None,
) -> NarratorLexicon:
    if lexicon is not None:
        return lexicon
    try:
        key = str(sanad_db_path) if sanad_db_path is not None else None
        return load_narrator_lexicon(key)
    except GraphNotBuiltError:
        return EMPTY_LEXICON


def _build_correction_prompt(
    validation_status: str,
    disallowed_narrators: list[str],
    corrections: dict[str, str],
) -> str:
    parts: list[str] = []
    if validation_status in corrections:
        parts.append(corrections[validation_status])
    if disallowed_narrators:
        joined = "، ".join(disallowed_narrators)
        parts.append(
            f"خطأ تحقق: ذكرت أسماء رواة غير واردة في مخرجات أداة get_isnad لهذا الطلب ({joined}). "
            "أعد صياغة الإجابة بحيث تقتصر فقط على الرواة الواردين حرفيًا في get_isnad، "
            "أو لا تذكر أي اسم راوٍ إذا لم تُستدعَ أداة get_isnad، "
            "أو أجب بالرفض التام إذا لم تكفِ الأدوات."
        )
    return "\n".join(parts)


def run_agent(
    question: str,
    retriever: Any,
    *,
    k: int = 5,
    enforce_citations: bool = True,
    model: str | None = None,
    sanad_db_path: Path | str | None = None,
    max_tool_calls: int = MAX_TOOL_CALLS,
    tool_timeout_s: float = DEFAULT_TOOL_TIMEOUT_S,
    client: Any = None,
    generate_fn: Callable[..., Any] | None = None,
    search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
    isnad_fn: Callable[[int], dict[str, Any]] | None = None,
    lexicon: NarratorLexicon | None = None,
    fallback_fn: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run tool-calling loop with C1 bounds/timeout/fallback and C2 validation."""
    from src.answer import (
        CORRECTIONS,
        GENERATE_TIMEOUT_MS,
        MODEL,
        REFUSAL,
        TEMPERATURE,
        VALID_ANSWER,
        VALID_REFUSAL,
        attach_sanad,
        cited_ids,
        loose_cited_ids,
        ordered_cited_ids,
        validate_answer,
    )

    resolved_model = model or MODEL
    resolved_db_path = Path(sanad_db_path) if sanad_db_path is not None else GRAPH_DB_PATH
    agent_tools = build_agent_tools()
    is_global_model = resolved_model.startswith("gemini-3") or resolved_model.startswith("gemini-4")

    def _is_retryable_api_error(exc: Exception) -> bool:
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if isinstance(code, int):
            return code == 429 or code >= 500
        msg = str(exc)
        return any(tok in msg for tok in ("429", "500", "502", "503", "504", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED", "UNAVAILABLE"))

    def _default_generate(contents: list[Any], *, allow_tools: bool) -> Any:
        import time
        from src.answer import INITIAL_BACKOFF_SECONDS, MAX_ATTEMPTS

        active_client = client if client is not None else _get_default_client()
        mode = "AUTO" if allow_tools else "NONE"
        config_kwargs: dict[str, Any] = {
            "system_instruction": AGENT_SYSTEM_INSTRUCTION,
            "temperature": TEMPERATURE,
            "http_options": types.HttpOptions(timeout=GENERATE_TIMEOUT_MS),
            "tools": [agent_tools],
            "tool_config": types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode=mode)
            ),
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        }
        if is_global_model:
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="LOW")
        config = types.GenerateContentConfig(**config_kwargs)

        delay = INITIAL_BACKOFF_SECONDS
        for attempt in range(MAX_ATTEMPTS):
            try:
                return active_client.models.generate_content(
                    model=resolved_model,
                    contents=contents,
                    config=config,
                )
            except Exception as exc:
                if attempt == MAX_ATTEMPTS - 1 or not _is_retryable_api_error(exc):
                    raise
                time.sleep(delay)
                delay *= 2

    def _get_default_client() -> Any:
        from src.answer import get_client

        return get_client(location="global" if is_global_model else None)

    model_call = generate_fn if generate_fn is not None else _default_generate

    def _exec_search(query: str) -> list[dict[str, Any]]:
        if search_fn is not None:
            return list(search_fn(query, k))
        return list(retriever.search(query, k=k))

    def _exec_isnad(hadith_id: int) -> dict[str, Any]:
        if isnad_fn is not None:
            return dict(isnad_fn(hadith_id))
        conn = open_graph(resolved_db_path)
        try:
            return dict(context_for_local_hadith(conn, hadith_id))
        finally:
            conn.close()

    tool_trace: list[dict[str, Any]] = []
    tool_hadith_ids: set[int] = set()
    isnad_results: list[dict[str, Any]] = []
    chunks_by_id: dict[int, dict[str, Any]] = {}
    ordered_chunks: list[dict[str, Any]] = []
    pro_calls_used = 0

    def _record_chunk(chunk: dict[str, Any]) -> None:
        hid = int(chunk["hadith_id"])
        if hid not in chunks_by_id:
            chunks_by_id[hid] = chunk
            ordered_chunks.append(chunk)

    def _run_fallback(exc: Exception) -> dict[str, Any]:
        if fallback_fn is None:
            raise exc
        fb = dict(fallback_fn())
        fb["agent_used"] = True
        fb["agent_fallback"] = True
        fb["fallback_reason"] = f"{type(exc).__name__}: {exc}"
        fb["tool_calls"] = tool_trace
        fb["tool_hadith_ids"] = sorted(tool_hadith_ids)
        fb["pro_calls_used"] = pro_calls_used
        return fb

    contents: list[Any] = [
        types.Content(role="user", parts=[types.Part.from_text(text=question)])
    ]
    draft_answer = ""

    try:
        while len(tool_trace) < max_tool_calls:
            pro_calls_used += 1
            response = model_call(contents, allow_tools=True)
            fn_calls, text, candidate_content = _extract_response_parts(response)

            if candidate_content is not None:
                contents.append(candidate_content)
            elif fn_calls:
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part(function_call=fc) for fc in fn_calls],
                    )
                )

            if not fn_calls:
                draft_answer = text
                break

            remaining = max_tool_calls - len(tool_trace)
            fn_response_parts: list[types.Part] = []
            for fc in fn_calls[:remaining]:
                name = str(getattr(fc, "name", "") or "")
                args = dict(getattr(fc, "args", None) or {})
                if name == "search_hadith":
                    query = str(args.get("query") or question)
                    chunks = _run_with_timeout(
                        lambda q=query: _exec_search(q),
                        tool_timeout_s,
                    )
                    for ch in chunks:
                        hid = int(ch["hadith_id"])
                        tool_hadith_ids.add(hid)
                        _record_chunk(ch)
                    payload = {
                        "query": query,
                        "results": [
                            {
                                "hadith_id": int(ch["hadith_id"]),
                                "chapter": (ch.get("metadata") or {}).get("chapter_arabic", ""),
                                "matn": _chunk_matn(ch),
                            }
                            for ch in chunks
                        ],
                    }
                    tool_trace.append(
                        {"name": "search_hadith", "args": {"query": query}, "result": payload["results"]}
                    )
                    fn_response_parts.append(
                        types.Part.from_function_response(name=name, response=payload)
                    )
                elif name == "get_isnad":
                    hid = _coerce_hadith_id(args.get("hadith_id"))
                    ctx = _run_with_timeout(
                        lambda target_id=hid: _exec_isnad(target_id),
                        tool_timeout_s,
                    )
                    isnad_results.append(ctx)
                    if ctx.get("status") != INVALID_LOCAL_HADITH_ID:
                        tool_hadith_ids.add(hid)
                        local_meta = ctx.get("local_hadith") or {}
                        _record_chunk(
                            {
                                "hadith_id": hid,
                                "text": "",
                                "metadata": {"chapter_arabic": local_meta.get("chapter_ar", "")},
                            }
                        )
                    payload = _format_isnad_for_model(ctx)
                    tool_trace.append(
                        {"name": "get_isnad", "args": {"hadith_id": hid}, "result": ctx}
                    )
                    fn_response_parts.append(
                        types.Part.from_function_response(name=name, response=payload)
                    )
                else:
                    raise ValueError(f"Unknown agent tool requested: {name!r}")

            if fn_response_parts:
                contents.append(types.Content(role="user", parts=fn_response_parts))

            # If we hit the tool budget on this step or truncated excess calls, break to final answer turn.
            if len(tool_trace) >= max_tool_calls or len(fn_calls) > remaining:
                break

        if not draft_answer:
            limit_note = types.Part.from_text(
                text=(
                    "استُنفد حد استدعاء الأدوات. قدّم الآن الإجابة النهائية بالعربية "
                    "اعتمادًا فقط على مخرجات الأدوات أعلاه مع التوثيق الصارم، "
                    f"أو اكتب حرفيًا: \"{REFUSAL}\""
                )
            )
            if contents and getattr(contents[-1], "role", None) == "user":
                merged_parts = list(getattr(contents[-1], "parts", None) or ()) + [limit_note]
                contents[-1] = types.Content(role="user", parts=merged_parts)
            else:
                contents.append(types.Content(role="user", parts=[limit_note]))
            pro_calls_used += 1
            final_resp = model_call(contents, allow_tools=False)
            _, draft_answer, final_content = _extract_response_parts(final_resp)
            if final_content is not None:
                contents.append(final_content)
    except Exception as exc:
        return _run_fallback(exc)

    raw = draft_answer or REFUSAL
    lex = _resolve_lexicon(lexicon, resolved_db_path)

    status = validate_answer(raw, tool_hadith_ids, tool_ids=tool_hadith_ids)
    disallowed = find_disallowed_narrators(raw, isnad_results, lex)

    invalid_citation = bool(cited_ids(raw) - tool_hadith_ids)
    missing_citation = status == "missing_citation"
    loose_out_of_context = bool(
        (loose_cited_ids(raw) - cited_ids(raw)) - tool_hadith_ids
    )
    mixed_refusal = status == "mixed_refusal"
    disallowed_attempt = list(disallowed)

    answer = raw
    regenerated = False
    final_status = status
    final_disallowed = disallowed

    needs_regen = status not in (VALID_ANSWER, VALID_REFUSAL) or bool(disallowed)
    if needs_regen and enforce_citations:
        regenerated = True
        feedback = _build_correction_prompt(status, disallowed, CORRECTIONS)
        regen_contents = list(contents)
        if not regen_contents or getattr(regen_contents[-1], "role", None) == "user":
            regen_contents.append(
                types.Content(role="model", parts=[types.Part.from_text(text=raw)])
            )
        regen_contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=feedback)])
        )
        try:
            pro_calls_used += 1
            regen_resp = model_call(regen_contents, allow_tools=False)
            _, regen_text, _ = _extract_response_parts(regen_resp)
        except Exception as exc:
            return _run_fallback(exc)

        answer = regen_text or REFUSAL
        final_status = validate_answer(answer, tool_hadith_ids, tool_ids=tool_hadith_ids)
        final_disallowed = find_disallowed_narrators(answer, isnad_results, lex)
        if final_status not in (VALID_ANSWER, VALID_REFUSAL) or final_disallowed:
            answer = REFUSAL
            final_status = VALID_REFUSAL
    elif needs_regen:
        # Even if citation enforcement is toggled off in experiments, C2 forbids ungrounded narrators
        if final_disallowed:
            answer = REFUSAL
            final_status = VALID_REFUSAL

    sanad: list[dict[str, Any]] = []
    sanad_error: str | None = None
    if final_status == VALID_ANSWER:
        sanad, sanad_error = attach_sanad(
            ordered_cited_ids(answer), db_path=resolved_db_path
        )

    return {
        "answer": answer,
        "raw": raw,
        "chunks": ordered_chunks,
        "sanad": sanad,
        "sanad_error": sanad_error,
        "invalid_citation_attempt": invalid_citation,
        "missing_citation_attempt": missing_citation,
        "loose_out_of_context_attempt": loose_out_of_context,
        "mixed_refusal_attempt": mixed_refusal,
        "disallowed_narrators_attempt": disallowed_attempt,
        "final_disallowed_narrators": final_disallowed,
        "regenerated": regenerated,
        "rewritten": None,
        "retried": False,
        "tool_calls": tool_trace,
        "tool_hadith_ids": sorted(tool_hadith_ids),
        "agent_used": True,
        "agent_fallback": False,
        "fallback_reason": None,
        "pro_calls_used": pro_calls_used,
    }
