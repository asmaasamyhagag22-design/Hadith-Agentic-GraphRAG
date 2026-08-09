import sys
import json
from pathlib import Path

import numpy as np
import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    DATA_BASE_PATH,
    DOCUMENT_REPRESENTATION,
    VECTORS_PATH,
    IDS_PATH,
    VECTORS_MATN,
    IDS_MATN,
    VECTORS_MATN_WITH_TITLE,
    IDS_MATN_WITH_TITLE,
)
from retrieve import load_chunk_lookup
from utils import split_isnad_matn

BATCH_SIZE = 1000

# كل صيغة مربوطة بملفات الـ vectors بتاعتها. من غير الربط ده ممكن
# نخزّن نص المتن ومعاه vectors اتعملت على النص الكامل.
REPRESENTATIONS = {
    "full": (VECTORS_PATH, IDS_PATH),
    "matn": (VECTORS_MATN, IDS_MATN),
    "chapter_matn": (VECTORS_MATN_WITH_TITLE, IDS_MATN_WITH_TITLE),
}


def build_document(chunk, representation):

    text = chunk["text"]

    if representation == "full":
        return text

    if representation == "matn":
        return split_isnad_matn(text)

    if representation == "chapter_matn":
        chapter = chunk["metadata"]["chapter_arabic"]
        return f"{chapter}\n\n{split_isnad_matn(text)}"

    raise ValueError(f"Unknown representation: {representation}")


def main(representation=DOCUMENT_REPRESENTATION):

    if representation not in REPRESENTATIONS:
        raise ValueError(
            f"Unknown representation: {representation}. "
            f"Expected one of {sorted(REPRESENTATIONS)}."
        )

    vectors_path, ids_path = REPRESENTATIONS[representation]

    embeddings = np.load(vectors_path)

    with open(ids_path, "r", encoding="utf-8") as f:
        chunk_ids = [str(cid) for cid in json.load(f)]

    if len(embeddings) != len(chunk_ids):
        raise ValueError(
            f"Vectors/IDs mismatch: {len(embeddings)} vectors "
            f"vs {len(chunk_ids)} ids in {ids_path.name}."
        )

    chunk_lookup = load_chunk_lookup()

    documents = []
    metadatas = []

    for chunk_id in chunk_ids:

        chunk = chunk_lookup[chunk_id]

        documents.append(build_document(chunk, representation))
        metadatas.append(chunk["metadata"])

    client = chromadb.PersistentClient(path=str(DATA_BASE_PATH))

    collection = client.get_or_create_collection(
        name="muslim_collection",
        metadata={"hnsw:space": "cosine"},
    )

    print(f"Representation: {representation}")
    print(f"Adding {len(chunk_ids)} documents...")

    for i in range(0, len(chunk_ids), BATCH_SIZE):

        collection.add(
            ids=chunk_ids[i:i + BATCH_SIZE],
            documents=documents[i:i + BATCH_SIZE],
            embeddings=embeddings[i:i + BATCH_SIZE].tolist(),
            metadatas=metadatas[i:i + BATCH_SIZE],
        )

        print(f"  {min(i + BATCH_SIZE, len(chunk_ids))}/{len(chunk_ids)}")

    print("Collection count:", collection.count())


if __name__ == "__main__":
    main()
