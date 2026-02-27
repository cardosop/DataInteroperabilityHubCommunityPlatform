"""
Comprehensive E2E tests for user management.

Covers:
- User CRUD operations
- User roles and role assignment
- User invitations
- User soft delete
- Token version increment on role change
- Audit logging
- State verification

Uses REAL services (no mocks).
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status

from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.audit.models import AuditEvent

from .conftest import E2ETestBase, get_response_data


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e4]
UserModel = get_user_model()


class UserManagementE2ETest(E2ETestBase):
    """Test user management operations"""
    
    def setUp(self):
        """Set up test fixtures with tenant admin user"""
        super().setUp()
        
        # Get or create tenant admin role (may already exist from tenant signals)
        self.tenant_admin_role, created = Role.objects.get_or_create(
            tenant=self.tenant,
            name='TENANT_ADMIN',
            defaults={'description': 'Tenant administrator'}
        )
        
        # Assign tenant admin role to user (if not already assigned)
        UserRole.objects.get_or_create(user=self.user, role=self.tenant_admin_role)
        
        # Refresh user to get updated roles
        self.user.refresh_from_db()
    
    def test_create_user_with_roles(self):
        """Test creating user with roles"""
        # Get or create roles (may already exist from tenant signals)
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name='DATA_PROVIDER',
            defaults={'description': 'Data provider role'}
        )
        data_consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name='DATA_CONSUMER',
            defaults={'description': 'Data consumer role'}
        )
        
        response = self.client.post(
            '/api/v1/users/',
            {
                'email': 'newuser@example.com',
                'display_name': 'New User',
                'role_ids': [str(data_provider_role.id), str(data_consumer_role.id)],
                'send_invitation': False
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual((get_response_data(response) or {})['email'], 'newuser@example.com')
        self.assertEqual((get_response_data(response) or {})['display_name'], 'New User')
        self.assertEqual((get_response_data(response) or {})['status'], UserStatus.ACTIVE)  # No invitation
        
        # Verify user exists in database
        user = User.objects.get(id=(get_response_data(response) or {})['id'])
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertEqual(user.status, UserStatus.ACTIVE)
        self.assertEqual(user.tenant, self.tenant)
        
        # Verify roles assigned
        user_roles = UserRole.objects.filter(user=user)
        role_names = {ur.role.name for ur in user_roles}
        self.assertIn('DATA_PROVIDER', role_names)
        self.assertIn('DATA_CONSUMER', role_names)
        
        # Verify audit log created
        self.verify_audit_log(
            action='USER_CREATED',
            resource_type='USER',
            resource_id=user.id,
            result='SUCCESS'
        )
    
    def test_create_user_with_invitation(self):
        """Test creating user with invitation"""
        response = self.client.post(
            '/api/v1/users/',
            {
                'email': 'invited@example.com',
                'display_name': 'Invited User',
                'send_invitation': True
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual((get_response_data(response) or {})['status'], UserStatus.INVITED)
        
        # Verify user exists with INVITED status
        user = User.objects.get(id=(get_response_data(response) or {})['id'])
        self.assertEqual(user.status, UserStatus.INVITED)
        self.assertIsNotNone(user.invitation_token)
        self.assertIsNotNone(user.invitation_token_expires_at)
    
    def test_list_users_with_filters(self):
        """Test listing users with status and role filters"""
        # Create users with different statuses
        active_user = User.objects.create_user(
            email='active@example.com',
            password='testpass123',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        invited_user = User.objects.create_user(
            email='invited@example.com',
            password='testpass123',
            tenant=self.tenant,
            status=UserStatus.INVITED
        )
        
        # List all users
        response = self.client.get('/api/v1/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len((get_response_data(response) or {})['results']), 2)
        
        # Filter by status
        response = self.client.get('/api/v1/users/?status=ACTIVE')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_emails = {u['email'] for u in (get_response_data(response) or {})['results']}
        self.assertIn('active@example.com', user_emails)
        self.assertNotIn('invited@example.com', user_emails)
    
    def test_get_user_details(self):
        """Test retrieving user details"""
        test_user = User.objects.create_user(
            email='testuser@example.com',
            password='testpass123',
            tenant=self.tenant,
            display_name='Test User',
            status=UserStatus.ACTIVE
        )
        
        response = self.client.get(f'/api/v1/users/{test_user.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((get_response_data(response) or {})['id'], str(test_user.id))
        self.assertEqual((get_response_data(response) or {})['email'], 'testuser@example.com')
        self.assertEqual((get_response_data(response) or {})['display_name'], 'Test User')
        self.assertEqual((get_response_data(response) or {})['status'], UserStatus.ACTIVE)
    
    def test_update_user_display_name(self):
        """Test updating user display name"""
        test_user = User.objects.create_user(
            email='updateuser@example.com',
            password='testpass123',
            tenant=self.tenant,
            display_name='Original Name',
            status=UserStatus.ACTIVE
        )
        
        response = self.client.patch(
            f'/api/v1/users/{test_user.id}/',
            {'display_name': 'Updated Name'},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((get_response_data(response) or {})['display_name'], 'Updated Name')
        
        # Verify database updated
        test_user.refresh_from_db()
        self.assertEqual(test_user.display_name, 'Updated Name')
        
        # Verify audit log created
        self.verify_audit_log(
            action='USER_UPDATED',
            resource_type='USER',
            resource_id=test_user.id,
            result='SUCCESS'
        )
    
    def test_update_user_roles_increments_token_version(self):
        """Test that updating user roles increments token version"""
        test_user = User.objects.create_user(
            email='roleuser@example.com',
            password='testpass123',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Get or create role (may already exist from tenant signals)
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name='DATA_PROVIDER',
            defaults={'description': 'Data provider role'}
        )
        
        # Get initial token version
        initial_token_version = test_user.token_version
        
        # Assign role via manage_roles endpoint
        response = self.client.post(
            f'/api/v1/users/{test_user.id}/roles/',
            {
                'role_id': str(data_provider_role.id),
                'action': 'assign'
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify token version incremented
        test_user.refresh_from_db()
        self.assertEqual(test_user.token_version, initial_token_version + 1)
        
        # Verify audit log created
        self.verify_audit_log(
            action='USER_ROLE_CHANGED',
            resource_type='USER',
            resource_id=test_user.id,
            result='SUCCESS'
        )
    
    def test_invite_user(self):
        """Test inviting a user via invite endpoint"""
        response = self.client.post(
            '/api/v1/users/invite/',
            {
                'email': 'invitee@example.com',
                'display_name': 'Invitee User'
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual((get_response_data(response) or {})['email'], 'invitee@example.com')
        self.assertEqual((get_response_data(response) or {})['status'], UserStatus.INVITED)
        
        # Verify user exists with invitation token
        user = User.objects.get(id=(get_response_data(response) or {})['id'])
        self.assertEqual(user.status, UserStatus.INVITED)
        self.assertIsNotNone(user.invitation_token)
        
        # Verify audit log created
        self.verify_audit_log(
            action='USER_INVITED',
            resource_type='USER',
            resource_id=user.id,
            result='SUCCESS'
        )
    
    def test_delete_user_without_resources(self):
        """Test deleting user without resources (hard delete)"""
        test_user = User.objects.create_user(
            email='deleteuser@example.com',
            password='testpass123',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        user_id = test_user.id
        
        response = self.client.delete(f'/api/v1/users/{test_user.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify user is deleted (hard delete for users without resources)
        self.assertFalse(User.objects.filter(id=user_id).exists())
        
        # Verify audit log created
        # Note: User is deleted, so we check by email or action
        audit_event = AuditEvent.objects.filter(
            action='USER_DELETED',
            resource_type='USER',
            tenant=self.tenant
        ).order_by('-timestamp').first()
        self.assertIsNotNone(audit_event)
    
    def test_delete_user_with_resources_soft_delete(self):
        """Test deleting user with resources performs soft delete"""
        from hub.apps.assets.models import Asset
        
        test_user = User.objects.create_user(
            email='resourceuser@example.com',
            password='testpass123',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create an asset for this user (user has resources)
        asset = Asset.objects.create(
            tenant=self.tenant,
            key='test-asset',
            name='Test Asset',
            created_by=test_user
        )
        
        response = self.client.delete(f'/api/v1/users/{test_user.id}/')
        
        # User with resources returns 200 with message (soft delete)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user is soft deleted (status = DISABLED, but still exists)
        test_user.refresh_from_db()
        self.assertEqual(test_user.status, UserStatus.DISABLED)
        self.assertTrue(test_user.is_disabled())
    
    def test_delete_self_fails(self):
        """Test that users cannot delete themselves"""
        response = self.client.delete(f'/api/v1/users/{self.user.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cannot delete themselves', (get_response_data(response) or {})['error'].lower())
        
        # Verify user still exists
        self.user.refresh_from_db()
        self.assertEqual(self.user.status, UserStatus.ACTIVE)
    
    def test_create_user_duplicate_email_fails(self):
        """Test creating user with duplicate email fails"""
        existing_user = User.objects.create_user(
            email='duplicate@example.com',
            password='testpass123',
            tenant=self.tenant
        )
        
        response = self.client.post(
            '/api/v1/users/',
            {
                'email': 'duplicate@example.com',
                'display_name': 'Duplicate User',
                'send_invitation': False
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', (get_response_data(response) or {}))
    
    def test_create_user_invalid_email_fails(self):
        """Test creating user with invalid email format fails"""
        response = self.client.post(
            '/api/v1/users/',
            {
                'email': 'invalid-email',
                'display_name': 'Invalid User',
                'send_invitation': False
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', (get_response_data(response) or {}))
    
    def test_update_user_status(self):
        """Test updating user status"""
        test_user = User.objects.create_user(
            email='statususer@example.com',
            password='testpass123',
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        response = self.client.patch(
            f'/api/v1/users/{test_user.id}/',
            {'status': UserStatus.DISABLED},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((get_response_data(response) or {})['status'], UserStatus.DISABLED)
        
        # Verify database updated
        test_user.refresh_from_db()
        self.assertEqual(test_user.status, UserStatus.DISABLED)
        self.assertTrue(test_user.is_disabled())

