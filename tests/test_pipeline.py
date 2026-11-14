import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from google.genai.errors import ServerError

import src.answer as answer
import src.answer_eval as answer_eval
import src.evaluate as evaluate
from src.config import (
    DOC_EXPANSIONS_G38_PATH,
    IDS_MATN,
    PROCESSED_CHUNKS_PATH,
    VECTORS_EXPANSION_G38_GEMINI001,
    VECTORS_MATN,
    VECTORS_MATN_GEMINI001,
    VECTORS_PATH,
)
import src.pipeline as pipeline_module
from src.pipeline import (
    BM25_WEIGHT,
    CANDIDATES,
    DEFAULT_K,
    DEFAULT_MODE,
    DENSE_WEIGHT,
    RERANK_MODEL,
    RRF_K,
    TOP_K_IN,
    UPGRADED_HYDE_ALPHA,
    UPGRADED_WEIGHTS,
    VARIANT,
    build_pipeline,
    pipeline_config,
    resolve_pipeline_mode,
)
from rerank import MMARCO, RerankingRetriever
from retrieve import HybridRetriever, Retriever, UpgradedRetriever, load_chunk_lookup
from utils import MODEL_NAME


def _write_fixture_index(directory):
    root = Path(directory)
    chunks = [
        {
            "id": "101_0",
            "text": "حدثنا زيد قال رسول الله لا يؤمن أحدكم حتى يحب لأخيه ما يحب لنفسه",
            "matn": "لا يؤمن أحدكم حتى يحب لأخيه ما يحب لنفسه",
            "metadata": {"hadith_number": 7354, "chapter_arabic": "كتاب الإيمان"},
        },
        {
            "id": "102_0",
            "text": "حدثنا عمرو قال رسول الله من صام رمضان إيمانا واحتسابا غفر له",
            "matn": "من صام رمضان إيمانا واحتسابا غفر له",
            "metadata": {"hadith_number": 8950, "chapter_arabic": "كتاب الصيام"},
        },
    ]
    chunks_path = root / "chunks.json"
    chunks_path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")

    vectors = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    ids = ["101_0", "102_0"]

    paths = {}
    for prefix in ("full", "matn", "title"):
        vec_path = root / f"vectors_{prefix}.npy"
        ids_path = root / f"ids_{prefix}.json"
        np.save(vec_path, vectors)
        ids_path.write_text(json.dumps(ids), encoding="utf-8")
        paths[prefix] = (vec_path, ids_path)

    return chunks_path, paths


@pytest.mark.parametrize(
    ("stage", "embedding_calls", "hyde_calls"),
    [("query embedding", 1, 0), ("HyDE", 1, 1), ("HyDE embedding", 2, 1)],
)
@pytest.mark.parametrize("failure_kind", ["timeout", "api-error"])
def test_default_pipeline_returns_legacy_results_on_api_failure(
    tmp_path, monkeypatch, stage, embedding_calls, hyde_calls, failure_kind
):
    chunks_path, paths = _write_fixture_index(tmp_path)
    vectors_path, ids_path = paths["matn"]
    expansions_path = tmp_path / "expansions.jsonl"
    expansions_path.write_text(
        json.dumps({"chunk_id": "102_0", "expansion_text": "صيام رمضان"}) + "\n",
        encoding="utf-8",
    )
    index_paths = {
        "vectors_path": vectors_path,
        "ids_path": ids_path,
        "chunks_path": chunks_path,
    }
    monkeypatch.delenv("MUSNAD_RETRIEVAL_PIPELINE", raising=False)
    upgraded = build_pipeline(
        **index_paths,
        matn_vectors_path=vectors_path,
        exp_vectors_path=vectors_path,
        expansions_jsonl_path=expansions_path,
        query_cache_path=tmp_path / "no-query-cache.npz",
        hyde_cache_path=tmp_path / "no-hyde-cache.npz",
        api_timeout_ms=1500,
    )
    monkeypatch.setenv("MUSNAD_RETRIEVAL_PIPELINE", "legacy")
    legacy = build_pipeline(**index_paths)
    question = "ما فضل صيام رمضان؟"

    local_encoder = MagicMock()
    local_encoder.encode.return_value = np.array([[0.0, 1.0]], dtype=np.float32)
    local_reranker = MagicMock()
    local_reranker.predict.return_value = [0.9, 0.1]
    local_reranker.tokenizer.return_value = {"input_ids": [1, 2]}

    client = MagicMock()
    embedding = SimpleNamespace(embeddings=[SimpleNamespace(values=[0.0, 1.0])])
    client.models.embed_content.return_value = embedding
    client.models.generate_content.return_value = SimpleNamespace(text="من صام رمضان")
    failure = (
        TimeoutError("request timed out") if failure_kind == "timeout"
        else ServerError(503, {"error": {"message": "unavailable"}})
    )
    if stage == "query embedding":
        client.models.embed_content.side_effect = failure
    elif stage == "HyDE":
        client.models.generate_content.side_effect = failure
    else:
        client.models.embed_content.side_effect = [embedding, failure]

    with (
        patch("retrieve.get_model", return_value=local_encoder),
        patch("rerank.get_reranker", return_value=local_reranker),
        patch("google.genai.Client", return_value=client) as mock_api,
    ):
        expected = legacy.search(question, k=1)
        assert expected[0]["hadith_id"] == 8950
        mock_api.assert_not_called()

        assert upgraded.search(question, k=1) == expected
        assert upgraded.last_used_fallback
        assert client.models.generate_content.call_count == hyde_calls
        assert client.models.embed_content.call_count == embedding_calls
        assert all(call.kwargs["http_options"].timeout == 1500 for call in mock_api.call_args_list)


