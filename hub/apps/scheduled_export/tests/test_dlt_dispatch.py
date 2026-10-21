"""Phase 6 (openspec wire-databricks-dlt-movement task 6.2) — the export
side of the movement spine: the worker-run lifecycles (the manual
trigger + the internal run-create) dispatch the canonical
``execute_dlt_export`` entrypoint for dlt-flagged tenants and record the
write outcome on the run's terminal state.

The sanctioned patch point is the ENTRYPOINT SYMBOL
(``hub.data_movement.export_execution.execute_dlt_export`` — the 4.4
dispatch-symbol convention; the entrypoint stays the single canonical
seam): the pins replace it with a recorder and assert the dispatch row
ids + the no-double-dispatch contract. Everything else is REAL: real
Postgres rows (tenant/export/run), real DRF views over real HTTP, real
worker API-key auth on the internal endpoints.
"""

import uuid
from unittest import mock

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

_EXPORT_ENTRYPOINT = "hub.data_movement.export_execution.execute_dlt_export"
_DEPLOYMENT_TRIGGER = (
    "hub.apps.scheduled_export.views._trigger_deployment_via_prefect_integration_service"
)


def _create_worker_api_key(tenant, user):
    from hub.apps.auth.models import APIKey
    from hub.apps.scheduled_export.internal_auth import SCOPE_SCHEDULED_EXPORT_INTERNAL

    plaintext = APIKey.generate_key()
    APIKey.objects.create(
        tenant=tenant,
        user=user,
        key_hash=APIKey.hash_key(plaintext),
        name=f"worker-key-{uuid.uuid4().hex[:8]}",
        scopes=[SCOPE_SCHEDULED_EXPORT_INTERNAL],
    )
    return plaintext


def _mk_tenant(*, flagged):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"dlt-dispatch-{uid}",
        slug=f"dlt-dispatch-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=flagged,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"dlt-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _mk_export(tenant):
    from hub.apps.assets.models import Asset

    asset = Asset.objects.create(tenant=tenant, name="src", created_by=None)
    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"exp-{uuid.uuid4().hex[:8]}",
        destination_type=DestinationType.S3,
        destination_config={"bucket": "test-bucket"},
        schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
        source_scope={"asset_ids": [str(asset.id)]},
        status=ScheduledExportStatus.ACTIVE,
    )


class TestExportTriggerDispatch:
    """The manual run endpoint dispatches the dlt spine for flagged
    tenants — and keeps the Prefect path otherwise."""

    def setUp(self):
        self.user = None

    def _trigger(self, tenant, scheduled_export):
        self.user = _mk_user(tenant)
        client = APIClient()
        client.force_authenticate(user=self.user)
        return client.post(
            f"/api/v1/scheduled-exports/{scheduled_export.id}/trigger/",
            data={},
            format="json",
        )

    def test_trigger_dispatches_the_entrypoint_with_the_export_row_id(self):
        tenant = _mk_tenant(flagged=True)
        scheduled_export = _mk_export(tenant)

        recorder = mock.Mock(
            return_value={
                "items_found": 3,
                "items_exported": 3,
                "items_failed": 0,
                "error_message": None,
            }
        )
        with mock.patch(_EXPORT_ENTRYPOINT, recorder):
            resp = self._trigger(tenant, scheduled_export)

        assert resp.status_code == 200
        recorder.assert_called_once_with(str(scheduled_export.id))
        run = ScheduledExportRun.objects.get(scheduled_export=scheduled_export)
        assert run.status == ScheduledExportRunStatus.COMPLETED, (
            "the run's terminal state records the dlt write outcome"
        )
        assert (run.result_json or {}).get("dlt_outcome", {}).get("items_exported") == 3

    def test_a_failing_outcome_marks_the_run_failed(self):
        tenant = _mk_tenant(flagged=True)
        scheduled_export = _mk_export(tenant)

        recorder = mock.Mock(
            return_value={
                "items_found": 0,
                "items_exported": 0,
                "items_failed": 1,
                "error_message": "destination rejected the write",
            }
        )
        with mock.patch(_EXPORT_ENTRYPOINT, recorder):
            resp = self._trigger(tenant, scheduled_export)

        assert resp.status_code == 200
        run = ScheduledExportRun.objects.get(scheduled_export=scheduled_export)
        assert run.status == ScheduledExportRunStatus.FAILED
        assert (run.result_json or {}).get("dlt_outcome", {}).get("error_message") == (
            "destination rejected the write"
        )

    def test_trigger_keeps_the_prefect_path_when_not_flagged(self):
        tenant = _mk_tenant(flagged=False)
        scheduled_export = _mk_export(tenant)

        recorder = mock.Mock()
        deployment = mock.Mock(return_value=(True, "fr-legacy", None))
        with (
            mock.patch(_EXPORT_ENTRYPOINT, recorder),
            mock.patch(_DEPLOYMENT_TRIGGER, deployment),
        ):
            resp = self._trigger(tenant, scheduled_export)

        recorder.assert_not_called(), "a non-flagged tenant must never dispatch the dlt entrypoint"
        assert deployment.called, "the legacy Prefect deployment path stays for non-flagged tenants"
        assert resp.status_code in (200, 201, 202)


class TestExportInternalRunCreateDispatch(TestCase):
    """The worker-run lifecycle (internal runs create) dispatches the
    same spine — with the no-double-dispatch idempotency contract."""

    def setUp(self):
        self.tenant = _mk_tenant(flagged=True)
        self.user = _mk_user(self.tenant)
        self.scheduled_export = _mk_export(self.tenant)
        self.client = APIClient()
        worker_key = _create_worker_api_key(self.tenant, self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {worker_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _post_run(self, **payload):
        body = {"scheduled_export_id": str(self.scheduled_export.id), **payload}
        return self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            data=body,
            format="json",
        )

    def test_the_internal_run_create_dispatches_for_a_flagged_tenant(self):
        recorder = mock.Mock(
            return_value={
                "items_found": 2,
                "items_exported": 2,
                "items_failed": 0,
                "error_message": None,
            }
        )
        with mock.patch(_EXPORT_ENTRYPOINT, recorder):
            resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")

        assert resp.status_code in (200, 201, 202)
        recorder.assert_called_once_with(str(self.scheduled_export.id))
        run = ScheduledExportRun.objects.get(scheduled_export=self.scheduled_export)
        assert run.status == ScheduledExportRunStatus.COMPLETED

    def test_the_idempotent_replay_never_double_dispatches(self):
        key = f"ik-{uuid.uuid4().hex}"
        recorder = mock.Mock(
            return_value={
                "items_found": 1,
                "items_exported": 1,
                "items_failed": 0,
                "error_message": None,
            }
        )
        with mock.patch(_EXPORT_ENTRYPOINT, recorder):
            first = self._post_run(idempotency_key=key)
            second = self._post_run(idempotency_key=key)

        assert first.status_code in (200, 201)
        assert second.status_code == 200
        assert recorder.call_count == 1, (
            "the replay must return the existing run, never re-dispatch"
        )
