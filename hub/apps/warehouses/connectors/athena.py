"""
Phase 275.C.3 — AthenaConnector over pyathena / boto3.

Auth via IAM/SigV4 (Hub IRSA from 275.A.7).
Trino-derived SQL. AWS Glue Catalog reflection.
bytes-scanned cost guard. Async result-set polling pattern
(canary for ABC fitness).
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

# Athena async polling state constants.
ATHENA_TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})
ATHENA_POLL_INTERVAL_S = 1.0
ATHENA_MAX_POLL_S = 300  # 5 minutes max for async queries


class AthenaConnector(WarehouseConnector):
    """Phase 275.C.3 — Athena warehouse connector.

    Auth via IAM/SigV4 (Hub IRSA from 275.A.7).
    SQL dialect: Trino-derived (Presto/Athena SQL).
    Schema reflection via AWS Glue Catalog.
    bytes-scanned cost guard (~$5/TB scanned).
    Async result-set polling via start_query_execution + get_query_results.
    """

    warehouse_type = "athena"

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
        self._glue_client = None

    def connect(self) -> None:
        try:
            import boto3

            region = self._config.get("region", "us-east-1")
            self._client = boto3.client(
                "athena",
                region_name=region,
                aws_access_key_id=self._config.get("aws_access_key_id"),
                aws_secret_access_key=self._config.get("aws_secret_access_key"),
            )
            self._glue_client = boto3.client(
                "glue",
                region_name=region,
                aws_access_key_id=self._config.get("aws_access_key_id"),
                aws_secret_access_key=self._config.get("aws_secret_access_key"),
            )
            self._connected = True

            logger.info(
                "athena_connected",
                extra=redact_extra(
                    tenant_id=self._tenant_id,
                    region=region,
                    workgroup=self._config.get("workgroup", "primary"),
                ),
            )
        except ImportError:
            logger.warning("boto3 not installed for Athena connector")
            raise
        except Exception:
            logger.exception("athena_connect_failed")
            raise

    def execute_query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> QueryResult:
        self._check_circuit_breaker(self._tenant_id)

        database = self._config.get("database", "default")
        workgroup = self._config.get("workgroup", "primary")

        # Parameterised binding for Athena — replace :param placeholders.
        # Athena's API doesn't support native parameter binding;
        # values are sanitised before interpolation.
        if params:
            for k, v in (params or {}).items():
                safe_val = str(v).replace("'", "''")
                sql = sql.replace(f":{k}", f"'{safe_val}'")

        started = time.monotonic()
        start_kwargs = {
            "QueryString": f"{sql} LIMIT {limit}" if limit and "LIMIT" not in sql.upper() else sql,
            "QueryExecutionContext": {"Database": database},
            "WorkGroup": workgroup,
        }
        output_location = self._config.get("output_location", "")
        if output_location:
            start_kwargs["ResultConfiguration"] = {"OutputLocation": output_location}
        response = self._client.start_query_execution(**start_kwargs)
        query_id = response["QueryExecutionId"]

        # ── Async result-set polling (canary for ABC fitness) ────────
        state = "RUNNING"
        poll_start = time.monotonic()
        while state not in ATHENA_TERMINAL_STATES:
            elapsed = time.monotonic() - poll_start
            if elapsed > ATHENA_MAX_POLL_S:
                self._client.stop_query_execution(QueryExecutionId=query_id)
                raise TimeoutError(
                    f"Athena query {query_id} timed out after {ATHENA_MAX_POLL_S}s"
                )
            time.sleep(ATHENA_POLL_INTERVAL_S)
            status = self._client.get_query_execution(QueryExecutionId=query_id)
            state = status["QueryExecution"]["Status"]["State"]

        if state != "SUCCEEDED":
            reason = status["QueryExecution"]["Status"].get("StateChangeReason", "")
            raise RuntimeError(f"Athena query {query_id} failed ({state}): {reason}")

        result = self._client.get_query_results(
            QueryExecutionId=query_id, MaxResults=limit or 1000,
        )
        rows_data = result["ResultSet"]["Rows"]
        cols = [c["VarCharValue"] for c in rows_data[0]["Data"]] if rows_data else []
        data_rows = [
            [field.get("VarCharValue", "") for field in row["Data"]]
            for row in rows_data[1:]
        ]
        elapsed = (time.monotonic() - started) * 1000
        stats = status["QueryExecution"].get("Statistics", {})
        bytes_scanned = stats.get("DataScannedInBytes", 0)
        cost = float(bytes_scanned) / 1e9 * 5.0  # ~$5/TB

        result_obj = QueryResult(
            columns=cols, rows=data_rows, row_count=len(data_rows),
            duration_ms=round(elapsed, 2),
            cost_units=round(cost, 6),
            cost_unit_label="bytes_scanned",
        )
        self._record_cost(self._tenant_id, cost, "bytes_scanned")
        return result_obj

    def reflect_schema(self, table_name: str) -> List[SchemaColumn]:
        """AWS Glue Catalog reflection."""
        db, tbl = table_name.split(".", 1) if "." in table_name else (
            self._config.get("database", "default"), table_name,
        )
        response = self._glue_client.get_table(DatabaseName=db, Name=tbl)
        columns = response["Table"].get("StorageDescriptor", {}).get("Columns", [])
        partitions = response["Table"].get("PartitionKeys", [])
        return [
            SchemaColumn(
                name=c["Name"], data_type=c.get("Type", "string"),
                comment=c.get("Comment", ""),
            )
            for c in columns + partitions
        ]

    def close(self) -> None:
        self._connected = False
