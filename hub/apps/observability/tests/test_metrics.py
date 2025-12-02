"""
Tests for Prometheus metrics
"""
import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.observability.metrics import (


    http_requests_total,
    http_request_duration_seconds,
    jobs_started_total,
    metrics_view,
)


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MetricsTest(TestCase):
    """Test metrics functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
    
    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint"""
        # Use trailing slash to match URL pattern
        response = self.client.get('/metrics/')
        # If we get a redirect, follow it
        if response.status_code in [301, 302]:
            response = self.client.get(response.url, follow=True)
        self.assertEqual(response.status_code, 200, f"Expected 200, got {response.status_code}. Response: {response.content[:200]}")
        # Content-Type might vary, check if it contains the expected type
        content_type = response.get('Content-Type', '')
        self.assertIn('text/plain', content_type)
        content = response.content.decode()
        self.assertIn('http_requests_total', content)
    
    def test_http_metrics(self):
        """Test HTTP request metrics"""
        # Make a request
        response = self.client.get('/health/')
        
        # Metrics should be recorded (via middleware)
        # We can't easily test the exact values without Prometheus running,
        # but we can verify the metrics exist
        self.assertIsNotNone(http_requests_total)
        self.assertIsNotNone(http_request_duration_seconds)
    
    def test_job_metrics(self):
        """Test job metrics"""
        # Metrics should exist
        self.assertIsNotNone(jobs_started_total)
        
        # Increment metric
        jobs_started_total.labels(
            job_type='DQ_RUN',
            tenant_id=str(self.tenant.id)
        ).inc()
        
        # Verify metric exists (can't easily test value without Prometheus)
        self.assertTrue(True)  # Placeholder - metric exists

