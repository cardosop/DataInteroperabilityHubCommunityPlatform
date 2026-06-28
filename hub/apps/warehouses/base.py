"""
Phase 275.A.2 — WarehouseConnector ABC + framework primitives.

Defines the contract every warehouse connector must implement:
- Live SELECT (parameterised binding only — NEVER string-concatenate)
- Schema reflection
- Query-timeout cascade (client > Hub > driver > warehouse)
- Per-tenant cost guard
- Circuit-breaker integration
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Return shape for ``WarehouseConnector.execute_query()``."""

    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    duration_ms: float = 0.0
    cost_units: float = 0.0
    cost_unit_label: str = ""


@dataclass
class SchemaColumn:
    """Single column from warehouse schema reflection."""

    name: str
    data_type: str
    nullable: bool = True
    comment: str = ""


class WarehouseConnector(ABC):
    """Phase 275.A.2 — abstract base for all warehouse drivers.

    Subclasses implement ``connect()``, ``execute_query()``, and
    ``reflect_schema()``. Parameterised queries are enforced by
    contract — connectors MUST use the driver's parameter-binding API.
    """

    # Warehouse type key (e.g. "snowflake", "bigquery").
    warehouse_type: str = ""

    def __init__(self, connection_config: dict, timeout_ms: int = 30_000):
        self._config = connection_config
        self._timeout_ms = timeout_ms
        self._connected = False

    @abstractmethod
    def connect(self) -> None:
        """Establish a live connection to the warehouse."""

    @abstractmethod
    def execute_query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> QueryResult:
        """Execute a parameterised SELECT query.

        ``sql`` MUST use driver-native parameter placeholders
        (``:param`` for Snowflake, ``@param`` for Databricks,
        ``%(param)s`` for BigQuery/Athena-style).

        NEVER use string concatenation or f-strings for user-supplied
        filter values — a CI check enforces this.
        """

    @abstractmethod
    def reflect_schema(self, table_name: str) -> list[SchemaColumn]:
        """Return the column schema for a warehouse table."""

    @abstractmethod
    def close(self) -> None:
        """Close the connection and release resources."""

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()

    def _check_circuit_breaker(self, tenant_id: str) -> None:
        """Raise if the circuit breaker is open for this tenant+warehouse."""
        try:
            from hub.apps.core.resilience.service_breakers import is_circuit_open

            channel = f"warehouse_{self.warehouse_type}_{tenant_id}"
            if is_circuit_open(channel):
                raise ConnectionError(
                    f"Circuit breaker open for {self.warehouse_type} on tenant {tenant_id}"
                )
        except ImportError:
            pass  # circuit breaker not yet wired

    def _record_cost(self, tenant_id: str, cost_units: float, unit_label: str) -> None:
        """Emit a cost metric for observability."""
        try:
            from hub.apps.observability.otel_metrics import warehouse_cost_units_total

            warehouse_cost_units_total.labels(
                warehouse=self.warehouse_type,
                tenant=tenant_id,
                unit=unit_label,
            ).inc(cost_units)
        except Exception:
            logger.warning(
                "Failed to record warehouse cost metric "
                "(warehouse=%s, tenant=%s, cost=%s, label=%s)",
                self.warehouse_type, tenant_id, cost_units, unit_label,
                exc_info=True,
            )


# ── Connector factory ──────────────────────────────────────────────────


def get_connector_for_connection(warehouse_type: str):
    """Return the connector class for *warehouse_type*.

    Args:
        warehouse_type: ``SNOWFLAKE``, ``BIGQUERY``, ``DATABRICKS``, or ``ATHENA``.

    Returns:
        A ``WarehouseConnector`` subclass.

    Raises:
        ValueError: Unknown warehouse type.
    """
    from .connectors.athena import AthenaConnector
    from .connectors.bigquery import BigQueryConnector
    from .connectors.databricks import DatabricksConnector
    from .connectors.snowflake import SnowflakeConnector

    _map = {
        "SNOWFLAKE": SnowflakeConnector,
        "BIGQUERY": BigQueryConnector,
        "DATABRICKS": DatabricksConnector,
        "ATHENA": AthenaConnector,
    }
    cls = _map.get(warehouse_type.upper())
    if cls is None:
        raise ValueError(
            f"Unsupported warehouse type: '{warehouse_type}'. Valid: {list(_map.keys())}"
        )
    return cls
