import tempfile
import unittest
from pathlib import Path

from src.check_docs import canonical_bytes, canonical_hash, recorded_hash


ROWS = [
    '{"question": "س1", "hadith_ids": [7354], "answerable": true}',
    '{"question": "س2", "hadith_ids": [8950], "answerable": true}',
    '{"question": "س3", "hadith_ids": [9694], "answerable": true}',
]


def write(directory, name, rows, newline="\n"):

    path = Path(directory) / name
    path.write_bytes(newline.join(rows).encode("utf-8") + newline.encode("utf-8"))

    return path


class CanonicalHashTests(unittest.TestCase):
    """البصمة لازم تتجاهل اصطلاح نهاية السطر وبس."""

    def test_crlf_and_lf_of_the_same_content_hash_identically(self):
        with tempfile.TemporaryDirectory() as directory:
            lf = write(directory, "lf.jsonl", ROWS, "\n")
            crlf = write(directory, "crlf.jsonl", ROWS, "\r\n")

            self.assertNotEqual(lf.read_bytes(), crlf.read_bytes())
            self.assertEqual(canonical_hash(lf), canonical_hash(crlf))

    def test_crlf_file_is_larger_by_exactly_one_byte_per_line(self):
        with tempfile.TemporaryDirectory() as directory:
            lf = write(directory, "lf.jsonl", ROWS, "\n")
            crlf = write(directory, "crlf.jsonl", ROWS, "\r\n")

            self.assertEqual(
                len(crlf.read_bytes()) - len(lf.read_bytes()), len(ROWS)
            )

    def test_lone_cr_is_not_normalized(self):
        # CRLF -> LF فقط. الـ CR لوحده بيفضل زي ما هو.
        self.assertEqual(canonical_bytes(b"a\r\nb"), b"a\nb")
        self.assertEqual(canonical_bytes(b"a\rb"), b"a\rb")


class ContentChangeStillDetectedTests(unittest.TestCase):
    """التطبيع مايخفيش أي تغيير حقيقي."""

    def test_changing_one_character_changes_the_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            original = write(directory, "a.jsonl", ROWS)
            edited = write(
                directory, "b.jsonl",
                [ROWS[0].replace("س1", "س9")] + ROWS[1:],
            )

            self.assertNotEqual(canonical_hash(original), canonical_hash(edited))

    def test_changing_row_order_changes_the_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            original = write(directory, "a.jsonl", ROWS)
            reordered = write(directory, "b.jsonl", list(reversed(ROWS)))

            self.assertNotEqual(
                canonical_hash(original), canonical_hash(reordered)
            )

    def test_changing_a_ground_truth_id_changes_the_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            original = write(directory, "a.jsonl", ROWS)
            expanded = write(
                directory, "b.jsonl",
                [ROWS[0].replace("[7354]", "[7354, 7355]")] + ROWS[1:],
            )

            self.assertNotEqual(
                canonical_hash(original), canonical_hash(expanded)
            )

    def test_trailing_whitespace_change_changes_the_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            original = write(directory, "a.jsonl", ROWS)
            padded = write(directory, "b.jsonl", [ROWS[0] + " "] + ROWS[1:])

            self.assertNotEqual(canonical_hash(original), canonical_hash(padded))


class RecordedHashLookupTests(unittest.TestCase):
    """كل ملف بيتقارن بالخلية بتاعته هو، مش بأي بصمة في المستند."""

    DOC = "\n".join([
        "| `data/raw/golden.jsonl` | 33 | **27** | `a7ec05f48ec0491a` |",
        "| `data/raw/synthetic_eval.jsonl` | 224 | 224 | `4bec52d5a56a8fc8` |",
        "| `data/raw/muslim.json` | 7,459 | — | `63a99e46155dc6e9` |",
    ])

    def test_each_dataset_resolves_to_its_own_recorded_hash(self):
        self.assertEqual(
            recorded_hash(self.DOC, "golden.jsonl"), "a7ec05f48ec0491a"
        )
        self.assertEqual(
            recorded_hash(self.DOC, "synthetic_eval.jsonl"), "4bec52d5a56a8fc8"
        )
        self.assertEqual(
            recorded_hash(self.DOC, "muslim.json"), "63a99e46155dc6e9"
        )

    def test_a_hash_recorded_elsewhere_does_not_satisfy_another_dataset(self):
        doc = "| `data/raw/golden.jsonl` | 33 | `a7ec05f48ec0491a` |"

        self.assertIsNone(recorded_hash(doc, "synthetic_eval.jsonl"))

    def test_full_length_digests_in_other_tables_are_not_mistaken_for_the_cell(self):
        doc = (
            "| `data/raw/muslim.json` | 7,459 | "
            "`e3ae9dc8b4a03e19dd19b13e595881cb5730b094e72a393b7d1d69e93c67742a` |"
        )

        self.assertIsNone(recorded_hash(doc, "muslim.json"))

    def test_conflicting_recorded_hashes_are_an_error(self):
        doc = "\n".join([
            "| `data/raw/golden.jsonl` | 33 | `a7ec05f48ec0491a` |",
            "| `data/raw/golden.jsonl` | 33 | `0000000000000000` |",
        ])

        with self.assertRaises(SystemExit):
            recorded_hash(doc, "golden.jsonl")


if __name__ == "__main__":
    unittest.main()
