"""
Phase 275.C.3 — AthenaConnector over pyathena / boto3.

Implements the WarehouseConnector ABC for AWS Athena.
Async result-set polling pattern (canary for ABC fitness).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from hub.apps.warehouses.connectors import (
    QueryResult,
    SchemaColumn,
    WarehouseConnector,
)


class AthenaConnector(WarehouseConnector):
    """Phase 275.C.3 — Athena warehouse connector.

    Auth via IAM/SigV4 (Hub IRSA from 275.A.7).
    SQL dialect: Trino-derived (Presto/Athena SQL).
    Schema reflection via AWS Glue Catalog.
    bytes-scanned cost guard.
    """

    warehouse_type = "athena"

    def __init__(self, connection_config: dict, timeout_ms: int = 30_000):
        super().__init__(connection_config, timeout_ms)
        self._client = None

    def connect(self) -> None:
        import logging
        logger = logging.getLogger(__name__)

        try:
            import boto3
            self._client = boto3.client(
                "athena",
                region_name=self._config.get("region", "us-east-1"),
                aws_access_key_id=self._config.get("aws_access_key_id"),
                aws_secret_access_key=self._config.get("aws_secret_access_key"),
            )
            self._connected = True
        except ImportError:
            logger.warning("boto3 not installed")
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
        self._check_circuit_breaker("")
        import time

        database = self._config.get("database", "default")
        workgroup = self._config.get("workgroup", "primary")

        if params:
            for k, v in (params or {}).items():
                sql = sql.replace(f":{k}", f"'{v}'")

        response = self._client.start_query_execution(
            QueryString=f"{sql} LIMIT {limit}" if limit else sql,
            QueryExecutionContext={"Database": database},
            WorkGroup=workgroup,
        )
        query_id = response["QueryExecutionId"]

        # Async polling loop
        while True:
            status = self._client.get_query_execution(QueryExecutionId=query_id)
            state = status["QueryExecution"]["Status"]["State"]
            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(1.0)

        if state != "SUCCEEDED":
            raise RuntimeError(f"Athena query {query_id} failed: {state}")

        result = self._client.get_query_results(
            QueryExecutionId=query_id, MaxResults=limit,
        )
        rows_data = result["ResultSet"]["Rows"]
        cols = [c["VarCharValue"] for c in rows_data[0]["Data"]] if rows_data else []
        data_rows = [
            [field.get("VarCharValue", "") for field in row["Data"]]
            for row in rows_data[1:]
        ]
        bytes_scanned = status["QueryExecution"].get("Statistics", {}).get("DataScannedInBytes", 0)

        return QueryResult(
            columns=cols, rows=data_rows, row_count=len(data_rows),
            duration_ms=0.0, cost_units=float(bytes_scanned) / 1e9 * 5.0,
            cost_unit_label="bytes_scanned",
        )

    def reflect_schema(self, table_name: str) -> List[SchemaColumn]:
        import boto3
        glue = boto3.client("glue", region_name=self._config.get("region", "us-east-1"))
        db, tbl = table_name.split(".", 1) if "." in table_name else ("default", table_name)
        response = glue.get_table(DatabaseName=db, Name=tbl)
        return [
            SchemaColumn(
                name=c["Name"], data_type=c.get("Type", "string"),
                comment=c.get("Comment", ""),
            )
            for c in response["Table"].get("StorageDescriptor", {}).get("Columns", [])
        ]

    def close(self) -> None:
        self._connected = False
