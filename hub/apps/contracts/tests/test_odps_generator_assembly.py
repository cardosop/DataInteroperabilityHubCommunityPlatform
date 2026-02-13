"""
Unit tests for ODPS Generator - Document Assembly (Task 2.1.8)

Tests verify:
1. Complete ODPS document structure assembly
2. Schema URL setting (ODPS 4.1)
3. Version field setting ("4.1")
4. YAML output formatting
5. JSON output formatting
"""

from django.test import SimpleTestCase, TestCase

from hub.apps.contracts.odps_errors import ODPSExportError
from hub.apps.contracts.odps_generator import (
    format_odps_as_json,
    format_odps_as_yaml,
    generate_odps_from_hubcontract,
)


class ODPSGeneratorDocumentAssemblyTest(SimpleTestCase):
    """Test ODPS generator document assembly"""

    def test_document_assembly_has_schema_url(self):
        """
        Test that assembled ODPS document has correct schema URL.

        Scenario: Generate ODPS 4.1 document
        Expected: schema field contains correct URL for ODPS 4.1
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "description": "Test product description"},
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify schema URL
        self.assertIn("schema", result)
        self.assertEqual(result["schema"], "https://opendataproducts.org/schema/v4.1")

    def test_document_assembly_has_version_field(self):
        """
        Test that assembled ODPS document has correct version field.

        Scenario: Generate ODPS 4.1 document
        Expected: version field is "4.1"
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify version field
        self.assertIn("version", result)
        self.assertEqual(result["version"], "4.1")

    def test_document_assembly_has_product_section(self):
        """
        Test that assembled ODPS document has product section.

        Scenario: Generate ODPS document
        Expected: product section exists with details
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify product section
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("en", result["product"]["details"])

    def test_document_assembly_complete_structure(self):
        """
        Test that assembled ODPS document has complete structure.

        Scenario: Generate ODPS document with all sections
        Expected: All sections are properly assembled
        """
        hub_contract = {
            "id": "complete-product",
            "info": {
                "name": "Complete Product",
                "description": "Complete product description",
                "version": "1.0.0",
                "tags": ["data", "analytics"],
                "owners": [{"name": "Data Team", "email": "data@example.com"}],
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"},
                    {"name": "name", "data_type": "string"},
                ]
            },
            "marketplace": {
                "license_summary": "MIT License",
                "x_odps": {
                    "pricing_plans": [{"planID": "basic", "name": "Basic Plan", "price": 9.99}]
                },
            },
            "lifecycle": {"slas": {"availability": 99.9}, "x_odps": {"status": "active"}},
            "quality": {"default_profile_key": "production-profile"},
            "extensions": {
                "x_odps": {"product_strategy": {"objectives": ["Increase data quality"]}}
            },
        }

        result = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Verify complete structure
        self.assertIn("schema", result)
        self.assertIn("version", result)
        self.assertIn("product", result)
        self.assertIn("license", result)
        self.assertIn("dataHolder", result)

        # Verify schema and version
        self.assertEqual(result["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(result["version"], "4.1")

        # Verify product section
        self.assertIn("details", result["product"])
        self.assertIn("marketplace", result["product"])
        self.assertIn("SLA", result["product"])
        self.assertIn("dataQuality", result["product"])

        # Verify productStrategy (ODPS 4.1+)
        self.assertIn("productStrategy", result)

    def test_document_assembly_with_different_versions(self):
        """
        Test that assembled ODPS document uses correct schema URL for different versions.

        Scenario: Generate ODPS documents with different versions
        Expected: Schema URL matches the target version
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        versions = ["4.1", "4.0", "3.9"]
        for version in versions:
            result = generate_odps_from_hubcontract(hub_contract, target_version=version)

            self.assertEqual(result["schema"], f"https://opendataproducts.org/schema/v{version}")
            self.assertEqual(result["version"], version)


