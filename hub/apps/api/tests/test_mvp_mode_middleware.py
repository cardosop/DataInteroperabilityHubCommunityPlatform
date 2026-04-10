"""
Phase 216.0.4 — MVP mode middleware coverage.

Tests:
  1. Every prefix in MVP_GATED_RELATIVE_PREFIXES returns 404 when MVP_MODE=true.
  2. Every prefix is reachable (200 or 401, not 404) when MVP_MODE=false.
  3. Every prefix in mvp_mode.py has a corresponding URL route (catches typos).
  4. Non-gated paths (/api/v1/assets/, /api/v1/auth/me/) pass through in both modes.

The middleware reads ``settings.MVP_MODE`` (not ``os.environ``), so we use
``@override_settings(MVP_MODE=True/False)`` throughout.
"""
import pytest
from django.test import TestCase, override_settings
from django.urls import resolve, Resolver404

from hub.apps.api.mvp_mode import (
    MVP_GATED_RELATIVE_PREFIXES,
    API_V1_PREFIX,
    is_mvp_gated_api_v1_path,
)

pytestmark = pytest.mark.django_db


class MvpGatedPrefixRoutabilityTest(TestCase):
    """Every prefix in MVP_GATED_RELATIVE_PREFIXES must resolve to at least one URL route."""

    def test_every_gated_prefix_has_a_url_route(self):
        """Catches typos: if a prefix doesn't match any URL, the gate is useless."""
        unroutable = []
        for prefix in MVP_GATED_RELATIVE_PREFIXES:
            test_path = f"{API_V1_PREFIX}{prefix}"
            try:
                resolve(test_path)
            except Resolver404:
                unroutable.append(prefix)

        if unroutable:
            self.fail(
                f"MVP_GATED_RELATIVE_PREFIXES contains prefixes with no URL route "
                f"(typo?): {unroutable}. Either fix the prefix or add a URL pattern."
            )


class MvpModeGatingTest(TestCase):
    """is_mvp_gated_api_v1_path correctly classifies paths."""

    def test_gated_paths_detected(self):
        for prefix in MVP_GATED_RELATIVE_PREFIXES:
            path = f"{API_V1_PREFIX}{prefix}some-resource/"
            self.assertTrue(
                is_mvp_gated_api_v1_path(path),
                f"{path} should be gated but is_mvp_gated_api_v1_path returned False",
            )

    def test_non_gated_paths_not_detected(self):
        non_gated = [
            "/api/v1/assets/",
            "/api/v1/auth/me/",
            "/api/v1/compliance/runs/",
            "/api/v1/contracts/",
            "/api/v1/files/upload/",
            "/api/v1/tenants/",
        ]
        for path in non_gated:
            self.assertFalse(
                is_mvp_gated_api_v1_path(path),
                f"{path} should NOT be gated but is_mvp_gated_api_v1_path returned True",
            )

    def test_non_api_v1_paths_not_gated(self):
        non_api = [
            "/health/",
            "/admin/",
            "/api/v2/mesh/",
            "/mesh/",
        ]
        for path in non_api:
            self.assertFalse(
                is_mvp_gated_api_v1_path(path),
                f"{path} should not be gated (not under /api/v1/)",
            )


class MvpModeMiddlewareIntegrationTest(TestCase):
    """End-to-end middleware test via Django test client.

    The middleware reads ``settings.MVP_MODE`` per-request (not os.environ),
    so we use ``@override_settings`` to toggle the gate.
    """

    @override_settings(MVP_MODE=True)
    def test_gated_path_returns_404_when_mvp_mode_true(self):
        for prefix in MVP_GATED_RELATIVE_PREFIXES:
            path = f"{API_V1_PREFIX}{prefix}"
            response = self.client.get(path)
            self.assertEqual(
                response.status_code,
                404,
                f"Expected 404 for {path} with MVP_MODE=True, got {response.status_code}",
            )

    @override_settings(MVP_MODE=False)
    def test_gated_path_not_404_when_mvp_mode_false(self):
        for prefix in MVP_GATED_RELATIVE_PREFIXES:
            path = f"{API_V1_PREFIX}{prefix}"
            response = self.client.get(path)
            self.assertNotEqual(
                response.status_code,
                404,
                f"{path} should be reachable (200/401/403) with MVP_MODE=False, got 404",
            )

    @override_settings(MVP_MODE=True)
    def test_non_gated_path_passes_through_in_mvp_mode(self):
        # /api/v1/auth/me/ should return 401 (not authenticated), not 404
        response = self.client.get("/api/v1/auth/me/")
        self.assertIn(
            response.status_code,
            (200, 401, 403),
            f"/api/v1/auth/me/ should pass through MVP gate, got {response.status_code}",
        )


class MvpGatedPrefixCompletenessTest(TestCase):
    """Verify the prefix list covers all expected post-MVP namespaces."""

    def test_expected_prefixes_are_gated(self):
        expected = {
            "mesh/",
            "virtualization/",
            "integrations/",
            "baas/",
            "ml/",
            "ai/",
            "transformation/",
            "social/",
            "scheduled-ingestions/",
            "scheduled-exports/",
        }
        actual = set(MVP_GATED_RELATIVE_PREFIXES)
        missing = expected - actual
        self.assertFalse(
            missing,
            f"Expected gated prefixes missing from MVP_GATED_RELATIVE_PREFIXES: {missing}",
        )
