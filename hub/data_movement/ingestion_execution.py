"""
285.6.2.5 — DLT ingestion execution entry point.

Called by the scheduled ingestion workflow and service layer when
``tenant.data_movement_enabled`` is True.  Replaces the legacy
``SourceConnectorFactory`` path with the dlt unified pipeline.
"""

from __future__ import annotations

from typing import Any

import structlog

from hub.apps.audit import event_types
from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.data_movement.audit_events import emit_intake_transition
from hub.data_movement.dlt_credentials import resolve_credentials
from hub.data_movement.dlt_pipeline import (
    SOURCE_MAP,
    create_ingestion_pipeline,
)
from hub.data_movement.load_outcome import load_outcome
from hub.data_movement.pipeline_scope import MovementPipelineExecutor
from hub.data_movement.retry_policy import RetryExhaustedError, call_with_bounded_retry
from hub.data_movement.warehouse_query_runner import (
    WarehouseQueryRunner,
    WarehouseQueryRunnerError,
)

logger = structlog.get_logger(__name__)


def _normalize_discovered_files(files: list[Any]) -> list[dict[str, Any]]:
    """Bridge the connector/dlt discovery contract.

    The source connectors return ``list[str]`` object keys (the legacy
    workflow's contract — services/prefect-integration/connectors/
    s3_connector.py ``discover_files``), while the dlt ``ingest_files``
    resource consumes ``{"key": ...}`` dicts. Bare strings map to
    ``{"key": s}``; dicts pass through unchanged. Without this bridge a
    REAL S3 source with files failed every run with
    ``AttributeError: 'str' object has no attribute 'get'``
    (JOURNEY-INGESTION-001 real-work blocker, 2026-10-03).
    """
    normalized: list[dict[str, Any]] = []
    for item in files:
        if isinstance(item, str):
            normalized.append({"key": item})
        elif isinstance(item, dict):
            normalized.append(item)
        else:
            logger.warning(
                "dlt_ingestion_unknown_discovery_item",
                item_type=type(item).__name__,
            )
    return normalized


