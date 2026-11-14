"""Deterministic Arabic linguistic intent classifier for Musnad query routing.

Classifies incoming Arabic questions into ``"chain"`` (narrator, isnad, chain
count, companion/teacher attribution, or narrator membership) or ``"text"``
(hadith content, jurisprudence, or meaning) using compiled regex rules derived
from general Arabic hadith-sciences terminology — with zero model calls.
"""

from __future__ import annotations

import re
from typing import Literal

RouteIntent = Literal["chain", "text"]

_DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u0640\u200c-\u200f]")
_ALEF_RE = re.compile(r"[أإآٱ]")
_PUNCT_RE = re.compile(r"[^\w\u0621-\u064a\s]+")
_WHITESPACE_RE = re.compile(r"\s+")

_END = r"(?![\u0621-\u064a])"
_START = r"(?<![\u0621-\u064a])"

# General Arabic linguistic rules for isnad/narrator intent.
# Each tuple is (rule_name, compiled_pattern).
_CHAIN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "explicit_isnad_or_sanad_term",
        re.compile(
            rf"{_START}(?:"
            r"[وفبلك]?(?:ال)?اسناد(?:ا|ه|ها|هما|هم)?|"
            r"[وفبلك]?(?:ال)?اسانيد(?:ه|ها|هما|هم)?|"
            r"[وفبلك]?سنده|"
            r"للاسنا?د|للاسانيد|للسند|"
            r"(?:في|من|عن|ضمن|ما|كم|اذكر|بين)\s+(?:ال)?سند|"
            r"سند\s+(?:ال?حديث|هذا\s+الحديث|مسلم|الروا[ةه]|صحيح)|"
            r"سلسل[ةه]\s+(?:ال)?(?:سند|اسناد|اسانيد|روا[ةه]|ال?حديث)|"
            r"سلاسل\s+(?:ال)?(?:سند|اسناد|اسانيد|روا[ةه]|ال?حديث)"
            rf"){_END}"
        ),
    ),
    (
        "isnad_or_route_count",
        re.compile(
            rf"{_START}(?:"
            r"(?:كم|ما)\s+(?:عدد\s+)?(?:ال?اسانيد|ال?طرق|طرقا|طريقا|ال?سلاسل|سلسل[ةه]|اسنادا)|"
            r"عدد\s+(?:ال?اسانيد|طرق\s+(?:ال?حديث|ال?رواي[ةه]|هذا)|ال?سلاسل)|"
            r"كم\s+طريقا?\s+(?:ورد|وردت|روي|ثبت|جاء|له|لها|للحديث|لحديث)|"
            r"(?:ال?طرق|طرق\s+(?:ال?حديث|الرواي[ةه]))\s+(?:ال?مسجل[ةه]|ال?وارد[ةه]|المتعددة)"
            rf"){_END}"
        ),
    ),
    (
        "narrators_or_grading_query",
        re.compile(
            rf"{_START}(?:"
            r"رواته|رواتها|"
            r"(?:ال?رواة|رواة)\s+(?:ال?حديث|هذا|السند|الاسناد|الاسانيد)|"
            r"حكم\s+(?:رواته|رواة)|"
            r"(?:من|ما\s+اسماء|اذكر|سم)\s+(?:هم\s+)?(?:ال?رواة|رواة)"
            rf"){_END}"
        ),
    ),
    (
        "muslim_teacher_query",
        re.compile(
            rf"{_START}(?:"
            r"(?:شيخ|شيوخ|اساتذة)\s+(?:الامام\s+)?مسلم|"
            r"(?:عمن|عن\s+من|ممن)\s+(?:اخذ|رو[ىي]|سمع|تلق[ىي]|حدث)\s+(?:عنه\s+)?(?:الامام\s+)?مسلم|"
            r"(?:ال?راوي|الشيخ)\s+المباشر\s+(?:للامام\s+|ل)?مسلم|"
            r"(?:اخذ|تلق[ىي]|سمع)\s+(?:الامام\s+)?مسلم\s+(?:عنه|ال?حديث|هذا)"
            rf"){_END}"
        ),
    ),
    (
        "who_narrated_hadith",
        re.compile(
            rf"{_START}(?:"
            r"(?:من|ما\s+اسم|اي|سم)\s+(?:هو\s+|هي\s+|هم\s+|الذي\s+|التي\s+|الذين\s+)?(?:راوي|الراوي|ناقل)\s+(?:ال?حديث|حديث|هذا|عن)|"
            r"(?:من|اي)\s+(?:هو\s+|هي\s+|الذي\s+|التي\s+)?(?:رو[ىي]|روت|رواه|روته|يروي|تروي|نقل|نقلت)\s+(?:ال?حديث|حديث|هذا\s+ال?حديث|عن\s+(?:النبي|رسول)|في\s+صحيح)|"
            r"(?:ال?صحابي(?:[ةه])?\s+)راوي\s+(?:ال?حديث|حديث|هذا)|"
            r"(?:من|ما\s+اسم)\s+(?:هو\s+|هي\s+)?ال?صحابي(?:[ةه])?\b.*?(?:رو[ىي]|روت|يروي|تروي|رواه|روته|نقل|نقلت|تلق[ىي]|سند|اسناد|اسانيد|طرق|حديث\s*رقم|الحديث\s*رقم|لحديث|لهذا\s+الحديث)"
            rf"){_END}"
        ),
    ),
    (
        "narrator_membership_in_chain",
        re.compile(
            rf"{_START}(?:"
            r"هل\s+.*?(?:في|ضمن|من|بين|عبر)\s+(?:[وفبلك]?سند\b|سند[ها]?|[وفبلك]?(?:ال)?اسناد|[وفبلك]?(?:ال)?اسانيد|طرق\s+(?:ال?حديث|ال?رواي[ةه]|هذا)|احد\s+اسانيد|اي\s+(?:من\s+)?اسانيد|سلسل[ةه]|رواة)|"
            r"هل\s+(?:شارك|شاركت|رو[ىي]|روت|يروي|تروي|ظهر|ظهرت|يظهر|تظهر|ورد|وردت|يرد|ترد|وقع|وقعت|ذ?كر)\s+.*?(?:في\s+رواي[ةه]\s+(?:ال?حديث|هذا)|(?:ال?حديث|حديث)\s+رقم\s+\d+|في\s+(?:احد\s+)?(?:سند|اسناد|اسانيد|طرق))|"
            r"هل\s+\S+(?:\s+\S+){0,5}\s+(?:من|ضمن|احد|من\s+بين)\s+(?:رواة|شيوخ|اسانيد)\s+(?:ال?حديث|هذا|مسلم)"
            rf"){_END}"
        ),
    ),
)


def normalize_for_routing(text: str) -> str:
    """Normalize Arabic diacritics, alefs, and punctuation for rule matching."""
    cleaned = _DIACRITICS_RE.sub("", text or "")
    cleaned = _ALEF_RE.sub("ا", cleaned)
    cleaned = _PUNCT_RE.sub(" ", cleaned)
    return _WHITESPACE_RE.sub(" ", cleaned).strip()


def matched_chain_rule(question: str) -> str | None:
    """Return the first matching chain rule name for ``question``, else None."""
    norm = normalize_for_routing(question)
    if not norm:
        return None
    for rule_name, pattern in _CHAIN_RULES:
        if pattern.search(norm):
            return rule_name
    return None


def classify_intent(question: str) -> RouteIntent:
    """Classify a question as ``'chain'`` or ``'text'`` deterministically."""
    return "chain" if matched_chain_rule(question) is not None else "text"
