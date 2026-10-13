"""ML-asset management views (openspec add-databricks-ml-assets task
12.6) — the management surface the ML-assets page rides (design D5/D7).

- **models** — the P1 mirror listing (mirror-first: ZERO network
  reads); the register POST ensures the registered model through the
  MLflow surface (the GET's 404 creates it — never a blind create),
  upserts the mirror row, and emits ``DATABRICKS_ML_MODEL_REGISTERED``.
- **versions** — the 12.2 service's version log; the reported version
  row lands in the mirror and ``DATABRICKS_ML_VERSION_LOGGED`` emits.
- **aliases** — set/remove through the UC REST pins (the 12.2
  service); ``DATABRICKS_ML_ALIAS_SET``/``REMOVED`` emit per performed
  operation; the model row's aliases list reflects the landed state.
- **feature tables** — the mirror-derived listing (the 12.3 tag
  convention, ZERO network reads); the mark/unmark drive the UC REST
  tag assignments — ``DATABRICKS_ML_FEATURE_TAG_SET`` is the
  vocabulary's single tag event for BOTH directions.
- **serving/vector endpoints** — the 12.4 service; the lists are
  mirror-first (ZERO network reads), the creates/deletes drive the
  pinned client and ``DATABRICKS_ML_SERVING_CREATED``/``DELETED`` emit
  (``SERVING_UPDATED`` awaits the endpoint-config-update operation —
  the 12.4 design's documented follow-up).

The surface sits behind the ONE flag gate (``gate_ml_assets`` — design
D5) on top of the master control-plane gate; a flag-off request refuses
403 ``DATABRICKS_ML_ASSETS_DISABLED`` with ZERO workspace API calls.
One audit row per PERFORMED operation (resource_type=
``DATABRICKS_ML_ASSET``, identifiers only, best-effort — the Phase 273
contract); a refusal emits NOTHING. A workspace 404 surfaces the
UC-DB-019 error table's classified ``DATABRICKS_UC_OBJECT_NOT_FOUND``.

The client factory seam (``_build_ml_assets_client``) is the 0.8
``_build_probe_client`` convention — tests redirect it to a local
transport, the client itself is the production client.
"""

from __future__ import annotations

from typing import Any, ClassVar

from rest_framework import status, viewsets
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.databricks_admin.client import DatabricksApiError
from hub.apps.databricks_admin.feature_tables import (
    feature_tables_for_workspace,
    mark_feature_table,
    unmark_feature_table,
)
from hub.apps.databricks_admin.ml_assets import (
    MlAssetsDisabled,
    create_serving_endpoint,
    create_vector_search_endpoint,
    delete_serving_endpoint,
    emit_ml_asset_audit,
    ensure_registered_model,
    gate_ml_assets,
    register_model_version,
    remove_model_alias,
    set_model_alias,
)
from hub.apps.databricks_admin.models import (
    DatabricksMlServingEndpoint,
    DatabricksWorkspace,
    UCModel,
    UCTable,
)
from hub.apps.databricks_admin.throttles import MlAssetsRateThrottle
from hub.apps.databricks_admin.views import _gate_control_plane


class _MlAssetsDisabled(APIException):
    """The D5 surface gate — the flag is off for this tenant (the
    service gate's DRF-facing twin; ``gate_ml_assets`` stays
    framework-free, the view translates)."""

    status_code = status.HTTP_403_FORBIDDEN
    code: ClassVar[str] = "DATABRICKS_ML_ASSETS_DISABLED"
    default_detail: ClassVar[dict[str, str]] = {
        "code": "DATABRICKS_ML_ASSETS_DISABLED",
        "message": "The ML-assets surface is disabled for this tenant",
    }


class _UcObjectNotFound(APIException):
    """The UC-DB-019 error table's classified 404 — an unknown mirror
    row OR the workspace's own 404 on the operation."""

    status_code = status.HTTP_404_NOT_FOUND
    code: ClassVar[str] = "DATABRICKS_UC_OBJECT_NOT_FOUND"
    default_detail: ClassVar[dict[str, str]] = {
        "code": "DATABRICKS_UC_OBJECT_NOT_FOUND",
        "message": "The Unity Catalog object was not found",
    }


