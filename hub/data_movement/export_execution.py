"""
285.6.2.6 — DLT export execution entry point.

Called by the scheduled export service when ``tenant.data_movement_enabled``
is True (or when the destination is a warehouse type with no legacy connector).
Replaces the ``DestinationConnectorFactory`` path with dlt verified
destinations.

Task 6.5 (design D4) wiring: the pre-export ODCS contract validation runs
BEFORE any movement work (an invalid contract fails the run with ZERO side
effects — no credential resolution, no staging target, no pipeline); the
Databricks path resolves the managed-volume staging target + a scoped write
credential fail-closed; and the pipeline.run executes INSIDE the
guard-bypass scope via ``MovementPipelineExecutor`` — the only place in the
repo where the read-only guard is bypassed.
"""

from __future__ import annotations

from typing import Any

import structlog

from hub.apps.audit import event_types
from hub.apps.scheduled_export.models import DestinationType, ScheduledExport
from hub.data_movement.audit_events import emit_export_transition
from hub.data_movement.dlt_credentials import resolve_credentials
from hub.data_movement.dlt_pipeline import (
    DESTINATION_MAP,
    create_export_pipeline,
)
from hub.data_movement.export_preflight import (
    ExportContractValidationError,
    validate_export_contracts,
)
from hub.data_movement.load_outcome import load_outcome
from hub.data_movement.pipeline_scope import (
    CredentialNotResolvedError,
    MovementPipelineExecutor,
    ScopedCredentialError,
    ScopedWriteCredential,
)
from hub.data_movement.staging import DatabricksStagingRefused, resolve_staging_target

logger = structlog.get_logger(__name__)

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


def _scoped_credential_for(target, resolved: dict) -> ScopedWriteCredential:
    """Bind the resolved credential material to the staging target — the
    scoped write credential the pipeline runs with (spec: PAT/M2M from the
    configured stores, never a new store, never plaintext in configs).

    Fail-closed: no token-shaped material → ``CredentialNotResolvedError``.
    An M2M-shaped config (client_id/secret) cannot be materialized here —
    the connection-backed resolver lands in task 6.6.
    """
    material = resolved.get("token") or resolved.get("secret_value") or resolved.get("password")
    if isinstance(material, str) and material.strip():
        return ScopedWriteCredential(kind="PAT", material=material, target=target.qualified)
    if resolved.get("client_id"):
        raise CredentialNotResolvedError(
            "M2M-shaped credential config cannot be materialized for the staging "
            "target — the WarehouseConnection-backed resolver lands in task 6.6"
        )
    raise CredentialNotResolvedError(
        f"no scoped write credential material resolved for the UC staging target "
        f"{target.qualified} — the pipeline refuses to run without one"
    )


