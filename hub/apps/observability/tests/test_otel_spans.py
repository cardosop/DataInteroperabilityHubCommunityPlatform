"""
Phase 121G — OTel Span Tests

Verifies OpenTelemetry instrumentation module contracts.
"""

from django.test import TestCase


class TestOTelSpanAttributes(TestCase):
    """Verify OTel module structure and counter behavior."""

    def test_otel_metrics_module_exports_required_symbols(self):
        """OTel metrics module exports all required metrics and utilities."""
        from hub.apps.observability import otel_metrics

        expected_symbols = [
            "http_requests_total",
            "http_request_duration_seconds",
            "http_errors_total",
            "jobs_started_total",
            "job_duration_seconds",
            "db_connections_active",
            "job_queue_length",
            "dq_runs_total",
            "compliance_runs_total",
            "contract_validations_total",
            "get_status_class",
            "metrics_view",
        ]
        for name in expected_symbols:
            self.assertTrue(
                hasattr(otel_metrics, name),
                f"otel_metrics module missing required export: {name}",
            )

    def test_counter_increment_tracks_value(self):
        """Counter increment updates internal value tracking."""
        from hub.apps.observability.otel_metrics import http_requests_total

        labeled = http_requests_total.labels(method="GET", route="/otel-test/", status_class="2xx")
        before = labeled._value.get()
        labeled.inc()
        self.assertEqual(labeled._value.get(), before + 1)

    def test_get_status_class_maps_all_ranges(self):
        """get_status_class correctly maps HTTP codes across all ranges."""
        from hub.apps.observability.otel_metrics import get_status_class

        self.assertEqual(get_status_class(200), "2xx")
        self.assertEqual(get_status_class(299), "2xx")
        self.assertEqual(get_status_class(400), "4xx")
        self.assertEqual(get_status_class(404), "4xx")
        self.assertEqual(get_status_class(500), "5xx")
        self.assertEqual(get_status_class(503), "5xx")
        self.assertEqual(get_status_class(100), "other")
        self.assertEqual(get_status_class(300), "other")
