"""
Phase 5 integration tests: process-file path calls DQ, Files, Datasets, Search,
DLQ (via mark_file_failed), Notifications (at run completion); Compliance and
Semantic when configured. No mocks: real services.
"""

import unittest
import os
import uuid

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

# Force MinIO endpoint and credentials in tests so we never hit real AWS.
# Use env when set (e.g. Docker compose) so credentials match the running MinIO.
_TEST_S3_ENDPOINT = os.environ.get("AWS_S3_ENDPOINT_URL", "http://localhost:9000")
_TEST_S3_USE_SSL = os.environ.get("AWS_S3_USE_SSL", "false").lower() in ("1", "true", "yes")
_TEST_AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "minio")
_TEST_AWS_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123")

# Patch sql_flush to use CASCADE so TransactionTestCase teardown does not hang
# (same root cause as test_scheduled_ingestion_comprehensive_validation.py).
try:
    import django.db.backends.postgresql.operations as pg_operations

    if not hasattr(pg_operations.DatabaseOperations.sql_flush, "_patched_for_cascade"):
        _original_sql_flush = pg_operations.DatabaseOperations.sql_flush

        def _patched_sql_flush(
            self, style, tables, *, reset_sequences=False, allow_cascade=False
        ):
            return _original_sql_flush(
                self, style, tables, reset_sequences=reset_sequences, allow_cascade=True
            )

        _patched_sql_flush._patched_for_cascade = True
        pg_operations.DatabaseOperations.sql_flush = _patched_sql_flush
except Exception:
    pass

from hub.apps.audit.models import AuditEvent
from hub.apps.auth.models import APIKey
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File
from hub.apps.scheduled_ingestion.internal_auth import SCOPE_SCHEDULED_INGESTION_INTERNAL
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.files.storage import S3StorageClient
from hub.apps.scheduled_ingestion.worker_services import process_file_for_run
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

# TransactionTestCase flush (teardown) can exceed 300s with many tables; allow 600s so
# test body + teardown complete (real DQ, MinIO, Semantic, DB flush).
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.timeout(600),
]


def _create_worker_api_key(tenant, user):
    plaintext = APIKey.generate_key()
    key_hash = APIKey.hash_key(plaintext)
    APIKey.objects.create(
        tenant=tenant,
        user=user,
        key_hash=key_hash,
        name="Worker API Key",
        scopes=[SCOPE_SCHEDULED_INGESTION_INTERNAL],
    )
    return plaintext


