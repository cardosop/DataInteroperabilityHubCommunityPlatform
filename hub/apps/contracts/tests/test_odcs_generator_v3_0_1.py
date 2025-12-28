"""
Unit tests for ODCS Generator V3.0.1.

Tests the ODCSGeneratorV3_0_1 class following TDD approach
and engineering best practices without mocks/stubs.
"""
import pytest
from django.test import TestCase

from hub.apps.contracts.odcs_generator import ODCSGeneratorV3_0_1
from hub.apps.contracts.odcs_errors import ODCSGenerationError
from hub.apps.contracts.normalization import normalize_contract

pytestmark = pytest.mark.django_db(transaction=True)


class ODCSGeneratorV3_0_1StructureTest(TestCase):
    """Test ODCSGeneratorV3_0_1 structure and instantiation"""

    def test_can_instantiate_generator(self):
        """Test that ODCSGeneratorV3_0_1 can be instantiated"""
        generator = ODCSGeneratorV3_0_1()
        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_1)

    def test_has_generate_method(self):
        """Test that generator has generate_odcs_from_hubcontract method"""
        generator = ODCSGeneratorV3_0_1()
        self.assertTrue(hasattr(generator, "generate_odcs_from_hubcontract"))
        self.assertTrue(callable(generator.generate_odcs_from_hubcontract))

    def test_target_version_is_3_0_1(self):
        """Test that target_version is set to 3.0.1"""
        generator = ODCSGeneratorV3_0_1()
        self.assertEqual(generator.target_version, "3.0.1")


class ODCSGeneratorV3_0_1BasicMappingTest(TestCase):
    """Test basic field mappings (id, name, description, version)"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_1()
        self.minimal_hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            }
        }

    def test_generates_basic_odcs_structure(self):
        """Test generation of basic ODCS 3.0.1 structure"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(self.minimal_hub_contract)

        self.assertEqual(odcs_doc["apiVersion"], "odcs.io/v3.0.1")
        self.assertEqual(odcs_doc["kind"], "DataContract")
        self.assertEqual(odcs_doc["id"], "test-contract-1")
        self.assertEqual(odcs_doc["name"], "Test Contract")

    def test_maps_description(self):
        """Test mapping of description field"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "description": "A test contract description"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertEqual(odcs_doc["description"], "A test contract description")

    def test_maps_version(self):
        """Test mapping of version field"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "version": "1.0.0"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertEqual(odcs_doc["version"], "1.0.0")

    def test_handles_missing_optional_fields(self):
        """Test that missing optional fields don't cause errors"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(self.minimal_hub_contract)
        self.assertNotIn("description", odcs_doc)
        self.assertNotIn("version", odcs_doc)

    def test_ignores_target_version_parameter(self):
        """Test that target_version parameter is ignored (always uses 3.0.1)"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(
            self.minimal_hub_contract,
            target_version="3.0.2"  # Should be ignored
        )
        self.assertEqual(odcs_doc["apiVersion"], "odcs.io/v3.0.1")


