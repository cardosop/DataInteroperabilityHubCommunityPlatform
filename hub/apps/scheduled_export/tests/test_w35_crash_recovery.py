"""W3.5 (oss-release-remediation R2-P4) — crash recovery (export side).

Evidence pins (real DB + real management command via ``call_command``):

* **Detector dry-run covers NULL ``started_at``** — a RUNNING export run
  with NULL ``started_at`` is detected and reported, without mutation.
* **Killed-worker run recovered** — a RUNNING run whose lease expired
  (stale heartbeat) is recovered to FAILED.
* **The lease protects a live worker** — a RUNNING run past the age
  threshold with a FRESH heartbeat is left alone.
* **Worker heartbeat** — the internal PATCH accepts ``heartbeat_at``
  (the export flow's liveness seam).
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
from hub.apps.scheduled_export.internal_auth import SCOPE_SCHEDULED_EXPORT_INTERNAL
from hub.apps.scheduled_export.models import (
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.timeout(120),
]


def _age(delta: timedelta):
    return timezone.now() - delta


def _backdate(run, *, created_delta, started_delta=None, heartbeat_delta=None):
    fields = {"created_at": _age(created_delta), "updated_at": _age(created_delta)}
    if started_delta is not None:
        fields["started_at"] = _age(started_delta)
    if heartbeat_delta is not None:
        fields["heartbeat_at"] = _age(heartbeat_delta)
    type(run).objects.filter(pk=run.pk).update(**fields)


class StuckExportRunDetectorTest(TestCase):
    """The export detector honors the heartbeat lease and covers
    NULL started_at."""

    def setUp(self):
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W35 Export Tenant {unique}",
            slug=f"w35-export-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w35-export-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name=f"W35 Export {unique}",
            schedule_config={"cron": "0 3 * * *", "timezone": "UTC"},
            destination_type="S3",
            destination_config={"bucket": "dest-bucket"},
            source_scope={"dataset_ids": [str(uuid.uuid4())]},
        )
        plaintext = APIKey.generate_key()
        APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=APIKey.hash_key(plaintext),
            name=f"worker-key-{uuid.uuid4().hex[:8]}",
            scopes=[SCOPE_SCHEDULED_EXPORT_INTERNAL],
        )
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {plaintext}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _mk_run(self):
        return ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.RUNNING,
            started_at=timezone.now(),
        )

    def _run_command(self, dry_run):
        out = StringIO()
        call_command("detect_and_remediate_stuck_export_runs", stdout=out, dry_run=dry_run)
        return out.getvalue()

    def test_dry_run_covers_null_started_at(self):
        """A RUNNING run with NULL started_at (past the age threshold) is
        detected; dry-run mutates nothing."""
        run = self._mk_run()
        _backdate(
            run,
            created_delta=timedelta(hours=3),
            started_delta=None,
            heartbeat_delta=timedelta(hours=3),
        )
        run.started_at = None
        run.save(update_fields=["started_at"])

        output = self._run_command(dry_run=True)

        assert "stuck run(s)" in output
        assert str(run.id) in output, "the NULL-started_at run must be detected"
        assert "[DRY RUN]" in output
        run.refresh_from_db()
        assert run.status == ScheduledExportRunStatus.RUNNING

    def test_killed_worker_run_recovered(self):
        """A RUNNING run whose lease expired is recovered to FAILED."""
        run = self._mk_run()
        _backdate(
            run,
            created_delta=timedelta(hours=3),
            started_delta=timedelta(hours=3),
            heartbeat_delta=timedelta(hours=3),
        )

        output = self._run_command(dry_run=False)

        assert "Marked hub run as FAILED" in output
        run.refresh_from_db()
        assert run.status == ScheduledExportRunStatus.FAILED
        assert run.completed_at is not None
        assert "stuck" in ((run.result_json or {}).get("error_message") or "").lower()

    def test_fresh_heartbeat_protects_a_live_worker(self):
        """The lease contract: past the age threshold with a FRESH
        heartbeat = live worker — never recovered."""
        live = self._mk_run()
        _backdate(
            live,
            created_delta=timedelta(hours=3),
            started_delta=timedelta(hours=3),
            heartbeat_delta=timedelta(seconds=10),
        )

        output = self._run_command(dry_run=False)

        live.refresh_from_db()
        assert live.status == ScheduledExportRunStatus.RUNNING, (
            "a fresh heartbeat means the worker is alive — the detector must not recover the run"
        )
        assert str(live.id) not in output or "No stuck runs found" in output

    def test_internal_patch_accepts_heartbeat(self):
        """The internal PATCH carries the worker's heartbeat (the export
        flow's liveness seam)."""
        resp = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        run_id = resp.data["id"]

        heartbeat = timezone.now()
        patch_resp = self.client.patch(
            f"/api/v1/scheduled-exports/internal/runs/{run_id}/",
            {"heartbeat_at": heartbeat.isoformat()},
            format="json",
        )
        assert patch_resp.status_code == status.HTTP_200_OK
        run = ScheduledExportRun.objects.get(id=run_id)
        assert run.heartbeat_at is not None, "the PATCH must persist the heartbeat"
