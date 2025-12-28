"""
Unit tests for ODCS Generator V3.0.0.

Tests the ODCSGeneratorV3_0_0 class following TDD approach
and engineering best practices without mocks/stubs.
"""
import pytest
from django.test import TestCase

from hub.apps.contracts.odcs_generator import ODCSGeneratorV3_0_0
from hub.apps.contracts.odcs_errors import ODCSGenerationError
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0 import ODCSNormalizerV3_0_0

pytestmark = pytest.mark.django_db(transaction=True)


class ODCSGeneratorV3_0_0StructureTest(TestCase):
    """Test ODCSGeneratorV3_0_0 class structure"""

    def test_class_exists(self):
        """Test that ODCSGeneratorV3_0_0 class exists"""
        self.assertTrue(hasattr(ODCSGeneratorV3_0_0, '__name__'))
        self.assertEqual(ODCSGeneratorV3_0_0.__name__, 'ODCSGeneratorV3_0_0')

    def test_can_instantiate(self):
        """Test that ODCSGeneratorV3_0_0 can be instantiated"""
        generator = ODCSGeneratorV3_0_0()
        self.assertIsNotNone(generator)
        self.assertIsInstance(generator, ODCSGeneratorV3_0_0)

    def test_has_generate_method(self):
        """Test that ODCSGeneratorV3_0_0 has generate_odcs_from_hubcontract method"""
        generator = ODCSGeneratorV3_0_0()
        self.assertTrue(hasattr(generator, 'generate_odcs_from_hubcontract'))
        self.assertTrue(callable(generator.generate_odcs_from_hubcontract))


class ODCSGeneratorV3_0_0BasicMappingTest(TestCase):
    """Test ODCSGeneratorV3_0_0 basic field mappings"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0()
        self.minimal_hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            }
        }

    def test_generate_minimal_contract(self):
        """Test generation of minimal HubContract to ODCS 3.0.0"""
        odcs_doc = self.generator.generate_odcs_from_hubcontract(
            self.minimal_hub_contract
        )

        self.assertIsInstance(odcs_doc, dict)
        self.assertEqual(odcs_doc["apiVersion"], "odcs.io/v3.0.0")
        self.assertEqual(odcs_doc["kind"], "DataContract")
        self.assertEqual(odcs_doc["id"], "test-contract-1")
        self.assertEqual(odcs_doc["name"], "Test Contract")

    def test_generate_with_version(self):
        """Test generation includes version when present"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "version": "1.0.0"
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        self.assertEqual(odcs_doc["version"], "1.0.0")

    def test_generate_with_description(self):
        """Test generation includes description when present"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "description": "A test contract description"
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        self.assertEqual(odcs_doc["description"], "A test contract description")

    def test_generate_with_all_basic_fields(self):
        """Test generation with all basic fields"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "description": "A test contract",
                "version": "1.0.0"
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        self.assertEqual(odcs_doc["apiVersion"], "odcs.io/v3.0.0")
        self.assertEqual(odcs_doc["kind"], "DataContract")
        self.assertEqual(odcs_doc["id"], "test-contract-1")
        self.assertEqual(odcs_doc["name"], "Test Contract")
        self.assertEqual(odcs_doc["version"], "1.0.0")
        self.assertEqual(odcs_doc["description"], "A test contract")


class ODCSGeneratorV3_0_0SchemaMappingTest(TestCase):
    """Test ODCSGeneratorV3_0_0 schema section mapping"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0()

    def test_generate_with_schema_fields(self):
        """Test generation includes schema with fields"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string"
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "nullable": False
                    }
                ]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        self.assertIn("schema", odcs_doc)
        self.assertIn("fields", odcs_doc["schema"])
        self.assertEqual(len(odcs_doc["schema"]["fields"]), 2)
        self.assertEqual(odcs_doc["schema"]["fields"][0]["name"], "id")
        self.assertEqual(odcs_doc["schema"]["fields"][0]["type"], "string")
        self.assertEqual(odcs_doc["schema"]["fields"][1]["name"], "name")
        self.assertEqual(odcs_doc["schema"]["fields"][1]["type"], "string")
        self.assertEqual(odcs_doc["schema"]["fields"][1]["nullable"], False)

    def test_generate_with_primary_key(self):
        """Test generation includes primary key when present"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"}
                ],
                "primary_key": ["id"]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        self.assertIn("primaryKey", odcs_doc["schema"])
        self.assertEqual(odcs_doc["schema"]["primaryKey"], "id")

    def test_generate_with_models_array(self):
        """Test generation handles models[] array structure"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "models": [
                {
                    "name": "User",
                    "fields": [
                        {"name": "id", "type": "string"}
                    ]
                }
            ]
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        # Should map models[] to schema
        self.assertIn("schema", odcs_doc)
        # For single model, should be a single schema object
        if isinstance(odcs_doc["schema"], dict):
            self.assertIn("fields", odcs_doc["schema"])
            self.assertEqual(odcs_doc["schema"]["fields"][0]["name"], "id")


