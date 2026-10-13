"""P7 (openspec add-databricks-cost-guardrails task 7.3) — the RQ job
handler for ``JobType.DATABRICKS_COST_SYNC``.

``_execute_databricks_cost_sync_job`` is the executor surface the jobs
dispatcher calls (the per-type handler lives HERE, inside
``databricks_admin`` — the provider boundary holds; the jobs app imports
only this handler function).

One job row = ONE tenant. The handler wraps the whole sync in
``tenant_context(tenant_id)`` (the worker contract — RLS-scoped ledger
writes) and syncs every ACTIVE workspace of that tenant. Fail-closed
workspaces are SKIPPED with a recorded reason — one tenant's
misconfiguration never blocks another tenant's sync.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from hub.apps.databricks_admin.cost_sync import sync_workspace_cost
from hub.apps.databricks_admin.models import DatabricksWorkspace, DatabricksWorkspaceStatus

if TYPE_CHECKING:
    from hub.apps.jobs.models import Job

logger = structlog.get_logger(__name__)


def _execute_databricks_cost_sync_job(job_obj: Job, *, client_factory=None) -> dict:
    """Sync every ACTIVE workspace of the job's tenant.

    Returns ``{"workspaces_synced", "workspaces_skipped", "rows_ingested"}``.
    Raises on transport/API failures (the RQ layer marks the job FAILED
    and the per-type retry policy applies). ``client_factory`` is the
    sanctioned transport seam passed through to the sync (the 1.4
    convention — tests redirect the production client to a local
    transport; production passes nothing).
    """
    from hub.apps.tenants.request_tenant import tenant_context

    tenant_id = str(job_obj.tenant_id)
    synced = 0
    skipped: list[dict] = []
    rows_ingested = 0

    with tenant_context(tenant_id):
        workspaces = list(
            DatabricksWorkspace.objects.filter(
                tenant_id=tenant_id,
                status=DatabricksWorkspaceStatus.ACTIVE,
            ).order_by("name")
        )
        for workspace in workspaces:
            outcome = sync_workspace_cost(workspace, client_factory=client_factory)
            if "skipped" in outcome:
                skipped.append({"workspace": workspace.name, "reason": outcome["skipped"]})
                continue
            synced += 1
            rows_ingested += outcome.get("rows_ingested", 0)

    return {
        "workspaces_synced": synced,
        "workspaces_skipped": skipped,
        "rows_ingested": rows_ingested,
    }