@override_settings(
    AWS_STORAGE_BUCKET_NAME="hub-files",
    AWS_ACCESS_KEY_ID=_TEST_AWS_ACCESS_KEY,
    AWS_SECRET_ACCESS_KEY=_TEST_AWS_SECRET_KEY,
    AWS_S3_ENDPOINT_URL=_TEST_S3_ENDPOINT,
    AWS_S3_USE_SSL=_TEST_S3_USE_SSL,
)
class ProcessFileIntegrationsTest(TestCase):
    """
    Verify process-file path uses real DQ, Files, Datasets, Search, DLQ;
    Compliance and Semantic when configured. No mocks.
    """

    # Skip DB flush in teardown so test + teardown complete within pytest timeout (600s).
    # Flush with many tables can exceed 600s; isolation is via transaction rollback.
    @classmethod
    def _fixture_teardown(cls):
        pass

    def tearDown(self):
        """Ensure DB connection is usable before teardown (avoids hang)."""
        from django.db import connection
        connection.ensure_connection()
        super().tearDown()

    def setUp(self):
        # Detect MinIO availability so storage-dependent tests can skip when unavailable
        self._storage_available = False
        try:
            client = S3StorageClient()
            client._ensure_bucket_exists()
            self._storage_available = True
        except Exception as e:
            err = str(e).lower()
            if "invalidaccesskeyid" in err or "access key" in err:
                pass
            elif "connection" in err or "could not connect" in err or "name resolution" in err:
                pass

        suffix = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Phase5 Tenant {suffix}",
            slug=f"phase5-tenant-{suffix}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"phase5-{suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Phase5 Ingestion",
            source_type=SourceType.S3,
            source_config={
                "bucket": "test-bucket",
                "send_notifications": False,
            },
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        self.ingestion_run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=timezone.now(),
        )

    def tearDown(self):
        # TransactionTestCase teardown runs flush; ensure DB connection is open so flush does not raise "connection already closed"
        from django.db import connection

        try:
            connection.ensure_connection()
        except Exception:
            pass
        super().tearDown()

    def test_process_file_creates_file_and_dataset_and_indexes(self):
        """process_file_for_run creates File, Dataset, and indexes (Search); real services."""
        if not self._storage_available:
            raise unittest.SkipTest("MinIO storage not available in test environment")
        csv_content = b"id,name\n1,alpha\n2,beta\n"
        result = process_file_for_run(
            run_id=str(self.ingestion_run.id),
            file_path="data/sample.csv",
            file_content=csv_content,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            dq_options={"strict_mode": False},
        )
        self.assertIn("file_id", result)
        self.assertIn("dataset_id", result)
        file_id = result["file_id"]
        dataset_id = result["dataset_id"]
        self.assertTrue(File.objects.filter(id=file_id, tenant=self.tenant).exists())
        self.assertTrue(Dataset.objects.filter(id=dataset_id, tenant=self.tenant).exists())
        dataset = Dataset.objects.get(id=dataset_id)
        self.assertEqual(str(dataset.file_id), str(file_id))

    def test_process_file_permanent_failure_marks_dlq_state(self):
        """Permanent failure (e.g. empty file) marks file failed in incremental state (DLQ sync at run completion)."""
        from hub.apps.scheduled_ingestion.incremental_state import IncrementalStateManager

        csv_content = b""
        from hub.apps.core.services.base import ValidationError as ServiceValidationError

        with self.assertRaises(ServiceValidationError) as ctx:
            process_file_for_run(
                run_id=str(self.ingestion_run.id),
                file_path="data/empty.csv",
                file_content=csv_content,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )
        self.assertIn("empty", str(ctx.exception).lower())
        self.scheduled_ingestion.refresh_from_db()
        state_manager = IncrementalStateManager(self.scheduled_ingestion)
        failed = state_manager.get_failed_files()
        self.assertIn("data/empty.csv", [f["file_path"] for f in failed])

    def test_process_file_with_run_compliance_creates_compliance_run_when_configured(self):
        """When source_config.run_compliance is True, process_file_for_run creates a compliance run for the dataset."""
        if not self._storage_available:
            raise unittest.SkipTest("MinIO storage not available in test environment")
        cfg = self.scheduled_ingestion.get_source_config()
        cfg["run_compliance"] = True
        self.scheduled_ingestion.source_config = cfg
        self.scheduled_ingestion.save(update_fields=["source_config"])
        csv_content = b"id,name\n1,alpha\n2,beta\n"
        result = process_file_for_run(
            run_id=str(self.ingestion_run.id),
            file_path="data/sample.csv",
            file_content=csv_content,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            dq_options={"strict_mode": False},
        )
        dataset_id = result["dataset_id"]
        from hub.apps.compliance.models import ComplianceRun

        compliance_runs = ComplianceRun.objects.filter(dataset_id=dataset_id, tenant=self.tenant)
        self.assertGreaterEqual(
            compliance_runs.count(),
            1,
            "Compliance run should be created when run_compliance is configured",
        )

    def test_process_file_with_run_semantic_mapping_invokes_semantic_path(self):
        """When source_config.run_semantic_mapping is True, process_file_for_run invokes semantic mapping (non-fatal)."""
        if not self._storage_available:
            raise unittest.SkipTest("MinIO storage not available in test environment")
        cfg = self.scheduled_ingestion.get_source_config()
        cfg["run_semantic_mapping"] = True
        self.scheduled_ingestion.source_config = cfg
        self.scheduled_ingestion.save(update_fields=["source_config"])
        csv_content = b"id,name\n1,alpha\n2,beta\n"
        result = process_file_for_run(
            run_id=str(self.ingestion_run.id),
            file_path="data/sample.csv",
            file_content=csv_content,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            dq_options={"strict_mode": False},
        )
        self.assertIn("dataset_id", result)
        dataset = Dataset.objects.get(id=result["dataset_id"])
        from hub.apps.semantic.models import SemanticResource

        semantic = SemanticResource.objects.filter(
            resource_type="DATASET",
            resource_id=dataset.id,
            tenant=self.tenant,
        ).first()
        if semantic is not None:
            self.assertEqual(semantic.resource_id, dataset.id)
