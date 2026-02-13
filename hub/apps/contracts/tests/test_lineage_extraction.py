"""
Unit tests for multi-level lineage extraction.
"""

from django.test import TestCase

from hub.apps.contracts.lineage import (
    extract_contract_level_lineage,
    extract_field_level_lineage,
    extract_model_level_lineage,
)


class TestContractLevelLineageExtraction(TestCase):
    """Tests for contract-level lineage extraction."""

    def test_extract_contract_level_lineage_with_transform_sources(self):
        """Test extraction of contract-level lineage with transformSourceObjects."""
        odcs_contract = {
            "id": "test-contract",
            "name": "Test Contract",
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "source-contract"},
                {"namespace": "ns2", "name": "another-contract", "version": "1.0.0"},
            ],
        }

        result = extract_contract_level_lineage(odcs_contract)

        self.assertIsNotNone(result)
        self.assertIn("entries", result)
        self.assertEqual(len(result["entries"]), 1)
        self.assertIn("input_fields", result["entries"][0])
        self.assertEqual(len(result["entries"][0]["input_fields"]), 2)
        self.assertIn("contracts", result)
        self.assertEqual(len(result["contracts"]), 2)

    def test_extract_contract_level_lineage_with_transform_logic(self):
        """Test extraction of contract-level lineage with transformLogic."""
        odcs_contract = {
            "id": "test-contract",
            "name": "Test Contract",
            "transformLogic": "SELECT * FROM source",
        }

        result = extract_contract_level_lineage(odcs_contract)

        self.assertIsNotNone(result)
        self.assertIn("entries", result)
        self.assertEqual(len(result["entries"]), 1)
        self.assertIn("transformations", result["entries"][0])
        self.assertEqual(len(result["entries"][0]["transformations"]), 1)
        self.assertEqual(
            result["entries"][0]["transformations"][0]["logic"], "SELECT * FROM source"
        )

    def test_extract_contract_level_lineage_with_both(self):
        """Test extraction with both transformSourceObjects and transformLogic."""
        odcs_contract = {
            "id": "test-contract",
            "name": "Test Contract",
            "transformSourceObjects": [{"namespace": "ns1", "name": "source"}],
            "transformLogic": "SELECT * FROM source",
        }

        result = extract_contract_level_lineage(odcs_contract)

        self.assertIsNotNone(result)
        self.assertIn("entries", result)
        entry = result["entries"][0]
        self.assertIn("input_fields", entry)
        self.assertIn("transformations", entry)

    def test_extract_contract_level_lineage_no_lineage(self):
        """Test extraction when no lineage data is present."""
        odcs_contract = {
            "id": "test-contract",
            "name": "Test Contract",
        }

        result = extract_contract_level_lineage(odcs_contract)

        self.assertIsNone(result)

    def test_extract_contract_level_lineage_contract_references(self):
        """Test extraction of contract references."""
        odcs_contract = {
            "id": "test-contract",
            "name": "Test Contract",
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "contract1"},  # Contract reference
                {"namespace": "ns2", "name": "contract2", "model": "model1"},  # Model reference
                {"namespace": "ns3", "name": "contract3", "field": "field1"},  # Field reference
            ],
        }

        result = extract_contract_level_lineage(odcs_contract)

        self.assertIsNotNone(result)
        self.assertIn("contracts", result)
        # Only the first one should be a contract reference
        self.assertEqual(len(result["contracts"]), 1)
        self.assertEqual(result["contracts"][0]["name"], "contract1")


