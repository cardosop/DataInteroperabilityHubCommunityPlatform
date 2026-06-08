"""Tests for version discovery endpoint GET /api/v1/ (277.B.110)."""

import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.api.versioning import (
    APIVersionManager,
    DeprecatedEndpoint,
)


pytestmark = pytest.mark.django_db


class VersionDiscoveryResponseShapeTest(TestCase):
    """Verifies the GET /api/v1/ response contains all required fields."""

    def setUp(self):
        self.client = APIClient()
        cache.clear()

    @pytest.mark.integration
    def test_returns_200(self):
        resp = self.client.get("/api/v1/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    @pytest.mark.integration
    def test_has_name(self):
        resp = self.client.get("/api/v1/")
        self.assertIn("name", resp.data)

    @pytest.mark.integration
    def test_has_current_version(self):
        resp = self.client.get("/api/v1/")
        self.assertIn("current_version", resp.data)
        self.assertEqual(resp.data["current_version"], "v1.0.0")

    @pytest.mark.integration
    def test_has_supported_versions(self):
        resp = self.client.get("/api/v1/")
        self.assertIn("supported_versions", resp.data)
        self.assertIsInstance(resp.data["supported_versions"], list)
        self.assertIn("v1.0.0", resp.data["supported_versions"])

    @pytest.mark.integration
    def test_has_deprecated_endpoints(self):
        resp = self.client.get("/api/v1/")
        self.assertIn("deprecated_endpoints", resp.data)
        self.assertIsInstance(resp.data["deprecated_endpoints"], list)

    @pytest.mark.integration
    def test_deprecated_endpoint_structure(self):
        resp = self.client.get("/api/v1/")
        deps = resp.data["deprecated_endpoints"]
        # search/apps.py registers at least 5 deprecated endpoints on
        # app startup — if the list is empty the field is not being
        # populated and the test would pass vacuously.
        self.assertGreater(
            len(deps), 0,
            "Expected at least one deprecated endpoint from search/apps.py registration",
        )
        for dep in deps:
            self.assertIn("path", dep)
            self.assertIn("method", dep)
            self.assertIn("deprecated_since", dep)
            self.assertIn("sunset_date", dep)
            self.assertIn("replacement", dep)
            self.assertIn("migration_guide", dep)

    @pytest.mark.integration
    def test_has_links(self):
        resp = self.client.get("/api/v1/")
        self.assertIn("links", resp.data)
        links = resp.data["links"]
        self.assertIn("openapi_schema", links)
        self.assertIn("openapi_json", links)
        self.assertIn("changelog", links)
        self.assertIn("versioning_policy", links)

    @pytest.mark.integration
    def test_has_base_url(self):
        resp = self.client.get("/api/v1/")
        self.assertEqual(resp.data["base_url"], "/api/v1")

    @pytest.mark.integration
    def test_has_documentation(self):
        resp = self.client.get("/api/v1/")
        self.assertIn("documentation", resp.data)
        self.assertIn("openapi_yaml", resp.data["documentation"])

    @pytest.mark.integration
    def test_has_endpoints(self):
        resp = self.client.get("/api/v1/")
        self.assertIn("endpoints", resp.data)
        eps = resp.data["endpoints"]
        # Core endpoints must be present
        for key in ("auth", "assets", "contracts", "compliance", "webhooks",
                     "governance", "billing", "notifications", "capabilities"):
            self.assertIn(key, eps, f"Missing endpoint: {key}")

    @pytest.mark.integration
    def test_no_auth_required(self):
        """Public endpoint — no authentication needed."""
        resp = self.client.get("/api/v1/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class VersionDiscoveryDeprecatedEndpointsTest(TestCase):
    """Verifies deprecated endpoints appear in the response."""

    def setUp(self):
        self.client = APIClient()
        cache.clear()
        # Register a test deprecated endpoint
        self.test_dep = DeprecatedEndpoint(
            path="/api/v1/test-deprecated/",
            method="GET",
            deprecated_since="2026-01-01",
            sunset_date="2026-04-01",
            replacement="/api/v2/test/",
            migration_guide="Test migration guide",
        )
        APIVersionManager.register_deprecated_endpoint(self.test_dep)

    def tearDown(self):
        # Clean up the registered endpoint to avoid polluting other tests
        key = f"GET:/api/v1/test-deprecated/"
        APIVersionManager.DEPRECATED_ENDPOINTS.pop(key, None)

    @pytest.mark.integration
    def test_registered_deprecated_endpoint_appears(self):
        resp = self.client.get("/api/v1/")
        deps = resp.data["deprecated_endpoints"]
        paths = [d["path"] for d in deps]
        self.assertIn("/api/v1/test-deprecated/", paths)

    @pytest.mark.integration
    def test_deprecated_fields_are_correct(self):
        resp = self.client.get("/api/v1/")
        deps = resp.data["deprecated_endpoints"]
        match = next(
            (d for d in deps if d["path"] == "/api/v1/test-deprecated/"),
            None,
        )
        self.assertIsNotNone(
            match,
            "Test-deprecated endpoint /api/v1/test-deprecated/ not found in "
            "deprecated_endpoints list — was the setUp registration missed?",
        )
        self.assertEqual(match["method"], "GET")
        self.assertEqual(match["deprecated_since"], "2026-01-01")
        self.assertEqual(match["sunset_date"], "2026-04-01")
        self.assertEqual(match["replacement"], "/api/v2/test/")
        self.assertEqual(match["migration_guide"], "Test migration guide")


class VersionDiscoveryRateLimitTest(TestCase):
    """Verifies the 30/min per-IP rate limit (277.B.110).

    DRF caches ``SimpleRateThrottle.THROTTLE_RATES`` at import time from
    ``api_settings.DEFAULT_THROTTLE_RATES``.  ``@override_settings`` does
    NOT refresh that cached class attribute, so we mutate it directly and
    restore it in ``tearDown``.
    """

    def setUp(self):
        self.client = APIClient()
        # Clear ALL caches so preceding tests that hit /api/v1/
        # (VersionDiscoveryResponseShapeTest, MvpModeMiddlewareIntegrationTest)
        # don't consume the rate-limit budget for 127.0.0.1.
        from django.core.cache import caches
        for cache_name in caches:
            caches[cache_name].clear()

        # DRF's SimpleRateThrottle.THROTTLE_RATES is a class-level dict
        # snapshotted at import time.  @override_settings cannot reach it,
        # so we patch it directly for deterministic test assertions.
        from rest_framework.throttling import SimpleRateThrottle
        self._saved_throttle_rates = dict(SimpleRateThrottle.THROTTLE_RATES)
        SimpleRateThrottle.THROTTLE_RATES["version_discovery"] = "3/minute"

    def tearDown(self):
        from rest_framework.throttling import SimpleRateThrottle
        SimpleRateThrottle.THROTTLE_RATES.clear()
        SimpleRateThrottle.THROTTLE_RATES.update(self._saved_throttle_rates)

    @pytest.mark.integration
    def test_rate_limit_enforced_at_3_per_minute(self):
        """With a 3/min limit, the 4th request returns 429."""
        for _ in range(3):
            resp = self.client.get("/api/v1/")
            self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self.client.get("/api/v1/")
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @pytest.mark.integration
    def test_different_ip_not_rate_limited(self):
        """Rate limit is per-IP — a different IP is not affected."""
        for _ in range(3):
            resp = self.client.get("/api/v1/", REMOTE_ADDR="10.0.0.1")
            self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self.client.get("/api/v1/", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Different IP should still get through
        resp2 = self.client.get("/api/v1/", REMOTE_ADDR="10.0.0.2")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
