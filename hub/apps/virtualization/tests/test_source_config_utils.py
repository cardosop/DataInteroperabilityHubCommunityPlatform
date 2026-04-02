"""
Unit tests for virtualization source_config_utils.

Tests credential masking for API responses.
"""
import pytest
from django.test import TestCase

from hub.apps.virtualization.source_config_utils import (
    mask_source_config,
    mask_sources_for_api,
)

pytestmark = pytest.mark.django_db(transaction=True)


class MaskSourceConfigTest(TestCase):
    """Test mask_source_config."""

    def test_mask_password(self):
        """Password field is masked."""
        config = {"type": "postgresql", "host": "localhost", "password": "secret123"}
        result = mask_source_config(config)
        self.assertEqual(result["password"], "***masked***")
        self.assertEqual(result["host"], "localhost")

    def test_mask_connection_string(self):
        """connection_string field is masked (ODBC)."""
        config = {
            "type": "odbc",
            "connection_string": "DRIVER={PostgreSQL};SERVER=localhost;PWD=secret",
        }
        result = mask_source_config(config)
        self.assertEqual(result["connection_string"], "***masked***")

    def test_mask_pwd(self):
        """pwd field is masked."""
        config = {"type": "odbc", "host": "localhost", "pwd": "mypassword"}
        result = mask_source_config(config)
        self.assertEqual(result["pwd"], "***masked***")

    def test_non_sensitive_preserved(self):
        """Non-sensitive fields are preserved."""
        config = {
            "type": "odbc",
            "host": "localhost",
            "database": "testdb",
            "username": "user",
        }
        result = mask_source_config(config)
        self.assertEqual(result["host"], "localhost")
        self.assertEqual(result["database"], "testdb")
        self.assertEqual(result["username"], "user")

    def test_empty_config(self):
        """Empty or None config returns as-is."""
        self.assertEqual(mask_source_config({}), {})
        self.assertEqual(mask_source_config(None), None)

    def test_empty_value_not_masked(self):
        """Empty string value is not masked (no credential to protect)."""
        config = {"type": "postgresql", "password": ""}
        result = mask_source_config(config)
        self.assertEqual(result["password"], "")


class MaskSourcesForApiTest(TestCase):
    """Test mask_sources_for_api."""

    def test_mask_multiple_sources(self):
        """Multiple sources are masked."""
        sources = [
            {"type": "postgresql", "host": "db1", "password": "p1"},
            {"type": "odbc", "connection_string": "DSN=myodbc;PWD=secret"},
        ]
        result = mask_sources_for_api(sources)
        self.assertEqual(result[0]["password"], "***masked***")
        self.assertEqual(result[1]["connection_string"], "***masked***")

    def test_empty_list(self):
        """Empty list returns empty list."""
        self.assertEqual(mask_sources_for_api([]), [])

    def test_none_returns_empty(self):
        """None returns empty list."""
        self.assertEqual(mask_sources_for_api(None), [])