class _MlInvalidFullName(APIException):
    """The register payload's full_name is missing or not the
    three-part ``catalog.schema.name`` shape."""

    status_code = status.HTTP_400_BAD_REQUEST
    code: ClassVar[str] = "DATABRICKS_ML_INVALID_FULL_NAME"
    default_detail: ClassVar[dict[str, str]] = {
        "code": "DATABRICKS_ML_INVALID_FULL_NAME",
        "message": "full_name must be the three-part catalog.schema.name shape",
    }


class _MlInvalidConfig(APIException):
    """The serving/vector payload is malformed (a missing/invalid name
    or a non-object config)."""

    status_code = status.HTTP_400_BAD_REQUEST
    code: ClassVar[str] = "DATABRICKS_ML_INVALID_CONFIG"
    default_detail: ClassVar[dict[str, str]] = {
        "code": "DATABRICKS_ML_INVALID_CONFIG",
        "message": "The payload must carry a non-empty name and an object config",
    }


class _MlApiError(APIException):
    """A workspace rejection surfaces with the client's classified code
    (never a raw 500)."""

    def __init__(self, http_status: int, code: str, message: str):
        self.status_code = http_status
        self.code = code
        super().__init__(detail={"code": code, "message": message})


def _gate_ml_assets_surface(view) -> None:
    try:
        gate_ml_assets(view)
    except MlAssetsDisabled:
        raise _MlAssetsDisabled() from None


def _build_ml_assets_client(workspace: DatabricksWorkspace, credential=None):
    """The REAL production client in workspace mode (the 0.8
    `_build_probe_client` convention). Tests redirect this factory to a
    local transport — the client itself is the production client."""
    from hub.apps.databricks_admin.client import DatabricksApiClient

    if credential is None:
        credential = (
            workspace.credentials.filter(auth_mode__in=["PAT", "OAUTH_M2M"])
            .order_by("-created_at")
            .first()
        )
    kwargs: dict = {}
    if credential is not None:
        kwargs["credential_config"] = credential.get_config()
        kwargs["auth_mode"] = credential.auth_mode
    return DatabricksApiClient(
        workspace=workspace,
        tenant_id=str(workspace.tenant_id),
        **kwargs,
    )


def _call(op):
    """Run a client operation; a workspace 404 surfaces the error
    table's classified code, any other rejection carries the client's
    own classified code + status."""
    try:
        return op()
    except DatabricksApiError as exc:
        http_status = getattr(exc, "status_code", None) or status.HTTP_400_BAD_REQUEST
        code = getattr(exc, "code", None) or "DATABRICKS_API_ERROR"
        if http_status == status.HTTP_404_NOT_FOUND:
            raise _UcObjectNotFound() from None
        raise _MlApiError(http_status, code, str(exc)) from None


def _parse_full_name(payload: dict) -> tuple[str, str, str]:
    full_name = str((payload or {}).get("full_name") or "").strip()
    parts = full_name.split(".")
    if len(parts) != 3 or any(not part for part in parts):
        raise _MlInvalidFullName()
    return parts[0], parts[1], parts[2]


def _model_to_dict(row: UCModel) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "full_name": row.full_name,
        "comment": row.comment,
        "owner": row.owner,
        "aliases": row.aliases,
        "latest_version": row.latest_version,
        "synced_at": row.synced_at.isoformat(),
    }


def _table_to_dict(row: UCTable) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "full_name": row.full_name,
        "table_type": row.table_type,
        "tags": row.tags,
        "synced_at": row.synced_at.isoformat(),
    }


def _endpoint_to_dict(row: DatabricksMlServingEndpoint) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "endpoint_type": row.endpoint_type,
        "state": row.state,
        "config": row.config,
        "synced_at": row.synced_at.isoformat(),
    }


def _paginated(request, rows: list[Any]) -> Response:
    paginator = StandardPageNumberPagination()
    page = paginator.paginate_queryset(rows, request)
    return paginator.get_paginated_response(list(page) if page is not None else [])


