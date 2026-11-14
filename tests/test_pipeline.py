import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import src.answer as answer
import src.answer_eval as answer_eval
import src.evaluate as evaluate
from src.config import IDS_MATN, PROCESSED_CHUNKS_PATH, VECTORS_MATN, VECTORS_PATH
from src.pipeline import (
    BM25_WEIGHT,
    CANDIDATES,
    DEFAULT_K,
    DENSE_WEIGHT,
    RERANK_MODEL,
    RRF_K,
    TOP_K_IN,
    VARIANT,
    build_pipeline,
    pipeline_config,
)
from rerank import MMARCO, RerankingRetriever
from retrieve import HybridRetriever, Retriever, load_chunk_lookup
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


class PipelineConfigurationTests(unittest.TestCase):
    """مسار الـ CLI هو نفسه المسار المقيس في evaluate و answer_eval بالظبط."""

    def test_pipeline_constants_match_measured_parameters(self):
        self.assertEqual(MODEL_NAME, "intfloat/multilingual-e5-base")
        self.assertEqual(VARIANT, "matn")
        self.assertEqual(CANDIDATES, 50)
        self.assertEqual(RRF_K, 60)
        self.assertEqual(DENSE_WEIGHT, 1.0)
        self.assertEqual(BM25_WEIGHT, 1.0)
        self.assertEqual(RERANK_MODEL, MMARCO)
        self.assertEqual(RERANK_MODEL, "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
        self.assertEqual(TOP_K_IN, 10)
        self.assertEqual(DEFAULT_K, 5)
        self.assertEqual(answer_eval.DEFAULT_K, 5)
        self.assertEqual(answer_eval.DEFAULT_RERANKERS, (MMARCO,))
        self.assertNotEqual(VECTORS_MATN, VECTORS_PATH)

    def test_cli_pipeline_matches_evaluated_retriever_on_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            chunks_path, paths = _write_fixture_index(directory)
            matn_vec, matn_ids = paths["matn"]
            full_vec, full_ids = paths["full"]
            title_vec, title_ids = paths["title"]

            cli_pipeline = build_pipeline(
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

    @unittest.skipUnless(
        VECTORS_MATN.exists() and IDS_MATN.exists() and PROCESSED_CHUNKS_PATH.exists(),
        "processed index files not present",
    )
    def test_cli_pipeline_equals_evaluated_pipeline_on_disk_index(self):
        cli_pipeline = build_pipeline()
        evaluated = dict(evaluate.build_retrievers(answer_eval.DEFAULT_RERANKERS))
        label = f"Hybrid + {MMARCO.split('/')[-1]}"
        eval_pipeline = evaluated[label]

        config = pipeline_config(cli_pipeline, k=DEFAULT_K)
        self.assertEqual(config, pipeline_config(eval_pipeline, k=answer_eval.DEFAULT_K))
        self.assertEqual(config["vectors_path"], VECTORS_MATN)
        self.assertEqual(config["ids_path"], IDS_MATN)
        self.assertEqual(config["bm25_variant"], "matn")
        self.assertEqual(config["candidates"], 50)
        self.assertEqual(config["rrf_k"], 60)
        self.assertEqual(config["rerank_model"], MMARCO)
        self.assertEqual(config["top_k_in"], 10)
        self.assertEqual(config["k"], 5)


if __name__ == "__main__":
    unittest.main()