class ODCSGeneratorV3_0_0QualityMappingTest(TestCase):
    """Test ODCSGeneratorV3_0_0 quality section mapping"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0()

    def test_generate_with_quality_rules(self):
        """Test generation includes quality rules when present"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "quality": {
                "rules": [
                    {
                        "name": "completeness",
                        "type": "metric",
                        "threshold": 0.95
                    }
                ]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        self.assertIn("quality", odcs_doc)
        self.assertIn("rules", odcs_doc["quality"])
        self.assertEqual(len(odcs_doc["quality"]["rules"]), 1)
        self.assertEqual(odcs_doc["quality"]["rules"][0]["name"], "completeness")


class ODCSGeneratorV3_0_0LifecycleMappingTest(TestCase):
    """Test ODCSGeneratorV3_0_0 lifecycle section mapping"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0()

    def test_generate_with_lifecycle(self):
        """Test generation includes lifecycle when present"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "lifecycle": {
                "data_source": "database",
                "refresh_cadence": "daily"
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        self.assertIn("lifecycle", odcs_doc)
        self.assertEqual(odcs_doc["lifecycle"]["data_source"], "database")
        self.assertEqual(odcs_doc["lifecycle"]["refresh_cadence"], "daily")


class ODCSGeneratorV3_0_0ServicelevelsMappingTest(TestCase):
    """Test ODCSGeneratorV3_0_0 servicelevels section mapping"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0()

    def test_generate_with_servicelevels(self):
        """Test generation includes servicelevels when present"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "servicelevels": [
                {
                    "name": "availability",
                    "target": "99.9%",
                    "unit": "percentage"
                }
            ]
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        self.assertIn("slaProperties", odcs_doc)
        self.assertEqual(len(odcs_doc["slaProperties"]), 1)
        self.assertEqual(odcs_doc["slaProperties"][0]["property"], "availability")
        self.assertEqual(odcs_doc["slaProperties"][0]["target"], "99.9%")


class ODCSGeneratorV3_0_0LineageMappingTest(TestCase):
    """Test ODCSGeneratorV3_0_0 lineage section mapping"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0()

    def test_generate_with_lineage(self):
        """Test generation includes lineage when present"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract"
            },
            "lineage": {
                "entries": [
                    {
                        "contract_id": "source-contract",
                        "contract_version": "1.0.0"
                    }
                ],
                "transform_logic": "SELECT * FROM source"
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        self.assertIn("transformSourceObjects", odcs_doc)
        self.assertEqual(len(odcs_doc["transformSourceObjects"]), 1)
        self.assertEqual(odcs_doc["transformSourceObjects"][0]["name"], "source-contract")
        self.assertIn("transformLogic", odcs_doc)
        self.assertEqual(odcs_doc["transformLogic"], "SELECT * FROM source")


class ODCSGeneratorV3_0_0InfoSectionMappingTest(TestCase):
    """Test ODCSGeneratorV3_0_0 info section mapping (owners, tags)"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0()

    def test_generate_with_owners(self):
        """Test generation includes owners when present"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "owners": [
                    {
                        "name": "John Doe",
                        "email": "john@example.com"
                    }
                ]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        self.assertIn("info", odcs_doc)
        self.assertIn("owners", odcs_doc["info"])
        self.assertEqual(len(odcs_doc["info"]["owners"]), 1)
        self.assertEqual(odcs_doc["info"]["owners"][0]["name"], "John Doe")
        self.assertEqual(odcs_doc["info"]["owners"][0]["email"], "john@example.com")

    def test_generate_with_tags(self):
        """Test generation includes tags when present"""
        hub_contract = {
            "id": "test-contract-1",
            "info": {
                "name": "Test Contract",
                "tags": ["production", "critical"]
            }
        }

        odcs_doc = self.generator.generate_odcs_from_hubcontract(hub_contract)

        self.assertIn("info", odcs_doc)
        self.assertIn("tags", odcs_doc["info"])
        self.assertEqual(odcs_doc["info"]["tags"], ["production", "critical"])


