"""Phase 5 (openspec add-delta-sharing-server task 5.4) — the snapshot job.

A Parquet snapshot materializes through a Hub ``Job`` row
(``JobType.DATABRICKS_DELTA_SHARE_SNAPSHOT`` — design D4): the service
reads the share table's source rows through the warehouse connector
(the D12 background path — the connection's own credential IS the M2M
identity, the ``query_share_table_json`` pattern), writes Parquet + a
Delta-protocol log entry into Hub S3 through the production
``S3StorageClient``, and stamps the 5.3 ``DeltaShareSnapshot`` row
(version + the files manifest + the ``expires_at`` TTL stamp).

Contracts:

- **The job spine**: the Hub Job walks PENDING → RUNNING → terminal
  (the 4.4 precedent); a failure fails the Job with the message and
  NEVER stamps a row (no partial snapshots).
- **Idempotent re-materialization**: an existing row for the same
  (share, schema, table, version) is REUSED — the TTL is re-stamped
  (freshness validated), S3 is never rewritten, no duplicated version
  rows (the model's unique grain is the belt-and-braces).
- **TTL governs freshness**: ``ensure_fresh_snapshot`` serves a fresh
  snapshot with ZERO work (the 5.3 ``latest_snapshot`` lookup); an
  expired or missing one dispatches the refresh job and returns the
  (re)stamped row. A failed refresh raises ``DeltaShareSnapshotError``.
- **Fail-closed**: an asset without a warehouse connection is refused
  BEFORE any source read; malformed source data (duplicate columns,
  row-arity mismatch, a non-numeric version) is refused BEFORE any S3
  write; the RLS contract wraps every snapshot-table query in
  ``tenant_context``.
- **Audit best-effort**: ``DATABRICKS_SHARE_SNAPSHOT_COMPLETED`` /
  ``DATABRICKS_SHARE_SNAPSHOT_FAILED`` emitted at the terminal
  chokepoints (the action strings are the 5.7 constants' exact values —
  the event_types registration lands with 5.7, the 0b.1/4.4 precedent;
  ``create_audit_event`` does not validate actions). An audit-DB outage
  never blocks the snapshot (the Phase 273 contract).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.utils import timezone

from hub.apps.jobs.models import Job, JobStatus, JobType

if TYPE_CHECKING:
    from collections.abc import Callable

    from hub.apps.assets.models import Asset
    from hub.apps.databricks_admin.models import DeltaShareSnapshot

logger = logging.getLogger(__name__)

# The 5.7 audit actions — the CANONICAL constants (task 5.7 registers
# them; the emission references the same names, so a rename fails at the
# import site, the 0.16 contract).
from hub.apps.audit.event_types import (
    DATABRICKS_SHARE_SNAPSHOT_COMPLETED,  # constants are the module's
    DATABRICKS_SHARE_SNAPSHOT_FAILED,  # audit vocabulary
)

_AUDIT_ACTION_COMPLETED = DATABRICKS_SHARE_SNAPSHOT_COMPLETED
_AUDIT_ACTION_FAILED = DATABRICKS_SHARE_SNAPSHOT_FAILED
_AUDIT_RESOURCE_TYPE = "DELTA_SHARE_SNAPSHOT"

# The delta protocol's log entry shape: commitInfo + metaData + add (the
# 5.3 serving side parses these entries for the table version).
_DELTA_LOG_OPERATION = "WRITE"


class DeltaShareSnapshotError(Exception):
    """The snapshot service's classified failure (catalogued 500)."""

    code = "DELTA_SHARE_SNAPSHOT_FAILED"


@dataclass
class _SourceVersion:
    """The reader seam's contract: the materialized source version (the
    delta-table-version header) + the projected columns + rows."""

    version: int
    columns: list[str]
    rows: list[list] = field(default_factory=list)


