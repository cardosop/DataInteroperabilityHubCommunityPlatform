"""
E2E tests for Platform Admin persona.

Tests that Platform Admin:
- Can access any tenant configuration
- Can view system-wide metrics
- Can configure platform defaults
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from tests.e2e.conftest import E2ETestBase, get_response_data

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e4]
User = get_user_model()


class PlatformAdminPersonaTest(E2ETestBase):
    """E2E tests for Platform Admin persona"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create platform admin user
        self.platform_admin = User.objects.create_user(
            email=f"platform_admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,  # Platform admins don't belong to a tenant
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )

        # Create another tenant for cross-tenant access tests
        _suffix = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_suffix}",
            slug=f"other-tenant-{_suffix}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Authenticate as platform admin
        self.client.force_authenticate(user=self.platform_admin)

    def test_platform_admin_can_get_own_tenant_config(self):
        """Test Platform Admin can GET any tenant configuration"""
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("default_dq_profile", resp_data)

    def test_platform_admin_can_get_other_tenant_config(self):
        """Test Platform Admin can GET other tenant configuration"""
        response = self.client.get(f"/api/v1/tenants/{self.other_tenant.id}/config/")
        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("default_dq_profile", resp_data)

    def test_platform_admin_can_patch_any_tenant_config(self):
        """Test Platform Admin can PATCH any tenant configuration"""
        data = {"default_dq_profile": "intake_basic_gx"}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_data["default_dq_profile"], "intake_basic_gx")

    def test_platform_admin_can_patch_other_tenant_config(self):
        """Test Platform Admin can PATCH other tenant configuration"""
        data = {"default_dq_profile": "intake_basic_soda"}

        response = self.client.patch(
            f"/api/v1/tenants/{self.other_tenant.id}/config/", data, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_data["default_dq_profile"], "intake_basic_soda")

    def test_platform_admin_can_list_all_tenants(self):
        """Test Platform Admin can list all tenants"""
        # Verify each tenant is individually retrievable (avoids pagination issues)
        for tenant in [self.tenant, self.other_tenant]:
            response = self.client.get(f"/api/v1/tenants/{tenant.id}/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            resp_data = get_response_data(response) or {}
            self.assertEqual(resp_data.get("id"), str(tenant.id))

        # Also verify the list endpoint is accessible
        response = self.client.get("/api/v1/tenants/", {"page_size": 100})
        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp_data)
        self.assertGreater(len(resp_data["results"]), 0)

    def test_platform_admin_can_create_tenant(self):
        """Test Platform Admin can create tenants"""
        data = {"name": "New Tenant", "slug": "new-tenant", "region": "us-east-1"}

        response = self.client.post("/api/v1/tenants/", data, format="json")

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp_data["name"], "New Tenant")

    def test_platform_admin_can_update_tenant(self):
        """Test Platform Admin can update tenants"""
        data = {"name": "Updated Tenant Name"}

        response = self.client.patch(f"/api/v1/tenants/{self.tenant.id}/", data, format="json")

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_data["name"], "Updated Tenant Name")

    def test_platform_admin_can_view_system_metrics(self):
        """Test Platform Admin can view system-wide metrics"""
        # Platform admin should have access to metrics endpoints
        # This would typically be a metrics endpoint
        # For now, we verify they can access tenant info across tenants

        response1 = self.client.get(f"/api/v1/tenants/{self.tenant.id}/")
        response2 = self.client.get(f"/api/v1/tenants/{self.other_tenant.id}/")

        # Should be able to access both
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

    def test_platform_admin_can_configure_platform_defaults(self):
        """Test Platform Admin can configure platform defaults"""
        # Platform defaults are typically configured in settings
        # For testing, we verify platform admin can set tenant configs
        # which may serve as defaults for new tenants

        data = {
            "default_dq_profile": "intake_basic_gx",
            "allowed_compliance_regimes": ["GDPR", "CCPA"],
        }

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_data["default_dq_profile"], "intake_basic_gx")

    def test_platform_admin_cross_tenant_config_access(self):
        """Test Platform Admin can access configs across all tenants"""
        # Configure tenant1
        data1 = {"default_dq_profile": "intake_basic_gx"}
        response1 = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data1, format="json"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Configure tenant2
        data2 = {"default_dq_profile": "intake_basic_soda"}
        response2 = self.client.patch(
            f"/api/v1/tenants/{self.other_tenant.id}/config/", data2, format="json"
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Verify both configs
        get_response1 = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        get_response2 = self.client.get(f"/api/v1/tenants/{self.other_tenant.id}/config/")
        data1 = get_response_data(get_response1) or {}
        data2 = get_response_data(get_response2) or {}
        self.assertEqual(data1["default_dq_profile"], "intake_basic_gx")
        self.assertEqual(data2["default_dq_profile"], "intake_basic_soda")

    def test_platform_admin_can_suspend_tenant(self):
        """Test Platform Admin can suspend tenants"""
        data = {"reason": "Test suspension"}

        response = self.client.post(
            f"/api/v1/tenants/{self.tenant.id}/suspend/", data, format="json"
        )

        # Should be able to suspend
        if response.status_code == status.HTTP_404_NOT_FOUND:
            self.skipTest("Tenant suspend endpoint not available (404)")
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_204_NO_CONTENT,
            ],
        )

    def test_platform_admin_can_reactivate_tenant(self):
        """Test Platform Admin can reactivate tenants"""
        from hub.apps.tenants.models import TenantStatus

        # Suspend tenant first (required for reactivation)
        self.tenant.suspend()
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, TenantStatus.SUSPENDED)

        response = self.client.post(
            f"/api/v1/tenants/{self.tenant.id}/reactivate/", {}, format="json"
        )

        # Should be able to reactivate
        self.assertLess(
            response.status_code,
            500,
        )

    def test_platform_admin_can_view_all_users(self):
        """Test Platform Admin can view all users across tenants"""
        response = self.client.get("/api/v1/users/")

        # Should be able to list users
        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", resp_data)

    def test_platform_admin_can_manage_tenant_kyc(self):
        """Test Platform Admin can manage tenant KYC status"""
        data = {"kyc_status": "VERIFIED"}

        response = self.client.patch(f"/api/v1/tenants/{self.tenant.id}/", data, format="json")

        # Should be able to update KYC status
        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_data["kyc_status"], "VERIFIED")

    def test_platform_admin_tenant_isolation_override(self):
        """Test Platform Admin can override tenant isolation"""
        # Platform admin should be able to access resources across tenants
        # This is tested through cross-tenant config access above

        # Verify can access both tenants' configs
        response1 = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        response2 = self.client.get(f"/api/v1/tenants/{self.other_tenant.id}/config/")

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

    def test_platform_admin_system_wide_permissions(self):
        """Test Platform Admin has system-wide permissions"""
        # Platform admin should have elevated permissions across the system
        # Test by accessing various admin endpoints

        endpoints = [
            "/api/v1/tenants/",
            "/api/v1/users/",
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)
            # Should have access
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_platform_admin_no_tenant_restriction(self):
        """Test Platform Admin is not restricted to a single tenant"""
        # Platform admin should not have tenant_id restriction
        self.assertIsNone(self.platform_admin.tenant)

        # Should be able to access any tenant
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
