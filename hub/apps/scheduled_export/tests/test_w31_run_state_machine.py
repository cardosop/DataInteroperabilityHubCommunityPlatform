"""W3.1 (oss-release-remediation R2-P1) — scheduled-export run state machine.

Evidence pins (all real DB + real DRF over the internal worker API; the only
patched symbol is the sanctioned dlt-entrypoint seam):

* **FAILED→COMPLETED rejected** — a terminal run cannot be re-opened by a
  late worker PATCH; the endpoint returns 400 ``INVALID_TRANSITION`` and
  the row keeps its terminal status.
* **No re-fired side effects** — the rejected PATCH creates no new
  SideEffect rows, leaves the parent export's run bookkeeping untouched,
  and emits no ``RUN_COMPLETED`` audit event.
* **Worker honors CANCELLED** — process-export-item on a CANCELLED run
  raises ``RUN_CANCELLED`` (400 over HTTP); the dlt spine records its
  outcome without overwriting a run cancelled mid-flight.
* **Guarded model + service writes** — direct ORM status writes and
  ``ScheduledExportService.update_export_run`` transitions are validated
  against the shared matrix (``GuardedStateMachine``).
"""

import uuid

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.auth.models import APIKey
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.jobs.models import SideEffect
from hub.apps.scheduled_export.internal_auth import SCOPE_SCHEDULED_EXPORT_INTERNAL
from hub.apps.scheduled_export.models import (
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
)
from hub.apps.scheduled_export.services import ScheduledExportService
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.timeout(120),
]

_EXPORT_ENTRYPOINT = "hub.data_movement.export_execution.execute_dlt_export"

RUNS_URL = "/api/v1/scheduled-exports/internal/runs/"


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


def _mk_export(tenant, *, flagged=False):
    if flagged:
        tenant.data_movement_enabled = True
        tenant.save(update_fields=["data_movement_enabled"])
    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"W31 Export {uuid.uuid4().hex[:8]}",
        schedule_config={"cron": "0 3 * * *", "timezone": "UTC"},
        destination_type="S3",
        destination_config={"bucket": "dest-bucket", "prefix": "out/", "send_notifications": False},
        source_scope={"dataset_ids": [str(uuid.uuid4())]},
    )


