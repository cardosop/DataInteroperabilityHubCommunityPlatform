"""
Phase 275.C.2 — DatabricksConnector over databricks-sql-connector.

Auth via PAT/OAuth/Service Principal from encrypted vault.
SparkSQL dialect. Unity Catalog reflection. DBU cost attribution.
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
from hub.apps.warehouses.exceptions import WarehouseConnectionError
from hub.apps.warehouses.log_helpers import redact_extra

logger = logging.getLogger(__name__)

_M2M_EXCHANGE_MAX_ATTEMPTS = 3
_M2M_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_M2M_RETRY_BASE_DELAY = 0.5
_M2M_RETRY_MAX_DELAY = 2.0


def resolve_access_token(
    config: dict,
    exchange_base_url: str | None = None,
    obo_provider=None,
) -> str:
    """P0 (task 0.11) + P0b (task 0b.5) — resolve the bearer for a Databricks config.

    OBO (interactive paths, task 0b.5): when ``obo_provider`` is passed,
    the per-request identity comes from the authenticated Hub session —
    the provider resolves/refreshes the bound user token and is
    FAIL-CLOSED (``DATABRICKS_OBO_REFRESH_FAILED``): a PAT/M2M credential
    in ``config`` is NEVER used as a fallback here.

    PAT (default for legacy configs without ``auth_mode``): the stored
    ``pat_token``. OAUTH_M2M (background jobs): a REAL oidc
    client-credentials exchange against the workspace host
    (``exchange_base_url`` is a transport seam for tooling/tests — the
    production default is ``https://<host>``). Implemented locally: the
    provider-boundary contract forbids importing ``databricks_admin``
    from other apps.
    """
    if obo_provider is not None:
        return obo_provider.get_bearer()

    auth_mode = config.get("auth_mode", "PAT")
    if auth_mode == "PAT":
        token = config.get("pat_token", "")
        if not token:
            raise WarehouseConnectionError("Databricks PAT config has no 'pat_token' value")
        return token
    if auth_mode == "OAUTH_M2M":
        import httpx

        from hub.apps.core.resilience.backoff import sleep_with_jitter

        base_url = (exchange_base_url or f"https://{config.get('host', '')}").rstrip("/")
        last_response = None
        for attempt in range(_M2M_EXCHANGE_MAX_ATTEMPTS):
            response = httpx.post(
                f"{base_url}/oidc/v1/token",
                data={
                    "grant_type": "client_credentials",
                    "scope": "all-apis",
                    "client_id": config.get("client_id", ""),
                    "client_secret": config.get("client_secret", ""),
                },
                timeout=15.0,
            )
            last_response = response
            if (
                response.status_code in _M2M_RETRYABLE_STATUSES
                and attempt < _M2M_EXCHANGE_MAX_ATTEMPTS - 1
            ):
                # Same repo resilience stack as every other control-plane
                # call: full-jitter backoff on 429/5xx.
                sleep_with_jitter(attempt, _M2M_RETRY_BASE_DELAY, _M2M_RETRY_MAX_DELAY)
                continue
            break
        if last_response is None or last_response.status_code != 200:
            raise WarehouseConnectionError(
                "Databricks OAuth M2M token exchange failed with "
                f"{getattr(last_response, 'status_code', 'no response')}"
            )
        try:
            payload = last_response.json()
        except ValueError as exc:
            # Classified like every other token-body failure — never a raw
            # JSONDecodeError leaking through the connector layer.
            raise WarehouseConnectionError(
                f"Databricks OAuth M2M token response is not valid JSON: {exc}"
            ) from exc
        token = payload.get("access_token", "") if isinstance(payload, dict) else ""
        if not token:
            raise WarehouseConnectionError("Databricks OAuth M2M response carried no access_token")
        return token
    raise WarehouseConnectionError(
        f"Unsupported Databricks auth_mode '{auth_mode}' (PAT|OAUTH_M2M)"
    )


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
        super().__init__(
            connection_config,
            timeout_ms,
            tenant_id=tenant_id,
            asset_id=asset_id,
            request_id=request_id,
        )
        self._conn = None

    def _session_config(self) -> dict:
        """The queryTag session keys (pilot-readiness 2.3): tagged by
        default with the tenant/asset identity; ``session_tags_enabled:
        false`` is the EXPLICIT opt-out (the free-edition workspace
        rejects the keys with CONFIG_NOT_AVAILABLE — the live finding).
        Disable is strictly the false VALUE — an absent or truthy flag
        keeps the tags (P3-1: the inline-refactor had dropped the
        opt-out contract entirely)."""
        if self._config.get("session_tags_enabled") is False:
            return {}
        session_cfg = {}
        if self._tenant_id:
            session_cfg["spark.databricks.queryTag.tenant_id"] = self._tenant_id
        if self._asset_id:
            session_cfg["spark.databricks.queryTag.asset_id"] = self._asset_id
        return session_cfg

    def connect(self) -> None:
        try:
            from databricks import sql

            session_cfg = self._session_config()

            host = (self._config.get("host", "") or "").strip()
            # Stored configs historically carried the URL scheme
            # ("https://dbc-...") — the driver expects a bare hostname.
            host = host.removeprefix("https://").removeprefix("http://").rstrip("/")

            self._conn = sql.connect(
                server_hostname=host,
                http_path=self._config.get("http_path", ""),
                access_token=resolve_access_token(self._config),
                catalog=self._config.get("catalog", ""),
                schema=self._config.get("schema", ""),
                _socket_timeout=(self._timeout_ms // 1000) or 30,
                session_configuration=(session_cfg or None),
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
        params: dict[str, Any] | None = None,
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
            # Estimate DBU: SQL Warehouse ~0.55 DBU/hr (2X-Small), min 60s.
            cost_dbu = max(elapsed, 60.0) / 3600.0 * 0.55
            self._record_cost(self._tenant_id, cost_dbu, "dbu")
        except Exception:
            logger.exception(
                "databricks_query_failed",
                extra=redact_extra(tenant_id=self._tenant_id, sql_preview=sql[:200]),
            )
            raise
        else:
            return result
        finally:
            cursor.close()

    def reflect_schema(self, table_name: str) -> list[SchemaColumn]:
        # DESCRIBE TABLE is universally supported across Databricks versions
        # (INFORMATION_SCHEMA.COLUMNS requires fine-grained UC permissions on
        # some workspaces).
        # Validate table_name to prevent SQL injection via f-string interpolation.
        # Databricks identifiers: catalog.schema.table (each part alphanumeric + underscore).
        import re

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", table_name):
            raise ValueError(f"Invalid table_name for schema reflection: {table_name!r}")

        sql = f"DESCRIBE TABLE {table_name}"
        result = self.execute_query(sql)
        # P0 (task 0.11): execute_query already records the DBU cost —
        # the extra record here double-counted every schema reflection.
        return [
            SchemaColumn(
                name=r[0],
                data_type=r[1],
                nullable=True,
                comment=r[2] or "",
            )
            for r in result.rows
        ]

    def close(self) -> None:
        if self._conn:
            with contextlib.suppress(Exception):
                self._conn.close()
            self._connected = False
