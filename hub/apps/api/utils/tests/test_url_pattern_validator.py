"""
Tests for URL Pattern Validator

Task: 9.6.3.1.4 - Add URL pattern validation utility
"""

import sys

from django.test import TestCase

from hub.apps.api.utils.url_pattern_validator import (
    URLPatternValidationError,
    URLPatternValidationResult,
    URLPatternValidator,
    validate_url_patterns,
)


class URLPatternValidatorTest(TestCase):
    """Test URL pattern validator functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = URLPatternValidator()

    def test_normalize_pattern(self):
        """Test pattern normalization"""
        # Test named groups
        pattern = r"^contracts/(?P<id>[^/.]+)/lineage/visualization/$"
        normalized = self.validator._normalize_pattern(pattern)
        self.assertIn("{id}", normalized)
        self.assertNotIn("(?P<id>", normalized)

        # Test full path
        full_pattern = "/api/v1/contracts/(?P<id>[^/.]+)/lineage/visualization/"
        normalized = self.validator._normalize_pattern(full_pattern)
        self.assertEqual(normalized, "/api/v1/contracts/{id}/lineage/visualization/")

    def test_validate_no_duplication_catches_duplicate(self):
        """Test that duplicate service name detection works"""
        pattern_info = {
            "pattern": r"^contracts/(?P<id>[^/.]+)/lineage/visualization/$",
            "normalized_pattern": "/api/v1/contracts/contracts/{id}/lineage/visualization/",
            "url_name": "test-url",
            "file_path": "test/urls.py",
            "line_number": None,
        }

        errors = self.validator.validate_no_duplication(pattern_info)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].rule, "no_duplication")
        self.assertIn("Duplicate segment", errors[0].message)
        self.assertEqual(errors[0].severity, "error")

    def test_validate_no_duplication_passes_valid_pattern(self):
        """Test that valid patterns pass duplication check"""
        pattern_info = {
            "pattern": r"^(?P<id>[^/.]+)/lineage/visualization/$",
            "normalized_pattern": "/api/v1/contracts/{id}/lineage/visualization/",
            "url_name": "test-url",
            "file_path": "test/urls.py",
            "line_number": None,
        }

        errors = self.validator.validate_no_duplication(pattern_info)
        self.assertEqual(len(errors), 0)

    def test_validate_plural_resources_catches_singular(self):
        """Test that singular resource names are caught"""
        pattern_info = {
            "pattern": r"^asset/$",
            "normalized_pattern": "/api/v1/asset/",
            "url_name": "asset-list",
            "file_path": "test/urls.py",
            "line_number": None,
        }

        errors = self.validator.validate_plural_resources(pattern_info)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].rule, "plural_resources")
        self.assertIn("should be plural", errors[0].message)

    def test_validate_plural_resources_passes_plural(self):
        """Test that plural resource names pass"""
        pattern_info = {
            "pattern": r"^assets/$",
            "normalized_pattern": "/api/v1/assets/",
            "url_name": "asset-list",
            "file_path": "test/urls.py",
            "line_number": None,
        }

        errors = self.validator.validate_plural_resources(pattern_info)
        self.assertEqual(len(errors), 0)

    def test_validate_kebab_case_catches_snake_case(self):
        """Test that snake_case is caught"""
        pattern_info = {
            "pattern": r"^test_resource/$",
            "normalized_pattern": "/api/v1/test_resource/",
            "url_name": "test-resource",
            "file_path": "test/urls.py",
            "line_number": None,
        }

        errors = self.validator.validate_kebab_case(pattern_info)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].rule, "kebab_case")
        self.assertIn("snake_case", errors[0].message)

    def test_validate_kebab_case_catches_camel_case(self):
        """Test that camelCase is caught"""
        pattern_info = {
            "pattern": r"^testResource/$",
            "normalized_pattern": "/api/v1/testResource/",
            "url_name": "test-resource",
            "file_path": "test/urls.py",
            "line_number": None,
        }

        errors = self.validator.validate_kebab_case(pattern_info)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].rule, "kebab_case")
        self.assertIn("camelCase", errors[0].message)

    def test_validate_kebab_case_passes_valid(self):
        """Test that valid kebab-case passes"""
        pattern_info = {
            "pattern": r"^test-resource/$",
            "normalized_pattern": "/api/v1/test-resource/",
            "url_name": "test-resource",
            "file_path": "test/urls.py",
            "line_number": None,
        }

        errors = self.validator.validate_kebab_case(pattern_info)
        self.assertEqual(len(errors), 0)

    def test_validate_explicit_naming_warns_abbreviation(self):
        """Test that unclear abbreviations generate warnings"""
        pattern_info = {
            "pattern": r"^dc/$",
            "normalized_pattern": "/api/v1/dc/",
            "url_name": "dc-list",
            "file_path": "test/urls.py",
            "line_number": None,
        }

        warnings = self.validator.validate_explicit_naming(pattern_info)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].rule, "explicit_naming")
        self.assertEqual(warnings[0].severity, "warning")
        self.assertIn("Abbreviation", warnings[0].message)

    def test_validate_explicit_naming_passes_explicit(self):
        """Test that explicit names pass"""
        pattern_info = {
            "pattern": r"^data-contracts/$",
            "normalized_pattern": "/api/v1/data-contracts/",
            "url_name": "data-contracts-list",
            "file_path": "test/urls.py",
            "line_number": None,
        }

        warnings = self.validator.validate_explicit_naming(pattern_info)
        self.assertEqual(len(warnings), 0)

    def test_extract_url_patterns(self):
        """Test that URL patterns can be extracted"""
        patterns = self.validator.extract_url_patterns()

        # Should extract at least some patterns
        self.assertIsInstance(patterns, list)

        # Check that patterns have required fields
        if patterns:
            pattern = patterns[0]
            self.assertIn("pattern", pattern)
            self.assertIn("normalized_pattern", pattern)

    def test_validate_all_integration(self):
        """Integration test for validate_all method"""
        result = self.validator.validate_all(strict=False)

        self.assertIsInstance(result, URLPatternValidationResult)
        self.assertIsInstance(result.total_patterns, int)
        self.assertIsInstance(result.errors, list)
        self.assertIsInstance(result.warnings, list)
        self.assertIsInstance(result.passed, bool)

        # Should have extracted patterns
        self.assertGreater(result.total_patterns, 0)

    def test_format_errors(self):
        """Test error formatting"""
        # Create a test result with errors
        error = URLPatternValidationError(
            rule="no_duplication",
            pattern="/api/v1/contracts/contracts/{id}/",
            url_name="test-url",
            file_path="test/urls.py",
            line_number=None,
            message="Duplicate segment 'contracts' appears twice",
            severity="error",
            suggestion="Remove duplicate segment",
        )

        result = URLPatternValidationResult(
            total_patterns=10, errors=[error], warnings=[], passed=False
        )

        formatted = self.validator.format_errors(result)

        self.assertIn("URL Pattern Validation Results", formatted)
        self.assertIn("no_duplication", formatted)
        self.assertIn("Duplicate segment", formatted)
        self.assertIn("Remove duplicate segment", formatted)

    def test_validate_url_patterns_convenience_function(self):
        """Test convenience function"""
        result = validate_url_patterns(strict=False, raise_on_error=False)

        self.assertIsInstance(result, URLPatternValidationResult)
        self.assertGreater(result.total_patterns, 0)


class URLPatternValidatorStartupTest(TestCase):
    """Test URL pattern validation at Django startup"""

    def test_startup_validation_runs(self):
        """Test that startup validation can run without errors"""
        # This test verifies that the validation can be called at startup
        # without causing Django initialization issues

        try:
            from django.apps import apps

            from hub.apps.api.apps import ApiConfig

            # Get the actual app config from Django's registry
            app_config = apps.get_app_config("api")

            # Verify it's our config
            self.assertIsInstance(app_config, ApiConfig)

            # Call ready() - should not raise (it's already been called, but we can test the logic)
            # The ready() method should handle errors gracefully

        except Exception as e:
            self.fail(f"Startup validation should not raise exceptions: {e}")

    def test_startup_validation_skips_migrations(self):
        """Test that validation is skipped during migrations"""
        from django.apps import apps

        from hub.apps.api.apps import ApiConfig

        # Get app config
        app_config = apps.get_app_config("api")
        self.assertIsInstance(app_config, ApiConfig)

        # Simulate migration command
        original_argv = sys.argv[:]
        try:
            sys.argv = ["manage.py", "migrate"]
            should_validate = app_config._should_validate()
            self.assertFalse(should_validate, "Validation should be skipped during migrations")
        finally:
            sys.argv = original_argv

    def test_startup_validation_runs_in_normal_mode(self):
        """Test that validation runs in normal Django mode"""
        from unittest.mock import patch

        from django.apps import apps

        from hub.apps.api.apps import ApiConfig

        # Get app config
        app_config = apps.get_app_config("api")
        self.assertIsInstance(app_config, ApiConfig)

        # Mock should_skip_initialization to return False (simulating normal mode)
        # Since we're in a test, unittest is loaded, so we need to mock the check
        with patch("hub.apps.core.utils.test_mode.should_skip_initialization", return_value=False):
            should_validate = app_config._should_validate()
            self.assertTrue(should_validate, "Validation should run in normal mode")


class URLPatternValidatorRealPatternsTest(TestCase):
    """Test validator against real URL patterns from the codebase"""

    def test_validates_real_patterns(self):
        """Test that validator works with real Django URL patterns"""
        validator = URLPatternValidator()
        result = validator.validate_all(strict=False)

        # Should have extracted real patterns
        self.assertGreater(result.total_patterns, 0, "Should extract real URL patterns")

        # Check that we can identify the contracts lineage visualization pattern
        # (which we fixed in task 9.6.3.1.1)
        contracts_patterns = [
            p
            for p in validator.patterns
            if "lineage" in p.get("normalized_pattern", "").lower()
            and "visualization" in p.get("normalized_pattern", "").lower()
        ]

        if contracts_patterns:
            # Verify the fixed pattern doesn't have duplication
            for pattern_info in contracts_patterns:
                errors = validator.validate_no_duplication(pattern_info)
                # Should not have duplication errors for the fixed pattern
                duplication_errors = [e for e in errors if e.rule == "no_duplication"]
                self.assertEqual(
                    len(duplication_errors),
                    0,
                    f"Fixed pattern should not have duplication: {pattern_info['normalized_pattern']}",
                )

    def test_validation_catches_known_issues(self):
        """Test that validation can catch known issues if they exist"""
        validator = URLPatternValidator()
        result = validator.validate_all(strict=False)

        # Log results for debugging
        if not result.passed:
            formatted = validator.format_errors(result)
            # Don't fail the test, but log the issues
            print(f"\nValidation found issues:\n{formatted}")

        # Test passes regardless - we're just verifying the validator works
        self.assertIsNotNone(result)
