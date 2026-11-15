from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import faiss
import numpy as np

from config import (
    API_TIMEOUT_MS,
    DOC_EXPANSIONS_G38_PATH,
    IDS_MATN,
    IDS_PATH,
    PROCESSED_CHUNKS_PATH,
    QUERIES_GEMINI001_CACHE_PATH,
    QUERIES_HYDE_G38_CACHE_PATH,
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


def _l2_normalize_vec(vec):
    arr = np.asarray(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    return arr / max(float(norm), 1e-12)


class UpgradedRetriever:
    """
    خط الاسترجاع النهائي المختار (E5 + قاعدة البساطة P4):
    - التضمين: gemini-embedding-001 (3072d) للمتن فقط (Dense_m)
    - الاستعلام الافتراضي (E4 HyDE): gemini-3.8-flash بمزج متجه الاستعلام
      (0.7 * q_vec + 0.3 * hyde_vec)
    - الافتراضي (1:0:0:0): بحث كثيف مباشر على المتن دون BM25 أو توسيع وثائق أو cross-encoder
      (مع دعم أوزان مخصّصة عند الحاجة في التجارب).
    """

    def __init__(
        self,
        matn_vectors,
        exp_vectors=None,
        bm25_matn=None,
        bm25_exp=None,
        chunk_ids=None,
        chunk_lookup=None,
        query_vec_cache=None,
        hyde_vec_cache=None,
        weights=(1.0, 0.0, 0.0, 0.0),
        hyde_alpha=0.7,
        candidates=50,
        rrf_k=60,
        api_timeout_ms=API_TIMEOUT_MS,
        fallback_retriever=None,
        fallback_factory=None,
        matn_vectors_path=None,
        exp_vectors_path=None,
        expansions_jsonl_path=None,
        ids_path=None,
    ):
        self.weights = [float(w) for w in weights]
        if len(self.weights) != 4 or not any(w > 0 for w in self.weights):
            raise ValueError(f"Expected 4 weights with at least one > 0, got {weights!r}")
        if self.weights[1] > 0 and exp_vectors is None:
            raise ValueError("exp_vectors is required when weight[1] > 0")
        if self.weights[2] > 0 and bm25_matn is None:
            raise ValueError("bm25_matn is required when weight[2] > 0")
        if self.weights[3] > 0 and bm25_exp is None:
            raise ValueError("bm25_exp is required when weight[3] > 0")

        self.matn_vectors = np.ascontiguousarray(matn_vectors, dtype=np.float32)
        self.exp_vectors = (
            np.ascontiguousarray(exp_vectors, dtype=np.float32)
            if exp_vectors is not None
            else None
        )
        self.bm25_matn = bm25_matn
        self.bm25_exp = bm25_exp
        self.chunk_ids = [str(cid) for cid in (chunk_ids or [])]
        self.chunk_lookup = chunk_lookup
        self.query_vec_cache = dict(query_vec_cache or {})
        self.hyde_vec_cache = dict(hyde_vec_cache or {})
        self.hyde_alpha = float(hyde_alpha)
        self.candidates = candidates
        self.rrf_k = rrf_k
        self.api_timeout_ms = int(api_timeout_ms) if api_timeout_ms else None
        self.fallback_retriever = fallback_retriever
        self.fallback_factory = fallback_factory
        self.matn_vectors_path = (
            Path(matn_vectors_path) if matn_vectors_path else None
        )
        self.exp_vectors_path = (
            Path(exp_vectors_path) if exp_vectors_path else None
        )
        self.expansions_jsonl_path = (
            Path(expansions_jsonl_path) if expansions_jsonl_path else None
        )
        self.ids_path = Path(ids_path) if ids_path else None
        self.mode = "upgraded"
        self.default_k = 5
        self.last_used_fallback = False
        self.hyde_text_cache = {}
        self.last_hyde_text = None
        self.last_call_stats = {"flash_calls": 0, "embed_calls": 0}
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
        weights=(1.0, 0.0, 0.0, 0.0),
        hyde_alpha=0.7,
        candidates=50,
        rrf_k=60,
        api_timeout_ms=API_TIMEOUT_MS,
        fallback_retriever=None,
        fallback_factory=None,
    ):
        w0, w1, w2, w3 = (float(w) for w in weights)
        if chunk_lookup is None:
            chunk_lookup = load_chunk_lookup(chunks_path)

        with open(ids_path, "r", encoding="utf-8") as f:
            chunk_ids = [str(cid) for cid in json.load(f)]

        matn_vectors = np.load(matn_vectors_path)
        exp_vectors = np.load(exp_vectors_path) if w1 > 0 else None

        bm25_matn = None
        if w2 > 0:
            matn_texts = [
                split_isnad_matn(chunk_lookup[cid]["text"]) for cid in chunk_ids
            ]
            bm25_matn = BM25Index(chunk_ids, matn_texts)

        bm25_exp = None
        if w3 > 0:
            exp_by_cid = {}
            with open(expansions_jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        row = json.loads(line)
                        exp_by_cid[str(row["chunk_id"])] = row["expansion_text"]
            exp_texts = [exp_by_cid.get(cid, "") for cid in chunk_ids]
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
            weights=(w0, w1, w2, w3),
            hyde_alpha=hyde_alpha,
            candidates=candidates,
            rrf_k=rrf_k,
            api_timeout_ms=api_timeout_ms,
            fallback_retriever=fallback_retriever,
            fallback_factory=fallback_factory,
            matn_vectors_path=matn_vectors_path,
            exp_vectors_path=exp_vectors_path if w1 > 0 else None,
            expansions_jsonl_path=expansions_jsonl_path if w3 > 0 else None,
            ids_path=ids_path,
        )

    @staticmethod
    def _embed_text(embed_client, text, types_mod):
        resp = embed_client.models.embed_content(
            model="gemini-embedding-001",
            contents=[text],
            config=types_mod.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY", output_dimensionality=3072
            ),
        )
        return _l2_normalize_vec(resp.embeddings[0].values)

    def _compute_raw_query_vector(self, question, *, http_opts=None, embed_client=None):
        """Compute L2-normalized gemini-embedding-001 vector for ``question``."""
        from dotenv import load_dotenv
        from google import genai
        from google.genai import types

        load_dotenv()
        if http_opts is None and self.api_timeout_ms:
            http_opts = types.HttpOptions(timeout=self.api_timeout_ms)
        if embed_client is None:
            embed_client = genai.Client(http_options=http_opts)
        return self._embed_text(embed_client, strip_diacritics(question), types)

    def _embed_raw_query_vector(self, question, http_opts=None, embed_client=None):
        """Return L2-normalized gemini-embedding-001 vector for ``question``, caching it."""
        if question in self.query_vec_cache:
            return self.query_vec_cache[question]
        vec = self._compute_raw_query_vector(
            question, http_opts=http_opts, embed_client=embed_client
        )
        self.query_vec_cache[question] = vec
        return vec

    def get_query_embedding(self, question):
        """Return cached or freshly embedded 3072d query vector, or None on API failure."""
        if question in self.query_vec_cache:
            return self.query_vec_cache[question]
        try:
            return self._embed_raw_query_vector(question)
        except Exception:
            return None

    def _generate_and_embed_hyde(
        self, question, *, http_opts=None, gen_client=None, embed_client=None
    ):
        """Generate a HyDE passage via gemini-3.8-flash and embed it with gemini-embedding-001."""
        from google import genai
        from google.genai import types

        active_gen = (
            gen_client
            if gen_client is not None
            else genai.Client(location="global", http_options=http_opts)
        )
        hyde_prompt = (
            "أنت عالم بالحديث النبوي الشريف وبألفاظ صحيح مسلم.\n"
            "اكتب متن حديث نبوي افتراضي موجز (سطرين إلى ثلاثة أسطر، بدون إسناد وبدون أرقام) "
            "يجيب عن السؤال التالي بأسلوب وألفاظ قريبة من متون صحيح مسلم.\n\n"
            f"السؤال: {question}"
        )
        resp_h = active_gen.models.generate_content(
            model="gemini-3.8-flash",
            contents=hyde_prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                thinking_config=types.ThinkingConfig(thinking_level="LOW"),
            ),
        )
        raw_hyde = (resp_h.text or "").strip()
        pseudo = strip_diacritics(raw_hyde) or strip_diacritics(question)
        active_embed = (
            embed_client
            if embed_client is not None
            else genai.Client(http_options=http_opts)
        )
        h_vec = self._embed_text(active_embed, pseudo, types)
        return raw_hyde, h_vec

    def _blended_query_vector(self, question):
        need_q = question not in self.query_vec_cache
        need_hyde = self.hyde_alpha < 1.0 and question not in self.hyde_vec_cache

        if need_q or need_hyde:
            from dotenv import load_dotenv
            from google import genai
            from google.genai import types

            load_dotenv()
            http_opts = (
                types.HttpOptions(timeout=self.api_timeout_ms)
                if self.api_timeout_ms
                else None
            )
            if need_q and need_hyde:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    q_fut = pool.submit(
                        self._compute_raw_query_vector,
                        question,
                        http_opts=http_opts,
                    )
                    h_fut = pool.submit(
                        self._generate_and_embed_hyde,
                        question,
                        http_opts=http_opts,
                    )
                    q_vec = q_fut.result()
                    raw_hyde, h_vec = h_fut.result()
                self.query_vec_cache[question] = q_vec
                self.hyde_text_cache[question] = raw_hyde
                self.hyde_vec_cache[question] = h_vec
            elif need_q:
                self.query_vec_cache[question] = self._compute_raw_query_vector(
                    question, http_opts=http_opts
                )
            else:
                raw_hyde, h_vec = self._generate_and_embed_hyde(
                    question, http_opts=http_opts
                )
                self.hyde_text_cache[question] = raw_hyde
                self.hyde_vec_cache[question] = h_vec

        q_vec = self.query_vec_cache[question]
        if self.hyde_alpha >= 1.0:
            return q_vec
        h_vec = self.hyde_vec_cache[question]
        return _l2_normalize_vec(
            self.hyde_alpha * q_vec + (1.0 - self.hyde_alpha) * h_vec
        )

    def _get_fallback_retriever(self):
        if self.fallback_retriever is None and self.fallback_factory is not None:
            self.fallback_retriever = self.fallback_factory()
        return self.fallback_retriever

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
        flash_calls = 0
        embed_calls = 0
        if cache_key not in self._dense_rank_cache:
            had_q = question in self.query_vec_cache
            had_h = question in self.hyde_vec_cache
            had_t = question in self.hyde_text_cache
            try:
                q_vec = self._blended_query_vector(question)
            except Exception as error:
                fallback = self._get_fallback_retriever()
                if fallback is None:
                    raise
                self.last_used_fallback = True
                self.last_hyde_text = None
                self.last_call_stats = {
                    "flash_calls": 1 if (not had_t and question in self.hyde_text_cache) else 0,
                    "embed_calls": (
                        (1 if (not had_q and question in self.query_vec_cache) else 0)
                        + (1 if (not had_h and question in self.hyde_vec_cache) else 0)
                    ),
                }
                print(
                    f"[warn] upgraded retrieval API failed ({type(error).__name__}: {error}); "
                    f"falling back to legacy local pipeline.",
                    file=sys.stderr,
                )
                return fallback.search(question, k=k)
            flash_calls = 1 if (self.hyde_alpha < 1.0 and not had_t and question in self.hyde_text_cache) else 0
            embed_calls = (
                (1 if (not had_q and question in self.query_vec_cache) else 0)
                + (1 if (self.hyde_alpha < 1.0 and not had_h and question in self.hyde_vec_cache) else 0)
            )
            w0, w1, w2, w3 = self.weights
            active_lists = []
            active_weights = []
            if w0 > 0:
                active_lists.append(self._top_dense_ids(self.matn_vectors, q_vec, cand_k))
                active_weights.append(w0)
            if w1 > 0:
                active_lists.append(self._top_dense_ids(self.exp_vectors, q_vec, cand_k))
                active_weights.append(w1)
            if w2 > 0:
                active_lists.append(self.bm25_matn.ranked_ids(question, k=cand_k))
                active_weights.append(w2)
            if w3 > 0:
                active_lists.append(self.bm25_exp.ranked_ids(question, k=cand_k))
                active_weights.append(w3)
            self._dense_rank_cache[cache_key] = (
                active_lists[0]
                if len(active_lists) == 1
                else reciprocal_rank_fusion(
                    active_lists,
                    k=self.rrf_k,
                    weights=active_weights,
                )
            )

        self.last_used_fallback = False
        self.last_hyde_text = (
            self.hyde_text_cache.get(question) if self.hyde_alpha < 1.0 else None
        )
        self.last_call_stats = {"flash_calls": flash_calls, "embed_calls": embed_calls}
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
    """يحوّل النداءات القديمة إلى `pipeline.build_pipeline` كمصدر وحيد للمسار."""
    from pipeline import build_pipeline

    return build_pipeline(mode=pipeline, chunk_lookup=chunk_lookup)
