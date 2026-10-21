"""
Phase 275.D.2 — Warehouse WriteAdapter for outbound exports.

``dlt`` (data load tool) is the default backend for writing to
Snowflake/BigQuery/Databricks/Athena. Each warehouse can override
with a native loader (Snowpipe, BQ load jobs, COPY INTO, CTAS)
behind the same WriteAdapter interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class WriteAdapter(ABC):
    """Phase 275.D.2 — abstract adapter for writing rows to a warehouse.

    Each warehouse type has a concrete implementation. The ``dlt``
    library handles schema management, idempotency, and normalisation
    for all 4 destinations by default.
    """

    @abstractmethod
    def write_rows(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
        schema: list[dict[str, str]] | None = None,
        *,
        mode: str = "append",
    ) -> dict[str, Any]:
        """Write rows to the target warehouse table.

        Returns a dict with ``{rows_written, status, load_id}``.

        ``dlt`` handles: schema inference, incremental loading,
        idempotency via load_id, and normalisation.
        """

    @abstractmethod
    def create_table(self, table_name: str, schema: list[dict[str, str]]) -> None:
        """Create the target table with the given schema."""


class DltAdapter(WriteAdapter):
    """Default WriteAdapter using ``dlt`` (data load tool).

    ``dlt`` is the default for all 4 warehouse destinations.
    Replace with a native loader per warehouse if needed.
    """

    def __init__(
        self,
        destination_type: str,
        credentials: dict,
        *,
        tenant_id: str | None = None,
        hub_asset_uri: str | None = None,
    ):
        self._destination = destination_type  # "snowflake", "bigquery", etc.
        self._credentials = credentials
        # 275.E.3c lineage context — optional; emission no-ops when absent.
        self._tenant_id = tenant_id
        self._hub_asset_uri = hub_asset_uri

    def write_rows(
        self,
        table_name: str,
        rows: list[dict[str, Any]],
        _schema: list[dict[str, str]] | None = None,
        *,
        mode: str = "append",
    ) -> dict[str, Any]:
        """Delegate to dlt.pipeline().run()."""
        try:
            import dlt

            pipeline = dlt.pipeline(
                pipeline_name=f"meshant_{self._destination}_{table_name}",
                destination=self._destination,
                credentials=self._credentials,
            )
            # dlt normalises schema + handles idempotency via load_id.
            info = pipeline.run(rows, table_name=table_name, write_disposition=mode)
            self._emit_export_lineage(table_name)
            return {
                "rows_written": len(rows),
                "status": "success",
                "load_id": getattr(info, "load_id", ""),
            }
        except ImportError:
            return {
                "rows_written": 0,
                "status": "error",
                "load_id": "",
                "error": "dlt not installed",
            }
        except Exception as exc:
            return {"rows_written": 0, "status": "error", "load_id": "", "error": str(exc)}

    def _emit_export_lineage(self, table_name: str) -> None:
        """275.E.3c — fire-and-forget OpenLineage emit on successful export.

        Best-effort by contract: a lineage-emission failure must never
        fail or retry the export itself.
        """
        if not self._tenant_id or not self._hub_asset_uri:
            return
        try:
            from hub.apps.warehouses.lineage import emit_warehouse_export_event

            emit_warehouse_export_event(
                tenant_id=self._tenant_id,
                hub_asset_uri=self._hub_asset_uri,
                warehouse_table_uri=f"{self._destination}://{table_name}",
            )
        except Exception:
            pass

    def create_table(self, table_name: str, schema: list[dict[str, str]]) -> None:
        """dlt handles table creation during first write."""
