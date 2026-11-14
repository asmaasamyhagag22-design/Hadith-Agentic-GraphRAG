"""Deterministic evaluator for Sahih Muslim chain-of-narration questions.

Scores predictions against ``data/raw/chain_eval_{dev,test}.jsonl`` without using
any LLM judge:
- **Routing correctness**: ``get_isnad`` called when needed, and
  ``search_hadith`` called when the hadith is not named in the question.
- **Narrator faithfulness**: zero narrator names in the answer that do not appear
  in ``get_isnad`` results returned during the request.
- **Answer correctness**: expected narrator IDs/names present, exact isnad count
  or boolean membership matched, and clean abstention when a hadith has no
  recorded chain or requests unavailable narrator gradings.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from src.answer import REFUSAL, cited_ids
from src.build_chain_eval import CHAIN_EVAL_DEV_PATH, CHAIN_EVAL_PATH, CHAIN_EVAL_TEST_PATH
from src.sanad_names import (
    NarratorLexicon,
    find_disallowed_narrators,
    load_narrator_lexicon,
    normalize_arabic_name,
    text_contains_expected_narrator,
)

_ABSTAIN_REGEXES = (
    re.compile(r"المصادر\s+المتاحه\s+لا\s+تجيب"),
    re.compile(r"لا\s+(?:يوجد|توجد)\s+(?:\S+\s+){0,4}(?:اسناد|اسانيد|سلسله|سلاسل|ربط|حكم|احكام)"),
    re.compile(r"لا\s+(?:يتوفر|تتوفر|تتوافر|تتضمن|تشمل|يشمل|تضم|يضم)\s+(?:\S+\s+){0,5}(?:اسناد|اسانيد|سلسله|سلاسل|ربط|حكم|احكام|الجرح)"),
    re.compile(r"ليس\s+(?:له|لها|فيها|للحديث)\s+(?:\S+\s+){0,3}(?:اسناد|اسانيد|سلسله|ربط|حكم|احكام)"),
    re.compile(r"لم\s+(?:يسجل|تسجل|يرد)\s+(?:له|لها|في)\s+(?:\S+\s+){0,3}(?:اسناد|اسانيد|سلسله|ربط|حكم|احكام)"),
    re.compile(r"(?:غير\s+مربوط|بلا\s+اسناد|بدون\s+اسناد|لا\s+يحوي\s+اسناد|لا\s+يحتوي\s+(?:علي|على)\s+اسناد)"),
    re.compile(r"(?:حكم|احكام)\s+(?:الرواه|الجرح\s+والتعديل|ابن\s+حجر)\s+(?:\S+\s+){0,3}(?:غير\s+متوفر|غير\s+متوفره|غير\s+متوافر|غير\s+متوافره|غير\s+موجود|مفقود|غير\s+مدرج)"),
    re.compile(r"(?:غير\s+متوفر|غير\s+متوفره|غير\s+متوافر|غير\s+متوافره|غير\s+موجود|غير\s+موجوده)\s+في\s+(?:قاعده|المصادر)"),
    re.compile(r"(?:تعذر\s+العثور\s+على|لا\s+يمكن\s+(?:التحقق|الجزم|تحديد)\s+(?:من\s+)?(?:اسناد|راوي|الصحابي|حكم))"),
)

_GRADING_FABRICATION_RE = re.compile(
    r"(?<![\w\u0621-\u064a])(?:"
    r"رواته\s+ثقات|"
    r"رجاله\s+ثقات|"
    r"سنده\s+صحيح|"
    r"إسناده\s+صحيح|"
    r"اسناده\s+صحيح|"
    r"حكم\s+(?:عليه\s+)?ابن\s+حجر\s+(?:بأنه|بانه)\s+(?:ثقة|صدوق|ضعيف|متروك|حسن)|"
    r"(?:هو|راوٍ|راو)\s+(?:ثقة|صدوق|ضعيف|متروك|كذاب|مجهول)"
    r")(?![\w\u0621-\u064a])"
)

_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

_ARABIC_COUNT_WORDS: dict[int, tuple[str, ...]] = {
    1: ("واحد", "واحدة", "وحيد", "إسناد واحد", "اسناد واحد", "طريق واحد", "طريقا واحدا", "سلسلة واحدة"),
    2: ("اثنان", "اثنين", "اثنتان", "اثنتين", "إسنادان", "اسنادان", "إسنادين", "اسنادين", "طريقان", "طريقين", "سلسلتان", "سلسلتين"),
    3: ("ثلاثة", "ثلاث", "ثلاثة أسانيد", "ثلاثة اسانيد", "ثلاث طرق", "ثلاث سلاسل"),
    4: ("أربعة", "اربعة", "أربع", "اربع", "أربعة أسانيد", "اربعة اسانيد", "أربع طرق", "أربع سلاسل"),
    5: ("خمسة", "خمس", "خمسة أسانيد", "خمسة اسانيد", "خمس طرق", "خمس سلاسل"),
    6: ("ستة", "ست", "ستة أسانيد", "ستة اسانيد", "ست طرق", "ست سلاسل"),
    7: ("سبعة", "سبع", "سبعة أسانيد", "سبعة اسانيد", "سبع طرق"),
    8: ("ثمانية", "ثمان", "ثماني"),
    9: ("تسعة", "تسع"),
    10: ("عشرة", "عشر"),
}

_CITATION_NOISE_RE = re.compile(
    r"\[\s*\d+\s*\]|"
    r"\(\s*المصدر\s*:[^)]*\)|"
    r"(?:حديث|الحديث|مسلم)\s*(?:رقم)?\s*\d+|"
    r"رقم\s+\d+"
)

_NEGATIVE_BOOL_RE = re.compile(
    r"(?:^|[\s،.:؛])(?:لا|كلا|لم\s+يرد|لا\s+يظهر|لا\s+يروي|لم\s+يقع|لم\s+يشارك|"
    r"غير\s+وارد|غير\s+موجود|ليس\s+(?:ضمن|في|من\s+بين|موجودا)|لم\s+يُذكر|لم\s+يذكر)(?=$|[\s،.:؛])"
)
_POSITIVE_BOOL_RE = re.compile(
    r"(?:^|[\s،.:؛])(?:نعم|بلى|ورد|يظهر|ظهر|يروي|موجود|شارك|ذكر|وقع)(?=$|[\s،.:؛])"
)


def load_chain_eval(path: Path | None = None) -> list[dict[str, Any]]:
    resolved = path or CHAIN_EVAL_PATH
    with resolved.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def is_chain_abstention(answer: str) -> bool:
    """Return True if ``answer`` cleanly states refusal or missing graph/grading info."""
    stripped = (answer or "").strip()
    if not stripped:
        return False
    if REFUSAL in stripped:
        return True
    norm = normalize_arabic_name(stripped).replace("ة", "ه")
    return any(pattern.search(norm) for pattern in _ABSTAIN_REGEXES)


def has_grading_fabrication(answer: str) -> bool:
    """Return True if ``answer`` asserts a narrator jarh/ta'dil grading ruling."""
    if not answer:
        return False
    return bool(_GRADING_FABRICATION_RE.search(answer))


