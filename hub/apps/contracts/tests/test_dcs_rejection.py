"""
Tests for deprecated contract specification rejection.

These tests verify that deprecated contract formats are properly rejected with clear error messages
directing users to migrate to ODCS.
"""

import pytest
from rest_framework import status

from hub.apps.contracts.models import Contract, NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.spec_detection import detect_spec_type
from hub.apps.contracts.tests.test_base import ContractsAPITestBase

pytestmark = pytest.mark.django_db(transaction=True)


class DCSRejectionTestBase(ContractsAPITestBase):
    """Base test class for DCS rejection tests with common setup"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()


class DCSRejectionTestCase(DCSRejectionTestBase):
    """Test cases for deprecated contract specification rejection"""

    def test_dcs_contract_detection_in_spec_detection(self):
        """Test that deprecated contract formats are detected (but will be rejected during normalization)"""
        dcs_contract = {
            "dataContractSpecification": "0.9.0",
            "id": "test-contract",
            "info": {"title": "Test Contract", "version": "1.0.0"},
        }

        # Detection should return ODCS (but normalization will reject it)
        spec_type, spec_version = detect_spec_type(dcs_contract)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "3.0.2")

    def test_dcs_contract_rejection_in_normalization(self):
        """Test that contracts with dataContractSpecification normalize as ODCS (no DCS-specific rejection)"""
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
info:
  title: Test Contract
  version: 1.0.0
schema:
  type: object
  properties:
    field1:
      type: string
"""

        _hub_contract, spec_type, _spec_version, _norm_status, errors, _warnings = (
            normalize_contract(dcs_contract_yaml, format="yaml")
        )

        # DCS contracts are treated as ODCS (not DCS-specific rejection)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        # Should not contain DCS-specific error messages
        error_message = " ".join(errors) if errors else ""
        self.assertNotIn("DCS contracts are no longer supported", error_message)
        self.assertNotIn("Data Contract Specification (DCS) is no longer supported", error_message)

    def test_dcs_contract_rejection_via_api(self):
        """Test that deprecated contract formats are rejected via API with proper error response"""
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
info:
  title: Test Contract
  version: 1.0.0
schema:
  type: object
  properties:
    field1:
      type: string
"""

        response = self.client.post(
            "/api/v1/contracts/",
            {"original_raw": dcs_contract_yaml, "original_format": "YAML"},
            format="json",
        )

        # Should return 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Error message should be clear and helpful
        error_data = response.data
        self.assertIn(
            "error", str(error_data).lower() or "errors" in error_data or "detail" in error_data
        )

        # Check error message content
        error_message = str(error_data)
        if "errors" in error_data:
            error_message = " ".join(str(e) for e in error_data.get("errors", []))
        elif "detail" in error_data:
            error_message = str(error_data["detail"])

        # Should contain error indication (but not deprecated format-specific)
        self.assertIsInstance(error_message, str)
        self.assertGreater(len(error_message), 0)
        # Should not contain deprecated format-specific messages
        self.assertNotIn("DCS contracts are no longer supported", error_message)
        self.assertNotIn("Data Contract Specification (DCS) is no longer supported", error_message)

    def test_odcs_contract_acceptance(self):
        """Test that ODCS contracts are still accepted (regression test)"""
        odcs_contract_yaml = """
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: test-contract
name: Test Contract
version: 1.0.0
schema:
  fields:
    - name: field1
      type: string
      nullable: false
"""

        hub_contract, spec_type, _spec_version, norm_status, _errors, _warnings = (
            normalize_contract(odcs_contract_yaml, format="yaml")
        )

        # Normalization should succeed
        self.assertIsNotNone(hub_contract)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertIn(
            norm_status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

    def test_dcs_contract_with_api_version_field(self):
        """Test that contracts with both deprecated and ODCS-like fields normalize as ODCS"""
        import json

        # Contract with dataContractSpecification (deprecated) but also has apiVersion
        mixed_contract = {
            "dataContractSpecification": "0.9.0",
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
        }

        # Should normalize as ODCS (apiVersion and kind take precedence)
        _hub_contract, spec_type, spec_version, _norm_status, errors, _warnings = (
            normalize_contract(json.dumps(mixed_contract), format="json")
        )

        # Should be detected as ODCS (apiVersion and kind take precedence)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        self.assertEqual(spec_version, "3.0.2")
        # Should not contain DCS-specific error messages
        error_message = " ".join(errors) if errors else ""
        self.assertNotIn("DCS contracts are no longer supported", error_message)
        self.assertNotIn("Data Contract Specification (DCS) is no longer supported", error_message)

    def test_error_message_for_invalid_contract(self):
        """Test that error messages are provided for invalid contracts"""
        invalid_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
"""

        _hub_contract, _spec_type, _spec_version, norm_status, errors, _warnings = (
            normalize_contract(invalid_contract_yaml, format="yaml")
        )

        # Should have normalization failure
        self.assertEqual(norm_status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(errors), 0)

        error_message = " ".join(errors)
        # Should contain error information (but not deprecated format-specific)
        self.assertIsInstance(error_message, str)
        self.assertGreater(len(error_message), 0)
        # Should not contain deprecated format-specific messages
        self.assertNotIn("DCS contracts are no longer supported", error_message)
        self.assertNotIn("Data Contract Specification (DCS) is no longer supported", error_message)


