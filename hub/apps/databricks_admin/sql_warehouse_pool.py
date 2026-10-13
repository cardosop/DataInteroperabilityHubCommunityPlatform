"""Per-tenant SQL-warehouse connection pool (openspec
add-databricks-sql-warehouses task 3.5) — the D4 hard-isolation design.

- PER-(TENANT, WAREHOUSE) KEYING: the registry is keyed by
  ``(tenant_id, warehouse_id)`` — the structural guarantee that a
  connection can never cross the tenant boundary.
- HAND-OUT TENANT RE-CHECK (the spec's belt-and-braces): every borrow
  re-verifies the entry's recorded tenant AND the connection's own
  ``_tenant_id`` marker (the shape ``DatabricksApiClient`` exposes).
  A mismatch is a corruption signal — fail-loud with
  ``DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH``, the connection closed,
  never served. A factory result whose marker disagrees is refused the
  same way BEFORE it is pooled.
- PER-TENANT BOUND (the 0.11 semaphore pattern, applied to pools):
  each tenant gets its OWN ``BoundedSemaphore(max_per_tenant)`` — the
  slot is held for the BORROW's duration and freed at ``release()``.
  Tenant A at capacity raises ``DATABRICKS_WAREHOUSE_POOL_EXHAUSTED``;
  tenant B's borrows are untouched.
- IDLE REAPER: a daemon thread wakes every ``reap_interval_s`` and
  closes + removes connections idle beyond ``idle_timeout_s``;
  ``reap()`` runs one deterministic sweep (the thread's body).
- ``stop()`` halts the reaper, closes every pooled connection and
  empties the registry (worker shutdown); the pool is terminal
  afterwards (borrow raises ``RuntimeError``).

The pool is generic over the connection factory — the caller supplies
the identity-resolved client (the 3.3 contract: the caller owns the
client). No credentials ever live here.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class DatabricksWarehousePoolError(Exception):
    """The pool's classified refusals (never a workspace error)."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


@dataclass
class _PoolEntry:
    connection: Any
    tenant_id: str
    in_use: bool = True
    last_used: float = field(default_factory=time.monotonic)


