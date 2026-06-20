"""
285.6.2.5 — DLT ingestion execution entry point.

Called by the scheduled ingestion workflow and service layer when
``tenant.data_movement_enabled`` is True.  Replaces the legacy
``SourceConnectorFactory`` path with the dlt unified pipeline.
"""

from __future__ import annotations

import logging
from typing import Any

from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.data_movement.dlt_credentials import resolve_credentials
from hub.data_movement.dlt_pipeline import (
    SOURCE_MAP,
    create_ingestion_pipeline,
)

logger = logging.getLogger(__name__)


def execute_dlt_ingestion(scheduled_ingestion_id: str) -> dict[str, Any]:
    """Execute a scheduled ingestion via the dlt DataMovementPipeline.

    Returns a dict matching the existing workflow output shape so callers
    can treat both code paths uniformly:
        {
            "files_found": int,
            "files_processed": int,
            "files_failed": int,
            "datasets_created": int,
            "error_message": str | None,
        }
    """
    obj = ScheduledIngestion.objects.select_related("tenant").get(id=scheduled_ingestion_id)

    # ---- resolve credentials -----------------------------------------------
    creds = resolve_credentials(obj.credential_ref) if obj.credential_ref else {}
    (obj.get_source_config() if hasattr(obj, "get_source_config") else (obj.source_config or {}))

    # ---- create pipeline ----------------------------------------------------
    pipeline = create_ingestion_pipeline(
        source_type=obj.source_type,
        pipeline_name=f"ingestion-{obj.id}",
        credential_ref=obj.credential_ref,
    )

    dlt_source = SOURCE_MAP.get(obj.source_type, "filesystem")
    logger.info(
        "dlt_ingestion_starting",
        ingestion_id=scheduled_ingestion_id,
        source_type=obj.source_type,
        dlt_source=dlt_source,
        tenant_id=str(obj.tenant_id),
    )

    # ---- run pipeline -------------------------------------------------------
    files_found = 0
    files_processed = 0
    files_failed = 0
    datasets_created = 0
    error_message = None

    try:
        result = pipeline.run(
            resources=[],  # dlt resources from dlt_resources module
            credentials=creds,
        )
        # Extract counts from dlt LoadInfo (available after pipeline.run())
        for load in result.get("loads", []):
            if load.get("status") == "completed":
                files_processed += 1
            elif load.get("status") == "failed":
                files_failed += 1

        files_found = files_processed + files_failed
        datasets_created = files_processed  # one dataset per successfully ingested file

        logger.info(
            "dlt_ingestion_completed",
            ingestion_id=scheduled_ingestion_id,
            files_found=files_found,
            files_processed=files_processed,
            files_failed=files_failed,
        )
    except Exception as exc:
        error_message = str(exc)
        logger.exception(
            "dlt_ingestion_failed",
            ingestion_id=scheduled_ingestion_id,
            error=error_message,
        )

    # ---- emit audit event ---------------------------------------------------
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="SCHEDULED_INGESTION",
            action="DLT_INGESTION_COMPLETED",
            actor_user=None,
            tenant=obj.tenant,
            resource_id=str(obj.id),
            result="SUCCESS" if not error_message else "FAILURE",
            details={
                "files_found": files_found,
                "files_processed": files_processed,
                "files_failed": files_failed,
                "datasets_created": datasets_created,
                "dlt_source": dlt_source,
                "error_message": error_message,
            },
            infer_tenant_from_actor=False,
        )
    except Exception:
        logger.exception("dlt_ingestion_audit_failed")

    return {
        "files_found": files_found,
        "files_processed": files_processed,
        "files_failed": files_failed,
        "datasets_created": datasets_created,
        "error_message": error_message,
    }
