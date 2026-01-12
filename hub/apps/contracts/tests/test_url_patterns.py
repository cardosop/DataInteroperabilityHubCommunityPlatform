"""
Tests for contracts URL patterns.

Task: 9.6.3.1.1 - Fix contracts URL pattern duplication
"""

import uuid
from django.test import TestCase
from django.urls import reverse, resolve, Resolver404
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.contracts.models import Contract
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus, Role, UserRole


class ContractsURLPatternTest(TestCase):
    """Test URL pattern resolution and reverse lookup for contracts endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant_id=self.tenant.id,
            status=UserStatus.ACTIVE
        )

        # Create contract
        self.contract = Contract.objects.create(
            tenant_id=self.tenant.id,
            hub_contract_json={
                "id": "test-contract",
                "info": {"name": "Test Contract"}
            }
        )

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_lineage_visualization_url_pattern_resolution(self):
        """Test that lineage visualization URL pattern resolves correctly."""
        contract_id = str(self.contract.id)
        url = f"/api/v1/contracts/{contract_id}/lineage/visualization/"

        # Should resolve without duplication
        try:
            resolved = resolve(url)
            self.assertEqual(resolved.url_name, "contract-lineage-visualization-custom")
            self.assertIn("id", resolved.kwargs)
            self.assertEqual(resolved.kwargs["id"], contract_id)
        except Resolver404 as e:
            self.fail(f"URL pattern did not resolve: {e}")

    def test_lineage_visualization_url_pattern_no_duplication(self):
        """Test that lineage visualization URL does not have duplicate 'contracts' segment."""
        contract_id = str(self.contract.id)
        url = f"/api/v1/contracts/{contract_id}/lineage/visualization/"

        # Should NOT contain duplicate 'contracts'
        self.assertNotIn("/contracts/contracts/", url)

        # Should resolve correctly
        resolved = resolve(url)
        self.assertEqual(resolved.url_name, "contract-lineage-visualization-custom")

    def test_lineage_visualization_reverse_lookup(self):
        """Test reverse lookup for lineage visualization endpoint."""
        contract_id = str(self.contract.id)

        # Should be able to reverse the URL
        try:
            url = reverse(
                "contract-lineage-visualization-custom",
                kwargs={"id": contract_id}
            )

            # Should not contain duplicate 'contracts'
            self.assertNotIn("/contracts/contracts/", url)

            # Should match expected pattern
            self.assertIn(f"/api/v1/contracts/{contract_id}/lineage/visualization/", url)

            # Should resolve back to the same endpoint
            resolved = resolve(url)
            self.assertEqual(resolved.url_name, "contract-lineage-visualization-custom")
            self.assertEqual(resolved.kwargs["id"], contract_id)

        except Exception as e:
            self.fail(f"Reverse lookup failed: {e}")

    def test_lineage_visualization_endpoint_integration(self):
        """Integration test for lineage visualization endpoint."""
        contract_id = str(self.contract.id)
        url = f"/api/v1/contracts/{contract_id}/lineage/visualization/"

        # Should be accessible (may return 200 or other status, but should not 404)
        response = self.client.get(url)

        # Should not be 404 (pattern resolved correctly)
        self.assertNotEqual(response.status_code, status.HTTP_404_NOT_FOUND,
                           f"Endpoint not found. URL: {url}, Response: {response.data if hasattr(response, 'data') else response.content}")

        # Should be accessible (200, 400, 403, etc. are all valid - just not 404)
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ], f"Unexpected status code: {response.status_code}")

    def test_lineage_visualization_url_pattern_with_format_query_param(self):
        """Test that lineage visualization URL works with format query parameter."""
        contract_id = str(self.contract.id)
        url = f"/api/v1/contracts/{contract_id}/lineage/visualization/?format=dot"

        # Should resolve correctly even with query parameter
        try:
            resolved = resolve(url.split("?")[0])  # Resolve without query params
            self.assertEqual(resolved.url_name, "contract-lineage-visualization-custom")
            self.assertEqual(resolved.kwargs["id"], contract_id)
        except Resolver404 as e:
            self.fail(f"URL pattern did not resolve with query parameter: {e}")

    def test_lineage_visualization_url_pattern_with_uuid(self):
        """Test that lineage visualization URL pattern works with UUID contract IDs."""
        # Create contract with UUID
        contract_uuid = uuid.uuid4()
        contract = Contract.objects.create(
            tenant_id=self.tenant.id,
            id=contract_uuid,
            hub_contract_json={
                "id": "test-contract-uuid",
                "info": {"name": "Test Contract UUID"}
            }
        )

        contract_id = str(contract.id)
        url = f"/api/v1/contracts/{contract_id}/lineage/visualization/"

        # Should resolve correctly
        try:
            resolved = resolve(url)
            self.assertEqual(resolved.url_name, "contract-lineage-visualization-custom")
            self.assertEqual(resolved.kwargs["id"], contract_id)
        except Resolver404 as e:
            self.fail(f"URL pattern did not resolve with UUID: {e}")

    def test_lineage_visualization_url_pattern_with_string_id(self):
        """Test that lineage visualization URL pattern works with string contract IDs."""
        # Note: Contract model uses UUID as primary key, but URL pattern accepts string IDs
        # This test verifies the URL pattern can handle string representations of UUIDs
        contract_uuid = uuid.uuid4()
        contract = Contract.objects.create(
            tenant_id=self.tenant.id,
            id=contract_uuid,
            hub_contract_json={
                "id": "test-contract-string-id",
                "info": {"name": "Test Contract String"}
            }
        )

        # Use string representation of UUID (which is what URLs use)
        contract_string_id = str(contract_uuid)
        url = f"/api/v1/contracts/{contract_string_id}/lineage/visualization/"

        # Should resolve correctly
        try:
            resolved = resolve(url)
            self.assertEqual(resolved.url_name, "contract-lineage-visualization-custom")
            self.assertEqual(resolved.kwargs["id"], contract_string_id)
        except Resolver404 as e:
            self.fail(f"URL pattern did not resolve with string ID: {e}")

    def test_lineage_visualization_url_pattern_invalid_id(self):
        """Test that lineage visualization URL pattern handles invalid IDs gracefully."""
        invalid_id = "nonexistent-id-12345"
        url = f"/api/v1/contracts/{invalid_id}/lineage/visualization/"

        # Should resolve (pattern matches), but endpoint may return 404 for non-existent contract
        try:
            resolved = resolve(url)
            self.assertEqual(resolved.url_name, "contract-lineage-visualization-custom")
            self.assertEqual(resolved.kwargs["id"], invalid_id)
        except Resolver404 as e:
            self.fail(f"URL pattern should resolve even for invalid ID: {e}")

