"""TDD pins for the per-tenant SQL-warehouse connection pool (openspec
add-databricks-sql-warehouses task 3.5) — the D4 hard-isolation design.

The pool is keyed per (tenant, warehouse); connections are NEVER shared
across tenants — the registry is tenant-keyed AND the hand-out
re-checks the tenant on every borrow (entry-level + the connection's
own tenant marker). A tenant's exhaustion is bound by a PER-TENANT
semaphore (the 0.11 pattern, applied to pools): tenant A at capacity
can never affect tenant B's borrows. Idle connections are reaped on a
timer (a daemon reaper thread + a deterministic ``reap()`` sweep).

No mocks: REAL threads (concurrency pins), a REAL connection stand-in
with a real ``close()`` (the pool is generic over the factory — the
in-process structure IS the surface under test), and real time-based
reaper behavior.
"""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = pytest.mark.django_db(transaction=True)


class _Conn:
    """A REAL connection stand-in: carries the tenant marker (the shape
    ``DatabricksApiClient`` exposes as ``_tenant_id``) and a real
    ``close()`` with observable state."""

    def __init__(self, tenant_id=None, name=None):
        self._tenant_id = tenant_id
        self.name = name or uuid.uuid4().hex[:6]
        self.closed = False

    def close(self):
        self.closed = True


def _factory_maker(calls=None):
    def factory(tenant_id):
        if calls is not None:
            calls.append(tenant_id)
        return _Conn(tenant_id=tenant_id)

    return factory


def _pool(**kwargs):
    from hub.apps.databricks_admin.sql_warehouse_pool import SqlWarehousePool

    defaults = {"reap_interval_s": 30}  # keep the timer quiet unless a pin opts in
    defaults.update(kwargs)
    pool = SqlWarehousePool(**defaults)
    # stop the daemon reaper on teardown (a leaked thread would keep the
    # interpreter alive and cross-contaminate the next test's timers).
    import atexit

    atexit.register(pool.stop)
    return pool


class TestBorrowReuse:
    def test_borrow_release_borrow_returns_the_same_connection(self):
        pool = _pool()
        calls = []
        factory = _factory_maker(calls)

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        pool.release(conn)
        again = pool.borrow("tenant-a", "wh-1", factory=factory)
        assert again is conn, "a released connection must be REUSED"
        assert len(calls) == 1, "the factory ran exactly once"

    def test_same_tenant_different_warehouse_gets_distinct_connections(self):
        pool = _pool()
        calls = []
        factory = _factory_maker(calls)

        first = pool.borrow("tenant-a", "wh-1", factory=factory)
        second = pool.borrow("tenant-a", "wh-2", factory=factory)
        assert first is not second
        assert len(calls) == 2

    def test_different_tenants_same_warehouse_never_share(self):
        """Structural isolation: tenant B's borrow NEVER returns tenant
        A's entry — even for the SAME warehouse id."""
        pool = _pool()
        calls = []
        factory = _factory_maker(calls)

        a_conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        pool.release(a_conn)
        b_conn = pool.borrow("tenant-b", "wh-1", factory=factory)
        assert b_conn is not a_conn, "a connection must never cross the tenant boundary"
        assert len(calls) == 2


class TestTenantRecheck:
    def test_tampered_entry_tenant_fails_loud_and_removes_the_entry(self):
        """The hand-out re-checks the tenant on EVERY borrow: an entry
        whose recorded tenant was corrupted is refused, closed and
        removed — never served."""
        pool = _pool()
        factory = _factory_maker()

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        pool.release(conn)

        # Simulate the keying-bug corruption the re-check exists for.
        entry = pool._entries[("tenant-a", "wh-1")][0]
        entry.tenant_id = "tenant-b"

        from hub.apps.databricks_admin.sql_warehouse_pool import DatabricksWarehousePoolError

        with pytest.raises(DatabricksWarehousePoolError) as excinfo:
            pool.borrow("tenant-a", "wh-1", factory=factory)
        assert getattr(excinfo.value, "code", None) == "DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH"
        assert conn.closed, "the corrupted entry's connection is closed, never served"
        assert ("tenant-a", "wh-1") not in pool._entries

    def test_connection_with_wrong_tenant_marker_is_refused_at_creation(self):
        """The factory's OWN tenant marker is verified before the
        connection is pooled — a wrong-tenant client is closed and
        never stored (fail-closed at the boundary)."""
        pool = _pool()

        def wrong_factory(_tenant_id):
            return _Conn(tenant_id="tenant-other")

        from hub.apps.databricks_admin.sql_warehouse_pool import DatabricksWarehousePoolError

        with pytest.raises(DatabricksWarehousePoolError) as excinfo:
            pool.borrow("tenant-a", "wh-1", factory=wrong_factory)
        assert getattr(excinfo.value, "code", None) == "DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH"
        assert ("tenant-a", "wh-1") not in pool._entries

        # The refused creation released its slot — a correct borrow works.
        calls = []
        conn = pool.borrow("tenant-a", "wh-1", factory=_factory_maker(calls))
        assert conn._tenant_id == "tenant-a"

    def test_connections_without_a_tenant_marker_are_pooled(self):
        """The entry-level key IS the structural guarantee; objects
        without a ``_tenant_id`` marker (a generic factory result) are
        pooled and re-checked at the entry level only."""
        pool = _pool()

        def bare_factory(_tenant_id):
            return object()

        conn = pool.borrow("tenant-a", "wh-1", factory=bare_factory)
        assert conn is not None
        pool.release(conn)
        assert pool.borrow("tenant-a", "wh-1", factory=bare_factory) is conn


