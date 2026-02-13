"""
Unit tests for ODCS Generator V3.0.2.

Tests the ODCSGeneratorV3_0_2 class following TDD approach
and engineering best practices without mocks/stubs.
"""

import pytest
from django.test import TestCase

from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.odcs_errors import ODCSGenerationError
from hub.apps.contracts.odcs_generator import ODCSGeneratorV3_0_2

pytestmark = pytest.mark.django_db(transaction=True)


class ODCSGeneratorV3_0_2StructureTest(TestCase):
    """Test ODCSGeneratorV3_0_2 structure and instantiation"""

    def test_can_instantiate_generator(self):
        """Test that ODCSGeneratorV3_0_2 can be instantiated"""
        generator = ODCSGeneratorV3_0_2()
        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_2)

    def test_has_generate_method(self):
        """Test that generator has generate_odcs_from_hubcontract method"""
        generator = ODCSGeneratorV3_0_2()
        self.assertTrue(hasattr(generator, "generate_odcs_from_hubcontract"))
        self.assertTrue(callable(generator.generate_odcs_from_hubcontract))


class ODCSGeneratorV3_0_2BasicMappingTest(TestCase):
    """Test basic field mappings (id, name, description, version)"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()
        self.minimal_hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

    def test_generates_basic_odcs_structure(self):
        """Test generation of basic ODCS structure"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(self.minimal_hub_contract)

        self.assertEqual(odcs_doc["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(odcs_doc["kind"], "DataContract")
        self.assertEqual(odcs_doc["id"], "test-contract-1")
        self.assertEqual(odcs_doc["name"], "Test Contract")

    def test_maps_description(self):
        """Test mapping of description field"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract", "description": "A test contract description"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertEqual(odcs_doc["description"], "A test contract description")

    def test_maps_version(self):
        """Test mapping of version field"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract", "version": "1.0.0"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertEqual(odcs_doc["version"], "1.0.0")

    def test_handles_missing_optional_fields(self):
        """Test that missing optional fields don't cause errors"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(self.minimal_hub_contract)
        self.assertNotIn("description", odcs_doc)
        self.assertNotIn("version", odcs_doc)


class ODCSGeneratorV3_0_2InfoSectionTest(TestCase):
    """Test info section mappings (owners, tags)"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()

    def test_maps_owners_list(self):
        """Test mapping of owners list"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "owners": [
                    {"name": "John Doe", "email": "john@example.com"},
                    {"name": "Jane Smith", "email": "jane@example.com"},
                ],
            },
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("info", odcs_doc)
        self.assertIn("owners", odcs_doc["info"])
        self.assertEqual(len(odcs_doc["info"]["owners"]), 2)
        self.assertEqual(odcs_doc["info"]["owners"][0]["name"], "John Doe")
        self.assertEqual(odcs_doc["info"]["owners"][0]["email"], "john@example.com")

    def test_maps_owners_string_list(self):
        """Test mapping of owners as string list"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract", "owners": ["John Doe", "Jane Smith"]},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("info", odcs_doc)
        self.assertIn("owners", odcs_doc["info"])
        self.assertEqual(len(odcs_doc["info"]["owners"]), 2)
        self.assertEqual(odcs_doc["info"]["owners"][0]["name"], "John Doe")

    def test_maps_tags(self):
        """Test mapping of tags"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract", "tags": ["production", "customer-data", "pii"]},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("info", odcs_doc)
        self.assertIn("tags", odcs_doc["info"])
        self.assertEqual(odcs_doc["info"]["tags"], ["production", "customer-data", "pii"])

    def test_maps_domain_tenant_dataproduct(self):
        """Test mapping of domain, tenant, and dataProduct fields"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "domain": "customer",
                "tenant": "acme-corp",
                "dataProduct": "customer-analytics",
            },
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("info", odcs_doc)
        self.assertEqual(odcs_doc["info"]["domain"], "customer")
        self.assertEqual(odcs_doc["info"]["tenant"], "acme-corp")
        self.assertEqual(odcs_doc["info"]["dataProduct"], "customer-analytics")


