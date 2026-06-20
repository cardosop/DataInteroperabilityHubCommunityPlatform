"""
285.6.2 — Shared worker run lifecycle for dlt pipelines.

Unifies the duplicated worker lifecycle from scheduled_ingestion and scheduled_export.
"""

from __future__ import annotations

from typing import Any

import structlog
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event

logger = structlog.get_logger(__name__)


def start_run(
    run_instance,
    job_id: str,
    tenant_id: str,
    direction: str,
) -> dict[str, Any]:
    """Mark a run as STARTED and emit audit event."""
    run_instance.status = "RUNNING"
    run_instance.started_at = timezone.now()
    run_instance.save(update_fields=["status", "started_at"])

    try:
        create_audit_event(
            resource_type="SCHEDULED_RUN",
            action=f"{direction.upper()}_RUN_STARTED",
            tenant_id=tenant_id,
            resource_id=str(run_instance.id),
            details={"job_id": job_id, "direction": direction},
        )
    except Exception:
        logger.warning("audit_emit_failed", event="run_started", run_id=str(run_instance.id))

    return {"status": "RUNNING", "started_at": run_instance.started_at.isoformat()}


def complete_run(
    run_instance,
    job_id: str,
    tenant_id: str,
    direction: str,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mark a run as COMPLETED and emit audit event."""
    run_instance.status = "COMPLETED"
    run_instance.completed_at = timezone.now()
    if result:
        run_instance.result_json = result
    run_instance.save(update_fields=["status", "completed_at", "result_json"])

    try:
        create_audit_event(
            resource_type="SCHEDULED_RUN",
            action=f"{direction.upper()}_RUN_COMPLETED",
            tenant_id=tenant_id,
            resource_id=str(run_instance.id),
            details={"job_id": job_id, "direction": direction},
        )
    except Exception:
        logger.warning("audit_emit_failed", event="run_completed", run_id=str(run_instance.id))

    return {"status": "COMPLETED", "completed_at": run_instance.completed_at.isoformat()}


def fail_run(
    run_instance,
    job_id: str,
    tenant_id: str,
    direction: str,
    error: str,
) -> dict[str, Any]:
    """Mark a run as FAILED and emit audit event."""
    run_instance.status = "FAILED"
    run_instance.completed_at = timezone.now()
    run_instance.error_message = error[:1000]
    run_instance.save(update_fields=["status", "completed_at", "error_message"])

    try:
        create_audit_event(
            resource_type="SCHEDULED_RUN",
            action=f"{direction.upper()}_RUN_FAILED",
            tenant_id=tenant_id,
            resource_id=str(run_instance.id),
            details={"job_id": job_id, "direction": direction, "error": error[:256]},
            result="FAILURE",
        )
    except Exception:
        logger.warning("audit_emit_failed", event="run_failed", run_id=str(run_instance.id))

    return {"status": "FAILED", "error": error[:256]}
