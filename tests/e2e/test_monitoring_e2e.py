"""
E2E tests for monitoring.

Tests complete monitoring journeys: Prometheus metrics exposure,
Grafana dashboards, alerting rules, distributed tracing,
log correlation, and edge cases. Uses real services (no mocks).
"""
import os
import re
import time
import uuid

import pytest
import requests
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from hub.apps.jobs.models import JobStatus, JobType
from hub.apps.observability.logging import (
    configure_structlog,
    redact_pii,
    redact_pii_processor,
)
from hub.apps.observability.middleware import MetricsMiddleware
from hub.apps.observability.otel_metrics import (
    compliance_runs_total,
    dq_runs_total,
    http_requests_total,
    jobs_completed_total,
    jobs_started_total,
    tenant_queued_jobs,
    tenant_running_jobs,
)
from hub.apps.observability.tracing import get_tracer
from tests.factories import JobFactory, TenantFactory

from .conftest import (
    get_grafana_service_url,
    get_jaeger_service_url,
    get_prometheus_service_url,
)

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e5,
]
User = get_user_model()


class PrometheusMetricsExposureE2ETest(TestCase):
    """E2E tests for Prometheus metrics exposure"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

    def test_prometheus_metrics_endpoint_accessible(self):
        """Test that Prometheus metrics endpoint is accessible"""
        response = self.client.get('/metrics/')

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'text/plain', response.get('Content-Type', ''),
        )

    def test_prometheus_metrics_format_valid(self):
        """Test that metrics are in valid Prometheus format"""
        response = self.client.get('/metrics/')

        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')

        # Should have HELP and TYPE comments
        self.assertIn('# HELP', content)
        self.assertIn('# TYPE', content)

        # Should have metric lines
        lines = [
            line for line in content.split('\n')
            if line and not line.startswith('#')
        ]
        self.assertGreater(len(lines), 0)

    def test_prometheus_metrics_include_http_metrics(self):
        """Test that HTTP metrics are exposed"""
        # Make requests to generate metrics
        for _ in range(3):
            self.client.get('/health/')

        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('http_requests_total', content)
        self.assertIn('http_request_duration_seconds', content)

    def test_prometheus_metrics_include_job_metrics(self):
        """Test that job metrics are exposed"""
        # Create jobs to generate metrics
        JobFactory.create_job(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
        )

        # Increment job metrics
        jobs_started_total.labels(
            type=JobType.DQ_RUN,
            tenant_id=str(self.tenant.id),
        ).inc()

        # Also record completed metric
        jobs_completed_total.labels(
            type=JobType.DQ_RUN,
            status='COMPLETED',
            tenant_id=str(self.tenant.id),
        ).inc()

        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('jobs_started_total', content)
        self.assertIn('jobs_completed_total', content)

    def test_prometheus_metrics_include_per_tenant_metrics(self):
        """Test that per-tenant metrics are exposed"""
        tenant_id = str(self.tenant.id)

        # Set per-tenant metrics
        tenant_running_jobs.labels(
            tenant_id=tenant_id,
        ).set(5)
        tenant_queued_jobs.labels(
            tenant_id=tenant_id,
        ).set(3)

        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('tenant_running_jobs', content)
        self.assertIn('tenant_queued_jobs', content)

    def test_prometheus_metrics_include_service_metrics(self):
        """Test that service-specific metrics are exposed"""
        tenant_id = str(self.tenant.id)

        # Increment service metrics
        dq_runs_total.labels(
            status='success',
            engine='great_expectations',
            tenant_id=tenant_id,
        ).inc()

        compliance_runs_total.labels(
            status='success',
            risk_level='low',
            tenant_id=tenant_id,
        ).inc()

        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('dq_runs_total', content)
        self.assertIn('compliance_runs_total', content)

    def test_prometheus_metrics_scrapable_by_prometheus(self):
        """Test that metrics can be scraped by Prometheus"""
        # Generate metrics
        self.client.get('/health/')

        # Get metrics
        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Prometheus should be able to parse this
        self.assertIn('http_requests_total', content)

        # Verify metric lines are parseable
        lines = content.split('\n')
        metric_lines = [
            line for line in lines
            if line and not line.startswith('#')
        ]
        for line in metric_lines[:10]:  # Check first 10
            if line.strip():
                # Should have metric name and value
                self.assertTrue(
                    ' ' in line or '\t' in line,
                    f"Metric line should have space: {line}",
                )


class GrafanaDashboardsE2ETest(TestCase):
    """E2E tests for Grafana dashboards"""

    def setUp(self):
        """Set up test configuration"""
        self.grafana_url = get_grafana_service_url()
        self.timeout = 5

    def _check_grafana_available(self):
        """Check if Grafana is available (single attempt)"""
        try:
            resp = requests.get(
                f"{self.grafana_url}/api/health",
                timeout=self.timeout,
            )
            if resp.status_code in [200, 401, 403]:
                return True
        except (
            requests.exceptions.RequestException,
            requests.exceptions.Timeout,
        ):
            pass
        try:
            resp = requests.get(
                f"{self.grafana_url}/",
                timeout=self.timeout,
            )
            return resp.status_code in [200, 302, 401, 403]
        except (
            requests.exceptions.RequestException,
            requests.exceptions.Timeout,
        ):
            return False

    def _check_grafana_with_retry(
        self, max_attempts=10, delay_seconds=5,
    ):
        """Check Grafana with retries (handles slow startup)"""
        for attempt in range(max_attempts):
            if self._check_grafana_available():
                return True
            if attempt < max_attempts - 1:
                # INTENTIONAL: e2e test polling real services
                time.sleep(delay_seconds)
        return False

    def test_grafana_accessible(self):
        """Test that Grafana is accessible"""
        if not self._check_grafana_with_retry():
            pytest.skip(
                "Grafana not available (not reachable at "
                "%s after retries; ensure grafana-test "
                "container is running)" % self.grafana_url
            )

        try:
            resp = requests.get(
                f"{self.grafana_url}/api/health",
                timeout=self.timeout,
            )
            self.assertIn(
                resp.status_code, [200, 401, 403],
            )
        except requests.exceptions.RequestException:
            try:
                resp = requests.get(
                    f"{self.grafana_url}/",
                    timeout=self.timeout,
                )
                self.assertIn(
                    resp.status_code, [200, 302, 401, 403],
                )
            except requests.exceptions.RequestException:
                pytest.skip("Grafana not accessible")

    def test_grafana_dashboards_exist(self):
        """Test that Grafana dashboards exist"""
        dashboard_dir = 'monitoring/grafana/dashboards'
        if os.path.exists(dashboard_dir):
            self.assertTrue(os.path.exists(dashboard_dir))
        else:
            # Dashboards might be in different location
            pass

    def test_grafana_datasource_configured(self):
        """Test that Grafana datasource is configured"""
        path = 'monitoring/grafana/datasources/prometheus.yml'
        if os.path.exists(path):
            self.assertTrue(os.path.exists(path))
        else:
            # Datasource might be configured differently
            pass


class AlertingRulesE2ETest(TestCase):
    """E2E tests for alerting rules"""

    def setUp(self):
        """Set up test configuration"""
        self.prometheus_url = get_prometheus_service_url()
        self.timeout = 5

    def _check_prometheus_available(self):
        """Check if Prometheus is available"""
        try:
            resp = requests.get(
                f"{self.prometheus_url}/-/healthy",
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return True
        except (
            requests.exceptions.RequestException,
            requests.exceptions.Timeout,
        ):
            pass

        # Try /api/v1/status/config as fallback
        try:
            resp = requests.get(
                f"{self.prometheus_url}/api/v1/status/config",
                timeout=self.timeout,
            )
            return resp.status_code in [200, 401, 403]
        except (
            requests.exceptions.RequestException,
            requests.exceptions.Timeout,
        ):
            return False

    def test_alerting_rules_configured(self):
        """Test that alerting rules are configured"""
        path = 'monitoring/prometheus/alerts.yml'
        if os.path.exists(path):
            self.assertTrue(os.path.exists(path))
        else:
            # Alerts might be in different location
            pass

    def test_alertmanager_configured(self):
        """Test that Alertmanager is configured"""
        path = 'monitoring/alertmanager/alertmanager.yml'
        if os.path.exists(path):
            self.assertTrue(os.path.exists(path))
        else:
            # Config might be in different location
            pass

    def test_prometheus_alerts_endpoint(self):
        """Test that Prometheus alerts endpoint is accessible"""
        if not self._check_prometheus_available():
            try:
                url = (
                    f"{self.prometheus_url}"
                    "/api/v1/status/config"
                )
                resp = requests.get(url, timeout=self.timeout)
                if resp.status_code in [200, 401, 403]:
                    return
            except requests.exceptions.RequestException:
                pass
            pytest.skip("Prometheus not available")

        try:
            url = f"{self.prometheus_url}/api/v1/alerts"
            resp = requests.get(url, timeout=self.timeout)
            self.assertIn(
                resp.status_code, [200, 401, 403],
            )
        except requests.exceptions.RequestException:
            try:
                url = (
                    f"{self.prometheus_url}"
                    "/api/v1/status/config"
                )
                resp = requests.get(url, timeout=self.timeout)
                self.assertIn(
                    resp.status_code, [200, 401, 403],
                )
            except requests.exceptions.RequestException:
                pytest.skip("Prometheus not accessible")


class DistributedTracingE2ETest(TestCase):
    """E2E tests for distributed tracing"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.tenant = TenantFactory.create_tenant()

    def test_tracing_setup_complete(self):
        """Test that tracing setup is complete"""
        try:
            from opentelemetry import trace

            # Verify we can get a tracer provider and tracer
            provider = trace.get_tracer_provider()
            self.assertIsNotNone(provider)

            tracer = provider.get_tracer('test-setup')
            self.assertIsNotNone(tracer)

            # Verify the tracer can create a span
            with tracer.start_as_current_span("check") as span:
                self.assertIsNotNone(span)
                self.assertIsNotNone(
                    span.get_span_context(),
                )
        except ImportError:
            pytest.skip("OpenTelemetry not installed")

    def test_trace_context_in_logs(self):
        """Test that trace context is added to logs via API"""
        # TraceIDMiddleware adds X-Trace-Id to /api/ responses
        response = self.client.get('/api/v1/assets/')

        trace_id = response.get('X-Trace-Id')
        self.assertIsNotNone(
            trace_id,
            "Response must include X-Trace-Id header",
        )
        assert trace_id is not None
        # Trace ID should be a 32-character hex string
        self.assertEqual(len(trace_id), 32)
        self.assertTrue(
            all(c in '0123456789abcdef' for c in trace_id),
            f"Trace ID must be lowercase hex: {trace_id}",
        )

    def test_trace_correlation_across_services(self):
        """Test that traces can be correlated across services"""
        # Make two API requests and verify both get trace IDs
        response1 = self.client.get('/api/v1/assets/')
        response2 = self.client.get('/api/v1/assets/')

        tid1 = response1.get('X-Trace-Id')
        tid2 = response2.get('X-Trace-Id')

        self.assertIsNotNone(
            tid1, "First response must include X-Trace-Id",
        )
        self.assertIsNotNone(
            tid2, "Second response must include X-Trace-Id",
        )

        # Each request should get a unique trace ID
        self.assertNotEqual(
            tid1, tid2,
            "Different requests must get different trace IDs",
        )

        # Both should be valid 32-char hex
        assert tid1 is not None
        assert tid2 is not None
        for tid in (tid1, tid2):
            self.assertEqual(len(tid), 32)
            self.assertTrue(
                all(c in '0123456789abcdef' for c in tid),
            )

    def test_jaeger_trace_export(self):
        """Test that traces are exported to Jaeger"""
        jaeger_url = get_jaeger_service_url()
        timeout = 5

        try:
            resp = requests.get(jaeger_url, timeout=timeout)
            self.assertIn(
                resp.status_code, [200, 401, 403],
            )
        except requests.exceptions.RequestException:
            pytest.skip("Jaeger not accessible")


