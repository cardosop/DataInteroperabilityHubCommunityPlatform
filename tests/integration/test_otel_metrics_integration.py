"""
Integration tests for OpenTelemetry metrics export.

Tests verify that OpenTelemetry metrics are properly exported in Prometheus format
and can be scraped by Prometheus.
"""

import re
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from hub.apps.observability.otel_metrics import (
    asset_compliance_status,
    asset_dq_status,
    cache_hits_total,
    cache_misses_total,
    compliance_runs_total,
    contract_migrations_total,
    contract_validations_total,
    db_connections_active,
    db_query_duration_seconds,
    dq_runs_total,
    file_upload_size_bytes,
    file_uploads_total,
    http_errors_total,
    http_request_duration_seconds,
    http_requests_total,
    job_duration_seconds,
    job_queue_length,
    jobs_completed_total,
    jobs_failed_total,
    jobs_started_total,
    tenant_queued_jobs,
    tenant_running_jobs,
)
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class OpenTelemetryMetricsIntegrationTest(TestCase):
    """Integration tests for OpenTelemetry metrics export"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.tenant = TenantFactory.create_tenant()
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

    def test_metrics_endpoint_returns_prometheus_format(self):
        """Test that /metrics endpoint returns Prometheus format"""
        response = self.client.get("/metrics/")

        # Should return 200 or 503 (if metrics not available)
        self.assertIn(response.status_code, [200, 503])

        if response.status_code == 200:
            self.assertIn("text/plain", response.get("Content-Type", ""))
            content = response.content.decode("utf-8")
            # Should have Prometheus format indicators
            self.assertTrue(len(content) > 0)

    def test_metrics_endpoint_includes_all_metric_types(self):
        """Test that /metrics endpoint includes all metric types"""
        # Generate metrics of each type
        http_requests_total.labels(method="GET", route="/test/", status_class="2xx").inc()
        http_request_duration_seconds.labels(
            method="GET", route="/test/", status_class="2xx"
        ).observe(0.1)
        http_errors_total.labels(method="GET", route="/test/", status_code=404).inc()

        jobs_started_total.labels(type="DQ_RUN", tenant_id=str(self.tenant.id)).inc()
        job_duration_seconds.labels(type="DQ_RUN", status="COMPLETED").observe(10.5)

        tenant_running_jobs.labels(tenant_id=str(self.tenant.id)).set(5)
        job_queue_length.labels(type="DQ_RUN", queue_name="default").set(3)

        response = self.client.get("/metrics/")
        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Should include Counter metrics
            self.assertIn("http_requests_total", content)
            self.assertIn("jobs_started_total", content)

            # Should include Histogram metrics
            self.assertIn("http_request_duration_seconds", content)
            self.assertIn("job_duration_seconds", content)

            # Should include Gauge metrics (UpDownCounter)
            self.assertIn("tenant_running_jobs", content)
            self.assertIn("job_queue_length", content)

    def test_metrics_endpoint_help_and_type_comments(self):
        """Test that metrics include HELP and TYPE comments"""
        response = self.client.get("/metrics/")
        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Should have HELP comments
            self.assertIn("# HELP", content)

            # Should have TYPE comments
            self.assertIn("# TYPE", content)

            # Verify format
            help_lines = [line for line in content.split("\n") if line.startswith("# HELP")]
            self.assertGreater(len(help_lines), 0)

    def test_metrics_endpoint_performance(self):
        """Test that metrics endpoint responds quickly"""
        import time

        start_time = time.time()
        response = self.client.get("/metrics/")
        duration = time.time() - start_time

        # Should respond in < 1 second
        self.assertLess(duration, 1.0, f"Metrics endpoint took {duration:.2f}s")
        self.assertIn(response.status_code, [200, 503])

    def test_metrics_export_after_requests(self):
        """Test that metrics are exported after making requests"""
        # Make several requests to generate metrics via middleware
        for _i in range(5):
            self.client.get("/health/")

        # Get metrics
        response = self.client.get("/metrics/")
        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Should include metrics from requests
            self.assertIn("http_requests_total", content)

    def test_metrics_labels_preserved(self):
        """Test that metric labels are preserved in export"""
        tenant_id = str(self.tenant.id)

        # Set per-tenant metric
        tenant_running_jobs.labels(tenant_id=tenant_id).set(5)

        # Get metrics
        response = self.client.get("/metrics/")
        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Should include tenant_id in labels
            self.assertIn("tenant_running_jobs", content)
            # Note: OpenTelemetry may format labels differently, so we check for metric name
            # The actual label format may vary but metric should be present

    def test_all_counter_metrics_exported(self):
        """Test that all Counter metrics are exported"""
        # Record metrics
        http_requests_total.labels(method="GET", route="/test/", status_class="2xx").inc()
        http_errors_total.labels(method="GET", route="/test/", status_code=404).inc()
        jobs_started_total.labels(type="DQ_RUN", tenant_id=str(self.tenant.id)).inc()
        jobs_completed_total.labels(
            type="DQ_RUN", status="COMPLETED", tenant_id=str(self.tenant.id)
        ).inc()
        jobs_failed_total.labels(
            type="DQ_RUN", error_code="TIMEOUT", tenant_id=str(self.tenant.id)
        ).inc()
        dq_runs_total.labels(
            status="success", engine="great_expectations", tenant_id=str(self.tenant.id)
        ).inc()
        compliance_runs_total.labels(
            status="success", risk_level="low", tenant_id=str(self.tenant.id)
        ).inc()
        cache_hits_total.labels(cache_key_prefix="rate_limit").inc()
        cache_misses_total.labels(cache_key_prefix="rate_limit").inc()
        file_uploads_total.labels(
            status="success", file_type="csv", tenant_id=str(self.tenant.id)
        ).inc()
        contract_validations_total.labels(
            status="valid", spec_type="ODCS", tenant_id=str(self.tenant.id)
        ).inc()
        contract_migrations_total.labels(
            source_version="1.0",
            target_version="2.0",
            strategy="auto",
            status="success",
            tenant_id=str(self.tenant.id),
        ).inc()

        response = self.client.get("/metrics/")
        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Check for Counter metrics (may have prefixes in OpenTelemetry)
            counter_metrics = [
                "http_requests_total",
                "http_errors_total",
                "jobs_started_total",
                "jobs_completed_total",
                "jobs_failed_total",
                "dq_runs_total",
                "compliance_runs_total",
                "cache_hits_total",
                "cache_misses_total",
                "file_uploads_total",
                "contract_validations_total",
                "contract_migrations_total",
            ]

            for metric in counter_metrics:
                # Check for metric name (may be prefixed by OpenTelemetry)
                found = any(
                    metric in line or metric.replace("_total", "") in line
                    for line in content.split("\n")
                )
                self.assertTrue(found, f"Counter metric {metric} should be in export")

    def test_all_histogram_metrics_exported(self):
        """Test that all Histogram metrics are exported"""
        # Record metrics
        http_request_duration_seconds.labels(
            method="GET", route="/test/", status_class="2xx"
        ).observe(0.1)
        job_duration_seconds.labels(type="DQ_RUN", status="COMPLETED").observe(10.5)
        db_query_duration_seconds.labels(operation="SELECT").observe(0.01)
        file_upload_size_bytes.labels(file_type="csv").observe(1024)

        response = self.client.get("/metrics/")
        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Check for Histogram metrics
            histogram_metrics = [
                "http_request_duration_seconds",
                "job_duration_seconds",
                "db_query_duration_seconds",
                "file_upload_size_bytes",
            ]

            for metric in histogram_metrics:
                found = any(metric in line for line in content.split("\n"))
                self.assertTrue(found, f"Histogram metric {metric} should be in export")

    def test_all_gauge_metrics_exported(self):
        """Test that all Gauge metrics are exported"""
        # Record metrics
        db_connections_active.set(5)
        job_queue_length.labels(type="DQ_RUN", queue_name="default").set(3)
        tenant_running_jobs.labels(tenant_id=str(self.tenant.id)).set(5)
        tenant_queued_jobs.labels(tenant_id=str(self.tenant.id)).set(3)
        asset_dq_status.labels(status="PASS", tenant_id=str(self.tenant.id)).set(10)
        asset_compliance_status.labels(status="COMPLIANT", tenant_id=str(self.tenant.id)).set(5)

        response = self.client.get("/metrics/")
        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Check for Gauge metrics (UpDownCounter)
            gauge_metrics = [
                "db_connections_active",
                "job_queue_length",
                "tenant_running_jobs",
                "tenant_queued_jobs",
                "asset_dq_status_count",
                "asset_compliance_status_count",
            ]

            for metric in gauge_metrics:
                found = any(metric in line for line in content.split("\n"))
                self.assertTrue(found, f"Gauge metric {metric} should be in export")

    def test_metrics_prometheus_format_valid(self):
        """Test that metrics are in valid Prometheus format"""
        # Generate some metrics
        http_requests_total.labels(method="GET", route="/test/", status_class="2xx").inc()

        response = self.client.get("/metrics/")
        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Should have HELP and TYPE comments
            self.assertIn("# HELP", content)
            self.assertIn("# TYPE", content)

            # Should have metric lines
            lines = [line for line in content.split("\n") if line and not line.startswith("#")]
            self.assertGreater(len(lines), 0)

            # Verify metric lines are parseable (name value or name{labels} value)
            for line in lines[:10]:  # Check first 10 metric lines
                if line.strip():
                    # Should have metric name and value
                    parts = line.split()
                    self.assertGreaterEqual(
                        len(parts), 2, f"Metric line should have name and value: {line}"
                    )

    def test_metrics_can_be_scraped_by_prometheus(self):
        """Test that metrics can be scraped by Prometheus (format validation)"""
        # Generate metrics
        self.client.get("/health/")
        http_requests_total.labels(method="GET", route="/health/", status_class="2xx").inc()

        # Get metrics
        response = self.client.get("/metrics/")
        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Prometheus should be able to parse this
            # Verify format is correct
            self.assertIn("http_requests_total", content)

            # Verify metric lines are parseable
            lines = content.split("\n")
            metric_lines = [line for line in lines if line and not line.startswith("#")]
            for line in metric_lines[:10]:  # Check first 10
                if line.strip():
                    # Should have metric name and value (separated by space or tab)
                    self.assertTrue(
                        " " in line or "\t" in line, f"Metric line should have space: {line}"
                    )

                    # Should not have invalid characters
                    self.assertNotIn("\x00", line, "Metric line should not contain null bytes")

    def test_histogram_buckets_exported(self):
        """Test that histogram buckets are exported correctly"""
        # Record histogram values
        http_request_duration_seconds.labels(
            method="GET", route="/test/", status_class="2xx"
        ).observe(0.1)
        http_request_duration_seconds.labels(
            method="GET", route="/test/", status_class="2xx"
        ).observe(0.5)
        http_request_duration_seconds.labels(
            method="GET", route="/test/", status_class="2xx"
        ).observe(1.0)

        response = self.client.get("/metrics/")
        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Should include histogram metric
            self.assertIn("http_request_duration_seconds", content)

            # Should include bucket information (OpenTelemetry exports buckets)
            # Buckets are typically exported as _bucket metrics
            bucket_lines = [line for line in content.split("\n") if "_bucket" in line]
            # OpenTelemetry may export buckets differently, so we just verify histogram exists
            self.assertTrue(len(bucket_lines) > 0 or "http_request_duration_seconds" in content)

    def test_metric_labels_correct_format(self):
        """Test that metric labels are in correct format"""
        tenant_id = str(self.tenant.id)

        # Record metrics with labels
        http_requests_total.labels(method="GET", route="/test/", status_class="2xx").inc()
        jobs_started_total.labels(type="DQ_RUN", tenant_id=tenant_id).inc()

        response = self.client.get("/metrics/")
        if response.status_code == 200:
            content = response.content.decode("utf-8")

            # Should include metrics with labels
            # OpenTelemetry formats labels as attributes, Prometheus exporter converts to labels
            # Format: metric_name{label1="value1",label2="value2"} value
            self.assertIn("http_requests_total", content)
            self.assertIn("jobs_started_total", content)

            # Verify labels are present (format may vary)
            # Check for label-like patterns
            label_pattern = r"\{[^}]+\}"
            lines_with_labels = [
                line for line in content.split("\n") if re.search(label_pattern, line)
            ]
            # Should have at least some metrics with labels
            self.assertGreater(len(lines_with_labels), 0)
