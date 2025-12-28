"""
Unit tests for contract normalization.
"""
import json
import pytest
from django.test import TestCase
from hub.apps.contracts.normalization import (
    normalize_contract,
    validate_hubcontract_schema
)
from hub.apps.contracts.spec_detection import detect_spec_type
from hub.apps.contracts.coverage import calculate_coverage
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

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(hub_contract["hub_contract_version"], "1.0.0")
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
            "hub_contract_version": "1.0.0",
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

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

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

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

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

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

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

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

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

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

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

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

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

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

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

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)

    def test_status_normalization_failed_exception(self):
        """Test NORMALIZATION_FAILED status when exception occurs"""
        # Invalid contract structure that will cause exception
        odcs_contract = None

        # normalize_contract expects a string, so we need to handle None differently
        # For None input, we'll pass an empty dict as JSON
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps({}),
            format="JSON",
            spec_type="ODCS"
        )

        # normalize_contract may return None or an empty contract for invalid input
        # The status should indicate failure
        self.assertEqual(status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(errors), 0)

    def test_models_normalization_and_schema_derivation(self):
        """ODCS schema list is normalized into models[] with derived schema view."""
        odcs_contract = {
            "id": "models-test",
            "name": "Contract with Models",
            "schema": [
                {
                    "name": "users",
                    "description": "Users model",
                    "fields": [
                        {"name": "id", "type": "string", "primaryKey": True},
                        {"name": "email", "type": "string", "unique": True}
                    ],
                    "indexes": [{"fields": ["email"]}]
                },
                {
                    "name": "orders",
                    "fields": [{"name": "order_id", "type": "string"}]
                }
            ]
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertIn("models", hub_contract)
        self.assertEqual(len(hub_contract["models"]), 2)
        first_model = hub_contract["models"][0]
        self.assertEqual(first_model["name"], "users")
        self.assertEqual(first_model["fields"][0]["is_primary_key"], True)
        self.assertTrue(first_model["fields"][1]["is_unique"])
        self.assertIn("schema", hub_contract)
        self.assertEqual(hub_contract["schema"]["fields"][0]["name"], "id")

    def test_servicelevels_and_quality_rules_mapping(self):
        """slaProperties and quality rules map into canonical structures."""
        odcs_contract = {
            "id": "sla-quality",
            "name": "Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "slaProperties": [
                {"id": "sla1", "property": "availability", "target": "99.9", "unit": "%", "priority": "P1"}
            ],
            "quality": {
                "default_profile_key": "intake_basic",
                "rules": [
                    {"id": "q1", "name": "not_null", "dimension": "Completeness", "rule": "NOT NULL", "severity": "HIGH"}
                ]
            }
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertIn("servicelevels", hub_contract)
        self.assertEqual(hub_contract["servicelevels"][0]["property"], "availability")
        self.assertIn("quality", hub_contract)
        self.assertEqual(hub_contract["quality"]["rules"][0]["name"], "not_null")

    def test_contact_and_servers_and_terms_mapping(self):
        """Support, servers, and description map into contact/servers/terms."""
        odcs_contract = {
            "id": "contact-servers",
            "name": "Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "support": [
                {"name": "Data Team", "email": "data@example.com", "url": "https://support.example.com", "tool": "jira"}
            ],
            "servers": [
                {"type": "postgresql", "url": "postgres://db.example.com", "description": "Primary DB"}
            ],
            "description": {
                "usage": "Internal analytics only",
                "limitations": "No PII sharing"
            }
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(hub_contract["contact"][0]["email"], "data@example.com")
        self.assertEqual(hub_contract["servers"][0]["type"], "postgresql")
        self.assertEqual(hub_contract["terms"]["usage"], "Internal analytics only")

    def test_quality_type_and_specification_mapping(self):
        """quality.type/specification should be captured."""
        odcs_contract = {
            "id": "quality-type",
            "name": "Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "quality": {
                "type": "GreatExpectations",
                "specification": "ge://profiles/basic",
                "rules": [{"name": "not_null", "rule": "NOT NULL"}]
            }
        }
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(hub_contract["quality"]["type"], "GreatExpectations")
        self.assertEqual(hub_contract["quality"]["specification"], "ge://profiles/basic")

    def test_roles_team_pricing_and_lineage_mapping(self):
        """Roles, team, price, and lineage fields should map into HubContract."""
        odcs_contract = {
            "id": "roles-team",
            "name": "Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "roles": [{"roleName": "data-reader", "accessType": "read"}],
            "team": [{"member": "alice", "role": "owner"}],
            "price": {"priceAmount": 100, "priceCurrency": "USD", "priceUnit": "month"},
            "transformSourceObjects": [{"namespace": "ns", "name": "src", "model_name": "m", "field": "f"}],
            "transformLogic": "SELECT * FROM src"
        }
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(hub_contract["roles"][0]["roleName"], "data-reader")
        self.assertEqual(hub_contract["team"][0]["member"], "alice")
        self.assertEqual(hub_contract["pricing"]["priceAmount"], 100)
        self.assertIn("lineage", hub_contract)
        # Lineage is LineageSection with entries list
        self.assertIn("entries", hub_contract["lineage"])
        self.assertEqual(hub_contract["lineage"]["entries"][0]["input_fields"][0]["name"], "src")
        self.assertEqual(hub_contract["lineage"]["entries"][0]["transformations"][0]["logic"], "SELECT * FROM src")

    def test_server_type_specific_mapping_and_extensions(self):
        """Servers should map type-specific fields and retain extensions."""
        odcs_contract = {
            "id": "servers-map",
            "name": "Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "servers": [
                {
                    "type": "snowflake",
                    "account": "acct",
                    "warehouse": "wh",
                    "database": "db",
                    "schema": "public",
                    "region": "us-west",
                    "extra_field": "keep_me"
                },
                {
                    "type": "kafka",
                    "topic": "events",
                    "bootstrapServers": "kafka:9092"
                }
            ]
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        servers = hub_contract.get("servers", [])
        self.assertEqual(servers[0]["type"], "snowflake")
        self.assertEqual(servers[0]["account"], "acct")
        self.assertIn("extensions", servers[0])
        self.assertEqual(servers[1]["topic"], "events")
        self.assertEqual(servers[1]["type"], "kafka")

    def test_normalization_coverage_calculation(self):
        """Test normalization coverage metrics calculation"""
        # Contract with all sections
        full_contract = {
            "hub_contract_version": "1.0.0",
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

        coverage_result = calculate_coverage(full_contract)

        # Coverage should be high (most sections present)
        self.assertGreater(coverage_result.overall, 0.5)
        self.assertLessEqual(coverage_result.overall, 1.0)
        self.assertIn("info", coverage_result.sections)
        self.assertFalse(coverage_result.sections["info"].missing_required)

        # Contract with minimal sections
        minimal_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test",
            "info": {
                "name": "Test"
            },
            "schema": {
                "fields": [{"name": "id", "data_type": "string"}]
            }
        }

        minimal_coverage = calculate_coverage(minimal_contract)

        # Minimal contract should have lower coverage
        self.assertLess(minimal_coverage.overall, coverage_result.overall)
        self.assertGreater(minimal_coverage.overall, 0.0)

    def test_normalization_attaches_coverage_metadata(self):
        """Normalization should persist coverage details for observability."""
        odcs_contract = {
            "id": "coverage-test",
            "name": "Coverage Test",
            "schema": {"fields": [{"name": "id", "type": "string"}]}
        }

        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        self.assertIsNotNone(hub_contract)
        self.assertIn("normalization", hub_contract)
        coverage = hub_contract["normalization"].get("coverage")
        self.assertIsInstance(coverage, dict)
        self.assertIn("sections", coverage)

    def test_normalize_contract_replaces_deprecated_function(self):
        """
        Test that normalize_contract() works as a replacement for the deprecated
        normalize_odcs_to_hubcontract() function.

        This test verifies that normalize_contract() produces the same results
        as the deprecated function would have, ensuring backward compatibility.
        """
        odcs_contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "replacement-test",
            "name": "Replacement Test Contract",
            "version": "1.0.0",
            "description": "Test description",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": True}
                ],
                "primary_key": ["id"]
            },
            "info": {
                "owners": [{"name": "Test Owner", "email": "owner@example.com"}],
                "tags": ["test", "replacement"]
            }
        }

        # Use normalize_contract() as replacement for deprecated function
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract),
            format="JSON",
            spec_type="ODCS"
        )

        # Verify the function works correctly
        self.assertIsNotNone(hub_contract)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertIsNotNone(spec_version)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(len(errors), 0)

        # Verify contract structure
        self.assertEqual(hub_contract["id"], "replacement-test")
        self.assertEqual(hub_contract["info"]["name"], "Replacement Test Contract")
        self.assertIn("schema", hub_contract)
        self.assertIn("fields", hub_contract["schema"])
        self.assertEqual(len(hub_contract["schema"]["fields"]), 2)

        # Verify info section
        self.assertIn("owners", hub_contract["info"])
        self.assertIn("tags", hub_contract["info"])
        self.assertEqual(len(hub_contract["info"]["owners"]), 1)
        self.assertEqual(len(hub_contract["info"]["tags"]), 2)
