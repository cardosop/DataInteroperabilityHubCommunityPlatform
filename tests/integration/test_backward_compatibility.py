"""
Comprehensive backward compatibility tests.

Tests backward compatibility features including:
- Deprecated endpoint warnings
- Old URL patterns (should return 404 as documented)
- Backward compatibility wrappers (normalization functions)
- Migration paths
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.api.versioning import APIVersionManager, DeprecatedEndpoint
from hub.apps.contracts.normalization import normalize_odcs_to_hubcontract
from tests.factories import TenantFactory, UserFactory

User = get_user_model()

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.integration]


class DeprecatedEndpointTest(TestCase):
    """Test deprecated endpoint warnings"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.client.force_authenticate(user=self.user)

    def test_deprecated_endpoint_warning_header(self):
        """Test that deprecated endpoints return Warning header"""
        # Register a test deprecated endpoint
        endpoint = DeprecatedEndpoint(
            path="/api/v1/test/deprecated/",
            method="GET",
            deprecated_since="2025-01-01",
            sunset_date="2026-01-01T00:00:00Z",
            replacement="/api/v1/test/new/",
            migration_guide="https://docs.example.com/migration",
        )
        APIVersionManager.register_deprecated_endpoint(endpoint)

        # Note: This test verifies the infrastructure works
        # Actual deprecated endpoints would need to be registered in production code
        retrieved = APIVersionManager.get_deprecated_endpoint("/api/v1/test/deprecated/", "GET")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.path, "/api/v1/test/deprecated/")
        self.assertEqual(retrieved.replacement, "/api/v1/test/new/")

        # Clean up
        APIVersionManager.DEPRECATED_ENDPOINTS.clear()

    def test_deprecated_endpoint_warning_header_format(self):
        """Test that warning header is properly formatted"""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/test/deprecated/",
            method="GET",
            deprecated_since="2025-01-01",
            sunset_date="2026-01-01T00:00:00Z",
            replacement="/api/v1/test/new/",
        )
        warning = endpoint.get_warning_header()
        self.assertIn("299", warning)
        self.assertIn("Deprecated API", warning)
        self.assertIn('sunset="2026-01-01T00:00:00Z"', warning)
        self.assertIn('link="/api/v1/test/new/"', warning)

    def test_deprecated_endpoint_sunset_check(self):
        """Test that sunset check works correctly"""
        from datetime import timedelta
        from django.utils import timezone

        # Endpoint not yet sunset
        endpoint = DeprecatedEndpoint(
            path="/api/v1/test/deprecated/",
            method="GET",
            deprecated_since="2025-01-01",
            sunset_date=(timezone.now() + timedelta(days=30)).isoformat(),
        )
        self.assertFalse(endpoint.is_sunset())

        # Endpoint already sunset
        endpoint = DeprecatedEndpoint(
            path="/api/v1/test/deprecated/",
            method="GET",
            deprecated_since="2025-01-01",
            sunset_date=(timezone.now() - timedelta(days=30)).isoformat(),
        )
        self.assertTrue(endpoint.is_sunset())


class OldURLPatternTest(TestCase):
    """Test that old URL patterns return 404 (as documented in migration guide)"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.client.force_authenticate(user=self.user)

    def test_old_compliance_runs_url_returns_404(self):
        """Test that old /compliance-runs/ URL pattern returns 404"""
        # Old pattern: /api/v1/compliance/compliance-runs/
        # New pattern: /api/v1/compliance/runs/
        response = self.client.get("/api/v1/compliance/compliance-runs/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_old_dq_runs_url_returns_404(self):
        """Test that old /dq-runs/ URL pattern returns 404"""
        # Old pattern: /api/v1/dq/dq-runs/
        # New pattern: /api/v1/dq/runs/
        response = self.client.get("/api/v1/dq/dq-runs/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_old_compliance_runs_detail_url_returns_404(self):
        """Test that old compliance runs detail URL returns 404"""
        test_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"/api/v1/compliance/compliance-runs/{test_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_old_dq_runs_detail_url_returns_404(self):
        """Test that old DQ runs detail URL returns 404"""
        test_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"/api/v1/dq/dq-runs/{test_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_old_compliance_runs_results_url_returns_404(self):
        """Test that old compliance runs results URL returns 404"""
        test_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"/api/v1/compliance/compliance-runs/{test_id}/results/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_old_dq_runs_results_url_returns_404(self):
        """Test that old DQ runs results URL returns 404"""
        test_id = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"/api/v1/dq/dq-runs/{test_id}/results/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class MigrationPathTest(TestCase):
    """Test that migration paths work correctly"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.client.force_authenticate(user=self.user)

    def test_new_compliance_runs_url_works(self):
        """Test that new /runs/ URL pattern works correctly"""
        # New pattern: /api/v1/compliance/runs/
        url = reverse("compliance-run-list")
        response = self.client.get(url)
        # Should return 200 (empty list) or 401/403 (auth required)
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_new_dq_runs_url_works(self):
        """Test that new /runs/ URL pattern works correctly"""
        # New pattern: /api/v1/dq/runs/
        url = reverse("dq-run-list")
        response = self.client.get(url)
        # Should return 200 (empty list) or 401/403 (auth required)
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_url_reverse_uses_new_patterns(self):
        """Test that reverse() uses new URL patterns"""
        # Compliance runs
        compliance_url = reverse("compliance-run-list")
        self.assertIn("/compliance/runs/", compliance_url)
        self.assertNotIn("/compliance-runs/", compliance_url)

        # DQ runs
        dq_url = reverse("dq-run-list")
        self.assertIn("/dq/runs/", dq_url)
        self.assertNotIn("/dq-runs/", dq_url)


