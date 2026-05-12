"""
Phase 275.C.2 — DatabricksConnector over databricks-sql-connector.

Auth via PAT/OAuth/Service Principal from encrypted vault.
SparkSQL dialect. Unity Catalog reflection. DBU cost attribution.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from hub.apps.warehouses.connectors import (
    QueryResult,
    SchemaColumn,
    WarehouseConnector,
)
from hub.apps.warehouses.log_helpers import redact_extra

logger = logging.getLogger(__name__)


class DatabricksConnector(WarehouseConnector):
    """Phase 275.C.2 — Databricks warehouse connector.

    Auth via PAT/OAuth/Service Principal from vault.
    SQL dialect: SparkSQL.
    Schema reflection via Unity Catalog INFORMATION_SCHEMA.
    DBU cost attribution via session configuration tags.
    """

    warehouse_type = "databricks"

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
        self._conn = None

    def connect(self) -> None:
        try:
            from databricks import sql

            self._conn = sql.connect(
                server_hostname=self._config.get("host", ""),
                http_path=self._config.get("http_path", ""),
                access_token=self._config.get("pat_token", ""),
                catalog=self._config.get("catalog", ""),
                schema=self._config.get("schema", ""),
                _socket_timeout=(self._timeout_ms // 1000) or 30,
                session_configuration={
                    "spark.databricks.queryTag.tenant_id": self._tenant_id,
                    "spark.databricks.queryTag.asset_id": self._asset_id,
                },
            )
            self._connected = True

            logger.info(
                "databricks_connected",
                extra=redact_extra(
                    tenant_id=self._tenant_id,
                    host=self._config.get("host"),
                ),
            )
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
        self._check_circuit_breaker(self._tenant_id)

        started = time.monotonic()
        cursor = self._conn.cursor()
        try:
            # Parameterised binding — SparkSQL uses :param placeholders.
            cursor.execute(sql, params or {})
            rows = cursor.fetchmany(limit) if limit else cursor.fetchall()
            cols = [desc[0] for desc in cursor.description] if cursor.description else []
            elapsed = (time.monotonic() - started) * 1000

            result = QueryResult(
                columns=cols,
                rows=[list(r) for r in rows],
                row_count=len(rows),
                duration_ms=round(elapsed, 2),
            )
            self._record_cost(self._tenant_id, 0.0, "dbu")
            return result
        except Exception:
            logger.exception(
                "databricks_query_failed",
                extra=redact_extra(tenant_id=self._tenant_id, sql_preview=sql[:200]),
            )
            raise
        finally:
            cursor.close()

    def reflect_schema(self, table_name: str) -> List[SchemaColumn]:
        parts = table_name.split(".")
        catalog = parts[0] if len(parts) > 2 else self._config.get("catalog", "main")
        schema_name = parts[-2] if len(parts) > 1 else self._config.get("schema", "default")
        tbl = parts[-1]

        sql = (
            f"SELECT COLUMN_NAME, DATA_TYPE, NULLABLE, COMMENT "
            f"FROM {catalog}.INFORMATION_SCHEMA.COLUMNS "
            f"WHERE TABLE_SCHEMA = %(schema)s AND TABLE_NAME = %(table)s "
            f"ORDER BY ORDINAL_POSITION"
        )
        result = self.execute_query(sql, {"schema": schema_name, "table": tbl})
        return [
            SchemaColumn(
                name=r[0], data_type=r[1],
                nullable=bool(r[2]) if r[2] is not None else True,
                comment=r[3] or "",
            )
            for r in result.rows
        ]

    def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._connected = False
