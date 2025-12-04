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
    detect_spec_type,
    _calculate_normalization_coverage
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


class FieldPropertyExtractionTest(TestCase):
    """Test complete field property extraction (7.1.1.3)"""
    
    def test_odcs_extract_all_field_properties(self):
        """Test extracting all field properties from ODCS"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {
                        "name": "email",
                        "type": "string",
                        "nullable": False,
                        "description": "User email address",
                        "semantic_type": "EMAIL",
                        "format": "email",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                        "enum": None,
                        "default": None,
                        "min_length": 5,
                        "max_length": 255,
                        "minimum": None,
                        "maximum": None,
                        "metadata": {
                            "source_system": "CRM",
                            "pii": True
                        }
                    },
                    {
                        "name": "age",
                        "type": "integer",
                        "nullable": True,
                        "description": "User age",
                        "minimum": 0,
                        "maximum": 150,
                        "default": 0
                    },
                    {
                        "name": "status",
                        "type": "string",
                        "nullable": False,
                        "enum": ["active", "inactive", "pending"]
                    }
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(len(fields), 3)
        
        # Check first field (email) has all properties
        email_field = fields[0]
        self.assertEqual(email_field["name"], "email")
        self.assertEqual(email_field["data_type"], "string")
        self.assertEqual(email_field["nullable"], False)
        self.assertEqual(email_field["description"], "User email address")
        self.assertEqual(email_field["semantic_type"], "EMAIL")
        self.assertEqual(email_field["format"], "email")
        self.assertEqual(email_field["pattern"], "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
        self.assertEqual(email_field["min_length"], 5)
        self.assertEqual(email_field["max_length"], 255)
        self.assertIn("metadata", email_field)
        self.assertEqual(email_field["metadata"]["source_system"], "CRM")
        
        # Check second field (age) has numeric constraints
        age_field = fields[1]
        self.assertEqual(age_field["name"], "age")
        self.assertEqual(age_field["data_type"], "integer")
        self.assertEqual(age_field["minimum"], 0)
        self.assertEqual(age_field["maximum"], 150)
        self.assertEqual(age_field["default"], 0)
        
        # Check third field (status) has enum
        status_field = fields[2]
        self.assertEqual(status_field["name"], "status")
        self.assertEqual(status_field["enum"], ["active", "inactive", "pending"])
    
    def test_datacontract_com_extract_all_field_properties(self):
        """Test extracting all field properties from DataContract.com"""
        dc_contract = {
            "id": "test",
            "dataContractSpecification": "0.4.0",
            "info": {
                "title": "Test Contract"
            },
            "schema": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "User email address",
                        "format": "email",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                        "minLength": 5,
                        "maxLength": 255,
                        "x-datahub": {
                            "semantic_type": "EMAIL",
                            "metadata": {
                                "source_system": "CRM"
                            }
                        }
                    },
                    "age": {
                        "type": "integer",
                        "description": "User age",
                        "minimum": 0,
                        "maximum": 150,
                        "default": 0
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "inactive", "pending"]
                    }
                },
                "required": ["email", "status"]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(dc_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(len(fields), 3)
        
        # Check first field (email) has all properties
        email_field = fields[0]
        self.assertEqual(email_field["name"], "email")
        self.assertEqual(email_field["data_type"], "string")
        self.assertEqual(email_field["nullable"], False)  # In required list
        self.assertEqual(email_field["description"], "User email address")
        self.assertEqual(email_field["semantic_type"], "EMAIL")
        self.assertEqual(email_field["format"], "email")
        self.assertEqual(email_field["pattern"], "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
        self.assertEqual(email_field["min_length"], 5)
        self.assertEqual(email_field["max_length"], 255)
        self.assertIn("metadata", email_field)
        self.assertEqual(email_field["metadata"]["source_system"], "CRM")
        
        # Check second field (age) has numeric constraints
        age_field = fields[1]
        self.assertEqual(age_field["name"], "age")
        self.assertEqual(age_field["data_type"], "integer")
        self.assertEqual(age_field["nullable"], True)  # Not in required list
        self.assertEqual(age_field["minimum"], 0)
        self.assertEqual(age_field["maximum"], 150)
        self.assertEqual(age_field["default"], 0)
        
        # Check third field (status) has enum and is not nullable
        status_field = fields[2]
        self.assertEqual(status_field["name"], "status")
        self.assertEqual(status_field["nullable"], False)  # In required list
        self.assertEqual(status_field["enum"], ["active", "inactive", "pending"])
    
    def test_field_properties_preserved_in_hubcontract(self):
        """Test that all field properties are preserved in HubContract schema.fields[] array"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {
                        "name": "test_field",
                        "type": "string",
                        "nullable": True,
                        "description": "Test field",
                        "semantic_type": "TEST_TYPE",
                        "format": "uri",
                        "pattern": ".*",
                        "enum": ["value1", "value2"],
                        "default": "value1",
                        "min_length": 1,
                        "max_length": 100,
                        "minimum": 0,
                        "maximum": 100,
                        "metadata": {"key": "value"}
                    }
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        field = hub_contract["schema"]["fields"][0]
        
        # Verify all properties are present
        self.assertEqual(field["name"], "test_field")
        self.assertEqual(field["data_type"], "string")
        self.assertEqual(field["nullable"], True)
        self.assertEqual(field["description"], "Test field")
        self.assertEqual(field["semantic_type"], "TEST_TYPE")
        self.assertEqual(field["format"], "uri")
        self.assertEqual(field["pattern"], ".*")
        self.assertEqual(field["enum"], ["value1", "value2"])
        self.assertEqual(field["default"], "value1")
        self.assertEqual(field["min_length"], 1)
        self.assertEqual(field["max_length"], 100)
        self.assertEqual(field["minimum"], 0)
        self.assertEqual(field["maximum"], 100)
        self.assertEqual(field["metadata"], {"key": "value"})


