"""
حارس ضد انحراف التوثيق.

EXPERIMENTS.md هو مصدر الحقيقة للأرقام. الملف ده بيتأكد إن:

1. كل رقم في جداول النتايج في README موجود في EXPERIMENTS.md
2. بصمات مجموعات التقييم لسه مطابقة لللي EXPERIMENTS مسجّله

الحاجة التانية هي الأهم: لو اتعدّل golden.jsonl والأرقام
فضلت مكانها، الفرق بعد شهر هيبان كأنه تحسّن في النظام وهو
تغيير في البيانات.

البصمة بتتحسب على نص canonical: CRLF بيتحوّل لـ LF قبل
SHA-256. من غير الخطوة دي نفس الـ commit بيدي بصمة مختلفة
على ويندوز وعلى لينكس، فالبوابة كانت بتفشل من غير ما تتغير
أي بيانات. مفيش أي تطبيع تاني — تغيير حرف واحد أو ترتيب
سطر أو رقم حديث بيغيّر البصمة زي ما هو مطلوب.
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

# خلية البصمة في جدول «نسخة القياس» — بالضبط HASH_PREFIX رقم
# ست عشري بين علامتي `. البصمات الكاملة (64) في تجارب تانية
# مش بتطابق، وده مقصود: كل ملف بيتقارن بالخلية بتاعته هو.
_HASH_CELL = re.compile(r"`([0-9a-f]{%d})`" % HASH_PREFIX)

# جداول النتايج في README محصورة بين العنوانين دول
_RESULTS_START = "## Results"
_RESULTS_END = "## Design decisions"


def canonical_bytes(data):
    """
    نفس النص = نفس البايتات، مهما كان اصطلاح نهاية السطر.

    ده التطبيع الوحيد المسموح بيه. الترتيب والمسافات جوه
    السطر وقيم البيانات بتفضل زي ما هي.
    """

    return data.replace(b"\r\n", b"\n")


def canonical_hash(path):

    return hashlib.sha256(
        canonical_bytes(path.read_bytes())
    ).hexdigest()[:HASH_PREFIX]


def recorded_hash(experiments, name):
    """
    بيجيب البصمة المسجّلة للملف ده تحديدًا.

    الإصدار القديم كان بيدوّر على البصمة في المستند كله، فأي
    بصمة مسجّلة في أي تجربة تانية كانت بتعدّي البوابة. هنا
    السطر لازم يذكر الملف نفسه.
    """

    needle = f"`data/raw/{name}`"

    found = [
        digest
        for line in experiments.splitlines() if needle in line
        for digest in _HASH_CELL.findall(line)
    ]

    if not found:
        return None

    if len(set(found)) > 1:
        raise SystemExit(
            f"{EXPERIMENTS.name} records more than one hash for {name}: "
            f"{sorted(set(found))}"
        )

    return found[0]


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

        digest = canonical_hash(path)
        expected = recorded_hash(experiments, path.name)

        if expected is None:
            print(
                f"✗ {path.name} has no recorded hash in "
                f"{EXPERIMENTS.name} — every evaluation dataset must be "
                f"pinned to the numbers measured on it"
            )
            ok = False

        elif digest != expected:
            print(
                f"✗ {path.name} hashes to {digest}, but {EXPERIMENTS.name} "
                f"records {expected} — the dataset changed but the numbers "
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
