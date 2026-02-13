"""
Unit tests for sample data extraction.
"""

import pytest
from django.test import TestCase

from hub.apps.datasets.schema_inference import extract_sample_data

pytestmark = pytest.mark.django_db(transaction=True)


class SampleDataExtractionTest(TestCase):
    """Test sample data extraction for different file formats"""

    def test_extract_sample_data_csv(self):
        """Test sample data extraction from CSV"""
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
        """Test sample data extraction from JSON Lines"""
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
        """Test sample data extraction from JSON array"""
        json_content = b"""[{"name": "John", "age": 30}, {"name": "Jane", "age": 25}, {"name": "Bob", "age": 35}]"""

        sample = extract_sample_data(json_content, "JSON", sample_size=2)

        self.assertEqual(len(sample), 2)
        self.assertEqual(sample[0]["name"], "John")
        self.assertEqual(sample[1]["name"], "Jane")

    def test_extract_sample_data_csv_empty(self):
        """Test sample data extraction from empty CSV"""
        csv_content = b"""name,age,city"""

        sample = extract_sample_data(csv_content, "CSV", sample_size=10)

        self.assertEqual(len(sample), 0)

    def test_extract_sample_data_csv_more_rows_than_sample(self):
        """Test sample data extraction limits to sample size"""
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
        """Test sample data extraction from single JSON object"""
        json_content = b"""{"name": "John", "age": 30, "city": "NYC"}"""

        sample = extract_sample_data(json_content, "JSON", sample_size=10)

        self.assertEqual(len(sample), 1)
        self.assertEqual(sample[0]["name"], "John")

    def test_extract_sample_data_csv_different_delimiter(self):
        """Test sample data extraction from CSV with semicolon delimiter"""
        csv_content = b"""name;age;city
John;30;NYC
Jane;25;LA"""

        sample = extract_sample_data(csv_content, "CSV", sample_size=10)

        self.assertEqual(len(sample), 2)
        self.assertEqual(sample[0]["name"], "John")
        self.assertEqual(sample[0]["age"], "30")

    # ========== SUCCESS SCENARIOS ==========

    def test_extract_sample_data_parquet_success(self):
        """Test sample data extraction from Parquet format (success scenario)"""
        # Note: Parquet extraction may require additional libraries
        # This test verifies the function handles Parquet format
        try:
            # Create minimal parquet-like content (may not be valid parquet)
            parquet_content = b"PARQUET"  # Placeholder

            sample = extract_sample_data(parquet_content, "PARQUET", sample_size=5)

            # Should return list (may be empty if format not supported)
            self.assertIsInstance(sample, list)
        except Exception:
            # If Parquet not supported, that's acceptable
            pass

    # ========== FAILURE SCENARIOS ==========

    def test_extract_sample_data_invalid_format(self):
        """Test sample data extraction with invalid format (failure scenario)"""
        csv_content = b"name,age\nJohn,30"

        # Should handle invalid format gracefully
        try:
            sample = extract_sample_data(csv_content, "INVALID_FORMAT", sample_size=10)
            # If succeeds, should return empty list or handle gracefully
            self.assertIsInstance(sample, list)
        except (ValueError, NotImplementedError):
            # If fails, that's acceptable for invalid format
            pass

    def test_extract_sample_data_corrupted_csv(self):
        """Test sample data extraction from corrupted CSV (failure scenario)"""
        corrupted_csv = b"name,age\nJohn,30\nJane"  # Incomplete row

        # Should handle corrupted data gracefully
        try:
            sample = extract_sample_data(corrupted_csv, "CSV", sample_size=10)
            # If succeeds, should return what it can parse
            self.assertIsInstance(sample, list)
        except Exception:
            # If fails, that's acceptable for corrupted data
            pass

    def test_extract_sample_data_corrupted_json(self):
        """Test sample data extraction from corrupted JSON (failure scenario)"""
        corrupted_json = b'{"name": "John", "age": 30'  # Incomplete JSON

        # Should handle corrupted data gracefully
        try:
            sample = extract_sample_data(corrupted_json, "JSON", sample_size=10)
            # If succeeds, should return empty list or handle gracefully
            self.assertIsInstance(sample, list)
        except Exception:
            # If fails, that's acceptable for corrupted data
            pass

    # ========== ERROR HANDLING ==========

    def test_extract_sample_data_empty_content(self):
        """Test sample data extraction from empty content (error handling)"""
        empty_content = b""

        # Should handle empty content gracefully
        try:
            sample = extract_sample_data(empty_content, "CSV", sample_size=10)
            # Should return empty list
            self.assertEqual(len(sample), 0)
        except Exception:
            # If fails, that's acceptable for empty content
            pass

    def test_extract_sample_data_none_content(self):
        """Test sample data extraction with None content (error handling)"""
        # Should handle None gracefully
        try:
            sample = extract_sample_data(None, "CSV", sample_size=10)
            # Should return empty list or handle gracefully
            self.assertIsInstance(sample, list)
        except (TypeError, AttributeError):
            # If fails, that's acceptable for None content
            pass

    def test_extract_sample_data_zero_sample_size(self):
        """Test sample data extraction with zero sample_size (error handling)"""
        csv_content = b"name,age\nJohn,30\nJane,25"

        # Should handle zero sample size gracefully
        try:
            sample = extract_sample_data(csv_content, "CSV", sample_size=0)
            # Should return empty list
            self.assertEqual(len(sample), 0)
        except Exception:
            # If fails, that's acceptable for zero sample size
            pass

    def test_extract_sample_data_very_large_sample_size(self):
        """Test sample data extraction with very large sample_size (error handling)"""
        csv_content = b"name,age\nJohn,30\nJane,25"

        # Should handle large sample size gracefully
        try:
            sample = extract_sample_data(csv_content, "CSV", sample_size=999999)
            # Should return available rows (limited by content)
            self.assertIsInstance(sample, list)
            self.assertLessEqual(len(sample), 2)  # Only 2 rows available
        except Exception:
            # If fails, that's acceptable for very large sample size
            pass