def run_snapshot_job(
    *,
    asset: Asset,
    source_reader: Callable | None = None,
    actor_user=None,
    ttl_seconds: int | None = None,
    storage=None,
    now: Callable[[], datetime] = timezone.now,
) -> Job:
    """Run the snapshot job for the asset's share table and follow it to
    its terminal state (design D4).

    Returns the Hub ``Job`` row in its terminal state. The job's
    ``result_json`` carries ``snapshot_id`` (the stamped row) and
    ``reused_existing`` — the idempotency marker. All emissions are
    best-effort (the Phase 273 contract).
    """
    from hub.apps.databricks_admin.delta_sharing_service import (
        schema_name_for,
        share_name_for,
        table_name_for,
    )

    tenant = asset.tenant
    share = share_name_for(tenant)
    schema = schema_name_for(asset)
    table = table_name_for(asset)
    ttl = ttl_seconds if ttl_seconds is not None else settings.DELTA_SHARE_SNAPSHOT_TTL_SECONDS

    job = Job.objects.create(
        tenant=tenant,
        type=JobType.DATABRICKS_DELTA_SHARE_SNAPSHOT,
        status=JobStatus.PENDING,
        resource_type="ASSET",
        resource_id=asset.id,
        created_by=actor_user,
        details_json={
            "share_name": share,
            "schema_name": schema,
            "table_name": table,
        },
    )

    connection = getattr(asset, "warehouse_connection", None)
    if connection is None:
        # Fail-closed BEFORE any source read — an unconnected asset can
        # never be snapshotted (the spine still records the failure).
        _fail_job(
            job,
            "the asset has no warehouse connection — fail-closed before any source read",
            now=now,
        )
        _emit_snapshot_audit(
            _AUDIT_ACTION_FAILED,
            tenant=tenant,
            actor_user=actor_user,
            job=job,
            details={
                "share_name": share,
                "schema_name": schema,
                "table_name": table,
                "error": "the asset has no warehouse connection",
            },
        )
        return job

    job.status = JobStatus.RUNNING
    job.started_at = now()
    job.save(update_fields=["status", "started_at"])

    reader = source_reader or _connector_source_reader
    try:
        source = reader(connection, table, str(tenant.id))
        _validate_source(source)
        snapshot, reused = _materialize_or_reuse(
            tenant_id=tenant.id,
            share=share,
            schema=schema,
            table=table,
            source=source,
            ttl_seconds=ttl,
            storage=storage,
            now=now,
        )
    except Exception as exc:
        message = f"snapshot failed: {exc}"
        _fail_job(job, message, now=now)
        _emit_snapshot_audit(
            _AUDIT_ACTION_FAILED,
            tenant=tenant,
            actor_user=actor_user,
            job=job,
            details={
                "share_name": share,
                "schema_name": schema,
                "table_name": table,
                "error": str(exc),
            },
        )
        return job

    job.status = JobStatus.COMPLETED
    job.completed_at = now()
    job.result_json = {
        "source_version": source.version,
        "snapshot_id": str(snapshot.id),
        "reused_existing": reused,
        "files_count": len(snapshot.files),
    }
    job.save(update_fields=["status", "completed_at", "result_json"])
    _emit_snapshot_audit(
        _AUDIT_ACTION_COMPLETED,
        tenant=tenant,
        actor_user=actor_user,
        job=job,
        resource_id=str(snapshot.id),
        details={
            "share_name": share,
            "schema_name": schema,
            "table_name": table,
            "source_version": source.version,
            "files_count": len(snapshot.files),
        },
    )
    return job


def ensure_fresh_snapshot(
    *,
    asset: Asset,
    source_reader: Callable | None = None,
    actor_user=None,
    ttl_seconds: int | None = None,
    storage=None,
    now: Callable[[], datetime] = timezone.now,
) -> DeltaShareSnapshot:
    """The 5.3 data path's calling contract — a fresh snapshot is served
    as-is with ZERO work; an expired or missing one dispatches the
    refresh job and returns the (re)stamped row. A failed refresh raises
    ``DeltaShareSnapshotError``."""
    from hub.apps.databricks_admin.delta_sharing_service import (
        latest_snapshot,
        schema_name_for,
        share_name_for,
        table_name_for,
    )
    from hub.apps.databricks_admin.models import DeltaShareSnapshot
    from hub.apps.tenants.request_tenant import tenant_context

    tenant_id = str(asset.tenant_id)
    share = share_name_for(asset.tenant)
    schema = schema_name_for(asset)
    table = table_name_for(asset)

    # Tenant Isolation RLS contract: the freshness read is tenant-scoped —
    # wrap it here (self-contained; a direct caller without a request-
    # scoped GUC — the tests, the snapshot job spine — must still see the
    # tenant's own row, never dispatch a refresh over an invisible one).
    # The caller's clock rides through — the freshness comparison must use
    # the same `now` the stamp used (the time-bomb class).
    with tenant_context(tenant_id):
        fresh = latest_snapshot(tenant_id, share=share, schema=schema, table=table, now=now)
    if fresh is not None:
        return fresh

    job = run_snapshot_job(
        asset=asset,
        source_reader=source_reader,
        actor_user=actor_user,
        ttl_seconds=ttl_seconds,
        storage=storage,
        now=now,
    )
    if job.status != JobStatus.COMPLETED:
        raise DeltaShareSnapshotError(job.error_message or "the snapshot refresh failed")

    snapshot_id = (job.result_json or {}).get("snapshot_id")
    with tenant_context(tenant_id):
        if snapshot_id:
            try:
                return DeltaShareSnapshot.objects.get(id=snapshot_id, tenant_id=asset.tenant_id)
            except DeltaShareSnapshot.DoesNotExist:
                pass
        row = (
            DeltaShareSnapshot.objects.filter(
                tenant_id=asset.tenant_id,
                share_name=share,
                schema_name=schema,
                table_name=table,
            )
            .order_by("-version")
            .first()
        )
    if row is None:
        raise DeltaShareSnapshotError("the snapshot refresh produced no snapshot row")
    return row


