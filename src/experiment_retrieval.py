"""
بيشغّل نفس الأسئلة على الصيغ التلاتة ويطبع النتايج للمقارنة.

كل صيغة بتتحمّل بملف الـ vectors وملف الـ ids بتوعها مع بعض،
فلو حصل عدم تطابق الـ Retriever هيرمي خطأ واضح بدل ما يرجّع
أرقام أحاديث غلط بهدوء.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    VECTORS_PATH,
    IDS_PATH,
    VECTORS_MATN,
    IDS_MATN,
    VECTORS_MATN_WITH_TITLE,
    IDS_MATN_WITH_TITLE,
)
from retrieve import Retriever
from answer import answer_question, load_questions


EXPERIMENTS = [
    ("Full (Sanad + Matn)", VECTORS_PATH, IDS_PATH),
    ("Matn Only", VECTORS_MATN, IDS_MATN),
    ("Chapter + Matn", VECTORS_MATN_WITH_TITLE, IDS_MATN_WITH_TITLE),
]


def main():

    questions = load_questions()

    print(f"\nRunning {len(questions)} questions...\n")

    for name, vectors_path, ids_path in EXPERIMENTS:

        print("\n" + "=" * 100)
        print(f"Experiment: {name}")
        print("=" * 100)

        retriever = Retriever.from_files(vectors_path, ids_path)

        for question in questions:

            print(f"\nQuestion: {question}")

            answer, chunks = answer_question(question, retriever)

            print("\nAnswer:")
            print(answer)

            print("\nRetrieved Chunks:")

            for chunk in chunks:

                print(
                    f"Rank: {chunk['rank']} | "
                    f"Hadith ID: {chunk['hadith_id']} | "
                    f"Score: {chunk['score']:.4f}"
                )

            print("-" * 80)


if __name__ == "__main__":
    main()