class ODCSGeneratorV3_0_0ErrorHandlingTest(TestCase):
    """Test ODCSGeneratorV3_0_0 error handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0()

    def test_generate_with_missing_info(self):
        """Test generation fails when info section is missing"""
        invalid_contract = {
            "id": "test-contract-1"
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            self.generator.generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)
        self.assertEqual(error.context["field_path"], "/info")

    def test_generate_with_missing_name(self):
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

    def test_generate_with_missing_id(self):
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


class ODCSGeneratorV3_0_0RoundTripTest(TestCase):
    """Test ODCSGeneratorV3_0_0 round-trip validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.generator = ODCSGeneratorV3_0_0()
        self.normalizer = ODCSNormalizerV3_0_0()

    def test_round_trip_basic_contract(self):
        """Test round-trip: ODCS 3.0.0 → HubContract → ODCS 3.0.0"""
        # Start with ODCS 3.0.0 contract
        original_odcs = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-contract-1",
            "name": "Test Contract",
            "version": "1.0.0",
            "description": "A test contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            }
        }

        # Normalize to HubContract
        norm_result = self.normalizer.normalize(original_odcs, spec_version="3.0.0")
        # Status can be NORMALIZED_OK or NORMALIZED_WITH_WARNINGS
        self.assertIn(norm_result.status.value, ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"])
        self.assertIsNotNone(norm_result.hub_contract, f"Normalization failed with errors: {norm_result.errors}")
        hub_contract = norm_result.hub_contract

        # Generate back to ODCS 3.0.0
        generated_odcs = self.generator.generate_odcs_from_hubcontract(hub_contract)

        # Verify basic fields match
        self.assertEqual(generated_odcs["apiVersion"], "odcs.io/v3.0.0")
        self.assertEqual(generated_odcs["kind"], "DataContract")
        self.assertEqual(generated_odcs["id"], original_odcs["id"])
        self.assertEqual(generated_odcs["name"], original_odcs["name"])
        self.assertEqual(generated_odcs["version"], original_odcs["version"])
        self.assertEqual(generated_odcs["description"], original_odcs["description"])

        # Verify schema matches
        self.assertIn("schema", generated_odcs)
        self.assertIn("fields", generated_odcs["schema"])
        self.assertEqual(len(generated_odcs["schema"]["fields"]), 2)

    def test_round_trip_with_quality(self):
        """Test round-trip with quality section"""
        original_odcs = {
            "apiVersion": "odcs.io/v3.0.0",
            "kind": "DataContract",
            "id": "test-contract-1",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"}
                ]
            },
            "quality": {
                "rules": [
                    {
                        "name": "completeness",
                        "type": "metric",
                        "threshold": 0.95
                    }
                ]
            }
        }

        # Normalize to HubContract
        norm_result = self.normalizer.normalize(original_odcs, spec_version="3.0.0")
        # Status can be NORMALIZED_OK or NORMALIZED_WITH_WARNINGS
        self.assertIn(norm_result.status.value, ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"])
        self.assertIsNotNone(norm_result.hub_contract, f"Normalization failed with errors: {norm_result.errors}")
        hub_contract = norm_result.hub_contract

        # Generate back to ODCS 3.0.0
        generated_odcs = self.generator.generate_odcs_from_hubcontract(hub_contract)

        # Verify quality section is present
        self.assertIn("quality", generated_odcs)
        self.assertIn("rules", generated_odcs["quality"])

