import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import faiss
import numpy as np

from config import (
    PROCESSED_CHUNKS_PATH,
    VECTORS_PATH,
    IDS_PATH,
)
from utils import get_model, strip_diacritics
from lexical import BM25Index, reciprocal_rank_fusion


def load_chunk_lookup(path=PROCESSED_CHUNKS_PATH):

    with open(path, "r", encoding="utf-8") as f:
        processed_chunks = json.load(f)

    return {
        str(chunk["id"]): chunk
        for chunk in processed_chunks
    }


class Retriever:
    """
    بيربط الفهرس بقايمة الـ IDs بتاعته في حتة واحدة.

    الفهرس لوحده بيرجع أرقام صفوف بس؛ ترجمتها لأحاديث
    محتاجة القايمة اللي اتبنى منها بالظبط. لما الاتنين
    يبقوا في نفس الكائن، مستحيل تستخدمي فهرس مع قايمة غيره.
    """

    def __init__(
        self,
        index,
        chunk_ids,
        chunk_lookup,
        vectors_path=None,
        ids_path=None,
    ):

        if index.ntotal != len(chunk_ids):
            raise ValueError(
                f"Index/IDs mismatch: index has {index.ntotal} vectors "
                f"but {len(chunk_ids)} ids were given. "
                "Each vectors file must be loaded with the ids file "
                "that was saved alongside it."
            )

        self.index = index
        self.chunk_ids = chunk_ids
        self.chunk_lookup = chunk_lookup
        self.vectors_path = Path(vectors_path) if vectors_path else None
        self.ids_path = Path(ids_path) if ids_path else None

    @classmethod
    def from_files(
        cls,
        vectors_path=VECTORS_PATH,
        ids_path=IDS_PATH,
        chunks_path=PROCESSED_CHUNKS_PATH,
        chunk_lookup=None,
    ):
        """
        chunk_lookup اختياري عشان لما نبني كذا فهرس مع بعض
        منحمّلش نفس ملف الـ chunks كذا مرة.
        """

        embeddings = np.load(vectors_path)

        with open(ids_path, "r", encoding="utf-8") as f:
            chunk_ids = [str(cid) for cid in json.load(f)]

        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)

        if chunk_lookup is None:
            chunk_lookup = load_chunk_lookup(chunks_path)

        return cls(
            index,
            chunk_ids,
            chunk_lookup,
            vectors_path=vectors_path,
            ids_path=ids_path,
        )

    def search(self, question, k=5):

        # نفس المعالجة اللي اتعملت للوثائق، وإلا السؤال والوثيقة
        # هيتقارنوا وهما متمثّلين بطريقتين مختلفتين.
        query_embedding = get_model().encode(
            ["query: " + strip_diacritics(question)],
            normalize_embeddings=True,
        )

        scores, indices = self.index.search(
            np.asarray(query_embedding).reshape(1, -1),
            k,
        )

        results = []

        for rank, idx in enumerate(indices[0]):

            if idx < 0:
                continue

            chunk_id = self.chunk_ids[idx]

            chunk = self.chunk_lookup.get(chunk_id)

            if chunk is None:
                continue

            results.append({
                "rank": rank + 1,
                "score": float(scores[0][rank]),
                "chunk_id": chunk["id"],
                "hadith_id": chunk["metadata"]["hadith_number"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
            })

        return results


class LexicalRetriever:
    """BM25 لوحده — موجود عشان يبقى في عمود مستقل في التقييم."""

    def __init__(self, bm25, chunk_lookup):
        self.bm25 = bm25
        self.chunk_lookup = chunk_lookup

    def search(self, question, k=5):

        results = []

        for rank, chunk_id in enumerate(
            self.bm25.ranked_ids(question, k=k), start=1
        ):

            chunk = self.chunk_lookup.get(chunk_id)

            if chunk is None:
                continue

            results.append({
                "rank": rank,
                "score": None,
                "chunk_id": chunk["id"],
                "hadith_id": chunk["metadata"]["hadith_number"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
            })

        return results


class HybridRetriever:
    """
    بحث دلالي + BM25، مدموجين بالـ RRF.

    كل باحث بيرشّح `candidates` وثيقة، وبيتدمجوا بالمراتب
    مش بالدرجات — الدرجتين مقياسهم مختلف تمامًا فجمعهم
    مباشرة بيبقى بلا معنى.
    """

    def __init__(
        self,
        dense,
        bm25,
        candidates=50,
        rrf_k=60,
        dense_weight=1.0,
        bm25_weight=1.0,
    ):

        if list(dense.chunk_ids) != list(bm25.chunk_ids):
            raise ValueError(
                "Dense and BM25 indexes were built over different id lists."
            )

        self.dense = dense
        self.bm25 = bm25
        self.candidates = candidates
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight

    @property
    def chunk_lookup(self):
        return self.dense.chunk_lookup

    def search(self, question, k=5):

        dense_ids = [
            str(r["chunk_id"])
            for r in self.dense.search(question, k=self.candidates)
        ]

        lexical_ids = self.bm25.ranked_ids(question, k=self.candidates)

        fused = reciprocal_rank_fusion(
            [dense_ids, lexical_ids],
            k=self.rrf_k,
            weights=[self.dense_weight, self.bm25_weight],
        )

        results = []

        for rank, chunk_id in enumerate(fused[:k], start=1):

            chunk = self.dense.chunk_lookup.get(chunk_id)

            if chunk is None:
                continue

            results.append({
                "rank": rank,
                "score": None,  # الـ RRF بيرتّب، مش بيدّي درجة تشابه
                "chunk_id": chunk["id"],
                "hadith_id": chunk["metadata"]["hadith_number"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
            })

        return results


def retrieve_relevant_chunks(question, retriever, k=5):

    return retriever.search(question, k=k)
