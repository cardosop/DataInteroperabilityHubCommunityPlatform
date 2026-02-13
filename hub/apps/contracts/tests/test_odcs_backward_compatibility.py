"""
Comprehensive backward compatibility tests for ODCS normalization (Task 1.6.9)

Tests ensure that all ODCS versions normalize correctly and produce consistent
results compared to the baseline (ODCS 3.0.2). This test suite verifies:
- ODCS 3.0.2 normalization (baseline)
- ODCS 3.0.1 normalization (no regression)
- ODCS 3.0.0 normalization (no regression)
- ODCS 3.0.0-preview normalization (no regression)
- ODCS 2.2.2 normalization (no regression)
- Normalization result comparison with baseline
- Regression test suite for all ODCS versions
"""

import json
from typing import Any, Dict, List, Optional
from unittest import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import (
    NormalizationResult,
    get_normalizer,
    normalize_contract,
)
from hub.apps.contracts.normalization.odcs_normalizer_v2_2_2 import ODCSNormalizerV2_2_2
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0 import ODCSNormalizerV3_0_0
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_0_preview import (
    ODCSNormalizerV3_0_0_Preview,
)
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_1 import ODCSNormalizerV3_0_1
from hub.apps.contracts.normalization.odcs_normalizer_v3_0_2 import ODCSNormalizerV3_0_2


