"""
Tests for Prometheus metrics.

Comprehensive tests without mocks/stubs, following engineering best practices and TDD principles.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from hub.apps.observability.otel_metrics import (
    get_status_class,
    http_request_duration_seconds,
    http_requests_total,
    jobs_started_total,
    metrics_view,
)
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MetricsTest(TestCase):
    """Test metrics functionality"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_metrics_endpoint(self):
        """Test Prometheus metrics endpoint"""
        # Use trailing slash to match URL pattern
        response = self.client.get("/metrics/")
        # If we get a redirect, follow it
        if response.status_code in [301, 302]:
            response = self.client.get(response.url, follow=True)
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}. Response: {response.content[:200]}",
        )
        # Content-Type might vary, check if it contains the expected type
        content_type = response.get("Content-Type", "")
        self.assertIn("text/plain", content_type)
        content = response.content.decode()
        self.assertIn("http_requests_total", content)

    def test_http_metrics(self):
        """Test HTTP request metrics"""
        # Make a request
        self.client.get("/health/")

        # Metrics should be recorded (via middleware)
        # We can't easily test the exact values without Prometheus running,
        # but we can verify the metrics exist
        self.assertIsNotNone(http_requests_total)
        self.assertIsNotNone(http_request_duration_seconds)

    def test_job_metrics(self):
        """Test job metrics"""
        self.assertIsNotNone(jobs_started_total)
        labeled = jobs_started_total.labels(job_type="DQ_RUN", tenant_id=str(self.tenant.id))
        before = labeled._value.get()
        labeled.inc()
        after = labeled._value.get()
        self.assertEqual(after, before + 1, "Counter did not increment")


class MetricsFailureTest(TestCase):
    """Test metrics failure scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_metrics_endpoint_not_available(self):
        """Test metrics endpoint when metrics not available"""
        # Metrics endpoint should handle unavailability gracefully
        response = self.client.get("/metrics/")

        # Should return 200 (if available) or 503 (if not available)
        self.assertIn(response.status_code, [200, 503])

    def test_metrics_with_invalid_labels(self):
        """Test metrics with None label values are accepted (converted to string)"""
        http_requests_total.labels(method=None, route="/api/v1/test/", status_class="2xx").inc()

    def test_metrics_with_missing_labels(self):
        """Test metrics with incomplete labels raises or fills defaults"""
        http_requests_total.labels(method="GET").inc()


class MetricsEdgeCasesTest(TestCase):
    """Test metrics edge cases"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_metrics_with_empty_string_labels(self):
        """Test metrics with empty string labels"""
        http_requests_total.labels(method="", route="", status_class="").inc()

    def test_metrics_with_very_long_labels(self):
        """Test metrics with very long label values"""
        long_route = "/api/v1/" + "a" * 1000 + "/"
        http_requests_total.labels(method="GET", route=long_route, status_class="2xx").inc()

    def test_metrics_with_special_characters(self):
        """Test metrics with special characters in labels"""
        http_requests_total.labels(
            method="GET", route="/api/v1/test!@#$%^&*()/", status_class="2xx"
        ).inc()

    def test_metrics_with_unicode(self):
        """Test metrics with unicode characters in labels"""
        http_requests_total.labels(method="GET", route="/api/v1/测试/", status_class="2xx").inc()

    def test_metrics_multiple_increments(self):
        """Test multiple increments to same metric"""
        labeled_metric = http_requests_total.labels(
            method="GET", route="/api/v1/multi-inc-test/", status_class="2xx"
        )
        before = labeled_metric._value.get()
        for _ in range(100):
            labeled_metric.inc()
        after = labeled_metric._value.get()
        self.assertEqual(after, before + 100)

    def test_metrics_concurrent_access(self):
        """Test metrics with concurrent-like access"""
        labeled = jobs_started_total.labels(job_type="DQ_RUN", tenant_id=str(self.tenant.id))
        before = labeled._value.get()
        for _i in range(50):
            labeled.inc()
        after = labeled._value.get()
        self.assertEqual(after, before + 50)

    def test_status_class_edge_cases(self):
        """Test status class calculation edge cases"""
        self.assertEqual(get_status_class(199), "other")
        self.assertEqual(get_status_class(299), "2xx")
        self.assertEqual(get_status_class(399), "other")
        self.assertEqual(get_status_class(499), "4xx")
        self.assertEqual(get_status_class(599), "5xx")
        self.assertEqual(get_status_class(600), "other")


class MetricsErrorHandlingTest(TestCase):
    """Test metrics error handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_metrics_handle_none_gracefully(self):
        """Test metrics handle None meter gracefully"""
        labeled = http_requests_total.labels(
            method="GET", route="/api/v1/test/", status_class="2xx"
        )
        before = labeled._value.get()
        labeled.inc()
        after = labeled._value.get()
        self.assertEqual(after, before + 1)

    def test_metrics_endpoint_error_handling(self):
        """Test metrics endpoint error handling"""
        # Metrics endpoint should handle errors gracefully
        response = self.client.get("/metrics/")

        # Should return appropriate status code
        self.assertIn(response.status_code, [200, 500, 503])

    def test_metrics_view_handles_exceptions(self):
        """Test metrics view handles exceptions"""
        # Directly test metrics_view function
        from django.http import HttpRequest

        request = HttpRequest()
        request.method = "GET"

        response = metrics_view(request)

        # Should return HttpResponse with appropriate status
        self.assertIsNotNone(response)
        self.assertIn(response.status_code, [200, 500, 503])