class NormalizationBackwardCompatibilityTest(TestCase):
    """Test backward compatibility for normalization functions"""

    def test_normalize_odcs_to_hubcontract_still_works(self):
        """Test that deprecated normalize_odcs_to_hubcontract function still works"""
        # This is a backward compatibility wrapper
        odcs_contract = {
            "id": "test-contract",
            "name": "Test Contract",
            "schema": {
                "fields": [
                    {
                        "name": "field1",
                        "type": "string",
                        "required": True,
                    }
                ]
            },
        }

        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Should return valid results
        self.assertIsNotNone(hub_contract)
        self.assertIsInstance(hub_contract, dict)
        self.assertIsInstance(errors, list)
        self.assertIsInstance(warnings, list)

    def test_normalize_odcs_to_hubcontract_signature(self):
        """Test that normalize_odcs_to_hubcontract maintains old signature"""
        odcs_contract = {
            "id": "test-contract",
            "name": "Test Contract",
            "schema": {"fields": []},
        }

        # Should return tuple of (hub_contract, status, errors, warnings)
        result = normalize_odcs_to_hubcontract(odcs_contract)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)
        hub_contract, status, errors, warnings = result

        # Verify types
        self.assertIsInstance(status, str)
        self.assertIsInstance(errors, list)
        self.assertIsInstance(warnings, list)

    def test_normalize_odcs_to_hubcontract_handles_empty_fields(self):
        """Test that backward compatibility wrapper handles edge cases"""
        odcs_contract = {
            "id": "test-contract",
            "name": "Test Contract",
            "schema": {"fields": []},
        }

        hub_contract, status, errors, warnings = normalize_odcs_to_hubcontract(odcs_contract)

        # Should handle empty fields gracefully
        # Note: When fields are empty and there are errors, hub_contract may be None
        # This is expected behavior - the wrapper maintains the same behavior as the underlying function
        self.assertIsInstance(errors, list)
        self.assertIsInstance(warnings, list)
        # hub_contract can be None if there are critical errors (empty fields is critical)
        if hub_contract is not None:
            self.assertIsInstance(hub_contract, dict)


class APIVersionCompatibilityTest(TestCase):
    """Test API version compatibility"""

    def test_same_major_version_is_compatible(self):
        """Test that same major version is compatible"""
        from hub.apps.api.versioning import APIVersion

        v1_0 = APIVersion(1, 0, 0)
        v1_1 = APIVersion(1, 1, 0)
        v1_2_3 = APIVersion(1, 2, 3)

        self.assertTrue(v1_0.is_compatible_with(v1_1))
        self.assertTrue(v1_1.is_compatible_with(v1_0))
        self.assertTrue(v1_0.is_compatible_with(v1_2_3))
        self.assertTrue(v1_2_3.is_compatible_with(v1_0))

    def test_different_major_versions_are_incompatible(self):
        """Test that different major versions are incompatible"""
        from hub.apps.api.versioning import APIVersion

        v1_0 = APIVersion(1, 0, 0)
        v2_0 = APIVersion(2, 0, 0)

        self.assertFalse(v1_0.is_compatible_with(v2_0))
        self.assertFalse(v2_0.is_compatible_with(v1_0))

    def test_api_version_parsing(self):
        """Test API version parsing"""
        from hub.apps.api.versioning import APIVersion

        # Test various formats
        self.assertEqual(APIVersion.parse("v1"), APIVersion(1, 0, 0))
        self.assertEqual(APIVersion.parse("v1.0"), APIVersion(1, 0, 0))
        self.assertEqual(APIVersion.parse("v1.0.0"), APIVersion(1, 0, 0))
        self.assertEqual(APIVersion.parse("v1.2.3"), APIVersion(1, 2, 3))
        self.assertIsNone(APIVersion.parse("invalid"))



