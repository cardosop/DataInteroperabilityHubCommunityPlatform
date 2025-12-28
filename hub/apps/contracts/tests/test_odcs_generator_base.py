"""
Unit tests for ODCS Generator Base Class.

Tests the ODCSGeneratorBase abstract class following TDD approach
and engineering best practices without mocks/stubs.
"""
import pytest
from django.test import TestCase
from abc import ABC

from hub.apps.contracts.odcs_generator import ODCSGeneratorBase
from hub.apps.contracts.odcs_errors import (
    ODCSGenerationError,
    ODCSExportError,
)

pytestmark = pytest.mark.django_db(transaction=True)


class ConcreteODCSGenerator(ODCSGeneratorBase):
    """Concrete implementation for testing the base class."""

    def generate_odcs_from_hubcontract(
        self,
        hub_contract: dict,
        target_version: str | None = None
    ) -> dict:
        """
        Concrete implementation for testing.

        Args:
            hub_contract: HubContract dictionary
            target_version: Target ODCS version (optional)

        Returns:
            ODCS document as dictionary
        """
        # Validate structure first
        self.validate_hub_contract_structure(hub_contract)

        # Generate minimal ODCS document
        contract_id = hub_contract["id"]
        name = hub_contract["info"]["name"]
        version = target_version or "3.0.2"

        self.log_generation_start(contract_id, name, version)

        odcs_doc = {
            "apiVersion": f"odcs.io/v{version}",
            "kind": "DataContract",
            "id": contract_id,
            "name": name,
        }

        # Add optional fields
        info = hub_contract["info"]
        if "version" in info and info["version"]:
            self.validate_field_type(info["version"], str, "/info/version", allow_none=False)
            odcs_doc["version"] = info["version"]

        if "description" in info and info["description"]:
            self.validate_field_type(info["description"], str, "/info/description", allow_none=False)
            odcs_doc["description"] = info["description"]

        self.log_generation_complete(contract_id, name, version)
        return odcs_doc


class ODCSGeneratorBaseStructureTest(TestCase):
    """Test ODCSGeneratorBase structure and abstract methods"""

    def test_is_abstract_base_class(self):
        """Test that ODCSGeneratorBase is an abstract base class"""
        self.assertTrue(issubclass(ODCSGeneratorBase, ABC))

    def test_cannot_instantiate_base_class_directly(self):
        """Test that base class cannot be instantiated directly"""
        with self.assertRaises(TypeError):
            ODCSGeneratorBase()

    def test_can_instantiate_concrete_subclass(self):
        """Test that concrete subclass can be instantiated"""
        generator = ConcreteODCSGenerator()
        self.assertIsInstance(generator, ODCSGeneratorBase)

    def test_has_logger_attribute(self):
        """Test that base class has logger attribute"""
        generator = ConcreteODCSGenerator()
        self.assertTrue(hasattr(generator, "logger"))
        self.assertIsNotNone(generator.logger)

    def test_requires_generate_odcs_from_hubcontract_implementation(self):
        """Test that subclasses must implement generate_odcs_from_hubcontract"""
        class IncompleteGenerator(ODCSGeneratorBase):
            pass

        with self.assertRaises(TypeError):
            IncompleteGenerator()


