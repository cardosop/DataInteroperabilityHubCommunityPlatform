"""
Unit tests for tenant "me" endpoints: GET /tenants/me/usage/, GET/PATCH /tenants/me/config/.

Phase 8 — Tenant Usage & Config.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus

# Use transaction=False so TenantSuspensionMiddleware sees subscription created in setUp
# (with transaction=True the middleware can use a different connection and returns 403 for PATCH)
pytestmark = pytest.mark.django_db(transaction=True)


class TenantMeUsageViewTest(TestCase):
    """Test GET /api/v1/tenants/me/usage/"""

    def setUp(self):
        self.client = APIClient()
        uid = str(uuid.uuid4())[:8]
        uid = uuid.uuid4().hex[:8]
        # Usage data (plans, limits, counters) is billing-derived — core-only
        # deployments serve a minimal payload by design.
        from hub.apps.manifest import is_core_only

        if is_core_only():
            self.skipTest(
                "tenant usage payload is paid-layer (billing limit_registry) — minimal in core-only mode"
            )
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        ensure_tenant_has_active_subscription(self.tenant)
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        self.tenant_admin = User.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant_admin, role=self.admin_role)
        self.provider_user = User.objects.create_user(
            email="provider@test.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.provider_user, role=self.provider_role)

    def test_me_usage_success_tenant_admin(self):
        """Success: TENANT_ADMIN gets usage for own tenant."""
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.get("/api/v1/tenants/me/usage/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tenant_id"], str(self.tenant.id))
