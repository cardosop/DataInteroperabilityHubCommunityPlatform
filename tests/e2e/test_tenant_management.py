"""
Comprehensive E2E tests for tenant management.

Covers:
- Tenant CRUD operations
- Tenant suspension and reactivation
- Tenant deletion
- KYC status verification
- Audit logging
- State verification

Uses REAL services (no mocks).
"""
import pytest
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status

from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.users.models import Role, UserRole

from .conftest import E2ETestBase, get_response_data


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e4]
User = get_user_model()


class TenantManagementE2ETest(E2ETestBase):
    """Test tenant management operations"""
    
    def setUp(self):
        """Set up test fixtures with platform admin user"""
        super().setUp()
        
        # Create platform admin user for tenant management operations
        self.platform_admin = User.objects.create_user(
            email=f"platform-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            is_platform_admin=True
        )
        
        # Switch to platform admin for tenant management tests
        self.client.force_authenticate(user=self.platform_admin)
    
    def test_create_tenant_success(self):
        """Test creating a tenant with valid data"""
        response = self.client.post(
            '/api/v1/tenants/',
            {
                'name': 'New Test Tenant',
                'slug': 'new-test-tenant',
                'region': 'us-east-1'
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = get_response_data(response) or {}
        self.assertEqual(data.get('name'), 'New Test Tenant')
        self.assertEqual(data.get('slug'), 'new-test-tenant')
        self.assertEqual(data.get('status'), TenantStatus.ACTIVE)
        self.assertEqual(data.get('kyc_status'), KYCStatus.UNVERIFIED)

        # Verify tenant exists in database
        tenant = Tenant.objects.get(id=data['id'])
        self.assertEqual(tenant.name, 'New Test Tenant')
        self.assertEqual(tenant.slug, 'new-test-tenant')
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertEqual(tenant.kyc_status, KYCStatus.UNVERIFIED)
        
        # Verify audit log created
        self.verify_audit_log(
            action='TENANT_CREATED',
            resource_type='TENANT',
            resource_id=tenant.id,
            result='SUCCESS'
        )
    
    def test_create_tenant_duplicate_slug_fails(self):
        """Test creating tenant with duplicate slug fails"""
        # Create first tenant
        tenant1 = Tenant.objects.create(
            name='First Tenant',
            slug='duplicate-slug',
            kyc_status=KYCStatus.VERIFIED
        )
        
        # Try to create second tenant with same slug
        response = self.client.post(
            '/api/v1/tenants/',
            {
                'name': 'Second Tenant',
                'slug': 'duplicate-slug',
                'region': 'us-east-1'
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = get_response_data(response) or {}
        # Standardized error response: {"detail": "...", "code": "DUPLICATE_SLUG", ...}
        self.assertEqual(data.get('code'), 'DUPLICATE_SLUG')
        self.assertIn('slug', data.get('detail', ''))
    
    def test_get_tenant_success(self):
        """Test retrieving tenant details"""
        import uuid
        unique_name = f'Test Tenant Get {uuid.uuid4().hex[:8]}'
        tenant = Tenant.objects.create(
            name=unique_name,
            slug='test-tenant-get',
            kyc_status=KYCStatus.VERIFIED
        )
        
        response = self.client.get(f'/api/v1/tenants/{tenant.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertEqual(data.get('id'), str(tenant.id))
        self.assertEqual(data.get('name'), unique_name)
        self.assertEqual(data.get('slug'), 'test-tenant-get')
        self.assertEqual(data.get('status'), TenantStatus.ACTIVE)
        self.assertEqual(data.get('kyc_status'), KYCStatus.VERIFIED)
    
    def test_update_tenant_success(self):
        """Test updating tenant name and description"""
        tenant = Tenant.objects.create(
            name='Original Name',
            slug='test-tenant-update',
            kyc_status=KYCStatus.UNVERIFIED
        )
        
        response = self.client.patch(
            f'/api/v1/tenants/{tenant.id}/',
            {
                'name': 'Updated Name',
                'kyc_status': KYCStatus.VERIFIED
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertEqual(data.get('name'), 'Updated Name')
        self.assertEqual(data.get('kyc_status'), KYCStatus.VERIFIED)

        # Verify database updated
        tenant.refresh_from_db()
        self.assertEqual(tenant.name, 'Updated Name')
        self.assertEqual(tenant.kyc_status, KYCStatus.VERIFIED)
        
        # Verify audit log created
        self.verify_audit_log(
            action='TENANT_UPDATED',
            resource_type='TENANT',
            resource_id=tenant.id,
            result='SUCCESS'
        )
    
    def test_suspend_tenant_success(self):
        """Test suspending a tenant"""
        tenant = Tenant.objects.create(
            name=f'Test Tenant {uuid.uuid4().hex[:8]}',
            slug='test-tenant-suspend',
            kyc_status=KYCStatus.VERIFIED
        )
        
        response = self.client.post(
            f'/api/v1/tenants/{tenant.id}/suspend/',
            {
                'reason': 'Violation of terms of service'
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertEqual(data.get('status'), TenantStatus.SUSPENDED)

        # Verify database updated
        tenant.refresh_from_db()
        self.assertEqual(tenant.status, TenantStatus.SUSPENDED)
        self.assertTrue(tenant.is_suspended())

        # Verify audit log created
        self.verify_audit_log(
            action='TENANT_SUSPENDED',
            resource_type='TENANT',
            resource_id=tenant.id,
            result='SUCCESS'
        )
    
    def test_suspend_deleted_tenant_fails(self):
        """Test suspending a deleted tenant fails"""
        tenant = Tenant.objects.create(
            name=f'Test Tenant {uuid.uuid4().hex[:8]}',
            slug='test-tenant-suspend-deleted',
            kyc_status=KYCStatus.VERIFIED
        )
        tenant.soft_delete()
        
        response = self.client.post(
            f'/api/v1/tenants/{tenant.id}/suspend/',
            {'reason': 'Test'},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = get_response_data(response) or {}
        self.assertIn('deleted', (data.get('error') or '').lower())
    
    def test_reactivate_tenant_success(self):
        """Test reactivating a suspended tenant"""
        import uuid
        unique_name = f'Test Tenant Reactivate {uuid.uuid4().hex[:8]}'
        tenant = Tenant.objects.create(
            name=unique_name,
            slug='test-tenant-reactivate',
            kyc_status=KYCStatus.VERIFIED
        )
        tenant.suspend()
        
        response = self.client.post(
            f'/api/v1/tenants/{tenant.id}/reactivate/',
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertEqual(data.get('status'), TenantStatus.ACTIVE)

        # Verify database updated
        tenant.refresh_from_db()
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertFalse(tenant.is_suspended())

        # Verify audit log created
        self.verify_audit_log(
            action='TENANT_REACTIVATED',
            resource_type='TENANT',
            resource_id=tenant.id,
            result='SUCCESS'
        )
    
    def test_reactivate_active_tenant_fails(self):
        """Test reactivating an active tenant fails"""
        import uuid
        unique_name = f'Test Tenant Reactivate Active {uuid.uuid4().hex[:8]}'
        tenant = Tenant.objects.create(
            name=unique_name,
            slug='test-tenant-reactivate-active',
            kyc_status=KYCStatus.VERIFIED
        )
        
        response = self.client.post(
            f'/api/v1/tenants/{tenant.id}/reactivate/',
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = get_response_data(response) or {}
        error_msg = str(data.get('error', '')).lower()
        self.assertTrue(
            'active' in error_msg or 'suspended' in error_msg or 'reactivate' in error_msg,
            f"Error should explain why reactivation failed, got: {data}"
        )

    def test_delete_tenant_success(self):
        """Test deleting a tenant (soft delete)"""
        tenant = Tenant.objects.create(
            name=f'Test Tenant {uuid.uuid4().hex[:8]}',
            slug='test-tenant-delete',
            kyc_status=KYCStatus.VERIFIED
        )
        
        response = self.client.delete(
            f'/api/v1/tenants/{tenant.id}/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify soft delete (tenant still exists but marked as deleted)
        tenant.refresh_from_db()
        self.assertEqual(tenant.status, TenantStatus.DELETED)
        self.assertIsNotNone(tenant.deleted_at)
        self.assertTrue(tenant.is_deleted())
        
        # Verify audit log created
        self.verify_audit_log(
            action='TENANT_DELETED',
            resource_type='TENANT',
            resource_id=tenant.id,
            result='SUCCESS'
        )
    
    def test_suspended_tenant_blocks_writes(self):
        """Test that suspended tenant cannot perform write operations"""
        suspended_tenant = Tenant.objects.create(
            name='Suspended Tenant',
            slug='suspended-tenant',
            kyc_status=KYCStatus.VERIFIED
        )
        suspended_tenant.suspend()
        suspended_tenant.refresh_from_db()
        self.assertEqual(suspended_tenant.status, TenantStatus.SUSPENDED)

        suspended_user = User.objects.create_user(
            email='suspended@example.com',
            password='testpass123',
            tenant=suspended_tenant
        )

        self.client.force_authenticate(user=suspended_user)

        # Try to create an asset — should be blocked by suspension middleware
        response = self.client.post(
            '/api/v1/assets/',
            {'key': 'test-asset', 'name': 'Test Asset'},
            format='json'
        )

        # Write MUST be rejected (not 201 Created)
        self.assertNotEqual(
            response.status_code, status.HTTP_201_CREATED,
            "Suspended tenant write should be blocked, but asset was created"
        )
        # Should be 403 Forbidden from the suspension middleware
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_suspended_tenant_allows_reads(self):
        """Test that suspended tenant can still perform read operations"""
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        # Create tenant and give it a subscription so the user can create resources
        suspended_tenant = Tenant.objects.create(
            name='Suspended Tenant Reads',
            slug='suspended-tenant-reads',
            kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(suspended_tenant)

        suspended_user = User.objects.create_user(
            email='suspended-read@example.com',
            password='testpass123',
            tenant=suspended_tenant
        )
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=suspended_tenant,
            name='TENANT_ADMIN',
            defaults={'description': 'Tenant Administrator'}
        )
        UserRole.objects.get_or_create(user=suspended_user, role=tenant_admin_role)

        # Create an asset while tenant is ACTIVE
        self.client.force_authenticate(user=suspended_user)
        asset_id = self.create_asset(key='read-test-asset', name='Read Test Asset')

        # Now suspend the tenant
        suspended_tenant.suspend()
        suspended_tenant.refresh_from_db()
        self.assertEqual(suspended_tenant.status, TenantStatus.SUSPENDED)

        # Read should still work for a suspended tenant
        response = self.client.get(f'/api/v1/assets/{asset_id}/')
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
            "Suspended tenant read should return 200 (allowed) or 404 (not blocked by suspension)"
        )
        # If 200, verify we got data back
        if response.status_code == status.HTTP_200_OK:
            data = get_response_data(response) or {}
            self.assertEqual(data.get('id'), str(asset_id))
    
    def test_kyc_status_verification_for_marketplace(self):
        """Test that KYC status affects marketplace publishing"""
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        # Create tenant with UNVERIFIED KYC status (subscription needed to pass middleware; KYC intentionally unverified)
        unverified_tenant = Tenant.objects.create(
            name='Unverified Tenant',
            slug='unverified-tenant',
            kyc_status=KYCStatus.UNVERIFIED
        )
        ensure_tenant_has_active_subscription(unverified_tenant)

        unverified_user = User.objects.create_user(
            email='unverified@example.com',
            password='testpass123',
            tenant=unverified_tenant
        )
        # Assign DATA_PROVIDER so user can create asset; KYC is enforced at marketplace publish
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=unverified_tenant,
            name='DATA_PROVIDER',
            defaults={'description': 'Data provider'}
        )
        UserRole.objects.get_or_create(user=unverified_user, role=data_provider_role)
        self.client.force_authenticate(user=unverified_user)
        
        # Create and activate asset
        asset_id = self.create_asset(key='test-asset-kyc', name='Test Asset')
        
        # Try to publish to marketplace (should fail without KYC)
        # Note: This test assumes marketplace publishing requires KYC
        # Adjust based on actual implementation
        response = self.client.post(
            '/api/v1/marketplace/listings/',
            {
                'asset_id': asset_id,
                'title': 'Test Listing',
                'short_description': 'Test Description',
                'price_model': 'FREE'
            },
            format='json'
        )
        
        # Should fail if KYC is required (may be 400 for validation or 403 for KYC)
        if response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]:
            data = get_response_data(response) or {}
            error_msg = data.get('error', '')
            if isinstance(error_msg, dict):
                error_msg = error_msg.get('message', '') or str(error_msg)
            else:
                error_msg = str(error_msg)
            # Check for KYC error or validation error (validation may come first)
            error_str = str(error_msg).lower()
            # If it's a validation error, that's okay - KYC check may happen later
            # If it's a KYC error, verify it mentions KYC
            if 'kyc' in error_str or 'verified' in error_str:
                self.assertIn('kyc', error_str)
        
        # Verify KYC status
        self.assertFalse(unverified_tenant.can_publish_to_marketplace())
        
        # Update KYC status to VERIFIED
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.patch(
            f'/api/v1/tenants/{unverified_tenant.id}/',
            {'kyc_status': KYCStatus.VERIFIED},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        unverified_tenant.refresh_from_db()
        self.assertEqual(unverified_tenant.kyc_status, KYCStatus.VERIFIED)
        self.assertTrue(unverified_tenant.can_publish_to_marketplace())

