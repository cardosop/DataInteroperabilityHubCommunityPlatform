"""
Unit tests for ODCS Generator Main Function (generate_odcs_from_hubcontract).

Tests the main generation function with metrics, logging, and error handling
following engineering best practices without mocks/stubs.
"""
import pytest
import time
from django.test import TestCase

from hub.apps.contracts.odcs_generator import (
    generate_odcs_from_hubcontract,
    get_supported_odcs_versions,
)
from hub.apps.contracts.odcs_format_converter import (
    format_odcs_as_json,
    format_odcs_as_yaml,
    convert_yaml_to_json,
    convert_json_to_yaml,
)
from hub.apps.contracts.odcs_errors import ODCSGenerationError

pytestmark = pytest.mark.django_db(transaction=True)


class ODCSGeneratorMainFunctionTest(TestCase):
    """Test the main generate_odcs_from_hubcontract function"""

    def setUp(self):
        """Set up test fixtures"""
        self.minimal_hub_contract = {
            "id": "test-main-1",
            "info": {
                "name": "Test Contract",
                "version": "1.0.0"
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"}
                ]
            }
        }

    def test_generate_with_minimal_contract(self):
        """Test generation with minimal HubContract"""
        odcs = generate_odcs_from_hubcontract(self.minimal_hub_contract)

        self.assertIsInstance(odcs, dict)
        self.assertEqual(odcs["id"], "test-main-1")
        self.assertEqual(odcs["name"], "Test Contract")
        self.assertIn("apiVersion", odcs)
        self.assertIn("kind", odcs)

    def test_generate_with_explicit_version(self):
        """Test generation with explicit version parameter"""
        odcs = generate_odcs_from_hubcontract(
            self.minimal_hub_contract,
            target_version="3.0.0"
        )

        self.assertEqual(odcs["apiVersion"], "odcs.io/v3.0.0")

    def test_generate_with_version_detection(self):
        """Test generation with version detection from HubContract"""
        hub_contract = {
            "id": "test-main-2",
            "info": {"name": "Test Contract"},
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "original_spec": {
                "type": "ODCS",
                "version": "3.0.1"
            }
        }

        odcs = generate_odcs_from_hubcontract(hub_contract)

        # Should detect and use version 3.0.1
        self.assertEqual(odcs["apiVersion"], "odcs.io/v3.0.1")

    def test_generate_with_tenant_id(self):
        """Test generation with tenant_id parameter for metrics"""
        odcs = generate_odcs_from_hubcontract(
            self.minimal_hub_contract,
            tenant_id="test-tenant-123"
        )

        self.assertIsInstance(odcs, dict)
        self.assertEqual(odcs["id"], "test-main-1")


