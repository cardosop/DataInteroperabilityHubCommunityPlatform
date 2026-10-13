"""TDD pins for task 3.10 — the pool's reuse/eviction/isolation contract
exercised with the PRODUCTION connection type.

The 3.5 suite pins the pool's mechanics with a connection stand-in; this
suite pins them with REAL ``DatabricksApiClient`` instances — the exact
object the pool pools in production. The client's own ``_tenant_id``
marker (the shape the pool re-checks on every borrow) and its REAL
httpx transport (the thing eviction/stop actually close) are the
surfaces under test:

- **reuse** — a released borrow returns the SAME client (the factory ran
  once); the marker matches the requesting tenant.
- **eviction** — the idle reaper closes the REAL httpx transport and
  removes the entry; ``stop()`` closes every pooled transport and the
  pool turns terminal.
- **isolation** — cross-tenant borrows produce DISTINCT real clients
  with distinct markers; tenant A's exhaustion never affects tenant B;
  a factory result whose marker disagrees is closed and refused before
  it is pooled (fail-closed at the boundary).

No mocks: real clients, real transports, real threads. No network
traffic — no test issues a request, so the closed-transport state is
observable without any server.
"""

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = pytest.mark.django_db(transaction=True)


def _real_client(tenant_id):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url="http://127.0.0.1:1",  # never dialed — closed transports only
        tenant_id=tenant_id,
        credential_config={"token": "dapi-pool"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
        use_breaker=False,  # the 1.7 delegation convention — the test owns the transport
    )


def _factory_maker(calls=None):
    def factory(tenant_id):
        if calls is not None:
            calls.append(tenant_id)
        return _real_client(tenant_id)

    return factory


def _pool(**kwargs):
    from hub.apps.databricks_admin.sql_warehouse_pool import SqlWarehousePool

    defaults = {"reap_interval_s": 30}
    defaults.update(kwargs)
    pool = SqlWarehousePool(**defaults)
    import atexit

    atexit.register(pool.stop)
    return pool


def _transport_closed(conn):
    """The real client's httpx transport closure (observable)."""
    return conn._client.is_closed


class TestReuse:
    def test_borrow_release_borrow_returns_the_same_real_client(self):
        pool = _pool()
        calls = []
        factory = _factory_maker(calls)

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        assert isinstance(conn, type(_real_client("x")))
        assert conn._tenant_id == "tenant-a"
        pool.release(conn)
        again = pool.borrow("tenant-a", "wh-1", factory=factory)
        assert again is conn, "a released real client must be REUSED"
        assert len(calls) == 1, "the factory ran exactly once"
        assert not _transport_closed(conn), "a pooled borrow keeps its transport open"

    def test_same_tenant_different_warehouse_gets_distinct_real_clients(self):
        pool = _pool()
        factory = _factory_maker()

        first = pool.borrow("tenant-a", "wh-1", factory=factory)
        second = pool.borrow("tenant-a", "wh-2", factory=factory)
        assert first is not second
        assert first._tenant_id == second._tenant_id == "tenant-a"


class TestEviction:
    def test_the_reaper_closes_the_real_transport_and_removes_the_entry(self):
        pool = _pool(idle_timeout_s=0.05)
        factory = _factory_maker()

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        pool.release(conn)
        time.sleep(0.1)
        assert pool.reap() == 1
        assert _transport_closed(conn), "the reaper closes the REAL httpx transport"
        assert ("tenant-a", "wh-1") not in pool._entries

        fresh = pool.borrow("tenant-a", "wh-1", factory=factory)
        assert fresh is not conn
        assert not _transport_closed(fresh), "the replacement client is live"

    def test_in_use_real_clients_survive_the_reap(self):
        pool = _pool(idle_timeout_s=0.05)
        factory = _factory_maker()

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        time.sleep(0.1)
        assert pool.reap() == 0
        assert not _transport_closed(conn), "an in-use transport is never closed"
        assert ("tenant-a", "wh-1") in pool._entries

    def test_stop_closes_every_pooled_real_transport(self):
        pool = _pool()
        factory = _factory_maker()

        a_conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        b_conn = pool.borrow("tenant-b", "wh-1", factory=factory)
        pool.release(a_conn)
        pool.release(b_conn)
        pool.stop()
        assert _transport_closed(a_conn), "stop() closes tenant A's real transport"
        assert _transport_closed(b_conn), "stop() closes tenant B's real transport"
        with pytest.raises(RuntimeError):
            pool.borrow("tenant-a", "wh-1", factory=factory)


