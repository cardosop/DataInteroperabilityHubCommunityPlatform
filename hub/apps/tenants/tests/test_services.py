"""
Unit tests for Tenant Service (hub.apps.tenants.services).

Tests get_tenant_config, get_tenant_config_value, TenantService (get_tenant, create_tenant,
update_tenant, delete_tenant, validate_kyc_verified) with real DB. No mocks/stubs.
"""

import pytest
from django.test import TestCase

from hub.apps.core.services.base import NotFoundError, PermissionError, ValidationError
from hub.apps.tenants.models import KYCStatus, Tenant, TenantConfig, TenantStatus
from hub.apps.tenants.services import (
    TenantService,
    get_tenant_compliance_regimes,
    get_tenant_config,
    get_tenant_config_value,
    get_tenant_dq_profile,
    get_tenant_file_size_limit,
    get_tenant_job_limits,
)

pytestmark = pytest.mark.django_db(transaction=True)


class GetTenantConfigTest(TestCase):
    """Test get_tenant_config and get_tenant_config_value with real DB."""

    def setUp(self):
        import uuid
        uid = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")

    def test_get_tenant_config_no_config_returns_platform_defaults(self):
        """Success: tenant with no TenantConfig returns dict with platform defaults and tenant_id."""
        result = get_tenant_config(self.tenant)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["tenant_id"], str(self.tenant.id))
        self.assertIn("default_dq_profile", result)
        self.assertIn("rate_limits", result)
        self.assertIn("data_retention_days", result)

    def test_get_tenant_config_with_config_returns_merged_values(self):
        """Success: tenant with TenantConfig returns merged config with tenant overrides."""
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_soda",
            data_retention_days=180,
        )
        result = get_tenant_config(self.tenant)
        self.assertEqual(result["tenant_id"], str(self.tenant.id))
        self.assertEqual(result["default_dq_profile"], "intake_basic_soda")
        self.assertEqual(result["data_retention_days"], 180)

    def test_get_tenant_config_value_with_config_returns_tenant_value(self):
        """Success: get_tenant_config_value returns tenant value when set."""
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_soda",
        )
        value = get_tenant_config_value(self.tenant, "default_dq_profile")
        self.assertEqual(value, "intake_basic_soda")

    def test_get_tenant_config_value_no_config_returns_platform_default(self):
        """Success: get_tenant_config_value returns platform default when no config."""
        value = get_tenant_config_value(self.tenant, "default_dq_profile")
        self.assertIsNotNone(value)

    def test_get_tenant_config_includes_trust_signals_enabled(self):
        """Phase 11: get_tenant_config includes trust_signals_enabled."""
        result = get_tenant_config(self.tenant)
        self.assertIn("trust_signals_enabled", result)
        self.assertIs(result["trust_signals_enabled"], True)

        TenantConfig.objects.create(tenant=self.tenant, trust_signals_enabled=False)
        result2 = get_tenant_config(self.tenant)
        self.assertIs(result2["trust_signals_enabled"], False)

    def test_get_tenant_config_includes_versioning_enabled(self):
        """Phase 12: get_tenant_config includes versioning_enabled."""
        result = get_tenant_config(self.tenant)
        self.assertIn("versioning_enabled", result)
        self.assertIs(result["versioning_enabled"], True)

        TenantConfig.objects.create(tenant=self.tenant, versioning_enabled=False)
        result2 = get_tenant_config(self.tenant)
        self.assertIs(result2["versioning_enabled"], False)

    def test_get_tenant_config_includes_workflows_enabled(self):
        """Phase 14: get_tenant_config includes workflows_enabled."""
        result = get_tenant_config(self.tenant)
        self.assertIn("workflows_enabled", result)
        self.assertIs(result["workflows_enabled"], True)

        TenantConfig.objects.create(tenant=self.tenant, workflows_enabled=False)
        result2 = get_tenant_config(self.tenant)
        self.assertIs(result2["workflows_enabled"], False)

    def test_get_tenant_config_value_custom_default_overrides_platform(self):
        """Edge case: custom default argument overrides platform default."""
        value = get_tenant_config_value(self.tenant, "default_dq_profile", default="custom_profile")
        self.assertEqual(value, "custom_profile")


