import unittest

from src.experiment_e0_gold_expansion import (
    build_equivalence_maps,
    expand_dataset,
)


class EquivalentMatnExpansionTests(unittest.TestCase):

    def test_identical_normalised_matn_expands_gold_ids(self):
        chunks = [
            {
                "id": "100_0",
                "text": "حَدَّثَنَا قُتَيْبَةُ قَالَ رَسُولُ اللَّهِ ﷺ: المسلِمُ مَنْ سَلِمَ المسلِمُونَ مِنْ لِسَانِهِ وَيَدِهِ",
                "metadata": {"hadith_number": 100},
            },
            {
                "id": "200_0",
                "text": "حَدَّثَنَا يَحْيَى قَالَ رَسُولُ اللَّهِ ﷺ: المُسْلِمُ مَنْ سَلِمَ المُسْلِمُونَ مِنْ لِسَانِهِ وَيَدِهِ",
                "metadata": {"hadith_number": 200},
            },
            {
                "id": "300_0",
                "text": "حَدَّثَنَا أَبُو بَكْرٍ قَالَ رَسُولُ اللَّهِ ﷺ: الدِّينُ النَّصِيحَةُ",
                "metadata": {"hadith_number": 300},
            },
        ]

        d_groups, l_groups, h_dense, h_lex = build_equivalence_maps(chunks)
        items = [{"question": "من المسلم؟", "answerable": True, "hadith_ids": [100]}]

        expanded, changed_dense, changed_union = expand_dataset(
            items, d_groups, l_groups, h_dense, h_lex
        )

        self.assertEqual(changed_dense, 1)
        self.assertEqual(changed_union, 1)
        self.assertEqual(expanded[0]["hadith_ids"], [100, 200])


if __name__ == "__main__":
    unittest.main()
