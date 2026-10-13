"""Phase 3 (openspec add-databricks-sql-warehouses task 3.8) — SQL
warehouse lifecycle operations with audit emission.

The lifecycle's SINGLE audit chokepoint (the 2.9 emit precedent): each
performed lifecycle operation wraps the 3.3 compute client and emits
one audit row — resource_type=``DATABRICKS_WAREHOUSE``, action
CREATED/STARTED/STOPPED/RESIZED/DELETED — with tenant + actor
attribution and IDENTIFIERS-ONLY details (no credential material; the
0.16 redaction contract). Contracts:

- **No-op idempotency**: a no-op start/stop (the 3.3 client's ``None``
  result) emits NOTHING — the events are per-operation (D6), an
  operator reading the trail sees what actually happened.
- **Failed transitions**: a ``DatabricksWarehouseStateError`` (or any
  classified ``DatabricksApiError``) PROPAGATES — the error code is the
  surface (the spec scenario); no audit row is fabricated for an
  operation that did not run.
- **Best-effort**: an audit-DB outage never blocks the lifecycle
  operation (the Phase 273 contract).
- **Identity**: the CALLER owns the client (the 3.2/3.3 contract) —
  these functions take ``client`` as a required keyword.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def create_sql_warehouse(
    workspace,
    *,
    client,
    name: str,
    serverless: bool,
    auto_stop_mins: int,
    size: str | None = None,
    actor_user=None,
) -> str:
    """Create the warehouse through the compute client; returns the
    warehouse id. Emits ``CREATED`` on success."""
    warehouse_id = client.create(
        name=name, serverless=serverless, auto_stop_mins=auto_stop_mins, size=size
    )
    _emit_warehouse_audit(
        "CREATED",
        workspace,
        warehouse_id,
        actor_user=actor_user,
    )
    return warehouse_id


def start_sql_warehouse(workspace, warehouse_id: str, *, client, actor_user=None) -> dict | None:
    """START the warehouse; emits ``STARTED`` only when a start was
    actually issued (a no-op on STARTING/RUNNING emits nothing)."""
    result = client.start(warehouse_id)
    if result is not None:
        _emit_warehouse_audit("STARTED", workspace, warehouse_id, actor_user=actor_user)
    return result


def stop_sql_warehouse(workspace, warehouse_id: str, *, client, actor_user=None) -> dict | None:
    """STOP the warehouse; emits ``STOPPED`` only when a stop was
    actually issued (a no-op on STOPPING/STOPPED/DELETING emits nothing)."""
    result = client.stop(warehouse_id)
    if result is not None:
        _emit_warehouse_audit("STOPPED", workspace, warehouse_id, actor_user=actor_user)
    return result


def resize_sql_warehouse(
    workspace, warehouse_id: str, size: str, *, client, actor_user=None
) -> dict:
    """Resize the warehouse (a PATCH with the new size tier); emits
    ``RESIZED`` carrying the requested size in the details."""
    result = client.update(warehouse_id, size=size)
    _emit_warehouse_audit(
        "RESIZED", workspace, warehouse_id, actor_user=actor_user, extra={"size": size}
    )
    return result


def delete_sql_warehouse(workspace, warehouse_id: str, *, client, actor_user=None) -> None:
    """Delete the warehouse; emits ``DELETED`` on success."""
    client.delete(warehouse_id)
    _emit_warehouse_audit("DELETED", workspace, warehouse_id, actor_user=actor_user)


def _emit_warehouse_audit(
    action: str,
    workspace,
    warehouse_id: str,
    *,
    actor_user=None,
    extra: dict | None = None,
) -> None:
    """The chokepoint — one row per performed operation.

    The mirror row's pk anchors the event's ``resource_id`` when it
    exists (a just-created warehouse has no row yet — the Databricks id
    lives in the details either way). Best-effort: an audit-DB outage
    never blocks the operation (the Phase 273 contract).
    """
    try:
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        mirror = DatabricksSqlWarehouse.objects.filter(
            workspace=workspace, warehouse_id=warehouse_id
        ).first()
        event_details = {
            "warehouse_id": warehouse_id,
            "workspace_id": str(workspace.id),
        }
        if extra:
            event_details.update(extra)
        create_audit_event(
            resource_type="DATABRICKS_WAREHOUSE",
            action=action,
            actor_user=actor_user,
            tenant=workspace.tenant,
            resource_id=mirror.id if mirror is not None else None,
            details=event_details,
        )
    except Exception:
        logger.warning(
            "databricks_warehouse_audit_failed",
            extra={"action": action, "warehouse_id": warehouse_id},
        )