class PipelineConfigurationTests(unittest.TestCase):
    """مسار الـ CLI هو نفسه المسار المقيس في evaluate و answer_eval بالظبط."""

    def test_pipeline_constants_match_measured_parameters(self):
        self.assertEqual(DEFAULT_MODE, "upgraded")
        self.assertEqual(MODEL_NAME, "intfloat/multilingual-e5-base")
        self.assertEqual(VARIANT, "matn")
        self.assertEqual(CANDIDATES, 50)
        self.assertEqual(RRF_K, 60)
        self.assertEqual(DENSE_WEIGHT, 1.0)
        self.assertEqual(BM25_WEIGHT, 1.0)
        self.assertEqual(UPGRADED_WEIGHTS, (8.0, 2.0, 1.0, 1.0))
        self.assertEqual(UPGRADED_HYDE_ALPHA, 0.7)
        self.assertEqual(RERANK_MODEL, MMARCO)
        self.assertEqual(RERANK_MODEL, "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
        self.assertEqual(TOP_K_IN, 10)
        self.assertEqual(DEFAULT_K, 5)
        self.assertEqual(answer_eval.DEFAULT_K, 5)
        self.assertEqual(answer_eval.DEFAULT_RERANKERS, (MMARCO,))
        self.assertNotEqual(VECTORS_MATN, VECTORS_PATH)

    def test_default_mode_is_upgraded_and_env_selects_legacy(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MUSNAD_RETRIEVAL_PIPELINE", None)
            self.assertEqual(resolve_pipeline_mode(), "upgraded")
        with patch.dict(os.environ, {"MUSNAD_RETRIEVAL_PIPELINE": "legacy"}):
            self.assertEqual(resolve_pipeline_mode(), "legacy")
        with self.assertRaises(ValueError):
            resolve_pipeline_mode("unknown-mode")

        sentinel_upgraded = MagicMock()
        sentinel_legacy = MagicMock()
        with (
            patch.object(pipeline_module, "load_chunk_lookup", return_value={}),
            patch.object(UpgradedRetriever, "from_files", return_value=sentinel_upgraded) as mock_up,
            patch.object(pipeline_module, "build_legacy_pipeline", return_value=sentinel_legacy) as mock_leg,
        ):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("MUSNAD_RETRIEVAL_PIPELINE", None)
                self.assertIs(build_pipeline(), sentinel_upgraded)
                mock_up.assert_called_once()
                mock_leg.assert_not_called()

            mock_up.reset_mock()
            with patch.dict(os.environ, {"MUSNAD_RETRIEVAL_PIPELINE": "legacy"}):
                self.assertIs(build_pipeline(), sentinel_legacy)
                mock_leg.assert_called_once()
                mock_up.assert_not_called()

    def test_cli_pipeline_matches_evaluated_retriever_on_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            chunks_path, paths = _write_fixture_index(directory)
            matn_vec, matn_ids = paths["matn"]
            full_vec, full_ids = paths["full"]
            title_vec, title_ids = paths["title"]

            cli_pipeline = build_pipeline(
                mode="legacy",
                vectors_path=matn_vec,
                ids_path=matn_ids,
                chunks_path=chunks_path,
            )

            dense_variants = [
                ("Dense: full (sanad+matn)", full_vec, full_ids, "full"),
                ("Dense: matn only", matn_vec, matn_ids, "matn"),
                ("Dense: chapter + matn", title_vec, title_ids, "chapter_matn"),
            ]

            with (
                patch.object(evaluate, "DENSE_VARIANTS", dense_variants),
                patch.object(
                    evaluate,
                    "load_chunk_lookup",
                    side_effect=lambda: load_chunk_lookup(chunks_path),
                ),
            ):
                evaluated = dict(evaluate.build_retrievers(answer_eval.DEFAULT_RERANKERS))

            label = f"Hybrid + {MMARCO.split('/')[-1]}"
            self.assertIn(label, evaluated)
            eval_pipeline = evaluated[label]

            self.assertIsInstance(cli_pipeline, RerankingRetriever)
            self.assertIsInstance(cli_pipeline.base, HybridRetriever)
            self.assertIsInstance(cli_pipeline.base.dense, Retriever)

            self.assertEqual(
                pipeline_config(cli_pipeline, k=DEFAULT_K),
                pipeline_config(eval_pipeline, k=answer_eval.DEFAULT_K),
            )

    def test_answer_main_uses_build_pipeline_not_dense_full(self):
        fake_pipeline = object()
        chunks = [
            {
                "rank": 1,
                "chunk_id": "8950_0",
                "hadith_id": 8950,
                "score": 0.7367,
                "metadata": {"chapter_arabic": "كتاب الصيام"},
            }
        ]
        printed = []
        with (
            patch("src.answer.build_pipeline", return_value=fake_pipeline) as mock_build,
            patch("src.answer.load_questions", return_value=["سؤال تجريبي؟"]),
            patch("src.answer.answer_question", return_value=("إجابة", chunks)) as mock_ans,
            patch("builtins.print", side_effect=lambda *args: printed.append(" ".join(str(a) for a in args))),
        ):
            answer.main()

        mock_build.assert_called_once_with()
        mock_ans.assert_called_once_with("سؤال تجريبي؟", fake_pipeline, k=5)
        output = "\n".join(printed)
        self.assertIn("Rank: 1", output)
        self.assertIn("Hadith ID: 8950", output)
        self.assertIn("Chapter: كتاب الصيام", output)
        self.assertIn("rerank score: 0.7367", output)

    @pytest.mark.requires_data
    @unittest.skipUnless(
        VECTORS_MATN.exists() and IDS_MATN.exists() and PROCESSED_CHUNKS_PATH.exists(),
        "processed index files not present",
    )
    def test_cli_pipeline_equals_evaluated_pipeline_on_disk_index(self):
        cli_pipeline = build_pipeline(mode="legacy")
        evaluated = dict(evaluate.build_retrievers(answer_eval.DEFAULT_RERANKERS))
        label = f"Hybrid + {MMARCO.split('/')[-1]}"
        eval_pipeline = evaluated[label]

        config = pipeline_config(cli_pipeline, k=DEFAULT_K)
        self.assertEqual(config, pipeline_config(eval_pipeline, k=answer_eval.DEFAULT_K))
        self.assertEqual(config["mode"], "legacy")
        self.assertEqual(config["vectors_path"], VECTORS_MATN)
        self.assertEqual(config["ids_path"], IDS_MATN)
        self.assertEqual(config["bm25_variant"], "matn")
        self.assertEqual(config["candidates"], 50)
        self.assertEqual(config["rrf_k"], 60)
        self.assertEqual(config["rerank_model"], MMARCO)
        self.assertEqual(config["top_k_in"], 10)
        self.assertEqual(config["k"], 5)

    @pytest.mark.requires_data
    @unittest.skipUnless(
        VECTORS_MATN_GEMINI001.exists()
        and VECTORS_EXPANSION_G38_GEMINI001.exists()
        and DOC_EXPANSIONS_G38_PATH.exists()
        and IDS_MATN.exists()
        and PROCESSED_CHUNKS_PATH.exists(),
        "upgraded index files not present",
    )
    def test_cli_upgraded_pipeline_equals_evaluated_pipeline_on_disk_index(self):
        cli_pipeline = build_pipeline()
        evaluated = dict(
            evaluate.build_retrievers(
                answer_eval.DEFAULT_RERANKERS, include_upgraded=True
            )
        )
        eval_pipeline = evaluated["Upgraded (E5)"]

        self.assertIsInstance(cli_pipeline, UpgradedRetriever)
        config = pipeline_config(cli_pipeline, k=DEFAULT_K)
        self.assertEqual(config, pipeline_config(eval_pipeline, k=answer_eval.DEFAULT_K))
        self.assertEqual(config["mode"], "upgraded")
        self.assertEqual(config["weights"], (8.0, 2.0, 1.0, 1.0))
        self.assertEqual(config["hyde_alpha"], 0.7)
        self.assertIsNone(config["rerank_model"])
        self.assertEqual(config["k"], 5)

    @pytest.mark.requires_data
    @pytest.mark.requires_api
    @unittest.skipUnless(
        VECTORS_MATN_GEMINI001.exists()
        and VECTORS_EXPANSION_G38_GEMINI001.exists()
        and DOC_EXPANSIONS_G38_PATH.exists()
        and IDS_MATN.exists()
        and PROCESSED_CHUNKS_PATH.exists(),
        "upgraded index files not present",
    )
    def test_upgraded_pipeline_search_returns_top_k(self):
        cli_pipeline = build_pipeline()
        results = cli_pipeline.search("ما جزاء من صام رمضان إيماناً واحتساباً؟", k=DEFAULT_K)
        self.assertEqual(len(results), DEFAULT_K)
        self.assertFalse(cli_pipeline.last_used_fallback)
        self.assertTrue(all(r["hadith_id"] for r in results))


if __name__ == "__main__":
    unittest.main()
