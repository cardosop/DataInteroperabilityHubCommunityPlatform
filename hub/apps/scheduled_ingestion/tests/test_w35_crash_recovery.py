"""W3.5 (oss-release-remediation R2-P4) — crash recovery.

Evidence pins (real DB + real management command via ``call_command``;
the only patched symbol is the sanctioned dlt-entrypoint seam):

* **Detector dry-run covers both states** — PENDING runs (the worker
  died before pickup) and RUNNING runs with NULL ``started_at`` are
  detected and reported, without mutation.
* **Killed-worker run recovered** — a RUNNING run whose lease expired
  (stale heartbeat — the worker's last liveness claim predates the
  crash) is recovered to FAILED with the stuck message.
* **The lease protects a live worker** — a RUNNING run past the age
  threshold with a FRESH heartbeat is left alone.
* **Worker heartbeat** — the RQ worker task writes ``heartbeat_at``,
  and the internal PATCH accepts it (the Prefect flow's liveness seam).
"""

import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.models import APIKey
from hub.apps.scheduled_ingestion.internal_auth import SCOPE_SCHEDULED_INGESTION_INTERNAL
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.timeout(120),
]

_INGESTION_ENTRYPOINT = "hub.data_movement.ingestion_execution.execute_dlt_ingestion"


def _age(delta: timedelta):
    return timezone.now() - delta


def _backdate(run, *, created_delta, started_delta=None, heartbeat_delta=None):
    fields = {"created_at": _age(created_delta), "updated_at": _age(created_delta)}
    if started_delta is not None:
        fields["started_at"] = _age(started_delta)
    if heartbeat_delta is not None:
        fields["heartbeat_at"] = _age(heartbeat_delta)
    type(run).objects.filter(pk=run.pk).update(**fields)


class StuckRunDetectorTest(TestCase):
    """The detector covers PENDING + NULL started_at and honors the
    heartbeat lease (killed worker recovered; live worker protected)."""

    def setUp(self):
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W35 Ingest Tenant {unique}",
            slug=f"w35-ingest-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w35-ingest-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name=f"W35 Ingestion {unique}",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )

    def _mk_run(self, status_val):
        return ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=status_val,
            started_at=timezone.now(),
        )

    def _run_command(self, dry_run):
        out = StringIO()
        call_command("detect_and_remediate_stuck_runs", stdout=out, dry_run=dry_run)
        return out.getvalue()

    def test_dry_run_covers_pending_and_null_started_at(self):
        """The evidence pin: a PENDING run (never picked up) and a RUNNING
        run with NULL started_at are BOTH detected, and dry-run mutates
        neither."""
        pending = self._mk_run(ScheduledIngestionRunStatus.PENDING)
        _backdate(pending, created_delta=timedelta(hours=3))
        running_null_started = self._mk_run(ScheduledIngestionRunStatus.RUNNING)
        _backdate(
            running_null_started,
            created_delta=timedelta(hours=3),
            started_delta=None,
            heartbeat_delta=timedelta(hours=3),
        )
        running_null_started.started_at = None
        running_null_started.save(update_fields=["started_at"])

        output = self._run_command(dry_run=True)

        assert "stuck run(s)" in output
        assert str(pending.id) in output, "the PENDING run must be detected"
        assert str(running_null_started.id) in output, (
            "the NULL-started_at RUNNING run must be detected"
        )
        assert "[DRY RUN]" in output
        pending.refresh_from_db()
        running_null_started.refresh_from_db()
        assert pending.status == ScheduledIngestionRunStatus.PENDING
        assert running_null_started.status == ScheduledIngestionRunStatus.RUNNING

    def test_killed_worker_run_recovered(self):
        """A RUNNING run whose lease expired (stale heartbeat, no Prefect
        flow) is recovered to FAILED with the stuck message."""
        run = self._mk_run(ScheduledIngestionRunStatus.RUNNING)
        _backdate(
            run,
            created_delta=timedelta(hours=3),
            started_delta=timedelta(hours=3),
            heartbeat_delta=timedelta(hours=3),
        )

        output = self._run_command(dry_run=False)

        assert "Marked hub run as FAILED" in output
        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.FAILED
        assert run.completed_at is not None
        assert "Prefect flow run not found" in run.error_message

    def test_fresh_heartbeat_protects_a_live_worker(self):
        """The lease contract: a RUNNING run past the age threshold with a
        FRESH heartbeat is a live worker — never recovered."""
        live = self._mk_run(ScheduledIngestionRunStatus.RUNNING)
        _backdate(
            live,
            created_delta=timedelta(hours=3),
            started_delta=timedelta(hours=3),
            heartbeat_delta=timedelta(seconds=10),
        )

        output = self._run_command(dry_run=False)

        live.refresh_from_db()
        assert live.status == ScheduledIngestionRunStatus.RUNNING, (
            "a fresh heartbeat means the worker is alive — the detector must not recover the run"
        )
        assert str(live.id) not in output or "No stuck runs found" in output

    def test_pending_never_picked_up_recovered(self):
        """A PENDING run past the threshold (the worker died before
        pickup) is recovered to FAILED."""
        run = self._mk_run(ScheduledIngestionRunStatus.PENDING)
        _backdate(run, created_delta=timedelta(hours=3))

        output = self._run_command(dry_run=False)

        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.FAILED
        assert run.completed_at is not None
        assert "stuck" in (run.error_message or "").lower()
        assert "PENDING" in output


class WorkerHeartbeatTest(TestCase):
    """The worker's liveness seams: the RQ task writes heartbeat_at and
    the internal PATCH accepts it."""

    def setUp(self):
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W35 HB Tenant {unique}",
            slug=f"w35-hb-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w35-hb-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name=f"W35 HB Ingestion {unique}",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        plaintext = APIKey.generate_key()
        APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=APIKey.hash_key(plaintext),
            name=f"worker-key-{uuid.uuid4().hex[:8]}",
            scopes=[SCOPE_SCHEDULED_INGESTION_INTERNAL],
        )
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {plaintext}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def test_rq_task_writes_heartbeat(self):
        """The RQ worker task claims the run with a heartbeat."""
        from unittest import mock

        from hub.apps.scheduled_ingestion.tasks import execute_scheduled_ingestion_run

        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.PENDING,
            started_at=timezone.now(),
        )
        outcome = {
            "files_found": 1,
            "files_processed": 1,
            "files_failed": 0,
            "datasets_created": 1,
        }
        with mock.patch(_INGESTION_ENTRYPOINT, return_value=outcome):
            execute_scheduled_ingestion_run(str(run.id), str(self.tenant.id))

        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.COMPLETED
        assert run.heartbeat_at is not None, "the worker must leave a liveness claim on the run"

    def test_internal_patch_accepts_heartbeat(self):
        """The internal PATCH carries the worker's heartbeat (the Prefect
        flow's liveness seam)."""
        resp = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        run_id = resp.data["id"]

        heartbeat = timezone.now()
        patch_resp = self.client.patch(
            f"/api/v1/scheduled-ingestions/internal/runs/{run_id}/",
            {"heartbeat_at": heartbeat.isoformat()},
            format="json",
        )
        assert patch_resp.status_code == status.HTTP_200_OK
        run = ScheduledIngestionRun.objects.get(id=run_id)
        assert run.heartbeat_at is not None, "the PATCH must persist the heartbeat"
