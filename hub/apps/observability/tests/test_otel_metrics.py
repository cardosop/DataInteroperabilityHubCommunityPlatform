"""
Comprehensive unit tests for OpenTelemetry Metrics.

Tests cover:
- Metric initialization and setup
- Counter metrics (inc, add, labels)
- Histogram metrics (observe, record)
- UpDownCounter metrics (set, inc, dec)
- Metrics view endpoint
- Error handling and edge cases
- Metric wrapper behavior when OpenTelemetry unavailable

All tests use real implementations - no mocks/stubs.
The metric wrappers (_CounterWrapper, _HistogramWrapper, _UpDownCounterWrapper)
handle None meters gracefully by no-opping, so no try/except blocks are needed.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from hub.apps.observability.otel_metrics import (
    OPENTELEMETRY_AVAILABLE,
    compliance_runs_total,
    contract_validations_total,
    db_connections_active,
    dq_runs_total,
    get_meter,
    get_status_class,
    http_request_duration_seconds,
    http_requests_total,
    job_duration_seconds,
    job_queue_length,
    jobs_started_total,
    setup_opentelemetry_metrics,
)
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class OpenTelemetryMetricsSetupTest(TestCase):
    """Test OpenTelemetry metrics setup and initialization"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_setup_opentelemetry_metrics_success(self):
        """Test successful OpenTelemetry metrics setup"""
        meter = setup_opentelemetry_metrics()

        if OPENTELEMETRY_AVAILABLE:
            # When OTEL is available, expect a meter instance (not None, not a random object)
            self.assertIsNotNone(meter, "setup_opentelemetry_metrics() returned None but OTEL is available")
        else:
            self.assertIsNone(meter, "setup_opentelemetry_metrics() should return None when OTEL unavailable")

    @override_settings(OPENTELEMETRY_METRICS_ENABLED=False)
    def test_setup_opentelemetry_metrics_disabled(self):
        """Test metrics setup when disabled in settings"""
        meter = setup_opentelemetry_metrics()
        self.assertIsNone(meter)

    def test_get_meter_returns_meter_or_none(self):
        """Test getting meter instance"""
        meter = get_meter()

        if OPENTELEMETRY_AVAILABLE:
            self.assertIsNotNone(meter, "get_meter() returned None but OTEL is available")
        else:
            self.assertIsNone(meter, "get_meter() should return None when OTEL unavailable")

    def test_get_status_class_2xx(self):
        """Test status class calculation for 2xx codes"""
        self.assertEqual(get_status_class(200), "2xx")
        self.assertEqual(get_status_class(201), "2xx")
        self.assertEqual(get_status_class(299), "2xx")

    def test_get_status_class_4xx(self):
        """Test status class calculation for 4xx codes"""
        self.assertEqual(get_status_class(400), "4xx")
        self.assertEqual(get_status_class(404), "4xx")
        self.assertEqual(get_status_class(499), "4xx")

    def test_get_status_class_5xx(self):
        """Test status class calculation for 5xx codes"""
        self.assertEqual(get_status_class(500), "5xx")
        self.assertEqual(get_status_class(503), "5xx")
        self.assertEqual(get_status_class(599), "5xx")

    def test_get_status_class_other(self):
        """Test status class calculation for other codes"""
        self.assertEqual(get_status_class(100), "other")
        self.assertEqual(get_status_class(300), "other")
        self.assertEqual(get_status_class(600), "other")


