"""Phase 5 (task 5.3) — the Delta Sharing catalog + serving services.

The Hub's native protocol catalog maps the tenant's shareable assets
onto the Delta Sharing hierarchy:

- share   = ``meshant`` — one share per tenant (``share_name_for``);
- schema  = the asset's UUID hex (``schema_name_for`` — deterministic,
  collision-free, reversible);
- table   = the asset's external table ref (``table_name_for`` — the
  external-table-ref convention the removed fabricated stub used).

Only LIVE_QUERY assets with a warehouse connection and
``semantic_federate_optout=False`` are shareable (``shareable_assets``).

Serving modes (the 5.1 design D2): the query endpoint is JSON mode — a
SELECT proxied through the PRODUCTION warehouse connector (the connector
FACTORY is module-level: the sanctioned patch point for the outbound
warehouse boundary, the 4.4 recorder convention); the version endpoint
is Parquet mode — presigned URL file actions from the snapshot row
(materialized by 5.4's job), REAL presigns from the production
``S3StorageClient`` with a short expiry.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

from hub.apps.warehouses.base import get_connector_for_connection

logger = logging.getLogger(__name__)

SHARE_NAME = "meshant"

# The table ref is interpolated into a SELECT — the connector's
# reflect_schema identifier discipline (alphanumeric + underscore + dot
# for catalog.schema.table), never SQL.
_TABLE_REF_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]*$")

# Presigned URL expiry for the data mode (seconds).
PRESIGN_EXPIRY_SECONDS = 3600

# JSON-mode default row cap (the protocol's limitHint default).
DEFAULT_QUERY_LIMIT = 100
MAX_QUERY_LIMIT = 1000


def share_name_for(_tenant) -> str:
    """The tenant's single share name."""
    return SHARE_NAME


def schema_name_for(asset) -> str:
    """The asset's schema name (its UUID hex — deterministic)."""
    return str(asset.id).replace("-", "")


def table_name_for(asset) -> str:
    """The asset's table ref (the external table ref / table name)."""
    meta = asset.metadata_json or {}
    return meta.get("external_table_ref") or meta.get("table_name") or ""


def shareable_assets(tenant_id):
    """The tenant's shareable assets (LIVE_QUERY + connected + opted in),
    under the tenant's RLS context."""
    from hub.apps.assets.models import Asset, DataStrategy
    from hub.apps.tenants.request_tenant import tenant_context

    with tenant_context(str(tenant_id)):
        return list(
            Asset.objects.filter(
                tenant_id=tenant_id,
                data_strategy=DataStrategy.LIVE_QUERY,
                warehouse_connection__isnull=False,
                semantic_federate_optout=False,
            ).order_by("name")
        )


def resolve_share_table(tenant_id, *, share: str, schema: str, table: str) -> object | None:
    """Resolve the protocol's (share, schema, table) triple to the
    tenant's shareable asset — None for any mismatch (unknown share,
    schema, table, or an opted-out asset)."""
    if share != SHARE_NAME:
        return None
    from hub.apps.assets.models import Asset
    from hub.apps.tenants.request_tenant import tenant_context

    with tenant_context(str(tenant_id)):
        asset = (
            Asset.objects.filter(tenant_id=tenant_id, id__startswith=schema[:8])
            .filter(
                data_strategy="LIVE_QUERY",
                warehouse_connection__isnull=False,
                semantic_federate_optout=False,
            )
            .first()
        )
        if asset is None or schema_name_for(asset) != schema:
            return None
        if table_name_for(asset) != table:
            return None
        return asset


def latest_snapshot(
    tenant_id,
    *,
    share: str,
    schema: str,
    table: str,
    now: Callable[[], datetime] = timezone.now,
):
    """The newest non-expired snapshot row for the triple — None when
    none exists. A NULL expires_at is treated as EXPIRED (fail-closed:
    a snapshot without a TTL stamp is never served).

    ``now`` is the injectable clock — the materialize/stamp paths accept
    the same seam, and the freshness comparison MUST ride the caller's
    clock (a fixture-pinned ``now`` with a hardcoded ``timezone.now``
    here expires the row as real time advances — the time-bomb class)."""
    from hub.apps.databricks_admin.models import DeltaShareSnapshot
    from hub.apps.tenants.request_tenant import tenant_context

    with tenant_context(str(tenant_id)):
        return (
            DeltaShareSnapshot.objects.filter(
                tenant_id=tenant_id,
                share_name=share,
                schema_name=schema,
                table_name=table,
                expires_at__gt=now(),
            )
            .order_by("-version")
            .first()
        )


def query_share_table_json(*, connection, table_name: str, limit: int, tenant_id: str):
    """JSON mode — SELECT * FROM {table} LIMIT n through the production
    warehouse connector (the connection's own credential IS the
    background M2M identity — the D12 path). The factory is the module
    seam; the caller passes the production one by default."""

    if not _TABLE_REF_RE.match(table_name):
        raise ValueError(f"Invalid table ref {table_name!r} — never interpolated into SQL")

    connector_class = get_connector_for_connection(connection.warehouse_type)
    config = connection.get_config()
    connector = connector_class(config, tenant_id=str(tenant_id))
    try:
        connector.connect()
        return connector.execute_query(f"SELECT * FROM {table_name} LIMIT {limit}", limit=limit)
    finally:
        connector.close()


def build_metadata(asset, table_name: str) -> dict:
    """The protocol metaData envelope for the asset."""
    meta = asset.metadata_json or {}
    return {
        "id": str(asset.id).replace("-", ""),
        "name": table_name,
        "description": asset.name,
        "format": {"provider": "parquet"},
        "schemaString": meta.get("schema_string") or meta.get("schemaString") or "",
        "partitionColumns": [],
        "configuration": {},
    }


def build_file_action(file: dict) -> dict:
    """The protocol file action for one snapshot file — the URL is a
    REAL presigned download URL from the production storage client."""
    from hub.apps.files.storage import S3StorageClient

    url = S3StorageClient().generate_presigned_download_url(
        key=file["path"],
        expires_in=PRESIGN_EXPIRY_SECONDS,
    )
    return {
        "url": url,
        "id": file["id"],
        "partitionValues": file.get("partition_values") or {},
        "size": file.get("size") or 0,
    }
