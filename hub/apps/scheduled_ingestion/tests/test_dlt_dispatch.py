"""Phase 6 (openspec wire-databricks-dlt-movement task 6.2) — the
ingestion side of the movement spine: the worker-run lifecycles (the
manual trigger + the internal run-create) dispatch the canonical
``execute_dlt_ingestion`` entrypoint for dlt-flagged tenants and record
the outcome on the run's terminal state.

The sanctioned patch point is the ENTRYPOINT SYMBOL
(``hub.data_movement.ingestion_execution.execute_dlt_ingestion`` — the
4.4 dispatch-symbol convention). Everything else is REAL: real Postgres
rows, real DRF views over real HTTP, real worker API-key auth on the
internal endpoints.
"""

import uuid
from unittest import mock

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

_INGESTION_ENTRYPOINT = "hub.data_movement.ingestion_execution.execute_dlt_ingestion"
_DEPLOYMENT_TRIGGER = (
    "hub.apps.scheduled_ingestion.views._trigger_deployment_via_prefect_integration_service"
)


def _create_worker_api_key(tenant, user):
    from hub.apps.auth.models import APIKey
    from hub.apps.scheduled_ingestion.internal_auth import SCOPE_SCHEDULED_INGESTION_INTERNAL

    plaintext = APIKey.generate_key()
    APIKey.objects.create(
        tenant=tenant,
        user=user,
        key_hash=APIKey.hash_key(plaintext),
        name=f"worker-key-{uuid.uuid4().hex[:8]}",
        scopes=[SCOPE_SCHEDULED_INGESTION_INTERNAL],
    )
    return plaintext


def _mk_tenant(*, flagged):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"dlt-ingest-{uid}",
        slug=f"dlt-ingest-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=flagged,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"dlt-ing-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _mk_ingestion(tenant):
    user = _mk_user(tenant)
    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"ing-{uuid.uuid4().hex[:8]}",
        source_type="S3",
        source_config={"bucket": "src-bucket"},
        schedule_type="DAILY",
        schedule_config={"time": "00:00"},
        file_pattern=".*\\.csv",
        status=ScheduledIngestionStatus.ACTIVE,
        created_by=user,
    )


def _outcome(**overrides):
    result = {
        "files_found": 2,
        "files_processed": 2,
        "files_failed": 0,
        "datasets_created": 1,
        "ingestion_state": {"processed_files": 2, "failed_files": 0},
    }
    result.update(overrides)
    return result


class TestIngestionTriggerDispatch:
    """The manual run endpoint dispatches the dlt spine for flagged
    tenants — and keeps the Prefect path otherwise."""

    def _trigger(self, tenant, scheduled_ingestion):
        user = _mk_user(tenant)
        client = APIClient()
        client.force_authenticate(user=user)
        return client.post(
            f"/api/v1/scheduled-ingestions/{scheduled_ingestion.id}/trigger/",
            data={},
            format="json",
        )

    def test_trigger_dispatches_the_entrypoint_with_the_ingestion_row_id(self):
        tenant = _mk_tenant(flagged=True)
        scheduled_ingestion = _mk_ingestion(tenant)

        recorder = mock.Mock(return_value=_outcome())
        with mock.patch(_INGESTION_ENTRYPOINT, recorder):
            resp = self._trigger(tenant, scheduled_ingestion)

        assert resp.status_code == 200
        recorder.assert_called_once_with(str(scheduled_ingestion.id))
        run = ScheduledIngestionRun.objects.get(scheduled_ingestion=scheduled_ingestion)
        assert run.status == ScheduledIngestionRunStatus.COMPLETED, (
            "the run's terminal state records the dlt write outcome"
        )
        assert (run.result_json or {}).get("dlt_outcome", {}).get("files_processed") == 2

    def test_a_failing_outcome_marks_the_run_failed(self):
        tenant = _mk_tenant(flagged=True)
        scheduled_ingestion = _mk_ingestion(tenant)

        recorder = mock.Mock(return_value=_outcome(files_failed=2, files_processed=0))
        with mock.patch(_INGESTION_ENTRYPOINT, recorder):
            resp = self._trigger(tenant, scheduled_ingestion)

        assert resp.status_code == 200
        run = ScheduledIngestionRun.objects.get(scheduled_ingestion=scheduled_ingestion)
        assert run.status == ScheduledIngestionRunStatus.FAILED

    def test_trigger_keeps_the_prefect_path_when_not_flagged(self):
        tenant = _mk_tenant(flagged=False)
        scheduled_ingestion = _mk_ingestion(tenant)

        recorder = mock.Mock()
        deployment = mock.Mock(return_value=(True, "fr-legacy", None))
        with (
            mock.patch(_INGESTION_ENTRYPOINT, recorder),
            mock.patch(_DEPLOYMENT_TRIGGER, deployment),
        ):
            resp = self._trigger(tenant, scheduled_ingestion)

        recorder.assert_not_called(), "a non-flagged tenant must never dispatch the dlt entrypoint"
        assert deployment.called, "the legacy Prefect deployment path stays for non-flagged tenants"
        assert resp.status_code in (200, 201, 202)


class TestIngestionInternalRunCreateDispatch(TestCase):
    """The worker-run lifecycle (internal runs create) dispatches the
    same spine — with the no-double-dispatch idempotency contract."""

    def setUp(self):
        self.tenant = _mk_tenant(flagged=True)
        self.user = _mk_user(self.tenant)
        self.scheduled_ingestion = _mk_ingestion(self.tenant)
        self.client = APIClient()
        worker_key = _create_worker_api_key(self.tenant, self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {worker_key}",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _post_run(self, **payload):
        body = {"scheduled_ingestion_id": str(self.scheduled_ingestion.id), **payload}
        return self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            data=body,
            format="json",
        )

    def test_the_internal_run_create_dispatches_for_a_flagged_tenant(self):
        recorder = mock.Mock(return_value=_outcome())
        with mock.patch(_INGESTION_ENTRYPOINT, recorder):
            resp = self._post_run(idempotency_key=f"ik-{uuid.uuid4().hex}")

        assert resp.status_code in (200, 201, 202)
        recorder.assert_called_once_with(str(self.scheduled_ingestion.id))
        run = ScheduledIngestionRun.objects.get(scheduled_ingestion=self.scheduled_ingestion)
        assert run.status == ScheduledIngestionRunStatus.COMPLETED

    def test_the_idempotent_replay_never_double_dispatches(self):
        key = f"ik-{uuid.uuid4().hex}"
        recorder = mock.Mock(return_value=_outcome())
        with mock.patch(_INGESTION_ENTRYPOINT, recorder):
            first = self._post_run(idempotency_key=key)
            second = self._post_run(idempotency_key=key)

        assert first.status_code in (200, 201)
        assert second.status_code == 200
        assert recorder.call_count == 1, (
            "the replay must return the existing run, never re-dispatch"
        )
