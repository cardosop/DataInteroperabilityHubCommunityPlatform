"""
Unit tests for schema inference functionality.
"""

import pytest
from django.test import TestCase

from hub.apps.datasets.schema_inference import (
    detect_delimiter,
    detect_encoding,
    infer_enum_from_values,
    infer_field_properties,
    infer_format_from_values,
    infer_pattern_from_values,
    infer_schema_from_csv,
    infer_schema_from_json,
    infer_schema_from_parquet,
    infer_semantic_type_from_field,
    infer_type_from_values,
)

pytestmark = pytest.mark.django_db(transaction=True)


class SchemaInferenceTest(TestCase):
    """Test schema inference for different file formats"""

    def test_detect_delimiter_comma(self):
        """Test delimiter detection for comma-separated CSV"""
        content = b"name,age,city\nJohn,30,NYC\nJane,25,LA"
        delimiter = detect_delimiter(content)
        self.assertEqual(delimiter, ",")

    def test_detect_delimiter_semicolon(self):
        """Test delimiter detection for semicolon-separated CSV"""
        content = b"name;age;city\nJohn;30;NYC\nJane;25;LA"
        delimiter = detect_delimiter(content)
        self.assertEqual(delimiter, ";")

    def test_detect_delimiter_tab(self):
        """Test delimiter detection for tab-separated CSV"""
        content = b"name\tage\tcity\nJohn\t30\tNYC\nJane\t25\tLA"
        delimiter = detect_delimiter(content)
        self.assertEqual(delimiter, "\t")

    def test_infer_type_integer(self):
        """Test type inference for integer values"""
        values = [1, 2, 3, 4, 5]
        type_info = infer_type_from_values(values)
        self.assertEqual(type_info["data_type"], "integer")
        self.assertFalse(type_info["nullable"])

    def test_infer_type_float(self):
        """Test type inference for float values"""
        values = [1.5, 2.7, 3.2, 4.9, 5.1]
        type_info = infer_type_from_values(values)
        self.assertEqual(type_info["data_type"], "float")
        self.assertFalse(type_info["nullable"])

    def test_infer_type_string(self):
        """Test type inference for string values"""
        values = ["apple", "banana", "cherry"]
        type_info = infer_type_from_values(values)
        self.assertEqual(type_info["data_type"], "string")
        self.assertFalse(type_info["nullable"])

    def test_infer_type_boolean(self):
        """Test type inference for boolean values"""
        values = ["true", "false", "true", "false"]
        type_info = infer_type_from_values(values)
        self.assertEqual(type_info["data_type"], "boolean")
        self.assertFalse(type_info["nullable"])

    def test_infer_type_nullable(self):
        """Test type inference with null values"""
        values = [1, 2, None, 4, 5]
        type_info = infer_type_from_values(values)
        self.assertEqual(type_info["data_type"], "integer")
        self.assertTrue(type_info["nullable"])

    def test_infer_schema_from_csv_simple(self):
        """Test schema inference from simple CSV"""
        csv_content = b"""name,age,city
John,30,NYC
Jane,25,LA
Bob,35,Chicago"""

        schema = infer_schema_from_csv(csv_content, sample_size=10)

        self.assertIn("fields", schema)
        self.assertEqual(len(schema["fields"]), 3)

        # Check field names
        field_names = [f["name"] for f in schema["fields"]]
        self.assertIn("name", field_names)
        self.assertIn("age", field_names)
        self.assertIn("city", field_names)

        # Check age field type (should be integer)
        age_field = next(f for f in schema["fields"] if f["name"] == "age")
        self.assertEqual(age_field["data_type"], "integer")

        # Check inference metadata
        self.assertIn("inference_metadata", schema)
        self.assertEqual(schema["inference_metadata"]["format"], "CSV")


