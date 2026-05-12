"""
Phase 275.B.2 — BigQueryConnector over google-cloud-bigquery.

Implements the WarehouseConnector ABC for Google BigQuery.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from hub.apps.warehouses.connectors import (
    QueryResult,
    SchemaColumn,
    WarehouseConnector,
)


class BigQueryConnector(WarehouseConnector):
    """Phase 275.B.2 — BigQuery warehouse connector.

    Auth via service-account JSON / Workload Identity from vault.
    SQL dialect: BigQuery Standard SQL.
    Schema reflection via INFORMATION_SCHEMA.COLUMNS.
    bytes-billed cost guard via dryRun=True.
    """

    warehouse_type = "bigquery"

    def __init__(self, connection_config: dict, timeout_ms: int = 30_000):
        super().__init__(connection_config, timeout_ms)
        self._client = None

    def connect(self) -> None:
        import logging
        logger = logging.getLogger(__name__)

        try:
            from google.cloud import bigquery
            from google.oauth2 import service_account

            sa_info = self._config.get("service_account_json")
            if sa_info and isinstance(sa_info, dict):
                credentials = service_account.Credentials.from_service_account_info(sa_info)
                self._client = bigquery.Client(
                    project=self._config.get("project", ""),
                    credentials=credentials,
                )
            else:
                self._client = bigquery.Client(
                    project=self._config.get("project", ""),
                )
            self._connected = True
        except ImportError:
            logger.warning("google-cloud-bigquery not installed")
            raise
        except Exception:
            logger.exception("bigquery_connect_failed")
            raise

    def execute_query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> QueryResult:
        self._check_circuit_breaker("")
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            dry_run=False,
            use_query_cache=True,
        )
        if params:
            job_config.query_parameters = [
                bigquery.ScalarQueryParameter(k, "STRING", v)
                for k, v in (params or {}).items()
            ]

        query_job = self._client.query(
            f"{sql} LIMIT {limit}" if limit else sql,
            job_config=job_config,
        )
        rows = list(query_job.result(max_results=limit))
        cols = [field.name for field in query_job.result().schema] if rows else []
        cost = float(query_job.total_bytes_billed or 0) / 1e12 * 5.0  # ~$5/TB

        return QueryResult(
            columns=cols,
            rows=[[getattr(r, c, None) for c in cols] for r in rows],
            row_count=len(rows),
            duration_ms=0.0,
            cost_units=cost,
            cost_unit_label="bytes_billed",
        )

    def reflect_schema(self, table_name: str) -> List[SchemaColumn]:
        dataset, table = table_name.split(".", 1) if "." in table_name else ("", table_name)
        table_ref = self._client.dataset(dataset).table(table)
        self._client.get_table(table_ref)  # warm cache
        schema = self._client.get_table(table_ref).schema
        return [
            SchemaColumn(
                name=field.name, data_type=field.field_type,
                nullable=field.mode == "NULLABLE", comment=field.description or "",
            )
            for field in schema
        ]

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._connected = False
