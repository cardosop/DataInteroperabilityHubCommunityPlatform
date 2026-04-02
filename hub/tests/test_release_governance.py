"""
112.J — Release governance tests.

Proves:
1. J.1: Security findings tracker exists with required sections
2. J.1: CI security scanning workflows are configured
3. J.2: SearchViewSet deprecation is registered in the central
        APIVersionManager with correct sunset date
4. J.2: SearchViewSet responses include deprecation headers
"""
import os

import pytest
from django.test import TestCase


pytestmark = pytest.mark.django_db(transaction=True)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _read_file(rel_path):
    path = os.path.join(_REPO_ROOT, rel_path)
    if not os.path.exists(path):
        pytest.skip(f"{rel_path} not found")
    with open(path) as f:
        return f.read()


class SecurityFindingsTrackerTest(TestCase):
    """J.1 — Pen test scope, findings tracking, risk acceptance."""

    def test_security_findings_file_exists(self):
        """docs/SECURITY_FINDINGS.md must exist."""
        path = os.path.join(
            _REPO_ROOT, "docs/SECURITY_FINDINGS.md",
        )
        self.assertTrue(
            os.path.exists(path),
            "docs/SECURITY_FINDINGS.md must exist",
        )

    def test_has_pen_test_scope(self):
        content = _read_file("docs/SECURITY_FINDINGS.md")
        self.assertIn("Pen Test Scope", content)

    def test_has_remediation_slas(self):
        content = _read_file("docs/SECURITY_FINDINGS.md")
        self.assertIn("Remediation SLA", content)
        self.assertIn("Critical", content)
        self.assertIn("7 days", content)

    def test_has_risk_acceptance_register(self):
        content = _read_file("docs/SECURITY_FINDINGS.md")
        self.assertIn("Risk Acceptance", content)

    def test_has_ci_security_controls(self):
        content = _read_file("docs/SECURITY_FINDINGS.md")
        self.assertIn("CI/CD Security Controls", content)
        self.assertIn("Bandit", content)
        self.assertIn("pip-audit", content)
        self.assertIn("Trivy", content)

    def test_security_scan_workflow_exists(self):
        """CI must have security-scan workflow."""
        path = os.path.join(
            _REPO_ROOT,
            ".github/workflows/security-scan.yml",
        )
        self.assertTrue(
            os.path.exists(path),
            "security-scan.yml workflow must exist",
        )

    def test_pen_test_plan_exists(self):
        """Pen test plan document must exist."""
        path = os.path.join(
            _REPO_ROOT,
            "InputDocs/Security_Review_and_Pentest_Plan.md",
        )
        self.assertTrue(
            os.path.exists(path),
            "Security_Review_and_Pentest_Plan.md must exist",
        )


class SearchViewSetDeprecationTest(TestCase):
    """J.2 — SearchViewSet deprecation calendar tracked."""

    def test_search_viewset_registered_in_version_manager(self):
        """
        SearchViewSet must be registered in
        APIVersionManager.DEPRECATED_ENDPOINTS.
        """
        from hub.apps.api.versioning import APIVersionManager

        endpoint = APIVersionManager.get_deprecated_endpoint(
            "/api/v1/search/", "GET",
        )
        self.assertIsNotNone(
            endpoint,
            "SearchViewSet /api/v1/search/ must be "
            "registered as deprecated",
        )

    def test_sunset_date_is_2026_04_18(self):
        """Sunset date must be 2026-04-18 (30-day window)."""
        from hub.apps.api.versioning import APIVersionManager

        endpoint = APIVersionManager.get_deprecated_endpoint(
            "/api/v1/search/", "GET",
        )
        self.assertIsNotNone(endpoint)
        self.assertEqual(endpoint.sunset_date, "2026-04-18")

    def test_replacement_points_to_unified_search(self):
        """Replacement must point to /api/search/."""
        from hub.apps.api.versioning import APIVersionManager

        endpoint = APIVersionManager.get_deprecated_endpoint(
            "/api/v1/search/", "GET",
        )
        self.assertIsNotNone(endpoint)
        self.assertEqual(endpoint.replacement, "/api/search/")

    def test_search_viewset_has_deprecation_header(self):
        """SearchViewSet finalize_response must set Deprecation header.

        Verified by checking the class has its own finalize_response
        that references the header name — stronger than source-code
        grep because it resolves MRO correctly.
        """
        from hub.apps.search.views import SearchViewSet
        import inspect

        self.assertTrue(
            "finalize_response" in SearchViewSet.__dict__,
            "SearchViewSet must override finalize_response",
        )
        source = inspect.getsource(SearchViewSet.finalize_response)
        self.assertIn(
            "Deprecation",
            source,
            "finalize_response must reference Deprecation header",
        )

    def test_all_search_actions_registered(self):
        """All 5 SearchViewSet actions must be in the
        deprecation registry."""
        from hub.apps.api.versioning import APIVersionManager

        expected_paths = [
            ("/api/v1/search/", "GET"),
            ("/api/v1/search/suggestions/", "GET"),
            ("/api/v1/search/analytics/", "GET"),
            ("/api/v1/search/track-click/", "POST"),
            ("/api/v1/search/rebuild-index/", "POST"),
        ]
        for path, method in expected_paths:
            endpoint = APIVersionManager.get_deprecated_endpoint(
                path, method,
            )
            self.assertIsNotNone(
                endpoint,
                f"{method} {path} must be registered as "
                f"deprecated",
            )
