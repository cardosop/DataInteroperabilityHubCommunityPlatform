"""P7 (openspec add-databricks-cost-guardrails task 7.8) — the
management-command pins (the 7.3 review's gap #2: the command was
described but unpinned): the admin-DB discovery + one PENDING
DATABRICKS_COST_SYNC job per tenant under that tenant's tenant_context.

NO MOCKS: real Postgres rows (tenants/workspaces/jobs) over the admin +
default DB aliases; the command runs for real via call_command.
"""

from __future__ import annotations

import uuid

import pytest
from django.core.management import call_command

from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksWorkspace,
    DatabricksWorkspaceStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"cmd-{uid}",
        slug=f"cmd-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_workspace(tenant, *, status=DatabricksWorkspaceStatus.ACTIVE):
    return DatabricksWorkspace.objects.bulk_create(
        [
            DatabricksWorkspace(
                tenant=tenant,
                name=f"ws-{uuid.uuid4().hex[:8]}",
                host="dbc-fixture.cloud.databricks.com",
                cloud=DatabricksCloud.AWS,
                region="us-east-1",
                status=status,
            )
        ]
    )[0]


class TestCostSyncCommand:
    def test_the_dry_run_lists_only_tenants_with_active_workspaces(self, capsys):
        active_tenant = _mk_tenant()
        _mk_workspace(active_tenant, status=DatabricksWorkspaceStatus.ACTIVE)
        disabled_tenant = _mk_tenant()
        _mk_workspace(disabled_tenant, status=DatabricksWorkspaceStatus.DISABLED)
        bare_tenant = _mk_tenant()  # no workspaces at all

        result = call_command("databricks_cost_sync", "--dry-run")

        assert isinstance(result, str)
        listed = result.splitlines()
        assert str(active_tenant.id) in listed
        assert str(disabled_tenant.id) not in listed, "a DISABLED workspace never schedules a sync"
        assert str(bare_tenant.id) not in listed, "a tenant without workspaces never schedules"
        assert f"{len(listed)} tenant(s)" in capsys.readouterr().out

    def test_the_run_creates_one_pending_job_per_tenant(self, capsys):
        from unittest import mock

        from hub.apps.jobs.models import Job, JobStatus, JobType

        tenant = _mk_tenant()
        _mk_workspace(tenant)

        # The enqueue is the outbound boundary (the 4.4 convention): the
        # test env runs RQ SYNCHRONOUSLY (settings ASYNC=False), so the
        # recorder keeps the worker out — the pin asserts the command's
        # own contract: the job ROW + the enqueue, never the sync
        # execution (the 7.3 handler suite owns that).
        enqueued: list = []

        class _RecorderQueue:
            def enqueue(self, func, job_id=None, **kwargs):
                enqueued.append({"func": func, "job_id": job_id, "kwargs": kwargs})
                return mock.Mock()

        with mock.patch("hub.apps.jobs.utils.get_queue", return_value=_RecorderQueue()):
            call_command("databricks_cost_sync")

        job = Job.objects.get(tenant=tenant, type=JobType.DATABRICKS_COST_SYNC)
        assert job.status == JobStatus.PENDING
        assert job.resource_type == "TENANT"
        assert job.resource_id == tenant.id
        # The clone DB carries leaked fixture tenants from earlier failed
        # runs — the command legitimately discovers them ALL. The pin
        # scopes to THIS test's job row (leak-proof): exactly one
        # cost-sync dispatch for THIS tenant's job.
        own_enqueues = [e for e in enqueued if e["job_id"] == str(job.id)]
        assert len(own_enqueues) == 1, "exactly one worker dispatch for this tenant's job row"
        assert own_enqueues[0]["kwargs"].get("job_type") == JobType.DATABRICKS_COST_SYNC
        assert "DATABRICKS_COST_SYNC job(s)." in capsys.readouterr().out
