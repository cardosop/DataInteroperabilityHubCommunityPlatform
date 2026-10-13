"""Phase 1 (openspec add-databricks-uc-read task 1.4) — UC search feed.

Feeds the mirrored UC objects (1.2) into the Hub's core `SearchIndex`
(Postgres full-text) so they surface through the EXISTING search surface
(`UnifiedSearchView`) — which already carries the Phase 273 throttle +
`SEARCH_PERFORMED` audit contract, so UC results inherit it unchanged.

Provider boundary: this module lives in `databricks_admin` and imports
the CORE search model — the search app never imports a databricks_admin
model (the boundary contract holds in the legal direction).
"""

from __future__ import annotations

import logging

from django.contrib.postgres.search import SearchVector

from hub.apps.databricks_admin.models import (
    DatabricksWorkspace,
    UCCatalog,
    UCModel,
    UCSchema,
    UCTable,
    UCView,
    UCVolume,
)
from hub.apps.search.models import SearchIndex

logger = logging.getLogger(__name__)

# Mirror model → SearchIndex resource type. The types are registered on
# the SearchIndex.resource_type choices (code-only — no schema change).
# UCExternalLocation/UCStorageCredential are mirrored but deliberately
# NOT searchable (the 1.4 spec covers six types) — index/delete calls for
# them are no-ops, so the 1.5 delta-diff can treat every mirror object
# uniformly.
RESOURCE_TYPES: dict = {
    UCCatalog: "DATABRICKS_UC_CATALOG",
    UCSchema: "DATABRICKS_UC_SCHEMA",
    UCTable: "DATABRICKS_UC_TABLE",
    UCView: "DATABRICKS_UC_VIEW",
    UCVolume: "DATABRICKS_UC_VOLUME",
    UCModel: "DATABRICKS_UC_MODEL",
}


def _document(obj) -> dict:
    """The searchable document shape for a mirror row."""
    doc = {
        "title": obj.name,
        "description": getattr(obj, "comment", "") or "",
        "schema_text": "",
        "owner_id": None,
        "owner_email": None,
        "lineage_metadata": {
            "workspace_id": str(_workspace_id(obj)),
            "full_name": getattr(obj, "full_name", "") or "",
        },
    }
    if isinstance(obj, UCTable):
        # Flatten name AND type (the repo's _flatten_schema convention —
        # SearchIndex.schema_text carries "field names and types").
        parts: list[str] = []
        for col in obj.columns or []:
            if not isinstance(col, dict):
                continue
            parts.append(str(col.get("name", "") or ""))
            type_text = col.get("type_text") or col.get("type_name") or col.get("type") or ""
            if type_text:
                parts.append(str(type_text))
        doc["schema_text"] = " ".join(part for part in parts if part)
        doc["lineage_metadata"].update(
            {"catalog": obj.schema.catalog.name, "schema": obj.schema.name}
        )
    elif isinstance(obj, (UCView, UCVolume, UCModel)):
        doc["lineage_metadata"].update(
            {"catalog": obj.schema.catalog.name, "schema": obj.schema.name}
        )
        if isinstance(obj, UCView):
            doc["schema_text"] = obj.view_definition[:2000]
    elif isinstance(obj, UCSchema):
        doc["lineage_metadata"]["catalog"] = obj.catalog.name
    return doc


def _workspace_id(obj):
    if hasattr(obj, "workspace_id"):
        return obj.workspace_id
    if isinstance(obj, UCSchema):
        return obj.catalog.workspace_id
    return obj.schema.catalog.workspace_id


def index_uc_object(obj) -> SearchIndex | None:
    """Create/update the SearchIndex row for one mirror object.

    Returns None for the mirrored-but-not-searchable types (external
    locations, storage credentials) — the 1.5 sync calls this for every
    mirror object and the no-op keeps it from crashing the diff loop.
    """
    resource_type = RESOURCE_TYPES.get(type(obj))
    if resource_type is None:
        logger.debug(
            "skipped_non_searchable_uc_type type=%s resource_id=%s",
            type(obj).__name__,
            obj.id,
        )
        return None
    doc = _document(obj)
    row, created = SearchIndex.objects.update_or_create(
        tenant=_tenant_of(obj),
        resource_type=resource_type,
        resource_id=obj.id,
        defaults={
            "title": doc["title"],
            "description": doc["description"],
            "schema_fields": obj.columns if isinstance(obj, UCTable) else None,
            "schema_text": doc["schema_text"],
            "lineage_metadata": doc["lineage_metadata"],
            "owner_id": doc["owner_id"],
            "owner_email": doc["owner_email"],
        },
    )
    row.search_vector = (
        SearchVector("title", weight="A", config="english")
        + SearchVector("description", weight="B", config="english")
        + SearchVector("schema_text", weight="C", config="english")
    )
    row.save(update_fields=["search_vector"])
    logger.info(
        "indexed_uc_object resource_type=%s resource_id=%s created=%s",
        resource_type,
        obj.id,
        created,
    )
    return row