class ODCSGeneratorBaseValidationTest(TestCase):
    """Test ODCSGeneratorBase validation methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ConcreteODCSGenerator()
        self.valid_hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "description": "A test contract",
                "version": "1.0.0"
            },
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"}
                ]
            }
        }

    def test_validate_hub_contract_structure_with_valid_contract(self):
        """Test validation passes with valid HubContract"""
        # Should not raise any exception
        self.generator.validate_hub_contract_structure(self.valid_hub_contract)

    def test_validate_hub_contract_structure_with_non_dict(self):
        """Test validation fails when HubContract is not a dictionary"""
        invalid_contract = "not a dict"

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.validate_hub_contract_structure(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_GENERATION_FAILED)
        self.assertEqual(error.context["field_path"], "/")
        self.assertEqual(error.context["expected"], "dict")
        self.assertEqual(error.context["actual"], "str")

    def test_validate_hub_contract_structure_missing_info(self):
        """Test validation fails when 'info' section is missing"""
        invalid_contract = {
            "id": "test-contract-1"
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.validate_hub_contract_structure(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)
        self.assertEqual(error.context["field_path"], "/info")
        self.assertEqual(error.context["expected"], "dict")
        self.assertIsNone(error.context["actual"])

    def test_validate_hub_contract_structure_info_not_dict(self):
        """Test validation fails when 'info' is not a dictionary"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": "not a dict"
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.validate_hub_contract_structure(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_GENERATION_FAILED)
        self.assertEqual(error.context["field_path"], "/info")
        self.assertEqual(error.context["expected"], "dict")
        self.assertEqual(error.context["actual"], "str")

    def test_validate_hub_contract_structure_missing_name(self):
        """Test validation fails when 'info.name' is missing"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": {}
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.validate_hub_contract_structure(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)
        self.assertEqual(error.context["field_path"], "/info/name")
        self.assertEqual(error.context["expected"], "str")
        self.assertIsNone(error.context["actual"])

    def test_validate_hub_contract_structure_name_not_string(self):
        """Test validation fails when 'info.name' is not a string"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": {
                "name": 123
            }
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.validate_hub_contract_structure(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_GENERATION_FAILED)
        self.assertEqual(error.context["field_path"], "/info/name")
        self.assertEqual(error.context["expected"], "str (non-empty)")
        self.assertEqual(error.context["actual"], "int")

    def test_validate_hub_contract_structure_name_empty_string(self):
        """Test validation fails when 'info.name' is empty string"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": {
                "name": ""
            }
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.validate_hub_contract_structure(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_GENERATION_FAILED)
        self.assertEqual(error.context["field_path"], "/info/name")
        self.assertEqual(error.context["expected"], "str (non-empty)")

    def test_validate_hub_contract_structure_name_whitespace_only(self):
        """Test validation fails when 'info.name' is whitespace only"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "   "
            }
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.validate_hub_contract_structure(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_GENERATION_FAILED)
        self.assertEqual(error.context["field_path"], "/info/name")

    def test_validate_hub_contract_structure_missing_id(self):
        """Test validation fails when 'id' is missing"""
        invalid_contract = {
            "info": {
                "name": "Test Contract"
            }
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.validate_hub_contract_structure(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)
        self.assertEqual(error.context["field_path"], "/id")
        self.assertEqual(error.context["expected"], "str")
        self.assertIsNone(error.context["actual"])

    def test_validate_hub_contract_structure_id_not_string(self):
        """Test validation fails when 'id' is not a string"""
        invalid_contract = {
            "id": 123,
            "info": {
                "name": "Test Contract"
            }
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.validate_hub_contract_structure(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_GENERATION_FAILED)
        self.assertEqual(error.context["field_path"], "/id")
        self.assertEqual(error.context["expected"], "str")
        self.assertEqual(error.context["actual"], "int")

    def test_validate_field_type_with_valid_value(self):
        """Test field type validation passes with valid value"""
        # Should not raise any exception
        self.generator.validate_field_type("test", str, "/test/field")

    def test_validate_field_type_with_wrong_type(self):
        """Test field type validation fails with wrong type"""
        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.validate_field_type(123, str, "/test/field")

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_GENERATION_FAILED)
        self.assertEqual(error.context["field_path"], "/test/field")
        self.assertEqual(error.context["expected"], "str")
        self.assertEqual(error.context["actual"], "int")

    def test_validate_field_type_with_none_not_allowed(self):
        """Test field type validation fails when None is not allowed"""
        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.validate_field_type(None, str, "/test/field", allow_none=False)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)
        self.assertEqual(error.context["field_path"], "/test/field")
        self.assertEqual(error.context["expected"], "str")
        self.assertIsNone(error.context["actual"])

    def test_validate_field_type_with_none_allowed(self):
        """Test field type validation passes when None is allowed"""
        # Should not raise any exception
        self.generator.validate_field_type(None, str, "/test/field", allow_none=True)

    def test_validate_field_type_with_dict_type(self):
        """Test field type validation with dict type"""
        # Should not raise any exception
        self.generator.validate_field_type({"key": "value"}, dict, "/test/field")

    def test_validate_field_type_with_list_type(self):
        """Test field type validation with list type"""
        # Should not raise any exception
        self.generator.validate_field_type([1, 2, 3], list, "/test/field")


