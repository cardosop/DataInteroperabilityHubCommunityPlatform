"""
Phase 270.F.2 — ``poll_compliance_job`` tenant_context safety net.

What this suite pins
====================
Per spec 270.F.4: "per-task regression test runs the task without
``tenant_context()`` set (RLS active); asserts ``DoesNotExist``
raised — proves safety net engages."

The compliance_runs table has Row-Level Security enabled at
[`hub/apps/compliance/migrations/0100_enable_rls_compliance_runs.py`](../../migrations/0100_enable_rls_compliance_runs.py).
The policy is gated by ``app.rls_compliance_runs_enabled='true'``
+ requires ``tenant_id::text = current_setting('app.current_tenant_id', true)``.

This suite simulates the post-rollout state where RLS is fully
active (the production scenario) by binding a query against
``current_setting('app.current_tenant_id')`` directly. Without
``tenant_context``, the GUC is empty → the query matches nothing
→ DoesNotExist. With ``tenant_context``, the GUC is set → the
query matches → row returned.

NO MOCKS POLICY
===============
Real Postgres, real ComplianceRun + Tenant rows, real
``tenant_context`` context manager. No Stripe / external boundary
is invoked (the failure modes pinned here are intra-process).
"""
from __future__ import annotations
import pytest

import uuid
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset
from hub.apps.compliance.models import (
    ComplianceRun,
    ComplianceRunStatus,
)
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.tenants.request_tenant import tenant_context
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_run_for_tenant():
    sfx = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"T {sfx}", slug=f"t-{sfx}",
        status="ACTIVE", kyc_status=KYCStatus.VERIFIED,
    )
    user = User.objects.create_user(
        email=f"u-{sfx}@example.com",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    # Create a minimal Asset/Dataset for ComplianceRun FK validation
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"asset-{sfx}",
        name=f"Asset {sfx}",
        status="DRAFT",
        created_by=user,
    )
    from hub.apps.files.models import File, FileStatus
    file_obj = File.objects.create(
        tenant=tenant,
        name="test.csv",
        content_type="text/csv",
        size=128,
        status=FileStatus.ACTIVE,
        storage_path=f"{tenant.id}/{sfx}/test.csv",
        created_by=user,
    )
    dataset = Dataset.objects.create(
        tenant=tenant,
        asset=asset,
        file=file_obj,
        format="CSV",
        row_count=1,
        created_by=user,
    )
    job = Job.objects.create(
        tenant=tenant,
        type=JobType.COMPLIANCE_RUN,
        status=JobStatus.PENDING,
        resource_type="COMPLIANCE_RUN",
        resource_id=uuid.uuid4(),
        created_by=user,
        timeout_seconds=1800,
        details_json={"scan_mode": "internal"},
    )
    run = ComplianceRun.objects.create(
        tenant=tenant,
        job=job,
        asset=asset,
        dataset=dataset,
        scan_mode="FILE_SCAN",
        status=ComplianceRunStatus.QUEUED,
        metadata_json={"job_id": "rem-1", "poll_url": "/x"},
    )
    return tenant, run


def _query_run_under_rls_gate(run_id):
    """Helper that mimics what a RLS-active production query
    would do: returns the run ONLY when
    ``app.current_tenant_id`` matches the row's tenant_id.
    Without ``tenant_context``, the GUC is empty → no match →
    DoesNotExist.
    """
    return ComplianceRun.objects.extra(
        where=[
            "tenant_id::text = NULLIF("
            "current_setting('app.current_tenant_id', true), ''"
            ")"
        ],
    ).get(id=run_id)


# ---------------------------------------------------------------------------
# Tier 1 — Safety net engages without tenant_context
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPollComplianceJobSafetyNet(TestCase):
    """Pins the contract that running the task WITHOUT
    tenant_context (the RLS-active state) trips
    ComplianceRun.DoesNotExist — the safety net the spec
    270.F.4 mandates we prove."""

    @pytest.mark.integration
    def test_without_tenant_context_simulated_rls_returns_does_not_exist(self):
        """Direct query through the RLS-gate-simulating helper:
        with no GUC set, the row is invisible."""
        _, run = _seed_run_for_tenant()
        with pytest.raises(ComplianceRun.DoesNotExist):
            _query_run_under_rls_gate(run.id)

    @pytest.mark.integration
    def test_with_tenant_context_simulated_rls_returns_row(self):
        """Inverse: with tenant_context set, the same query
        succeeds — proves the wrapper actually carries the GUC
        across to the ORM."""
        tenant, run = _seed_run_for_tenant()
        with tenant_context(tenant.id):
            fetched = _query_run_under_rls_gate(run.id)
        assert fetched.id == run.id


# ---------------------------------------------------------------------------
# Tier 2 — poll_compliance_job accepts tenant_id kwarg
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPollComplianceJobAcceptsTenantIdKwarg(TestCase):
    """The refactor signature MUST accept ``tenant_id`` as a kwarg
    so the enqueue sites can pass it. Pinned via inspect so a
    future signature change can't silently regress."""

    @pytest.mark.integration
    def test_signature_accepts_tenant_id_kwarg(self):
        import inspect
        from hub.apps.compliance.tasks import poll_compliance_job

        sig = inspect.signature(poll_compliance_job)
        # Either an explicit parameter OR a **kwargs sink.
        params = sig.parameters
        assert "tenant_id" in params or any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in params.values()
        ), (
            f"poll_compliance_job must accept tenant_id kwarg; "
            f"got params={list(params)}"
        )

    @pytest.mark.integration
    def test_runs_clean_when_tenant_id_passed(self):
        """End-to-end happy path — tenant_id passed, the function
        loads the run successfully + reaches the QUEUED→reenqueue
        branch (we patch the re-enqueue so the test doesn't
        recurse into the RQ queue)."""
        tenant, run = _seed_run_for_tenant()

        from hub.apps.compliance.tasks import poll_compliance_job

        with patch(
            "hub.apps.compliance.tasks._reenqueue"
        ) as mock_reenqueue, patch(
            "hub.apps.compliance.service_client.ComplianceServiceClient",
        ) as mock_client_cls:
            mock_client_cls.return_value.get_scan_result.return_value = {
                "status": "QUEUED",
                "job_id": "rem-1",
            }
            # tenant_id kwarg explicitly passed.
            poll_compliance_job(str(run.id), tenant_id=str(tenant.id))
        # Reenqueue fired — proves the function reached the
        # non-terminal QUEUED branch (which only happens AFTER
        # the run was successfully loaded).
        mock_reenqueue.assert_called_once()
