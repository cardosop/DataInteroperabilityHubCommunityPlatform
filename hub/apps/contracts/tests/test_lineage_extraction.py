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
        self.assertEqual(result["entries"][0]["transformations"][0]["logic"], "SELECT * FROM source")

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
                {"namespace": "ns2", "name": "contract2", "model": "model2", "field": "field1"},  # Field reference
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
                {"namespace": "ns1", "name": "source-contract", "model": "source-model", "field": "source-field"},
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
        self.assertEqual(result["transformations"][0]["logic"], "CONCAT(source_field1, source_field2)")

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
        self.assertEqual(result["transformations"][0]["description"], "Concatenates two source fields")

    def test_extract_field_level_lineage_with_both(self):
        """Test extraction with both transformSourceObjects and transformLogic."""
        odcs_field = {
            "name": "test-field",
            "type": "string",
            "transformSourceObjects": [{"namespace": "ns1", "name": "source", "model": "model1", "field": "field1"}],
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

