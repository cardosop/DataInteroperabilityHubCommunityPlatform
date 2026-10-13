"""W3.6 (oss-release-remediation R2-P4/F13) — the internal cancel
endpoint for scheduled ingestion runs.

The cancel action is the operator-facing half of the W3.1 machinery:
the guarded state matrix already admits PENDING/RUNNING → CANCELLED and
the worker already honours CANCELLED — the endpoint exposes that as a
semantic, worker-authenticated action with the matrix as the guardrail.

Pins (real DB + the real internal API; no mocks):

  * RUNNING → CANCELLED (200, row CANCELLED, completed_at stamped).
  * PENDING → CANCELLED (the never-picked-up run).
  * A terminal run (COMPLETED) cannot be cancelled — 400
    INVALID_TRANSITION (the guarded matrix speaks).
  * A foreign tenant's run is invisible — 403.
  * No worker credentials — 401.
"""

from __future__ import annotations

import uuid

import pytest
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

pytestmark = pytest.mark.django_db(transaction=True)


class IngestionCancelEndpointTest(TestCase):
    def setUp(self):
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W36 Cancel Tenant {unique}",
            slug=f"w36-cancel-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w36-cancel-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name=f"W36 Cancel Ingestion {unique}",
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

    def _mk_run(self, run_status):
        return ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=run_status,
            started_at=timezone.now(),
        )

    def _cancel(self, run_id):
        return self.client.post(
            f"/api/v1/scheduled-ingestions/internal/runs/{run_id}/cancel/",
            format="json",
        )

    def test_running_run_cancelled(self):
        run = self._mk_run(ScheduledIngestionRunStatus.RUNNING)

        resp = self._cancel(run.id)

        assert resp.status_code == status.HTTP_200_OK, resp.data
        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.CANCELLED
        assert run.completed_at is not None, "the cancel stamps the terminal timestamp"

    def test_pending_run_cancelled(self):
        run = self._mk_run(ScheduledIngestionRunStatus.PENDING)

        resp = self._cancel(run.id)

        assert resp.status_code == status.HTTP_200_OK, resp.data
        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.CANCELLED

    def test_terminal_run_cannot_be_cancelled(self):
        run = self._mk_run(ScheduledIngestionRunStatus.COMPLETED)

        resp = self._cancel(run.id)

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["code"] == "INVALID_TRANSITION", resp.data
        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.COMPLETED, (
            "a terminal run must never be reopened by the cancel action"
        )

    def test_foreign_tenant_run_invisible(self):
        other = Tenant.objects.create(
            name="W36 Other Tenant",
            slug=f"w36-other-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        foreign_ingestion = ScheduledIngestion.objects.create(
            tenant=other,
            name="W36 Foreign",
            source_type=SourceType.S3,
            source_config={"bucket": "other-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*",
            created_by=None,
        )
        foreign_run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=foreign_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=timezone.now(),
        )

        resp = self._cancel(foreign_run.id)

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        foreign_run.refresh_from_db()
        assert foreign_run.status == ScheduledIngestionRunStatus.RUNNING

    def test_unauthenticated_cancel_rejected(self):
        run = self._mk_run(ScheduledIngestionRunStatus.RUNNING)
        anonymous = APIClient()
        anonymous.credentials(HTTP_X_TENANT_ID=str(self.tenant.id))

        resp = anonymous.post(
            f"/api/v1/scheduled-ingestions/internal/runs/{run.id}/cancel/",
            format="json",
        )

        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
        run.refresh_from_db()
        assert run.status == ScheduledIngestionRunStatus.RUNNING
