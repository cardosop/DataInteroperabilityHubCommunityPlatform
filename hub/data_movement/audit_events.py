"""Phase 6 (openspec wire-databricks-dlt-movement task 6.9, design D6) —
the warehouse movement audit set.

One row per Hub-side transition: ``WAREHOUSE_EXPORT_STARTED`` at the
export dispatch chokepoint, ``WAREHOUSE_EXPORT_COMPLETED`` or
``WAREHOUSE_EXPORT_FAILED`` at the export terminal (a refused run never
dispatched — it writes ONLY the FAILED terminal row); the
``WAREHOUSE_INTAKE_*`` mirror rides the ingestion legs.

Best-effort (the Phase 273 contract): an audit-DB outage NEVER blocks the
movement — every emission is swallowed with a warning, never raised.
"""

from __future__ import annotations

from typing import Any

import structlog

from hub.apps.audit import event_types
from hub.apps.audit.utils import create_audit_event

logger = structlog.get_logger(__name__)

_EXPORT_RESOURCE_TYPE = "SCHEDULED_EXPORT"
_INTAKE_RESOURCE_TYPE = "SCHEDULED_INGESTION"

# The terminal-success actions per direction (everything else in the set
# is a FAILURE terminal).
_EXPORT_SUCCESS_ACTION = event_types.WAREHOUSE_EXPORT_COMPLETED
_INTAKE_SUCCESS_ACTION = event_types.WAREHOUSE_INTAKE_COMPLETED


def _emit(
    *,
    resource_type: str,
    action: str,
    tenant,
    resource_id: str,
    success_action: str,
    details: dict[str, Any],
) -> None:
    try:
        create_audit_event(
            resource_type=resource_type,
            action=action,
            actor_user=None,
            tenant=tenant,
            resource_id=resource_id,
            result="SUCCESS" if action == success_action else "FAILURE",
            details=details,
            infer_tenant_from_actor=False,
        )
    except Exception:
        # outage never blocks the movement.
        logger.warning(
            "warehouse_audit_emit_failed",
            action=action,
            resource_id=resource_id,
        )


def emit_export_transition(action: str, export, *, details: dict[str, Any] | None = None) -> None:
    """One best-effort audit row per export Hub-side transition."""
    _emit(
        resource_type=_EXPORT_RESOURCE_TYPE,
        action=action,
        tenant=export.tenant,
        resource_id=str(export.id),
        success_action=_EXPORT_SUCCESS_ACTION,
        details=details or {},
    )


def emit_intake_transition(
    action: str, ingestion, *, details: dict[str, Any] | None = None
) -> None:
    """One best-effort audit row per intake Hub-side transition."""
    _emit(
        resource_type=_INTAKE_RESOURCE_TYPE,
        action=action,
        tenant=ingestion.tenant,
        resource_id=str(ingestion.id),
        success_action=_INTAKE_SUCCESS_ACTION,
        details=details or {},
    )
