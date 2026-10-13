"""P7 (openspec add-databricks-cost-guardrails task 7.3, design D2) — the
hourly ``system.billing.usage`` sync.

One workspace per call: the billing delta (``start_time >= `` the
workspace's ``last_cost_synced_at`` stamp) is read through the REAL
``SqlStatementExecutor`` on the workspace's RUNNING SQL warehouse under
the workspace's M2M identity (the D12 background purpose ``cost_sync``)
and appended to the tenant's ``DatabricksCostLedger`` with the
``billing_sync`` source attribution. The sync entry point establishes
``tenant_context(workspace.tenant_id)`` ITSELF (the RLS contract) — the
ledger is RLS-scoped; the job layer's own wrap stays as harmless
nesting.

Fail-closed workspaces are SKIPPED with a recorded reason and ZERO
network calls: no M2M credential, no approver-chain linkage, a D12
identity-resolution failure, or no RUNNING SQL warehouse mirror. One
tenant's misconfiguration never blocks another tenant's sync.

The stamp advance is a PARTIAL save (``update_fields``) — the workspace
host validators are skipped (the 0.8 partial-save contract).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import structlog

from hub.apps.databricks_admin.models import (
    DatabricksCostLedger,
    DatabricksSqlWarehouseState,
    DatabricksWorkspace,
)

logger = structlog.get_logger(__name__)

# The billing read — identifier-free (system tables), the delta bound
# rides as the named :last_synced parameter (never in the SQL text).
_BILLING_SELECT = (
    'SELECT usage_metadata, usage_quantity, usage_unit, start_time FROM "system.billing.usage"'
)


def _skip(workspace, reason: str) -> dict:
    logger.warning(
        "databricks_cost_sync_skipped",
        workspace=str(workspace.id),
        reason=reason,
    )
    return {"skipped": reason}


def _ingest_rows(workspace, rows: list[list]) -> int:
    """Append the billing rows to the tenant's ledger with the
    ``billing_sync`` attribution. The stamp advances to the max billing
    start_time seen (ISO timestamps sort chronologically)."""
    ingested = 0
    max_start: str | None = None
    for row in rows:
        metadata, quantity, unit, start_time = row
        if start_time is None:
            continue
        try:
            units = Decimal(str(quantity))
        except (InvalidOperation, ValueError):
            logger.warning(
                "databricks_cost_sync_unparseable_units",
                workspace=str(workspace.id),
                raw=str(quantity),
            )
            continue
        DatabricksCostLedger.objects.create(
            tenant_id=workspace.tenant_id,
            workspace=workspace,
            source="billing_sync",
            units=units,
            unit_label=str(unit or "DBU")[:32],
            meta={
                "start_time": str(start_time),
                "usage_metadata": str(metadata or ""),
            },
        )
        # 7.4 — every ledger row lands in the rolling-hour window
        # (best-effort: a cache outage never blocks the sync).
        try:
            import redis as redis_mod

            from hub.apps.core.redis_pools import get_redis_cache_pool
            from hub.apps.databricks_admin.budget_window import record_units

            record_units(
                redis_mod.Redis(connection_pool=get_redis_cache_pool()),
                str(workspace.tenant_id),
                units=units,
            )
        except (redis_mod.RedisError, ConnectionError, OSError):
            logger.warning(
                "budget_window_record_failed",
                workspace=str(workspace.id),
                error="cache unavailable",
            )
        ingested += 1
        if max_start is None or str(start_time) > max_start:
            max_start = str(start_time)

    if max_start:
        # A partial save skips the host/region validators (0.8 contract).
        workspace.last_cost_synced_at = datetime.fromisoformat(max_start.replace("Z", "+00:00"))
        workspace.save(update_fields=["last_cost_synced_at"])
    return ingested


def sync_workspace_cost(
    workspace: DatabricksWorkspace,
    *,
    client_factory: Callable | None = None,
) -> dict:
    """Sync ONE workspace's billing delta. Returns
    ``{"rows_ingested": N}`` or ``{"skipped": reason}`` — a skip NEVER
    touches the network. Raises only for transport/API failures (the job
    layer marks FAILED and the retry policy applies)."""
    # Tenant Isolation RLS contract (CLAUDE.md): the sync is a WORKER —
    # every tenant-scoped access (credential/warehouse lookups, ledger
    # writes, the stamp advance) must run inside ``tenant_context``.
    # The entry point establishes the context ITSELF (self-contained —
    # a future caller can never forget the wrap; the job layer's own
    # wrap stays as harmless nesting).
    from hub.apps.tenants.request_tenant import tenant_context

    with tenant_context(str(workspace.tenant_id)):
        return _sync_workspace_cost_in_context(
            workspace,
            client_factory=client_factory,
        )


def _sync_workspace_cost_in_context(
    workspace: DatabricksWorkspace,
    *,
    client_factory: Callable | None = None,
) -> dict:
    """The tenant-context-wrapped body of ``sync_workspace_cost``."""
    from hub.apps.databricks_admin.identity import (
        DatabricksOBOError,
        HybridIdentityError,
        resolve_execution_identity,
    )
    from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor
    from hub.apps.databricks_admin.uc_sync import _select_service_credential
    from hub.apps.databricks_admin.uc_views import _build_uc_client

    credential = _select_service_credential(workspace)
    if credential is None:
        return _skip(workspace, "workspace has no M2M credential (D12 background identity)")
    if credential.approval_request is None:
        return _skip(
            workspace,
            "the workspace M2M credential carries no approver-chain "
            "linkage (approval_request) — D12 background execution is "
            "fail-closed without human approval lineage",
        )
    try:
        identity = resolve_execution_identity(
            purpose="cost_sync",
            workspace=workspace,
            credential=credential,
            approval_request=credential.approval_request,
        )
    except (HybridIdentityError, DatabricksOBOError) as exc:
        return _skip(workspace, f"D12 identity resolution failed: {exc}")

    factory = client_factory or _build_uc_client
    client = factory(workspace, identity)

    warehouse = (
        workspace.sql_warehouses.filter(state=DatabricksSqlWarehouseState.RUNNING)
        .order_by("name")
        .first()
    )
    if warehouse is None:
        return _skip(workspace, "no RUNNING SQL warehouse mirror to execute the billing read")

    stamp = workspace.last_cost_synced_at
    statement = _BILLING_SELECT
    params = None
    if stamp:
        statement += " WHERE start_time > :last_synced"
        # STRICT > — the boundary row is already in the ledger; a >= bound
        # would re-ingest it every run (the duplicate-row class). The
        # billing rows carry the connector's Z-form; the stamp must
        # serialize in the SAME form so the string ordering on both sides
        # is chronological (isoformat()'s +00:00 would sort AFTER "Z").
        params = {"last_synced": stamp.strftime("%Y-%m-%dT%H:%M:%SZ")}
    statement += " ORDER BY start_time"

    result = SqlStatementExecutor(client, warehouse_id=warehouse.warehouse_id).execute(
        statement, warehouse_id=warehouse.warehouse_id, parameters=params
    )
    ingested = _ingest_rows(workspace, result.rows)
    logger.info(
        "databricks_cost_sync_completed",
        workspace=str(workspace.id),
        rows_ingested=ingested,
    )
    return {"rows_ingested": ingested}
