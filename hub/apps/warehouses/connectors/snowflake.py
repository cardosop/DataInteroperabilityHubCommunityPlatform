"""
Phase 275.B.1 — SnowflakeConnector over snowflake-connector-python.

Auth via PAT/JWT/keypair from the encrypted vault.
SQL dialect: Snowflake SQL. INFORMATION_SCHEMA reflection.
Query-tag for cost attribution. Circuit-breaker integration.
"""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Any

from hub.apps.warehouses.base import (
    QueryResult,
    SchemaColumn,
    WarehouseConnector,
)
from hub.apps.warehouses.log_helpers import redact_extra

logger = logging.getLogger(__name__)


class SnowflakeConnector(WarehouseConnector):
    """Phase 275.B.1 — Snowflake warehouse connector.

    Auth via PAT/JWT/keypair from the encrypted vault.
    SQL dialect: Snowflake SQL.
    Schema reflection via INFORMATION_SCHEMA.COLUMNS.
    Query-tag for cost attribution: {tenant_id, asset_id, request_id}.
    """

    warehouse_type = "snowflake"

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
        config = self._config
        try:
            import snowflake.connector

            self._conn = snowflake.connector.connect(
                account=config.get("account", ""),
                user=config.get("user", ""),
                authenticator=config.get("authenticator", "snowflake"),
                password=config.get("password"),
                token=config.get("token"),
                private_key=config.get("private_key"),
                warehouse=config.get("warehouse"),
                database=config.get("database"),
                schema=config.get("schema"),
                login_timeout=(self._timeout_ms // 1000) or 5,
                session_parameters={
                    "QUERY_TAG": self._build_query_tag(),
                },
            )
            self._connected = True

            logger.info(
                "snowflake_connected",
                extra=redact_extra(
                    tenant_id=self._tenant_id,
                    account=config.get("account"),
                    warehouse=config.get("warehouse"),
                ),
            )
        except ImportError:
            logger.warning("snowflake-connector-python not installed")
            raise
        except Exception:
            logger.exception(
                "snowflake_connect_failed",
            )
            raise

    def _build_query_tag(self) -> str:
        """Build a JSON query-tag for cost attribution."""
        import json

        return json.dumps(
            {
                "tenant_id": self._tenant_id,
                "asset_id": self._asset_id,
                "request_id": self._request_id,
                "source": "meshant-hub",
            }
        )

    def execute_query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> QueryResult:
        self._check_circuit_breaker(self._tenant_id)

        started = time.monotonic()
        cursor = self._conn.cursor()
        try:
            # Parameterised binding — NEVER string-concatenate.
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            rows = cursor.fetchmany(limit) if limit else cursor.fetchall()
            cols = [desc[0] for desc in cursor.description] if cursor.description else []
            elapsed = (time.monotonic() - started) * 1000

            result = QueryResult(
                columns=cols,
                rows=[list(r) for r in rows],
                row_count=len(rows),
                duration_ms=round(elapsed, 2),
            )
            # Estimate credits: Small warehouse (2 credits/hr), min 60s billing.
            # Per-query credit attribution can be refined via QUERY_HISTORY.
            cost_credits = max(elapsed, 60.0) / 3600.0 * 2.0
            self._record_cost(self._tenant_id, cost_credits, "snowflake_credits")
            return result
        except Exception:
            logger.exception(
                "snowflake_query_failed",
                extra=redact_extra(
                    tenant_id=self._tenant_id,
                    sql_preview=sql[:200],
                ),
            )
            raise
        finally:
            cursor.close()

    def reflect_schema(self, table_name: str) -> list[SchemaColumn]:
        import time
        sql = (
            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COMMENT "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = %(table_name)s "
            "ORDER BY ORDINAL_POSITION"
        )
        t0 = time.monotonic()
        result = self.execute_query(sql, {"table_name": table_name.upper()})
        elapsed = time.monotonic() - t0
        self._record_cost(self._tenant_id, max(elapsed, 60.0) / 3600.0 * 2.0, "snowflake-credit")
        return [
            SchemaColumn(
                name=r[0],
                data_type=r[1],
                nullable=r[2] == "YES",
                comment=r[3] or "",
            )
            for r in result.rows
        ]

    def close(self) -> None:
        if self._conn:
            with contextlib.suppress(Exception):
                self._conn.close()
            self._connected = False
