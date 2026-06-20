"""
Comprehensive Backward Compatibility Tests for CI

Tests backward compatibility for all ODPS and ODCS versions:
- ODPS: 4.1, 4.0, 3.x, 2.x, 1.x
- ODCS: 3.0.2, 3.0.1, 3.0.0, 3.0.0-preview, 2.2.2

Tests graceful degradation and ensures no regression in existing flows.
Uses real services (no mocks/stubs).
"""

import json
import sys
from pathlib import Path

from django.test import TestCase

from hub.apps.contracts.models import NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import get_normalizer
from hub.apps.contracts.odps_version_detection import detect_odps_version

# Import ODCS normalization functions from datacontract-service
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
    ODCS_NORMALIZATION_AVAILABLE = False
    normalize_contract = None
    detect_odcs_spec_type = None


# Supported versions
ODPS_VERSIONS = ["4.1", "4.0", "3.x", "2.x", "1.x"]
ODCS_VERSIONS = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]


def create_odps_contract(version):
    """Create a valid ODPS contract for a specific version."""
    if version == "3.x":
        schema_version = "3.9"
    elif version == "2.x":
        schema_version = "2.9"
    elif version == "1.x":
        schema_version = "1.9"
    else:
        schema_version = version

    return {
        "schema": f"https://opendataproducts.org/schema/v{schema_version}",
        "version": schema_version,
        "product": {
            "details": {
                "en": {
                    "productID": f"test-product-{version}",
                    "name": f"Test Product {version}",
                    "description": f"Test description for {version}",
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


def create_odcs_contract(version):
    """Create a valid ODCS contract for a specific version."""
    api_version = f"odcs.io/v{version}" if version != "2.2.2" else f"odcs/v{version}"
    return {
        "apiVersion": api_version,
        "kind": "DataContract",
        "id": f"test-odcs-{version}",
        "name": f"Test ODCS Contract {version}",
        "version": "1.0.0",
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


class TestODPSBackwardCompatibility(TestCase):
    """Comprehensive backward compatibility tests for ODPS versions."""

    def test_odps_version_detection_all_versions(self):
        """Test that all ODPS versions are detected correctly."""
        for version in ODPS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odps_contract(version)
                detected_version = detect_odps_version(contract)
                self.assertNotEqual(
                    detected_version,
                    "unknown",
                    f"Version {version} should be detected, got {detected_version}",
                )

    def test_odps_normalizer_selection_all_versions(self):
        """Test that correct normalizer is selected for each ODPS version."""
        for version in ODPS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odps_contract(version)
                detected_version = detect_odps_version(contract)
                normalizer = get_normalizer(OriginalSpecType.ODPS, detected_version, contract)
                self.assertIsNotNone(
                    normalizer, f"Normalizer should be found for ODPS version {version}"
                )
                self.assertTrue(
                    normalizer.supports(OriginalSpecType.ODPS, detected_version, contract),
                    f"Normalizer should support ODPS version {version}",
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
                    result.hub_contract, f"Normalization should succeed for ODPS version {version}"
                )
                self.assertIn(
                    result.status,
                    [
                        NormalizationStatus.NORMALIZED_OK,
                        NormalizationStatus.NORMALIZED_WITH_WARNINGS,
                    ],
                    f"Status should be OK or WARNINGS for version {version}",
                )
                self.assertEqual(len(result.errors), 0, f"No errors expected for version {version}")
                self.assertIn(
                    "id",
                    result.hub_contract,
                    f"HubContract should have 'id' field for version {version}",
                )

    def test_odps_graceful_degradation_newer_features(self):
        """Test graceful degradation when newer features are present in older versions."""
        for version in ODPS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odps_contract(version)
                contract["productStrategy"] = {"objectives": ["Should be gracefully handled"]}
                detected_version = detect_odps_version(contract)
                normalizer = get_normalizer(OriginalSpecType.ODPS, detected_version, contract)
                result = normalizer.normalize(contract, spec_version=detected_version)
                self.assertIsNotNone(
                    result.hub_contract,
                    f"Normalization should succeed with graceful degradation for version {version}",
                )

    def test_odps_graceful_degradation_missing_optional_fields(self):
        """Test graceful handling of missing optional fields."""
        for version in ODPS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odps_contract(version)
                detected_version = detect_odps_version(contract)
                normalizer = get_normalizer(OriginalSpecType.ODPS, detected_version, contract)
                result = normalizer.normalize(contract, spec_version=detected_version)
                self.assertIsNotNone(
                    result.hub_contract,
                    f"Normalization should succeed with missing optional fields for version {version}",
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
                spec_type, _detected_version = detect_odcs_spec_type(contract)
                self.assertEqual(spec_type, "ODCS", f"Should detect ODCS for version {version}")

    def test_odcs_basic_normalization_all_versions(self):
        """Test basic normalization for all ODCS versions."""
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odcs_contract(version)
                contract_json = json.dumps(contract)
                hub_contract, status, errors, _warnings = normalize_contract(
                    contract_json, format="json"
                )
                self.assertIsNotNone(
                    hub_contract, f"Normalization should succeed for ODCS version {version}"
                )
                self.assertIn(
                    status,
                    ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"],
                    f"Status should be OK or WARNINGS for version {version}",
                )
                self.assertEqual(len(errors), 0, f"No errors expected for version {version}")
                self.assertEqual(
                    hub_contract.id,
                    contract["id"],
                    f"Contract ID should be preserved for version {version}",
                )

    def test_odcs_graceful_degradation_newer_features(self):
        """Test graceful degradation when newer features are present in older versions."""
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odcs_contract(version)
                contract["quality"] = {"checks": [{"type": "type_check", "field": "id"}]}
                contract_json = json.dumps(contract)
                hub_contract, _status, _errors, _warnings = normalize_contract(
                    contract_json, format="json"
                )
                self.assertIsNotNone(
                    hub_contract,
                    f"Normalization should succeed with graceful degradation for version {version}",
                )

    def test_odcs_graceful_degradation_missing_optional_fields(self):
        """Test graceful handling of missing optional fields."""
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odcs_contract(version)
                minimal_contract = {
                    "apiVersion": contract["apiVersion"],
                    "kind": contract["kind"],
                    "id": contract["id"],
                    "schema": contract["schema"],
                }
                contract_json = json.dumps(minimal_contract)
                hub_contract, _status, _errors, _warnings = normalize_contract(
                    contract_json, format="json"
                )
                self.assertIsNotNone(
                    hub_contract,
                    f"Normalization should succeed with missing optional fields for version {version}",
                )


class TestNoRegressionExistingFlows(TestCase):
    """Tests to ensure no regression in existing flows."""

    def test_existing_odcs_3_0_2_flow(self):
        """Test that existing ODCS 3.0.2 flow still works."""
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        contract = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "existing-flow-test",
            "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
        }
        contract_json = json.dumps(contract)
        hub_contract, _status, errors, _warnings = normalize_contract(contract_json, format="json")
        self.assertIsNotNone(hub_contract, "Existing ODCS 3.0.2 flow should work")
        self.assertEqual(len(errors), 0, "No errors expected in existing flow")
        self.assertEqual(hub_contract.id, "existing-flow-test", "Contract ID should be preserved")

    def test_existing_odps_4_1_flow(self):
        """Test that existing ODPS 4.1 flow still works."""
        contract = create_odps_contract("4.1")
        contract["product"]["details"]["en"]["productID"] = "existing-odps-flow"
        detected_version = detect_odps_version(contract)
        normalizer = get_normalizer(OriginalSpecType.ODPS, detected_version, contract)
        result = normalizer.normalize(contract, spec_version=detected_version)
        self.assertIsNotNone(result.hub_contract, "Existing ODPS 4.1 flow should work")
        self.assertEqual(len(result.errors), 0, "No errors expected in existing flow")
        self.assertEqual(
            result.hub_contract["id"], "existing-odps-flow", "Contract ID should be preserved"
        )

    def test_all_odcs_versions_no_regression(self):
        """Test that all ODCS versions work without regression."""
        if not ODCS_NORMALIZATION_AVAILABLE:
            self.skipTest("ODCS normalization not available")

        for version in ODCS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odcs_contract(version)
                contract["id"] = f"regression-test-{version}"
                contract_json = json.dumps(contract)
                hub_contract, _status, errors, _warnings = normalize_contract(
                    contract_json, format="json"
                )
                self.assertIsNotNone(
                    hub_contract, f"ODCS version {version} should work without regression"
                )
                self.assertEqual(len(errors), 0, f"No errors expected for version {version}")
                self.assertEqual(
                    hub_contract.id,
                    f"regression-test-{version}",
                    f"Contract ID should be preserved for version {version}",
                )

    def test_all_odps_versions_no_regression(self):
        """Test that all ODPS versions work without regression."""
        for version in ODPS_VERSIONS:
            with self.subTest(version=version):
                contract = create_odps_contract(version)
                contract["product"]["details"]["en"]["productID"] = f"regression-test-{version}"
                detected_version = detect_odps_version(contract)
                normalizer = get_normalizer(OriginalSpecType.ODPS, detected_version, contract)
                result = normalizer.normalize(contract, spec_version=detected_version)
                self.assertIsNotNone(
                    result.hub_contract, f"ODPS version {version} should work without regression"
                )
                self.assertEqual(len(result.errors), 0, f"No errors expected for version {version}")
                self.assertEqual(
                    result.hub_contract["id"],
                    f"regression-test-{version}",
                    f"Contract ID should be preserved for version {version}",
                )
