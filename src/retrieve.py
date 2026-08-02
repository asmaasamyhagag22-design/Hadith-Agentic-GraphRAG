import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from config import PROCESSED_CHUNKS_PATH

VECTORS_PATH = PROCESSED_CHUNKS_PATH.parent / "vectors.npy"
IDS_PATH = PROCESSED_CHUNKS_PATH.parent / "chunk_ids.json"

embeddings = np.load(VECTORS_PATH)
with open(IDS_PATH, "r", encoding="utf-8") as f:
    chunk_ids = json.load(f)


with open(PROCESSED_CHUNKS_PATH, "r", encoding="utf-8") as f:
    processed_chunks = json.load(f)


# Create a FAISS index
dimension = embeddings.shape[1]
index = faiss.IndexFlatIP(dimension)
index.add(embeddings)


model = SentenceTransformer("intfloat/multilingual-e5-base")
def retrieve_relevant_chunks(question, k=5):
    query_text = "query: " + question
    query_embedding = model.encode([query_text], normalize_embeddings=True)
    
    scores, indices = index.search(query_embedding.reshape(1, -1), k)
    
    results = []
    for i in range(k):
        idx = indices[0][i]
        score = scores[0][i]
        chunk_id = chunk_ids[idx]
        chunk_data = next((chunk for chunk in processed_chunks if chunk["id"] == chunk_id), None)
        
        if chunk_data:
            results.append({
                "rank": i + 1,
                "score": score,
                "hadith_id": chunk_data['id'],
                "text": chunk_data['text'],
                "metadata": chunk_data['metadata']
            })
    return results
