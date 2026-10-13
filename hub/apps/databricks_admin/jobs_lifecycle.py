"""Databricks job lifecycle service (openspec add-databricks-jobs task
4.6) — the client lifecycle chokepoint with first-class audit.

Each function drives the PRODUCTION 4.3 jobs client (the caller owns
identity — the client never selects credentials) and emits ONE audit
row per PERFORMED operation: ``DATABRICKS_JOB_CREATED/UPDATED/DELETED``
with resource_type=``DATABRICKS_JOB``. A gate-first refusal raises
BEFORE any operation, so no audit row exists for a refused job.

Emission is BEST-EFFORT (D5 / the Phase 273 contract): an audit-DB
outage never blocks the operation. The mirror row's pk anchors the
event's ``resource_id`` when it exists (a just-created job has no row
yet — the Databricks id lives in the details either way).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hub.apps.databricks_admin.models import DatabricksWorkspace

logger = logging.getLogger(__name__)


def create_databricks_job(
    workspace: DatabricksWorkspace,
    *,
    client,
    name: str,
    tasks: list,
    job_clusters: list | None = None,
    schedule: dict | None = None,
    max_concurrent_runs: int | None = None,
    actor_user=None,
) -> str:
    """Create the job through the pinned client (the gate runs first);
    emits ``DATABRICKS_JOB_CREATED`` on success."""
    job_id = client.create_job(
        name=name,
        tasks=tasks,
        job_clusters=job_clusters,
        schedule=schedule,
        max_concurrent_runs=max_concurrent_runs,
    )
    _emit_job_audit("DATABRICKS_JOB_CREATED", workspace, job_id, actor_user=actor_user)
    return job_id


def update_databricks_job(
    workspace: DatabricksWorkspace,
    job_id: str,
    *,
    client,
    name: str,
    tasks: list,
    job_clusters: list | None = None,
    schedule: dict | None = None,
    actor_user=None,
) -> dict:
    """Update the job through the pinned client (the gate runs on the
    new settings first); emits ``DATABRICKS_JOB_UPDATED`` on success."""
    result = client.update_job(
        job_id,
        name=name,
        tasks=tasks,
        job_clusters=job_clusters,
        schedule=schedule,
    )
    _emit_job_audit("DATABRICKS_JOB_UPDATED", workspace, job_id, actor_user=actor_user)
    return result


def delete_databricks_job(
    workspace: DatabricksWorkspace, job_id: str, *, client, actor_user=None
) -> None:
    """Delete the job through the pinned client; emits
    ``DATABRICKS_JOB_DELETED`` on success."""
    client.delete_job(job_id)
    _emit_job_audit("DATABRICKS_JOB_DELETED", workspace, job_id, actor_user=actor_user)


def _emit_job_audit(
    action: str,
    workspace: DatabricksWorkspace,
    job_id: str,
    *,
    actor_user=None,
    extra: dict | None = None,
) -> None:
    """The chokepoint — one row per performed operation.

    The mirror row's pk anchors the event's ``resource_id`` when it
    exists (a just-created job has no row yet — the Databricks id
    lives in the details either way). Best-effort: an audit-DB outage
    never blocks the operation (the Phase 273 contract).
    """
    try:
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.databricks_admin.models import DatabricksJob

        mirror = DatabricksJob.objects.filter(workspace=workspace, job_id=job_id).first()
        event_details = {
            "job_id": job_id,
            "workspace_id": str(workspace.id),
        }
        if extra:
            event_details.update(extra)
        create_audit_event(
            resource_type="DATABRICKS_JOB",
            action=action,
            actor_user=actor_user,
            tenant=workspace.tenant,
            resource_id=mirror.id if mirror is not None else None,
            details=event_details,
        )
    except Exception:
        logger.warning(
            "databricks_job_audit_failed",
            extra={"action": action, "job_id": job_id},
        )
