"""P0-1 battery finding (2026-10-18) — the shared worker run lifecycle's
audit emission was silently broken.

``start_run`` / ``complete_run`` / ``fail_run`` called
``create_audit_event(..., tenant_id=...)`` — a kwarg the function does
not accept (its parameter is ``tenant``). The bare-except audit guard
swallowed the TypeError, so every SCHEDULED_RUN audit row silently
failed to emit. The same kwarg bug was found by the semantic suite's
SSRF-audit pin on the query-time SSRF block path
(``SPARQL_FEDERATION_SSRF_BLOCKED``) — one root cause, two surfaces,
both fixed in P0-1 (the utility now also accepts a raw tenant id,
assigning the FK via ``tenant_id=``).

These pins drive the REAL functions against REAL Postgres rows and
assert one AuditEvent per transition with the right action/tenant —
the bug class must not silently regress. The best-effort contract
(an audit-store failure never blocks the run outcome) is pinned too.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from hub.apps.audit.models import AuditEvent
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


class TestWorkerRunLifecycleAudit:
    """The SCHEDULED_RUN audit rows land, per transition, per tenant."""

    def _context(self):
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"WRL Tenant {uid}",
            slug=f"wrl-tenant-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.UNVERIFIED,
        )
        ensure_tenant_has_active_subscription(tenant)
        user = User.objects.create_user(
            email=f"wrl-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status="ACTIVE",
        )
        ingestion = ScheduledIngestion.objects.create(
            tenant=tenant,
            name=f"WRL Ingest {uid}",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket", "region": "us-east-1"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "02:00", "timezone": "UTC"},
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=user,
            next_run_at=timezone.now(),
        )
        run_instance = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=ingestion,
            status=ScheduledIngestionRunStatus.PENDING,
        )
        return tenant, run_instance

    def _audit_rows(self, tenant, action: str):
        return list(
            AuditEvent.objects.filter(
                tenant=tenant,
                action=action,
                resource_type="SCHEDULED_RUN",
            ).order_by("timestamp")
        )

    def test_start_run_emits_one_started_audit_row(self):
        from hub.data_movement.worker_run_lifecycle import start_run

        tenant, run_instance = self._context()
        outcome = start_run(
            run_instance,
            job_id=str(uuid.uuid4()),
            tenant_id=str(tenant.id),
            direction="export",
        )

        assert outcome["status"] == "RUNNING"
        rows = self._audit_rows(tenant, "EXPORT_RUN_STARTED")
        assert len(rows) == 1, "exactly one STARTED audit row per transition"
        assert str(rows[0].resource_id) == str(run_instance.id)
        assert rows[0].result == "SUCCESS"

    def test_complete_run_emits_one_completed_audit_row(self):
        from hub.data_movement.worker_run_lifecycle import complete_run

        tenant, run_instance = self._context()
        outcome = complete_run(
            run_instance,
            job_id=str(uuid.uuid4()),
            tenant_id=str(tenant.id),
            direction="export",
            result={"files": 3},
        )

        assert outcome["status"] == "COMPLETED"
        rows = self._audit_rows(tenant, "EXPORT_RUN_COMPLETED")
        assert len(rows) == 1
        assert str(rows[0].resource_id) == str(run_instance.id)

    def test_fail_run_emits_one_failed_audit_row(self):
        from hub.data_movement.worker_run_lifecycle import fail_run

        tenant, run_instance = self._context()
        outcome = fail_run(
            run_instance,
            job_id=str(uuid.uuid4()),
            tenant_id=str(tenant.id),
            direction="export",
            error="destination down",
        )

        assert outcome["status"] == "FAILED"
        rows = self._audit_rows(tenant, "EXPORT_RUN_FAILED")
        assert len(rows) == 1
        assert rows[0].result == "FAILURE"

    def test_an_audit_store_failure_never_blocks_the_outcome(self, monkeypatch):
        """The best-effort contract: the run outcome is reported even
        when the audit store fails (the bare-except guard's ONLY job —
        never a blanket for wrong kwargs, which the pins above catch)."""
        from hub.data_movement import worker_run_lifecycle

        tenant, run_instance = self._context()

        def _explode(*args, **kwargs):
            raise RuntimeError("audit store down")

        monkeypatch.setattr(worker_run_lifecycle, "create_audit_event", _explode)
        outcome = worker_run_lifecycle.complete_run(
            run_instance,
            job_id=str(uuid.uuid4()),
            tenant_id=str(tenant.id),
            direction="export",
        )

        assert outcome["status"] == "COMPLETED"
        assert not self._audit_rows(tenant, "EXPORT_RUN_COMPLETED"), (
            "nothing was written — but the outcome still reported"
        )
