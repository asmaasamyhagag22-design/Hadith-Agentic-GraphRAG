with open(PROCESSED_CHUNKS_PATH, "r", encoding="utf-8") as f:
    processed_chunks = json.load(f)

count = 0
for chunk in processed_chunks:
    if str(chunk["id"]).startswith("7278"):
        print(chunk["id"])
        print(chunk["text"][:300])
        print("=" * 80)
        count += 1

print("Number of chunks:", count)