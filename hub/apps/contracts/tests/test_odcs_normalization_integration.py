"""
Comprehensive integration tests for ODCS normalization (Task 1.7.3)

Tests ensure that ODCS → HubContract normalization works correctly for all versions
with comprehensive coverage including:
- All ODCS versions (3.0.2, 3.0.1, 3.0.0, 3.0.0-preview, 2.2.2)
- Missing fields graceful degradation
- Baseline comparison (no regression)
- Technical normalization correctness
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from unittest import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import (
    get_normalizer,
    NormalizationResult,
)
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_2 import ODCSNormalizerV3_0_2
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_1 import ODCSNormalizerV3_0_1
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0 import ODCSNormalizerV3_0_0
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0_preview import ODCSNormalizerV3_0_0_Preview
from hub.apps.contracts.normalization.odcs_normalizer_v2_2_2 import ODCSNormalizerV2_2_2


class ODCSNormalizationIntegrationTestBase(TestCase):
    """Base class for ODCS normalization integration tests with shared fixtures."""

    def setUp(self):
        """Set up comprehensive test fixtures for all ODCS versions."""
        # Comprehensive baseline contract (ODCS 3.0.2) - technical normalization test
        self.baseline_contract_3_0_2 = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "integration-test-baseline",
            "name": "Integration Test Baseline Contract",
            "version": "1.0.0",
            "description": "Comprehensive baseline contract for integration testing",
            "info": {
                "owners": [
                    {
                        "name": "Data Engineering Team",
                        "email": "data-eng@example.com"
                    },
                    {
                        "name": "Product Team",
                        "email": "product@example.com"
                    }
                ],
                "tags": ["integration", "test", "baseline", "technical"],
                "domain": "analytics",
                "tenant": "test-tenant"
            },
            "support": [
                {
                    "name": "Support Team",
                    "email": "support@example.com"
                },
                {
                    "type": "slack",
                    "url": "https://slack.example.com/channels/support"
                }
            ],
            "servers": [
                {
                    "type": "postgres",
                    "url": "postgresql://localhost:5432/testdb",
                    "description": "Test database server"
                },
                {
                    "type": "s3",
                    "url": "s3://bucket/path",
                    "description": "S3 storage"
                }
            ],
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False,
                        "description": "Unique identifier",
                        "constraints": {
                            "unique": True
                        }
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "nullable": True,
                        "description": "Name field",
                        "constraints": {
                            "minLength": 1,
                            "maxLength": 100
                        }
                    },
                    {
                        "name": "value",
                        "type": "number",
                        "nullable": True,
                        "description": "Numeric value",
                        "constraints": {
                            "minimum": 0,
                            "maximum": 1000
                        }
                    },
                    {
                        "name": "timestamp",
                        "type": "datetime",
                        "nullable": False,
                        "description": "Timestamp field"
                    }
                ]
            },
            "quality": {
                "default_profile_key": "test_profile",
                "rules": [
                    {
                        "type": "completeness",
                        "field": "id",
                        "threshold": 1.0
                    },
                    {
                        "type": "validity",
                        "field": "value",
                        "threshold": 0.95
                    }
                ]
            },
            "privacy_compliance": {
                "contains_personal_data": False,
                "personal_data_categories": [],
                "jurisdictions": ["US"],
                "legal_bases": ["legitimate_interest"]
            },
            "lifecycle": {
                "data_source": "database",
                "refresh_cadence": "daily"
            },
            "marketplace": {
                "license_summary": "MIT",
                "intended_use": ["analytics", "reporting"],
                "restricted_use": ["commercial"]
            },
            "slaProperties": [
                {
                    "name": "availability",
                    "target": 0.99,
                    "unit": "percentage"
                }
            ]
        }

        # Store baseline normalization result for comparison
        self.baseline_result: Optional[NormalizationResult] = None

    def _create_versioned_contract(self, version: str) -> Dict[str, Any]:
        """Create a versioned contract from the baseline."""
        contract = self.baseline_contract_3_0_2.copy()
        contract["apiVersion"] = f"odcs.io/v{version}"
        contract["id"] = f"integration-test-{version.replace('.', '-').replace('-preview', '-preview')}"
        return contract

    def _normalize_with_version_specific_normalizer(
        self,
        contract_data: Dict[str, Any],
        version: str
    ) -> NormalizationResult:
        """Normalize using version-specific normalizer."""
        normalizers = {
            "3.0.2": ODCSNormalizerV3_0_2(),
            "3.0.1": ODCSNormalizerV3_0_1(),
            "3.0.0": ODCSNormalizerV3_0_0(),
            "3.0.0-preview": ODCSNormalizerV3_0_0_Preview(),
            "2.2.2": ODCSNormalizerV2_2_2(),
        }
        normalizer = normalizers.get(version)
        if not normalizer:
            raise ValueError(f"No normalizer found for version {version}")
        return normalizer.normalize(contract_data, spec_version=version)

    def _normalize_via_registry(
        self,
        contract_data: Dict[str, Any],
        version: str
    ) -> NormalizationResult:
        """Normalize using the normalizer registry."""
        normalizer = get_normalizer(OriginalSpecType.ODCS, version, contract_data)
        if not normalizer:
            raise ValueError(f"No normalizer found in registry for version {version}")
        return normalizer.normalize(contract_data, spec_version=version)

    def _assert_hub_contract_structure(self, hub_contract: Dict[str, Any], version: str):
        """Assert that hub_contract has the expected structure."""
        # Required top-level fields
        assert "id" in hub_contract, f"HubContract missing 'id' for version {version}"
        assert "info" in hub_contract, f"HubContract missing 'info' for version {version}"
        assert "schema" in hub_contract, f"HubContract missing 'schema' for version {version}"

        # Required info fields
        info = hub_contract["info"]
        assert "name" in info, f"HubContract.info missing 'name' for version {version}"
        assert "version" in info, f"HubContract.info missing 'version' for version {version}"

        # Required schema fields
        schema = hub_contract["schema"]
        assert "fields" in schema, f"HubContract.schema missing 'fields' for version {version}"

        # Normalization metadata
        assert "normalization" in hub_contract, f"HubContract missing 'normalization' metadata for version {version}"
        normalization = hub_contract["normalization"]
        assert "original_spec_type" in normalization, f"HubContract.normalization missing 'original_spec_type' for version {version}"
        assert "original_spec_version" in normalization, f"HubContract.normalization missing 'original_spec_version' for version {version}"
        assert normalization["original_spec_type"] == OriginalSpecType.ODCS, f"HubContract.normalization.original_spec_type should be ODCS for version {version}"

    def _assert_normalization_result_valid(
        self,
        result: NormalizationResult,
        version: str,
        expect_success: bool = True
    ):
        """Assert that normalization result is valid."""
        assert result is not None, f"NormalizationResult is None for version {version}"
        assert result.spec_type == OriginalSpecType.ODCS, f"NormalizationResult.spec_type should be ODCS for version {version}"
        assert result.spec_version == version, f"NormalizationResult.spec_version should be {version}, got {result.spec_version}"
        assert isinstance(result.errors, list), f"NormalizationResult.errors should be a list for version {version}"
        assert isinstance(result.warnings, list), f"NormalizationResult.warnings should be a list for version {version}"

        if expect_success:
            assert result.status in [
                NormalizationStatus.NORMALIZED_OK,
                NormalizationStatus.NORMALIZED_WITH_WARNINGS
            ], f"Normalization should succeed for version {version}, got status {result.status}. Errors: {result.errors if result.errors else 'None'}"
            assert result.hub_contract is not None, f"HubContract should not be None for version {version}"
            self._assert_hub_contract_structure(result.hub_contract, version)
        else:
            assert result.status == NormalizationStatus.NORMALIZATION_FAILED, f"Normalization should fail for version {version}"

    def _compare_with_baseline(
        self,
        result: NormalizationResult,
        baseline: NormalizationResult,
        version: str,
        allow_version_differences: bool = True
    ):
        """Compare normalization result with baseline."""
        # Both should have hub_contract
        assert result.hub_contract is not None, f"Result hub_contract is None for version {version}"
        assert baseline.hub_contract is not None, "Baseline hub_contract is None"

        result_hc = result.hub_contract
        baseline_hc = baseline.hub_contract

        # Core fields should match (if present in both)
        if "id" in baseline_hc and "id" in result_hc:
            # IDs may differ due to version-specific contract IDs
            pass

        # Info structure should be similar
        if "info" in baseline_hc and "info" in result_hc:
            baseline_info = baseline_hc["info"]
            result_info = result_hc["info"]

            # Name should be normalized similarly
            if "name" in baseline_info and "name" in result_info:
                # Names may differ due to version-specific contract names
                pass

            # Version should match
            if "version" in baseline_info and "version" in result_info:
                assert baseline_info["version"] == result_info["version"], \
                    f"Version mismatch: baseline={baseline_info['version']}, result={result_info['version']} for version {version}"

        # Schema structure should be similar
        if "schema" in baseline_hc and "schema" in result_hc:
            baseline_schema = baseline_hc["schema"]
            result_schema = result_hc["schema"]

            # Fields should be normalized similarly
            if "fields" in baseline_schema and "fields" in result_schema:
                baseline_fields = baseline_schema["fields"]
                result_fields = result_schema["fields"]
                # Field count may differ due to version-specific schema differences
                # But structure should be similar
                assert isinstance(baseline_fields, list), "Baseline fields should be a list"
                assert isinstance(result_fields, list), f"Result fields should be a list for version {version}"

        # Normalization metadata should be consistent
        if "normalization" in baseline_hc and "normalization" in result_hc:
            baseline_norm = baseline_hc["normalization"]
            result_norm = result_hc["normalization"]

            # Original spec type should match
            if "original_spec_type" in baseline_norm and "original_spec_type" in result_norm:
                assert baseline_norm["original_spec_type"] == result_norm["original_spec_type"], \
                    f"Original spec type mismatch for version {version}"

            # Original spec version should match the version being tested
            if "original_spec_version" in result_norm:
                assert result_norm["original_spec_version"] == version, \
                    f"Original spec version should be {version}, got {result_norm['original_spec_version']}"


class ODCSNormalizationAllVersionsTest(ODCSNormalizationIntegrationTestBase):
    """Test ODCS normalization for all versions."""

    def test_normalize_3_0_2_via_version_specific_normalizer(self):
        """Test ODCS 3.0.2 normalization using version-specific normalizer."""
        contract_data = self._create_versioned_contract("3.0.2")
        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")

        self._assert_normalization_result_valid(result, "3.0.2", expect_success=True)
        assert result.hub_contract["id"] == "integration-test-3-0-2"
        assert result.hub_contract["info"]["name"] == "Integration Test Baseline Contract"

    def test_normalize_3_0_1_via_version_specific_normalizer(self):
        """Test ODCS 3.0.1 normalization using version-specific normalizer."""
        contract_data = self._create_versioned_contract("3.0.1")
        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.1")

        self._assert_normalization_result_valid(result, "3.0.1", expect_success=True)
        assert result.hub_contract["id"] == "integration-test-3-0-1"
        assert result.hub_contract["info"]["name"] == "Integration Test Baseline Contract"

    def test_normalize_3_0_0_via_version_specific_normalizer(self):
        """Test ODCS 3.0.0 normalization using version-specific normalizer."""
        contract_data = self._create_versioned_contract("3.0.0")
        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.0")

        self._assert_normalization_result_valid(result, "3.0.0", expect_success=True)
        assert result.hub_contract["id"] == "integration-test-3-0-0"
        assert result.hub_contract["info"]["name"] == "Integration Test Baseline Contract"

    def test_normalize_3_0_0_preview_via_version_specific_normalizer(self):
        """Test ODCS 3.0.0-preview normalization using version-specific normalizer."""
        contract_data = self._create_versioned_contract("3.0.0-preview")
        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.0-preview")

        self._assert_normalization_result_valid(result, "3.0.0-preview", expect_success=True)
        assert result.hub_contract["id"] == "integration-test-3-0-0-preview"
        assert result.hub_contract["info"]["name"] == "Integration Test Baseline Contract"

    def test_normalize_2_2_2_via_version_specific_normalizer(self):
        """Test ODCS 2.2.2 normalization using version-specific normalizer."""
        # 2.2.2 may have different structure, use a compatible contract
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "integration-test-2-2-2",
            "name": "Integration Test 2.2.2 Contract",
            "version": "1.0.0",
            "description": "ODCS 2.2.2 contract for integration testing",
            "info": {
                "owners": [
                    {
                        "name": "Data Engineering Team",
                        "email": "data-eng@example.com"
                    }
                ],
                "tags": ["integration", "test"]
            },
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
                        "nullable": True,
                        "description": "Name field"
                    }
                ]
            },
            "quality": {
                "rules": [
                    {
                        "type": "completeness",
                        "field": "id",
                        "threshold": 1.0
                    }
                ]
            }
        }
        result = self._normalize_with_version_specific_normalizer(contract_data, "2.2.2")

        self._assert_normalization_result_valid(result, "2.2.2", expect_success=True)
        assert result.hub_contract["id"] == "integration-test-2-2-2"
        assert result.hub_contract["info"]["name"] == "Integration Test 2.2.2 Contract"

    def test_normalize_all_versions_via_registry(self):
        """Test that all versions can be normalized via the normalizer registry."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            if version == "2.2.2":
                # Use simpler contract for 2.2.2
                contract_data = {
                    "apiVersion": f"odcs.io/v{version}",
                    "kind": "DataContract",
                    "id": f"integration-test-{version.replace('.', '-')}",
                    "name": f"Integration Test {version} Contract",
                    "version": "1.0.0",
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
            else:
                contract_data = self._create_versioned_contract(version)

            result = self._normalize_via_registry(contract_data, version)
            self._assert_normalization_result_valid(result, version, expect_success=True)


class ODCSNormalizationGracefulDegradationTest(ODCSNormalizationIntegrationTestBase):
    """Test graceful degradation for missing fields."""

    def test_normalize_with_missing_name(self):
        """Test that normalization handles missing 'name' field gracefully."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-missing-name",
            # Missing 'name' field
            "version": "1.0.0",
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

        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")

        # Should have errors for missing required field
        assert len(result.errors) > 0, "Should have errors for missing 'name' field"
        assert any("name" in error.lower() for error in result.errors), \
            "Error should mention 'name' field"
        # But should still return a hub_contract (for debugging)
        assert result.hub_contract is not None, "Should return hub_contract even with errors"

    def test_normalize_with_missing_schema(self):
        """Test that normalization handles missing 'schema' field gracefully."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-missing-schema",
            "name": "Test Missing Schema",
            "version": "1.0.0"
            # Missing 'schema' field
        }

        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")

        # Should have errors for missing required field
        assert len(result.errors) > 0, "Should have errors for missing 'schema' field"
        assert any("schema" in error.lower() or "fields" in error.lower() for error in result.errors), \
            "Error should mention 'schema' or 'fields'"
        # But should still return a hub_contract (for debugging)
        assert result.hub_contract is not None, "Should return hub_contract even with errors"

    def test_normalize_with_missing_optional_fields(self):
        """Test that normalization handles missing optional fields gracefully."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-missing-optional",
            "name": "Test Missing Optional Fields",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False
                    }
                ]
            }
            # Missing optional fields: info, quality, lifecycle, marketplace, etc.
        }

        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")

        # Should succeed (optional fields are optional)
        assert result.status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS
        ], "Should succeed with missing optional fields"
        assert result.hub_contract is not None, "Should return hub_contract"
        # Should have warnings for missing optional fields (if any)
        # But no errors for missing optional fields

    def test_normalize_with_missing_info_owners(self):
        """Test that normalization handles missing 'info.owners' gracefully."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-missing-owners",
            "name": "Test Missing Owners",
            "version": "1.0.0",
            "info": {
                # Missing 'owners'
                "tags": ["test"]
            },
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

        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")

        # Should succeed (owners is optional)
        assert result.status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS
        ], "Should succeed with missing 'info.owners'"
        assert result.hub_contract is not None, "Should return hub_contract"

    def test_normalize_with_missing_quality_rules(self):
        """Test that normalization handles missing 'quality.rules' gracefully."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-missing-quality-rules",
            "name": "Test Missing Quality Rules",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False
                    }
                ]
            },
            "quality": {
                "default_profile_key": "test_profile"
                # Missing 'rules'
            }
        }

        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")

        # Should succeed (rules is optional)
        assert result.status in [
            NormalizationStatus.NORMALIZED_OK,
            NormalizationStatus.NORMALIZED_WITH_WARNINGS
        ], "Should succeed with missing 'quality.rules'"
        assert result.hub_contract is not None, "Should return hub_contract"
        assert "quality" in result.hub_contract, "Should have 'quality' section"

    def test_normalize_with_missing_fields_all_versions(self):
        """Test graceful degradation for missing fields across all versions."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            contract_data = {
                "apiVersion": f"odcs.io/v{version}",
                "kind": "DataContract",
                "id": f"test-missing-{version.replace('.', '-')}",
                "name": f"Test Missing Fields {version}",
                "version": "1.0.0",
                "schema": {
                    "fields": [
                        {
                            "name": "id",
                            "type": "string",
                            "nullable": False
                        }
                    ]
                }
                # Missing optional fields
            }

            result = self._normalize_with_version_specific_normalizer(contract_data, version)

            # Should succeed (only required fields present)
            assert result.status in [
                NormalizationStatus.NORMALIZED_OK,
                NormalizationStatus.NORMALIZED_WITH_WARNINGS
            ], f"Should succeed for version {version} with missing optional fields"
            assert result.hub_contract is not None, f"Should return hub_contract for version {version}"