def answer_matches_count(answer: str, expected_count: int) -> bool:
    """Match ``expected_count`` as a standalone digit or Arabic number word."""
    cleaned = _CITATION_NOISE_RE.sub(" ", answer or "").translate(_ARABIC_INDIC_DIGITS)
    norm = normalize_arabic_name(cleaned)
    if re.search(rf"(?<!\d){expected_count}(?!\d)", norm):
        return True
    for phrase in _ARABIC_COUNT_WORDS.get(expected_count, ()):
        pnorm = normalize_arabic_name(phrase)
        if re.search(rf"(?<![\w\u0621-\u064a]){re.escape(pnorm)}(?![\w\u0621-\u064a])", norm):
            return True
    return False


def answer_matches_boolean(answer: str, expected_bool: bool) -> bool:
    """Match a deterministic yes/no membership response in Arabic."""
    if is_chain_abstention(answer):
        return False
    norm = normalize_arabic_name(answer or "")
    has_neg = bool(_NEGATIVE_BOOL_RE.search(norm))
    has_pos = bool(_POSITIVE_BOOL_RE.search(norm))
    if expected_bool:
        return has_pos and not re.match(r"^(?:لا|لم\s+يرد|لا\s+يظهر|غير\s+موجود)\b", norm)
    return has_neg and not re.match(r"^(?:نعم|بلى)\b", norm)


