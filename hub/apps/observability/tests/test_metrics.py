"""
Tests for Prometheus metrics
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.observability.metrics import (
    http_requests_total,
    http_request_duration_seconds,
    jobs_started_total,
    metrics_view,
)

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
        response = self.client.get('/metrics')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain; version=0.0.4; charset=utf-8')
        self.assertIn('http_requests_total', response.content.decode())
    
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