class GetTenantHelpersTest(TestCase):
    """Test get_tenant_dq_profile, get_tenant_compliance_regimes, get_tenant_file_size_limit, get_tenant_job_limits."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")

    def test_get_tenant_dq_profile_success(self):
        """Success: returns DQ profile for existing tenant (or platform default)."""
        result = get_tenant_dq_profile(str(self.tenant.id))
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_get_tenant_dq_profile_invalid_uuid_returns_platform_default(self):
        """Failure/edge: invalid UUID returns platform default (no exception)."""
        result = get_tenant_dq_profile("not-a-uuid")
        self.assertIsInstance(result, str)

    def test_get_tenant_dq_profile_nonexistent_tenant_returns_platform_default(self):
        """Failure: nonexistent tenant_id returns platform default."""
        import uuid

        fake_id = str(uuid.uuid4())
        result = get_tenant_dq_profile(fake_id)
        self.assertIsInstance(result, str)

    def test_get_tenant_compliance_regimes_success(self):
        """Success: returns list for existing tenant."""
        result = get_tenant_compliance_regimes(str(self.tenant.id))
        self.assertIsInstance(result, list)

    def test_get_tenant_file_size_limit_success(self):
        """Success: returns int for existing tenant."""
        result = get_tenant_file_size_limit(str(self.tenant.id))
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)

    def test_get_tenant_job_limits_success(self):
        """Success: returns dict with max_job_concurrency and max_queued_jobs."""
        result = get_tenant_job_limits(str(self.tenant.id))
        self.assertIn("max_job_concurrency", result)
        self.assertIn("max_queued_jobs", result)
        self.assertIsInstance(result["max_job_concurrency"], int)
        self.assertIsInstance(result["max_queued_jobs"], int)


class TenantServiceTest(TestCase):
    """Test TenantService with real DB. No mocks."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.service = TenantService(tenant_id=str(self.tenant.id), user_id=None)

    def test_get_tenant_success(self):
        """Success: get_tenant returns tenant by id."""
        result = self.service.get_tenant(str(self.tenant.id))
        self.assertEqual(result.id, self.tenant.id)
        self.assertEqual(result.name, self.tenant.name)

    def test_get_tenant_not_found_raises(self):
        """Failure: get_tenant raises NotFoundError for nonexistent id."""
        import uuid

        fake_id = str(uuid.uuid4())
        with self.assertRaises(NotFoundError):
            self.service.get_tenant(fake_id)

    def test_validate_kyc_verified_success(self):
        """Success: validate_kyc_verified returns tenant when KYC is VERIFIED."""
        self.tenant.kyc_status = KYCStatus.VERIFIED
        self.tenant.save()
        result = self.service.validate_kyc_verified(str(self.tenant.id))
        self.assertEqual(result.id, self.tenant.id)

    def test_validate_kyc_verified_failure_raises_permission_error(self):
        """Failure: validate_kyc_verified raises PermissionError when KYC not VERIFIED."""
        self.tenant.kyc_status = KYCStatus.UNVERIFIED
        self.tenant.save()
        with self.assertRaises(PermissionError) as cm:
            self.service.validate_kyc_verified(str(self.tenant.id))
        self.assertIn("VERIFIED", str(cm.exception))

    def test_create_tenant_success(self):
        """Success: create_tenant creates tenant with ACTIVE status and UNVERIFIED KYC."""
        service = TenantService(tenant_id=None, user_id=None)
        tenant = service.create_tenant(name="New Tenant", slug="new-tenant", region="us-east-1")
        self.assertIsNotNone(tenant.id)
        self.assertEqual(tenant.name, "New Tenant")
        self.assertEqual(tenant.slug, "new-tenant")
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)
        self.assertEqual(tenant.kyc_status, KYCStatus.UNVERIFIED)
        self.assertEqual(tenant.region, "us-east-1")

    def test_update_tenant_success(self):
        """Success: update_tenant updates name and kyc_status."""
        result = self.service.update_tenant(
            str(self.tenant.id),
            name="Updated Name",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.assertEqual(result.name, "Updated Name")
        self.assertEqual(result.kyc_status, KYCStatus.VERIFIED)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.name, "Updated Name")

    def test_update_tenant_not_found_raises(self):
        """Failure: update_tenant raises NotFoundError for nonexistent id."""
        import uuid

        fake_id = str(uuid.uuid4())
        with self.assertRaises(NotFoundError):
            self.service.update_tenant(fake_id, name="Any")

    def test_delete_tenant_success(self):
        """Success: delete_tenant soft-deletes tenant."""
        result = self.service.delete_tenant(str(self.tenant.id))
        self.assertEqual(result.status, TenantStatus.DELETED)
        self.assertIsNotNone(result.deleted_at)

    def test_delete_tenant_already_deleted_raises(self):
        """Failure: delete_tenant raises ValidationError when tenant already deleted."""
        self.tenant.soft_delete()
        with self.assertRaises(ValidationError) as cm:
            self.service.delete_tenant(str(self.tenant.id))
        self.assertIn("already deleted", str(cm.exception).lower())
