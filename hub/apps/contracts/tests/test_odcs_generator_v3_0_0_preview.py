"""
Unit tests for ODCS Generator V3.0.0-Preview.

Tests the ODCSGeneratorV3_0_0_Preview class following TDD approach
and engineering best practices without mocks/stubs.
"""

import json

import pytest
from django.test import TestCase

from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.odcs_errors import ODCSGenerationError
from hub.apps.contracts.odcs_generator import ODCSGeneratorV3_0_0_Preview

pytestmark = pytest.mark.django_db(transaction=True)


class ODCSGeneratorV3_0_0_PreviewStructureTest(TestCase):
    """Test ODCSGeneratorV3_0_0_Preview structure and instantiation"""

    def test_can_instantiate_generator(self):
        """Test that ODCSGeneratorV3_0_0_Preview can be instantiated"""
        generator = ODCSGeneratorV3_0_0_Preview()
        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_0_Preview)

    def test_has_generate_method(self):
        """Test that generator has generate_odcs_from_hubcontract method"""
        generator = ODCSGeneratorV3_0_0_Preview()
        self.assertTrue(hasattr(generator, "generate_odcs_from_hubcontract"))
        self.assertTrue(callable(generator.generate_odcs_from_hubcontract))


class ODCSGeneratorV3_0_0_PreviewBasicMappingTest(TestCase):
    """Test basic field mappings (id, name, description, version)"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0_Preview()
        self.minimal_hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

    def test_maps_id(self):
        """Test mapping of id field"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(self.minimal_hub_contract)
        self.assertEqual(odcs_doc["id"], "test-contract-1")

    def test_maps_name(self):
        """Test mapping of name field"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(self.minimal_hub_contract)
        self.assertEqual(odcs_doc["name"], "Test Contract")

    def test_maps_description(self):
        """Test mapping of description field"""
        hub_contract = self.minimal_hub_contract.copy()
        hub_contract["info"]["description"] = "Test description"
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertEqual(odcs_doc["description"], "Test description")

    def test_maps_version(self):
        """Test mapping of version field"""
        hub_contract = self.minimal_hub_contract.copy()
        hub_contract["info"]["version"] = "1.0.0"
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertEqual(odcs_doc["version"], "1.0.0")

    def test_sets_api_version(self):
        """Test that apiVersion is set correctly for 3.0.0-preview"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(self.minimal_hub_contract)
        self.assertEqual(odcs_doc["apiVersion"], "odcs.io/v3.0.0-preview")

    def test_sets_kind(self):
        """Test that kind is set correctly"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(self.minimal_hub_contract)
        self.assertEqual(odcs_doc["kind"], "DataContract")


class ODCSGeneratorV3_0_0_PreviewInfoSectionTest(TestCase):
    """Test info section mappings (owners, tags)"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0_Preview()
        self.base_hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

    def test_maps_owners_list(self):
        """Test mapping of owners list"""
        hub_contract = self.base_hub_contract.copy()
        hub_contract["info"]["owners"] = [
            {"name": "Owner 1", "email": "owner1@example.com"},
            {"name": "Owner 2"},
        ]
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("info", odcs_doc)
        self.assertIn("owners", odcs_doc["info"])
        self.assertEqual(len(odcs_doc["info"]["owners"]), 2)
        self.assertEqual(odcs_doc["info"]["owners"][0]["name"], "Owner 1")
        self.assertEqual(odcs_doc["info"]["owners"][0]["email"], "owner1@example.com")

    def test_maps_owners_string_list(self):
        """Test mapping of owners as string list"""
        hub_contract = self.base_hub_contract.copy()
        hub_contract["info"]["owners"] = ["Owner 1", "Owner 2"]
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("info", odcs_doc)
        self.assertIn("owners", odcs_doc["info"])
        self.assertEqual(len(odcs_doc["info"]["owners"]), 2)
        self.assertEqual(odcs_doc["info"]["owners"][0]["name"], "Owner 1")

    def test_maps_tags(self):
        """Test mapping of tags"""
        hub_contract = self.base_hub_contract.copy()
        hub_contract["info"]["tags"] = ["tag1", "tag2", "tag3"]
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("info", odcs_doc)
        self.assertIn("tags", odcs_doc["info"])
        self.assertEqual(odcs_doc["info"]["tags"], ["tag1", "tag2", "tag3"])


