"""
Unit tests for TenantConfig validators.

GAP-0.2.3: Comprehensive validator tests covering all validation functions.
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError

from hub.apps.tenants.validators import (
    validate_dq_profile,
    validate_compliance_regimes,
    validate_rate_limits,
    get_platform_defaults,
    VALID_DQ_PROFILES,
    VALID_COMPLIANCE_REGIMES,
    PLATFORM_MAX_RATE_LIMITS,
)


pytestmark = pytest.mark.django_db(transaction=True)


class ValidateDQProfileTest(TestCase):
    """Test validate_dq_profile function"""
    
    # GAP-0.2.3.1: validate_dq_profile tests
    def test_valid_profile_keys(self):
        """Test valid profile keys (intake_basic_gx, intake_basic_soda)"""
        for profile in VALID_DQ_PROFILES:
            try:
                validate_dq_profile(profile)
            except ValidationError:
                self.fail(f"validate_dq_profile raised ValidationError for valid profile: {profile}")
    
    def test_invalid_profile_key(self):
        """Test invalid profile key (not in VALID_DQ_PROFILES)"""
        with self.assertRaises(ValidationError) as cm:
            validate_dq_profile("invalid_profile")
        
        error_message = str(cm.exception)
        self.assertIn("Invalid DQ profile key", error_message)
        self.assertIn("invalid_profile", error_message)
    
    def test_empty_string_passes_validation(self):
        """Empty string is treated as 'not set' (falsy) and passes validation.

        The validator uses ``if value`` guard — empty string is falsy,
        so it skips the allowed-list check. This matches the model's
        ``blank=True`` behavior: empty means 'use platform default'.
        """
        # Should NOT raise — empty string is treated as "not set"
        validate_dq_profile("")  # no exception expected
    
    def test_none_value(self):
        """Test None value (should be valid, uses platform default)"""
        # None should pass (validator only checks if value is truthy)
        try:
            validate_dq_profile(None)
        except ValidationError:
            self.fail("validate_dq_profile raised ValidationError for None")


class ValidateComplianceRegimesTest(TestCase):
    """Test validate_compliance_regimes function"""
    
    # GAP-0.2.3.2: validate_compliance_regimes tests
    def test_valid_regimes(self):
        """Test valid regimes (GDPR, LGPD, CCPA, HIPAA, SOX)"""
        for regime in VALID_COMPLIANCE_REGIMES:
            try:
                validate_compliance_regimes([regime])
            except ValidationError:
                self.fail(f"validate_compliance_regimes raised ValidationError for valid regime: {regime}")
        
        # Test multiple valid regimes
        try:
            validate_compliance_regimes(VALID_COMPLIANCE_REGIMES)
        except ValidationError:
            self.fail("validate_compliance_regimes raised ValidationError for all valid regimes")
    
    def test_invalid_regime(self):
        """Test invalid regime (not in VALID_COMPLIANCE_REGIMES)"""
        with self.assertRaises(ValidationError) as cm:
            validate_compliance_regimes(["INVALID_REGIME"])
        
        error_message = str(cm.exception)
        self.assertIn("Invalid compliance regimes", error_message)
        self.assertIn("INVALID_REGIME", error_message)
    
    def test_empty_list(self):
        """Test empty list (should be valid)"""
        try:
            validate_compliance_regimes([])
        except ValidationError:
            self.fail("validate_compliance_regimes raised ValidationError for empty list")
    
    def test_none_value(self):
        """Test None value (should be invalid - must be list)"""
        with self.assertRaises(ValidationError) as cm:
            validate_compliance_regimes(None)
        
        error_message = str(cm.exception)
        self.assertIn("must be a list", error_message)
    
    def test_non_list_value(self):
        """Test non-list value (should be invalid)"""
        with self.assertRaises(ValidationError) as cm:
            validate_compliance_regimes("GDPR")  # String instead of list
        
        error_message = str(cm.exception)
        self.assertIn("must be a list", error_message)
    
    def test_duplicate_regimes(self):
        """Test duplicate regimes in list (should be valid or deduplicated)"""
        # Validator doesn't check for duplicates, so it should pass
        try:
            validate_compliance_regimes(["GDPR", "GDPR", "LGPD"])
        except ValidationError:
            self.fail("validate_compliance_regimes raised ValidationError for duplicate regimes")
    
    def test_mixed_valid_invalid_regimes(self):
        """Test list with both valid and invalid regimes"""
        with self.assertRaises(ValidationError) as cm:
            validate_compliance_regimes(["GDPR", "INVALID_REGIME", "LGPD"])
        
        error_message = str(cm.exception)
        self.assertIn("Invalid compliance regimes", error_message)
        self.assertIn("INVALID_REGIME", error_message)


class ValidateRateLimitsTest(TestCase):
    """Test validate_rate_limits function"""
    
    # GAP-0.2.3.3: validate_rate_limits tests
    def test_valid_rate_limits_for_each_category(self):
        """Test valid rate limits for each category"""
        for category in PLATFORM_MAX_RATE_LIMITS.keys():
            platform_max = PLATFORM_MAX_RATE_LIMITS[category]
            limits = {}
            
            if "burst_per_10s" in platform_max:
                limits["burst_per_10s"] = platform_max["burst_per_10s"]
            if "sustained_per_min" in platform_max:
                limits["sustained_per_min"] = platform_max["sustained_per_min"]
            if "daily_cap" in platform_max:
                limits["daily_cap"] = platform_max["daily_cap"]
            
            try:
                validate_rate_limits({category: limits})
            except ValidationError:
                self.fail(f"validate_rate_limits raised ValidationError for valid category {category}")
    
    def test_invalid_category(self):
        """Test invalid category (not in PLATFORM_MAX_RATE_LIMITS)"""
        with self.assertRaises(ValidationError) as cm:
            validate_rate_limits({"invalid_category": {"burst_per_10s": 10}})
        
        error_message = str(cm.exception)
        self.assertIn("Invalid rate limit category", error_message)
        self.assertIn("invalid_category", error_message)
    
    def test_rate_limits_exceeding_platform_maximums(self):
        """Test rate limits exceeding platform maximums (burst_per_10s, sustained_per_min, daily_cap)"""
        # Test burst_per_10s exceeding maximum
        with self.assertRaises(ValidationError) as cm:
            validate_rate_limits({
                "dq_runs": {
                    "burst_per_10s": PLATFORM_MAX_RATE_LIMITS["dq_runs"]["burst_per_10s"] + 1
                }
            })
        error_message = str(cm.exception)
        self.assertIn("exceeds platform maximum", error_message)
        
        # Test sustained_per_min exceeding maximum
        with self.assertRaises(ValidationError) as cm:
            validate_rate_limits({
                "dq_runs": {
                    "sustained_per_min": PLATFORM_MAX_RATE_LIMITS["dq_runs"]["sustained_per_min"] + 1
                }
            })
        error_message = str(cm.exception)
        self.assertIn("exceeds platform maximum", error_message)
        
        # Test daily_cap exceeding maximum
        with self.assertRaises(ValidationError) as cm:
            validate_rate_limits({
                "dq_runs": {
                    "daily_cap": PLATFORM_MAX_RATE_LIMITS["dq_runs"]["daily_cap"] + 1
                }
            })
        error_message = str(cm.exception)
        self.assertIn("exceeds platform maximum", error_message)
    
    def test_rate_limits_at_platform_maximums(self):
        """Test rate limits at platform maximums (boundary condition)"""
        # Test at maximum (should be valid)
        try:
            validate_rate_limits({
                "dq_runs": {
                    "burst_per_10s": PLATFORM_MAX_RATE_LIMITS["dq_runs"]["burst_per_10s"],
                    "sustained_per_min": PLATFORM_MAX_RATE_LIMITS["dq_runs"]["sustained_per_min"],
                    "daily_cap": PLATFORM_MAX_RATE_LIMITS["dq_runs"]["daily_cap"]
                }
            })
        except ValidationError:
            self.fail("validate_rate_limits raised ValidationError for limits at platform maximum")
    
    def test_rate_limits_below_platform_maximums(self):
        """Test rate limits below platform maximums (should be valid)"""
        try:
            validate_rate_limits({
                "dq_runs": {
                    "burst_per_10s": PLATFORM_MAX_RATE_LIMITS["dq_runs"]["burst_per_10s"] - 1,
                    "sustained_per_min": PLATFORM_MAX_RATE_LIMITS["dq_runs"]["sustained_per_min"] - 1,
                    "daily_cap": PLATFORM_MAX_RATE_LIMITS["dq_runs"]["daily_cap"] - 1
                }
            })
        except ValidationError:
            self.fail("validate_rate_limits raised ValidationError for limits below platform maximum")
    
    def test_daily_cap_for_category_that_doesnt_support_it(self):
        """Test daily_cap for category that doesn't support it (should be invalid)"""
        # file_uploads doesn't support daily_cap
        with self.assertRaises(ValidationError) as cm:
            validate_rate_limits({
                "file_uploads": {
                    "daily_cap": 1000
                }
            })
        
        error_message = str(cm.exception)
        self.assertIn("does not support daily_cap", error_message)
    
    def test_empty_dict(self):
        """Test empty dict (should be valid, uses platform defaults)"""
        try:
            validate_rate_limits({})
        except ValidationError:
            self.fail("validate_rate_limits raised ValidationError for empty dict")
    
    def test_none_value(self):
        """Test None value (should be invalid - must be dict)"""
        with self.assertRaises(ValidationError) as cm:
            validate_rate_limits(None)
        
        error_message = str(cm.exception)
        self.assertIn("must be a dictionary", error_message)
    
    def test_non_dict_value(self):
        """Test non-dict value (should be invalid)"""
        with self.assertRaises(ValidationError) as cm:
            validate_rate_limits("not_a_dict")
        
        error_message = str(cm.exception)
        self.assertIn("must be a dictionary", error_message)
    
    def test_multiple_categories(self):
        """Test rate limits with multiple categories"""
        try:
            validate_rate_limits({
                "dq_runs": {
                    "burst_per_10s": 20,
                    "sustained_per_min": 60,
                    "daily_cap": 10000
                },
                "file_uploads": {
                    "burst_per_10s": 10,
                    "sustained_per_min": 30
                }
            })
        except ValidationError:
            self.fail("validate_rate_limits raised ValidationError for multiple valid categories")


