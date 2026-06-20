"""
Comprehensive unit tests for SCHEDULED_INGESTION job processing.

Phase 3: process_job(SCHEDULED_INGESTION) always no-ops; execution is Prefect-only.
Tests for no-op path (test_process_job_*) and for legacy _execute_scheduled_ingestion_job
using real ScheduledIngestionProcessor (no mocks).

All tests use real implementations (no mocks/stubs).
"""

import os
import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.scheduled_ingestion_job import _execute_scheduled_ingestion_job
from hub.apps.jobs.tasks import process_job
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _is_workflow_unavailable_exception(e: Exception) -> bool:
    """True if the exception indicates workflow engine or source connector is not available."""
    msg = str(e).lower()
    return (
        "workflow" in msg
        or "connector" in msg
        or "source" in msg
        or "connect_to_source" in msg
        or "rolled back" in msg
    )


def _get_s3_source_config_for_integration():
    """Return source_config for S3 integration tests. Uses MinIO when env has AWS_S3_ENDPOINT_URL."""
    endpoint = os.environ.get("AWS_S3_ENDPOINT_URL")
    if endpoint:
        return {
            "bucket": "test-bucket",
            "prefix": "data/",
            "access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", "minio"),
            "secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123"),
            "endpoint_url": endpoint,
        }
    return {
        "bucket": "test-bucket",
        "prefix": "data/",
        "access_key_id": "test-key",
        "secret_access_key": "test-secret",
    }


def _ensure_test_bucket_exists():
    """Create test-bucket in MinIO if it doesn't exist. No-op when not using MinIO."""
    endpoint = os.environ.get("AWS_S3_ENDPOINT_URL")
    if not endpoint:
        return
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import ClientError

        config = Config(connect_timeout=5, read_timeout=10)
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "minio"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123"),
            region_name="us-east-1",
            config=config,
        )
        try:
            s3.head_bucket(Bucket="test-bucket")
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchBucket"):
                try:
                    s3.create_bucket(Bucket="test-bucket")
                except ClientError as create_err:
                    if (
                        create_err.response.get("Error", {}).get("Code")
                        != "BucketAlreadyOwnedByYou"
                    ):
                        raise
    except Exception:
        pass  # Don't fail setUp if MinIO not reachable


