"""Comprehensive model tests for scheduled_ingestion — Phase 100.8"""

import uuid

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.django_db]
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from hub.apps.scheduled_ingestion.models import (
    IngestionCost,
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

User = get_user_model()


class ScheduledIngestionModelTest(TestCase):
    """Test ScheduledIngestion model validation and lifecycle."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="pass", tenant=self.tenant, status="ACTIVE"
        )

    def _create_ingestion(self, **overrides):
        defaults = dict(
            tenant=self.tenant,
            name=f"Ing {uuid.uuid4().hex[:6]}",
            source_type=SourceType.S3,
            source_config={"bucket": "b", "region": "us-east-1"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "03:00", "timezone": "UTC"},
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )
        defaults.update(overrides)
        return ScheduledIngestion.objects.create(**defaults)

    def test_create_with_valid_cron_expression(self):
        ing = self._create_ingestion(
            schedule_type=ScheduleType.CUSTOM_CRON,
            schedule_config={"cron": "0 2 * * *", "timezone": "UTC"},
        )
    def test_invalid_file_pattern_raises_validation_error(self):
        """Invalid regex in file_pattern raises ValidationError on clean."""
        ing = self._create_ingestion()
        ing.file_pattern = "[invalid"
        with self.assertRaises(ValidationError):
            ing.full_clean()

    def test_next_run_at_calculated_on_save(self):
        """next_run_at is auto-calculated when saving an ACTIVE ingestion."""
        ing = self._create_ingestion()
        self.assertIsNotNone(ing.next_run_at)

    def test_failure_tracking_fields(self):
        """consecutive_failure_count and last_error_at track failures."""
        ing = self._create_ingestion()
        ing.consecutive_failure_count = 3
        ing.last_error_at = timezone.now()
        ing.error_message = "Connection refused"
        ing.save(
            update_fields=[
                "consecutive_failure_count",
                "last_error_at",
                "error_message",
                "updated_at",
            ]
        )
        ing.refresh_from_db()
        self.assertEqual(ing.consecutive_failure_count, 3)
        self.assertIsNotNone(ing.last_error_at)
        self.assertEqual(ing.error_message, "Connection refused")

    def test_unique_name_per_tenant(self):
        """Duplicate name within same tenant raises ValidationError (model calls full_clean on save)."""
        from django.core.exceptions import ValidationError as DjangoValidationError

        name = f"Unique {uuid.uuid4().hex[:6]}"
        self._create_ingestion(name=name)
        with self.assertRaises((IntegrityError, DjangoValidationError)):
            self._create_ingestion(name=name)

    def test_source_types_all_valid(self):
        """All SourceType enum values are accepted."""
        for st in [SourceType.S3, SourceType.GCS, SourceType.HTTP, SourceType.HTTPS]:
            ing = self._create_ingestion(source_type=st)
            self.assertEqual(ing.source_type, st)


class ScheduledIngestionRunModelTest(TestCase):
    """Test ScheduledIngestionRun model."""

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
            name=f"Ing {uid}",
            source_type=SourceType.S3,
            source_config={"bucket": "b", "region": "us-east-1"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "03:00", "timezone": "UTC"},
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )

    def test_run_status_transitions(self):
        """Run can transition PENDING -> RUNNING -> COMPLETED."""
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.ingestion, status=ScheduledIngestionRunStatus.PENDING
        )
        self.assertEqual(run.status, ScheduledIngestionRunStatus.PENDING)
        run.status = ScheduledIngestionRunStatus.RUNNING
        run.started_at = timezone.now()
        run.save()
        run.refresh_from_db()
        self.assertEqual(run.status, ScheduledIngestionRunStatus.RUNNING)
        run.status = ScheduledIngestionRunStatus.COMPLETED
        run.completed_at = timezone.now()
        run.save()
        run.refresh_from_db()
        self.assertEqual(run.status, ScheduledIngestionRunStatus.COMPLETED)

    def test_run_file_tracking(self):
        """Run tracks files_found, files_processed, files_failed."""
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            files_found=10,
            files_processed=8,
            files_failed=2,
            datasets_created=3,
        )
        self.assertEqual(run.files_found, 10)
        self.assertEqual(run.files_processed, 8)
        self.assertEqual(run.files_failed, 2)
        self.assertEqual(run.datasets_created, 3)

    def test_run_duration_tracking(self):
        """Run tracks started_at and completed_at for duration calculation."""
        start = timezone.now()
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=start,
            completed_at=start + timezone.timedelta(minutes=5),
        )
        duration = (run.completed_at - run.started_at).total_seconds()
        self.assertEqual(duration, 300)

    def test_run_dlq_sync_status(self):
        """DLQ sync status tracked on run."""
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            dlq_sync_status="SYNCED",
        )
        self.assertEqual(run.dlq_sync_status, "SYNCED")


class IngestionCostModelTest(TestCase):
    """Test IngestionCost model."""

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
            name=f"Ing {uid}",
            source_type=SourceType.S3,
            source_config={"bucket": "b", "region": "us-east-1"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "03:00", "timezone": "UTC"},
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )

    def test_cost_auto_calculation(self):
        """total_cost_usd = storage + compute + network."""
        cost = IngestionCost.objects.create(
            scheduled_ingestion=self.ingestion,
            storage_cost_usd=1.50,
            compute_cost_usd=2.00,
            network_cost_usd=0.50,
            period_start=timezone.now(),
            period_end=timezone.now(),
        )
        cost.refresh_from_db()
        # total should be auto-calculated (model save logic)
        expected = 1.50 + 2.00 + 0.50
        self.assertAlmostEqual(float(cost.total_cost_usd), expected, places=2)