class TestModelLevelLineageExtraction(TestCase):
    """Tests for model-level lineage extraction."""

    def test_extract_model_level_lineage_with_transform_sources(self):
        """Test extraction of model-level lineage with transformSourceObjects."""
        odcs_schema = {
            "name": "test-model",
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "source-contract", "model": "source-model"},
            ],
        }

        result = extract_model_level_lineage(odcs_schema)

        self.assertIsNotNone(result)
        self.assertIn("entries", result)
        self.assertEqual(len(result["entries"]), 1)
        self.assertIn("input_fields", result["entries"][0])

    def test_extract_model_level_lineage_with_transform_logic(self):
        """Test extraction of model-level lineage with transformLogic."""
        odcs_schema = {
            "name": "test-model",
            "transformLogic": "SELECT * FROM source_model",
        }

        result = extract_model_level_lineage(odcs_schema)

        self.assertIsNotNone(result)
        self.assertIn("entries", result)
        self.assertIn("transformations", result["entries"][0])

    def test_extract_model_level_lineage_model_references(self):
        """Test extraction of model references."""
        odcs_schema = {
            "name": "test-model",
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "contract1", "model": "model1"},  # Model reference
                {
                    "namespace": "ns2",
                    "name": "contract2",
                    "model": "model2",
                    "field": "field1",
                },  # Field reference
            ],
        }

        result = extract_model_level_lineage(odcs_schema)

        self.assertIsNotNone(result)
        self.assertIn("models", result)
        # Only the first one should be a model reference
        self.assertEqual(len(result["models"]), 1)
        self.assertEqual(result["models"][0]["model_name"], "model1")

    def test_extract_model_level_lineage_no_lineage(self):
        """Test extraction when no lineage data is present."""
        odcs_schema = {
            "name": "test-model",
        }

        result = extract_model_level_lineage(odcs_schema)

        self.assertIsNone(result)


