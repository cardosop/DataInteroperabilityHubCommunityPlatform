"""SQL warehouse state mirror (openspec add-databricks-sql-warehouses
task 3.2).

The mirror is a READ cache of the Databricks-owned warehouse state: the
refresh lists the workspace's warehouses through the pinned compute
surface (`sql.warehouses.list`, 2.0) and delta-diffs them into
``DatabricksSqlWarehouse`` rows — created/updated/unchanged/deleted,
with the freshness stamp touched ONLY on change (the 1.5 UC-sync
convention). The Hub NEVER invents a state: an API-reported state the
vocabulary does not know is SKIPPED with a warning (the row is not
created), and deleted warehouses are removed from the mirror without
any compensating action.

The caller owns the client (identity resolution is the 3.3 compute
client's contract); this service only maps reported state.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from django.utils import timezone

from hub.apps.databricks_admin.models import (
    DatabricksSqlWarehouse,
    DatabricksSqlWarehouseState,
    DatabricksWorkspace,
)

if TYPE_CHECKING:
    from hub.apps.databricks_admin.client import DatabricksApiClient

logger = logging.getLogger(__name__)

# The mirrorable fields (warehouse_id is the identity, never rewritten).
_MIRRORED_FIELDS = ("name", "state", "serverless", "size", "auto_stop_mins")


def _json_object(client: DatabricksApiClient) -> dict:
    """One version-pinned GET with the 0.7 JSON discipline: a malformed
    2xx body is a classified error, never a leaked JSONDecodeError."""
    from hub.apps.databricks_admin.client import DatabricksApiError

    response = client.request("GET", "sql.warehouses.list")
    try:
        payload = response.json()
    except ValueError as exc:
        raise DatabricksApiError("sql.warehouses.list returned a non-JSON body") from exc
    if not isinstance(payload, dict):
        raise DatabricksApiError("sql.warehouses.list returned a non-object body")
    return payload


def refresh_sql_warehouse_mirror(
    workspace: DatabricksWorkspace, *, client: DatabricksApiClient
) -> dict:
    """One list call → delta-diff into the mirror.

    Returns ``{"created", "updated", "unchanged", "deleted"}`` counters.
    The caller runs under the tenant context (RLS) and owns the client
    identity — this service never selects credentials.
    """
    payload = _json_object(client)
    reported = payload.get("warehouses") or []
    if not isinstance(reported, list):
        raise TypeError("sql.warehouses.list must return a warehouses list")

    counters = {"created": 0, "updated": 0, "unchanged": 0, "deleted": 0}
    seen_ids: set[str] = set()

    for item in reported:
        if not isinstance(item, dict):
            logger.warning(
                "databricks_sql_warehouse_mirror_skip_junk_row",
                extra={"workspace": str(workspace.id)},
            )
            continue
        warehouse_id = str(item.get("id") or "")
        if not warehouse_id:
            logger.warning(
                "databricks_sql_warehouse_mirror_skip_missing_id",
                extra={"workspace": str(workspace.id)},
            )
            continue
        seen_ids.add(warehouse_id)

        # An unknown API state is SKIPPED — the mirror never invents a
        # state the compute API did not report in the vocabulary.
        raw_state = str(item.get("state") or "")
        if raw_state not in DatabricksSqlWarehouseState.values:
            logger.warning(
                "databricks_sql_warehouse_mirror_skip_unknown_state",
                extra={
                    "workspace": str(workspace.id),
                    "warehouse_id": warehouse_id,
                    "state": raw_state,
                },
            )
            continue

        # 3.2 review hardening — malformed fields are SKIPPED, never
        # coerced, never a crash: a string-valued serverless would coerce
        # to True in Python, a non-numeric auto-stop would raise, and a
        # non-scalar size would fail the model's full_clean. The "never
        # invent" principle extends to SHAPES.
        raw_name = item.get("name")
        raw_serverless = item.get("serverless")
        raw_size = item.get("size")
        raw_auto_stop = item.get("auto_stop_mins")
        if not isinstance(raw_name, str) or not raw_name.strip():
            logger.warning(
                "databricks_sql_warehouse_mirror_skip_missing_name",
                extra={"workspace": str(workspace.id), "warehouse_id": warehouse_id},
            )
            continue
        if not isinstance(raw_serverless, bool):
            logger.warning(
                "databricks_sql_warehouse_mirror_skip_non_bool_serverless",
                extra={"workspace": str(workspace.id), "warehouse_id": warehouse_id},
            )
            continue
        if raw_size is not None and not isinstance(raw_size, str):
            logger.warning(
                "databricks_sql_warehouse_mirror_skip_non_scalar_size",
                extra={"workspace": str(workspace.id), "warehouse_id": warehouse_id},
            )
            continue
        try:
            auto_stop = int(raw_auto_stop) if raw_auto_stop is not None else 0
        except (TypeError, ValueError):
            logger.warning(
                "databricks_sql_warehouse_mirror_skip_non_numeric_auto_stop",
                extra={"workspace": str(workspace.id), "warehouse_id": warehouse_id},
            )
            continue

        defaults = {
            "name": raw_name,
            "state": raw_state,
            "serverless": raw_serverless,
            "size": raw_size,
            "auto_stop_mins": auto_stop,
        }
        row = DatabricksSqlWarehouse.objects.filter(
            workspace=workspace, warehouse_id=warehouse_id
        ).first()
        if row is None:
            DatabricksSqlWarehouse.objects.create(
                workspace=workspace, warehouse_id=warehouse_id, **defaults
            )
            # 3.8 — a warehouse that arrives already STARTING anchors its
            # long-STARTING timer at this refresh.
            if raw_state == "STARTING":
                _record_starting_transition(workspace, warehouse_id, now=time.time())
            counters["created"] += 1
            continue
        old_state = row.state
        changed = False
        for field, value in defaults.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                changed = True
        if changed:
            row.synced_at = timezone.now()
            row.save()
            counters["updated"] += 1
            # 3.8 — STARTING transitions anchor/reset the long-STARTING
            # timer (entered → first-seen epoch; left → 0).
            if old_state != "STARTING" and row.state == "STARTING":
                _record_starting_transition(workspace, warehouse_id, now=time.time())
            elif old_state == "STARTING" and row.state != "STARTING":
                _record_starting_transition(workspace, warehouse_id, now=0)
        else:
            counters["unchanged"] += 1

    # Deleted-on-the-workspace rows leave the mirror — derived, never
    # compensated (the spec scenario).
    for row in DatabricksSqlWarehouse.objects.filter(workspace=workspace):
        if row.warehouse_id not in seen_ids:
            if row.state == "STARTING":
                _record_starting_transition(workspace, row.warehouse_id, now=0)
            row.delete()
            counters["deleted"] += 1

    # 3.8 — the fleet observability stamps (best-effort by the record
    # functions' own contract; a metric-backend outage never fails the
    # refresh).
    _record_fleet_gauges(workspace)

    return counters


def _record_starting_transition(workspace, warehouse_id: str, *, now: float) -> None:
    """3.8 — anchor/reset the long-STARTING timer for one warehouse."""
    from hub.apps.databricks_admin.metrics import record_warehouse_starting_since

    record_warehouse_starting_since(
        warehouse_id=warehouse_id,
        tenant_id=str(workspace.tenant_id),
        workspace_id=str(workspace.id),
        seconds_since_epoch=now,
    )


def _record_fleet_gauges(workspace) -> None:
    """3.8 — stamp the last-success anchor + per-state counts."""
    from hub.apps.databricks_admin.metrics import (
        record_warehouse_mirror_success,
        record_warehouse_state_counts,
    )

    record_warehouse_mirror_success(
        tenant_id=str(workspace.tenant_id), workspace_id=str(workspace.id)
    )
    record_warehouse_state_counts(workspace)
