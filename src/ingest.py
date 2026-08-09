import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import MUSLIM_JSON_PATH, PROCESSED_CHUNKS_PATH
from utils import chunk_text, is_reference_only


def build_chapter_map(data):

    chapter_map = {}

    for chapter in data.get("chapters", []):

        chapter_map[chapter["id"]] = {
            "arabic_name": chapter["arabic"],
            "english_name": chapter["english"],
        }

    return chapter_map


def build_chunks(data):
    """
    بيرجع chunk لكل حديث بنصه الكامل (سند + متن).
    الأحاديث الطويلة بس هي اللي بتتقسم، وبالطول لا غير.
    """

    chapter_map = build_chapter_map(data)

    processed_chunks = []

    for hadith in data.get("hadiths", []):

        hadith_id = hadith["id"]
        chapter_id = hadith["chapterId"]

        id_in_book = hadith.get("idInBook", "Unknown")

        chapter_info = chapter_map.get(
            chapter_id,
            {
                "arabic_name": "Unknown",
                "english_name": "Unknown",
            },
        )

        hadith_text = hadith.get("arabic", "")

        parts = chunk_text(hadith_text)

        for part_index, part in enumerate(parts):

            processed_chunks.append({
                "id": f"{hadith_id}_{part_index}",
                "text": part,
                "metadata": {
                    "parent_id": hadith_id,
                    "hadith_number": hadith_id,
                    "id_in_book": id_in_book,
                    "chapter_id": chapter_id,
                    "chapter_arabic": chapter_info["arabic_name"],
                    "source": "صحيح مسلم",
                    "author": "الإمام مسلم بن الحجاج القشيري النيسابوري",
                    # بيتخزّن ومتشالش: الحديث موجود في المصدر
                    # وليه رقم، بس مش هيدخل فهرس البحث.
                    "reference_only": is_reference_only(part),
                },
            })

    return processed_chunks


def main():

    with open(MUSLIM_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    processed_chunks = build_chunks(data)

    hadith_count = len(data.get("hadiths", []))

    print(f"Hadiths: {hadith_count}")
    print(f"Chunks:  {len(processed_chunks)}")

    PROCESSED_CHUNKS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        PROCESSED_CHUNKS_PATH,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            processed_chunks,
            f,
            ensure_ascii=False,
            indent=4,
        )

    print(f"Saved to {PROCESSED_CHUNKS_PATH}")


if __name__ == "__main__":
    main()