class EnhancedSchemaInferenceTest(TestCase):
    """Test enhanced schema inference with format, pattern, enum, semantic_type (GAP-8.2.4)"""

    def test_infer_format_email(self):
        """Test format inference for email addresses (GAP-8.2.4)"""
        values = ["user@example.com", "test@domain.org", "admin@company.co.uk"]

        format_value = infer_format_from_values(values, "email")

        self.assertEqual(format_value, "email")

    def test_infer_format_uri(self):
        """Test format inference for URIs (GAP-8.2.4)"""
        values = ["https://example.com", "http://test.org", "ftp://files.example.com"]

        format_value = infer_format_from_values(values, "url")

        self.assertEqual(format_value, "uri")

    def test_infer_format_date_time(self):
        """Test format inference for date-time values (GAP-8.2.4)"""
        values = ["2024-01-01T12:00:00", "2024-02-15T18:30:00", "2024-03-20T09:15:00"]

        format_value = infer_format_from_values(values, "timestamp")

        self.assertEqual(format_value, "date-time")

    def test_infer_format_date(self):
        """Test format inference for date values (GAP-8.2.4)"""
        values = ["2024-01-01", "2024-02-15", "2024-03-20"]

        format_value = infer_format_from_values(values, "date")

        self.assertEqual(format_value, "date")

    def test_infer_pattern_phone(self):
        """Test pattern inference for phone numbers (GAP-8.2.4)"""
        values = ["+1-555-123-4567", "+44 20 7946 0958", "555-123-4567"]

        pattern = infer_pattern_from_values(values)

        self.assertIsNotNone(pattern)
        self.assertIn("\\d", pattern)

    def test_infer_pattern_uuid(self):
        """Test pattern inference for UUIDs (GAP-8.2.4)"""
        values = [
            "550e8400-e29b-41d4-a716-446655440000",
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
        ]

        pattern = infer_pattern_from_values(values)

        self.assertIsNotNone(pattern)
        self.assertIn("8", pattern)
        self.assertIn("4", pattern)

    def test_infer_enum_from_values(self):
        """Test enum inference from limited unique values (GAP-8.2.4)"""
        values = ["active", "pending", "active", "pending", "active", "pending", "active"]

        enum = infer_enum_from_values(values)

        self.assertIsNotNone(enum)
        self.assertEqual(len(enum), 2)
        self.assertIn("active", enum)
        self.assertIn("pending", enum)

    def test_infer_enum_not_enum(self):
        """Test that enum is not inferred for too many unique values"""
        values = [f"value_{i}" for i in range(50)]

        enum = infer_enum_from_values(values)

        self.assertIsNone(enum)

    def test_infer_semantic_type_from_field_name(self):
        """Test semantic type inference from field name (GAP-8.2.4)"""
        # Test order_id
        semantic_type = infer_semantic_type_from_field("order_id", ["1", "2", "3"])
        self.assertEqual(semantic_type, "ORDER_ID")

        # Test email
        semantic_type = infer_semantic_type_from_field("email", ["test@example.com"])
        self.assertEqual(semantic_type, "EMAIL")

        # Test phone_number
        semantic_type = infer_semantic_type_from_field("phone_number", ["555-1234"])
        self.assertEqual(semantic_type, "PHONE_NUMBER")

        # Test customer_id
        semantic_type = infer_semantic_type_from_field("customer_id", ["123"])
        self.assertEqual(semantic_type, "CUSTOMER_ID")

        # Test timestamp
        semantic_type = infer_semantic_type_from_field("created_at", ["2024-01-01"])
        self.assertEqual(semantic_type, "TIMESTAMP")

    def test_infer_semantic_type_from_data_pattern(self):
        """Test semantic type inference from data patterns (GAP-8.2.4)"""
        # Test email from data
        values = ["user@example.com", "test@domain.org"]
        semantic_type = infer_semantic_type_from_field("contact", values)
        self.assertEqual(semantic_type, "EMAIL")

        # Test phone from data
        values = ["+1-555-123-4567", "+44 20 7946 0958"]
        semantic_type = infer_semantic_type_from_field("contact", values)
        self.assertEqual(semantic_type, "PHONE_NUMBER")

        # Test URI from data
        values = ["https://example.com", "http://test.org"]
        semantic_type = infer_semantic_type_from_field("link", values)
        self.assertEqual(semantic_type, "URI")

    def test_infer_field_properties_complete(self):
        """Test complete field property inference (GAP-8.2.4)"""
        values = ["user@example.com", "test@domain.org", "admin@company.co.uk"]

        properties = infer_field_properties(values, "email")

        # Verify all properties are inferred
        self.assertIn("format", properties)
        self.assertEqual(properties["format"], "email")
        self.assertIn("semantic_type", properties)
        self.assertEqual(properties["semantic_type"], "EMAIL")
        self.assertIn("min_length", properties)
        self.assertIn("max_length", properties)

    def test_infer_field_properties_with_enum(self):
        """Test field property inference with enum (GAP-8.2.4)"""
        values = ["active", "pending", "active", "pending", "active"]

        properties = infer_field_properties(values, "status")

        self.assertIn("enum", properties)
        self.assertEqual(len(properties["enum"]), 2)
        self.assertIn("active", properties["enum"])
        self.assertIn("pending", properties["enum"])

    def test_infer_field_properties_with_pattern(self):
        """Test field property inference with pattern (GAP-8.2.4)"""
        values = ["+1-555-123-4567", "+44 20 7946 0958", "555-123-4567"]

        properties = infer_field_properties(values, "phone")

        self.assertIn("pattern", properties)
        self.assertIsNotNone(properties["pattern"])
        self.assertIn("semantic_type", properties)
        self.assertEqual(properties["semantic_type"], "PHONE_NUMBER")

    def test_schema_inference_includes_enhanced_properties(self):
        """Test that schema inference includes enhanced properties (GAP-8.2.4)"""
        csv_content = b"""email,status,phone
user@example.com,active,+1-555-123-4567
test@domain.org,pending,+44 20 7946 0958
admin@company.co.uk,active,555-123-4567"""

        schema = infer_schema_from_csv(csv_content, sample_size=10)

        # Verify enhanced properties are included
        email_field = next(f for f in schema["fields"] if f["name"] == "email")
        self.assertIn("format", email_field)
        self.assertEqual(email_field["format"], "email")
        self.assertIn("semantic_type", email_field)
        self.assertEqual(email_field["semantic_type"], "EMAIL")

        status_field = next(f for f in schema["fields"] if f["name"] == "status")
        self.assertIn("enum", status_field)
        self.assertIsNotNone(status_field["enum"])

        phone_field = next(f for f in schema["fields"] if f["name"] == "phone")
        self.assertIn("pattern", phone_field)
        self.assertIsNotNone(phone_field["pattern"])
        self.assertIn("semantic_type", phone_field)
        self.assertEqual(phone_field["semantic_type"], "PHONE_NUMBER")

    def test_schema_inference_primary_key_candidates(self):
        """Test that primary key candidates are identified (GAP-8.2.4)"""
        csv_content = b"""id,name,email
1,John,john@example.com
2,Jane,jane@example.com
3,Bob,bob@example.com"""

        schema = infer_schema_from_csv(csv_content, sample_size=10)

        self.assertIn("primary_key_candidates", schema)
        self.assertIn("id", schema["primary_key_candidates"])

    def test_schema_inference_unique_constraint_candidates(self):
        """Test that unique constraint candidates are identified (GAP-8.2.4)"""
        # Use data with unique values but some nulls to make it a unique constraint candidate
        # (not a primary key candidate since primary keys require all non-null)
        csv_content = b"""email,name,age
john@example.com,John,30
jane@example.com,Jane,25
bob@example.com,Bob,
alice@example.com,Alice,28"""

        schema = infer_schema_from_csv(csv_content, sample_size=10)

        self.assertIn("unique_constraint_candidates", schema)
        # age should be in unique candidates (has nulls, so not PK candidate)
        # email has all unique non-null values, so it's a PK candidate, not unique constraint candidate
        self.assertIn("age", schema["unique_constraint_candidates"])

    def test_schema_inference_index_recommendations(self):
        """Test that index recommendations are provided (GAP-8.2.4)"""
        csv_content = b"""order_id,customer_id,created_at,amount
ORD-001,CUST-001,2024-01-01T12:00:00,100.50
ORD-002,CUST-002,2024-01-02T13:00:00,200.75
ORD-003,CUST-001,2024-01-03T14:00:00,150.25"""

        schema = infer_schema_from_csv(csv_content, sample_size=10)

        self.assertIn("index_recommendations", schema)
        self.assertGreater(len(schema["index_recommendations"]), 0)

        # Verify ID fields are recommended for indexing
        id_fields = [
            rec["field"] for rec in schema["index_recommendations"] if "id" in rec["field"].lower()
        ]
        self.assertGreater(len(id_fields), 0)

    def test_infer_schema_from_csv_with_nulls(self):
        """Test schema inference from CSV with null values"""
        csv_content = b"""name,age,city
John,30,NYC
Jane,,LA
Bob,35,"""

        schema = infer_schema_from_csv(csv_content, sample_size=10)

        # Age field should be nullable
        age_field = next(f for f in schema["fields"] if f["name"] == "age")
        self.assertTrue(age_field["nullable"])

        # City field should be nullable
        city_field = next(f for f in schema["fields"] if f["name"] == "city")
        self.assertTrue(city_field["nullable"])

    def test_infer_schema_from_json_simple(self):
        """Test schema inference from simple JSON objects"""
        json_content = b"""{"name": "John", "age": 30, "city": "NYC"}
{"name": "Jane", "age": 25, "city": "LA"}
{"name": "Bob", "age": 35, "city": "Chicago"}"""

        schema = infer_schema_from_json(json_content, sample_size=10)

        self.assertIn("fields", schema)
        self.assertEqual(len(schema["fields"]), 3)

        # Check field names
        field_names = [f["name"] for f in schema["fields"]]
        self.assertIn("name", field_names)
        self.assertIn("age", field_names)
        self.assertIn("city", field_names)

        # Check inference metadata
        self.assertIn("inference_metadata", schema)
        self.assertEqual(schema["inference_metadata"]["format"], "JSON")

    def test_infer_schema_from_json_array(self):
        """Test schema inference from JSON array"""
        json_content = b"""[{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]"""

        schema = infer_schema_from_json(json_content, sample_size=10)

        self.assertIn("fields", schema)
        self.assertEqual(len(schema["fields"]), 2)

    def test_infer_schema_from_json_nested(self):
        """Test schema inference from nested JSON objects"""
        json_content = b"""{"user": {"name": "John", "age": 30}, "city": "NYC"}
{"user": {"name": "Jane", "age": 25}, "city": "LA"}"""

        schema = infer_schema_from_json(json_content, sample_size=10)

        # Should flatten nested objects with dot notation
        field_names = [f["name"] for f in schema["fields"]]
        self.assertIn("user.name", field_names)
        self.assertIn("user.age", field_names)
        self.assertIn("city", field_names)

    def test_infer_schema_from_csv_delimiter_detection(self):
        """Test CSV schema inference with different delimiters"""
        # Semicolon-delimited CSV
        csv_content = b"""name;age;city
John;30;NYC
Jane;25;LA"""

        schema = infer_schema_from_csv(csv_content, sample_size=10)

        self.assertIn("inference_metadata", schema)
        # Should detect semicolon delimiter
        self.assertEqual(schema["inference_metadata"]["delimiter"], ";")

    def test_infer_schema_from_csv_primary_key_candidate(self):
        """Test primary key candidate detection"""
        csv_content = b"""id,name,age
1,John,30
2,Jane,25
3,Bob,35"""

        schema = infer_schema_from_csv(csv_content, sample_size=10)

        # ID field should be a primary key candidate (all unique, non-null)
        self.assertIn("primary_key_candidates", schema)
        self.assertIn("id", schema["primary_key_candidates"])

    # ========== SUCCESS SCENARIOS ==========

    def test_schema_inference_success_csv(self):
        """Test successful schema inference from CSV (success scenario)"""
        csv_content = b"name,age\nJohn,30\nJane,25"

        schema = infer_schema_from_csv(csv_content, sample_size=10)

        # Should return schema
        self.assertIsNotNone(schema)
        self.assertIn("fields", schema)

    def test_schema_inference_success_json(self):
        """Test successful schema inference from JSON (success scenario)"""
        json_content = b'[{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]'

        schema = infer_schema_from_json(json_content, sample_size=10)

        # Should return schema
        self.assertIsNotNone(schema)
        self.assertIn("fields", schema)

    # ========== FAILURE SCENARIOS ==========

    def test_schema_inference_failure_invalid_csv(self):
        """Test schema inference with malformed binary CSV raises ValueError."""
        invalid_csv = b"\xff\xfe\x00\x01"

        with self.assertRaises(ValueError):
            infer_schema_from_csv(invalid_csv, sample_size=10)

    def test_schema_inference_failure_invalid_json(self):
        """Test schema inference with invalid JSON raises ValueError."""
        invalid_json = b'{"invalid": json}'

        with self.assertRaises(ValueError) as cm:
            infer_schema_from_json(invalid_json, sample_size=10)
        self.assertIn("Invalid JSON", str(cm.exception))

    def test_schema_inference_failure_empty_content(self):
        """Test schema inference with empty content raises ValueError."""
        empty_content = b""

        with self.assertRaises(ValueError) as cm:
            infer_schema_from_csv(empty_content, sample_size=10)
        self.assertTrue(
            "empty" in str(cm.exception).lower()
            or "no header" in str(cm.exception).lower()
            or "no columns" in str(cm.exception).lower(),
            f"Empty content must produce 'empty'/'no headers'/'no columns' error; "
            f"got: {cm.exception}",
        )

    # ========== ERROR HANDLING ==========

    def test_infer_schema_from_csv_returns_valid_schema(self):
        """infer_schema_from_csv returns a well-formed schema for valid CSV."""
        csv_content = b"name,age\nJohn,30\nJane,25"

        schema = infer_schema_from_csv(csv_content, sample_size=10)
        self.assertIsNotNone(schema)
        self.assertIn("fields", schema)
        self.assertGreater(len(schema["fields"]), 0,
            "Schema must contain at least one field")

    def test_detect_delimiter_detects_comma(self):
        """detect_delimiter returns the correct delimiter for comma-separated content."""
        content = b"name,age\nJohn,30"

        delimiter = detect_delimiter(content)
        self.assertIsNotNone(delimiter)
        self.assertEqual(delimiter, ",")

    # ── Encoding detection (gap: previously untested) ────────────────

    def test_detect_encoding_utf8(self):
        """UTF-8 bytes are detected as utf-8."""
        content = "Hello, 世界".encode("utf-8")
        encoding = detect_encoding(content)
        self.assertEqual(encoding, "utf-8")

    def test_detect_encoding_latin1_fallback(self):
        """Bytes that fail UTF-8 must fall back to latin-1 or windows-1252."""
        # 0xFF is invalid UTF-8 but valid latin-1
        content = b"Hello\xffWorld"
        encoding = detect_encoding(content)
        self.assertIn(encoding, ("latin-1", "windows-1252"),
            f"Expected latin-1 or windows-1252 fallback, got: {encoding}")

    def test_detect_encoding_empty_content(self):
        """Empty bytes must return utf-8 (the default)."""
        content = b""
        encoding = detect_encoding(content)
        self.assertEqual(encoding, "utf-8")

    # ── Parquet inference (gap: previously untested) ─────────────────

    def test_infer_schema_from_parquet_success(self):
        """Minimal Parquet file returns well-formed schema."""
        try:
            import pandas as pd
            import io
        except ImportError:
            self.skipTest("pandas not available for Parquet schema inference")

        df = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        schema = infer_schema_from_parquet(buf.getvalue())

        self.assertIsNotNone(schema)
        self.assertIn("fields", schema)
        # Must have both columns
        field_names = {f["name"] for f in schema["fields"]}
        self.assertEqual(field_names, {"id", "name"})
        self.assertIn("inference_metadata", schema)

    def test_infer_schema_from_parquet_raises_import_error_when_pandas_missing(self):
        """When pandas is not available, parquet inference raises ImportError."""
        try:
            import pandas as _pd  # noqa: F401
            self.skipTest("pandas is available; cannot test missing-pandas path")
        except ImportError:
            pass
        with self.assertRaises(ImportError):
            infer_schema_from_parquet(b"fake-parquet-bytes")
