"""Tests for slim cloud dependency profile, MUSNAD_CLOUD=1 guards, and lazy heavy imports."""

from __future__ import annotations

import ast
from pathlib import Path
import tomllib

import pytest

from src.pipeline import build_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent

HEAVY_IMPORTS = {
    "torch",
    "transformers",
    "sentence_transformers",
    "faiss",
    "rank_bm25",
    "chromadb",
    "openpyxl",
}

CLOUD_IMPORTED_SRC_MODULES = [
    "src/answer.py",
    "src/agent.py",
    "src/pipeline.py",
    "src/retrieve.py",
    "src/lexical.py",
    "src/rerank.py",
    "src/router.py",
    "src/sanad_context.py",
    "src/sanad_graph.py",
    "src/build_sanad_graph.py",
    "src/profile_mis.py",
    "src/sanad_names.py",
    "src/experiment_variants.py",
    "src/trace.py",
    "src/utils.py",
    "src/config.py",
]


def _top_level_imported_roots(py_path: Path) -> set[str]:
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    roots: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_pyproject_cloud_group_excludes_heavy_packages() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    cloud_deps = data["dependency-groups"]["cloud"]
    names = {dep.split(">=")[0].split("==")[0].split("<")[0].strip().lower() for dep in cloud_deps}

    assert {"numpy", "google-genai", "python-dotenv", "streamlit", "boto3"}.issubset(names)
    for banned in ("torch", "sentence-transformers", "transformers", "faiss-cpu", "rank-bm25", "chromadb", "openpyxl"):
        assert banned not in names


def test_cloud_runtime_modules_have_no_heavy_top_level_imports() -> None:
    for rel in CLOUD_IMPORTED_SRC_MODULES:
        top_imports = _top_level_imported_roots(REPO_ROOT / rel)
        overlap = top_imports & HEAVY_IMPORTS
        assert not overlap, f"{rel} has banned top-level imports for cloud image: {sorted(overlap)}"


def test_cloud_mode_disables_legacy_mode_and_fallback(monkeypatch, tmp_path: Path) -> None:
    import json
    import numpy as np

    monkeypatch.setenv("MUSNAD_CLOUD", "1")
    with pytest.raises(RuntimeError, match="Legacy pipeline is disabled"):
        build_pipeline(mode="legacy")

    # Verify UpgradedRetriever built under MUSNAD_CLOUD=1 sets fallback_factory=None
    chunks_path = tmp_path / "chunks.json"
    ids_path = tmp_path / "ids.json"
    vecs_path = tmp_path / "vecs.npy"
    chunks_path.write_text(
        json.dumps([{"id": "h1", "text": "نص حديث", "metadata": {"hadith_number": 1}}]),
        encoding="utf-8",
    )
    ids_path.write_text(json.dumps(["h1"]), encoding="utf-8")
    np.save(vecs_path, np.ones((1, 4), dtype=np.float32))

    retriever = build_pipeline(
        mode="upgraded",
        matn_vectors_path=vecs_path,
        ids_path=ids_path,
        chunks_path=chunks_path,
        query_cache_path=tmp_path / "missing_q.npz",
        hyde_cache_path=tmp_path / "missing_h.npz",
    )
    assert retriever.fallback_factory is None
    assert retriever.fallback_retriever is None
