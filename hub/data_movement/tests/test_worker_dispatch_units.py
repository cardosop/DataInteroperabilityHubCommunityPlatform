"""Phase 6 (openspec wire-databricks-dlt-movement task 6.11) — the
worker-lifecycle dispatch units at the SERVICE level: the two canonical
seams (``ScheduledExportService.execute_export`` /
``IngestionService.execute_ingestion_run``) dispatch the entrypoints with
the row ids and record the terminal state — and a replayed call NEVER
re-dispatches (the service-level no-double-dispatch contract; the 6.2
HTTP pins cover the view layer, these pins cover the seams directly).

The sanctioned patch points are the entrypoint symbols in the service
modules (the 4.4 dispatch-symbol convention). Everything else is REAL:
real Postgres rows (tenant/export/ingestion/run), the real services.
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest

from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.scheduled_export.services import ScheduledExportService
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
)
from hub.apps.scheduled_ingestion.services import IngestionService
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

_EXPORT_ENTRYPOINT = "hub.data_movement.export_execution.execute_dlt_export"
_INGESTION_ENTRYPOINT = "hub.data_movement.ingestion_execution.execute_dlt_ingestion"


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"dispatch-unit-{uid}",
        slug=f"dispatch-unit-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=True,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"du-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _mk_export(tenant):
    from hub.apps.assets.models import Asset

    asset = Asset.objects.create(tenant=tenant, name="src", created_by=None)
    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"du-exp-{uuid.uuid4().hex[:8]}",
        destination_type=DestinationType.S3,
        destination_config={"bucket": "test-bucket"},
        schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
        source_scope={"asset_ids": [str(asset.id)]},
        status=ScheduledExportStatus.ACTIVE,
    )


def _mk_ingestion(tenant, user):
    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"du-ing-{uuid.uuid4().hex[:8]}",
        source_type="S3",
        source_config={"bucket": "src-bucket"},
        schedule_type="DAILY",
        schedule_config={"time": "00:00"},
        file_pattern=".*\\.csv",
        status=ScheduledIngestionStatus.ACTIVE,
        created_by=user,
    )


class TestExportSeamDispatchUnits:
    def test_the_seam_dispatches_the_entrypoint_with_the_export_row_id(self):
        tenant = _mk_tenant()
        user = _mk_user(tenant)
        scheduled_export = _mk_export(tenant)
        service = ScheduledExportService(tenant_id=str(tenant.id), user_id=str(user.id))

        recorder = mock.Mock(
            return_value={
                "items_found": 1,
                "items_exported": 1,
                "items_failed": 0,
                "error_message": None,
            }
        )
        with mock.patch(_EXPORT_ENTRYPOINT, recorder):
            result = service.execute_export(
                str(scheduled_export.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )

        recorder.assert_called_once_with(str(scheduled_export.id))
        run = ScheduledExportRun.objects.get(scheduled_export=scheduled_export)
        assert run.status == ScheduledExportRunStatus.COMPLETED
        assert (run.result_json or {}).get("dlt_outcome", {}).get("items_exported") == 1
        assert result["run_id"] == str(run.id)
        assert result["run_status"] == ScheduledExportRunStatus.COMPLETED

    def test_a_failing_outcome_marks_the_run_failed(self):
        tenant = _mk_tenant()
        user = _mk_user(tenant)
        scheduled_export = _mk_export(tenant)
        service = ScheduledExportService(tenant_id=str(tenant.id), user_id=str(user.id))

        recorder = mock.Mock(
            return_value={
                "items_found": 0,
                "items_exported": 0,
                "items_failed": 1,
                "error_message": "destination rejected the write",
            }
        )
        with mock.patch(_EXPORT_ENTRYPOINT, recorder):
            service.execute_export(
                str(scheduled_export.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )

        run = ScheduledExportRun.objects.get(scheduled_export=scheduled_export)
        assert run.status == ScheduledExportRunStatus.FAILED
        assert (run.result_json or {}).get("dlt_outcome", {}).get("error_message") == (
            "destination rejected the write"
        )

    def test_a_replayed_seam_call_never_double_dispatches(self):
        tenant = _mk_tenant()
        user = _mk_user(tenant)
        scheduled_export = _mk_export(tenant)
        service = ScheduledExportService(tenant_id=str(tenant.id), user_id=str(user.id))

        recorder = mock.Mock(
            return_value={
                "items_found": 1,
                "items_exported": 1,
                "items_failed": 0,
                "error_message": None,
            }
        )
        key = f"ik-{uuid.uuid4().hex}"
        with mock.patch(_EXPORT_ENTRYPOINT, recorder):
            first = service.execute_export(
                str(scheduled_export.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                idempotency_key=key,
            )
            second = service.execute_export(
                str(scheduled_export.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                idempotency_key=key,
            )

        assert recorder.call_count == 1, (
            "the service-level replay must return the existing run, never re-dispatch"
        )
        assert second["run_id"] == first["run_id"]


class TestIngestionSeamDispatchUnits:
    def test_the_seam_dispatches_through_the_entrypoint_and_stamps_the_run(self):
        tenant = _mk_tenant()
        user = _mk_user(tenant)
        scheduled_ingestion = _mk_ingestion(tenant, user)
        service = IngestionService(tenant_id=str(tenant.id), user_id=str(user.id))

        recorder = mock.Mock(
            return_value={
                "files_found": 2,
                "files_processed": 2,
                "files_failed": 0,
                "datasets_created": 1,
                "error_message": None,
            }
        )
        with mock.patch(_INGESTION_ENTRYPOINT, recorder):
            result = service.execute_ingestion_run(
                str(scheduled_ingestion.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )

        recorder.assert_called_once_with(str(scheduled_ingestion.id))
        run = ScheduledIngestionRun.objects.get(scheduled_ingestion=scheduled_ingestion)
        assert run.status == ScheduledIngestionRunStatus.COMPLETED
        assert (run.result_json or {}).get("dlt_outcome", {}).get("files_processed") == 2
        assert result["run_id"] == str(run.id)

    def test_a_failing_outcome_marks_the_run_failed(self):
        tenant = _mk_tenant()
        user = _mk_user(tenant)
        scheduled_ingestion = _mk_ingestion(tenant, user)
        service = IngestionService(tenant_id=str(tenant.id), user_id=str(user.id))

        recorder = mock.Mock(
            return_value={
                "files_found": 1,
                "files_processed": 0,
                "files_failed": 1,
                "datasets_created": 0,
                "error_message": "source refused the read",
            }
        )
        with mock.patch(_INGESTION_ENTRYPOINT, recorder):
            service.execute_ingestion_run(
                str(scheduled_ingestion.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )

        run = ScheduledIngestionRun.objects.get(scheduled_ingestion=scheduled_ingestion)
        assert run.status == ScheduledIngestionRunStatus.FAILED
        assert (run.result_json or {}).get("dlt_outcome", {}).get("error_message") == (
            "source refused the read"
        )

    def test_a_replayed_seam_call_never_double_dispatches(self):
        tenant = _mk_tenant()
        user = _mk_user(tenant)
        scheduled_ingestion = _mk_ingestion(tenant, user)
        service = IngestionService(tenant_id=str(tenant.id), user_id=str(user.id))

        recorder = mock.Mock(
            return_value={
                "files_found": 1,
                "files_processed": 1,
                "files_failed": 0,
                "datasets_created": 1,
                "error_message": None,
            }
        )
        key = f"ik-{uuid.uuid4().hex}"
        with mock.patch(_INGESTION_ENTRYPOINT, recorder):
            first = service.execute_ingestion_run(
                str(scheduled_ingestion.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                idempotency_key=key,
            )
            second = service.execute_ingestion_run(
                str(scheduled_ingestion.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                idempotency_key=key,
            )

        assert recorder.call_count == 1, (
            "the service-level replay must return the existing run, never re-dispatch"
        )
        assert second["run_id"] == first["run_id"]