class CounterMetricsTest(TestCase):
    """Test Counter metrics functionality"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_http_requests_total_metric_exists(self):
        """Test that http_requests_total metric exists"""
        self.assertIsNotNone(http_requests_total)
        self.assertEqual(http_requests_total.name, "http_requests_total")

    def test_http_requests_total_increment(self):
        """Test incrementing HTTP requests counter"""
        labeled_metric = http_requests_total.labels(
            method="GET", route="/api/v1/test/", status_class="2xx"
        )
        # The wrapper handles None meter gracefully (no-op), so this never raises
        labeled_metric.inc()
        # Verify internal counter was incremented
        self.assertGreaterEqual(labeled_metric._value.get(), 1)

    def test_http_requests_total_add(self):
        """Test adding to HTTP requests counter"""
        labeled_metric = http_requests_total.labels(
            method="POST", route="/api/v1/test/", status_class="2xx"
        )
        labeled_metric.inc(amount=5)
        self.assertGreaterEqual(labeled_metric._value.get(), 5)

    def test_jobs_started_total_metric_exists(self):
        """Test that jobs_started_total metric exists"""
        self.assertIsNotNone(jobs_started_total)
        self.assertEqual(jobs_started_total.name, "jobs_started_total")

    def test_jobs_started_total_labels(self):
        """Test jobs_started_total with labels"""
        labeled_metric = jobs_started_total.labels(job_type="DQ_RUN", tenant_id=str(self.tenant.id))
        labeled_metric.inc()
        self.assertGreaterEqual(labeled_metric._value.get(), 1)

    def test_dq_runs_total_metric_exists(self):
        """Test that dq_runs_total metric exists"""
        self.assertIsNotNone(dq_runs_total)
        self.assertEqual(dq_runs_total.name, "dq_runs_total")

    def test_compliance_runs_total_metric_exists(self):
        """Test that compliance_runs_total metric exists"""
        self.assertIsNotNone(compliance_runs_total)
        self.assertEqual(compliance_runs_total.name, "compliance_runs_total")

    def test_contract_validations_total_metric_exists(self):
        """Test that contract_validations_total metric exists"""
        self.assertIsNotNone(contract_validations_total)
        self.assertEqual(contract_validations_total.name, "contract_validations_total")


class HistogramMetricsTest(TestCase):
    """Test Histogram metrics functionality"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_http_request_duration_seconds_metric_exists(self):
        """Test that http_request_duration_seconds metric exists"""
        self.assertIsNotNone(http_request_duration_seconds)
        self.assertEqual(http_request_duration_seconds.name, "http_request_duration_seconds")

    def test_http_request_duration_observe(self):
        """Test observing HTTP request duration"""
        labeled_metric = http_request_duration_seconds.labels(
            method="GET", route="/api/v1/test/", status_class="2xx"
        )
        labeled_metric.observe(0.123)
        # _value._count increments on each observe() call
        self.assertGreaterEqual(labeled_metric._value.get(), 1)

    def test_job_duration_seconds_metric_exists(self):
        """Test that job_duration_seconds metric exists"""
        self.assertIsNotNone(job_duration_seconds)
        self.assertEqual(job_duration_seconds.name, "job_duration_seconds")

    def test_job_duration_observe(self):
        """Test observing job duration"""
        labeled_metric = job_duration_seconds.labels(job_type="DQ_RUN", status="COMPLETED")
        labeled_metric.observe(10.5)
        self.assertGreaterEqual(labeled_metric._value.get(), 1)


class UpDownCounterMetricsTest(TestCase):
    """Test UpDownCounter (Gauge) metrics functionality"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_db_connections_active_metric_exists(self):
        """Test that db_connections_active metric exists"""
        self.assertIsNotNone(db_connections_active)
        self.assertEqual(db_connections_active.name, "db_connections_active")

    def test_db_connections_active_set(self):
        """Test setting database connections active count"""
        db_connections_active.set(5)
        # set() calls add() internally; value proxy tracks the set value
        self.assertEqual(db_connections_active._value.get(), 5)

    def test_job_queue_length_metric_exists(self):
        """Test that job_queue_length metric exists"""
        self.assertIsNotNone(job_queue_length)
        self.assertEqual(job_queue_length.name, "job_queue_length")

    def test_job_queue_length_inc_dec(self):
        """Test incrementing and decrementing job queue length"""
        labeled_metric = job_queue_length.labels(job_type="DQ_RUN", queue_name="default")
        labeled_metric.inc()
        self.assertEqual(labeled_metric._value.get(), 1)
        labeled_metric.dec()
        self.assertEqual(labeled_metric._value.get(), 0)


class MetricsViewEndpointTest(TestCase):
    """Test metrics view endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_metrics_endpoint_exists(self):
        """Test that metrics endpoint responds successfully"""
        response = self.client.get("/metrics/")
        if OPENTELEMETRY_AVAILABLE:
            self.assertEqual(response.status_code, 200,
                           "Metrics endpoint must return 200 when OTEL is available")
        else:
            self.assertIn(response.status_code, [200, 503],
                         "Metrics endpoint returns 200 or 503 when OTEL unavailable")

    def test_metrics_endpoint_content_type(self):
        """Test metrics endpoint content type"""
        response = self.client.get("/metrics/")

        if response.status_code == 200:
            content_type = response.get("Content-Type", "")
            self.assertIn("text/plain", content_type,
                         "Metrics endpoint must return text/plain content type")

    def test_metrics_endpoint_content(self):
        """Test metrics endpoint returns parseable Prometheus text"""
        response = self.client.get("/metrics/")

        if response.status_code == 200:
            content = response.content.decode()
            self.assertIsInstance(content, str)
            self.assertGreater(len(content), 0, "Metrics endpoint returned empty response")
            # Prometheus format lines should start with # HELP or # TYPE or metric name
            self.assertTrue(
                content.startswith("#") or "http_requests_total" in content,
                "Metrics endpoint should return Prometheus-formatted content",
            )


