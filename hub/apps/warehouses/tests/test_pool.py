"""
Tests for ``hub.apps.warehouses.pool`` — connection pool management.
"""

from unittest import mock

from django.test import SimpleTestCase

from hub.apps.warehouses.exceptions import WarehouseConnectionError
from hub.apps.warehouses.pool import (
    PoolEntry,
    WarehouseConnectionPool,
    get_connection_pool,
)


class PoolEntryTests(SimpleTestCase):
    """Tests for the PoolEntry dataclass."""

    def test_defaults(self):
        connector = object()
        entry = PoolEntry(connector=connector)
        assert entry.connector is connector
        assert entry.in_use is False
        assert entry.last_used > 0


class WarehouseConnectionPoolTests(SimpleTestCase):
    """Tests for WarehouseConnectionPool lifecycle."""

    def setUp(self):
        self.pool = WarehouseConnectionPool(max_connections=5, idle_timeout_s=300)

    def test_acquire_creates_connector(self):
        """acquire calls factory and returns a connector."""
        expected = object()
        connector = self.pool.acquire("t1", "snowflake", lambda: expected)
        assert connector is expected

    def test_acquire_reuses_idle_connector(self):
        """Releasing then acquiring again returns the same connector."""
        conn1 = self.pool.acquire("t1", "snowflake", lambda: object())
        self.pool.release("t1", "snowflake")
        conn2 = self.pool.acquire("t1", "snowflake", lambda: object())
        assert conn1 is conn2

    def test_acquire_different_tenants_different_connectors(self):
        """Different tenant/warehouse combos produce different connectors."""
        conn1 = self.pool.acquire("t1", "snowflake", lambda: object())
        conn2 = self.pool.acquire("t2", "snowflake", lambda: object())
        assert conn1 is not conn2

    def test_acquire_different_warehouse_types_different_connectors(self):
        """Different warehouse types for same tenant produce different connectors."""
        conn1 = self.pool.acquire("t1", "snowflake", lambda: object())
        conn2 = self.pool.acquire("t1", "bigquery", lambda: object())
        assert conn1 is not conn2

    def test_acquire_exhausted_pool_raises(self):
        """When all slots are active, further acquires raise."""
        pool = WarehouseConnectionPool(max_connections=2)
        pool.acquire("t1", "snowflake", lambda: object())
        pool.acquire("t2", "snowflake", lambda: object())
        with self.assertRaises(WarehouseConnectionError) as ctx:
            pool.acquire("t3", "snowflake", lambda: object())
        assert "exhausted" in str(ctx.exception).lower()

    def test_release_marks_idle(self):
        """After release, the connector is marked not in_use."""
        self.pool.acquire("t1", "snowflake", lambda: object())
        self.pool.release("t1", "snowflake")
        # acquirable again without exhausting
        self.pool.acquire("t1", "snowflake", lambda: object())

    def test_release_unknown_key_no_error(self):
        """Releasing an unregistered key does not raise."""
        self.pool.release("unknown", "snowflake")
        # No exception → pass

    def test_idle_timeout_eviction(self):
        """Expired idle connectors are closed and evicted."""
        pool = WarehouseConnectionPool(max_connections=2, idle_timeout_s=0)
        mock_connector = mock.MagicMock()
        pool.acquire("t1", "snowflake", lambda: mock_connector)
        pool.release("t1", "snowflake")
        # Next acquire should purge the expired entry and create a new one
        new_connector = object()
        result = pool.acquire("t1", "snowflake", lambda: new_connector)
        assert result is new_connector
        mock_connector.close.assert_called_once()

    def test_purge_closes_expired_connectors(self):
        """Expired idle connectors have .close() called."""
        pool = WarehouseConnectionPool(max_connections=5, idle_timeout_s=0)
        mock1 = mock.MagicMock()
        mock2 = mock.MagicMock()
        pool.acquire("t1", "snowflake", lambda: mock1)
        pool.acquire("t2", "bigquery", lambda: mock2)
        pool.release("t1", "snowflake")
        pool.release("t2", "bigquery")
        # Next acquire triggers purge of all expired
        pool.acquire("t3", "snowflake", lambda: object())
        assert mock1.close.called
        assert mock2.close.called

    def test_close_error_handled_gracefully(self):
        """If connector.close() raises during purge, other entries still purged."""
        pool = WarehouseConnectionPool(max_connections=5, idle_timeout_s=0)
        bad = mock.MagicMock()
        bad.close.side_effect = RuntimeError("close failed")
        good = mock.MagicMock()
        pool.acquire("t1", "snowflake", lambda: bad)
        pool.acquire("t2", "bigquery", lambda: good)
        pool.release("t1", "snowflake")
        pool.release("t2", "bigquery")
        # Should not raise despite bad.close() error
        pool.acquire("t3", "athena", lambda: object())
        assert good.close.called


class GetConnectionPoolTests(SimpleTestCase):
    """Tests for the module-level singleton get_connection_pool()."""

    def test_returns_singleton(self):
        pool1 = get_connection_pool()
        pool2 = get_connection_pool()
        assert pool1 is pool2

    def test_returns_warehouse_connection_pool_instance(self):
        pool = get_connection_pool()
        assert isinstance(pool, WarehouseConnectionPool)
