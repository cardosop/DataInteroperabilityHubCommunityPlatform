"""
Integration tests for multi-tenant isolation (T.8).

Tests that tenants cannot access each other's data.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.files.models import File, FileStatus
import uuid


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MultiTenantIsolationTest(TestCase):
    """Integration tests for multi-tenant isolation (T.8)"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Tenant A
        self.tenant_a = Tenant.objects.create(
            name="Tenant A",
            slug="tenant-a",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.user_a = User.objects.create_user(
            email=f"user_a-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant_a
        )
        
        self.client_a = APIClient()
        self.client_a.force_authenticate(user=self.user_a)
        
        # Tenant B
        self.tenant_b = Tenant.objects.create(
            name="Tenant B",
            slug="tenant-b",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.user_b = User.objects.create_user(
            email=f"user_b-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant_b
        )
        
        self.client_b = APIClient()
        self.client_b.force_authenticate(user=self.user_b)
        
        # Create assets for each tenant
        self.asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            key="asset-a",
            name="Asset A",
            status=AssetStatus.ACTIVE,
            created_by=self.user_a
        )
        
        self.asset_b = Asset.objects.create(
            tenant=self.tenant_b,
            key="asset-b",
            name="Asset B",
            status=AssetStatus.ACTIVE,
            created_by=self.user_b
        )
    
    def test_tenant_cannot_see_other_tenant_assets(self):
        """Test that tenant A cannot see tenant B's assets"""
        # Tenant A lists assets
        response = self.client_a.get('/api/v1/assets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        asset_ids = [asset['id'] for asset in response.data['results']]
        
        # Should only see own assets
        self.assertIn(str(self.asset_a.id), asset_ids)
        self.assertNotIn(str(self.asset_b.id), asset_ids)
    
    def test_tenant_cannot_access_other_tenant_asset(self):
        """Test that tenant A cannot access tenant B's asset by ID"""
        # Tenant A tries to access tenant B's asset
        response = self.client_a.get(f'/api/v1/assets/{self.asset_b.id}/')

        # Should return 403 or 404 (forbidden or not found due to tenant filtering)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_tenant_cannot_update_other_tenant_asset(self):
        """Test that tenant A cannot update tenant B's asset"""
        response = self.client_a.patch(
            f'/api/v1/assets/{self.asset_b.id}/',
            {'name': 'Hacked Asset'},
            format='json'
        )

        # Should return 403 or 404
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Asset should remain unchanged
        self.asset_b.refresh_from_db()
        self.assertEqual(self.asset_b.name, 'Asset B')

    def test_tenant_cannot_delete_other_tenant_asset(self):
        """Test that tenant A cannot delete tenant B's asset"""
        response = self.client_a.delete(f'/api/v1/assets/{self.asset_b.id}/')

        # Should return 403 or 404
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Asset should still exist
        self.assertTrue(Asset.objects.filter(id=self.asset_b.id).exists())
    
    def test_tenant_cannot_create_contract_for_other_tenant_asset(self):
        """Test that tenant A cannot create contract for tenant B's asset"""
        response = self.client_a.post(
            '/api/v1/contracts/',
            {
                'asset_id': str(self.asset_b.id),
                'original_raw': '{"id": "test"}',
                'original_format': 'JSON'
            },
            format='json'
        )
        
        # Must be 403 or 404 (tenant isolation), NOT 400 (schema validation)
        body = (
            response.data if hasattr(response, "data")
            else response.content
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND],
            f"Tenant isolation should return 403/404, got "
            f"{response.status_code}: {body}",
        )
    
    def test_tenant_cannot_upload_file_for_other_tenant(self):
        """Test that tenant A cannot access files belonging to tenant B.

        Files are scoped to the authenticated user's tenant. Verify that
        tenant B cannot use file IDs from tenant A's namespace.
        """
        from hub.apps.files.models import File, FileStatus

        # Create file belonging to tenant A
        file_a = File.objects.create(
            tenant=self.tenant_a,
            name="secret.csv",
            content_type="text/csv",
            size=100,
            storage_path="tenant-a/secret.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user_a,
            content_sha256="abc123",
        )

        # Tenant B tries to access tenant A's file via dataset creation
        response = self.client_b.post(
            "/api/v1/datasets/",
            {"file_id": str(file_a.id)},
            format="json",
        )

        # Should be rejected — file belongs to tenant A, not tenant B
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND],
            f"Tenant B should NOT access tenant A's file. Got {response.status_code}",
        )
    
    def test_tenant_isolation_in_contracts(self):
        """Test tenant isolation in contracts"""
        # Create contract for tenant A
        contract_a = Contract.objects.create(
            tenant=self.tenant_a,
            asset=self.asset_a,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type='ODCS',
            original_format='JSON',
            original_raw='{"id": "test"}',
            created_by=self.user_a
        )
        
        # Tenant B tries to access tenant A's contract
        response = self.client_b.get(f'/api/v1/contracts/{contract_a.id}/')

        # Should return 403 or 404
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_tenant_isolation_in_files(self):
        """Test tenant isolation in files"""
        # Create file for tenant A
        file_a = File.objects.create(
            tenant=self.tenant_a,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            storage_path="test/path",
            status=FileStatus.ACTIVE,
            created_by=self.user_a
        )

        # Tenant B tries to access tenant A's file
        response = self.client_b.get(f'/api/v1/files/{file_a.id}/')

        # Should return 403 or 404
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

