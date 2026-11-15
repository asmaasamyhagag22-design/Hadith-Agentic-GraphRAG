"""
البحث اللفظي (BM25) — الطرف التاني من الاسترجاع الهجين.

البحث الدلالي بيلاقي المعنى القريب، وبيضيع لما السؤال
يعتمد على لفظ محدد («يوم الشك»، «كافل اليتيم»). BM25
بيمسك بالظبط الحالة دي.
"""

import re

from utils import strip_diacritics

# أي حاجة مش حرف عربي أو رقم بتبقى فاصل: علامات الترقيم،
# ورموز التنسيق اللي جوة النص زي ‏ و ‎.
_TOKEN_SPLIT = re.compile(r"[^ء-ي0-9]+")

_ALEF_FORMS = str.maketrans({
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ٱ": "ا",
    "ى": "ي",
    "ة": "ه",
})

# «ال» التعريف بتخلي نفس الكلمة توكنين مختلفين («الصوم» و«صوم»)
# فبتقسم إحصائيات BM25 على الاتنين. شيلها بتوحّدهم.
_MIN_STEM_LENGTH = 4


def tokenize(text):

    text = strip_diacritics(text).translate(_ALEF_FORMS)

    tokens = []

    for token in _TOKEN_SPLIT.split(text):

        if not token:
            continue

        if token.startswith("ال") and len(token) > _MIN_STEM_LENGTH:
            token = token[2:]

        tokens.append(token)

    return tokens


class BM25Index:

    def __init__(self, chunk_ids, texts):

        if len(chunk_ids) != len(texts):
            raise ValueError(
                f"IDs/texts mismatch: {len(chunk_ids)} ids "
                f"vs {len(texts)} texts."
            )

        from rank_bm25 import BM25Okapi

        self.chunk_ids = list(chunk_ids)
        self.bm25 = BM25Okapi([tokenize(text) for text in texts])

    def ranked_ids(self, question, k):
        """
        بترجع الـ IDs مرتبة تنازليًا حسب درجة BM25.
        الترتيب هو المطلوب هنا مش الدرجات، لأن الدمج
        بالـ RRF بيشتغل على المراتب.
        """

        scores = self.bm25.get_scores(tokenize(question))

        order = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:k]

        return [self.chunk_ids[i] for i in order]


def reciprocal_rank_fusion(rank_lists, k=60, weights=None):
    """
    بتدمج قوايم مرتبة من بواحث مختلفة من غير ما تحتاج
    تعاير درجاتهم — كل قايمة بتساهم بـ weight/(k + rank).

    الثابت k=60 بيقلل تأثير المراكز الأولى الشاذة، وهو
    الرقم المستخدم في الورقة الأصلية.

    weights: وزن لكل قايمة بنفس الترتيب. الافتراضي متساوي.
    بيسمح نرجّح BM25 على الدلالي أو العكس — الاتنين
    بيكسبوا في أنواع أسئلة مختلفة.
    """

    if weights is None:
        weights = [1.0] * len(rank_lists)

    if len(weights) != len(rank_lists):
        raise ValueError(
            f"Got {len(weights)} weights for {len(rank_lists)} rank lists."
        )

    scores = {}

    for ranks, weight in zip(rank_lists, weights):

        for rank, doc_id in enumerate(ranks):
            scores[doc_id] = scores.get(doc_id, 0) + weight / (k + rank + 1)

    return sorted(scores, key=scores.get, reverse=True)