def extract_isnad_results_from_prediction(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect all ``sanad_context`` dicts returned via ``get_isnad`` tool calls."""
    if "isnad_results" in prediction and prediction["isnad_results"] is not None:
        return list(prediction["isnad_results"])
    results: list[dict[str, Any]] = []
    for tc in prediction.get("tool_calls") or ():
        if tc.get("name") == "get_isnad" and isinstance(tc.get("result"), dict):
            results.append(tc["result"])
    return results


def score_routing(item: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    """Deterministically score whether required tools were invoked cleanly."""
    tool_calls = list(prediction.get("tool_calls") or ())
    names = [str(tc.get("name") or "") for tc in tool_calls]

    requires_search = bool(item.get("requires_search", False))
    requires_isnad = bool(item.get("requires_isnad", True))

    search_called = "search_hadith" in names
    isnad_called = "get_isnad" in names

    expected_ids = {int(x) for x in (item.get("hadith_ids") or ())}
    isnad_called_ids: set[int] = set()
    for tc in tool_calls:
        if tc.get("name") == "get_isnad":
            args = tc.get("args") or {}
            hid = args.get("hadith_id")
            if hid is not None:
                try:
                    isnad_called_ids.add(int(hid))
                except (TypeError, ValueError):
                    pass

    search_ok = (search_called == requires_search)
    isnad_ok = (not requires_isnad) or isnad_called
    if isnad_ok and requires_isnad and not requires_search and expected_ids:
        # When the hadith ID was named in the prompt, verify get_isnad targeted it.
        isnad_ok = bool(isnad_called_ids & expected_ids)

    return {
        "search_needed": requires_search,
        "search_called": search_called,
        "isnad_needed": requires_isnad,
        "isnad_called": isnad_called,
        "isnad_called_ids": sorted(isnad_called_ids),
        "routing_correct": bool(search_ok and isnad_ok),
    }


def score_chain_item(
    item: dict[str, Any],
    prediction: dict[str, Any],
    lexicon: NarratorLexicon | None = None,
) -> dict[str, Any]:
    """Deterministically score one chain-evaluation item."""
    lex = lexicon if lexicon is not None else load_narrator_lexicon()
    answer = str(prediction.get("answer") or "")
    isnad_results = extract_isnad_results_from_prediction(prediction)
    routing = score_routing(item, prediction)

    disallowed_narrators = find_disallowed_narrators(answer, isnad_results, lex)
    no_hallucinated_narrators = len(disallowed_narrators) == 0

    abstained = is_chain_abstention(answer)
    fabricated_grading = has_grading_fabrication(answer)

    expected_abstain = bool(item.get("expected_abstain", False))
    expected_partial_abstain = bool(item.get("expected_partial_abstain", False))
    qtype = str(item.get("type") or "")
    expected_ids = [int(x) for x in (item.get("hadith_ids") or ())]
    expected_narrators = list(item.get("expected_narrators") or ())
    answer_cited_ids = cited_ids(answer)

    citation_ok = True
    if answer_cited_ids and expected_ids:
        citation_ok = bool(set(answer_cited_ids) & set(expected_ids))

    abstain_correct: bool | None = None
    answer_correct = False
    failure_reasons: list[str] = []

    if not no_hallucinated_narrators:
        failure_reasons.append(f"disallowed_narrators={disallowed_narrators}")
    if fabricated_grading:
        failure_reasons.append("fabricated_grading")

    if expected_abstain:
        abstain_correct = abstained
        answer_correct = abstained and no_hallucinated_narrators and not fabricated_grading
        if not abstained:
            failure_reasons.append("failed_to_abstain")
    elif qtype in ("who_narrated_companion", "who_narrated_teacher", "topic_who_narrated"):
        if abstained and not expected_partial_abstain:
            failure_reasons.append("false_refusal")
        elif REFUSAL in answer:
            failure_reasons.append("full_refusal_on_answerable")
        else:
            missing_narrators = [
                n.get("name_ar_mapped") or n.get("narrator_id")
                for n in expected_narrators
                if not text_contains_expected_narrator(answer, n)
            ]
            partial_abstain_ok = (not expected_partial_abstain) or abstained
            if missing_narrators:
                failure_reasons.append(f"missing_narrators={missing_narrators}")
            if not partial_abstain_ok:
                failure_reasons.append("missing_grading_abstention")
            if not citation_ok:
                failure_reasons.append(f"wrong_citation={answer_cited_ids}")
            answer_correct = (
                not missing_narrators
                and partial_abstain_ok
                and no_hallucinated_narrators
                and not fabricated_grading
                and citation_ok
            )
    elif qtype == "isnad_count":
        expected_count = item.get("expected_count")
        count_ok = (
            expected_count is not None
            and not abstained
            and answer_matches_count(answer, int(expected_count))
        )
        if not count_ok:
            failure_reasons.append(f"wrong_or_missing_count(expected={expected_count})")
        if not citation_ok:
            failure_reasons.append(f"wrong_citation={answer_cited_ids}")
        answer_correct = (
            count_ok
            and no_hallucinated_narrators
            and not fabricated_grading
            and citation_ok
        )
    elif qtype == "narrator_in_chain":
        expected_bool = item.get("expected_bool")
        bool_ok = expected_bool is not None and answer_matches_boolean(answer, bool(expected_bool))
        narr_ok = True
        if expected_bool is True and expected_narrators:
            narr_ok = all(text_contains_expected_narrator(answer, n) for n in expected_narrators)
            if not narr_ok:
                failure_reasons.append("missing_expected_narrator")
        if not bool_ok:
            failure_reasons.append(f"wrong_boolean(expected={expected_bool})")
        if not citation_ok:
            failure_reasons.append(f"wrong_citation={answer_cited_ids}")
        answer_correct = (
            bool_ok
            and narr_ok
            and no_hallucinated_narrators
            and not fabricated_grading
            and citation_ok
        )
    else:
        failure_reasons.append(f"unknown_type={qtype}")

    return {
        "id": item.get("id"),
        "split": item.get("split"),
        "type": qtype,
        "question": item.get("question"),
        "expected_abstain": expected_abstain,
        "abstained": abstained,
        "abstain_correct": abstain_correct,
        "routing_correct": routing["routing_correct"],
        "routing": routing,
        "no_hallucinated_narrators": no_hallucinated_narrators,
        "disallowed_narrators": disallowed_narrators,
        "fabricated_grading": fabricated_grading,
        "answer_correct": bool(answer_correct),
        "failure_reasons": failure_reasons,
        "cited_ids": answer_cited_ids,
        "answer": answer,
    }


def aggregate_chain_scores(scored_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate routing, answer, hallucination, and abstention metrics."""
    n = len(scored_rows)
    routing_hits = sum(1 for r in scored_rows if r["routing_correct"])
    answer_hits = sum(1 for r in scored_rows if r["answer_correct"])
    no_halluc_hits = sum(1 for r in scored_rows if r["no_hallucinated_narrators"])
    abstention_rows = [r for r in scored_rows if r["expected_abstain"]]
    abstain_hits = sum(1 for r in abstention_rows if r["abstain_correct"])

    by_type: dict[str, dict[str, Any]] = {}
    type_counts = Counter(r["type"] for r in scored_rows)
    for qtype, total_t in sorted(type_counts.items()):
        subset = [r for r in scored_rows if r["type"] == qtype]
        by_type[qtype] = {
            "n": total_t,
            "routing_correct": sum(1 for r in subset if r["routing_correct"]),
            "answer_correct": sum(1 for r in subset if r["answer_correct"]),
            "routing_accuracy": round(sum(1 for r in subset if r["routing_correct"]) / total_t, 4),
            "answer_accuracy": round(sum(1 for r in subset if r["answer_correct"]) / total_t, 4),
        }

    return {
        "n": n,
        "routing_correct": routing_hits,
        "routing_accuracy": round(routing_hits / n, 4) if n else 0.0,
        "answer_correct": answer_hits,
        "answer_accuracy": round(answer_hits / n, 4) if n else 0.0,
        "no_hallucinated_narrators": no_halluc_hits,
        "no_hallucinated_rate": round(no_halluc_hits / n, 4) if n else 0.0,
        "abstention_total": len(abstention_rows),
        "abstention_correct": abstain_hits,
        "abstention_accuracy": round(abstain_hits / len(abstention_rows), 4) if abstention_rows else None,
        "by_type": by_type,
    }


def evaluate_chain_predictions(
    items: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    lexicon: NarratorLexicon | None = None,
) -> dict[str, Any]:
    if len(items) != len(predictions):
        raise ValueError(f"Mismatched items ({len(items)}) vs predictions ({len(predictions)}).")
    lex = lexicon if lexicon is not None else load_narrator_lexicon()
    rows = [score_chain_item(it, pred, lex) for it, pred in zip(items, predictions)]
    summary = aggregate_chain_scores(rows)
    return {
        **summary,
        "rows": rows,
    }


def run_chain_eval(
    runner: Callable[[str], dict[str, Any]],
    items: list[dict[str, Any]],
    *,
    lexicon: NarratorLexicon | None = None,
) -> dict[str, Any]:
    """Run ``runner(question)`` over ``items`` and score deterministically."""
    predictions: list[dict[str, Any]] = []
    latencies_ms: list[float] = []
    for item in items:
        t0 = time.perf_counter()
        pred = runner(item["question"])
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed_ms)
        predictions.append(pred)
    report_dict = evaluate_chain_predictions(items, predictions, lexicon=lexicon)
    for row, lat in zip(report_dict["rows"], latencies_ms):
        row["latency_ms"] = round(lat, 2)
    sorted_lat = sorted(latencies_ms)
    if sorted_lat:
        mid = len(sorted_lat) // 2
        median = sorted_lat[mid] if len(sorted_lat) % 2 else (sorted_lat[mid - 1] + sorted_lat[mid]) / 2
        p95_idx = min(len(sorted_lat) - 1, int(0.95 * (len(sorted_lat) - 1)))
        report_dict["latency_median_ms"] = round(median, 2)
        report_dict["latency_p95_ms"] = round(sorted_lat[p95_idx], 2)
    return report_dict


