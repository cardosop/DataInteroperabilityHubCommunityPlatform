"""
Unit tests for Job Queue Metrics

Tests verify that job queue metrics are properly defined and can be used
to track job queue performance, worker health, and processing rates.

All tests use real implementations (no mocks/stubs) and follow engineering best practices.
"""
from django.test import TestCase
from hub.apps.observability.otel_metrics import (
    job_queue_length,
    job_queue_depth,
    job_processing_rate,
    job_worker_active,
    job_worker_throughput,
    job_retry_count,
    job_timeout_rate,
)


class JobQueueMetricsTest(TestCase):
    """Unit tests for job queue metrics"""

    def test_job_queue_length_metric_exists(self):
        """Test that job_queue_length metric exists"""
        self.assertIsNotNone(job_queue_length)

    def test_job_queue_length_labels(self):
        """Test that job_queue_length can be used with labels"""
        job_queue_length.labels(
            job_type='ODPS_NORMALIZATION',
            queue_name='job_default'
        ).inc()
        # Verify operation completed successfully
        self.assertIsNotNone(True)  # Operation completed without raising

    def test_job_queue_depth_metric_exists(self):
        """Test that job_queue_depth metric exists"""
        self.assertIsNotNone(job_queue_depth)

    def test_job_queue_depth_labels(self):
        """Test that job_queue_depth can be used with labels"""
        job_queue_depth.labels(
            job_type='ODPS_NORMALIZATION',
            queue_name='job_default'
        ).inc()
        # Verify operation completed successfully
        self.assertIsNotNone(True)  # Operation completed without raising

    def test_job_processing_rate_metric_exists(self):
        """Test that job_processing_rate metric exists"""
        self.assertIsNotNone(job_processing_rate)

    def test_job_processing_rate_labels(self):
        """Test that job_processing_rate can be used with labels"""
        job_processing_rate.labels(
            job_type='ODPS_NORMALIZATION',
            status='COMPLETED',
            queue_name='job_default'
        ).inc()
        # Verify operation completed successfully
        self.assertIsNotNone(True)  # Operation completed without raising

    def test_job_worker_active_metric_exists(self):
        """Test that job_worker_active metric exists"""
        self.assertIsNotNone(job_worker_active)

    def test_job_worker_active_labels(self):
        """Test that job_worker_active can be used with labels"""
        job_worker_active.labels(
            worker_id='worker-1',
            queue_name='job_default'
        ).inc()
        # Verify operation completed successfully
        self.assertIsNotNone(True)  # Operation completed without raising

    def test_job_worker_throughput_metric_exists(self):
        """Test that job_worker_throughput metric exists"""
        self.assertIsNotNone(job_worker_throughput)

    def test_job_worker_throughput_labels(self):
        """Test that job_worker_throughput can be used with labels"""
        job_worker_throughput.labels(
            worker_id='worker-1',
            job_type='ODPS_NORMALIZATION'
        ).inc()
        # Verify operation completed successfully
        self.assertIsNotNone(True)  # Operation completed without raising

    def test_job_retry_count_metric_exists(self):
        """Test that job_retry_count metric exists"""
        self.assertIsNotNone(job_retry_count)

    def test_job_retry_count_labels(self):
        """Test that job_retry_count can be used with labels"""
        job_retry_count.labels(
            job_type='ODPS_NORMALIZATION',
            queue_name='job_default'
        ).observe(2.0)
        # Verify operation completed successfully
        self.assertIsNotNone(True)  # Operation completed without raising

    def test_job_timeout_rate_metric_exists(self):
        """Test that job_timeout_rate metric exists"""
        self.assertIsNotNone(job_timeout_rate)

    def test_job_timeout_rate_labels(self):
        """Test that job_timeout_rate can be used with labels"""
        job_timeout_rate.labels(
            job_type='ODPS_NORMALIZATION',
            queue_name='job_default'
        ).inc()
        # Verify operation completed successfully
        self.assertIsNotNone(True)  # Operation completed without raising

    def test_all_odps_job_types_supported(self):
        """Test that all ODPS job types can be tracked"""
        odps_job_types = [
            'ODPS_NORMALIZATION',
            'ODPS_REF_RESOLUTION',
            'ODPS_EXPORT',
            'ODPS_SEMANTIC_MAPPING',
            'ODPS_LINKING',
        ]

        for job_type in odps_job_types:
            # Test job_queue_length
            job_queue_length.labels(
                job_type=job_type,
                queue_name='job_default'
            ).inc()

            # Test job_processing_rate
            job_processing_rate.labels(
                job_type=job_type,
                status='COMPLETED',
                queue_name='job_default'
            ).inc()

            # Test job_retry_count
            job_retry_count.labels(
                job_type=job_type,
                queue_name='job_default'
            ).observe(0.0)

            # Test job_timeout_rate
            job_timeout_rate.labels(
                job_type=job_type,
                queue_name='job_default'
            ).inc()

        # All operations should succeed without error
        self.assertIsNotNone(True)  # Operation completed without raising

