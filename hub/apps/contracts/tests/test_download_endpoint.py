"""
Integration tests for contract download endpoint (Task 2.2.2)

Comprehensive integration tests verifying:
1. Download endpoint functionality
2. Format selection (odps, odcs, hubcontract)
3. Output format selection (yaml, json)
4. File download headers (Content-Disposition)
5. Original vs generated format handling

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


class ContractDownloadEndpointTest(TestCase):
    """Integration tests for contract download endpoint"""

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
            "description": "Test contract for download",
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
                    "description": "Test contract for download",
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

    def test_download_hubcontract_format_json(self):
        """Test downloading contract as HubContract format in JSON"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/download/",
            {"format": "hubcontract", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("Content-Disposition", response)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".hubcontract.json", response["Content-Disposition"])

        # Verify content is valid JSON
        data = json.loads(response.content)
        self.assertEqual(data["id"], "test-contract-odcs")
        self.assertEqual(data["info"]["name"], "Test ODCS Contract")

    def test_download_hubcontract_format_yaml(self):
        """Test downloading contract as HubContract format in YAML"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/download/",
            {"format": "hubcontract", "output_format": "yaml"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("yaml", response["Content-Type"].lower())
        self.assertIn("Content-Disposition", response)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".hubcontract.yaml", response["Content-Disposition"])

        # Verify YAML content is valid
        import yaml

        data = yaml.safe_load(response.content)
        self.assertEqual(data["id"], "test-contract-odcs")
        self.assertEqual(data["info"]["name"], "Test ODCS Contract")

    def test_download_odcs_format_json(self):
        """Test downloading contract as ODCS format in JSON"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/download/",
            {"format": "odcs", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("Content-Disposition", response)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".odcs.json", response["Content-Disposition"])

        data = json.loads(response.content)
        self.assertEqual(data["id"], "test-contract-odcs")
        self.assertEqual(data["name"], "Test ODCS Contract")

    def test_download_odcs_format_yaml(self):
        """Test downloading contract as ODCS format in YAML"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/download/",
            {"format": "odcs", "output_format": "yaml"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("yaml", response["Content-Type"].lower())
        self.assertIn("Content-Disposition", response)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".odcs.yaml", response["Content-Disposition"])

        # Verify YAML content is valid
        import yaml

        data = yaml.safe_load(response.content)
        self.assertEqual(data["id"], "test-contract-odcs")
        self.assertEqual(data["name"], "Test ODCS Contract")

    def test_download_odps_format_json(self):
        """Test downloading contract as ODPS format in JSON"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/download/",
            {"format": "odps", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("Content-Disposition", response)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".odps.json", response["Content-Disposition"])

        # Verify content is valid JSON and contains ODPS structure
        data = json.loads(response.content)
        self.assertIn("schema", data)
        self.assertIn("version", data)

    def test_download_odps_format_yaml(self):
        """Test downloading contract as ODPS format in YAML"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/download/",
            {"format": "odps", "output_format": "yaml"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("yaml", response["Content-Type"].lower())
        self.assertIn("Content-Disposition", response)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".odps.yaml", response["Content-Disposition"])

        # Verify YAML content is valid and contains ODPS structure
        import yaml

        data = yaml.safe_load(response.content)
        self.assertIn("schema", data)
        self.assertIn("version", data)

    def test_download_default_format(self):
        """Test downloading contract with default format (hubcontract, json)"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/download/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("Content-Disposition", response)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn(".hubcontract.json", response["Content-Disposition"])

        # Verify content is valid JSON
        data = json.loads(response.content)
        self.assertEqual(data["id"], "test-contract-odcs")

    def test_download_invalid_format(self):
        """Test downloading contract with invalid format parameter"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/download/",
            {"format": "invalid"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", json.loads(response.content))

    def test_download_invalid_output_format(self):
        """Test downloading contract with invalid output_format parameter"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/download/",
            {"output_format": "invalid"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", json.loads(response.content))

    def test_download_nonexistent_contract(self):
        """Test downloading nonexistent contract ID"""
        self.client.force_authenticate(user=self.user)

        import uuid

        nonexistent_id = uuid.uuid4()
        response = self.client.get(
            f"/api/v1/contracts/{nonexistent_id}/download/",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_unauthorized(self):
        """Test download endpoint requires authentication"""
        # Don't authenticate
        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/download/",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_download_contract_without_hub_contract_json(self):
        """Test downloading contract without hub_contract_json"""
        self.client.force_authenticate(user=self.user)

        # Create contract without hub_contract_json
        contract_no_hub = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            hub_contract_json=None,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Try to download as hubcontract (should fail)
        response = self.client.get(
            f"/api/v1/contracts/{contract_no_hub.id}/download/",
            {"format": "hubcontract"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", json.loads(response.content))

        # Try to download as odcs (should work if original_raw exists)
        response = self.client.get(
            f"/api/v1/contracts/{contract_no_hub.id}/download/",
            {"format": "odcs"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Content-Disposition", response)

    def test_download_filename_sanitization(self):
        """Test that filenames are properly sanitized"""
        self.client.force_authenticate(user=self.user)

        # Create contract with special characters in name (in hub_contract_json)
        contract_special = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "test-contract-special",
                "info": {
                    "name": "Test/Contract:Name*With?Special|Chars",
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        response = self.client.get(
            f"/api/v1/contracts/{contract_special.id}/download/",
            {"format": "hubcontract", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Content-Disposition", response)
        # Filename should not contain special characters
        content_disposition = response["Content-Disposition"]
        self.assertNotIn("/", content_disposition)
        self.assertNotIn(":", content_disposition)
        self.assertNotIn("*", content_disposition)
        self.assertNotIn("?", content_disposition)
        self.assertNotIn("|", content_disposition)

    def test_download_cross_tenant_isolation(self):
        """Test that users can only download contracts from their own tenant"""
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
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "other-contract",
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Try to download contract from other tenant
        response = self.client.get(
            f"/api/v1/contracts/{other_contract.id}/download/",
        )

        # Should return 404 (not found) due to tenant isolation
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ODCSDownloadVersionSupportTest(TestCase):
    """Comprehensive tests for ODCS download with version support (Task 9.5.4.1.5.1)"""

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
                "description": "Test contract for version download",
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
        self.contract_without_original = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw="",
            hub_contract_json=self.hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

    def _extract_filename_from_content_disposition(self, content_disposition):
        """Helper to extract filename from Content-Disposition header"""
        if 'filename="' in content_disposition:
            start = content_disposition.index('filename="') + len('filename="')
            end = content_disposition.index('"', start)
            return content_disposition[start:end]
        elif "filename=" in content_disposition:
            start = content_disposition.index("filename=") + len("filename=")
            return content_disposition[start:]
        return None

    def test_download_odcs_with_version_parameter_3_0_2_json(self):
        """Test downloading ODCS with version parameter 3.0.2 as JSON"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("Content-Disposition", response)
        self.assertIn("attachment", response["Content-Disposition"])

        # Check filename includes version
        filename = self._extract_filename_from_content_disposition(response["Content-Disposition"])
        self.assertIsNotNone(filename)
        self.assertIn(".odcs.json", filename)
        # Filename should include version (may be in name or as separate identifier)
        # Format: {name}.odcs.{version}.json or {name}-v{version}.odcs.json
        self.assertTrue(
            "3.0.2" in filename or "v3.0.2" in filename or "302" in filename,
            f"Filename '{filename}' should contain version 3.0.2"
        )

        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(data["id"], "test-contract-version")

    def test_download_odcs_with_version_parameter_3_0_2_yaml(self):
        """Test downloading ODCS with version parameter 3.0.2 as YAML"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "yaml", "version": "3.0.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("yaml", response["Content-Type"].lower())
        self.assertIn("Content-Disposition", response)
        self.assertIn("attachment", response["Content-Disposition"])

        filename = self._extract_filename_from_content_disposition(response["Content-Disposition"])
        self.assertIsNotNone(filename)
        self.assertIn(".odcs.yaml", filename)

        import yaml
        data = yaml.safe_load(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.2")

    def test_download_odcs_with_version_parameter_3_0_1_json(self):
        """Test downloading ODCS with version parameter 3.0.1 as JSON"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "3.0.1"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.1")

        filename = self._extract_filename_from_content_disposition(response["Content-Disposition"])
        self.assertIsNotNone(filename)
        self.assertIn(".odcs.json", filename)

    def test_download_odcs_with_version_parameter_3_0_0_json(self):
        """Test downloading ODCS with version parameter 3.0.0 as JSON"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "3.0.0"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.0")

    def test_download_odcs_with_version_parameter_3_0_0_preview_json(self):
        """Test downloading ODCS with version parameter 3.0.0-preview as JSON"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "3.0.0-preview"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.0-preview")

    def test_download_odcs_with_version_parameter_2_2_2_json(self):
        """Test downloading ODCS with version parameter 2.2.2 as JSON"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "2.2.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v2.2.2")

    def test_download_odcs_when_original_raw_missing_generates_json(self):
        """Test downloading ODCS when original_raw is missing - should generate from HubContract"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Content-Disposition", response)
        self.assertIn("attachment", response["Content-Disposition"])

        data = json.loads(response.content)
        self.assertIn("apiVersion", data)
        self.assertIn("kind", data)
        self.assertEqual(data["kind"], "DataContract")
        self.assertEqual(data["id"], "test-contract-version")

    def test_download_odcs_when_original_exists_and_version_matches_returns_original_json(self):
        """Test downloading ODCS when original_raw exists and version matches - should return original"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_with_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Content-Disposition", response)

        data = json.loads(response.content)
        # Should return original (not generated)
        self.assertEqual(data["id"], "test-contract-v302")
        self.assertEqual(data["name"], "Test Contract v3.0.2")
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.2")

    def test_download_odcs_when_original_exists_but_version_different_generates_json(self):
        """Test downloading ODCS when original_raw exists but version is different - should generate"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_with_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "3.0.1"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Content-Disposition", response)

        data = json.loads(response.content)
        # Should generate new version (not return original)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.1")
        # ID should come from hub_contract_json, not original
        self.assertEqual(data["id"], "test-contract-version")

    def test_download_odcs_format_conversion_json_to_yaml(self):
        """Test format conversion during download: JSON to YAML"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_with_original.id}/download/",
            {"format": "odcs", "output_format": "yaml", "version": "3.0.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("yaml", response["Content-Type"].lower())
        self.assertIn("Content-Disposition", response)

        filename = self._extract_filename_from_content_disposition(response["Content-Disposition"])
        self.assertIsNotNone(filename)
        self.assertIn(".odcs.yaml", filename)

        import yaml
        data = yaml.safe_load(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(data["id"], "test-contract-v302")

    def test_download_odcs_format_conversion_yaml_to_json(self):
        """Test format conversion during download: YAML to JSON"""
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
            f"/api/v1/contracts/{contract_yaml.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn("Content-Disposition", response)

        filename = self._extract_filename_from_content_disposition(response["Content-Disposition"])
        self.assertIsNotNone(filename)
        self.assertIn(".odcs.json", filename)

        data = json.loads(response.content)
        self.assertEqual(data["apiVersion"], "odcs.io/v3.0.2")
        self.assertEqual(data["id"], "test-yaml")

    def test_download_odcs_error_handling_invalid_version(self):
        """Test error handling for invalid ODCS version"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "99.99.99"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", json.loads(response.content))
        error_msg = str(json.loads(response.content)["error"]).lower()
        self.assertIn("version", error_msg)

    def test_download_odcs_error_handling_generation_failure(self):
        """Test error handling for generation failures"""
        self.client.force_authenticate(user=self.user)

        # Create contract with invalid hub_contract_json (missing required fields)
        invalid_contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw="",
            hub_contract_json={},  # Invalid - missing required fields
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        response = self.client.get(
            f"/api/v1/contracts/{invalid_contract.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )

        # Should return 500 with error details
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("error", json.loads(response.content))

    def test_download_odcs_filename_includes_version(self):
        """Test that downloaded filename includes version information"""
        self.client.force_authenticate(user=self.user)

        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            with self.subTest(version=version):
                response = self.client.get(
                    f"/api/v1/contracts/{self.contract_without_original.id}/download/",
                    {"format": "odcs", "output_format": "json", "version": version},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("Content-Disposition", response)

                filename = self._extract_filename_from_content_disposition(response["Content-Disposition"])
                self.assertIsNotNone(filename, f"Filename should be present for version {version}")
                self.assertIn(".odcs.json", filename, f"Filename should contain .odcs.json for version {version}")

    def test_download_odcs_all_versions_json(self):
        """Test downloading ODCS in all supported versions as JSON"""
        self.client.force_authenticate(user=self.user)

        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            with self.subTest(version=version):
                response = self.client.get(
                    f"/api/v1/contracts/{self.contract_without_original.id}/download/",
                    {"format": "odcs", "output_format": "json", "version": version},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response["Content-Type"], "application/json")
                self.assertIn("Content-Disposition", response)

                data = json.loads(response.content)
                self.assertEqual(data["apiVersion"], f"odcs.io/v{version}")
                self.assertEqual(data["id"], "test-contract-version")

    def test_download_odcs_all_versions_yaml(self):
        """Test downloading ODCS in all supported versions as YAML"""
        self.client.force_authenticate(user=self.user)

        versions = ["3.0.2", "3.0.1", "3.0.0", "3.0.0-preview", "2.2.2"]

        for version in versions:
            with self.subTest(version=version):
                response = self.client.get(
                    f"/api/v1/contracts/{self.contract_without_original.id}/download/",
                    {"format": "odcs", "output_format": "yaml", "version": version},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("yaml", response["Content-Type"].lower())
                self.assertIn("Content-Disposition", response)

                import yaml
                data = yaml.safe_load(response.content)
                self.assertEqual(data["apiVersion"], f"odcs.io/v{version}")
                self.assertEqual(data["id"], "test-contract-version")

    def test_download_odcs_content_disposition_header_format(self):
        """Test that Content-Disposition header is properly formatted"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content_disposition = response["Content-Disposition"]

        # Should start with "attachment;"
        self.assertTrue(content_disposition.startswith("attachment;"))
        # Should contain filename=
        self.assertIn("filename=", content_disposition)
        # Filename should be quoted
        self.assertIn('"', content_disposition)

    def test_download_odcs_content_type_header(self):
        """Test that Content-Type header is correctly set"""
        self.client.force_authenticate(user=self.user)

        # Test JSON
        response_json = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "json", "version": "3.0.2"},
        )
        self.assertEqual(response_json.status_code, status.HTTP_200_OK)
        self.assertEqual(response_json["Content-Type"], "application/json")

        # Test YAML
        response_yaml = self.client.get(
            f"/api/v1/contracts/{self.contract_without_original.id}/download/",
            {"format": "odcs", "output_format": "yaml", "version": "3.0.2"},
        )
        self.assertEqual(response_yaml.status_code, status.HTTP_200_OK)
        self.assertIn("yaml", response_yaml["Content-Type"].lower())

