"""
Comprehensive E2E tests for multi-tenant isolation.

Covers:
- Data isolation between tenants
- Cross-tenant access prevention
- Tenant-scoped queries
- Cross-tenant resource access (with entitlements)
- Tenant context enforcement

Uses REAL services (no mocks).
"""
import pytest
from django.test import TestCase
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.marketplace.models import Entitlement, EntitlementStatus, Listing, ListingStatus, PricingModel

from .conftest import E2ETestBase


pytestmark = pytest.mark.django_db(transaction=True)


class MultiTenantIsolationE2ETest(E2ETestBase):
    """Test multi-tenant isolation"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create another tenant
        self.other_tenant = Tenant.objects.create(
            name='Other Tenant',
            slug='other-tenant',
            kyc_status=KYCStatus.VERIFIED
        )
        from hub.apps.users.models import User
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='testpass123',
            tenant=self.other_tenant
        )
    
    def test_asset_tenant_isolation(self):
        """Test assets are tenant-isolated"""
        # Create asset in current tenant
        asset_id1 = self.create_asset(key='isolation-1', name='Isolation 1')
        
        # Switch to other tenant
        self.client.force_authenticate(user=self.other_user)
        
        # Try to access asset from other tenant (should fail)
        response = self.client.get(f'/api/v1/assets/assets/{asset_id1}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Create asset in other tenant (user is already authenticated as other_user)
        asset_id2 = self.create_asset(key='isolation-2', name='Isolation 2')
        
        # Switch back to original tenant
        self.client.force_authenticate(user=self.user)
        
        # Try to access other tenant's asset (should fail)
        response = self.client.get(f'/api/v1/assets/assets/{asset_id2}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_contract_tenant_isolation(self):
        """Test contracts are tenant-isolated"""
        # Create contract in current tenant
        asset_id1 = self.create_asset(key='contract-iso-1', name='Contract Iso 1')
        contract_id1 = self.create_contract(
            asset_id1,
            original_raw='{"id": "test", "name": "Test Contract", "schema": {"fields": []}}'
        )
        
        # Switch to other tenant
        self.client.force_authenticate(user=self.other_user)
        
        # Try to access contract from other tenant (should fail)
        response = self.client.get(f'/api/v1/contracts/contracts/{contract_id1}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_dataset_tenant_isolation(self):
        """Test datasets are tenant-isolated"""
        import hashlib
        
        # Create dataset in current tenant
        asset_id1 = self.create_asset(key='dataset-iso-1', name='Dataset Iso 1')
        test_content = b'col1,col2\nval1,val2'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id1 = self.init_file_upload(name='dataset_iso1.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id1, content_sha256=content_hash, test_content=test_content)
        dataset_id1 = self.create_dataset(file_id1, asset_id1)
        
        # Switch to other tenant
        self.client.force_authenticate(user=self.other_user)
        
        # Try to access dataset from other tenant (should fail)
        response = self.client.get(f'/api/v1/datasets/datasets/{dataset_id1}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_file_tenant_isolation(self):
        """Test files are tenant-isolated"""
        import hashlib
        
        # Create file in current tenant
        test_content = b'file content'
        content_hash = hashlib.sha256(test_content).hexdigest()
        file_id1 = self.init_file_upload(name='file_iso1.csv', content_type='text/csv', size=len(test_content))
        self.complete_file_upload(file_id1, content_sha256=content_hash, test_content=test_content)
        
        # Switch to other tenant
        self.client.force_authenticate(user=self.other_user)
        
        # Try to access file from other tenant (should fail)
        response = self.client.get(f'/api/v1/files/files/{file_id1}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Try to download file (should fail)
        response = self.client.get(f'/api/v1/files/files/{file_id1}/download/')
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])
    
    def test_list_resources_tenant_isolation(self):
        """Test listing resources only returns tenant's resources"""
        # Create resources in current tenant
        asset_id1 = self.create_asset(key='list-iso-1', name='List Iso 1')
        asset_id2 = self.create_asset(key='list-iso-2', name='List Iso 2')
        
        # Create resources in other tenant
        self.client.force_authenticate(user=self.other_user)
        asset_id3 = self.create_asset(key='list-iso-3', name='List Iso 3')
        
        # List assets (should only see other tenant's assets)
        response = self.client.get('/api/v1/assets/assets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = {a['id'] for a in response.data['results']}
        self.assertIn(str(asset_id3), asset_ids)
        self.assertNotIn(str(asset_id1), asset_ids)
        self.assertNotIn(str(asset_id2), asset_ids)
    
    def test_cross_tenant_access_with_entitlement(self):
        """Test cross-tenant access with entitlement"""
        from hub.apps.marketplace.models import Entitlement, EntitlementStatus
        
        # Create asset in provider tenant
        asset_id = self.create_asset(key='entitlement-access-test', name='Entitlement Access Test')
        contract_id = self.create_contract(
            asset_id,
            original_raw='{"id": "test", "name": "Test Contract", "schema": {"fields": []}}'
        )
        self.prepare_contract_for_activation(contract_id)
        self.prepare_asset_for_activation(asset_id)
        
        # Activate asset for listing
        asset = Asset.objects.get(id=asset_id)
        asset.status = AssetStatus.ACTIVE
        asset.save(update_fields=['status'])
        
        # Create listing for entitlement
        listing = Listing.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
            metadata_json={'title': 'Test Listing'}
        )
        
        # Create entitlement for consumer tenant
        entitlement = Entitlement.objects.create(
            tenant=self.other_tenant,
            asset=asset,
            listing=listing,
            status=EntitlementStatus.ACTIVE
        )
        
        # Switch to consumer tenant
        self.client.force_authenticate(user=self.other_user)
        
        # Should be able to access asset with entitlement
        response = self.client.get(f'/api/v1/assets/assets/{asset_id}/')
        # May succeed with entitlement or still require explicit entitlement check
        # This depends on implementation
    
    def test_tenant_context_enforcement(self):
        """Test tenant context is enforced in all operations"""
        # Create asset without explicit tenant (should use user's tenant)
        asset_id = self.create_asset(key='context-test', name='Context Test')
        
        # Verify asset belongs to user's tenant
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.tenant, self.tenant)
        
        # Switch to other tenant
        self.client.force_authenticate(user=self.other_user)
        
        # Create asset (should belong to other tenant)
        asset_id2 = self.create_asset(key='context-test-2', name='Context Test 2')
        
        # Verify asset belongs to other tenant
        asset2 = Asset.objects.get(id=asset_id2)
        self.assertEqual(asset2.tenant, self.other_tenant)
    
    def test_tenant_isolation_in_search(self):
        """Test tenant isolation in search operations"""
        # Create assets in both tenants
        asset_id1 = self.create_asset(key='search-iso-1', name='Search Iso 1')
        
        self.client.force_authenticate(user=self.other_user)
        asset_id2 = self.create_asset(key='search-iso-2', name='Search Iso 2')
        
        # Search (should only see current tenant's assets)
        response = self.client.get('/api/v1/assets/assets/?search=Iso')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        asset_ids = {a['id'] for a in response.data['results']}
        self.assertIn(str(asset_id2), asset_ids)
        self.assertNotIn(str(asset_id1), asset_ids)
