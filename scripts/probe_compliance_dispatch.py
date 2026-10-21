#!/usr/bin/env python3
"""P0-6 (close-oss-release-conditions, ticket W105-COMPLIANCE-DISPATCH-
ENQUEUE) — the compliance-dispatch end-to-end probe.

Runs in a FRESH process (no pytest transaction wrapper), against the
REAL stack: the autocommit dispatch shape the worker-side callers use
(intake scan, dlt catalog records) MUST land the job on the RQ queue
immediately; the atomic shape MUST land it after the commit. Exits 0
only when both land and the cleanup completes — the D2 failure shape
(PENDING row + empty queue) exits non-zero.

Inherits the environment (the Django test job's env block); writes
probe rows with a unique slug and removes them again — safe to run
against a shared test DB.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

# Force (not setdefault): the pytest parent may export an empty
# DJANGO_SETTINGS_MODULE; and put the repo root on sys.path so the
# `hub` package resolves regardless of the invocation cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "hub.settings"

import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction

from hub.apps.assets.models import Asset
from hub.apps.compliance.services import ComplianceService
from hub.apps.jobs.utils import get_queue, get_queue_for_job_type
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus


def _find_job(job_id: str):
    """The enqueued job, wherever it currently sits: the queue (normal),
    the started registry, or the failed registry (a live worker may
    consume the probe job between the enqueue and the inspection — the
    contract is that the job LEFT the PENDING-only state, i.e. the
    enqueue happened)."""
    from hub.apps.jobs.models import JobType

    queue = get_queue(get_queue_for_job_type(JobType.COMPLIANCE_RUN))
    for job in list(queue.jobs):
        if job.args and job.args[0] == job_id:
            return job
    for registry in (queue.failed_job_registry, queue.started_job_registry):
        for rq_id in registry.get_job_ids():
            job = queue.fetch_job(rq_id)
            if job is not None and job.args and job.args[0] == job_id:
                return job
    return None


def _cleanup_queue_job(job_id: str) -> None:
    job = _find_job(job_id)
    if job is not None:
        job.delete()


def _dispatch(tenant, user, asset, *, inside_atomic: bool):
    service = ComplianceService(tenant_id=str(tenant.id), user_id=str(user.id))
    if inside_atomic:
        with transaction.atomic():
            run = service.create_compliance_run(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                asset_id=str(asset.id),
                scan_mode="internal",
                tenant=tenant,
                user=user,
                asset=asset,
            )
            if _find_job(str(run.job.id)) is not None:
                raise SystemExit("FAIL: enqueued BEFORE the commit — the atomic shape leaked")
    else:
        run = service.create_compliance_run(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
            tenant=tenant,
            user=user,
            asset=asset,
        )
    if _find_job(str(run.job.id)) is None:
        raise SystemExit(
            "FAIL: the job is NOT on the RQ queue — PENDING-forever orphan (D2 signature)"
        )
    _cleanup_queue_job(str(run.job.id))
    return run


def main() -> int:
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"probe-dispatch-{uid}",
        slug=f"probe-dispatch-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    try:
        ensure_tenant_has_active_subscription(tenant)
        user = get_user_model().objects.create_user(
            email=f"probe-dispatch-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"probe-dispatch-{uid}",
            name="Probe Dispatch Asset",
            created_by=user,
        )
        _dispatch(tenant, user, asset, inside_atomic=False)
        _dispatch(tenant, user, asset, inside_atomic=True)
        print("PROBE-COMPLIANCE-DISPATCH OK: autocommit + atomic dispatches land on the queue")
        return 0
    finally:
        # Reverse-FK order cleanup: runs -> job rows -> asset -> user -> tenant.
        from hub.apps.compliance.models import ComplianceRun
        from hub.apps.jobs.models import Job

        ComplianceRun.objects.filter(tenant=tenant).delete()
        Job.objects.filter(tenant=tenant).delete()
        Asset.objects.filter(tenant=tenant).delete()
        tenant.users.all().delete()
        tenant.delete()


if __name__ == "__main__":
    sys.exit(main())