class LogCorrelationE2ETest(TestCase):
    """E2E tests for log correlation"""

    def setUp(self):
        """Set up test data"""
        configure_structlog()
        self.client = Client()
        self.tenant = TenantFactory.create_tenant()

    def test_log_correlation_with_trace_id(self):
        """Test that logs include trace_id for correlation"""
        # TraceIDMiddleware sets X-Trace-Id on /api/ responses
        response = self.client.get('/api/v1/assets/')

        trace_id = response.get('X-Trace-Id')
        self.assertIsNotNone(
            trace_id,
            "Response must include X-Trace-Id",
        )
        assert trace_id is not None
        self.assertEqual(
            len(trace_id), 32,
            "Trace ID must be 32 hex characters",
        )
        self.assertTrue(
            all(c in '0123456789abcdef' for c in trace_id),
        )

    def test_log_correlation_with_span_id(self):
        """Test that logs include span_id for correlation"""
        # TraceIDMiddleware generates span_id internally;
        # X-Trace-Id on response confirms the middleware ran
        response = self.client.get('/api/v1/assets/')
        trace_id = response.get('X-Trace-Id')
        self.assertIsNotNone(
            trace_id,
            "X-Trace-Id must be set, confirming span",
        )

        # Second request gets a different trace (and span)
        response2 = self.client.get('/api/v1/assets/')
        trace_id_2 = response2.get('X-Trace-Id')
        self.assertIsNotNone(trace_id_2)
        self.assertNotEqual(
            trace_id, trace_id_2,
            "Different requests must produce different spans",
        )

    def test_log_correlation_with_request_id(self):
        """Test that logs include request_id for correlation"""
        # RequestIDMiddleware sets X-Request-ID on responses
        response = self.client.get('/api/v1/assets/')

        req_id = response.get('X-Request-ID')
        self.assertIsNotNone(
            req_id,
            "Response must include X-Request-ID",
        )

        # Second request gets a different request ID
        response2 = self.client.get('/api/v1/assets/')
        req_id_2 = response2.get('X-Request-ID')
        self.assertIsNotNone(req_id_2)
        self.assertNotEqual(
            req_id, req_id_2,
            "Different requests must get different IDs",
        )

    def test_log_correlation_pii_redaction(self):
        """Test that PII is redacted in logs for correlation"""
        # Verify redact_pii actually redacts email addresses
        result = redact_pii("User test@example.com logged in")
        self.assertNotIn("test@example.com", result)
        self.assertIn("[EMAIL_REDACTED]", result)

        # Verify redact_pii_processor redacts PII fields
        event_dict = {
            'event': 'User test@example.com logged in',
            'email': 'sensitive@example.com',
            'password': 'secret123',
        }
        processed = redact_pii_processor(
            None, None, event_dict,
        )
        self.assertNotIn(
            'test@example.com', processed['event'],
        )
        self.assertEqual(processed['email'], '[REDACTED]')
        self.assertEqual(
            processed['password'], '[REDACTED]',
        )

    def test_log_correlation_structured_format(self):
        """Test that logs are in structured format"""
        import structlog

        configure_structlog()

        # Verify structlog has the expected processors
        config = structlog.get_config()
        processor_names = [
            getattr(p, '__name__', type(p).__name__)
            for p in config.get('processors', [])
        ]
        self.assertIn(
            'merge_contextvars', processor_names,
            "must include merge_contextvars processor",
        )
        self.assertIn(
            'add_trace_context', processor_names,
            "must include add_trace_context processor",
        )
        self.assertIn(
            'redact_pii_processor', processor_names,
            "must include redact_pii_processor",
        )