class TestPerTenantIsolation:
    def test_exhausted_tenant_does_not_affect_another_tenant(self):
        """The spec scenario: tenant A at capacity → A's borrows raise
        POOL_EXHAUSTED; tenant B's borrows still succeed (the
        per-tenant semaphore — the 0.11 pattern)."""
        pool = _pool(max_per_tenant=1)
        factory = _factory_maker()

        pool.borrow("tenant-a", "wh-1", factory=factory)
        from hub.apps.databricks_admin.sql_warehouse_pool import DatabricksWarehousePoolError

        with pytest.raises(DatabricksWarehousePoolError) as excinfo:
            pool.borrow("tenant-a", "wh-2", factory=factory)
        assert getattr(excinfo.value, "code", None) == "DATABRICKS_WAREHOUSE_POOL_EXHAUSTED"

        b_conn = pool.borrow("tenant-b", "wh-1", factory=factory)
        assert b_conn._tenant_id == "tenant-b", "tenant B borrows succeed despite A's exhaustion"

    def test_release_frees_the_tenants_capacity(self):
        """The 0.11 semaphore semantics: the per-tenant slot is held for
        the BORROW's duration and freed at release — an idle connection
        never blocks the tenant's other warehouses."""
        pool = _pool(max_per_tenant=1)
        factory = _factory_maker()

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        pool.release(conn)
        again = pool.borrow("tenant-a", "wh-2", factory=factory)
        assert again is not None
        assert again is not conn, "a different warehouse gets its OWN connection"

    def test_releasing_a_foreign_connection_fails_loud(self):
        pool = _pool()
        factory = _factory_maker()

        pool.borrow("tenant-a", "wh-1", factory=factory)
        with pytest.raises(ValueError, match="not pooled"):
            pool.release(_Conn(tenant_id="tenant-a"))  # never pooled


class TestIdleReaper:
    def test_idle_connection_beyond_timeout_is_closed_and_removed(self):
        pool = _pool(idle_timeout_s=0.05)
        calls = []
        factory = _factory_maker(calls)

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        pool.release(conn)
        time.sleep(0.1)
        pool.reap()
        assert conn.closed, "the reaper closes idle connections"
        assert ("tenant-a", "wh-1") not in pool._entries

        fresh = pool.borrow("tenant-a", "wh-1", factory=factory)
        assert fresh is not conn
        assert len(calls) == 2, "a new connection is created after the reap"

    def test_in_use_connections_survive_the_reap(self):
        pool = _pool(idle_timeout_s=0.05)
        factory = _factory_maker()

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        time.sleep(0.1)
        pool.reap()
        assert not conn.closed, "an in-use connection is never reaped"
        assert ("tenant-a", "wh-1") in pool._entries

    def test_a_raising_close_is_best_effort(self):
        pool = _pool(idle_timeout_s=0.05)
        factory = _factory_maker()

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)

        def broken_close():
            raise OSError("transport gone")

        conn.close = broken_close
        pool.release(conn)
        time.sleep(0.1)
        pool.reap()  # must not raise
        assert ("tenant-a", "wh-1") not in pool._entries, (
            "a connection whose close() raises is still removed"
        )