def _record_export_failure(obj: ScheduledExport, exc: Exception) -> dict[str, Any]:
    """Record a pre-run refusal (zero side effects) as a FAILURE outcome."""
    error_message = f"{getattr(exc, 'code', 'EXPORT_FAILED')}: {exc}"
    logger.error(
        "dlt_export_refused",
        export_id=str(obj.id),
        error=error_message,
    )
    # 6.9 — a refused run never dispatched: the FAILED terminal row only
    # (no STARTED row — the movement never began).
    emit_export_transition(
        event_types.WAREHOUSE_EXPORT_FAILED,
        obj,
        details={"error_message": error_message},
    )
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="SCHEDULED_EXPORT",
            action="DLT_EXPORT_COMPLETED",
            actor_user=None,
            tenant=obj.tenant,
            resource_id=str(obj.id),
            result="FAILURE",
            details={
                "items_found": 0,
                "items_exported": 0,
                "items_failed": 0,
                "error_message": error_message,
            },
            infer_tenant_from_actor=False,
        )
    except Exception:
        logger.exception("dlt_export_audit_failed")
    return {
        "items_found": 0,
        "items_exported": 0,
        "items_failed": 0,
        "error_message": error_message,
    }


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

    # ---- pre-flight: ODCS contract validation BEFORE any movement work --
    try:
        validate_export_contracts(obj)
    except ExportContractValidationError as exc:
        return _record_export_failure(obj, exc)

    # ---- destination config -------------------------------------------------
    dest_config = (
        obj.get_destination_config()
        if hasattr(obj, "get_destination_config")
        else (obj.destination_config or {})
    )

    # ---- the pipeline execution context (task 6.5) -------------------------
    # The Databricks path resolves the managed-volume staging target FIRST
    # (a refused target stops the run before any credential work), then the
    # scoped write credential fail-closed; every path runs the pipeline
    # INSIDE the guard-bypass scope via the executor.
    executor = MovementPipelineExecutor(tenant=obj.tenant)
    creds: dict = {}
    if obj.destination_type == DestinationType.DATABRICKS_TABLE:
        try:
            staging_target = resolve_staging_target(obj.tenant, destination_config=dest_config)
        except DatabricksStagingRefused as exc:
            return _record_export_failure(obj, exc)
        creds = resolve_credentials(obj.credential_ref) if obj.credential_ref else {}
        try:
            credential = _scoped_credential_for(staging_target, creds)
            executor = MovementPipelineExecutor(
                tenant=obj.tenant,
                staging_target=staging_target,
                credential=credential,
            )
        except (CredentialNotResolvedError, ScopedCredentialError) as exc:
            return _record_export_failure(obj, exc)
    else:
        creds = resolve_credentials(obj.credential_ref) if obj.credential_ref else {}

    # ---- create pipeline ----------------------------------------------------
    dlt_dest = DESTINATION_MAP.get(obj.destination_type, "filesystem")
    pipeline = create_export_pipeline(
        destination_type=obj.destination_type,
        pipeline_name=f"export-{obj.id}",
        credential_ref=obj.credential_ref,
    )

    # 6.9 — the dispatch chokepoint: one STARTED row per dispatched run.
    emit_export_transition(
        event_types.WAREHOUSE_EXPORT_STARTED,
        obj,
        details={
            "destination_type": obj.destination_type,
            "dlt_destination": dlt_dest,
        },
    )

    logger.info(
        "dlt_export_starting",
        export_id=scheduled_export_id,
        destination_type=obj.destination_type,
        dlt_destination=dlt_dest,
        tenant_id=str(obj.tenant_id),
    )

    # ---- run pipeline (inside the guard-bypass scope) ----------------------
    items_found = 0
    items_exported = 0
    items_failed = 0
    error_message = None

    # 6.11 — the source scope becomes the dlt resources (the hub performs
    # the write); the destination config maps onto the dlt destination
    # credentials (dlt's run() takes credentials=, NOT ad-hoc kwargs — the
    # previous **dest_config splat crashed every real run with TypeError).
    from hub.data_movement.export_sources import export_resources

    resources = export_resources(obj)
    run_credentials = creds
    if obj.destination_type == DestinationType.DATABRICKS_TABLE:
        run_credentials = {
            **creds,
            "server_hostname": dest_config.get("host", ""),
            "http_path": dest_config.get("http_path", ""),
            "catalog": dest_config.get("catalog", ""),
        }
        # Normalize the resolved material onto dlt's credential key: the
        # legacy resolver's token/secret_value/password shapes (and the
        # 6.6 resolver's access_token) all become the destination's
        # access_token (the same material _scoped_credential_for accepts).
        material = (
            creds.get("access_token")
            or creds.get("token")
            or creds.get("secret_value")
            or creds.get("password")
        )
        if material:
            run_credentials["access_token"] = material

    try:
        result = executor.execute(
            lambda: pipeline.run(resources=resources, credentials=run_credentials)
        )
        # W3.4 — the canonical extraction shared with the ingestion
        # cursor: the REAL dlt 1.30 LoadInfo (load_packages/.state) or
        # the legacy fixture dict shape.  The pre-fix
        # ``result.get("loads")`` AttributeError'd on every REAL run,
        # zeroing the counts and failing the audit.
        counts = load_outcome(result)
        items_exported = counts["succeeded"]
        items_failed = counts["failed"]

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

    # ---- emit audit events --------------------------------------------------
    # 6.9 — the terminal chokepoint: ONE COMPLETED or FAILED row per run
    # (best-effort via the shared emitter, alongside the dlt-level row).
    emit_export_transition(
        event_types.WAREHOUSE_EXPORT_COMPLETED
        if not error_message
        else event_types.WAREHOUSE_EXPORT_FAILED,
        obj,
        details={
            "items_found": items_found,
            "items_exported": items_exported,
            "items_failed": items_failed,
            "dlt_destination": dlt_dest,
            "error_message": error_message,
        },
    )
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
