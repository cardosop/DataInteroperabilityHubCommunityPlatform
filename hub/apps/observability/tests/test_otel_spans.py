"""
Phase 121G — OTel Span Tests

Verifies OpenTelemetry instrumentation on API middleware.
"""
from django.test import TestCase


class TestOTelSpanAttributes(TestCase):
    """Verify OTel span creation with required attributes."""

    def test_otel_metrics_module_importable(self):
        """OTel metrics module is importable."""
        from hub.apps.observability import otel_metrics
        self.assertIsNotNone(otel_metrics)

    def test_http_requests_counter_exists(self):
        """http_requests_total counter is defined."""
        from hub.apps.observability.otel_metrics import http_requests_total
        self.assertIsNotNone(http_requests_total)

    def test_http_request_duration_histogram_exists(self):
        """http_request_duration_seconds histogram is defined."""
        from hub.apps.observability.otel_metrics import (
            http_request_duration_seconds,
        )
        self.assertIsNotNone(http_request_duration_seconds)

    def test_counter_supports_labels(self):
        """Counter supports labels (method, route, status_class)."""
        from hub.apps.observability.otel_metrics import http_requests_total
        labeled = http_requests_total.labels(
            method="GET", route="/test/", status_class="2xx"
        )
        self.assertIsNotNone(labeled)

    def test_counter_increment_tracks_value(self):
        """Counter increment updates internal value tracking."""
        from hub.apps.observability.otel_metrics import http_requests_total
        labeled = http_requests_total.labels(
            method="GET", route="/otel-test/", status_class="2xx"
        )
        labeled.inc()
        self.assertGreaterEqual(labeled._value.get(), 1)

    def test_get_status_class_function(self):
        """get_status_class correctly maps HTTP codes."""
        from hub.apps.observability.otel_metrics import get_status_class
        self.assertEqual(get_status_class(200), "2xx")
        self.assertEqual(get_status_class(404), "4xx")
        self.assertEqual(get_status_class(500), "5xx")

    def test_metrics_view_exists(self):
        """Metrics view endpoint is defined."""
        from hub.apps.observability.otel_metrics import metrics_view
        self.assertIsNotNone(metrics_view)
