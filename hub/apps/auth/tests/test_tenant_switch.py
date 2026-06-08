"""
Tests for tenant switch API and X-Tenant-Id middleware.

Phase 29.65.3 (TDD). Covers:
- GET /auth/me/tenants/ — list tenants from UserTenantMembership
- POST /auth/switch-tenant/ — validate membership, return me summary
- X-Tenant-Id middleware — validate membership, 403 if invalid

No mocks — uses real implementations.
"""

import uuid

import pytest
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.auth.middleware import TenantScopingMiddleware
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.users.models import UserTenantMembership

pytestmark = pytest.mark.django_db(transaction=True)


class MeTenantsEndpointTest(TestCase):
    """Test GET /auth/me/tenants/."""

    def setUp(self):
        uid = str(uuid.uuid4())[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"Tenant A {uid}",
            slug=f"tenant-a-{uid}",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"Tenant B {uid}",
            slug=f"tenant-b-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"me-tenants-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_a)
        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_b)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_get_me_tenants_returns_list(self):
        """GET /auth/me/tenants/ returns tenants with id, name, slug."""
        response = self.client.get("/api/v1/auth/me/tenants/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        ids = {t["id"] for t in data}
        self.assertIn(str(self.tenant_a.id), ids)
        self.assertIn(str(self.tenant_b.id), ids)
        for t in data:
            self.assertIn("id", t)
            self.assertIn("name", t)
            self.assertIn("slug", t)

    def test_get_me_tenants_unauthorized(self):
        """GET /auth/me/tenants/ returns 401 when not authenticated."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/auth/me/tenants/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_me_tenants_empty_when_no_memberships(self):
        """GET /auth/me/tenants/ returns [] when user has no memberships."""
        user2 = User.objects.create_user(
            email=f"no-mem-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.filter(user=user2).delete()
        self.client.force_authenticate(user=user2)
        response = self.client.get("/api/v1/auth/me/tenants/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    @override_settings(FEATURE_TENANT_SWITCH_ENABLED=False)
    def test_get_me_tenants_returns_403_when_feature_disabled(self):
        """GET /auth/me/tenants/ returns 403 when FEATURE_TENANT_SWITCH_ENABLED is False."""
        response = self.client.get("/api/v1/auth/me/tenants/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("disabled", response.json().get("detail", "").lower())

    def test_get_me_includes_feature_tenant_switch_enabled(self):
        """GET /auth/me/ includes feature_tenant_switch_enabled (default True)."""
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("feature_tenant_switch_enabled", data)
        self.assertIs(data["feature_tenant_switch_enabled"], True)

    @override_settings(FEATURE_TENANT_SWITCH_ENABLED=False)
    def test_get_me_includes_feature_tenant_switch_enabled_false_when_disabled(self):
        """GET /auth/me/ returns feature_tenant_switch_enabled=False when setting disabled."""
        cache.clear()  # Ensure fresh response (me view caches GET)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIs(data["feature_tenant_switch_enabled"], False)


class SwitchTenantEndpointTest(TestCase):
    """Test POST /auth/switch-tenant/."""

    def setUp(self):
        uid = str(uuid.uuid4())[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"Switch A {uid}",
            slug=f"switch-a-{uid}",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"Switch B {uid}",
            slug=f"switch-b-{uid}",
        )
        self.tenant_c = Tenant.objects.create(
            name=f"Switch C {uid}",
            slug=f"switch-c-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"switch-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_a)
        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_b)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_switch_tenant_success_returns_me_summary(self):
        """POST /auth/switch-tenant/ with valid tenant_id returns 200 + me summary."""
        response = self.client.post(
            "/api/v1/auth/switch-tenant/",
            {"tenant_id": str(self.tenant_b.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data.get("tenant_id"), str(self.tenant_b.id))
        self.assertIn("id", data)
        self.assertIn("email", data)

    def test_switch_tenant_invalid_membership_returns_403(self):
        """POST /auth/switch-tenant/ with tenant user has no membership returns 403."""
        response = self.client.post(
            "/api/v1/auth/switch-tenant/",
            {"tenant_id": str(self.tenant_c.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_switch_tenant_missing_tenant_id_returns_400(self):
        """POST /auth/switch-tenant/ without tenant_id returns 400."""
        response = self.client.post(
            "/api/v1/auth/switch-tenant/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_switch_tenant_invalid_uuid_returns_400(self):
        """POST /auth/switch-tenant/ with invalid tenant_id returns 400."""
        response = self.client.post(
            "/api/v1/auth/switch-tenant/",
            {"tenant_id": "not-a-uuid"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_switch_tenant_unauthorized(self):
        """POST /auth/switch-tenant/ returns 401 when not authenticated."""
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/v1/auth/switch-tenant/",
            {"tenant_id": str(self.tenant_b.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_switch_tenant_creates_tenant_switch_audit_event(self):
        """POST /auth/switch-tenant/ creates TENANT_SWITCH audit event with from/to tenant ids."""
        initial_count = AuditEvent.objects.filter(action="TENANT_SWITCH").count()
        response = self.client.post(
            "/api/v1/auth/switch-tenant/",
            {"tenant_id": str(self.tenant_b.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        events = AuditEvent.objects.filter(
            action="TENANT_SWITCH",
            actor_user=self.user,
        ).order_by("-timestamp")
        self.assertGreaterEqual(events.count(), 1)
        latest = events.first()
        self.assertEqual(latest.details_json.get("to_tenant_id"), str(self.tenant_b.id))
        self.assertEqual(latest.details_json.get("from_tenant_id"), str(self.tenant_a.id))

    @override_settings(FEATURE_TENANT_SWITCH_ENABLED=False)
    def test_switch_tenant_returns_403_when_feature_disabled(self):
        """POST /auth/switch-tenant/ returns 403 when FEATURE_TENANT_SWITCH_ENABLED is False."""
        response = self.client.post(
            "/api/v1/auth/switch-tenant/",
            {"tenant_id": str(self.tenant_b.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("disabled", response.json().get("detail", "").lower())


class XTenantIdMiddlewareTest(TestCase):
    """Test X-Tenant-Id header handling in TenantScopingMiddleware."""

    def setUp(self):
        uid = str(uuid.uuid4())[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"XTenant A {uid}",
            slug=f"xtenant-a-{uid}",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"XTenant B {uid}",
            slug=f"xtenant-b-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"xtenant-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_a)
        UserTenantMembership.objects.create(user=self.user, tenant=self.tenant_b)
        self.factory = RequestFactory()
        self.get_response = lambda r: __import__("django.http").http.HttpResponse()
        self.middleware = TenantScopingMiddleware(self.get_response)

    def test_x_tenant_id_valid_membership_sets_request_tenant_id(self):
        """X-Tenant-Id with valid membership sets request.tenant_id."""
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user
        request.META["HTTP_X_TENANT_ID"] = str(self.tenant_b.id)

        self.middleware.process_request(request)

        self.assertEqual(str(request.tenant_id), str(self.tenant_b.id))
        self.assertEqual(request.tenant.id, self.tenant_b.id)

    def test_x_tenant_id_invalid_membership_returns_403_response(self):
        """X-Tenant-Id with invalid membership causes 403 response from middleware."""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-xtest-{_uid}",
        )
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user
        request.META["HTTP_X_TENANT_ID"] = str(other_tenant.id)

        response = self.middleware(request)

        self.assertEqual(response.status_code, 403)

    def test_x_tenant_id_empty_uses_user_tenant(self):
        """X-Tenant-Id empty or missing falls back to user.tenant_id."""
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user
        # No X-Tenant-Id header

        self.middleware.process_request(request)

        self.assertEqual(str(request.tenant_id), str(self.tenant_a.id))

    def test_x_tenant_id_unauthenticated_returns_401(self):
        """X-Tenant-Id with no user (no session, no JWT) returns 401.

        The middleware returns 401 (not 403) so that the frontend's
        automatic refresh-on-401 → retry path can transparently
        re-authenticate on token expiry.  403 would break this flow
        because it means "your credentials are valid but insufficient"
        — which the frontend correctly does not retry.
        """
        request = self.factory.get("/api/v1/assets/")
        request.user = None
        request.META["HTTP_X_TENANT_ID"] = str(self.tenant_b.id)

        response = self.middleware(request)

        self.assertEqual(response.status_code, 401)

    def test_x_tenant_id_with_jwt_valid_membership_sets_request_tenant_id(self):
        """X-Tenant-Id with JWT (no force_authenticate) and valid membership sets request.tenant_id."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant_a.id)
        )
        request = self.factory.get(
            "/api/v1/assets/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_TENANT_ID=str(self.tenant_b.id),
        )
        request.user = None  # Simulate no session; user comes from JWT

        self.middleware.process_request(request)

        self.assertEqual(str(request.tenant_id), str(self.tenant_b.id))
        self.assertEqual(request.tenant.id, self.tenant_b.id)

    @override_settings(FEATURE_TENANT_SWITCH_ENABLED=False)
    def test_x_tenant_id_returns_403_when_feature_disabled(self):
        """X-Tenant-Id returns 403 when FEATURE_TENANT_SWITCH_ENABLED is False."""
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user
        request.META["HTTP_X_TENANT_ID"] = str(self.tenant_b.id)

        response = self.middleware(request)

        self.assertEqual(response.status_code, 403)