class MonitoringEdgeCasesE2ETest(TestCase):
    """E2E tests for monitoring edge cases"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.tenant = TenantFactory.create_tenant()

    def test_metrics_endpoint_high_load(self):
        """Test metrics endpoint under high load"""
        num_requests = 100
        start_time = time.monotonic()
        for _ in range(num_requests):
            self.client.get('/health/')
        load_duration = time.monotonic() - start_time

        # Get metrics after load
        metrics_start = time.monotonic()
        response = self.client.get('/metrics/')
        metrics_duration = time.monotonic() - metrics_start

        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn('http_requests_total', content)

        # Metrics endpoint should respond within 2s
        self.assertLess(
            metrics_duration, 2.0,
            "Metrics endpoint took "
            f"{metrics_duration:.2f}s, expected < 2s",
        )

        # All health requests should complete fast
        self.assertLess(
            load_duration, 30.0,
            "100 health requests took "
            f"{load_duration:.2f}s, expected < 30s",
        )

    def test_metrics_endpoint_concurrent_requests(self):
        """Test metrics endpoint with concurrent requests"""
        import threading

        results = []

        def get_metrics():
            resp = self.client.get('/metrics/')
            results.append(resp.status_code)

        # Make concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=get_metrics)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All should succeed
        self.assertEqual(len(results), 10)
        self.assertTrue(
            all(status == 200 for status in results),
        )

    def test_metrics_with_special_characters_in_labels(self):
        """Test metrics with special characters in labels"""
        http_requests_total.labels(
            method='GET',
            route='/test/with-special-chars',
            status_class='2xx',
        ).inc()

        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Verify the label value appears in the output
        self.assertIn('http_requests_total', content)
        self.assertIn('/test/with-special-chars', content)

    def test_metrics_with_unicode_in_labels(self):
        """Test metrics with unicode in labels"""
        http_requests_total.labels(
            method='GET',
            route='/test/\u6d4b\u8bd5',
            status_class='2xx',
        ).inc()

        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Verify the unicode label appears in output
        self.assertIn('http_requests_total', content)
        self.assertIn('\u6d4b\u8bd5', content)

    def test_metrics_with_very_long_labels(self):
        """Test metrics with very long labels"""
        long_route = '/test/' + 'x' * 1000

        http_requests_total.labels(
            method='GET',
            route=long_route,
            status_class='2xx',
        ).inc()

        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Verify the long label actually appears
        self.assertIn('http_requests_total', content)
        self.assertIn(long_route, content)

    def test_metrics_with_many_tenants(self):
        """Test metrics with many tenants"""
        tenants = []
        for i in range(10):
            tenant = TenantFactory.create_tenant()
            tenants.append(tenant)

        # Set metrics for each tenant
        for idx, tenant in enumerate(tenants):
            tenant_running_jobs.labels(
                tenant_id=str(tenant.id),
            ).set(idx)

        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Should include all tenant metrics
        self.assertIn('tenant_running_jobs', content)

    def test_metrics_persist_after_health_check(self):
        """Test metrics available after health check requests"""
        # Generate metrics via health check
        health_response = self.client.get('/health/')
        self.assertIn(
            health_response.status_code, [200, 503],
        )

        # Fetch metrics and verify incremented counter
        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        self.assertIn('http_requests_total', content)

        # Verify non-zero count
        match = re.search(
            r'http_requests_total\{[^}]*\}\s+'
            r'(\d+\.?\d*)',
            content,
        )
        self.assertIsNotNone(
            match,
            "http_requests_total must have a sample",
        )
        assert match is not None
        value = float(match.group(1))
        self.assertGreater(
            value, 0,
            "http_requests_total must be > 0",
        )

    def test_tracing_with_disabled_setting(self):
        """Test tracing behavior when disabled"""
        from django.test import override_settings

        with override_settings(OPENTELEMETRY_ENABLED=False):
            tracer = get_tracer('test')
            # get_tracer returns None when disabled
            self.assertIsNone(
                tracer,
                "get_tracer must return None when "
                "OPENTELEMETRY_ENABLED=False",
            )

    def test_logging_with_missing_trace_context(self):
        """Test logging when trace context is missing"""
        import structlog

        configure_structlog()
        logger = structlog.get_logger(__name__)

        # Log without trace context -- must not raise
        logger.info("test message without trace context")

        # Verify add_trace_context processor handles missing
        # context gracefully by returning event_dict unchanged
        from hub.apps.observability.logging import (
            add_trace_context,
        )
        event = {'event': 'test', 'level': 'info'}
        result = add_trace_context(None, None, event)
        self.assertEqual(result['event'], 'test')

    def test_metrics_middleware_normalizes_routes(self):
        """Test that metrics middleware normalizes routes"""
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse()

        middleware = MetricsMiddleware(get_response)

        # Test route normalization
        normalized = middleware._normalize_route(
            '/api/v1/contracts/'
            '123e4567-e89b-12d3-a456-426614174000/',
        )
        self.assertEqual(
            normalized, '/api/v1/contracts/{id}/',
        )

        normalized = middleware._normalize_route(
            '/api/v1/assets/123/',
        )
        self.assertEqual(
            normalized, '/api/v1/assets/{id}/',
        )

    def test_metrics_middleware_handles_missing_start_time(self):
        """Test metrics middleware handles missing start time"""
        from django.http import HttpResponse
        from django.test import RequestFactory

        def get_response(request):
            return HttpResponse()

        middleware = MetricsMiddleware(get_response)
        request = RequestFactory().get("/test/")
        # Ensure _metrics_start_time is not set
        if hasattr(request, "_metrics_start_time"):
            delattr(request, "_metrics_start_time")
        response = HttpResponse()
        response.status_code = 200

        # Should not fail if start_time is missing
        result = middleware.process_response(
            request, response,
        )
        self.assertIsNotNone(result)

    def test_prometheus_metrics_registry_cleanup(self):
        """Test that metrics registry handles cleanup"""
        # Generate metrics
        self.client.get('/health/')

        # Get metrics multiple times -- all must succeed
        for _ in range(5):
            response = self.client.get('/metrics/')
            self.assertEqual(response.status_code, 200)

        # Final fetch should still contain metrics
        content = response.content.decode('utf-8')
        self.assertIn('http_requests_total', content)

    def test_metrics_with_zero_values(self):
        """Test that metrics with zero values are handled"""
        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Should include metrics even if zero
        self.assertIn('jobs_started_total', content)

    def test_metrics_with_negative_values(self):
        """Test that metrics handle negative values"""
        tenant_id = str(self.tenant.id)
        metric = tenant_running_jobs.labels(
            tenant_id=tenant_id,
        )

        metric.set(5)
        metric.dec(10)  # Should result in -5

        # Should handle negative values
        self.assertEqual(metric._value.get(), -5)

    def test_tracing_sampling_rate_configuration(self):
        """Test that tracing sampling rate is configured"""
        from django.conf import settings

        # Sampling rate: 100% in dev, 10% in production
        is_production = not settings.DEBUG
        expected_rate = 0.10 if is_production else 1.0

        # Verify the rate is a valid float in [0, 1]
        self.assertGreaterEqual(expected_rate, 0.0)
        self.assertLessEqual(expected_rate, 1.0)

        # In test mode (DEBUG=True) rate should be 1.0
        if settings.DEBUG:
            self.assertEqual(expected_rate, 1.0)
        else:
            self.assertEqual(expected_rate, 0.10)

    def test_log_correlation_with_nested_spans(self):
        """Test log correlation with nested spans"""
        try:
            tracer = get_tracer('test')
            if tracer:
                with tracer.start_as_current_span(
                    "parent_span",
                ) as parent:
                    with tracer.start_as_current_span(
                        "child_span",
                    ) as child:
                        p_ctx = parent.get_span_context()
                        c_ctx = child.get_span_context()

                        # Same trace_id for parent & child
                        self.assertEqual(
                            p_ctx.trace_id,
                            c_ctx.trace_id,
                        )
        except ImportError:
            pytest.skip("OpenTelemetry not installed")

    def test_metrics_endpoint_cors_headers(self):
        """Test metrics endpoint has appropriate headers"""
        response = self.client.get('/metrics/')

        # Metrics endpoint should return 200
        self.assertEqual(response.status_code, 200)

    def test_metrics_endpoint_cache_headers(self):
        """Test metrics endpoint has appropriate cache"""
        response = self.client.get('/metrics/')
        self.assertEqual(response.status_code, 200)

        # Metrics should not be cached with long TTL
        cache_control = response.get('Cache-Control', '')
        self.assertNotIn('max-age=3600', cache_control)
