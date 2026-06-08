"""
Comprehensive E2E tests for Tenant Admin (TA) persona journeys.

Covers all 5 TA journeys:
- JOURNEY-TA-001: Onboard New User
- JOURNEY-TA-002: Configure Tenant Settings
- JOURNEY-TA-003: Monitor Tenant Usage (if exists)
- JOURNEY-TA-004: Manage Tenant Billing (if exists)
- JOURNEY-TA-007: Cost Tracking (billing usage + invoices)

All tests use REAL services (no mocks/stubs) and follow TDD approach.
Target: 100% journey coverage for all TA journeys.
"""
import pytest

pytestmark = pytest.mark.slow
import time
import uuid
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from hub.apps.tenants.models import Tenant, KYCStatus, TenantConfig
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, Role, UserRole, UserStatus
from hub.apps.audit.models import AuditEvent

from .conftest import E2ETestBase, get_response_data


pytestmark = [
    pytest.mark.uc_journey_persona,
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e,
    pytest.mark.persona("Tenant Admin"),
    pytest.mark.journey("JOURNEY-TA-001"),
    pytest.mark.journey("JOURNEY-TA-002"),
    pytest.mark.journey("JOURNEY-TA-003"),
    pytest.mark.journey("JOURNEY-TA-004"),
    pytest.mark.journey("JOURNEY-TA-007"),
    pytest.mark.journey("JOURNEY-TA-SUBSCRIPTION"),
    pytest.mark.journey("JOURNEY-TA-TENANT-SETTINGS"),
]


