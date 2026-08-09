import re

from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-base"
MAX_TOKENS = 450

_model = None


def get_model():
    """
    يحمّل الموديل مرة واحدة بس، وأول ما يتطلب فعلاً.
    كده استيراد الملف ده مش بيحمّل موديل من غير داعي.
    """

    global _model

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)

    return _model


# ----------------------------------------------------------
# فصل السند عن المتن
# ----------------------------------------------------------
#
# المطابقة بتحصل على نسخة مطبَّعة من النص (من غير تشكيل،
# وبألف موحّدة) بس القطع بيحصل في النص الأصلي بتشكيله.
# عشان كده بنبني خريطة من مواضع النسخة المطبَّعة لمواضع الأصل.

_ARABIC_LETTER = "ء-ي"

_DIACRITICS = re.compile("[ً-ْٰـ]")

_ALEF_FORMS = {
    "أ": "ا",  # أ
    "إ": "ا",  # إ
    "آ": "ا",  # آ
    "ٱ": "ا",  # ٱ
    "ى": "ي",  # ى
}

# الإشارة الأوضح لبداية المتن: فعل رواية + المُسنَد إليه.
_NARRATION_VERBS = [
    "قال", "عن", "ان", "سمعت", "كان",
    "رايت", "اتي", "سالت", "خطبنا",
    "نهي", "امر", "بعث",
]

_SUBJECTS = "(?:رسول الله|النبي)"

_MARKER_RE = re.compile(
    f"(?<![{_ARABIC_LETTER}])"
    f"(?:{'|'.join(_NARRATION_VERBS)}) {_SUBJECTS}"
)

# للأحاديث الموقوفة اللي مفيهاش ذكر صريح للنبي: آخر حلقة
# في السند، وبعدها أول فعل قول — المتن بيبدأ بعده.
_CHAIN_RE = re.compile(
    f"(?<![{_ARABIC_LETTER}])"
    f"(?:حدثنا|حدثني|اخبرنا|اخبرني|انبانا|عن)"
    f"(?![{_ARABIC_LETTER}])"
)

_SAID_RE = re.compile(
    f"(?<![{_ARABIC_LETTER}])"
    f"(?:قال|قالت|قالوا|يقول)"
    f"(?![{_ARABIC_LETTER}])"
)

_LEADING_NOISE = ' \t\n،؛.,:"‏‎٫٬‘’“”'

# لو القطع طلّع نص قصير أوي يبقى غالبًا وقع في نص اسم راوٍ
# أو في آخر الحديث. أأمن نرجّع النص كامل من إننا نبني الفهرس
# على شظية.
MIN_MATN_CHARS = 25

# السند بيكون في أول النص دايمًا. قِسنا توزيع طوله على
# الحالات اللي المطابقة فيها مؤكدة: الوسيط 206 حرف،
# والمئين 98 هو 801. فبنقصر البحث على أول 800 حرف —
# من غير الحد ده الأحاديث الطويلة بيتقص منها جوه المتن
# لأن كلمات زي «عن» و«قال» بتتكرر في السرد نفسه.
ISNAD_WINDOW_CHARS = 800


def strip_diacritics(text):
    """
    بيشيل التشكيل قبل الـ embedding.

    الـ tokenizer بتاع e5 بيفكّك العربي المشكول لحروف مفردة
    (3.59 ضعف عدد التوكنز، ومفيش وحدات معنى)، فالبحث بيبوظ.
    النص الأصلي بتشكيله بيفضل متخزّن للعرض.
    """

    return _DIACRITICS.sub("", text)


def normalize_for_matching(text):
    """
    بترجع النسخة المطبَّعة وخريطة مواضعها في النص الأصلي.
    """

    chars = []
    index_map = []

    for i, ch in enumerate(text):

        if _DIACRITICS.match(ch):
            continue

        chars.append(_ALEF_FORMS.get(ch, ch))
        index_map.append(i)

    return "".join(chars), index_map


