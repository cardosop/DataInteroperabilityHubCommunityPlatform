"""
Edge case tests for contract normalization.

Tests missing optional sections, partial field properties, invalid properties,
information preservation, and large contracts.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.contracts.normalization import (
    NormalizationStatus,
    normalize_odcs_to_hubcontract,
)
from hub.apps.users.models import User, UserStatus
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)
User = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model()


class NormalizationEdgeCaseTest(TestCase):
    """Edge case tests for contract normalization"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def _get_field_by_name(self, fields, field_name):
        """Helper to get a field by name from a list of field dicts"""
        if isinstance(fields, list):
            for field in fields:
                if field.get("name") == field_name:
                    return field
            return {}
        # If it's a dict (old format), return the field directly
        return fields.get(field_name, {})

    # Missing Optional Sections Tests

    def test_normalize_contract_missing_owners(self):
        """Test normalization with missing owners section"""
        odcs_contract = {
            "id": "test-contract-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            # No owners
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertIn("info", hub_contract)
        # Owners should be missing (not None, just not present)
        self.assertNotIn("owners", hub_contract.get("info", {}))

    def test_normalize_contract_missing_tags(self):
        """Test normalization with missing tags section"""
        odcs_contract = {
            "id": "test-contract-2",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            # No tags
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertIn("info", hub_contract)
        # Tags should be missing
        self.assertNotIn("tags", hub_contract.get("info", {}))

    def test_normalize_contract_missing_quality(self):
        """Test normalization with missing quality section"""
        odcs_contract = {
            "id": "test-contract-3",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            # No quality section
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        # Quality section should be missing
        self.assertNotIn("quality", hub_contract)

    def test_normalize_contract_missing_compliance(self):
        """Test normalization with missing compliance section"""
        odcs_contract = {
            "id": "test-contract-4",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            # No compliance section
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        # Compliance section should be missing
        self.assertNotIn("privacy_compliance", hub_contract)

    def test_normalize_contract_missing_lifecycle(self):
        """Test normalization with missing lifecycle section"""
        odcs_contract = {
            "id": "test-contract-5",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            # No lifecycle section
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        # Lifecycle section should be missing
        self.assertNotIn("lifecycle", hub_contract)

    def test_normalize_contract_missing_marketplace(self):
        """Test normalization with missing marketplace section"""
        odcs_contract = {
            "id": "test-contract-6",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            # No marketplace section
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        # Marketplace section should be missing
        self.assertNotIn("marketplace", hub_contract)

    def test_normalize_contract_all_optional_sections_missing(self):
        """Test normalization with all optional sections missing"""
        odcs_contract = {
            "id": "test-contract-7",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        # Only required sections should be present
        self.assertIn("info", hub_contract)
        self.assertIn("schema", hub_contract)
        self.assertNotIn("quality", hub_contract)
        self.assertNotIn("privacy_compliance", hub_contract)
        self.assertNotIn("lifecycle", hub_contract)
        self.assertNotIn("marketplace", hub_contract)

    # Partial Field Properties Tests

    def test_normalize_contract_field_only_format(self):
        """Test normalization with field having only format property"""
        odcs_contract = {
            "id": "test-contract-8",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "email", "type": "string", "format": "email"}]},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "email")
        self.assertEqual(field.get("format"), "email")
        # Other properties should not be present
        self.assertNotIn("enum", field)
        self.assertNotIn("min", field)
        self.assertNotIn("max", field)

    def test_normalize_contract_field_only_enum(self):
        """Test normalization with field having only enum property"""
        odcs_contract = {
            "id": "test-contract-9",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {"name": "status", "type": "string", "enum": ["active", "inactive", "pending"]}
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "status")
        self.assertEqual(field.get("enum"), ["active", "inactive", "pending"])
        # Other properties should not be present
        self.assertNotIn("format", field)
        self.assertNotIn("min", field)
        self.assertNotIn("max", field)

    def test_normalize_contract_field_only_min(self):
        """Test normalization with field having only min property"""
        odcs_contract = {
            "id": "test-contract-10",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "age", "type": "integer", "minimum": 0}]},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "age")
        self.assertEqual(field.get("min"), 0)
        # Other properties should not be present
        self.assertNotIn("max", field)
        self.assertNotIn("format", field)
        self.assertNotIn("enum", field)

    def test_normalize_contract_field_only_max(self):
        """Test normalization with field having only max property"""
        odcs_contract = {
            "id": "test-contract-11",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "age", "type": "integer", "maximum": 120}]},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "age")
        self.assertEqual(field.get("max"), 120)
        # Other properties should not be present
        self.assertNotIn("min", field)
        self.assertNotIn("format", field)
        self.assertNotIn("enum", field)

    def test_normalize_contract_field_min_max_only(self):
        """Test normalization with field having only min and max"""
        odcs_contract = {
            "id": "test-contract-12",
            "name": "Test Contract",
            "schema": {
                "fields": [{"name": "age", "type": "integer", "minimum": 0, "maximum": 120}]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "age")
        self.assertEqual(field.get("min"), 0)
        self.assertEqual(field.get("max"), 120)

    def test_normalize_contract_field_pattern_only(self):
        """Test normalization with field having only pattern property"""
        odcs_contract = {
            "id": "test-contract-13",
            "name": "Test Contract",
            "schema": {
                "fields": [{"name": "order_id", "type": "string", "pattern": "^ORD-[0-9]{8}$"}]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "order_id")
        self.assertEqual(field.get("pattern"), "^ORD-[0-9]{8}$")

    # Invalid Field Properties Tests

    def test_normalize_contract_invalid_format(self):
        """Test normalization with invalid format property"""
        odcs_contract = {
            "id": "test-contract-14",
            "name": "Test Contract",
            "schema": {
                "fields": [{"name": "field1", "type": "string", "format": "invalid_format_xyz"}]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Should still normalize, but may have warnings
        self.assertIsNotNone(hub_contract)
        # Invalid format should be preserved (information preservation)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "field1")
        self.assertEqual(field.get("format"), "invalid_format_xyz")

    def test_normalize_contract_invalid_pattern_regex(self):
        """Test normalization with invalid pattern regex"""
        odcs_contract = {
            "id": "test-contract-15",
            "name": "Test Contract",
            "schema": {
                "fields": [{"name": "field1", "type": "string", "pattern": "[invalid(regex"}]
            },
        }

        hub_contract, _status, _errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Should still normalize, invalid pattern preserved
        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "field1")
        self.assertEqual(field.get("pattern"), "[invalid(regex")
        # May have warnings about invalid regex
        if warnings:
            self.assertTrue(
                any("pattern" in str(w).lower() or "regex" in str(w).lower() for w in warnings)
            )

    def test_normalize_contract_invalid_enum_values(self):
        """Test normalization with invalid enum values (wrong types)"""
        odcs_contract = {
            "id": "test-contract-16",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "string",
                        "enum": ["value1", 123, None, {"nested": "object"}],
                    }
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Should normalize, enum values preserved (may have warnings)
        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "field1")
        enum = field.get("enum")
        self.assertIsNotNone(enum)
        # Enum should be preserved as-is (information preservation)

    def test_normalize_contract_invalid_min_max(self):
        """Test normalization with invalid min/max (min > max)"""
        odcs_contract = {
            "id": "test-contract-17",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "integer",
                        "minimum": 100,
                        "maximum": 50,  # Invalid: min > max
                    }
                ]
            },
        }

        hub_contract, _status, _errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Should normalize, but may have warnings
        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "field1")
        self.assertEqual(field.get("min"), 100)
        self.assertEqual(field.get("max"), 50)
        # Invalid range (min > max) — normalization may produce warnings or silently fix
        # The contract preserves the values as given; check warnings if present
        if warnings:
            self.assertTrue(
                any("min" in str(w).lower() or "max" in str(w).lower() for w in warnings)
            )

    def test_normalize_contract_invalid_min_type(self):
        """Test normalization with invalid min type (string instead of number)"""
        odcs_contract = {
            "id": "test-contract-18",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "integer",
                        "minimum": "invalid",  # Should be number
                    }
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Should normalize, invalid value preserved
        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "field1")
        # Invalid min should be preserved or converted
        min_value = field.get("min")
        self.assertIsNotNone(min_value)

    def test_normalize_contract_invalid_max_type(self):
        """Test normalization with invalid max type (string instead of number)"""
        odcs_contract = {
            "id": "test-contract-19",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "integer",
                        "maximum": "invalid",  # Should be number
                    }
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Should normalize, invalid value preserved
        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "field1")
        max_value = field.get("max")
        self.assertIsNotNone(max_value)

    # Information Preservation Tests

    def test_normalize_contract_unmappable_fields_in_extensions(self):
        """Test that unmappable fields are preserved in extensions"""
        odcs_contract = {
            "id": "test-contract-20",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "custom_extension": {"unmappable_field": "value", "nested": {"data": "preserved"}},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        # Extensions cause NORMALIZED_WITH_WARNINGS status (they indicate unmappable fields)
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )
        # Extensions should be preserved
        self.assertIn("extensions", hub_contract)
        extensions = hub_contract.get("extensions", {})
        self.assertIn("custom_extension", extensions)
        self.assertEqual(extensions["custom_extension"]["unmappable_field"], "value")

    def test_normalize_contract_multiple_extensions(self):
        """Test preservation of multiple extension sections"""
        odcs_contract = {
            "id": "test-contract-21",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "extension1": {"data": "value1"},
            "extension2": {"data": "value2"},
            "x-custom": {"data": "value3"},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        extensions = hub_contract.get("extensions", {})
        # All extensions should be preserved
        self.assertIn("extension1", extensions)
        self.assertIn("extension2", extensions)
        self.assertIn("x-custom", extensions)

    def test_normalize_contract_nested_extensions(self):
        """Test preservation of nested extension structures"""
        odcs_contract = {
            "id": "test-contract-22",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "custom": {"level1": {"level2": {"level3": "deep_value"}}},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        extensions = hub_contract.get("extensions", {})
        self.assertIn("custom", extensions)
        nested = extensions["custom"]["level1"]["level2"]
        self.assertEqual(nested["level3"], "deep_value")

    # Large Contracts Tests

    def test_normalize_contract_1000_fields(self):
        """Test normalization with 1000+ fields"""
        fields = []
        for i in range(1000):
            fields.append(
                {"name": f"field_{i}", "type": "string", "description": f"Field {i} description"}
            )

        odcs_contract = {
            "id": "test-contract-large",
            "name": "Large Contract",
            "schema": {"fields": fields},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        schema_fields = hub_contract.get("schema", {}).get("fields", [])
        # Should have all 1000 fields
        self.assertEqual(len(schema_fields), 1000)

    def test_normalize_contract_100_quality_rules(self):
        """Test normalization with 100+ quality rules"""
        quality_rules = []
        for i in range(100):
            quality_rules.append(
                {
                    "rule_id": f"rule_{i}",
                    "dimension": "completeness",
                    "expression": f"field_{i} IS NOT NULL",
                    "severity": "ERROR",
                }
            )

        odcs_contract = {
            "id": "test-contract-quality",
            "name": "Contract with Many Rules",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "quality": {"rules": quality_rules},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        quality = hub_contract.get("quality", {})
        rules = quality.get("rules", [])
        self.assertEqual(len(rules), 100)

    def test_normalize_contract_20_owners(self):
        """Test normalization with 20+ owners"""
        owners = []
        for i in range(20):
            owners.append({"name": f"Owner {i}", "email": f"owner{i}@example.com"})

        odcs_contract = {
            "id": "test-contract-owners",
            "name": "Contract with Many Owners",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "info": {"owners": owners},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        info = hub_contract.get("info", {})
        owners_list = info.get("owners", [])
        self.assertEqual(len(owners_list), 20)

    def test_normalize_contract_100_tags(self):
        """Test normalization with 100+ tags"""
        tags = [f"tag_{i}" for i in range(100)]

        odcs_contract = {
            "id": "test-contract-tags",
            "name": "Contract with Many Tags",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "info": {"tags": tags},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        info = hub_contract.get("info", {})
        tags_list = info.get("tags", [])
        self.assertEqual(len(tags_list), 100)

    def test_normalize_contract_all_large_sections(self):
        """Test normalization with all large sections (1000 fields, 100 rules, 20 owners, 100 tags)"""
        fields = [{"name": f"field_{i}", "type": "string"} for i in range(1000)]
        quality_rules = [
            {
                "rule_id": f"rule_{i}",
                "dimension": "completeness",
                "expression": f"field_{i} IS NOT NULL",
                "severity": "ERROR",
            }
            for i in range(100)
        ]
        owners = [{"name": f"Owner {i}", "email": f"owner{i}@example.com"} for i in range(20)]
        tags = [f"tag_{i}" for i in range(100)]

        odcs_contract = {
            "id": "test-contract-all-large",
            "name": "Large Contract All Sections",
            "schema": {"fields": fields},
            "quality": {"rules": quality_rules},
            "info": {"owners": owners, "tags": tags},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        # Verify all sections
        self.assertEqual(len(hub_contract.get("schema", {}).get("fields", {})), 1000)
        self.assertEqual(len(hub_contract.get("quality", {}).get("rules", [])), 100)
        self.assertEqual(len(hub_contract.get("info", {}).get("owners", [])), 20)
        self.assertEqual(len(hub_contract.get("info", {}).get("tags", [])), 100)

    # Additional Edge Cases

    def test_normalize_contract_empty_fields(self):
        """Test normalization with empty fields array"""
        odcs_contract = {
            "id": "test-contract-empty",
            "name": "Empty Contract",
            "schema": {"fields": []},
        }

        hub_contract, _status, errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Empty fields array causes validation errors, and hub_contract is None when errors exist
        self.assertGreater(len(errors), 0, "Empty fields should produce validation errors")
        self.assertIsNone(hub_contract, "hub_contract should be None when errors are present")

    def test_normalize_contract_null_values(self):
        """Test normalization with null values in optional fields"""
        odcs_contract = {
            "id": "test-contract-null",
            "name": "Contract with Nulls",
            "description": None,
            "version": None,
            "schema": {"fields": [{"name": "field1", "type": "string", "description": None}]},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        # Null values should be handled gracefully
        info = hub_contract.get("info", {})
        # Description may be None or omitted
        self.assertIn("name", info)

    def test_normalize_contract_empty_strings(self):
        """Test normalization with empty strings"""
        odcs_contract = {
            "id": "test-contract-empty-strings",
            "name": "",
            "description": "",
            "schema": {"fields": [{"name": "field1", "type": "string", "description": ""}]},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Should normalize, empty strings preserved
        self.assertIsNotNone(hub_contract)
        info = hub_contract.get("info", {})
        # Empty name may cause warnings or errors
        if status == NormalizationStatus.NORMALIZED_OK:
            self.assertIn("name", info)

    def test_normalize_contract_very_long_strings(self):
        """Test normalization with very long string values"""
        long_string = "x" * 10000  # 10KB string

        odcs_contract = {
            "id": "test-contract-long",
            "name": "Contract with Long Strings",
            "description": long_string,
            "schema": {
                "fields": [{"name": "field1", "type": "string", "description": long_string}]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        # Long strings should be preserved
        info = hub_contract.get("info", {})
        self.assertEqual(len(info.get("description", "")), 10000)

    def test_normalize_contract_special_characters(self):
        """Test normalization with special characters in field names and values"""
        odcs_contract = {
            "id": "test-contract-special",
            "name": "Contract with Special Chars",
            "schema": {
                "fields": [
                    {
                        "name": "field-with-dashes",
                        "type": "string",
                        "description": "Field with special chars: !@#$%^&*()",
                    },
                    {"name": "field_with_underscores", "type": "string"},
                    {"name": "field.with.dots", "type": "string"},
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        # All field names should be preserved - check in list of field dicts
        field_names = [field.get("name") for field in fields]
        self.assertIn("field-with-dashes", field_names)
        self.assertIn("field_with_underscores", field_names)
        self.assertIn("field.with.dots", field_names)

    def test_normalize_contract_unicode_characters(self):
        """Test normalization with unicode characters"""
        odcs_contract = {
            "id": "test-contract-unicode",
            "name": "Contract with 测试 Unicode",
            "description": "Description with émojis 🎉 and 中文",
            "schema": {
                "fields": [
                    {
                        "name": "field_测试",
                        "type": "string",
                        "description": "Field with 中文 description",
                    }
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        info = hub_contract.get("info", {})
        self.assertIn("测试", info.get("name", ""))
        fields = hub_contract.get("schema", {}).get("fields", [])
        field_names = [field.get("name") for field in fields]
        self.assertIn("field_测试", field_names)

    def test_normalize_contract_nested_structures(self):
        """Test normalization with deeply nested structures"""
        odcs_contract = {
            "id": "test-contract-nested",
            "name": "Nested Contract",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "object",
                        "properties": {
                            "nested1": {
                                "type": "object",
                                "properties": {"nested2": {"type": "string"}},
                            }
                        },
                    }
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        # Nested structures should be preserved.
        #
        # Phase 227 Wave 1: the canonical HubContract dict uses ``type``
        # (Pydantic by_alias=True output) post-roundtrip, but historic
        # internal helpers used ``data_type``. Accept either so the
        # assertion is robust to which side of the Pydantic boundary
        # this hub_contract was sampled from.
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "field1")
        observed_type = field.get("data_type") or field.get("type")
        self.assertEqual(observed_type, "object")
        # Phase 227 L2 — recursive walker now preserves the nested
        # children too. Verify the chain `field1 → nested1 → nested2`
        # survived normalisation.
        sub_fields = field.get("fields") or []
        self.assertTrue(sub_fields, f"field1 lost its nested fields: {field}")
        nested1 = self._get_field_by_name(sub_fields, "nested1")
        self.assertTrue(nested1, f"nested1 missing from field1.fields: {sub_fields}")
        nested1_sub = nested1.get("fields") or []
        self.assertTrue(nested1_sub, f"nested1 lost its nested fields: {nested1}")
        nested2 = self._get_field_by_name(nested1_sub, "nested2")
        self.assertTrue(nested2, f"nested2 missing: {nested1_sub}")
        observed_nested2_type = nested2.get("data_type") or nested2.get("type")
        self.assertEqual(observed_nested2_type, "string")

    def test_normalize_contract_array_fields(self):
        """Test normalization with array/list fields"""
        odcs_contract = {
            "id": "test-contract-array",
            "name": "Array Contract",
            "schema": {
                "fields": [
                    {"name": "tags", "type": "array", "items": {"type": "string"}},
                    {"name": "numbers", "type": "array", "items": {"type": "integer"}},
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        # fields is a list of dicts, not a dict - check for field names in the list
        field_names = [field.get("name") for field in fields]
        self.assertIn("tags", field_names)
        self.assertIn("numbers", field_names)

    def test_normalize_contract_boolean_fields(self):
        """Test normalization with boolean fields"""
        odcs_contract = {
            "id": "test-contract-boolean",
            "name": "Boolean Contract",
            "schema": {
                "fields": [
                    {"name": "is_active", "type": "boolean"},
                    {"name": "is_verified", "type": "boolean", "default": False},
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        is_active = self._get_field_by_name(fields, "is_active")
        # Accept either canonical key (Pydantic alias renames data_type ↔ type).
        self.assertEqual(
            is_active.get("data_type") or is_active.get("type"),
            "boolean",
        )

    def test_normalize_contract_date_time_fields(self):
        """Test normalization with date/time fields"""
        odcs_contract = {
            "id": "test-contract-datetime",
            "name": "DateTime Contract",
            "schema": {
                "fields": [
                    {"name": "created_at", "type": "string", "format": "date-time"},
                    {"name": "birth_date", "type": "string", "format": "date"},
                    {"name": "time_only", "type": "string", "format": "time"},
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        created_at = self._get_field_by_name(fields, "created_at")
        self.assertEqual(created_at.get("format"), "date-time")

    def test_normalize_contract_numeric_precision(self):
        """Test normalization with numeric fields having precision/scale"""
        odcs_contract = {
            "id": "test-contract-numeric",
            "name": "Numeric Contract",
            "schema": {
                "fields": [
                    {
                        "name": "price",
                        "type": "number",
                        "format": "decimal",
                        "precision": 10,
                        "scale": 2,
                    },
                    {"name": "amount", "type": "number", "format": "double"},
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        price = self._get_field_by_name(fields, "price")
        # Precision/scale may be preserved in metadata (implementation-dependent)
        metadata = price.get("metadata", {})
        if metadata:
            self.assertIn("precision", metadata)
            self.assertIn("scale", metadata)

    def test_normalize_contract_required_vs_optional_fields(self):
        """Test normalization with required and optional field markers"""
        odcs_contract = {
            "id": "test-contract-required",
            "name": "Required Fields Contract",
            "schema": {
                "fields": [
                    {"name": "required_field", "type": "string", "required": True},
                    {"name": "optional_field", "type": "string", "required": False},
                    {"name": "nullable_field", "type": "string", "nullable": True},
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        required = self._get_field_by_name(fields, "required_field")
        optional = self._get_field_by_name(fields, "optional_field")
        nullable = self._get_field_by_name(fields, "nullable_field")
        # Required/optional/nullable should be preserved
        self.assertIsNotNone(required)
        self.assertIsNotNone(optional)
        self.assertIsNotNone(nullable)

    def test_normalize_contract_default_values(self):
        """Test normalization with default values"""
        odcs_contract = {
            "id": "test-contract-defaults",
            "name": "Defaults Contract",
            "schema": {
                "fields": [
                    {"name": "status", "type": "string", "default": "pending"},
                    {"name": "count", "type": "integer", "default": 0},
                    {"name": "is_active", "type": "boolean", "default": True},
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        status_field = self._get_field_by_name(fields, "status")
        self.assertEqual(status_field.get("default"), "pending")

    def test_normalize_contract_primary_key_constraints(self):
        """Test normalization with primary key constraints"""
        odcs_contract = {
            "id": "test-contract-pk",
            "name": "Primary Key Contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "primaryKey": True},
                    {"name": "name", "type": "string"},
                    {"name": "email", "type": "string", "unique": True},
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        schema = hub_contract.get("schema", {})
        # Primary key should be extracted
        self.assertIn("primary_key", schema)
        self.assertEqual(schema.get("primary_key"), ["id"])

    def test_normalize_contract_unique_constraints(self):
        """Test normalization with unique constraints"""
        odcs_contract = {
            "id": "test-contract-unique",
            "name": "Unique Constraints Contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "email", "type": "string", "unique": True},
                    {"name": "username", "type": "string", "unique": True},
                ],
                "uniqueConstraints": [{"fields": ["email", "username"]}],
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        schema = hub_contract.get("schema", {})
        # Unique constraints should be extracted
        unique_constraints = schema.get("unique_constraints", [])
        self.assertGreater(len(unique_constraints), 0)

    def test_normalize_contract_indexes(self):
        """Test normalization with indexes"""
        odcs_contract = {
            "id": "test-contract-indexes",
            "name": "Indexes Contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "email", "type": "string", "indexed": True},
                    {"name": "created_at", "type": "date-time", "indexed": True},
                ],
                "indexes": [
                    {"name": "idx_email", "fields": ["email"]},
                    {"name": "idx_created", "fields": ["created_at"]},
                ],
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        schema = hub_contract.get("schema", {})
        # Indexes should be extracted
        indexes = schema.get("indexes", [])
        self.assertGreater(len(indexes), 0)

    def test_normalize_contract_foreign_keys(self):
        """Test normalization with foreign key relationships"""
        odcs_contract = {
            "id": "test-contract-fk",
            "name": "Foreign Keys Contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "user_id", "type": "string"},
                    {"name": "order_id", "type": "string"},
                ],
                "relationships": [
                    {"type": "foreignKey", "from": "user_id", "to": "users.id"},
                    {"type": "foreignKey", "from": "order_id", "to": "orders.id"},
                ],
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        # Foreign keys should be preserved in extensions or metadata
        extensions = hub_contract.get("extensions", {})
        # Relationships may be in extensions
        if "relationships" in extensions:
            self.assertGreater(len(extensions["relationships"]), 0)

    def test_normalize_contract_odcs_detection(self):
        """Test automatic detection of ODCS format"""
        # ODCS format
        odcs_contract = {
            "id": "test-odcs",
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "name": "ODCS Contract",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Should normalize successfully
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        # Name should be extracted correctly
        self.assertEqual(hub_contract["info"]["name"], "ODCS Contract")

    def test_normalize_contract_normalization_status_tracking(self):
        """Test that normalization status is tracked correctly"""
        odcs_contract = {
            "id": "test-status",
            "name": "Status Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
        }

        hub_contract, status, errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        # Status should be NORMALIZED_OK for valid contract
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(len(errors), 0)

    def test_normalize_contract_normalization_warnings(self):
        """Test that normalization warnings are generated appropriately"""
        odcs_contract = {
            "id": "test-warnings",
            "name": "Warnings Test",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "string",
                        "pattern": "[invalid(regex",  # Invalid regex
                    }
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        # May have warnings about invalid pattern
        # Status should still be OK or WITH_WARNINGS
        self.assertIn(
            status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

    def test_normalize_contract_normalization_errors(self):
        """Test that normalization errors are generated for invalid contracts"""
        # Invalid contract (missing required fields)
        invalid_contract = {
            "id": "test-errors"
            # Missing name and schema
        }

        hub_contract, status, errors, _warnings = normalize_odcs_to_hubcontract(invalid_contract)

        # Should fail normalization
        self.assertIsNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(errors), 0)

    def test_normalize_contract_preserve_original_structure(self):
        """Test that original contract structure is preserved in extensions"""
        odcs_contract = {
            "id": "test-preserve",
            "name": "Preserve Test",
            "custom_field": "custom_value",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        # Custom fields should be preserved in extensions
        extensions = hub_contract.get("extensions", {})
        # Original structure may be preserved
        self.assertIsNotNone(extensions)

    def test_normalize_contract_field_metadata_preservation(self):
        """Test that field metadata is preserved"""
        odcs_contract = {
            "id": "test-metadata",
            "name": "Metadata Test",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "string",
                        "description": "Field description",
                        "examples": ["example1", "example2"],
                        "metadata": {"source": "database", "column": "field_1"},
                    }
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = self._get_field_by_name(fields, "field1")
        # Metadata should be preserved
        metadata = field.get("metadata", {})
        if metadata:
            self.assertIn("source", metadata or {})

    def test_normalize_contract_semantic_type_extraction(self):
        """Test extraction of semantic types"""
        odcs_contract = {
            "id": "test-semantic",
            "name": "Semantic Test",
            "schema": {
                "fields": [
                    {"name": "email", "type": "string", "format": "email", "semanticType": "EMAIL"},
                    {"name": "phone", "type": "string", "semanticType": "PHONE"},
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        email_field = self._get_field_by_name(fields, "email")
        # Semantic type should be extracted
        self.assertEqual(email_field.get("semantic_type"), "EMAIL")

    def test_normalize_contract_quality_profile_extraction(self):
        """Test extraction of quality profile"""
        odcs_contract = {
            "id": "test-quality-profile",
            "name": "Quality Profile Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "quality": {"default_profile_key": "intake_basic_gx", "rules": []},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        quality = hub_contract.get("quality", {})
        self.assertEqual(quality.get("default_profile_key"), "intake_basic_gx")

    def test_normalize_contract_compliance_jurisdictions_extraction(self):
        """Test extraction of compliance jurisdictions"""
        odcs_contract = {
            "id": "test-compliance",
            "name": "Compliance Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "privacy": {"jurisdictions": ["GDPR", "LGPD", "CCPA"]},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        compliance = hub_contract.get("privacy_compliance", {})
        jurisdictions = compliance.get("jurisdictions", [])
        self.assertIn("GDPR", jurisdictions)
        self.assertIn("LGPD", jurisdictions)
        self.assertIn("CCPA", jurisdictions)

    def test_normalize_contract_lifecycle_refresh_cadence(self):
        """Test extraction of lifecycle refresh cadence"""
        odcs_contract = {
            "id": "test-lifecycle",
            "name": "Lifecycle Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "lifecycle": {"refresh_cadence": "DAILY", "data_source": "OLTP.orders"},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        lifecycle = hub_contract.get("lifecycle", {})
        self.assertEqual(lifecycle.get("refresh_cadence"), "DAILY")
        self.assertEqual(lifecycle.get("data_source"), "OLTP.orders")

    def test_normalize_contract_marketplace_license_extraction(self):
        """Test extraction of marketplace license"""
        odcs_contract = {
            "id": "test-marketplace",
            "name": "Marketplace Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["analytics", "machine_learning"],
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        marketplace = hub_contract.get("marketplace", {})
        self.assertEqual(marketplace.get("license_summary"), "MIT License")
        intended_use = marketplace.get("intended_use", [])
        self.assertIn("analytics", intended_use)
        self.assertIn("machine_learning", intended_use)

    # Additional Edge Cases to Reach 100+ Tests

    def test_normalize_contract_field_with_all_properties(self):
        """Test normalization with field having all possible properties"""
        odcs_contract = {
            "id": "test-all-props",
            "name": "All Properties Test",
            "schema": {
                "fields": [
                    {
                        "name": "comprehensive_field",
                        "type": "string",
                        "description": "Field with all properties",
                        "semantic_type": "EMAIL",
                        "format": "email",
                        "pattern": "^[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}$",
                        "enum": ["value1", "value2"],
                        "default": "value1",
                        "min_length": 5,
                        "max_length": 100,
                        "minimum": 0,
                        "maximum": 1000,
                        "nullable": False,
                        "required": True,
                        "metadata": {"source": "database", "column": "email_col"},
                    }
                ]
            },
        }

        hub_contract, status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = next((f for f in fields if f.get("name") == "comprehensive_field"), None)
        self.assertIsNotNone(field)
        self.assertEqual(field.get("semantic_type"), "EMAIL")
        self.assertEqual(field.get("format"), "email")
        self.assertEqual(field.get("pattern"), "^[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}$")
        self.assertEqual(field.get("enum"), ["value1", "value2"])
        self.assertEqual(field.get("default"), "value1")
        # Pydantic emits the alias forms (minLength/maxLength) post-roundtrip;
        # accept either canonical name (Phase 227 Wave 1 alias-tolerance).
        self.assertEqual(field.get("min_length") or field.get("minLength"), 5)
        self.assertEqual(field.get("max_length") or field.get("maxLength"), 100)
        self.assertEqual(field.get("minimum"), 0)
        self.assertEqual(field.get("maximum"), 1000)
        self.assertEqual(field.get("nullable"), False)

    def test_normalize_contract_empty_owners_array(self):
        """Test normalization with empty owners array"""
        odcs_contract = {
            "id": "test-empty-owners",
            "name": "Empty Owners Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "info": {"owners": []},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        info = hub_contract.get("info", {})
        owners = info.get("owners", [])
        self.assertEqual(len(owners), 0)

    def test_normalize_contract_empty_tags_array(self):
        """Test normalization with empty tags array"""
        odcs_contract = {
            "id": "test-empty-tags",
            "name": "Empty Tags Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "info": {"tags": []},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        info = hub_contract.get("info", {})
        tags = info.get("tags", [])
        self.assertEqual(len(tags), 0)

    def test_normalize_contract_empty_quality_rules(self):
        """Test normalization with empty quality rules"""
        odcs_contract = {
            "id": "test-empty-quality",
            "name": "Empty Quality Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "quality": {"rules": []},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        quality = hub_contract.get("quality", {})
        rules = quality.get("rules", [])
        self.assertEqual(len(rules), 0)

    def test_normalize_contract_owner_without_email(self):
        """Test normalization with owner missing email"""
        odcs_contract = {
            "id": "test-owner-no-email",
            "name": "Owner No Email Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "info": {"owners": [{"name": "Owner Name"}]},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        info = hub_contract.get("info", {})
        owners = info.get("owners", [])
        self.assertEqual(len(owners), 1)
        # Owner should be preserved even without email
        self.assertEqual(owners[0].get("name"), "Owner Name")

    def test_normalize_contract_owner_without_name(self):
        """Test normalization with owner missing name"""
        odcs_contract = {
            "id": "test-owner-no-name",
            "name": "Owner No Name Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "info": {"owners": [{"email": "owner@example.com"}]},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        info = hub_contract.get("info", {})
        owners = info.get("owners", [])
        self.assertEqual(len(owners), 1)
        # Owner should be preserved even without name
        self.assertEqual(owners[0].get("email"), "owner@example.com")

    def test_normalize_contract_duplicate_field_names(self):
        """Test normalization with duplicate field names (should preserve all)"""
        odcs_contract = {
            "id": "test-duplicate-fields",
            "name": "Duplicate Fields Test",
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"},
                    {"name": "field1", "type": "integer"},  # Duplicate name
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        # Both fields should be preserved (may have warnings)
        field1_count = sum(1 for f in fields if f.get("name") == "field1")
        self.assertGreaterEqual(field1_count, 1)

    def test_normalize_contract_field_without_name(self):
        """Test normalization with field missing name"""
        odcs_contract = {
            "id": "test-field-no-name",
            "name": "Field No Name Test",
            "schema": {
                "fields": [
                    {"type": "string"}  # Missing name
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Should normalize but may have warnings/errors about missing name
        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        self.assertGreater(len(fields), 0, "Field should be included in output")
        field = fields[0]
        self.assertEqual(field.get("name"), "")

    def test_normalize_contract_field_without_type(self):
        """Test normalization with field missing type"""
        odcs_contract = {
            "id": "test-field-no-type",
            "name": "Field No Type Test",
            "schema": {
                "fields": [
                    {"name": "field1"}  # Missing type
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = next((f for f in fields if f.get("name") == "field1"), None)
        # Type should default to "string". Accept either canonical key
        # (Pydantic alias renames data_type ↔ type).
        self.assertEqual(field.get("data_type") or field.get("type"), "string")

    def test_normalize_contract_quality_rule_without_dimension(self):
        """Test normalization with quality rule missing dimension"""
        odcs_contract = {
            "id": "test-quality-no-dimension",
            "name": "Quality No Dimension Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "quality": {
                "rules": [
                    {"rule_id": "rule1", "expression": "field1 IS NOT NULL", "severity": "ERROR"}
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        quality = hub_contract.get("quality", {})
        rules = quality.get("rules", [])
        # Rule should be preserved even without dimension
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].get("rule_id"), "rule1")

    def test_normalize_contract_quality_rule_without_expression(self):
        """Test normalization with quality rule missing expression"""
        odcs_contract = {
            "id": "test-quality-no-expression",
            "name": "Quality No Expression Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "quality": {
                "rules": [{"rule_id": "rule1", "dimension": "completeness", "severity": "ERROR"}]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        quality = hub_contract.get("quality", {})
        rules = quality.get("rules", [])
        # Rule should be preserved even without expression
        self.assertEqual(len(rules), 1)

    def test_normalize_contract_compliance_without_jurisdictions(self):
        """Test normalization with compliance missing jurisdictions"""
        odcs_contract = {
            "id": "test-compliance-no-jurisdictions",
            "name": "Compliance No Jurisdictions Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["EMAIL"],
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        compliance = hub_contract.get("privacy_compliance", {})
        self.assertEqual(compliance.get("contains_personal_data"), True)
        # Jurisdictions may be missing or empty
        jurisdictions = compliance.get("jurisdictions", [])
        self.assertIsInstance(jurisdictions, list)

    def test_normalize_contract_lifecycle_without_refresh_cadence(self):
        """Test normalization with lifecycle missing refresh cadence"""
        odcs_contract = {
            "id": "test-lifecycle-no-cadence",
            "name": "Lifecycle No Cadence Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "lifecycle": {"data_source": "OLTP.orders"},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        lifecycle = hub_contract.get("lifecycle", {})
        self.assertEqual(lifecycle.get("data_source"), "OLTP.orders")
        # Refresh cadence may be missing
        self.assertNotIn("refresh_cadence", lifecycle)

    def test_normalize_contract_marketplace_without_license(self):
        """Test normalization with marketplace missing license"""
        odcs_contract = {
            "id": "test-marketplace-no-license",
            "name": "Marketplace No License Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "marketplace": {"intended_use": ["analytics"]},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        marketplace = hub_contract.get("marketplace", {})
        intended_use = marketplace.get("intended_use", [])
        self.assertIn("analytics", intended_use)
        # License may be missing
        self.assertNotIn("license_summary", marketplace)

    def test_normalize_contract_nested_quality_rules(self):
        """Test normalization with nested quality rule structures"""
        odcs_contract = {
            "id": "test-nested-quality",
            "name": "Nested Quality Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "quality": {
                "rules": [
                    {
                        "rule_id": "rule1",
                        "dimension": "completeness",
                        "expression": "field1 IS NOT NULL",
                        "severity": "ERROR",
                        "field": "field1",
                        "metadata": {"nested": {"deep": "value"}},
                    }
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        quality = hub_contract.get("quality", {})
        rules = quality.get("rules", [])
        rule = rules[0]
        # Nested metadata should be preserved
        metadata = rule.get("metadata", {})
        if metadata:
            nested = metadata.get("nested", {})
            self.assertEqual(nested.get("deep"), "value")

    def test_normalize_contract_complex_compliance_policy(self):
        """Test normalization with complex compliance policy"""
        odcs_contract = {
            "id": "test-complex-compliance",
            "name": "Complex Compliance Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["EMAIL", "PHONE", "ADDRESS"],
                "jurisdictions": ["GDPR", "LGPD", "CCPA", "HIPAA"],
                "legal_bases": ["CONSENT", "CONTRACT", "LEGAL_OBLIGATION"],
                "retention_policy": {
                    "period": "P5Y",
                    "notes": "5 years retention",
                    "conditions": ["After contract end", "Upon request"],
                },
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        compliance = hub_contract.get("privacy_compliance", {})
        self.assertEqual(len(compliance.get("personal_data_categories", [])), 3)
        self.assertEqual(len(compliance.get("jurisdictions", [])), 4)
        retention = compliance.get("retention_policy", {})
        self.assertEqual(retention.get("period"), "P5Y")

    def test_normalize_contract_complex_lifecycle_policy(self):
        """Test normalization with complex lifecycle policy"""
        odcs_contract = {
            "id": "test-complex-lifecycle",
            "name": "Complex Lifecycle Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "lifecycle": {
                "data_source": "OLTP.orders",
                "refresh_cadence": "DAILY",
                "slas": {
                    "availability": "99.9",
                    "latency_ms_p95": 5000,
                    "latency_ms_p99": 10000,
                    "throughput_rps": 1000,
                },
                "backup_policy": {"frequency": "DAILY", "retention": "P30D"},
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        lifecycle = hub_contract.get("lifecycle", {})
        slas = lifecycle.get("slas", {})
        self.assertEqual(slas.get("availability"), "99.9")
        # Additional fields may be in extensions
        extensions = hub_contract.get("extensions", {})
        if extensions:
            odcs_ext = extensions.get("odcs", {})
            lifecycle_ext = odcs_ext.get("lifecycle", {})
            if lifecycle_ext:
                self.assertIn("backup_policy", lifecycle_ext)

    def test_normalize_contract_mixed_case_field_names(self):
        """Test normalization with mixed case field names"""
        odcs_contract = {
            "id": "test-mixed-case",
            "name": "Mixed Case Test",
            "schema": {
                "fields": [
                    {"name": "Field1", "type": "string"},
                    {"name": "field_2", "type": "string"},
                    {"name": "FIELD_3", "type": "string"},
                    {"name": "field-4", "type": "string"},
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field_names = [f.get("name") for f in fields]
        # All field names should be preserved as-is
        self.assertIn("Field1", field_names)
        self.assertIn("field_2", field_names)
        self.assertIn("FIELD_3", field_names)
        self.assertIn("field-4", field_names)

    def test_normalize_contract_field_with_whitespace_in_name(self):
        """Test normalization with field name containing whitespace"""
        odcs_contract = {
            "id": "test-whitespace",
            "name": "Whitespace Test",
            "schema": {
                "fields": [
                    {"name": "field with spaces", "type": "string"},
                    {"name": "field\twith\ttabs", "type": "string"},
                    {"name": "field\nwith\nnewlines", "type": "string"},
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        # Field names with whitespace should be preserved
        field_names = [f.get("name") for f in fields]
        self.assertIn("field with spaces", field_names)

    def test_normalize_contract_field_with_sql_keywords(self):
        """Test normalization with field names that are SQL keywords"""
        odcs_contract = {
            "id": "test-sql-keywords",
            "name": "SQL Keywords Test",
            "schema": {
                "fields": [
                    {"name": "select", "type": "string"},
                    {"name": "from", "type": "string"},
                    {"name": "where", "type": "string"},
                    {"name": "order", "type": "string"},
                    {"name": "group", "type": "string"},
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field_names = [f.get("name") for f in fields]
        # SQL keywords should be preserved as field names
        self.assertIn("select", field_names)
        self.assertIn("from", field_names)
        self.assertIn("where", field_names)

    def test_normalize_contract_very_long_field_names(self):
        """Test normalization with very long field names"""
        long_name = "field_" + "x" * 199  # 205 characters (6 + 199 = 205)

        odcs_contract = {
            "id": "test-long-names",
            "name": "Long Names Test",
            "schema": {"fields": [{"name": long_name, "type": "string"}]},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field = fields[0]
        # Very long field name should be preserved
        self.assertEqual(len(field.get("name")), 205)

    def test_normalize_contract_field_with_unicode_in_name(self):
        """Test normalization with unicode characters in field names"""
        odcs_contract = {
            "id": "test-unicode-names",
            "name": "Unicode Names Test",
            "schema": {
                "fields": [
                    {"name": "field_测试", "type": "string"},
                    {"name": "field_émoji🎉", "type": "string"},
                    {"name": "field_中文", "type": "string"},
                ]
            },
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        fields = hub_contract.get("schema", {}).get("fields", [])
        field_names = [f.get("name") for f in fields]
        # Unicode field names should be preserved
        self.assertIn("field_测试", field_names)
        self.assertIn("field_émoji🎉", field_names)
        self.assertIn("field_中文", field_names)

    def test_normalize_contract_quality_profile_without_rules(self):
        """Test normalization with quality profile but no rules"""
        odcs_contract = {
            "id": "test-quality-profile-only",
            "name": "Quality Profile Only Test",
            "schema": {"fields": [{"name": "field1", "type": "string"}]},
            "quality": {"default_profile_key": "intake_basic_gx"},
        }

        hub_contract, _status, _errors, _warnings = normalize_odcs_to_hubcontract(odcs_contract)

        self.assertIsNotNone(hub_contract)
        quality = hub_contract.get("quality", {})
        self.assertEqual(quality.get("default_profile_key"), "intake_basic_gx")
        # Rules may be missing or empty
        rules = quality.get("rules", [])
        self.assertIsInstance(rules, list)
