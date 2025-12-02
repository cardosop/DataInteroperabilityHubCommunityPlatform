"""
E2E tests for observability endpoints (metrics).
"""
import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from tests.e2e.conftest import E2ETestBase


class ObservabilityE2ETest(E2ETestBase):
    """E2E tests for observability endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.client = APIClient()
    
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        response = self.client.get('/metrics/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/plain', response['Content-Type'])
        
        # Metrics should be in Prometheus format
        content = response.content.decode('utf-8')
        
        # Check for common Prometheus metric types
        # Note: Actual metrics depend on what's configured
        # At minimum, we should get a response
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0)
    
    def test_metrics_endpoint_returns_text(self):
        """Test that metrics endpoint returns text/plain."""
        response = self.client.get('/metrics/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Prometheus metrics include version in content type
        self.assertIn('text/plain', response['Content-Type'])
        self.assertIn('charset=utf-8', response['Content-Type'])

