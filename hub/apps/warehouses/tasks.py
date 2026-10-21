"""
Phase 277.B.047 — Async warehouse query tasks.

Long-running queries (>5s estimated) are dispatched to django_rq
instead of blocking a gunicorn worker.  The task wraps execution in
``tenant_context(tenant_id)`` per CLAUDE.md RLS contract and emits
a Job row so the SPA can poll `/jobs/{id}/` for completion.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from django.utils import timezone

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.utils import get_queue_for_job_type

logger = logging.getLogger(__name__)

# Queries with estimated duration above this threshold are routed to RQ.
ASYNC_ESTIMATED_DURATION_THRESHOLD_S = 5

# Fallback timeout for async warehouse queries.
WAREHOUSE_ASYNC_TIMEOUT_S = 3600  # 1 hour


def enqueue_warehouse_query(
    *,
    warehouse_type: str,
    tenant_id: str,
    user_id: str,
    sql: str,
    params: dict[str, Any] | None = None,
    resource_id: str = "",
    resource_type: str = "WAREHOUSE_QUERY",
    force_async: bool = False,
    estimated_duration_s: int = 0,
) -> Job:
    """
    Dispatch a warehouse query to django_rq if it's expected to be
    long-running.  Returns a ``Job`` row the SPA can poll.

    Short cached queries (<ASYNC_ESTIMATED_DURATION_THRESHOLD_S) are
    NOT enqueued when ``force_async`` is False — the caller should
    execute them synchronously instead.
    """
    if not force_async and estimated_duration_s < ASYNC_ESTIMATED_DURATION_THRESHOLD_S:
        raise ValueError(
            f"Query estimated at {estimated_duration_s}s — below async threshold "
            f"({ASYNC_ESTIMATED_DURATION_THRESHOLD_S}s). Execute synchronously."
        )

    from hub.apps.tenants.models import Tenant

    tenant = Tenant.objects.get(id=tenant_id)

    job = Job.objects.create(
        tenant=tenant,
        type=JobType.WAREHOUSE_QUERY,
        resource_type=resource_type,
        resource_id=resource_id or "",
        status=JobStatus.PENDING,
        details_json={
            "sql": sql,
            "params": params,
            "warehouse_type": warehouse_type,
            "user_id": user_id,
            "estimated_duration_s": estimated_duration_s,
        },
        created_by_id=user_id or None,
    )

    queue = get_queue_for_job_type(JobType.WAREHOUSE_QUERY)
    queue.enqueue(
        _execute_warehouse_query_async,
        str(job.id),
        job_type=JobType.WAREHOUSE_QUERY,
        timeout=WAREHOUSE_ASYNC_TIMEOUT_S,
    )

    logger.info(
        "warehouse_query_enqueued",
        job_id=str(job.id),
        warehouse_type=warehouse_type,
        tenant_id=tenant_id,
        estimated_duration_s=estimated_duration_s,
    )

    return job


def _execute_warehouse_query_async(job_id: str) -> dict[str, Any]:
    """
    RQ task entry point.  Wraps execution in ``tenant_context()``
    per CLAUDE.md RLS contract so the warehouse connector sees the
    correct tenant GUC.
    """
    from hub.apps.jobs.models import Job, JobStatus
    from hub.apps.tenants.request_tenant import tenant_context

    job = Job.objects.get(id=job_id)
    details = job.details_json or {}
    tenant_id = str(job.tenant_id) if job.tenant_id else ""
    warehouse_type = details.get("warehouse_type", "")
    sql = details.get("sql", "")
    params = details.get("params")

    # ── Tenant context (RLS contract) ──────────────────────────────
    with tenant_context(tenant_id):
        job.status = JobStatus.RUNNING
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at", "updated_at"])

        try:
            connector = _get_connector(warehouse_type, tenant_id, job)
            started = time.monotonic()
            result = connector.execute_query(sql, params=params)
            elapsed_ms = (time.monotonic() - started) * 1000

            job.status = JobStatus.COMPLETED
            job.completed_at = timezone.now()
            job.details_json = {
                **details,
                "result": {
                    "columns": result.columns,
                    "row_count": len(result.rows),
                    "sample_rows": result.rows[:100],
                },
                "elapsed_ms": elapsed_ms,
            }
            job.save(update_fields=["status", "completed_at", "details_json", "updated_at"])

            logger.info(
                "warehouse_query_completed",
                job_id=str(job.id),
                warehouse_type=warehouse_type,
                elapsed_ms=elapsed_ms,
                row_count=len(result.rows),
            )
            return {"status": "COMPLETED", "row_count": len(result.rows)}

        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)[:2000]
            job.completed_at = timezone.now()
            job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])

            logger.error(
                "warehouse_query_failed",
                job_id=str(job.id),
                warehouse_type=warehouse_type,
                error=str(exc),
                exc_info=True,
            )
            return {"status": "FAILED", "error": str(exc)}


def _get_connector(warehouse_type: str, tenant_id: str, job: Job):
    """Instantiate the correct connector for the warehouse type."""
    from hub.apps.warehouses.connectors.athena import AthenaConnector
    from hub.apps.warehouses.connectors.bigquery import BigQueryConnector
    from hub.apps.warehouses.connectors.databricks import DatabricksConnector
    from hub.apps.warehouses.connectors.snowflake import SnowflakeConnector
    from hub.apps.warehouses.models import WarehouseConnection

    connection = WarehouseConnection.objects.filter(
        tenant_id=tenant_id,
        warehouse_type=warehouse_type,
    ).first()
    if not connection:
        raise ValueError(f"No WarehouseConnection for tenant={tenant_id} type={warehouse_type}")

    connector_cls = {
        "athena": AthenaConnector,
        "bigquery": BigQueryConnector,
        "databricks": DatabricksConnector,
        "snowflake": SnowflakeConnector,
    }.get(warehouse_type)

    if not connector_cls:
        raise ValueError(f"Unknown warehouse type: {warehouse_type}")

    return connector_cls(
        connection_config=connection.config or {},
        tenant_id=tenant_id,
        request_id=str(job.id),
    )