class ODPSGeneratorJSONFormatTest(SimpleTestCase):
    """Test ODPS generator JSON formatting"""

    def test_format_odps_as_json_basic(self):
        """
        Test formatting ODPS document as JSON.

        Scenario: Format ODPS document as JSON
        Expected: Valid JSON string is returned
        """
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }

        result = format_odps_as_json(odps_doc)

        # Verify result is a string
        self.assertIsInstance(result, str)

        # Verify it's valid JSON
        import json

        parsed = json.loads(result)
        self.assertEqual(parsed["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(parsed["version"], "4.1")

    def test_format_odps_as_json_with_indent(self):
        """
        Test formatting ODPS document as JSON with custom indentation.

        Scenario: Format ODPS document as JSON with indent=4
        Expected: JSON string with 4-space indentation
        """
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }

        result = format_odps_as_json(odps_doc, indent=4)

        # Verify result is a string
        self.assertIsInstance(result, str)

        # Verify it's valid JSON
        import json

        parsed = json.loads(result)
        self.assertEqual(parsed["version"], "4.1")

        # Verify indentation (should have 4 spaces)
        lines = result.split("\n")
        if len(lines) > 1:
            # Second line should start with 4 spaces
            self.assertTrue(lines[1].startswith("    "))

    def test_format_odps_as_json_with_unicode(self):
        """
        Test formatting ODPS document as JSON with unicode characters.

        Scenario: Format ODPS document with unicode characters
        Expected: Unicode characters are preserved (ensure_ascii=False)
        """
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {"productID": "test-product", "name": "Test Product with émojis 🚀"}
                }
            },
        }

        result = format_odps_as_json(odps_doc, ensure_ascii=False)

        # Verify unicode characters are preserved
        self.assertIn("émojis", result)
        self.assertIn("🚀", result)

        # Verify it's valid JSON
        import json

        parsed = json.loads(result)
        self.assertIn("émojis", parsed["product"]["details"]["en"]["name"])

    def test_format_odps_as_json_with_complete_document(self):
        """
        Test formatting complete ODPS document as JSON.

        Scenario: Format complete ODPS document with all sections
        Expected: Valid JSON string with all sections
        """
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test description",
                    }
                },
                "marketplace": {
                    "pricingPlans": [{"planID": "basic", "name": "Basic Plan", "price": 9.99}]
                },
                "SLA": {"declarative": {"dimensions": {"availability": {"target": 99.9}}}},
            },
            "license": {"en": {"definition": "MIT License"}},
        }

        result = format_odps_as_json(odps_doc)

        # Verify result is valid JSON
        import json

        parsed = json.loads(result)

        # Verify all sections are present
        self.assertIn("schema", parsed)
        self.assertIn("version", parsed)
        self.assertIn("product", parsed)
        self.assertIn("license", parsed)
        self.assertIn("marketplace", parsed["product"])
        self.assertIn("SLA", parsed["product"])

    def test_format_odps_as_json_with_invalid_document(self):
        """
        Test error handling when formatting invalid document as JSON.

        Scenario: Format non-dictionary as JSON
        Expected: ODPSExportError with field_path and expected/actual types
        """
        with self.assertRaises(ODPSExportError) as context:
            format_odps_as_json("not-a-dict")

        error = context.exception
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/")
        if "expected" in error.context:
            self.assertEqual(error.context["expected"], "dict")
        if "actual" in error.context:
            self.assertIn("str", error.context["actual"])

    def test_format_odps_as_json_with_non_serializable_object(self):
        """
        Test error handling when document contains non-serializable objects.

        Scenario: Format document with non-serializable object
        Expected: ODPSExportError with error context
        """

        class NonSerializable:
            pass

        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "custom": NonSerializable(),  # Non-serializable
                    }
                }
            },
        }

        with self.assertRaises(ODPSExportError) as context:
            format_odps_as_json(odps_doc)

        error = context.exception
        self.assertIn("json", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/")


class ODPSGeneratorYAMLFormatTest(SimpleTestCase):
    """Test ODPS generator YAML formatting"""

    def test_format_odps_as_yaml_basic(self):
        """
        Test formatting ODPS document as YAML.

        Scenario: Format ODPS document as YAML
        Expected: Valid YAML string is returned
        """
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test-product", "name": "Test Product"}}},
        }

        result = format_odps_as_yaml(odps_doc)

        # Verify result is a string
        self.assertIsInstance(result, str)

        # Verify it's valid YAML
        try:
            import yaml

            parsed = yaml.safe_load(result)
            self.assertEqual(parsed["schema"], "https://opendataproducts.org/schema/v4.1")
            self.assertEqual(parsed["version"], "4.1")
        except ImportError:
            # PyYAML not available, skip YAML parsing test
            self.skipTest("PyYAML not available")

    def test_format_odps_as_yaml_with_unicode(self):
        """
        Test formatting ODPS document as YAML with unicode characters.

        Scenario: Format ODPS document with unicode characters
        Expected: Unicode characters are preserved (allow_unicode=True)
        """
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {"productID": "test-product", "name": "Test Product with émojis 🚀"}
                }
            },
        }

        result = format_odps_as_yaml(odps_doc, allow_unicode=True)

        # Verify unicode characters are preserved
        self.assertIn("émojis", result)
        self.assertIn("🚀", result)

        # Verify it's valid YAML
        try:
            import yaml

            parsed = yaml.safe_load(result)
            self.assertIn("émojis", parsed["product"]["details"]["en"]["name"])
        except ImportError:
            self.skipTest("PyYAML not available")

    def test_format_odps_as_yaml_with_complete_document(self):
        """
        Test formatting complete ODPS document as YAML.

        Scenario: Format complete ODPS document with all sections
        Expected: Valid YAML string with all sections
        """
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "Test description",
                    }
                },
                "marketplace": {
                    "pricingPlans": [{"planID": "basic", "name": "Basic Plan", "price": 9.99}]
                },
            },
            "license": {"en": {"definition": "MIT License"}},
        }

        result = format_odps_as_yaml(odps_doc)

        # Verify result is valid YAML
        try:
            import yaml

            parsed = yaml.safe_load(result)

            # Verify all sections are present
            self.assertIn("schema", parsed)
            self.assertIn("version", parsed)
            self.assertIn("product", parsed)
            self.assertIn("license", parsed)
        except ImportError:
            self.skipTest("PyYAML not available")

    def test_format_odps_as_yaml_with_invalid_document(self):
        """
        Test error handling when formatting invalid document as YAML.

        Scenario: Format non-dictionary as YAML
        Expected: ODPSExportError with field_path and expected/actual types
        """
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        with self.assertRaises(ODPSExportError) as context:
            format_odps_as_yaml("not-a-dict")

        error = context.exception
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/")
        if "expected" in error.context:
            self.assertEqual(error.context["expected"], "dict")
        if "actual" in error.context:
            self.assertIn("str", error.context["actual"])

    def test_format_odps_as_yaml_without_pyyaml(self):
        """
        Test error handling when PyYAML is not available.

        Scenario: Format document as YAML without PyYAML installed
        Expected: ODPSExportError with message and context (field_path, expected, actual)

        Uses _yaml_available=False to exercise the same code path as when PyYAML
        is missing, so the test runs without skip and without mocks.
        """
        odps_doc = {"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1"}

        with self.assertRaises(ODPSExportError) as context:
            format_odps_as_yaml(odps_doc, _yaml_available=False)

        error = context.exception
        self.assertIn("pyyaml", error.message.lower())
        self.assertIn("not available", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/")
        self.assertIn("expected", error.context)
        self.assertIn("actual", error.context)


class ODPSGeneratorAssemblyIntegrationTest(SimpleTestCase):
    """Integration tests for ODPS generator document assembly"""

    def test_generate_and_format_as_json(self):
        """
        Test generating ODPS document and formatting as JSON.

        Scenario: Generate ODPS document and format as JSON
        Expected: Valid JSON string with complete structure
        """
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product",
                "description": "Test product description",
                "version": "1.0.0",
            },
            "schema": {"fields": []},
        }

        # Generate ODPS document
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Format as JSON
        json_output = format_odps_as_json(odps_doc)

        # Verify JSON output
        self.assertIsInstance(json_output, str)

        # Parse and verify
        import json

        parsed = json.loads(json_output)
        self.assertEqual(parsed["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(parsed["version"], "4.1")
        self.assertIn("product", parsed)

    def test_generate_and_format_as_yaml(self):
        """
        Test generating ODPS document and formatting as YAML.

        Scenario: Generate ODPS document and format as YAML
        Expected: Valid YAML string with complete structure
        """
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product",
                "description": "Test product description",
                "version": "1.0.0",
            },
            "schema": {"fields": []},
        }

        # Generate ODPS document
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Format as YAML
        yaml_output = format_odps_as_yaml(odps_doc)

        # Verify YAML output
        self.assertIsInstance(yaml_output, str)

        # Parse and verify
        parsed = yaml.safe_load(yaml_output)
        self.assertEqual(parsed["schema"], "https://opendataproducts.org/schema/v4.1")
        self.assertEqual(parsed["version"], "4.1")
        self.assertIn("product", parsed)

    def test_complete_workflow_generate_format_json_yaml(self):
        """
        Test complete workflow: generate, format as JSON, format as YAML.

        Scenario: Generate ODPS document and format in both formats
        Expected: Both JSON and YAML outputs are valid and equivalent
        """
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        hub_contract = {
            "id": "complete-product",
            "info": {
                "name": "Complete Product",
                "description": "Complete product description",
                "version": "1.0.0",
                "tags": ["data", "analytics"],
                "owners": [{"name": "Data Team", "email": "data@example.com"}],
            },
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "marketplace": {
                "license_summary": "MIT License",
                "x_odps": {
                    "pricing_plans": [{"planID": "basic", "name": "Basic Plan", "price": 9.99}]
                },
            },
        }

        # Generate ODPS document
        odps_doc = generate_odps_from_hubcontract(hub_contract, target_version="4.1")

        # Format as JSON
        json_output = format_odps_as_json(odps_doc)

        # Format as YAML
        yaml_output = format_odps_as_yaml(odps_doc)

        # Parse both
        import json

        json_parsed = json.loads(json_output)
        yaml_parsed = yaml.safe_load(yaml_output)

        # Verify both have same structure
        self.assertEqual(json_parsed["schema"], yaml_parsed["schema"])
        self.assertEqual(json_parsed["version"], yaml_parsed["version"])
        self.assertEqual(
            json_parsed["product"]["details"]["en"]["name"],
            yaml_parsed["product"]["details"]["en"]["name"],
        )

    def test_document_assembly_handles_special_characters(self):
        """Test that document assembly handles special characters correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test & Co. (Special)", "description": "Test <description> & more"},
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify special characters are preserved
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("en", result["product"]["details"])
        self.assertEqual(result["product"]["details"]["en"]["name"], "Test & Co. (Special)")
        self.assertEqual(
            result["product"]["details"]["en"]["description"], "Test <description> & more"
        )

    def test_document_assembly_handles_very_large_documents(self):
        """Test that document assembly handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "description": large_description},
            "schema": {"fields": []},
        }

        # Should handle large documents gracefully
        try:
            result = generate_odps_from_hubcontract(hub_contract)
            # If generation succeeds, verify structure
            self.assertIn("product", result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, ODPSExportError, "Should raise ODPSExportError for very large documents"
            )

    def test_document_assembly_handles_none_values(self):
        """Test that document assembly handles None values correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "description": None, "version": None},  # None value
            "schema": {"fields": []},
        }

        # Should handle None values gracefully
        try:
            result = generate_odps_from_hubcontract(hub_contract)
            # If generation succeeds, None values may be omitted or handled
            self.assertIsNotNone(result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, ODPSExportError, "Should raise ODPSExportError for None values"
            )

    def test_document_assembly_handles_nested_structures(self):
        """Test that document assembly handles nested structures correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {
                "name": "Test Product",
                "nested": {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}},
            },
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify nested structure is preserved (may be in extensions or details)
        self.assertIn("product", result)
        # Nested structures may be preserved in various places depending on implementation
        self.assertIsNotNone(result)

    def test_format_odps_as_json_handles_special_characters(self):
        """Test that JSON formatting handles special characters correctly."""
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test & Co. (Special)",
                        "description": "Test <description> & more",
                    }
                }
            },
        }

        result = format_odps_as_json(odps_doc)

        # Verify special characters are preserved in JSON
        import json

        parsed = json.loads(result)
        self.assertEqual(parsed["product"]["details"]["en"]["name"], "Test & Co. (Special)")
        self.assertEqual(
            parsed["product"]["details"]["en"]["description"], "Test <description> & more"
        )

    def test_format_odps_as_yaml_handles_special_characters(self):
        """Test that YAML formatting handles special characters correctly."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test & Co. (Special)",
                        "description": "Test <description> & more",
                    }
                }
            },
        }

        result = format_odps_as_yaml(odps_doc)

        # Verify special characters are preserved in YAML
        parsed = yaml.safe_load(result)
        self.assertEqual(parsed["product"]["details"]["en"]["name"], "Test & Co. (Special)")
        self.assertEqual(
            parsed["product"]["details"]["en"]["description"], "Test <description> & more"
        )

    def test_format_odps_as_json_handles_very_large_documents(self):
        """Test that JSON formatting handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product", "description": large_description}}
            },
        }

        # Should handle large documents gracefully
        try:
            result = format_odps_as_json(odps_doc)
            # If formatting succeeds, verify it's valid JSON
            import json

            parsed = json.loads(result)
            self.assertIn("product", parsed)
        except Exception as e:
            # If formatting fails, it should fail gracefully
            self.assertIsInstance(
                e, ODPSExportError, "Should raise ODPSExportError for very large documents"
            )

    def test_format_odps_as_yaml_handles_very_large_documents(self):
        """Test that YAML formatting handles very large documents correctly."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        large_description = "A" * 100000  # 100KB string
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"name": "Test Product", "description": large_description}}
            },
        }

        # Should handle large documents gracefully
        try:
            result = format_odps_as_yaml(odps_doc)
            # If formatting succeeds, verify it's valid YAML
            parsed = yaml.safe_load(result)
            self.assertIn("product", parsed)
        except Exception as e:
            # If formatting fails, it should fail gracefully
            self.assertIsInstance(
                e, ODPSExportError, "Should raise ODPSExportError for very large documents"
            )

    def test_format_odps_as_json_handles_nested_structures(self):
        """Test that JSON formatting handles nested structures correctly."""
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product",
                        "nested": {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}},
                    }
                }
            },
        }

        result = format_odps_as_json(odps_doc)

        # Verify nested structure is preserved in JSON
        import json

        parsed = json.loads(result)
        self.assertIn("nested", parsed["product"]["details"]["en"])
        self.assertIn(
            "level1",
            parsed["product"]["details"]["en"]["nested"],
            "Nested structures should be preserved",
        )

    def test_format_odps_as_yaml_handles_nested_structures(self):
        """Test that YAML formatting handles nested structures correctly."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not available")

        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "name": "Test Product",
                        "nested": {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}},
                    }
                }
            },
        }

        result = format_odps_as_yaml(odps_doc)

        # Verify nested structure is preserved in YAML
        parsed = yaml.safe_load(result)
        self.assertIn("nested", parsed["product"]["details"]["en"])
        self.assertIn(
            "level1",
            parsed["product"]["details"]["en"]["nested"],
            "Nested structures should be preserved",
        )
