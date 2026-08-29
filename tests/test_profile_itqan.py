import unittest

from src.profile_itqan import filled, name_stats


class MissingValueTests(unittest.TestCase):
    def test_none_and_string_sentinels_are_missing(self):
        for value in (None, "", " - ", "None", "null", [], {}):
            with self.subTest(value=value):
                self.assertFalse(filled(value))

    def test_real_zero_and_nonempty_collections_are_filled(self):
        for value in (0, "0", [0], {"value": None}):
            with self.subTest(value=value):
                self.assertTrue(filled(value))


class VariantCollisionTests(unittest.TestCase):
    def test_repeated_alias_within_profile_is_not_cross_profile_collision(self):
        records = [
            {"full_name": "زيد", "namings": ["زيد", "زيد"]},
            {"full_name": "عمرو", "namings": ["عمرو"]},
        ]
        stats = name_stats(records)["namings"]
        self.assertEqual(stats["duplicate_normalized_variants_within_profile"], 1)
        self.assertEqual(stats["variants_pointing_to_multiple_profiles"], 0)

    def test_alias_shared_across_profiles_is_a_collision(self):
        records = [
            {"full_name": "زيد الأول", "namings": ["أبو زيد"]},
            {"full_name": "زيد الثاني", "namings": ["أبو زيد"]},
        ]
        stats = name_stats(records)["namings"]
        self.assertEqual(stats["variants_pointing_to_multiple_profiles"], 1)
        self.assertEqual(stats["profiles_touched_by_variant_collisions"], 2)


if __name__ == "__main__":
    unittest.main()