class ODCSGeneratorV3_0_1InfoSectionTest(TestCase):
    """Test info section mappings (owners, tags)"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_1()

    def test_maps_owners_list(self):
        """Test mapping of owners list"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "owners": [
                    {"name": "John Doe", "email": "john@example.com"},
                    {"name": "Jane Smith", "email": "jane@example.com"}
                ]
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("info", odcs_doc)
        self.assertIn("owners", odcs_doc["info"])
        self.assertEqual(len(odcs_doc["info"]["owners"]), 2)
        self.assertEqual(odcs_doc["info"]["owners"][0]["name"], "John Doe")
        self.assertEqual(odcs_doc["info"]["owners"][0]["email"], "john@example.com")

    def test_maps_tags(self):
        """Test mapping of tags"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "tags": ["production", "customer-data", "pii"]
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("info", odcs_doc)
        self.assertIn("tags", odcs_doc["info"])
        self.assertEqual(odcs_doc["info"]["tags"], ["production", "customer-data", "pii"])


class ODCSGeneratorV3_0_1SchemaMappingTest(TestCase):
    """Test schema section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_1()

    def test_maps_schema_fields(self):
        """Test mapping of schema fields"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "data_type": "string",
                        "nullable": False,
                        "description": "Unique identifier"
                    },
                    {
                        "name": "name",
                        "data_type": "string",
                        "nullable": True,
                        "min_length": 1,
                        "max_length": 100
                    }
                ]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("schema", odcs_doc)
        self.assertIn("fields", odcs_doc["schema"])
        self.assertEqual(len(odcs_doc["schema"]["fields"]), 2)

        # Check first field
        field1 = odcs_doc["schema"]["fields"][0]
        self.assertEqual(field1["name"], "id")
        self.assertEqual(field1["type"], "string")
        self.assertEqual(field1["nullable"], False)
        self.assertEqual(field1["description"], "Unique identifier")

        # Check second field
        field2 = odcs_doc["schema"]["fields"][1]
        self.assertEqual(field2["name"], "name")
        self.assertEqual(field2["type"], "string")
        self.assertEqual(field2["nullable"], True)
        self.assertEqual(field2["minLength"], 1)
        self.assertEqual(field2["maxLength"], 100)

    def test_maps_primary_key(self):
        """Test mapping of primary key"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"},
                    {"name": "name", "data_type": "string"}
                ],
                "primary_key": ["id"]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("schema", odcs_doc)
        self.assertIn("primary_key", odcs_doc["schema"])
        self.assertEqual(odcs_doc["schema"]["primary_key"], "id")

    def test_maps_composite_primary_key(self):
        """Test mapping of composite primary key"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id1", "data_type": "string"},
                    {"name": "id2", "data_type": "string"}
                ],
                "primary_key": ["id1", "id2"]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("schema", odcs_doc)
        self.assertIn("primary_key", odcs_doc["schema"])
        self.assertEqual(odcs_doc["schema"]["primary_key"], ["id1", "id2"])

    def test_maps_unique_constraints(self):
        """Test mapping of unique constraints"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"},
                    {"name": "email", "data_type": "string"}
                ],
                "unique_constraints": [["email"]]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("schema", odcs_doc)
        self.assertIn("unique_constraints", odcs_doc["schema"])
        self.assertEqual(odcs_doc["schema"]["unique_constraints"], [["email"]])

    def test_maps_indexes(self):
        """Test mapping of indexes"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"},
                    {"name": "name", "data_type": "string"}
                ],
                "indexes": [["name"]]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("schema", odcs_doc)
        self.assertIn("indexes", odcs_doc["schema"])
        self.assertEqual(odcs_doc["schema"]["indexes"], [["name"]])

    def test_handles_schema_with_type_field(self):
        """Test that schema fields can use 'type' instead of 'data_type'"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"}
                ]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("schema", odcs_doc)
        self.assertEqual(odcs_doc["schema"]["fields"][0]["type"], "string")