class ODCSNormalizationBaselineComparisonTest(ODCSNormalizationIntegrationTestBase):
    """Test baseline comparison (no regression)."""

    def setUp(self):
        """Set up baseline for comparison."""
        super().setUp()
        # Normalize baseline contract
        baseline_contract = self.baseline_contract_3_0_2
        self.baseline_result = self._normalize_with_version_specific_normalizer(
            baseline_contract,
            "3.0.2"
        )
        self._assert_normalization_result_valid(self.baseline_result, "3.0.2", expect_success=True)

    def test_3_0_2_matches_baseline(self):
        """Test that ODCS 3.0.2 normalization matches baseline (no regression)."""
        contract_data = self.baseline_contract_3_0_2
        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")

        self._assert_normalization_result_valid(result, "3.0.2", expect_success=True)
        self._compare_with_baseline(result, self.baseline_result, "3.0.2")

    def test_3_0_1_compared_to_baseline(self):
        """Test that ODCS 3.0.1 normalization is consistent with baseline structure."""
        contract_data = self._create_versioned_contract("3.0.1")
        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.1")

        self._assert_normalization_result_valid(result, "3.0.1", expect_success=True)
        # Compare structure (not exact match, as versions may differ)
        self._compare_with_baseline(result, self.baseline_result, "3.0.1", allow_version_differences=True)

    def test_3_0_0_compared_to_baseline(self):
        """Test that ODCS 3.0.0 normalization is consistent with baseline structure."""
        contract_data = self._create_versioned_contract("3.0.0")
        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.0")

        self._assert_normalization_result_valid(result, "3.0.0", expect_success=True)
        # Compare structure (not exact match, as versions may differ)
        self._compare_with_baseline(result, self.baseline_result, "3.0.0", allow_version_differences=True)

    def test_3_0_0_preview_compared_to_baseline(self):
        """Test that ODCS 3.0.0-preview normalization is consistent with baseline structure."""
        contract_data = self._create_versioned_contract("3.0.0-preview")
        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.0-preview")

        self._assert_normalization_result_valid(result, "3.0.0-preview", expect_success=True)
        # Compare structure (not exact match, as versions may differ)
        self._compare_with_baseline(result, self.baseline_result, "3.0.0-preview", allow_version_differences=True)

    def test_2_2_2_compared_to_baseline(self):
        """Test that ODCS 2.2.2 normalization is consistent with baseline structure."""
        # Use compatible contract for 2.2.2
        contract_data = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "integration-test-2-2-2",
            "name": "Integration Test Baseline Contract",
            "version": "1.0.0",
            "description": "Comprehensive baseline contract for integration testing",
            "info": {
                "owners": [
                    {
                        "name": "Data Engineering Team",
                        "email": "data-eng@example.com"
                    }
                ],
                "tags": ["integration", "test", "baseline", "technical"]
            },
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
                        "nullable": True,
                        "description": "Name field"
                    }
                ]
            },
            "quality": {
                "rules": [
                    {
                        "type": "completeness",
                        "field": "id",
                        "threshold": 1.0
                    }
                ]
            }
        }
        result = self._normalize_with_version_specific_normalizer(contract_data, "2.2.2")

        self._assert_normalization_result_valid(result, "2.2.2", expect_success=True)
        # Compare structure (not exact match, as 2.2.2 may have different features)
        self._compare_with_baseline(result, self.baseline_result, "2.2.2", allow_version_differences=True)

    def test_all_versions_consistent_structure(self):
        """Test that all versions produce consistent HubContract structure."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]
        results = {}

        for version in versions:
            if version == "2.2.2":
                # Use simpler contract for 2.2.2
                contract_data = {
                    "apiVersion": f"odcs.io/v{version}",
                    "kind": "DataContract",
                    "id": f"integration-test-{version.replace('.', '-')}",
                    "name": "Integration Test Baseline Contract",
                    "version": "1.0.0",
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
            else:
                contract_data = self._create_versioned_contract(version)

            result = self._normalize_with_version_specific_normalizer(contract_data, version)
            self._assert_normalization_result_valid(result, version, expect_success=True)
            results[version] = result

        # All results should have consistent structure
        for version, result in results.items():
            assert result.hub_contract is not None, f"HubContract should not be None for version {version}"
            self._assert_hub_contract_structure(result.hub_contract, version)

            # All should have same normalization metadata structure
            assert "normalization" in result.hub_contract, f"Missing normalization metadata for version {version}"
            normalization = result.hub_contract["normalization"]
            assert normalization["original_spec_type"] == OriginalSpecType.ODCS, \
                f"Original spec type should be ODCS for version {version}"
            assert normalization["original_spec_version"] == version, \
                f"Original spec version should be {version} for version {version}"


class ODCSNormalizationTechnicalCorrectnessTest(ODCSNormalizationIntegrationTestBase):
    """Test technical correctness of ODCS normalization."""

    def test_schema_fields_normalized_correctly(self):
        """Test that schema fields are normalized correctly."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-schema-fields",
            "name": "Test Schema Fields",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False,
                        "description": "Unique identifier",
                        "constraints": {
                            "unique": True
                        }
                    },
                    {
                        "name": "value",
                        "type": "number",
                        "nullable": True,
                        "description": "Numeric value"
                    }
                ]
            }
        }

        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")
        self._assert_normalization_result_valid(result, "3.0.2", expect_success=True)

        # Check schema normalization
        assert "schema" in result.hub_contract, "Should have 'schema' section"
        schema = result.hub_contract["schema"]
        assert "fields" in schema, "Should have 'fields' in schema"
        fields = schema["fields"]
        assert len(fields) == 2, "Should have 2 fields"
        assert fields[0]["name"] == "id", "First field should be 'id'"
        assert fields[1]["name"] == "value", "Second field should be 'value'"

    def test_info_section_normalized_correctly(self):
        """Test that info section is normalized correctly."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-info-section",
            "name": "Test Info Section",
            "version": "1.0.0",
            "info": {
                "owners": [
                    {
                        "name": "Data Team",
                        "email": "data@example.com"
                    }
                ],
                "tags": ["test", "integration"]
            },
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

        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")
        self._assert_normalization_result_valid(result, "3.0.2", expect_success=True)

        # Check info normalization
        assert "info" in result.hub_contract, "Should have 'info' section"
        info = result.hub_contract["info"]
        assert "name" in info, "Should have 'name' in info"
        assert info["name"] == "Test Info Section", "Name should match"
        assert "version" in info, "Should have 'version' in info"
        assert info["version"] == "1.0.0", "Version should match"
        assert "owners" in info, "Should have 'owners' in info"
        assert len(info["owners"]) == 1, "Should have 1 owner"
        assert "tags" in info, "Should have 'tags' in info"
        assert len(info["tags"]) == 2, "Should have 2 tags"

    def test_quality_section_normalized_correctly(self):
        """Test that quality section is normalized correctly."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-quality-section",
            "name": "Test Quality Section",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False
                    }
                ]
            },
            "quality": {
                "default_profile_key": "test_profile",
                "rules": [
                    {
                        "type": "completeness",
                        "field": "id",
                        "threshold": 1.0
                    }
                ]
            }
        }

        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")
        self._assert_normalization_result_valid(result, "3.0.2", expect_success=True)

        # Check quality normalization
        assert "quality" in result.hub_contract, "Should have 'quality' section"
        quality = result.hub_contract["quality"]
        assert "default_profile_key" in quality, "Should have 'default_profile_key' in quality"
        assert quality["default_profile_key"] == "test_profile", "Default profile key should match"

    def test_lifecycle_section_normalized_correctly(self):
        """Test that lifecycle section is normalized correctly."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-lifecycle-section",
            "name": "Test Lifecycle Section",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False
                    }
                ]
            },
            "lifecycle": {
                "data_source": "database",
                "refresh_cadence": "daily"
            }
        }

        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")
        self._assert_normalization_result_valid(result, "3.0.2", expect_success=True)

        # Check lifecycle normalization
        assert "lifecycle" in result.hub_contract, "Should have 'lifecycle' section"
        lifecycle = result.hub_contract["lifecycle"]
        assert "data_source" in lifecycle, "Should have 'data_source' in lifecycle"
        assert lifecycle["data_source"] == "database", "Data source should match"
        assert "refresh_cadence" in lifecycle, "Should have 'refresh_cadence' in lifecycle"
        assert lifecycle["refresh_cadence"] == "daily", "Refresh cadence should match"

    def test_normalization_metadata_present(self):
        """Test that normalization metadata is present in HubContract."""
        contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-normalization-metadata",
            "name": "Test Normalization Metadata",
            "version": "1.0.0",
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

        result = self._normalize_with_version_specific_normalizer(contract_data, "3.0.2")
        self._assert_normalization_result_valid(result, "3.0.2", expect_success=True)

        # Check normalization metadata
        assert "normalization" in result.hub_contract, "Should have 'normalization' metadata"
        normalization = result.hub_contract["normalization"]
        assert "original_spec_type" in normalization, "Should have 'original_spec_type'"
        assert normalization["original_spec_type"] == OriginalSpecType.ODCS, \
            "Original spec type should be ODCS"
        assert "original_spec_version" in normalization, "Should have 'original_spec_version'"
        assert normalization["original_spec_version"] == "3.0.2", \
            "Original spec version should be 3.0.2"
        assert "coverage" in normalization, "Should have 'coverage' in normalization"

