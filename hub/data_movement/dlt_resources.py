"""
285.6.3.1 — dlt resource definitions replacing worker_services.py processing steps.

Each processing step is a @dlt.resource with write_disposition.
These run as pipeline hooks inside DataMovementPipeline.run().
Existing worker_services.py remains as fallback during transition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

import dlt
import structlog

logger = structlog.get_logger(__name__)


@dlt.resource(write_disposition="merge", primary_key="file_key")
def ingest_files(
    files: list[dict[str, Any]],
    source_type: str,
    credential_ref: str | None = None,  # dlt resource arg — keyword-bound by dlt's resource config
) -> Iterator[dict[str, Any]]:
    """
    285.6.3.1 — dlt resource: ingest files from source.

    Replaces process_file_for_run() logic from worker_services.py.
    Each file is yielded as a row; dlt handles schema inference,
    normalisation, and incremental merging.

    write_disposition="merge" deduplicates by file_key.

    The ``@dlt.resource`` decorator is mandatory (exactly ONE — a
    stacked duplicate wraps the resource object and loses the
    function-name inference): dlt 1.30 rejects undecorated generators
    with ``ResourceNameMissing`` at ``step=extract`` (every
    scheduled-ingestion run FAILED there — JOURNEY-INGESTION-001 E2E).
    """
    for f in files:
        # Defense in depth: the source connectors return bare ``str``
        # keys while this resource's documented contract is
        # ``{"key": ...}`` dicts. ``_discover_source_files`` normalizes
        # at the boundary, but a bare string reaching the resource must
        # still work — it used to raise ``AttributeError: 'str' object
        # has no attribute 'get'`` and FAILED every real S3 run
        # (JOURNEY-INGESTION-001 real-work blocker, 2026-10-03).
        file = {"key": f} if isinstance(f, str) else f
        file_key = file.get("key", file.get("path", ""))
        file_format = file.get("format", _infer_format(file_key))
        yield {
            "file_key": file_key,
            "file_name": file.get("name", file_key.split("/")[-1]),
            "file_format": file_format,
            "file_size_bytes": file.get("size", 0),
            "source_type": source_type,
            "source_path": file.get("path", file_key),
            "etag": file.get("etag", ""),
            "last_modified": file.get("last_modified", ""),
            "ingested_at": dlt.common.pendulum.now().isoformat(),
        }


@dlt.resource(write_disposition="replace")
def raw_records(
    file_content: bytes,
    file_format: str,
    file_key: str,
) -> Iterator[dict[str, Any]]:
    """
    285.6.3.1 — Parse and yield raw records from a file.

    Replaces the format-specific parsing in worker_services.py:64-95.
    dlt normalises records to a consistent schema across formats.

    W3.3 (R2-P2) — ``replace`` is the idempotent re-export contract:
    every run replaces the table with the CURRENT source scope, so a
    re-export never duplicates destination rows. dlt 1.30 ground truth
    (probed on the filesystem destination): ``replace`` deletes the
    previous load files per run and keeps every resource of the SAME run
    (multi-file exports coexist), while ``merge`` silently falls back to
    ``append`` on filesystem — the naive disposition would leave
    duplicates on S3/GCS/AZURE_BLOB destinations.
    """
    records: list[dict[str, Any]] = []
    if file_format == "csv":
        import csv
        import io

        reader = csv.DictReader(io.StringIO(file_content.decode("utf-8", errors="replace")))
        records = list(reader)
    elif file_format == "json":
        import json

        data = json.loads(file_content)
        records = data if isinstance(data, list) else [data]
    elif file_format == "parquet":
        try:
            import io as _io

            import pyarrow.parquet as pq

            table = pq.read_table(_io.BytesIO(file_content))
            records = table.to_pylist()
        except ImportError:
            logger.warning("parquet_not_supported", file_key=file_key)

    for i, record in enumerate(records):
        record["_file_key"] = file_key
        record["_row_index"] = i
        yield record


@dlt.resource(write_disposition="merge", primary_key="dataset_id")
def dataset_metadata(
    datasets: list[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    """
    285.6.3.1 — Track dataset metadata for each ingested file.

    Replaces _create_dataset_atomic() logic from worker_services.py:305.
    """
    for ds in datasets:
        yield {
            "dataset_id": ds.get("id", ""),
            "file_key": ds.get("file_key", ""),
            "row_count": ds.get("row_count", 0),
            "schema_json": ds.get("schema", {}),
            "format": ds.get("format", ""),
            "created_at": dlt.common.pendulum.now().isoformat(),
        }


def _infer_format(file_path: str) -> str:
    """Infer file format from extension."""
    ext = file_path.lower().rsplit(".", 1)[-1] if "." in file_path else ""
    format_map = {
        "csv": "csv",
        "tsv": "csv",
        "json": "json",
        "jsonl": "json",
        "ndjson": "json",
        "parquet": "parquet",
        "pq": "parquet",
        "avro": "avro",
    }
    return format_map.get(ext, "csv")
