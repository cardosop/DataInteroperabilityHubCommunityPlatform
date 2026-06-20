"""
Phase 275.A.16 — Schema-change detection for LIVE_QUERY assets.

Daily per-asset job compares warehouse-side schema against Hub's
Dataset.schema_json. Emits WAREHOUSE_SCHEMA_DRIFT audit when drift
is detected. Blocks live queries on the drifted asset until reconciled.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def check_schema_drift(
    *,
    asset,
    warehouse_connection,
    tenant,
) -> dict | None:
    """Compare warehouse schema against Dataset.schema_json.

    Returns a drift report dict if schemas diverge, None if consistent.
    Emits WAREHOUSE_SCHEMA_DRIFT audit on drift detection.
    """

    dataset = asset.datasets.first()
    if not dataset or not dataset.schema_json:
        return None

    hub_schema = dataset.schema_json
    if isinstance(hub_schema, list):
        hub_columns = {c.get("name", ""): c.get("data_type", "") for c in hub_schema}
    else:
        hub_columns = hub_schema.get("columns", {})

    # Resolve connector and reflect warehouse schema.
    try:
        config = warehouse_connection.get_config()
        connector = _get_connector(warehouse_connection.warehouse_type, config)
        connector.connect()
        wh_columns_list = connector.reflect_schema(dataset.name or asset.name)
        wh_columns = {c.name: c.data_type for c in wh_columns_list}
        connector.close()
    except Exception:
        logger.exception("schema_drift_check_failed")
        return None

    # Compare.
    added = [c for c in wh_columns if c not in hub_columns]
    removed = [c for c in hub_columns if c not in wh_columns]
    type_changed = [c for c in wh_columns if c in hub_columns and wh_columns[c] != hub_columns[c]]

    if added or removed or type_changed:
        drift = {
            "warehouse_type": warehouse_connection.warehouse_type,
            "asset_id": str(asset.id),
            "added_columns": added,
            "removed_columns": removed,
            "type_changes": type_changed,
        }

        try:
            from hub.apps.audit.event_types import WAREHOUSE_SCHEMA_DRIFT
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="ASSET",
                action=WAREHOUSE_SCHEMA_DRIFT,
                actor_user=None,
                tenant=tenant,
                resource_id=str(asset.id),
                result="WARNING",
                details=drift,
            )
        except Exception:
            pass

        return drift
    return None


def _get_connector(warehouse_type: str, config: dict):
    """Resolve the appropriate connector for the warehouse type."""
    if warehouse_type == "SNOWFLAKE":
        from hub.apps.warehouses.connectors.snowflake import SnowflakeConnector

        return SnowflakeConnector(config)
    elif warehouse_type == "BIGQUERY":
        from hub.apps.warehouses.connectors.bigquery import BigQueryConnector

        return BigQueryConnector(config)
    elif warehouse_type == "DATABRICKS":
        from hub.apps.warehouses.connectors.databricks import DatabricksConnector

        return DatabricksConnector(config)
    elif warehouse_type == "ATHENA":
        from hub.apps.warehouses.connectors.athena import AthenaConnector

        return AthenaConnector(config)
    else:
        raise ValueError(f"Unknown warehouse type: {warehouse_type}")