def _discover_source_files(obj: ScheduledIngestion) -> list[dict[str, Any]]:
    """Discover the source's files via the source-connector factory.

    Mirrors the legacy workflow's ``_discover_files_task`` (285.6.3.1):
    the connector module lives in the prefect-integration service
    package, so the factory is imported lazily; the decrypted config
    comes from the model's ``get_source_config()`` (the ``_encrypted``
    envelope at rest is transparent here).
    """
    from hub.apps.orchestration.workflows.scheduled_ingestion import (
        _get_source_connector_or_fail,
    )

    config = obj.get_source_config()

    connector = _get_source_connector_or_fail(obj.source_type)
    pattern = obj.file_pattern or ".*"
    return _normalize_discovered_files(connector.discover_files(config, pattern))


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

    # 6.9 — the dispatch chokepoint: one INTAKE_STARTED row per dispatched run.
    emit_intake_transition(
        event_types.WAREHOUSE_INTAKE_STARTED,
        obj,
        details={"source_type": obj.source_type},
    )

    # 6.7 — the DATABRICKS_SOURCE branch: the warehouse read is bounded by
    # the incremental cursor (dlt pipeline state, keyed per pipeline +
    # asset) and rows load through the dlt resource — a re-run resumes
    # from the last cursor, never a full re-read.
    if obj.source_type == "DATABRICKS_SOURCE":
        outcome = _run_databricks_source(obj)
        _emit_ingestion_audit(obj, "sql_database", outcome)
        return outcome

    # ---- resolve credentials -----------------------------------------------
    creds = resolve_credentials(obj.credential_ref) if obj.credential_ref else {}

    # ---- create pipeline ----------------------------------------------------
    pipeline_name = f"ingestion-{obj.id}"
    pipeline = create_ingestion_pipeline(
        source_type=obj.source_type,
        pipeline_name=pipeline_name,
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
    retry_count = 0
    error_message = None

    try:
        # Discover the source's files through the same connector factory
        # the legacy workflow uses (285.6.3.1). An empty source completes
        # with zero counts — the legacy terminal contract, no dlt run.
        files = _discover_source_files(obj)
        if not files:
            logger.info(
                "dlt_ingestion_no_files",
                ingestion_id=scheduled_ingestion_id,
                source_type=obj.source_type,
                tenant_id=str(obj.tenant_id),
            )
        else:
            from hub.data_movement.dlt_incremental import (
                get_processed_keys,
                mark_processed,
            )
            from hub.data_movement.dlt_resources import ingest_files

            # W3.3 (R2-P2) — the live-path incremental filter: discovery
            # returns the FULL file list on every run (the real source
            # contract), so the execution filters through the dlt
            # processed-key state. A re-run of an unchanged source
            # short-circuits before the pipeline; a file whose load
            # failed is NOT marked, so the next run retries it.
            processed_keys = set(get_processed_keys(pipeline_name))

            def _file_key(file) -> str:
                # Raw-string-safe: the resource's own contract accepts
                # bare string keys (``{"key": f}``) — the filter must
                # match it, never crash on them.
                if isinstance(file, str):
                    return file
                return file.get("key") or file.get("path", "")

            pending = [f for f in files if _file_key(f) and _file_key(f) not in processed_keys]
            if not pending:
                logger.info(
                    "dlt_ingestion_all_files_processed",
                    ingestion_id=scheduled_ingestion_id,
                    discovered=len(files),
                    processed=len(processed_keys),
                )
            else:
                resources = [ingest_files(pending, obj.source_type, obj.credential_ref)]
                # The pipeline execution context (task 6.5): the run executes
                # INSIDE the guard-bypass scope via the executor — the only place
                # the read-only guard is bypassed.
                # W3.9 (F6) — the bounded retry policy: RETRYABLE failures
                # (connection/timeout/refused) are retried with backoff;
                # permanent failures (schema/permission/resource) fail
                # immediately.  The pending keys are only marked on success
                # (W3.4), so a retried load can never double-process.
                executor = MovementPipelineExecutor(tenant=obj.tenant)
                try:
                    result, retry_count = call_with_bounded_retry(
                        lambda: executor.execute(
                            lambda: pipeline.run(resources=resources, credentials=creds)
                        )
                    )
                except RetryExhaustedError as exc:
                    # The bound is spent — record the budget and surface
                    # the ORIGINAL error text (str() delegates).
                    retry_count = exc.retry_count
                    raise
                # W3.4 — the canonical extraction: the REAL dlt 1.30
                # LoadInfo (load_packages/.state) or the legacy fixture
                # dict shape.  The pre-fix ``result.get("loads")``
                # AttributeError'd on every REAL run — the error path
                # then zeroed the counts and never advanced a key.
                counts = load_outcome(result)
                files_processed = counts["succeeded"]
                files_failed = counts["failed"]

                files_found = files_processed + files_failed

                # W3.8 (R2-P7/D6) — catalog parity: a fully successful
                # load creates the REAL File/Dataset records (the D6
                # parity-first fix). ``datasets_created`` counts the
                # real rows — created now or recovered from a crashed
                # earlier attempt — never the fabricated
                # ``files_processed`` echo. A catalog failure counts
                # the file as failed and leaves every key unmarked so
                # the next run retries the batch (the per-source-key
                # idempotency guard keeps the retry duplicate-free).
                if files_failed == 0 and files_processed > 0:
                    from hub.data_movement.ingestion_catalog import (
                        sync_catalog_records,
                    )

                    sync = sync_catalog_records(obj, pending)
                    datasets_created = sync.created + sync.recovered
                    if sync.failed:
                        files_failed += sync.failed
                        files_found = files_processed + files_failed
                        error_message = "catalog creation failed: " + "; ".join(
                            f"{f['file_key']}: {f['error']} ({f['code']})" for f in sync.failures
                        )
                    else:
                        # W3.4 (R2-P3) — cursor-on-success: the keys
                        # advance ONLY when the load AND the catalog
                        # creation fully succeeded.
                        mark_processed(pipeline_name, [_file_key(f) for f in pending])

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

    outcome = {
        "files_found": files_found,
        "files_processed": files_processed,
        "files_failed": files_failed,
        "datasets_created": datasets_created,
        "retry_count": retry_count,
        "error_message": error_message,
    }
    _emit_ingestion_audit(obj, dlt_source, outcome)
    return outcome


def _run_databricks_source(obj: ScheduledIngestion) -> dict[str, Any]:
    """6.7 — the DATABRICKS_SOURCE ingestion branch (design D1).

    The read goes through the REAL ``WarehouseQueryRunner`` bound to the
    source's warehouse connection (the 6.3 spine — the connection's own
    decrypted config is the identity), bounded by the incremental cursor
    recorded in the dlt pipeline state (keyed per pipeline + asset). The
    rows load through the dlt resource inside the guard-bypass executor
    scope; the cursor advances ONLY after a successful load — a failed
    run leaves it exactly where the last successful run put it.
    """
    # The lazy-dlt discipline (the 285 scaffold): the dlt-backed
    # incremental module imports at FUNCTION level so the entrypoint stays
    # importable without dlt installed (the 6.2 dispatch suites run in
    # environments without the full requirement set).
    from hub.data_movement.dlt_incremental import (
        advance_databricks_source_cursor,
        databricks_source_read_sql,
        databricks_source_rows,
        get_databricks_source_cursor,
    )

    pipeline_name = f"ingestion-{obj.id}"
    asset_key = str(obj.asset_id) if getattr(obj, "asset_id", None) else str(obj.id)
    outcome = {
        "files_found": 0,
        "files_processed": 0,
        "files_failed": 0,
        "datasets_created": 0,
        "error_message": None,
    }

    try:
        config = (
            obj.get_source_config()
            if hasattr(obj, "get_source_config")
            else (obj.source_config or {})
        )
        connection = _resolve_source_connection(obj, config)
        table_ref = str(config.get("table") or "").strip()
        cursor_field = str(config.get("cursor_field") or "updated_at").strip()

        cursor = get_databricks_source_cursor(pipeline_name, asset_key)
        sql, params = databricks_source_read_sql(table_ref, cursor_field, cursor)

        runner = WarehouseQueryRunner.from_connection(connection, query_type="ingestion")
        rows = runner.execute(sql, params)
        resource = databricks_source_rows(rows, asset_id=asset_key)

        creds = resolve_credentials(obj.credential_ref) if obj.credential_ref else {}
        pipeline = create_ingestion_pipeline(
            source_type=obj.source_type,
            pipeline_name=pipeline_name,
            credential_ref=obj.credential_ref,
        )
        executor = MovementPipelineExecutor(tenant=obj.tenant)
        # W3.9 (F6) — the bounded retry policy also covers the
        # DATABRICKS_SOURCE load (same retryable/permanent split).
        try:
            result, retry_count = call_with_bounded_retry(
                lambda: executor.execute(lambda: pipeline.run([resource], credentials=creds))
            )
        except RetryExhaustedError as exc:
            retry_count = exc.retry_count
            raise
        counts = load_outcome(result)
        outcome["files_processed"] = counts["succeeded"]
        outcome["files_failed"] = counts["failed"]
        outcome["files_found"] = outcome["files_processed"] + outcome["files_failed"]
        outcome["retry_count"] = retry_count

        # W3.8 (R2-P7/D6) — catalog parity on the DATABRICKS_SOURCE
        # branch: a fully successful read materializes its rows into ONE
        # File + Dataset (the JSONL payload), so ``datasets_created``
        # counts a REAL row — one dataset version per successful read.
        # The SQL cursor advances ONLY when the catalog row landed; a
        # failed materialization counts as a failed load and the next
        # run retries the same read (the cursor is unchanged).
        if outcome["files_failed"] == 0 and outcome["files_processed"] > 0:
            try:
                from hub.apps.scheduled_ingestion.catalog_records import (
                    check_ingestion_plan_limits,
                    create_file_and_dataset_records,
                )
                from hub.data_movement.ingestion_catalog import (
                    materialize_databricks_rows,
                )

                cursor_value = cursor.get("last_value") if cursor else None
                file_name, source_key, payload = materialize_databricks_rows(
                    rows,
                    asset_key=asset_key,
                    table_ref=table_ref,
                    cursor_value=cursor_value,
                )
                check_ingestion_plan_limits(str(obj.tenant_id), len(payload))
                create_file_and_dataset_records(obj, file_name, payload, source_key=source_key)
                outcome["datasets_created"] = 1

                # W3.4 (R2-P3) — cursor-on-success: the SQL cursor
                # advances ONLY when files_failed == 0 AND at least one
                # load was accounted AND the catalog row landed (the
                # pre-fix advanced unconditionally — a failed load
                # silently skipped the rows it had just read).
                advance_databricks_source_cursor(
                    pipeline_name, asset_key, cursor_field=cursor_field, rows=rows
                )
            except Exception as exc:
                outcome["files_failed"] += 1
                outcome["error_message"] = f"catalog creation failed: {exc}"
                logger.exception(
                    "dlt_databricks_source_catalog_failed",
                    ingestion_id=str(obj.id),
                    error=outcome["error_message"],
                )
        logger.info(
            "dlt_databricks_source_ingestion_completed",
            ingestion_id=str(obj.id),
            rows_read=len(rows),
            cursor_field=cursor_field,
        )
    except Exception as exc:
        outcome["error_message"] = str(exc)
        logger.exception(
            "dlt_databricks_source_ingestion_failed",
            ingestion_id=str(obj.id),
            error=outcome["error_message"],
        )
    return outcome


def _resolve_source_connection(obj: ScheduledIngestion, config: dict[str, Any]):
    """6.7 — the source's warehouse connection, scoped to the ingestion's
    tenant. Fail closed with the catalogued ``WAREHOUSE_CONNECTION_REQUIRED``
    classification BEFORE any warehouse work."""
    from hub.apps.warehouses.models import WarehouseConnection

    connection_id = config.get("warehouse_connection_id")
    if not connection_id:
        raise WarehouseQueryRunnerError(
            "WAREHOUSE_CONNECTION_REQUIRED",
            "a DATABRICKS_SOURCE ingestion needs a warehouse_connection_id "
            "in its source_config — fail-closed before any warehouse work",
        )
    connection = WarehouseConnection.objects.filter(
        id=connection_id, tenant_id=obj.tenant_id
    ).first()
    if connection is None:
        raise WarehouseQueryRunnerError(
            "WAREHOUSE_CONNECTION_REQUIRED",
            f"no WarehouseConnection {connection_id} for the ingestion's tenant",
        )
    return connection


def _emit_ingestion_audit(
    obj: ScheduledIngestion, dlt_source: str, outcome: dict[str, Any]
) -> None:
    """The DLT_INGESTION_COMPLETED audit — one row per Hub-side run
    (best-effort: an audit-DB outage never blocks the movement)."""
    # 6.9 — the terminal chokepoint: ONE INTAKE COMPLETED or FAILED row
    # per run, alongside the dlt-level row.
    emit_intake_transition(
        event_types.WAREHOUSE_INTAKE_COMPLETED
        if not outcome.get("error_message")
        else event_types.WAREHOUSE_INTAKE_FAILED,
        obj,
        details={
            "files_found": outcome.get("files_found", 0),
            "files_processed": outcome.get("files_processed", 0),
            "files_failed": outcome.get("files_failed", 0),
            "datasets_created": outcome.get("datasets_created", 0),
            "retry_count": outcome.get("retry_count", 0),
            "dlt_source": dlt_source,
            "error_message": outcome.get("error_message"),
        },
    )
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="SCHEDULED_INGESTION",
            action="DLT_INGESTION_COMPLETED",
            actor_user=None,
            tenant=obj.tenant,
            resource_id=str(obj.id),
            result="SUCCESS" if not outcome.get("error_message") else "FAILURE",
            details={
                "files_found": outcome.get("files_found", 0),
                "files_processed": outcome.get("files_processed", 0),
                "files_failed": outcome.get("files_failed", 0),
                "datasets_created": outcome.get("datasets_created", 0),
                "retry_count": outcome.get("retry_count", 0),
                "dlt_source": dlt_source,
                "error_message": outcome.get("error_message"),
            },
            infer_tenant_from_actor=False,
        )
    except Exception:
        logger.exception("dlt_ingestion_audit_failed")
