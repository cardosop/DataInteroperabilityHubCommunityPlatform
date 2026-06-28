"""
Unit tests for Job Retry Metrics

Tests verify that job retry metrics are properly defined and can be used
to track retry delays and retry failures.

All tests use real implementations (no mocks/stubs) and follow engineering best practices.
"""

from django.test import TestCase

from hub.apps.observability.otel_metrics import (
    job_retry_count,
    job_retry_delay_seconds,
    job_retry_failures_total,
)


class JobRetryMetricsTest(TestCase):
    """Unit tests for job retry metrics"""

    def test_job_retry_count_metric_exists(self):
        """Test that job_retry_count metric exists"""
        self.assertIsNotNone(job_retry_count)

    def test_job_retry_count_labels(self):
        """job_retry_count Histogram accepts labels and observe()."""
        job_retry_count.labels(
            job_type="ODPS_NORMALIZATION", queue_name="job_default"
        ).observe(2.0)

    def test_job_retry_delay_seconds_metric_exists(self):
        """Test that job_retry_delay_seconds metric exists"""
        self.assertIsNotNone(job_retry_delay_seconds)

    def test_job_retry_delay_seconds_labels(self):
        """job_retry_delay_seconds Histogram accepts labels and observe()."""
        job_retry_delay_seconds.labels(job_type="ODPS_NORMALIZATION").observe(120.0)

    def test_job_retry_failures_total_metric_exists(self):
        """Test that job_retry_failures_total metric exists"""
        self.assertIsNotNone(job_retry_failures_total)

    def test_job_retry_failures_total_labels(self):
        """job_retry_failures_total Counter accepts labels and increments."""
        labeled = job_retry_failures_total.labels(
            job_type="ODPS_NORMALIZATION", error_type="TIMEOUT"
        )
        before = labeled._value.get()
        labeled.inc()
        self.assertEqual(labeled._value.get() - before, 1)

    def test_all_odps_job_types_supported(self):
        """All ODPS job types accept labels without raising."""
        odps_job_types = [
            "ODPS_NORMALIZATION",
            "ODPS_REF_RESOLUTION",
            "ODPS_EXPORT",
            "ODPS_SEMANTIC_MAPPING",
            "ODPS_LINKING",
        ]

        for job_type in odps_job_types:
            job_retry_count.labels(job_type=job_type, queue_name="job_default").observe(1.0)
            job_retry_delay_seconds.labels(job_type=job_type).observe(60.0)
            job_retry_failures_total.labels(job_type=job_type, error_type="TIMEOUT").inc()