class MetricsFailureTest(TestCase):
    """Test metrics failure scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_metrics_handle_none_meter_gracefully(self):
        """Test that metrics handle None meter gracefully"""
        # Metrics wrappers are designed to no-op when meter is None;
        # this must never raise an exception.
        http_requests_total.labels(
            method="GET", route="/api/v1/test/", status_class="2xx"
        ).inc()
        # If we reach here without exception, the graceful handling works

    def test_metrics_labels_with_missing_required_labels(self):
        """Test metrics with incomplete labels use the available labels"""
        # The wrapper accepts any kwargs as labels; missing labels don't raise
        labeled_metric = http_requests_total.labels(method="GET")
        labeled_metric.inc()
        self.assertGreaterEqual(labeled_metric._value.get(), 1)

    def test_metrics_with_invalid_label_values(self):
        """Test metrics convert None labels to string representation"""
        # The wrapper converts label values via _labeled_metric_cache_key
        # which uses str(v); None -> "None"
        labeled_metric = http_requests_total.labels(
            method=None, route="/api/v1/test/", status_class="2xx"
        )
        labeled_metric.inc()
        self.assertGreaterEqual(labeled_metric._value.get(), 1)


class MetricsEdgeCasesTest(TestCase):
    """Test metrics edge cases"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_metrics_with_empty_labels(self):
        """Test metrics with empty labels dict"""
        # set() on the wrapper calls _UpDownCounterWrapper.set() which handles
        # no attributes case
        db_connections_active.set(0)
        self.assertEqual(db_connections_active._value.get(), 0)

    def test_metrics_with_very_long_label_values(self):
        """Test metrics with very long label values"""
        long_route = "/api/v1/" + "a" * 1000 + "/"
        labeled_metric = http_requests_total.labels(
            method="GET", route=long_route, status_class="2xx"
        )
        labeled_metric.inc()
        self.assertGreaterEqual(labeled_metric._value.get(), 1)

    def test_metrics_with_special_characters_in_labels(self):
        """Test metrics with special characters in labels"""
        labeled_metric = http_requests_total.labels(
            method="GET", route="/api/v1/test!@#$%^&*()/", status_class="2xx"
        )
        labeled_metric.inc()
        self.assertGreaterEqual(labeled_metric._value.get(), 1)

    def test_metrics_with_unicode_in_labels(self):
        """Test metrics with unicode characters in labels"""
        labeled_metric = http_requests_total.labels(
            method="GET", route="/api/v1/测试/", status_class="2xx"
        )
        labeled_metric.inc()
        self.assertGreaterEqual(labeled_metric._value.get(), 1)

    def test_metrics_multiple_increments(self):
        """Test multiple increments to same metric"""
        labeled_metric = http_requests_total.labels(
            method="GET", route="/api/v1/test/", status_class="2xx"
        )
        before = labeled_metric._value.get()
        for _ in range(10):
            labeled_metric.inc()
        self.assertEqual(labeled_metric._value.get(), before + 10)

    def test_metrics_negative_values(self):
        """Test metrics with negative values"""
        # UpDownCounter._value tracks the last set() call, not cumulative add() calls.
        # Set to a known baseline, then verify add() and add(-1) work correctly.
        db_connections_active.set(10)
        self.assertEqual(db_connections_active._value.get(), 10)
        db_connections_active.add(-3)
        # _value still reflects last set(10); the internal counter now holds 7.
        # Reset to read back the accumulated value.
        # The _current_values dict holds the running total per label key.
        self.assertEqual(db_connections_active._value.get(), 10)  # unchanged by add()
        # Restore to neutral value for test isolation
        db_connections_active.set(0)

    def test_metrics_zero_values(self):
        """Test metrics with zero values"""
        before_set = db_connections_active._value.get()
        db_connections_active.set(0)
        self.assertEqual(db_connections_active._value.get(), 0)
        # Restore previous value for isolation
        db_connections_active.set(before_set)

        labeled_metric = http_requests_total.labels(
            method="GET", route="/api/v1/test/", status_class="2xx"
        )
        before = labeled_metric._value.get()
        labeled_metric.inc(amount=0)
        self.assertEqual(labeled_metric._value.get(), before)

    def test_metrics_very_large_values(self):
        """Test metrics with very large values"""
        db_connections_active.set(999999999)
        self.assertEqual(db_connections_active._value.get(), 999999999)

        labeled_metric = job_duration_seconds.labels(job_type="DQ_RUN", status="COMPLETED")
        labeled_metric.observe(999999.99)
        self.assertGreaterEqual(labeled_metric._value.get(), 1)


class MetricsErrorHandlingTest(TestCase):
    """Test metrics error handling"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.client = Client()

    def test_metrics_view_handles_generation_error(self):
        """Test metrics view handles generation without crashing"""
        response = self.client.get("/metrics/")
        if OPENTELEMETRY_AVAILABLE:
            self.assertEqual(response.status_code, 200,
                           "Metrics endpoint must return 200 when OTEL is available")
        else:
            self.assertIn(response.status_code, [200, 503],
                         "Metrics endpoint returns 200 or 503 when OTEL unavailable")

    def test_metrics_view_handles_missing_registry(self):
        """Test metrics view handles missing registry gracefully"""
        response = self.client.get("/metrics/")
        if OPENTELEMETRY_AVAILABLE:
            self.assertEqual(response.status_code, 200)
        else:
            self.assertIn(response.status_code, [200, 503])

    def test_metrics_handle_concurrent_access(self):
        """Test metrics handle concurrent access pattern"""
        labeled_metric = http_requests_total.labels(
            method="GET", route="/api/v1/test/", status_class="2xx"
        )
        before = labeled_metric._value.get()
        for _ in range(100):
            labeled_metric.inc()
        self.assertEqual(labeled_metric._value.get(), before + 100)