def format_chain_report(results: dict[str, Any], title: str = "Chain Evaluation") -> str:
    lines = [
        f"=== {title} (n={results['n']}) ===",
        f"  Routing accuracy:          {results['routing_correct']}/{results['n']} ({results['routing_accuracy']*100:.1f}%)",
        f"  Answer accuracy:           {results['answer_correct']}/{results['n']} ({results['answer_accuracy']*100:.1f}%)",
        f"  No hallucinated narrators: {results['no_hallucinated_narrators']}/{results['n']} ({results['no_hallucinated_rate']*100:.1f}%)",
    ]
    if results.get("abstention_total"):
        lines.append(
            f"  Abstention accuracy:       {results['abstention_correct']}/{results['abstention_total']} "
            f"({results['abstention_accuracy']*100:.1f}%)"
        )
    if "latency_median_ms" in results:
        lines.append(
            f"  Latency:                   median={results['latency_median_ms']:.1f} ms, p95={results['latency_p95_ms']:.1f} ms"
        )
    lines.append("  By type:")
    for qtype, stats in sorted(results.get("by_type", {}).items()):
        lines.append(
            f"    - {qtype:24s} n={stats['n']:2d} | routing={stats['routing_correct']}/{stats['n']} "
            f"| answer={stats['answer_correct']}/{stats['n']}"
        )
    return "\n".join(lines)


def _split_path(split: str) -> Path:
    if split == "dev":
        return CHAIN_EVAL_DEV_PATH
    if split == "test":
        return CHAIN_EVAL_TEST_PATH
    if split == "all":
        return CHAIN_EVAL_PATH
    raise ValueError(f"Unsupported split: {split!r}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Score or run deterministic Sahih Muslim chain evaluation.")
    parser.add_argument("--split", choices=("dev", "test", "all"), default="dev")
    parser.add_argument("--predictions", type=Path, help="Optional JSON/JSONL file of saved predictions to score offline.")
    parser.add_argument("--output", type=Path, help="Optional JSON path to save detailed report.")
    args = parser.parse_args(argv)

    items = load_chain_eval(_split_path(args.split))
    if args.predictions is None:
        raise SystemExit("Pass --predictions <path> to score saved predictions offline, or call run_chain_eval from runner code.")

    raw_text = args.predictions.read_text(encoding="utf-8").strip()
    if args.predictions.suffix == ".jsonl":
        preds = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
    else:
        data = json.loads(raw_text)
        preds = data if isinstance(data, list) else data["predictions"]

    results = evaluate_chain_predictions(items, preds)
    print(format_chain_report(results, title=f"Chain Eval ({args.split})"))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
