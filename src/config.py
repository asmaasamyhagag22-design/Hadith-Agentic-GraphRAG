import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# مجلدات البيانات الخارجية. كانت متعرّفة نسبيًا جوّه الموديولات،
# فكانت بتتحلّ بالنسبة لمجلد التشغيل مش لمكان المشروع — يعني نفس
# الكود بيرجّع صفر بروفايل من غير أي خطأ لو اتنفّذ من مجلد تاني.
EXTERNAL_DIR = RAW_DIR / "external"
ITQAN_DIR = EXTERNAL_DIR / "itqan"
MIS_DIR = EXTERNAL_DIR / "mis"

MUSLIM_JSON_PATH = RAW_DIR / "muslim.json"
QUESTIONS_PATH = RAW_DIR / "questions.txt"
GOLDEN_PATH = RAW_DIR / "golden.jsonl"

# مجموعة كبيرة مولَّدة آليًا — لاختيار الإعدادات فقط.
# الأرقام اللي تتقال للناس بتيجي من GOLDEN_PATH المتحقَّق منها يدويًا.
SYNTHETIC_EVAL_PATH = RAW_DIR / "synthetic_eval.jsonl"

PROCESSED_CHUNKS_PATH = PROCESSED_DIR / "muslim_chunks.json"

DATA_BASE_PATH = DATA_DIR / "database"
DOCUMENT_REPRESENTATION = "full"

# كل ملف vectors ليه ملف ids بنفس الترتيب. الاتنين بيتحمّلوا مع بعض دايمًا.
VECTORS_PATH = PROCESSED_DIR / "vectors.npy"
IDS_PATH = PROCESSED_DIR / "chunk_ids.json"

VECTORS_MATN = PROCESSED_DIR / "vectors_matn.npy"
IDS_MATN = PROCESSED_DIR / "chunk_ids_matn.json"

VECTORS_MATN_WITH_TITLE = PROCESSED_DIR / "vectors_title.npy"
IDS_MATN_WITH_TITLE = PROCESSED_DIR / "chunk_ids_title.json"

# مسار الاسترجاع المختار في التجربة النهائية (E5):
# "upgraded" = gemini-embedding-001 (3072d) + E2 expansion (g38flash) + E4 HyDE (0.7:0.3) + 4-way RRF (8:2:1:1) [الافتراضي]
# "legacy"   = multilingual-e5-base + BM25 (RRF 1:1) + mmarco top-10 reranker (محلي بلا API، ويُستخدم تلقائيًا كبديل احتياطي عند تعثّر API)
RETRIEVAL_PIPELINE = os.environ.get("MUSNAD_RETRIEVAL_PIPELINE", "upgraded")
API_TIMEOUT_MS = int(os.environ.get("MUSNAD_API_TIMEOUT_MS", "15000"))

VECTORS_MATN_GEMINI001 = PROCESSED_DIR / "vectors_matn_gemini001_3072.npy"
VECTORS_EXPANSION_G38_GEMINI001 = (
    PROCESSED_DIR / "vectors_expansion_g38flash_gemini001_3072.npy"
)
DOC_EXPANSIONS_G38_PATH = PROCESSED_DIR / "doc_expansions_g38flash.jsonl"
QUERIES_GEMINI001_CACHE_PATH = PROCESSED_DIR / "queries_gemini001.npz"
QUERIES_HYDE_G38_CACHE_PATH = (
    PROCESSED_DIR / "queries_hyde_g38flash_gemini001.npz"
)