def _tenant_of(obj):
    if isinstance(obj, UCCatalog):
        return obj.workspace.tenant
    if isinstance(obj, UCSchema):
        return obj.catalog.workspace.tenant
    return obj.schema.catalog.workspace.tenant


def delete_uc_index(obj) -> None:
    """Drop the SearchIndex row for a mirror object (mirror deletion).

    No-op for the mirrored-but-not-searchable types.
    """
    resource_type = RESOURCE_TYPES.get(type(obj))
    if resource_type is None:
        return
    SearchIndex.objects.filter(
        tenant=_tenant_of(obj),
        resource_type=resource_type,
        resource_id=obj.id,
    ).delete()


def reindex_uc_workspace(workspace: DatabricksWorkspace) -> int:
    """Re-index the workspace's WHOLE mirror estate; returns the row count.

    Then sweeps stale index rows (mirror rows deleted without
    delete_uc_index) and orphan rows of hard-deleted sibling workspaces.
    The 1.5 sync job calls this after each delta-diff.
    """
    _rel = "schema__catalog__workspace__tenant"
    objects: list = []
    objects.extend(
        UCCatalog.objects.filter(workspace=workspace).select_related("workspace__tenant")
    )
    objects.extend(
        UCSchema.objects.filter(catalog__workspace=workspace).select_related(
            "catalog__workspace__tenant"
        )
    )
    objects.extend(
        UCTable.objects.filter(schema__catalog__workspace=workspace).select_related(_rel)
    )
    objects.extend(UCView.objects.filter(schema__catalog__workspace=workspace).select_related(_rel))
    objects.extend(
        UCVolume.objects.filter(schema__catalog__workspace=workspace).select_related(_rel)
    )
    objects.extend(
        UCModel.objects.filter(schema__catalog__workspace=workspace).select_related(_rel)
    )

    for obj in objects:
        index_uc_object(obj)

    _sweep_stale_rows(workspace, objects)
    return len(objects)


def _sweep_stale_rows(workspace: DatabricksWorkspace, objects: list) -> None:
    """Drop UC index rows whose mirror data is gone.

    Two sweeps, both tenant-scoped and restricted to the UC resource
    types (never the tenant-wide `startswith` catch-all — a sibling
    workspace's rows must survive, and a future `DATABRICKS_UC_*` type
    registered by another feed must not be caught here):

    1. THIS workspace's rows whose mirror id no longer exists.
    2. Orphan rows whose lineage workspace no longer exists at all for
       the tenant (hard-deleting a workspace cascades the mirror rows
       but NOT the index rows — and no reindex ever runs for a deleted
       workspace, so only a sibling's reindex can clean them up).
    """
    type_filter = {"resource_type__in": list(RESOURCE_TYPES.values())}

    # (1) Per-workspace stale sweep — never crosses workspace boundaries.
    known_ids = {obj.id for obj in objects}
    SearchIndex.objects.filter(
        tenant=workspace.tenant,
        lineage_metadata__workspace_id=str(workspace.id),
        **type_filter,
    ).exclude(resource_id__in=known_ids).delete()

    # (2) Orphan-workspace sweep — rows referencing workspaces that no
    # longer exist for the tenant (incl. rows missing the workspace_id
    # key, which this feed always writes — they are unattributable).
    valid_workspace_ids = {
        str(ws_id)
        for ws_id in DatabricksWorkspace.objects.filter(tenant=workspace.tenant).values_list(
            "id", flat=True
        )
    }
    referenced = set(
        SearchIndex.objects.filter(tenant=workspace.tenant, **type_filter)
        .values_list("lineage_metadata__workspace_id", flat=True)
        .distinct()
    )
    orphan_workspace_ids = referenced - valid_workspace_ids
    if orphan_workspace_ids:
        SearchIndex.objects.filter(
            tenant=workspace.tenant,
            lineage_metadata__workspace_id__in=orphan_workspace_ids,
            **type_filter,
        ).delete()
