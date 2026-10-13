"""Phase 1 (openspec add-databricks-uc-read task 1.3) — UC browse API.

Mirror-first browse: listings and details read the mirror models (1.2);
the table-detail effective-permissions answer is LIVE per request through
the UC REST `effective-permissions` endpoint, executed with the user's
OBO bearer (D12 INTERACTIVE identity — fail-closed without a binding,
never a service-credential fallback).

Nested under the workspace registry; gated by the workspace-registry
flag + kill switch (the 0.12 `_gate_control_plane`); throttled per the
Phase 273 contract (tenant-scoped scope).
"""

from __future__ import annotations

import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.databricks_admin.client import (
    DatabricksApiClient,
    DatabricksApiError,
    DatabricksOBOError,
)
from hub.apps.databricks_admin.identity import HybridIdentityError, resolve_execution_identity
from hub.apps.databricks_admin.models import (
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
from hub.apps.databricks_admin.obo_tokens import OBOTokenProvider
from hub.apps.databricks_admin.views import _gate_control_plane

logger = logging.getLogger(__name__)


def _to_dict(obj, fields: tuple[str, ...]) -> dict:
    return {f: getattr(obj, f) for f in fields}


def _paginated(request, queryset, serializer) -> Response:
    paginator = StandardPageNumberPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator.get_paginated_response(
        [serializer(row) for row in (page if page is not None else queryset)]
    )


def _build_uc_obo_provider(workspace: DatabricksWorkspace, user):
    """The user's OBO token source for this workspace, or None.

    None → the D12 decision point fails closed (no binding = no browse on
    interactive paths). The OIDC client id comes from the workspace's SSO
    config; a missing config is ALSO a fail-closed outcome downstream.
    """
    from hub.apps.databricks_admin.bindings import resolve_binding
    from hub.apps.tenants.models import TenantConfig

    binding = resolve_binding(user=user, workspace=workspace)
    if binding is None:
        return None
    config_row = TenantConfig.objects.filter(tenant=workspace.tenant).first()
    sso = (config_row.get_sso_config() if config_row else {}).get("databricks", {})
    if not sso.get("client_id"):
        return None
    return OBOTokenProvider(
        binding=binding,
        oidc_client_id=sso["client_id"],
        oidc_base_url=f"https://{workspace.host}",
    )


def _build_uc_client(workspace: DatabricksWorkspace, identity) -> DatabricksApiClient:
    """The browse client for a resolved identity (factory seam — tests
    redirect to a local transport; the client is the production client).

    The GCP fallback (0b.8) resolves the workspace's OWN PAT/M2M
    credential with ``obo_provider=None`` — the client must carry that
    credential or the D12 decision result is discarded and the
    permissions call runs with NO auth (1.3 review fix)."""
    kwargs: dict = {}
    if identity.credential is not None:
        kwargs["credential_config"] = identity.credential.get_config()
        kwargs["auth_mode"] = identity.credential.auth_mode
    return DatabricksApiClient(
        workspace=workspace,
        tenant_id=str(workspace.tenant_id),
        obo_provider=identity.obo_provider,
        **kwargs,
    )


class UCBrowseViewSet(viewsets.ViewSet):
    """Nested UC browse endpoints (authenticated users, flag-gated)."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "databricks_uc_browse"

    def get_permissions(self):
        return [IsAuthenticated()]

    def initial(self, request, *args, **kwargs):
        _gate_control_plane(self)
        return super().initial(request, *args, **kwargs)

    def _workspace(self, request, workspace_id) -> DatabricksWorkspace:
        workspace = DatabricksWorkspace.objects.filter(
            tenant=getattr(request, "tenant", None) or getattr(request.user, "tenant", None),
            id=workspace_id,
        ).first()
        if workspace is None:
            raise NotFound()
        return workspace

    # ── listings (mirror-first) ──────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="catalogs")
    def catalogs(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        qs = UCCatalog.objects.filter(workspace=workspace)
        return _paginated(
            request,
            qs,
            lambda c: _to_dict(
                c,
                (
                    "id",
                    "name",
                    "catalog_type",
                    "comment",
                    "properties",
                    "owner",
                    "full_name",
                    "synced_at",
                ),
            ),
        )

    @action(detail=False, methods=["get"], url_path="catalogs/(?P<catalog_id>[^/.]+)/schemas")
    def schemas(self, request, workspace_id, catalog_id):
        workspace = self._workspace(request, workspace_id)
        catalog = UCCatalog.objects.filter(workspace=workspace, id=catalog_id).first()
        if catalog is None:
            raise NotFound()
        qs = UCSchema.objects.filter(catalog=catalog)
        return _paginated(
            request,
            qs,
            lambda s: _to_dict(s, ("id", "name", "comment", "owner", "full_name", "synced_at")),
        )

    def _schema_scoped(self, request, workspace_id, schema_id, model, fields):
        workspace = self._workspace(request, workspace_id)
        schema = UCSchema.objects.filter(catalog__workspace=workspace, id=schema_id).first()
        if schema is None:
            raise NotFound()
        qs = model.objects.filter(schema=schema)
        return _paginated(request, qs, lambda row: _to_dict(row, fields))

    @action(detail=False, methods=["get"], url_path="schemas/(?P<schema_id>[^/.]+)/tables")
    def tables(self, request, workspace_id, schema_id):
        return self._schema_scoped(
            request,
            workspace_id,
            schema_id,
            UCTable,
            ("id", "name", "table_type", "columns", "comment", "owner", "full_name", "synced_at"),
        )

    @action(detail=False, methods=["get"], url_path="schemas/(?P<schema_id>[^/.]+)/views")
    def views(self, request, workspace_id, schema_id):
        return self._schema_scoped(
            request,
            workspace_id,
            schema_id,
            UCView,
            ("id", "name", "comment", "owner", "full_name", "synced_at"),
        )

    @action(detail=False, methods=["get"], url_path="schemas/(?P<schema_id>[^/.]+)/volumes")
    def volumes(self, request, workspace_id, schema_id):
        return self._schema_scoped(
            request,
            workspace_id,
            schema_id,
            UCVolume,
            ("id", "name", "volume_type", "comment", "owner", "full_name", "synced_at"),
        )

    @action(detail=False, methods=["get"], url_path="schemas/(?P<schema_id>[^/.]+)/models")
    def models(self, request, workspace_id, schema_id):
        return self._schema_scoped(
            request,
            workspace_id,
            schema_id,
            UCModel,
            (
                "id",
                "name",
                "aliases",
                "latest_version",
                "comment",
                "owner",
                "full_name",
                "synced_at",
            ),
        )

    @action(detail=False, methods=["get"], url_path="external-locations")
    def external_locations(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        qs = UCExternalLocation.objects.filter(workspace=workspace)
        return _paginated(
            request,
            qs,
            lambda loc: _to_dict(
                loc, ("id", "name", "url", "credential_name", "owner", "full_name", "synced_at")
            ),
        )

    @action(detail=False, methods=["get"], url_path="storage-credentials")
    def storage_credentials(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        qs = UCStorageCredential.objects.filter(workspace=workspace)
        return _paginated(
            request,
            qs,
            lambda c: _to_dict(c, ("id", "name", "comment", "owner", "full_name", "synced_at")),
        )

    # ── table detail + LIVE effective permissions ────────────────────

    @action(detail=False, methods=["get"], url_path="tables/(?P<table_id>[^/.]+)")
    def table_detail(self, request, workspace_id, table_id):
        workspace = self._workspace(request, workspace_id)
        table = (
            UCTable.objects.filter(schema__catalog__workspace=workspace, id=table_id)
            .select_related("schema__catalog")
            .first()
        )
        if table is None:
            raise NotFound()

        # D12 INTERACTIVE identity: OBO required; no binding → fail-closed.
        # Identity failures are CLASSIFIED at the boundary (they are not
        # server faults): the catalogue maps DATABRICKS_OBO_REFRESH_FAILED
        # to 502 and DATABRICKS_HYBRID_IDENTITY_VIOLATION to 403 — before
        # any network call.
        obo_provider = _build_uc_obo_provider(workspace, request.user)
        try:
            identity = resolve_execution_identity(
                purpose="catalog_browse",
                workspace=workspace,
                obo_provider=obo_provider,
            )
        except DatabricksOBOError as exc:
            return Response(
                {"code": exc.code, "message": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except HybridIdentityError as exc:
            return Response(
                {"code": exc.code, "message": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )
        client = _build_uc_client(workspace, identity)
        try:
            try:
                # Phase 9 (task 9.4) — the effective-permissions answer is
                # PAGED (design D5's gotcha: max_results=0 + the
                # next_page_token loop); a one-shot fetch silently
                # truncates the permissions list.
                from hub.apps.databricks_admin.uc_sync import _list_path_pages

                permissions = _list_path_pages(
                    client,
                    "uc.effective_permissions.table",
                    "privilege_assignments",
                    {"full_name": table.full_name},
                )
            finally:
                client.close()
        except DatabricksApiError as exc:
            logger.warning(
                "databricks_uc_effective_permissions_failed",
                extra={"workspace_id": str(workspace.id), "error_code": exc.code},
            )
            return Response(
                {
                    "code": "DATABRICKS_AUTH_FAILED",
                    "message": "Effective permissions lookup failed",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "id": str(table.id),
                "name": table.name,
                "table_type": table.table_type,
                "columns": table.columns,
                "comment": table.comment,
                "owner": table.owner,
                "full_name": table.full_name,
                "catalog": table.schema.catalog.name,
                "schema": table.schema.name,
                "synced_at": table.synced_at,
                "effective_permissions": permissions,
            },
            status=status.HTTP_200_OK,
        )
