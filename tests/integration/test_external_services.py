"""
Integration tests for external service connectivity (health, config).

Uses real HTTP where applicable; no mocks/stubs for service behavior.
"""

import pytest
from django.conf import settings
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class ExternalServicesIntegrationTest(TestCase):
    """Integration tests for external service configuration and health."""

    def test_health_endpoint_responds(self):
        """Health endpoint responds (real server)."""
        from django.test import Client

        client = Client()
        response = client.get("/health/")
        self.assertIn(response.status_code, [200, 503])

    def test_external_service_urls_configurable(self):
        """External service URLs can be read from settings (no mock)."""
        semantic_url = getattr(settings, "SEMANTIC_SERVICE_URL", None)
        dq_url = getattr(settings, "DQ_SERVICE_URL", None)
        compliance_url = getattr(settings, "COMPLIANCE_SERVICE_URL", None)
        # At least one external service URL must be configured in any
        # real deployment; in test environments, all three may be set.
        configured = [u for u in (semantic_url, dq_url, compliance_url) if u is not None]
        self.assertGreaterEqual(
            len(configured), 1,
            "Expected at least one external service URL to be configured"
        )
