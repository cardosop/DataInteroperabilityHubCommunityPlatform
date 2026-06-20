"""Comprehensive tests for worker_run_lifecycle.py — Phase 100.7"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.jobs.models import SideEffect, SideEffectStatus, SideEffectType
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.scheduled_ingestion.worker_run_lifecycle import (
    apply_run_completion_side_effects,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ApplyRunCompletionSideEffectsTest(TestCase):
    """Test apply_run_completion_side_effects for COMPLETED and FAILED runs."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE"
        )
        self.ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name=f"Ingest {uid}",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket", "region": "us-east-1"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "02:00", "timezone": "UTC"},
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
            next_run_at=timezone.now(),
        )

    def _create_run(self, status=ScheduledIngestionRunStatus.RUNNING):
        return ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.ingestion,
            status=status,
            started_at=timezone.now(),
        )

    def test_completed_run_updates_next_run_at(self):
        """Completed run recalculates parent's next_run_at to a future time."""
        run = self._create_run()
        now = timezone.now()
        apply_run_completion_side_effects(run, "COMPLETED")
        self.ingestion.refresh_from_db()
        self.assertIsNotNone(self.ingestion.next_run_at)
        # next_run_at should be in the future (recalculated from schedule)
        self.assertGreater(self.ingestion.next_run_at, now)

    def test_completed_run_resets_failure_count(self):
        """Successful completion resets consecutive_failure_count to 0."""
        self.ingestion.consecutive_failure_count = 3
        self.ingestion.save(update_fields=["consecutive_failure_count"])
        run = self._create_run()
        apply_run_completion_side_effects(run, "COMPLETED")
        self.ingestion.refresh_from_db()
        self.assertEqual(self.ingestion.consecutive_failure_count, 0)

    def test_completed_run_creates_cost_tracking_side_effect(self):
        """COMPLETED run creates COST_TRACKING side effect."""
        run = self._create_run()
        apply_run_completion_side_effects(run, "COMPLETED")
        self.assertTrue(
            SideEffect.objects.filter(
                run_object_id=run.pk, effect_type=SideEffectType.COST_TRACKING
            ).exists()
        )

    def test_completed_run_creates_all_side_effects(self):
        """COMPLETED run creates COST_TRACKING, DLQ_SYNC, NOTIFICATION, AUDIT_EVENT."""
        run = self._create_run()
        apply_run_completion_side_effects(run, "COMPLETED")
        types = set(
            SideEffect.objects.filter(run_object_id=run.pk).values_list("effect_type", flat=True)
        )
        self.assertIn(SideEffectType.COST_TRACKING, types)
        self.assertIn(SideEffectType.DLQ_SYNC, types)
        self.assertIn(SideEffectType.NOTIFICATION, types)
        self.assertIn(SideEffectType.AUDIT_EVENT, types)

    def test_failed_run_increments_failure_count(self):
        """Failed run increments consecutive_failure_count."""
        self.ingestion.consecutive_failure_count = 0
        self.ingestion.save(update_fields=["consecutive_failure_count"])
        run = self._create_run()
        run.error_message = "S3 connection refused"
        run.save()
        apply_run_completion_side_effects(run, "FAILED")
        self.ingestion.refresh_from_db()
        self.assertEqual(self.ingestion.consecutive_failure_count, 1)

    def test_failed_run_does_not_create_cost_tracking(self):
        """FAILED run does NOT create COST_TRACKING side effect."""
        run = self._create_run()
        apply_run_completion_side_effects(run, "FAILED")
        self.assertFalse(
            SideEffect.objects.filter(
                run_object_id=run.pk, effect_type=SideEffectType.COST_TRACKING
            ).exists()
        )

    def test_auto_pause_after_max_consecutive_failures(self):
        """After max consecutive failures, ingestion auto-pauses."""
        self.ingestion.consecutive_failure_count = 4
        self.ingestion.save(update_fields=["consecutive_failure_count"])
        run = self._create_run()
        run.error_message = "5th failure"
        run.save()
        apply_run_completion_side_effects(run, "FAILED")
        self.ingestion.refresh_from_db()
        self.assertEqual(self.ingestion.status, ScheduledIngestionStatus.PAUSED)

    def test_failure_count_resets_on_success_after_failures(self):
        """Success after failures resets consecutive_failure_count."""
        self.ingestion.consecutive_failure_count = 3
        self.ingestion.status = ScheduledIngestionStatus.ERROR
        self.ingestion.save(update_fields=["consecutive_failure_count", "status"])
        run = self._create_run()
        apply_run_completion_side_effects(run, "COMPLETED")
        self.ingestion.refresh_from_db()
        self.assertEqual(self.ingestion.consecutive_failure_count, 0)
        self.assertEqual(self.ingestion.status, ScheduledIngestionStatus.ACTIVE)

    def test_failure_below_threshold_does_not_pause(self):
        """Failure count below max threshold keeps status as ERROR, not PAUSED."""
        self.ingestion.consecutive_failure_count = 2
        self.ingestion.save(update_fields=["consecutive_failure_count"])
        run = self._create_run()
        run.error_message = "3rd failure - below threshold"
        run.save()
        apply_run_completion_side_effects(run, "FAILED")
        self.ingestion.refresh_from_db()
        self.assertEqual(self.ingestion.consecutive_failure_count, 3)
        self.assertEqual(self.ingestion.status, ScheduledIngestionStatus.ERROR)

    def test_side_effects_are_executed_immediately(self):
        """Side effects are attempted and completed immediately."""
        run = self._create_run()
        apply_run_completion_side_effects(run, "COMPLETED")
        effects = SideEffect.objects.filter(run_object_id=run.pk)
        self.assertGreater(effects.count(), 0)
        for se in effects:
            self.assertGreaterEqual(
                se.attempt_count,
                1,
                f"{se.effect_type} was not attempted",
            )
            self.assertIn(
                se.status,
                (SideEffectStatus.COMPLETED, SideEffectStatus.FAILED),
                f"{se.effect_type} should reach terminal status, got {se.status}",
            )

    def test_failed_side_effect_does_not_propagate(self):
        """A failing side effect doesn't prevent other side effects from running."""
        run = self._create_run()
        apply_run_completion_side_effects(run, "COMPLETED")
        # Even if some side effects fail (e.g. notification service down),
        # all should have been attempted
        effects = SideEffect.objects.filter(run_object_id=run.pk)
        attempted = effects.filter(attempt_count__gte=1).count()
        self.assertEqual(attempted, effects.count())
