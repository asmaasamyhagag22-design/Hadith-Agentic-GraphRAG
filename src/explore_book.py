import json
from config import MUSLIM_JSON_PATH

with open(MUSLIM_JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

chapters = data.get("chapters", [])
book_ids = [chapter.get("bookId") for chapter in chapters]
print(f"Unique books: {len(set(book_ids))}")

chapters_of_book_2 = [c for c in chapters if c.get("bookId") == 2]
print(f"Chapters with bookId==2: {len(chapters_of_book_2)}")

hadiths = data.get("hadiths", [])
hadiths_of_book_2 = [h for h in hadiths if h.get("bookId") == 2]
print(f"Hadiths with bookId==2: {len(hadiths_of_book_2)}")

print("First chapter:", chapters_of_book_2[0]["arabic"])
print("Last chapter:", chapters_of_book_2[-1]["arabic"])