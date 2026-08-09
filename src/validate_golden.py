"""
بوابة تحقق للـ golden dataset — تتشغّل قبل أي تقييم.

السبب: تلات مرات في المشروع طلع إن «فشل النظام» كان في
الحقيقة خطأ في الـ ground truth (عاشوراء، الغش، النية).
الأخطاء دي مش بتعلن عن نفسها — بتظهر كأرقام سيئة، وبتتصدّق.

بيخرج بكود 1 لو فيه مشكلة عشان ينفع يتحط في CI.
"""

import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import MUSLIM_JSON_PATH, GOLDEN_PATH
from utils import strip_diacritics

_ALEF_FORMS = str.maketrans({
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ٱ": "ا",
    "ى": "ي",
    "ة": "ه",
})

_NON_ARABIC = re.compile(r"[^ء-ي ]+")

# أول كام كلمة من المتن بتتقارن. قصيرة عشان الاختلافات
# الإملائية في آخر الاقتباس متسقطش تحقق صحيح.
_MATN_PROBE_WORDS = 5


def normalize(text):

    text = strip_diacritics(text).translate(_ALEF_FORMS)

    return " ".join(_NON_ARABIC.sub(" ", text).split())


def load_corpus_text():
    """{hadith_id: نص مطبَّع}"""

    with open(MUSLIM_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        hadith["id"]: normalize(hadith.get("arabic", ""))
        for hadith in data.get("hadiths", [])
    }


def load_golden(path=GOLDEN_PATH):

    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def check_item(item, corpus, all_text):

    problems = []

    question = item.get("question", "<no question>")
    kind = item.get("type", "matn")
    hadith_ids = item.get("hadith_ids", [])
    answerable = item.get("answerable", True)

    for hadith_id in hadith_ids:
        if hadith_id not in corpus:
            problems.append(f"hadith id {hadith_id} not found in the corpus")

    # أسئلة الرواة ليها أحاديث مرجعية رغم إنها غير قابلة
    # للإجابة نصيًا — الاستثناء ده مقصود.
    if not answerable and kind != "narrator" and hadith_ids:
        problems.append(
            f"answerable=false but hadith_ids is not empty ({hadith_ids})"
        )

    if answerable and not hadith_ids:
        problems.append("answerable=true but no hadith_ids given")

    matn = item.get("matn", "").strip()

    if matn and hadith_ids and kind == "matn":

        probe = " ".join(normalize(matn).split()[:_MATN_PROBE_WORDS])

        found = any(
            probe in corpus[h]
            for h in hadith_ids
            if h in corpus
        )

        if not found:
            problems.append(
                f"matn text not found in any listed hadith — probe: '{probe}'"
            )

    # سؤال رفض لازم يكون فعلاً مالوش أثر في المتن، وإلا
    # يبقى إحنا بنختبر رفض حاجة موجودة.
    if kind == "refusal":
        problems.extend(check_refusal(item, corpus, all_text))

    return question, problems


def check_refusal(item, corpus, all_text):
    """
    نوعين من الغياب:

    probe_terms          — كل لفظ منهم لازم يكون غايب خالص
    probe_terms_together — الألفاظ موجودة كل واحد لوحده، بس
                           المفروض ما يجتمعوش في حديث واحد
                           (زي «الكهف» و«الجمعة»)
    """

    problems = []

    for term in item.get("probe_terms", []):

        if normalize(term) in all_text:
            problems.append(
                f"refusal question but '{term}' does appear in the corpus"
            )

    together = [normalize(t) for t in item.get("probe_terms_together", [])]

    if together:

        matches = [
            hadith_id
            for hadith_id, text in corpus.items()
            if all(term in text for term in together)
        ]

        if matches:
            problems.append(
                f"refusal question but {item['probe_terms_together']} "
                f"co-occur in hadith(s) {matches[:5]}"
            )

    if not item.get("probe_terms") and not together:
        problems.append(
            "refusal question has no probe_terms — its premise is unchecked"
        )

    return problems


def main():

    corpus = load_corpus_text()
    all_text = "\n".join(corpus.values())

    golden = load_golden()

    print(f"Corpus hadiths : {len(corpus)}")
    print(f"Golden entries : {len(golden)}\n")

    total_problems = 0

    for item in golden:

        question, problems = check_item(item, corpus, all_text)

        if problems:
            total_problems += len(problems)
            print(f"✗ {question}")
            for problem in problems:
                print(f"    {problem}")

    if total_problems:
        print(f"\n{total_problems} problem(s) found.")
        return 1

    print("All entries valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
