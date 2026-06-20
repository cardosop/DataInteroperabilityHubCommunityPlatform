"""
Security tests for personal tenant registration (useronboardfix 2.2.1).

Tests isolation, privilege escalation prevention, rate limits, and
registration error handling. Uses real DB and auth; no mocks/stubs.
"""

import uuid

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, User

pytestmark = [
    pytest.mark.django_db(transaction=True),
]


class PersonalTenantSecurityTest(TestCase):
    """Security tests for personal tenant users."""

    def setUp(self):
        """Ensure FREE plan exists for personal tenant creation."""
        call_command("seed_default_plans")
        self.client = APIClient()

    def test_personal_tenant_user_cannot_access_other_tenant(self):
        """User with personal tenant cannot access another tenant's resources."""
        email = f"sec-{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePass123"
        name = "Security User"

        reg = self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "password": password, "name": name},
            format="json",
        )
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)
        personal_tenant_id = reg.data["tenant_id"]

        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")

        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {uuid.uuid4().hex[:8]}",
            slug=f"other-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key="other-asset",
            name="Other Asset",
            domain="test",
            status=AssetStatus.ACTIVE,
        )

        resp = self.client.get(f"/api/v1/assets/{other_asset.id}/")
        self.assertIn(
            resp.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
            "Cross-tenant asset access must be 403 or 404",
        )
        self.assertNotEqual(str(other_tenant.id), str(personal_tenant_id))

    def test_personal_tenant_user_cannot_escalate_to_tenant_admin(self):
        """Non-admin user cannot assign TENANT_ADMIN to self."""
        email = f"escalate-{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePass123"
        name = "Escalate User"

        reg = self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "password": password, "name": name},
            format="json",
        )
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)

        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")

        user = User.objects.get(email=email)
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant_id=user.tenant_id,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )

        resp = self.client.post(
            f"/api/v1/users/{user.id}/roles/",
            {"role_id": str(tenant_admin_role.id), "action": "assign"},
            format="json",
        )
        self.assertEqual(
            resp.status_code,
            status.HTTP_403_FORBIDDEN,
            "Non-admin user must not be able to assign TENANT_ADMIN to self",
        )
        user.refresh_from_db()
        role_names = list(user.user_roles.values_list("role__name", flat=True))
        self.assertNotIn(
            "TENANT_ADMIN",
            role_names,
            "User must not have TENANT_ADMIN after forbidden assign attempt",
        )

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_personal_tenant_rate_limits_applied(self):
        """Personal tenant user is subject to rate limits on auth endpoints."""
        from hub.apps.tenants.models import TenantConfig

        email = f"ratelimit-{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePass123"
        name = "Rate Limit User"

        reg = self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "password": password, "name": name},
            format="json",
        )
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)
        tenant_id = reg.data["tenant_id"]

        TenantConfig.objects.update_or_create(
            tenant_id=tenant_id,
            defaults={
                "rate_limits": {
                    "auth": {"10": 1, "60": 2},
                },
            },
        )

        login = self.client.post(
            "/api/v1/auth/login/",
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")

        first = self.client.get("/api/v1/auth/me/")
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = self.client.get("/api/v1/auth/me/")
        self.assertEqual(
            second.status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Second request within burst window must be rate limited",
        )

    def test_register_does_not_leak_tenant_slug_collision_info(self):
        """Register error on tenant collision must not leak slug or collision details."""
        from hub.apps.core.services.base import ValidationError as ServiceValidationError
        from hub.apps.tenants.services import PersonalTenantService

        call_command("seed_default_plans")
        email = f"leak-{uuid.uuid4().hex[:8]}@example.com"
        name = f"Personal - {email}"

        Tenant.objects.create(
            name=name,
            slug=f"personal-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        service = PersonalTenantService()
        with self.assertRaises(ServiceValidationError):
            service.create_personal_tenant_for_user(email=email, display_name="Leak User")

        exc = cm.exception
        self.assertEqual(getattr(exc, "code", None), "TENANT_CREATE_COLLISION")
        detail = getattr(exc, "message", str(exc))
        self.assertNotIn(
            "slug",
            detail.lower(),
            "Service error must not leak slug in collision",
        )
        self.assertNotIn(
            "collision",
            detail.lower(),
            "Service error must not leak collision type",
        )
        self.assertNotIn(
            "personal-",
            detail,
            "Service error must not leak personal tenant slug pattern",
        )

    def test_register_http_error_does_not_leak_tenant_slug_collision_info(self):
        """HTTP register error on collision must not leak slug/collision in response."""
        call_command("seed_default_plans")
        email = f"http-leak-{uuid.uuid4().hex[:8]}@example.com"
        name = f"Personal - {email}"

        Tenant.objects.create(
            name=name,
            slug=f"personal-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        resp = self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "password": "SecurePass123", "name": "HTTP Leak User"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        data = resp.json()
        text = resp.content.decode("utf-8", errors="replace")

        for leak in ("slug", "collision", "TENANT_CREATE_COLLISION"):
            self.assertNotIn(
                leak.lower(),
                text.lower(),
                f"HTTP register error must not leak '{leak}' in response",
            )
        self.assertIn(
            "Registration failed",
            data.get("detail", data.get("error", "")),
            "Must return generic registration failure message",
        )
        self.assertNotEqual(
            data.get("code", ""),
            "TENANT_CREATE_COLLISION",
            "HTTP code must be sanitized to REGISTRATION_FAILED",
        )
