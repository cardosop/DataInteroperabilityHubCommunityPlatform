"""W3.2 (oss-release-remediation R2-P5) — uniform run completion.

Every entrypoint that finalizes a scheduled-ingestion run (the dlt spine,
the RQ worker task, the internal PATCH) must route completion through
``apply_run_completion_side_effects`` exactly once — the parent
``next_run_at`` recompute, the failure accounting + auto-pause, the
outbox rows, and the completion audit must fire identically on every
path. Evidence pins (real DB + real DRF; the only patched symbol is the
sanctioned dlt-entrypoint seam):

* **dlt-tenant `next_run_at` recompute** — a stale parent ``next_run_at``
  is recomputed when the spine finalizes a run.
* **Auto-pause** — MAX_CONSECUTIVE_FAILURES consecutive spine failures
  pause the parent schedule (and one failure sets ERROR + counters).
* **Exactly once** — replays and same-status PATCHes after a spine
  completion create no second side-effect wave.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.auth.models import APIKey
from hub.apps.jobs.models import SideEffect
from hub.apps.scheduled_ingestion.internal_auth import SCOPE_SCHEDULED_INGESTION_INTERNAL
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
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

RUNS_URL = "/api/v1/scheduled-ingestions/internal/runs/"

# The dlt outcome the spine records (canonical shape from the W3.1 pins).
_SUCCESS_OUTCOME = {
    "files_found": 2,
    "files_processed": 2,
    "files_failed": 0,
    "datasets_created": 1,
    "ingestion_state": {"processed_files": 2, "failed_files": 0},
}


def _create_worker_api_key(tenant, user):
    plaintext = APIKey.generate_key()
    APIKey.objects.create(
        tenant=tenant,
        user=user,
        key_hash=APIKey.hash_key(plaintext),
        name=f"worker-key-{uuid.uuid4().hex[:8]}",
        scopes=[SCOPE_SCHEDULED_INGESTION_INTERNAL],
    )
    return plaintext


class DltSpineUniformCompletionTest(TestCase):
    """The dlt spine finalizes runs through the same completion contract
    as the RQ worker task and the internal PATCH."""

    def setUp(self):
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W32 Ingest Tenant {unique}",
            slug=f"w32-ingest-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
            data_movement_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w32-ingest-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name=f"W32 Ingestion {unique}",
            source_type=SourceType.S3,
            source_config={"bucket": "src-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        worker_key = _create_worker_api_key(self.tenant, self.user)
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {worker_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _post_run(self, **payload):
        body = {"scheduled_ingestion_id": str(self.scheduled_ingestion.id), **payload}
        return self.client.post(RUNS_URL, data=body, format="json")

    def _stale_next_run_at(self):
        """A recognizably stale parent next_run_at — the completion
        contract must recompute it (the pre-fix spine left it stale)."""
        stale = timezone.now() - timedelta(days=30)
        self.scheduled_ingestion.next_run_at = stale
        self.scheduled_ingestion.save(update_fields=["next_run_at"])
        return stale

    def test_dlt_spine_completion_recomputes_next_run_at(self):
        """A dlt-spine COMPLETED run recomputes the parent next_run_at and
        fires the completion side effects (outbox rows + audit)."""
        from unittest import mock

        stale = self._stale_next_run_at()
        with mock.patch(_INGESTION_ENTRYPOINT, return_value=_SUCCESS_OUTCOME):
            resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")

        assert resp.status_code in (200, 201)
        assert resp.data.get("run_status") == "COMPLETED"
        run = ScheduledIngestionRun.objects.get(scheduled_ingestion=self.scheduled_ingestion)

        self.scheduled_ingestion.refresh_from_db()
        assert self.scheduled_ingestion.next_run_at != stale, (
            "the dlt spine must recompute next_run_at (the pre-fix spine left it stale)"
        )
        assert self.scheduled_ingestion.next_run_at > timezone.now()
        assert self.scheduled_ingestion.consecutive_failure_count == 0
        assert self.scheduled_ingestion.status == ScheduledIngestionStatus.ACTIVE

        side_effect_types = set(
            SideEffect.objects.filter(run_object_id=run.pk).values_list("effect_type", flat=True)
        )
        assert "DLQ_SYNC" in side_effect_types
        assert "NOTIFICATION" in side_effect_types
        assert "AUDIT_EVENT" in side_effect_types
        assert "COST_TRACKING" in side_effect_types, "COMPLETED runs track costs"
        assert AuditEvent.objects.filter(
            resource_type="SCHEDULED_INGESTION_RUN",
            action="RUN_COMPLETED",
            resource_id=str(run.id),
        ).exists(), "the completion audit fires on the spine path too"

    def test_dlt_spine_failure_updates_parent_failure_accounting(self):
        """A dlt-spine FAILED run increments consecutive_failure_count,
        sets ERROR + last_error_at, and propagates the run's error
        message to the parent."""
        from unittest import mock

        failure = {
            "files_found": 1,
            "files_processed": 0,
            "files_failed": 1,
            "error_message": "dlt boom",
        }
        with mock.patch(_INGESTION_ENTRYPOINT, return_value=failure):
            resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")

        assert resp.status_code in (200, 201)
        run = ScheduledIngestionRun.objects.get(scheduled_ingestion=self.scheduled_ingestion)
        assert run.status == ScheduledIngestionRunStatus.FAILED

        self.scheduled_ingestion.refresh_from_db()
        assert self.scheduled_ingestion.status == ScheduledIngestionStatus.ERROR
        assert self.scheduled_ingestion.consecutive_failure_count == 1
        assert self.scheduled_ingestion.last_error_at is not None
        assert self.scheduled_ingestion.error_message == "dlt boom", (
            "the spine must propagate the run's error message to the parent"
        )
        assert AuditEvent.objects.filter(
            resource_type="SCHEDULED_INGESTION_RUN",
            action="RUN_FAILED",
            resource_id=str(run.id),
        ).exists()

    def test_dlt_spine_auto_pauses_after_max_consecutive_failures(self):
        """MAX_CONSECUTIVE_FAILURES consecutive spine failures auto-pause
        the parent schedule — the Phase 71 contract on the dlt path."""
        from unittest import mock

        from django.conf import settings

        max_failures = int(getattr(settings, "MAX_CONSECUTIVE_FAILURES", 5))
        failure = {
            "files_found": 1,
            "files_processed": 0,
            "files_failed": 1,
            "error_message": "boom",
        }
        for _ in range(max_failures):
            with mock.patch(_INGESTION_ENTRYPOINT, return_value=failure):
                resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")
            assert resp.status_code in (200, 201)

        self.scheduled_ingestion.refresh_from_db()
        assert self.scheduled_ingestion.status == ScheduledIngestionStatus.PAUSED, (
            "the dlt spine must drive the Phase 71 auto-pause contract"
        )
        assert self.scheduled_ingestion.consecutive_failure_count == max_failures

    def test_dlt_spine_replay_fires_side_effects_exactly_once(self):
        """An idempotent replay returns the existing run without a second
        side-effect wave."""
        from unittest import mock

        key = f"ik-{uuid.uuid4().hex}"
        stale = self._stale_next_run_at()
        with mock.patch(_INGESTION_ENTRYPOINT, return_value=_SUCCESS_OUTCOME):
            first = self._post_run(idempotency_key=key)
            second = self._post_run(idempotency_key=key)

        assert first.status_code in (200, 201)
        assert second.status_code == 200
        run = ScheduledIngestionRun.objects.get(scheduled_ingestion=self.scheduled_ingestion)
        assert second.data.get("id") == str(run.id), "the replay returns the existing run"
        side_effects_after_first = SideEffect.objects.filter(run_object_id=run.pk).count()
        assert side_effects_after_first > 0

        # The replay must not have re-fired anything (next_run_at is
        # recomputed only for a real completion).
        second_count = SideEffect.objects.filter(run_object_id=run.pk).count()
        assert second_count == side_effects_after_first
        self.scheduled_ingestion.refresh_from_db()
        assert self.scheduled_ingestion.next_run_at != stale
        assert (
            AuditEvent.objects.filter(
                resource_type="SCHEDULED_INGESTION_RUN",
                action="RUN_COMPLETED",
                resource_id=str(run.id),
            ).count()
            == 1
        ), "exactly one completion audit for one completion"

    def test_same_status_patch_after_spine_completion_does_not_refire(self):
        """A worker PATCH replaying COMPLETED after the spine finalized the
        run is a no-op — no second side-effect wave across entrypoints."""
        from unittest import mock

        with mock.patch(_INGESTION_ENTRYPOINT, return_value=_SUCCESS_OUTCOME):
            resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")
        assert resp.status_code in (200, 201)
        run = ScheduledIngestionRun.objects.get(scheduled_ingestion=self.scheduled_ingestion)
        side_effects_after_spine = SideEffect.objects.filter(run_object_id=run.pk).count()
        assert side_effects_after_spine > 0

        patch_resp = self.client.patch(
            f"{RUNS_URL}{run.id}/",
            {"status": "COMPLETED", "completed_at": timezone.now().isoformat()},
            format="json",
        )
        assert patch_resp.status_code == status.HTTP_200_OK
        assert (
            SideEffect.objects.filter(run_object_id=run.pk).count() == side_effects_after_spine
        ), "the PATCH replay must not create a second side-effect wave"
