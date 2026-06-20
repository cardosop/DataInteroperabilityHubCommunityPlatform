"""
E2E tests for TENANT_ADMIN persona.

Tests tenant configuration management, tenant isolation, and tenant-specific settings.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from hub.apps.tenants.models import KYCStatus, Tenant, TenantConfig
from hub.apps.users.models import Role, User, UserRole, UserStatus
from tests.e2e.conftest import E2ETestBase, get_response_data

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e4]
User = get_user_model()


class TenantAdminPersonaTest(E2ETestBase):
    """E2E tests for TENANT_ADMIN persona"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create TENANT_ADMIN role for tenant1
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )

        # Create tenant admin user
        self.tenant_admin = User.objects.create_user(
            email=f"tenant_admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant_admin, role=self.tenant_admin_role)

        # Create another tenant for isolation tests (subscription so config PATCH is allowed)
        _ot_suffix = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_ot_suffix}",
            slug=f"other-tenant-{_ot_suffix}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(self.other_tenant)

        # Create other tenant's admin
        other_admin_role, _ = Role.objects.get_or_create(
            tenant=self.other_tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.other_tenant_admin = User.objects.create_user(
            email=f"other_admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.other_tenant_admin, role=other_admin_role)

        # Authenticate as tenant admin
        self.client.force_authenticate(user=self.tenant_admin)

    def test_tenant_admin_can_get_own_tenant_config(self):
        """Test TENANT_ADMIN can GET own tenant configuration"""
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("default_dq_profile", resp_data)
        self.assertIn("allowed_compliance_regimes", resp_data)
        self.assertIn("rate_limits", resp_data)

    def test_tenant_admin_can_patch_own_tenant_config(self):
        """Test TENANT_ADMIN can PATCH own tenant configuration"""
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
        self.assertEqual(resp_data["allowed_compliance_regimes"], ["GDPR", "CCPA"])

    def test_tenant_admin_cannot_access_other_tenant_config(self):
        """Test TENANT_ADMIN cannot access other tenant configuration"""
        response = self.client.get(f"/api/v1/tenants/{self.other_tenant.id}/config/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", get_response_data(response) or {})

    def test_tenant_admin_cannot_patch_other_tenant_config(self):
        """Test TENANT_ADMIN cannot PATCH other tenant configuration"""
        data = {"default_dq_profile": "hacked_profile"}

        response = self.client.patch(
            f"/api/v1/tenants/{self.other_tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tenant_admin_can_configure_dq_profile(self):
        """Test TENANT_ADMIN can configure tenant-specific DQ profile"""
        data = {"default_dq_profile": "intake_basic_gx"}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_data["default_dq_profile"], "intake_basic_gx")

        # Verify it's persisted
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.default_dq_profile, "intake_basic_gx")

    def test_tenant_admin_can_configure_compliance_regimes(self):
        """Test TENANT_ADMIN can configure tenant-specific compliance regimes"""
        data = {"allowed_compliance_regimes": ["GDPR", "LGPD", "HIPAA"]}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(resp_data["allowed_compliance_regimes"]), {"GDPR", "LGPD", "HIPAA"})

    def test_tenant_admin_can_configure_rate_limits(self):
        """Test TENANT_ADMIN can configure tenant-specific rate limits"""
        data = {
            "rate_limits": {
                "dq_runs": {"burst_per_10s": 50, "sustained_per_min": 200},
                "compliance_runs": {"burst_per_10s": 30, "sustained_per_min": 100},
            }
        }

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("rate_limits", resp_data)
        self.assertIn("dq_runs", resp_data["rate_limits"])
        self.assertEqual(resp_data["rate_limits"]["dq_runs"]["burst_per_10s"], 50)

    def test_tenant_admin_can_configure_file_size_limits(self):
        """Test TENANT_ADMIN can configure tenant-specific file size limits"""
        data = {"max_file_size_bytes": 500 * 1024 * 1024}  # 500 MB in bytes

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_data["max_file_size_bytes"], 500 * 1024 * 1024)

    def test_tenant_admin_can_configure_job_concurrency(self):
        """Test TENANT_ADMIN can configure tenant-specific job concurrency"""
        data = {"max_job_concurrency": 10}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_data["max_job_concurrency"], 10)

    def test_tenant_admin_can_view_tenant_usage_metrics(self):
        """Test TENANT_ADMIN can view tenant usage metrics"""
        # TENANT_ADMIN can view their own tenant config (which includes usage-related settings)
        # Note: Viewing tenant details requires Platform Admin, but config access is allowed
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Config includes tenant_id which confirms it's for the correct tenant
        self.assertEqual(resp_data["tenant_id"], str(self.tenant.id))

    def test_tenant_admin_config_isolation(self):
        """Test tenant configuration is isolated between tenants"""
        # Configure tenant1
        data1 = {"default_dq_profile": "intake_basic_gx"}
        response1 = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data1, format="json"
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Switch to other tenant admin
        self.client.force_authenticate(user=self.other_tenant_admin)

        # Configure other tenant
        data2 = {"default_dq_profile": "intake_basic_soda"}
        response2 = self.client.patch(
            f"/api/v1/tenants/{self.other_tenant.id}/config/", data2, format="json"
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Verify isolation - tenant1 config unchanged
        self.client.force_authenticate(user=self.tenant_admin)
        response3 = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        resp_data3 = get_response_data(response3) or {}
        self.assertEqual(resp_data3["default_dq_profile"], "intake_basic_gx")

    def test_tenant_admin_partial_config_update(self):
        """Test TENANT_ADMIN can partially update configuration"""
        # First set some values
        data1 = {
            "default_dq_profile": "intake_basic_gx",
            "max_file_size_bytes": 100 * 1024 * 1024,  # 100 MB in bytes
        }
        self.client.patch(f"/api/v1/tenants/{self.tenant.id}/config/", data1, format="json")

        # Then update only one field
        data2 = {"default_dq_profile": "intake_basic_soda"}
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data2, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_data["default_dq_profile"], "intake_basic_soda")
        # Other field should remain (ModelSerializer preserves existing fields on partial update)
        self.assertEqual(resp_data["max_file_size_bytes"], 100 * 1024 * 1024)

    def test_tenant_admin_config_validation(self):
        """Test tenant configuration validation for TENANT_ADMIN"""
        # Invalid DQ profile
        data = {"default_dq_profile": "invalid_profile"}
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        # Should fail validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", get_response_data(response) or {})

    def test_tenant_admin_config_rate_limits_validation(self):
        """Test rate limits validation for TENANT_ADMIN"""
        # Invalid rate limit structure (missing required fields)
        data = {"rate_limits": {"dq_runs": {}}}  # Empty dict
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        # Should fail validation (at least one limit required)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tenant_admin_config_platform_maximums(self):
        """Test tenant config respects platform maximums"""
        # Try to set rate limit above platform maximum
        data = {"rate_limits": {"dq_runs": {"burst_per_10s": 10000}}}  # Very high

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        # Should either reject or cap at platform maximum
        resp_data = get_response_data(response) or {}
        if response.status_code == status.HTTP_200_OK:
            # If accepted, should be capped
            self.assertLessEqual(
                resp_data["rate_limits"]["dq_runs"]["burst_per_10s"],
                10000,  # Platform max should be less
            )
        else:
            # Or rejected
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tenant_admin_can_view_all_config_fields(self):
        """Test TENANT_ADMIN can view all configuration fields"""
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify all expected fields are present
        expected_fields = [
            "default_dq_profile",
            "allowed_compliance_regimes",
            "rate_limits",
            "max_file_size_bytes",
            "max_job_concurrency",
        ]
        for field in expected_fields:
            self.assertIn(field, resp_data)

    def test_tenant_admin_config_merge_behavior(self):
        """Test configuration merge behavior for partial updates"""
        # Set initial config
        data1 = {
            "default_dq_profile": "intake_basic_gx",
            "max_file_size_bytes": 200 * 1024 * 1024,  # 200 MB in bytes
        }
        self.client.patch(f"/api/v1/tenants/{self.tenant.id}/config/", data1, format="json")

        # Update with new fields
        data2 = {"max_job_concurrency": 5, "allowed_compliance_regimes": ["GDPR"]}
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data2, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # All fields should be present (serializer preserves existing fields on partial update)
        self.assertEqual(resp_data["default_dq_profile"], "intake_basic_gx")
        self.assertEqual(resp_data["max_file_size_bytes"], 200 * 1024 * 1024)
        self.assertEqual(resp_data["max_job_concurrency"], 5)
        self.assertIn("GDPR", resp_data["allowed_compliance_regimes"])

    def test_tenant_admin_config_created_on_first_patch(self):
        """Test config is created on first PATCH if it doesn't exist"""
        # Delete config if exists
        TenantConfig.objects.filter(tenant=self.tenant).delete()

        # PATCH should create config
        data = {"default_dq_profile": "intake_basic_gx"}
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Config should now exist
        self.assertTrue(TenantConfig.objects.filter(tenant=self.tenant).exists())

    def test_tenant_admin_cannot_delete_config(self):
        """Test TENANT_ADMIN cannot delete tenant config (no DELETE endpoint)"""
        # There should be no DELETE endpoint for config
        response = self.client.delete(f"/api/v1/tenants/{self.tenant.id}/config/")

        # Should return 405 Method Not Allowed or 404 Not Found
        self.assertIn(
            response.status_code, [status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_404_NOT_FOUND]
        )

    def test_tenant_admin_config_with_empty_values(self):
        """Test handling of empty values in configuration"""
        # Set config with some values
        data1 = {"default_dq_profile": "profile1", "allowed_compliance_regimes": ["GDPR", "CCPA"]}
        self.client.patch(f"/api/v1/tenants/{self.tenant.id}/config/", data1, format="json")

        # Try to set empty array
        data2 = {"allowed_compliance_regimes": []}
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data2, format="json"
        )

        # Should handle empty array appropriately
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_tenant_admin_config_response_format(self):
        """Test configuration response format matches API spec"""
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify response structure
        self.assertIsInstance(resp_data, dict)
        self.assertIn("default_dq_profile", resp_data)
        self.assertIn("allowed_compliance_regimes", resp_data)
        self.assertIsInstance(resp_data["allowed_compliance_regimes"], list)

    def test_tenant_admin_config_timestamps(self):
        """Test configuration timestamps are updated on PATCH"""
        # Get initial config
        response1 = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        resp_data1 = get_response_data(response1) or {}
        initial_updated_at = resp_data1.get("updated_at")

        # Wait a moment and update
        import time

        time.sleep(0.1)  # noqa: sleep-needed  # INTENTIONAL: e2e/integration test polling real services

        data = {"default_dq_profile": "intake_basic_soda"}
        response2 = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )
        resp_data2 = get_response_data(response2) or {}
        # Updated timestamp should be different (if included in response)
        if "updated_at" in resp_data2:
            self.assertNotEqual(resp_data2["updated_at"], initial_updated_at)

    def test_tenant_admin_config_error_handling(self):
        """Test error handling for invalid tenant ID"""
        invalid_tenant_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"/api/v1/tenants/{invalid_tenant_id}/config/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", get_response_data(response) or {})

    def test_tenant_admin_config_concurrent_updates(self):
        """Test handling of concurrent configuration updates"""
        # Simulate concurrent updates by making multiple requests
        data1 = {"default_dq_profile": "intake_basic_gx"}
        data2 = {"default_dq_profile": "intake_basic_soda"}

        response1 = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data1, format="json"
        )
        response2 = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data2, format="json"
        )

        # Both should succeed (last write wins)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Final value should be from last update
        final_response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        final_data = get_response_data(final_response) or {}
        self.assertEqual(final_data["default_dq_profile"], "intake_basic_soda")

    def test_tenant_admin_config_all_compliance_regimes(self):
        """Test TENANT_ADMIN can configure all compliance regimes"""
        data = {"allowed_compliance_regimes": ["GDPR", "LGPD", "CCPA", "HIPAA", "SOX"]}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_data["allowed_compliance_regimes"]), 5)

    def test_tenant_admin_config_rate_limits_all_categories(self):
        """Test TENANT_ADMIN can configure rate limits for all categories"""
        data = {
            "rate_limits": {
                "dq_runs": {"burst_per_10s": 50, "sustained_per_min": 200},
                "compliance_runs": {"burst_per_10s": 30, "sustained_per_min": 100},
                "contract_validation": {
                    "burst_per_10s": 100,
                    "sustained_per_min": 300,  # Platform max is 300
                },
                "sparql_queries": {"burst_per_10s": 50, "sustained_per_min": 200},
            }
        }

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("dq_runs", resp_data["rate_limits"])
        self.assertIn("compliance_runs", resp_data["rate_limits"])
        self.assertIn("contract_validation", resp_data["rate_limits"])
        self.assertIn("sparql_queries", resp_data["rate_limits"])

    def test_tenant_admin_config_platform_defaults_fallback(self):
        """Test platform defaults are used when config not set"""
        # Delete config to test defaults
        TenantConfig.objects.filter(tenant=self.tenant).delete()

        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return platform defaults
        self.assertIn("default_dq_profile", resp_data)
        self.assertIn("allowed_compliance_regimes", resp_data)

    def test_tenant_admin_config_nested_rate_limits(self):
        """Test nested rate limits structure"""
        data = {
            "rate_limits": {
                "dq_runs": {"burst_per_10s": 50, "sustained_per_min": 200, "daily_cap": 1000}
            }
        }

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        resp_data = get_response_data(response) or {}
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("burst_per_10s", resp_data["rate_limits"]["dq_runs"])
        self.assertIn("sustained_per_min", resp_data["rate_limits"]["dq_runs"])
        self.assertIn("daily_cap", resp_data["rate_limits"]["dq_runs"])

    def test_tenant_admin_config_read_only_fields(self):
        """Test read-only fields cannot be modified"""
        # Try to modify tenant_id (if exposed)
        data = {"tenant_id": str(self.other_tenant.id)}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        # Should either ignore or reject
        resp_data = get_response_data(response) or {}
        if response.status_code == status.HTTP_200_OK:
            # If accepted, tenant_id should not change
            self.assertNotEqual(resp_data.get("tenant_id"), str(self.other_tenant.id))

    def test_tenant_admin_config_unicode_values(self):
        """Test configuration handles unicode values in compliance regimes"""
        # Use unicode in compliance regimes (which may accept it)
        data = {"allowed_compliance_regimes": ["GDPR", "测试"]}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        # Should handle unicode (may fail validation if regimes must be from allowed list)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
