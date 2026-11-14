"""Offline unit tests for deterministic Arabic routing and auto|on|off composition."""

from __future__ import annotations

import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import src.answer as ans
import src.router as router_mod
from src.pipeline import resolve_agent_enabled, resolve_agent_mode
from src.retrieve import UpgradedRetriever
from src.router import (
    classify_intent,
    classify_intent_with_trace,
    load_router_weights,
    matched_chain_rule,
)


class _TextPipelineDummy:
    agent_mode = "auto"
    agent_enabled = False

    def search(self, query: str, k: int = 5):
        return [
            {
                "hadith_id": 8950,
                "rank": 1,
                "text": "حدثنا زيد قال رسول الله صلى الله عليه وسلم نص تجريبي",
                "matn": "نص تجريبي في صحيح مسلم",
                "metadata": {"chapter_arabic": "كتاب الإيمان"},
            }
        ]


def _create_sanad_fixture(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE local_hadith (
                local_id INTEGER PRIMARY KEY,
                id_in_book INTEGER,
                book_id INTEGER,
                chapter_id INTEGER,
                chapter_ar TEXT,
                chapter_en TEXT
            );
            CREATE TABLE mis_narrator (
                narrator_id TEXT PRIMARY KEY,
                label TEXT,
                name_ar TEXT,
                name_ar_mapped TEXT,
                name_en_mapped TEXT,
                gender TEXT,
                generation TEXT
            );
            CREATE TABLE mis_hadith (
                book_no INTEGER,
                hadith_no INTEGER,
                chapter_no INTEGER,
                unit_no INTEGER,
                declared_sanad_count INTEGER,
                PRIMARY KEY (book_no, hadith_no)
            );
            CREATE TABLE hadith_mis_link (
                local_id INTEGER PRIMARY KEY,
                id_in_book INTEGER,
                mis_book_no INTEGER,
                mis_hadith_no INTEGER,
                link_status TEXT,
                link_relation TEXT,
                linkage_version TEXT,
                linkage_artifact_sha256 TEXT,
                candidate_status TEXT,
                similarity REAL,
                quick_similarity REAL
            );
            CREATE TABLE isnad (
                book_no INTEGER,
                hadith_no INTEGER,
                sanad_no INTEGER,
                step_count INTEGER,
                narrator_count INTEGER,
                PRIMARY KEY (book_no, hadith_no, sanad_no)
            );
            CREATE TABLE transmission (
                book_no INTEGER,
                hadith_no INTEGER,
                sanad_no INTEGER,
                position INTEGER,
                from_narrator_id TEXT,
                to_narrator_id TEXT,
                source_label TEXT
            );
            """
        )
        conn.execute("INSERT INTO local_hadith VALUES (8950, 1, 1, 1, 'كتاب الإيمان', 'Faith')")
        conn.execute(
            "INSERT INTO mis_narrator VALUES ('13', 'Abu Huraira', 'أبو هريرة الدوسي', 'أبو هريرة الدوسي', 'Abu Huraira', 'M', 'Comp')"
        )
        conn.execute(
            "INSERT INTO mis_narrator VALUES ('30022', 'Zuhayr', 'زهير بن حرب', 'زهير بن حرب', 'Zuhayr', 'M', '3rd')"
        )
        conn.execute("INSERT INTO mis_hadith VALUES (1, 10, 1, 1, 1)")
        conn.execute(
            "INSERT INTO hadith_mis_link VALUES (8950, 1, 1, 10, 'ACCEPTED_LINK_V1', 'exact', 'v1', 'abc', 'ok', 1.0, 1.0)"
        )
        conn.execute("INSERT INTO isnad VALUES (1, 10, 1, 1, 2)")
        conn.execute("INSERT INTO transmission VALUES (1, 10, 1, 1, '13', '30022', 'src')")
        conn.commit()
    finally:
        conn.close()


class RouterClassifierTests(unittest.TestCase):
    def test_chain_questions_with_or_without_id(self) -> None:
        chain_prompts = [
            "من الصحابي الذي روى حديث رقم 5120؟",
            "من الصحابية التي روت هذا الحديث عن النبي؟",
            "من هو شيخ الإمام مسلم في الحديث رقم 6011؟",
            "عمّن أخذ الإمام مسلم الحديث رقم 7100؟",
            "من الراوي المباشر لمسلم في حديث رقم 8400؟",
            "كم عدد الأسانيد المسجلة للحديث رقم 6500؟",
            "كم طريقًا ورد بها إسناد الحديث رقم 9102؟",
            "هل ورد اسم الزهري في سند الحديث رقم 7001؟",
            "هل شارك مالك بن أنس في رواية الحديث رقم 8002؟",
            "هل يظهر قتادة ضمن رواة حديث رقم 8300؟",
            "من روى حديث بني الإسلام على خمس في صحيح مسلم؟",
            "من هو الصحابي راوي حديث الدين المعاملة؟",
            "اذكر رواة الحديث رقم 9015 وحكم رواته.",
            "ما سلسلة إسناد حديث بدء الوحي؟",
        ]
        for q in chain_prompts:
            with self.subTest(q=q):
                self.assertEqual(classify_intent(q), "chain", f"Missed rule: {q}")
                self.assertIsNotNone(matched_chain_rule(q))

    def test_general_arabic_text_questions_stay_text(self) -> None:
        text_prompts = [
            "ما حكم الوضوء بعد أكل لحم الإبل؟",
            "كم عدد ركعات صلاة الضحى؟",
            "من هو المفلس يوم القيامة كما بيّن النبي؟",
            "ماذا حدث عندما فتح المسلمون مكة؟",
            "هل ورد في الحديث النهي عن الغضب؟",
            "ما فضل ذكر الله كما روي في صحيح مسلم؟",
            "من الصحابي الذي سأل النبي عن علامات الساعة في القصة؟",
            "كيف يؤدي المسلم صلاة الاستسقاء؟",
            "ما عقوبة الغش في البيع والمعاملات؟",
        ]
        for q in text_prompts:
            with self.subTest(q=q):
                self.assertEqual(classify_intent(q), "text", f"False trigger rule={matched_chain_rule(q)}: {q}")

    def test_optional_definite_prefix_pairs_and_no_buggy_al_question_mark(self) -> None:
        source_text = Path(router_mod.__file__).read_text(encoding="utf-8")
        # Catch bare "ال?" where "?" makes only "ل" optional instead of "(?:ال)?".
        self.assertIsNone(
            re.search(r"ال\?", source_text),
            "Found bare 'ال?' in src/router.py; must use '(?:ال)?'",
        )

        # General Arabic definite vs bare-noun pairs covering every fixed rule.
        definite_bare_pairs = [
            ("ما سند الحديث في باب الصبر؟", "ما سند حديث في باب الصبر؟"),
            ("ما سلسلة الحديث الوارد؟", "ما سلسلة حديث الوارد؟"),
            ("كم عدد الأسانيد؟", "كم عدد أسانيد هذه الرواية؟"),
            ("كم عدد الطرق المذكورة؟", "كم عدد طرق هذه الرواية؟"),
            ("كم عدد السلاسل الواردة؟", "كم عدد سلاسل هذه الرواية؟"),
            ("كم عدد طرق الحديث في الرواية؟", "كم عدد طرق حديث في رواية؟"),
            ("ما الطرق المسجلة لهذا الباب؟", "هل لهذا الباب طرق مسجلة؟"),
            ("ما الطرق الواردة للحديث؟", "هل وردت طرق واردة لحديث الغسل؟"),
            ("ما أسماء الرواة في هذا الباب؟", "ما أسماء رواة المتن؟"),
            ("من الراوي المباشر لمسلم هنا؟", "من راوي المباشر لمسلم هنا؟"),
            ("أخذ مسلم الحديث عنه أم لا؟", "أخذ مسلم حديث عنه أم لا؟"),
            ("من روى الحديث عن أصحابه؟", "من روى حديث الزكاة عن أصحابه؟"),
            ("من الصحابي راوي الحديث؟", "من صحابي راوي حديث الصدق؟"),
            ("ما اسم الصحابي الذي روى حديث رقم 4100؟", "ما اسم صحابي روى حديث رقم 4100؟"),
            ("هل ورد هذا الاسم في الحديث رقم 4120؟", "هل ورد هذا الاسم في حديث رقم 4120؟"),
            ("هل هو من شيوخ الحديث في الصحيح؟", "هل هو من شيوخ حديث الإخلاص؟"),
        ]
        for with_al, without_al in definite_bare_pairs:
            with self.subTest(with_al=with_al, without_al=without_al):
                self.assertEqual(
                    classify_intent(with_al),
                    "chain",
                    f"Definite form missed: {with_al}",
                )
                self.assertEqual(
                    classify_intent(without_al),
                    "chain",
                    f"Bare form missed (optional-prefix bug): {without_al}",
                )


class AgentModeCompositionTests(unittest.TestCase):
    def test_resolve_agent_mode_supports_auto_on_off(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_agent_mode(), "auto")
        self.assertEqual(resolve_agent_mode("auto"), "auto")
        self.assertEqual(resolve_agent_mode("ON"), "on")
        self.assertEqual(resolve_agent_mode("off"), "off")
        self.assertEqual(resolve_agent_mode(True), "on")
        self.assertEqual(resolve_agent_mode(False), "off")
        with self.assertRaises(ValueError):
            resolve_agent_mode("invalid")

        self.assertTrue(resolve_agent_enabled("auto", question="كم عدد الأسانيد للحديث رقم 5120؟"))
        self.assertFalse(resolve_agent_enabled("auto", question="ما حكم الصيام يوم الاثنين؟"))
        self.assertFalse(resolve_agent_enabled("auto"))

    def test_auto_mode_dispatches_text_to_rag_with_sanad_and_chain_to_agent(self) -> None:
        retriever = _TextPipelineDummy()
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "sanad.sqlite"
            _create_sanad_fixture(db_path)

            text_reply = "الحكم مذكور في الحديث (المصدر: صحيح مسلم، حديث رقم 8950)"
            fake_agent_out = {
                "answer": "روى الحديث أبو هريرة (المصدر: صحيح مسلم، حديث رقم 8950)",
                "raw": "روى الحديث أبو هريرة (المصدر: صحيح مسلم، حديث رقم 8950)",
                "chunks": [{"hadith_id": 8950}],
                "sanad": [],
                "sanad_error": None,
                "invalid_citation_attempt": False,
                "missing_citation_attempt": False,
                "loose_out_of_context_attempt": False,
                "mixed_refusal_attempt": False,
                "regenerated": False,
                "rewritten": None,
                "retried": False,
            }

            with patch.dict(os.environ, {"MUSNAD_AGENT": "auto"}):
                with (
                    patch("src.answer.generate", return_value=text_reply) as mock_gen,
                    patch("src.agent.run_agent", return_value=fake_agent_out) as mock_agent,
                ):
                    text_out = ans.answer_with_details(
                        "ما فضل الصدقة في صحيح مسلم؟",
                        retriever,
                        sanad_db_path=db_path,
                    )
                    self.assertEqual(mock_gen.call_count, 1)
                    self.assertEqual(mock_agent.call_count, 0)
                    self.assertEqual(len(text_out["sanad"]), 1)
                    self.assertEqual(text_out["sanad"][0]["hadith_id"], 8950)

                    chain_out = ans.answer_with_details(
                        "من الصحابي الذي روى الحديث رقم 8950؟",
                        retriever,
                        sanad_db_path=db_path,
                    )
                    self.assertEqual(mock_gen.call_count, 1)
                    self.assertEqual(mock_agent.call_count, 1)
                    self.assertEqual(chain_out["answer"], fake_agent_out["answer"])


class RouterV3EmbeddingTests(unittest.TestCase):
    def test_v2_fast_path_skips_embedding_and_falls_back_when_missing(self) -> None:
        called = 0

        def _fail_if_called(q: str):
            nonlocal called
            called += 1
            raise RuntimeError("embedding API down")

        # v2 regex fast path must return chain without invoking embedding provider.
        fast_trace = classify_intent_with_trace(
            "كم عدد الأسانيد للحديث رقم 5120؟",
            embedding_provider=_fail_if_called,
            version="v3",
        )
        self.assertEqual(fast_trace["intent"], "chain")
        self.assertEqual(fast_trace["path"], "v2_fast_path")
        self.assertEqual(called, 0)

        # When v2 misses and embedding provider raises/returns None, fall back cleanly to v2 ("text").
        fb_trace = classify_intent_with_trace(
            "بأي صحابي ارتبط هذا الأثر؟",
            embedding_provider=_fail_if_called,
            version="v3",
        )
        self.assertEqual(fb_trace["intent"], "text")
        self.assertEqual(fb_trace["path"], "v2_fallback_no_embedding")
        self.assertEqual(called, 1)

    def test_v3_logreg_classifies_mocked_embeddings_with_temporary_weights(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            w_path = Path(tmp) / "weights.npz"
            w = np.zeros(3072, dtype=np.float32)
            w[0] = 6.0
            np.savez(
                w_path,
                weights=w,
                intercept=np.array([0.0], dtype=np.float64),
                threshold=np.array([0.5], dtype=np.float64),
                metadata=np.array(["{}"], dtype=object),
            )
            load_router_weights.cache_clear()
            try:
                pos_vec = np.zeros(3072, dtype=np.float32)
                pos_vec[0] = 1.0
                neg_vec = np.zeros(3072, dtype=np.float32)
                neg_vec[0] = -1.0

                chain_trace = classify_intent_with_trace(
                    "بأي شخص اتصل هذا المروي؟",
                    embedding=pos_vec,
                    version="v3",
                    weights_path=w_path,
                )
                self.assertEqual(chain_trace["intent"], "chain")
                self.assertEqual(chain_trace["path"], "v3_logreg")

                text_trace = classify_intent_with_trace(
                    "ماذا قال أبو هريرة عن الصيام؟",
                    embedding=neg_vec,
                    version="v3",
                    weights_path=w_path,
                )
                self.assertEqual(text_trace["intent"], "text")
                self.assertEqual(text_trace["path"], "v3_logreg")
            finally:
                load_router_weights.cache_clear()

    def test_upgraded_retriever_shares_query_embedding_zero_extra_calls(self) -> None:
        matn_vecs = np.zeros((1, 3072), dtype=np.float32)
        matn_vecs[0, 1] = 1.0
        chunk_lookup = {
            "8950_0": {
                "id": "8950_0",
                "text": "حدثنا زهير عن أبي هريرة قال من صام رمضان",
                "metadata": {"hadith_number": 8950, "chapter_arabic": "كتاب الصيام"},
            }
        }
        retriever = UpgradedRetriever(
            matn_vectors=matn_vecs,
            chunk_ids=["8950_0"],
            chunk_lookup=chunk_lookup,
            hyde_alpha=1.0,  # disable HyDE call so only query embed runs once
        )
        retriever.agent_mode = "auto"

        embed_calls = 0

        class _FakeEmbedModels:
            def embed_content(self, **kwargs):
                nonlocal embed_calls
                embed_calls += 1
                vec = np.zeros(3072, dtype=np.float32)
                vec[1] = 1.0
                return SimpleNamespace(embeddings=[SimpleNamespace(values=vec.tolist())])

        class _FakeGenAIClient:
            def __init__(self, **kwargs):
                self.models = _FakeEmbedModels()

        with tempfile.TemporaryDirectory() as tmp:
            w_path = Path(tmp) / "weights.npz"
            w = np.zeros(3072, dtype=np.float32)
            w[1] = -6.0  # force text classification on vec[1]=1.0
            np.savez(
                w_path,
                weights=w,
                intercept=np.array([0.0], dtype=np.float64),
                threshold=np.array([0.5], dtype=np.float64),
                metadata=np.array(["{}"], dtype=object),
            )
            db_path = Path(tmp) / "sanad.sqlite"
            _create_sanad_fixture(db_path)
            load_router_weights.cache_clear()
            try:
                with (
                    patch("google.genai.Client", _FakeGenAIClient),
                    patch.object(router_mod, "ROUTER_WEIGHTS_PATH", w_path),
                    patch("src.answer.generate", return_value="الصوم جنة (المصدر: صحيح مسلم، حديث رقم 8950)"),
                ):
                    out = ans.answer_with_details(
                        "ماذا قال أبو هريرة عن الصيام؟",
                        retriever,
                        sanad_db_path=db_path,
                    )
                self.assertEqual(embed_calls, 1)
                self.assertEqual(len(out["sanad"]), 1)
                self.assertEqual(out["sanad"][0]["hadith_id"], 8950)
            finally:
                load_router_weights.cache_clear()


if __name__ == "__main__":
    unittest.main()
