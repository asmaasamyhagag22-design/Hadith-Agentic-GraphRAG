import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import faiss
import numpy as np

from config import (
    DOC_EXPANSIONS_G38_PATH,
    IDS_MATN,
    IDS_PATH,
    PROCESSED_CHUNKS_PATH,
    QUERIES_GEMINI001_CACHE_PATH,
    QUERIES_HYDE_G38_CACHE_PATH,
    RETRIEVAL_PIPELINE,
    VECTORS_EXPANSION_G38_GEMINI001,
    VECTORS_MATN,
    VECTORS_MATN_GEMINI001,
    VECTORS_PATH,
)
from utils import get_model, split_isnad_matn, strip_diacritics
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

    def __init__(self, index, chunk_ids, chunk_lookup):

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

        return cls(index, chunk_ids, chunk_lookup)

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


def _l2_normalize_vec(vec):
    arr = np.asarray(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    return arr / max(float(norm), 1e-12)


class UpgradedRetriever:
    """
    خط الاسترجاع النهائي المختار في التجربة E5:
    - التضمين: gemini-embedding-001 (3072d) للمتن (Dense_m) وتوسيع الوثائق (Dense_e)
    - التوسيع المعجمي والدلالي (E2): gemini-3.8-flash (Dense_e + BM25_e)
    - الاستعلام الافتراضي (E4 HyDE): gemini-3.8-flash بمزج متجه الاستعلام
      (0.7 * q_vec + 0.3 * hyde_vec)
    - الدمج: 4-way RRF بأوزان (8, 2, 1, 1) وعمق مرشحين 50 دون cross-encoder reranker (E3)
    """

    def __init__(
        self,
        matn_vectors,
        exp_vectors,
        bm25_matn,
        bm25_exp,
        chunk_ids,
        chunk_lookup,
        query_vec_cache=None,
        hyde_vec_cache=None,
        weights=(8.0, 2.0, 1.0, 1.0),
        hyde_alpha=0.7,
        candidates=50,
        rrf_k=60,
    ):
        self.matn_vectors = np.ascontiguousarray(matn_vectors, dtype=np.float32)
        self.exp_vectors = np.ascontiguousarray(exp_vectors, dtype=np.float32)
        self.bm25_matn = bm25_matn
        self.bm25_exp = bm25_exp
        self.chunk_ids = [str(cid) for cid in chunk_ids]
        self.chunk_lookup = chunk_lookup
        self.query_vec_cache = dict(query_vec_cache or {})
        self.hyde_vec_cache = dict(hyde_vec_cache or {})
        self.weights = list(weights)
        self.hyde_alpha = float(hyde_alpha)
        self.candidates = candidates
        self.rrf_k = rrf_k
        self._dense_rank_cache = {}

    @classmethod
    def from_files(
        cls,
        matn_vectors_path=VECTORS_MATN_GEMINI001,
        exp_vectors_path=VECTORS_EXPANSION_G38_GEMINI001,
        expansions_jsonl_path=DOC_EXPANSIONS_G38_PATH,
        ids_path=IDS_MATN,
        chunks_path=PROCESSED_CHUNKS_PATH,
        query_cache_path=QUERIES_GEMINI001_CACHE_PATH,
        hyde_cache_path=QUERIES_HYDE_G38_CACHE_PATH,
        chunk_lookup=None,
        weights=(8.0, 2.0, 1.0, 1.0),
        hyde_alpha=0.7,
        candidates=50,
        rrf_k=60,
    ):
        if chunk_lookup is None:
            chunk_lookup = load_chunk_lookup(chunks_path)

        with open(ids_path, "r", encoding="utf-8") as f:
            chunk_ids = [str(cid) for cid in json.load(f)]

        matn_vectors = np.load(matn_vectors_path)
        exp_vectors = np.load(exp_vectors_path)

        exp_by_cid = {}
        with open(expansions_jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    exp_by_cid[str(row["chunk_id"])] = row["expansion_text"]

        matn_texts = [
            split_isnad_matn(chunk_lookup[cid]["text"]) for cid in chunk_ids
        ]
        exp_texts = [exp_by_cid.get(cid, "") for cid in chunk_ids]

        bm25_matn = BM25Index(chunk_ids, matn_texts)
        bm25_exp = BM25Index(chunk_ids, exp_texts)

        query_vec_cache = {}
        if Path(query_cache_path).exists():
            q_data = np.load(query_cache_path, allow_pickle=True)
            for q, v in zip(q_data["questions"], q_data["vec3072"]):
                query_vec_cache[str(q)] = _l2_normalize_vec(v)

        hyde_vec_cache = {}
        if Path(hyde_cache_path).exists():
            h_data = np.load(hyde_cache_path, allow_pickle=True)
            for q, v in zip(h_data["questions"], h_data["vec_query_3072"]):
                hyde_vec_cache[str(q)] = _l2_normalize_vec(v)

        return cls(
            matn_vectors=matn_vectors,
            exp_vectors=exp_vectors,
            bm25_matn=bm25_matn,
            bm25_exp=bm25_exp,
            chunk_ids=chunk_ids,
            chunk_lookup=chunk_lookup,
            query_vec_cache=query_vec_cache,
            hyde_vec_cache=hyde_vec_cache,
            weights=weights,
            hyde_alpha=hyde_alpha,
            candidates=candidates,
            rrf_k=rrf_k,
        )

    def _blended_query_vector(self, question):
        if question not in self.query_vec_cache or (
            self.hyde_alpha < 1.0 and question not in self.hyde_vec_cache
        ):
            from dotenv import load_dotenv
            from google import genai
            from google.genai import types

            load_dotenv()
            embed_client = genai.Client()
            if question not in self.query_vec_cache:
                resp_q = embed_client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=[strip_diacritics(question)],
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_QUERY", output_dimensionality=3072
                    ),
                )
                self.query_vec_cache[question] = _l2_normalize_vec(
                    resp_q.embeddings[0].values
                )

            if self.hyde_alpha < 1.0 and question not in self.hyde_vec_cache:
                gen_client = genai.Client(location="global")
                hyde_prompt = (
                    "أنت عالم بالحديث النبوي الشريف وبألفاظ صحيح مسلم.\n"
                    "اكتب متن حديث نبوي افتراضي موجز (سطرين إلى ثلاثة أسطر، بدون إسناد وبدون أرقام) "
                    "يجيب عن السؤال التالي بأسلوب وألفاظ قريبة من متون صحيح مسلم.\n\n"
                    f"السؤال: {question}"
                )
                resp_h = gen_client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=hyde_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        thinking_config=types.ThinkingConfig(
                            thinking_level="LOW"
                        ),
                    ),
                )
                pseudo = strip_diacritics((resp_h.text or "").strip()) or strip_diacritics(question)
                resp_he = embed_client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=[pseudo],
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_QUERY", output_dimensionality=3072
                    ),
                )
                self.hyde_vec_cache[question] = _l2_normalize_vec(
                    resp_he.embeddings[0].values
                )

        q_vec = self.query_vec_cache[question]
        if self.hyde_alpha >= 1.0:
            return q_vec
        h_vec = self.hyde_vec_cache[question]
        return _l2_normalize_vec(
            self.hyde_alpha * q_vec + (1.0 - self.hyde_alpha) * h_vec
        )

    def _top_dense_ids(self, matrix, q_vec, top_k):
        scores = matrix @ q_vec
        if top_k < len(scores):
            part = np.argpartition(-scores, top_k)[:top_k]
            top_idx = part[np.argsort(-scores[part])]
        else:
            top_idx = np.argsort(-scores)
        return [self.chunk_ids[int(i)] for i in top_idx]

    def search(self, question, k=5):
        cand_k = max(self.candidates, k)
        cache_key = (question, cand_k)
        if cache_key not in self._dense_rank_cache:
            q_vec = self._blended_query_vector(question)
            dm_ids = self._top_dense_ids(self.matn_vectors, q_vec, cand_k)
            de_ids = self._top_dense_ids(self.exp_vectors, q_vec, cand_k)
            bm_ids = self.bm25_matn.ranked_ids(question, k=cand_k)
            be_ids = self.bm25_exp.ranked_ids(question, k=cand_k)
            self._dense_rank_cache[cache_key] = reciprocal_rank_fusion(
                [dm_ids, de_ids, bm_ids, be_ids],
                k=self.rrf_k,
                weights=self.weights,
            )

        fused = self._dense_rank_cache[cache_key]
        results = []
        for rank, chunk_id in enumerate(fused[:k], start=1):
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


def build_default_retriever(pipeline=None, chunk_lookup=None):
    """
    يبني باحث الاسترجاع الافتراضي بناءً على علم الإعداد `RETRIEVAL_PIPELINE`
    ("upgraded" للمسار الجديد E5، أو "legacy" للمسار القديم).
    """
    mode = pipeline or RETRIEVAL_PIPELINE
    if chunk_lookup is None:
        chunk_lookup = load_chunk_lookup()

    if mode == "upgraded" and VECTORS_MATN_GEMINI001.exists():
        return UpgradedRetriever.from_files(chunk_lookup=chunk_lookup)

    matn_dense = Retriever.from_files(
        VECTORS_MATN, IDS_MATN, chunk_lookup=chunk_lookup
    )
    bm25 = BM25Index(
        matn_dense.chunk_ids,
        [
            split_isnad_matn(chunk_lookup[cid]["text"])
            for cid in matn_dense.chunk_ids
        ],
    )
    hybrid = HybridRetriever(matn_dense, bm25)
    from rerank import RerankingRetriever

    return RerankingRetriever(hybrid)
