"""
Unit tests for User API views.
"""

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class UserViewSetTest(TestCase):
    """Test UserViewSet CRUD operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create platform admin user
        self.platform_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            is_platform_admin=True,
        )

        # Create tenant admin user with TENANT_ADMIN role
        self.tenant_admin = User.objects.create_user(
            email=f"tenant_admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.create(user=self.tenant_admin, role=tenant_admin_role)

        # Create regular user
        self.regular_user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Active subscription required so TenantSuspensionMiddleware allows writes
        ensure_tenant_has_active_subscription(self.tenant)

    def test_create_user(self):
        """Test user creation verifies response, DB state, and password not leaked."""
        self.client.force_authenticate(user=self.tenant_admin)

        unique_email = f"newuser-{uuid.uuid4().hex[:8]}@example.com"
        data = {
            "email": unique_email,
            "display_name": "New User",
            "password": "testpass123",
            "tenant": str(self.tenant.id),
            "send_invitation": False,  # G2.2: status derived from send_invitation
        }

        response = self.client.post("/api/v1/users/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], unique_email)
        self.assertEqual(response.data["status"], "ACTIVE")
        # Password must never be returned in API response
        self.assertNotIn("password", response.data)

        # Verify user was created in DB with correct fields
        user = User.objects.get(email=unique_email)
        self.assertEqual(user.tenant, self.tenant)
        self.assertEqual(user.status, UserStatus.ACTIVE)
        self.assertTrue(user.check_password("testpass123"), "Password should be set correctly")

    def test_create_user_unauthenticated(self):
        """Unauthenticated request to create user must return 401."""
        response = self.client.post(
            "/api/v1/users/",
            {"email": "unauth@example.com", "password": "testpass123"},
            format="json",
        )
        self.assertIn(
            response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
        )

    def test_create_user_duplicate_email(self):
        """Creating user with duplicate email returns 400, not 500."""
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.post(
            "/api/v1/users/",
            {
                "email": self.regular_user.email,
                "password": "testpass123",
                "tenant": str(self.tenant.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_users_returns_paginated_results(self):
        """Test user listing returns paginated DRF response with required fields."""
        self.client.force_authenticate(user=self.tenant_admin)

        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify pagination structure
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertIsInstance(response.data["results"], list)

    def test_list_users_tenant_scoped(self):
        """Tenant admin only sees own-tenant users, not cross-tenant or tenant-less."""
        self.client.force_authenticate(user=self.tenant_admin)

        # Retrieve by ID to definitively test scoping (pagination-proof)
        # Own-tenant user: should be visible
        response = self.client.get(f"/api/v1/users/{self.regular_user.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Platform admin (no tenant): should NOT be visible to tenant admin
        response = self.client.get(f"/api/v1/users/{self.platform_admin.id}/")
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "Tenant admin must NOT see users outside their tenant",
        )

    def test_retrieve_user(self):
        """Test user retrieval"""
        self.client.force_authenticate(user=self.tenant_admin)

        response = self.client.get(f"/api/v1/users/{self.regular_user.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.regular_user.email)

    def test_update_user(self):
        """Test user update (TENANT_ADMIN can update)"""
        self.client.force_authenticate(user=self.tenant_admin)

        data = {"display_name": "Updated Name"}

        response = self.client.patch(f"/api/v1/users/{self.regular_user.id}/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["display_name"], "Updated Name")

        # Verify update
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.display_name, "Updated Name")

    def test_update_user_requires_tenant_admin(self):
        """Regular user cannot update another user — 403 and no DB change."""
        self.client.force_authenticate(user=self.regular_user)
        original_name = self.tenant_admin.display_name

        response = self.client.patch(
            f"/api/v1/users/{self.tenant_admin.id}/", {"display_name": "Hacked"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify the target user was NOT actually modified
        self.tenant_admin.refresh_from_db()
        self.assertEqual(
            self.tenant_admin.display_name,
            original_name,
            "Regular user must NOT be able to modify another user's data",
        )

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
            format="json",
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
        """Test user update creates exactly one USER_UPDATED audit event with correct actor."""
        from hub.apps.audit.models import AuditEvent

        self.client.force_authenticate(user=self.tenant_admin)

        # Count events BEFORE the action
        events_before = AuditEvent.objects.filter(
            resource_type="USER",
            resource_id=self.regular_user.id,
            action="USER_UPDATED",
        ).count()

        response = self.client.patch(
            f"/api/v1/users/{self.regular_user.id}/",
            {"display_name": "Audited Name"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify exactly 1 new event was created (not 0, not 5)
        events_after = AuditEvent.objects.filter(
            resource_type="USER",
            resource_id=self.regular_user.id,
            action="USER_UPDATED",
        )
        self.assertEqual(
            events_after.count(),
            events_before + 1,
            "Exactly one USER_UPDATED audit event should be created",
        )
        event = events_after.order_by("-timestamp").first()
        self.assertEqual(event.action, "USER_UPDATED")
        self.assertEqual(str(event.actor_user_id), str(self.tenant_admin.id))

    def test_delete_user_no_resources(self):
        """Test user deletion when user has no resources (hard delete)"""
        self.client.force_authenticate(user=self.tenant_admin)

        # Create a user with no resources
        test_user = User.objects.create_user(
            email=f"todelete-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        user_id = test_user.id

        response = self.client.delete(f"/api/v1/users/{user_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify user was deleted
        self.assertFalse(User.objects.filter(id=user_id).exists())

    def test_delete_nonexistent_user_returns_404(self):
        """Deleting a non-existent user must return 404, not 204 or 500."""
        self.client.force_authenticate(user=self.tenant_admin)
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.delete(f"/api/v1/users/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_user_invalid_uuid_returns_error(self):
        """Deleting with invalid UUID must return 400 or 404, not 500."""
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.delete("/api/v1/users/not-a-uuid/")
        self.assertIn(
            response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]
        )

    def test_invite_user(self):
        """Test user invitation creates user with token, correct status, and membership."""
        self.client.force_authenticate(user=self.tenant_admin)

        invite_email = f"invited-{uuid.uuid4().hex[:8]}@example.com"
        data = {"email": invite_email, "display_name": "Invited User"}

        response = self.client.post("/api/v1/users/invite/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], invite_email)
        self.assertEqual(response.data["status"], "INVITED")
        # Password must not be in response
        self.assertNotIn("password", response.data)

        # Verify user was created with invitation token
        user = User.objects.get(email=invite_email)
        self.assertEqual(user.status, UserStatus.INVITED)
        self.assertIsNotNone(user.invitation_token)
        self.assertIsNotNone(user.invitation_token_expires_at)
        self.assertGreater(user.invitation_token_expires_at, timezone.now() + timedelta(days=6))

        # Verify UserTenantMembership was created (29.65.4)
        from hub.apps.users.models import UserTenantMembership

        self.assertTrue(
            UserTenantMembership.objects.filter(user=user, tenant=self.tenant).exists(),
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
            email=f"existing-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.post(
            "/api/v1/users/invite/",
            {"email": existing_user.email, "display_name": "Existing User"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["email"], existing_user.email)

        from hub.apps.users.models import UserTenantMembership

        self.assertTrue(
            UserTenantMembership.objects.filter(user=existing_user, tenant=self.tenant).exists(),
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
        brandnew_email = f"brandnew-{uuid.uuid4().hex[:8]}@example.com"
        response = self.client.post(
            "/api/v1/users/invite/",
            {
                "email": brandnew_email,
                "display_name": "Brand New User",
                "role_ids": [str(data_provider_role.id)],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email=brandnew_email)
        self.assertEqual(user.status, UserStatus.INVITED)
        self.assertEqual(user.tenant_id, self.tenant.id)

        from hub.apps.users.models import UserTenantMembership

        self.assertTrue(
            UserTenantMembership.objects.filter(user=user, tenant=self.tenant).exists(),
            "Invite new user must create UserTenantMembership",
        )

    def test_tenant_scoping_blocks_cross_tenant_access(self):
        """Regular user cannot retrieve or list users from another tenant."""
        self.client.force_authenticate(user=self.regular_user)

        # Create another tenant and user
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Direct retrieval of cross-tenant user must return 404 (not 200 or 403)
        response = self.client.get(f"/api/v1/users/{other_user.id}/")
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "Cross-tenant user retrieval must return 404",
        )

        # Own-tenant user must still be accessible
        response = self.client.get(f"/api/v1/users/{self.tenant_admin.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_platform_admin_sees_all_users(self):
        """Test that platform admins can see users across tenants"""
        self.client.force_authenticate(user=self.platform_admin)

        # With --reuse-db the users table can contain thousands of rows.
        # Instead of relying on all users fitting in one page, verify that
        # the platform admin can retrieve specific users by ID (cross-tenant).
        for target_user in (self.platform_admin, self.tenant_admin, self.regular_user):
            response = self.client.get(f"/api/v1/users/{target_user.id}/")
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Platform admin should be able to retrieve user {target_user.email}",
            )
            self.assertEqual(response.data["email"], target_user.email)

    # ========== SECURITY TESTS ==========

    def test_unauthenticated_list_returns_401_or_403(self):
        """Unauthenticated GET /users/ must be rejected."""
        response = self.client.get("/api/v1/users/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_unauthenticated_retrieve_returns_401_or_403(self):
        """Unauthenticated GET /users/{id}/ must be rejected."""
        response = self.client.get(f"/api/v1/users/{self.regular_user.id}/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_regular_user_cannot_delete_other_user(self):
        """Regular user cannot delete another user in the same tenant."""
        self.client.force_authenticate(user=self.regular_user)
        target = User.objects.create_user(
            email=f"victim-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        response = self.client.delete(f"/api/v1/users/{target.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Verify user was NOT deleted
        self.assertTrue(User.objects.filter(id=target.id).exists())

    def test_cross_tenant_update_blocked(self):
        """Tenant admin cannot PATCH a user from a different tenant."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"XTenant {_uid}",
            slug=f"xtenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        other_user = User.objects.create_user(
            email=f"xuser-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.patch(
            f"/api/v1/users/{other_user.id}/",
            {"display_name": "Hacked from other tenant"},
            format="json",
        )
        # Cross-tenant update returns 404 (user not in queryset).
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        other_user.refresh_from_db()
        self.assertNotEqual(other_user.display_name, "Hacked from other tenant")

    def test_retrieve_invalid_uuid_returns_error(self):
        """GET /users/not-a-uuid/ must return 400 or 404, not 500."""
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.get("/api/v1/users/not-a-uuid/")
        self.assertIn(
            response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]
        )
