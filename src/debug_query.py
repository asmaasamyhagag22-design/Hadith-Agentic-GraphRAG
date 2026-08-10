"""فحص يدوي: يعرض أجزاء حديث معيّن بعد الـ ingest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from embed import load_chunks
from utils import split_isnad_matn


def main(hadith_id):

    count = 0

    for chunk in load_chunks():

        if chunk["metadata"]["hadith_number"] != hadith_id:
            continue

        count += 1

        print(f"--- {chunk['id']} "
              f"(reference_only={chunk['metadata']['reference_only']}) ---")
        print("full:", chunk["text"][:200])
        print("matn:", split_isnad_matn(chunk["text"])[:200])
        print()

    print(f"chunks for hadith {hadith_id}: {count}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 7278)
