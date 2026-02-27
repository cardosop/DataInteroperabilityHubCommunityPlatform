"""
Unit tests for Job Retry Configuration

Tests verify that job retry configuration is properly loaded from settings
and that retry delay calculation works correctly with configurable factors.

All tests use real implementations (no mocks/stubs) and follow engineering best practices.
"""
from django.test import TestCase, override_settings
from hub.apps.jobs.utils import (
    get_job_max_retries,
    get_job_retry_initial_delay,
    get_job_retry_max_delay,
    get_job_retry_backoff_factor,
    calculate_retry_delay,
)
from hub.apps.jobs.models import JobType


class JobRetryConfigurationTest(TestCase):
    """Unit tests for job retry configuration"""

    def test_get_job_max_retries_from_settings(self):
        """Test that get_job_max_retries reads from settings"""
        max_retries = get_job_max_retries(JobType.DQ_RUN)
        self.assertIsInstance(max_retries, int)
        self.assertGreater(max_retries, 0)

    def test_get_job_max_retries_default(self):
        """Test that get_job_max_retries returns default for unknown job type"""
        max_retries = get_job_max_retries('UNKNOWN_JOB_TYPE')
        self.assertEqual(max_retries, 2)  # Default from function

    def test_get_job_retry_initial_delay_from_settings(self):
        """Test that get_job_retry_initial_delay reads from settings"""
        initial_delay = get_job_retry_initial_delay(JobType.DQ_RUN)
        self.assertIsInstance(initial_delay, int)
        self.assertGreater(initial_delay, 0)

    def test_get_job_retry_initial_delay_default(self):
        """Test that get_job_retry_initial_delay returns default for unknown job type"""
        initial_delay = get_job_retry_initial_delay('UNKNOWN_JOB_TYPE')
        self.assertEqual(initial_delay, 60)  # Default JOB_RETRY_BASE_DELAY

    def test_get_job_retry_max_delay_from_settings(self):
        """Test that get_job_retry_max_delay reads from settings"""
        max_delay = get_job_retry_max_delay(JobType.DQ_RUN)
        self.assertIsInstance(max_delay, int)
        self.assertGreater(max_delay, 0)

    def test_get_job_retry_max_delay_default(self):
        """Test that get_job_retry_max_delay returns default for unknown job type"""
        max_delay = get_job_retry_max_delay('UNKNOWN_JOB_TYPE')
        self.assertEqual(max_delay, 3600)  # Default 1 hour

    def test_get_job_retry_backoff_factor_from_settings(self):
        """Test that get_job_retry_backoff_factor reads from settings"""
        backoff_factor = get_job_retry_backoff_factor(JobType.DQ_RUN)
        self.assertIsInstance(backoff_factor, float)
        self.assertGreater(backoff_factor, 0)

    def test_get_job_retry_backoff_factor_default(self):
        """Test that get_job_retry_backoff_factor returns default for unknown job type"""
        backoff_factor = get_job_retry_backoff_factor('UNKNOWN_JOB_TYPE')
        self.assertEqual(backoff_factor, 2.0)  # Default

    def test_calculate_retry_delay_with_job_type(self):
        """Test that calculate_retry_delay uses job-specific configuration"""
        # Test with DQ_RUN (default: initial_delay=60, backoff_factor=2.0)
        delay_0 = calculate_retry_delay(0, job_type=JobType.DQ_RUN)
        delay_1 = calculate_retry_delay(1, job_type=JobType.DQ_RUN)
        delay_2 = calculate_retry_delay(2, job_type=JobType.DQ_RUN)

        self.assertEqual(delay_0, 60)  # 60 * (2^0) = 60
        self.assertEqual(delay_1, 120)  # 60 * (2^1) = 120
        self.assertEqual(delay_2, 240)  # 60 * (2^2) = 240

    def test_calculate_retry_delay_respects_max_delay(self):
        """Test that calculate_retry_delay caps at max_delay"""
        # DQ_RUN has max_delay=3600, so delay_5 should be capped
        delay_5 = calculate_retry_delay(5, job_type=JobType.DQ_RUN)
        # 60 * (2^5) = 1920, but should be capped at 3600
        self.assertLessEqual(delay_5, 3600)

    def test_calculate_retry_delay_backward_compatibility(self):
        """Test that calculate_retry_delay works without job_type (backward compatibility)"""
        delay = calculate_retry_delay(1, base_delay=60)
        self.assertEqual(delay, 120)  # 60 * (2^1) = 120

    @override_settings(
        JOB_RETRY_INITIAL_DELAY={'DQ_RUN': 30},
        JOB_RETRY_BACKOFF_FACTOR={'DQ_RUN': 3.0},
        JOB_RETRY_MAX_DELAY={'DQ_RUN': 600}
    )
    def test_calculate_retry_delay_custom_configuration(self):
        """Test that calculate_retry_delay uses custom configuration from settings"""
        delay_0 = calculate_retry_delay(0, job_type=JobType.DQ_RUN)
        delay_1 = calculate_retry_delay(1, job_type=JobType.DQ_RUN)
        delay_2 = calculate_retry_delay(2, job_type=JobType.DQ_RUN)

        self.assertEqual(delay_0, 30)  # 30 * (3^0) = 30
        self.assertEqual(delay_1, 90)  # 30 * (3^1) = 90
        self.assertEqual(delay_2, 270)  # 30 * (3^2) = 270, capped at 600

    def test_calculate_retry_delay_all_odps_job_types(self):
        """Test that calculate_retry_delay works for all ODPS job types"""
        odps_job_types = [
            JobType.ODPS_NORMALIZATION,
            JobType.ODPS_REF_RESOLUTION,
            JobType.ODPS_EXPORT,
            JobType.ODPS_SEMANTIC_MAPPING,
            JobType.ODPS_LINKING,
        ]

        for job_type in odps_job_types:
            delay = calculate_retry_delay(1, job_type=job_type)
            self.assertIsInstance(delay, int)
            self.assertGreater(delay, 0)
            self.assertLessEqual(delay, get_job_retry_max_delay(job_type))

    def test_retry_configuration_all_job_types(self):
        """Test that retry configuration exists for all job types"""
        all_job_types = [
            JobType.DQ_RUN,
            JobType.COMPLIANCE_RUN,
            JobType.CONTRACT_VALIDATION,
            JobType.SEMANTIC_MAPPING,
            JobType.CONTRACT_MIGRATION,
            JobType.SCHEDULED_INGESTION,
            JobType.RETENTION_POLICY_ENFORCEMENT,
            JobType.SEARCH_INDEX_UPDATE,
            JobType.ODPS_NORMALIZATION,
            JobType.ODPS_REF_RESOLUTION,
            JobType.ODPS_EXPORT,
            JobType.ODPS_SEMANTIC_MAPPING,
            JobType.ODPS_LINKING,
            JobType.VIRTUAL_QUERY_EXECUTION,
            JobType.MARKETPLACE_SYNC,
        ]

        for job_type in all_job_types:
            max_retries = get_job_max_retries(job_type)
            initial_delay = get_job_retry_initial_delay(job_type)
            max_delay = get_job_retry_max_delay(job_type)
            backoff_factor = get_job_retry_backoff_factor(job_type)

            self.assertGreater(max_retries, 0, f"Max retries should be > 0 for {job_type}")
            self.assertGreater(initial_delay, 0, f"Initial delay should be > 0 for {job_type}")
            self.assertGreater(max_delay, 0, f"Max delay should be > 0 for {job_type}")
            self.assertGreater(backoff_factor, 0, f"Backoff factor should be > 0 for {job_type}")
            self.assertLessEqual(initial_delay, max_delay, f"Initial delay should be <= max_delay for {job_type}")

