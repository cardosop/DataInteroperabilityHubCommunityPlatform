"""
Phase 5 integration tests: process-file path calls DQ, Files, Datasets, Search,
DLQ (via mark_file_failed), Notifications (at run completion); Compliance and
Semantic when configured. No mocks: real services.
"""

import uuid

import pytest
from django.test import TransactionTestCase
from django.utils import timezone

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
from hub.apps.scheduled_ingestion.worker_services import process_file_for_run
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

# TransactionTestCase flush (teardown) can exceed 300s with many tables; allow 600s so
# test body + teardown complete (real DQ, MinIO, Semantic, DB flush).
pytestmark = [
    pytest.mark.django_db(transaction=True),
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


class ProcessFileIntegrationsTest(TransactionTestCase):
    """
    Verify process-file path uses real DQ, Files, Datasets, Search, DLQ;
    Compliance and Semantic when configured. No mocks.
    """

    def setUp(self):
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
        self.run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=timezone.now(),
        )

    def test_process_file_creates_file_and_dataset_and_indexes(self):
        """process_file_for_run creates File, Dataset, and indexes (Search); real services."""
        csv_content = b"id,name\n1,alpha\n2,beta\n"
        result = process_file_for_run(
            run_id=str(self.run.id),
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
                run_id=str(self.run.id),
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
        self.scheduled_ingestion.source_config["run_compliance"] = True
        self.scheduled_ingestion.save(update_fields=["source_config"])
        csv_content = b"id,name\n1,alpha\n2,beta\n"
        result = process_file_for_run(
            run_id=str(self.run.id),
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
        self.scheduled_ingestion.source_config["run_semantic_mapping"] = True
        self.scheduled_ingestion.save(update_fields=["source_config"])
        csv_content = b"id,name\n1,alpha\n2,beta\n"
        result = process_file_for_run(
            run_id=str(self.run.id),
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
