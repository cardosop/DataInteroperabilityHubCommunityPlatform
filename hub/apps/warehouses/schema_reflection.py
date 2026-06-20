"""
Phase 275.B — Schema reflection at LIVE_QUERY asset registration.

Resolves the warehouse connector for a LIVE_QUERY asset, reflects the
table schema, and populates Dataset.schema_json + sample_data_json.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def reflect_and_populate(asset: Any, table_name: str | None = None) -> dict[str, Any]:
    """Reflect the schema of *asset*'s warehouse table and populate its
    latest Dataset with the reflected schema + a 100-row sample.

    Args:
        asset: An Asset with ``data_strategy=LIVE_QUERY`` and a
            ``warehouse_connection`` FK.
        table_name: Override the table to reflect. Defaults to the
            table name stored in asset metadata.

    Returns:
        Dict with ``columns`` (list of SchemaColumn dicts) and
        ``sample_rows`` (list of dicts, up to 100 rows).
    """
    from hub.apps.datasets.models import Dataset

    connection = asset.warehouse_connection
    if connection is None:
        raise ValueError(f"Asset {asset.id} has no warehouse_connection set.")

    if not table_name:
        meta = asset.metadata or {}
        table_name = meta.get("external_table_ref") or meta.get("table_name")
    if not table_name:
        raise ValueError(f"Cannot determine table name for asset {asset.id}.")

    config = connection.get_config()
    from .base import get_connector_for_connection

    connector_cls = get_connector_for_connection(connection.warehouse_type)
    connector = connector_cls(config, tenant_id=str(connection.tenant_id))

    connector.connect()
    try:
        # Reflect schema
        columns = connector.reflect_schema(table_name)
        column_dicts: list[dict[str, Any]] = [
            {"name": c.name, "data_type": c.data_type, "nullable": c.nullable, "comment": c.comment}
            for c in columns
        ]

        # Fetch up to 100 sample rows
        try:
            result = connector.execute_query(
                f"SELECT * FROM {table_name} LIMIT 100",
            )
            sample_rows = [dict(zip([c.name for c in columns], row)) for row in result.rows]
        except Exception as exc:
            logger.warning(
                "warehouse_sample_fetch_failed",
                asset_id=str(asset.id),
                error=str(exc),
            )
            sample_rows = []
    finally:
        with contextlib.suppress(Exception):
            connector.close()

    # Populate the latest Dataset
    latest = Dataset.objects.filter(asset=asset).order_by("-version").first()
    if latest:
        latest.schema_json = {"fields": column_dicts}
        latest.sample_data_json = sample_rows[:100]
        latest.save(update_fields=["schema_json", "sample_data_json", "updated_at"])

    return {"columns": column_dicts, "sample_rows": sample_rows}
