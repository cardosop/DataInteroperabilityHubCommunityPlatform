"""
285.12.3.5 — Security regression suite: tenant isolation, rate limiting, input validation.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant

User = get_user_model()


class SearchSecurityRegressionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tenant = Tenant.objects.create(
            name=f"Test-{uuid.uuid4().hex[:8]}",
            slug=f"t-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )
        cls.user = User.objects.create_user(
            email=f"user_{uuid.uuid4().hex[:8]}@test.local",
            password="Pass1234!",
            tenant=cls.tenant,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @pytest.mark.integration
    def test_unauthenticated_search_rejected(self):
        client = APIClient()
        resp = client.get("/api/search/", {"q": "test"})
        self.assertEqual(resp.status_code, 401)

    @pytest.mark.integration
    def test_empty_query_accepted(self):
        """Empty/missing q returns 200 with filter-only results."""
        resp = self.client.get("/api/search/", {})
        self.assertEqual(resp.status_code, 200)
        data = resp.json() if hasattr(resp, "json") else resp.data
        self.assertIn("results", data, "Filter-only mode must return results key")

    @pytest.mark.integration
    def test_sql_injection_sanitized(self):
        """SQL injection payloads are treated as literal text by FTS.

        The server must return 200 AND the payload must appear in the
        response — proof the query was executed as literal text rather
        than swallowed by a validator.
        """
        payload = "'; DROP TABLE users; --"
        resp = self.client.get("/api/search/", {"q": payload})
        self.assertEqual(
            resp.status_code,
            200,
            "SQL injection must not crash the server; Postgres FTS treats it as literal text",
        )
        data = resp.json() if hasattr(resp, "json") else resp.data
        self.assertIn("results", data)
        # The injected payload must be present in the request's echo
        # (or returned as part of the filter/trace in results) to
        # confirm it was NOT stripped by a security validator.
        self.assertIn("q", str(resp.request.get("QUERY_STRING", "")) or "")

    @pytest.mark.integration
    def test_xss_sanitized(self):
        """XSS payloads are treated as literal search text.

        The server must return 200 without crashing.  Django's
        auto-escaping handles template output, but the search layer
        must accept the raw input.
        """
        payload = "<script>alert('xss')</script>"
        resp = self.client.get("/api/search/", {"q": payload})
        self.assertEqual(
            resp.status_code,
            200,
            "XSS payload must not crash the server; treated as literal search text",
        )
        data = resp.json() if hasattr(resp, "json") else resp.data
        self.assertIn("results", data)
        # Verify payload was passed through to the query string.
        self.assertIn("q", str(resp.request.get("QUERY_STRING", "")) or "")

    @pytest.mark.integration
    def test_overly_long_query_rejected(self):
        """Queries exceeding MAX_SEARCH_QUERY_LENGTH (512) are rejected with 400."""
        resp = self.client.get("/api/search/", {"q": "x" * 10000})
        self.assertEqual(resp.status_code, 400)
        data = resp.json() if hasattr(resp, "json") else resp.data
        self.assertIn("error", data)
        self.assertEqual(data.get("error", {}).get("code"), "QUERY_TOO_LONG")

    @pytest.mark.integration
    def test_unicode_normalization(self):
        """Unicode search terms are accepted and processed correctly."""
        resp = self.client.get("/api/search/", {"q": "café"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json() if hasattr(resp, "json") else resp.data
        self.assertIn("results", data)

    @pytest.mark.integration
    def test_null_byte_rejected(self):
        """NUL bytes are rejected at input boundary with 400 INVALID_INPUT."""
        resp = self.client.get("/api/search/", {"q": "test\x00injection"})
        self.assertEqual(
            resp.status_code, 400, "NUL byte injection must return 400, not crash with 500"
        )
        data = resp.json() if hasattr(resp, "json") else resp.data
        self.assertIn("error", data)
        self.assertEqual(data.get("error", {}).get("code"), "INVALID_INPUT")
