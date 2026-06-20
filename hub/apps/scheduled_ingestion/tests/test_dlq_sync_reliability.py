"""
Phase 72.6 — DLQ Sync Reliability Tests

Tests that dlq_sync_status is correctly tracked on ScheduledIngestionRun
and that the recovery command works.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
)


@pytest.mark.django_db(transaction=True)
class DLQSyncStatusTest(TestCase):
    """Test dlq_sync_status tracking in worker_run_lifecycle."""

    def test_dlq_sync_status_field_exists(self):
        """ScheduledIngestionRun must have dlq_sync_status field."""
        field_names = [f.name for f in ScheduledIngestionRun._meta.get_fields()]
        self.assertIn("dlq_sync_status", field_names)

    def test_dlq_sync_status_default_is_pending(self):
        """Default dlq_sync_status should be PENDING."""
        field = ScheduledIngestionRun._meta.get_field("dlq_sync_status")
        self.assertEqual(field.default, "PENDING")

    def test_lifecycle_sets_synced_on_success(self):
        """worker_run_lifecycle sets dlq_sync_status=SYNCED after successful DLQ sync."""
        import uuid

        from hub.apps.scheduled_ingestion.worker_run_lifecycle import _execute_dlq_sync
        from hub.apps.tenants.models import Tenant
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"DLQ Sync Test {uid}",
            slug=f"dlq-sync-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(tenant)
        si = ScheduledIngestion.objects.create(
            tenant=tenant,
            name=f"dlq-si-{uid}",
            source_type="S3",
            schedule_type="DAILY",
            schedule_config={"time": "00:00"},
            source_config={"bucket": "test"},
        )
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=si,
            status=ScheduledIngestionRunStatus.COMPLETED,
            dlq_sync_status="PENDING",
        )
        _execute_dlq_sync(str(si.id), str(run.id))
        run.refresh_from_db()
        self.assertEqual(run.dlq_sync_status, "SYNCED")

    def test_lifecycle_sets_failed_on_exception(self):
        """worker_run_lifecycle sets dlq_sync_status=FAILED when DLQ sync raises."""
        import uuid
        from unittest.mock import patch as _patch

        from hub.apps.scheduled_ingestion.worker_run_lifecycle import _execute_dlq_sync
        from hub.apps.tenants.models import Tenant
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"DLQ Fail Test {uid}",
            slug=f"dlq-fail-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(tenant)
        si = ScheduledIngestion.objects.create(
            tenant=tenant,
            name=f"dlq-fail-si-{uid}",
            source_type="S3",
            schedule_type="DAILY",
            schedule_config={"time": "00:00"},
            source_config={"bucket": "test"},
        )
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=si,
            status=ScheduledIngestionRunStatus.COMPLETED,
            dlq_sync_status="PENDING",
        )
        _dlq_sync = (
            "hub.apps.scheduled_ingestion.dead_letter_queue"
            ".DeadLetterQueueManager.sync_from_ingestion_state"
        )
        with _patch(_dlq_sync, side_effect=RuntimeError("sync failed")):
            with self.assertRaises(RuntimeError):
                _execute_dlq_sync(str(si.id), str(run.id))
        run.refresh_from_db()
        self.assertEqual(run.dlq_sync_status, "FAILED")


@pytest.mark.django_db(transaction=True)
class DLQSyncRecoveryCommandTest(TestCase):
    """Test retry_failed_dlq_sync management command."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant

        self.tenant = Tenant.objects.create(
            name="Test DLQ Tenant",
            slug="test-dlq-tenant",
            status="ACTIVE",
        )

    def _create_run(self, dlq_status="FAILED", hours_ago=2):
        si = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="test-si",
            source_type="S3",
            schedule_type="DAILY",
            schedule_config={"time": "00:00", "timezone": "UTC"},
            source_config={"bucket": "test"},
        )
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=si,
            status=ScheduledIngestionRunStatus.COMPLETED,
            dlq_sync_status=dlq_status,
        )
        # Bypass auto_now
        ScheduledIngestionRun.objects.filter(id=run.id).update(
            updated_at=timezone.now() - timedelta(hours=hours_ago),
        )
        run.refresh_from_db()
        return run

    @patch(
        "hub.apps.scheduled_ingestion.dead_letter_queue.DeadLetterQueueManager.sync_from_ingestion_state"
    )
    def test_recovery_command_retries_failed(self, mock_sync):
        """FAILED runs older than 1hr should be retried."""
        run = self._create_run(dlq_status="FAILED", hours_ago=2)
        out = StringIO()
        call_command("retry_failed_dlq_sync", stdout=out)
        run.refresh_from_db()
        self.assertEqual(run.dlq_sync_status, "SYNCED")
        mock_sync.assert_called_once()

    def test_recovery_skips_recent_failures(self):
        """FAILED runs younger than 1hr should be skipped."""
        run = self._create_run(dlq_status="FAILED", hours_ago=0)
        out = StringIO()
        call_command("retry_failed_dlq_sync", stdout=out)
        run.refresh_from_db()
        self.assertEqual(run.dlq_sync_status, "FAILED")

    def test_recovery_skips_synced_runs(self):
        """SYNCED runs should not be retried."""
        run = self._create_run(dlq_status="SYNCED", hours_ago=2)
        out = StringIO()
        call_command("retry_failed_dlq_sync", stdout=out)
        run.refresh_from_db()
        self.assertEqual(run.dlq_sync_status, "SYNCED")
