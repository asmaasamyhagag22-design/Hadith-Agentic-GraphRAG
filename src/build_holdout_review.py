"""Build human-review Markdown package (`docs/holdout_review.md`) from holdout_draft.jsonl.

Reads `data/raw/holdout_draft.jsonl` and `data/raw/muslim.json` strictly read-only,
extracting the vocalised matn for every candidate hadith ID, grouping items by
category/type (`single_hadith`, `sibling_hadiths`, `out_of_scope_refusal`/`refusal`),
and attaching `[ ] accept / [ ] reject / [ ] edit` review checkboxes.

NEVER modifies or runs any model/retrieval evaluation on `holdout_draft.jsonl`.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import BASE_DIR, MUSLIM_JSON_PATH, RAW_DIR
from src.utils import split_isnad_matn

HOLDOUT_DRAFT_PATH = RAW_DIR / "holdout_draft.jsonl"
HOLDOUT_REVIEW_PATH = BASE_DIR / "docs" / "holdout_review.md"

GROUP_ORDER: tuple[tuple[str, str], ...] = (
    ("single_hadith", "Single-hadith matn questions (`type=matn`, `category=single_hadith`)"),
    ("sibling_hadiths", "Sibling-hadiths matn questions (`type=matn`, `category=sibling_hadiths`)"),
    ("out_of_scope_refusal", "Out-of-scope refusal questions (`type=refusal`, `category=out_of_scope_refusal`)"),
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_holdout_draft(path: Path = HOLDOUT_DRAFT_PATH) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_muslim_index(path: Path = MUSLIM_JSON_PATH) -> tuple[dict[int, dict[str, Any]], dict[int, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    chapters = {
        int(ch["id"]): str(ch.get("arabic", ""))
        for ch in data.get("chapters", [])
    }
    hadiths = {
        int(h["id"]): h
        for h in data.get("hadiths", [])
    }
    return hadiths, chapters


def _group_key(row: dict[str, Any]) -> str:
    cat = str(row.get("category") or "").strip()
    if cat:
        return cat
    return "out_of_scope_refusal" if row.get("type") == "refusal" else "single_hadith"


def _format_blockquote(text: str) -> list[str]:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ["> *(empty)*"]
    return [f"> {cleaned}"]


def build_holdout_review_markdown(
    *,
    draft_path: Path = HOLDOUT_DRAFT_PATH,
    muslim_path: Path = MUSLIM_JSON_PATH,
) -> str:
    rows = load_holdout_draft(draft_path)
    hadiths, chapters = load_muslim_index(muslim_path)
    draft_sha = sha256_file(draft_path)
    muslim_sha = sha256_file(muslim_path)

    group_counts = Counter(_group_key(r) for r in rows)
    type_counts = Counter(str(r.get("type", "")) for r in rows)

    # Preserve canonical group order, plus any unexpected extra groups sorted cleanly.
    ordered_keys = [k for k, _ in GROUP_ORDER if group_counts.get(k, 0) > 0]
    title_by_key = dict(GROUP_ORDER)
    for k in sorted(group_counts):
        if k not in ordered_keys:
            ordered_keys.append(k)
            title_by_key[k] = f"Other (`{k}`)"

    lines: list[str] = [
        "# Musnad Held-Out Evaluation Review Package (`holdout_draft.jsonl`)",
        "",
        "Generated read-only from `data/raw/holdout_draft.jsonl` and `data/raw/muslim.json` for manual human specialist verification **before** freezing `holdout.jsonl` and before running any held-out evaluation.",
        "",
        "- **Draft source**: `data/raw/holdout_draft.jsonl` (`sha256`: `" + draft_sha + "`)",
        "- **Corpus source**: `data/raw/muslim.json` (`sha256`: `" + muslim_sha + "`)",
        f"- **Total draft questions**: `{len(rows)}` (`matn={type_counts.get('matn', 0)}`, `refusal={type_counts.get('refusal', 0)}`)",
        f"- **Breakdown by group**: `single_hadith={group_counts.get('single_hadith', 0)}`, `sibling_hadiths={group_counts.get('sibling_hadiths', 0)}`, `out_of_scope_refusal={group_counts.get('out_of_scope_refusal', 0)}`",
        "- **Rule**: Do not modify `data/raw/holdout_draft.jsonl` or run model/retrieval evaluations on it until human review is completed and frozen.",
        "",
        "## Review Instructions",
        "",
        "For each item below, inspect the Arabic question, verify the candidate IDs against the **vocalised matn** loaded directly from `data/raw/muslim.json` (candidate lists are ordered top-12 retrieval candidates from `holdout_draft.jsonl`), and mark one decision checkbox:",
        "- `[ ] accept` — keep the question and draft gold `hadith_ids` (or confirm valid out-of-scope refusal).",
        "- `[ ] reject` — exclude the item (ambiguous question, multiple unrelated hadiths, or in-scope match found for a draft refusal).",
        "- `[ ] edit` — revise wording or approve an updated subset/superset of `hadith_ids` from the candidates below.",
        "",
        "---",
        "",
    ]

    # Index original 1-based line numbers so edits map deterministically back to holdout_draft.jsonl.
    indexed_rows = list(enumerate(rows, start=1))

    for g_idx, key in enumerate(ordered_keys, start=1):
        group_items = [(orig_idx, r) for orig_idx, r in indexed_rows if _group_key(r) == key]
        lines.append(f"## {g_idx}. {title_by_key[key]} — `n = {len(group_items)}`")
        lines.append("")

        for item_pos, (orig_idx, row) in enumerate(group_items, start=1):
            q_type = str(row.get("type", ""))
            category = str(row.get("category", ""))
            answerable = bool(row.get("answerable", False))
            draft_gold = [int(x) for x in (row.get("hadith_ids") or [])]
            candidates = [int(x) for x in (row.get("candidate_gold_ids") or [])]

            # Include any draft_gold IDs first/preserved without dropping anything.
            display_ids: list[int] = list(candidates)
            for gid in draft_gold:
                if gid not in display_ids:
                    display_ids.insert(0, gid)

            lines.append(f"### Item {orig_idx:03d} ({key} #{item_pos})")
            lines.append("")
            lines.append(f"- **Question**: {row.get('question', '')}")
            lines.append(
                f"- **Type**: `{q_type}` | **Category**: `{category}` | "
                f"**Answerable**: `{answerable}` | **Draft `hadith_ids`**: `{draft_gold}` | "
                f"**Candidate IDs (`{len(display_ids)}`)**: `{display_ids}`"
            )
            if row.get("probe_terms"):
                lines.append(f"- **Probe terms**: `{row['probe_terms']}`")
            if row.get("probe_terms_together"):
                lines.append(f"- **Probe terms together**: `{row['probe_terms_together']}`")
            if row.get("note"):
                lines.append(f"- **Draft note**: {row['note']}")
            lines.append("")
            lines.append("**Review decision:**")
            lines.append("- [ ] accept")
            lines.append("- [ ] reject")
            lines.append("- [ ] edit (approved `hadith_ids` / revised text): ______________________________")
            lines.append("")

            if display_ids:
                lines.append("**Candidate hadiths (vocalised *matn* from `data/raw/muslim.json`):**")
                lines.append("")
                draft_set = set(draft_gold)
                for c_rank, hid in enumerate(display_ids, start=1):
                    h = hadiths.get(hid)
                    gold_tag = " **[draft gold]**" if hid in draft_set else ""
                    if h is None:
                        lines.append(f"- **Candidate {c_rank}: `hadith_id={hid}`**{gold_tag} — *(NOT FOUND in `muslim.json`)*")
                        lines.append("")
                        continue
                    arabic_full = str(h.get("arabic", ""))
                    matn_voc = split_isnad_matn(arabic_full)
                    chap_ar = chapters.get(int(h.get("chapterId", -1)), "Unknown")
                    id_in_book = h.get("idInBook", "?")
                    split_note = (
                        " *(split fallback: full vocalised hadith shown)*"
                        if matn_voc == arabic_full
                        else ""
                    )
                    lines.append(
                        f"- **Candidate {c_rank}: `hadith_id={hid}`**{gold_tag} "
                        f"(`idInBook={id_in_book}`, chapter: `{chap_ar}`){split_note}:"
                    )
                    lines.extend(_format_blockquote(matn_voc))
                    lines.append("")
            else:
                lines.append("*(No candidate hadiths — out-of-scope refusal item; verify no match exists in Sahih Muslim.)*")
                lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    content = build_holdout_review_markdown()
    HOLDOUT_REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    HOLDOUT_REVIEW_PATH.write_text(content, encoding="utf-8")
    print(
        f"Wrote {HOLDOUT_REVIEW_PATH} ({len(content.splitlines())} lines, "
        f"{len(content.encode('utf-8'))} bytes)"
    )


if __name__ == "__main__":
    main()