class ODCSGeneratorBaseGenerationTest(TestCase):
    """Test ODCSGeneratorBase generation methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ConcreteODCSGenerator()
        self.valid_hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "description": "A test contract",
                "version": "1.0.0"
            },
            "schema": {
                "fields": [
                    {"name": "field1", "type": "string"}
                ]
            }
        }

    def test_generate_odcs_from_hubcontract_with_valid_contract(self):
        """Test generation succeeds with valid HubContract"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(
            self.valid_hub_contract,
            target_version="3.0.2"
        )

        self.assertIsInstance(odcs_doc, dict)
        self.assertEqual(odcs_doc["id"], "test-contract-1")
        self.assertEqual(odcs_doc["name"], "Test Contract")
        self.assertEqual(odcs_doc["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(odcs_doc["kind"], "DataContract")
        self.assertEqual(odcs_doc["version"], "1.0.0")
        self.assertEqual(odcs_doc["description"], "A test contract")

    def test_generate_odcs_from_hubcontract_with_minimal_contract(self):
        """Test generation succeeds with minimal HubContract"""
        minimal_contract = {
            "id": "minimal-contract",
            "info": {
                "name": "Minimal Contract"
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(
            minimal_contract,
            target_version="3.0.2"
        )

        self.assertIsInstance(odcs_doc, dict)
        self.assertEqual(odcs_doc["id"], "minimal-contract")
        self.assertEqual(odcs_doc["name"], "Minimal Contract")
        self.assertNotIn("version", odcs_doc)
        self.assertNotIn("description", odcs_doc)

    def test_generate_odcs_from_hubcontract_with_invalid_structure(self):
        """Test generation fails with invalid HubContract structure"""
        invalid_contract = {
            "id": "test-contract-1"
            # Missing 'info' section
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)
        self.assertEqual(error.context["field_path"], "/info")

    def test_generate_odcs_from_hubcontract_with_missing_name(self):
        """Test generation fails when info.name is missing"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": {}
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)
        self.assertEqual(error.context["field_path"], "/info/name")

    def test_generate_odcs_from_hubcontract_with_missing_id(self):
        """Test generation fails when id is missing"""
        invalid_contract = {
            "info": {
                "name": "Test Contract"
            }
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)
        self.assertEqual(error.context["field_path"], "/id")

    def test_generate_odcs_from_hubcontract_with_invalid_version_type(self):
        """Test generation fails when info.version has wrong type"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "version": 123  # Should be string
            }
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_GENERATION_FAILED)
        self.assertEqual(error.context["field_path"], "/info/version")
        self.assertEqual(error.context["expected"], "str")

    def test_generate_odcs_from_hubcontract_with_invalid_description_type(self):
        """Test generation fails when info.description has wrong type"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "description": 123  # Should be string
            }
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_GENERATION_FAILED)
        self.assertEqual(error.context["field_path"], "/info/description")
        self.assertEqual(error.context["expected"], "str")


class ODCSGeneratorBaseLoggingTest(TestCase):
    """Test ODCSGeneratorBase logging methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ConcreteODCSGenerator()

    def test_log_generation_start(self):
        """Test log_generation_start method exists and can be called"""
        # Should not raise any exception
        self.generator.log_generation_start(
            contract_id="test-1",
            name="Test Contract",
            target_version="3.0.2"
        )

    def test_log_generation_complete(self):
        """Test log_generation_complete method exists and can be called"""
        # Should not raise any exception
        self.generator.log_generation_complete(
            contract_id="test-1",
            name="Test Contract",
            target_version="3.0.2"
        )

    def test_log_generation_error(self):
        """Test log_generation_error method exists and can be called"""
        # Should not raise any exception
        error = ValueError("Test error")
        self.generator.log_generation_error(
            error=error,
            contract_id="test-1",
            field_path="/test/field"
        )