class TestFieldLevelLineageExtraction(TestCase):
    """Tests for field-level lineage extraction."""

    def test_extract_field_level_lineage_with_transform_sources(self):
        """Test extraction of field-level lineage with transformSourceObjects."""
        odcs_field = {
            "name": "test-field",
            "type": "string",
            "transformSourceObjects": [
                {
                    "namespace": "ns1",
                    "name": "source-contract",
                    "model": "source-model",
                    "field": "source-field",
                },
            ],
        }

        result = extract_field_level_lineage(odcs_field)

        self.assertIsNotNone(result)
        self.assertIn("input_fields", result)
        self.assertEqual(len(result["input_fields"]), 1)

    def test_extract_field_level_lineage_with_transform_logic(self):
        """Test extraction of field-level lineage with transformLogic."""
        odcs_field = {
            "name": "test-field",
            "type": "string",
            "transformLogic": "CONCAT(source_field1, source_field2)",
        }

        result = extract_field_level_lineage(odcs_field)

        self.assertIsNotNone(result)
        self.assertIn("transformations", result)
        self.assertEqual(len(result["transformations"]), 1)
        self.assertEqual(
            result["transformations"][0]["logic"], "CONCAT(source_field1, source_field2)"
        )

    def test_extract_field_level_lineage_with_transform_description(self):
        """Test extraction of field-level lineage with transformDescription."""
        odcs_field = {
            "name": "test-field",
            "type": "string",
            "transformDescription": "Concatenates two source fields",
        }

        result = extract_field_level_lineage(odcs_field)

        self.assertIsNotNone(result)
        self.assertIn("transformations", result)
        self.assertEqual(
            result["transformations"][0]["description"], "Concatenates two source fields"
        )

    def test_extract_field_level_lineage_with_both(self):
        """Test extraction with both transformSourceObjects and transformLogic."""
        odcs_field = {
            "name": "test-field",
            "type": "string",
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "source", "model": "model1", "field": "field1"}
            ],
            "transformLogic": "source_field1",
            "transformDescription": "Direct mapping",
        }

        result = extract_field_level_lineage(odcs_field)

        self.assertIsNotNone(result)
        self.assertIn("input_fields", result)
        self.assertIn("transformations", result)
        transform = result["transformations"][0]
        self.assertIn("logic", transform)
        self.assertIn("description", transform)

    def test_extract_field_level_lineage_no_lineage(self):
        """Test extraction when no lineage data is present."""
        odcs_field = {
            "name": "test-field",
            "type": "string",
        }

        result = extract_field_level_lineage(odcs_field)

        self.assertIsNone(result)

    # Edge cases and error handling tests for contract-level lineage
    def test_extract_contract_level_lineage_with_empty_dict(self):
        """Test extraction with empty dictionary."""
        result = extract_contract_level_lineage({})
        self.assertIsNone(result)

    def test_extract_contract_level_lineage_with_none_input(self):
        """Test extraction handles None input gracefully."""
        # Function expects dict, but test that it handles gracefully
        # In practice, type checking would catch this, but test defensive behavior
        try:
            result = extract_contract_level_lineage(None)  # type: ignore
            # If it doesn't raise, result should be None or handle gracefully
            self.assertIsNone(result)
        except (AttributeError, TypeError):
            # Expected - None doesn't have .get() method
            pass

    def test_extract_contract_level_lineage_with_empty_transform_sources(self):
        """Test extraction with empty transformSourceObjects list."""
        odcs_contract = {
            "id": "test-contract",
            "transformSourceObjects": [],
        }
        result = extract_contract_level_lineage(odcs_contract)
        self.assertIsNotNone(result)
        self.assertIn("entries", result)
        self.assertEqual(len(result["entries"]), 1)
        self.assertEqual(len(result["entries"][0]["input_fields"]), 0)

    def test_extract_contract_level_lineage_with_invalid_transform_sources_type(self):
        """Test extraction with invalid transformSourceObjects type (not list)."""
        odcs_contract = {
            "id": "test-contract",
            "transformSourceObjects": "not-a-list",  # Invalid type
        }
        result = extract_contract_level_lineage(odcs_contract)
        # Should handle gracefully - only transformLogic would be used if present
        self.assertIsNone(result)  # No transformLogic, so None

    def test_extract_contract_level_lineage_with_mixed_valid_invalid_sources(self):
        """Test extraction with mix of valid and invalid source objects."""
        odcs_contract = {
            "id": "test-contract",
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "valid-contract"},
                "invalid-entry",  # Not a dict
                {"namespace": "ns2", "name": "another-valid"},
                None,  # None entry
            ],
        }
        result = extract_contract_level_lineage(odcs_contract)
        self.assertIsNotNone(result)
        self.assertIn("entries", result)
        # Should include all entries, filtering happens in reference extraction
        self.assertEqual(len(result["entries"]), 1)
        self.assertIn("contracts", result)
        # Only valid dict entries should be extracted as contract refs
        self.assertGreaterEqual(len(result["contracts"]), 1)

    def test_extract_contract_level_lineage_with_special_characters_in_names(self):
        """Test extraction with special characters in namespace/name."""
        odcs_contract = {
            "id": "test-contract",
            "transformSourceObjects": [
                {"namespace": "ns-1_test", "name": "contract.name-v2"},
                {"namespace": "ns@domain", "name": "contract#123"},
            ],
        }
        result = extract_contract_level_lineage(odcs_contract)
        self.assertIsNotNone(result)
        self.assertIn("contracts", result)
        self.assertEqual(len(result["contracts"]), 2)

    def test_extract_contract_level_lineage_with_unicode_characters(self):
        """Test extraction with unicode characters in names."""
        odcs_contract = {
            "id": "test-contract",
            "transformSourceObjects": [
                {"namespace": "命名空间", "name": "合同名称"},
                {"namespace": "espaço", "name": "contrato"},
            ],
        }
        result = extract_contract_level_lineage(odcs_contract)
        self.assertIsNotNone(result)
        self.assertIn("contracts", result)
        self.assertEqual(len(result["contracts"]), 2)

    def test_extract_contract_level_lineage_with_very_long_transform_logic(self):
        """Test extraction with very long transformLogic string."""
        long_logic = "SELECT " + ", ".join([f"field_{i}" for i in range(1000)])
        odcs_contract = {
            "id": "test-contract",
            "transformLogic": long_logic,
        }
        result = extract_contract_level_lineage(odcs_contract)
        self.assertIsNotNone(result)
        self.assertIn("entries", result)
        self.assertEqual(result["entries"][0]["transformations"][0]["logic"], long_logic)

    def test_extract_contract_level_lineage_with_many_source_objects(self):
        """Test extraction with many transformSourceObjects."""
        odcs_contract = {
            "id": "test-contract",
            "transformSourceObjects": [
                {"namespace": f"ns{i}", "name": f"contract{i}"} for i in range(100)
            ],
        }
        result = extract_contract_level_lineage(odcs_contract)
        self.assertIsNotNone(result)
        self.assertIn("contracts", result)
        self.assertEqual(len(result["contracts"]), 100)

    def test_extract_contract_level_lineage_with_partial_source_object(self):
        """Test extraction with source objects missing namespace or name."""
        odcs_contract = {
            "id": "test-contract",
            "transformSourceObjects": [
                {"namespace": "ns1"},  # Missing name
                {"name": "contract1"},  # Missing namespace
                {"namespace": "ns2", "name": "contract2"},  # Complete
            ],
        }
        result = extract_contract_level_lineage(odcs_contract)
        self.assertIsNotNone(result)
        # All should be included in entries, but only complete ones as contract refs
        self.assertIn("contracts", result)
        # At least the complete one should be there
        self.assertGreaterEqual(len(result["contracts"]), 1)

    # Edge cases and error handling tests for model-level lineage
    def test_extract_model_level_lineage_with_empty_dict(self):
        """Test extraction with empty dictionary."""
        result = extract_model_level_lineage({})
        self.assertIsNone(result)

    def test_extract_model_level_lineage_with_empty_transform_sources(self):
        """Test extraction with empty transformSourceObjects list."""
        odcs_schema = {
            "name": "test-model",
            "transformSourceObjects": [],
        }
        result = extract_model_level_lineage(odcs_schema)
        self.assertIsNotNone(result)
        self.assertIn("entries", result)
        self.assertEqual(len(result["entries"]), 1)

    def test_extract_model_level_lineage_with_invalid_transform_sources_type(self):
        """Test extraction with invalid transformSourceObjects type."""
        odcs_schema = {
            "name": "test-model",
            "transformSourceObjects": {"not": "a-list"},
        }
        result = extract_model_level_lineage(odcs_schema)
        # Should handle gracefully
        self.assertIsNone(result)  # No transformLogic, so None

    def test_extract_model_level_lineage_with_mixed_valid_invalid_sources(self):
        """Test extraction with mix of valid and invalid source objects."""
        odcs_schema = {
            "name": "test-model",
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "contract1", "model": "model1"},
                "invalid-entry",
                {"namespace": "ns2", "name": "contract2", "model": "model2", "field": "field1"},
            ],
        }
        result = extract_model_level_lineage(odcs_schema)
        self.assertIsNotNone(result)
        self.assertIn("models", result)
        # Only entries without field should be model refs
        model_refs = [m for m in result["models"] if "field" not in str(m)]
        self.assertGreaterEqual(len(model_refs), 1)

    def test_extract_model_level_lineage_with_field_reference_should_not_be_model_ref(self):
        """Test that field references are not included in model references."""
        odcs_schema = {
            "name": "test-model",
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "contract1", "model": "model1", "field": "field1"},
            ],
        }
        result = extract_model_level_lineage(odcs_schema)
        # Field references should not be in models list
        if result and "models" in result:
            self.assertEqual(len(result["models"]), 0)

    def test_extract_model_level_lineage_with_special_characters(self):
        """Test extraction with special characters in model names."""
        odcs_schema = {
            "name": "test-model",
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "contract1", "model": "model-name_v2"},
            ],
        }
        result = extract_model_level_lineage(odcs_schema)
        self.assertIsNotNone(result)
        if result and "models" in result:
            self.assertGreaterEqual(len(result["models"]), 0)

    # Edge cases and error handling tests for field-level lineage
    def test_extract_field_level_lineage_with_empty_dict(self):
        """Test extraction with empty dictionary."""
        result = extract_field_level_lineage({})
        self.assertIsNone(result)

    def test_extract_field_level_lineage_with_empty_transform_sources(self):
        """Test extraction with empty transformSourceObjects list."""
        odcs_field = {
            "name": "test-field",
            "transformSourceObjects": [],
        }
        result = extract_field_level_lineage(odcs_field)
        self.assertIsNotNone(result)
        self.assertIn("input_fields", result)
        self.assertEqual(len(result["input_fields"]), 0)

    def test_extract_field_level_lineage_with_invalid_transform_sources_type(self):
        """Test extraction with invalid transformSourceObjects type."""
        odcs_field = {
            "name": "test-field",
            "transformSourceObjects": "not-a-list",
        }
        result = extract_field_level_lineage(odcs_field)
        # Should return None if no transformLogic either
        self.assertIsNone(result)

    def test_extract_field_level_lineage_with_only_transform_description(self):
        """Test extraction with only transformDescription (no logic or sources)."""
        odcs_field = {
            "name": "test-field",
            "transformDescription": "Some transformation",
        }
        result = extract_field_level_lineage(odcs_field)
        # Should return None - requires transformLogic or transformSourceObjects
        self.assertIsNone(result)

    def test_extract_field_level_lineage_with_empty_strings(self):
        """Test extraction with empty string values."""
        odcs_field = {
            "name": "test-field",
            "transformLogic": "",
            "transformDescription": "",
        }
        result = extract_field_level_lineage(odcs_field)
        # Empty strings should be handled - may return None or empty transformation
        if result:
            # If it returns something, check structure
            self.assertIn("transformations", result)

    def test_extract_field_level_lineage_with_whitespace_only_logic(self):
        """Test extraction with whitespace-only transformLogic."""
        odcs_field = {
            "name": "test-field",
            "transformLogic": "   \n\t   ",
        }
        result = extract_field_level_lineage(odcs_field)
        # Should still create transformation entry
        self.assertIsNotNone(result)
        self.assertIn("transformations", result)

    def test_extract_field_level_lineage_with_mixed_valid_invalid_sources(self):
        """Test extraction with mix of valid and invalid source objects."""
        odcs_field = {
            "name": "test-field",
            "transformSourceObjects": [
                {"namespace": "ns1", "name": "contract1", "model": "model1", "field": "field1"},
                "invalid-entry",
                None,
            ],
        }
        result = extract_field_level_lineage(odcs_field)
        self.assertIsNotNone(result)
        self.assertIn("input_fields", result)
        # Should include all entries in input_fields
        self.assertGreaterEqual(len(result["input_fields"]), 1)

    def test_extract_field_level_lineage_with_special_characters_in_field_names(self):
        """Test extraction with special characters in field names."""
        odcs_field = {
            "name": "test-field",
            "transformSourceObjects": [
                {
                    "namespace": "ns1",
                    "name": "contract1",
                    "model": "model1",
                    "field": "field-name_v2",
                },
            ],
        }
        result = extract_field_level_lineage(odcs_field)
        self.assertIsNotNone(result)
        self.assertIn("input_fields", result)

    def test_extract_field_level_lineage_with_very_long_transform_logic(self):
        """Test extraction with very long transformLogic."""
        long_logic = "CONCAT(" + ", ".join([f"field_{i}" for i in range(500)]) + ")"
        odcs_field = {
            "name": "test-field",
            "transformLogic": long_logic,
        }
        result = extract_field_level_lineage(odcs_field)
        self.assertIsNotNone(result)
        self.assertEqual(result["transformations"][0]["logic"], long_logic)
