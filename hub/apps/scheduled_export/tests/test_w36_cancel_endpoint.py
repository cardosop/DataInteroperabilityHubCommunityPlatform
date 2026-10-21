"""W3.6 (oss-release-remediation R2-P4/F13) — the internal cancel
endpoint for scheduled export runs.

Mirror of the ingestion cancel action: the guarded matrix admits
PENDING/RUNNING → CANCELLED (W3.1) and the export worker honours
CANCELLED — the endpoint exposes the semantic action.

Pins (real DB + the real internal API; no mocks): RUNNING → CANCELLED;
a terminal run cannot be cancelled (400 INVALID_TRANSITION); a foreign
tenant's run is invisible (403); unauthenticated → 401/403.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.auth.models import APIKey
from hub.apps.scheduled_export.internal_auth import SCOPE_SCHEDULED_EXPORT_INTERNAL
from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class ExportCancelEndpointTest(TestCase):
    def setUp(self):
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W36 Exp Cancel Tenant {unique}",
            slug=f"w36-exp-cancel-tenant-{unique}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"w36-exp-cancel-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.scheduled_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name=f"W36 Cancel Export {unique}",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
            status=ScheduledExportStatus.ACTIVE,
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

    def _mk_run(self, run_status):
        return ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=run_status,
            started_at=timezone.now(),
        )

    def _cancel(self, run_id):
        return self.client.post(
            f"/api/v1/scheduled-exports/internal/runs/{run_id}/cancel/",
            format="json",
        )

    def test_running_run_cancelled(self):
        run = self._mk_run(ScheduledExportRunStatus.RUNNING)

        resp = self._cancel(run.id)

        assert resp.status_code == status.HTTP_200_OK, resp.data
        run.refresh_from_db()
        assert run.status == ScheduledExportRunStatus.CANCELLED
        assert run.completed_at is not None, "the cancel stamps the terminal timestamp"

    def test_terminal_run_cannot_be_cancelled(self):
        run = self._mk_run(ScheduledExportRunStatus.COMPLETED)

        resp = self._cancel(run.id)

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["code"] == "INVALID_TRANSITION", resp.data
        run.refresh_from_db()
        assert run.status == ScheduledExportRunStatus.COMPLETED

    def test_foreign_tenant_run_invisible(self):
        other = Tenant.objects.create(
            name="W36 Exp Other Tenant",
            slug=f"w36-exp-other-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        foreign_export = ScheduledExport.objects.create(
            tenant=other,
            name="W36 Exp Foreign",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "other-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
            status=ScheduledExportStatus.ACTIVE,
        )
        foreign_run = ScheduledExportRun.objects.create(
            scheduled_export=foreign_export,
            tenant=other,
            status=ScheduledExportRunStatus.RUNNING,
            started_at=timezone.now(),
        )

        resp = self._cancel(foreign_run.id)

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        foreign_run.refresh_from_db()
        assert foreign_run.status == ScheduledExportRunStatus.RUNNING

    def test_unauthenticated_cancel_rejected(self):
        run = self._mk_run(ScheduledExportRunStatus.RUNNING)
        anonymous = APIClient()
        anonymous.credentials(HTTP_X_TENANT_ID=str(self.tenant.id))

        resp = anonymous.post(
            f"/api/v1/scheduled-exports/internal/runs/{run.id}/cancel/",
            format="json",
        )

        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
        run.refresh_from_db()
        assert run.status == ScheduledExportRunStatus.RUNNING
