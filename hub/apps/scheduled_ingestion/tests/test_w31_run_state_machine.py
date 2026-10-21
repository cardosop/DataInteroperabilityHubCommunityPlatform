"""W3.1 (oss-release-remediation R2-P1) — scheduled-ingestion run state machine.

Evidence pins (all real DB + real DRF over the internal worker API; the only
patched symbols are the sanctioned dlt-entrypoint seams):

* **FAILED→COMPLETED rejected** — a terminal run cannot be re-opened by a
  late worker PATCH; the endpoint returns 400 ``INVALID_TRANSITION`` and
  the row keeps its terminal status.
* **No re-fired side effects** — the rejected PATCH creates no new
  SideEffect rows, leaves ``next_run_at`` untouched, and emits no
  ``RUN_COMPLETED`` audit event.
* **Worker honors CANCELLED** — process-file on a CANCELLED run returns
  400 ``RUN_CANCELLED`` (no File rows); a completion PATCH cannot
  overwrite CANCELLED; the dlt spine records its outcome without
  overwriting a run cancelled mid-flight.
* **Guarded model writes** — direct ORM status writes on an existing row
  are validated against the shared matrix (``GuardedStateMachine``).
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
from hub.apps.jobs.models import SideEffect
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

RUNS_URL = "/api/v1/scheduled-ingestions/internal/runs/"


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


class InternalRunStateMachineTest(TestCase):
    """Internal worker PATCH + process-file pins over the real stack."""

    def setUp(self):
        self.client = APIClient()
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W31 Ingest Tenant {unique}",
            slug=f"w31-ingest-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w31-ingest-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.plaintext_key = _create_worker_api_key(self.tenant, self.user)
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name=f"W31 Ingestion {unique}",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket", "prefix": "data/", "send_notifications": False},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )

    def _auth(self):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _create_run(self, **kwargs):
        self._auth()
        response = self.client.post(
            RUNS_URL,
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        run = ScheduledIngestionRun.objects.get(id=response.data["id"])
        for key, value in kwargs.items():
            setattr(run, key, value)
        if kwargs:
            run.save()
        return run

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
        assert run.status == ScheduledIngestionRunStatus.FAILED

    def test_patch_failed_to_completed_does_not_refire_side_effects(self):
        """The rejected FAILED→COMPLETED PATCH fires NO side effects."""
        run = self._create_run()
        resp = self._patch(
            str(run.id), {"status": "FAILED", "completed_at": timezone.now().isoformat()}
        )
        assert resp.status_code == status.HTTP_200_OK

        self.scheduled_ingestion.refresh_from_db()
        next_run_at_after_failed = self.scheduled_ingestion.next_run_at
        side_effects_after_failed = SideEffect.objects.filter(run_object_id=run.pk).count()
        completed_audits_after_failed = AuditEvent.objects.filter(
            resource_type="SCHEDULED_INGESTION_RUN",
            action="RUN_COMPLETED",
            resource_id=str(run.id),
        ).count()

        resp = self._patch(str(run.id), {"status": "COMPLETED"})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.FAILED
        assert (
            SideEffect.objects.filter(run_object_id=run.pk).count() == side_effects_after_failed
        ), "the rejected transition must not create new side-effect rows"
        self.scheduled_ingestion.refresh_from_db()
        assert self.scheduled_ingestion.next_run_at == next_run_at_after_failed
        assert (
            AuditEvent.objects.filter(
                resource_type="SCHEDULED_INGESTION_RUN",
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
        assert run.status == ScheduledIngestionRunStatus.CANCELLED

    def test_patch_running_to_cancelled_succeeds(self):
        """RUNNING→CANCELLED is a legal terminal hop."""
        run = self._create_run()
        resp = self._patch(
            str(run.id), {"status": "CANCELLED", "completed_at": timezone.now().isoformat()}
        )
        assert resp.status_code == status.HTTP_200_OK
        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.CANCELLED

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

        resp = self._patch(
            str(run.id), {"files_failed": 2, "result_json": {"note": "late metadata"}}
        )
        assert resp.status_code == status.HTTP_200_OK
        run.refresh_from_db()
        assert run.files_failed == 2
        assert (run.result_json or {}).get("note") == "late metadata"

    def test_patch_pending_to_completed_succeeds(self):
        """PENDING→terminal is the legacy Prefect full-flow contract (the
        trigger-created run is PATCHed straight to its terminal state) —
        it stays legal, while terminal re-opening stays blocked."""
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.PENDING,
            started_at=timezone.now(),
        )
        resp = self._patch(
            str(run.id), {"status": "COMPLETED", "completed_at": timezone.now().isoformat()}
        )
        assert resp.status_code == status.HTTP_200_OK
        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.COMPLETED

    def test_direct_status_write_on_existing_run_rejected(self):
        """Direct ORM status writes on an existing row hit the model guard."""
        run = self._create_run()
        self._patch(str(run.id), {"status": "FAILED"})
        run.refresh_from_db()

        run.status = ScheduledIngestionRunStatus.COMPLETED
        with pytest.raises(DjangoValidationError):
            run.save(update_fields=["status", "updated_at"])

    def test_process_file_on_cancelled_run_rejected(self):
        """The worker's process-file endpoint honors CANCELLED (400 RUN_CANCELLED)."""
        from hub.apps.files.models import File

        run = self._create_run()
        assert self._patch(str(run.id), {"status": "CANCELLED"}).status_code == status.HTTP_200_OK

        self._auth()
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/process-file/",
            {
                "run_id": str(run.id),
                "file_path": "data/cancelled.csv",
                "file_content": "aGVsbG8=",  # base64 "hello"
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data.get("code") == "RUN_CANCELLED"
        assert File.objects.filter(tenant=self.tenant).count() == 0, (
            "no File row may be created for a cancelled run"
        )


class DltSpineCancelHonorTest(TestCase):
    """The dlt dispatch spine honors a run cancelled mid-flight."""

    def setUp(self):
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W31 Spine Tenant {unique}",
            slug=f"w31-spine-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
            data_movement_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w31-spine-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name=f"W31 Spine Ingestion {unique}",
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

    def _dlt_outcome(self, **overrides):
        result = {
            "files_found": 2,
            "files_processed": 2,
            "files_failed": 0,
            "datasets_created": 1,
            "ingestion_state": {"processed_files": 2, "failed_files": 0},
        }
        result.update(overrides)
        return result

    def test_spine_marks_run_running_before_dispatch(self):
        """The run is RUNNING (not PENDING) while the entrypoint executes."""
        from unittest import mock

        observed = {}

        def _read_status_during_dispatch(scheduled_ingestion_id):
            run = ScheduledIngestionRun.objects.get(scheduled_ingestion_id=scheduled_ingestion_id)
            observed["status"] = str(run.status)
            return self._dlt_outcome()

        with mock.patch(_INGESTION_ENTRYPOINT, side_effect=_read_status_during_dispatch):
            resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")

        assert resp.status_code in (200, 201)
        assert observed.get("status") == "RUNNING", (
            "the spine must transition PENDING→RUNNING before dispatching the entrypoint"
        )

    def test_spine_does_not_overwrite_run_cancelled_midflight(self):
        """A run cancelled while the entrypoint executes keeps CANCELLED;
        the dlt outcome is recorded without overwriting the terminal state."""
        from unittest import mock

        def _cancel_midflight(scheduled_ingestion_id):
            run = ScheduledIngestionRun.objects.get(scheduled_ingestion_id=scheduled_ingestion_id)
            run.status = ScheduledIngestionRunStatus.CANCELLED
            run.completed_at = timezone.now()
            run.save(update_fields=["status", "completed_at", "updated_at"])
            return self._dlt_outcome()

        with mock.patch(_INGESTION_ENTRYPOINT, side_effect=_cancel_midflight):
            resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")

        assert resp.status_code in (200, 201)
        assert resp.data.get("run_status") == "CANCELLED"
        run = ScheduledIngestionRun.objects.get(scheduled_ingestion=self.scheduled_ingestion)
        assert run.status == ScheduledIngestionRunStatus.CANCELLED, (
            "the spine must never overwrite a CANCELLED run with a terminal outcome"
        )
        assert (run.result_json or {}).get("dlt_outcome", {}).get("files_processed") == 2, (
            "the dlt outcome is still recorded on the cancelled run"
        )


# ── Matrix pins (new surface — the shared machine owns the hop table) ──

_INGESTION_LEGAL_HOPS = {
    ScheduledIngestionRunStatus.PENDING: {
        ScheduledIngestionRunStatus.RUNNING,
        ScheduledIngestionRunStatus.COMPLETED,
        ScheduledIngestionRunStatus.FAILED,
        ScheduledIngestionRunStatus.CANCELLED,
    },
    ScheduledIngestionRunStatus.RUNNING: {
        ScheduledIngestionRunStatus.COMPLETED,
        ScheduledIngestionRunStatus.FAILED,
        ScheduledIngestionRunStatus.CANCELLED,
    },
    ScheduledIngestionRunStatus.COMPLETED: set(),
    ScheduledIngestionRunStatus.FAILED: set(),
    ScheduledIngestionRunStatus.CANCELLED: set(),
}


class IngestionRunMatrixTest(TestCase):
    """The ingestion run matrix, pinned exhaustively over every pair."""

    def test_matrix_covers_every_pair(self):
        from hub.apps.scheduled_ingestion.models import IngestionRunStateMachine

        all_statuses = list(ScheduledIngestionRunStatus)
        for src in all_statuses:
            for dst in all_statuses:
                expected = dst in _INGESTION_LEGAL_HOPS[src]
                assert IngestionRunStateMachine.can_transition(src, dst) is expected, (
                    f"{src.value}→{dst.value} legality mismatch"
                )

    def test_terminal_states_derived_from_the_matrix(self):
        from hub.apps.scheduled_ingestion.models import IngestionRunStateMachine

        terminals = {
            ScheduledIngestionRunStatus.COMPLETED,
            ScheduledIngestionRunStatus.FAILED,
            ScheduledIngestionRunStatus.CANCELLED,
        }
        for st in ScheduledIngestionRunStatus:
            assert IngestionRunStateMachine.is_terminal(st) is (st in terminals), (
                f"terminal derivation mismatch for {st.value}"
            )

    def test_validate_transition_raises_on_illegal_hop(self):
        from hub.apps.scheduled_ingestion.models import IngestionRunStateMachine

        with pytest.raises(DjangoValidationError):
            IngestionRunStateMachine.validate_transition(
                ScheduledIngestionRunStatus.FAILED, ScheduledIngestionRunStatus.COMPLETED
            )

    def test_validate_transition_is_raw_string_safe(self):
        """Legacy direct-assignment paths leave raw strings — the matrix
        must not treat them as a bypass (the primitive contract)."""
        from hub.apps.scheduled_ingestion.models import IngestionRunStateMachine

        assert IngestionRunStateMachine.can_transition("RUNNING", "COMPLETED")
        assert not IngestionRunStateMachine.can_transition("FAILED", "COMPLETED")


class RqWorkerTaskLifecycleTest(TestCase):
    """The RQ worker task (the trigger's async spine sibling) honors the
    same guarded lifecycle: PENDING→RUNNING before the entrypoint, and
    a cancelled run is never overwritten."""

    def setUp(self):
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W31 RQ Tenant {unique}",
            slug=f"w31-rq-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
            data_movement_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w31-rq-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name=f"W31 RQ Ingestion {unique}",
            source_type=SourceType.S3,
            source_config={"bucket": "src-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )

    def _mk_pending_run(self):
        return ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.PENDING,
            started_at=timezone.now(),
        )

    def _dlt_outcome(self, **overrides):
        result = {
            "files_found": 1,
            "files_processed": 1,
            "files_failed": 0,
            "datasets_created": 1,
        }
        result.update(overrides)
        return result

    def test_task_marks_running_before_dispatch_and_finalizes(self):
        """The task transitions PENDING→RUNNING before the entrypoint and
        writes the terminal state through the matrix."""
        from unittest import mock

        from hub.apps.scheduled_ingestion.tasks import execute_scheduled_ingestion_run

        run = self._mk_pending_run()
        observed = {}

        def _read_status_during_dispatch(scheduled_ingestion_id):
            run_row = ScheduledIngestionRun.objects.get(
                scheduled_ingestion_id=scheduled_ingestion_id
            )
            observed["status"] = str(run_row.status)
            return self._dlt_outcome()

        with mock.patch(_INGESTION_ENTRYPOINT, side_effect=_read_status_during_dispatch):
            execute_scheduled_ingestion_run(str(run.id), str(self.tenant.id))

        assert observed.get("status") == "RUNNING", (
            "the task must transition PENDING→RUNNING before dispatching the entrypoint"
        )
        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.COMPLETED
        assert (run.result_json or {}).get("dlt_outcome", {}).get("files_processed") == 1

    def test_task_skips_run_cancelled_before_pickup(self):
        """A run cancelled before the task picks it up is skipped — the
        entrypoint never runs."""
        from unittest import mock

        from hub.apps.scheduled_ingestion.tasks import execute_scheduled_ingestion_run

        run = self._mk_pending_run()
        run.status = ScheduledIngestionRunStatus.CANCELLED
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at", "updated_at"])

        recorder = mock.Mock(return_value=self._dlt_outcome())
        with mock.patch(_INGESTION_ENTRYPOINT, recorder):
            execute_scheduled_ingestion_run(str(run.id), str(self.tenant.id))

        recorder.assert_not_called(), "a cancelled run must never dispatch the entrypoint"
        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.CANCELLED

    def test_task_does_not_overwrite_run_cancelled_midflight(self):
        """A run cancelled while the pipeline ran keeps CANCELLED; the dlt
        outcome is recorded without overwriting the terminal state."""
        from unittest import mock

        from hub.apps.scheduled_ingestion.tasks import execute_scheduled_ingestion_run

        run = self._mk_pending_run()

        def _cancel_midflight(scheduled_ingestion_id):
            run_row = ScheduledIngestionRun.objects.get(
                scheduled_ingestion_id=scheduled_ingestion_id
            )
            run_row.status = ScheduledIngestionRunStatus.CANCELLED
            run_row.completed_at = timezone.now()
            run_row.save(update_fields=["status", "completed_at", "updated_at"])
            return self._dlt_outcome()

        with mock.patch(_INGESTION_ENTRYPOINT, side_effect=_cancel_midflight):
            execute_scheduled_ingestion_run(str(run.id), str(self.tenant.id))

        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.CANCELLED, (
            "the task must never overwrite a CANCELLED run with a terminal outcome"
        )
        assert (run.result_json or {}).get("dlt_outcome", {}).get("files_processed") == 1, (
            "the dlt outcome is still recorded on the cancelled run"
        )
