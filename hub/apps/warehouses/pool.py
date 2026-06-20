"""
Phase 275.E — Per-tenant warehouse connection pool.

Manages a bounded pool of warehouse connector instances keyed by
(tenant_id, warehouse_type).  Enforces max connections and idle timeout.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from .exceptions import WarehouseConnectionError


@dataclass
class PoolEntry:
    connector: Any
    last_used: float = field(default_factory=time.monotonic)
    in_use: bool = False


class WarehouseConnectionPool:
    """Thread-safe bounded pool of warehouse connectors.

    Keyed by ``(tenant_id, warehouse_type)``.  Reuses idle connectors
    within the idle timeout window.
    """

    def __init__(
        self,
        max_connections: int = 10,
        idle_timeout_s: int = 300,
    ):
        self._max = max_connections
        self._idle_timeout = idle_timeout_s
        self._pool: dict[str, PoolEntry] = OrderedDict()
        self._lock = threading.RLock()

    def _key(self, tenant_id: str, warehouse_type: str) -> str:
        return f"{tenant_id}:{warehouse_type}"

    def acquire(
        self,
        tenant_id: str,
        warehouse_type: str,
        factory,
    ) -> Any:
        """Get or create a connector for *tenant_id*/*warehouse_type*.

        *factory* is a callable that returns a new connector instance.
        """
        key = self._key(tenant_id, warehouse_type)
        with self._lock:
            # Purge expired idle entries.
            now = time.monotonic()
            expired = [
                k
                for k, e in self._pool.items()
                if not e.in_use and (now - e.last_used) > self._idle_timeout
            ]
            for k in expired:
                with contextlib.suppress(Exception):
                    self._pool[k].connector.close()
                del self._pool[k]

            # Return existing idle connector.
            if key in self._pool and not self._pool[key].in_use:
                entry = self._pool[key]
                entry.in_use = True
                entry.last_used = now
                return entry.connector

            # Enforce max connections.
            active = sum(1 for e in self._pool.values() if e.in_use)
            if active >= self._max:
                raise WarehouseConnectionError(
                    f"Connection pool exhausted ({active}/{self._max} active). "
                    "Retry later or increase max_connections."
                )

            # Create new connector.
            connector = factory()
            self._pool[key] = PoolEntry(connector=connector, in_use=True)
            # Evict oldest idle if over max.
            while len(self._pool) > self._max:
                idle_keys = [k for k, e in self._pool.items() if not e.in_use]
                if not idle_keys:
                    break
                oldest = idle_keys[0]
                with contextlib.suppress(Exception):
                    self._pool[oldest].connector.close()
                del self._pool[oldest]

            return connector

    def release(self, tenant_id: str, warehouse_type: str) -> None:
        """Mark a connector as idle."""
        key = self._key(tenant_id, warehouse_type)
        with self._lock:
            if key in self._pool:
                self._pool[key].in_use = False
                self._pool[key].last_used = time.monotonic()


# Module-level singleton.
_pool: WarehouseConnectionPool | None = None


def get_connection_pool() -> WarehouseConnectionPool:
    global _pool
    if _pool is None:
        _pool = WarehouseConnectionPool()
    return _pool
