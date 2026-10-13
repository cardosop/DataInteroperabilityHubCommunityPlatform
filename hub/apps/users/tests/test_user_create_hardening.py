"""
W1.2 (oss-release-remediation, R2-S2) — user-create hardening pins.

The user-create endpoint trusted the client for BOTH the target tenant
(the R2-B1 register-JOIN class: a TENANT_ADMIN could create users in a
foreign tenant) and the assigned roles (escalation: platform-level roles
requested by a tenant admin were silently dropped, not rejected). The
create action must be gated like update/destroy (TENANT_ADMIN or
PLATFORM_ADMIN), the tenant must come from the REQUEST, and the
requested roles must lie inside the requester-assignable set — anything
else is 403.
"""

import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus


def _unique_slug():
    return uuid.uuid4().hex[:8]


class UserCreateHardeningTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        slug_a = _unique_slug()
        slug_b = _unique_slug()

        self.tenant_a = Tenant.objects.create(
            name=f"Tenant A {slug_a}",
            slug=slug_a,
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"Tenant B {slug_b}",
            slug=slug_b,
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant_a)
        ensure_tenant_has_active_subscription(self.tenant_b)

        self.platform_admin = User.objects.create_user(
            email=f"w12_platform_{slug_a}@example.com",
            password="testpass123",
            is_platform_admin=True,
        )

        self.tenant_a_admin = User.objects.create_user(
            email=f"w12_admin_a_{slug_a}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        admin_role_a, _ = Role.objects.get_or_create(
            tenant=self.tenant_a,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.create(user=self.tenant_a_admin, role=admin_role_a)

        self.regular_user_a = User.objects.create_user(
            email=f"w12_regular_a_{slug_a}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )

        # A platform-level role (tenant=None) — assigning it is escalation.
        self.platform_role, _ = Role.objects.get_or_create(
            tenant=None,
            name="PLATFORM_ADMIN",
            defaults={"description": "Platform Administrator"},
        )

    def _create_payload(self, **overrides):
        payload = {
            "email": f"w12_created_{_unique_slug()}@example.com",
            "display_name": "Created User",
            "password": "testpass123",
        }
        payload.update(overrides)
        return payload

    # ── R2-S2 pins ─────────────────────────────────────────────────────────

    def test_non_admin_cannot_create_users(self):
        """Create must be gated like update/destroy — a plain user gets 403."""
        self.client.force_authenticate(user=self.regular_user_a)
        response = self.client.post(
            "/api/v1/users/", self._create_payload(), format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cross_tenant_create_is_rejected(self):
        """A TENANT_ADMIN creating a user in a FOREIGN tenant is 403 — the
        tenant must come from the request, never the payload."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.post(
            "/api/v1/users/",
            self._create_payload(tenant=str(self.tenant_b.id)),
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_tenant_admin_creates_in_their_own_tenant(self):
        """The happy path: no tenant in the payload, scoped to the actor."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.post(
            "/api/v1/users/", self._create_payload(), format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED, response.content
        created = User.objects.get(email=response.json()["email"])
        assert created.tenant_id == self.tenant_a.id

    def test_payload_tenant_matching_the_request_tenant_is_ignored(self):
        """A matching tenant in the payload is a read-only field — ignored,
        the request tenant wins."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.post(
            "/api/v1/users/",
            self._create_payload(tenant=str(self.tenant_a.id)),
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED, response.content
        created = User.objects.get(email=response.json()["email"])
        assert created.tenant_id == self.tenant_a.id

    def test_role_escalation_is_rejected(self):
        """A TENANT_ADMIN requesting a platform-level (tenant=None) role is
        403 — role_ids must lie inside the requester-assignable set."""
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.post(
            "/api/v1/users/",
            self._create_payload(role_ids=[str(self.platform_role.id)]),
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_foreign_tenant_role_is_rejected(self):
        """A role from ANOTHER tenant is outside the assignable set → 403."""
        foreign_role, _ = Role.objects.get_or_create(
            tenant=self.tenant_b,
            name="DATA_PROVIDER",
            defaults={"description": "Foreign provider role"},
        )
        self.client.force_authenticate(user=self.tenant_a_admin)
        response = self.client.post(
            "/api/v1/users/",
            self._create_payload(role_ids=[str(foreign_role.id)]),
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_platform_admin_can_create_in_any_tenant(self):
        """PLATFORM_ADMIN keeps the explicit cross-tenant create path."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.post(
            "/api/v1/users/",
            self._create_payload(tenant=str(self.tenant_b.id)),
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED, response.content
        created = User.objects.get(email=response.json()["email"])
        assert created.tenant_id == self.tenant_b.id