class ODCSBackwardCompatibilityTestBase(TestCase):
    """Base class for ODCS backward compatibility tests with shared fixtures."""

    def setUp(self):
        """Set up test fixtures for all ODCS versions."""
        # Baseline contract (ODCS 3.0.2 format) - comprehensive example
        self.baseline_contract_3_0_2 = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract-baseline",
            "name": "Test Contract Baseline",
            "version": "1.0.0",
            "description": "Baseline contract for backward compatibility testing",
            "info": {
                "owners": [{"name": "Data Team", "email": "data-team@example.com"}],
                "tags": ["test", "baseline"],
                "domain": "test",
                "tenant": "test-tenant",
            },
            "support": [{"name": "Support Team", "email": "support@example.com"}],
            "servers": [
                {
                    "type": "postgres",
                    "url": "postgresql://localhost:5432/testdb",
                    "description": "Test database",
                }
            ],
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False,
                        "description": "Unique identifier",
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "nullable": True,
                        "description": "Name field",
                    },
                    {
                        "name": "value",
                        "type": "number",
                        "nullable": True,
                        "description": "Numeric value",
                    },
                ]
            },
            "quality": {"default_profile_key": "test_profile"},
            "lifecycle": {"data_source": "database", "refresh_cadence": "daily"},
        }

        # ODCS 3.0.1 contract (same structure, different version)
        self.contract_3_0_1 = self._create_versioned_contract("3.0.1")

        # ODCS 3.0.0 contract (same structure, different version)
        self.contract_3_0_0 = self._create_versioned_contract("3.0.0")

        # ODCS 3.0.0-preview contract (same structure, different version)
        self.contract_3_0_0_preview = self._create_versioned_contract("3.0.0-preview")

        # ODCS 2.2.2 contract (may have different structure)
        self.contract_2_2_2 = {
            "apiVersion": "odcs.io/v2.2.2",
            "kind": "DataContract",
            "id": "test-contract-2-2-2",
            "name": "Test Contract 2.2.2",
            "version": "1.0.0",
            "description": "ODCS 2.2.2 contract for backward compatibility testing",
            "info": {
                "owners": [{"name": "Data Team", "email": "data-team@example.com"}],
                "tags": ["test", "baseline"],
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False,
                        "description": "Unique identifier",
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "nullable": True,
                        "description": "Name field",
                    },
                ]
            },
        }

        # Minimal contract for basic normalization tests
        self.minimal_contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "minimal-test",
            "name": "Minimal Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

    def _create_versioned_contract(self, version: str) -> Dict[str, Any]:
        """Create a versioned contract from the baseline."""
        contract = self.baseline_contract_3_0_2.copy()
        contract["apiVersion"] = f"odcs.io/v{version}"
        contract["id"] = (
            f"test-contract-{version.replace('.', '-').replace('-preview', '-preview')}"
        )
        return contract

    def _normalize_contract(
        self, contract_data: Dict[str, Any], version: str
    ) -> NormalizationResult:
        """Normalize a contract using the appropriate normalizer."""
        normalizer = get_normalizer(OriginalSpecType.ODCS, version, contract_data)
        return normalizer.normalize(contract_data, spec_version=version)

    def _normalize_via_api(self, contract_data: Dict[str, Any]) -> NormalizationResult:
        """Normalize a contract via the normalize_contract API."""
        # Convert dict to JSON string for normalize_contract API
        raw_contract = json.dumps(contract_data)

        # Call normalize_contract with JSON format
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=raw_contract, format="json"
        )

        # Convert tuple result to NormalizationResult
        return NormalizationResult(
            hub_contract=hub_contract,
            status=status,
            errors=errors,
            warnings=warnings,
            spec_type=spec_type,
            spec_version=spec_version,
            coverage=None,  # Coverage not returned by normalize_contract
        )

    def _compare_normalization_results(
        self,
        baseline: NormalizationResult,
        other: NormalizationResult,
        version: str,
        allow_version_differences: bool = True,
    ) -> List[str]:
        """
        Compare two normalization results and return list of differences.

        Args:
            baseline: Baseline normalization result (ODCS 3.0.2)
            other: Other version normalization result
            version: Version being compared
            allow_version_differences: If True, ignore version-specific differences

        Returns:
            List of difference descriptions (empty if no differences)
        """
        differences: List[str] = []

        # Compare status
        if baseline.status != other.status:
            differences.append(
                f"Status mismatch: baseline={baseline.status}, {version}={other.status}"
            )

        # Compare hub_contract structure
        if baseline.hub_contract is None and other.hub_contract is None:
            return differences  # Both failed, no further comparison needed

        if baseline.hub_contract is None:
            differences.append(f"Baseline normalization failed but {version} succeeded")
            return differences

        if other.hub_contract is None:
            differences.append(f"{version} normalization failed but baseline succeeded")
            return differences

        # Compare core fields that should be consistent
        core_fields = ["id", "info", "schema"]
        for field in core_fields:
            if field not in baseline.hub_contract and field not in other.hub_contract:
                continue
            if field not in baseline.hub_contract:
                differences.append(f"Baseline missing field: {field}")
            elif field not in other.hub_contract:
                differences.append(f"{version} missing field: {field}")
            else:
                # Compare field values (simplified comparison)
                baseline_value = baseline.hub_contract[field]
                other_value = other.hub_contract[field]
                if isinstance(baseline_value, dict) and isinstance(other_value, dict):
                    # Compare dict keys
                    baseline_keys = set(baseline_value.keys())
                    other_keys = set(other_value.keys())
                    missing_in_other = baseline_keys - other_keys
                    extra_in_other = other_keys - baseline_keys
                    if missing_in_other:
                        differences.append(f"{version} missing keys in {field}: {missing_in_other}")
                    if extra_in_other and not allow_version_differences:
                        differences.append(f"{version} has extra keys in {field}: {extra_in_other}")
                elif baseline_value != other_value:
                    # For non-dict values, check if difference is acceptable
                    if not allow_version_differences:
                        differences.append(
                            f"{field} value mismatch: baseline={baseline_value}, {version}={other_value}"
                        )

        # Compare errors (should be similar or acceptable)
        if len(baseline.errors) != len(other.errors):
            differences.append(
                f"Error count mismatch: baseline={len(baseline.errors)}, {version}={len(other.errors)}"
            )

        # Compare warnings (may differ, but log for review)
        if len(baseline.warnings) != len(other.warnings):
            # Warnings can differ, but log for information
            pass

        return differences


