from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

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
