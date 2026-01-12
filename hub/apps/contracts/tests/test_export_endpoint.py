"""
Integration tests for contract export endpoint (Task 2.2.1)

Comprehensive integration tests verifying:
1. Export endpoint functionality
2. Format selection (odps, odcs, hubcontract)
3. Output format selection (yaml, json)
4. Original vs generated format handling

Tests use real implementations (no mocks/stubs) and follow TDD principles.
"""

import json
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalSpecType,
    OriginalFormat,
    NormalizationStatus,
)
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ContractExportEndpointTest(TestCase):
    """Integration tests for contract export endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create ODCS contract
        self.odcs_contract_data = {
            "id": "test-contract-odcs",
            "name": "Test ODCS Contract",
            "description": "Test contract for export",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "description": "Unique identifier"},
                    {"name": "name", "type": "string", "description": "Name field"},
                ]
            },
        }

        # Create contract with ODCS original
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "test-contract-odcs",
                "info": {
                    "name": "Test ODCS Contract",
                    "description": "Test contract for export",
                    "version": "1.0.0",
                },
                "schema": {
                    "fields": [
                        {"name": "id", "type": "string", "description": "Unique identifier"},
                        {"name": "name", "type": "string", "description": "Name field"},
                    ]
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

    def test_export_hubcontract_format_json(self):
        """Test exporting contract as HubContract format in JSON"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/export/",
            {"format": "hubcontract", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")

        data = json.loads(response.content)
        self.assertEqual(data["id"], "test-contract-odcs")
        self.assertEqual(data["info"]["name"], "Test ODCS Contract")
        self.assertIn("hub_contract_version", data)

    def test_export_hubcontract_format_yaml(self):
        """Test exporting contract as HubContract format in YAML"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/export/",
            {"format": "hubcontract", "output_format": "yaml"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("yaml", response["Content-Type"].lower())

        # Verify YAML content is valid
        import yaml

        data = yaml.safe_load(response.content)
        self.assertEqual(data["id"], "test-contract-odcs")
        self.assertEqual(data["info"]["name"], "Test ODCS Contract")

    def test_export_odcs_format_json(self):
        """Test exporting contract as ODCS format in JSON"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/export/",
            {"format": "odcs", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")

        data = json.loads(response.content)
        self.assertEqual(data["id"], "test-contract-odcs")
        self.assertEqual(data["name"], "Test ODCS Contract")
        self.assertIn("schema", data)

    def test_export_odcs_format_yaml(self):
        """Test exporting contract as ODCS format in YAML"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/export/",
            {"format": "odcs", "output_format": "yaml"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("yaml", response["Content-Type"].lower())

        # Verify YAML content is valid
        import yaml

        data = yaml.safe_load(response.content)
        self.assertEqual(data["id"], "test-contract-odcs")
        self.assertEqual(data["name"], "Test ODCS Contract")

    def test_export_odps_format_json(self):
        """Test exporting contract as ODPS format in JSON"""
        self.client.force_authenticate(user=self.user)

        # Update contract to have marketplace data for ODPS export
        self.contract.hub_contract_json["marketplace"] = {
            "license_summary": "Test license",
            "intended_use": ["analytics"],
        }
        self.contract.save()

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/export/",
            {"format": "odps", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")

        data = json.loads(response.content)
        self.assertIn("schema", data)
        self.assertIn("version", data)
        self.assertIn("product", data)

    def test_export_odps_format_yaml(self):
        """Test exporting contract as ODPS format in YAML"""
        self.client.force_authenticate(user=self.user)

        # Update contract to have marketplace data for ODPS export
        self.contract.hub_contract_json["marketplace"] = {
            "license_summary": "Test license",
            "intended_use": ["analytics"],
        }
        self.contract.save()

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/export/",
            {"format": "odps", "output_format": "yaml"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("yaml", response["Content-Type"].lower())

        # Verify YAML content is valid
        import yaml

        data = yaml.safe_load(response.content)
        self.assertIn("schema", data)
        self.assertIn("version", data)
        self.assertIn("product", data)

    def test_export_default_format_hubcontract(self):
        """Test export endpoint defaults to hubcontract format"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/export/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertIn("hub_contract_version", data)

    def test_export_default_output_format_json(self):
        """Test export endpoint defaults to JSON output format"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/export/",
            {"format": "hubcontract"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_export_invalid_format(self):
        """Test export endpoint with invalid format parameter"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/export/",
            {"format": "invalid"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_export_invalid_output_format(self):
        """Test export endpoint with invalid output_format parameter"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/export/",
            {"format": "hubcontract", "output_format": "invalid"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_export_nonexistent_contract(self):
        """Test export endpoint with nonexistent contract ID"""
        self.client.force_authenticate(user=self.user)

        import uuid

        nonexistent_id = uuid.uuid4()
        response = self.client.get(
            f"/api/v1/contracts/{nonexistent_id}/export/",
            {"format": "hubcontract"},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_contract_without_hub_contract_json(self):
        """Test export endpoint with contract that has no hub_contract_json"""
        self.client.force_authenticate(user=self.user)

        # Create contract without hub_contract_json
        contract_no_hub = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            hub_contract_json=None,
            normalization_status=NormalizationStatus.NOT_NORMALIZED,
            status=ContractStatus.DRAFT,
            created_by=self.user,
        )

        # Try to export as hubcontract (should fail)
        response = self.client.get(
            f"/api/v1/contracts/{contract_no_hub.id}/export/",
            {"format": "hubcontract"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

        # Try to export as odcs (should work with original_raw)
        response = self.client.get(
            f"/api/v1/contracts/{contract_no_hub.id}/export/",
            {"format": "odcs", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["id"], "test-contract-odcs")

    def test_export_odps_without_marketplace_data(self):
        """Test exporting ODPS format when contract has no marketplace data"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/export/",
            {"format": "odps", "output_format": "json"},
        )

        # Should still work, just without marketplace sections
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertIn("schema", data)
        self.assertIn("product", data)

    def test_export_unauthorized(self):
        """Test export endpoint requires authentication"""
        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/export/",
            {"format": "hubcontract"},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_export_cross_tenant_isolation(self):
        """Test export endpoint respects tenant isolation"""
        self.client.force_authenticate(user=self.user)

        # Create another tenant and contract
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        other_contract = Contract.objects.create(
            tenant=other_tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            hub_contract_json=self.contract.hub_contract_json,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        # Try to export contract from other tenant (should fail)
        response = self.client.get(
            f"/api/v1/contracts/{other_contract.id}/export/",
            {"format": "hubcontract"},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ODCSExportVersionSupportTest(TestCase):
    """Comprehensive tests for ODCS export with version support (Task 9.5.4.1.4.1)"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create HubContract for generation tests
        self.hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-contract-version",
            "info": {
                "name": "Test Contract Version",
                "description": "Test contract for version export",
                "version": "1.0.0",
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string", "description": "Unique identifier"},
                    {"name": "name", "data_type": "string", "description": "Name field"},
                ]
            },
        }

        # Create ODCS contract data for version 3.0.2
        self.odcs_contract_v3_0_2 = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract-v302",
            "name": "Test Contract v3.0.2",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"},
                ]
            },
        }

        # Create contract with ODCS original (version 3.0.2)
        self.contract_with_original = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_v3_0_2),
            hub_contract_json=self.hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Create contract without original_raw (for generation tests)
        # Note: original_spec_version is required by the model, so we set a default
        # The test scenario is about missing original_raw, not missing version
        self.contract_without_original = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",  # Required field, default to latest
            original_format=OriginalFormat.JSON,  # Required field, set a default
            original_raw="",  # Empty string instead of None to satisfy model constraints
            hub_contract_json=self.hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

    def test_export_odcs_with_version_parameter_3_0_2(self):
        """Test exporting ODCS with version parameter 3.0.2"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")

        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(data["id"], "test-contract-version")
        self.assertEqual(data["name"], "Test Contract Version")

    def test_export_odcs_with_version_parameter_3_0_1(self):
        """Test exporting ODCS with version parameter 3.0.1"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.1"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.1")
        self.assertEqual(data["id"], "test-contract-version")

    def test_export_odcs_with_version_parameter_3_0_0(self):
        """Test exporting ODCS with version parameter 3.0.0"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.0"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.0")
        self.assertEqual(data["id"], "test-contract-version")

    def test_export_odcs_with_version_parameter_3_0_0_preview(self):
        """Test exporting ODCS with version parameter 3.0.0-preview"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.0-preview"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.0-preview")
        self.assertEqual(data["id"], "test-contract-version")

    def test_export_odcs_with_version_parameter_2_2_2(self):
        """Test exporting ODCS with version parameter 2.2.2"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "2.2.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v2.2.2")
        self.assertEqual(data["id"], "test-contract-version")

    def test_export_odcs_when_original_raw_missing_generates(self):
        """Test exporting ODCS when original_raw is missing - should generate from HubContract"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        # Should have generated ODCS document
        self.assertIn("apiVersion", data)
        self.assertIn("kind", data)
        self.assertEqual(data["kind"], "DataContract")
        self.assertEqual(data["id"], "test-contract-version")

    def test_export_odcs_when_original_exists_and_version_matches_returns_original(self):
        """Test exporting ODCS when original_raw exists and version matches - should return original"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_with_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        # Should return original (not generated)
        self.assertEqual(data["id"], "test-contract-v302")
        self.assertEqual(data["name"], "Test Contract v3.0.2")
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.2")

    def test_export_odcs_when_original_exists_but_version_different_generates(self):
        """Test exporting ODCS when original_raw exists but version is different - should generate"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_with_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.1"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        # Should generate new version (not return original)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.1")
        # ID should come from hub_contract_json, not original
        self.assertEqual(data["id"], "test-contract-version")

    def test_export_odcs_format_conversion_json_to_yaml(self):
        """Test format conversion during export: JSON to YAML"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_with_original.id}/export/",
            {"format": "odcs", "output_format": "yaml", "version": "3.0.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("yaml", response["Content-Type"].lower())

        # Verify YAML is valid and contains expected data
        import yaml
        data = yaml.safe_load(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(data["id"], "test-contract-v302")

    def test_export_odcs_format_conversion_yaml_to_json(self):
        """Test format conversion during export: YAML to JSON"""
        self.client.force_authenticate(user=self.user)

        # Create contract with YAML original
        yaml_original = "apiVersion: odcs.io/v3.0.2\nkind: DataContract\nid: test-yaml\nname: Test YAML"
        contract_yaml = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.YAML,
            original_raw=yaml_original,
            hub_contract_json=self.hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        response = self.client.get(
            f"/api/v1/contracts/{contract_yaml.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")

        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(data["id"], "test-yaml")

    def test_export_odcs_error_handling_invalid_version(self):
        """Test error handling for invalid ODCS version"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "99.99.99"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("version", str(response.data["error"]).lower())

    def test_export_odcs_error_handling_invalid_version_format(self):
        """Test error handling for invalid version format"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "invalid-version"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_export_odcs_error_handling_generation_failure(self):
        """Test error handling for generation failures"""
        self.client.force_authenticate(user=self.user)

        # Create contract with invalid hub_contract_json (missing required fields)
        invalid_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",  # Required field
            original_format=OriginalFormat.JSON,  # Required field
            original_raw="",  # Empty string instead of None
            hub_contract_json={},  # Invalid - missing required fields
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        response = self.client.get(
            f"/api/v1/contracts/{invalid_contract.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )

        # Should return 500 with error details
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", response.data)

    def test_export_odcs_performance_under_2s(self):
        """Test performance: export should complete in under 2 seconds (p95)"""
        import time
        self.client.force_authenticate(user=self.user)

        start_time = time.time()
        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )
        duration = time.time() - start_time

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Performance check: should complete in under 2 seconds
        self.assertLess(duration, 2.0, f"Export took {duration:.2f}s, expected < 2.0s")

    def test_export_odcs_all_versions_json(self):
        """Test exporting ODCS in all supported versions as JSON"""
        self.client.force_authenticate(user=self.user)

        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            with self.subTest(version=version):
                response = self.client.get(
                    f"/api/v1/contracts/{self.contract_without_original.id}/export/",
                    {"format": "odcs", "output_format": "json", "version": version},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                data = json.loads(response.content)
                self.assertEqual(data["apiVersion"], f"odcs.io/v{version}")
                self.assertEqual(data["id"], "test-contract-version")

    def test_export_odcs_all_versions_yaml(self):
        """Test exporting ODCS in all supported versions as YAML"""
        self.client.force_authenticate(user=self.user)

        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            with self.subTest(version=version):
                response = self.client.get(
                    f"/api/v1/contracts/{self.contract_without_original.id}/export/",
                    {"format": "odcs", "output_format": "yaml", "version": version},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                import yaml
                data = yaml.safe_load(response.content)
                self.assertEqual(data["apiVersion"], f"odcs.io/v{version}")
                self.assertEqual(data["id"], "test-contract-version")

    def test_export_odcs_without_version_uses_original_or_default(self):
        """Test exporting ODCS without version parameter - should use original version or default"""
        self.client.force_authenticate(user=self.user)

        # Test with contract that has original (should use original version)
        response = self.client.get(
            f"/api/v1/contracts/{self.contract_with_original.id}/export/",
            {"format": "odcs", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        # Should use original version (3.0.2)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.2")

        # Test with contract without original (should default to 3.0.2)
        response2 = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/export/",
            {"format": "odcs", "output_format": "json"},
        )

        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = json.loads(response2.content)
        # Should default to latest version (3.0.2)
        self.assertEqual(data2["apiVersion"], "odcs.io/v3.0.2")

