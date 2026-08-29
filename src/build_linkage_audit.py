"""
عيّنة مراجعة يدوية مُطبَّقة (stratified) لربط MIS بمجموعتنا.

الغرض **اكتشاف أنماط الفشل**، مش تأكيد النجاح. عيّنة عشوائية
من المطابقات السهلة عالية التشابه هتديك رقم متفائل ومالوش
قيمة تشخيصية — عشان كده الطبقات هنا مقصود منها تشمل الحالات
اللي الربط بيقع فيها.

المخرَج ملف مراجعة **من غير حكم** — القرار للمراجع البشري،
مش للسكريبت.

⚠ الرقم 94.0% هو **تغطية ربط آلية عالية الثقة** تحت معيار
SequenceMatcher ratio حقيقي ≥ 0.90. مش دقة ولا صحة. والتشابه النصي **مساندة آلية**
مش تحقّق مستقل: توليد المرشح والتحقق منه الاتنين مشتقين من
نص الحديث نفسه، فهما مرتبطان بالتصميم.
"""

import sys
import csv
import json
import random
import difflib
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import PROCESSED_DIR
from profile_mis import (
    read_sheet,
    load_corpus,
    normalize,
    tail_signature,
    CONTENT,
    EDGES,
)

AUDIT_CSV = PROCESSED_DIR / "linkage_audit_sample.csv"
AUDIT_META = PROCESSED_DIR / "linkage_audit_sampling.json"

SEED = 20260809
PER_STRATUM = 12

SHORT_TEXT_WORDS = 25

COLUMNS = [
    "stratum",
    "our_idInBook",
    "our_chapterId",
    "mis_HadithNo",
    "mis_ChapterNo",
    "similarity",
    "link_strategy",
    "our_text",
    "mis_text",
    "manual_verdict",
    "notes",
]


def similarity(ours, theirs):

    return round(
        difflib.SequenceMatcher(
            None, normalize(ours).split(),
            normalize(theirs).split(), autojunk=False
        ).quick_ratio(),
        3,
    )


def build_candidates(corpus, mis, multi_isnad_hadiths):
    """
    بيصنّف كل حديث عندنا لطبقة واحدة بالظبط. الترتيب هنا
    أولوية: الحالات الصعبة بتاخد الأسبقية على السهلة عشان
    ما تتبلعش جوه طبقة «تشابه عالي».
    """

    index = {}

    for record in mis:
        key = tail_signature(record["HadithText_GhairMushakkal"])
        if key:
            index.setdefault(key, []).append(record)

    rows = []

    for hadith in corpus:

        key = tail_signature(hadith["arabic"])
        candidates = index.get(key, [])

        words = len(normalize(hadith["arabic"]).split())

        if not candidates:
            # لا مرشح إطلاقًا — أهم طبقة، الربط فشل هنا
            rows.append(("unmatched", hadith, None, None, "tail (none)"))
            continue

        if len(candidates) > 1:
            # نفس النهاية عند أكتر من حديث — تكرار ألفاظ
            rows.append((
                "ambiguous_tail", hadith, candidates[0],
                similarity(hadith["arabic"],
                           candidates[0]["HadithText_GhairMushakkal"]),
                f"tail ({len(candidates)} candidates)",
            ))
            continue

        record = candidates[0]
        score = similarity(hadith["arabic"],
                           record["HadithText_GhairMushakkal"])

        if score < 0.70:
            stratum = "sim_below_0.70"
        elif score < 0.90:
            stratum = "sim_0.70_0.90"
        elif score < 0.95:
            stratum = "sim_0.90_0.95_borderline"
        elif words <= SHORT_TEXT_WORDS:
            stratum = "very_short_text"
        elif record["HadithNo"] in multi_isnad_hadiths:
            stratum = "multi_isnad"
        else:
            stratum = "sim_above_0.95"

        rows.append((stratum, hadith, record, score, "tail (unique)"))

    return rows


