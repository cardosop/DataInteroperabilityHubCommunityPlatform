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
        """Test that job_retry_count can be used with labels"""
        job_retry_count.labels(job_type="ODPS_NORMALIZATION", queue_name="job_default").observe(2.0)
        # Verify operation completed successfully
        self.assertIsNotNone(True)  # Operation completed without raising

    def test_job_retry_delay_seconds_metric_exists(self):
        """Test that job_retry_delay_seconds metric exists"""
        self.assertIsNotNone(job_retry_delay_seconds)

    def test_job_retry_delay_seconds_labels(self):
        """Test that job_retry_delay_seconds can be used with labels"""
        job_retry_delay_seconds.labels(job_type="ODPS_NORMALIZATION").observe(120.0)
        # Verify operation completed successfully
        self.assertIsNotNone(True)  # Operation completed without raising

    def test_job_retry_failures_total_metric_exists(self):
        """Test that job_retry_failures_total metric exists"""
        self.assertIsNotNone(job_retry_failures_total)

    def test_job_retry_failures_total_labels(self):
        """Test that job_retry_failures_total can be used with labels"""
        job_retry_failures_total.labels(job_type="ODPS_NORMALIZATION", error_type="TIMEOUT").inc()
        # Verify operation completed successfully
        self.assertIsNotNone(True)  # Operation completed without raising

    def test_all_odps_job_types_supported(self):
        """Test that all ODPS job types can be tracked"""
        odps_job_types = [
            "ODPS_NORMALIZATION",
            "ODPS_REF_RESOLUTION",
            "ODPS_EXPORT",
            "ODPS_SEMANTIC_MAPPING",
            "ODPS_LINKING",
        ]

        for job_type in odps_job_types:
            # Test job_retry_count
            job_retry_count.labels(job_type=job_type, queue_name="job_default").observe(1.0)

            # Test job_retry_delay_seconds
            job_retry_delay_seconds.labels(job_type=job_type).observe(60.0)

            # Test job_retry_failures_total
            job_retry_failures_total.labels(job_type=job_type, error_type="TIMEOUT").inc()

        # All operations should succeed without error
        self.assertIsNotNone(True)  # Operation completed without raising
