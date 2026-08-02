import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import MUSLIM_JSON_PATH, PROCESSED_CHUNKS_PATH

with open(MUSLIM_JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

chapter_map = {}
for chapter in data.get("chapters", []):
    chapter_map[chapter["id"]] = {
        "arabic_name": chapter["arabic"],
        "english_name": chapter["english"],   
    }

processed_chunks = []
for hadith in data.get("hadiths", []):
    hadith_id = hadith["id"]
    chapter_id = hadith["chapterId"]
    
    id_in_book = hadith.get("idInBook", "Unknown")
    
    chapter_info = chapter_map.get(chapter_id, {"arabic_name": "Unknown", "english_name": "Unknown"})

    hadith_arabic = hadith.get("arabic", "")
    chunk_data = {
        "id": hadith_id,
        "text": hadith_arabic,
        "metadata": {
            "hadith_number": hadith_id,
            "id_in_book": id_in_book, # تمت الإضافة هنا
            "chapter_id": chapter_id,
            "chapter_arabic": chapter_info.get("arabic_name", "Unknown"),
            "source": "صحيح مسلم",
            "author": "الإمام مسلم بن الحجاج القشيري النيسابوري",
        }
    }
    processed_chunks.append(chunk_data)

print(f"Processed {len(processed_chunks)} chunks from the data.")

PROCESSED_CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)

with open(PROCESSED_CHUNKS_PATH, "w", encoding="utf-8") as f:
    json.dump(processed_chunks, f, ensure_ascii=False, indent=4)

print(f"Processed chunks saved to: {PROCESSED_CHUNKS_PATH}")