class ODCSGeneratorV3_0_0_PreviewSchemaMappingTest(TestCase):
    """Test schema section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0_Preview()
        self.base_hub_contract = {"id": "test-contract-1", "info": {"name": "Test Contract"}}

    def test_maps_single_schema_object(self):
        """Test mapping of single schema object"""
        hub_contract = self.base_hub_contract.copy()
        hub_contract["schema"] = {
            "fields": [
                {"name": "id", "data_type": "string", "nullable": False},
                {"name": "name", "data_type": "string", "nullable": True},
            ]
        }
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("schema", odcs_doc)
        self.assertIn("fields", odcs_doc["schema"])
        self.assertEqual(len(odcs_doc["schema"]["fields"]), 2)
        self.assertEqual(odcs_doc["schema"]["fields"][0]["name"], "id")
        self.assertEqual(odcs_doc["schema"]["fields"][0]["type"], "string")

    def test_maps_field_properties(self):
        """Test mapping of field properties (format, pattern, enum, etc.)"""
        hub_contract = self.base_hub_contract.copy()
        hub_contract["schema"] = {
            "fields": [
                {
                    "name": "email",
                    "data_type": "string",
                    "format": "email",
                    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                    "nullable": False,
                    "description": "Email address",
                }
            ]
        }
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        field = odcs_doc["schema"]["fields"][0]
        self.assertEqual(field["format"], "email")
        self.assertEqual(field["pattern"], "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
        self.assertEqual(field["description"], "Email address")
        self.assertEqual(field["nullable"], False)

    def test_maps_primary_key(self):
        """Test mapping of primary key"""
        hub_contract = self.base_hub_contract.copy()
        hub_contract["schema"] = {
            "fields": [{"name": "id", "data_type": "string"}],
            "primary_key": "id",
        }
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("primaryKey", odcs_doc["schema"])
        self.assertEqual(odcs_doc["schema"]["primaryKey"], "id")

    def test_maps_unique_constraints_and_indexes(self):
        """Test mapping of unique constraints and indexes"""
        hub_contract = self.base_hub_contract.copy()
        hub_contract["schema"] = {
            "fields": [
                {"name": "id", "data_type": "string"},
                {"name": "email", "data_type": "string"},
            ],
            "unique_constraints": [["email"]],
            "indexes": [["email"]],
        }
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("uniqueConstraints", odcs_doc["schema"])
        self.assertIn("indexes", odcs_doc["schema"])


class ODCSGeneratorV3_0_0_PreviewQualityMappingTest(TestCase):
    """Test quality section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0_Preview()
        self.base_hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

    def test_maps_default_profile_key(self):
        """Test mapping of default_profile_key"""
        hub_contract = self.base_hub_contract.copy()
        hub_contract["quality"] = {"default_profile_key": "profile1"}
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("quality", odcs_doc)
        self.assertEqual(odcs_doc["quality"]["default_profile_key"], "profile1")

    def test_maps_quality_rules(self):
        """Test mapping of quality rules"""
        hub_contract = self.base_hub_contract.copy()
        hub_contract["quality"] = {
            "rules": [
                {
                    "name": "not_null",
                    "type": "not_null",
                    "expression": "id IS NOT NULL",
                    "severity": "error",
                }
            ]
        }
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("quality", odcs_doc)
        self.assertIn("rules", odcs_doc["quality"])
        self.assertEqual(len(odcs_doc["quality"]["rules"]), 1)
        self.assertEqual(odcs_doc["quality"]["rules"][0]["name"], "not_null")


