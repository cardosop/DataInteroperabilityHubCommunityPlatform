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
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
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

        response = self.client.get(f"/api/v1/contracts/contracts/{self.contract.id}/export/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertIn("hub_contract_version", data)

    def test_export_default_output_format_json(self):
        """Test export endpoint defaults to JSON output format"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
            {"format": "hubcontract"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_export_invalid_format(self):
        """Test export endpoint with invalid format parameter"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
            {"format": "invalid"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_export_invalid_output_format(self):
        """Test export endpoint with invalid output_format parameter"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
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
            f"/api/v1/contracts/contracts/{nonexistent_id}/export/",
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
            f"/api/v1/contracts/contracts/{contract_no_hub.id}/export/",
            {"format": "hubcontract"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

        # Try to export as odcs (should work with original_raw)
        response = self.client.get(
            f"/api/v1/contracts/contracts/{contract_no_hub.id}/export/",
            {"format": "odcs", "output_format": "json"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = json.loads(response.content)
        self.assertEqual(data["id"], "test-contract-odcs")

    def test_export_odps_without_marketplace_data(self):
        """Test exporting ODPS format when contract has no marketplace data"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
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
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
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
            f"/api/v1/contracts/contracts/{other_contract.id}/export/",
            {"format": "hubcontract"},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

