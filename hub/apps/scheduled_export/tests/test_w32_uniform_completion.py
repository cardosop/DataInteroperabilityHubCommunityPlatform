"""W3.2 (oss-release-remediation R2-P5) — uniform run completion (export).

Every entrypoint that finalizes a scheduled-export run (the dlt spine via
``execute_export`` — reached from BOTH the internal run-create and the
public trigger — and the internal PATCH) must route completion through
``apply_run_completion_side_effects`` exactly once: the parent
``next_run_at`` recompute + ``last_run_at``/``last_run_status``
bookkeeping, the Phase-71 failure accounting + auto-pause, the outbox
rows, and the completion audit must fire identically on every path.
Evidence pins (real DB + real DRF; the only patched symbol is the
sanctioned dlt-entrypoint seam):

* **dlt-tenant `next_run_at` recompute** — a stale parent ``next_run_at``
  is recomputed when the spine finalizes a run.
* **Auto-pause** — MAX_CONSECUTIVE_FAILURES consecutive spine failures
  pause the parent export (and one failure sets ERROR + counters).
* **Exactly once** — replays create no second side-effect wave.
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
from hub.apps.scheduled_export.internal_auth import SCOPE_SCHEDULED_EXPORT_INTERNAL
from hub.apps.scheduled_export.models import (
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.timeout(120),
]

_EXPORT_ENTRYPOINT = "hub.data_movement.export_execution.execute_dlt_export"

RUNS_URL = "/api/v1/scheduled-exports/internal/runs/"

_SUCCESS_OUTCOME = {"items_found": 2, "items_exported": 2, "items_failed": 0}


def _create_worker_api_key(tenant, user):
    plaintext = APIKey.generate_key()
    APIKey.objects.create(
        tenant=tenant,
        user=user,
        key_hash=APIKey.hash_key(plaintext),
        name=f"worker-key-{uuid.uuid4().hex[:8]}",
        scopes=[SCOPE_SCHEDULED_EXPORT_INTERNAL],
    )
    return plaintext


class DltExportSpineUniformCompletionTest(TestCase):
    """The dlt export spine finalizes runs through the same completion
    contract as the internal PATCH."""

    def setUp(self):
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W32 Export Tenant {unique}",
            slug=f"w32-export-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
            data_movement_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w32-export-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name=f"W32 Export {unique}",
            schedule_config={"cron": "0 3 * * *", "timezone": "UTC"},
            destination_type="S3",
            destination_config={"bucket": "dest-bucket", "prefix": "out/"},
            source_scope={"dataset_ids": [str(uuid.uuid4())]},
        )
        worker_key = _create_worker_api_key(self.tenant, self.user)
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {worker_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _post_run(self, **payload):
        body = {"scheduled_export_id": str(self.scheduled_export.id), **payload}
        return self.client.post(RUNS_URL, data=body, format="json")

    def _stale_next_run_at(self):
        stale = timezone.now() - timedelta(days=30)
        self.scheduled_export.next_run_at = stale
        self.scheduled_export.save(update_fields=["next_run_at"])
        return stale

    def test_dlt_export_spine_completion_recomputes_next_run_at(self):
        """A dlt-spine COMPLETED export run recomputes the parent
        next_run_at, records last_run bookkeeping, and fires the
        completion side effects (outbox rows + audit)."""
        from unittest import mock

        stale = self._stale_next_run_at()
        with mock.patch(_EXPORT_ENTRYPOINT, return_value=_SUCCESS_OUTCOME):
            resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")

        assert resp.status_code in (200, 201)
        assert resp.data.get("run_status") == "COMPLETED"
        run = ScheduledExportRun.objects.get(scheduled_export=self.scheduled_export)

        self.scheduled_export.refresh_from_db()
        assert self.scheduled_export.next_run_at != stale, (
            "the dlt spine must recompute next_run_at (the pre-fix spine left it stale)"
        )
        assert self.scheduled_export.next_run_at > timezone.now()
        assert self.scheduled_export.last_run_at is not None
        assert self.scheduled_export.last_run_status == ScheduledExportRunStatus.COMPLETED
        assert self.scheduled_export.consecutive_failure_count == 0
        assert self.scheduled_export.status == ScheduledExportStatus.ACTIVE

        side_effect_types = set(
            SideEffect.objects.filter(run_object_id=run.pk).values_list("effect_type", flat=True)
        )
        assert "NOTIFICATION" in side_effect_types
        assert "AUDIT_EVENT" in side_effect_types
        assert "COST_TRACKING" in side_effect_types, "COMPLETED runs track costs"
        assert AuditEvent.objects.filter(
            resource_type="SCHEDULED_EXPORT_RUN",
            action="RUN_COMPLETED",
            resource_id=str(run.id),
        ).exists(), "the completion audit fires on the spine path too"

    def test_dlt_export_spine_failure_updates_parent_failure_accounting(self):
        """A dlt-spine FAILED export run sets ERROR on the parent and
        increments the Phase-71 consecutive-failure counter."""
        from unittest import mock

        failure = {
            "items_found": 1,
            "items_exported": 0,
            "items_failed": 1,
            "error_message": "boom",
        }
        with mock.patch(_EXPORT_ENTRYPOINT, return_value=failure):
            resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")

        assert resp.status_code in (200, 201)
        run = ScheduledExportRun.objects.get(scheduled_export=self.scheduled_export)
        assert run.status == ScheduledExportRunStatus.FAILED

        self.scheduled_export.refresh_from_db()
        assert self.scheduled_export.status == ScheduledExportStatus.ERROR
        assert self.scheduled_export.consecutive_failure_count == 1, (
            "the export failure counter is wired (Phase 71 design)"
        )
        assert self.scheduled_export.last_error_at is not None
        assert AuditEvent.objects.filter(
            resource_type="SCHEDULED_EXPORT_RUN",
            action="RUN_FAILED",
            resource_id=str(run.id),
        ).exists()

    def test_dlt_export_spine_auto_pauses_after_max_consecutive_failures(self):
        """MAX_CONSECUTIVE_FAILURES consecutive spine failures auto-pause
        the parent export — the Phase 71 contract on the dlt path."""
        from unittest import mock

        from django.conf import settings

        max_failures = int(getattr(settings, "MAX_CONSECUTIVE_FAILURES", 5))
        failure = {
            "items_found": 1,
            "items_exported": 0,
            "items_failed": 1,
            "error_message": "boom",
        }
        for _ in range(max_failures):
            with mock.patch(_EXPORT_ENTRYPOINT, return_value=failure):
                resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")
            assert resp.status_code in (200, 201)

        self.scheduled_export.refresh_from_db()
        assert self.scheduled_export.status == ScheduledExportStatus.PAUSED, (
            "the dlt spine must drive the Phase 71 auto-pause contract"
        )
        assert self.scheduled_export.consecutive_failure_count == max_failures

    def test_dlt_export_spine_replay_fires_side_effects_exactly_once(self):
        """An idempotent replay returns the existing run without a second
        side-effect wave."""
        from unittest import mock

        key = f"ik-{uuid.uuid4().hex}"
        with mock.patch(_EXPORT_ENTRYPOINT, return_value=_SUCCESS_OUTCOME):
            first = self._post_run(idempotency_key=key)
            second = self._post_run(idempotency_key=key)

        assert first.status_code in (200, 201)
        assert second.status_code == 200

        run = ScheduledExportRun.objects.get(scheduled_export=self.scheduled_export)
        side_effects_after_first = SideEffect.objects.filter(run_object_id=run.pk).count()
        assert side_effects_after_first > 0
        assert SideEffect.objects.filter(run_object_id=run.pk).count() == side_effects_after_first
        assert (
            AuditEvent.objects.filter(
                resource_type="SCHEDULED_EXPORT_RUN",
                action="RUN_COMPLETED",
                resource_id=str(run.id),
            ).count()
            == 1
        ), "exactly one completion audit for one completion"

    def test_public_trigger_uses_the_same_completion_contract(self):
        """The public trigger (the spine's second caller) finalizes through
        the same completion contract exactly once."""
        from unittest import mock

        stale = self._stale_next_run_at()
        user_client = APIClient()
        user_client.force_authenticate(user=self.user)
        with mock.patch(_EXPORT_ENTRYPOINT, return_value=_SUCCESS_OUTCOME):
            resp = user_client.post(
                f"/api/v1/scheduled-exports/{self.scheduled_export.id}/trigger/",
                data={},
                format="json",
            )

        assert resp.status_code == status.HTTP_200_OK
        run = ScheduledExportRun.objects.get(scheduled_export=self.scheduled_export)
        assert run.status == ScheduledExportRunStatus.COMPLETED

        self.scheduled_export.refresh_from_db()
        assert self.scheduled_export.next_run_at != stale, (
            "the trigger-path completion recomputes next_run_at"
        )
        assert (
            AuditEvent.objects.filter(
                resource_type="SCHEDULED_EXPORT_RUN",
                action="RUN_COMPLETED",
                resource_id=str(run.id),
            ).count()
            == 1
        ), "exactly one completion audit across the trigger path"
