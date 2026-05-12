"""
Phase 275.C.2 — DatabricksConnector over databricks-sql-connector.

Implements the WarehouseConnector ABC for Databricks.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from hub.apps.warehouses.connectors import (
    QueryResult,
    SchemaColumn,
    WarehouseConnector,
)


class DatabricksConnector(WarehouseConnector):
    """Phase 275.C.2 — Databricks warehouse connector.

    Auth via PAT/OAuth/Service Principal from vault.
    SQL dialect: SparkSQL.
    Schema reflection via Unity Catalog.
    """

    warehouse_type = "databricks"

    def __init__(self, connection_config: dict, timeout_ms: int = 30_000):
        super().__init__(connection_config, timeout_ms)
        self._conn = None

    def connect(self) -> None:
        import logging
        logger = logging.getLogger(__name__)

        try:
            from databricks import sql
            self._conn = sql.connect(
                server_hostname=self._config.get("host", ""),
                http_path=self._config.get("http_path", ""),
                access_token=self._config.get("pat_token", ""),
                catalog=self._config.get("catalog", ""),
                schema=self._config.get("schema", ""),
                _socket_timeout=(self._timeout_ms // 1000) or 30,
            )
            self._connected = True
        except ImportError:
            logger.warning("databricks-sql-connector not installed")
            raise
        except Exception:
            logger.exception("databricks_connect_failed")
            raise

    def execute_query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> QueryResult:
        self._check_circuit_breaker("")
        cursor = self._conn.cursor()
        try:
            cursor.execute(sql, params or {})
            rows = cursor.fetchmany(limit) if limit else cursor.fetchall()
            cols = [desc[0] for desc in cursor.description] if cursor.description else []
            return QueryResult(
                columns=cols,
                rows=[list(r) for r in rows],
                row_count=len(rows),
                duration_ms=0.0,
            )
        finally:
            cursor.close()

    def reflect_schema(self, table_name: str) -> List[SchemaColumn]:
        parts = table_name.split(".")
        catalog = parts[0] if len(parts) > 2 else self._config.get("catalog", "")
        schema_name = parts[-2] if len(parts) > 1 else self._config.get("schema", "")
        tbl = parts[-1]

        sql = (
            "SELECT COLUMN_NAME, DATA_TYPE, NULLABLE, COMMENT "
            f"FROM {catalog}.INFORMATION_SCHEMA.COLUMNS "
            f"WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(table)s"
        )
        result = self.execute_query(sql, {"schema": schema_name, "table": tbl})
        return [
            SchemaColumn(name=r[0], data_type=r[1], nullable=bool(r[2]), comment=r[3] or "")
            for r in result.rows
        ]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._connected = False
