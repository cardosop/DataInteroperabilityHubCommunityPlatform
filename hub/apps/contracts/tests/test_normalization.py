"""
Unit tests for contract normalization.
"""
import pytest
from django.test import TestCase
from hub.apps.contracts.normalization import (
    normalize_contract,
    normalize_odcs_to_hubcontract,
    normalize_datacontract_com_to_hubcontract,
    validate_hubcontract_schema,
    detect_spec_type
)
from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType



pytestmark = pytest.mark.django_db(transaction=True)
class NormalizationTest(TestCase):
    """Test contract normalization"""
    
    def test_detect_spec_type_odcs(self):
        """Test detecting ODCS spec type"""
        contract_data = {
            "id": "test",
            "name": "Test",
            "odcs_version": "3.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"}
                ]
            }
        }
        
        spec_type, spec_version = detect_spec_type(contract_data)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
    
    def test_detect_spec_type_datacontract_com(self):
        """Test detecting DataContract.com spec type"""
        contract_data = {
            "id": "test",
            "dataContractSpecification": "0.4.0",
            "info": {
                "title": "Test Contract"
            },
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"}
                }
            }
        }
        
        spec_type, spec_version = detect_spec_type(contract_data)
        self.assertEqual(spec_type, OriginalSpecType.DATACONTRACT_COM)
    
    def test_normalize_odcs_to_hubcontract(self):
        """Test normalizing ODCS contract to HubContract"""
        odcs_contract = {
            "id": "test-contract",
            "name": "Test Contract",
            "description": "Test description",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": True}
                ],
                "primary_key": ["id"]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(hub_contract["hub_contract_version"], 1)
        self.assertEqual(hub_contract["id"], "test-contract")
        self.assertEqual(hub_contract["info"]["name"], "Test Contract")
        self.assertIn("fields", hub_contract["schema"])
        self.assertEqual(len(hub_contract["schema"]["fields"]), 2)
    
    def test_normalize_datacontract_com_to_hubcontract(self):
        """Test normalizing DataContract.com contract to HubContract"""
        dc_contract = {
            "id": "test-contract",
            "dataContractSpecification": "0.4.0",
            "info": {
                "title": "Test Contract",
                "description": "Test description",
                "version": "1.0.0"
            },
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string", "description": "Name field"}
                },
                "required": ["id"]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(dc_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(hub_contract["hub_contract_version"], 1)
        self.assertEqual(hub_contract["id"], "test-contract")
        self.assertEqual(hub_contract["info"]["name"], "Test Contract")
        self.assertIn("fields", hub_contract["schema"])
        self.assertEqual(len(hub_contract["schema"]["fields"]), 2)
    
    def test_normalize_contract_json(self):
        """Test normalizing contract from JSON"""
        import json
        
        contract_data = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"}
                ]
            }
        }
        
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(contract_data),
            format="JSON"
        )
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
    
    def test_normalize_contract_yaml(self):
        """Test normalizing contract from YAML"""
        yaml_content = """
id: test
name: Test
schema:
  fields:
    - name: id
      type: string
"""
        
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=yaml_content,
            format="YAML"
        )
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
    
    def test_validate_hubcontract_schema_valid(self):
        """Test validating a valid HubContract"""
        hub_contract = {
            "hub_contract_version": 1,
            "id": "test-contract",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"}
                ]
            }
        }
        
        is_valid, errors = validate_hubcontract_schema(hub_contract)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
    
    def test_validate_hubcontract_schema_invalid(self):
        """Test validating an invalid HubContract"""
        hub_contract = {
            "id": "test-contract",
            # Missing hub_contract_version
            # Missing info
            # Missing schema
        }
        
        is_valid, errors = validate_hubcontract_schema(hub_contract)
        
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
    
    def test_normalize_contract_with_extensions(self):
        """Test normalization preserves unmappable fields in extensions"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "custom_field": "custom_value",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"}
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertIn("extensions", hub_contract)
        self.assertIn("odcs", hub_contract["extensions"])
        self.assertIn("custom_field", hub_contract["extensions"]["odcs"])
        self.assertEqual(hub_contract["extensions"]["odcs"]["custom_field"], "custom_value")
        self.assertEqual(status, NormalizationStatus.NORMALIZED_WITH_WARNINGS)

