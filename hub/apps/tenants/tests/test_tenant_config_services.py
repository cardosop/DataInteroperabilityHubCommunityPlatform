"""
Unit tests for TenantConfig services.

GAP-0.2.5: Comprehensive service tests covering get_tenant_config and get_tenant_config_value.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.tenants.services import get_tenant_config, get_tenant_config_value
from hub.apps.tenants.validators import get_platform_defaults

pytestmark = pytest.mark.django_db(transaction=True)


class GetTenantConfigTest(TestCase):
    """Test get_tenant_config function"""

    def setUp(self):
        """Set up test data"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.platform_defaults = get_platform_defaults()

    # GAP-0.2.5.1: get_tenant_config tests
    def test_returns_platform_defaults_when_config_doesnt_exist(self):
        """Test returns platform defaults when config doesn't exist"""
        config_dict = get_tenant_config(self.tenant)

        # Should return platform defaults
        self.assertEqual(
            config_dict["default_dq_profile"], self.platform_defaults["default_dq_profile"]
        )
        self.assertEqual(
            config_dict["allowed_compliance_regimes"],
            self.platform_defaults["allowed_compliance_regimes"],
        )
        self.assertEqual(
            config_dict["default_compliance_regimes"],
            self.platform_defaults["default_compliance_regimes"],
        )
        self.assertEqual(
            config_dict["data_retention_days"], self.platform_defaults["data_retention_days"]
        )
        self.assertEqual(
            config_dict["max_file_size_bytes"], self.platform_defaults["max_file_size_bytes"]
        )
        self.assertEqual(
            config_dict["max_job_concurrency"], self.platform_defaults["max_job_concurrency"]
        )
        self.assertEqual(config_dict["max_queued_jobs"], self.platform_defaults["max_queued_jobs"])

        # Should include tenant_id
        self.assertEqual(config_dict["tenant_id"], str(self.tenant.id))

    def test_returns_tenant_specific_values_when_config_exists(self):
        """Test returns tenant-specific values when config exists"""
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_soda",
            allowed_compliance_regimes=["GDPR"],
            default_compliance_regimes=["GDPR"],
            data_retention_days=1825,
            max_file_size_bytes=5368709120,
            max_job_concurrency=10,
            max_queued_jobs=100,
        )

        config_dict = get_tenant_config(self.tenant)

        # Should return tenant-specific values
        self.assertEqual(config_dict["default_dq_profile"], "intake_basic_soda")
        self.assertEqual(config_dict["allowed_compliance_regimes"], ["GDPR"])
        self.assertEqual(config_dict["default_compliance_regimes"], ["GDPR"])
        self.assertEqual(config_dict["data_retention_days"], 1825)
        self.assertEqual(config_dict["max_file_size_bytes"], 5368709120)
        self.assertEqual(config_dict["max_job_concurrency"], 10)
        self.assertEqual(config_dict["max_queued_jobs"], 100)

    def test_merges_tenant_values_with_platform_defaults(self):
        """Test merges tenant values with platform defaults (partial config)"""
        # Create config with only some fields set
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_soda",
            # Leave other fields as None/empty
        )

        config_dict = get_tenant_config(self.tenant)

        # Tenant-specific value should be used
        self.assertEqual(config_dict["default_dq_profile"], "intake_basic_soda")

        # Platform defaults should be used for other fields
        self.assertEqual(
            config_dict["allowed_compliance_regimes"],
            self.platform_defaults["allowed_compliance_regimes"],
        )
        self.assertEqual(
            config_dict["data_retention_days"], self.platform_defaults["data_retention_days"]
        )

    def test_response_structure(self):
        """Test response structure (all fields present, tenant_id included)"""
        config_dict = get_tenant_config(self.tenant)

        required_fields = [
            "tenant_id",
            "default_dq_profile",
            "allowed_compliance_regimes",
            "default_compliance_regimes",
            "data_retention_days",
            "rate_limits",
            "max_file_size_bytes",
            "max_job_concurrency",
            "max_queued_jobs",
            "created_at",
            "updated_at",
        ]

        for field in required_fields:
            self.assertIn(field, config_dict, f"Response missing required field: {field}")

    def test_timestamp_serialization(self):
        """Test timestamp serialization (ISO format)"""
        from datetime import datetime as dt

        TenantConfig.objects.create(tenant=self.tenant)

        config_dict = get_tenant_config(self.tenant)

        # created_at must be present and parseable
        self.assertIsNotNone(
            config_dict["created_at"],
            "created_at should not be None for a just-created config",
        )
        self.assertIsInstance(config_dict["created_at"], str)
        # Verify it parses as ISO 8601
        parsed = dt.fromisoformat(
            config_dict["created_at"].replace("Z", "+00:00"),
        )
        self.assertIsInstance(parsed, dt)

        self.assertIsNotNone(config_dict["updated_at"])
        self.assertIsInstance(config_dict["updated_at"], str)
        parsed2 = dt.fromisoformat(
            config_dict["updated_at"].replace("Z", "+00:00"),
        )
        self.assertIsInstance(parsed2, dt)

    def test_none_values_are_replaced_with_platform_defaults(self):
        """Test None values are replaced with platform defaults"""
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile=None,
            data_retention_days=None,
            max_file_size_bytes=None,
        )

        config_dict = get_tenant_config(self.tenant)

        # None values should be replaced with platform defaults
        self.assertEqual(
            config_dict["default_dq_profile"], self.platform_defaults["default_dq_profile"]
        )
        self.assertEqual(
            config_dict["data_retention_days"], self.platform_defaults["data_retention_days"]
        )
        self.assertEqual(
            config_dict["max_file_size_bytes"], self.platform_defaults["max_file_size_bytes"]
        )

    def test_empty_lists_fall_back_to_platform_defaults(self):
        """Test empty lists are falsy and fall back to platform defaults.

        The service uses the ``or`` operator, so ``[] or default``
        returns the platform default.  This is intentional: an empty
        list means "no tenant override — use platform default".
        """
        TenantConfig.objects.create(
            tenant=self.tenant,
            allowed_compliance_regimes=[],
            default_compliance_regimes=[],
        )

        config_dict = get_tenant_config(self.tenant)

        self.assertEqual(
            config_dict["allowed_compliance_regimes"],
            self.platform_defaults["allowed_compliance_regimes"],
        )
        self.assertEqual(
            config_dict["default_compliance_regimes"],
            self.platform_defaults["default_compliance_regimes"],
        )

    def test_empty_dict_for_rate_limits_is_replaced_with_platform_defaults(self):
        """Test empty dict for rate_limits is replaced with platform defaults"""
        TenantConfig.objects.create(tenant=self.tenant, rate_limits={})

        config_dict = get_tenant_config(self.tenant)

        # Empty dict should be replaced with platform defaults
        self.assertEqual(config_dict["rate_limits"], self.platform_defaults["rate_limits"])

    def test_rate_limits_partial_structure_merges_correctly(self):
        """Test rate_limits partial structure (only some categories) merges correctly"""
        TenantConfig.objects.create(
            tenant=self.tenant,
            rate_limits={"dq_runs": {"burst_per_10s": 30, "sustained_per_min": 90}},
        )

        config_dict = get_tenant_config(self.tenant)

        # Tenant-specific dq_runs should be used
        self.assertEqual(config_dict["rate_limits"]["dq_runs"]["burst_per_10s"], 30)
        self.assertEqual(config_dict["rate_limits"]["dq_runs"]["sustained_per_min"], 90)

        # Other categories should use platform defaults
        self.assertIn("file_uploads", config_dict["rate_limits"])
        self.assertEqual(
            config_dict["rate_limits"]["file_uploads"],
            self.platform_defaults["rate_limits"]["file_uploads"],
        )