class SqlWarehousePool:
    """Thread-safe bounded pool of SQL-warehouse connections (see the
    module docstring for the contracts)."""

    def __init__(
        self,
        *,
        max_per_tenant: int | None = None,
        idle_timeout_s: float | None = None,
        reap_interval_s: float | None = None,
    ):
        from django.conf import settings

        self._max_per_tenant = (
            max_per_tenant
            if max_per_tenant is not None
            else settings.DATABRICKS_WAREHOUSE_POOL_MAX_PER_TENANT
        )
        self._idle_timeout = (
            idle_timeout_s
            if idle_timeout_s is not None
            else settings.DATABRICKS_WAREHOUSE_POOL_IDLE_TIMEOUT_SECONDS
        )
        self._reap_interval = (
            reap_interval_s
            if reap_interval_s is not None
            else settings.DATABRICKS_WAREHOUSE_POOL_REAP_INTERVAL_SECONDS
        )
        self._lock = threading.RLock()
        self._entries: dict[tuple[str, str], list[_PoolEntry]] = {}
        self._by_conn: dict[int, tuple[tuple[str, str], _PoolEntry]] = {}
        self._tenant_slots: dict[str, threading.BoundedSemaphore] = {}
        self._stopped = False
        self._stop_event = threading.Event()
        self._reaper: threading.Thread | None = None
        self._reaper_guard = threading.Lock()

    # ── the borrow/release surface ──────────────────────────────────────

    def borrow(self, tenant_id: str, warehouse_id: str, factory) -> Any:
        """Get a connection for ``(tenant_id, warehouse_id)``.

        ``factory(tenant_id)`` builds a new connection when no idle one
        exists. Raises ``DatabricksWarehousePoolError`` (EXHAUSTED /
        TENANT_MISMATCH) or ``RuntimeError`` once stopped.
        """
        if self._stopped:
            raise RuntimeError("the pool is stopped")
        self._ensure_reaper()
        key = (str(tenant_id), str(warehouse_id))

        # The tenant's slot spans EVERY borrow (reused or created) and
        # is freed at ``release`` — acquiring it here, at the top, is
        # what makes the per-tenant bound a bound on CONCURRENT
        # borrows (the 0.11 semaphore semantics). The 3.5-review stress
        # pin caught the first draft acquiring on CREATE only: a reused
        # borrow then freed a slot it never acquired and the
        # BoundedSemaphore over-released under churn.
        slot = self._tenant_slot(str(tenant_id))
        if not slot.acquire(blocking=False):
            # 3.8 — the pool-pressure exhaustion counter (best-effort).
            self._record_pool_metrics(tenant_id, exhausted=True)
            raise DatabricksWarehousePoolError(
                f"warehouse connection pool exhausted for tenant {tenant_id} "
                f"(max {self._max_per_tenant})",
                code="DATABRICKS_WAREHOUSE_POOL_EXHAUSTED",
            )
        try:
            with self._lock:
                for entry in list(self._entries.get(key, ())):
                    if entry.in_use:
                        continue
                    # The hand-out re-check (raises inside the helper —
                    # TRY301): the entry's recorded tenant AND the
                    # connection's own marker must match (a keying bug
                    # must never serve a foreign connection).
                    self._verify_idle_entry(key, entry, str(tenant_id))
                    entry.in_use = True
                    entry.last_used = time.monotonic()
                    # 3.8 — the borrow counter + in-use gauge (best-effort).
                    self._record_pool_metrics(tenant_id, borrowed=True)
                    return entry.connection

            # No idle entry — create one (TRY301: the tenant-verifying
            # raise lives in _build_connection, outside this try-block).
            connection = self._build_connection(str(tenant_id), factory)
        except Exception:
            # Every refusal path returns the slot — a refused borrow
            # never leaks the tenant's capacity.
            slot.release()
            raise
        entry = _PoolEntry(connection=connection, tenant_id=str(tenant_id))
        with self._lock:
            self._entries.setdefault(key, []).append(entry)
            self._by_conn[id(connection)] = (key, entry)
        # 3.8 — the borrow counter + in-use gauge (best-effort).
        self._record_pool_metrics(tenant_id, borrowed=True)
        return connection

    def release(self, connection) -> None:
        """End a borrow: the entry goes idle and the tenant's slot is
        freed (the 0.11 semantics — the slot spans the borrow, not the
        entry's lifetime)."""
        with self._lock:
            found = self._by_conn.get(id(connection))
            if found is None:
                raise ValueError("connection is not pooled")
            key, entry = found
            if not entry.in_use:
                raise ValueError("connection is not in use")
            entry.in_use = False
            entry.last_used = time.monotonic()
        self._tenant_slot(key[0]).release()
        # 3.8 — the in-use gauge follows the release (best-effort).
        self._record_pool_metrics(key[0])

    # ── observability (3.8) ─────────────────────────────────────────────

    def _record_pool_metrics(
        self, tenant_id: str, *, borrowed: bool = False, exhausted: bool = False
    ) -> None:
        """The pool-pressure hooks — the borrow/exhaustion counters and
        the in-use gauge computed from the REAL entries. Best-effort:
        the record functions never raise (a metric-backend outage never
        fails the pool)."""
        from hub.apps.databricks_admin.metrics import (
            record_pool_borrow,
            record_pool_exhausted,
            set_pool_in_use,
        )

        tenant = str(tenant_id)
        if borrowed:
            record_pool_borrow(tenant_id=tenant)
        if exhausted:
            record_pool_exhausted(tenant_id=tenant)
        with self._lock:
            in_use = 0
            for (t, _w), entries in self._entries.items():
                if t == tenant:
                    in_use += sum(1 for entry in entries if entry.in_use)
        set_pool_in_use(tenant_id=tenant, count=in_use)

    # ── the reaper surface ──────────────────────────────────────────────

    def reap(self) -> int:
        """One deterministic sweep: close + remove every connection
        idle beyond ``idle_timeout_s``. Returns the closed count."""
        closed = 0
        now = time.monotonic()
        with self._lock:
            for key, entries in list(self._entries.items()):
                for entry in list(entries):
                    if not entry.in_use and (now - entry.last_used) > self._idle_timeout:
                        self._close_entry(key, entry)
                        closed += 1
        return closed

    def stop(self) -> None:
        """Terminal shutdown: halt the reaper thread and close every
        pooled connection."""
        self._stopped = True
        self._stop_event.set()
        with self._lock:
            for entries in list(self._entries.values()):
                for entry in list(entries):
                    with contextlib.suppress(Exception):
                        entry.connection.close()
            self._entries.clear()
            self._by_conn.clear()
        if self._reaper is not None:
            self._reaper.join(timeout=5)

    # ── internals ───────────────────────────────────────────────────────

    def _tenant_slot(self, tenant_id: str) -> threading.BoundedSemaphore:
        with self._lock:
            slot = self._tenant_slots.get(tenant_id)
            if slot is None:
                slot = threading.BoundedSemaphore(self._max_per_tenant)
                self._tenant_slots[tenant_id] = slot
            return slot

    def _verify_idle_entry(self, key: tuple[str, str], entry: _PoolEntry, tenant_id: str) -> None:
        """The borrow-time hand-out re-check (raises — TRY301: the
        raises live here, outside the borrow's slot-release try-block).

        A mismatch is a corruption signal: the entry is closed and
        removed and ``DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH``
        propagates — the connection is NEVER served."""
        if entry.tenant_id != tenant_id:
            self._close_entry(key, entry)
            raise DatabricksWarehousePoolError(
                f"pooled connection for tenant {entry.tenant_id!r} "
                f"requested by tenant {tenant_id!r}",
                code="DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH",
            )
        marker = getattr(entry.connection, "_tenant_id", None)
        if marker is not None and str(marker) != tenant_id:
            self._close_entry(key, entry)
            raise DatabricksWarehousePoolError(
                f"pooled connection carries tenant marker {marker!r}, "
                f"requested by tenant {tenant_id!r}",
                code="DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH",
            )

    def _build_connection(self, tenant_id: str, factory):
        """Factory call + the creation-time tenant verification.

        Raises (TRY301 — the raise lives here, outside the borrow's
        slot-release try-block): a factory result whose ``_tenant_id``
        marker disagrees is closed and REFUSED before it is pooled
        (fail-closed at the boundary)."""
        connection = factory(tenant_id)
        marker = getattr(connection, "_tenant_id", None)
        if marker is not None and str(marker) != str(tenant_id):
            with contextlib.suppress(Exception):
                connection.close()
            raise DatabricksWarehousePoolError(
                f"the factory produced a connection for tenant "
                f"{marker!r}, requested by tenant {tenant_id!r}",
                code="DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH",
            )
        return connection

    def _close_entry(self, key: tuple[str, str], entry: _PoolEntry) -> None:
        """Best-effort close + registry removal (never raises)."""
        with contextlib.suppress(Exception):
            entry.connection.close()
        self._by_conn.pop(id(entry.connection), None)
        entries = self._entries.get(key)
        if entries:
            with contextlib.suppress(ValueError):
                entries.remove(entry)
            if not entries:
                del self._entries[key]

    def _ensure_reaper(self) -> None:
        if self._reaper is not None:
            return
        with self._reaper_guard:
            if self._reaper is None:
                thread = threading.Thread(
                    target=self._reaper_loop,
                    name="databricks-warehouse-pool-reaper",
                    daemon=True,
                )
                self._reaper = thread
                thread.start()

    def _reaper_loop(self) -> None:
        while not self._stop_event.wait(self._reap_interval):
            with contextlib.suppress(Exception):
                self.reap()


# Module-level singleton (the 275.E pattern — a registry slot instead of
# a `global` rebind so the module stays PLW0603-clean).
_pool_registry: dict[str, SqlWarehousePool] = {}
_pool_guard = threading.Lock()


def get_sql_warehouse_pool() -> SqlWarehousePool:
    with _pool_guard:
        pool = _pool_registry.get("default")
        if pool is None:
            pool = SqlWarehousePool()
            _pool_registry["default"] = pool
        return pool
