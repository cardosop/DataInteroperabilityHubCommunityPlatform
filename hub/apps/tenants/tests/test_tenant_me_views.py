"""
Unit tests for tenant "me" endpoints: GET /tenants/me/usage/, GET/PATCH /tenants/me/config/.

Phase 8 — Tenant Usage & Config.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.users.models import Role, User, UserRole, UserStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

# Use transaction=False so TenantSuspensionMiddleware sees subscription created in setUp
# (with transaction=True the middleware can use a different connection and returns 403 for PATCH)
pytestmark = pytest.mark.django_db(transaction=True)


class TenantMeUsageViewTest(TestCase):
    """Test GET /api/v1/tenants/me/usage/"""

    def setUp(self):
        self.client = APIClient()
        uid = str(uuid.uuid4())[:8]
        uid = uuid.uuid4().hex[:8]
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
        # The usage response uses dynamic *_usage keys from RESOURCE_COUNTERS.
        # Legacy top-level keys (storage_bytes, storage_gb, api_calls_this_month)
        # were replaced by individual counter keys under their own names.
        self.assertIn("storage_gb_usage", response.data)
        self.assertIn("plan_limits", response.data)
        self.assertIn("usage_percentages", response.data)

    def test_me_usage_success_data_provider(self):
        """Success: Any tenant user gets usage (authenticated with tenant context)."""
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.get("/api/v1/tenants/me/usage/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tenant_id"], str(self.tenant.id))

    def test_me_usage_401_unauthenticated(self):
        """Failure: 401 when unauthenticated."""
        response = self.client.get("/api/v1/tenants/me/usage/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_usage_400_when_user_has_no_tenant(self):
        """Failure: 400 when user has no tenant context."""
        user_no_tenant = User.objects.create_user(
            email="no-tenant@test.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=user_no_tenant)
        response = self.client.get("/api/v1/tenants/me/usage/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Tenant context required", str(response.data.get("error", "")))


class TenantMeConfigViewTest(TestCase):
    """Test GET/PATCH /api/v1/tenants/me/config/"""

    def setUp(self):
        self.client = APIClient()
        uid = str(uuid.uuid4())[:8]
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.other_tenant = Tenant.objects.create(name=f"Other {uid}", slug=f"other-tenant-{uid}")
        ensure_tenant_has_active_subscription(self.tenant)
        ensure_tenant_has_active_subscription(self.other_tenant)
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
            email=f"admin-{uid}@test.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant_admin, role=self.admin_role)
        self.provider_user = User.objects.create_user(
            email=f"provider-{uid}@test.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.provider_user, role=self.provider_role)
        self.platform_admin = User.objects.create_user(
            email=f"platform-{uid}@test.com",
            password="testpass123",
            is_platform_admin=True,
        )

    def test_me_config_get_success_tenant_admin(self):
        """Success: TENANT_ADMIN gets config for own tenant."""
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.get("/api/v1/tenants/me/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tenant_id"], str(self.tenant.id))
        self.assertIn("default_dq_profile", response.data)
        self.assertIn("allowed_compliance_regimes", response.data)

    def test_me_config_get_success_platform_admin(self):
        """Success: Platform Admin gets config for their tenant (from user.tenant_id)."""
        self.platform_admin.tenant = self.tenant
        self.platform_admin.save()
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get("/api/v1/tenants/me/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["tenant_id"], str(self.tenant.id))

    def test_me_config_get_403_data_provider(self):
        """Failure: 403 when user lacks TENANT_ADMIN role."""
        self.client.force_authenticate(user=self.provider_user)
        response = self.client.get("/api/v1/tenants/me/config/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_config_get_401_unauthenticated(self):
        """Failure: 401 when unauthenticated."""
        response = self.client.get("/api/v1/tenants/me/config/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_config_patch_success(self):
        """Success: TENANT_ADMIN patches config."""
        self.client.force_authenticate(user=self.tenant_admin)
        data = {"default_dq_profile": "intake_basic_soda"}
        response = self.client.patch("/api/v1/tenants/me/config/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["default_dq_profile"], "intake_basic_soda")
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.default_dq_profile, "intake_basic_soda")

    def test_me_config_patch_multiple_fields(self):
        """Success: PATCH updates multiple fields."""
        self.client.force_authenticate(user=self.tenant_admin)
        data = {
            "default_dq_profile": "intake_basic_soda",
            "data_retention_days": 365,
            "max_job_concurrency": 5,
        }
        response = self.client.patch("/api/v1/tenants/me/config/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["default_dq_profile"], "intake_basic_soda")
        self.assertEqual(response.data["data_retention_days"], 365)
        self.assertEqual(response.data["max_job_concurrency"], 5)

    def test_me_config_patch_400_invalid_dq_profile(self):
        """Failure: 400 with invalid DQ profile."""
        self.client.force_authenticate(user=self.tenant_admin)
        data = {"default_dq_profile": "invalid_profile"}
        response = self.client.patch("/api/v1/tenants/me/config/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_config_patch_403_data_provider(self):
        """Failure: 403 when user lacks TENANT_ADMIN role."""
        self.client.force_authenticate(user=self.provider_user)
        data = {"default_dq_profile": "intake_basic_soda"}
        response = self.client.patch("/api/v1/tenants/me/config/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_config_400_when_user_has_no_tenant(self):
        """Failure: 400 when user has no tenant context."""
        user_no_tenant = User.objects.create_user(
            email="no-tenant-config@test.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=user_no_tenant)
        response = self.client.get("/api/v1/tenants/me/config/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Tenant context required", str(response.data.get("error", "")))

    def test_tenant_admin_usage_then_config_flow(self):
        """Integration: Tenant admin fetches usage then config in sequence."""
        self.client.force_authenticate(user=self.tenant_admin)
        usage_resp = self.client.get("/api/v1/tenants/me/usage/")
        self.assertEqual(usage_resp.status_code, status.HTTP_200_OK)
        config_resp = self.client.get("/api/v1/tenants/me/config/")
        self.assertEqual(config_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(usage_resp.data["tenant_id"], config_resp.data["tenant_id"])

    def test_me_config_get_includes_trust_signals_enabled(self):
        """Phase 11: GET config includes trust_signals_enabled (platform default True)."""
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.get("/api/v1/tenants/me/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("trust_signals_enabled", response.data)
        self.assertIs(response.data["trust_signals_enabled"], True)

    def test_me_config_patch_trust_signals_enabled_persistence(self):
        """Phase 11: PATCH trust_signals_enabled persists and returns updated value."""
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.patch(
            "/api/v1/tenants/me/config/",
            {"trust_signals_enabled": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIs(response.data["trust_signals_enabled"], False)

        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertIs(config.trust_signals_enabled, False)

        # Re-enable
        response2 = self.client.patch(
            "/api/v1/tenants/me/config/",
            {"trust_signals_enabled": True},
            format="json",
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertIs(response2.data["trust_signals_enabled"], True)
        config.refresh_from_db()
        self.assertIs(config.trust_signals_enabled, True)

    def test_me_config_get_includes_versioning_enabled(self):
        """Phase 12: GET config includes versioning_enabled (platform default True)."""
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.get("/api/v1/tenants/me/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("versioning_enabled", response.data)
        self.assertIs(response.data["versioning_enabled"], True)

    def test_me_config_patch_versioning_enabled_persistence(self):
        """Phase 12: PATCH versioning_enabled persists and returns updated value."""
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.patch(
            "/api/v1/tenants/me/config/",
            {"versioning_enabled": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIs(response.data["versioning_enabled"], False)

        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertIs(config.versioning_enabled, False)

        # Re-enable
        response2 = self.client.patch(
            "/api/v1/tenants/me/config/",
            {"versioning_enabled": True},
            format="json",
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertIs(response2.data["versioning_enabled"], True)
        config.refresh_from_db()
        self.assertIs(config.versioning_enabled, True)

    def test_me_config_get_includes_workflows_enabled(self):
        """Phase 14: GET config includes workflows_enabled (platform default True)."""
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.get("/api/v1/tenants/me/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("workflows_enabled", response.data)
        self.assertIs(response.data["workflows_enabled"], True)

    def test_me_config_patch_workflows_enabled_persistence(self):
        """Phase 14: PATCH workflows_enabled persists and returns updated value."""
        self.client.force_authenticate(user=self.tenant_admin)
        response = self.client.patch(
            "/api/v1/tenants/me/config/",
            {"workflows_enabled": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIs(response.data["workflows_enabled"], False)

        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertIs(config.workflows_enabled, False)

        # Re-enable
        response2 = self.client.patch(
            "/api/v1/tenants/me/config/",
            {"workflows_enabled": True},
            format="json",
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertIs(response2.data["workflows_enabled"], True)
        config.refresh_from_db()
        self.assertIs(config.workflows_enabled, True)
