"""
285.6.2.3–4 — DataMovementPipeline: unified dlt wrapper for ingestion and export.

Single class for both directions. Maps SourceType/DestinationType enum values
to dlt verified source/destination functions.
"""
from __future__ import annotations
import os
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

# Lazy-loaded dlt module — imported only when a pipeline is actually created.
# This allows the module to be registered and configured without dlt installed.
_dlt = None


def _get_dlt():
    global _dlt
    if _dlt is None:
        import dlt as _dlt_module

        _dlt = _dlt_module
        # 285.6.5.9 — Production dlt log config
        _dlt.config["log_level"] = os.environ.get("DLT_LOG_LEVEL", "WARNING")
        _dlt.config["enable_runtime_trace"] = False
    return _dlt

# ── Source/Destination type mapping ─────────────────────────────────

SOURCE_MAP: Dict[str, str] = {
    "S3": "filesystem",
    "GCS": "filesystem",
    "AZURE_BLOB": "filesystem",
    "HTTP": "rest_api",
    "HTTPS": "rest_api",
    "FTP": "filesystem",
    "SFTP": "filesystem",
    "DATABASE": "sql_database",
    "SNOWFLAKE_SOURCE": "sql_database",
    "BIGQUERY_SOURCE": "sql_database",
    "DATABRICKS_SOURCE": "sql_database",
    "ATHENA_SOURCE": "sql_database",
}

DESTINATION_MAP: Dict[str, str] = {
    "S3": "filesystem",
    "GCS": "filesystem",
    "AZURE_BLOB": "filesystem",
    "SNOWFLAKE_TABLE": "snowflake",
    "BIGQUERY_TABLE": "bigquery",
    "DATABRICKS_TABLE": "databricks",
    "ATHENA_TABLE": "athena",
    "HTTP": "filesystem",   # 285.6.4.2 — custom destination
    "FTP": "filesystem",    # 285.6.4.2 — custom destination
}

# dlt schema per direction to isolate state tables
DLT_SCHEMA_INGESTION = "dlt_ingestion"
DLT_SCHEMA_EXPORT = "dlt_export"


class DataMovementPipeline:
    """
    285.6.2.3 — Unified dlt pipeline wrapper.

    Handles both ingestion (source → staging) and export (staging → destination).
    Credential resolution delegated to dlt_credentials.resolve_credentials().
    """

    def __init__(
        self,
        direction: str,  # "ingestion" or "export"
        pipeline_name: str,
        destination_type: str | None = None,
        source_type: str | None = None,
        credential_ref: str | None = None,
    ):
        if direction not in ("ingestion", "export"):
            raise ValueError(f"direction must be 'ingestion' or 'export', got '{direction}'")
        self.direction = direction
        self.pipeline_name = pipeline_name
        self.destination_type = destination_type
        self.source_type = source_type
        self.credential_ref = credential_ref

        schema = DLT_SCHEMA_INGESTION if direction == "ingestion" else DLT_SCHEMA_EXPORT
        dataset_name = pipeline_name.replace("-", "_")

        dlt_mod = _get_dlt()
        self._pipeline = dlt_mod.pipeline(
            pipeline_name=pipeline_name,
            destination=self._resolve_destination(),
            dataset_name=dataset_name,
            dev_mode=os.environ.get("DLT_DEV_MODE", "false") == "true",
        )
        logger.info(
            "dlt_pipeline_created",
            direction=direction,
            pipeline_name=pipeline_name,
            destination=self._pipeline.destination.__name__ if self._pipeline.destination else None,
            schema=schema,
        )

    def _resolve_destination(self):
        """Resolve dlt destination from destination_type."""
        if self.direction == "export" and self.destination_type:
            dlt_dest = DESTINATION_MAP.get(self.destination_type)
            if dlt_dest:
                return _get_dlt().destinations.__dict__.get(dlt_dest, None)
        # Ingestion uses filesystem staging by default
        return _get_dlt().destinations.filesystem

    def run(self, resources: list[Any], **kwargs) -> Dict[str, Any]:
        """Run the dlt pipeline with the given resources."""
        load_info = self._pipeline.run(resources, **kwargs)
        return {
            "pipeline_name": self.pipeline_name,
            "dataset_name": self._pipeline.dataset_name,
            "loads": [
                {
                    "load_id": p.load_id,
                    "status": p.status,
                    "started_at": str(p.started_at) if p.started_at else None,
                    "finished_at": str(p.finished_at) if p.finished_at else None,
                }
                for p in load_info.loads
            ],
        }

    def metrics(self) -> Dict[str, Any]:
        """Export dlt LoadInfo metrics for Prometheus."""
        return {
            "pipeline_name": self.pipeline_name,
            "last_trace": self._pipeline.last_trace.last_trace if self._pipeline.last_trace else None,
            "state": str(self._pipeline.state) if self._pipeline.state else {},
        }

    @property
    def pipeline(self):
        return self._pipeline


def create_ingestion_pipeline(
    source_type: str,
    pipeline_name: str,
    credential_ref: str | None = None,
) -> DataMovementPipeline:
    """285.6.2.4 — Factory for ingestion pipelines."""
    return DataMovementPipeline(
        direction="ingestion",
        pipeline_name=pipeline_name,
        source_type=source_type,
        credential_ref=credential_ref,
    )


def create_export_pipeline(
    destination_type: str,
    pipeline_name: str,
    credential_ref: str | None = None,
) -> DataMovementPipeline:
    """285.6.2.4 — Factory for export pipelines."""
    return DataMovementPipeline(
        direction="export",
        pipeline_name=pipeline_name,
        destination_type=destination_type,
        credential_ref=credential_ref,
    )