class TestTimerReaper:
    def test_background_timer_reaps_without_an_explicit_call(self):
        pool = _pool(idle_timeout_s=0.05, reap_interval_s=0.1)
        factory = _factory_maker()

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        pool.release(conn)
        deadline = time.monotonic() + 2.0
        while ("tenant-a", "wh-1") in pool._entries and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ("tenant-a", "wh-1") not in pool._entries, "the timer reaper fired on its own"
        assert conn.closed

    def test_stop_halts_the_reaper_and_closes_everything(self):
        pool = _pool(idle_timeout_s=0.05, reap_interval_s=0.1)
        factory = _factory_maker()

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        pool.release(conn)
        pool.stop()
        assert conn.closed, "stop() closes every pooled connection"
        assert pool._reaper is not None
        pool._reaper.join(timeout=1.0)
        assert not pool._reaper.is_alive(), "stop() halts the reaper thread"
        with pytest.raises(RuntimeError):
            pool.borrow("tenant-a", "wh-1", factory=factory)


class TestConcurrentBorrows:
    def test_concurrent_same_key_borrows_get_distinct_connections(self):
        """REAL threads: 8 concurrent borrows of the same key each get
        their OWN connection (the lock never hands one entry to two
        callers) and none raise."""
        pool = _pool(max_per_tenant=8)
        factory = _factory_maker()

        def worker(_):
            return pool.borrow("tenant-a", "wh-1", factory=factory)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(worker, range(8)))
        assert len({id(c) for c in results}) == 8, "each borrower got a distinct connection"

    def test_borrow_release_loops_under_a_live_reaper_never_cross_tenants(self):
        """The stress interleave: two tenants churn borrow/release while
        the reaper sweeps continuously (idle_timeout tiny) — every borrow
        succeeds and every connection's marker matches its requesting
        tenant (structural isolation under REAL races)."""
        pool = _pool(max_per_tenant=4, idle_timeout_s=0.01)
        factory = _factory_maker()
        stop_reaping = threading.Event()
        failures: list[Exception] = []
        crossed: list[tuple[str, str]] = []

        def reaper():
            while not stop_reaping.is_set():
                pool.reap()
                time.sleep(0.005)

        def churn(tenant_id):
            for _ in range(25):
                conn = pool.borrow(tenant_id, "wh-1", factory=factory)
                if conn._tenant_id != tenant_id:
                    crossed.append((tenant_id, conn._tenant_id))
                time.sleep(0.001)
                pool.release(conn)

        reaper_thread = threading.Thread(target=reaper, daemon=True)
        reaper_thread.start()
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(churn, t) for t in ("tenant-a", "tenant-b")] * 2
            for future in futures:
                try:
                    future.result()
                except Exception as exc:
                    failures.append(exc)
        stop_reaping.set()
        reaper_thread.join(timeout=2.0)

        assert not failures, failures
        assert not crossed, "a connection crossed the tenant boundary under churn"


class TestSingleton:
    def test_get_sql_warehouse_pool_returns_the_same_instance(self):
        from hub.apps.databricks_admin.sql_warehouse_pool import get_sql_warehouse_pool

        assert get_sql_warehouse_pool() is get_sql_warehouse_pool()


class TestTerminalEdges:
    def test_stop_is_idempotent(self):
        pool = _pool()
        factory = _factory_maker()

        pool.borrow("tenant-a", "wh-1", factory=factory)
        pool.stop()
        pool.stop()  # must not raise
        with pytest.raises(RuntimeError):
            pool.borrow("tenant-a", "wh-1", factory=factory)

    def test_release_after_the_entry_was_reaped_fails_loud(self):
        """A stale release (the entry reaped while idle, after the
        borrow ended) must never silently double-free the tenant's
        slot — the registry lookup fails loud instead."""
        pool = _pool(idle_timeout_s=0.01)
        factory = _factory_maker()

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        # The in-use entry survives a reap (pinned elsewhere) — the
        # FIRST release succeeds and puts it idle.
        pool.reap()
        pool.release(conn)
        time.sleep(0.05)
        pool.reap()  # the now-idle entry is closed + removed
        with pytest.raises(ValueError, match="not pooled"):
            pool.release(conn)


class TestSettingsKeys:
    def test_pool_tuning_knobs_are_real_settings(self):
        from django.conf import settings

        assert settings.DATABRICKS_WAREHOUSE_POOL_MAX_PER_TENANT == 20
        assert settings.DATABRICKS_WAREHOUSE_POOL_IDLE_TIMEOUT_SECONDS == 300
        assert settings.DATABRICKS_WAREHOUSE_POOL_REAP_INTERVAL_SECONDS == 60
