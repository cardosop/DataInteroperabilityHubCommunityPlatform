"""
Phase 275.B.1 — SnowflakeConnector over snowflake-connector-python.

Implements the WarehouseConnector ABC for Snowflake.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from hub.apps.warehouses.connectors import (
    QueryResult,
    SchemaColumn,
    WarehouseConnector,
)


class SnowflakeConnector(WarehouseConnector):
    """Phase 275.B.1 — Snowflake warehouse connector.

    Auth via PAT/JWT/keypair from the vault.
    SQL dialect: Snowflake SQL.
    Schema reflection via INFORMATION_SCHEMA.COLUMNS.
    Query-tag for cost attribution.
    """

    warehouse_type = "snowflake"

    def __init__(self, connection_config: dict, timeout_ms: int = 30_000):
        super().__init__(connection_config, timeout_ms)
        self._conn = None

    def connect(self) -> None:
        """Establish connection using snowflake-connector-python."""
        config = self._config
        import logging
        logger = logging.getLogger(__name__)

        try:
            import snowflake.connector
            self._conn = snowflake.connector.connect(
                account=config.get("account", ""),
                user=config.get("user", ""),
                authenticator=config.get("authenticator", "snowflake"),
                password=config.get("password"),
                private_key=config.get("private_key"),
                warehouse=config.get("warehouse"),
                database=config.get("database"),
                schema=config.get("schema"),
                login_timeout=(self._timeout_ms // 1000) or 5,
            )
            self._connected = True
        except ImportError:
            logger.warning("snowflake-connector-python not installed")
            raise
        except Exception:
            logger.exception("snowflake_connect_failed")
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
        sql = (
            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COMMENT "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = %(table_name)s "
            "ORDER BY ORDINAL_POSITION"
        )
        result = self.execute_query(sql, {"table_name": table_name})
        return [
            SchemaColumn(
                name=r[0], data_type=r[1],
                nullable=r[2] == "YES", comment=r[3] or "",
            )
            for r in result.rows
        ]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._connected = False