class GetTenantConfigValueTest(TestCase):
    """Test get_tenant_config_value function"""

    def setUp(self):
        """Set up test data"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.platform_defaults = get_platform_defaults()

    # GAP-0.2.5.2: get_tenant_config_value tests
    def test_returns_tenant_specific_value_when_set(self):
        """Test returns tenant-specific value when set"""
        TenantConfig.objects.create(
            tenant=self.tenant, default_dq_profile="intake_basic_soda", data_retention_days=1825
        )

        value = get_tenant_config_value(self.tenant, "default_dq_profile")
        self.assertEqual(value, "intake_basic_soda")

        value = get_tenant_config_value(self.tenant, "data_retention_days")
        self.assertEqual(value, 1825)

    def test_returns_platform_default_when_tenant_value_not_set(self):
        """Test returns platform default when tenant value not set"""
        # No config exists
        value = get_tenant_config_value(self.tenant, "default_dq_profile")
        self.assertEqual(value, self.platform_defaults["default_dq_profile"])

        value = get_tenant_config_value(self.tenant, "data_retention_days")
        self.assertEqual(value, self.platform_defaults["data_retention_days"])

    def test_returns_custom_default_when_provided(self):
        """Test returns custom default when provided"""
        custom_default = "custom_value"
        value = get_tenant_config_value(self.tenant, "default_dq_profile", custom_default)
        self.assertEqual(value, custom_default)

    def test_returns_none_for_nonexistent_key(self):
        """Test returns None for non-existent key (no default provided)"""
        value = get_tenant_config_value(self.tenant, "nonexistent_key")
        self.assertIsNone(value)

    def test_all_configuration_keys(self):
        """Test all configuration keys return correct values."""
        TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_soda",
            allowed_compliance_regimes=["GDPR"],
            default_compliance_regimes=["GDPR"],
            data_retention_days=1825,
            max_file_size_bytes=5368709120,
            max_job_concurrency=10,
            max_queued_jobs=100,
        )

        expected = {
            "default_dq_profile": "intake_basic_soda",
            "allowed_compliance_regimes": ["GDPR"],
            "default_compliance_regimes": ["GDPR"],
            "data_retention_days": 1825,
            "max_file_size_bytes": 5368709120,
            "max_job_concurrency": 10,
            "max_queued_jobs": 100,
        }

        for key, expected_val in expected.items():
            value = get_tenant_config_value(self.tenant, key)
            self.assertEqual(
                value,
                expected_val,
                f"Key {key}: expected {expected_val}, got {value}",
            )