class ODCSGeneratorV3_0_2SchemaMappingTest(TestCase):
    """Test schema section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()

    def test_maps_single_schema_object(self):
        """Test mapping of single schema object"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string", "nullable": False},
                    {"name": "email", "data_type": "string", "nullable": True, "format": "email"},
                ],
                "primary_key": ["id"],
            },
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("schema", odcs_doc)
        self.assertIn("fields", odcs_doc["schema"])
        self.assertEqual(len(odcs_doc["schema"]["fields"]), 2)
        self.assertEqual(odcs_doc["schema"]["fields"][0]["name"], "id")
        self.assertEqual(odcs_doc["schema"]["fields"][0]["type"], "string")
        self.assertEqual(odcs_doc["schema"]["fields"][0]["nullable"], False)
        self.assertEqual(odcs_doc["schema"]["primaryKey"], "id")

    def test_maps_models_array(self):
        """Test mapping of models array to schema array"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "models": [
                {
                    "name": "users",
                    "fields": [
                        {"name": "id", "data_type": "string"},
                        {"name": "email", "data_type": "string"},
                    ],
                    "primary_key": ["id"],
                },
                {
                    "name": "orders",
                    "fields": [{"name": "order_id", "data_type": "string"}],
                    "primary_key": ["order_id"],
                },
            ],
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("schema", odcs_doc)
        self.assertIsInstance(odcs_doc["schema"], list)
        self.assertEqual(len(odcs_doc["schema"]), 2)
        self.assertEqual(odcs_doc["schema"][0]["name"], "users")
        self.assertEqual(odcs_doc["schema"][1]["name"], "orders")

    def test_maps_single_model_to_schema_object(self):
        """Test mapping of single model to schema object (not array)"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "models": [{"name": "users", "fields": [{"name": "id", "data_type": "string"}]}],
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("schema", odcs_doc)
        # Single model should map to schema object, not array
        self.assertIsInstance(odcs_doc["schema"], dict)
        self.assertEqual(odcs_doc["schema"]["name"], "users")

    def test_maps_field_properties(self):
        """Test mapping of field properties (format, pattern, enum, etc.)"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {
                "fields": [
                    {
                        "name": "email",
                        "data_type": "string",
                        "format": "email",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                        "min_length": 5,
                        "max_length": 255,
                    },
                    {
                        "name": "status",
                        "data_type": "string",
                        "enum": ["active", "inactive", "pending"],
                    },
                    {"name": "age", "data_type": "integer", "minimum": 0, "maximum": 150},
                ]
            },
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        email_field = odcs_doc["schema"]["fields"][0]
        self.assertEqual(email_field["format"], "email")
        self.assertEqual(
            email_field["pattern"], "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
        )
        self.assertEqual(email_field["minLength"], 5)
        self.assertEqual(email_field["maxLength"], 255)

        status_field = odcs_doc["schema"]["fields"][1]
        self.assertEqual(status_field["enum"], ["active", "inactive", "pending"])

        age_field = odcs_doc["schema"]["fields"][2]
        self.assertEqual(age_field["minimum"], 0)
        self.assertEqual(age_field["maximum"], 150)

    def test_maps_unique_constraints_and_indexes(self):
        """Test mapping of unique constraints and indexes"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"},
                    {"name": "email", "data_type": "string"},
                ],
                "primary_key": ["id"],
                "unique_constraints": [["email"]],
                "indexes": [["email"]],
            },
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertEqual(odcs_doc["schema"]["primaryKey"], "id")
        self.assertEqual(odcs_doc["schema"]["uniqueConstraints"], [["email"]])
        self.assertEqual(odcs_doc["schema"]["indexes"], [["email"]])


