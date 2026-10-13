"""Phase 1 (openspec add-databricks-uc-read task 1.5) — UC metadata sync.

Fetches the workspace's Unity Catalog estate through the version-pinned
REST surface (D2), delta-diffs it into the 1.2 mirror models, and keeps
the 1.4 search feed exact via ``reindex_uc_workspace`` (the documented
1.4 contract: the sync calls it after each delta-diff).

Identity: the CALLER resolves the D12 decision (``resolve_execution_identity``,
purpose ``uc_sync`` — workspace M2M credential WITH approver-chain audit
linkage) and builds the client through the ``_build_uc_client`` factory
(uc_views, the 1.3 seam). This module never selects credentials itself
beyond the workspace's linked M2M credential — and fails closed (skips,
zero network calls) when the linkage is absent.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from django.utils import timezone

from hub.apps.databricks_admin.client import (
    DatabricksApiClient,
    DatabricksApiError,
    DatabricksOBOError,
)
from hub.apps.databricks_admin.identity import HybridIdentityError, resolve_execution_identity
from hub.apps.databricks_admin.models import (
    DatabricksCredentialAuthMode,
    DatabricksWorkspace,
    UCCatalog,
    UCExternalLocation,
    UCModel,
    UCSchema,
    UCStorageCredential,
    UCTable,
    UCView,
    UCVolume,
)

# The client factory seam (uc_views, task 1.3). Tests redirect it to a
# real local transport; production builds the workspace-mode client.
from hub.apps.databricks_admin.uc_views import _build_uc_client

logger = logging.getLogger(__name__)

MAX_PAGE_SIZE = 100

# Estate key → (api operation, response list key, query-param factory).
# Params are built from the PARENT context (catalog/schema names).
_LIST_SURFACES: dict[str, tuple[str, str, Callable[[str, str], dict]]] = {
    "catalogs": ("uc.catalogs.list", "catalogs", lambda _c, _s: {}),
    "schemas": ("uc.schemas.list", "schemas", lambda c, _s: {"catalog_name": c}),
    "tables": ("uc.tables.list", "tables", lambda c, s: {"catalog_name": c, "schema_name": s}),
    "views": ("uc.views.list", "views", lambda c, s: {"catalog_name": c, "schema_name": s}),
    "volumes": ("uc.volumes.list", "volumes", lambda c, s: {"catalog_name": c, "schema_name": s}),
    "models": ("uc.models.list", "models", lambda c, s: {"catalog_name": c, "schema_name": s}),
    "external_locations": ("uc.external_locations.list", "external_locations", lambda _c, _s: {}),
    "storage_credentials": (
        "uc.storage_credentials.list",
        "storage_credentials",
        lambda _c, _s: {},
    ),
}

# Surfaces nested under a catalog (fetched per catalog).
_CATALOG_SCOPED = ("schemas",)
# Surfaces nested under a schema (fetched per schema).
_SCHEMA_SCOPED = ("tables", "views", "volumes", "models")
# Surfaces nested under nothing (workspace-level).
_WORKSPACE_SCOPED = ("catalogs", "external_locations", "storage_credentials")


def _json_object(
    client: DatabricksApiClient, operation: str, params: dict, path_params: dict | None = None
) -> dict:
    """One version-pinned GET with the 0.7 JSON discipline: a malformed
    2xx body is a classified error, never a leaked JSONDecodeError."""
    response = client.request("GET", operation, params=dict(params), path_params=path_params)
    try:
        payload = response.json()
    except ValueError as exc:
        raise DatabricksApiError(f"{operation} returned a non-JSON body") from exc
    if not isinstance(payload, dict):
        raise DatabricksApiError(f"{operation} returned a non-object body")
    return payload


def _list_pages(client: DatabricksApiClient, operation: str, list_key: str, params: dict) -> list:
    """Follow ``next_page_token`` chains exactly (the UC REST contract).

    1.12 hardening: a repeating ``next_page_token`` (a real workspace bug
    surface) would loop FOREVER — the seen-token guard fails the sync with
    a classified error instead of hanging the worker.
    """
    items: list = []
    seen_tokens: set[str] = set()
    request_params = dict(params)
    request_params["max_results"] = MAX_PAGE_SIZE
    while True:
        payload = _json_object(client, operation, request_params)
        items.extend(payload.get(list_key) or [])
        next_token = payload.get("next_page_token")
        if not next_token:
            return items
        if next_token in seen_tokens:
            raise DatabricksApiError(
                f"{operation} returned a repeating next_page_token "
                f"({next_token!r}) — refusing to loop the pagination"
            )
        seen_tokens.add(next_token)
        request_params["page_token"] = next_token


def _list_path_pages(
    client: DatabricksApiClient,
    operation: str,
    list_key: str,
    path_params: dict,
    *,
    max_results: int = 0,
) -> dict:
    """Follow ``next_page_token`` chains for a PATH-parameterized listing
    (Phase 9 task 9.4 — the effective-permissions convention, design D5's
    gotcha: ``max_results=0``, the server default, then loop until the
    token is absent). Returns the assembled object with ``list_key``
    merged across pages; the repeating-token guard is shared with
    ``_list_pages`` (a real workspace bug surface must fail classified,
    never hang)."""
    items: list = []
    seen_tokens: set[str] = set()
    request_params: dict = {"max_results": max_results}
    while True:
        payload = _json_object(client, operation, request_params, path_params)
        items.extend(payload.get(list_key) or [])
        next_token = payload.get("next_page_token")
        if not next_token:
            return {list_key: items}
        if next_token in seen_tokens:
            raise DatabricksApiError(
                f"{operation} returned a repeating next_page_token "
                f"({next_token!r}) — refusing to loop the pagination"
            )
        seen_tokens.add(next_token)
        request_params["page_token"] = next_token


def _str(item: dict, key: str, default: str = "") -> str:
    value = item.get(key)
    return str(value) if value is not None else default


def _int(item: dict, key: str, default: int = 0) -> int:
    try:
        return int(item.get(key) or default)
    except (TypeError, ValueError):
        return default


def _normalize(key: str, item: Any) -> dict:
    """Map a raw UC REST payload row to the mirror-relevant shape."""
    common = {
        "name": _str(item, "name"),
        "comment": _str(item, "comment"),
        "owner": _str(item, "owner"),
        "full_name": _str(item, "full_name"),
    }
    if key == "catalogs":
        common.update(
            {
                "catalog_type": _str(item, "catalog_type", "MANAGED"),
                "properties": item.get("properties")
                if isinstance(item.get("properties"), dict)
                else {},
            }
        )
    elif key == "schemas":
        common.update(
            {
                "catalog_name": _str(item, "catalog_name"),
                "properties": item.get("properties")
                if isinstance(item.get("properties"), dict)
                else {},
            }
        )
    elif key == "tables":
        columns = item.get("columns")
        tags = item.get("tags")
        common.update(
            {
                "catalog_name": _str(item, "catalog_name"),
                "schema_name": _str(item, "schema_name"),
                "table_type": _str(item, "table_type", "MANAGED"),
                "storage_location": _str(item, "storage_location"),
                "columns": columns if isinstance(columns, list) else [],
                "tags": tags if isinstance(tags, list) else [],
            }
        )
    elif key == "views":
        common.update(
            {
                "catalog_name": _str(item, "catalog_name"),
                "schema_name": _str(item, "schema_name"),
                "view_definition": _str(item, "view_definition"),
            }
        )
    elif key == "volumes":
        common.update(
            {
                "catalog_name": _str(item, "catalog_name"),
                "schema_name": _str(item, "schema_name"),
                "volume_type": _str(item, "volume_type", "MANAGED"),
                "storage_location": _str(item, "storage_location"),
            }
        )
    elif key == "models":
        aliases = item.get("aliases")
        common.update(
            {
                "catalog_name": _str(item, "catalog_name"),
                "schema_name": _str(item, "schema_name"),
                "aliases": aliases if isinstance(aliases, list) else [],
                "latest_version": _int(item, "latest_version"),
            }
        )
    elif key == "external_locations":
        common.update(
            {
                "url": _str(item, "url"),
                "credential_name": _str(item, "credential_name"),
            }
        )
    elif key == "storage_credentials":
        pass
    return common


def fetch_uc_estate(client: DatabricksApiClient) -> dict:
    """The workspace's whole UC estate as normalized dicts.

    Catalogs are paged; schemas are fetched PER catalog and the
    schema-scoped surfaces per schema — the query params carry the
    parent context on every request.
    """
    estate: dict[str, list] = {}
    for key in ("catalogs", "external_locations", "storage_credentials"):
        operation, list_key, params_fn = _LIST_SURFACES[key]
        estate[key] = [
            _normalize(key, item)
            for item in _list_pages(client, operation, list_key, params_fn("", ""))
        ]

    catalog_names = [catalog["name"] for catalog in estate["catalogs"]]
    estate["schemas"] = []
    for catalog_name in catalog_names:
        operation, list_key, params_fn = _LIST_SURFACES["schemas"]
        schemas = [
            _normalize("schemas", item)
            for item in _list_pages(client, operation, list_key, params_fn(catalog_name, ""))
        ]
        estate["schemas"].extend(schemas)
        for schema in schemas:
            for key in _SCHEMA_SCOPED:
                operation, list_key, params_fn = _LIST_SURFACES[key]
                estate.setdefault(key, []).extend(
                    _normalize(key, item)
                    for item in _list_pages(
                        client, operation, list_key, params_fn(catalog_name, schema["name"])
                    )
                )
    for key in _SCHEMA_SCOPED:
        estate.setdefault(key, [])
    return estate


# ── delta-diff ──────────────────────────────────────────────────────────────

# Natural key of each mirror row (the uniqueness column within its parent).
_NATURAL_KEY = {
    UCCatalog: "name",
    UCSchema: "name",
    UCTable: "name",
    UCView: "name",
    UCVolume: "name",
    UCModel: "name",
    UCExternalLocation: "name",
    UCStorageCredential: "name",
}

# Model → (estate key, mirror-field → (payload key, default)).
_FIELD_MAPS: dict = {
    UCCatalog: (
        "catalogs",
        {
            "comment": ("comment", ""),
            "catalog_type": ("catalog_type", "MANAGED"),
            "properties": ("properties", {}),
            "owner": ("owner", ""),
            "full_name": ("full_name", ""),
        },
    ),
    UCSchema: (
        "schemas",
        {
            "comment": ("comment", ""),
            "properties": ("properties", {}),
            "owner": ("owner", ""),
            "full_name": ("full_name", ""),
        },
    ),
    UCTable: (
        "tables",
        {
            "comment": ("comment", ""),
            "table_type": ("table_type", "MANAGED"),
            "storage_location": ("storage_location", ""),
            "columns": ("columns", []),
            "tags": ("tags", []),
            "owner": ("owner", ""),
            "full_name": ("full_name", ""),
        },
    ),
    UCView: (
        "views",
        {
            "comment": ("comment", ""),
            "view_definition": ("view_definition", ""),
            "owner": ("owner", ""),
            "full_name": ("full_name", ""),
        },
    ),
    UCVolume: (
        "volumes",
        {
            "comment": ("comment", ""),
            "volume_type": ("volume_type", "MANAGED"),
            "storage_location": ("storage_location", ""),
            "owner": ("owner", ""),
            "full_name": ("full_name", ""),
        },
    ),
    UCModel: (
        "models",
        {
            "comment": ("comment", ""),
            "aliases": ("aliases", []),
            "latest_version": ("latest_version", 0),
            "owner": ("owner", ""),
            "full_name": ("full_name", ""),
        },
    ),
    UCExternalLocation: (
        "external_locations",
        {
            "url": ("url", ""),
            "credential_name": ("credential_name", ""),
            "owner": ("owner", ""),
            "full_name": ("full_name", ""),
        },
    ),
    UCStorageCredential: (
        "storage_credentials",
        {
            "comment": ("comment", ""),
            "owner": ("owner", ""),
            "full_name": ("full_name", ""),
        },
    ),
}

# Upsert order — parents BEFORE children (a new schema needs its
# catalog mirror row; a new table needs its schema).
_UPSERT_ORDER = (
    UCCatalog,
    UCSchema,
    UCTable,
    UCView,
    UCVolume,
    UCModel,
    UCExternalLocation,
    UCStorageCredential,
)

# Deletion order — children BEFORE parents so ``delete_uc_index`` can
# still resolve the parent chain (and the parent FK CASCADE never
# orphanes a child's index row silently).
_DELETE_ORDER = (
    UCTable,
    UCView,
    UCVolume,
    UCModel,
    UCSchema,
    UCCatalog,
    UCExternalLocation,
    UCStorageCredential,
)


def _scoped_qs(workspace, model):
    if model is UCCatalog:
        return model.objects.filter(workspace=workspace)
    if model is UCSchema:
        return model.objects.filter(catalog__workspace=workspace)
    if model in (UCExternalLocation, UCStorageCredential):
        return model.objects.filter(workspace=workspace)
    return model.objects.filter(schema__catalog__workspace=workspace)


def _parent_resolvers(workspace):
    """Parent lookups cached per apply, filled LAZILY — a fresh estate's
    parents are created BY this very apply (upsert order guarantees a
    parent exists before its children), so a cache miss fetches the row
    just created and caches it (one query per parent, never N+1)."""
    catalog_by_name = {
        catalog.name: catalog for catalog in UCCatalog.objects.filter(workspace=workspace)
    }
    schema_by_key = {
        (schema.catalog.name, schema.name): schema
        for schema in UCSchema.objects.filter(catalog__workspace=workspace).select_related(
            "catalog"
        )
    }

    def parent_scope(model, item):
        if model is UCCatalog:
            return {"workspace": workspace}
        if model is UCSchema:
            catalog_name = item["catalog_name"]
            catalog = catalog_by_name.get(catalog_name)
            if catalog is None:
                catalog = UCCatalog.objects.get(workspace=workspace, name=catalog_name)
                catalog_by_name[catalog_name] = catalog
            return {"catalog": catalog}
        if model in (UCExternalLocation, UCStorageCredential):
            return {"workspace": workspace}
        schema_key = (item["catalog_name"], item["schema_name"])
        schema = schema_by_key.get(schema_key)
        if schema is None:
            schema = UCSchema.objects.select_related("catalog").get(
                catalog__workspace=workspace,
                catalog__name=schema_key[0],
                name=schema_key[1],
            )
            schema_by_key[schema_key] = schema
        return {"schema": schema}

    return parent_scope


def _upsert_collection(workspace, model, rows, counters, parent_scope) -> None:
    """Create new mirror rows; refresh changed ones; unchanged rows are
    NOT rewritten (their ``synced_at`` freshness stamp is left alone)."""
    key_field = _NATURAL_KEY[model]
    field_map = _FIELD_MAPS[model][1]
    existing = {getattr(row, key_field): row for row in _scoped_qs(workspace, model)}
    for item in rows:
        changes = {
            mirror_field: item.get(payload_key, default)
            for mirror_field, (payload_key, default) in field_map.items()
        }
        obj = existing.get(item["name"])
        if obj is None:
            # The natural key rides on every create (it is NOT part of
            # the field map — the map only carries changeable fields).
            model.objects.create(**parent_scope(model, item), name=item["name"], **changes)
            counters["created"] += 1
            continue
        if any(getattr(obj, field) != value for field, value in changes.items()):
            for field, value in changes.items():
                setattr(obj, field, value)
            obj.synced_at = timezone.now()
            obj.save()
            counters["updated"] += 1
        else:
            counters["unchanged"] += 1


def _delete_missing(workspace, model, rows, counters) -> None:
    """Drop mirror rows absent from the estate (index rows first)."""
    remote_names = {item["name"] for item in rows}
    for obj in _scoped_qs(workspace, model):
        if obj.name in remote_names:
            continue
        from hub.apps.databricks_admin.uc_search import delete_uc_index

        delete_uc_index(obj)
        obj.delete()
        counters["deleted"] += 1


def apply_uc_delta(workspace: DatabricksWorkspace, estate: dict) -> dict:
    """Delta-diff the estate into the mirror models (the sync entry
    point runs under ``tenant_context``), then re-run the 1.4 reindex so
    the search feed is exact (sweeps any cascade orphans).

    The upsert/delete phase is ONE transaction — a mid-apply failure
    leaves NO partial mirror (1.5 review hardening). The reindex runs
    AFTER the transaction commits: the index can never get ahead of the
    committed mirror, and its sweep self-heals any index row dropped by
    a rolled-back deletion."""
    from django.db import transaction

    counters = {"created": 0, "updated": 0, "unchanged": 0, "deleted": 0}
    parent_scope = _parent_resolvers(workspace)
    with transaction.atomic():
        for model in _UPSERT_ORDER:
            _upsert_collection(
                workspace, model, estate.get(_FIELD_MAPS[model][0], []), counters, parent_scope
            )
        for model in _DELETE_ORDER:
            _delete_missing(workspace, model, estate.get(_FIELD_MAPS[model][0], []), counters)
    from hub.apps.databricks_admin.uc_search import reindex_uc_workspace

    reindex_uc_workspace(workspace)
    return counters


# ── orchestration (D12) ─────────────────────────────────────────────────────


def _select_service_credential(workspace):
    """The workspace's M2M credential for background syncs — prefer the
    one WITH approver-chain linkage, then the newest."""
    credentials = list(
        workspace.credentials.filter(auth_mode=DatabricksCredentialAuthMode.OAUTH_M2M).order_by(
            "-created_at"
        )
    )
    if not credentials:
        return None
    linked = [credential for credential in credentials if credential.approval_request_id]
    return (linked or credentials)[0]


def _emit_sync_audit(workspace, *, success: bool, details: dict) -> None:
    """Best-effort sync audit (an audit-DB outage never blocks a sync)."""
    try:
        from hub.apps.audit.event_types import (
            DATABRICKS_UC_METADATA_SYNC_FAILED,
            DATABRICKS_UC_METADATA_SYNCED,
        )
        from hub.apps.audit.utils import create_audit_event

        action = DATABRICKS_UC_METADATA_SYNCED if success else DATABRICKS_UC_METADATA_SYNC_FAILED
        create_audit_event(
            resource_type="DATABRICKS_WORKSPACE",
            action=action,
            tenant=workspace.tenant,
            resource_id=str(workspace.id),
            result="SUCCESS" if success else "FAILURE",
            details=details,
        )
    except Exception:
        logger.warning("databricks_uc_sync_audit_failed", extra={"workspace": str(workspace.id)})


def sync_uc_workspace(
    workspace: DatabricksWorkspace,
    *,
    client_factory: Callable | None = None,
) -> dict:
    """Sync ONE workspace end-to-end.

    Returns ``{"counters": {...}}`` on success or ``{"skipped": reason}``
    for the fail-closed conditions (no M2M credential, no approver-chain
    linkage, D12 violation) — a skip NEVER touches the network. Raises
    only for transport/API failures (the job layer marks FAILED and the
    retry policy applies). Every outcome records its 1.10 metric
    (outcome + duration; success additionally rows + last-success).
    """
    tenant_id = str(workspace.tenant_id)
    start = time.perf_counter()

    # Tenant Isolation RLS contract (CLAUDE.md): the sync is a WORKER —
    # every tenant-scoped access (credential lookup, mirror upserts/
    # deletes, the audit row, the reindex) must run inside
    # ``tenant_context``. The entry point establishes the context ITSELF
    # (self-contained — a future caller can never forget the wrap; the
    # job layer's own wrap stays as harmless nesting).
    from hub.apps.tenants.request_tenant import tenant_context

    with tenant_context(tenant_id):
        return _sync_uc_workspace_in_context(
            workspace,
            tenant_id=tenant_id,
            start=start,
            client_factory=client_factory,
        )


def _sync_uc_workspace_in_context(
    workspace: DatabricksWorkspace,
    *,
    tenant_id: str,
    start: float,
    client_factory: Callable | None = None,
) -> dict:
    """The tenant-context-wrapped body of ``sync_uc_workspace``."""
    from hub.apps.databricks_admin import metrics

    factory = client_factory or _build_uc_client

    def _record_skip(reason: str) -> dict:
        logger.warning(
            "databricks_uc_sync_skipped", extra={"workspace": str(workspace.id), "reason": reason}
        )
        metrics.record_sync_outcome("skipped", tenant_id=tenant_id)
        metrics.record_sync_duration(seconds=time.perf_counter() - start)
        return {"skipped": reason}

    credential = _select_service_credential(workspace)
    if credential is None:
        return _record_skip("workspace has no M2M credential (D12 background identity)")
    if credential.approval_request is None:
        return _record_skip(
            "the workspace M2M credential carries no approver-chain "
            "linkage (approval_request) — D12 background execution is "
            "fail-closed without human approval lineage"
        )
    try:
        identity = resolve_execution_identity(
            purpose="uc_sync",
            workspace=workspace,
            credential=credential,
            approval_request=credential.approval_request,
        )
    except (HybridIdentityError, DatabricksOBOError) as exc:
        return _record_skip(f"D12 identity resolution failed: {exc}")

    # 1.10 — the WHOLE fetch+apply is one guarded block: a TRANSPORT/API
    # failure (the most likely failure mode) emits the per-workspace
    # SYNC_FAILED audit row + the failure metric, then re-raises (the
    # job layer's JOB_FAILED row is not a substitute for the
    # workspace-scoped record).
    try:
        with factory(workspace, identity) as client:
            estate = fetch_uc_estate(client)
        counters = apply_uc_delta(workspace, estate)
    except Exception as exc:
        _emit_sync_audit(
            workspace,
            success=False,
            details={"error": str(exc), "error_type": type(exc).__name__},
        )
        metrics.record_sync_outcome("failure", tenant_id=tenant_id)
        metrics.record_sync_duration(seconds=time.perf_counter() - start)
        raise

    # 1.6 — extend the lineage graph from the fresh mirror. Fail-soft:
    # the mirror is the load-bearing contract; lineage is a derived
    # consumer and must never fail the metadata sync.
    lineage = None
    try:
        from hub.apps.contracts.lineage_sync import sync_uc_lineage

        lineage = sync_uc_lineage(tenant=workspace.tenant, workspace_id=str(workspace.id))
    except Exception as exc:
        logger.warning(
            "databricks_uc_lineage_sync_failed",
            extra={"workspace": str(workspace.id), "error": str(exc)},
        )

    details = dict(counters)
    if lineage is not None:
        details["lineage"] = lineage
    _emit_sync_audit(workspace, success=True, details=details)
    metrics.record_sync_outcome("success", tenant_id=tenant_id)
    metrics.record_sync_duration(seconds=time.perf_counter() - start)
    for operation in ("created", "updated", "deleted"):
        metrics.record_sync_rows(operation, counters.get(operation, 0), tenant_id=tenant_id)
    metrics.record_sync_success_timestamp(
        tenant_id=tenant_id,
        workspace_id=str(workspace.id),
        value=time.time(),
    )
    return {"counters": counters, "lineage": lineage}
