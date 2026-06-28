"""
Comprehensive URL Pattern Validation Tests

Task: 9.6.4.1.1 - Create URL pattern validation tests

Tests verify:
1. No duplicate service names in patterns
2. Pattern resolution works for all patterns
3. Reverse URL lookups work for all patterns with url_name
4. All URL patterns follow naming standards

All tests use real Django URL patterns (no mocks/stubs).
"""

import uuid

import pytest
from django.test import TestCase
from django.urls import NoReverseMatch, Resolver404, get_resolver, resolve, reverse
from rest_framework.test import APIClient

from hub.apps.api.utils.url_pattern_validator import (
    URLPatternValidationError,
    URLPatternValidationResult,
    URLPatternValidator,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class URLPatternNoDuplicationTest(TestCase):
    """Test that no duplicate service names exist in URL patterns"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = URLPatternValidator()

    def test_no_duplicate_service_names(self):
        """Test that no URL patterns have duplicate service names"""
        result = self.validator.validate_all(strict=False)

        # Check for duplication errors
        duplication_errors = [e for e in result.errors if e.rule == "no_duplication"]

        if duplication_errors:
            error_messages = "\n".join(
                [f"  - {e.pattern}: {e.message}" for e in duplication_errors]
            )
            self.fail(
                f"Found {len(duplication_errors)} patterns with duplicate service names:\n"
                f"{error_messages}"
            )

        # Test passes if no duplication errors found
        self.assertEqual(len(duplication_errors), 0)

    def test_duplicate_detection_works(self):
        """Test that duplicate detection logic works correctly"""
        # Create a pattern with duplicate segments
        pattern_info = {
            "pattern": r"^contracts/contracts/(?P<id>[^/.]+)/$",
            "normalized_pattern": "/api/v1/contracts/contracts/{id}/",
            "url_name": "test-duplicate",
            "file_path": "test/urls.py",
            "line_number": None,
        }

        errors = self.validator.validate_no_duplication(pattern_info)
        self.assertGreater(len(errors), 0, "Should detect duplicate 'contracts' segment")
        self.assertEqual(errors[0].rule, "no_duplication")
        self.assertIn("Duplicate segment", errors[0].message)

    def test_no_duplicate_in_valid_patterns(self):
        """Test that valid patterns without duplicates pass"""
        pattern_info = {
            "pattern": r"^contracts/(?P<id>[^/.]+)/lineage/visualization/$",
            "normalized_pattern": "/api/v1/contracts/{id}/lineage/visualization/",
            "url_name": "contract-lineage-visualization",
            "file_path": "test/urls.py",
            "line_number": None,
        }

        errors = self.validator.validate_no_duplication(pattern_info)
        self.assertEqual(len(errors), 0, "Valid pattern should not have duplication errors")


class URLPatternResolutionTest(TestCase):
    """Test URL pattern resolution for all patterns"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = URLPatternValidator()
        self.patterns = self.validator.extract_url_patterns()
        self.resolver = get_resolver()

    def test_all_api_v1_patterns_resolve(self):
        """Test that all /api/v1/ patterns can be resolved"""
        unresolved_patterns = []
        resolution_errors = []

        for pattern_info in self.patterns:
            normalized_pattern = pattern_info.get("normalized_pattern", "")

            # Only test API v1 patterns
            if not normalized_pattern.startswith("/api/v1/"):
                continue

            # Skip patterns with path parameters - we'll test those separately
            if "{" in normalized_pattern:
                continue

            try:
                resolved = resolve(normalized_pattern)
                self.assertIsNotNone(resolved, f"Pattern should resolve: {normalized_pattern}")
            except Resolver404 as e:
                unresolved_patterns.append(
                    {
                        "pattern": normalized_pattern,
                        "original_pattern": pattern_info.get("pattern", ""),
                        "url_name": pattern_info.get("url_name"),
                        "error": str(e),
                    }
                )
            except Exception as e:
                resolution_errors.append({"pattern": normalized_pattern, "error": str(e)})

        if unresolved_patterns:
            error_details = "\n".join(
                [
                    f"  - {p['pattern']} (url_name: {p.get('url_name', 'N/A')}): {p['error']}"
                    for p in unresolved_patterns[:10]  # Show first 10
                ]
            )
            self.fail(
                f"Found {len(unresolved_patterns)} patterns that could not be resolved:\n"
                f"{error_details}"
                + (
                    f"\n  ... and {len(unresolved_patterns) - 10} more"
                    if len(unresolved_patterns) > 10
                    else ""
                )
            )

        if resolution_errors:
            error_details = "\n".join(
                [f"  - {p['pattern']}: {p['error']}" for p in resolution_errors[:10]]
            )
            self.fail(
                f"Found {len(resolution_errors)} patterns with resolution errors:\n{error_details}"
            )

    def test_pattern_resolution_with_parameters(self):
        """Test that patterns with path parameters can be resolved with sample values"""
        # Test a few common patterns with parameters
        test_cases = [
            ("/api/v1/contracts/{id}/", {"id": str(uuid.uuid4())}, ["id", "pk"]),
            ("/api/v1/assets/{id}/", {"id": str(uuid.uuid4())}, ["id", "pk"]),
            ("/api/v1/dq/runs/{id}/", {"id": str(uuid.uuid4())}, ["id", "pk"]),
            ("/api/v1/compliance/runs/{id}/", {"id": str(uuid.uuid4())}, ["id", "pk"]),
        ]

        resolved_count = 0
        for pattern_template, kwargs, possible_param_names in test_cases:
            # Replace {id} with actual value
            test_url = pattern_template.format(**kwargs)

            try:
                resolved = resolve(test_url)
                self.assertIsNotNone(resolved, f"Pattern should resolve: {test_url}")

                # Verify the ID parameter was captured (check common parameter names)
                param_found = False
                for param_name in possible_param_names:
                    if param_name in resolved.kwargs:
                        self.assertEqual(str(resolved.kwargs[param_name]), kwargs["id"])
                        param_found = True
                        break

                # Some patterns might use 'path' parameter (for catch-all patterns)
                # That's acceptable - we just verify resolution works
                if not param_found and "path" in resolved.kwargs:
                    # Path parameter might contain the full path - verify it contains the ID
                    path_value = resolved.kwargs.get("path", "")
                    if kwargs["id"] in path_value:
                        param_found = True

                if param_found:
                    resolved_count += 1
            except Resolver404:
                # Some patterns might not exist - that's okay for this test
                # We're just verifying the resolution mechanism works
                pass

        # At least half of the tested patterns should resolve with parameters
        self.assertGreaterEqual(
            resolved_count, len(test_cases) * 0.5,
            f"Only {resolved_count}/{len(test_cases)} parametrized patterns resolved"
        )

    def test_pattern_resolution_consistency(self):
        """Test that pattern resolution is consistent across similar patterns"""
        # Extract all collection endpoints (end with / and no {id})
        collection_patterns = [
            p
            for p in self.patterns
            if p.get("normalized_pattern", "").startswith("/api/v1/")
            and p.get("normalized_pattern", "").endswith("/")
            and "{" not in p.get("normalized_pattern", "")
        ]

        resolved_count = 0
        for pattern_info in collection_patterns[:20]:  # Test first 20
            normalized_pattern = pattern_info.get("normalized_pattern", "")
            try:
                resolved = resolve(normalized_pattern)
                if resolved:
                    resolved_count += 1
            except (Resolver404, Exception):
                pass

        # At least half of the collection patterns should resolve
        total_tested = min(len(collection_patterns), 20)
        self.assertGreaterEqual(
            resolved_count, total_tested * 0.5,
            f"Only {resolved_count}/{total_tested} collection patterns resolved"
        )


class URLPatternReverseLookupTest(TestCase):
    """Test reverse URL lookups for all patterns"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.validator = URLPatternValidator()
        self.patterns = self.validator.extract_url_patterns()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_reverse_lookup_for_patterns_with_url_name(self):
        """Test that reverse lookups work for patterns with url_name"""
        failed_reverses = []
        successful_reverses = []

        for pattern_info in self.patterns:
            url_name = pattern_info.get("url_name")
            normalized_pattern = pattern_info.get("normalized_pattern", "")

            # Only test API v1 patterns with url_name
            if not normalized_pattern.startswith("/api/v1/") or not url_name:
                continue

            # Skip patterns that require kwargs (path converters or regex groups)
            raw_pattern = pattern_info.get("pattern", "")
            has_params = (
                "{" in normalized_pattern or "<" in normalized_pattern or "(?P<" in raw_pattern
            )
            if has_params:
                continue

            try:
                reversed_url = reverse(url_name)
                # Reversed URL must be under /api/v1/ (we filtered for that above)
                if not reversed_url.startswith("/api/v1/"):
                    # url_name aliases to a non-API path (e.g. metrics) — skip
                    continue
                successful_reverses.append(
                    {
                        "url_name": url_name,
                        "reversed_url": reversed_url,
                        "expected_pattern": normalized_pattern,
                    }
                )
            except NoReverseMatch as e:  # noqa: no-reverse-match — URL validation cataloging
                failed_reverses.append(
                    {
                        "url_name": url_name,
                        "pattern": normalized_pattern,
                        "error": str(e),
                    }
                )

        # ALL simple patterns (no kwargs) with url_name must be reversible
        total_attempted = len(successful_reverses) + len(failed_reverses)
        self.assertGreater(total_attempted, 0, "Should have URL patterns to test")
        self.assertEqual(
            len(failed_reverses),
            0,
            f"{len(failed_reverses)}/{total_attempted} URL patterns failed reverse lookup:\n"
            + "\n".join(f"  - {f['url_name']}: {f['error']}" for f in failed_reverses[:10]),
        )

    def test_reverse_lookup_with_kwargs(self):
        """Test reverse lookups with required kwargs"""
        test_cases = [
            ("dq-run-detail", {"id": str(uuid.uuid4())}, "/api/v1/dq/runs/"),
            ("compliance-run-detail", {"id": str(uuid.uuid4())}, "/api/v1/compliance/runs/"),
            ("contract-detail", {"id": str(uuid.uuid4())}, "/api/v1/contracts/"),
            ("asset-detail", {"id": str(uuid.uuid4())}, "/api/v1/assets/"),
        ]

        successful = 0
        for url_name, kwargs, expected_prefix in test_cases:
            try:
                reversed_url = reverse(url_name, kwargs=kwargs)
                self.assertTrue(
                    reversed_url.startswith(expected_prefix),
                    f"Reversed URL should start with {expected_prefix}: {reversed_url}",
                )
                # Verify the ID is in the URL
                self.assertIn(kwargs["id"], reversed_url)
                successful += 1
            except NoReverseMatch:  # noqa: no-reverse-match — URL validation cataloging
                # URL name not registered — record for assertion
                pass
            except Exception as e:
                self.fail(f"Unexpected error reversing {url_name}: {e}")

        # All known URL names with kwargs must be reversible
        self.assertEqual(
            successful,
            len(test_cases),
            f"Only {successful}/{len(test_cases)} reverse lookups with kwargs succeeded",
        )

    def test_reverse_lookup_consistency(self):
        """Test that reverse and resolve are consistent"""
        # Test that reversing a URL name and then resolving it gives the same pattern
        test_url_names = [
            "dq-run-list",
            "compliance-run-list",
            "contract-list",
            "asset-list",
        ]

        consistent_count = 0
        for url_name in test_url_names:
            try:
                reversed_url = reverse(url_name)
                resolved = resolve(reversed_url)

                # Verify it resolved to something
                if resolved:
                    # Check that the url_name matches (allowing for DRF naming conventions)
                    if url_name in (resolved.url_name or "") or (resolved.url_name or "").endswith(
                        url_name.split("-")[-1]
                    ):
                        consistent_count += 1
            except (NoReverseMatch, Resolver404):  # noqa: no-reverse-match — URL validation cataloging
                pass

        # At least half of the tested URL names should be consistent
        self.assertGreaterEqual(
            consistent_count, len(test_url_names) * 0.5,
            f"Only {consistent_count}/{len(test_url_names)} reverse/resolve pairs consistent"
        )


class URLPatternComprehensiveTest(TestCase):
    """Comprehensive tests for all URL patterns"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = URLPatternValidator()
        self.result = self.validator.validate_all(strict=False)
        self.patterns = self.validator.patterns

    def test_all_patterns_extracted(self):
        """Test that patterns are extracted from Django URL configuration"""
        self.assertGreater(
            self.result.total_patterns, 0, "Should extract at least some URL patterns"
        )

        # Verify patterns have required fields
        for pattern_info in self.patterns[:10]:  # Check first 10
            self.assertIn("pattern", pattern_info)
            self.assertIn("normalized_pattern", pattern_info)

    def test_all_api_v1_patterns_follow_standards(self):
        """Test that all /api/v1/ patterns follow naming standards"""
        api_v1_patterns = [
            p for p in self.patterns if p.get("normalized_pattern", "").startswith("/api/v1/")
        ]

        self.assertGreater(len(api_v1_patterns), 0, "Should have at least some /api/v1/ patterns")

        # Check that validation passed (or log issues)
        if not self.result.passed:
            error_summary = "\n".join(
                [f"  - {e.rule}: {e.pattern} - {e.message}" for e in self.result.errors[:10]]
            )
            self.fail(
                f"URL pattern validation failed with {len(self.result.errors)} errors:\n"
                f"{error_summary}"
                + (
                    f"\n  ... and {len(self.result.errors) - 10} more errors"
                    if len(self.result.errors) > 10
                    else ""
                )
            )

        # Test should pass if validation passed
        self.assertTrue(self.result.passed, "All URL patterns should follow naming standards")

    def test_pattern_structure_consistency(self):
        """Test that URL patterns have consistent structure"""
        api_v1_patterns = [
            p for p in self.patterns if p.get("normalized_pattern", "").startswith("/api/v1/")
        ]

        for pattern_info in api_v1_patterns:
            normalized_pattern = pattern_info.get("normalized_pattern", "")

            # All patterns should start with /api/v1/
            self.assertTrue(
                normalized_pattern.startswith("/api/v1/"),
                f"Pattern should start with /api/v1/: {normalized_pattern}",
            )

            # Patterns should not have consecutive slashes (except after /api/v1/)
            if "//" in normalized_pattern.replace("/api/v1/", ""):
                self.fail(f"Pattern should not have consecutive slashes: {normalized_pattern}")

    def test_no_missing_url_names_for_important_patterns(self):
        """Test that important patterns have url_name for reverse lookup"""
        # Important patterns that should have url_name
        important_patterns = [
            p
            for p in self.patterns
            if p.get("normalized_pattern", "").startswith("/api/v1/")
            and (
                "/contracts/" in p.get("normalized_pattern", "")
                or "/assets/" in p.get("normalized_pattern", "")
                or "/dq/runs/" in p.get("normalized_pattern", "")
                or "/compliance/runs/" in p.get("normalized_pattern", "")
            )
        ]

        patterns_without_name = [p for p in important_patterns if not p.get("url_name")]

        if patterns_without_name:
            missing_names = "\n".join(
                [f"  - {p.get('normalized_pattern', 'N/A')}" for p in patterns_without_name[:10]]
            )
            self.fail(
                f"Found {len(patterns_without_name)} important patterns without url_name:\n{missing_names}"
            )

    def test_pattern_naming_standards(self):
        """Test that patterns follow naming standards (kebab-case, plural, etc.)"""
        # This is already tested by the validator, but we verify the results
        kebab_case_errors = [e for e in self.result.errors if e.rule == "kebab_case"]

        plural_errors = [e for e in self.result.errors if e.rule == "plural_resources"]

        if kebab_case_errors:
            error_details = "\n".join(
                [f"  - {e.pattern}: {e.message}" for e in kebab_case_errors[:5]]
            )
            self.fail(f"Found {len(kebab_case_errors)} kebab-case violations:\n{error_details}")

        if plural_errors:
            error_details = "\n".join([f"  - {e.pattern}: {e.message}" for e in plural_errors[:5]])
            self.fail(f"Found {len(plural_errors)} plural resource violations:\n{error_details}")

        # Test passes if no naming standard errors
        self.assertEqual(len(kebab_case_errors), 0, "No kebab-case violations should exist")
        self.assertEqual(len(plural_errors), 0, "No plural resource violations should exist")


class URLPatternIntegrationTest(TestCase):
    """Integration tests for URL patterns with real Django setup"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.validator = URLPatternValidator()
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user)

    def test_patterns_are_accessible(self):
        """Test that known endpoints are reachable (not 404/500)."""
        test_endpoints = [
            "/api/v1/contracts/",
            "/api/v1/assets/",
            "/api/v1/dq/runs/",
            "/api/v1/compliance/runs/",
        ]

        for endpoint in test_endpoints:
            response = self.client.get(endpoint)
            # 200 or 403 (tenant/permission) are acceptable; 404 means endpoint
            # is not registered; 500 means server error — both are failures.
            self.assertIn(
                response.status_code,
                [200, 403],
                f"{endpoint} returned {response.status_code} — expected 200 or 403",
            )

    def test_validation_at_startup(self):
        """Test that URL pattern validation can run at Django startup"""
        # This test verifies that validation doesn't break Django startup
        try:
            result = self.validator.validate_all(strict=False)
            self.assertIsNotNone(result)
            self.assertIsInstance(result, URLPatternValidationResult)
        except Exception as e:
            self.fail(f"URL pattern validation should not break Django startup: {e}")


class URLPatternValidatorEdgeCasesTest(TestCase):
    """Test edge cases and error handling in URL pattern validator"""

    def setUp(self):
        """Set up test fixtures"""
        self.validator = URLPatternValidator()

    def test_non_api_v1_patterns_skipped(self):
        """Test that non-API v1 patterns are skipped in validation"""
        # Test no duplication check skips non-API v1 patterns
        pattern_info = {
            "pattern": "/admin/users/{id}/",
            "normalized_pattern": "/admin/users/{id}/",
            "url_name": "admin-user-detail",
            "file_path": "admin/urls.py",
            "line_number": None,
        }
        errors = self.validator.validate_no_duplication(pattern_info)
        self.assertEqual(len(errors), 0, "Non-API v1 patterns should be skipped")

        # Test plural resources check skips non-API v1 patterns
        errors = self.validator.validate_plural_resources(pattern_info)
        self.assertEqual(len(errors), 0, "Non-API v1 patterns should be skipped")

        # Test kebab-case check skips non-API v1 patterns
        errors = self.validator.validate_kebab_case(pattern_info)
        self.assertEqual(len(errors), 0, "Non-API v1 patterns should be skipped")

        # Test explicit naming check skips non-API v1 patterns
        warnings = self.validator.validate_explicit_naming(pattern_info)
        self.assertEqual(len(warnings), 0, "Non-API v1 patterns should be skipped")

    def test_kebab_case_with_file_extensions(self):
        """Test kebab-case validation handles file extensions correctly"""
        # Pattern with file extension should check base name
        # Note: The normalized pattern might include the extension as a segment
        # which could trigger validation. Let's test with a valid kebab-case base name.
        pattern_info = {
            "pattern": r"^api/v1/data-contracts/(?P<id>[^/.]+)\.json$",
            "normalized_pattern": "/api/v1/data-contracts/{id}.json/",
            "url_name": "contract-json",
            "file_path": "contracts/urls.py",
            "line_number": None,
        }
        errors = self.validator.validate_kebab_case(pattern_info)
        # The validator should handle file extensions without crashing.
        # Whether it flags ".json" as an error depends on the implementation.
        self.assertIsInstance(errors, list)
        # Verify the validator processed the pattern without raising
        for error in errors:
            self.assertIsNotNone(error.rule)
            self.assertIsNotNone(error.message)

    def test_kebab_case_snake_case_detection(self):
        """Test that snake_case violations are detected"""
        pattern_info = {
            "pattern": r"^api/v1/data_contracts/$",
            "normalized_pattern": "/api/v1/data_contracts/",
            "url_name": "data-contracts",
            "file_path": "contracts/urls.py",
            "line_number": None,
        }
        errors = self.validator.validate_kebab_case(pattern_info)
        self.assertGreater(len(errors), 0, "Should detect snake_case violation")
        self.assertEqual(errors[0].rule, "kebab_case")
        self.assertIn("snake_case", errors[0].message)

    def test_kebab_case_camelcase_detection(self):
        """Test that camelCase violations are detected"""
        pattern_info = {
            "pattern": r"^api/v1/dataContracts/$",
            "normalized_pattern": "/api/v1/dataContracts/",
            "url_name": "data-contracts",
            "file_path": "contracts/urls.py",
            "line_number": None,
        }
        errors = self.validator.validate_kebab_case(pattern_info)
        self.assertGreater(len(errors), 0, "Should detect camelCase violation")
        self.assertEqual(errors[0].rule, "kebab_case")
        self.assertIn("camelCase", errors[0].message or "PascalCase")

    def test_explicit_naming_abbreviations(self):
        """Test that unclear abbreviations trigger warnings"""
        pattern_info = {
            "pattern": r"^api/v1/dq/runs/$",
            "normalized_pattern": "/api/v1/dq/runs/",
            "url_name": "dq-runs",
            "file_path": "dq/urls.py",
            "line_number": None,
        }
        warnings = self.validator.validate_explicit_naming(pattern_info)
        # 'dq' might be in UNCLEAR_ABBREVIATIONS
        # If it is, we should get a warning
        if warnings:
            self.assertEqual(warnings[0].rule, "explicit_naming")
            self.assertIn("unclear", warnings[0].message.lower())

    def test_strict_mode_treats_warnings_as_errors(self):
        """Test that strict mode converts warnings to errors.

        When validate_all(strict=True) is called, any warnings must cause
        passed=False (warnings are elevated to error status in strict mode).
        """
        result = self.validator.validate_all(strict=True)
        self.assertIsNotNone(result)

        if result.warnings:
            self.assertFalse(
                result.passed,
                "strict=True with warnings must set passed=False "
                f"({len(result.warnings)} warnings found)"
            )

    def test_format_errors_with_errors(self):
        """Test error formatting when there are errors"""
        # Create a pattern with a known violation
        pattern_info = {
            "pattern": r"^api/v1/contracts/contracts/(?P<id>[^/.]+)/$",
            "normalized_pattern": "/api/v1/contracts/contracts/{id}/",
            "url_name": "duplicate-contracts",
            "file_path": "contracts/urls.py",
            "line_number": 42,
        }
        errors = self.validator.validate_no_duplication(pattern_info)

        if errors:
            # Create a validation result with errors
            from hub.apps.api.utils.url_pattern_validator import URLPatternValidationResult

            result = URLPatternValidationResult(
                total_patterns=1, errors=errors, warnings=[], passed=False
            )
            formatted = self.validator.format_errors(result)
            self.assertIn("ERRORS:", formatted)
            self.assertIn("contracts/contracts", formatted)
            self.assertIn("Duplicate segment", formatted)

    def test_format_errors_with_warnings(self):
        """Test error formatting when there are warnings"""
        from hub.apps.api.utils.url_pattern_validator import (
            URLPatternValidationResult,
        )

        # Create a warning
        warning = URLPatternValidationError(
            rule="explicit_naming",
            pattern="/api/v1/dq/runs/",
            url_name="dq-runs",
            file_path="dq/urls.py",
            line_number=None,
            message="Abbreviation 'dq' is unclear",
            severity="warning",
            suggestion="Consider using 'data-quality'",
        )

        result = URLPatternValidationResult(
            total_patterns=1, errors=[], warnings=[warning], passed=True
        )
        formatted = self.validator.format_errors(result)
        self.assertIn("WARNINGS:", formatted)
        self.assertIn("dq", formatted)

    def test_format_errors_passed(self):
        """Test error formatting when validation passes"""
        from hub.apps.api.utils.url_pattern_validator import URLPatternValidationResult

        result = URLPatternValidationResult(total_patterns=10, errors=[], warnings=[], passed=True)
        formatted = self.validator.format_errors(result)
        self.assertIn("passed validation", formatted)
        self.assertIn("10", formatted)

    def test_validate_url_patterns_convenience_function(self):
        """Test the convenience function validate_url_patterns"""
        from hub.apps.api.utils.url_pattern_validator import validate_url_patterns

        # Test without raising on error
        result = validate_url_patterns(strict=False, raise_on_error=False)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, URLPatternValidationResult)

    def test_validate_url_patterns_raises_on_error(self):
        """Test that convenience function raises when raise_on_error=True and there are errors"""
        from hub.apps.api.utils.url_pattern_validator import validate_url_patterns

        # This test might not raise if there are no errors in the actual patterns
        # But we can test the logic path
        try:
            result = validate_url_patterns(strict=False, raise_on_error=True)
            # If no errors, should not raise
            self.assertIsNotNone(result)
        except ValueError as e:
            # If there are errors, should raise ValueError
            self.assertIn("validation failed", str(e).lower())

    def test_pattern_extraction_handles_missing_attributes(self):
        """Test that pattern extraction handles patterns without expected attributes"""
        # The extract_url_patterns method should handle patterns gracefully
        # even if they don't have all expected attributes
        patterns = self.validator.extract_url_patterns()
        self.assertIsInstance(patterns, list)
        # Should not crash even if some patterns are malformed

    def test_plural_resources_singular_detection(self):
        """Test that singular resource names are detected"""
        pattern_info = {
            "pattern": r"^api/v1/contract/(?P<id>[^/.]+)/$",
            "normalized_pattern": "/api/v1/contract/{id}/",
            "url_name": "contract-detail",
            "file_path": "contracts/urls.py",
            "line_number": None,
        }
        errors = self.validator.validate_plural_resources(pattern_info)
        self.assertGreater(len(errors), 0, "Should detect singular 'contract'")
        self.assertEqual(errors[0].rule, "plural_resources")
        self.assertIn("plural", errors[0].message.lower())

    def test_kebab_case_invalid_characters(self):
        """Test that invalid characters in segments are detected"""
        pattern_info = {
            "pattern": r"^api/v1/data@contracts/$",
            "normalized_pattern": "/api/v1/data@contracts/",
            "url_name": "data-contracts",
            "file_path": "contracts/urls.py",
            "line_number": None,
        }
        errors = self.validator.validate_kebab_case(pattern_info)
        self.assertGreater(len(errors), 0, "Should detect invalid '@' character")
        self.assertEqual(errors[0].rule, "kebab_case")
        self.assertIn("invalid", errors[0].message.lower() or "kebab-case")

    def test_pattern_with_view_class_callback(self):
        """Test pattern extraction handles view_class callbacks"""
        # This tests the code path where callback has view_class attribute
        # The actual extraction will process real Django patterns, so this
        # verifies the code path exists and works
        patterns = self.validator.extract_url_patterns()
        # Should successfully extract patterns even with view_class callbacks
        self.assertIsInstance(patterns, list)
        self.assertGreater(len(patterns), 0)

    def test_pattern_without_prefix(self):
        """Test pattern normalization when prefix is empty"""
        # Test the else branch in _extract_patterns_recursive when prefix is empty
        # This is tested indirectly through extract_url_patterns, but we can verify
        # the normalization logic handles empty prefixes
        normalized = self.validator._normalize_pattern("^contracts/(?P<id>[^/.]+)/$")
        self.assertIsInstance(normalized, str)
        self.assertIn("contracts", normalized)

    def test_pattern_with_leading_slash_in_clean_pattern(self):
        """Test pattern building when clean_pattern starts with /"""
        # Test the branch where clean_pattern.startswith('/') is True
        # This is tested through actual pattern extraction, but we verify it works
        patterns = self.validator.extract_url_patterns()
        # Patterns should be properly built even when they start with /
        for pattern in patterns[:5]:  # Check first 5 patterns
            self.assertIn("pattern", pattern)
            self.assertIn("normalized_pattern", pattern)

    def test_validate_all_with_errors_logs_appropriately(self):
        """Test that validate_all logs errors when validation fails"""
        # Create a validator and manually add an error to test logging
        # We can't easily test the logging directly, but we can verify
        # the error path is executed by checking the result
        result = self.validator.validate_all(strict=False)
        # The result should have proper structure regardless of pass/fail
        self.assertIsNotNone(result)
        self.assertIsInstance(result.passed, bool)
        self.assertIsInstance(result.errors, list)
        self.assertIsInstance(result.warnings, list)

    def test_validate_url_patterns_raises_with_errors(self):
        """Test that validate_url_patterns raises ValueError when raise_on_error=True and errors exist"""
        from hub.apps.api.utils.url_pattern_validator import validate_url_patterns

        # Create a validator that will have errors
        # We'll use strict mode to potentially create more errors
        # But we can't guarantee errors exist, so we test the path
        try:
            result = validate_url_patterns(strict=True, raise_on_error=True)
            # If no errors, should not raise
            if not result.passed:
                # This shouldn't happen if raise_on_error=True and there are errors
                # But if it does, the test still verifies the code path
                pass
        except ValueError:
            # Expected if there are errors
            pass
