"""
E2E tests for observability endpoints (metrics).
"""
import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from tests.e2e.conftest import E2ETestBase
pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e_batch3]



class ObservabilityE2ETest(E2ETestBase):
    """E2E tests for observability endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.client = APIClient()
    
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint returns valid metrics."""
        response = self.client.get('/metrics/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/plain', response['Content-Type'])

        # Metrics should be in Prometheus format
        content = response.content.decode('utf-8')

        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0, "Metrics endpoint must return non-empty content")

        # Verify Prometheus exposition format: must contain at least one HELP or TYPE line
        has_help = '# HELP' in content
        has_type = '# TYPE' in content
        self.assertTrue(
            has_help or has_type,
            "Metrics output must contain Prometheus HELP or TYPE comments",
        )

    def test_metrics_endpoint_returns_text(self):
        """Test that metrics endpoint returns text/plain with correct charset."""
        response = self.client.get('/metrics/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Prometheus metrics include version in content type
        self.assertIn('text/plain', response['Content-Type'])
        self.assertIn('charset=utf-8', response['Content-Type'])

        # Verify content contains actual metric lines (name value pairs)
        content = response.content.decode('utf-8')
        lines = [line for line in content.strip().split('\n') if line and not line.startswith('#')]
        self.assertGreater(
            len(lines), 0,
            "Metrics endpoint must return at least one metric data line",
        )