class InternalExportRunStateMachineTest(TestCase):
    """Internal worker PATCH pins over the real stack."""

    def setUp(self):
        self.client = APIClient()
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W31 Export Tenant {unique}",
            slug=f"w31-export-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w31-export-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.plaintext_key = _create_worker_api_key(self.tenant, self.user)
        self.scheduled_export = _mk_export(self.tenant)

    def _auth(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _create_run(self):
        self._auth()
        response = self.client.post(
            RUNS_URL,
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        return ScheduledExportRun.objects.get(id=response.data["id"])

    def _patch(self, run_id, payload):
        self._auth()
        return self.client.patch(f"{RUNS_URL}{run_id}/", payload, format="json")

    def test_patch_failed_to_completed_rejected(self):
        """FAILED→COMPLETED PATCH returns 400 INVALID_TRANSITION; row keeps FAILED."""
        run = self._create_run()
        resp = self._patch(str(run.id), {"status": "FAILED"})
        assert resp.status_code == status.HTTP_200_OK

        resp = self._patch(str(run.id), {"status": "COMPLETED"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data.get("code") == "INVALID_TRANSITION"
        run.refresh_from_db()
        assert run.status == ScheduledExportRunStatus.FAILED

    def test_patch_failed_to_completed_does_not_refire_side_effects(self):
        """The rejected FAILED→COMPLETED PATCH fires NO side effects."""
        run = self._create_run()
        resp = self._patch(
            str(run.id), {"status": "FAILED", "completed_at": timezone.now().isoformat()}
        )
        assert resp.status_code == status.HTTP_200_OK

        self.scheduled_export.refresh_from_db()
        next_run_at_after_failed = self.scheduled_export.next_run_at
        last_run_at_after_failed = self.scheduled_export.last_run_at
        side_effects_after_failed = SideEffect.objects.filter(run_object_id=run.pk).count()
        completed_audits_after_failed = AuditEvent.objects.filter(
            resource_type="SCHEDULED_EXPORT_RUN",
            action="RUN_COMPLETED",
            resource_id=str(run.id),
        ).count()

        resp = self._patch(str(run.id), {"status": "COMPLETED"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        run.refresh_from_db()
        assert run.status == ScheduledExportRunStatus.FAILED
        assert (
            SideEffect.objects.filter(run_object_id=run.pk).count() == side_effects_after_failed
        ), "the rejected transition must not create new side-effect rows"
        self.scheduled_export.refresh_from_db()
        assert self.scheduled_export.next_run_at == next_run_at_after_failed
        assert self.scheduled_export.last_run_at == last_run_at_after_failed
        assert (
            AuditEvent.objects.filter(
                resource_type="SCHEDULED_EXPORT_RUN",
                action="RUN_COMPLETED",
                resource_id=str(run.id),
            ).count()
            == completed_audits_after_failed
        ), "the rejected transition must not emit a RUN_COMPLETED audit"

    def test_patch_cancelled_to_completed_rejected(self):
        """A completion PATCH cannot overwrite a CANCELLED run."""
        run = self._create_run()
        resp = self._patch(str(run.id), {"status": "CANCELLED"})
        assert resp.status_code == status.HTTP_200_OK

        resp = self._patch(str(run.id), {"status": "COMPLETED"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data.get("code") == "INVALID_TRANSITION"
        run.refresh_from_db()
        assert run.status == ScheduledExportRunStatus.CANCELLED

    def test_patch_running_to_cancelled_succeeds(self):
        """RUNNING→CANCELLED is a legal terminal hop."""
        run = self._create_run()
        resp = self._patch(
            str(run.id), {"status": "CANCELLED", "completed_at": timezone.now().isoformat()}
        )
        assert resp.status_code == status.HTTP_200_OK
        run.refresh_from_db()
        assert run.status == ScheduledExportRunStatus.CANCELLED

    def test_patch_same_status_noop_does_not_refire(self):
        """A same-status PATCH is a no-op — no second side-effect wave."""
        run = self._create_run()
        resp = self._patch(
            str(run.id), {"status": "COMPLETED", "completed_at": timezone.now().isoformat()}
        )
        assert resp.status_code == status.HTTP_200_OK
        side_effects_after_first = SideEffect.objects.filter(run_object_id=run.pk).count()

        resp = self._patch(str(run.id), {"status": "COMPLETED"})
        assert resp.status_code == status.HTTP_200_OK
        assert (
            SideEffect.objects.filter(run_object_id=run.pk).count() == side_effects_after_first
        ), "a same-status replay must not create a second side-effect wave"

    def test_patch_counts_on_terminal_run_allowed(self):
        """Count/result updates on a terminal run (no status change) stay legal."""
        run = self._create_run()
        assert self._patch(str(run.id), {"status": "FAILED"}).status_code == status.HTTP_200_OK

        resp = self._patch(str(run.id), {"items_failed": 2, "result_json": {"note": "late"}})
        assert resp.status_code == status.HTTP_200_OK
        run.refresh_from_db()
        assert run.items_failed == 2
        assert (run.result_json or {}).get("note") == "late"

    def test_service_update_export_run_rejects_illegal_transition(self):
        """The service seam validates transitions (code INVALID_TRANSITION)."""
        run = self._create_run()
        self._patch(str(run.id), {"status": "FAILED"})

        service = ScheduledExportService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        with pytest.raises(ServiceValidationError) as excinfo:
            service.update_export_run(
                str(run.id),
                tenant_id=str(self.tenant.id),
                status="COMPLETED",
            )
        assert excinfo.value.code == "INVALID_TRANSITION"
        run.refresh_from_db()
        assert run.status == ScheduledExportRunStatus.FAILED

    def test_direct_status_write_on_existing_run_rejected(self):
        """Direct ORM status writes on an existing row hit the model guard."""
        run = self._create_run()
        self._patch(str(run.id), {"status": "FAILED"})
        run.refresh_from_db()

        run.status = ScheduledExportRunStatus.COMPLETED
        with pytest.raises(DjangoValidationError):
            run.save(update_fields=["status", "updated_at"])

    def test_process_export_item_on_cancelled_run_rejected(self):
        """The worker's process-export endpoint honors CANCELLED (400 RUN_CANCELLED)."""
        run = self._create_run()
        assert self._patch(str(run.id), {"status": "CANCELLED"}).status_code == status.HTTP_200_OK

        self._auth()
        response = self.client.post(
            "/api/v1/scheduled-exports/internal/process-export/",
            {
                "run_id": str(run.id),
                "dataset_id": str(uuid.uuid4()),
                "destination_path": "out/cancelled.parquet",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data.get("code") == "RUN_CANCELLED"


class DltExportSpineCancelHonorTest(TestCase):
    """The dlt export spine honors a run cancelled mid-flight."""

    def setUp(self):
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W31 Export Spine {unique}",
            slug=f"w31-export-spine-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
            data_movement_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w31-export-spine-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_export = _mk_export(self.tenant, flagged=True)
        worker_key = _create_worker_api_key(self.tenant, self.user)
        self.client = APIClient()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {worker_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _post_run(self, **payload):
        body = {"scheduled_export_id": str(self.scheduled_export.id), **payload}
        return self.client.post(RUNS_URL, data=body, format="json")

    def _dlt_outcome(self, **overrides):
        result = {"items_found": 2, "items_exported": 2, "items_failed": 0}
        result.update(overrides)
        return result

    def test_spine_does_not_overwrite_run_cancelled_midflight(self):
        """A run cancelled while the entrypoint executes keeps CANCELLED;
        the dlt outcome is recorded without overwriting the terminal state."""
        from unittest import mock

        def _cancel_midflight(scheduled_export_id):
            run = ScheduledExportRun.objects.get(scheduled_export_id=scheduled_export_id)
            run.status = ScheduledExportRunStatus.CANCELLED
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at", "updated_at"])
            return self._dlt_outcome()

        with mock.patch(_EXPORT_ENTRYPOINT, side_effect=_cancel_midflight):
            resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")

        assert resp.status_code in (200, 201)
        assert resp.data.get("run_status") == "CANCELLED"
        run = ScheduledExportRun.objects.get(scheduled_export=self.scheduled_export)
        assert run.status == ScheduledExportRunStatus.CANCELLED, (
            "the spine must never overwrite a CANCELLED run with a terminal outcome"
        )
        assert (run.result_json or {}).get("dlt_outcome", {}).get("items_exported") == 2, (
            "the dlt outcome is still recorded on the cancelled run"
        )


# ── Matrix pins (new surface — the shared machine owns the hop table) ──

_EXPORT_LEGAL_HOPS = {
    ScheduledExportRunStatus.RUNNING: {
        ScheduledExportRunStatus.COMPLETED,
        ScheduledExportRunStatus.FAILED,
        ScheduledExportRunStatus.CANCELLED,
    },
    ScheduledExportRunStatus.COMPLETED: set(),
    ScheduledExportRunStatus.FAILED: set(),
    ScheduledExportRunStatus.CANCELLED: set(),
}


class ExportRunMatrixTest(TestCase):
    """The export run matrix, pinned exhaustively over every pair."""

    def test_matrix_covers_every_pair(self):
        from hub.apps.scheduled_export.models import ExportRunStateMachine

        all_statuses = list(ScheduledExportRunStatus)
        for src in all_statuses:
            for dst in all_statuses:
                expected = dst in _EXPORT_LEGAL_HOPS[src]
                assert ExportRunStateMachine.can_transition(src, dst) is expected, (
                    f"{src.value}→{dst.value} legality mismatch"
                )

    def test_terminal_states_derived_from_the_matrix(self):
        from hub.apps.scheduled_export.models import ExportRunStateMachine

        terminals = {
            ScheduledExportRunStatus.COMPLETED,
            ScheduledExportRunStatus.FAILED,
            ScheduledExportRunStatus.CANCELLED,
        }
        for st in ScheduledExportRunStatus:
            assert ExportRunStateMachine.is_terminal(st) is (st in terminals), (
                f"terminal derivation mismatch for {st.value}"
            )

    def test_validate_transition_raises_on_illegal_hop(self):
        from hub.apps.scheduled_export.models import ExportRunStateMachine

        with pytest.raises(DjangoValidationError):
            ExportRunStateMachine.validate_transition(
                ScheduledExportRunStatus.FAILED, ScheduledExportRunStatus.COMPLETED
            )

    def test_validate_transition_is_raw_string_safe(self):
        """Legacy direct-assignment paths leave raw strings — the matrix
        must not treat them as a bypass (the primitive contract)."""
        from hub.apps.scheduled_export.models import ExportRunStateMachine

        assert ExportRunStateMachine.can_transition("RUNNING", "COMPLETED")
        assert not ExportRunStateMachine.can_transition("FAILED", "COMPLETED")
