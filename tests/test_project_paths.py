import os
import tempfile
import unittest
from pathlib import Path

import src.profile_itqan as profile_itqan
from src.config import BASE_DIR, ITQAN_DIR, MIS_DIR
from src.audit_linkage_validation_identity import DEFAULT_OUTPUT, DEFAULT_REVIEW


class AbsolutePathTests(unittest.TestCase):
    """المسارات بتتحسب من مكان المشروع مش من مجلد التشغيل."""

    def test_external_data_paths_are_absolute(self):
        self.assertTrue(ITQAN_DIR.is_absolute())
        self.assertTrue(MIS_DIR.is_absolute())

    def test_default_artifact_paths_are_absolute(self):
        self.assertTrue(DEFAULT_REVIEW.is_absolute())
        self.assertTrue(DEFAULT_OUTPUT.is_absolute())

    def test_paths_sit_under_the_project_root(self):
        self.assertEqual(ITQAN_DIR, BASE_DIR / "data" / "raw" / "external" / "itqan")
        self.assertEqual(MIS_DIR, BASE_DIR / "data" / "raw" / "external" / "mis")


class WorkingDirectoryIndependenceTests(unittest.TestCase):
    """نفس النتيجة سواء اتنفّذ من جذر المستودع أو من أي مجلد تاني."""

    def test_resolved_paths_do_not_change_with_the_process_directory(self):
        original = os.getcwd()
        try:
            os.chdir(BASE_DIR)
            from_root = (ITQAN_DIR.resolve(), MIS_DIR.resolve(), DEFAULT_REVIEW.resolve())

            with tempfile.TemporaryDirectory() as elsewhere:
                os.chdir(elsewhere)
                from_elsewhere = (
                    ITQAN_DIR.resolve(), MIS_DIR.resolve(), DEFAULT_REVIEW.resolve()
                )
                # Windows cannot remove a directory that is still the cwd.
                os.chdir(BASE_DIR)

            self.assertEqual(from_root, from_elsewhere)
        finally:
            os.chdir(original)

    def test_a_relative_path_would_have_differed(self):
        # The defect being fixed: a cwd-relative constant resolves to a
        # different place from a different directory, silently.
        original = os.getcwd()
        try:
            os.chdir(BASE_DIR)
            relative_from_root = Path("data/raw/external/itqan").resolve()

            with tempfile.TemporaryDirectory() as elsewhere:
                os.chdir(elsewhere)
                relative_from_elsewhere = Path("data/raw/external/itqan").resolve()
                os.chdir(BASE_DIR)

            self.assertNotEqual(relative_from_root, relative_from_elsewhere)
        finally:
            os.chdir(original)


class MissingDataFailsLoudlyTests(unittest.TestCase):
    """غياب البيانات بيرمي خطأ واضح، ما بيرجعش مجموعة فاضية."""

    def test_absent_profile_shards_raise_instead_of_returning_empty(self):
        original = profile_itqan.ITQAN_DIR
        try:
            with tempfile.TemporaryDirectory() as empty:
                profile_itqan.ITQAN_DIR = Path(empty)

                with self.assertRaises(FileNotFoundError) as caught:
                    profile_itqan.load_profiles()

            self.assertIn("No Itqan profile shards", str(caught.exception))
        finally:
            profile_itqan.ITQAN_DIR = original

    def test_the_error_names_the_directory_and_how_to_fix_it(self):
        original = profile_itqan.ITQAN_DIR
        try:
            with tempfile.TemporaryDirectory() as empty:
                profile_itqan.ITQAN_DIR = Path(empty)

                with self.assertRaises(FileNotFoundError) as caught:
                    profile_itqan.load_profiles()

            message = str(caught.exception)
            self.assertIn(empty, message)
            self.assertIn("DATA_SOURCES.md", message)
        finally:
            profile_itqan.ITQAN_DIR = original


if __name__ == "__main__":
    unittest.main()