class ODCSGeneratorV3_0_0_PreviewLifecycleMappingTest(TestCase):
    """Test lifecycle section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0_Preview()
        self.base_hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

    def test_maps_lifecycle_section(self):
        """Test mapping of lifecycle section"""
        hub_contract = self.base_hub_contract.copy()
        hub_contract["lifecycle"] = {
            "data_source": "database",
            "refresh_cadence": "daily",
            "slas": {"availability": "99.9%", "latency_ms_p95": 100},
        }
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("lifecycle", odcs_doc)
        self.assertEqual(odcs_doc["lifecycle"]["data_source"], "database")
        self.assertEqual(odcs_doc["lifecycle"]["refresh_cadence"], "daily")
        self.assertIn("slas", odcs_doc["lifecycle"])


class ODCSGeneratorV3_0_0_PreviewErrorHandlingTest(TestCase):
    """Test error handling for invalid inputs"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0_Preview()

    def test_raises_error_for_missing_id(self):
        """Test that missing id raises error"""
        hub_contract = {"info": {"name": "Test Contract"}}
        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("id", str(cm.exception).lower())

    def test_raises_error_for_missing_name(self):
        """Test that missing name raises error"""
        hub_contract = {"id": "test-contract-1", "info": {}}
        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("name", str(cm.exception).lower())

    def test_raises_error_for_wrong_type(self):
        """Test that wrong field type raises error"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract", "version": 123},  # Should be string
        }
        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("version", str(cm.exception).lower())


class ODCSGeneratorV3_0_0_PreviewEdgeCasesTest(TestCase):
    """Test edge cases (empty arrays, None values, optional fields)"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0_Preview()
        self.base_hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

    def test_handles_empty_owners_list(self):
        """Test handling of empty owners list"""
        hub_contract = self.base_hub_contract.copy()
        hub_contract["info"]["owners"] = []
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        # Empty owners list must not produce owners key in output.
        # The generator may omit the info section entirely (when no info fields
        # are populated) or include it without the owners key.  Use .get() so
        # the assertion runs unconditionally.
        self.assertNotIn(
            "owners",
            odcs_doc.get("info", {}),
            "Empty owners list must not produce owners key in output",
        )

    def test_handles_missing_optional_fields(self):
        """Test handling of missing optional fields"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(self.base_hub_contract)
        # Should not raise error for missing optional fields
        self.assertIn("id", odcs_doc)
        self.assertIn("name", odcs_doc)


class ODCSGeneratorV3_0_0_PreviewRoundTripTest(TestCase):
    """Test round-trip: ODCS 3.0.0-preview → HubContract → ODCS 3.0.0-preview"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0_Preview()

    def test_round_trip_basic_contract(self):
        """Test round-trip with basic contract"""
        hub_contract = {
            "id": "test-contract-roundtrip",
            "info": {"name": "Test Contract Roundtrip", "version": "1.0.0"},
            "schema": {"fields": [{"name": "id", "data_type": "string", "nullable": False}]},
        }

        # Generate ODCS 3.0.0-preview
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        # Normalize back to HubContract (convert to JSON string first)
        odcs_json = json.dumps(odcs_doc)
        hub_contract_dict, _spec_type, _spec_version, _status, errors, _warnings = (
            normalize_contract(odcs_json, "JSON", spec_type="ODCS")
        )
        self.assertIsNotNone(hub_contract_dict)
        self.assertEqual(len(errors), 0, f"Normalization errors: {errors}")

        # Generate ODCS 3.0.0-preview again
        odcs_doc_2 = self.generator.generate_odcs_from_hubcontract(hub_contract_dict)

        # Compare key fields
        self.assertEqual(odcs_doc["id"], odcs_doc_2["id"])
        self.assertEqual(odcs_doc["name"], odcs_doc_2["name"])

    def test_round_trip_with_quality_and_lifecycle(self):
        """Test round-trip with quality and lifecycle sections"""
        hub_contract = {
            "id": "test-contract-full",
            "info": {"name": "Test Contract Full", "version": "1.0.0"},
            "schema": {"fields": [{"name": "id", "data_type": "string", "nullable": False}]},
            "quality": {
                "default_profile_key": "profile1",
                "rules": [{"name": "not_null", "type": "not_null", "expression": "id IS NOT NULL"}],
            },
            "lifecycle": {"data_source": "database", "refresh_cadence": "daily"},
        }

        # Generate ODCS 3.0.0-preview
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        # Normalize back to HubContract (convert to JSON string first)
        odcs_json = json.dumps(odcs_doc)
        hub_contract_dict, _spec_type, _spec_version, _status, errors, _warnings = (
            normalize_contract(odcs_json, "JSON", spec_type="ODCS")
        )
        self.assertIsNotNone(hub_contract_dict)
        self.assertEqual(len(errors), 0, f"Normalization errors: {errors}")

        # Generate ODCS 3.0.0-preview again
        odcs_doc_2 = self.generator.generate_odcs_from_hubcontract(hub_contract_dict)

        # Compare key fields
        self.assertEqual(odcs_doc["id"], odcs_doc_2["id"])
        self.assertEqual(odcs_doc["name"], odcs_doc_2["name"])

    def test_generation_handles_unicode_characters(self):
        """Test that generation handles unicode characters correctly."""
        hub_contract = {
            "id": "test-unicode",
            "info": {"name": "测试合同", "description": "测试描述"},
            "schema": {"fields": [{"name": "字段名称", "data_type": "string"}]},
        }

        result = self.generator.generate_odcs_from_hubcontract(hub_contract)

        # Verify unicode characters are preserved
        self.assertIn("name", result)
        self.assertEqual(result["name"], "测试合同")

    def test_generation_handles_special_characters(self):
        """Test that generation handles special characters correctly."""
        hub_contract = {
            "id": "test-special",
            "info": {"name": "Test & Co. (Special)", "description": "Test <description> & more"},
            "schema": {"fields": [{"name": "field-name", "data_type": "string"}]},
        }

        result = self.generator.generate_odcs_from_hubcontract(hub_contract)

        # Verify special characters are preserved
        self.assertIn("name", result)
        self.assertEqual(result["name"], "Test & Co. (Special)")

    def test_generation_handles_very_large_documents(self):
        """Test that generation handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = {
            "id": "test-large",
            "info": {"name": "Test Product", "description": large_description},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        result = self.generator.generate_odcs_from_hubcontract(hub_contract)
        # Verify the generator handles the large input and preserves the data
        self.assertIn("name", result)
        self.assertEqual(result["name"], "Test Product")
        self.assertIn("description", result, "Large description must be present in output")
        self.assertEqual(
            result["description"],
            large_description,
            "Large description value must be preserved exactly",
        )

    def test_generation_handles_none_values(self):
        """Test that generation handles None values correctly."""
        hub_contract = {
            "id": "test-none",
            "info": {"name": "Test Product", "description": None},  # None value
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        # None values should be omitted or handled gracefully
        result = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIsNotNone(result)
        self.assertIn("name", result)
        self.assertEqual(result["name"], "Test Product")
        # None-valued fields must be absent from output
        self.assertNotIn(
            "description", result, "None description field must be omitted from output"
        )

    def test_generation_handles_nested_structures(self):
        """Test that generation handles nested structures correctly."""
        hub_contract = {
            "id": "test-nested",
            "info": {
                "name": "Test Product",
                "nested": {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}},
            },
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        result = self.generator.generate_odcs_from_hubcontract(hub_contract)

        # Verify the generator doesn't crash and preserves known fields.
        self.assertIsNotNone(result)
        self.assertIn("name", result)
        self.assertEqual(
            result["name"],
            "Test Product",
            "Name must be correctly extracted from deeply nested hub_contract info",
        )
        # Verify the generator produces a structurally valid ODCS doc
        self.assertIn("apiVersion", result)
        self.assertIn("kind", result)
        self.assertEqual(result["kind"], "DataContract")