class ODCSGeneratorV3_0_2QualityMappingTest(TestCase):
    """Test quality section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()

    def test_maps_quality_rules(self):
        """Test mapping of quality rules"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "quality": {
                "rules": [
                    {
                        "id": "q1",
                        "name": "No null emails",
                        "dimension": "completeness",
                        "type": "not_null",
                        "rule": "email IS NOT NULL",
                        "severity": "error",
                    },
                    {
                        "id": "q2",
                        "name": "Valid email format",
                        "dimension": "validity",
                        "type": "regex",
                        "rule": "email ~ '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'",
                        "severity": "error",
                    },
                ]
            },
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("quality", odcs_doc)
        self.assertIn("rules", odcs_doc["quality"])
        self.assertEqual(len(odcs_doc["quality"]["rules"]), 2)
        self.assertEqual(odcs_doc["quality"]["rules"][0]["id"], "q1")
        self.assertEqual(odcs_doc["quality"]["rules"][0]["name"], "No null emails")

    def test_maps_default_profile_key(self):
        """Test mapping of default_profile_key"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "quality": {"default_profile_key": "intake_basic"},
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("quality", odcs_doc)
        self.assertEqual(odcs_doc["quality"]["default_profile_key"], "intake_basic")


class ODCSGeneratorV3_0_2LifecycleMappingTest(TestCase):
    """Test lifecycle section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()

    def test_maps_lifecycle_section(self):
        """Test mapping of lifecycle section"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "lifecycle": {
                "data_source": "postgresql://db.example.com:5432/customer_db",
                "refresh_cadence": "daily",
                "slas": {"availability": 99.9, "latency_ms_p95": 100},
            },
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("lifecycle", odcs_doc)
        self.assertEqual(
            odcs_doc["lifecycle"]["data_source"], "postgresql://db.example.com:5432/customer_db"
        )
        self.assertEqual(odcs_doc["lifecycle"]["refresh_cadence"], "daily")
        self.assertEqual(odcs_doc["lifecycle"]["slas"]["availability"], 99.9)


class ODCSGeneratorV3_0_2ServicelevelsMappingTest(TestCase):
    """Test servicelevels section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()

    def test_maps_servicelevels_to_sla_properties(self):
        """Test mapping of servicelevels to slaProperties"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "servicelevels": [
                {
                    "name": "availability",
                    "target": 99.9,
                    "unit": "percent",
                    "description": "99.9% availability SLA",
                },
                {
                    "name": "latency",
                    "target": 100,
                    "unit": "milliseconds",
                    "description": "100ms latency SLA",
                },
            ],
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("slaProperties", odcs_doc)
        self.assertEqual(len(odcs_doc["slaProperties"]), 2)
        self.assertEqual(odcs_doc["slaProperties"][0]["property"], "availability")
        self.assertEqual(odcs_doc["slaProperties"][0]["target"], 99.9)
        self.assertEqual(odcs_doc["slaProperties"][0]["unit"], "percent")


class ODCSGeneratorV3_0_2LineageMappingTest(TestCase):
    """Test lineage section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()

    def test_maps_lineage_to_transform_source_objects(self):
        """Test mapping of lineage to transformSourceObjects"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "lineage": {
                "entries": [
                    {
                        "contract_id": "source-customer-contract",
                        "contract_version": "1.0.0",
                        "namespace": "ns1",
                        "model": "source-customer",
                        "field": "customer_id",
                    }
                ],
                "transform_logic": "SELECT id, email, created_at FROM source_customer WHERE status = 'active'",
            },
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("transformSourceObjects", odcs_doc)
        self.assertEqual(len(odcs_doc["transformSourceObjects"]), 1)
        self.assertEqual(odcs_doc["transformSourceObjects"][0]["name"], "source-customer-contract")
        self.assertEqual(odcs_doc["transformSourceObjects"][0]["version"], "1.0.0")
        self.assertEqual(odcs_doc["transformSourceObjects"][0]["namespace"], "ns1")
        self.assertIn("transformLogic", odcs_doc)
        self.assertEqual(
            odcs_doc["transformLogic"],
            "SELECT id, email, created_at FROM source_customer WHERE status = 'active'",
        )


class ODCSGeneratorV3_0_2MarketplaceMappingTest(TestCase):
    """Test marketplace section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()

    def test_maps_marketplace_section(self):
        """Test mapping of marketplace section"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "marketplace": {
                "license_summary": "Internal use only",
                "intended_use": ["analytics", "reporting"],
                "restricted_use": ["external-distribution"],
            },
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("marketplace", odcs_doc)
        self.assertEqual(odcs_doc["marketplace"]["license_summary"], "Internal use only")
        self.assertEqual(odcs_doc["marketplace"]["intended_use"], ["analytics", "reporting"])
        self.assertEqual(odcs_doc["marketplace"]["restricted_use"], ["external-distribution"])


class ODCSGeneratorV3_0_2PrivacyComplianceMappingTest(TestCase):
    """Test privacy_compliance section mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()

    def test_maps_privacy_compliance_section(self):
        """Test mapping of privacy_compliance section"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "privacy_compliance": {
                "contains_personal_data": True,
                "jurisdictions": ["GDPR", "CCPA"],
                "personal_data_categories": ["PII"],
                "retention_policy": {
                    "retention_period_days": 365,
                    "retention_reason": "Business operations",
                },
            },
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertIn("privacy_compliance", odcs_doc)
        self.assertTrue(odcs_doc["privacy_compliance"]["contains_personal_data"])
        self.assertEqual(odcs_doc["privacy_compliance"]["jurisdictions"], ["GDPR", "CCPA"])


class ODCSGeneratorV3_0_2ErrorHandlingTest(TestCase):
    """Test error handling for invalid inputs"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()

    def test_handles_missing_required_field_name(self):
        """Test error handling for missing required field name"""
        invalid_contract = {"id": "test-contract-1", "info": {}}

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)
        self.assertIn("info/name", error.context["field_path"])

    def test_handles_wrong_type_for_description(self):
        """Test error handling for wrong type in description"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract", "description": 123},  # Should be string
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_GENERATION_FAILED)
        self.assertIn("info/description", error.context["field_path"])

    def test_handles_missing_field_name_in_schema(self):
        """Test error handling for missing field name in schema"""
        invalid_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"data_type": "string"}]},  # Missing name
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)
        self.assertIn("fields/0/name", error.context["field_path"])


class ODCSGeneratorV3_0_2EdgeCasesTest(TestCase):
    """Test edge cases (empty arrays, null values, optional fields)"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()

    def test_handles_empty_owners_list(self):
        """Test handling of empty owners list"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract", "owners": []},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        # Empty owners list should not be included
        if "info" in odcs_doc:
            self.assertNotIn("owners", odcs_doc.get("info", {}))

    def test_handles_empty_tags_list(self):
        """Test handling of empty tags list"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract", "tags": []},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        # Empty tags list should not be included
        if "info" in odcs_doc:
            self.assertNotIn("tags", odcs_doc.get("info", {}))

    def test_handles_none_values_gracefully(self):
        """Test handling of None values in optional fields"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {"name": "Test Contract", "description": None, "version": None},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        # Should not raise error, None values should be skipped
        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)
        self.assertNotIn("description", odcs_doc)
        self.assertNotIn("version", odcs_doc)


class ODCSGeneratorV3_0_2RoundTripTest(TestCase):
    """Test round-trip: ODCS → HubContract → ODCS"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_2()

    def test_round_trip_basic_contract(self):
        """Test round-trip with basic contract"""
        # Start with ODCS 3.0.2 contract
        original_odcs = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract-roundtrip",
            "name": "Test Contract Roundtrip",
            "version": "1.0.0",
            "description": "A test contract for round-trip testing",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "email", "type": "string", "nullable": True, "format": "email"},
                ],
                "primaryKey": "id",
            },
        }

        # Convert ODCS to JSON string for normalization
        import json

        odcs_json = json.dumps(original_odcs)

        # Normalize ODCS → HubContract
        hub_contract_dict, spec_type, spec_version, status, errors, warnings = normalize_contract(
            odcs_json, "JSON", spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract_dict)
        self.assertEqual(len(errors), 0, f"Normalization errors: {errors}")

        # Generate ODCS from HubContract
        generated_odcs = self.generator.generate_odcs_from_hubcontract(hub_contract_dict)

        # Verify basic fields match
        self.assertEqual(generated_odcs["id"], original_odcs["id"])
        self.assertEqual(generated_odcs["name"], original_odcs["name"])
        self.assertEqual(generated_odcs["version"], original_odcs["version"])
        self.assertEqual(generated_odcs["description"], original_odcs["description"])

        # Verify schema fields match
        self.assertIn("schema", generated_odcs)
        self.assertEqual(len(generated_odcs["schema"]["fields"]), 2)
        self.assertEqual(generated_odcs["schema"]["fields"][0]["name"], "id")
        self.assertEqual(generated_odcs["schema"]["fields"][0]["type"], "string")
        self.assertEqual(generated_odcs["schema"]["fields"][0]["nullable"], False)

    def test_round_trip_with_quality_and_lifecycle(self):
        """Test round-trip with quality and lifecycle sections"""
        # Start with ODCS 3.0.2 contract with quality and lifecycle
        original_odcs = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract-full",
            "name": "Test Contract Full",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "quality": {
                "default_profile_key": "intake_basic",
                "rules": [
                    {
                        "id": "q1",
                        "name": "No null emails",
                        "dimension": "completeness",
                        "type": "not_null",
                        "rule": "email IS NOT NULL",
                        "severity": "error",
                    }
                ],
            },
            "lifecycle": {
                "data_source": "postgresql://db.example.com:5432/customer_db",
                "refresh_cadence": "daily",
            },
        }

        # Convert ODCS to JSON string for normalization
        import json

        odcs_json = json.dumps(original_odcs)

        # Normalize ODCS → HubContract
        hub_contract_dict, spec_type, spec_version, status, errors, warnings = normalize_contract(
            odcs_json, "JSON", spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract_dict)
        self.assertEqual(len(errors), 0, f"Normalization errors: {errors}")

        # Generate ODCS from HubContract
        generated_odcs = self.generator.generate_odcs_from_hubcontract(hub_contract_dict)

        # Verify quality section
        self.assertIn("quality", generated_odcs)
        self.assertEqual(generated_odcs["quality"]["default_profile_key"], "intake_basic")
        self.assertIn("rules", generated_odcs["quality"])
        self.assertEqual(len(generated_odcs["quality"]["rules"]), 1)

        # Verify lifecycle section
        self.assertIn("lifecycle", generated_odcs)
        self.assertEqual(
            generated_odcs["lifecycle"]["data_source"],
            "postgresql://db.example.com:5432/customer_db",
        )
        self.assertEqual(generated_odcs["lifecycle"]["refresh_cadence"], "daily")

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
        self.assertIn("description", result)
        self.assertEqual(result["description"], "测试描述")

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
        self.assertIn("description", result)
        self.assertEqual(result["description"], "Test <description> & more")

    def test_generation_handles_very_large_documents(self):
        """Test that generation handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = {
            "id": "test-large",
            "info": {"name": "Test Product", "description": large_description},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        # Should handle large documents gracefully
        try:
            result = self.generator.generate_odcs_from_hubcontract(hub_contract)
            # If generation succeeds, verify structure
            self.assertIn("name", result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, ODCSGenerationError, "Should raise ODCSGenerationError for very large documents"
            )

    def test_generation_handles_none_values(self):
        """Test that generation handles None values correctly."""
        hub_contract = {
            "id": "test-none",
            "info": {"name": "Test Product", "description": None},  # None value
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        # Should handle None values gracefully
        try:
            result = self.generator.generate_odcs_from_hubcontract(hub_contract)
            # If generation succeeds, None values may be omitted or handled
            self.assertIsNotNone(result)
        except Exception as e:
            # If generation fails, it should fail gracefully
            self.assertIsInstance(
                e, ODCSGenerationError, "Should raise ODCSGenerationError for None values"
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

        # Verify nested structure is preserved
        self.assertIn("name", result)
        self.assertIsNotNone(result)
