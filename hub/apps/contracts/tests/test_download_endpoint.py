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
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
            {"format": "invalid"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", json.loads(response.content))

    def test_download_invalid_output_format(self):
        """Test downloading contract with invalid output_format parameter"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
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
            f"/api/v1/contracts/contracts/{nonexistent_id}/download/",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_unauthorized(self):
        """Test download endpoint requires authentication"""
        # Don't authenticate
        response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
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
            f"/api/v1/contracts/contracts/{contract_no_hub.id}/download/",
            {"format": "hubcontract"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", json.loads(response.content))

        # Try to download as odcs (should work if original_raw exists)
        response = self.client.get(
            f"/api/v1/contracts/contracts/{contract_no_hub.id}/download/",
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
            f"/api/v1/contracts/contracts/{contract_special.id}/download/",
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
            f"/api/v1/contracts/contracts/{other_contract.id}/download/",
        )

        # Should return 404 (not found) due to tenant isolation
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

