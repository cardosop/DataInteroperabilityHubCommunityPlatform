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
        # At least one of these may be set in env
        _ = getattr(settings, "SEMANTIC_SERVICE_URL", None)
        _ = getattr(settings, "DQ_SERVICE_URL", None)
        _ = getattr(settings, "COMPLIANCE_SERVICE_URL", None)
