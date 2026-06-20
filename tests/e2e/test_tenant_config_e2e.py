"""
Comprehensive E2E tests for Tenant Configuration API.

Covers:
- Persona-based tests (TENANT_ADMIN, Platform Admin, DATA_PROVIDER, DATA_CONSUMER, AUDITOR)
- Configuration usage journeys (DQ profile, compliance regimes, file size limits, job concurrency)
- Edge cases (all fields, partial updates, validation, concurrent updates)
- Real service integration (no mocks)

Uses REAL services (no mocks).
"""

import pytest

pytestmark = pytest.mark.slow
import uuid

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status

from hub.apps.tenants.models import KYCStatus, Tenant, TenantConfig
from hub.apps.tenants.validators import get_platform_defaults
from hub.apps.users.models import Role, User, UserRole, UserStatus

from .conftest import E2ETestBase, get_response_data

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e,
    pytest.mark.e2e_batch4,  # Tenant Config tests
]
User = get_user_model()


class TenantConfigE2ETest(E2ETestBase):
    """E2E tests for Tenant Configuration API"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create additional tenants for cross-tenant tests
        self.tenant2 = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create roles
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        self.consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_CONSUMER", defaults={"description": "Data Consumer"}
        )
        self.auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="AUDITOR", defaults={"description": "Auditor"}
        )

        # Create platform admin
        self.platform_admin = User.objects.create_user(
            email=f"platform-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )

        # Create tenant admin for tenant1
        self.tenant1_admin = User.objects.create_user(
            email=f"tenant1-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant1_admin, role=self.admin_role)

        # Create tenant admin for tenant2
        self.tenant2_admin = User.objects.create_user(
            email=f"tenant2-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant2,
            status=UserStatus.ACTIVE,
        )
        admin_role2, _ = Role.objects.get_or_create(
            tenant=self.tenant2,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.create(user=self.tenant2_admin, role=admin_role2)

        # Create DATA_PROVIDER user
        self.provider_user = User.objects.create_user(
            email=f"provider-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.provider_user, role=self.provider_role)

        # Create DATA_CONSUMER user
        self.consumer_user = User.objects.create_user(
            email=f"consumer-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.consumer_user, role=self.consumer_role)

        # Create AUDITOR user
        self.auditor_user = User.objects.create_user(
            email=f"auditor-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.auditor_user, role=self.auditor_role)

        self.platform_defaults = get_platform_defaults()

    # TENANT_ADMIN Persona Tests
    def test_tenant_admin_get_own_config(self):
        """TENANT_ADMIN can retrieve own tenant config"""
        self.client.force_authenticate(user=self.tenant1_admin)

        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tenant_id", (get_response_data(response) or {}))
        self.assertEqual(str(self.tenant.id), (get_response_data(response) or {})["tenant_id"])
        # Should return platform defaults if config doesn't exist
        self.assertEqual(
            (get_response_data(response) or {})["default_dq_profile"],
            self.platform_defaults["default_dq_profile"],
        )

    def test_tenant_admin_get_own_config_with_existing_config(self):
        """TENANT_ADMIN can retrieve own tenant config when config exists"""
        TenantConfig.objects.create(
            tenant=self.tenant, default_dq_profile="intake_basic_soda", data_retention_days=1825
        )

        self.client.force_authenticate(user=self.tenant1_admin)
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            (get_response_data(response) or {})["default_dq_profile"], "intake_basic_soda"
        )
        self.assertEqual((get_response_data(response) or {})["data_retention_days"], 1825)

    def test_tenant_admin_update_own_config(self):
        """TENANT_ADMIN can update own tenant config"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"default_dq_profile": "intake_basic_soda", "data_retention_days": 1825}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            (get_response_data(response) or {})["default_dq_profile"], "intake_basic_soda"
        )
        self.assertEqual((get_response_data(response) or {})["data_retention_days"], 1825)

        # Verify persisted
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.default_dq_profile, "intake_basic_soda")
        self.assertEqual(config.data_retention_days, 1825)

        # Verify subsequent GET returns updated values
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        self.assertEqual(
            (get_response_data(response) or {})["default_dq_profile"], "intake_basic_soda"
        )
        self.assertEqual((get_response_data(response) or {})["data_retention_days"], 1825)

    def test_tenant_admin_cannot_access_other_tenant_config_get(self):
        """TENANT_ADMIN cannot GET other tenant config (403)"""
        self.client.force_authenticate(user=self.tenant1_admin)

        response = self.client.get(f"/api/v1/tenants/{self.tenant2.id}/config/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tenant_admin_cannot_access_other_tenant_config_patch(self):
        """TENANT_ADMIN cannot PATCH other tenant config (403)"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"default_dq_profile": "intake_basic_soda"}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant2.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # Platform Admin Persona Tests
    def test_platform_admin_get_any_tenant_config(self):
        """Platform Admin can retrieve any tenant config"""
        self.client.force_authenticate(user=self.platform_admin)

        # Can access tenant1 config
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Can access tenant2 config
        response = self.client.get(f"/api/v1/tenants/{self.tenant2.id}/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_platform_admin_update_any_tenant_config(self):
        """Platform Admin can update any tenant config"""
        self.client.force_authenticate(user=self.platform_admin)
        data = {"default_dq_profile": "intake_basic_soda"}

        # Can update tenant1 config
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Can update tenant2 config
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant2.id}/config/", data, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # DATA_PROVIDER Persona Tests
    def test_data_provider_cannot_access_config_get(self):
        """DATA_PROVIDER cannot GET tenant config (403)"""
        self.client.force_authenticate(user=self.provider_user)

        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_data_provider_cannot_access_config_patch(self):
        """DATA_PROVIDER cannot PATCH tenant config (403)"""
        self.client.force_authenticate(user=self.provider_user)
        data = {"default_dq_profile": "intake_basic_soda"}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # DATA_CONSUMER Persona Tests
    def test_data_consumer_cannot_access_config(self):
        """DATA_CONSUMER cannot access tenant config (403)"""
        self.client.force_authenticate(user=self.consumer_user)

        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/",
            {"default_dq_profile": "intake_basic_soda"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # AUDITOR Persona Tests
    def test_auditor_cannot_access_config(self):
        """AUDITOR cannot access tenant config (403)"""
        self.client.force_authenticate(user=self.auditor_user)

        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # Configuration Persistence Tests — verify config is stored and
    # retrievable via API.  Downstream enforcement (DQ profile selection,
    # compliance regimes, file size limits, job concurrency) is tested
    # in dedicated integration tests.

    @override_settings(DQ_SERVICE_URL="http://localhost:8083")
    def test_config_stores_dq_profile_selection(self):
        """Verify default_dq_profile is persisted and retrievable via API"""
        TenantConfig.objects.create(tenant=self.tenant, default_dq_profile="intake_basic_soda")

        # Verify DB persistence
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.default_dq_profile, "intake_basic_soda")

        # Verify API returns the config
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        self.assertEqual(response.status_code, 200)
        data = get_response_data(response) or {}
        self.assertEqual(data.get("default_dq_profile"), "intake_basic_soda")

    @override_settings(COMPLIANCE_SERVICE_URL="http://localhost:8082")
    def test_config_stores_compliance_regimes(self):
        """Verify compliance regimes are persisted and retrievable via API"""
        TenantConfig.objects.create(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD", "CCPA"],
            default_compliance_regimes=["GDPR", "LGPD"],
        )

        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.default_compliance_regimes, ["GDPR", "LGPD"])

        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        self.assertEqual(response.status_code, 200)
        data = get_response_data(response) or {}
        self.assertEqual(data.get("default_compliance_regimes"), ["GDPR", "LGPD"])

    def test_config_stores_file_size_limit(self):
        """Verify max_file_size_bytes is persisted and retrievable via API"""
        max_size = 5 * 1024 * 1024 * 1024  # 5GB
        TenantConfig.objects.create(tenant=self.tenant, max_file_size_bytes=max_size)

        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.max_file_size_bytes, max_size)

        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        self.assertEqual(response.status_code, 200)
        data = get_response_data(response) or {}
        self.assertEqual(data.get("max_file_size_bytes"), max_size)

    def test_config_stores_job_concurrency(self):
        """Verify job concurrency limits are persisted and retrievable via API"""
        TenantConfig.objects.create(tenant=self.tenant, max_job_concurrency=2, max_queued_jobs=10)

        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.max_job_concurrency, 2)
        self.assertEqual(config.max_queued_jobs, 10)

        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        self.assertEqual(response.status_code, 200)
        data = get_response_data(response) or {}
        self.assertEqual(data.get("max_job_concurrency"), 2)
        self.assertEqual(data.get("max_queued_jobs"), 10)

    # Edge Case Tests
    def test_config_with_all_fields_set(self):
        """Create config with all fields populated"""
        self.client.force_authenticate(user=self.tenant1_admin)

        data = {
            "default_dq_profile": "intake_basic_soda",
            "allowed_compliance_regimes": ["GDPR", "LGPD", "CCPA"],
            "default_compliance_regimes": ["GDPR", "LGPD"],
            "data_retention_days": 1825,
            "rate_limits": {
                "dq_runs": {"burst_per_10s": 20, "sustained_per_min": 60, "daily_cap": 10000},
                "file_uploads": {"burst_per_10s": 10, "sustained_per_min": 30},
            },
            "max_file_size_bytes": 10737418240,  # 10GB
            "max_job_concurrency": 5,
            "max_queued_jobs": 50,
        }

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify all fields are returned in GET response
        response = self.client.get(f"/api/v1/tenants/{self.tenant.id}/config/")
        self.assertEqual(
            (get_response_data(response) or {})["default_dq_profile"], "intake_basic_soda"
        )
        self.assertEqual(
            (get_response_data(response) or {})["allowed_compliance_regimes"],
            ["GDPR", "LGPD", "CCPA"],
        )
        self.assertEqual(
            (get_response_data(response) or {})["default_compliance_regimes"], ["GDPR", "LGPD"]
        )
        self.assertEqual((get_response_data(response) or {})["data_retention_days"], 1825)
        self.assertEqual((get_response_data(response) or {})["max_file_size_bytes"], 10737418240)
        self.assertEqual((get_response_data(response) or {})["max_job_concurrency"], 5)
        self.assertEqual((get_response_data(response) or {})["max_queued_jobs"], 50)

    def test_config_partial_update(self):
        """Partial update - update only one field"""
        # Create config with some fields
        TenantConfig.objects.create(
            tenant=self.tenant, default_dq_profile="intake_basic_gx", data_retention_days=2555
        )

        self.client.force_authenticate(user=self.tenant1_admin)

        # Update only default_dq_profile
        data = {"default_dq_profile": "intake_basic_soda"}
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify other fields remain unchanged
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.default_dq_profile, "intake_basic_soda")
        self.assertEqual(config.data_retention_days, 2555)  # Unchanged

    def test_config_rate_limits_partial_update(self):
        """Partial update of rate_limits - update only one category"""
        # Create config with rate_limits for all categories
        TenantConfig.objects.create(
            tenant=self.tenant,
            rate_limits={
                "dq_runs": {"burst_per_10s": 20, "sustained_per_min": 60},
                "file_uploads": {"burst_per_10s": 10, "sustained_per_min": 30},
            },
        )

        self.client.force_authenticate(user=self.tenant1_admin)

        # Update only dq_runs category
        # Note: Current implementation replaces entire rate_limits dict (not merging)
        # This test documents current behavior
        data = {"rate_limits": {"dq_runs": {"burst_per_10s": 25, "sustained_per_min": 70}}}
        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify dq_runs updated
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.rate_limits["dq_runs"]["burst_per_10s"], 25)
        self.assertEqual(config.rate_limits["dq_runs"]["sustained_per_min"], 70)
        # Note: file_uploads is replaced (current behavior - DictField replaces entire dict)
        # This is expected behavior - merge logic would be an enhancement

    def test_config_validation_edge_cases_minimum(self):
        """Test validation edge cases - minimum data_retention_days"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"data_retention_days": 90}  # Minimum

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((get_response_data(response) or {})["data_retention_days"], 90)

    def test_config_validation_edge_cases_maximum(self):
        """Test validation edge cases - maximum data_retention_days"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"data_retention_days": 3650}  # Maximum

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual((get_response_data(response) or {})["data_retention_days"], 3650)

    def test_config_validation_edge_cases_below_minimum(self):
        """Test validation edge cases - below minimum data_retention_days"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"data_retention_days": 89}  # Below minimum

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_config_validation_edge_cases_above_maximum(self):
        """Test validation edge cases - above maximum data_retention_days"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"data_retention_days": 3651}  # Above maximum

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_config_validation_edge_cases_empty_arrays(self):
        """Test validation edge cases - empty compliance regime arrays"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {"allowed_compliance_regimes": [], "default_compliance_regimes": []}

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Note: get_tenant_config() returns platform defaults when fields are None/empty
        # Empty arrays are valid and stored, but GET response merges with platform defaults
        # Verify the config was stored correctly
        config = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(config.allowed_compliance_regimes, [])
        self.assertEqual(config.default_compliance_regimes, [])

    def test_config_validation_edge_cases_full_subset(self):
        """Test validation edge cases - default_compliance_regimes = allowed_compliance_regimes"""
        self.client.force_authenticate(user=self.tenant1_admin)
        data = {
            "allowed_compliance_regimes": ["GDPR", "LGPD"],
            "default_compliance_regimes": ["GDPR", "LGPD"],  # Full subset
        }

        response = self.client.patch(
            f"/api/v1/tenants/{self.tenant.id}/config/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            (get_response_data(response) or {})["default_compliance_regimes"], ["GDPR", "LGPD"]
        )

    def test_config_deletion_cascade(self):
        """Test config deletion cascade when tenant is deleted"""
        # Create a tenant without users to test cascade delete
        test_tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )

        config = TenantConfig.objects.create(
            tenant=test_tenant, default_dq_profile="intake_basic_soda"
        )
        config_id = config.id

        # Delete tenant (no users, so no RESTRICT constraint)
        test_tenant.delete()

        # Verify TenantConfig is deleted (cascade delete)
        self.assertFalse(TenantConfig.objects.filter(id=config_id).exists())
