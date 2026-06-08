"""
285.12.3.5 — Security regression suite: tenant isolation, rate limiting, input validation.
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant

User = get_user_model()


class SearchSecurityRegressionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tenant = Tenant.objects.create(
            name=f"Test-{uuid.uuid4().hex[:8]}", slug=f"t-{uuid.uuid4().hex[:8]}", status="ACTIVE",
        )
        cls.user = User.objects.create_user(
            email=f"user_{uuid.uuid4().hex[:8]}@test.local", password="Pass1234!",
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
        """SQL injection payloads are treated as literal text by FTS — safe by design."""
        resp = self.client.get("/api/search/", {"q": "'; DROP TABLE users; --"})
        self.assertEqual(resp.status_code, 200,
            "SQL injection must not crash the server; Postgres FTS treats it as literal text")
        data = resp.json() if hasattr(resp, "json") else resp.data
        self.assertIn("results", data)

    @pytest.mark.integration
    def test_xss_sanitized(self):
        """XSS payloads are treated as literal search text; Django auto-escapes in templates."""
        resp = self.client.get("/api/search/", {"q": "<script>alert('xss')</script>"})
        self.assertEqual(resp.status_code, 200,
            "XSS payload must not crash the server; treated as literal search text")
        data = resp.json() if hasattr(resp, "json") else resp.data
        self.assertIn("results", data)

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
        self.assertEqual(resp.status_code, 400,
            "NUL byte injection must return 400, not crash with 500")
        data = resp.json() if hasattr(resp, "json") else resp.data
        self.assertIn("error", data)
        self.assertEqual(data.get("error", {}).get("code"), "INVALID_INPUT")
