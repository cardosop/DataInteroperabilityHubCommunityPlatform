"""P7 (openspec add-databricks-cost-guardrails task 7.5, design D4) — the
Databricks ledger writer registered into the warehouses cost-recording
seam.

ONE append-only ``DatabricksCostLedger`` row per executed query carrying
the source attribution (``query``/``export``/``ingestion``/``job``).
Registered by ``databricks_admin/apps.py::ready()`` — the
provider-boundary inversion: ``warehouses`` never imports this app; this
app plugs its ledger into the provider-agnostic seam.

The write runs INSIDE ``tenant_context(record.tenant_id)`` (the CLAUDE.md
worker/signal contract) so the ledger's RLS WITH CHECK sees the matching
``app.current_tenant_id`` even on non-request paths — the workspace/
warehouse attribution resolution happens inside the same scope, so a
cross-tenant id resolves to ``None`` (filtered by the USING policy)
instead of leaking attribution. Shape discipline BEFORE any DB touch: an
unknown source or negative units raise ValueError — the warehouses facade
turns the raise into a logged drop, never a movement failure. Unresolvable
workspace/warehouse ids are NOT a hard failure: the SET_NULL columns exist
precisely so the cost row survives with its attribution dropped (the
ledger is the cost truth; the attribution is the garnish).
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from hub.apps.databricks_admin.models import (
    DatabricksCostLedger,
    DatabricksCostLedgerSource,
    DatabricksSqlWarehouse,
    DatabricksWorkspace,
)
from hub.apps.tenants.request_tenant import tenant_context

if TYPE_CHECKING:
    from hub.apps.warehouses.cost_recording import CostRecord

logger = structlog.get_logger(__name__)


def _resolve_attribution(model, object_id: str | None):
    """Best-effort resolution of a workspace/warehouse attribution id —
    a missing, malformed, or cross-tenant id drops the attribution with
    a warning; the cost row still lands (SET_NULL preserves the ledger)."""
    if not object_id:
        return None
    try:
        return model.objects.get(id=object_id)
    except (model.DoesNotExist, ValueError, TypeError):
        logger.warning(
            "databricks_cost_ledger_attribution_unresolved",
            model=model.__name__,
            object_id=str(object_id),
        )
        return None


def _record_window(row: DatabricksCostLedger, warehouse, *, redis_client_factory) -> None:
    """7.4 join — every ledger row lands in the rolling-hour window the
    enforcement reads. Best-effort: a cache outage never blocks the cost
    write (the D3 discipline — a missing window degrades the enforcement
    to the ledger fallback, it never breaks the movement)."""
    try:
        import redis as redis_mod

        from hub.apps.core.redis_pools import get_redis_cache_pool
        from hub.apps.databricks_admin.budget_window import record_units

        client = (
            redis_client_factory()
            if redis_client_factory is not None
            else redis_mod.Redis(connection_pool=get_redis_cache_pool())
        )
        record_units(
            client,
            str(row.tenant_id),
            warehouse_id=warehouse.warehouse_id if warehouse else None,
            units=row.units,
        )
    except (redis_mod.RedisError, ConnectionError, OSError):
        logger.warning(
            "databricks_budget_window_record_failed",
            tenant_id=str(row.tenant_id),
            error="cache unavailable",
        )


def record_ledger_cost(
    record: CostRecord,
    *,
    redis_client_factory=None,
) -> DatabricksCostLedger:
    """Append ONE ledger row for the executed-query cost record and land
    it in the rolling-hour budget window (the 7.4 recorder join).

    Raises ValueError for an unknown source or negative units (the
    facade logs and drops); every other failure — an unknown tenant, a
    broken connection — propagates to the facade the same way. The row
    is created inside ``tenant_context`` so the RLS policy sees the
    row's own tenant.
    """
    if record.source not in DatabricksCostLedgerSource.values:
        raise ValueError(
            f"Unknown cost source {record.source!r} — "
            f"valid: {sorted(DatabricksCostLedgerSource.values)}"
        )
    units = Decimal(str(record.units))
    if units < 0:
        raise ValueError(f"Cost units must be non-negative, got {units}")
    label = (record.unit_label or "").strip() or "DBU"
    label = label[:32]

    with tenant_context(record.tenant_id):
        row = DatabricksCostLedger.objects.create(
            tenant_id=record.tenant_id,
            workspace=_resolve_attribution(DatabricksWorkspace, record.workspace_id),
            warehouse=_resolve_attribution(DatabricksSqlWarehouse, record.warehouse_id),
            source=record.source,
            units=units,
            unit_label=label,
            meta=record.meta or {},
        )
    _record_window(row, row.warehouse, redis_client_factory=redis_client_factory)
    return row