class DatabricksMlAssetViewSet(viewsets.ViewSet):
    """ML-asset management (authenticated users, flag-gated)."""

    throttle_classes = (MlAssetsRateThrottle,)
    throttle_scope = "databricks_ml_assets"

    def get_permissions(self):
        return [IsAuthenticated()]

    def initial(self, request, *args, **kwargs):
        _gate_control_plane(self)
        _gate_ml_assets_surface(self)
        return super().initial(request, *args, **kwargs)

    def _workspace(self, request, workspace_id) -> DatabricksWorkspace:
        from rest_framework.exceptions import NotFound

        workspace = DatabricksWorkspace.objects.filter(
            tenant=getattr(request, "tenant", None) or getattr(request.user, "tenant", None),
            id=workspace_id,
        ).first()
        if workspace is None:
            raise NotFound()
        return workspace

    def _model(self, workspace: DatabricksWorkspace, model_id) -> UCModel:
        row = UCModel.objects.filter(schema__catalog__workspace=workspace, id=model_id).first()
        if row is None:
            raise _UcObjectNotFound()
        return row

    def _table(self, workspace: DatabricksWorkspace, table_id) -> UCTable:
        row = UCTable.objects.filter(schema__catalog__workspace=workspace, id=table_id).first()
        if row is None:
            raise _UcObjectNotFound()
        return row

    # ── models (mirror-first list + register) ─────────────────────────

    def models(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        rows = list(UCModel.objects.filter(schema__catalog__workspace=workspace).order_by("name"))
        return _paginated(request, [_model_to_dict(row) for row in rows])

    def register_model(self, request, workspace_id):
        from hub.apps.databricks_admin.models import UCSchema

        workspace = self._workspace(request, workspace_id)
        catalog_name, schema_name, model_name = _parse_full_name(request.data or {})
        full_name = f"{catalog_name}.{schema_name}.{model_name}"
        schema = UCSchema.objects.filter(
            catalog__workspace=workspace, catalog__name=catalog_name, name=schema_name
        ).first()
        if schema is None:
            raise _UcObjectNotFound()
        client = _build_ml_assets_client(workspace)
        _call(lambda: ensure_registered_model(client, full_name))
        row, _ = UCModel.objects.update_or_create(
            schema=schema,
            name=model_name,
            defaults={"full_name": full_name},
        )
        emit_ml_asset_audit(
            "DATABRICKS_ML_MODEL_REGISTERED",
            workspace,
            resource_id=str(row.id),
            actor_user=request.user,
            details={"full_name": full_name, "workspace_id": str(workspace.id)},
        )
        return Response(_model_to_dict(row), status=status.HTTP_201_CREATED)

    # ── versions ──────────────────────────────────────────────────────

    def log_version(self, request, workspace_id, model_id):
        workspace = self._workspace(request, workspace_id)
        model = self._model(workspace, model_id)
        payload = request.data or {}
        source = str(payload.get("source") or "").strip()
        if not source:
            raise _MlInvalidConfig()
        run_id = str(payload.get("run_id") or "")
        client = _build_ml_assets_client(workspace)
        version_row = _call(
            lambda: register_model_version(client, model=model, source=source, run_id=run_id)
        )
        emit_ml_asset_audit(
            "DATABRICKS_ML_VERSION_LOGGED",
            workspace,
            resource_id=str(version_row.id),
            actor_user=request.user,
            details={
                "full_name": model.full_name,
                "version": version_row.version,
                "workspace_id": str(workspace.id),
            },
        )
        return Response({"version": version_row.version}, status=status.HTTP_201_CREATED)

    # ── aliases ───────────────────────────────────────────────────────

    def set_alias(self, request, workspace_id, model_id, alias):
        workspace = self._workspace(request, workspace_id)
        model = self._model(workspace, model_id)
        payload = request.data or {}
        try:
            version = int(payload.get("version_num"))
        except (TypeError, ValueError):
            raise _MlInvalidConfig() from None
        client = _build_ml_assets_client(workspace)
        _call(lambda: set_model_alias(client, model=model, alias=alias, version=version))
        emit_ml_asset_audit(
            "DATABRICKS_ML_ALIAS_SET",
            workspace,
            resource_id=str(model.id),
            actor_user=request.user,
            details={
                "full_name": model.full_name,
                "alias": alias,
                "workspace_id": str(workspace.id),
            },
        )
        return Response({"full_name": model.full_name, "alias": alias, "version_num": version})

    def remove_alias(self, request, workspace_id, model_id, alias):
        workspace = self._workspace(request, workspace_id)
        model = self._model(workspace, model_id)
        client = _build_ml_assets_client(workspace)
        _call(lambda: remove_model_alias(client, model=model, alias=alias))
        emit_ml_asset_audit(
            "DATABRICKS_ML_ALIAS_REMOVED",
            workspace,
            resource_id=str(model.id),
            actor_user=request.user,
            details={
                "full_name": model.full_name,
                "alias": alias,
                "workspace_id": str(workspace.id),
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── feature tables (the 12.3 tag convention) ──────────────────────

    def feature_tables(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        rows = feature_tables_for_workspace(workspace)
        return _paginated(request, [_table_to_dict(row) for row in rows])

    def mark_feature_table(self, request, workspace_id, table_id):
        workspace = self._workspace(request, workspace_id)
        table = self._table(workspace, table_id)
        client = _build_ml_assets_client(workspace)
        _call(lambda: mark_feature_table(client, table.full_name))
        emit_ml_asset_audit(
            "DATABRICKS_ML_FEATURE_TAG_SET",
            workspace,
            resource_id=str(table.id),
            actor_user=request.user,
            details={
                "full_name": table.full_name,
                "tag_key": "feature_store",
                "workspace_id": str(workspace.id),
            },
        )
        return Response(_table_to_dict(table))

    def unmark_feature_table(self, request, workspace_id, table_id):
        workspace = self._workspace(request, workspace_id)
        table = self._table(workspace, table_id)
        client = _build_ml_assets_client(workspace)
        _call(lambda: unmark_feature_table(client, table.full_name))
        emit_ml_asset_audit(
            "DATABRICKS_ML_FEATURE_TAG_SET",
            workspace,
            resource_id=str(table.id),
            actor_user=request.user,
            details={
                "full_name": table.full_name,
                "tag_key": "feature_store",
                "workspace_id": str(workspace.id),
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── serving + vector endpoints (the 12.4 surface) ─────────────────

    def _parse_endpoint_payload(self, payload: dict) -> tuple[str, dict]:
        name = str((payload or {}).get("name") or "").strip()
        config = (payload or {}).get("config")
        if not name or not isinstance(config, dict):
            raise _MlInvalidConfig()
        return name, config

    def serving_endpoints(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        rows = list(
            DatabricksMlServingEndpoint.objects.filter(
                workspace=workspace, endpoint_type="SERVING"
            ).order_by("name")
        )
        return _paginated(request, [_endpoint_to_dict(row) for row in rows])

    def create_serving_endpoint(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        name, config = self._parse_endpoint_payload(request.data or {})
        client = _build_ml_assets_client(workspace)
        row = _call(
            lambda: create_serving_endpoint(client, workspace=workspace, name=name, config=config)
        )
        emit_ml_asset_audit(
            "DATABRICKS_ML_SERVING_CREATED",
            workspace,
            resource_id=str(row.id),
            actor_user=request.user,
            details={
                "name": name,
                "endpoint_type": "SERVING",
                "workspace_id": str(workspace.id),
            },
        )
        return Response(_endpoint_to_dict(row), status=status.HTTP_201_CREATED)

    def delete_serving_endpoint(self, request, workspace_id, name):
        workspace = self._workspace(request, workspace_id)
        client = _build_ml_assets_client(workspace)
        _call(lambda: delete_serving_endpoint(client, workspace=workspace, name=name))
        emit_ml_asset_audit(
            "DATABRICKS_ML_SERVING_DELETED",
            workspace,
            resource_id=None,
            actor_user=request.user,
            details={
                "name": name,
                "endpoint_type": "SERVING",
                "workspace_id": str(workspace.id),
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def vector_search_endpoints(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        rows = list(
            DatabricksMlServingEndpoint.objects.filter(
                workspace=workspace, endpoint_type="VECTOR"
            ).order_by("name")
        )
        return _paginated(request, [_endpoint_to_dict(row) for row in rows])

    def create_vector_search_endpoint(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        name, config = self._parse_endpoint_payload(request.data or {})
        client = _build_ml_assets_client(workspace)
        row = _call(
            lambda: create_vector_search_endpoint(
                client, workspace=workspace, name=name, config=config
            )
        )
        emit_ml_asset_audit(
            "DATABRICKS_ML_SERVING_CREATED",
            workspace,
            resource_id=str(row.id),
            actor_user=request.user,
            details={
                "name": name,
                "endpoint_type": "VECTOR",
                "workspace_id": str(workspace.id),
            },
        )
        return Response(_endpoint_to_dict(row), status=status.HTTP_201_CREATED)
