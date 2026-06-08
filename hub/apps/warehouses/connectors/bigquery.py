"""
Phase 275.B.2 — BigQueryConnector over google-cloud-bigquery.

Auth via service-account JSON / Workload Identity from encrypted vault.
Standard SQL. INFORMATION_SCHEMA.COLUMNS reflection.
bytes-billed cost guard via dryRun=True. Circuit-breaker integration.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from hub.apps.warehouses.base import (
    QueryResult,
    SchemaColumn,
    WarehouseConnector,
)
from hub.apps.warehouses.log_helpers import redact_extra

logger = logging.getLogger(__name__)


class BigQueryConnector(WarehouseConnector):
    """Phase 275.B.2 — BigQuery warehouse connector.

    Auth via service-account JSON / Workload Identity from vault.
    SQL dialect: BigQuery Standard SQL.
    Schema reflection via INFORMATION_SCHEMA.COLUMNS.
    bytes-billed cost guard via dryRun=True.
    """

    warehouse_type = "bigquery"

    def __init__(
        self,
        connection_config: dict,
        timeout_ms: int = 30_000,
        tenant_id: str = "",
        asset_id: str = "",
        request_id: str = "",
    ):
        super().__init__(connection_config, timeout_ms)
        self._tenant_id = tenant_id
        self._asset_id = asset_id
        self._request_id = request_id
        self._client = None

    def connect(self) -> None:
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

            logger.info(
                "bigquery_connected",
                extra=redact_extra(
                    tenant_id=self._tenant_id,
                    project=self._config.get("project"),
                ),
            )
        except ImportError:
            logger.warning("google-cloud-bigquery not installed")
            raise
        except Exception:
            logger.exception("bigquery_connect_failed")
            raise

    def estimate_cost(self, sql: str) -> float:
        """Phase 275.B.2 — dryRun cost preview before live query.

        Returns estimated bytes to be processed as a dollar amount
        (~$5/TB). Does NOT execute the query.
        """
        self._check_circuit_breaker(self._tenant_id)

        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        query_job = self._client.query(sql, job_config=job_config)
        bytes_billed = query_job.total_bytes_processed or 0
        cost = float(bytes_billed) / 1e12 * 5.0  # ~$5/TB
        logger.info(
            "bigquery_dry_run_cost",
            extra=redact_extra(
                tenant_id=self._tenant_id,
                bytes_billed=bytes_billed,
                estimated_cost_usd=round(cost, 6),
            ),
        )
        return cost

    def execute_query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> QueryResult:
        self._check_circuit_breaker(self._tenant_id)

        from google.cloud import bigquery

        started = time.monotonic()
        job_config = bigquery.QueryJobConfig(
            dry_run=False,
            use_query_cache=True,
        )
        # Parameterised binding via ScalarQueryParameter.
        if params:
            job_config.query_parameters = [
                bigquery.ScalarQueryParameter(k, "STRING", str(v))
                for k, v in (params or {}).items()
            ]

        limited_sql = f"{sql} LIMIT {limit}" if limit and "LIMIT" not in sql.upper() else sql
        query_job = self._client.query(limited_sql, job_config=job_config)
        rows = list(query_job.result(max_results=limit))
        cols = [field.name for field in query_job.result().schema] if rows else []
        elapsed = (time.monotonic() - started) * 1000
        cost = float(query_job.total_bytes_billed or 0) / 1e12 * 5.0

        result = QueryResult(
            columns=cols,
            rows=[[getattr(r, c, None) for c in cols] for r in rows],
            row_count=len(rows),
            duration_ms=round(elapsed, 2),
            cost_units=round(cost, 6),
            cost_unit_label="bytes_billed",
        )
        self._record_cost(self._tenant_id, cost, "bytes_billed")
        return result

    def reflect_schema(self, table_name: str) -> List[SchemaColumn]:
        parts = table_name.split(".")
        dataset = parts[0] if len(parts) > 1 else self._config.get("dataset", "")
        table = parts[1] if len(parts) > 1 else table_name
        table_ref = self._client.dataset(dataset).table(table)
        self._client.get_table(table_ref)
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
            try:
                self._client.close()
            except Exception:
                pass
            self._connected = False
