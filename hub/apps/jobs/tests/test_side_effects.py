"""
Phase 76.5 — Side-Effect Outbox Pattern Tests

Tests:
  1. test_side_effects_created_on_run_completion
  2. test_failed_side_effect_retried_by_command
  3. test_side_effect_max_attempts_respected
"""

import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.jobs.models import SideEffect, SideEffectStatus, SideEffectType


def _ensure_tenant():
    from hub.apps.tenants.models import Tenant

    tenant, _ = Tenant.objects.get_or_create(
        name="side-effect-test",
        defaults={"slug": "side-effect-test"},
    )
    return tenant


def _create_ingestion_and_run(tenant, *, run_status="RUNNING"):
    """Create a ScheduledIngestion + ScheduledIngestionRun using raw SQL to avoid model-level side effects."""
    from django.db import connection

    si_id = uuid.uuid4()
    run_id = uuid.uuid4()
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
                str(si_id),
                str(tenant.id),
                f"test-{uuid.uuid4().hex[:8]}",
                "HTTP",
                '{"url":"https://example.com/data.csv","send_notifications":false}',
                "DAILY",
                '{"cron":"0 0 * * *","timezone":"UTC"}',
                "ACTIVE",
                0,
                now,
                now,
                False,
                False,
                "default",
                "PENDING",
            ],
        )
        c.execute(
            """INSERT INTO scheduled_ingestion_runs
               (id, scheduled_ingestion_id, status, started_at,
                files_found, files_processed, files_failed, datasets_created,
                dlq_sync_status, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            [
                str(run_id),
                str(si_id),
                run_status,
                now,
                0,
                0,
                0,
                0,
                "PENDING",
                now,
                now,
            ],
        )

    from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun

    return ScheduledIngestionRun.objects.select_related("scheduled_ingestion").get(pk=run_id)


@pytest.mark.django_db(transaction=True)
class SideEffectOnRunCompletionTest(TestCase):
    """76.5 — test_side_effects_created_on_run_completion"""

    def test_side_effects_created_on_run_completion(self):
        """Trigger run completion → assert SideEffect records created for each effect type."""
        tenant = _ensure_tenant()
        run = _create_ingestion_and_run(tenant, run_status="RUNNING")

        from hub.apps.scheduled_ingestion.worker_run_lifecycle import (
            apply_run_completion_side_effects,
        )

        apply_run_completion_side_effects(run, "COMPLETED")

        run_ct = ContentType.objects.get_for_model(run)
        side_effects = SideEffect.objects.filter(
            run_content_type=run_ct,
            run_object_id=run.pk,
        )

        # COMPLETED triggers 4 effects: COST_TRACKING, DLQ_SYNC, NOTIFICATION, AUDIT_EVENT
        self.assertEqual(side_effects.count(), 4)

        created_types = set(side_effects.values_list("effect_type", flat=True))
        expected_types = {
            SideEffectType.COST_TRACKING,
            SideEffectType.DLQ_SYNC,
            SideEffectType.NOTIFICATION,
            SideEffectType.AUDIT_EVENT,
        }
        self.assertEqual(created_types, expected_types)

        # All should have attempt_count >= 1 (processed immediately)
        for se in side_effects:
            self.assertGreaterEqual(se.attempt_count, 1)

    def test_failed_status_creates_three_side_effects(self):
        """FAILED status should NOT create COST_TRACKING (only 3 effects)."""
        tenant = _ensure_tenant()
        run = _create_ingestion_and_run(tenant, run_status="RUNNING")

        from hub.apps.scheduled_ingestion.worker_run_lifecycle import (
            apply_run_completion_side_effects,
        )

        apply_run_completion_side_effects(run, "FAILED")

        run_ct = ContentType.objects.get_for_model(run)
        side_effects = SideEffect.objects.filter(
            run_content_type=run_ct,
            run_object_id=run.pk,
        )

        self.assertEqual(side_effects.count(), 3)
        created_types = set(side_effects.values_list("effect_type", flat=True))
        self.assertNotIn(SideEffectType.COST_TRACKING, created_types)


@pytest.mark.django_db(transaction=True)
class SideEffectRetryCommandTest(TestCase):
    """76.5 — test_failed_side_effect_retried_by_command"""

    def test_failed_side_effect_retried_by_command(self):
        """Seed a FAILED SideEffect → run retry command → assert re-attempted."""
        tenant = _ensure_tenant()
        run = _create_ingestion_and_run(tenant, run_status="COMPLETED")

        run_ct = ContentType.objects.get_for_model(run)

        # Seed a FAILED AUDIT_EVENT side effect with updated_at 31 min ago
        se = SideEffect.objects.create(
            run_content_type=run_ct,
            run_object_id=run.pk,
            effect_type=SideEffectType.AUDIT_EVENT,
            status=SideEffectStatus.FAILED,
            error_message="transient failure",
            attempt_count=1,
            context_json={
                "run_id": str(run.pk),
                "scheduled_ingestion_id": str(run.scheduled_ingestion_id),
                "new_status": "COMPLETED",
            },
        )
        # Backdate updated_at so the retry window is met
        SideEffect.objects.filter(pk=se.pk).update(
            updated_at=timezone.now() - timedelta(minutes=31),
        )

        out = StringIO()
        call_command("retry_failed_side_effects", stdout=out)

        se.refresh_from_db()
        # Should have been re-attempted (attempt_count incremented)
        self.assertGreaterEqual(se.attempt_count, 2)
        # AUDIT_EVENT against a real run should succeed
        self.assertEqual(se.status, SideEffectStatus.COMPLETED)


@pytest.mark.django_db(transaction=True)
class SideEffectMaxAttemptsTest(TestCase):
    """76.5 — test_side_effect_max_attempts_respected"""

    def test_side_effect_max_attempts_respected(self):
        """Seed with attempt_count=3 → run command → assert skipped (not retried)."""
        tenant = _ensure_tenant()
        run = _create_ingestion_and_run(tenant, run_status="COMPLETED")

        run_ct = ContentType.objects.get_for_model(run)

        se = SideEffect.objects.create(
            run_content_type=run_ct,
            run_object_id=run.pk,
            effect_type=SideEffectType.DLQ_SYNC,
            status=SideEffectStatus.FAILED,
            error_message="permanent failure",
            attempt_count=3,
            context_json={
                "run_id": str(run.pk),
                "scheduled_ingestion_id": str(run.scheduled_ingestion_id),
                "new_status": "COMPLETED",
            },
        )
        # Backdate updated_at
        SideEffect.objects.filter(pk=se.pk).update(
            updated_at=timezone.now() - timedelta(minutes=31),
        )

        out = StringIO()
        call_command("retry_failed_side_effects", stdout=out)

        se.refresh_from_db()
        # Should NOT have been retried — attempt_count unchanged
        self.assertEqual(se.attempt_count, 3)
        self.assertEqual(se.status, SideEffectStatus.FAILED)
