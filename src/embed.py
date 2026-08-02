import sys
import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import PROCESSED_CHUNKS_PATH

with open(PROCESSED_CHUNKS_PATH, "r", encoding="utf-8") as f:
    processed_chunks = json.load(f)

texts = ["passage: " + chunk["text"] for chunk in processed_chunks]
chunk_ids = [chunk["id"] for chunk in processed_chunks]

model = SentenceTransformer("intfloat/multilingual-e5-base")
embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)

vectors_path = PROCESSED_CHUNKS_PATH.parent / "vectors.npy"
ids_path = PROCESSED_CHUNKS_PATH.parent / "chunk_ids.json"

np.save(vectors_path, embeddings)

with open(ids_path, "w", encoding="utf-8") as f:
    json.dump(chunk_ids, f, ensure_ascii=False)

print(f"Matrix shape: {embeddings.shape[0]} rows × {embeddings.shape[1]} columns")