"""
Enhanced Unit Tests for Contract Normalization.

Tests complete field property extraction, complete section normalization,
normalization status tracking, and information preservation.
Uses real normalization functions (no mocks).
"""
import pytest
import json
from django.test import TestCase

from hub.apps.contracts.normalization import (
    normalize_odcs_to_hubcontract,
    normalize_datacontract_com_to_hubcontract,
    normalize_contract,
    _determine_normalization_status,
    _calculate_normalization_coverage,
    detect_spec_type,
)
from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced

pytestmark = pytest.mark.django_db(transaction=True)


class EnhancedNormalizationTest(TestCase):
    """Enhanced normalization tests with complete field property extraction"""
    
    # Field Property Extraction Tests - ODCS
    def test_extract_semantic_type_from_odcs(self):
        """Test extracting semantic_type from ODCS structure"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {
                        "name": "email",
                        "type": "string",
                        "semantic_type": "EMAIL"
                    },
                    {
                        "name": "phone",
                        "type": "string",
                        "semantic_type": "PHONE"
                    }
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["semantic_type"], "EMAIL")
        self.assertEqual(fields[1]["semantic_type"], "PHONE")
    
    def test_extract_format_from_odcs(self):
        """Test extracting format from ODCS"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {
                        "name": "email",
                        "type": "string",
                        "format": "email"
                    },
                    {
                        "name": "uri",
                        "type": "string",
                        "format": "uri"
                    },
                    {
                        "name": "date",
                        "type": "string",
                        "format": "date"
                    },
                    {
                        "name": "datetime",
                        "type": "string",
                        "format": "date-time"
                    }
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["format"], "email")
        self.assertEqual(fields[1]["format"], "uri")
        self.assertEqual(fields[2]["format"], "date")
        self.assertEqual(fields[3]["format"], "date-time")
    
    def test_extract_pattern_from_odcs(self):
        """Test extracting pattern (regex) from ODCS"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {
                        "name": "email",
                        "type": "string",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
                    },
                    {
                        "name": "order_id",
                        "type": "string",
                        "pattern": "^[A-Z0-9]{8}$"
                    }
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["pattern"], "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
        self.assertEqual(fields[1]["pattern"], "^[A-Z0-9]{8}$")
    
    def test_extract_enum_from_odcs(self):
        """Test extracting enum (array of allowed values) from ODCS"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {
                        "name": "status",
                        "type": "string",
                        "enum": ["active", "inactive", "pending"]
                    },
                    {
                        "name": "priority",
                        "type": "string",
                        "enum": ["low", "medium", "high"]
                    }
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["enum"], ["active", "inactive", "pending"])
        self.assertEqual(fields[1]["enum"], ["low", "medium", "high"])
    
    def test_extract_default_from_odcs(self):
        """Test extracting default value from ODCS"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {
                        "name": "status",
                        "type": "string",
                        "default": "pending"
                    },
                    {
                        "name": "count",
                        "type": "integer",
                        "default": 0
                    },
                    {
                        "name": "enabled",
                        "type": "boolean",
                        "default": True
                    }
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["default"], "pending")
        self.assertEqual(fields[1]["default"], 0)
        self.assertEqual(fields[2]["default"], True)
    
    def test_extract_min_max_length_from_odcs(self):
        """Test extracting min_length and max_length from ODCS"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {
                        "name": "short_field",
                        "type": "string",
                        "min_length": 1,
                        "max_length": 10
                    },
                    {
                        "name": "long_field",
                        "type": "string",
                        "minLength": 5,  # Test camelCase variant
                        "maxLength": 255  # Test camelCase variant
                    }
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["min_length"], 1)
        self.assertEqual(fields[0]["max_length"], 10)
        self.assertEqual(fields[1]["min_length"], 5)
        self.assertEqual(fields[1]["max_length"], 255)
    
    def test_extract_min_max_numeric_from_odcs(self):
        """Test extracting minimum and maximum numeric values from ODCS"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {
                        "name": "age",
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 150
                    },
                    {
                        "name": "price",
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 10000.0
                    }
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["minimum"], 0)
        self.assertEqual(fields[0]["maximum"], 150)
        self.assertEqual(fields[1]["minimum"], 0.0)
        self.assertEqual(fields[1]["maximum"], 10000.0)
    
    def test_extract_metadata_from_odcs(self):
        """Test extracting metadata from ODCS"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "string",
                        "metadata": {
                            "source_system": "CRM",
                            "pii": True,
                            "sensitive": False
                        }
                    }
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        field = hub_contract["schema"]["fields"][0]
        self.assertIn("metadata", field)
        self.assertEqual(field["metadata"]["source_system"], "CRM")
        self.assertEqual(field["metadata"]["pii"], True)
        self.assertEqual(field["metadata"]["sensitive"], False)
    
    # Field Property Extraction Tests - DataContract.com
    def test_extract_semantic_type_from_datacontract_com(self):
        """Test extracting semantic_type from DataContract.com (x-datahub extension)"""
        dc_contract = {
            "id": "test",
            "dataContractSpecification": "0.4.0",
            "info": {"title": "Test"},
            "schema": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "x-datahub": {
                            "semantic_type": "EMAIL"
                        }
                    },
                    "phone": {
                        "type": "string",
                        "semantic_type": "PHONE"  # Direct field
                    }
                }
            }
        }
        
        hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(dc_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["semantic_type"], "EMAIL")
        self.assertEqual(fields[1]["semantic_type"], "PHONE")
    
    def test_extract_format_from_datacontract_com(self):
        """Test extracting format from DataContract.com JSON Schema"""
        dc_contract = {
            "id": "test",
            "dataContractSpecification": "0.4.0",
            "info": {"title": "Test"},
            "schema": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "uri": {"type": "string", "format": "uri"},
                    "date": {"type": "string", "format": "date"},
                    "datetime": {"type": "string", "format": "date-time"},
                    "uuid": {"type": "string", "format": "uuid"}
                }
            }
        }
        
        hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(dc_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["format"], "email")
        self.assertEqual(fields[1]["format"], "uri")
        self.assertEqual(fields[2]["format"], "date")
        self.assertEqual(fields[3]["format"], "date-time")
        self.assertEqual(fields[4]["format"], "uuid")
    
    def test_extract_pattern_from_datacontract_com(self):
        """Test extracting pattern from DataContract.com"""
        dc_contract = {
            "id": "test",
            "dataContractSpecification": "0.4.0",
            "info": {"title": "Test"},
            "schema": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
                    }
                }
            }
        }
        
        hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(dc_contract)
        
        self.assertIsNotNone(hub_contract)
        field = hub_contract["schema"]["fields"][0]
        self.assertEqual(field["pattern"], "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
    
    def test_extract_enum_from_datacontract_com(self):
        """Test extracting enum from DataContract.com"""
        dc_contract = {
            "id": "test",
            "dataContractSpecification": "0.4.0",
            "info": {"title": "Test"},
            "schema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "inactive", "pending"]
                    }
                }
            }
        }
        
        hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(dc_contract)
        
        self.assertIsNotNone(hub_contract)
        field = hub_contract["schema"]["fields"][0]
        self.assertEqual(field["enum"], ["active", "inactive", "pending"])
    
    def test_extract_default_from_datacontract_com(self):
        """Test extracting default from DataContract.com"""
        dc_contract = {
            "id": "test",
            "dataContractSpecification": "0.4.0",
            "info": {"title": "Test"},
            "schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "default": "pending"},
                    "count": {"type": "integer", "default": 0},
                    "enabled": {"type": "boolean", "default": True}
                }
            }
        }
        
        hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(dc_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["default"], "pending")
        self.assertEqual(fields[1]["default"], 0)
        self.assertEqual(fields[2]["default"], True)
    
    def test_extract_min_max_length_from_datacontract_com(self):
        """Test extracting minLength and maxLength from DataContract.com"""
        dc_contract = {
            "id": "test",
            "dataContractSpecification": "0.4.0",
            "info": {"title": "Test"},
            "schema": {
                "type": "object",
                "properties": {
                    "short_field": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 10
                    },
                    "long_field": {
                        "type": "string",
                        "minLength": 5,
                        "maxLength": 255
                    }
                }
            }
        }
        
        hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(dc_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["min_length"], 1)
        self.assertEqual(fields[0]["max_length"], 10)
        self.assertEqual(fields[1]["min_length"], 5)
        self.assertEqual(fields[1]["max_length"], 255)
    
    def test_extract_min_max_numeric_from_datacontract_com(self):
        """Test extracting minimum and maximum from DataContract.com"""
        dc_contract = {
            "id": "test",
            "dataContractSpecification": "0.4.0",
            "info": {"title": "Test"},
            "schema": {
                "type": "object",
                "properties": {
                    "age": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 150
                    },
                    "price": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 10000.0
                    }
                }
            }
        }
        
        hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(dc_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["minimum"], 0)
        self.assertEqual(fields[0]["maximum"], 150)
        self.assertEqual(fields[1]["minimum"], 0.0)
        self.assertEqual(fields[1]["maximum"], 10000.0)
    
    def test_extract_metadata_from_datacontract_com(self):
        """Test extracting metadata from DataContract.com (x-datahub extension)"""
        dc_contract = {
            "id": "test",
            "dataContractSpecification": "0.4.0",
            "info": {"title": "Test"},
            "schema": {
                "type": "object",
                "properties": {
                    "field1": {
                        "type": "string",
                        "x-datahub": {
                            "metadata": {
                                "source_system": "CRM",
                                "pii": True
                            }
                        }
                    },
                    "field2": {
                        "type": "string",
                        "metadata": {
                            "source_system": "ERP"
                        }
                    }
                }
            }
        }
        
        hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(dc_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertIn("metadata", fields[0])
        self.assertEqual(fields[0]["metadata"]["source_system"], "CRM")
        self.assertEqual(fields[0]["metadata"]["pii"], True)
        self.assertIn("metadata", fields[1])
        self.assertEqual(fields[1]["metadata"]["source_system"], "ERP")
    
    # Complete Section Normalization Tests
    def test_normalize_info_section_complete(self):
        """Test complete info section normalization"""
        odcs_contract = {
            "id": "test-contract",
            "name": "Test Contract",
            "description": "Test description",
            "version": "1.0.0",
            "info": {
                "owners": [
                    {"name": "Owner 1", "email": "owner1@example.com"},
                    {"name": "Owner 2", "email": "owner2@example.com"}
                ],
                "tags": ["tag1", "tag2", "tag3"]
            },
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(hub_contract["info"]["name"], "Test Contract")
        self.assertEqual(hub_contract["info"]["description"], "Test description")
        self.assertEqual(hub_contract["info"]["version"], "1.0.0")
        self.assertEqual(len(hub_contract["info"]["owners"]), 2)
        self.assertEqual(len(hub_contract["info"]["tags"]), 3)
    
    def test_normalize_schema_section_complete(self):
        """Test complete schema section normalization with constraints"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "email", "type": "string", "nullable": True},
                    {"name": "name", "type": "string", "nullable": False}
                ],
                "primary_key": ["id"],
                "unique_constraints": [["email"], ["name"]],
                "indexes": [
                    {"name": "idx_email", "fields": ["email"]},
                    ["name"]
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        schema = hub_contract["schema"]
        self.assertEqual(schema["primary_key"], ["id"])
        self.assertEqual(len(schema["unique_constraints"]), 2)
        self.assertEqual(len(schema["indexes"]), 2)
        
        # Verify field constraint flags
        fields = schema["fields"]
        self.assertTrue(fields[0]["is_primary_key"])  # id
        self.assertTrue(fields[1]["is_unique"])  # email
        self.assertTrue(fields[2]["is_unique"])  # name
        self.assertTrue(fields[1]["is_indexed"])  # email
        self.assertTrue(fields[2]["is_indexed"])  # name
    
    def test_normalize_quality_section_complete(self):
        """Test complete quality section normalization"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            },
            "quality": {
                "default_profile_key": "intake_basic_soda",
                "rules": [
                    {
                        "rule_id": "not_null_id",
                        "dimension": "completeness",
                        "expression": "id IS NOT NULL",
                        "severity": "ERROR",
                        "field": "id"
                    },
                    {
                        "rule_id": "valid_email",
                        "dimension": "validity",
                        "expression": "email REGEXP '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'",
                        "severity": "WARNING",
                        "field": "email"
                    }
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        quality = hub_contract["quality"]
        self.assertEqual(quality["default_profile_key"], "intake_basic_soda")
        self.assertEqual(len(quality["rules"]), 2)
        self.assertEqual(quality["rules"][0]["rule_id"], "not_null_id")
        self.assertEqual(quality["rules"][1]["rule_id"], "valid_email")
    
    def test_normalize_privacy_compliance_section_complete(self):
        """Test complete privacy_compliance section normalization"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            },
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL", "PII_DIRECT_PHONE"],
                "jurisdictions": ["GDPR", "LGPD", "CCPA"],
                "legal_bases": ["CONSENT", "LEGITIMATE_INTEREST"],
                "retention_policy": {
                    "period": "P5Y",
                    "notes": "5 years retention"
                }
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        compliance = hub_contract["privacy_compliance"]
        self.assertEqual(compliance["contains_personal_data"], True)
        self.assertEqual(len(compliance["personal_data_categories"]), 2)
        self.assertEqual(len(compliance["jurisdictions"]), 3)
        self.assertEqual(len(compliance["legal_bases"]), 2)
        self.assertIsNotNone(compliance["retention_policy"])
        self.assertEqual(compliance["retention_policy"]["period"], "P5Y")
    
    def test_normalize_lifecycle_section_complete(self):
        """Test complete lifecycle section normalization"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            },
            "lifecycle": {
                "data_source": "source.system.com",
                "refresh_cadence": "DAILY",
                "slas": {
                    "availability": "99.9",
                    "latency_ms_p95": 5000,
                    "latency_ms_p99": 10000
                }
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        lifecycle = hub_contract["lifecycle"]
        self.assertEqual(lifecycle["data_source"], "source.system.com")
        self.assertEqual(lifecycle["refresh_cadence"], "DAILY")
        self.assertEqual(lifecycle["slas"]["availability"], "99.9")
        self.assertEqual(lifecycle["slas"]["latency_ms_p95"], 5000)
    
    def test_normalize_marketplace_section_complete(self):
        """Test complete marketplace section normalization"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            },
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["analytics", "reporting", "machine_learning"],
                "restricted_use": ["resale", "competitive_analysis"]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        marketplace = hub_contract["marketplace"]
        self.assertEqual(marketplace["license_summary"], "MIT License")
        self.assertEqual(len(marketplace["intended_use"]), 3)
        self.assertEqual(len(marketplace["restricted_use"]), 2)
    
    # Normalization Status Tracking Tests
    def test_status_normalized_ok_all_sections(self):
        """Test NORMALIZED_OK status when all sections successfully mapped"""
        odcs_contract = {
            "id": "test",
            "name": "Test Contract",
            "schema": {
                "fields": [{"name": "id", "type": "string", "nullable": False}]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)
    
    def test_status_normalized_with_warnings_extensions(self):
        """Test NORMALIZED_WITH_WARNINGS status when extensions present"""
        odcs_contract = {
            "id": "test",
            "name": "Test Contract",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            },
            "unmappable_field": "value"
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_WITH_WARNINGS)
        self.assertGreater(len(warnings), 0)
        self.assertIn("extensions", hub_contract)
    
    def test_status_normalization_failed_missing_name(self):
        """Test NORMALIZATION_FAILED status when name is missing"""
        odcs_contract = {
            "id": "test",
            "name": "",  # Empty name
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)
    
    def test_status_normalization_failed_missing_fields(self):
        """Test NORMALIZATION_FAILED status when fields are missing"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": []  # Empty fields
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)
    
    def test_status_normalization_failed_exception(self):
        """Test NORMALIZATION_FAILED status when exception occurs"""
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(None)
        
        self.assertIsNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(errors), 0)
    
    # Information Preservation Tests
    def test_extensions_preserve_unmappable_fields(self):
        """Test that unmappable fields are preserved in extensions"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            },
            "custom_field_1": "value1",
            "custom_field_2": {"nested": "value"},
            "custom_array": [1, 2, 3]
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertIn("extensions", hub_contract)
        self.assertIn("odcs", hub_contract["extensions"])
        extensions = hub_contract["extensions"]["odcs"]
        self.assertEqual(extensions["custom_field_1"], "value1")
        self.assertEqual(extensions["custom_field_2"]["nested"], "value")
        self.assertEqual(extensions["custom_array"], [1, 2, 3])
    
    def test_extensions_preserve_datacontract_com_unmappable(self):
        """Test that unmappable DataContract.com fields are preserved"""
        dc_contract = {
            "id": "test",
            "dataContractSpecification": "0.4.0",
            "info": {"title": "Test"},
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"}
                }
            },
            "custom_field": "value",
            "x-custom-extension": {"key": "value"}
        }
        
        hub_contract, status, errors, warnings = normalize_datacontract_com_to_hubcontract(dc_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertIn("extensions", hub_contract)
        self.assertIn("datacontract_com", hub_contract["extensions"])
        extensions = hub_contract["extensions"]["datacontract_com"]
        self.assertEqual(extensions["custom_field"], "value")
        self.assertEqual(extensions["x-custom-extension"]["key"], "value")
    
    # Complete Contract Normalization Tests
    def test_normalize_complete_contract_all_sections(self):
        """Test normalizing complete contract with all sections"""
        odcs_contract = {
            "id": "complete-contract",
            "name": "Complete Contract",
            "description": "Complete contract description",
            "version": "2.0.0",
            "info": {
                "owners": [
                    {"name": "Data Team", "email": "data@example.com"}
                ],
                "tags": ["production", "analytics"]
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False,
                        "description": "Primary key",
                        "semantic_type": "ORDER_ID",
                        "format": "uuid",
                        "is_primary_key": True
                    },
                    {
                        "name": "email",
                        "type": "string",
                        "nullable": False,
                        "description": "User email",
                        "semantic_type": "EMAIL",
                        "format": "email",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                        "min_length": 5,
                        "max_length": 255,
                        "is_unique": True
                    }
                ],
                "primary_key": ["id"],
                "unique_constraints": [["email"]],
                "indexes": [{"name": "idx_email", "fields": ["email"]}]
            },
            "quality": {
                "default_profile_key": "intake_basic_soda",
                "rules": [
                    {
                        "rule_id": "not_null_id",
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
                "retention_policy": {"period": "P3Y"}
            },
            "lifecycle": {
                "data_source": "source.example.com",
                "refresh_cadence": "HOURLY",
                "slas": {
                    "availability": "99.9",
                    "latency_ms_p95": 1000
                }
            },
            "marketplace": {
                "license_summary": "Apache 2.0",
                "intended_use": ["analytics"],
                "restricted_use": []
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        
        # Verify all sections are present
        self.assertIn("info", hub_contract)
        self.assertIn("schema", hub_contract)
        self.assertIn("quality", hub_contract)
        self.assertIn("privacy_compliance", hub_contract)
        self.assertIn("lifecycle", hub_contract)
        self.assertIn("marketplace", hub_contract)
        
        # Verify info section
        self.assertEqual(hub_contract["info"]["name"], "Complete Contract")
        self.assertEqual(len(hub_contract["info"]["owners"]), 1)
        self.assertEqual(len(hub_contract["info"]["tags"]), 2)
        
        # Verify schema section
        self.assertEqual(len(hub_contract["schema"]["fields"]), 2)
        self.assertEqual(hub_contract["schema"]["primary_key"], ["id"])
        
        # Verify quality section
        self.assertEqual(hub_contract["quality"]["default_profile_key"], "intake_basic_soda")
        self.assertEqual(len(hub_contract["quality"]["rules"]), 1)
        
        # Verify compliance section
        self.assertEqual(hub_contract["privacy_compliance"]["contains_personal_data"], True)
        
        # Verify lifecycle section
        self.assertEqual(hub_contract["lifecycle"]["data_source"], "source.example.com")
        
        # Verify marketplace section
        self.assertEqual(hub_contract["marketplace"]["license_summary"], "Apache 2.0")
    
    def test_normalize_coverage_calculation(self):
        """Test normalization coverage calculation"""
        # Contract with all sections
        full_contract = ContractFactoryEnhanced.create_hub_contract_json()
        coverage = _calculate_normalization_coverage(full_contract)
        
        self.assertGreater(coverage, 0.5)
        self.assertLessEqual(coverage, 1.0)
        
        # Minimal contract
        minimal_contract = {
            "hub_contract_version": 1,
            "id": "test",
            "info": {"name": "Test"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]}
        }
        minimal_coverage = _calculate_normalization_coverage(minimal_contract)
        
        self.assertLess(minimal_coverage, coverage)
        self.assertGreater(minimal_coverage, 0.0)
    
    # Edge Cases
    def test_normalize_with_nullable_fields(self):
        """Test normalization with nullable and non-nullable fields"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {"name": "required_field", "type": "string", "nullable": False},
                    {"name": "optional_field", "type": "string", "nullable": True},
                    {"name": "default_nullable", "type": "string", "nullable": True, "default": None}
                ]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        fields = hub_contract["schema"]["fields"]
        self.assertEqual(fields[0]["nullable"], False)
        self.assertEqual(fields[1]["nullable"], True)
        self.assertEqual(fields[2]["nullable"], True)
    
    def test_normalize_with_all_field_properties_combined(self):
        """Test normalization with all field properties combined"""
        odcs_contract = {
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [
                    {
                        "name": "complete_field",
                        "type": "string",
                        "nullable": False,
                        "description": "Complete field with all properties",
                        "semantic_type": "EMAIL",
                        "format": "email",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                        "enum": None,
                        "default": "test@example.com",
                        "min_length": 5,
                        "max_length": 255,
                        "minimum": None,
                        "maximum": None,
                        "metadata": {
                            "source": "CRM",
                            "pii": True
                        },
                        "is_primary_key": True,
                        "is_unique": True,
                        "is_indexed": True
                    }
                ],
                "primary_key": ["complete_field"]
            }
        }
        
        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)
        
        self.assertIsNotNone(hub_contract)
        field = hub_contract["schema"]["fields"][0]
        
        # Verify all properties are present
        self.assertEqual(field["name"], "complete_field")
        self.assertEqual(field["data_type"], "string")
        self.assertEqual(field["nullable"], False)
        self.assertEqual(field["description"], "Complete field with all properties")
        self.assertEqual(field["semantic_type"], "EMAIL")
        self.assertEqual(field["format"], "email")
        self.assertIsNotNone(field["pattern"])
        self.assertEqual(field["default"], "test@example.com")
        self.assertEqual(field["min_length"], 5)
        self.assertEqual(field["max_length"], 255)
        self.assertIn("metadata", field)
        self.assertTrue(field["is_primary_key"])
        self.assertTrue(field["is_unique"])
        self.assertTrue(field["is_indexed"])

