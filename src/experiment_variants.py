"""
بيبني الصيغ التلاتة اللي بنقارنها في التجربة.

كل صيغة بتطلّع وثيقة واحدة لكل chunk موجود في
muslim_chunks.json وبنفس الترتيب — فقايمة الـ IDs
واحدة ومتطابقة مع الفهارس التلاتة.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    VECTORS_PATH,
    IDS_PATH,
    VECTORS_MATN,
    IDS_MATN,
    VECTORS_MATN_WITH_TITLE,
    IDS_MATN_WITH_TITLE,
)
from embed import load_chunks, indexable_chunks, embed_texts, save_ids
from utils import split_isnad_matn, strip_diacritics


def variant_text(chunk, variant):
    """
    نص الوثيقة حسب صيغة التمثيل — من غير بادئة e5 ومن غير
    تطبيع، عشان الـ BM25 يقدر يستخدم نفس النص.

    فصل السند بيحصل على النص الأصلي (الأنماط بتتطابق على
    نسخة مطبَّعة جوه الدالة).
    """

    text = chunk["text"]

    if variant == "full":
        return text

    matn = split_isnad_matn(text)

    if variant == "matn":
        return matn

    if variant == "chapter_matn":
        return f"{chunk['metadata']['chapter_arabic']}\n\n{matn}"

    raise ValueError(f"Unknown variant: {variant}")


def build_variants(processed_chunks):

    chunk_ids = []
    full_texts = []
    matn_texts = []
    title_texts = []

    for chunk in processed_chunks:

        chunk_ids.append(str(chunk["id"]))

        # التشكيل بيتشال هنا لأن ده اللي بيتعمله embedding
        for variant, bucket in (
            ("full", full_texts),
            ("matn", matn_texts),
            ("chapter_matn", title_texts),
        ):
            bucket.append(
                "passage: " + strip_diacritics(variant_text(chunk, variant))
            )

    return chunk_ids, full_texts, matn_texts, title_texts


def count_stripped(processed_chunks):
    """
    كام chunk اتشال منه السند فعلاً. الرقم ده لازم يتكتب
    في EXPERIMENTS.md — من غيره مش واضح صيغة الـ matn
    مختلفة عن الـ full قد إيه أصلاً.
    """

    return sum(
        1
        for chunk in processed_chunks
        if split_isnad_matn(chunk["text"]) != chunk["text"]
    )


def main():

    all_chunks = load_chunks()
    processed_chunks = indexable_chunks(all_chunks)

    chunk_ids, full_texts, matn_texts, title_texts = build_variants(
        processed_chunks
    )

    total = len(chunk_ids)
    stripped = count_stripped(processed_chunks)

    print(
        f"Chunks: {len(all_chunks)} "
        f"({len(all_chunks) - total} reference-only, excluded)"
    )
    print(f"Indexed: {total}")
    print(
        f"Isnad actually stripped: {stripped}/{total} "
        f"({stripped / total:.1%})"
    )

    variants = [
        ("Full (sanad + matn)", full_texts, VECTORS_PATH, IDS_PATH),
        ("Matn only", matn_texts, VECTORS_MATN, IDS_MATN),
        (
            "Chapter + matn",
            title_texts,
            VECTORS_MATN_WITH_TITLE,
            IDS_MATN_WITH_TITLE,
        ),
    ]

    for name, texts, vectors_path, ids_path in variants:

        print(f"\nEncoding: {name}")

        embeddings = embed_texts(texts)

        vectors_path.parent.mkdir(parents=True, exist_ok=True)

        np.save(vectors_path, embeddings)
        save_ids(chunk_ids, ids_path)

        print(f"  {embeddings.shape} -> {vectors_path.name}")


if __name__ == "__main__":
    main()
