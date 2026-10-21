"""
285.6.2.3-4 — DataMovementPipeline: unified dlt wrapper for ingestion and export.

Single class for both directions. Maps SourceType/DestinationType enum values
to dlt verified source/destination functions.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Lazy-loaded dlt module — imported only when a pipeline is actually created.
# This allows the module to be registered and configured without dlt installed.
_dlt = None


def _configure_dlt_pipelines_dir(dlt_module) -> None:
    """W3.10 — point dlt's pipeline STATE at the volume-backed path.

    The mechanism dlt 1.30 actually honors is the CONFIG injection
    (``dlt.config["pipelines.pipelines_dir"]``) — the ``DLT_PIPELINES_DIR``
    ENV VAR is IGNORED (the 6.7 trap: the pre-fix code set it and real
    pipelines still resolved under /tmp, which wiped the processed keys
    and SQL cursors on every container re-create).  The env var stays
    set for observability only.

    Where the configured dir is not creatable (host dev without the
    mount, read-only rootfs) the injection falls back to dlt's writable
    default with a warning — ephemeral THERE, never silently wrong in a
    deployment.
    """
    from django.conf import settings

    target = getattr(settings, "DLT_PIPELINES_DIR", None)
    if not target:
        return
    os.environ.setdefault("DLT_PIPELINES_DIR", target)
    try:
        os.makedirs(target, exist_ok=True)
    except OSError:
        logger.warning(
            "dlt_pipelines_dir_unavailable_falling_back",
            path=target,
        )
        return
    dlt_module.config["pipelines.pipelines_dir"] = target


def _get_dlt():
    global _dlt  # lazy-load cache: module global is deliberately mutated once
    if _dlt is None:
        # Pin dlt's state directories to a WRITABLE location BEFORE the
        # first ``import dlt``: the containers run with a read-only
        # rootfs (compose hardening), so dlt's defaults (``/var/dlt``)
        # raise ``OSError: [Errno 30] Read-only file system`` at
        # pipeline creation and every run FAILED before extract.
        # W3.10 — the pipeline STATE dir resolves through the config
        # injection above (volume-backed default), never /tmp.
        os.environ.setdefault("DLT_DATA_DIR", "/tmp/dlt-staging/.dlt/data")

        import dlt as _dlt_module

        _dlt = _dlt_module
        _configure_dlt_pipelines_dir(_dlt)
        # 285.6.5.9 — Production dlt log config
        _dlt.config["log_level"] = os.environ.get("DLT_LOG_LEVEL", "WARNING")
        _dlt.config["enable_runtime_trace"] = False
    return _dlt


# ── Source/Destination type mapping ─────────────────────────────────

SOURCE_MAP: dict[str, str] = {
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

DESTINATION_MAP: dict[str, str] = {
    "S3": "filesystem",
    "GCS": "filesystem",
    "AZURE_BLOB": "filesystem",
    "SNOWFLAKE_TABLE": "snowflake",
    "BIGQUERY_TABLE": "bigquery",
    "DATABRICKS_TABLE": "databricks",
    "ATHENA_TABLE": "athena",
    "HTTP": "filesystem",  # 285.6.4.2 — custom destination
    "FTP": "filesystem",  # 285.6.4.2 — custom destination
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
            # dlt 1.30: ``pipeline.destination`` is the destination factory
            # OBJECT (no ``__name__``) — ``destination_name`` is its label.
            destination=(
                getattr(self._pipeline.destination, "destination_name", None)
                if self._pipeline.destination
                else None
            ),
            schema=schema,
        )

    def _resolve_destination(self):
        """Resolve dlt destination from destination_type."""
        dlt_mod = _get_dlt()
        if self.direction == "export" and self.destination_type:
            dlt_dest = DESTINATION_MAP.get(self.destination_type)
            if dlt_dest:
                factory = dlt_mod.destinations.__dict__.get(dlt_dest, None)
                if dlt_dest == "filesystem" and factory is not None:
                    # S3/GCS/AZURE_BLOB export destinations hit the same
                    # bucket_url gap as ingestion (the factory is unbound
                    # by default) — apply the identical fallback.
                    return self._bind_filesystem_bucket(factory, dlt_mod)
                return factory
        # Ingestion uses filesystem staging by default.
        return self._bind_filesystem_bucket(dlt_mod.destinations.filesystem, dlt_mod)

    @staticmethod
    def _bind_filesystem_bucket(filesystem_dest, dlt_mod):
        """Bind ``bucket_url`` on the filesystem destination.

        The filesystem destination REQUIRES ``bucket_url`` and the
        runtime containers provided NO config source for it (no
        env/TOML) — dlt raised ``ConfigFieldMissingException: Missing
        1 field(s) ... bucket_url`` at ``step=sync`` and every
        scheduled-ingestion run FAILED (JOURNEY-INGESTION-001 E2E).

        Precedence: an explicit dlt config (env
        ``DESTINATION__FILESYSTEM__BUCKET_URL`` or a TOML entry — the
        canonical dlt override points, used by tests and operator
        deployments) wins; the settings-bound staging bucket
        (``DLT_FILESYSTEM_BUCKET_URL``) is the LAST resort so the
        unconfigured runtime still completes instead of dying at sync.
        """
        try:
            configured = dlt_mod.config.get("destination.filesystem.bucket_url")
        except Exception:
            configured = None
        if configured:
            return filesystem_dest
        from django.conf import settings

        bucket_url = getattr(settings, "DLT_FILESYSTEM_BUCKET_URL", "file:///app/dlt-staging")
        return filesystem_dest(bucket_url=bucket_url)

    def run(self, resources: list[Any], **kwargs) -> dict[str, Any]:
        """Run the dlt pipeline with the given resources.

        6.7 — the dlt 1.30 LoadInfo API: ``LoadInfo.loads`` was replaced
        by ``loads_ids`` + ``asdict()["load_packages"]`` (the 285.6 code
        targeted an older dlt 1.x surface). Each load package maps to one
        Hub-side "load": ``completed`` when the package finished loading
        with no failed jobs, ``failed`` otherwise.
        """
        load_info = self._pipeline.run(resources, **kwargs)
        packages = load_info.asdict().get("load_packages", [])
        return {
            "pipeline_name": self.pipeline_name,
            "dataset_name": self._pipeline.dataset_name,
            "loads": [
                {
                    "load_id": package.get("load_id"),
                    "status": (
                        "completed"
                        if package.get("state") == "loaded" and not load_info.has_failed_jobs
                        else "failed"
                    ),
                }
                for package in packages
            ],
        }

    def metrics(self) -> dict[str, Any]:
        """Export dlt LoadInfo metrics for Prometheus.

        6.7 — dlt 1.30: ``pipeline.last_trace`` is a ``PipelineTrace``
        object (no ``.last_trace`` chain) — ``asdict()`` is its payload.
        """
        return {
            "pipeline_name": self.pipeline_name,
            "last_trace": (
                self._pipeline.last_trace.asdict() if self._pipeline.last_trace else None
            ),
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