class ODCSGeneratorV3_0_1QualityMappingTest(TestCase):
    """Test quality section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_1()

    def test_maps_quality_rules(self):
        """Test mapping of quality rules"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            },
            "quality": {
                "rules": [
                    {
                        "name": "not_null",
                        "type": "completeness",
                        "description": "Field must not be null",
                        "expression": "field IS NOT NULL",
                        "severity": "error"
                    }
                ]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("quality", odcs_doc)
        self.assertIn("rules", odcs_doc["quality"])
        self.assertEqual(len(odcs_doc["quality"]["rules"]), 1)
        self.assertEqual(odcs_doc["quality"]["rules"][0]["name"], "not_null")
        self.assertEqual(odcs_doc["quality"]["rules"][0]["type"], "completeness")

    def test_maps_default_profile_key(self):
        """Test mapping of default_profile_key"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            },
            "quality": {
                "default_profile_key": "default"
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("quality", odcs_doc)
        self.assertEqual(odcs_doc["quality"]["default_profile_key"], "default")


class ODCSGeneratorV3_0_1LifecycleMappingTest(TestCase):
    """Test lifecycle section mappings with graceful degradation"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_1()

    def test_maps_lifecycle_basic_fields(self):
        """Test mapping of basic lifecycle fields (3.0.1 supported)"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            },
            "lifecycle": {
                "data_source": "database",
                "refresh_cadence": "DAILY",
                "slas": {
                    "availability": 99.9,
                    "latency_ms_p95": 5000
                }
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("lifecycle", odcs_doc)
        self.assertEqual(odcs_doc["lifecycle"]["data_source"], "database")
        self.assertEqual(odcs_doc["lifecycle"]["refresh_cadence"], "DAILY")
        self.assertIn("slas", odcs_doc["lifecycle"])
        self.assertEqual(odcs_doc["lifecycle"]["slas"]["availability"], 99.9)
        self.assertEqual(odcs_doc["lifecycle"]["slas"]["latency_ms_p95"], 5000)

    def test_gracefully_degrades_enhanced_lifecycle_features(self):
        """Test that 3.0.2+ enhanced lifecycle features are omitted with warning"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            },
            "lifecycle": {
                "data_source": "database",
                "enhanced_features": {"some": "value"},  # 3.0.2+ feature
                "advanced_slas": {"some": "value"}  # 3.0.2+ feature
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("lifecycle", odcs_doc)
        self.assertEqual(odcs_doc["lifecycle"]["data_source"], "database")
        # 3.0.2+ features should be omitted
        self.assertNotIn("enhanced_features", odcs_doc["lifecycle"])
        self.assertNotIn("advanced_slas", odcs_doc["lifecycle"])


class ODCSGeneratorV3_0_1MarketplaceMappingTest(TestCase):
    """Test marketplace section mappings with graceful degradation"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_1()

    def test_maps_marketplace_basic_fields(self):
        """Test mapping of basic marketplace fields (3.0.1 supported)"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            },
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["analytics", "reporting"],
                "restricted_use": ["resale", "marketing"]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("marketplace", odcs_doc)
        self.assertEqual(odcs_doc["marketplace"]["license_summary"], "MIT License")
        self.assertEqual(odcs_doc["marketplace"]["intended_use"], ["analytics", "reporting"])
        self.assertEqual(odcs_doc["marketplace"]["restricted_use"], ["resale", "marketing"])

    def test_gracefully_degrades_enhanced_marketplace_features(self):
        """Test that 3.0.2+ enhanced marketplace features are omitted with warning"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            },
            "marketplace": {
                "license_summary": "MIT License",
                "enhanced_features": {"some": "value"},  # 3.0.2+ feature
                "advanced_pricing": {"some": "value"}  # 3.0.2+ feature
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("marketplace", odcs_doc)
        self.assertEqual(odcs_doc["marketplace"]["license_summary"], "MIT License")
        # 3.0.2+ features should be omitted
        self.assertNotIn("enhanced_features", odcs_doc["marketplace"])
        self.assertNotIn("advanced_pricing", odcs_doc["marketplace"])


class ODCSGeneratorV3_0_1PrivacyComplianceMappingTest(TestCase):
    """Test privacy_compliance section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_1()

    def test_maps_privacy_compliance_fields(self):
        """Test mapping of privacy_compliance fields"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            },
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["email", "name"],
                "jurisdictions": ["EU", "US"],
                "legal_bases": ["consent", "legitimate_interest"],
                "retention_policy": {
                    "period": "P5Y",
                    "notes": "Retain for 5 years"
                }
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("privacy_compliance", odcs_doc)
        self.assertEqual(odcs_doc["privacy_compliance"]["contains_personal_data"], True)
        self.assertEqual(odcs_doc["privacy_compliance"]["personal_data_categories"], ["email", "name"])
        self.assertEqual(odcs_doc["privacy_compliance"]["jurisdictions"], ["EU", "US"])
        self.assertEqual(odcs_doc["privacy_compliance"]["legal_bases"], ["consent", "legitimate_interest"])
        self.assertIn("retention_policy", odcs_doc["privacy_compliance"])
        self.assertEqual(odcs_doc["privacy_compliance"]["retention_policy"]["period"], "P5Y")
        self.assertEqual(odcs_doc["privacy_compliance"]["retention_policy"]["notes"], "Retain for 5 years")


class ODCSGeneratorV3_0_1ValidationTest(TestCase):
    """Test validation and error handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_1()

    def test_validates_hub_contract_structure(self):
        """Test that invalid HubContract structure raises error"""
        invalid_contract = {
            "id": "test-contract-1"
            # Missing 'info' section
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertIn("info", error.message.lower())

    def test_validates_info_name_required(self):
        """Test that info.name is required"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": {}  # Missing 'name'
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertIn("name", error.message.lower())

    def test_validates_id_required(self):
        """Test that id is required"""
        invalid_contract = {
            "info": {
                "name": "Test Contract"
            }
            # Missing 'id'
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertIn("id", error.message.lower())

    def test_validates_field_types(self):
        """Test that invalid field types raise errors"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "description": 123  # Should be string
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"}
                ]
            }
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertIn("description", error.message.lower())


class ODCSGeneratorV3_0_1RoundTripTest(TestCase):
    """Test round-trip validation (ODCS 3.0.1 → HubContract → ODCS 3.0.1)"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_1()

    def test_round_trip_basic_contract(self):
        """Test round-trip with basic contract"""
        import json

        # Start with ODCS 3.0.1 contract
        original_odcs = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-contract-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "description": "A test contract",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False
                    }
                ]
            }
        }

        # Normalize to HubContract
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(original_odcs),
            format="json",
            spec_type="ODCS"
        )

        self.assertEqual(status.value, "NORMALIZED_OK")
        self.assertIsNotNone(hub_contract)
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")

        # Generate back to ODCS 3.0.1
        generated_odcs = self.generator.generate_odcs_from_hubcontract(hub_contract)

        # Verify key fields match
        self.assertEqual(generated_odcs["apiVersion"], "odcs.io/v3.0.1")
        self.assertEqual(generated_odcs["id"], original_odcs["id"])
        self.assertEqual(generated_odcs["name"], original_odcs["name"])
        self.assertEqual(generated_odcs["version"], original_odcs["version"])
        self.assertEqual(generated_odcs["description"], original_odcs["description"])
        self.assertIn("schema", generated_odcs)
        self.assertEqual(len(generated_odcs["schema"]["fields"]), 1)
        self.assertEqual(generated_odcs["schema"]["fields"][0]["name"], "id")

    def test_round_trip_with_all_sections(self):
        """Test round-trip with all sections"""
        import json

        # Start with comprehensive ODCS 3.0.1 contract
        original_odcs = {
            "apiVersion": "odcs.io/v3.0.1",
            "kind": "DataContract",
            "id": "test-contract-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "description": "A comprehensive test contract",
            "info": {
                "owners": [
                    {"name": "John Doe", "email": "john@example.com"}
                ],
                "tags": ["production", "test"]
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False
                    }
                ],
                "primary_key": "id"
            },
            "quality": {
                "rules": [
                    {
                        "name": "not_null",
                        "type": "completeness",
                        "description": "Field must not be null"
                    }
                ]
            },
            "lifecycle": {
                "data_source": "database",
                "refresh_cadence": "DAILY"
            },
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["analytics"]
            },
            "privacy_compliance": {
                "contains_personal_data": False
            }
        }

        # Normalize to HubContract
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(original_odcs),
            format="json",
            spec_type="ODCS"
        )

        self.assertEqual(status.value, "NORMALIZED_OK")
        self.assertIsNotNone(hub_contract)
        self.assertEqual(len(errors), 0, f"Unexpected errors: {errors}")

        # Generate back to ODCS 3.0.1
        generated_odcs = self.generator.generate_odcs_from_hubcontract(hub_contract)

        # Verify all sections are present
        self.assertEqual(generated_odcs["apiVersion"], "odcs.io/v3.0.1")
        self.assertEqual(generated_odcs["id"], original_odcs["id"])
        self.assertEqual(generated_odcs["name"], original_odcs["name"])
        self.assertIn("schema", generated_odcs)
        self.assertIn("quality", generated_odcs)
        self.assertIn("lifecycle", generated_odcs)
        self.assertIn("marketplace", generated_odcs)
        self.assertIn("privacy_compliance", generated_odcs)

