"""Tests verifying concurrent HyDE + raw-query embedding parity and true overlap."""

from __future__ import annotations

import hashlib
import threading
import time
from unittest.mock import patch

import numpy as np

from src.answer import format_context
from src.retrieve import UpgradedRetriever, _l2_normalize_vec
from src.utils import strip_diacritics


def _deterministic_vec(text: str, dim: int = 16) -> list[float]:
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    vec = rng.normal(size=dim).astype(np.float32)
    return vec.tolist()


def _sequential_reference_blended(
    retriever: UpgradedRetriever, question: str, client_factory
) -> tuple[np.ndarray, list[dict]]:
    """Run the pre-change sequential embed -> HyDE -> embed flow for strict parity checks."""
    from google.genai import types

    embed_client = client_factory()
    resp_q = embed_client.models.embed_content(
        model="gemini-embedding-001",
        contents=[strip_diacritics(question)],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY", output_dimensionality=3072
        ),
    )
    q_vec = _l2_normalize_vec(resp_q.embeddings[0].values)

    gen_client = client_factory(location="global")
    resp_h = gen_client.models.generate_content(
        model="gemini-3.8-flash",
        contents=question,
        config=types.GenerateContentConfig(temperature=0),
    )
    pseudo = strip_diacritics((resp_h.text or "").strip()) or strip_diacritics(question)
    resp_he = embed_client.models.embed_content(
        model="gemini-embedding-001",
        contents=[pseudo],
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY", output_dimensionality=3072
        ),
    )
    h_vec = _l2_normalize_vec(resp_he.embeddings[0].values)
    blended = _l2_normalize_vec(
        retriever.hyde_alpha * q_vec + (1.0 - retriever.hyde_alpha) * h_vec
    )
    top_ids = retriever._top_dense_ids(retriever.matn_vectors, blended, max(retriever.candidates, 5))[:5]
    chunks = []
    for rank, cid in enumerate(top_ids, start=1):
        ch = retriever.chunk_lookup[cid]
        chunks.append(
            {
                "rank": rank,
                "score": None,
                "chunk_id": ch["id"],
                "hadith_id": ch["metadata"]["hadith_number"],
                "text": ch["text"],
                "metadata": ch["metadata"],
            }
        )
    return blended, chunks


class _MockModels:
    def __init__(self, *, barrier: threading.Barrier | None = None):
        self.barrier = barrier

    def embed_content(self, *, model, contents, config):
        text = contents[0]
        # Only synchronize the first (raw query) embedding with HyDE generation;
        # HyDE embedding arrives after HyDE generation finishes.
        if self.barrier is not None and not text.startswith("حديث افتراضي"):
            self.barrier.wait(timeout=2.0)
        vals = _deterministic_vec(text)
        return type("EmbedResp", (), {"embeddings": [type("Emb", (), {"values": vals})()]})()

    def generate_content(self, *, model, contents, config):
        if self.barrier is not None:
            self.barrier.wait(timeout=2.0)
        return type(
            "GenResp",
            (),
            {"text": "حديث افتراضي في فضل الإخلاص والصلاة في المسجد."},
        )()


class _MockClient:
    def __init__(self, *args, barrier: threading.Barrier | None = None, **kwargs):
        self.models = _MockModels(barrier=barrier)


def _sample_retriever() -> UpgradedRetriever:
    dim = 16
    chunk_ids = [f"{hid}_0" for hid in (101, 102, 103, 104, 105, 106)]
    vecs = np.asarray(
        [_l2_normalize_vec(_deterministic_vec(f"matn {cid}", dim=dim)) for cid in chunk_ids],
        dtype=np.float32,
    )
    chunk_lookup = {
        cid: {
            "id": cid,
            "text": f"نص الحديث الموثق رقم {cid.split('_')[0]} في صحيح مسلم.",
            "metadata": {
                "hadith_number": int(cid.split("_")[0]),
                "chapter_arabic": f"باب {cid}",
            },
        }
        for cid in chunk_ids
    }
    return UpgradedRetriever(
        matn_vectors=vecs,
        chunk_ids=chunk_ids,
        chunk_lookup=chunk_lookup,
        weights=(1.0, 0.0, 0.0, 0.0),
        hyde_alpha=0.7,
    )


def test_parallel_hyde_outputs_identical_to_sequential():
    """Retrieved IDs, blended vector, and formatted context match sequential path identically."""
    question = "ما فضل الإخلاص والصلاة في المسجد؟"
    seq_ret = _sample_retriever()
    par_ret = _sample_retriever()

    seq_vec, seq_chunks = _sequential_reference_blended(
        seq_ret, question, lambda *a, **kw: _MockClient()
    )

    with patch("google.genai.Client", lambda *a, **kw: _MockClient()):
        par_vec = par_ret._blended_query_vector(question)
        par_chunks = par_ret.search(question, k=5)

    assert np.allclose(par_vec, seq_vec, atol=1e-7, rtol=1e-7)
    assert np.array_equal(par_vec, seq_vec)
    assert [c["hadith_id"] for c in par_chunks] == [c["hadith_id"] for c in seq_chunks]
    assert format_context(par_chunks).encode("utf-8") == format_context(seq_chunks).encode("utf-8")


def test_parallel_hyde_executes_raw_embed_and_hyde_concurrently():
    """A 2-party barrier proves raw-query embedding and HyDE generation overlap in time."""
    barrier = threading.Barrier(2, timeout=2.0)
    ret = _sample_retriever()

    with patch("google.genai.Client", lambda *a, **kw: _MockClient(barrier=barrier)):
        chunks = ret.search("سؤال للتوازي الحي", k=5)

    assert len(chunks) == 5
    assert ret.last_call_stats == {"flash_calls": 1, "embed_calls": 2}
    assert ret.last_hyde_text == "حديث افتراضي في فضل الإخلاص والصلاة في المسجد."
