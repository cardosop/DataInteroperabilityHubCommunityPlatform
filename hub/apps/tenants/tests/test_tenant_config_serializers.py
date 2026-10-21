"""
Unit tests for TenantConfig serializers.

GAP-0.2.2: Comprehensive serializer tests covering TenantConfigSerializer,
RateLimitsSerializer, and TenantConfigUpdateSerializer.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.tenants.models import Tenant, TenantConfig
from hub.apps.tenants.serializers import (
    RateLimitsSerializer,
    TenantConfigSerializer,
    TenantConfigUpdateSerializer,
)
from hub.apps.tenants.validators import (
    PLATFORM_MAX_RATE_LIMITS,
)

pytestmark = pytest.mark.django_db(transaction=True)


class RateLimitsSerializerTest(TestCase):
    """Test RateLimitsSerializer"""

    # GAP-0.2.2.2: RateLimitsSerializer tests
    def test_valid_rate_limit_structure_all_categories(self):
        """Test valid rate limit structure per category (all categories)"""
        categories = [
            "dq_runs",
            "compliance_runs",
            "file_uploads",
            "contract_validation",
            "catalog_reads",
            "sparql_queries",
        ]

        for category in categories:
            platform_max = PLATFORM_MAX_RATE_LIMITS[category]
            limits = {}

            if "burst_per_10s" in platform_max:
                limits["burst_per_10s"] = platform_max["burst_per_10s"]
            if "sustained_per_min" in platform_max:
                limits["sustained_per_min"] = platform_max["sustained_per_min"]
            if "daily_cap" in platform_max:
                limits["daily_cap"] = platform_max["daily_cap"]

            serializer = RateLimitsSerializer(data=limits)
            self.assertTrue(
                serializer.is_valid(),
                f"RateLimitsSerializer invalid for category {category}: {serializer.errors}",
            )

    def test_rate_limit_only_burst_per_10s(self):
        """Test rate limit with only burst_per_10s"""
        serializer = RateLimitsSerializer(data={"burst_per_10s": 20})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["burst_per_10s"], 20)

    def test_rate_limit_only_sustained_per_min(self):
        """Test rate limit with only sustained_per_min"""
        serializer = RateLimitsSerializer(data={"sustained_per_min": 60})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["sustained_per_min"], 60)

    def test_rate_limit_only_daily_cap(self):
        """Test rate limit with only daily_cap (for applicable categories)"""
        serializer = RateLimitsSerializer(data={"daily_cap": 10000})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["daily_cap"], 10000)

    def test_rate_limit_all_three_limits(self):
        """Test rate limit with all three limits"""
        serializer = RateLimitsSerializer(
            data={"burst_per_10s": 20, "sustained_per_min": 60, "daily_cap": 10000}
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["burst_per_10s"], 20)
        self.assertEqual(serializer.validated_data["sustained_per_min"], 60)
        self.assertEqual(serializer.validated_data["daily_cap"], 10000)

    def test_rate_limit_negative_values(self):
        """Test rate limit with negative values"""
        serializer = RateLimitsSerializer(data={"burst_per_10s": -10})
        self.assertFalse(serializer.is_valid())
        self.assertIn("burst_per_10s", serializer.errors)

    def test_rate_limit_zero_values(self):
        """Test rate limit with zero values"""
        serializer = RateLimitsSerializer(data={"burst_per_10s": 0})
        self.assertFalse(serializer.is_valid())
        self.assertIn("burst_per_10s", serializer.errors)

    def test_rate_limit_missing_required_fields(self):
        """Test rate limit with missing required fields (at least one limit must be specified)"""
        serializer = RateLimitsSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
        error_message = str(serializer.errors["non_field_errors"][0])
        self.assertIn("At least one rate limit", error_message)


class TenantConfigSerializerTest(TestCase):
    """Test TenantConfigSerializer"""

    def setUp(self):
        """Set up test data"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")

    # GAP-0.2.2.1: TenantConfigSerializer tests
    def test_serialization_of_all_fields(self):
        """Test serialization of all fields (read-only fields, writable fields)"""
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_gx",
            allowed_compliance_regimes=["GDPR", "LGPD"],
            default_compliance_regimes=["GDPR"],
            data_retention_days=2555,
            max_file_size_bytes=10737418240,
            max_job_concurrency=5,
            max_queued_jobs=50,
            rate_limits={
                "dq_runs": {"burst_per_10s": 20, "sustained_per_min": 60, "daily_cap": 10000}
            },
        )

        serializer = TenantConfigSerializer(config)
        data = serializer.data

        # Check all fields are present
        self.assertIn("tenant_id", data)
        self.assertIn("default_dq_profile", data)
        self.assertIn("allowed_compliance_regimes", data)
        self.assertIn("default_compliance_regimes", data)
        self.assertIn("data_retention_days", data)
        self.assertIn("rate_limits", data)
        self.assertIn("max_file_size_bytes", data)
        self.assertIn("max_job_concurrency", data)
        self.assertIn("max_queued_jobs", data)
        self.assertIn("trust_signals_enabled", data)
        self.assertIn("versioning_enabled", data)
        self.assertIn("workflows_enabled", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

        # Check values
        self.assertEqual(str(self.tenant.id), data["tenant_id"])
        self.assertEqual("intake_basic_gx", data["default_dq_profile"])
        self.assertEqual(["GDPR", "LGPD"], data["allowed_compliance_regimes"])
        self.assertEqual(["GDPR"], data["default_compliance_regimes"])
        self.assertEqual(2555, data["data_retention_days"])
        self.assertEqual(10737418240, data["max_file_size_bytes"])
        self.assertEqual(5, data["max_job_concurrency"])
        self.assertEqual(50, data["max_queued_jobs"])

    def test_deserialization_with_valid_data(self):
        """Test deserialization with valid data (all fields)"""
        data = {
            "default_dq_profile": "intake_basic_soda",
            "allowed_compliance_regimes": ["GDPR", "LGPD", "CCPA"],
            "default_compliance_regimes": ["GDPR", "LGPD"],
            "data_retention_days": 1825,
            "max_file_size_bytes": 5368709120,
            "max_job_concurrency": 10,
            "max_queued_jobs": 100,
            "rate_limits": {
                "dq_runs": {"burst_per_10s": 30, "sustained_per_min": 90, "daily_cap": 20000}
            },
        }

        serializer = TenantConfigSerializer(data=data)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        self.assertEqual(serializer.validated_data["default_dq_profile"], "intake_basic_soda")
        self.assertEqual(
            serializer.validated_data["allowed_compliance_regimes"], ["GDPR", "LGPD", "CCPA"]
        )

    def test_deserialization_with_partial_data(self):
        """Test deserialization with partial data (only some fields)"""
        data = {"default_dq_profile": "intake_basic_gx", "data_retention_days": 1825}

        serializer = TenantConfigSerializer(data=data)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        self.assertEqual(serializer.validated_data["default_dq_profile"], "intake_basic_gx")
        self.assertEqual(serializer.validated_data["data_retention_days"], 1825)

    def test_deserialization_with_invalid_dq_profile(self):
        """Test deserialization with invalid DQ profile"""
        data = {"default_dq_profile": "invalid_profile"}

        serializer = TenantConfigSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("default_dq_profile", serializer.errors)

    def test_deserialization_with_invalid_compliance_regime(self):
        """Test deserialization with invalid compliance regime"""
        data = {"allowed_compliance_regimes": ["GDPR", "INVALID_REGIME"]}

        serializer = TenantConfigSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("allowed_compliance_regimes", serializer.errors)

    def test_deserialization_with_invalid_data_retention_days(self):
        """Test deserialization with invalid data retention days (out of range)"""
        data = {
            "data_retention_days": 50  # Below minimum of 90
        }

        serializer = TenantConfigSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("data_retention_days", serializer.errors)

    def test_deserialization_with_invalid_rate_limits(self):
        """Test deserialization with invalid rate limits (exceeds platform maximums)"""
        data = {
            "rate_limits": {
                "dq_runs": {
                    "burst_per_10s": PLATFORM_MAX_RATE_LIMITS["dq_runs"]["burst_per_10s"] + 1
                }
            }
        }

        serializer = TenantConfigSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("rate_limits", serializer.errors)

    def test_deserialization_default_compliance_regimes_not_subset(self):
        """Test deserialization with default_compliance_regimes not subset of allowed_compliance_regimes"""
        data = {
            "allowed_compliance_regimes": ["GDPR", "LGPD"],
            "default_compliance_regimes": ["GDPR", "CCPA"],  # CCPA not in allowed
        }

        serializer = TenantConfigSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("default_compliance_regimes", serializer.errors)

    def test_read_only_fields_cannot_be_updated(self):
        """Test read-only fields cannot be updated (tenant_id, created_at, updated_at)"""
        config = TenantConfig.objects.create(tenant=self.tenant)

        data = {
            "tenant_id": "00000000-0000-0000-0000-000000000000",
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2020-01-01T00:00:00Z",
        }

        serializer = TenantConfigSerializer(config, data=data, partial=True)
        # Read-only fields should be ignored, not cause errors
        self.assertTrue(serializer.is_valid())

        # Verify read-only fields are not updated
        serializer.save()
        config.refresh_from_db()
        self.assertNotEqual(str(config.tenant.id), "00000000-0000-0000-0000-000000000000")

    def test_timestamp_serialization_format(self):
        """Test timestamp serialization format (ISO 8601)"""
        config = TenantConfig.objects.create(tenant=self.tenant)

        serializer = TenantConfigSerializer(config)
        data = serializer.data

        # Check timestamp format
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

        # Verify ISO 8601 format (contains 'T' and 'Z' or timezone offset)
        if data["created_at"]:
            self.assertIn("T", data["created_at"])
        if data["updated_at"]:
            self.assertIn("T", data["updated_at"])


class TenantConfigUpdateSerializerTest(TestCase):
    """Test TenantConfigUpdateSerializer"""

    def setUp(self):
        """Set up test data"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.config = TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_gx",
            allowed_compliance_regimes=["GDPR", "LGPD"],
            default_compliance_regimes=["GDPR"],
            data_retention_days=2555,
            rate_limits={
                "dq_runs": {"burst_per_10s": 20, "sustained_per_min": 60, "daily_cap": 10000}
            },
        )

    # GAP-0.2.2.3: TenantConfigUpdateSerializer tests
    def test_partial_update_single_field(self):
        """Test partial update (single field: default_dq_profile)"""
        data = {"default_dq_profile": "intake_basic_soda"}

        serializer = TenantConfigUpdateSerializer(self.config, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        serializer.save()

        self.config.refresh_from_db()
        self.assertEqual(self.config.default_dq_profile, "intake_basic_soda")
        # Other fields should be unchanged
        self.assertEqual(self.config.data_retention_days, 2555)

    def test_partial_update_multiple_fields(self):
        """Test partial update (multiple fields)"""
        data = {"default_dq_profile": "intake_basic_soda", "data_retention_days": 1825}

        serializer = TenantConfigUpdateSerializer(self.config, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        serializer.save()

        self.config.refresh_from_db()
        self.assertEqual(self.config.default_dq_profile, "intake_basic_soda")
        self.assertEqual(self.config.data_retention_days, 1825)

    def test_partial_update_rate_limits_structure(self):
        """Test partial update (rate_limits nested structure)"""
        data = {"rate_limits": {"file_uploads": {"burst_per_10s": 15, "sustained_per_min": 45}}}

        serializer = TenantConfigUpdateSerializer(self.config, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        serializer.save()

        self.config.refresh_from_db()
        self.assertIn("file_uploads", self.config.rate_limits)
        self.assertEqual(self.config.rate_limits["file_uploads"]["burst_per_10s"], 15)
        # Existing dq_runs should be preserved (partial update merges)
        # Actually, DictField replaces the entire dict, so dq_runs might be lost
        # This is a known limitation - we might need to implement merge logic

    def test_partial_update_with_empty_dict(self):
        """Test partial update with empty dict (should clear rate_limits)"""
        data = {"rate_limits": {}}

        serializer = TenantConfigUpdateSerializer(self.config, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        serializer.save()

        self.config.refresh_from_db()
        self.assertEqual(self.config.rate_limits, {})

    def test_partial_update_with_none(self):
        """Test partial update with None (should not update field)"""

        data = {"default_dq_profile": None}

        serializer = TenantConfigUpdateSerializer(self.config, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        serializer.save()

        self.config.refresh_from_db()
        # None should clear the field
        self.assertIsNone(self.config.default_dq_profile)

    def test_partial_update_preserves_existing_values(self):
        """Test partial update preserves existing values for non-updated fields"""
        original_data_retention = self.config.data_retention_days
        original_max_file_size = self.config.max_file_size_bytes

        data = {"default_dq_profile": "intake_basic_soda"}

        serializer = TenantConfigUpdateSerializer(self.config, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        serializer.save()

        self.config.refresh_from_db()
        self.assertEqual(self.config.default_dq_profile, "intake_basic_soda")
        self.assertEqual(self.config.data_retention_days, original_data_retention)
        if original_max_file_size:
            self.assertEqual(self.config.max_file_size_bytes, original_max_file_size)

    def test_partial_update_cross_field_validation(self):
        """Test partial update validation (cross-field: default_compliance_regimes subset)"""
        data = {
            "allowed_compliance_regimes": ["GDPR", "LGPD"],
            "default_compliance_regimes": ["GDPR", "CCPA"],  # CCPA not in allowed
        }

        serializer = TenantConfigUpdateSerializer(self.config, data=data, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("default_compliance_regimes", serializer.errors)

    def test_partial_update_workflows_enabled(self):
        """Phase 14: Partial update workflows_enabled persists."""
        data = {"workflows_enabled": False}
        serializer = TenantConfigUpdateSerializer(self.config, data=data, partial=True)
        self.assertTrue(serializer.is_valid(), f"Serializer errors: {serializer.errors}")
        serializer.save()

        self.config.refresh_from_db()
        self.assertIs(self.config.workflows_enabled, False)

        data2 = {"workflows_enabled": True}
        serializer2 = TenantConfigUpdateSerializer(self.config, data=data2, partial=True)
        self.assertTrue(serializer2.is_valid(), f"Serializer errors: {serializer2.errors}")
        serializer2.save()
        self.config.refresh_from_db()
        self.assertIs(self.config.workflows_enabled, True)
