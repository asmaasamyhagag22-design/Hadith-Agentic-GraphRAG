"""
إعادة ترتيب النتايج بـ cross-encoder.

البحث الهجين بيوصّل الحديث الصح لأول 10 في 89% من الحالات
لكن للمركز الأول في 41% بس. الفرق ده مشكلة ترتيب: الـ
bi-encoder بيقارن متجهين اتحسبوا كل واحد لوحده، والـ
cross-encoder بيقرا السؤال والحديث مع بعض فبيشوف علاقات
مش ظاهرة في المتجهات.

مهم: بندخّل أول 10 مش 20 — القياس بيقول hit@10 = hit@20 =
hit@50 = 89%، يعني نفس السقف بنص التكلفة الحسابية.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sentence_transformers import CrossEncoder

from experiment_variants import variant_text
from utils import strip_diacritics

BGE = "BAAI/bge-reranker-v2-m3"
MMARCO = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# دول اتجربوا وفشلوا: كودهم المخصص مش متوافق مع نسخة
# transformers المثبتة (تفاصيل في EXPERIMENTS.md).
JINA = "jinaai/jina-reranker-v2-base-multilingual"
GTE = "Alibaba-NLP/gte-multilingual-reranker-base"

# اختبار McNemar المزدوج ما لقاش فرق معنوي بين MMARCO
# وBGE على أي مقياس (hit@1 على 224 سؤال: 11 مقابل 11،
# p=1.00). وMMARCO أصغر 17 مرة وأسرع ~6 مرات — 0.5 ثانية
# مقابل 3 ثواني لكل سؤال على CPU، وده الفرق بين واجهة
# تفاعلية وواجهة بطيئة.
DEFAULT_MODEL = MMARCO

DEFAULT_TOP_K_IN = 10

# حد الـ cross-encoders المعتاد. المتون الأطول بتتقطع،
# وبنعدّها عشان الرقم يتكتب مع النتايج مش يتخبّى.
MAX_LENGTH = 512

_models = {}


def get_reranker(model_name=DEFAULT_MODEL):
    """تحميل كسول، ونسخة واحدة لكل موديل زي utils.get_model."""

    if model_name not in _models:

        kwargs = {"max_length": MAX_LENGTH}

        # موديلات Jina وGTE معماريتها متعرّفة في الريبو بتاعها
        if model_name in (JINA, GTE):
            kwargs["trust_remote_code"] = True

        _models[model_name] = CrossEncoder(model_name, **kwargs)

    return _models[model_name]


def document_for_reranking(chunk):
    """
    نفس المعالجة اللي الفهرس اتبنى بيها بالظبط: المتن،
    من غير تشكيل. لو دخّلنا chunk['text'] الخام هيشوف
    السند كمان وهو ضوضاء بالنسبة للسؤال.
    """

    return strip_diacritics(variant_text(chunk, "matn"))


class RerankingRetriever:
    """
    بيغلّف أي retriever بنفس واجهة .search(question, k)
    وبنفس شكل الـ dict، فـ evaluate.evaluate() بيشتغل عليه
    من غير أي تعديل.
    """

    def __init__(
        self,
        base,
        model_name=DEFAULT_MODEL,
        top_k_in=DEFAULT_TOP_K_IN,
        chunk_lookup=None,
    ):
        self.base = base
        self.model_name = model_name
        self.top_k_in = top_k_in
        self.chunk_lookup = chunk_lookup or base.chunk_lookup

        self.query_seconds = []
        self.truncated = 0
        self.scored = 0

    def search(self, question, k=5):

        candidates = self.base.search(question, k=self.top_k_in)

        if not candidates:
            return []

        documents = [
            document_for_reranking(self.chunk_lookup[str(c["chunk_id"])])
            for c in candidates
        ]

        model = get_reranker(self.model_name)

        self._count_truncation(model, documents)

        started = time.perf_counter()

        scores = model.predict(
            [(question, document) for document in documents]
        )

        self.query_seconds.append(time.perf_counter() - started)

        order = sorted(
            range(len(candidates)),
            key=lambda i: float(scores[i]),
            reverse=True,
        )

        results = []

        for rank, index in enumerate(order[:k], start=1):

            result = dict(candidates[index])
            result["rank"] = rank
            result["score"] = float(scores[index])

            results.append(result)

        return results

    def _count_truncation(self, model, documents):

        tokenizer = model.tokenizer

        for document in documents:

            self.scored += 1

            length = len(
                tokenizer(document, truncation=False)["input_ids"]
            )

            if length > MAX_LENGTH:
                self.truncated += 1

    @property
    def seconds_per_query(self):

        if not self.query_seconds:
            return 0.0

        return sum(self.query_seconds) / len(self.query_seconds)