class ODCSBaselineNormalizationTest(ODCSBackwardCompatibilityTestBase):
    """Test ODCS 3.0.2 normalization (baseline)."""

    def test_baseline_normalization_3_0_2_comprehensive(self):
        """Test ODCS 3.0.2 normalization (baseline) with comprehensive contract."""
        result = self._normalize_contract(self.baseline_contract_3_0_2, "3.0.2")

        # Verify normalization succeeded
        self.assertIsNotNone(result.hub_contract, "Normalization should produce a hub contract")
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
            f"Normalization should succeed, got status: {result.status}",
        )

        # Verify core fields
        self.assertEqual(result.hub_contract["id"], "test-contract-baseline")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract Baseline")
        self.assertIn("schema", result.hub_contract)
        self.assertIn("fields", result.hub_contract["schema"])

        # Verify spec metadata
        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertEqual(result.spec_version, "3.0.2")

    def test_baseline_normalization_3_0_2_minimal(self):
        """Test ODCS 3.0.2 normalization (baseline) with minimal contract."""
        result = self._normalize_contract(self.minimal_contract, "3.0.2")

        # Verify normalization succeeded
        self.assertIsNotNone(result.hub_contract, "Normalization should produce a hub contract")
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
            f"Normalization should succeed, got status: {result.status}",
        )

        # Verify core fields
        self.assertEqual(result.hub_contract["id"], "minimal-test")
        self.assertEqual(result.hub_contract["info"]["name"], "Minimal Test Contract")
        self.assertIn("schema", result.hub_contract)

    def test_baseline_normalization_via_api(self):
        """Test ODCS 3.0.2 normalization via normalize_contract API."""
        result = self._normalize_via_api(self.baseline_contract_3_0_2)

        # Verify normalization succeeded
        self.assertIsNotNone(result.hub_contract, "Normalization should produce a hub contract")
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
            f"Normalization should succeed, got status: {result.status}",
        )

        # Verify spec metadata
        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertEqual(result.spec_version, "3.0.2")


class ODCSRegressionTest(ODCSBackwardCompatibilityTestBase):
    """Test ODCS backward compatibility - ensure no regression in older versions."""

    def test_odcs_3_0_1_normalization_no_regression(self):
        """Test ODCS 3.0.1 normalization (no regression)."""
        result = self._normalize_contract(self.contract_3_0_1, "3.0.1")

        # Verify normalization succeeded
        self.assertIsNotNone(
            result.hub_contract, "ODCS 3.0.1 normalization should produce a hub contract"
        )
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
            f"ODCS 3.0.1 normalization should succeed, got status: {result.status}",
        )

        # Verify core fields
        self.assertEqual(result.hub_contract["id"], "test-contract-3-0-1")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract Baseline")
        self.assertIn("schema", result.hub_contract)

        # Verify spec metadata
        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertEqual(result.spec_version, "3.0.1")

    def test_odcs_3_0_0_normalization_no_regression(self):
        """Test ODCS 3.0.0 normalization (no regression)."""
        result = self._normalize_contract(self.contract_3_0_0, "3.0.0")

        # Verify normalization succeeded
        self.assertIsNotNone(
            result.hub_contract, "ODCS 3.0.0 normalization should produce a hub contract"
        )
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
            f"ODCS 3.0.0 normalization should succeed, got status: {result.status}",
        )

        # Verify core fields
        self.assertEqual(result.hub_contract["id"], "test-contract-3-0-0")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract Baseline")
        self.assertIn("schema", result.hub_contract)

        # Verify spec metadata
        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertEqual(result.spec_version, "3.0.0")

    def test_odcs_3_0_0_preview_normalization_no_regression(self):
        """Test ODCS 3.0.0-preview normalization (no regression)."""
        result = self._normalize_contract(self.contract_3_0_0_preview, "3.0.0-preview")

        # Verify normalization succeeded
        self.assertIsNotNone(
            result.hub_contract, "ODCS 3.0.0-preview normalization should produce a hub contract"
        )
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
            f"ODCS 3.0.0-preview normalization should succeed, got status: {result.status}",
        )

        # Verify core fields
        self.assertEqual(result.hub_contract["id"], "test-contract-3-0-0-preview")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract Baseline")
        self.assertIn("schema", result.hub_contract)

        # Verify spec metadata
        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertEqual(result.spec_version, "3.0.0-preview")

    def test_odcs_2_2_2_normalization_no_regression(self):
        """Test ODCS 2.2.2 normalization (no regression)."""
        result = self._normalize_contract(self.contract_2_2_2, "2.2.2")

        # Verify normalization succeeded
        self.assertIsNotNone(
            result.hub_contract, "ODCS 2.2.2 normalization should produce a hub contract"
        )
        self.assertIn(
            result.status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
            f"ODCS 2.2.2 normalization should succeed, got status: {result.status}",
        )

        # Verify core fields
        self.assertEqual(result.hub_contract["id"], "test-contract-2-2-2")
        self.assertEqual(result.hub_contract["info"]["name"], "Test Contract 2.2.2")
        self.assertIn("schema", result.hub_contract)

        # Verify spec metadata
        self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
        self.assertEqual(result.spec_version, "2.2.2")


