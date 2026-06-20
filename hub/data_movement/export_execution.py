"""
285.6.2.6 — DLT export execution entry point.

Called by the scheduled export service when ``tenant.data_movement_enabled``
is True (or when the destination is a warehouse type with no legacy connector).
Replaces the ``DestinationConnectorFactory`` path with dlt verified
destinations.
"""

from __future__ import annotations

import logging
from typing import Any

from hub.apps.scheduled_export.models import ScheduledExport
from hub.data_movement.dlt_credentials import resolve_credentials
from hub.data_movement.dlt_pipeline import (
    DESTINATION_MAP,
    create_export_pipeline,
)

logger = logging.getLogger(__name__)

# Warehouse destination types that have NO legacy connector implementation.
# These MUST go through the dlt path regardless of the feature flag.
_WAREHOUSE_DESTINATIONS = frozenset(
    {
        "SNOWFLAKE_TABLE",
        "BIGQUERY_TABLE",
        "DATABRICKS_TABLE",
        "ATHENA_TABLE",
    }
)


def execute_dlt_export(scheduled_export_id: str) -> dict[str, Any]:
    """Execute a scheduled export via the dlt DataMovementPipeline.

    Returns a dict matching the existing export output shape:
        {
            "items_found": int,
            "items_exported": int,
            "items_failed": int,
            "error_message": str | None,
        }
    """
    obj = ScheduledExport.objects.select_related("tenant").get(id=scheduled_export_id)

    # ---- resolve credentials -----------------------------------------------
    creds = resolve_credentials(obj.credential_ref) if obj.credential_ref else {}
    dest_config = (
        obj.get_destination_config()
        if hasattr(obj, "get_destination_config")
        else (obj.destination_config or {})
    )

    # ---- create pipeline ----------------------------------------------------
    dlt_dest = DESTINATION_MAP.get(obj.destination_type, "filesystem")
    pipeline = create_export_pipeline(
        destination_type=obj.destination_type,
        pipeline_name=f"export-{obj.id}",
        credential_ref=obj.credential_ref,
    )

    logger.info(
        "dlt_export_starting",
        export_id=scheduled_export_id,
        destination_type=obj.destination_type,
        dlt_destination=dlt_dest,
        tenant_id=str(obj.tenant_id),
    )

    # ---- run pipeline -------------------------------------------------------
    items_found = 0
    items_exported = 0
    items_failed = 0
    error_message = None

    try:
        result = pipeline.run(
            resources=[],
            credentials=creds,
            **dest_config,
        )
        for load in result.get("loads", []):
            if load.get("status") == "completed":
                items_exported += 1
            elif load.get("status") == "failed":
                items_failed += 1

        items_found = items_exported + items_failed

        logger.info(
            "dlt_export_completed",
            export_id=scheduled_export_id,
            items_found=items_found,
            items_exported=items_exported,
            items_failed=items_failed,
        )
    except Exception as exc:
        error_message = str(exc)
        logger.exception(
            "dlt_export_failed",
            export_id=scheduled_export_id,
            error=error_message,
        )

    # ---- emit audit event ---------------------------------------------------
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="SCHEDULED_EXPORT",
            action="DLT_EXPORT_COMPLETED",
            actor_user=None,
            tenant=obj.tenant,
            resource_id=str(obj.id),
            result="SUCCESS" if not error_message else "FAILURE",
            details={
                "items_found": items_found,
                "items_exported": items_exported,
                "items_failed": items_failed,
                "dlt_destination": dlt_dest,
                "error_message": error_message,
            },
            infer_tenant_from_actor=False,
        )
    except Exception:
        logger.exception("dlt_export_audit_failed")

    return {
        "items_found": items_found,
        "items_exported": items_exported,
        "items_failed": items_failed,
        "error_message": error_message,
    }