def split_isnad_matn(text):
    """
    يفصل السند عن المتن.

    الأول: يدوّر على فعل رواية + ذكر النبي (قال رسول الله،
    عن النبي، أن رسول الله ...) والمتن بيبدأ من هناك.

    ولو ملقاش — وده بيحصل في الأحاديث الموقوفة — بيرجع
    لآخر حلقة في السند وياخد أول فعل قول بعدها.

    ولو الاتنين فشلوا بيرجع النص كما هو.
    """

    if not text:
        return text

    normalized, index_map = normalize_for_matching(text)

    marker = _MARKER_RE.search(normalized)

    if marker and index_map[marker.start()] <= ISNAD_WINDOW_CHARS:

        matn = text[index_map[marker.start()]:]

        if len(matn) >= MIN_MATN_CHARS:
            return matn

        return text

    # آخر حلقة سند جوه النافذة بس — أي «عن» أو «قال» بعد كده
    # بتبقى جزء من السرد مش من السند.
    last_link = None

    for link in _CHAIN_RE.finditer(normalized):

        if index_map[link.start()] > ISNAD_WINDOW_CHARS:
            break

        last_link = link

    if last_link:

        said = _SAID_RE.search(normalized, last_link.end())

        if said and said.end() < len(index_map):

            if index_map[said.start()] <= ISNAD_WINDOW_CHARS:

                matn = text[index_map[said.end()]:].lstrip(_LEADING_NOISE)

                if len(matn) >= MIN_MATN_CHARS:
                    return matn

    return text


def token_count(text):
    """
    يحسب عدد الـTokens الحقيقي باستخدام Tokenizer الخاص بالموديل.
    """

    return len(
        get_model().tokenizer(
            text,
            truncation=False
        )["input_ids"]
    )


def split_long_text(text, max_tokens=MAX_TOKENS):
    """
    يقسم النص الطويل إلى عدة Chunks
    بحيث لا يتجاوز كل Chunk عدد الـTokens المحدد.
    """

    tokenizer = get_model().tokenizer

    token_ids = tokenizer(
        text,
        truncation=False,
        add_special_tokens=False
    )["input_ids"]

    chunks = []

    for i in range(0, len(token_ids), max_tokens):

        current_tokens = token_ids[i:i + max_tokens]

        current_text = tokenizer.decode(
            current_tokens,
            skip_special_tokens=True
        )

        chunks.append(current_text)

    return chunks


# متابعات بترجع لحديث سابق من غير ما تعيد متنه:
# «بمثله»، «بنحو حديثهم»، «بهذا الإسناد». نصها مالوش
# محتوى مستقل، فوجوده في الفهرس بيزاحم الأحاديث الحقيقية.
_REFERENCE_MARKERS = [
    "بمثل حديث", "بمثله", "بمثل هذا", "بمثل ذلك",
    "بهذا الاسناد", "بهذا الحديث", "بهذه القصة",
    "بنحوه", "بنحو حديث", "نحو حديث", "مثل حديث",
    "بمعناه", "مثله سواء", "وفيه شيء من زيادة",
]

MAX_REFERENCE_MATN_CHARS = 150


def is_reference_only(text):
    """
    بترجع True لو الـ chunk مجرد إحالة لحديث تاني من غير متن.
    الشرطين مع بعض: المتن قصير **و** فيه صيغة إحالة صريحة —
    الطول لوحده بيوقّع أجزاء قصيرة فيها محتوى حقيقي.
    """

    matn = split_isnad_matn(text)

    if len(matn) > MAX_REFERENCE_MATN_CHARS:
        return False

    normalized, _ = normalize_for_matching(matn)

    return any(marker in normalized for marker in _REFERENCE_MARKERS)


def chunk_text(text, max_tokens=MAX_TOKENS):
    """
    التقطيع المستخدم في الـ ingest: بيحافظ على النص كامل
    (سند + متن) وبيقسم بالطول بس لما يتعدى الحد.

    مهم: إزالة السند مش بتحصل هنا. دي صيغة تمثيل،
    ومكانها مرحلة الـ embedding عشان نقدر نقارن الصيغ ببعضها.

    الطول بيتقاس على النص من غير تشكيل لأن ده اللي بيتعمله
    embedding فعلاً، لكن اللي بيتخزّن هو النص الأصلي بتشكيله.
    """

    stripped_tokens = token_count(strip_diacritics(text))

    if stripped_tokens <= max_tokens:
        return [text]

    # الحد المكافئ على النص المشكول: التشكيل بيضخّم عدد
    # التوكنز، فبنكبّر الحد بنفس النسبة عشان الأجزاء الناتجة
    # تفضل تحت الحد بعد ما يتشال التشكيل.
    inflation = token_count(text) / max(stripped_tokens, 1)

    return split_long_text(text, max(1, int(max_tokens * inflation)))


def prepare_text(text, max_tokens=MAX_TOKENS):
    """
    Pipeline كاملة:
    1. إزالة السند
    2. فحص عدد الـTokens
    3. لو طويل يتقسم
    """

    matn = split_isnad_matn(text)

    if token_count(matn) <= max_tokens:
        return [matn]

    return split_long_text(matn, max_tokens)