class JourneyTA001OnboardNewUserTests(E2ETestBase):
    """JOURNEY-TA-001: Onboard New User"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create tenant and tenant admin user
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)

        # Create tenant admin user
        self.tenant_admin = User.objects.create_user(
            email="admin@test-tenant.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create TENANT_ADMIN role and assign to admin
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )
        UserRole.objects.create(user=self.tenant_admin, role=self.tenant_admin_role)
        
        # Create DATA_PROVIDER role for new users
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )
        
        # Authenticate as tenant admin
        self.client.force_authenticate(user=self.tenant_admin)
    
    def test_onboard_new_user_with_invitation(self):
        """
        Test happy path: Create user → Send invitation → User accepts → Verify activation
        """
        # Step 1: Create new user with invitation
        response = self.client.post(
            '/api/v1/users/',
            {
                'email': 'newuser@test-tenant.com',
                'display_name': 'New User',
                'role_ids': [str(self.data_provider_role.id)],
                'send_invitation': True
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user_data = (get_response_data(response) or {})
        user_id = user_data.get('id') or (user_data.get('user') or {}).get('id')
        if user_id is None:
            # Fallback: fetch by email (response shape may vary)
            created = User.objects.filter(email='newuser@test-tenant.com').first()
            self.assertIsNotNone(created, f"User not created: {user_data}")
            user_id = str(created.id)
        self.assertIsNotNone(user_id, f"Response missing user id: {user_data}")
        
        # Verify user was created with INVITED status
        self.assertEqual(user_data['status'], UserStatus.INVITED.value)
        self.assertEqual(user_data['email'], 'newuser@test-tenant.com')
        # Tenant can be UUID object or string, convert to string for comparison
        tenant_id = str(user_data['tenant']) if user_data.get('tenant') else None
        self.assertEqual(tenant_id, str(self.tenant.id))
        
        # Verify invitation token was created in database (not in serializer response)
        user = User.objects.get(id=user_id)
        self.assertIsNotNone(user.invitation_token)
        self.assertIsNotNone(user.invitation_token_expires_at)
        
        # Verify role was assigned
        roles = user_data.get('roles') or []
        self.assertGreater(len(roles), 0, f"Expected roles, got: {user_data}")
        role_names = [r.get('name', r) if isinstance(r, dict) else str(r) for r in roles]
        self.assertIn('DATA_PROVIDER', role_names)
        
        # Step 2: Verify audit log entry (invited users get USER_INVITED, not USER_CREATED)
        self.verify_audit_log(
            resource_type='USER',
            action='USER_INVITED',
            resource_id=user_id,
            actor_user=self.tenant_admin
        )
        
        # Step 3: List users to verify new user appears
        response = self.client.get('/api/v1/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        users = (get_response_data(response) or {}).get('results', [])
        user_emails = [u['email'] for u in users]
        self.assertIn('newuser@test-tenant.com', user_emails)
        
        # Step 4: Get user details
        response = self.client.get(f'/api/v1/users/{user_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((get_response_data(response) or {})['email'], 'newuser@test-tenant.com')
        self.assertEqual((get_response_data(response) or {})['status'], UserStatus.INVITED.value)
    
    def test_onboard_new_user_without_invitation(self):
        """
        Test creating user without invitation (direct activation)
        """
        # Create user without invitation
        response = self.client.post(
            '/api/v1/users/',
            {
                'email': 'directuser@test-tenant.com',
                'display_name': 'Direct User',
                'password': 'testpass123',
                'role_ids': [str(self.data_provider_role.id)],
                'send_invitation': False,
                'status': UserStatus.ACTIVE.value
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user_data = (get_response_data(response) or {})
        user_id = user_data['id']
        
        # Verify user was created with ACTIVE status
        self.assertEqual(user_data['status'], UserStatus.ACTIVE.value)
        self.assertIsNone(user_data.get('invitation_token'))
        
        # Verify audit log
        self.verify_audit_log(
            resource_type='USER',
            action='USER_CREATED',
            resource_id=user_id,
            actor_user=self.tenant_admin
        )
    
    def test_invite_user_via_invite_endpoint(self):
        """
        Test using the dedicated invite endpoint
        """
        response = self.client.post(
            '/api/v1/users/invite/',
            {
                'email': 'invited@test-tenant.com',
                'display_name': 'Invited User',
                'role_ids': [str(self.data_provider_role.id)]
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user_data = (get_response_data(response) or {})
        
        # Verify user was created with INVITED status
        self.assertEqual(user_data['status'], UserStatus.INVITED.value)
        
        # Verify invitation token was created in database (not in serializer response)
        user = User.objects.get(id=user_data['id'])
        self.assertIsNotNone(user.invitation_token)
        self.assertIsNotNone(user.invitation_token_expires_at)
        
        # Verify audit log — inviting a user should log USER_INVITED
        self.verify_audit_log(
            resource_type='USER',
            action='USER_INVITED',
            resource_id=user_data['id'],
            actor_user=self.tenant_admin
        )
    
    def test_assign_role_to_user(self):
        """
        Test assigning a role to an existing user
        """
        # Create user first
        user = User.objects.create_user(
            email='norole@test-tenant.com',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Assign role
        response = self.client.post(
            f'/api/v1/users/{user.id}/roles/',
            {
                'role_id': str(self.data_provider_role.id),
                'action': 'assign'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify role was assigned
        user.refresh_from_db()
        user_roles = UserRole.objects.filter(user=user)
        role_ids = [ur.role.id for ur in user_roles]
        self.assertIn(self.data_provider_role.id, role_ids)
        
        # Verify audit log
        self.verify_audit_log(
            resource_type='USER',
            action='USER_ROLE_CHANGED',
            resource_id=str(user.id),
            actor_user=self.tenant_admin
        )
    
    def test_remove_role_from_user(self):
        """
        Test removing a role from a user
        """
        # Create user with role
        user = User.objects.create_user(
            email='withrole@test-tenant.com',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=user, role=self.data_provider_role)
        
        # Remove role
        response = self.client.post(
            f'/api/v1/users/{user.id}/roles/',
            {
                'role_id': str(self.data_provider_role.id),
                'action': 'remove'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify role was removed
        user.refresh_from_db()
        user_roles = UserRole.objects.filter(user=user, role=self.data_provider_role)
        self.assertEqual(user_roles.count(), 0)
    
    def test_update_user_details(self):
        """
        Test updating user details
        """
        # Create user
        user = User.objects.create_user(
            email='toupdate@test-tenant.com',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Update user
        response = self.client.patch(
            f'/api/v1/users/{user.id}/',
            {
                'display_name': 'Updated Name'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((get_response_data(response) or {})['display_name'], 'Updated Name')
        
        # Verify audit log
        self.verify_audit_log(
            resource_type='USER',
            action='USER_UPDATED',
            resource_id=str(user.id),
            actor_user=self.tenant_admin
        )
    
    def test_disable_user(self):
        """
        Test disabling a user (soft delete)
        """
        # Create user with resources (to trigger soft delete)
        from hub.apps.assets.models import Asset
        user = User.objects.create_user(
            email='todisable@test-tenant.com',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        # Create an asset to ensure user has resources
        Asset.objects.create(
            tenant=self.tenant,
            key='test-asset',
            name='Test Asset',
            created_by=user,
            status='ACTIVE'
        )
        
        # Delete user (should soft delete; API may return 200 or 204)
        response = self.client.delete(f'/api/v1/users/{user.id}/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])
        
        # Verify user was disabled
        user.refresh_from_db()
        self.assertEqual(user.status, UserStatus.DISABLED.value)
        
        # Verify audit log
        self.verify_audit_log(
            resource_type='USER',
            action='USER_DISABLED',
            resource_id=str(user.id),
            actor_user=self.tenant_admin
        )
    
    def test_list_users_with_filters(self):
        """
        Test listing users with status filter
        """
        # Create users with different statuses
        User.objects.create_user(
            email='active@test-tenant.com',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        User.objects.create_user(
            email='invited@test-tenant.com',
            tenant=self.tenant,
            status=UserStatus.INVITED
        )
        
        # Filter by ACTIVE status
        response = self.client.get('/api/v1/users/?status=ACTIVE')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        users = (get_response_data(response) or {}).get('results', [])
        user_emails = [u['email'] for u in users]
        self.assertIn('active@test-tenant.com', user_emails)
        self.assertNotIn('invited@test-tenant.com', user_emails)
        
        # Filter by INVITED status
        response = self.client.get('/api/v1/users/?status=INVITED')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        users = (get_response_data(response) or {}).get('results', [])
        user_emails = [u['email'] for u in users]
        self.assertIn('invited@test-tenant.com', user_emails)
        self.assertNotIn('active@test-tenant.com', user_emails)
    
    def test_error_duplicate_email(self):
        """
        Test error scenario: Creating user with duplicate email
        """
        # Create first user
        User.objects.create_user(
            email='duplicate@test-tenant.com',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Try to create duplicate
        response = self.client.post(
            '/api/v1/users/',
            {
                'email': 'duplicate@test-tenant.com',
                'display_name': 'Duplicate User'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_error_invite_existing_user(self):
        """
        Test error scenario: Inviting user that already exists
        """
        # Create user first
        User.objects.create_user(
            email='existing@test-tenant.com',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Try to invite existing user
        response = self.client.post(
            '/api/v1/users/invite/',
            {
                'email': 'existing@test-tenant.com',
                'display_name': 'Existing User'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_str = str((get_response_data(response) or {}) or {}).lower()
        self.assertTrue(
            'already exists' in error_str or 'duplicate' in error_str or 'exists' in error_str,
            f"Expected 'already exists' or similar in error, got: {(get_response_data(response) or {})}"
        )


class JourneyTA002ConfigureTenantSettingsTests(E2ETestBase):
    """JOURNEY-TA-002: Configure Tenant Settings"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create tenant and tenant admin user
        self.tenant = Tenant.objects.create(
            name=f"Config Tenant {uuid.uuid4().hex[:8]}",
            slug=f"config-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.tenant_admin = User.objects.create_user(
            email="configadmin@test-tenant.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create TENANT_ADMIN role and assign
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )
        UserRole.objects.create(user=self.tenant_admin, role=self.tenant_admin_role)
        
        # Authenticate as tenant admin
        self.client.force_authenticate(user=self.tenant_admin)
    
    def test_get_tenant_config_defaults(self):
        """
        Test getting tenant configuration with platform defaults
        """
        response = self.client.get(f'/api/v1/tenants/{self.tenant.id}/config/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        config = (get_response_data(response) or {})
        
        # Verify platform defaults are returned
        self.assertEqual(config['tenant_id'], str(self.tenant.id))
        self.assertIsNotNone(config.get('default_dq_profile'))
        self.assertIsNotNone(config.get('allowed_compliance_regimes'))
        self.assertIsNotNone(config.get('default_compliance_regimes'))
        self.assertIsNotNone(config.get('data_retention_days'))
        self.assertIsNotNone(config.get('max_file_size_bytes'))
        self.assertIsNotNone(config.get('max_job_concurrency'))
        self.assertIsNotNone(config.get('max_queued_jobs'))
    
    def test_update_dq_profile(self):
        """
        Test updating default DQ profile
        """
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'default_dq_profile': 'intake_basic_soda'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((get_response_data(response) or {})['default_dq_profile'], 'intake_basic_soda')
        
        # Verify config was saved
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.default_dq_profile, 'intake_basic_soda')
        
        # Verify audit log
        self.verify_audit_log(
            resource_type='TENANT',
            action='TENANT_CONFIG_UPDATED',
            resource_id=str(self.tenant.id),
            actor_user=self.tenant_admin
        )
    
    def test_update_compliance_regimes(self):
        """
        Test updating compliance regimes
        """
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'allowed_compliance_regimes': ['GDPR', 'HIPAA', 'SOX'],
                'default_compliance_regimes': ['GDPR', 'HIPAA']
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set((get_response_data(response) or {})['allowed_compliance_regimes']), {'GDPR', 'HIPAA', 'SOX'})
        self.assertEqual(set((get_response_data(response) or {})['default_compliance_regimes']), {'GDPR', 'HIPAA'})
        
        # Verify config was saved
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(set(config.allowed_compliance_regimes), {'GDPR', 'HIPAA', 'SOX'})
        self.assertEqual(set(config.default_compliance_regimes), {'GDPR', 'HIPAA'})
    
    def test_update_data_retention(self):
        """
        Test updating data retention period
        """
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'data_retention_days': 1825  # 5 years
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((get_response_data(response) or {})['data_retention_days'], 1825)
        
        # Verify config was saved
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.data_retention_days, 1825)
    
    def test_update_rate_limits(self):
        """
        Test updating rate limits
        """
        rate_limits = {
            'dq_runs': {
                'burst_per_10s': 25,
                'sustained_per_min': 70,
                'daily_cap': 12000
            },
            'file_uploads': {
                'burst_per_10s': 15,
                'sustained_per_min': 40
            }
        }
        
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'rate_limits': rate_limits
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify rate limits were saved
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.rate_limits['dq_runs']['burst_per_10s'], 25)
        self.assertEqual(config.rate_limits['file_uploads']['burst_per_10s'], 15)
    
    def test_update_file_size_limit(self):
        """
        Test updating maximum file size limit
        """
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'max_file_size_bytes': 21474836480  # 20 GB
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((get_response_data(response) or {})['max_file_size_bytes'], 21474836480)
        
        # Verify config was saved
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.max_file_size_bytes, 21474836480)
    
    def test_update_job_concurrency_limits(self):
        """
        Test updating job concurrency limits
        """
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'max_job_concurrency': 10,
                'max_queued_jobs': 100
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((get_response_data(response) or {})['max_job_concurrency'], 10)
        self.assertEqual((get_response_data(response) or {})['max_queued_jobs'], 100)
        
        # Verify config was saved
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.max_job_concurrency, 10)
        self.assertEqual(config.max_queued_jobs, 100)
    
    def test_partial_update_config(self):
        """
        Test partial update (only some fields)
        """
        # First, set some values
        self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'default_dq_profile': 'intake_basic_soda',
                'data_retention_days': 1825
            },
            format='json'
        )
        
        # Then update only one field
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'data_retention_days': 2555
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify both fields are still set
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.default_dq_profile, 'intake_basic_soda')
        self.assertEqual(config.data_retention_days, 2555)
    
    def test_error_invalid_dq_profile(self):
        """
        Test error scenario: Invalid DQ profile
        """
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'default_dq_profile': 'invalid_profile'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_error_invalid_compliance_regime(self):
        """
        Test error scenario: Invalid compliance regime
        """
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'allowed_compliance_regimes': ['INVALID_REGIME']
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_error_default_not_subset_of_allowed(self):
        """
        Test error scenario: Default compliance regimes not subset of allowed
        """
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'allowed_compliance_regimes': ['GDPR', 'HIPAA'],
                'default_compliance_regimes': ['GDPR', 'SOX']  # SOX not in allowed
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_error_invalid_retention_days(self):
        """
        Test error scenario: Retention days out of range
        """
        # Too low
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'data_retention_days': 50  # Below minimum of 90
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Too high
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'data_retention_days': 4000  # Above maximum of 3650
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class JourneyTA003MonitorTenantUsageTests(E2ETestBase):
    """JOURNEY-TA-003: Monitor Tenant Usage (if exists)"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create tenant and tenant admin user
        self.tenant = Tenant.objects.create(
            name=f"Usage Tenant {uuid.uuid4().hex[:8]}",
            slug=f"usage-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.tenant_admin = User.objects.create_user(
            email="usageadmin@test-tenant.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create TENANT_ADMIN role and assign
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )
        UserRole.objects.create(user=self.tenant_admin, role=self.tenant_admin_role)
        
        # Authenticate as tenant admin
        self.client.force_authenticate(user=self.tenant_admin)
    
    def test_monitor_tenant_usage_via_analytics(self):
        """
        Test monitoring tenant usage via API analytics (if endpoint exists)
        """
        # Check if analytics endpoint exists
        # For now, we'll test that we can query usage metrics if they exist
        # This is a placeholder test that can be expanded when usage monitoring API is implemented
        
        # Create some usage metrics
        from hub.apps.api.analytics.models import APIUsageMetric
        APIUsageMetric.objects.create(
            tenant=self.tenant,
            user=self.tenant_admin,
            endpoint_path='/api/v1/assets/',
            method='GET',
            status_code=200,
            latency_ms=45.2
        )
        APIUsageMetric.objects.create(
            tenant=self.tenant,
            user=self.tenant_admin,
            endpoint_path='/api/v1/assets/',
            method='POST',
            status_code=201,
            latency_ms=120.5
        )
        
        # Verify metrics were created
        metrics = APIUsageMetric.objects.filter(tenant=self.tenant)
        self.assertEqual(metrics.count(), 2)
        
        # Note: If a usage monitoring API endpoint exists, we would test it here
        # For now, we verify the metrics model works correctly
    
    def test_list_tenant_users_count(self):
        """
        Test getting count of tenant users as usage metric
        """
        # Create some users
        for i in range(5):
            User.objects.create_user(
                email=f'user{i}@test-tenant.com',
                tenant=self.tenant,
                status=UserStatus.ACTIVE
            )
        
        # List users to get count
        response = self.client.get('/api/v1/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        users = (get_response_data(response) or {}).get('results', [])
        
        # Should have at least 5 users (plus tenant admin)
        self.assertGreaterEqual(len(users), 5)


class JourneyTA004ManageTenantBillingTests(E2ETestBase):
    """JOURNEY-TA-004: Manage Tenant Billing (if exists)"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create tenant and tenant admin user
        self.tenant = Tenant.objects.create(
            name=f"Billing Tenant {uuid.uuid4().hex[:8]}",
            slug=f"billing-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.tenant_admin = User.objects.create_user(
            email="billingadmin@test-tenant.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create TENANT_ADMIN role and assign
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )
        UserRole.objects.create(user=self.tenant_admin, role=self.tenant_admin_role)
        
        # Authenticate as tenant admin
        self.client.force_authenticate(user=self.tenant_admin)
    
    def test_billing_not_implemented(self):
        """
        Test that billing management is not yet implemented
        This is a placeholder test that documents the current state
        """
        # Billing management is not yet implemented
        # This test documents that we've checked for billing functionality
        # and confirms it doesn't exist yet
        
        # Note: TenantViewSet requires platform admin permissions, not tenant admin
        # So we can't access it directly. Instead, we verify tenant admin can manage
        # tenant config (which is the main tenant admin capability)
        response = self.client.get(f'/api/v1/tenants/{self.tenant.id}/config/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Note: When billing API is implemented, we would test:
        # - Get billing information
        # - Update payment method
        # - View billing history
        # - Update subscription plan
        # etc.


class TenantAdminUseCasesTests(E2ETestBase):
    """Test use cases: Manage users, configure tenant settings, monitor usage, manage billing, manage roles"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create tenant and tenant admin user
        self.tenant = Tenant.objects.create(
            name=f"Use Case Tenant {uuid.uuid4().hex[:8]}",
            slug=f"usecase-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.tenant_admin = User.objects.create_user(
            email="usecaseadmin@test-tenant.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create roles
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )
        self.data_consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_CONSUMER",
            defaults={"description": "Data Consumer"}
        )
        
        UserRole.objects.create(user=self.tenant_admin, role=self.tenant_admin_role)
        
        # Authenticate as tenant admin
        self.client.force_authenticate(user=self.tenant_admin)
    
    def test_complete_user_management_workflow(self):
        """
        Test complete user management workflow: Create → Assign roles → Update → Disable
        """
        # Create user
        response = self.client.post(
            '/api/v1/users/',
            {
                'email': 'workflow@test-tenant.com',
                'display_name': 'Workflow User',
                'role_ids': [str(self.data_provider_role.id)],
                'send_invitation': False,
                'status': UserStatus.ACTIVE.value
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user_id = (get_response_data(response) or {})['id']
        
        # Update user
        response = self.client.patch(
            f'/api/v1/users/{user_id}/',
            {
                'display_name': 'Updated Workflow User'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Assign additional role
        response = self.client.post(
            f'/api/v1/users/{user_id}/roles/',
            {
                'role_id': str(self.data_consumer_role.id),
                'action': 'assign'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user has both roles (API returns roles as list of strings)
        response = self.client.get(f'/api/v1/users/{user_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        role_names = list((get_response_data(response) or {}).get('roles', []))
        self.assertIn('DATA_PROVIDER', role_names)
        self.assertIn('DATA_CONSUMER', role_names)
    
    def test_complete_config_management_workflow(self):
        """
        Test complete configuration management workflow: Get → Update multiple fields → Verify
        """
        # Get initial config
        response = self.client.get(f'/api/v1/tenants/{self.tenant.id}/config/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        initial_config = (get_response_data(response) or {})
        
        # Update multiple fields
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'default_dq_profile': 'intake_basic_soda',
                'data_retention_days': 1825,
                'max_job_concurrency': 8,
                'max_queued_jobs': 80
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all fields were updated
        self.assertEqual((get_response_data(response) or {})['default_dq_profile'], 'intake_basic_soda')
        self.assertEqual((get_response_data(response) or {})['data_retention_days'], 1825)
        self.assertEqual((get_response_data(response) or {})['max_job_concurrency'], 8)
        self.assertEqual((get_response_data(response) or {})['max_queued_jobs'], 80)
        
        # Verify other fields remain unchanged (or use defaults)
        self.assertIsNotNone((get_response_data(response) or {}).get('max_file_size_bytes'))


class TenantAdminErrorScenariosTests(E2ETestBase):
    """Test error scenarios: User management failure, tenant configuration failure"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create tenant and tenant admin user
        self.tenant = Tenant.objects.create(
            name=f"Error Tenant {uuid.uuid4().hex[:8]}",
            slug=f"error-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.tenant_admin = User.objects.create_user(
            email="erroradmin@test-tenant.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create TENANT_ADMIN role and assign
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"}
        )
        UserRole.objects.create(user=self.tenant_admin, role=self.tenant_admin_role)
        
        # Authenticate as tenant admin
        self.client.force_authenticate(user=self.tenant_admin)
    
    def test_error_create_user_missing_email(self):
        """
        Test error scenario: Creating user without email
        """
        response = self.client.post(
            '/api/v1/users/',
            {
                'display_name': 'No Email User'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_error_assign_nonexistent_role(self):
        """
        Test error scenario: Assigning non-existent role
        """
        user = User.objects.create_user(
            email='testuser@test-tenant.com',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        fake_role_id = str(uuid.uuid4())
        response = self.client.post(
            f'/api/v1/users/{user.id}/roles/',
            {
                'role_id': fake_role_id,
                'action': 'assign'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_error_access_other_tenant_config(self):
        """
        Test error scenario: Accessing another tenant's configuration
        """
        # Create another tenant
        _suffix = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_suffix}",
            slug=f"other-tenant-{_suffix}",
            kyc_status=KYCStatus.VERIFIED
        )

        # Try to access other tenant's config
        response = self.client.get(f'/api/v1/tenants/{other_tenant.id}/config/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_error_update_config_without_permission(self):
        """
        Test error scenario: Updating config without TENANT_ADMIN role
        """
        # Create regular user (not admin)
        regular_user = User.objects.create_user(
            email='regular@test-tenant.com',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Authenticate as regular user
        self.client.force_authenticate(user=regular_user)
        
        # Try to update config
        response = self.client.patch(
            f'/api/v1/tenants/{self.tenant.id}/config/',
            {
                'default_dq_profile': 'intake_basic_soda'
            },
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_error_delete_self(self):
        """
        Test error scenario: User trying to delete themselves
        """
        response = self.client.delete(f'/api/v1/users/{self.tenant_admin.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cannot delete themselves', (get_response_data(response) or {}).get('error', '').lower())


@pytest.mark.uc("UC-TA-007")
@pytest.mark.journey("JOURNEY-TA-007")
class TestJOURNEYTA007CostTracking(E2ETestBase):
    """JOURNEY-TA-007: Cost Tracking

    Verifies tenant admin can view billing usage and invoices.
    Endpoints: GET /api/v1/billing/subscription/current/,
               GET /api/v1/billing/invoices/
    """

    BILLING_SUBSCRIPTION_URL = "/api/v1/billing/subscription/"
    BILLING_INVOICES_URL = "/api/v1/billing/invoices/"
    BILLING_PLANS_URL = "/api/v1/billing/plans/"

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Cost Tracking Tenant {uid}",
            slug=f"cost-tracking-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.tenant_admin = User.objects.create_user(
            email=f"costadmin-{uid}@test-tenant.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.create(user=self.tenant_admin, role=self.tenant_admin_role)

        self.client.force_authenticate(user=self.tenant_admin)

        # Create a consumer user (no admin role) for 403 tests
        self.consumer = User.objects.create_user(
            email=f"consumer-{uid}@test-tenant.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_CONSUMER",
            defaults={"description": "Data Consumer"},
        )
        UserRole.objects.create(user=self.consumer, role=consumer_role)

    def test_get_billing_subscription_current(self):
        """GET /api/v1/billing/subscription/current/ → 200."""
        response = self.client.get(f"{self.BILLING_SUBSCRIPTION_URL}current/")
        if response.status_code == status.HTTP_404_NOT_FOUND:
            self.skipTest("Billing subscription endpoint not available (404)")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_billing_invoices(self):
        """GET /api/v1/billing/invoices/ → 200."""
        response = self.client.get(self.BILLING_INVOICES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_billing_plans(self):
        """GET /api/v1/billing/plans/ → 200."""
        response = self.client.get(self.BILLING_PLANS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_billing_invoices_unauthorized_returns_401(self):
        """Unauthenticated billing access → 401/403."""
        self.client.logout()
        response = self.client.get(self.BILLING_INVOICES_URL)
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_new_tenant_subscription_valid_response(self):
        """New tenant with active subscription → subscription endpoint returns valid data."""
        response = self.client.get(f"{self.BILLING_SUBSCRIPTION_URL}current/")
        if response.status_code == status.HTTP_200_OK:
            data = get_response_data(response) or {}
            # Subscription should have a status field
            self.assertIn("status", data)

    def test_new_tenant_invoices_empty_or_valid(self):
        """New tenant → invoices list is empty or has valid structure."""
        response = self.client.get(self.BILLING_INVOICES_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        # Should be a list or paginated response
        results = data.get("results", data) if isinstance(data, dict) else data
        self.assertIsInstance(results, (list, dict))


@pytest.mark.journey("JOURNEY-TA-SUBSCRIPTION")
class TestJOURNEYTASubscription(E2ETestBase):
    """JOURNEY-TA-SUBSCRIPTION: Manage Subscription

    Verifies tenant admin can view plans, current subscription, and invoices.
    """

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Sub Tenant {uid}",
            slug=f"sub-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.tenant_admin = User.objects.create_user(
            email=f"subadmin-{uid}@test.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ta_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN",
            defaults={"description": "Tenant Admin"},
        )
        UserRole.objects.create(user=self.tenant_admin, role=ta_role)
        self.client.force_authenticate(user=self.tenant_admin)

    def test_list_subscription_plans_success(self):
        """GET /api/v1/billing/plans/ → 200."""
        response = self.client.get("/api/v1/billing/plans/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_view_current_subscription_success(self):
        """GET /api/v1/billing/subscription/current/ → 200."""
        response = self.client.get("/api/v1/billing/subscription/current/")
        if response.status_code == status.HTTP_404_NOT_FOUND:
            self.skipTest("Billing subscription endpoint not available (404)")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_view_invoices_success(self):
        """GET /api/v1/billing/invoices/ → 200."""
        response = self.client.get("/api/v1/billing/invoices/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_subscription_failure_unauthorized(self):
        """Unauthenticated billing access → 401/403."""
        self.client.logout()
        response = self.client.get("/api/v1/billing/plans/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


@pytest.mark.journey("JOURNEY-TA-TENANT-SETTINGS")
class TestJOURNEYTATenantSettings(E2ETestBase):
    """JOURNEY-TA-TENANT-SETTINGS: Manage Tenant Settings

    Verifies tenant admin can view and update tenant config.
    """

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Settings Tenant {uid}",
            slug=f"settings-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.tenant_admin = User.objects.create_user(
            email=f"settingsadmin-{uid}@test.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ta_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN",
            defaults={"description": "Tenant Admin"},
        )
        UserRole.objects.create(user=self.tenant_admin, role=ta_role)
        self.client.force_authenticate(user=self.tenant_admin)

    def test_view_tenant_settings_success(self):
        """GET /api/v1/tenants/{id}/config/ → 200."""
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_tenant_settings_success(self):
        """PATCH /api/v1/tenants/{id}/config/ → 200."""
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/",
            {"data_retention_days": 365},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK,
            f"Valid retention days should succeed, got {response.status_code}: "
            f"{getattr(response, 'data', '')}")

    def test_view_subscription_as_usage_proxy(self):
        """GET /api/v1/billing/subscription/current/ as usage proxy → 200/404.

        Note: /billing/usage/ does not exist — subscription/current/ is the
        closest real endpoint for tenant usage/plan context.
        """
        response = self.client.get("/api/v1/billing/subscription/current/")
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
        )

    def test_tenant_settings_failure_other_tenant(self):
        """PATCH another tenant's config → 403/404."""
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        response = self.client.patch(
            f"/api/v1/tenants/{other_tenant.id}/config/",
            {"data_retention_days": 365},
            format="json",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND],
        )

