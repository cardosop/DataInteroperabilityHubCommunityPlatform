"""Phase 1 (openspec add-databricks-uc-read task 1.5) — the RQ job handler.

``_execute_databricks_uc_metadata_sync_job`` is the executor surface the
jobs dispatcher calls for ``JobType.DATABRICKS_UC_METADATA_SYNC`` (the
per-type handler lives HERE, inside ``databricks_admin``, so the estate
models and client never leak into the core jobs app — the provider
boundary holds; the jobs app imports only this handler function).

One job row = ONE tenant. The handler wraps the whole sync in
``tenant_context(tenant_id)`` (the worker contract — RLS-scoped mirror
writes) and syncs every ACTIVE workspace of that tenant. Fail-closed
workspaces (no M2M credential / no approver-chain linkage / D12
violation) are SKIPPED with a recorded reason — one tenant's
misconfiguration never blocks another tenant's sync, and no unlinked
service identity ever executes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from hub.apps.databricks_admin.models import DatabricksWorkspace, DatabricksWorkspaceStatus
from hub.apps.databricks_admin.uc_sync import sync_uc_workspace

if TYPE_CHECKING:
    from hub.apps.jobs.models import Job

logger = logging.getLogger(__name__)


def _execute_databricks_uc_metadata_sync_job(job_obj: Job) -> dict:
    """Sync every ACTIVE workspace of the job's tenant.

    Returns ``{"workspaces_synced", "workspaces_skipped", "counters"}``.
    Raises on transport/API failures (the RQ layer marks the job FAILED
    and the per-type retry policy applies).
    """
    from hub.apps.tenants.request_tenant import tenant_context

    tenant_id = str(job_obj.tenant_id)
    counters = {"created": 0, "updated": 0, "unchanged": 0, "deleted": 0}
    skipped: list[dict] = []
    synced = 0

    with tenant_context(tenant_id):
        workspaces = list(
            DatabricksWorkspace.objects.filter(
                tenant_id=tenant_id,
                status=DatabricksWorkspaceStatus.ACTIVE,
            ).order_by("name")
        )
        for workspace in workspaces:
            outcome = sync_uc_workspace(workspace)
            if "skipped" in outcome:
                skipped.append({"workspace": workspace.name, "reason": outcome["skipped"]})
                logger.warning(
                    "databricks_uc_sync_workspace_skipped",
                    extra={
                        "workspace": str(workspace.id),
                        "tenant_id": tenant_id,
                        "reason": outcome["skipped"],
                    },
                )
                continue
            synced += 1
            for key in counters:
                counters[key] += outcome["counters"].get(key, 0)

    return {
        "workspaces_synced": synced,
        "workspaces_skipped": skipped,
        "counters": counters,
    }
