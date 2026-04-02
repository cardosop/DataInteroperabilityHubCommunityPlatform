"""
Phase 71 (71.7) — Scheduled Ingestion Auto-Pause Tests

Tests consecutive failure tracking and auto-pause behavior.
"""

import uuid

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
)


@pytest.mark.django_db(transaction=True)
class ScheduledIngestionAutoPauseTest(TestCase):
    """Test auto-pause after consecutive failures."""

    def _create_schedule(self, failure_count=0):
        from hub.apps.tenants.models import Tenant
        from django.db import connection

        tenant, _ = Tenant.objects.get_or_create(
            name="auto-pause-test",
            defaults={"slug": "auto-pause-test"},
        )
        si_id = uuid.uuid4()
        now = timezone.now()
        with connection.cursor() as c:
            c.execute(
                """INSERT INTO scheduled_ingestions
                   (id, tenant_id, name, source_type, source_config,
                    schedule_type, schedule_config, status,
                    consecutive_failure_count, created_at, updated_at,
                    auto_create_asset, auto_activate,
                    prefect_work_pool_name, deployment_sync_status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [
                    str(si_id), str(tenant.id),
                    f"test-{uuid.uuid4().hex[:8]}", "HTTP",
                    '{"url":"https://example.com/data.csv"}',
                    "DAILY", '{"cron":"0 0 * * *","timezone":"UTC"}',
                    "ACTIVE", failure_count, now, now, False, False,
                    "default", "PENDING",
                ],
            )
        return ScheduledIngestion.objects.get(id=si_id)

    def _create_run(self, si, status_val, error_msg=None):
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=si,
            status=status_val,
            error_message=error_msg,
        )
        return run

    @override_settings(MAX_CONSECUTIVE_FAILURES=5)
    def test_auto_pause_after_consecutive_failures(self):
        """5th consecutive failure auto-pauses the schedule."""
        from hub.apps.scheduled_ingestion.worker_run_lifecycle import (
            apply_run_completion_side_effects,
        )

        si = self._create_schedule(failure_count=4)
        run = self._create_run(
            si, ScheduledIngestionRunStatus.FAILED, "Connection refused"
        )

        apply_run_completion_side_effects(run, "FAILED")

        si.refresh_from_db()
        self.assertEqual(si.status, ScheduledIngestionStatus.PAUSED)
        self.assertEqual(si.consecutive_failure_count, 5)
        self.assertIsNotNone(si.last_error_at)

    @override_settings(MAX_CONSECUTIVE_FAILURES=5)
    def test_success_resets_failure_count(self):
        """A COMPLETED run resets consecutive_failure_count to 0."""
        from hub.apps.scheduled_ingestion.worker_run_lifecycle import (
            apply_run_completion_side_effects,
        )

        si = self._create_schedule(failure_count=3)
        si.status = ScheduledIngestionStatus.ERROR
        si.save(update_fields=["status"])

        run = self._create_run(si, ScheduledIngestionRunStatus.COMPLETED)

        apply_run_completion_side_effects(run, "COMPLETED")

        si.refresh_from_db()
        self.assertEqual(si.consecutive_failure_count, 0)
        self.assertEqual(si.status, ScheduledIngestionStatus.ACTIVE)
        self.assertIsNone(si.last_error_at)

    @override_settings(MAX_CONSECUTIVE_FAILURES=5)
    def test_failure_below_threshold_sets_error(self):
        """Failure below threshold sets ERROR, not PAUSED."""
        from hub.apps.scheduled_ingestion.worker_run_lifecycle import (
            apply_run_completion_side_effects,
        )

        si = self._create_schedule(failure_count=2)
        run = self._create_run(
            si, ScheduledIngestionRunStatus.FAILED, "Timeout"
        )

        apply_run_completion_side_effects(run, "FAILED")

        si.refresh_from_db()
        self.assertEqual(si.status, ScheduledIngestionStatus.ERROR)
        self.assertEqual(si.consecutive_failure_count, 3)