def _connector_source_reader(connection, table_ref: str, tenant_id: str) -> _SourceVersion:
    """The production default reader (design D4) — the 5.3
    ``query_share_table_json`` pattern: the connector is built from the
    connection's own config (the background M2M identity) and reads the
    delta-table version header + the table rows."""
    import re

    from hub.apps.warehouses.base import get_connector_for_connection

    table_ref = (table_ref or "").strip()
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", table_ref):
        raise DeltaShareSnapshotError(
            f"Invalid table ref {table_ref!r} — never interpolated into SQL"
        )

    connector_class = get_connector_for_connection(connection.warehouse_type)
    config = connection.get_config()
    connector = connector_class(config, tenant_id=str(tenant_id))
    try:
        connector.connect()
        version_result = connector.execute_query(
            f"SELECT COALESCE(MAX(version), 0) FROM (DESCRIBE HISTORY {table_ref})"
        )
        version = int((version_result.rows[0][0] if version_result.rows else None) or 0)
        rows_result = connector.execute_query(
            f"SELECT * FROM {table_ref}", limit=settings.DELTA_SHARE_SNAPSHOT_MAX_ROWS
        )
        return _SourceVersion(
            version=version,
            columns=rows_result.columns,
            rows=rows_result.rows,
        )
    finally:
        connector.close()


def _materialize_or_reuse(
    *,
    tenant_id,
    share: str,
    schema: str,
    table: str,
    source: _SourceVersion,
    ttl_seconds: int,
    storage,
    now: Callable[[], datetime],
) -> tuple[DeltaShareSnapshot, bool]:
    """The idempotency + stamp chokepoint: an existing row for the SAME
    source version is reused (TTL re-stamped, S3 never rewritten); a new
    version writes the objects and stamps a new row. A stamp failure
    best-effort cleans the written objects (never orphaned S3)."""
    from hub.apps.databricks_admin.models import DeltaShareSnapshot
    from hub.apps.tenants.request_tenant import tenant_context

    with tenant_context(str(tenant_id)):
        existing = (
            DeltaShareSnapshot.objects.filter(
                tenant_id=tenant_id,
                share_name=share,
                schema_name=schema,
                table_name=table,
                version=source.version,
            )
            .order_by("-version")
            .first()
        )
        if existing is not None:
            existing.expires_at = now() + timedelta(seconds=ttl_seconds)
            existing.save(update_fields=["expires_at"])
            return existing, True

        files = _write_snapshot_objects(
            storage or _default_storage(),
            share=share,
            schema=schema,
            table=table,
            version=source.version,
            columns=source.columns,
            rows=source.rows,
        )
        try:
            row = DeltaShareSnapshot.objects.create(
                tenant_id=tenant_id,
                share_name=share,
                schema_name=schema,
                table_name=table,
                version=source.version,
                files=files,
                expires_at=now() + timedelta(seconds=ttl_seconds),
            )
        except Exception:
            _cleanup_written_objects(
                storage or _default_storage(), share, schema, table, source.version
            )
            raise
        return row, False


def _cleanup_written_objects(storage, share: str, schema: str, table: str, version: int) -> None:
    """Best-effort hygiene — a stamp failure never orphans S3 objects."""
    try:
        storage.delete_prefix(_version_base(share, schema, table, version))
    except Exception:
        logger.warning(
            "delta_share_snapshot_cleanup_failed",
            extra={"share": share, "schema": schema, "table": table, "version": version},
        )


