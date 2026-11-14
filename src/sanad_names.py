"""Deterministic Arabic narrator-name matching against the MIS SQLite graph.

Used by:
- ``src/chain_eval.py`` (Phase B3): verify expected narrators appear and no
  out-of-chain narrator names appear in agent answers.
- ``src/agent.py`` (Phase C2): validate that every narrator name written by the
  model appears in ``get_isnad`` tool results for the current request.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from src.sanad_graph import GRAPH_DB_PATH, open_graph

_DIACRITICS_RE = re.compile(r"[\u064b-\u065f\u0670\u0640\u200e\u200f\u200c\u200d]")
_ALEF_RE = re.compile(r"[أإآٱ]")
_SHAMELA_YAA_RE = re.compile(r"(?<![\w\u0621-\u064a])(?!(?:على|الى|حتى|متى|لدى)(?![\w\u0621-\u064a]))([\u0621-\u064a]+[\u0621-\u064a])ى(?![\w\u0621-\u064a])")
_ALI_BIN_RE = re.compile(r"(?<![\w\u0621-\u064a])([وفبلك])?على(?=\s+(?:بن|بنت)\b)")
_KUNYA_CASE_RE = re.compile(r"(?<![\w\u0621-\u064a])([وفبلك])?اب[واي](?=\s+\w)")
_BRACKETED_RE = re.compile(r"\[[^\]]*\]")
_PAREN_TEXT_RE = re.compile(r"[()]+")
_HONORIFICS_RE = re.compile(
    r"(?:رضي\s+الله\s+عنه(?:ما|م|ا)?|صلى\s+الله\s+عليه\s+وسلم|عليه\s+السلام|رحمه\s+الله)"
)
_WHITESPACE_RE = re.compile(r"\s+")

_NON_NISBA_THEOPHORIC = frozenset(
    {
        "الله",
        "الرحمن",
        "الرحيم",
        "الملك",
        "العزيز",
        "الكريم",
        "الوهاب",
        "الجبار",
        "الرزاق",
        "الغفار",
        "الصمد",
        "المجيد",
        "الحميد",
        "القادر",
        "الواحد",
        "المؤمن",
        "الاعلي",
        "الاعلى",
    }
)

# Multi-word phrases that appear in narrator strings but also frequently appear
# as ordinary Arabic words or generic first names (e.g., "عبد الله" in matn quotes)
# and must not trigger standalone out-of-chain false positives.
_GENERIC_TWO_WORD_PHRASES = frozenset(
    {
        "عبد الله",
        "عبد الرحمن",
        "عبد الملك",
        "عبد العزيز",
        "عبد الكريم",
        "عبد الرحيم",
        "عبد الواحد",
        "عبد المجيد",
        "عبد الحميد",
        "عبد الوهاب",
        "عبد السلام",
        "عبد القادر",
        "عبد الجبار",
        "عبد الوارث",
        "عبد الرزاق",
        "عبد الغفار",
        "عبد الاعلي",
        "عبد الصمد",
        "عبد المؤمن",
        "عبد ربه",
        "ابو بكر",
        "ابو عثمان",
        "ابو صالح",
        "ابو سلمة",
        "ابو اسامة",
        "ابو اسحاق",
        "ابو معاوية",
        "ابو عوانة",
        "ابو عبد",
        "ابو محمد",
        "ابو جعفر",
        "ابو داود",
        "ابو علي",
        "ابو نضرة",
        "ابو وائل",
        "ابو يحيى",
        "ابو يحيي",
        "ام المؤمنين",
        "مولي النبي",
        "رضي الله",
        "رحمه الله",
        "شيخ الاسلام",
        "امام دار",
        "بن عبد",
        "بن ابي",
        "بن محمد",
        "بن علي",
        "بن عمر",
        "بن مالك",
        "بن زيد",
        "بن سعيد",
        "بن صالح",
        "بن يزيد",
    }
)

# Unambiguous famous single-token narrator/companion identifiers used in chains
# and common questions (excluding words like مالك / مسلم / سالم / صالح / داود
# that appear routinely in hadith text or questions).
_SAFE_SINGLE_TOKEN_NAMES = frozenset(
    {
        "عائشة",
        "حفصة",
        "ميمونة",
        "الزهري",
        "الاعمش",
        "القعنبي",
        "الاوزاعي",
        "الشعبي",
        "النخعي",
        "السختياني",
        "البناني",
        "الدارقطني",
        "البخاري",
        "الترمذي",
        "النسائي",
        "الطبراني",
        "البيهقي",
        "الكوسج",
        "الخلال",
        "بندار",
        "غندر",
        "قتادة",
        "طاوس",
        "مكحول",
        "عكرمة",
        "الاسود",
        "مسروق",
        "علقمة",
        "همام",
    }
)

_NON_PERSON_PREFIXES = (
    "من اخبر",
    "من حدث",
    "بعض اصحاب",
    "بعض ولد",
    "بعض اهل",
    "رجل من",
    "غير ",
    "مولى ",
    "مولي ",
)


def normalize_arabic_name(text: str) -> str:
    """Normalize Arabic text for deterministic narrator matching."""
    cleaned = _DIACRITICS_RE.sub("", text or "")
    cleaned = _ALEF_RE.sub("ا", cleaned)
    cleaned = _BRACKETED_RE.sub(" ", cleaned)
    cleaned = _PAREN_TEXT_RE.sub(" ", cleaned)
    cleaned = _HONORIFICS_RE.sub(" ", cleaned)
    cleaned = _SHAMELA_YAA_RE.sub(r"\1ي", cleaned)
    cleaned = _ALI_BIN_RE.sub(lambda m: f"{m.group(1) or ''}علي", cleaned)
    cleaned = _KUNYA_CASE_RE.sub(lambda m: f"{m.group(1) or ''}ابو", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def _split_clean_segments(raw_name: str | None) -> list[str]:
    if not raw_name or raw_name.startswith("NotMapped"):
        return []
    segments: list[str] = []
    for part in re.split(r"\s*[-/,،]+\s*", raw_name):
        norm = normalize_arabic_name(part)
        if not norm:
            continue
        if any(norm.startswith(prefix) for prefix in _NON_PERSON_PREFIXES):
            continue
        segments.append(norm)
    return segments


def _extract_strict_forms_from_segment(seg: str) -> set[str]:
    """Generate unambiguous strict detection forms from one cleaned name segment."""
    forms: set[str] = set()
    words = seg.split()
    if not words:
        return forms

    # Strip leading honorific prefixes such as "ام المؤمنين "
    trimmed = list(words)
    if len(trimmed) >= 3 and trimmed[:2] == ["ام", "المؤمنين"]:
        trimmed = trimmed[2:]
    elif len(trimmed) >= 3 and trimmed[0] == "الامام":
        trimmed = trimmed[1:]

    candidate_word_lists = [words]
    if trimmed != words:
        candidate_word_lists.append(trimmed)

    for wlist in candidate_word_lists:
        n = len(wlist)
        if wlist[0] in _SAFE_SINGLE_TOKEN_NAMES:
            forms.add(wlist[0])
        if wlist[-1] in _SAFE_SINGLE_TOKEN_NAMES:
            forms.add(wlist[-1])
        if n == 1:
            continue

        full = " ".join(wlist)
        if full not in _GENERIC_TWO_WORD_PHRASES:
            forms.add(full)

        # Two-word forms: "ابو X" (excluding generic), "ام X", "ابن X"
        if n >= 2:
            two = " ".join(wlist[:2])
            if (
                wlist[0] in ("ابو", "ام", "ابن")
                and wlist[1] not in ("بن", "بنت", "الله", "الرحمن")
                and two not in _GENERIC_TWO_WORD_PHRASES
            ):
                forms.add(two)
            # First + Nisba (e.g. "سفيان الثوري", "عمرو الناقد", "ابراهيم النخعي")
            if wlist[1].startswith("ال") and len(wlist[1]) >= 4 and wlist[1] not in _NON_NISBA_THEOPHORIC:
                if two not in _GENERIC_TWO_WORD_PHRASES:
                    forms.add(two)
            if (
                n >= 3
                and wlist[-1].startswith("ال")
                and len(wlist[-1]) >= 4
                and wlist[-1] not in _NON_NISBA_THEOPHORIC
                and wlist[-2] != "عبد"
            ):
                first_nisba = f"{wlist[0]} {wlist[-1]}"
                if first_nisba not in _GENERIC_TWO_WORD_PHRASES:
                    forms.add(first_nisba)

        # Three-word nasab forms: "X بن Y" / "X بنت Y"
        if n >= 3 and wlist[1] in ("بن", "بنت"):
            three = " ".join(wlist[:3])
            if three not in _GENERIC_TWO_WORD_PHRASES:
                forms.add(three)
            # Handle kunya + nasab prefixes like "ابو بكر بن ابي شيبة" -> first 5
            if wlist[2] == "عبد" and n >= 4:
                forms.add(" ".join(wlist[:4]))
            if wlist[2] in ("ابو", "ابي") and n >= 4:
                forms.add(" ".join(wlist[:4]))
        if n >= 4 and wlist[0] == "ابو" and wlist[2] in ("بن", "بنت"):
            forms.add(" ".join(wlist[:4]))
            if n >= 5 and wlist[3] in ("ابو", "ابي", "عبد"):
                forms.add(" ".join(wlist[:5]))

        # Two-word "X بن Y" where "بن" was dropped or kunya was first
        if n >= 4:
            four = " ".join(wlist[:4])
            forms.add(four)
        if n >= 5:
            forms.add(" ".join(wlist[:5]))

    return {f for f in forms if f and f not in _GENERIC_TWO_WORD_PHRASES}


def narrator_strict_forms(name_ar: str | None, name_ar_mapped: str | None) -> set[str]:
    """Return normalized unambiguous narrator name forms for one narrator row."""
    forms: set[str] = set()
    for raw in (name_ar, name_ar_mapped):
        for seg in _split_clean_segments(raw):
            forms.update(_extract_strict_forms_from_segment(seg))
    return forms


def narrator_expected_aliases(
    name_ar: str | None,
    name_ar_mapped: str | None,
    *,
    extra_aliases: Iterable[str] = (),
) -> set[str]:
    """Return normalized aliases acceptable when checking expected narrator recall.

    Broadens ``narrator_strict_forms`` slightly for the *specific* narrator
    already verified as expected for the question (e.g., short given names
    like ``شعبة`` or ``سفيان`` or ``نافع`` or ``عائشة`` when present inside
    the narrator's own record).
    """
    aliases = narrator_strict_forms(name_ar, name_ar_mapped)
    for raw in (name_ar, name_ar_mapped):
        for seg in _split_clean_segments(raw):
            words = seg.split()
            if not words:
                continue
            aliases.add(seg)
            if len(words) >= 2 and words[:2] == ["ام", "المؤمنين"]:
                aliases.add(" ".join(words[2:]))
                if len(words) >= 3:
                    aliases.add(words[2])
            if words[0] in {"شعبة", "نافع", "عائشة", "حفصة", "قتادة", "طاوس"}:
                aliases.add(words[0])
            if words[-1] in {"الزهري", "الاعمش", "القعنبي", "الشعبي", "البخاري", "الناقد", "السمين", "الخدري", "الدوسي", "البجلي", "الثوري", "الداري"}:
                if words[-1] != "الدوسي" and words[-1] != "البجلي":
                    aliases.add(words[-1])
                if len(words) >= 2:
                    aliases.add(f"{words[0]} {words[-1]}")
    for alias in extra_aliases:
        norm = normalize_arabic_name(alias)
        if norm:
            aliases.add(norm)
    return {a for a in aliases if len(a) >= 3}


@dataclass(frozen=True)
class NarratorMention:
    phrase: str
    narrator_ids: frozenset[str]
    start: int
    end: int


class NarratorLexicon:
    """Compiled longest-match Arabic narrator phrase detector built from MIS rows."""

    def __init__(self, phrase_to_ids: dict[str, set[str]]) -> None:
        self.phrase_to_ids: dict[str, frozenset[str]] = {
            p: frozenset(ids) for p, ids in phrase_to_ids.items() if p
        }
        # Longest word count then longest char length first so specific names
        # (e.g. "عبد الله بن عمر بن الخطاب") win over inner substrings ("عمر بن الخطاب").
        sorted_phrases = sorted(
            self.phrase_to_ids.keys(),
            key=lambda s: (-len(s.split()), -len(s), s),
        )
        if sorted_phrases:
            alternation = "|".join(re.escape(p) for p in sorted_phrases)
            self._regex: re.Pattern[str] | None = re.compile(
                rf"(?<![\w\u0621-\u064a])[وفبلك]?(?P<narrator>{alternation})(?![\w\u0621-\u064a])"
            )
        else:
            self._regex = None

    @classmethod
    def from_records(cls, records: Iterable[dict[str, Any]]) -> "NarratorLexicon":
        phrase_to_ids: dict[str, set[str]] = {}
        for row in records:
            nid = str(row["narrator_id"])
            forms = narrator_strict_forms(row.get("name_ar"), row.get("name_ar_mapped"))
            for form in forms:
                phrase_to_ids.setdefault(form, set()).add(nid)
        return cls(phrase_to_ids)

    @classmethod
    def from_connection(cls, connection: sqlite3.Connection) -> "NarratorLexicon":
        rows = connection.execute(
            "SELECT narrator_id, name_ar, name_ar_mapped FROM mis_narrator"
        ).fetchall()
        return cls.from_records([dict(r) for r in rows])

    def find_mentions(self, text: str) -> list[NarratorMention]:
        if not text or self._regex is None:
            return []
        norm = normalize_arabic_name(text)
        if not norm:
            return []
        mentions: list[NarratorMention] = []
        for match in self._regex.finditer(norm):
            phrase = match.group("narrator")
            mentions.append(
                NarratorMention(
                    phrase=phrase,
                    narrator_ids=self.phrase_to_ids.get(phrase, frozenset()),
                    start=match.start("narrator"),
                    end=match.end("narrator"),
                )
            )
        return mentions


@lru_cache(maxsize=4)
def load_narrator_lexicon(db_path: str | None = None) -> NarratorLexicon:
    """Load and cache ``NarratorLexicon`` from ``sanad_graph.sqlite``."""
    resolved = Path(db_path) if db_path is not None else GRAPH_DB_PATH
    conn = open_graph(resolved)
    try:
        return NarratorLexicon.from_connection(conn)
    finally:
        conn.close()


def allowed_forms_from_isnad_results(isnad_results: Iterable[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """Collect allowed narrator IDs and normalized name forms from ``get_isnad`` results."""
    allowed_ids: set[str] = set()
    allowed_forms: set[str] = set()
    for ctx in isnad_results:
        for isnad in ctx.get("isnads") or ():
            for narrator in isnad.get("narrators") or ():
                nid = str(narrator.get("narrator_id") or "")
                if nid:
                    allowed_ids.add(nid)
                allowed_forms.update(
                    narrator_strict_forms(
                        narrator.get("name_ar"),
                        narrator.get("name_ar_mapped"),
                    )
                )
                allowed_forms.update(
                    narrator_expected_aliases(
                        narrator.get("name_ar"),
                        narrator.get("name_ar_mapped"),
                    )
                )
    return allowed_ids, allowed_forms


def find_disallowed_narrators(
    answer: str,
    isnad_results: Iterable[dict[str, Any]],
    lexicon: NarratorLexicon,
) -> list[str]:
    """Return any narrator phrases mentioned in ``answer`` not present in ``isnad_results``."""
    allowed_ids, allowed_forms = allowed_forms_from_isnad_results(isnad_results)
    disallowed: list[str] = []
    seen: set[str] = set()
    for mention in lexicon.find_mentions(answer):
        if mention.phrase in allowed_forms:
            continue
        if allowed_ids and (mention.narrator_ids & allowed_ids):
            continue
        if mention.phrase not in seen:
            seen.add(mention.phrase)
            disallowed.append(mention.phrase)
    return disallowed


def text_contains_expected_narrator(text: str, narrator: dict[str, Any]) -> bool:
    """Return True if normalized ``text`` contains any accepted alias of ``narrator``."""
    norm = normalize_arabic_name(text)
    if not norm:
        return False
    aliases = narrator_expected_aliases(
        narrator.get("name_ar"),
        narrator.get("name_ar_mapped"),
        extra_aliases=narrator.get("aliases") or (),
    )
    for alias in sorted(aliases, key=len, reverse=True):
        if re.search(rf"(?<![\w\u0621-\u064a]){re.escape(alias)}(?![\w\u0621-\u064a])", norm):
            return True
    return False
