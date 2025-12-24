"""
Comprehensive regression tests for ODCS backward compatibility.

Tests all ODCS versions (3.0.2, 3.0.1, 3.0.0, 3.0.0-preview, 2.2.2) to ensure:
1. No regression in existing normalization
2. Graceful degradation for older versions
3. Consistent output format across all versions
4. All critical fields are normalized correctly

This test suite ensures that version-specific normalizers maintain backward
compatibility and handle older versions gracefully.
"""
from django.test import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import (
    normalize_contract,
    get_normalizer,
    NormalizationResult,
)
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_2 import ODCSNormalizerV3_0_2
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_1 import ODCSNormalizerV3_0_1
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0 import ODCSNormalizerV3_0_0
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0_preview import ODCSNormalizerV3_0_0_Preview
from hub.apps.contracts.normalization.odcs_normalizer_v2_2_2 import ODCSNormalizerV2_2_2


class ODCSBackwardCompatibilityRegressionTest(TestCase):
    """Comprehensive regression tests for all ODCS versions."""

    def _create_base_odcs_contract(self, version: str) -> dict:
        """Create a base ODCS contract for the given version."""
        return {
            "apiVersion": f"odcs.io/v{version}",
            "kind": "DataContract",
            "id": f"test-contract-{version}",
            "name": f"Test Contract {version}",
            "version": "1.0.0",
            "description": f"Test contract for ODCS {version}",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False,
                        "description": "Unique identifier"
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "nullable": False,
                        "description": "Name field"
                    },
                    {
                        "name": "value",
                        "type": "number",
                        "nullable": True,
                        "description": "Numeric value"
                    }
                ]
            },
            "info": {
                "owners": [
                    {
                        "name": "Test Owner",
                        "email": "owner@example.com"
                    }
                ],
                "tags": ["test", "regression"]
            }
        }

    def _create_advanced_odcs_contract(self, version: str) -> dict:
        """Create an advanced ODCS contract with all features for the given version."""
        contract = self._create_base_odcs_contract(version)

        # Add quality section (available in all versions)
        contract["quality"] = {
            "default_profile_key": "default_profile",
            "rules": [
                {
                    "id": "rule1",
                    "name": "Completeness Check",
                    "type": "completeness",
                    "rule": "id IS NOT NULL"
                }
            ]
        }

        # Add lifecycle section (available in all versions)
        contract["lifecycle"] = {
            "data_source": "database",
            "refresh_cadence": "daily"
        }

        # Add marketplace section (available in 3.0.1+)
        if version in ["3.0.2", "3.0.1"]:
            contract["marketplace"] = {
                "pricing": {
                    "model": "free"
                }
            }

        return contract

    def test_odcs_3_0_2_normalization_no_regression(self):
        """Test that ODCS 3.0.2 normalization produces expected output (baseline)."""
        contract_data = self._create_advanced_odcs_contract("3.0.2")

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.2", contract_data)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_2)

        result = normalizer.normalize(contract_data, spec_version="3.0.2")

        # Verify normalization succeeded
        self.assertIsNotNone(result.hub_contract)
        self.assertIn(NormalizationStatus.NORMALIZED_OK, [result.status, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(result.errors), 0)

        # Verify critical fields
        self.assertEqual(result.hub_contract["id"], "test-contract-3.0.2")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract 3.0.2")
        self.assertEqual(result.hub_contract["info"]["version"], "1.0.0")

        # Verify schema normalization
        self.assertIn("schema", result.hub_contract)
        self.assertIn("fields", result.hub_contract["schema"])
        self.assertEqual(len(result.hub_contract["schema"]["fields"]), 3)

        # Verify info section
        self.assertIn("owners", result.hub_contract["info"])
        self.assertIn("tags", result.hub_contract["info"])

        # Verify quality section
        self.assertIn("quality", result.hub_contract)

        # Verify lifecycle section
        self.assertIn("lifecycle", result.hub_contract)

        # Verify marketplace section (3.0.2 feature)
        self.assertIn("marketplace", result.hub_contract)

    def test_odcs_3_0_1_normalization_no_regression(self):
        """Test that ODCS 3.0.1 normalization produces expected output (no regression)."""
        contract_data = self._create_advanced_odcs_contract("3.0.1")

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.1", contract_data)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_1)

        result = normalizer.normalize(contract_data, spec_version="3.0.1")

        # Verify normalization succeeded
        self.assertIsNotNone(result.hub_contract)
        self.assertIn(NormalizationStatus.NORMALIZED_OK, [result.status, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(result.errors), 0)

        # Verify critical fields (same as 3.0.2)
        self.assertEqual(result.hub_contract["id"], "test-contract-3.0.1")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract 3.0.1")
        self.assertEqual(result.hub_contract["info"]["version"], "1.0.0")

        # Verify schema normalization
        self.assertIn("schema", result.hub_contract)
        self.assertIn("fields", result.hub_contract["schema"])
        self.assertEqual(len(result.hub_contract["schema"]["fields"]), 3)

        # Verify marketplace section (3.0.1 feature)
        self.assertIn("marketplace", result.hub_contract)

    def test_odcs_3_0_0_normalization_no_regression(self):
        """Test that ODCS 3.0.0 normalization produces expected output (no regression)."""
        contract_data = self._create_advanced_odcs_contract("3.0.0")

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.0", contract_data)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_0)

        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        # Verify normalization succeeded
        self.assertIsNotNone(result.hub_contract)
        self.assertIn(NormalizationStatus.NORMALIZED_OK, [result.status, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(result.errors), 0)

        # Verify critical fields
        self.assertEqual(result.hub_contract["id"], "test-contract-3.0.0")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract 3.0.0")
        self.assertEqual(result.hub_contract["info"]["version"], "1.0.0")

        # Verify schema normalization
        self.assertIn("schema", result.hub_contract)
        self.assertIn("fields", result.hub_contract["schema"])
        self.assertEqual(len(result.hub_contract["schema"]["fields"]), 3)

        # Verify graceful degradation: marketplace may not be present in 3.0.0
        # (depends on implementation, but should not cause errors)

    def test_odcs_3_0_0_preview_normalization_no_regression(self):
        """Test that ODCS 3.0.0-preview normalization produces expected output (no regression)."""
        contract_data = self._create_advanced_odcs_contract("3.0.0-preview")

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.0-preview", contract_data)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV3_0_0_Preview)

        result = normalizer.normalize(contract_data, spec_version="3.0.0-preview")

        # Verify normalization succeeded
        self.assertIsNotNone(result.hub_contract)
        self.assertIn(NormalizationStatus.NORMALIZED_OK, [result.status, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(result.errors), 0)

        # Verify critical fields
        self.assertEqual(result.hub_contract["id"], "test-contract-3.0.0-preview")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract 3.0.0-preview")
        self.assertEqual(result.hub_contract["info"]["version"], "1.0.0")

        # Verify schema normalization
        self.assertIn("schema", result.hub_contract)
        self.assertIn("fields", result.hub_contract["schema"])
        self.assertEqual(len(result.hub_contract["schema"]["fields"]), 3)

    def test_odcs_2_2_2_normalization_no_regression(self):
        """Test that ODCS 2.2.2 normalization produces expected output (no regression)."""
        contract_data = self._create_advanced_odcs_contract("2.2.2")

        normalizer = get_normalizer(OriginalSpecType.ODCS, "2.2.2", contract_data)
        self.assertIsNotNone(normalizer)
        self.assertIsInstance(normalizer, ODCSNormalizerV2_2_2)

        result = normalizer.normalize(contract_data, spec_version="2.2.2")

        # Verify normalization succeeded
        self.assertIsNotNone(result.hub_contract)
        self.assertIn(NormalizationStatus.NORMALIZED_OK, [result.status, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(result.errors), 0)

        # Verify critical fields
        self.assertEqual(result.hub_contract["id"], "test-contract-2.2.2")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract 2.2.2")
        self.assertEqual(result.hub_contract["info"]["version"], "1.0.0")

        # Verify schema normalization
        self.assertIn("schema", result.hub_contract)
        self.assertIn("fields", result.hub_contract["schema"])
        self.assertEqual(len(result.hub_contract["schema"]["fields"]), 3)

    def test_graceful_degradation_3_0_0_missing_3_0_1_features(self):
        """Test graceful degradation when 3.0.0 contract is missing 3.0.1+ features."""
        contract_data = self._create_base_odcs_contract("3.0.0")
        # Intentionally omit marketplace section (3.0.1+ feature)

        normalizer = get_normalizer(OriginalSpecType.ODCS, "3.0.0", contract_data)
        result = normalizer.normalize(contract_data, spec_version="3.0.0")

        # Should normalize successfully without marketplace
        self.assertIsNotNone(result.hub_contract)
        self.assertIn(NormalizationStatus.NORMALIZED_OK, [result.status, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(result.errors), 0)

        # Critical fields should still be present
        self.assertEqual(result.hub_contract["id"], "test-contract-3.0.0")
        self.assertIn("schema", result.hub_contract)

    def test_graceful_degradation_2_2_2_missing_3_x_features(self):
        """Test graceful degradation when 2.2.2 contract is missing 3.x features."""
        contract_data = self._create_base_odcs_contract("2.2.2")
        # Intentionally omit 3.x-specific features

        normalizer = get_normalizer(OriginalSpecType.ODCS, "2.2.2", contract_data)
        result = normalizer.normalize(contract_data, spec_version="2.2.2")

        # Should normalize successfully without 3.x features
        self.assertIsNotNone(result.hub_contract)
        self.assertIn(NormalizationStatus.NORMALIZED_OK, [result.status, NormalizationStatus.NORMALIZED_WITH_WARNINGS])
        self.assertEqual(len(result.errors), 0)

        # Critical fields should still be present
        self.assertEqual(result.hub_contract["id"], "test-contract-2.2.2")
        self.assertIn("schema", result.hub_contract)

    def test_all_versions_produce_consistent_output_format(self):
        """Test that all ODCS versions produce consistent output format."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]
        results = {}

        for version in versions:
            contract_data = self._create_base_odcs_contract(version)
            normalizer = get_normalizer(OriginalSpecType.ODCS, version, contract_data)
            result = normalizer.normalize(contract_data, spec_version=version)
            results[version] = result.hub_contract

        # All versions should produce hub contracts with same structure
        for version, hub_contract in results.items():
            self.assertIsNotNone(hub_contract)
            # All should have these core fields
            self.assertIn("id", hub_contract)
            self.assertIn("info", hub_contract)
            self.assertIn("schema", hub_contract)
            self.assertIn("info", hub_contract)
            self.assertIn("name", hub_contract["info"])
            self.assertIn("version", hub_contract["info"])
            self.assertIn("fields", hub_contract["schema"])

    def test_all_versions_normalize_schema_fields_correctly(self):
        """Test that all versions normalize schema fields correctly."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            contract_data = self._create_base_odcs_contract(version)
            normalizer = get_normalizer(OriginalSpecType.ODCS, version, contract_data)
            result = normalizer.normalize(contract_data, spec_version=version)

            # All versions should normalize schema fields correctly
            self.assertIsNotNone(result.hub_contract)
            self.assertIn("schema", result.hub_contract)
            self.assertIn("fields", result.hub_contract["schema"])
            self.assertEqual(len(result.hub_contract["schema"]["fields"]), 3)

            # Verify field structure
            for field in result.hub_contract["schema"]["fields"]:
                self.assertIn("name", field)
                self.assertIn("data_type", field)  # Fields use data_type, not type

    def test_all_versions_normalize_info_section_correctly(self):
        """Test that all versions normalize info section correctly."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            contract_data = self._create_base_odcs_contract(version)
            normalizer = get_normalizer(OriginalSpecType.ODCS, version, contract_data)
            result = normalizer.normalize(contract_data, spec_version=version)

            # All versions should normalize info section correctly
            self.assertIsNotNone(result.hub_contract)
            self.assertIn("info", result.hub_contract)
            self.assertIn("name", result.hub_contract["info"])
            self.assertIn("version", result.hub_contract["info"])
            self.assertIn("owners", result.hub_contract["info"])
            self.assertIn("tags", result.hub_contract["info"])

    def test_no_regression_in_normalization_status(self):
        """Test that normalization status is consistent across versions."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            contract_data = self._create_base_odcs_contract(version)
            normalizer = get_normalizer(OriginalSpecType.ODCS, version, contract_data)
            result = normalizer.normalize(contract_data, spec_version=version)

            # All valid contracts should normalize successfully
            self.assertIsNotNone(result.hub_contract)
            self.assertIn(
                result.status,
                [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS]
            )
            self.assertEqual(len(result.errors), 0)

    def test_no_regression_in_error_handling(self):
        """Test that error handling is consistent across versions."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        # Test with invalid contract (missing required fields)
        invalid_contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract"
            # Missing id, name, schema
        }

        for version in versions:
            invalid_contract["apiVersion"] = f"odcs.io/v{version}"
            normalizer = get_normalizer(OriginalSpecType.ODCS, version, invalid_contract)
            result = normalizer.normalize(invalid_contract, spec_version=version)

            # All versions should handle errors consistently
            # Either fail with errors or produce contract with warnings
            self.assertTrue(
                result.status == NormalizationStatus.NORMALIZATION_FAILED or
                (result.hub_contract is not None and len(result.warnings) > 0)
            )

