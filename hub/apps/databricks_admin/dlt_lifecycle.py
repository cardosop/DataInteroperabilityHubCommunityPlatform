"""Databricks DLT pipeline audit helpers (openspec
add-databricks-dlt-pipelines task 10.8) — the emission chokepoints for
the six ``DATABRICKS_DLT_*`` events.

The vocabulary (one row per PERFORMED operation, resource_type=
``DATABRICKS_DLT_PIPELINE`` — the estate object, the 4.4 convention):

- ``DATABRICKS_DLT_PIPELINE_CREATED/UPDATED/DELETED`` emit from the DLT
  view actions (``dlt_views``) after the client call succeeds. A
  gate-first refusal (the 10.4 chain, the conflict gate) raises BEFORE
  any operation, so no audit row exists for a refused pipeline.
- ``DATABRICKS_DLT_UPDATE_STARTED`` emits from the start action after
  the client's ``start_update`` succeeds.
- ``DATABRICKS_DLT_UPDATE_SUCCEEDED/FAILED`` emit from the terminal
  chokepoint (``dlt_update_observability.finalize_terminal_update``) —
  SUCCEEDED for COMPLETED; FAILED for FAILED/CANCELED/TIMED_OUT (the
  status != COMPLETED convention, the 4.4 discipline).

Emission is BEST-EFFORT (D5 / the Phase 273 contract): an audit-DB
outage never blocks the operation. The mirror row's pk anchors the
event's ``resource_id`` when it exists (a just-created pipeline has no
row yet — the Databricks id lives in the details either way); details
carry identifiers only, never settings material (the 3.8 convention).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hub.apps.databricks_admin.models import (
        DatabricksDltPipeline,
        DatabricksDltPipelineUpdate,
        DatabricksWorkspace,
    )

logger = logging.getLogger(__name__)

# The terminal quartet (the 10.2 vocabulary) → the two audit outcomes.
_SUCCEEDED_STATES = frozenset({"COMPLETED"})


def _emit(
    action: str,
    workspace: DatabricksWorkspace,
    *,
    resource_id: str | None = None,
    actor_user=None,
    details: dict,
) -> None:
    """The shared best-effort emission chokepoint."""
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="DATABRICKS_DLT_PIPELINE",
            action=action,
            actor_user=actor_user,
            tenant=workspace.tenant,
            resource_id=resource_id,
            details=details,
        )
    except Exception:
        logger.warning(
            "databricks_dlt_audit_failed",
            extra={"action": action, "workspace_id": str(workspace.id)},
        )


def emit_dlt_pipeline_audit(
    action: str,
    workspace: DatabricksWorkspace,
    pipeline_id: str,
    *,
    actor_user=None,
) -> None:
    """One row per performed pipeline lifecycle operation
    (CREATED/UPDATED/DELETED). The mirror row's pk anchors
    ``resource_id`` when it exists; identifiers only in the details."""
    from hub.apps.databricks_admin.models import DatabricksDltPipeline

    mirror = DatabricksDltPipeline.objects.filter(
        workspace=workspace, pipeline_id=pipeline_id
    ).first()
    _emit(
        action,
        workspace,
        resource_id=mirror.id if mirror is not None else None,
        actor_user=actor_user,
        details={
            "pipeline_id": pipeline_id,
            "workspace_id": str(workspace.id),
        },
    )


def emit_dlt_update_started(
    workspace: DatabricksWorkspace,
    pipeline: DatabricksDltPipeline,
    update_id: str,
    *,
    actor_user=None,
) -> None:
    """The dispatch chokepoint — one STARTED row after the client's
    ``start_update`` succeeds (the 4.4 RUN_STARTED-at-dispatch
    convention)."""
    _emit(
        "DATABRICKS_DLT_UPDATE_STARTED",
        workspace,
        resource_id=pipeline.id,
        actor_user=actor_user,
        details={
            "pipeline_id": pipeline.pipeline_id,
            "update_id": update_id,
            "workspace_id": str(workspace.id),
        },
    )


def emit_dlt_update_terminal(
    workspace: DatabricksWorkspace,
    pipeline: DatabricksDltPipeline,
    update_row: DatabricksDltPipelineUpdate,
) -> None:
    """The terminal chokepoint — SUCCEEDED for COMPLETED, FAILED for
    every other terminal state (FAILED/CANCELED/TIMED_OUT — the status
    != COMPLETED convention, the 4.4 discipline)."""
    action = (
        "DATABRICKS_DLT_UPDATE_SUCCEEDED"
        if update_row.state in _SUCCEEDED_STATES
        else "DATABRICKS_DLT_UPDATE_FAILED"
    )
    _emit(
        action,
        workspace,
        resource_id=update_row.id,
        details={
            "pipeline_id": pipeline.pipeline_id,
            "update_id": update_row.update_id,
            "workspace_id": str(workspace.id),
        },
    )
