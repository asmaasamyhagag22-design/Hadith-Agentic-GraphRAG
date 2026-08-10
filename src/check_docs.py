"""
حارس ضد انحراف التوثيق.

EXPERIMENTS.md هو مصدر الحقيقة للأرقام. الملف ده بيتأكد إن:

1. كل رقم في جداول النتايج في README موجود في EXPERIMENTS.md
2. بصمات مجموعات التقييم لسه مطابقة لللي EXPERIMENTS مسجّله

الحاجة التانية هي الأهم: لو اتعدّل golden.jsonl والأرقام
فضلت مكانها، الفرق بعد شهر هيبان كأنه تحسّن في النظام وهو
تغيير في البيانات.
"""

import sys
import re
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import BASE_DIR, GOLDEN_PATH, SYNTHETIC_EVAL_PATH, MUSLIM_JSON_PATH

README = BASE_DIR / "README.md"
EXPERIMENTS = BASE_DIR / "EXPERIMENTS.md"

TRACKED_FILES = (GOLDEN_PATH, SYNTHETIC_EVAL_PATH, MUSLIM_JSON_PATH)

HASH_PREFIX = 16

# الأرقام اللي بتتقارن: نِسب مئوية وقيم MRR
_PERCENT = re.compile(r"\b\d{1,3}%")
_DECIMAL = re.compile(r"\b0\.\d{3}\b")

# جداول النتايج في README محصورة بين العنوانين دول
_RESULTS_START = "## Results"
_RESULTS_END = "## Design decisions"


def short_hash(path):

    return hashlib.sha256(path.read_bytes()).hexdigest()[:HASH_PREFIX]


def results_section(text):

    start = text.find(_RESULTS_START)
    end = text.find(_RESULTS_END)

    if start == -1 or end == -1:
        raise SystemExit(
            f"Could not locate the results section in {README.name} — "
            f"expected headings '{_RESULTS_START}' and '{_RESULTS_END}'."
        )

    return text[start:end]


def numbers_in(text):

    return set(_PERCENT.findall(text)) | set(_DECIMAL.findall(text))


def check_numbers():

    readme = README.read_text(encoding="utf-8")
    experiments = EXPERIMENTS.read_text(encoding="utf-8")

    claimed = numbers_in(results_section(readme))
    recorded = numbers_in(experiments)

    missing = sorted(claimed - recorded)

    if missing:
        print("✗ numbers in README results tables that EXPERIMENTS.md "
              "does not record:")
        for number in missing:
            print(f"    {number}")
        return False

    print(f"✓ all {len(claimed)} numbers in the README results tables "
          f"appear in EXPERIMENTS.md")

    return True


def check_hashes():

    experiments = EXPERIMENTS.read_text(encoding="utf-8")

    ok = True

    for path in TRACKED_FILES:

        digest = short_hash(path)

        if digest not in experiments:
            print(
                f"✗ {path.name} has hash {digest}, which EXPERIMENTS.md "
                f"does not record — the dataset changed but the numbers "
                f"were not re-measured"
            )
            ok = False

    if ok:
        print(f"✓ all {len(TRACKED_FILES)} evaluation datasets match the "
              f"hashes recorded in EXPERIMENTS.md")

    return ok


def main():

    print("Documentation consistency\n")

    passed = all([check_numbers(), check_hashes()])

    print()

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
