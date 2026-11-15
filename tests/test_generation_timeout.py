"""Tests for 45 s generation timeout, single retry, and trace logging."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.agent as agent_mod
import src.answer as answer_mod
from src.trace import TraceCollector


class _FakeRetriever:
    def search(self, question: str, k: int = 5):
        return [
            {
                "rank": 1,
                "hadith_id": 7306,
                "score": 0.99,
                "text": "حدثنا أبو بكر بن أبي شيبة عن ابن عباس...",
                "metadata": {"chapter_arabic": "كتاب الإيمان"},
            }
        ][:k]


class TestGenerationTimeout(unittest.TestCase):
    def test_default_generation_timeout_is_45_seconds(self):
        if "MUSNAD_GENERATE_TIMEOUT_MS" not in os.environ:
            self.assertEqual(answer_mod.GENERATE_TIMEOUT_MS, 45000)
        self.assertEqual(answer_mod.MAX_TIMEOUT_RETRIES, 1)

    def test_answer_text_path_retries_once_on_timeout_then_succeeds(self):
        calls = 0

        class _FakeModels:
            def generate_content(self, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise TimeoutError("deadline exceeded")
                return SimpleNamespace(text="إجابة صحيحة (المصدر: صحيح مسلم، حديث رقم 7306).")

        fake_client = SimpleNamespace(models=_FakeModels())
        trace = TraceCollector()

        with (
            patch.object(answer_mod, "get_client", return_value=fake_client),
            patch.object(answer_mod, "TIMEOUT_RETRY_BACKOFF_SECONDS", 0.0),
            patch.object(answer_mod, "attach_sanad", return_value=([], None)),
        ):
            res = answer_mod.answer_with_details(
                "ما حكم الصدق؟",
                _FakeRetriever(),
                use_agent=False,
                trace=trace,
            )

        self.assertEqual(calls, 2)
        self.assertIn("7306", res["answer"])

        gen_events = [e for e in trace.events if e.stage == "generation"]
        self.assertEqual(len(gen_events), 2)
        self.assertEqual(gen_events[0].data.get("event_kind"), "timeout_retry")
        self.assertTrue(gen_events[0].data.get("timed_out"))
        self.assertEqual(gen_events[0].data.get("pro_calls"), 0)

        self.assertEqual(gen_events[1].data.get("timeout_retries"), 1)
        self.assertEqual(gen_events[1].data.get("attempts"), 2)
        # No double-counting in summary: 1 initial attempt + 1 retry = 2 Pro calls.
        self.assertEqual(trace.summary()["call_counts"]["pro_calls"], 2)

    def test_answer_text_path_stops_after_second_timeout_and_logs_trace(self):
        calls = 0

        class _SlowModels:
            def generate_content(self, **kwargs):
                nonlocal calls
                calls += 1
                time.sleep(0.15)
                return SimpleNamespace(text="should never arrive")

        fake_client = SimpleNamespace(models=_SlowModels())
        trace = TraceCollector()

        with (
            patch.object(answer_mod, "get_client", return_value=fake_client),
            patch.object(answer_mod, "GENERATE_TIMEOUT_MS", 40),
            patch.object(answer_mod, "TIMEOUT_RETRY_BACKOFF_SECONDS", 0.0),
        ):
            with self.assertRaises(answer_mod.GenerationTimeoutError) as ctx:
                answer_mod.answer_with_details(
                    "سؤال طويل المهلة",
                    _FakeRetriever(),
                    use_agent=False,
                    trace=trace,
                )

        self.assertEqual(calls, 2)
        self.assertEqual(ctx.exception.attempts, 2)
        self.assertIn("45 ثانية", str(ctx.exception))

        gen_events = [e for e in trace.events if e.stage == "generation"]
        self.assertEqual(gen_events[0].data.get("event_kind"), "timeout_retry")
        self.assertEqual(gen_events[-1].data.get("status"), "timeout")
        self.assertTrue(gen_events[-1].data.get("timed_out"))
        self.assertEqual(gen_events[-1].data.get("timeout_retries"), 1)
        self.assertEqual(trace.summary()["call_counts"]["pro_calls"], 2)

    def test_agent_path_retries_once_then_raises_on_second_timeout(self):
        calls = 0
        fallback_called = False

        def _slow_generate_fn(contents, *, allow_tools: bool = True):
            nonlocal calls
            calls += 1
            time.sleep(0.15)
            return SimpleNamespace(candidates=[], text="", function_calls=[])

        def _unexpected_fallback(*args, **kwargs):
            nonlocal fallback_called
            fallback_called = True
            return {"answer": "fallback", "raw": "fallback", "chunks": []}

        trace = TraceCollector()
        with patch.object(answer_mod, "TIMEOUT_RETRY_BACKOFF_SECONDS", 0.0):
            with self.assertRaises(answer_mod.GenerationTimeoutError):
                agent_mod.run_agent(
                    "ما أسانيد حديث رقم 7306؟",
                    _FakeRetriever(),
                    generate_fn=_slow_generate_fn,
                    fallback_fn=_unexpected_fallback,
                    model_timeout_s=0.04,
                    trace=trace,
                )

        self.assertEqual(calls, 2)
        self.assertFalse(fallback_called)
        gen_events = [e for e in trace.events if e.stage == "generation"]
        self.assertEqual(gen_events[0].data.get("event_kind"), "timeout_retry")
        self.assertEqual(gen_events[-1].data.get("status"), "timeout")
        self.assertTrue(gen_events[-1].data.get("timed_out"))
        self.assertEqual(trace.summary()["call_counts"]["pro_calls"], 2)

    def test_agent_path_succeeds_after_single_timeout_retry(self):
        calls = 0

        def _flaky_generate_fn(contents, *, allow_tools: bool = True):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("first call timed out")
            return SimpleNamespace(
                text="السند صحيح عن ابن عباس (المصدر: صحيح مسلم، حديث رقم 7306).",
                function_calls=[],
                candidates=[],
            )

        trace = TraceCollector()
        with (
            patch.object(answer_mod, "TIMEOUT_RETRY_BACKOFF_SECONDS", 0.0),
            patch.object(answer_mod, "attach_sanad", return_value=([], None)),
        ):
            res = agent_mod.run_agent(
                "ما صحة حديث رقم 7306؟",
                _FakeRetriever(),
                generate_fn=_flaky_generate_fn,
                search_fn=lambda q, k=5: [
                    {"hadith_id": 7306, "text": "متن", "metadata": {"chapter_arabic": "الإيمان"}}
                ],
                isnad_fn=lambda hid: {"hadith_id": hid, "status": "LINKED_WITH_RECORDED_ISNAD", "isnads": []},
                enforce_citations=False,
                model_timeout_s=1.0,
                trace=trace,
            )

        self.assertEqual(calls, 2)
        self.assertFalse(res["agent_fallback"])
        self.assertIn("7306", res["answer"])
        gen_events = [e for e in trace.events if e.stage == "generation"]
        self.assertEqual(gen_events[0].data.get("event_kind"), "timeout_retry")
        self.assertEqual(gen_events[-1].data.get("timeout_retries"), 1)
        self.assertEqual(trace.summary()["call_counts"]["pro_calls"], 2)


if __name__ == "__main__":
    unittest.main()
