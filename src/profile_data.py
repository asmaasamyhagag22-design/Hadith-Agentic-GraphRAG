"""
تنميط البيانات الخام المتاحة فعلاً — الدليل وراء تقرير الجرد.

بيطبع JSON عشان الأرقام تبقى قابلة لإعادة الإنتاج بدل ما
تكون ادعاءات في محادثة. ما بيطبّعش وما بيدمجش أي حاجة —
قياس فقط.
"""

import sys
import json
import re
import hashlib
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import MUSLIM_JSON_PATH, PROCESSED_DIR
from utils import strip_diacritics, normalize_for_matching

PROFILE_PATH = PROCESSED_DIR / "data_profile.json"

# صيغ التحمّل والأداء — علامات وجود سند في النص العربي.
# مش مستخدمة للاستخراج هنا، بس لقياس كثافة البنية.
_TRANSMISSION = re.compile(
    r"(?<![ء-ي])(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|سمعت|عن)(?![ء-ي])"
)

_ARABIC_LETTER = re.compile(r"[ء-ي]")


def normalize(text):

    normalized, _ = normalize_for_matching(strip_diacritics(text))

    return normalized


def profile_corpus(data):

    hadiths = data["hadiths"]

    field_presence = Counter()
    english_keys = Counter()

    for hadith in hadiths:
        field_presence.update(hadith.keys())
        english_keys.update(hadith.get("english", {}).keys())

    narrators = [
        str(h.get("english", {}).get("narrator", "")).strip()
        for h in hadiths
    ]

    non_empty = [n for n in narrators if n]

    # كام كلمة عربية في حقل narrator — لو صفر يبقى إنجليزي بحت
    arabic_in_narrator = sum(1 for n in non_empty if _ARABIC_LETTER.search(n))

    link_counts = [
        len(_TRANSMISSION.findall(normalize(h["arabic"])))
        for h in hadiths
    ]

    link_distribution = Counter(link_counts)

    return {
        "records": len(hadiths),
        "chapters": len(data["chapters"]),
        "hadith_fields": dict(field_presence),
        "english_subfields": dict(english_keys),
        "structured_narrator_fields": [
            key for key in field_presence
            if any(t in key.lower() for t in
                   ("narr", "isnad", "sanad", "rawi", "chain", "grade"))
        ],
        "english_narrator_field": {
            "non_empty": len(non_empty),
            "empty": len(hadiths) - len(non_empty),
            "coverage": round(len(non_empty) / len(hadiths), 3),
            "mean_chars": round(
                sum(len(n) for n in non_empty) / max(len(non_empty), 1)
            ),
            "contains_arabic_script": arabic_in_narrator,
            "distinct_values": len(set(non_empty)),
            "is_free_prose": True,
            "note": (
                "opening sentence of the English translation, not a "
                "structured narrator list"
            ),
        },
        "arabic_transmission_markers_per_hadith": {
            "min": min(link_counts),
            "median": sorted(link_counts)[len(link_counts) // 2],
            "max": max(link_counts),
            "zero_markers": link_distribution[0],
            "distribution_head": dict(
                sorted(link_distribution.items())[:12]
            ),
        },
    }


def _directory_profile(path):
    files = sorted(item for item in path.rglob("*") if item.is_file())
    digest = hashlib.sha256()
    for item in files:
        digest.update(str(item.relative_to(path)).replace("\\", "/").encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return {
        "file_count": len(files),
        "bytes": sum(item.stat().st_size for item in files),
        "combined_sha256": digest.hexdigest(),
        "files": [str(item.relative_to(path)) for item in files],
    }


def profile_sources():
    """كل مصدر بيانات فعلي مطلوب لبوابة الربط، وهل هو موجود."""

    required = {
        "hadith_corpus": MUSLIM_JSON_PATH,
        "mis_hadith_and_chains": Path("data/raw/external/mis"),
        "itqan_narrator_profiles": Path("data/raw/external/itqan"),
    }

    report = {}

    for name, path in required.items():

        exists = path.exists()

        entry = {"path": str(path), "present": exists}

        if exists and path.is_file():
            entry["bytes"] = path.stat().st_size
            entry["sha256_16"] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()[:16]

        if exists and path.is_dir():
            entry.update(_directory_profile(path))

        report[name] = entry

    return report


def main():

    with open(MUSLIM_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    profile = {
        "sources": profile_sources(),
        "corpus": profile_corpus(data),
    }

    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(PROFILE_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    print(json.dumps(profile, ensure_ascii=False, indent=2))
    print(f"\nSaved -> {PROFILE_PATH}")


if __name__ == "__main__":
    main()
