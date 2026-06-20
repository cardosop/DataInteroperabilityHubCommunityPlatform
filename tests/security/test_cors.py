"""Phase 98: CORS header validation tests."""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

pytestmark = pytest.mark.security


class CORSSecurityTest(TestCase):
    """Verify CORS headers block unauthorized origins."""

    def test_evil_origin_no_cors_header(self):
        """Request with malicious Origin should not get CORS allow header."""
        client = APIClient()
        response = client.get(
            "/api/v1/health/",
            HTTP_ORIGIN="https://evil.com",
        )
        acao = response.get("Access-Control-Allow-Origin", "")
        self.assertNotEqual(
            acao,
            "https://evil.com",
            "CORS should not allow arbitrary origins",
        )
        self.assertNotEqual(
            acao,
            "*",
            "CORS should not use wildcard in non-dev",
        )

    def test_preflight_evil_origin_blocked(self):
        """OPTIONS preflight with evil origin should not return CORS headers."""
        client = APIClient()
        response = client.options(
            "/api/v1/assets/",
            HTTP_ORIGIN="https://evil.com",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        acao = response.get("Access-Control-Allow-Origin", "")
        self.assertNotEqual(acao, "https://evil.com")