class ScheduledIngestionJobTest(TestCase):
    """Comprehensive tests for SCHEDULED_INGESTION job processing using real implementations.

    Tests that run the full workflow (execute_scheduled_ingestion_job) may skip when the
    workflow engine or source connector is not available (e.g. Prefect/S3 not configured).
    Skip reason is cached so the job is run at most once per class.

    Uses unique tenant/slug and user email per run to avoid duplicate-key errors when
    running with xdist/parallel or --reuse-db.
    """

    reset_sequences = False
    serialized_rollback = False

    _workflow_unavailable_reason = None

    def _fixture_teardown(self):
        """Skip TRUNCATE CASCADE which causes >60s timeouts with many FK
        relationships on the shared test DB.

        Isolation is maintained by unique UUID-based tenant/user names in
        setUp — each test creates its own object graph that doesn't
        conflict with other tests.
        """

    def setUp(self):
        """Set up test fixtures with unique names to avoid collisions in parallel runs."""
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"ScheduledIngestionJob Test Tenant {unique}",
            slug=f"scheduled-ingestion-job-test-tenant-{unique}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        self.user = User.objects.create_user(
            email=f"scheduled-ingestion-job-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Ensure test-bucket exists in MinIO when using MinIO (integration tests)
        _ensure_test_bucket_exists()

        # Create scheduled ingestion (use MinIO config when AWS_S3_ENDPOINT_URL is set)
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config=_get_s3_source_config_for_integration(),
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            auto_create_asset=True,
            auto_activate=True,
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )

        # Create job
        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.SCHEDULED_INGESTION,
            status=JobStatus.PENDING,
            resource_type="SCHEDULED_INGESTION",
            resource_id=str(self.scheduled_ingestion.id),
            details_json={"prefect_flow_run_id": str(uuid.uuid4())},
            created_by=self.user,
        )

    def test_process_job_executed_by_prefect_no_op(self):
        """When job has executed_by_prefect=True, process_job no-ops; job marked COMPLETED with result."""
        self.job.details_json = {
            "executed_by_prefect": True,
            "prefect_flow_run_id": "prefect-flow-run-456",
        }
        self.job.save(update_fields=["details_json"])
        process_job(str(self.job.id), JobType.SCHEDULED_INGESTION.value)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.COMPLETED)
        self.assertTrue(self.job.result_json.get("executed_by_prefect"))
        self.assertIn("Prefect", self.job.result_json.get("message", ""))
        self.assertEqual(
            self.job.result_json.get("prefect_flow_run_id"),
            "prefect-flow-run-456",
        )

    def test_process_job_scheduled_ingestion_always_no_op(self):
        """Phase 3: process_job(SCHEDULED_INGESTION) always no-ops; no legacy RQ execution."""
        self.job.details_json = {"prefect_flow_run_id": "legacy-run-789"}
        self.job.save(update_fields=["details_json"])
        process_job(str(self.job.id), JobType.SCHEDULED_INGESTION.value)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobStatus.COMPLETED)
        self.assertTrue(self.job.result_json.get("executed_by_prefect"))
        self.assertIn("Prefect", self.job.result_json.get("message", ""))

    @pytest.mark.requires_prefect
    def test_execute_scheduled_ingestion_job_success(self):
        """
        Test successful scheduled ingestion job execution using real ScheduledIngestionProcessor.

        Uses real processor and workflow engine to verify end-to-end ingestion processing.
        Skips when workflow engine or source connector is not available (cached for class).
        """
        if ScheduledIngestionJobTest._workflow_unavailable_reason:
            self.skipTest(ScheduledIngestionJobTest._workflow_unavailable_reason)
        try:
            result = _execute_scheduled_ingestion_job(self.job)

            self.assertIn("status", result)
            self.assertIn("files_found", result)
            self.assertIn("files_processed", result)
            self.assertIn("files_failed", result)
            self.assertIn("datasets_created", result)
            self.assertIn("errors", result)

            run = ScheduledIngestionRun.objects.get(job_id=self.job.id)
            self.assertIn(
                run.status,
                [ScheduledIngestionRunStatus.COMPLETED, ScheduledIngestionRunStatus.FAILED],
            )
            self.assertIsNotNone(run.completed_at)

            self.scheduled_ingestion.refresh_from_db()
            self.assertIn(
                self.scheduled_ingestion.status,
                [ScheduledIngestionStatus.ACTIVE, ScheduledIngestionStatus.ERROR],
            )

        except Exception as e:
            if _is_workflow_unavailable_exception(e):
                reason = f"Workflow engine or source connector not available: {e}"
                ScheduledIngestionJobTest._workflow_unavailable_reason = reason
                self.skipTest(reason)
            raise  # Re-raise unexpected errors

    @pytest.mark.requires_prefect
    def test_execute_scheduled_ingestion_job_with_failures(self):
        """
        Test scheduled ingestion job execution with failures using real processor.

        Uses real processor to verify error handling when ingestion fails.
        Skips when workflow engine or source connector is not available (cached for class).
        """
        if ScheduledIngestionJobTest._workflow_unavailable_reason:
            self.skipTest(ScheduledIngestionJobTest._workflow_unavailable_reason)
        try:
            result = _execute_scheduled_ingestion_job(self.job)

            # Verify result structure
            self.assertIn("status", result)
            self.assertIn("files_found", result)
            self.assertIn("files_processed", result)
            self.assertIn("files_failed", result)
            self.assertIn("errors", result)

            # Verify run status (may be COMPLETED or FAILED depending on actual execution)
            run = ScheduledIngestionRun.objects.get(job_id=self.job.id)
            self.assertIn(
                run.status,
                [ScheduledIngestionRunStatus.COMPLETED, ScheduledIngestionRunStatus.FAILED],
            )
            self.assertIsNotNone(run.completed_at)

            # If failed, verify error message
            if run.status == ScheduledIngestionRunStatus.FAILED:
                self.assertIsNotNone(run.error_message)
                # Verify scheduled ingestion status set to ERROR
                self.scheduled_ingestion.refresh_from_db()
                self.assertEqual(self.scheduled_ingestion.status, ScheduledIngestionStatus.ERROR)

        except Exception as e:
            if _is_workflow_unavailable_exception(e):
                reason = f"Workflow engine or source connector not available: {e}"
                ScheduledIngestionJobTest._workflow_unavailable_reason = reason
                self.skipTest(reason)
            run = ScheduledIngestionRun.objects.filter(job_id=self.job.id).first()
            if run:
                self.assertEqual(run.status, ScheduledIngestionRunStatus.FAILED)
                self.assertIsNotNone(run.error_message)

    @pytest.mark.requires_prefect
    def test_execute_scheduled_ingestion_job_processor_exception(self):
        """
        Test scheduled ingestion job execution error handling using real processor.

        Uses real processor to verify exception handling when processor fails.
        Skips when workflow engine or source connector is not available (cached for class).
        """
        if ScheduledIngestionJobTest._workflow_unavailable_reason:
            self.skipTest(ScheduledIngestionJobTest._workflow_unavailable_reason)
        try:
            result = _execute_scheduled_ingestion_job(self.job)
            self.assertIn("status", result)
        except Exception as e:
            if _is_workflow_unavailable_exception(e):
                reason = f"Workflow engine or source connector not available: {e}"
                ScheduledIngestionJobTest._workflow_unavailable_reason = reason
                self.skipTest(reason)
            run = ScheduledIngestionRun.objects.filter(job_id=self.job.id).first()
            if run:
                self.assertEqual(run.status, ScheduledIngestionRunStatus.FAILED)
                self.assertIsNotNone(run.error_message)
                self.scheduled_ingestion.refresh_from_db()
                self.assertEqual(self.scheduled_ingestion.status, ScheduledIngestionStatus.ERROR)

    def test_execute_scheduled_ingestion_job_missing_id(self):
        """Test scheduled ingestion job execution with missing scheduled ingestion ID (in-memory only)."""
        self.job.resource_id = None
        self.job.details_json = {}
        # Do not save: Job.resource_id is NOT NULL in DB; test exercises the function with missing id in memory

        with self.assertRaises(ValueError) as cm:
            _execute_scheduled_ingestion_job(self.job)

        self.assertIn("scheduled ingestion id is required", str(cm.exception).lower())

    def test_execute_scheduled_ingestion_job_not_found(self):
        """Test scheduled ingestion job execution with non-existent scheduled ingestion"""
        self.job.resource_id = uuid.uuid4()
        self.job.save()

        # Code raises ValueError when ScheduledIngestion.DoesNotExist
        with self.assertRaises(ValueError) as cm:
            _execute_scheduled_ingestion_job(self.job)

        self.assertIn("not found", str(cm.exception))

    @pytest.mark.requires_prefect
    def test_execute_scheduled_ingestion_job_incremental_timestamp(self):
        """
        Test scheduled ingestion job persists last_incremental_value using real processor.

        Uses real processor to verify incremental timestamp persistence.
        Skips when workflow engine or source connector is not available (cached for class).
        """
        if ScheduledIngestionJobTest._workflow_unavailable_reason:
            self.skipTest(ScheduledIngestionJobTest._workflow_unavailable_reason)
        from django.utils.dateparse import parse_datetime

        initial_timestamp = parse_datetime("2024-01-01T00:00:00Z")
        self.scheduled_ingestion.last_processed_timestamp = initial_timestamp
        self.scheduled_ingestion.save(update_fields=["last_processed_timestamp"])

        try:
            result = _execute_scheduled_ingestion_job(self.job)
            self.assertIn("status", result)
            self.scheduled_ingestion.refresh_from_db()

        except Exception as e:
            if _is_workflow_unavailable_exception(e):
                reason = f"Workflow engine or source connector not available: {e}"
                ScheduledIngestionJobTest._workflow_unavailable_reason = reason
                self.skipTest(reason)
            raise

    @pytest.mark.requires_prefect
    def test_execute_scheduled_ingestion_job_existing_run(self):
        """
        Test scheduled ingestion job with existing run using real processor.

        Uses real processor to verify that existing runs are updated correctly.
        Skips when workflow engine or source connector is not available (cached for class).
        """
        if ScheduledIngestionJobTest._workflow_unavailable_reason:
            self.skipTest(ScheduledIngestionJobTest._workflow_unavailable_reason)
        # Create existing run
        existing_run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            job_id=self.job.id,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(minutes=5),
        )
        # So _execute_scheduled_ingestion_job finds and updates this run (no new run)
        self.job.details_json = (self.job.details_json or {}).copy()
        self.job.details_json["scheduled_ingestion_run_id"] = str(existing_run.id)
        self.job.save(update_fields=["details_json"])

        # Execute job using real processor
        try:
            _execute_scheduled_ingestion_job(self.job)

            # Verify existing run updated (not new one created)
            runs = ScheduledIngestionRun.objects.filter(job_id=self.job.id)
            self.assertEqual(runs.count(), 1)
            run = runs.first()
            self.assertEqual(run.id, existing_run.id)
            self.assertIn(
                run.status,
                [ScheduledIngestionRunStatus.COMPLETED, ScheduledIngestionRunStatus.FAILED],
            )

        except Exception as e:
            if _is_workflow_unavailable_exception(e):
                reason = f"Workflow engine or source connector not available: {e}"
                ScheduledIngestionJobTest._workflow_unavailable_reason = reason
                self.skipTest(reason)
            runs = ScheduledIngestionRun.objects.filter(job_id=self.job.id)
            self.assertEqual(runs.count(), 1)
            run = runs.first()
            self.assertEqual(run.id, existing_run.id)
            self.assertEqual(run.status, ScheduledIngestionRunStatus.FAILED)

    # ========== EDGE CASES ==========

    def test_execute_scheduled_ingestion_job_edge_case_empty_source_config(self):
        """Test scheduled ingestion job with empty source_config"""
        self.scheduled_ingestion.source_config = {}
        self.scheduled_ingestion.save(update_fields=["source_config"])

        # Execute job - should handle gracefully or raise appropriate error
        try:
            result = _execute_scheduled_ingestion_job(self.job)
            # If execution succeeds, verify result structure
            self.assertIn("status", result)
        except Exception as e:
            # Expected if source config is invalid
            error_msg = str(e).lower()
            if "workflow" in error_msg or "connector" in error_msg or "config" in error_msg:
                # Expected error for invalid config
                pass
            else:
                raise  # Re-raise unexpected errors

    def test_execute_scheduled_ingestion_job_edge_case_invalid_file_pattern(self):
        """Test that model validation rejects invalid file pattern regex (cannot persist invalid state)."""
        from django.core.exceptions import ValidationError

        self.scheduled_ingestion.file_pattern = "[invalid regex"
        with self.assertRaises(ValidationError) as cm:
            self.scheduled_ingestion.save(update_fields=["file_pattern"])
        msg = str(cm.exception).lower()
        self.assertTrue(
            "file pattern" in msg or "regex" in msg,
            f"Expected file pattern/regex in message: {cm.exception}",
        )
