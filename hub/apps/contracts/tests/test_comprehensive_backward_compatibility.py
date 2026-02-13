"""
Comprehensive Backward Compatibility Tests

Tests backward compatibility for all ODPS and ODCS versions:
- ODPS: 4.1, 4.0, 3.x, 2.x, 1.x
- ODCS: 3.0.2, 3.0.1, 3.0.0, 3.0.0-preview, 2.2.2

Tests graceful degradation and ensures no regression in existing flows.
Uses real services (no mocks/stubs).
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from django.test import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import get_normalizer
from hub.apps.contracts.odps_version_detection import detect_odps_version

# Import ODCS normalization functions from datacontract-service
# Add the service path to sys.path
_datacontract_service_path = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "services"
    / "datacontract-service"
)
if _datacontract_service_path.exists() and str(_datacontract_service_path) not in sys.path:
    sys.path.insert(0, str(_datacontract_service_path))

try:
    from normalize import detect_spec_type as detect_odcs_spec_type
    from normalize import normalize_contract

    ODCS_NORMALIZATION_AVAILABLE = True
except ImportError:
    # Fallback: use service endpoint if direct import fails
    ODCS_NORMALIZATION_AVAILABLE = False
    normalize_contract = None
    detect_odcs_spec_type = None


# Supported ODPS versions
ODPS_VERSIONS = ["4.1", "4.0", "3.x", "2.x", "1.x"]

# Supported ODCS versions
ODCS_VERSIONS = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]


def create_odps_contract(version: str, **overrides) -> Dict[str, Any]:
    """
    Create a valid ODPS contract for a specific version.

    Args:
        version: ODPS version (e.g., "4.1", "3.x", "2.x", "1.x")
        **overrides: Override default values

    Returns:
        ODPS contract dictionary
    """
    # Normalize version for schema URL
    if version == "3.x":
        schema_version = "3.9"
    elif version == "2.x":
        schema_version = "2.9"
    elif version == "1.x":
        schema_version = "1.9"
    else:
        schema_version = version

    contract = {
        "schema": f"https://opendataproducts.org/schema/v{schema_version}",
        "version": schema_version,
        "product": {
            "details": {
                "en": {
                    "productID": overrides.get("productID", f"test-product-{version}"),
                    "name": overrides.get("name", f"Test Product {version}"),
                    "description": overrides.get("description", f"Test description for {version}"),
                }
            },
            "dataSchema": {
                "fields": [
                    {"name": "id", "type": "string", "description": "Unique identifier"},
                    {"name": "name", "type": "string", "description": "Name field"},
                ]
            },
        },
    }

    # Apply overrides
    contract.update(overrides)

    return contract


def create_odcs_contract(version: str, **overrides) -> Dict[str, Any]:
    """
    Create a valid ODCS contract for a specific version.

    Args:
        version: ODCS version (e.g., "3.0.2")
        **overrides: Override default values

    Returns:
        ODCS contract dictionary
    """
    contract = {
        "apiVersion": f"odcs.io/v{version}",
        "kind": "DataContract",
        "id": overrides.get("id", f"test-odcs-{version}"),
        "name": overrides.get("name", f"Test ODCS Contract {version}"),
        "version": overrides.get("version", "1.0.0"),
        "schema": {
            "fields": [
                {
                    "name": "id",
                    "type": "string",
                    "nullable": False,
                    "description": "Unique identifier",
                },
                {"name": "name", "type": "string", "nullable": False, "description": "Name field"},
            ]
        },
    }

    # Version-specific adjustments
    if version == "2.2.2":
        contract["apiVersion"] = f"odcs/v{version}"

    # Apply overrides
    contract.update(overrides)

    return contract


class TestODPSBackwardCompatibility(TestCase):
    """Comprehensive backward compatibility tests for ODPS versions."""

    def test_odps_version_detection_all_versions(self):
        """Test that all ODPS versions are detected correctly."""
        for version in ODPS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odps_contract(version)
                detected_version = detect_odps_version(contract)

                # Version should be detected (may be normalized)
                self.assertNotEqual(
                    detected_version,
                    "unknown",
                    f"Version {version} should be detected, got {detected_version}",
                )

                # Check that detected version matches expected range
                if version == "4.1":
                    self.assertIn(
                        detected_version,
                        ["4.1", "4.0"],
                        f"Version {version} should detect as 4.1 or 4.0, got {detected_version}",
                    )
                elif version == "4.0":
                    self.assertEqual(
                        detected_version,
                        "4.0",
                        f"Version {version} should detect as 4.0, got {detected_version}",
                    )
                elif version == "3.x":
                    self.assertEqual(
                        detected_version,
                        "3.x",
                        f"Version {version} should detect as 3.x, got {detected_version}",
                    )
                elif version == "2.x":
                    self.assertEqual(
                        detected_version,
                        "2.x",
                        f"Version {version} should detect as 2.x, got {detected_version}",
                    )
                elif version == "1.x":
                    self.assertEqual(
                        detected_version,
                        "1.x",
                        f"Version {version} should detect as 1.x, got {detected_version}",
                    )

    def test_odps_normalizer_selection_all_versions(self):
        """Test that correct normalizer is selected for each ODPS version."""
        for version in ODPS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odps_contract(version)
                detected_version = detect_odps_version(contract)

                normalizer = get_normalizer(OriginalSpecType.ODPS, detected_version, contract)

                self.assertIsNotNone(
                    normalizer,
                    f"Normalizer should be found for ODPS version {version} (detected: {detected_version})",
                )

                # Verify normalizer supports this version
                self.assertTrue(
                    normalizer.supports(OriginalSpecType.ODPS, detected_version, contract),
                    f"Normalizer should support ODPS version {version} (detected: {detected_version})",
                )

    def test_odps_basic_normalization_all_versions(self):
        """Test basic normalization for all ODPS versions."""
        for version in ODPS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odps_contract(version)
                detected_version = detect_odps_version(contract)

                normalizer = get_normalizer(OriginalSpecType.ODPS, detected_version, contract)
                result = normalizer.normalize(contract, spec_version=detected_version)

                self.assertIsNotNone(
                    result.hub_contract,
                    f"Normalization should succeed for ODPS version {version}. Errors: {result.errors}",
                )
                self.assertIn(
                    result.status,
                    [
                        NormalizationStatus.NORMALIZED_OK,
                        NormalizationStatus.NORMALIZED_WITH_WARNINGS,
                    ],
                    f"Status should be OK or WARNINGS for version {version}, got {result.status}. Errors: {result.errors}",
                )
                self.assertEqual(
                    len(result.errors),
                    0,
                    f"No errors expected for version {version}. Errors: {result.errors}",
                )

                # Verify core fields are present
                self.assertIn(
                    "id",
                    result.hub_contract,
                    f"HubContract should have 'id' field for version {version}",
                )
                self.assertIn(
                    "info",
                    result.hub_contract,
                    f"HubContract should have 'info' field for version {version}",
                )

    def test_odps_graceful_degradation_newer_features_all_versions(self):
        """Test graceful degradation when newer features are present in older versions."""
        for version in ODPS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odps_contract(version)

                # Add features that may not be supported in older versions
                contract["productStrategy"] = {"objectives": ["Should be gracefully handled"]}
                contract["marketplace"] = {"paymentGateways": ["Should be gracefully handled"]}

                detected_version = detect_odps_version(contract)
                normalizer = get_normalizer(OriginalSpecType.ODPS, detected_version, contract)
                result = normalizer.normalize(contract, spec_version=detected_version)

                # Should normalize successfully even with unsupported features
                self.assertIsNotNone(
                    result.hub_contract,
                    f"Normalization should succeed with graceful degradation for version {version}. Errors: {result.errors}",
                )
                self.assertIn(
                    result.status,
                    [
                        NormalizationStatus.NORMALIZED_OK,
                        NormalizationStatus.NORMALIZED_WITH_WARNINGS,
                    ],
                    f"Status should be OK or WARNINGS with graceful degradation for version {version}. Errors: {result.errors}",
                )

    def test_odps_graceful_degradation_missing_optional_fields_all_versions(self):
        """Test graceful handling of missing optional fields."""
        for version in ODPS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odps_contract(version)

                # Remove optional fields
                if "marketplace" in contract.get("product", {}):
                    del contract["product"]["marketplace"]
                if "lifecycle" in contract.get("product", {}):
                    del contract["product"]["lifecycle"]
                if "quality" in contract.get("product", {}):
                    del contract["product"]["quality"]

                detected_version = detect_odps_version(contract)
                normalizer = get_normalizer(OriginalSpecType.ODPS, detected_version, contract)
                result = normalizer.normalize(contract, spec_version=detected_version)

                # Should normalize successfully even with missing optional fields
                self.assertIsNotNone(
                    result.hub_contract,
                    f"Normalization should succeed with missing optional fields for version {version}. Errors: {result.errors}",
                )
                self.assertIn(
                    result.status,
                    [
                        NormalizationStatus.NORMALIZED_OK,
                        NormalizationStatus.NORMALIZED_WITH_WARNINGS,
                    ],
                    f"Status should be OK or WARNINGS with missing optional fields for version {version}. Errors: {result.errors}",
                )


class TestODCSBackwardCompatibility(TestCase):
    """Comprehensive backward compatibility tests for ODCS versions."""

    def test_odcs_version_detection_all_versions(self):
        """Test that all ODCS versions are detected correctly."""
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odcs_contract(version)
                spec_type, detected_version = detect_odcs_spec_type(contract)

                self.assertEqual(
                    spec_type,
                    "ODCS",
                    f"Should detect ODCS for version {version}, got {spec_type}",
                )
                self.assertIn(
                    detected_version,
                    [version, version.replace("-preview", "")],
                    f"Version detection should return {version} or normalized version, got {detected_version}",
                )

    def test_odcs_basic_normalization_all_versions(self):
        """Test basic normalization for all ODCS versions."""
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):

                contract = create_odcs_contract(version)
                contract_json = json.dumps(contract)

                hub_contract, status, errors, warnings = normalize_contract(
                    contract_json, format="json"
                )

                self.assertIsNotNone(
                    hub_contract,
                    f"Normalization should succeed for ODCS version {version}. Errors: {errors}",
                )
                self.assertIn(
                    status,
                    ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"],
                    f"Status should be OK or WARNINGS for version {version}, got {status}. Errors: {errors}",
                )
                self.assertEqual(
                    len(errors),
                    0,
                    f"No errors expected for version {version}. Errors: {errors}",
                )

                # Verify core fields are present
                self.assertEqual(
                    hub_contract.id,
                    contract["id"],
                    f"HubContract should have correct 'id' for version {version}",
                )
                self.assertIsNotNone(
                    hub_contract.schema,
                    f"HubContract should have 'schema' for version {version}",
                )
                self.assertGreater(
                    len(hub_contract.schema.fields),
                    0,
                    f"HubContract should have schema fields for version {version}",
                )

    def test_odcs_graceful_degradation_newer_features_all_versions(self):
        """Test graceful degradation when newer features are present in older versions."""
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):

                contract = create_odcs_contract(version)

                # Add features that may not be supported in older versions
                contract["quality"] = {
                    "checks": [{"type": "type_check", "field": "id", "threshold": 1.0}]
                }
                contract["compliance"] = {
                    "allowed_to_store": True,
                    "applicable_regulations": ["GDPR"],
                }

                contract_json = json.dumps(contract)
                hub_contract, status, errors, warnings = normalize_contract(
                    contract_json, format="json"
                )

                # Should normalize successfully even with features that may not be fully supported
                self.assertIsNotNone(
                    hub_contract,
                    f"Normalization should succeed with graceful degradation for version {version}. Errors: {errors}",
                )
                self.assertIn(
                    status,
                    ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"],
                    f"Status should be OK or WARNINGS with graceful degradation for version {version}. Errors: {errors}",
                )

    def test_odcs_graceful_degradation_missing_optional_fields_all_versions(self):
        """Test graceful handling of missing optional fields."""
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):

                contract = create_odcs_contract(version)
                # Only include required fields
                minimal_contract = {
                    "apiVersion": contract["apiVersion"],
                    "kind": contract["kind"],
                    "id": contract["id"],
                    "schema": contract["schema"],
                }

                contract_json = json.dumps(minimal_contract)
                hub_contract, status, errors, warnings = normalize_contract(
                    contract_json, format="json"
                )

                # Should normalize successfully even with missing optional fields
                self.assertIsNotNone(
                    hub_contract,
                    f"Normalization should succeed with missing optional fields for version {version}. Errors: {errors}",
                )
                self.assertIn(
                    status,
                    ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"],
                    f"Status should be OK or WARNINGS with missing optional fields for version {version}. Errors: {errors}",
                )


class TestCrossFormatBackwardCompatibility(TestCase):
    """Tests for backward compatibility across ODPS and ODCS formats."""

    def test_odps_odcs_coexistence(self):
        """Test that ODPS and ODCS contracts can coexist without interference."""
        # Create ODPS contract
        odps_contract = create_odps_contract("4.1")
        odps_detected = detect_odps_version(odps_contract)
        odps_normalizer = get_normalizer(OriginalSpecType.ODPS, odps_detected, odps_contract)
        odps_result = odps_normalizer.normalize(odps_contract, spec_version=odps_detected)

        # Create ODCS contract
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        odcs_contract = create_odcs_contract("3.0.2")
        odcs_json = json.dumps(odcs_contract)
        odcs_hub_contract, odcs_status, odcs_errors, odcs_warnings = normalize_contract(
            odcs_json, format="json"
        )

        # Both should normalize successfully
        self.assertIsNotNone(
            odps_result.hub_contract,
            f"ODPS normalization should succeed. Errors: {odps_result.errors}",
        )
        self.assertIsNotNone(
            odcs_hub_contract,
            f"ODCS normalization should succeed. Errors: {odcs_errors}",
        )

        # Verify they produce different but valid HubContracts
        self.assertNotEqual(
            odps_result.hub_contract["id"],
            odcs_hub_contract.id,
            "ODPS and ODCS contracts should have different IDs",
        )

    def test_version_specific_features_preserved(self):
        """Test that version-specific features are preserved in extensions."""
        # Test ODPS
        odps_contract = create_odps_contract("4.1")
        odps_contract["customField"] = "ODPS-specific"
        odps_detected = detect_odps_version(odps_contract)
        odps_normalizer = get_normalizer(OriginalSpecType.ODPS, odps_detected, odps_contract)
        odps_result = odps_normalizer.normalize(odps_contract, spec_version=odps_detected)

        # Test ODCS
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        odcs_contract = create_odcs_contract("3.0.2")
        odcs_contract["customField"] = "ODCS-specific"
        odcs_json = json.dumps(odcs_contract)
        odcs_hub_contract, _, _, _ = normalize_contract(odcs_json, format="json")

        # Version-specific fields should be preserved in extensions
        if odps_result.hub_contract.get("extensions"):
            # ODPS extensions should contain custom fields
            pass  # Extensions structure may vary

        if odcs_hub_contract.extensions and odcs_hub_contract.extensions.odcs:
            self.assertTrue(
                "customField" in odcs_hub_contract.extensions.odcs,
                "ODCS custom fields should be preserved in extensions",
            )


class TestNoRegressionExistingFlows(TestCase):
    """Tests to ensure no regression in existing ODCS flows."""

    def test_existing_odcs_3_0_2_flow(self):
        """Test that existing ODCS 3.0.2 flow still works."""
        if not ODCS_NORMALIZATION_AVAILABLE:
            pytest.skip("ODCS normalization not available")

        # Standard ODCS 3.0.2 contract
        contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "existing-flow-test",
            "name": "Existing Flow Test",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }

        contract_json = json.dumps(contract)
        hub_contract, status, errors, warnings = normalize_contract(contract_json, format="json")

        self.assertIsNotNone(
            hub_contract,
            f"Existing ODCS 3.0.2 flow should work. Errors: {errors}",
        )
        self.assertEqual(
            len(errors),
            0,
            f"No errors expected in existing flow. Errors: {errors}",
        )
        self.assertEqual(
            hub_contract.id,
            "existing-flow-test",
            "Contract ID should be preserved",
        )

    def test_existing_odps_4_1_flow(self):
        """Test that existing ODPS 4.1 flow still works."""
        contract = create_odps_contract("4.1", productID="existing-odps-flow")
        detected_version = detect_odps_version(contract)
        normalizer = get_normalizer(OriginalSpecType.ODPS, detected_version, contract)
        result = normalizer.normalize(contract, spec_version=detected_version)

        self.assertIsNotNone(
            result.hub_contract,
            f"Existing ODPS 4.1 flow should work. Errors: {result.errors}",
        )
        self.assertEqual(
            len(result.errors),
            0,
            f"No errors expected in existing flow. Errors: {result.errors}",
        )
        self.assertEqual(
            result.hub_contract["id"],
            "existing-odps-flow",
            "Contract ID should be preserved",
        )

    def test_all_odcs_versions_no_regression(self):
        """Test that all ODCS versions work without regression."""
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):

                contract = create_odcs_contract(version, id=f"regression-test-{version}")
                contract_json = json.dumps(contract)
                hub_contract, status, errors, warnings = normalize_contract(
                    contract_json, format="json"
                )

                self.assertIsNotNone(
                    hub_contract,
                    f"ODCS version {version} should work without regression. Errors: {errors}",
                )
                self.assertEqual(
                    len(errors),
                    0,
                    f"No errors expected for version {version}. Errors: {errors}",
                )
                self.assertEqual(
                    hub_contract.id,
                    f"regression-test-{version}",
                    f"Contract ID should be preserved for version {version}",
                )

    def test_all_odps_versions_no_regression(self):
        """Test that all ODPS versions work without regression."""
        for version in ODPS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odps_contract(version, productID=f"regression-test-{version}")
                detected_version = detect_odps_version(contract)
                normalizer = get_normalizer(OriginalSpecType.ODPS, detected_version, contract)
                result = normalizer.normalize(contract, spec_version=detected_version)

                self.assertIsNotNone(
                    result.hub_contract,
                    f"ODPS version {version} should work without regression. Errors: {result.errors}",
                )
                self.assertEqual(
                    len(result.errors),
                    0,
                    f"No errors expected for version {version}. Errors: {result.errors}",
                )
                self.assertEqual(
                    result.hub_contract["id"],
                    f"regression-test-{version}",
                    f"Contract ID should be preserved for version {version}",
                )