class ODCSGeneratorAllVersionsTest(TestCase):
    """Test generation for all supported ODCS versions"""

    def setUp(self):
        """Set up test fixtures"""
        self.hub_contract = {
            "id": "test-all-versions",
            "info": {
                "name": "All Versions Test",
                "version": "1.0.0",
                "description": "Test contract for all versions"
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"}
                ],
                "primary_key": ["id"]
            }
        }

    def test_generate_version_3_0_2(self):
        """Test generation for ODCS 3.0.2"""
        odcs = generate_odcs_from_hubcontract(
            self.hub_contract,
            target_version="3.0.2"
        )

        self.assertEqual(odcs["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(odcs["id"], "test-all-versions")
        self.assertIn("schema", odcs)

    def test_generate_version_3_0_1(self):
        """Test generation for ODCS 3.0.1"""
        odcs = generate_odcs_from_hubcontract(
            self.hub_contract,
            target_version="3.0.1"
        )

        self.assertEqual(odcs["apiVersion"], "odcs.io/v3.0.1")
        self.assertEqual(odcs["id"], "test-all-versions")

    def test_generate_version_3_0_0(self):
        """Test generation for ODCS 3.0.0"""
        odcs = generate_odcs_from_hubcontract(
            self.hub_contract,
            target_version="3.0.0"
        )

        self.assertEqual(odcs["apiVersion"], "odcs.io/v3.0.0")
        self.assertEqual(odcs["id"], "test-all-versions")

    def test_generate_version_3_0_0_preview(self):
        """Test generation for ODCS 3.0.0-preview"""
        odcs = generate_odcs_from_hubcontract(
            self.hub_contract,
            target_version="3.0.0-preview"
        )

        self.assertEqual(odcs["apiVersion"], "odcs.io/v3.0.0-preview")
        self.assertEqual(odcs["id"], "test-all-versions")

    def test_generate_version_2_2_2(self):
        """Test generation for ODCS 2.2.2"""
        odcs = generate_odcs_from_hubcontract(
            self.hub_contract,
            target_version="2.2.2"
        )

        self.assertEqual(odcs["apiVersion"], "odcs.io/v2.2.2")
        self.assertEqual(odcs["id"], "test-all-versions")


class ODCSGeneratorFormatConversionTest(TestCase):
    """Test YAML/JSON format conversion"""

    def setUp(self):
        """Set up test fixtures"""
        self.hub_contract = {
            "id": "test-format",
            "info": {
                "name": "Format Test Contract",
                "version": "1.0.0",
                "description": "Test contract for format conversion"
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            }
        }

    def test_generate_and_format_as_json(self):
        """Test generation and JSON formatting"""
        odcs = generate_odcs_from_hubcontract(self.hub_contract)

        # Format as JSON
        json_result = format_odcs_as_json(odcs)

        self.assertIsInstance(json_result, str)
        self.assertIn("apiVersion", json_result)
        self.assertIn("odcs.io/v", json_result)

        # Verify it's valid JSON
        import json
        parsed = json.loads(json_result)
        self.assertEqual(parsed["id"], "test-format")

    def test_generate_and_format_as_yaml(self):
        """Test generation and YAML formatting"""
        odcs = generate_odcs_from_hubcontract(self.hub_contract)

        # Format as YAML
        yaml_result = format_odcs_as_yaml(odcs)

        self.assertIsInstance(yaml_result, str)
        self.assertIn("apiVersion", yaml_result)
        self.assertIn("odcs.io/v", yaml_result)

    def test_format_conversion_yaml_to_json(self):
        """Test YAML to JSON conversion"""
        odcs = generate_odcs_from_hubcontract(self.hub_contract)
        yaml_result = format_odcs_as_yaml(odcs)

        # Convert YAML to JSON
        json_result = convert_yaml_to_json(yaml_result)

        self.assertIsInstance(json_result, str)
        import json
        parsed = json.loads(json_result)
        self.assertEqual(parsed["id"], "test-format")

    def test_format_conversion_json_to_yaml(self):
        """Test JSON to YAML conversion"""
        odcs = generate_odcs_from_hubcontract(self.hub_contract)
        json_result = format_odcs_as_json(odcs)

        # Convert JSON to YAML
        yaml_result = convert_json_to_yaml(json_result)

        self.assertIsInstance(yaml_result, str)
        self.assertIn("apiVersion", yaml_result)


class ODCSGeneratorErrorHandlingTest(TestCase):
    """Test error handling in main function"""

    def test_generate_with_invalid_hubcontract_type(self):
        """Test error handling for invalid HubContract type"""
        with self.assertRaises(ODCSGenerationError) as cm:
            generate_odcs_from_hubcontract("not a dict")

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_GENERATION_FAILED)
        self.assertIn("dictionary", error.message.lower())

    def test_generate_with_missing_info(self):
        """Test error handling for missing info section"""
        invalid_contract = {
            "id": "test-error"
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)

    def test_generate_with_missing_name(self):
        """Test error handling for missing name"""
        invalid_contract = {
            "id": "test-error",
            "info": {}
        }

        with self.assertRaises(ODCSGenerationError) as cm:
            generate_odcs_from_hubcontract(invalid_contract)

        error = cm.exception
        self.assertEqual(error.error_code, ODCSGenerationError.ERROR_CODE_MISSING_REQUIRED_FIELD)
        self.assertIn("name", error.message.lower())


class ODCSGeneratorPerformanceTest(TestCase):
    """Test performance requirements"""

    def setUp(self):
        """Set up test fixtures"""
        self.typical_hub_contract = {
            "id": "test-performance",
            "info": {
                "name": "Performance Test Contract",
                "version": "1.0.0",
                "description": "A typical contract for performance testing",
                "owners": [
                    {"name": "John Doe", "email": "john@example.com"}
                ],
                "tags": ["production", "critical"]
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string"},
                    {"name": "email", "type": "string", "format": "email"},
                    {"name": "created_at", "type": "datetime"}
                ],
                "primary_key": ["id"]
            },
            "quality": {
                "rules": [
                    {"name": "completeness", "type": "metric", "threshold": 0.95}
                ]
            },
            "lifecycle": {
                "data_source": "database",
                "refresh_cadence": "daily"
            }
        }

    def test_generation_performance_under_2_seconds(self):
        """Test that generation completes in under 2 seconds (p95 requirement)"""
        # Run multiple times to get a better sense of performance
        durations = []
        for _ in range(10):
            start = time.time()
            odcs = generate_odcs_from_hubcontract(self.typical_hub_contract)
            duration = time.time() - start
            durations.append(duration)
            self.assertIsInstance(odcs, dict)

        # Calculate p95 (95th percentile)
        durations.sort()
        p95_index = int(len(durations) * 0.95)
        p95_duration = durations[p95_index] if p95_index < len(durations) else durations[-1]

        # p95 should be under 2 seconds
        self.assertLess(p95_duration, 2.0, f"p95 duration {p95_duration:.3f}s exceeds 2s threshold")

        # Average should also be reasonable
        avg_duration = sum(durations) / len(durations)
        self.assertLess(avg_duration, 1.0, f"Average duration {avg_duration:.3f}s is too high")

    def test_generation_performance_all_versions(self):
        """Test performance for all versions"""
        versions = get_supported_odcs_versions()

        for version in versions:
            start = time.time()
            odcs = generate_odcs_from_hubcontract(
                self.typical_hub_contract,
                target_version=version
            )
            duration = time.time() - start

            self.assertIsInstance(odcs, dict)
            # Each version should complete in under 2 seconds
            self.assertLess(duration, 2.0, f"Version {version} took {duration:.3f}s (exceeds 2s)")

