"""
W3.8 (oss-release-remediation R2-P7/D6) — the dlt spine's catalog sync.

The D6 parity-first fix: after a successful dlt load the spine creates
the REAL File/Dataset catalog records (through the shared
``hub.apps.scheduled_ingestion.catalog_records`` core — the same
implementation the legacy worker path uses), instead of fabricating
``datasets_created = files_processed``.

Contract:

* ``sync_catalog_records`` is per-file best-effort and NEVER raises: a
  failed download / validation / creation counts the file as FAILED
  with a classified code, and the caller leaves the processed keys
  unmarked so the next run retries the whole batch.
* Creation is idempotent by source key (the core's provenance markers):
  a retry after a crash between the row commit and the key marking
  finds the existing rows and counts them as RECOVERED — never a
  duplicate (which would trip the per-tenant unique-active-name
  constraint).
* ``materialize_databricks_rows`` renders the DATABRICKS_SOURCE read
  rows to JSONL so the database branch materializes one File + Dataset
  per successful read (versioned per run). Its source key embeds the
  read's cursor value, so a retry of the SAME read is idempotent while
  the next scheduled run (a new cursor) creates the next version.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from hub.apps.scheduled_ingestion.models import ScheduledIngestion

logger = structlog.get_logger(__name__)


class SourceDownloadError(Exception):
    """The source connector could not deliver the file content for
    catalog-record creation."""

    code = "SOURCE_DOWNLOAD_FAILED"


@dataclass
class CatalogSyncResult:
    """The catalog phase outcome for one batch of ingested files.

    ``created`` + ``recovered`` count the files whose catalog rows exist
    as a result of the run (fresh or recovered from a crashed earlier
    attempt) — the honest ``datasets_created``. ``failed`` lists the
    per-file classified failures.
    """

    created: int = 0
    recovered: int = 0
    failed: int = 0
    failures: list[dict[str, str]] = field(default_factory=list)


def download_source_file(scheduled_ingestion: ScheduledIngestion, file_key: str) -> bytes:
    """Download one source file's content through the source-connector
    factory (the legacy workflow's contract). Fails closed with the
    classified ``SourceDownloadError`` on a non-SUCCESS status or a
    raised connector error."""
    from hub.apps.orchestration.workflows import scheduled_ingestion as _wf

    connector = _wf._get_source_connector_or_fail(scheduled_ingestion.source_type)
    config = scheduled_ingestion.get_source_config()

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_key).suffix or "") as tmp:
            tmp_path = tmp.name
        result = connector.download_file(config, file_key, tmp_path)
        status = getattr(getattr(result, "status", None), "value", None)
        if status != "SUCCESS":
            message = getattr(result, "message", "") or "download failed"
            raise SourceDownloadError(f"{file_key}: {message}")
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            with contextlib.suppress(Exception):
                os.unlink(tmp_path)


def _file_key_of(file: dict[str, Any] | str) -> str:
    # Raw-string-safe: the connectors' discovery contract returns bare
    # string keys — the same bridge ``_normalize_discovered_files``
    # applies at the spine boundary.
    if isinstance(file, str):
        return file
    return str(file.get("key") or file.get("path") or "")


def _guard_max_file_size(file_key: str, size: int, max_file_size: int | None) -> None:
    """The per-file size cap (the legacy ``max_file_size_bytes``
    contract). Refused loudly — a file the dlt load already ingested
    must not silently lose its catalog record."""
    from hub.apps.core.services.base import (
        ValidationError as ServiceValidationError,
    )

    if max_file_size is not None and size > max_file_size:
        raise ServiceValidationError(
            f"File {file_key} exceeds the configured max_file_size_bytes ({max_file_size})",
            code="FILE_TOO_LARGE",
            details={"file_key": file_key, "max_file_size_bytes": max_file_size},
        )


def sync_catalog_records(
    scheduled_ingestion: ScheduledIngestion, files: list[dict[str, Any]]
) -> CatalogSyncResult:
    """Create the catalog records for a batch of successfully loaded
    files. Never raises — per-file failures are classified into the
    result."""
    from hub.apps.scheduled_ingestion.catalog_records import (
        check_ingestion_plan_limits,
        create_file_and_dataset_records,
    )

    result = CatalogSyncResult()
    source_config = scheduled_ingestion.get_source_config()
    max_file_size = source_config.get("max_file_size_bytes")

    for entry in files:
        file = {"key": entry} if isinstance(entry, str) else entry
        file_key = _file_key_of(file)
        if not file_key:
            # The spine's pending filter already excludes keyless files —
            # this is defense in depth for direct callers.
            continue
        try:
            _guard_max_file_size(file_key, int(file.get("size") or 0), max_file_size)
            content = download_source_file(scheduled_ingestion, file_key)
            _guard_max_file_size(file_key, len(content), max_file_size)
            # W2.7 (R2-B2) — the background plan-limit gate runs BEFORE
            # any File row exists (storage + dataset quota).
            check_ingestion_plan_limits(str(scheduled_ingestion.tenant_id), len(content))

            record = create_file_and_dataset_records(
                scheduled_ingestion,
                file_key,
                content,
                source_key=file_key,
            )
            if record.created:
                result.created += 1
            else:
                result.recovered += 1
        except Exception as exc:  # noqa: BLE001 - the per-file classification contract
            code = getattr(exc, "code", None) or "CATALOG_RECORD_CREATION_FAILED"
            result.failed += 1
            result.failures.append({"file_key": file_key, "code": code, "error": str(exc)})
            logger.warning(
                "dlt_ingestion_catalog_file_failed",
                ingestion_id=str(scheduled_ingestion.id),
                file_key=file_key,
                code=code,
                error=str(exc),
            )
    return result


def materialize_databricks_rows(
    rows: list[dict[str, Any]],
    *,
    asset_key: str,
    table_ref: str,
    cursor_value: Any,
) -> tuple[str, str, bytes]:
    """Render the DATABRICKS_SOURCE read rows to a JSONL File payload.

    Returns ``(file_name, source_key, payload)``. The source key embeds
    the read's cursor value: a retry of the SAME read (the cursor only
    advances on success) resolves to the same key, so the core's
    idempotency guard recovers the rows instead of duplicating them,
    while the next scheduled run creates the next dataset version.
    """
    payload = "\n".join(json.dumps(row, default=str) for row in rows).encode("utf-8")
    file_name = f"{table_ref or 'source'}_{uuid.uuid4().hex[:8]}.json"
    source_key = f"databricks:{asset_key}:{table_ref or 'source'}:{cursor_value or 'initial'}"
    return file_name, source_key, payload