def stratify(rows, chapters_by_hadith):
    """
    اختيار مُطبَّق مع توزيع على الكتب: جوه كل طبقة بنرتّب
    عشوائيًا لكن بنحاول ما ناخدش كذا حديث من نفس الكتاب،
    عشان العيّنة ما تتركزش في كتاب واحد.
    """

    rng = random.Random(SEED)

    grouped = {}

    for row in rows:
        grouped.setdefault(row[0], []).append(row)

    selected = []
    coverage = {}

    for stratum in sorted(grouped):

        pool = grouped[stratum][:]
        rng.shuffle(pool)

        seen_chapters = set()
        picked = []

        # تمريرة أولى: كتاب مختلف لكل عيّنة
        for row in pool:
            chapter = chapters_by_hadith[row[1]["idInBook"]]
            if chapter not in seen_chapters:
                seen_chapters.add(chapter)
                picked.append(row)
            if len(picked) == PER_STRATUM:
                break

        # تمريرة ثانية: كمّل لو الطبقة أصغر من عدد الكتب
        if len(picked) < PER_STRATUM:
            for row in pool:
                if row not in picked:
                    picked.append(row)
                if len(picked) == PER_STRATUM:
                    break

        selected.extend(picked)

        coverage[stratum] = {
            "population": len(pool),
            "sampled": len(picked),
            "distinct_chapters_in_sample": len(
                {chapters_by_hadith[r[1]["idInBook"]] for r in picked}
            ),
        }

    return selected, coverage


def reviewed_label_count(path=AUDIT_CSV):
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return sum(
            bool(row.get("manual_verdict", "").strip())
            for row in csv.DictReader(handle)
        )


def main():

    reviewed = reviewed_label_count()
    if reviewed:
        raise RuntimeError(
            f"Refusing to overwrite {AUDIT_CSV}: "
            f"{reviewed} diagnostic rows have human labels."
        )

    corpus = load_corpus()
    _, mis = read_sheet(CONTENT)
    _, edges = read_sheet(EDGES)

    sanad_counts = Counter()
    for edge in edges:
        sanad_counts[edge["HadithNo"]] = max(
            sanad_counts[edge["HadithNo"]], edge["SanadNo"] or 0
        )

    multi_isnad = {h for h, n in sanad_counts.items() if n > 1}

    chapters = {h["idInBook"]: h["chapterId"] for h in corpus}

    rows = build_candidates(corpus, mis, multi_isnad)

    population = Counter(r[0] for r in rows)

    selected, coverage = stratify(rows, chapters)

    AUDIT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(AUDIT_CSV, "w", encoding="utf-8-sig",
              newline="") as f:

        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()

        for stratum, hadith, record, score, strategy in selected:
            writer.writerow({
                "stratum": stratum,
                "our_idInBook": hadith["idInBook"],
                "our_chapterId": hadith["chapterId"],
                "mis_HadithNo": record["HadithNo"] if record else "",
                "mis_ChapterNo": record["ChapterNo"] if record else "",
                "similarity": score if score is not None else "",
                "link_strategy": strategy,
                "our_text": hadith["arabic"],
                "mis_text": (
                    record["HadithText_GhairMushakkal"] if record else ""
                ),
                "manual_verdict": "",
                "notes": "",
            })

    meta = {
        "seed": SEED,
        "per_stratum_target": PER_STRATUM,
        "total_sampled": len(selected),
        "criterion_note": (
            "94.0% is high-confidence automated linkage coverage under an "
            "order-sensitive full-text SequenceMatcher ratio >= 0.90. "
            "It is not precision. Full-text similarity "
            "is automated textual corroboration, not independent "
            "validation: candidate generation and corroboration both "
            "derive from the hadith text."
        ),
        "strata_definitions": {
            "unmatched": "no MIS record shares our tail signature",
            "ambiguous_tail": "tail signature matches several MIS records",
            "sim_below_0.70": "unique tail match, full-text similarity < 0.70",
            "sim_0.70_0.90": "unique tail match, similarity 0.70-0.90",
            "sim_0.90_0.95_borderline": "just above the 0.90 criterion",
            "very_short_text": (
                f"similarity >= 0.95 and <= {SHORT_TEXT_WORDS} words — "
                "short texts collide more easily"
            ),
            "multi_isnad": (
                "similarity >= 0.95 and the MIS record carries more than "
                "one isnad"
            ),
            "sim_above_0.95": "the easy case, included as a control",
        },
        "population_by_stratum": dict(population),
        "sample_by_stratum": coverage,
        "chapter_spread": "one hadith per chapter first, then top up",
    }

    with open(AUDIT_META, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"population by stratum ({len(rows)} corpus records)")
    for stratum in sorted(population):
        info = coverage.get(stratum, {})
        print(f"  {stratum:<26} {population[stratum]:>6}  "
              f"sampled {info.get('sampled', 0):>3}  "
              f"chapters {info.get('distinct_chapters_in_sample', 0):>3}")

    print(f"\nreview file  -> {AUDIT_CSV}  ({len(selected)} rows)")
    print(f"sampling doc -> {AUDIT_META}")
    print("\nmanual_verdict is intentionally blank: correct / wrong / uncertain")


if __name__ == "__main__":
    main()