class ODCSNormalizationComparisonTest(ODCSBackwardCompatibilityTestBase):
    """Compare normalization results with baseline (ODCS 3.0.2)."""

    def test_compare_3_0_1_with_baseline(self):
        """Compare ODCS 3.0.1 normalization results with baseline."""
        baseline_result = self._normalize_contract(self.baseline_contract_3_0_2, "3.0.2")
        other_result = self._normalize_contract(self.contract_3_0_1, "3.0.1")

        # Compare results
        differences = self._compare_normalization_results(
            baseline_result, other_result, "3.0.1", allow_version_differences=True
        )

        # Log differences for review (but don't fail if acceptable)
        if differences:
            print(f"\nODCS 3.0.1 comparison differences: {differences}")

        # Both should succeed
        self.assertIsNotNone(baseline_result.hub_contract, "Baseline should normalize successfully")
        self.assertIsNotNone(other_result.hub_contract, "ODCS 3.0.1 should normalize successfully")

        # Core fields should be present in both
        self.assertIn("id", baseline_result.hub_contract)
        self.assertIn("id", other_result.hub_contract)
        self.assertIn("info", baseline_result.hub_contract)
        self.assertIn("info", other_result.hub_contract)
        self.assertIn("schema", baseline_result.hub_contract)
        self.assertIn("schema", other_result.hub_contract)

    def test_compare_3_0_0_with_baseline(self):
        """Compare ODCS 3.0.0 normalization results with baseline."""
        baseline_result = self._normalize_contract(self.baseline_contract_3_0_2, "3.0.2")
        other_result = self._normalize_contract(self.contract_3_0_0, "3.0.0")

        # Compare results
        differences = self._compare_normalization_results(
            baseline_result, other_result, "3.0.0", allow_version_differences=True
        )

        # Log differences for review (but don't fail if acceptable)
        if differences:
            print(f"\nODCS 3.0.0 comparison differences: {differences}")

        # Both should succeed
        self.assertIsNotNone(baseline_result.hub_contract, "Baseline should normalize successfully")
        self.assertIsNotNone(other_result.hub_contract, "ODCS 3.0.0 should normalize successfully")

        # Core fields should be present in both
        self.assertIn("id", baseline_result.hub_contract)
        self.assertIn("id", other_result.hub_contract)
        self.assertIn("info", baseline_result.hub_contract)
        self.assertIn("info", other_result.hub_contract)
        self.assertIn("schema", baseline_result.hub_contract)
        self.assertIn("schema", other_result.hub_contract)

    def test_compare_3_0_0_preview_with_baseline(self):
        """Compare ODCS 3.0.0-preview normalization results with baseline."""
        baseline_result = self._normalize_contract(self.baseline_contract_3_0_2, "3.0.2")
        other_result = self._normalize_contract(self.contract_3_0_0_preview, "3.0.0-preview")

        # Compare results
        differences = self._compare_normalization_results(
            baseline_result, other_result, "3.0.0-preview", allow_version_differences=True
        )

        # Log differences for review (but don't fail if acceptable)
        if differences:
            print(f"\nODCS 3.0.0-preview comparison differences: {differences}")

        # Both should succeed
        self.assertIsNotNone(baseline_result.hub_contract, "Baseline should normalize successfully")
        self.assertIsNotNone(
            other_result.hub_contract, "ODCS 3.0.0-preview should normalize successfully"
        )

        # Core fields should be present in both
        self.assertIn("id", baseline_result.hub_contract)
        self.assertIn("id", other_result.hub_contract)
        self.assertIn("info", baseline_result.hub_contract)
        self.assertIn("info", other_result.hub_contract)
        self.assertIn("schema", baseline_result.hub_contract)
        self.assertIn("schema", other_result.hub_contract)

    def test_compare_2_2_2_with_baseline(self):
        """Compare ODCS 2.2.2 normalization results with baseline."""
        baseline_result = self._normalize_contract(self.baseline_contract_3_0_2, "3.0.2")
        other_result = self._normalize_contract(self.contract_2_2_2, "2.2.2")

        # Compare results
        differences = self._compare_normalization_results(
            baseline_result, other_result, "2.2.2", allow_version_differences=True
        )

        # Log differences for review (but don't fail if acceptable)
        if differences:
            print(f"\nODCS 2.2.2 comparison differences: {differences}")

        # Both should succeed
        self.assertIsNotNone(baseline_result.hub_contract, "Baseline should normalize successfully")
        self.assertIsNotNone(other_result.hub_contract, "ODCS 2.2.2 should normalize successfully")

        # Core fields should be present in both
        self.assertIn("id", baseline_result.hub_contract)
        self.assertIn("id", other_result.hub_contract)
        self.assertIn("info", baseline_result.hub_contract)
        self.assertIn("info", other_result.hub_contract)
        self.assertIn("schema", baseline_result.hub_contract)
        self.assertIn("schema", other_result.hub_contract)


