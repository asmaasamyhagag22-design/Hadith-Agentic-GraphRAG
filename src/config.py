from pathlib import Path 

BASE_DIR = Path(__file__).resolve().parent.parent

MUSLIM_JSON_PATH = BASE_DIR / "data" / "raw" /"muslim.json"
PROCESSED_CHUNKS_PATH = BASE_DIR / "data" / "processed" / "muslim_chunks.json"