class TestIsolation:
    def test_different_tenants_same_warehouse_never_share_a_real_client(self):
        pool = _pool()
        calls = []
        factory = _factory_maker(calls)

        a_conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        pool.release(a_conn)
        b_conn = pool.borrow("tenant-b", "wh-1", factory=factory)
        assert b_conn is not a_conn, "a real client must never cross the tenant boundary"
        assert b_conn._tenant_id == "tenant-b"
        assert len(calls) == 2

    def test_exhausted_tenant_does_not_affect_another_tenant(self):
        from hub.apps.databricks_admin.sql_warehouse_pool import DatabricksWarehousePoolError

        pool = _pool(max_per_tenant=1)
        factory = _factory_maker()

        pool.borrow("tenant-a", "wh-1", factory=factory)
        with pytest.raises(DatabricksWarehousePoolError) as excinfo:
            pool.borrow("tenant-a", "wh-2", factory=factory)
        assert excinfo.value.code == "DATABRICKS_WAREHOUSE_POOL_EXHAUSTED"

        b_conn = pool.borrow("tenant-b", "wh-1", factory=factory)
        assert b_conn._tenant_id == "tenant-b", (
            "tenant B's real client succeeds despite A's exhaustion"
        )

    def test_a_wrong_tenant_marker_is_refused_and_closed_before_pooling(self):
        from hub.apps.databricks_admin.sql_warehouse_pool import DatabricksWarehousePoolError

        pool = _pool()

        def wrong_factory(_tenant_id):
            return _real_client("tenant-other")

        refused = None

        def capture_factory(tenant_id):
            nonlocal refused
            refused = wrong_factory(tenant_id)
            return refused

        with pytest.raises(DatabricksWarehousePoolError) as excinfo:
            pool.borrow("tenant-a", "wh-1", factory=capture_factory)
        assert excinfo.value.code == "DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH"
        assert _transport_closed(refused), (
            "the refused real client's transport was closed, never served"
        )
        assert ("tenant-a", "wh-1") not in pool._entries

    def test_tampered_entry_tenant_fails_loud_with_the_real_client(self):
        from hub.apps.databricks_admin.sql_warehouse_pool import DatabricksWarehousePoolError

        pool = _pool()
        factory = _factory_maker()

        conn = pool.borrow("tenant-a", "wh-1", factory=factory)
        pool.release(conn)
        entry = pool._entries[("tenant-a", "wh-1")][0]
        entry.tenant_id = "tenant-b"

        with pytest.raises(DatabricksWarehousePoolError) as excinfo:
            pool.borrow("tenant-a", "wh-1", factory=factory)
        assert excinfo.value.code == "DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH"
        assert _transport_closed(conn), "the corrupted entry's real transport is closed"
        assert ("tenant-a", "wh-1") not in pool._entries


class TestConcurrentRealClients:
    def test_concurrent_borrows_get_distinct_real_clients_with_matching_markers(self):
        """REAL threads: 8 concurrent borrows of the same key each get
        their OWN real client whose marker matches the tenant — no entry
        is ever handed to two callers, no marker ever crosses."""
        pool = _pool(max_per_tenant=8)
        factory = _factory_maker()

        def worker(_):
            return pool.borrow("tenant-a", "wh-1", factory=factory)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(worker, range(8)))
        assert len({id(c) for c in results}) == 8
        assert {c._tenant_id for c in results} == {"tenant-a"}

    def test_two_tenants_churn_borrow_release_without_a_crossing(self):
        pool = _pool(max_per_tenant=4)
        factory = _factory_maker()
        crossed: list[tuple[str, str]] = []
        failures: list[Exception] = []

        def churn(tenant_id):
            for _ in range(10):
                try:
                    conn = pool.borrow(tenant_id, f"wh-{uuid.uuid4().hex[:4]}", factory=factory)
                except Exception as exc:
                    failures.append(exc)
                    continue
                if conn._tenant_id != tenant_id:
                    crossed.append((tenant_id, conn._tenant_id))
                pool.release(conn)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(churn, t) for t in ("tenant-a", "tenant-b")] * 2
            for future in futures:
                future.result()
        assert not failures, failures
        assert not crossed, "a real client crossed the tenant boundary under churn"
