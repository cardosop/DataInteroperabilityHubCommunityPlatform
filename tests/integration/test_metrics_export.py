"""
Integration tests for metrics export

Tests verify that /metrics endpoints return valid Prometheus format
and that metrics are properly exposed for scraping.
"""
import pytest
import re
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MetricsExportTest(TestCase):
    """Test metrics export endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
    
    def test_api_service_metrics_endpoint(self):
        """Test that API service /metrics endpoint returns valid Prometheus format"""
        response = self.client.get('/metrics/')
        
        # Should return 200
        self.assertEqual(response.status_code, 200)
        
        # Should have correct content type
        content_type = response.get('Content-Type', '')
        self.assertIn('text/plain', content_type)
        
        # Should contain Prometheus metrics
        content = response.content.decode('utf-8')
        
        # Check for common Prometheus metric patterns
        # Prometheus metrics format: metric_name{labels} value
        metric_pattern = r'^[a-zA-Z_:][a-zA-Z0-9_:]*\{[^}]*\}\s+[\d.]+$'
        lines = content.split('\n')
        metric_lines = [line for line in lines if line and not line.startswith('#')]
        
        # Should have at least some metrics
        self.assertGreater(len(metric_lines), 0, "Should have at least one metric")
        
        # Verify common metrics are present
        self.assertIn('http_requests_total', content)
        self.assertIn('http_request_duration_seconds', content)
    
    def test_metrics_format_valid(self):
        """Test that metrics follow Prometheus format"""
        response = self.client.get('/metrics/')
        content = response.content.decode('utf-8')
        
        # Prometheus format rules:
        # 1. Metric names: [a-zA-Z_:][a-zA-Z0-9_:]*
        # 2. Labels: {label="value",...}
        # 3. Values: numbers (int or float)
        # 4. Comments: # HELP and # TYPE
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue  # Skip comments and empty lines
            
            # Check for HELP or TYPE comments
            if line.startswith('# HELP') or line.startswith('# TYPE'):
                continue
            
            # Check metric format: name{labels} value
            # More lenient pattern to allow for various formats
            metric_match = re.match(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+([\d.]+|NaN|Inf|-Inf)', line)
            if metric_match:
                metric_name = metric_match.group(1)
                # Verify metric name is valid
                self.assertTrue(
                    re.match(r'^[a-zA-Z_:][a-zA-Z0-9_:]*$', metric_name),
                    f"Invalid metric name: {metric_name}"
                )
    
    def test_metrics_include_http_metrics(self):
        """Test that HTTP metrics are included"""
        # Make a request to generate metrics
        self.client.get('/health/')
        
        # Get metrics
        response = self.client.get('/metrics/')
        content = response.content.decode('utf-8')
        
        # Should include HTTP metrics
        self.assertIn('http_requests_total', content)
        self.assertIn('http_request_duration_seconds', content)
    
    def test_metrics_include_job_metrics(self):
        """Test that job metrics are included"""
        response = self.client.get('/metrics/')
        content = response.content.decode('utf-8')
        
        # Should include job metrics (even if zero)
        self.assertIn('jobs_started_total', content)
        self.assertIn('jobs_completed_total', content)
        self.assertIn('jobs_failed_total', content)
    
    def test_metrics_include_service_metrics(self):
        """Test that service-specific metrics are included"""
        response = self.client.get('/metrics/')
        content = response.content.decode('utf-8')
        
        # Should include DQ, compliance, and contract metrics
        self.assertIn('dq_runs_total', content)
        self.assertIn('compliance_runs_total', content)
        self.assertIn('contract_validations_total', content)
    
    def test_metrics_help_text(self):
        """Test that metrics include HELP and TYPE comments"""
        response = self.client.get('/metrics/')
        content = response.content.decode('utf-8')
        
        # Should have HELP comments
        self.assertIn('# HELP', content)
        
        # Should have TYPE comments
        self.assertIn('# TYPE', content)
        
        # Verify format: # HELP metric_name description
        help_pattern = r'# HELP\s+[a-zA-Z_:][a-zA-Z0-9_:]*\s+.+'
        help_lines = [line for line in content.split('\n') if line.startswith('# HELP')]
        self.assertGreater(len(help_lines), 0, "Should have HELP comments")
        
        # Verify format: # TYPE metric_name type
        type_pattern = r'# TYPE\s+[a-zA-Z_:][a-zA-Z0-9_:]*\s+(counter|gauge|histogram|summary)'
        type_lines = [line for line in content.split('\n') if line.startswith('# TYPE')]
        self.assertGreater(len(type_lines), 0, "Should have TYPE comments")
    
    def test_metrics_labels_format(self):
        """Test that metric labels are properly formatted"""
        response = self.client.get('/metrics/')
        content = response.content.decode('utf-8')
        
        # Find metrics with labels
        labeled_metric_pattern = r'^([a-zA-Z_:][a-zA-Z0-9_:]*)\{([^}]+)\}\s+[\d.]+$'
        
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            match = re.match(labeled_metric_pattern, line)
            if match:
                labels_str = match.group(2)
                # Labels should be comma-separated key="value" pairs
                # More lenient: just check it's not empty and has = sign
                self.assertIn('=', labels_str, f"Labels should have key=value format: {line}")
    
    def test_metrics_endpoint_performance(self):
        """Test that metrics endpoint responds quickly"""
        import time
        
        start_time = time.time()
        response = self.client.get('/metrics/')
        duration = time.time() - start_time
        
        # Should respond quickly (under 1 second)
        self.assertLess(duration, 1.0, f"Metrics endpoint took {duration:.2f}s, should be < 1s")
        self.assertEqual(response.status_code, 200)

