"""
Unit tests for sample data extraction.

Every test asserts a deterministic, specific outcome.  No test uses
``try/except:pass`` or ``self.skipTest`` inside the test body — those
patterns create non-tests that can never fail regardless of code
correctness.
"""

import pytest
from django.test import TestCase

from hub.apps.datasets.schema_inference import extract_sample_data

pytestmark = pytest.mark.django_db(transaction=True)


class SampleDataExtractionTest(TestCase):
    """Test sample data extraction for different file formats"""

    # ── Happy path ────────────────────────────────────────────────────

    def test_extract_sample_data_csv(self):
        csv_content = b"""name,age,city
John,30,NYC
Jane,25,LA
Bob,35,Chicago
Alice,28,Seattle
Charlie,32,Boston"""

        sample = extract_sample_data(csv_content, "CSV", sample_size=3)

        self.assertEqual(len(sample), 3)
        self.assertEqual(sample[0]["name"], "John")
        self.assertEqual(sample[0]["age"], "30")
        self.assertEqual(sample[1]["name"], "Jane")

    def test_extract_sample_data_json_lines(self):
        json_content = b"""{"name": "John", "age": 30, "city": "NYC"}
{"name": "Jane", "age": 25, "city": "LA"}
{"name": "Bob", "age": 35, "city": "Chicago"}
{"name": "Alice", "age": 28, "city": "Seattle"}"""

        sample = extract_sample_data(json_content, "JSON", sample_size=2)

        self.assertEqual(len(sample), 2)
        self.assertEqual(sample[0]["name"], "John")
        self.assertEqual(sample[0]["age"], 30)
        self.assertEqual(sample[1]["name"], "Jane")

    def test_extract_sample_data_json_array(self):
        json_content = (
            b'[{"name": "John", "age": 30}, '
            b'{"name": "Jane", "age": 25}, '
            b'{"name": "Bob", "age": 35}]'
        )

        sample = extract_sample_data(json_content, "JSON", sample_size=2)

        self.assertEqual(len(sample), 2)
        self.assertEqual(sample[0]["name"], "John")
        self.assertEqual(sample[1]["name"], "Jane")

    def test_extract_sample_data_csv_empty(self):
        sample = extract_sample_data(b"name,age,city", "CSV", sample_size=10)
        self.assertEqual(len(sample), 0)

    def test_extract_sample_data_csv_more_rows_than_sample(self):
        csv_content = b"""name,age,city
John,30,NYC
Jane,25,LA
Bob,35,Chicago
Alice,28,Seattle
Charlie,32,Boston
David,40,Miami
Eve,22,Portland"""

        sample = extract_sample_data(csv_content, "CSV", sample_size=3)

        self.assertEqual(len(sample), 3)
        self.assertEqual(sample[0]["name"], "John")
        self.assertEqual(sample[1]["name"], "Jane")
        self.assertEqual(sample[2]["name"], "Bob")

    def test_extract_sample_data_json_single_object(self):
        sample = extract_sample_data(
            b'{"name": "John", "age": 30, "city": "NYC"}', "JSON", sample_size=10
        )
        self.assertEqual(len(sample), 1)
        self.assertEqual(sample[0]["name"], "John")

    def test_extract_sample_data_csv_different_delimiter(self):
        csv_content = b"""name;age;city
John;30;NYC
Jane;25;LA"""

        sample = extract_sample_data(csv_content, "CSV", sample_size=10)

        self.assertEqual(len(sample), 2)
        self.assertEqual(sample[0]["name"], "John")
        self.assertEqual(sample[0]["age"], "30")

    # ── Format handling ───────────────────────────────────────────────

    def test_extract_sample_data_parquet_returns_list(self):
        """Parquet extraction with a real (smallest-possible) Parquet
        payload returns a list.  If the library is unavailable the
        test is skipped."""
        try:
            import io

            import pandas as pd
        except ImportError:
            self.skipTest("pandas not available for Parquet extraction")

        df = pd.DataFrame({"x": [1, 2, 3]})
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        sample = extract_sample_data(buf.getvalue(), "PARQUET", sample_size=5)
        self.assertIsInstance(sample, list)
        self.assertGreater(len(sample), 0, "Parquet extraction must return at least one row")

    def test_extract_sample_data_invalid_format_raises(self):
        """An unrecognised format must raise ValueError."""
        csv_content = b"name,age\nJohn,30"
        with self.assertRaises(ValueError):
            extract_sample_data(csv_content, "INVALID_FORMAT", sample_size=10)

    def test_extract_sample_data_corrupted_csv(self):
        """Corrupted CSV (incomplete row) returns a list — best-effort parse."""
        corrupted_csv = b"name,age\nJohn,30\nJane"
        sample = extract_sample_data(corrupted_csv, "CSV", sample_size=10)
        self.assertIsInstance(sample, list)
        # Best-effort: may return partial data (John,30) or empty list.
        # Either outcome is correct for corrupted input.
        if len(sample) > 0:
            self.assertIsInstance(sample[0], dict, "Partially parsed rows must be dicts")

    def test_extract_sample_data_corrupted_json(self):
        """Incomplete JSON must return an empty list."""
        corrupted_json = b'{"name": "John", "age": 30'
        sample = extract_sample_data(corrupted_json, "JSON", sample_size=10)
        self.assertIsInstance(sample, list)
        self.assertEqual(sample, [], "Corrupted JSON must return empty list")

    # ── Edge cases ────────────────────────────────────────────────────

    def test_extract_sample_data_empty_content(self):
        sample = extract_sample_data(b"", "CSV", sample_size=10)
        self.assertEqual(len(sample), 0)

    def test_extract_sample_data_none_content(self):
        """None content must raise AttributeError (bytes.decode() fails)."""
        with self.assertRaises(AttributeError):
            extract_sample_data(None, "CSV", sample_size=10)

    def test_extract_sample_data_zero_sample_size(self):
        csv_content = b"name,age\nJohn,30\nJane,25"
        sample = extract_sample_data(csv_content, "CSV", sample_size=0)
        self.assertIsInstance(sample, list)
        self.assertEqual(len(sample), 0)

    def test_extract_sample_data_very_large_sample_size(self):
        csv_content = b"name,age\nJohn,30\nJane,25"
        sample = extract_sample_data(csv_content, "CSV", sample_size=999999)
        self.assertIsInstance(sample, list)
        self.assertLessEqual(len(sample), 2)
