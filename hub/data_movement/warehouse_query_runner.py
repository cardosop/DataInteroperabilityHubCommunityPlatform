"""
285.10.1.1 — WarehouseQueryRunner: shared read-only SQL runner for DQ,
Compliance, and Transformation.

Executes parameterised SELECT queries against Snowflake, BigQuery, or
Databricks with read-only enforcement, exponential backoff retry,
circuit breaker integration, and cost tracking.

Also provides ``TableFQN`` for warehouse-aware table name parsing,
``WarehouseIdempotencyKey`` for cache/retry deduplication, and
``FakeWarehouseQueryRunner`` for deterministic testing.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import time
from dataclasses import dataclass
from typing import Any, ClassVar

# 6.3 — the production connector factory (the D12 M2M background path:
# the connection's own decrypted config IS the identity). A module-level
# attribute so the sanctioned test patch point (monkeypatching
# ``warehouse_query_runner.get_connector_for_connection``) reaches every
# delegation — the 5.3 service-module convention.
from hub.apps.warehouses.base import get_connector_for_connection

# ── 285.10.1.1.2 — TableFQN ───────────────────────────────────────────


class TableFQN:
    """Parse a fully-qualified table name per warehouse type.

    >>> fqn = TableFQN("ANALYTICS.PUBLIC.CUSTOMERS", "snowflake")
    >>> fqn.quoted()
    '"ANALYTICS"."PUBLIC"."CUSTOMERS"'
    """

    def __init__(self, table_fqn: str, warehouse_type: str = "snowflake"):
        self.raw = table_fqn
        self.warehouse_type = warehouse_type.lower()

        parts = table_fqn.replace('"', "").replace("`", "").split(".")
        self.database = parts[0] if len(parts) >= 3 else ""
        self.schema_name = parts[-2] if len(parts) >= 2 else ""
        self.table_name = parts[-1] if parts else ""

    def quoted(self) -> str:
        """Return the FQN with warehouse-appropriate quoting."""
        q = '"' if self.warehouse_type == "snowflake" else "`"
        parts = (
            [self.database, self.schema_name, self.table_name]
            if self.database
            else ([self.schema_name, self.table_name] if self.schema_name else [self.table_name])
        )
        return ".".join(f"{q}{p}{q}" for p in parts)

    def unqualified(self) -> str:
        return self.table_name

    def schema_qualified(self) -> str:
        if self.schema_name and self.table_name:
            return f"{self.schema_name}.{self.table_name}"
        return self.table_name

    def __str__(self):
        return self.raw


# ── Read-only guard ────────────────────────────────────────────────────


_READ_ONLY_BLOCKED = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


class ReadOnlyGuard:
    """Reject write-SQL statements to enforce read-only execution.

    The ONLY bypass is the pipeline execution scope (task 6.5 / design D4):
    inside ``MovementPipelineExecutor.execute`` the guard passes write SQL
    on the executor's thread; everywhere else — including every API
    boundary — it blocks. The default is always blocking.
    """

    @staticmethod
    def is_bypassed() -> bool:
        from hub.data_movement.pipeline_scope import is_guard_bypassed

        return is_guard_bypassed()

    @staticmethod
    def check(sql: str | None) -> None:
        if not sql:
            return
        if ReadOnlyGuard.is_bypassed():
            return
        match = _READ_ONLY_BLOCKED.search(sql)
        if match:
            raise ValueError(
                f"Write operation '{match.group(1).upper()}' is not allowed. "
                "Only SELECT queries may be executed."
            )


# ── 285.10.1.1.3 — Idempotency key ────────────────────────────────────


@dataclass(frozen=True)
class WarehouseIdempotencyKey:
    """Composite key for deduplication: ``(table_fqn, check_hash, last_modified)``.

    Cache TTL: 1 hour.  Two keys are equal when all three components match.
    """

    table_fqn: str
    check_definition_hash: str
    table_last_modified: str

    def __str__(self):
        return f"{self.table_fqn}|{self.check_definition_hash}|{self.table_last_modified}"

    @classmethod
    def build(
        cls,
        table_fqn: str,
        check_definition: dict[str, Any],
        last_modified: str = "",
    ) -> WarehouseIdempotencyKey:
        check_json = json.dumps(check_definition, sort_keys=True)
        check_hash = hashlib.sha256(check_json.encode()).hexdigest()[:16]
        return cls(
            table_fqn=table_fqn,
            check_definition_hash=check_hash,
            table_last_modified=last_modified,
        )


# ── 285.10.1.1.1 — WarehouseQueryRunner ───────────────────────────────


class WarehouseQueryRunnerError(Exception):
    """A classified runner failure carrying a catalogued error code.

    Raised fail-closed BEFORE any connector work: a run without a
    warehouse connection, or a connection that stores no credential
    config (``WAREHOUSE_CONNECTION_REQUIRED``). The retry loop never
    retries it — it is a configuration state, not a transport hiccup,
    so the failure is immediate with zero retry budget and zero breaker
    churn.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class WarehouseQueryRunner:
    """Shared read-only SQL runner for Snowflake, BigQuery, and Databricks.

    Features:
      - Read-only enforcement via ``ReadOnlyGuard``
      - Retry: 3 attempts with exponential backoff (5s, 15s, 45s)
      - Circuit breaker: after 5 consecutive failures, set metric
      - Cost tracking per query
    """

    _MAX_RETRIES = 3
    _RETRY_DELAYS: ClassVar[list[int]] = [5, 15, 45]  # seconds
    _CIRCUIT_FAILURE_THRESHOLD = 5

    def __init__(
        self,
        warehouse_type: str,
        credential_ref: str,
        tenant_slug: str = "",
        query_type: str = "",
        *,
        lineage_tenant_id: str | None = None,
        lineage_asset_uri: str | None = None,
    ):
        self.warehouse_type = warehouse_type.upper()
        self.credential_ref = credential_ref
        self.tenant_slug = tenant_slug
        self.query_type = query_type  # "dq" or "compliance" (285.10.V.32)
        # 275.E.3c — optional OpenLineage context; emission is capability-
        # gated (lineage.warehouse_live_query, OFF by default) and
        # fire-and-forget, so absent context is a clean no-op.
        self._lineage_tenant_id = lineage_tenant_id
        self._lineage_asset_uri = lineage_asset_uri
        self._consecutive_failures = 0
        self.total_cost = 0.0
        self.query_count = 0
        self._connection = None

    # ── Construction ──────────────────────────────────────────────────

    @classmethod
    def from_connection(
        cls,
        connection,
        *,
        tenant_slug: str = "",
        query_type: str = "",
        lineage_tenant_id: str | None = None,
        lineage_asset_uri: str | None = None,
    ) -> WarehouseQueryRunner:
        """Build the runner bound to a ``WarehouseConnection`` (6.3 — the
        D12 M2M background path: the connection's own config IS the
        identity; a hand-built credential is never consulted)."""
        runner = cls(
            warehouse_type=str(connection.warehouse_type),
            credential_ref=str(connection.id),
            tenant_slug=tenant_slug,
            query_type=query_type,
            lineage_tenant_id=lineage_tenant_id,
            lineage_asset_uri=lineage_asset_uri,
        )
        runner._connection = connection
        return runner

    # ── Public API ────────────────────────────────────────────────────

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a read-only SELECT query. Returns rows as dicts."""
        ReadOnlyGuard.check(sql)
        result = self._execute_with_retry(sql, params)
        # 285.10.V.32 — emit warehouse query metric
        self._emit_query_metric(outcome="success")
        self._emit_live_query_lineage()
        return result

    def _emit_live_query_lineage(self) -> None:
        """275.E.3c — fire-and-forget OpenLineage emit for a live query.

        OFF by default (``lineage.warehouse_live_query`` capability) and
        only armed when the caller supplied tenant/asset context.
        """
        if not self._lineage_tenant_id or not self._lineage_asset_uri:
            return
        try:
            from hub.apps.warehouses.lineage import emit_live_query_event

            emit_live_query_event(
                tenant_id=self._lineage_tenant_id,
                warehouse_table_uri=f"{self.warehouse_type.lower()}://{getattr(self, 'table_fqn', '') or ''}",
                hub_asset_uri=self._lineage_asset_uri,
            )
        except Exception:
            pass  # lineage is a downstream signal, never a query gate

    def _emit_query_metric(self, outcome: str) -> None:
        """Emit ``warehouse_native_query_total`` counter (best-effort)."""
        if not self.query_type:
            return
        try:
            from hub.apps.observability.otel_metrics import warehouse_native_query_total

            warehouse_native_query_total.add(
                1,
                attributes={
                    "query_type": self.query_type,
                    "warehouse_type": self.warehouse_type,
                    "outcome": outcome,
                },
            )
        except Exception:
            pass  # metrics are best-effort

    def execute_aggregate(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute an aggregate query. Returns the single result row."""
        rows = self.execute(sql, params)
        if rows:
            return dict(rows[0])
        return {}

    def get_table_schema(self, table_fqn: str) -> list[dict[str, Any]]:
        """Query INFORMATION_SCHEMA for table column metadata."""
        fqn = TableFQN(table_fqn, self.warehouse_type)

        if self.warehouse_type == "SNOWFLAKE":
            sql = (
                f"SELECT column_name, data_type, is_nullable "
                f"FROM {fqn.database}.INFORMATION_SCHEMA.COLUMNS "
                f"WHERE table_schema = '{fqn.schema_name}' "
                f"AND table_name = '{fqn.table_name}'"
            )
        elif self.warehouse_type == "BIGQUERY":
            sql = (
                f"SELECT column_name, data_type, is_nullable "
                f"FROM {fqn.database}.{fqn.schema_name}.INFORMATION_SCHEMA.COLUMNS "
                f"WHERE table_name = '{fqn.table_name}'"
            )
        elif self.warehouse_type == "DATABRICKS":
            sql = f"DESCRIBE TABLE {fqn.quoted()}"
        else:
            raise ValueError(f"Unsupported warehouse type: {self.warehouse_type}")

        rows = self.execute(sql)
        result: list[dict[str, Any]] = []
        for r in rows:
            result.append(
                {
                    "name": r.get("column_name", r.get("col_name", "")),
                    "type": r.get("data_type", r.get("data_type", "unknown")),
                    "nullable": r.get("is_nullable", "YES").upper() == "YES",
                }
            )
        return result

    # ── Internal ──────────────────────────────────────────────────────

    def _execute_with_retry(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute SQL with exponential backoff retry."""
        last_exc: Exception | None = None

        for attempt in range(self._MAX_RETRIES):
            try:
                result = self._execute_single(sql, params)
                self._consecutive_failures = 0
            except WarehouseQueryRunnerError:
                # A classified configuration failure — never a transport
                # hiccup: fail fast, zero retry budget, zero breaker churn.
                raise
            except Exception as exc:
                last_exc = exc
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._CIRCUIT_FAILURE_THRESHOLD:
                    self._set_circuit_open()

                if attempt < self._MAX_RETRIES - 1:
                    delay = self._RETRY_DELAYS[attempt]
                    time.sleep(delay)
            else:
                return result

        self._emit_query_metric(outcome="failure")
        raise RuntimeError(
            f"Query failed after {self._MAX_RETRIES} attempts. Last error: {last_exc}"
        ) from last_exc

    def _execute_single(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a single query attempt (6.3 — the production
        delegation).

        The bound connection's own decrypted config IS the M2M identity
        (the D12 background path): the production connector factory is
        consulted with the connection's warehouse type and the connector
        receives the decrypted config verbatim. A runner without a
        connection, or a connection that stores no credential config,
        fails CLOSED with ``WAREHOUSE_CONNECTION_REQUIRED`` BEFORE any
        factory/connector work — never a NotImplementedError crash,
        never a silently empty read. ``limit=0`` is the connectors'
        documented full-fetch convention — the movement read is never
        silently truncated at the driver default.
        """
        connection = self._connection
        if connection is None:
            raise WarehouseQueryRunnerError(
                "WAREHOUSE_CONNECTION_REQUIRED",
                "the run has no warehouse connection — fail-closed before any connector work",
            )
        config = connection.get_config()
        if not config:
            raise WarehouseQueryRunnerError(
                "WAREHOUSE_CONNECTION_REQUIRED",
                "the connection stores no credential config — fail-closed before any connector work",
            )
        self.query_count += 1
        self._track_cost(sql)

        connector_cls = get_connector_for_connection(str(connection.warehouse_type))
        connector = connector_cls(config, tenant_id=str(connection.tenant_id))
        try:
            connector.connect()
            result = connector.execute_query(sql, params=params, limit=0)
            return [dict(zip(result.columns, row, strict=True)) for row in result.rows]
        finally:
            with contextlib.suppress(Exception):
                connector.close()

    def _track_cost(self, sql: str) -> None:
        """Estimate per-query cost. Override for warehouse-specific pricing."""
        # Simple byte-based estimate
        self.total_cost += len(sql.encode()) * 0.000001  # ~$0.000001 per byte

    def _set_circuit_open(self) -> None:
        """Set circuit breaker metric after consecutive failures."""
        try:
            from hub.apps.observability.otel_metrics import get_meter

            meter = get_meter("warehouse_query_runner")
            counter = meter.create_counter(
                name="warehouse_circuit_open_total",
                description="Number of times the warehouse circuit breaker opened",
                unit="1",
            )
            counter.add(1, {"warehouse_type": self.warehouse_type})
        except Exception:
            pass  # metrics are best-effort


# ── 285.10.1.1.4 — FakeWarehouseQueryRunner ───────────────────────────


class FakeWarehouseQueryRunner(WarehouseQueryRunner):
    """Deterministic replacement for testing. Returns pre-configured results."""

    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        aggregate_result: dict[str, Any] | None = None,
        schema: list[dict[str, Any]] | None = None,
    ):
        super().__init__(
            "SNOWFLAKE", "arn:aws:secretsmanager:test:fake", "test-tenant", query_type=""
        )
        self._rows = rows or []
        self._aggregate = aggregate_result or {}
        self._schema = schema or []
        self.query_count = 0
        self.total_cost = 0.0

    def _execute_single(
        self,
        sql: str,
        params: dict[str, Any] | None = None,  # override of WarehouseQueryRunner signature
    ) -> list[dict[str, Any]]:
        self.query_count += 1
        self._track_cost(sql)
        return list(self._rows)

    def execute_aggregate(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:  # override of WarehouseQueryRunner signature
        self.query_count += 1
        return dict(self._aggregate)

    def get_table_schema(
        self, table_fqn: str
    ) -> list[dict[str, Any]]:  # override of WarehouseQueryRunner signature
        return list(self._schema)
