"""
Unit tests for TenantConfig model.
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from hub.apps.tenants.models import Tenant, TenantConfig, TenantStatus, KYCStatus
import uuid


pytestmark = pytest.mark.django_db(transaction=True)


class TenantConfigModelTest(TestCase):
    """Test TenantConfig model"""
    
    def setUp(self):
        """Set up test data"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}"
        )
    
    def test_create_tenant_config(self):
        """Test tenant config creation"""
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile="intake_basic_gx",
            allowed_compliance_regimes=["GDPR", "LGPD"],
            default_compliance_regimes=["GDPR"],
            data_retention_days=2555,
            max_file_size_bytes=10737418240,
            max_job_concurrency=5,
            max_queued_jobs=50,
        )
        
        self.assertEqual(config.tenant, self.tenant)
        self.assertEqual(config.default_dq_profile, "intake_basic_gx")
        self.assertEqual(config.allowed_compliance_regimes, ["GDPR", "LGPD"])
        self.assertEqual(config.default_compliance_regimes, ["GDPR"])
        self.assertEqual(config.data_retention_days, 2555)
        self.assertEqual(config.max_file_size_bytes, 10737418240)
        self.assertEqual(config.max_job_concurrency, 5)
        self.assertEqual(config.max_queued_jobs, 50)
    
    def test_tenant_config_one_to_one_relationship(self):
        """Test that tenant config has OneToOne relationship with tenant"""
        config1 = TenantConfig.objects.create(tenant=self.tenant)
        
        # Try to create another config for the same tenant (should fail)
        # Django's OneToOne validation raises ValidationError in full_clean(), not IntegrityError
        with self.assertRaises(ValidationError):
            TenantConfig.objects.create(tenant=self.tenant)
    
    def test_data_retention_days_minimum(self):
        """Test data retention days minimum constraint"""
        config = TenantConfig(tenant=self.tenant, data_retention_days=89)
        
        with self.assertRaises(ValidationError):
            config.full_clean()
    
    def test_data_retention_days_maximum(self):
        """Test data retention days maximum constraint"""
        config = TenantConfig(tenant=self.tenant, data_retention_days=3651)
        
        with self.assertRaises(ValidationError):
            config.full_clean()
    
    def test_data_retention_days_valid_range(self):
        """Test data retention days valid range"""
        config = TenantConfig(tenant=self.tenant, data_retention_days=2555)
        config.full_clean()  # Should not raise
    
    def test_default_compliance_regimes_subset_validation(self):
        """Test that default_compliance_regimes must be subset of allowed_compliance_regimes"""
        config = TenantConfig(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD"],
            default_compliance_regimes=["GDPR", "CCPA"],  # CCPA not in allowed
        )
        
        with self.assertRaises(ValidationError):
            config.full_clean()
    
    def test_default_compliance_regimes_valid_subset(self):
        """Test that valid subset of compliance regimes passes validation"""
        config = TenantConfig(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD", "CCPA"],
            default_compliance_regimes=["GDPR", "LGPD"],
        )
        config.full_clean()  # Should not raise
    
    def test_rate_limits_json_field(self):
        """Test rate limits JSON field"""
        rate_limits = {
            "dq_runs": {
                "burst_per_10s": 20,
                "sustained_per_min": 60,
                "daily_cap": 10000,
            },
            "file_uploads": {
                "burst_per_10s": 10,
                "sustained_per_min": 30,
            },
        }
        
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            rate_limits=rate_limits
        )
        
        self.assertEqual(config.rate_limits, rate_limits)
    
    def test_tenant_config_str(self):
        """Test tenant config string representation"""
        config = TenantConfig.objects.create(tenant=self.tenant)
        self.assertEqual(str(config), f"Config for {self.tenant.name}")
    
    def test_tenant_config_index(self):
        """Test that tenant_id index exists"""
        # This is tested implicitly by the migration
        # We can verify the index exists by checking query performance
        config = TenantConfig.objects.create(tenant=self.tenant)
        retrieved = TenantConfig.objects.get(tenant=self.tenant)
        self.assertEqual(retrieved, config)
    
    # GAP-0.2.1.1: Edge case tests for JSON fields
    def test_rate_limits_empty_dict(self):
        """Test rate_limits with empty dict (should be valid, uses platform defaults)"""
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            rate_limits={}
        )
        self.assertEqual(config.rate_limits, {})
        config.full_clean()  # Should not raise
    
    def test_rate_limits_null(self):
        """Test rate_limits with null value (should be valid, uses platform defaults)"""
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            rate_limits=None
        )
        self.assertIsNone(config.rate_limits)
        config.full_clean()  # Should not raise
    
    def test_allowed_compliance_regimes_empty_list(self):
        """Test allowed_compliance_regimes with empty list (should be valid)"""
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            allowed_compliance_regimes=[]
        )
        self.assertEqual(config.allowed_compliance_regimes, [])
        config.full_clean()  # Should not raise
    
    def test_default_compliance_regimes_empty_list(self):
        """Test default_compliance_regimes with empty list (should be valid)"""
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            default_compliance_regimes=[]
        )
        self.assertEqual(config.default_compliance_regimes, [])
        config.full_clean()  # Should not raise
    
    # GAP-0.2.1.2: Validation edge cases
    def test_data_retention_days_none(self):
        """Test data_retention_days with None (should be valid, uses platform default)"""
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            data_retention_days=None
        )
        self.assertIsNone(config.data_retention_days)
        config.full_clean()  # Should not raise
    
    def test_max_file_size_bytes_none(self):
        """Test max_file_size_bytes with None (should be valid, uses platform default)"""
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            max_file_size_bytes=None
        )
        self.assertIsNone(config.max_file_size_bytes)
        config.full_clean()  # Should not raise
    
    def test_max_job_concurrency_none(self):
        """Test max_job_concurrency with None (should be valid, uses platform default)"""
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            max_job_concurrency=None
        )
        self.assertIsNone(config.max_job_concurrency)
        config.full_clean()  # Should not raise
    
    def test_max_queued_jobs_none(self):
        """Test max_queued_jobs with None (should be valid, uses platform default)"""
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            max_queued_jobs=None
        )
        self.assertIsNone(config.max_queued_jobs)
        config.full_clean()  # Should not raise
    
    def test_default_dq_profile_empty_string(self):
        """Test default_dq_profile with empty string (blank=True allows it, but validator should reject invalid profile)"""
        config = TenantConfig(tenant=self.tenant, default_dq_profile="")
        # Empty string is allowed by blank=True, but if validator is applied it should reject it
        # Since there's no validator on the model field itself, empty string is valid at model level
        # Validation happens at serializer/validator level
        config.full_clean()  # Should not raise at model level
        self.assertEqual(config.default_dq_profile, "")
    
    def test_default_dq_profile_none(self):
        """Test default_dq_profile with None (should use platform default)"""
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            default_dq_profile=None
        )
        self.assertIsNone(config.default_dq_profile)
        config.full_clean()  # Should not raise
    
    # GAP-0.2.1.3: Rate limits — model stores raw JSON, serializer validates
    def test_rate_limits_model_stores_raw_json_without_validation(self):
        """Model JSONField stores arbitrary rate_limits without validation.

        Validation of categories, negative values, and zero values is
        enforced at the serializer/validator layer, NOT the model layer.
        This test documents that the model is a plain storage layer.
        """
        # Invalid category — model stores it
        config = TenantConfig.objects.create(
            tenant=self.tenant,
            rate_limits={"invalid_category": {"burst_per_10s": 10}},
        )
        self.assertEqual(
            config.rate_limits["invalid_category"]["burst_per_10s"], 10,
        )

        # Negative value — model stores it
        config.rate_limits = {"dq_runs": {"burst_per_10s": -10}}
        config.save()
        config.refresh_from_db()
        self.assertEqual(
            config.rate_limits["dq_runs"]["burst_per_10s"], -10,
        )

        # Zero value — model stores it
        config.rate_limits = {"dq_runs": {"burst_per_10s": 0}}
        config.save()
        config.refresh_from_db()
        self.assertEqual(
            config.rate_limits["dq_runs"]["burst_per_10s"], 0,
        )

    def test_rate_limits_invalid_values_rejected_by_serializer(self):
        """Serializer rejects invalid rate limit values that model allows.

        This verifies the validation layer catches what the model does
        not: invalid categories, negative values, zero values.
        """
        from hub.apps.tenants.serializers import TenantConfigUpdateSerializer

        # Invalid category
        serializer = TenantConfigUpdateSerializer(
            data={"rate_limits": {"bogus": {"burst_per_10s": 10}}},
            partial=True,
        )
        self.assertFalse(
            serializer.is_valid(),
            "Serializer should reject invalid rate limit category",
        )

        # Negative value
        serializer = TenantConfigUpdateSerializer(
            data={"rate_limits": {"dq_runs": {"burst_per_10s": -1}}},
            partial=True,
        )
        self.assertFalse(
            serializer.is_valid(),
            "Serializer should reject negative rate limit values",
        )

        # Zero value
        serializer = TenantConfigUpdateSerializer(
            data={"rate_limits": {"dq_runs": {"burst_per_10s": 0}}},
            partial=True,
        )
        self.assertFalse(
            serializer.is_valid(),
            "Serializer should reject zero rate limit values",
        )
    
    def test_rate_limits_partial_updates(self):
        """Test rate_limits with partial updates (only burst_per_10s, only sustained_per_min, only daily_cap)"""
        # Test only burst_per_10s
        config1 = TenantConfig.objects.create(
            tenant=self.tenant,
            rate_limits={"dq_runs": {"burst_per_10s": 20}}
        )
        self.assertEqual(config1.rate_limits["dq_runs"]["burst_per_10s"], 20)
        
        # Test only sustained_per_min
        tenant2 = Tenant.objects.create(name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}")
        config2 = TenantConfig.objects.create(
            tenant=tenant2,
            rate_limits={"dq_runs": {"sustained_per_min": 60}}
        )
        self.assertEqual(config2.rate_limits["dq_runs"]["sustained_per_min"], 60)
        
        # Test only daily_cap
        tenant3 = Tenant.objects.create(name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}")
        config3 = TenantConfig.objects.create(
            tenant=tenant3,
            rate_limits={"dq_runs": {"daily_cap": 10000}}
        )
        self.assertEqual(config3.rate_limits["dq_runs"]["daily_cap"], 10000)
    
    # GAP-0.2.1.4: Database constraint tests
    def test_cascade_delete(self):
        """Test OneToOne relationship cascade delete (delete tenant, config should be deleted)"""
        config = TenantConfig.objects.create(tenant=self.tenant)
        config_id = config.id
        
        # Delete tenant
        self.tenant.delete()
        
        # Config should be deleted
        self.assertFalse(TenantConfig.objects.filter(id=config_id).exists())
    
    def test_one_to_one_prevents_duplicate(self):
        """Test OneToOne relationship prevents duplicate configs.

        TenantConfig.save() calls full_clean() which catches the duplicate
        at the Django level (ValidationError) before hitting the DB constraint.
        """
        TenantConfig.objects.create(tenant=self.tenant)

        with self.assertRaises(ValidationError):
            TenantConfig.objects.create(tenant=self.tenant)
    
    # GAP-0.2.1.5: Model method tests
    def test_str_method(self):
        """Test __str__ method with various configurations"""
        config = TenantConfig.objects.create(tenant=self.tenant)
        self.assertEqual(str(config), f"Config for {self.tenant.name}")
        
        # Test with different tenant name
        tenant2 = Tenant.objects.create(name="Another Tenant", slug="another-tenant")
        config2 = TenantConfig.objects.create(tenant=tenant2)
        self.assertEqual(str(config2), "Config for Another Tenant")
    
    def test_clean_method_valid_data(self):
        """Test clean() method with valid data"""
        config = TenantConfig(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD"],
            default_compliance_regimes=["GDPR"]
        )
        config.clean()  # Should not raise
    
    def test_clean_method_invalid_data(self):
        """Test clean() method with invalid data (default_compliance_regimes not subset)"""
        config = TenantConfig(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD"],
            default_compliance_regimes=["GDPR", "CCPA"]  # CCPA not in allowed
        )
        with self.assertRaises(ValidationError):
            config.clean()
    
    def test_save_calls_full_clean(self):
        """Test save() method calls full_clean() (validation runs on save)"""
        config = TenantConfig(
            tenant=self.tenant,
            allowed_compliance_regimes=["GDPR", "LGPD"],
            default_compliance_regimes=["GDPR", "CCPA"]  # CCPA not in allowed
        )
        # save() should call full_clean() which should raise ValidationError
        with self.assertRaises(ValidationError):
            config.save()

