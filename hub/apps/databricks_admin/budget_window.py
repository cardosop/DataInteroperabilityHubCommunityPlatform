"""P7 (openspec add-databricks-cost-guardrails task 7.4, design D3) — the
Redis rolling-hour budget window.

A REAL Redis sorted set per tenant (+ optional per-warehouse scope) counts
the ledger-attributed units consumed in the rolling hour: every entry is
``f"{units}:{uuid}"`` scored by its epoch second, entries older than the
window are pruned on every read/write, and the key's TTL is refreshed to
the window length. The keys carry the tenant id FIRST (the Phase 273 key
discipline — one tenant's exhaustion never counts against another's).

The window is a cache of the ledger — the caller owns the failure
discipline (a Redis outage must NEVER falsely block the movement; the
enforcement degrades to the ledger fallback on the alert path).
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

WINDOW_SECONDS = 3600


def window_key(tenant_id: str, warehouse_id: str | None = None) -> str:
    """The tenant-scoped (optionally warehouse-scoped) window key."""
    key = f"databricks_cost_window_{tenant_id}"
    if warehouse_id:
        key = f"{key}_{warehouse_id}"
    return key


def _prune(redis_client, key: str, now: int) -> None:
    """Drop every entry older than the rolling window."""
    redis_client.zremrangebyscore(key, "-inf", now - WINDOW_SECONDS)


def record_units(
    redis_client,
    tenant_id: str,
    *,
    warehouse_id: str | None = None,
    units: Decimal,
    now: float | None = None,
) -> None:
    """Record consumed units into the rolling window (a ledger-append
    chokepoint call — best-effort per the caller's contract)."""
    epoch = int(now if now is not None else time.time())
    key = window_key(tenant_id, warehouse_id)
    _prune(redis_client, key, epoch)
    redis_client.zadd(key, {f"{units}:{uuid.uuid4().hex}": epoch})
    redis_client.expire(key, WINDOW_SECONDS)


def window_sum(
    redis_client,
    tenant_id: str,
    *,
    warehouse_id: str | None = None,
    now: float | None = None,
) -> Decimal:
    """The units consumed in the rolling hour (a Redis failure RAISES —
    the caller owns the best-effort degradation)."""
    epoch = int(now if now is not None else time.time())
    key = window_key(tenant_id, warehouse_id)
    _prune(redis_client, key, epoch)
    total = Decimal("0")
    for member in redis_client.zrangebyscore(key, epoch - WINDOW_SECONDS, "+inf"):
        total += Decimal(str(member).split(":", 1)[0])
    return total
