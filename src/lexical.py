"""
البحث اللفظي (BM25) — الطرف التاني من الاسترجاع الهجين.

البحث الدلالي بيلاقي المعنى القريب، وبيضيع لما السؤال
يعتمد على لفظ محدد («يوم الشك»، «كافل اليتيم»). BM25
بيمسك بالظبط الحالة دي.
"""

import re

from rank_bm25 import BM25Okapi

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


def reciprocal_rank_fusion(rank_lists, k=60):
    """
    بتدمج قوايم مرتبة من بواحث مختلفة من غير ما تحتاج
    تعاير درجاتهم — كل قايمة بتساهم بـ 1/(k + rank).

    الثابت k=60 بيقلل تأثير المراكز الأولى الشاذة، وهو
    الرقم المستخدم في الورقة الأصلية.
    """

    scores = {}

    for ranks in rank_lists:

        for rank, doc_id in enumerate(ranks):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)

    return sorted(scores, key=scores.get, reverse=True)
