"""Phase 2.6 — check_limit serialization pin (deterministic, no mocks).

``PlanLimitService.check_limit`` serializes concurrent same-tenant checks on
the TENANT-row ``select_for_update`` so the counter read + decision are
atomic (the counter race: two requests read count=9 with limit=10 and both
proceed → 11 resources). The lock is load-bearing even though version
allocation no longer depends on it (313.H.5 moved that to the asset row).

The pin: the test holds the tenant-row EXCLUSIVE lock on its own connection
(explicit transaction) and runs two REAL ``check_limit`` calls in threads.
If the service's own lock exists, both threads BLOCK behind the test lock
and neither completes while it is held (join-with-timeout stays alive). If
the lock is ever removed, the counter read is a plain SELECT and both
threads finish immediately — the assertion fails. Deterministic either way:
the observable is WHERE the threads block, not how long.

Dependency chain (documented per the task): check_limit → tenant-row lock
→ get_resource_count (billing.limit_registry) → create-flow call sites that
rely on the atomic read-and-decide.
"""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import DatabaseError, connection, connections

from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.tenants.models import Tenant, TenantPlan
from hub.apps.tenants.services import PlanLimitService

pytestmark = pytest.mark.django_db(transaction=True)


def test_check_limit_serializes_on_tenant_row_lock():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(name=f"Limit {uid}", slug=f"limit-{uid}", status="ACTIVE")
    plan = TenantPlan.objects.create(
        name=f"Limit Plan {uid}",
        slug=f"limit-plan-{uid}",
        tier="PRO",
        is_active=True,
        limits_json={"max_assets": 10},
    )
    tenant.plan = plan
    tenant.save(update_fields=["plan"])

    results: list[dict] = []
    errors: list[Exception] = []
    lock = threading.Lock()
    entered = threading.Event()

    def worker(barrier: threading.Barrier) -> None:
        connections["default"].close()
        try:
            barrier.wait(timeout=60)
            entered.set()
            service = PlanLimitService()
            result = service.check_limit(str(tenant.id), "max_assets")
            with lock:
                results.append(result)
        except (threading.BrokenBarrierError, DatabaseError, ValidationError, NotFoundError) as exc:
            with lock:
                errors.append(exc)
        finally:
            connections["default"].close()

    # Hold the tenant-row lock on the test's own connection.
    connection.set_autocommit(False)
    futures = []
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT id FROM {Tenant._meta.db_table} WHERE id = %s FOR UPDATE",
            [str(tenant.pk)],
        )
        cursor.fetchone()

        barrier = threading.Barrier(2)
        # The executor must NOT wrap the release — its with-block exit waits
        # for the blocked futures, so the lock would never be released
        # (verified deadlock). Release INSIDE the scope instead.
        executor = ThreadPoolExecutor(max_workers=2)
        futures = [executor.submit(worker, barrier) for _ in range(2)]
        assert entered.wait(timeout=30), "workers never entered the service"

        # THE PIN: while the test holds the tenant lock, neither worker
        # may complete — the service's own select_for_update must queue
        # behind it. If the lock were removed, the counter read would
        # not block and both futures would finish here.
        import concurrent.futures as cf

        for future in futures:
            with pytest.raises(cf.TimeoutError):
                future.result(timeout=0.5)

        # Release the test-held lock while the workers are still queued.
        connection.commit()
        connection.set_autocommit(True)
        for future in futures:
            future.result(timeout=120)
    finally:
        if not connection.get_autocommit():
            connection.commit()
            connection.set_autocommit(True)
        executor.shutdown(wait=True)

    assert errors == [], errors
    assert len(results) == 2
    assert all(r["allowed"] is True for r in results), results
    assert all(r["max"] == 10 for r in results), results
