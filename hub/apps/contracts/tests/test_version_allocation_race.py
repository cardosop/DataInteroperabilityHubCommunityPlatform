"""
313.H.5.1 — deterministic concurrency regression: parallel same-asset
contract creates must not collide on ``unique_contract_version_per_asset``.

The bug: the version allocators read ``max(version)`` for the asset
with a plain aggregate, allocate ``max + 1``, and INSERT. Two
concurrent creates read the same max → the second INSERT violates the
constraint → ``IntegrityError`` → 500. The fix (313.H.5.2) serializes
the allocation on the ASSET row (``select_for_update``) inside a
transaction at every allocation site.

Determinism lever (no stubs): the test holds an EXCLUSIVE lock on the
asset row on its OWN connection (an EXPLICIT transaction —
``set_autocommit(False)`` — a bare ``SELECT ... FOR UPDATE`` under
autocommit commits instantly and holds nothing) while both threads
(one barrier) run the REAL service:

* Pre-fix (create_odps): the path takes no asset lock — both threads
  read the same max, both INSERT the same version. The asset FK is
  DEFERRABLE INITIALLY DEFERRED, so the FK existence check (FOR KEY
  SHARE) runs at COMMIT, which QUEUES behind the test-held exclusive
  lock. On release one create commits and the other's unique probe
  sees the committed row → deterministic IntegrityError (red).
* Post-fix: the service's ``select_for_update()`` on the asset row
  queues BEHIND the test lock instead. On release, thread A allocates
  and commits, thread B then reads the new max → deterministic green
  with contiguous versions.

``create_contract`` is covered as the second entry point: pre-fix it
was INCIDENTALLY serialized by the plan-limit check's tenant-row lock;
post-fix it is explicitly serialized on the asset (no reliance on the
limit-check side effect).

NO MOCKS: real Postgres, real threads, real service, real ORM. The
only "test" construct is the row lock — a legitimate concurrency
primitive, not a stub of production code.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, connections

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, OriginalFormat, OriginalSpecType
from hub.apps.contracts.services.contract_service import ContractService, ODPSService
from hub.apps.tenants.models import Tenant, TenantPlan
from hub.apps.tenants.tests.factories import SubscriptionFactory

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

TOTAL_CONTRACTS = 2


def _payload(index: int) -> str:
    return json.dumps(
        {
            "id": f"race-contract-{index}",
            "name": f"Race Contract {index}",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": f"field_{index}", "type": "string"},
                ],
            },
        }
    )


def _odps_payload(index: int) -> str:
    """A distinct minimal ODPS 4.1 document per participant."""
    return json.dumps(
        {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"race-odps-{index}",
                        "name": f"Race ODPS {index}",
                        "description": "Race test",
                    }
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }
    )


def _setup_tenant_and_asset():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Race {uid}",
        slug=f"race-{uid}",
        status="ACTIVE",
    )
    plan = TenantPlan.objects.create(
        name=f"Race Plan {uid}",
        slug=f"race-plan-{uid}",
        tier="PRO",
        is_active=True,
        limits_json={"max_contracts": 1000},
    )
    # PlanLimitService resolves limits from ``tenant.plan``.
    tenant.plan = plan
    tenant.save(update_fields=["plan"])
    SubscriptionFactory.create_subscription(tenant=tenant, plan=plan)
    user = User.objects.create_user(
        email=f"race-{uid}@meshant.test",
        password="testpass",
        tenant=tenant,
    )
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"race-asset-{uid}",
        name="Race Asset",
        status=AssetStatus.ACTIVE,
        created_by=user,
    )
    return tenant, user, asset


def _run_concurrent_creates(
    create_callable,
) -> tuple[list[int], list[Exception]]:
    """Run TOTAL_CONTRACTS concurrent creates through ``create_callable``
    while the test holds the asset-row lock. Returns (versions, errors)."""
    versions: list[int] = []
    errors: list[Exception] = []
    lock = threading.Lock()
    entered = threading.Event()

    def worker(barrier: threading.Barrier, index: int) -> None:
        # Close ONLY this thread's connection — ``connections.close_all()``
        # would also close the MAIN thread's connection that holds the
        # asset-row lock, silently releasing it and destroying the
        # determinism lever.
        connections["default"].close()
        try:
            barrier.wait(timeout=60)
            entered.set()
            contract = create_callable(index)
            with lock:
                versions.append(contract.version)
        except Exception as exc:
            with lock:
                errors.append(exc)
        finally:
            connections["default"].close()

    barrier = threading.Barrier(TOTAL_CONTRACTS)
    with ThreadPoolExecutor(max_workers=TOTAL_CONTRACTS) as executor:
        futures = [executor.submit(worker, barrier, i) for i in range(TOTAL_CONTRACTS)]
        # Both threads have entered the service and are racing toward the
        # allocation; give them time to reach the blocking point, then
        # release the asset-row lock.
        assert entered.wait(timeout=30), "workers never entered the service"
        time.sleep(1.0)  # noqa: sleep-needed — test timing requirement  # INTENTIONAL: sleep-needed (auto-fixer marker completion)
        connection.commit()  # Release the test-held asset row lock
        for future in futures:
            future.result(timeout=120)
    return versions, errors


def _run_locked(asset: Asset, create_callable):
    """Hold the asset-row lock (explicit transaction on the test's own
    connection) and run the concurrent creates."""
    # ``set_autocommit(False)`` opens a REAL transaction: under
    # autocommit the FOR UPDATE would commit at statement end and
    # release the lock immediately (verified against pg_locks).
    connection.set_autocommit(False)
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT id FROM {Asset._meta.db_table} WHERE id = %s FOR UPDATE",
            [str(asset.pk)],
        )
        cursor.fetchone()
        return _run_concurrent_creates(create_callable)
    finally:
        connection.commit()
        connection.set_autocommit(True)


def _assert_contiguous(asset: Asset, versions: list[int], errors: list[Exception]):
    assert errors == [], (
        f"{len(errors)} of {TOTAL_CONTRACTS} parallel creates failed — "
        f"the version allocation raced. First error: {errors[0]!r}"
    )
    assert sorted(versions) == list(range(1, TOTAL_CONTRACTS + 1)), (
        f"versions must be contiguous 1..{TOTAL_CONTRACTS}; got {sorted(versions)}"
    )
    assert Contract.objects.filter(asset=asset).count() == TOTAL_CONTRACTS


def test_parallel_create_contract_calls_allocate_contiguous_versions():
    """create_contract: pre-fix incidentally serialized by the plan-limit
    tenant lock; post-fix explicitly serialized on the asset row."""
    tenant, user, asset = _setup_tenant_and_asset()

    def create(index: int) -> Contract:
        return ContractService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        ).create_contract(
            original_raw=_payload(index),
            original_format=OriginalFormat.JSON,
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            asset_id=str(asset.id),
            original_spec_type=OriginalSpecType.ODCS,
        )

    versions, errors = _run_locked(asset, create)
    _assert_contiguous(asset, versions, errors)


def test_parallel_create_odps_calls_allocate_contiguous_versions():
    """create_odps: no plan-limit tenant lock on this path — pre-fix the
    allocation raced (deterministic IntegrityError under the lever);
    post-fix the atomic + asset-row lock serializes it."""
    tenant, user, asset = _setup_tenant_and_asset()

    def create(index: int) -> Contract:
        return ODPSService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        ).create_odps(
            odps_raw=_odps_payload(index),
            odps_format="json",
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            asset_id=str(asset.id),
        )

    versions, errors = _run_locked(asset, create)
    _assert_contiguous(asset, versions, errors)