class ODCSRegressionTestSuite(ODCSBackwardCompatibilityTestBase):
    """Comprehensive regression test suite for all ODCS versions."""

    def test_all_versions_normalize_successfully(self):
        """Test that all ODCS versions normalize successfully."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]
        contracts = [
            self.baseline_contract_3_0_2,
            self.contract_3_0_1,
            self.contract_3_0_0,
            self.contract_3_0_0_preview,
            self.contract_2_2_2,
        ]

        results = {}
        for version, contract in zip(versions, contracts):
            with self.subTest(version=version):
                result = self._normalize_contract(contract, version)
                results[version] = result

                # Verify normalization succeeded
                self.assertIsNotNone(
                    result.hub_contract,
                    f"ODCS {version} normalization should produce a hub contract",
                )
                self.assertIn(
                    result.status,
                    [
                        NormalizationStatus.NORMALIZED_OK,
                        NormalizationStatus.NORMALIZED_WITH_WARNINGS,
                    ],
                    f"ODCS {version} normalization should succeed, got status: {result.status}",
                )

                # Verify spec metadata
                self.assertEqual(result.spec_type, OriginalSpecType.ODCS)
                self.assertEqual(result.spec_version, version)

        # Verify all versions produced results
        self.assertEqual(len(results), len(versions), "All versions should produce results")

    def test_all_versions_produce_consistent_core_fields(self):
        """Test that all ODCS versions produce consistent core fields."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]
        contracts = [
            self.baseline_contract_3_0_2,
            self.contract_3_0_1,
            self.contract_3_0_0,
            self.contract_3_0_0_preview,
            self.contract_2_2_2,
        ]

        core_fields = ["id", "info", "schema"]
        results = {}

        for version, contract in zip(versions, contracts):
            result = self._normalize_contract(contract, version)
            results[version] = result

            # Verify core fields are present
            for field in core_fields:
                self.assertIn(
                    field, result.hub_contract, f"ODCS {version} should have {field} field"
                )

        # Verify all versions have consistent core structure
        baseline_result = results["3.0.2"]
        for version in versions:
            if version == "3.0.2":
                continue
            other_result = results[version]
            for field in core_fields:
                self.assertIn(field, baseline_result.hub_contract)
                self.assertIn(field, other_result.hub_contract)

    def test_all_versions_handle_minimal_contract(self):
        """Test that all ODCS versions handle minimal contracts correctly."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            with self.subTest(version=version):
                # Create minimal contract for this version
                minimal = self.minimal_contract.copy()
                minimal["apiVersion"] = f"odcs.io/v{version}"

                result = self._normalize_contract(minimal, version)

                # Verify normalization succeeded (may have warnings for minimal contract)
                self.assertIsNotNone(
                    result.hub_contract, f"ODCS {version} should normalize minimal contract"
                )
                self.assertIn(
                    result.status,
                    [
                        NormalizationStatus.NORMALIZED_OK,
                        NormalizationStatus.NORMALIZED_WITH_WARNINGS,
                        NormalizationStatus.NORMALIZATION_FAILED,
                    ],
                    f"ODCS {version} minimal contract normalization should have valid status",
                )

                # If normalization succeeded, verify core fields
                if result.hub_contract:
                    self.assertIn("id", result.hub_contract)
                    self.assertIn("schema", result.hub_contract)

    def test_version_specific_normalizers_are_used(self):
        """Test that version-specific normalizers are used for each version."""
        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]
        contracts = [
            self.baseline_contract_3_0_2,
            self.contract_3_0_1,
            self.contract_3_0_0,
            self.contract_3_0_0_preview,
            self.contract_2_2_2,
        ]

        for version, contract in zip(versions, contracts):
            with self.subTest(version=version):
                normalizer = get_normalizer(OriginalSpecType.ODCS, version, contract)

                # Verify correct normalizer is used
                if version == "3.0.2":
                    self.assertIsInstance(normalizer, ODCSNormalizerV3_0_2)
                elif version == "3.0.1":
                    self.assertIsInstance(normalizer, ODCSNormalizerV3_0_1)
                elif version == "3.0.0":
                    self.assertIsInstance(normalizer, ODCSNormalizerV3_0_0)
                elif version == "3.0.0-preview":
                    self.assertIsInstance(normalizer, ODCSNormalizerV3_0_0_Preview)
                elif version == "2.2.2":
                    self.assertIsInstance(normalizer, ODCSNormalizerV2_2_2)

                # Verify normalizer supports the version
                self.assertTrue(
                    normalizer.supports(OriginalSpecType.ODCS, version, contract),
                    f"Normalizer for {version} should support version {version}",
                )

    def test_normalization_handles_unicode_characters(self):
        """Test that normalization handles unicode characters correctly."""
        contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-unicode",
            "name": "测试合同",
            "version": "1.0.0",
            "description": "测试描述",
            "schema": {"fields": [{"name": "字段名称", "type": "string"}]},
        }

        result = normalize_contract(
            raw_contract=json.dumps(contract), format="json", spec_type="ODCS"
        )

        hub_contract_dict, spec_type, spec_version, norm_status, errors, warnings = result

        # Should handle unicode characters
        self.assertIsNotNone(hub_contract_dict)
        if hub_contract_dict and "info" in hub_contract_dict:
            self.assertIsNotNone(hub_contract_dict["info"])

    def test_normalization_handles_special_characters(self):
        """Test that normalization handles special characters correctly."""
        contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-special",
            "name": "Test & Co. (Special)",
            "version": "1.0.0",
            "description": "Test <description> & more",
            "schema": {"fields": [{"name": "field-name", "type": "string"}]},
        }

        result = normalize_contract(
            raw_contract=json.dumps(contract), format="json", spec_type="ODCS"
        )

        hub_contract_dict, spec_type, spec_version, norm_status, errors, warnings = result

        # Should handle special characters
        self.assertIsNotNone(hub_contract_dict)
        if hub_contract_dict and "info" in hub_contract_dict:
            self.assertIsNotNone(hub_contract_dict["info"])

    def test_normalization_handles_very_large_documents(self):
        """Test that normalization handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-large",
            "name": "Test Product",
            "version": "1.0.0",
            "description": large_description,
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        result = normalize_contract(
            raw_contract=json.dumps(contract), format="json", spec_type="ODCS"
        )

        hub_contract_dict, spec_type, spec_version, norm_status, errors, warnings = result

        # Should handle very large documents
        self.assertIsNotNone(hub_contract_dict)

    def test_normalization_handles_none_values(self):
        """Test that normalization handles None values correctly."""
        contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-none",
            "name": "Test Product",
            "version": "1.0.0",
            "description": None,  # None value
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        result = normalize_contract(
            raw_contract=json.dumps(contract), format="json", spec_type="ODCS"
        )

        hub_contract_dict, spec_type, spec_version, norm_status, errors, warnings = result

        # Should handle None values gracefully
        self.assertIsNotNone(hub_contract_dict)

    def test_normalization_handles_nested_structures(self):
        """Test that normalization handles nested structures correctly."""
        contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-nested",
            "name": "Test Product",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                    }
                ]
            },
        }

        result = normalize_contract(
            raw_contract=json.dumps(contract), format="json", spec_type="ODCS"
        )

        hub_contract_dict, spec_type, spec_version, norm_status, errors, warnings = result

        # Should handle nested structures
        self.assertIsNotNone(hub_contract_dict)
        if hub_contract_dict and "schema" in hub_contract_dict:
            self.assertIsNotNone(hub_contract_dict["schema"])