def _write_snapshot_objects(
    storage,
    *,
    share: str,
    schema: str,
    table: str,
    version: int,
    columns: list[str],
    rows: list[list],
) -> list[dict]:
    """Materialize the REAL Parquet object + the Delta-protocol log entry
    into Hub S3; returns the files manifest
    ([{id, path, size, partition_values}]) the 5.3 row stamps."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    data = {columns[index]: [row[index] for row in rows] for index in range(len(columns))}
    arrow = pa.Table.from_pydict(data)
    sink = pa.BufferOutputStream()
    pq.write_table(arrow, sink, compression="snappy")
    payload = sink.getvalue().to_pybytes()

    file_id = uuid.uuid4().hex
    base = _version_base(share, schema, table, version)
    parquet_key = f"{base}part-00000-{file_id[:8]}.snappy.parquet"
    storage.upload_file(parquet_key, payload)

    files = [{"id": file_id, "path": parquet_key, "size": len(payload), "partition_values": {}}]
    log_key = f"{base}_delta_log/{version:020d}.json"
    storage.upload_file(
        log_key,
        json.dumps(
            _build_delta_log_entry(
                share=share,
                schema=schema,
                table=table,
                files=files,
                columns=columns,
            ),
            separators=(",", ":"),
        ),
    )
    return files


def _build_delta_log_entry(
    *, share: str, schema: str, table: str, files: list[dict], columns: list[str]
) -> dict:
    """The Delta-protocol log entry for the version (the 5.3 serving
    side parses it): commitInfo + metaData + one add per parquet file.
    The table's metaData id is DERIVED deterministically per
    (share/schema/table) — the protocol's stable-table-id contract."""
    now_ms = int(time.time() * 1000)
    prefix = settings.DELTA_SHARE_SNAPSHOT_STORAGE_PREFIX
    table_identity = f"{prefix}/{share}/{schema}/{table}"
    return {
        "commitInfo": {
            "timestamp": now_ms,
            "operation": _DELTA_LOG_OPERATION,
            "operationParameters": {"mode": "Append", "partitionBy": "[]"},
            "readVersion": -1,
            "isolationLevel": "Serializable",
            "isBlindAppend": True,
        },
        "metaData": {
            "id": uuid.uuid5(uuid.NAMESPACE_URL, table_identity).hex,
            "format": {"provider": "parquet", "options": {}},
            "schemaString": _spark_schema_string(columns),
            "partitionColumns": [],
            "configuration": {},
            "createdTime": now_ms,
        },
        "add": {
            "path": files[0]["path"],
            "partitionValues": {},
            "size": files[0]["size"],
            "modificationTime": now_ms,
            "dataChange": True,
        },
    }


def _spark_schema_string(columns: list[str]) -> str:
    """The delta metaData schemaString — the statement API projects
    strings, so every column maps to the Spark ``string`` type (the
    documented minimal mapping)."""
    return json.dumps(
        {
            "type": "struct",
            "fields": [
                {"name": column, "type": "string", "nullable": True, "metadata": {}}
                for column in columns
            ],
        },
        separators=(",", ":"),
    )


def _version_base(share: str, schema: str, table: str, version: int) -> str:
    prefix = settings.DELTA_SHARE_SNAPSHOT_STORAGE_PREFIX
    return f"{prefix}/{share}/{schema}/{table}/v{version:020d}/"


def _default_storage():
    from hub.apps.files.storage import S3StorageClient

    return S3StorageClient()


def _validate_source(source: _SourceVersion) -> None:
    """Shape discipline BEFORE any S3 write: a malformed source is a
    classified failure — never a silently corrupt parquet."""
    if (
        not isinstance(source.version, int)
        or isinstance(source.version, bool)
        or source.version < 0
    ):
        raise DeltaShareSnapshotError(
            f"the source version must be a non-negative integer, got {source.version!r}"
        )
    if not isinstance(source.columns, list) or not all(
        isinstance(column, str) for column in source.columns
    ):
        raise DeltaShareSnapshotError("the source columns must be a list of names")
    if len(set(source.columns)) != len(source.columns):
        raise DeltaShareSnapshotError(
            "duplicate column names are refused — never a silently corrupt parquet"
        )
    if not isinstance(source.rows, list):
        raise DeltaShareSnapshotError("the source rows must be a list")
    for index, row in enumerate(source.rows):
        if not isinstance(row, list) or len(row) != len(source.columns):
            arity = "non-list" if not isinstance(row, list) else len(row)
            raise DeltaShareSnapshotError(
                f"row {index} has {arity} values for {len(source.columns)} columns — "
                "never a silent truncation"
            )


def _fail_job(job: Job, message: str, *, now: Callable[[], datetime]) -> Job:
    job.status = JobStatus.FAILED
    job.completed_at = now()
    job.error_message = message
    job.save(update_fields=["status", "completed_at", "error_message"])
    return job


def _emit_snapshot_audit(
    action: str,
    *,
    tenant,
    actor_user,
    job: Job,
    details: dict[str, Any],
    resource_id: str | None = None,
) -> None:
    """The emission chokepoint — one row per terminal transition. The
    snapshot row's pk anchors ``resource_id`` when it exists (a failed
    run stamps no row). Best-effort: an audit-DB outage never blocks
    the snapshot (the Phase 273 contract)."""
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type=_AUDIT_RESOURCE_TYPE,
            action=action,
            actor_user=actor_user or job.created_by,
            tenant=tenant,
            resource_id=resource_id,
            details=details,
        )
    except Exception:
        logger.warning(
            "delta_share_snapshot_audit_failed",
            extra={"action": action, "job_id": str(job.id)},
        )
