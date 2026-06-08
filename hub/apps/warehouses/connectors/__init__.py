"""Warehouse connector implementations (Phase 275)."""
# Re-export the ABC and shared types from the parent connectors module
# so that ``from hub.apps.warehouses.base import QueryResult`` works.
from hub.apps.warehouses.base import (  # noqa: F401 — re-exports from the .py module
    QueryResult,
    SchemaColumn,
    WarehouseConnector,
    get_connector_for_connection,
)
