"""P0-6 (close-oss-release-conditions, ticket W105-COMPLIANCE-DISPATCH-ENQUEUE)
— the compliance-dispatch end-to-end pins.

The D2 crash drill observed COMPLIANCE_RUN Job rows created PENDING with
EMPTY RQ queues: the dispatch path registered the enqueue ONLY on
``transaction.on_commit``, and the worker-side callers (intake scan,
dlt catalog records) run OUTSIDE any atomic block — where on_commit
callbacks never fire. The row then sits PENDING forever with no worker
to pick it up.

The pytest transaction wrapper atomics EVERY alias, so the queue-side
landing is unobservable inside the test process — the real-stack probe
(``scripts/probe_compliance_dispatch.py``, the W11.9 real-boot pattern)
runs in a FRESH process and proves both shapes land on the REAL RQ
queue (RED against the pre-fix code: the probe exits non-zero with the
D2 signature). This module pins:

* the service dispatch persists the PENDING run with its job linkage
  (observable in-process);
* the subprocess probe exits 0 — autocommit dispatch lands immediately
  AND the atomic dispatch lands after its commit.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model

from hub.apps.assets.models import Asset
from hub.apps.compliance.models import ComplianceRunStatus
from hub.apps.compliance.services import ComplianceService
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

# default django_db (atomic + rollback, NO table truncation): the
# TransactionTestCase flush takes ACCESS EXCLUSIVE table locks and
# collides with sibling sessions on the shared test DB — the rollback
# shape is collision-free and this module needs no cross-test commits.
pytestmark = pytest.mark.django_db

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
PROBE = REPO_ROOT / "scripts" / "probe_compliance_dispatch.py"


def _seed_tenant_user_asset():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"probe-tenant-{uid}",
        slug=f"probe-tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    user = get_user_model().objects.create_user(
        email=f"probe-user-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"probe-asset-{uid}",
        name="Probe Asset",
        created_by=user,
    )
    return tenant, user, asset


def test_service_dispatch_persists_the_run_and_job_linkage():
    """The service-level contract observable in-process: the dispatch
    persists a PENDING run whose job row points back at the run."""
    tenant, user, asset = _seed_tenant_user_asset()
    service = ComplianceService(
        tenant_id=str(tenant.id),
        user_id=str(user.id),
    )
    run = service.create_compliance_run(
        tenant_id=str(tenant.id),
        user_id=str(user.id),
        asset_id=str(asset.id),
        scan_mode="internal",
        tenant=tenant,
        user=user,
        asset=asset,
    )
    assert run.status == ComplianceRunStatus.PENDING
    assert run.job is not None
    assert run.job.resource_id == str(run.id)
    assert run.job.details_json.get("compliance_run_id") == str(run.id)


def test_real_process_probe_lands_both_dispatch_shapes_on_the_queue():
    """The D2 contract, proven in a FRESH process (no pytest wrapper):
    autocommit dispatch lands immediately and the atomic dispatch lands
    after its commit — both on the REAL RQ queue. The probe cleans up
    its rows and queue jobs; its exit code is the assertion."""
    env = dict(os.environ)
    # The probe must boot the REAL settings shape: the inherited TESTING /
    # PYTEST_CURRENT_TEST markers activate the test-mode inline job
    # processor, which consumes enqueued jobs synchronously and removes
    # them from the queue — the probe's own queue inspection would then
    # race an invisible consumer. A fresh process with the markers
    # removed runs the production dispatch path.
    env.pop("TESTING", None)
    env.pop("PYTEST_CURRENT_TEST", None)
    # The probe's row cleanup rides post-delete signals that bump the
    # CACHE redis — settings fail hard on cache errors, and the
    # host-side recipe's cache URL may point at a stack that is down.
    # Point the probe's cache at the (proven-reachable) REDIS_URL
    # instance: the probe only needs the bumps to not crash the
    # cleanup, never the cache contents.
    if os.environ.get("REDIS_URL"):
        env["REDIS_CACHE_URL"] = os.environ["REDIS_URL"]
    result = subprocess.run(
        [sys.executable, str(PROBE)],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
    )
    assert result.returncode == 0, (
        "probe_compliance_dispatch.py failed:\n"
        + result.stdout[-2000:]
        + result.stderr[-2000:]
    )