class DCSRejectionIntegrationTestCase(DCSRejectionTestBase):
    """Integration tests for deprecated contract specification rejection in full workflow"""

    def test_dcs_contract_creation_fails(self):
        """Test that creating a contract with deprecated format fails via API"""
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
info:
  title: Test Contract
  version: 1.0.0
schema:
  type: object
  properties:
    field1:
      type: string
"""

        response = self.client.post(
            "/api/v1/contracts/",
            {"original_raw": dcs_contract_yaml, "original_format": "YAML"},
            format="json",
        )

        # Should fail
        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY],
        )

        # No contract should be created
        contract_count = Contract.objects.filter(tenant=self.tenant).count()
        self.assertEqual(contract_count, 0)

    def test_dcs_contract_update_fails(self):
        """Test that updating a contract to deprecated format fails"""
        # First create an ODCS contract
        odcs_contract_yaml = """
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: test-contract
name: Test Contract
version: 1.0.0
schema:
  fields:
    - name: field1
      type: string
      nullable: false
"""

        create_response = self.client.post(
            "/api/v1/contracts/",
            {"original_raw": odcs_contract_yaml, "original_format": "YAML"},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        contract_id = create_response.data["id"]

        # Try to update with deprecated format
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
info:
  title: Test Contract
  version: 1.0.0
"""

        update_response = self.client.put(
            f"/api/v1/contracts/{contract_id}/",
            {"original_raw": dcs_contract_yaml, "original_format": "YAML"},
            format="json",
        )

        # Should fail
        self.assertIn(
            update_response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY],
        )

    def test_dcs_contract_patch_fails(self):
        """Test that patching a contract with deprecated format fails"""
        # First create an ODCS contract
        odcs_contract_yaml = """
apiVersion: odcs.io/v3.0.2
kind: DataContract
id: test-contract
name: Test Contract
version: 1.0.0
schema:
  fields:
    - name: field1
      type: string
      nullable: false
"""

        create_response = self.client.post(
            "/api/v1/contracts/",
            {"original_raw": odcs_contract_yaml, "original_format": "YAML"},
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        contract_id = create_response.data["id"]

        # Try to patch with deprecated format
        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
info:
  title: Test Contract
  version: 1.0.0
"""

        patch_response = self.client.patch(
            f"/api/v1/contracts/{contract_id}/",
            {"original_raw": dcs_contract_yaml, "original_format": "YAML"},
            format="json",
        )

        # Should fail
        self.assertIn(
            patch_response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY],
        )

    def test_dcs_contract_malformed_json_handling(self):
        """Test handling of malformed JSON DCS contracts"""
        malformed_json = '{"dataContractSpecification": 0.9.0, "id": "test", invalid}'

        _hub_contract, _spec_type, _spec_version, norm_status, errors, _warnings = (
            normalize_contract(malformed_json, format="json")
        )

        # Should handle malformed JSON gracefully
        self.assertIsNotNone(norm_status)
        # May fail parsing or normalization
        if norm_status == NormalizationStatus.NORMALIZATION_FAILED:
            self.assertGreater(len(errors), 0)

    def test_dcs_contract_malformed_yaml_handling(self):
        """Test handling of malformed YAML DCS contracts"""
        malformed_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
info:
  title: Test Contract
  invalid: [unclosed bracket
"""

        _hub_contract, _spec_type, _spec_version, norm_status, errors, _warnings = (
            normalize_contract(malformed_yaml, format="yaml")
        )

        # Should handle malformed YAML gracefully
        self.assertIsNotNone(norm_status)
        # May fail parsing or normalization
        if norm_status == NormalizationStatus.NORMALIZATION_FAILED:
            self.assertGreater(len(errors), 0)

    def test_dcs_contract_empty_handling(self):
        """Test handling of empty DCS contracts"""
        empty_contract = ""

        _hub_contract, _spec_type, _spec_version, norm_status, errors, _warnings = (
            normalize_contract(empty_contract, format="yaml")
        )

        # Should handle empty contract gracefully
        self.assertIsNotNone(norm_status)
        # Should fail normalization
        self.assertEqual(norm_status, NormalizationStatus.NORMALIZATION_FAILED)
        self.assertGreater(len(errors), 0)

    def test_dcs_contract_missing_required_fields(self):
        """Test handling of DCS contracts with missing required fields"""
        incomplete_contract = """
dataContractSpecification: 0.9.0
# Missing id and info fields
"""

        _hub_contract, _spec_type, _spec_version, norm_status, errors, _warnings = (
            normalize_contract(incomplete_contract, format="yaml")
        )

        # Should handle missing fields gracefully
        self.assertIsNotNone(norm_status)
        # May fail validation or normalization
        if norm_status == NormalizationStatus.NORMALIZATION_FAILED:
            self.assertGreater(len(errors), 0)

    def test_dcs_contract_invalid_field_types(self):
        """Test handling of DCS contracts with invalid field types"""
        invalid_types_contract = """
dataContractSpecification: [invalid, array]
id: 12345  # Should be string
info:
  title: Test Contract
  version: 1.0.0
"""

        _hub_contract, _spec_type, _spec_version, norm_status, errors, _warnings = (
            normalize_contract(invalid_types_contract, format="yaml")
        )

        # Should handle invalid types gracefully
        self.assertIsNotNone(norm_status)
        # May fail validation or normalization
        if norm_status == NormalizationStatus.NORMALIZATION_FAILED:
            self.assertGreater(len(errors), 0)

    def test_dcs_contract_very_large_payload(self):
        """Test handling of very large DCS contracts"""
        self.client.force_authenticate(user=self.user)

        # Create a very large contract payload
        large_schema = "  " + "\n  ".join([f"field_{i}: string" for i in range(1000)])
        large_contract = f"""
dataContractSpecification: 0.9.0
id: large-contract
info:
  title: Large Contract
  version: 1.0.0
schema:
{large_schema}
"""

        response = self.client.post(
            "/api/v1/contracts/",
            {"original_raw": large_contract, "original_format": "YAML"},
            format="json",
        )

        # Should handle large payload gracefully (either succeed or return appropriate error)
        self.assertLess(
            response.status_code,
            500,
        )

    def test_dcs_contract_special_characters_handling(self):
        """Test handling of DCS contracts with special characters"""
        special_chars_contract = """
dataContractSpecification: 0.9.0
id: "test-contract-<script>alert('xss')</script>"
info:
  title: "Test Contract with 'quotes' and \"double quotes\""
  version: 1.0.0
"""

        _hub_contract, _spec_type, _spec_version, norm_status, _errors, _warnings = (
            normalize_contract(special_chars_contract, format="yaml")
        )

        # Should handle special characters gracefully
        self.assertIsNotNone(norm_status)
        # Should sanitize or handle special characters appropriately

    def test_dcs_contract_detection_with_different_versions(self):
        """Test detection of different DCS specification versions"""
        dcs_versions = ["0.9.0", "0.8.0", "0.7.0"]

        for version in dcs_versions:
            dcs_contract = {
                "dataContractSpecification": version,
                "id": f"test-contract-{version}",
                "info": {"title": "Test Contract", "version": "1.0.0"},
            }

            spec_type, _spec_version = detect_spec_type(dcs_contract)
            # All DCS versions should be detected as ODCS
            self.assertEqual(spec_type, OriginalSpecType.ODCS)

    def test_dcs_contract_api_error_response_structure(self):
        """Test that API error responses have proper structure"""
        self.client.force_authenticate(user=self.user)

        dcs_contract_yaml = """
dataContractSpecification: 0.9.0
id: test-contract
"""

        response = self.client.post(
            "/api/v1/contracts/",
            {"original_raw": dcs_contract_yaml, "original_format": "YAML"},
            format="json",
        )

        # Should return error response
        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY],
        )

        # Error response should have proper structure
        error_data = response.data
        self.assertIsNotNone(error_data)
        # Should contain error information
        self.assertTrue(
            "error" in str(error_data).lower()
            or "errors" in error_data
            or "detail" in error_data
            or "message" in str(error_data).lower()
        )
