import sys
import json
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    PROCESSED_CHUNKS_PATH,
    VECTORS_PATH,
    IDS_PATH,
)
from utils import get_model, strip_diacritics


def load_chunks(path=PROCESSED_CHUNKS_PATH):

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def indexable_chunks(chunks):
    """
    بتشيل المتابعات اللي مالهاش متن مستقل من الفهرس.
    بتفضل موجودة في muslim_chunks.json للعرض والرجوع ليها،
    بس مش بتتنافس على مراكز البحث.
    """

    return [
        chunk
        for chunk in chunks
        if not chunk["metadata"].get("reference_only", False)
    ]


def embed_texts(texts, batch_size=64):

    return get_model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )


def save_ids(chunk_ids, path):
    """
    قايمة الـ IDs دايمًا بتتحفظ جنب المصفوفة بتاعتها
    وبنفس الترتيب — ده اللي بيمنع عدم التطابق.
    """

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(chunk_ids, f, ensure_ascii=False, indent=4)


def main():

    all_chunks = load_chunks()
    processed_chunks = indexable_chunks(all_chunks)

    print(
        f"Chunks: {len(all_chunks)} "
        f"({len(all_chunks) - len(processed_chunks)} reference-only, excluded)"
    )

    texts = [
        "passage: " + strip_diacritics(chunk["text"])
        for chunk in processed_chunks
    ]

    chunk_ids = [
        str(chunk["id"])
        for chunk in processed_chunks
    ]

    print(f"Documents : {len(texts)}")

    embeddings = embed_texts(texts)

    print(f"Embedding shape: {embeddings.shape}")

    VECTORS_PATH.parent.mkdir(parents=True, exist_ok=True)

    np.save(VECTORS_PATH, embeddings)
    save_ids(chunk_ids, IDS_PATH)

    print(f"Saved vectors -> {VECTORS_PATH}")
    print(f"Saved ids     -> {IDS_PATH}")


if __name__ == "__main__":
    main()
