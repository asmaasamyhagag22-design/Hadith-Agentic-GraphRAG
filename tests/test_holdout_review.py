"""Offline unit tests for docs/holdout_review.md generation (Phase E1)."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.build_holdout_review import build_holdout_review_markdown


class HoldoutReviewBuilderTests(unittest.TestCase):
    def test_groups_by_type_extracts_vocalised_matn_and_keeps_draft_untouched(self) -> None:
        muslim_fixture = {
            "chapters": [
                {"id": 1, "arabic": "كتاب الإيمان"},
                {"id": 2, "arabic": "كتاب الصلاة"},
            ],
            "hadiths": [
                {
                    "id": 9001,
                    "idInBook": 10,
                    "chapterId": 1,
                    "arabic": "حَدَّثَنَا زَيْدٌ، قَالَ قَالَ رَسُولُ اللَّهِ صلى الله عليه وسلم ‏\"‏ الدِّينُ النَّصِيحَةُ لِلَّهِ وَلِرَسُولِهِ ‏\"‏",
                },
                {
                    "id": 9002,
                    "idInBook": 11,
                    "chapterId": 2,
                    "arabic": "حَدَّثَنَا عَمْرٌو، قَالَ سَمِعْتُ النَّبِيَّ صلى الله عليه وسلم يَقُولُ ‏\"‏ الصَّلَوَاتُ الْخَمْسُ كَفَّارَةٌ ‏\"‏",
                },
            ],
        }
        draft_rows = [
            {
                "question": "سؤال أحاديث شقيقة تجريبي؟",
                "type": "matn",
                "category": "sibling_hadiths",
                "answerable": True,
                "hadith_ids": [9002],
                "candidate_gold_ids": [9002, 9001],
            },
            {
                "question": "سؤال رفض خارج النطاق تجريبي؟",
                "type": "refusal",
                "category": "out_of_scope_refusal",
                "answerable": False,
                "hadith_ids": [],
                "candidate_gold_ids": [],
                "probe_terms": ["اختبار"],
            },
            {
                "question": "سؤال حديث مفرد تجريبي؟",
                "type": "matn",
                "category": "single_hadith",
                "answerable": True,
                "hadith_ids": [9001],
                "candidate_gold_ids": [9001],
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            muslim_path = tmp_dir / "muslim.json"
            draft_path = tmp_dir / "holdout_draft.jsonl"
            muslim_path.write_text(json.dumps(muslim_fixture, ensure_ascii=False), encoding="utf-8")
            draft_raw = "\n".join(json.dumps(r, ensure_ascii=False) for r in draft_rows) + "\n"
            draft_path.write_text(draft_raw, encoding="utf-8")
            before_sha = hashlib.sha256(draft_path.read_bytes()).hexdigest()

            md = build_holdout_review_markdown(draft_path=draft_path, muslim_path=muslim_path)
            after_sha = hashlib.sha256(draft_path.read_bytes()).hexdigest()

        self.assertEqual(before_sha, after_sha)
        # Grouped in canonical order: single_hadith -> sibling_hadiths -> out_of_scope_refusal.
        p_single = md.index("## 1. Single-hadith matn questions")
        p_sibling = md.index("## 2. Sibling-hadiths matn questions")
        p_refusal = md.index("## 3. Out-of-scope refusal questions")
        self.assertTrue(p_single < p_sibling < p_refusal)

        # Vocalised matn preserved and checkboxes attached on every item.
        self.assertIn("الدِّينُ النَّصِيحَةُ", md)
        self.assertIn("الصَّلَوَاتُ الْخَمْسُ", md)
        self.assertEqual(md.count("- [ ] accept"), 3)
        self.assertEqual(md.count("- [ ] reject"), 3)
        self.assertEqual(md.count("- [ ] edit"), 3)


if __name__ == "__main__":
    unittest.main()
