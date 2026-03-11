"""
Phase 15: Tests that AllowAny (public) endpoints return only intended public data.

Validates that unauthenticated access to api_info, semantic ontology/context,
and developer plugin/SDK endpoints does not expose sensitive data (no user emails,
tokens, tenant names, or internal IDs beyond public contract). No mocks.
See tasks.md Phase 15.2.2 and docs/AUDIT_POLICY.md.
"""

import re
import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


# Sensitive patterns that must NOT appear in public endpoint responses
SENSITIVE_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"Bearer\s+[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", re.I),  # JWT
    re.compile(r"refresh_token=[^&\s]+", re.I),
    re.compile(r"api_key=[^&\s]+", re.I),
    re.compile(r"password['\"]?\s*[:=]\s*['\"]?[^'\"]+", re.I),
]

# Keys that must NOT appear in public API info (only allow documented public keys)
API_INFO_ALLOWED_KEYS = {"name", "version", "base_url", "documentation", "endpoints"}


pytestmark = pytest.mark.django_db(transaction=True)


class AllowAnyPublicEndpointsTest(TestCase):
    """Unauthenticated access to AllowAny endpoints must return only public data."""

    def setUp(self):
        self.client = APIClient()
        # No authentication - testing public endpoints

    def _assert_no_sensitive_data_in_text(self, text: str, endpoint_name: str):
        """Assert response text does not contain sensitive patterns."""
        if not text:
            return
        for pattern in SENSITIVE_PATTERNS:
            matches = pattern.findall(text)
            assert not matches, (
                f"{endpoint_name} must not expose sensitive data; "
                f"found pattern {pattern.pattern}: {matches[:3]}"
            )

    def test_api_info_returns_only_public_data(self):
        """GET /api/v1/ (api_info) must return only name, version, base_url, documentation, endpoints."""
        response = self.client.get("/api/v1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Only allowed top-level keys
        for key in data:
            self.assertIn(key, API_INFO_ALLOWED_KEYS, f"api_info must not expose '{key}'")
        # No sensitive data in response body
        text = response.content.decode("utf-8", errors="replace")
        self._assert_no_sensitive_data_in_text(text, "api_info")
        # Must contain public fields
        self.assertIn("name", data)
        self.assertIn("version", data)
        self.assertIn("base_url", data)
        self.assertIn("endpoints", data)
        # Endpoints must be path-only (no tokens)
        for path in data.get("endpoints", {}).values():
            self._assert_no_sensitive_data_in_text(str(path), "api_info endpoints")

    def test_api_not_found_returns_no_sensitive_data(self):
        """GET non-existent /api/v1/ path must return 404 without sensitive data."""
        response = self.client.get("/api/v1/nonexistent-path-404-test/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        text = response.content.decode("utf-8", errors="replace")
        self._assert_no_sensitive_data_in_text(text, "api_not_found")

    def test_semantic_ontology_unauthenticated_returns_public_or_error_only(self):
        """GET /api/v1/semantic/ontology unauthenticated must return ontology or 503, no user/tenant data."""
        response = self.client.get("/api/v1/semantic/ontology")
        # 200 (ontology content) or 503 (service unavailable) are acceptable
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE))
        text = response.content.decode("utf-8", errors="replace")
        self._assert_no_sensitive_data_in_text(text, "semantic/ontology")
        if response.status_code == 200:
            # Should be Turtle or similar; no email/token
            self._assert_no_sensitive_data_in_text(text, "semantic/ontology body")

    def test_semantic_jsonld_context_unauthenticated_returns_public_or_error_only(self):
        """GET /api/v1/semantic/context.jsonld unauthenticated must return JSON-LD context or 503, no user/tenant data."""
        response = self.client.get("/api/v1/semantic/context.jsonld")
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE))
        text = response.content.decode("utf-8", errors="replace")
        self._assert_no_sensitive_data_in_text(text, "semantic/context")

    def test_developer_plugins_list_unauthenticated_returns_public_data_only(self):
        """GET /api/v1/developer/plugins/ unauthenticated must return only public plugin data."""
        response = self.client.get("/api/v1/developer/plugins/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        text = response.content.decode("utf-8", errors="replace")
        self._assert_no_sensitive_data_in_text(text, "developer/plugins")
        data = response.json()
        # Results may be list or paginated
        results = data.get("results", data) if isinstance(data, dict) else data
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    # Must not contain internal/secret keys
                    self.assertNotIn("secret", item, "plugins must not expose secret")
                    self.assertNotIn("api_key", item, "plugins must not expose api_key")
                    self.assertNotIn("password", item, "plugins must not expose password")

    def test_developer_sdk_documentation_list_unauthenticated_returns_public_data_only(self):
        """GET /api/v1/developer/sdk/ unauthenticated must return only public SDK docs."""
        response = self.client.get("/api/v1/developer/sdk/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        text = response.content.decode("utf-8", errors="replace")
        self._assert_no_sensitive_data_in_text(text, "developer/sdk-documentation")

    def test_auth_register_remains_public_and_behaves_correctly(self):
        """POST /api/v1/auth/register/ is public (AllowAny) and behaves correctly."""
        from django.core.management import call_command

        call_command("seed_default_plans")
        email = f"allowany-{uuid.uuid4().hex[:8]}@example.com"
        response = self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "password": "SecurePass123", "name": "AllowAny User"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn("id", data)
        self.assertIn("email", data)
        self.assertEqual(data["email"], email)
        self.assertIn("tenant_id", data)
        self.assertIsNotNone(data["tenant_id"])
        self.assertNotIn("password", data)
        text = response.content.decode("utf-8", errors="replace")
        self.assertNotIn("Bearer ", text, "auth/register must not expose tokens")
        self.assertNotIn("refresh_token", text.lower(), "auth/register must not expose refresh token")