class GetPlatformDefaultsTest(TestCase):
    """Test get_platform_defaults function"""
    
    # GAP-0.2.3.4: get_platform_defaults tests
    def test_platform_defaults_structure(self):
        """Test platform defaults structure (all required fields present)"""
        defaults = get_platform_defaults()
        
        required_fields = [
            "default_dq_profile",
            "allowed_compliance_regimes",
            "default_compliance_regimes",
            "data_retention_days",
            "rate_limits",
            "max_file_size_bytes",
            "max_job_concurrency",
            "max_queued_jobs",
        ]
        
        for field in required_fields:
            self.assertIn(field, defaults, f"Platform defaults missing required field: {field}")
    
    def test_platform_defaults_values(self):
        """Test platform defaults values (match expected defaults)"""
        defaults = get_platform_defaults()
        
        self.assertEqual(defaults["default_dq_profile"], "intake_basic_gx")
        from hub.apps.tenants.validators import VALID_COMPLIANCE_REGIMES
        self.assertEqual(
            defaults["allowed_compliance_regimes"],
            list(VALID_COMPLIANCE_REGIMES),
        )
        self.assertEqual(defaults["default_compliance_regimes"], ["GDPR", "LGPD"])
        self.assertEqual(defaults["data_retention_days"], 2555)
        self.assertEqual(defaults["max_file_size_bytes"], 10737418240)
        self.assertEqual(defaults["max_job_concurrency"], 5)
        self.assertEqual(defaults["max_queued_jobs"], 50)
    
    def test_platform_defaults_rate_limits_structure(self):
        """Test platform defaults rate_limits structure (all categories present)"""
        defaults = get_platform_defaults()
        rate_limits = defaults["rate_limits"]
        
        expected_categories = [
            "dq_runs",
            "compliance_runs",
            "file_uploads",
            "contract_validation",
            "catalog_reads",
            "sparql_queries",
        ]
        
        for category in expected_categories:
            self.assertIn(category, rate_limits, f"Platform defaults rate_limits missing category: {category}")
    
    def test_platform_defaults_immutability(self):
        """Test platform defaults immutability (should not be modified)"""
        defaults1 = get_platform_defaults()
        original_rate_limits = defaults1["rate_limits"].copy()
        
        # Try to modify
        defaults1["rate_limits"]["new_category"] = {"burst_per_10s": 10}
        defaults1["default_dq_profile"] = "modified"
        
        # Get fresh defaults
        defaults2 = get_platform_defaults()
        
        # Fresh defaults should not be affected
        self.assertNotIn("new_category", defaults2["rate_limits"])
        self.assertEqual(defaults2["default_dq_profile"], "intake_basic_gx")
        
        # Original should be modified (it's a dict reference)
        # But the function should return a new dict each time
        # Actually, the function returns a new dict, so modifications to defaults1 shouldn't affect defaults2
        # But to be safe, let's check that the function returns a new dict
        self.assertIsNot(defaults1, defaults2)

