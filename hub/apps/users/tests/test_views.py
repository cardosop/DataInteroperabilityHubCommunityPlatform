"""
Unit tests for User API views.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
import uuid

from hub.apps.users.models import User, Role, UserRole, UserStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class UserViewSetTest(TestCase):
    """Test UserViewSet CRUD operations"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create platform admin user
        self.platform_admin = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            is_platform_admin=True
        )
        
        # Create tenant admin user with TENANT_ADMIN role
        self.tenant_admin = User.objects.create_user(
            email="tenant_admin@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.create(user=self.tenant_admin, role=tenant_admin_role)
        
        # Create regular user
        self.regular_user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Active subscription required so TenantSuspensionMiddleware allows writes
        ensure_tenant_has_active_subscription(self.tenant)
    
    def test_create_user(self):
        """Test user creation"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        data = {
            "email": "newuser@example.com",
            "display_name": "New User",
            "password": "testpass123",
            "tenant": str(self.tenant.id),
            "status": "ACTIVE"
        }
        
        response = self.client.post("/api/v1/users/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "newuser@example.com")
        self.assertEqual(response.data["status"], "ACTIVE")
        
        # Verify user was created
        user = User.objects.get(email="newuser@example.com")
        self.assertEqual(user.tenant, self.tenant)
        self.assertEqual(user.status, UserStatus.ACTIVE)
    
    def test_list_users(self):
        """Test user listing (tenant-scoped)"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should only see users in the same tenant
        user_emails = [user["email"] for user in response.data["results"]]
        self.assertIn("tenant_admin@example.com", user_emails)
        self.assertIn("user@example.com", user_emails)
        self.assertNotIn("admin@example.com", user_emails)  # Platform admin not in tenant
    
    def test_retrieve_user(self):
        """Test user retrieval"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        response = self.client.get(f"/api/v1/users/{self.regular_user.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "user@example.com")
    
    def test_update_user(self):
        """Test user update (TENANT_ADMIN can update)"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        data = {
            "display_name": "Updated Name"
        }
        
        response = self.client.patch(
            f"/api/v1/users/{self.regular_user.id}/",
            data,
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["display_name"], "Updated Name")
        
        # Verify update
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.display_name, "Updated Name")

    def test_update_user_requires_tenant_admin(self):
        """Test regular user cannot update (403)"""
        self.client.force_authenticate(user=self.regular_user)
        
        response = self.client.patch(
            f"/api/v1/users/{self.tenant_admin.id}/",
            {"display_name": "Hacked"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)

    def test_update_user_with_roles(self):
        """Test user update with role assignment"""
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        self.client.force_authenticate(user=self.tenant_admin)
        
        response = self.client.put(
            f"/api/v1/users/{self.regular_user.id}/",
            {
                "display_name": "Provider User",
                "status": "ACTIVE",
                "role_ids": [str(data_provider_role.id)],
            },
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("DATA_PROVIDER", response.data["roles"])
        
        self.regular_user.refresh_from_db()
        role_names = [ur.role.name for ur in UserRole.objects.filter(user=self.regular_user)]
        self.assertIn("DATA_PROVIDER", role_names)

    def test_update_user_platform_admin_can_update(self):
        """Test platform admin can update user (cross-tenant)"""
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.patch(
            f"/api/v1/users/{self.regular_user.id}/",
            {"display_name": "Updated by Platform Admin"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["display_name"], "Updated by Platform Admin")

        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.display_name, "Updated by Platform Admin")

    def test_update_user_audit(self):
        """Test user update creates audit event"""
        from hub.apps.audit.models import AuditEvent

        self.client.force_authenticate(user=self.tenant_admin)
        
        self.client.patch(
            f"/api/v1/users/{self.regular_user.id}/",
            {"display_name": "Audited Name"},
            format="json"
        )
        
        events = AuditEvent.objects.filter(
            resource_type="USER",
            resource_id=self.regular_user.id,
        ).order_by("-timestamp")
        self.assertGreaterEqual(events.count(), 1)
        self.assertEqual(events.first().action, "USER_UPDATED")
    
    def test_delete_user_no_resources(self):
        """Test user deletion when user has no resources (hard delete)"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # Create a user with no resources
        test_user = User.objects.create_user(
            email="todelete@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        user_id = test_user.id
        
        response = self.client.delete(f"/api/v1/users/{user_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify user was deleted
        self.assertFalse(User.objects.filter(id=user_id).exists())
    
    def test_delete_user_with_resources(self):
        """Test user deletion when user has resources (soft delete)"""
        self.client.force_authenticate(user=self.tenant_admin)
        
        # For now, _user_has_resources returns False, so this will hard delete
        # When resources are implemented, this should soft delete
        # TODO: Update this test when resource checking is implemented
        pass
    
    def test_invite_user(self):
        """Test user invitation (new user creates user + membership)"""
        self.client.force_authenticate(user=self.tenant_admin)

        data = {
            "email": "invited@example.com",
            "display_name": "Invited User"
        }

        response = self.client.post("/api/v1/users/invite/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "invited@example.com")
        self.assertEqual(response.data["status"], "INVITED")

        # Verify user was created with invitation token
        user = User.objects.get(email="invited@example.com")
        self.assertIsNotNone(user.invitation_token)
        self.assertIsNotNone(user.invitation_token_expires_at)
        self.assertGreater(
            user.invitation_token_expires_at,
            timezone.now() + timedelta(days=6)
        )

        # Verify UserTenantMembership was created (29.65.4)
        from hub.apps.users.models import UserTenantMembership
        self.assertTrue(
            UserTenantMembership.objects.filter(
                user=user, tenant=self.tenant
            ).exists(),
            "Invite new user must create UserTenantMembership",
        )

    def test_invite_existing_user_adds_membership(self):
        """Invite existing user (same email) adds UserTenantMembership instead of failing."""
        uid = str(uuid.uuid4())[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uid}",
            slug=f"other-tenant-invite-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        existing_user = User.objects.create_user(
            email="existing@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.post(
            "/api/v1/users/invite/",
            {"email": "existing@example.com", "display_name": "Existing User"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], "existing@example.com")

        from hub.apps.users.models import UserTenantMembership
        self.assertTrue(
            UserTenantMembership.objects.filter(
                user=existing_user, tenant=self.tenant
            ).exists(),
            "Invite existing user must add UserTenantMembership",
        )
        existing_user.refresh_from_db()
        self.assertEqual(existing_user.tenant_id, other_tenant.id, "Primary tenant unchanged")

    def test_invite_new_user_creates_user_and_membership(self):
        """Invite new user creates User + UserTenantMembership."""
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.post(
            "/api/v1/users/invite/",
            {
                "email": "brandnew@example.com",
                "display_name": "Brand New User",
                "role_ids": [str(data_provider_role.id)],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email="brandnew@example.com")
        self.assertEqual(user.status, UserStatus.INVITED)
        self.assertEqual(user.tenant_id, self.tenant.id)

        from hub.apps.users.models import UserTenantMembership
        self.assertTrue(
            UserTenantMembership.objects.filter(
                user=user, tenant=self.tenant
            ).exists(),
            "Invite new user must create UserTenantMembership",
        )
    
    def test_tenant_scoping(self):
        """Test that users can only see users in their tenant"""
        self.client.force_authenticate(user=self.regular_user)
        
        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )
        
        # Regular user should not see users from other tenant
        response = self.client.get("/api/v1/users/")
        user_emails = [user["email"] for user in response.data["results"]]
        self.assertNotIn("other@example.com", user_emails)
        
        # Regular user should not be able to retrieve other tenant's user
        response = self.client.get(f"/api/v1/users/{other_user.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_platform_admin_sees_all_users(self):
        """Test that platform admins can see all users"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user_emails = [user["email"] for user in response.data["results"]]
        # Platform admin should see all users
        self.assertIn("admin@example.com", user_emails)
        self.assertIn("tenant_admin@example.com", user_emails)
        self.assertIn("user@example.com", user_emails)

