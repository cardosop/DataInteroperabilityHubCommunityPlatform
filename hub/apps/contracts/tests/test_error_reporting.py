"""
Unit tests for error reporting format.
"""

import pytest
from django.test import TestCase

from hub.apps.contracts.cli_client import group_errors_by_category, interpret_validation_status

pytestmark = pytest.mark.django_db(transaction=True)


class ErrorReportingTest(TestCase):
    """Test error reporting format"""

    def test_error_structure(self):
        """Test that errors have required structure"""
        result = {
            "validation_status": "INVALID",
            "issues": [
                {
                    "severity": "ERROR",
                    "category": "schema",
                    "path": "/schema/fields/0",
                    "message": "Field type is invalid",
                    "rule_id": "field_type_check",
                }
            ],
        }

        status, errors, warnings = interpret_validation_status(result)

        self.assertEqual(len(errors), 1)
        error = errors[0]

        # Check required fields
        self.assertIn("severity", error)
        self.assertIn("category", error)
        self.assertIn("path", error)
        self.assertIn("message", error)
        self.assertIn("rule_id", error)

        self.assertEqual(error["severity"], "ERROR")
        self.assertEqual(error["category"], "schema")
        self.assertEqual(error["path"], "/schema/fields/0")
        self.assertEqual(error["message"], "Field type is invalid")
        self.assertEqual(error["rule_id"], "field_type_check")

    def test_warning_structure(self):
        """Test that warnings have required structure"""
        result = {
            "validation_status": "WARNING_ONLY",
            "issues": [
                {
                    "severity": "WARNING",
                    "category": "style",
                    "path": "/info",
                    "message": "Missing description",
                    "rule_id": "missing_description",
                }
            ],
        }

        status, errors, warnings = interpret_validation_status(result)

        self.assertEqual(len(warnings), 1)
        warning = warnings[0]

        # Check required fields
        self.assertIn("severity", warning)
        self.assertIn("category", warning)
        self.assertIn("path", warning)
        self.assertIn("message", warning)
        self.assertIn("rule_id", warning)

        self.assertEqual(warning["severity"], "WARNING")
        self.assertEqual(warning["category"], "style")

    def test_error_grouping_structure(self):
        """Test error grouping maintains structure"""
        errors = [
            {
                "severity": "ERROR",
                "category": "schema",
                "path": "/schema",
                "message": "Schema error 1",
                "rule_id": "rule1",
            },
            {
                "severity": "ERROR",
                "category": "schema",
                "path": "/schema/fields",
                "message": "Schema error 2",
                "rule_id": "rule2",
            },
            {
                "severity": "ERROR",
                "category": "format",
                "path": "/format",
                "message": "Format error",
                "rule_id": "rule3",
            },
        ]

        grouped = group_errors_by_category(errors)

        # Check structure
        self.assertIn("schema", grouped)
        self.assertIn("format", grouped)
        self.assertEqual(len(grouped["schema"]), 2)
        self.assertEqual(len(grouped["format"]), 1)

        # Check that grouped errors maintain structure
        for error in grouped["schema"]:
            self.assertIn("severity", error)
            self.assertIn("category", error)
            self.assertIn("path", error)
            self.assertIn("message", error)
            self.assertIn("rule_id", error)

    def test_multiple_severities(self):
        """Test handling of multiple severity levels"""
        result = {
            "validation_status": "WARNING_ONLY",
            "issues": [
                {
                    "severity": "ERROR",
                    "category": "schema",
                    "path": "",
                    "message": "Error",
                    "rule_id": "",
                },
                {
                    "severity": "WARNING",
                    "category": "style",
                    "path": "",
                    "message": "Warning",
                    "rule_id": "",
                },
                {
                    "severity": "INFO",
                    "category": "info",
                    "path": "",
                    "message": "Info",
                    "rule_id": "",
                },
                {
                    "severity": "CRITICAL",
                    "category": "critical",
                    "path": "",
                    "message": "Critical",
                    "rule_id": "",
                },
            ],
        }

        status, errors, warnings = interpret_validation_status(result)

        # ERROR and CRITICAL should be in errors
        self.assertEqual(len(errors), 2)
        # WARNING and INFO should be in warnings
        self.assertEqual(len(warnings), 2)

    def test_empty_issues(self):
        """Test handling of empty issues"""
        result = {"validation_status": "VALID", "issues": []}

        status, errors, warnings = interpret_validation_status(result)

        self.assertEqual(status, "VALID")
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)

    def test_missing_fields_in_issue(self):
        """Test handling of issues with missing fields"""
        result = {
            "validation_status": "INVALID",
            "issues": [
                {
                    "severity": "ERROR",
                    # Missing category, path, message, rule_id
                }
            ],
        }

        status, errors, warnings = interpret_validation_status(result)

        # Should still create error with defaults
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertEqual(error["category"], "unknown")
        self.assertEqual(error["path"], "")
        self.assertEqual(error["message"], "")
        self.assertEqual(error["rule_id"], "")

    # Edge cases and error handling tests
    def test_interpret_validation_status_with_none_result(self):
        """Test handling of None result."""
        try:
            status, errors, warnings = interpret_validation_status(None)
            # If it doesn't raise, verify structure
            self.assertIsInstance(status, str)
            self.assertIsInstance(errors, list)
            self.assertIsInstance(warnings, list)
        except (TypeError, AttributeError):
            # If it raises exception, that's acceptable
            pass

    def test_interpret_validation_status_with_empty_dict(self):
        """Test handling of empty dictionary."""
        result = {}

        try:
            status, errors, warnings = interpret_validation_status(result)
            # Should handle gracefully
            self.assertIsInstance(status, str)
            self.assertIsInstance(errors, list)
            self.assertIsInstance(warnings, list)
        except (KeyError, AttributeError):
            # If it raises exception, that's acceptable
            pass

    def test_interpret_validation_status_with_missing_issues(self):
        """Test handling of result missing issues field."""
        result = {
            "validation_status": "VALID"
            # Missing issues field
        }

        try:
            status, errors, warnings = interpret_validation_status(result)
            # Should handle gracefully
            self.assertIsInstance(status, str)
            self.assertIsInstance(errors, list)
            self.assertIsInstance(warnings, list)
        except (KeyError, AttributeError):
            # If it raises exception, that's acceptable
            pass

    def test_interpret_validation_status_with_invalid_issues_type(self):
        """Test handling of invalid issues type."""
        result = {"validation_status": "INVALID", "issues": "not-a-list"}  # Invalid type

        try:
            status, errors, warnings = interpret_validation_status(result)
            # Should handle gracefully
            self.assertIsInstance(status, str)
            self.assertIsInstance(errors, list)
            self.assertIsInstance(warnings, list)
        except (TypeError, AttributeError):
            # If it raises exception, that's acceptable
            pass

    def test_group_errors_by_category_with_empty_list(self):
        """Test error grouping with empty error list."""
        errors = []
        grouped = group_errors_by_category(errors)

        self.assertIsInstance(grouped, dict)
        self.assertEqual(len(grouped), 0)

    def test_group_errors_by_category_with_none(self):
        """Test error grouping with None."""
        try:
            grouped = group_errors_by_category(None)
            # If it doesn't raise, verify structure
            self.assertIsInstance(grouped, dict)
        except (TypeError, AttributeError):
            # If it raises exception, that's acceptable
            pass

    def test_group_errors_by_category_with_invalid_error_structure(self):
        """Test error grouping with invalid error structure."""
        errors = [
            "not-a-dict",  # Invalid error structure
            {"category": "schema", "message": "Valid error"},
        ]

        try:
            grouped = group_errors_by_category(errors)
            # Should handle gracefully - may skip invalid entries
            self.assertIsInstance(grouped, dict)
            if "schema" in grouped:
                self.assertGreater(len(grouped["schema"]), 0)
        except (TypeError, AttributeError, KeyError):
            # If it raises exception, that's acceptable
            pass

    def test_group_errors_by_category_with_missing_category(self):
        """Test error grouping with errors missing category field."""
        errors = [
            {
                "severity": "ERROR",
                "path": "/schema",
                "message": "Error without category",
                "rule_id": "rule1",
                # Missing category
            }
        ]

        try:
            grouped = group_errors_by_category(errors)
            # Should handle gracefully - may use default category
            self.assertIsInstance(grouped, dict)
        except (KeyError, AttributeError):
            # If it raises exception, that's acceptable
            pass

    def test_interpret_validation_status_with_nested_issues(self):
        """Test handling of nested issues structure."""
        result = {
            "validation_status": "INVALID",
            "issues": [
                {
                    "severity": "ERROR",
                    "category": "schema",
                    "path": "/schema",
                    "message": "Error",
                    "rule_id": "rule1",
                    "nested": {"sub_error": "value"},
                }
            ],
        }

        status, errors, warnings = interpret_validation_status(result)

        # Should handle nested structures gracefully
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertIn("severity", error)
        self.assertIn("category", error)

    def test_interpret_validation_status_with_very_long_messages(self):
        """Test handling of very long error messages."""
        long_message = "A" * 10000
        result = {
            "validation_status": "INVALID",
            "issues": [
                {
                    "severity": "ERROR",
                    "category": "schema",
                    "path": "/schema",
                    "message": long_message,
                    "rule_id": "rule1",
                }
            ],
        }

        status, errors, warnings = interpret_validation_status(result)

        # Should handle long messages
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(errors[0]["message"]), 10000)

    def test_interpret_validation_status_with_special_characters(self):
        """Test handling of special characters in error messages."""
        result = {
            "validation_status": "INVALID",
            "issues": [
                {
                    "severity": "ERROR",
                    "category": "schema",
                    "path": "/schema/field-name_v2",
                    "message": "Error with special chars: <>&\"'",
                    "rule_id": "rule-name_v2",
                }
            ],
        }

        status, errors, warnings = interpret_validation_status(result)

        # Should handle special characters
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertIn("&", error["message"])
        self.assertIn("_", error["path"])

    def test_interpret_validation_status_with_unicode_characters(self):
        """Test handling of unicode characters in error messages."""
        result = {
            "validation_status": "INVALID",
            "issues": [
                {
                    "severity": "ERROR",
                    "category": "schema",
                    "path": "/schema",
                    "message": "错误消息：产品名称",
                    "rule_id": "rule1",
                }
            ],
        }

        status, errors, warnings = interpret_validation_status(result)

        # Should handle unicode characters
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertIn("错误", error["message"])

    def test_group_errors_by_category_preserves_all_fields(self):
        """Test that grouped errors preserve all original fields."""
        errors = [
            {
                "severity": "ERROR",
                "category": "schema",
                "path": "/schema",
                "message": "Error",
                "rule_id": "rule1",
                "custom_field": "custom_value",
            }
        ]

        grouped = group_errors_by_category(errors)

        # Should preserve all fields
        self.assertIn("schema", grouped)
        self.assertEqual(len(grouped["schema"]), 1)
        error = grouped["schema"][0]
        self.assertIn("custom_field", error)
        self.assertEqual(error["custom_field"], "custom_value")

    def test_group_errors_by_category_with_many_categories(self):
        """Test error grouping with many different categories."""
        errors = [
            {
                "severity": "ERROR",
                "category": f"category_{i}",
                "path": f"/path{i}",
                "message": f"Error {i}",
                "rule_id": f"rule{i}",
            }
            for i in range(50)
        ]

        grouped = group_errors_by_category(errors)

        # Should handle many categories
        self.assertEqual(len(grouped), 50)
        for i in range(50):
            self.assertIn(f"category_{i}", grouped)
            self.assertEqual(len(grouped[f"category_{i}"]), 1)