class NormalizationStatusTest(TestCase):
    """Test normalization status accuracy (7.1.3.3)"""
    
    def test_status_normalized_ok_all_sections_mapped(self):
        """Test NORMALIZED_OK status when all sections successfully mapped"""
        odcs_contract = {
            "id": "test",
            "name": "Test Contract",
            "description": "Test description",
            "version": "1.0.0",
            "info": {
                "owners": [{"name": "Owner", "email": "owner@example.com"}],
                "tags": ["tag1", "tag2"]
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ],
                "primary_key": ["id"]
            },
            "quality": {
                "default_profile_key": "basic",
                "rules": [
                    {
                        "rule_id": "rule1",
                        "dimension": "completeness",
                        "expression": "id IS NOT NULL",
                        "severity": "ERROR"
                    }
                ]
            },
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL"],
                "jurisdictions": ["GDPR"],
                "legal_bases": ["CONSENT"],
                "retention_policy": {"period": "P5Y", "notes": "5 years"}
            },
            "lifecycle": {
                "data_source": "source",
                "refresh_cadence": "DAILY",
                "slas": {"availability": "99.0", "latency_ms_p95": 5000}
            },
            "marketplace": {
                "license_summary": "Internal only",
                "intended_use": ["analytics"],
                "restricted_use": ["marketing"]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)
    
    def test_status_normalized_with_warnings_extensions_present(self):
        """Test NORMALIZED_WITH_WARNINGS status when extensions present"""
        odcs_contract = {
            "id": "test",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            },
            "unmappable_field": "unmappable_value"
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_WITH_WARNINGS)
        self.assertGreater(len(warnings), 0)
        self.assertIn("extensions", hub_contract)
    
    def test_status_normalization_failed_missing_critical_sections(self):
        """Test NORMALIZATION_FAILED status when critical sections missing"""
        # Missing schema.fields
        odcs_contract = {
            "id": "test",
            "name": "Test Contract",
            "schema": {}
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)
    
    def test_status_normalization_failed_missing_info_name(self):
        """Test NORMALIZATION_FAILED status when info.name missing"""
        odcs_contract = {
            "id": "test",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"}
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        # Empty name should cause FAILED status
        self.assertIsNotNone(hub_contract)
        self.assertFalse(hub_contract.get("info", {}).get("name"))  # Name is empty string
        self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)
    
    def test_status_normalization_failed_empty_fields(self):
        """Test NORMALIZATION_FAILED status when fields array is empty"""
        odcs_contract = {
            "id": "test",
            "name": "Test Contract",
            "schema": {
                "fields": []
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)
    
    def test_status_normalization_failed_exception(self):
        """Test NORMALIZATION_FAILED status when exception occurs"""
        # Invalid contract structure that will cause exception
        odcs_contract = None
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(errors), 0)
    
    def test_normalization_coverage_calculation(self):
        """Test normalization coverage metrics calculation"""
        # Contract with all sections
        full_contract = {
            "hub_contract_version": 1,
            "id": "test",
            "info": {
                "name": "Test",
                "description": "Description",
                "version": "1.0.0",
                "owners": [{"name": "Owner", "email": "owner@example.com"}],
                "tags": ["tag1"]
            },
            "schema": {
                "fields": [{"name": "id", "data_type": "string"}],
                "primary_key": ["id"],
                "unique_constraints": [],
                "indexes": []
            },
            "quality": {
                "default_profile_key": "basic",
                "rules": []
            },
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL"],
                "jurisdictions": ["GDPR"],
                "legal_bases": ["CONSENT"],
                "retention_policy": {"period": "P5Y"}
            },
            "lifecycle": {
                "data_source": "source",
                "refresh_cadence": "DAILY",
                "slas": {"availability": "99.0"}
            },
            "marketplace": {
                "license_summary": "Internal",
                "intended_use": ["analytics"],
                "restricted_use": []
            }
        }
        
        coverage = _calculate_normalization_coverage(full_contract)
        
        # Coverage should be high (most sections present)
        self.assertGreater(coverage, 0.5)
        self.assertLessEqual(coverage, 1.0)
        
        # Contract with minimal sections
        minimal_contract = {
            "hub_contract_version": 1,
            "id": "test",
            "info": {
                "name": "Test"
            },
            "schema": {
                "fields": [{"name": "id", "data_type": "string"}]
            }
        }
        
        minimal_coverage = _calculate_normalization_coverage(minimal_contract)
        
        # Minimal contract should have lower coverage
        self.assertLess(minimal_coverage, coverage)
        self.assertGreater(minimal_coverage, 0.0)

