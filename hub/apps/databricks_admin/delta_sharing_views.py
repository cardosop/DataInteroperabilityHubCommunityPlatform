"""Phase 5 (task 5.3) — the native Delta Sharing 1.0 protocol endpoints.

Routes (mounted at ``/api/v1/databricks/delta-sharing``):

- ``GET profile`` — the v1 client profile (shareCredentialsVersion,
  endpoint, the request's bearer token echoed);
- ``GET shares`` / ``GET shares/{share}`` — the oracle list/detail
  envelopes (``items`` arrays of ``{name}`` / ``{name, share}`` /
  ``{name, share, schema}`` objects);
- ``GET shares/{share}/schemas``, ``.../tables``, ``.../tables/{table}``;
- ``GET .../tables/{table}/metadata`` — the ndjson line protocol
  (``{"protocol": ...}`` + ``{"metaData": ...}``) with the
  ``delta-table-version`` response header;
- ``POST .../tables/{table}/query`` — JSON mode: the SELECT rides the
  production warehouse connector; the envelope appends the Hub's
  documented ``{"query": {"count", "rows"}}`` line;
- ``GET .../tables/{table}/version`` — Parquet mode: presigned-URL
  ``file`` actions from the snapshot row (materialized by 5.4's job).

Auth: bearer tokens ONLY (``DeltaShareTokenAuthentication``) — no
sessions. Every request is throttled per recipient token (5.2) and
audits ``WAREHOUSE_SHARE_ACCESSED`` (IP + user-agent, best-effort). A
401 audits ``WAREHOUSE_SHARE_AUTH_FAILED``. The token's scope triple and
``semantic_federate_optout`` filter EVERY listing and direct fetch —
anything outside the scope answers 404 (the UC-DB-012 contract).
"""

from __future__ import annotations

import json
import logging

from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.exceptions import NotAuthenticated, NotFound, ValidationError
from rest_framework.response import Response

from hub.apps.audit.event_types import (
    WAREHOUSE_SHARE_ACCESSED,
    WAREHOUSE_SHARE_AUTH_FAILED,
)
from hub.apps.databricks_admin.delta_sharing_auth import DeltaShareTokenAuthentication
from hub.apps.databricks_admin.throttles import DeltaShareTokenRateThrottle

logger = logging.getLogger(__name__)

_NDJSON = "application/x-ndjson; charset=utf-8"


class DeltaSharingProtocolViewSet(viewsets.ViewSet):
    """The protocol surface — bearer-token auth, per-token throttle, no
    DRF permission classes (the token IS the permission)."""

    authentication_classes = (DeltaShareTokenAuthentication,)
    permission_classes = ()
    throttle_classes = (DeltaShareTokenRateThrottle,)

    def perform_authentication(self, request):
        """Central chokepoint: a request with no successfully resolved
        token is refused here (no permission class will — the protocol
        has none) and audits ``WAREHOUSE_SHARE_AUTH_FAILED``."""
        super().perform_authentication(request)
        if getattr(request, "successful_authenticator", None) is None:
            _emit_auth_failed(request)
            raise NotAuthenticated()

    # ── catalog listing actions ────────────────────────────────────────

    def profile(self, request):
        """GET /profile — the v1 client profile."""
        token = request.auth
        endpoint = request.build_absolute_uri("/api/v1/databricks/delta-sharing")
        self._audit_access(request, token)
        return Response(
            {
                "shareCredentialsVersion": 1,
                "endpoint": endpoint,
                "bearerToken": request.META.get("HTTP_AUTHORIZATION", "").split(" ", 1)[-1],
            }
        )

    def list_shares(self, request):
        token = request.auth
        self._audit_access(request, token)
        from hub.apps.databricks_admin.delta_sharing_service import (
            SHARE_NAME,
            shareable_assets,
        )

        if not self._scope_allows(token, SHARE_NAME, None, None):
            return Response({"items": []})
        # The share exists iff the tenant has at least one shareable asset.
        if not shareable_assets(token.tenant_id):
            return Response({"items": []})
        return Response({"items": [{"name": SHARE_NAME}]})

    def get_share(self, request, share):
        token = request.auth
        self._audit_access(request, token)
        from hub.apps.databricks_admin.delta_sharing_service import SHARE_NAME

        if not self._scope_allows(token, SHARE_NAME, None, None) or share != SHARE_NAME:
            raise NotFound()
        return Response({"share": {"name": SHARE_NAME}})

    def list_schemas(self, request, share):
        token = request.auth
        self._audit_access(request, token)
        from hub.apps.databricks_admin.delta_sharing_service import (
            SHARE_NAME,
            schema_name_for,
            shareable_assets,
        )

        if not self._scope_allows(token, SHARE_NAME, None, None) or share != SHARE_NAME:
            raise NotFound()
        items = [
            {"name": schema_name_for(asset), "share": SHARE_NAME}
            for asset in shareable_assets(token.tenant_id)
            if self._scope_allows(token, SHARE_NAME, schema_name_for(asset), None)
        ]
        return Response({"items": items})

    def list_tables(self, request, share, schema):
        token = request.auth
        self._audit_access(request, token)
        from hub.apps.databricks_admin.delta_sharing_service import (
            SHARE_NAME,
            schema_name_for,
            shareable_assets,
            table_name_for,
        )

        if not self._scope_allows(token, SHARE_NAME, schema, None) or share != SHARE_NAME:
            raise NotFound()
        items = []
        for asset in shareable_assets(token.tenant_id):
            if schema_name_for(asset) != schema:
                continue
            items.append({"name": table_name_for(asset), "share": SHARE_NAME, "schema": schema})
        if not items:
            # A schema that matches NO shareable asset (opted out or
            # unknown) does not exist in the share — 404, never an empty
            # listing that leaks the schema name's existence.
            raise NotFound()
        return Response({"items": items})

    def get_table(self, request, share, schema, table):
        token = request.auth
        self._audit_access(request, token)
        self._resolve_asset(token, share, schema, table)
        from hub.apps.databricks_admin.delta_sharing_service import SHARE_NAME

        return Response({"table": {"name": table, "share": SHARE_NAME, "schema": schema}})

    # ── data actions ────────────────────────────────────────────────────

    def get_metadata(self, request, share, schema, table):
        token = request.auth
        self._audit_access(request, token)
        asset = self._resolve_asset(token, share, schema, table)
        from hub.apps.databricks_admin.delta_sharing_service import (
            build_metadata,
            latest_snapshot,
        )

        version = 0
        snapshot = latest_snapshot(token.tenant_id, share=share, schema=schema, table=table)
        if snapshot is not None:
            version = snapshot.version
        lines = [json.dumps({"protocol": {"minReaderVersion": 1}})]
        lines.append(json.dumps({"metaData": build_metadata(asset, table)}))
        return HttpResponse(
            "\n".join(lines) + "\n",
            content_type=_NDJSON,
            headers={"delta-table-version": str(version)},
        )

    def get_version(self, request, share, schema, table):
        token = request.auth
        self._audit_access(request, token)
        asset = self._resolve_asset(token, share, schema, table)
        from hub.apps.databricks_admin.delta_sharing_service import (
            build_file_action,
            build_metadata,
            latest_snapshot,
        )

        snapshot = latest_snapshot(token.tenant_id, share=share, schema=schema, table=table)
        if snapshot is None:
            raise NotFound()
        lines = [json.dumps({"protocol": {"minReaderVersion": 1}})]
        lines.append(json.dumps({"metaData": build_metadata(asset, table)}))
        for file in snapshot.files or []:
            lines.append(json.dumps({"file": build_file_action(file)}))
        return HttpResponse(
            "\n".join(lines) + "\n",
            content_type=_NDJSON,
            headers={"delta-table-version": str(snapshot.version)},
        )

    def query_table(self, request, share, schema, table):
        token = request.auth
        self._audit_access(request, token)
        asset = self._resolve_asset(token, share, schema, table)

        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        limit = body.get("limitHint", 100)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 100
        from hub.apps.databricks_admin.delta_sharing_service import (
            MAX_QUERY_LIMIT,
            build_metadata,
            query_share_table_json,
        )

        limit = max(1, min(limit, MAX_QUERY_LIMIT))
        connection = asset.warehouse_connection
        if connection is None:
            raise ValidationError(
                {"code": "DATABRICKS_DELTA_SHARE_QUERY_UNAVAILABLE"},
                code="query_unavailable",
            )
        try:
            result = query_share_table_json(
                connection=connection,
                table_name=table,
                limit=limit,
                tenant_id=str(token.tenant_id),
            )
        except ValueError as exc:
            # The unsafe/unknown table ref — refused before any query.
            raise ValidationError(
                {"code": "DATABRICKS_DELTA_SHARE_QUERY_UNAVAILABLE"},
                code="query_unavailable",
            ) from exc

        lines = [json.dumps({"protocol": {"minReaderVersion": 1}})]
        lines.append(json.dumps({"metaData": build_metadata(asset, table)}))
        lines.append(json.dumps({"query": {"count": result.row_count, "rows": result.rows}}))
        return HttpResponse(
            "\n".join(lines) + "\n",
            content_type=_NDJSON,
            headers={"delta-table-version": "0"},
        )

    # ── shared helpers ──────────────────────────────────────────────────

    def _resolve_asset(self, token, share, schema, table):
        """Scope + opt-out-aware resolution — anything outside the
        token's scope or opted out answers 404 (never a leak)."""
        if not self._scope_allows(token, share, schema, table):
            raise NotFound()
        from hub.apps.databricks_admin.delta_sharing_service import resolve_share_table

        asset = resolve_share_table(token.tenant_id, share=share, schema=schema, table=table)
        if asset is None:
            raise NotFound()
        return asset

    @staticmethod
    def _scope_allows(token, share, schema, table) -> bool:
        """The token's (share, schema, table) triple with NULL wildcards:
        a listing/direct fetch outside the scope is a 404."""
        if token.share_name != share:
            return False
        if schema is not None and token.schema_name is not None and token.schema_name != schema:
            return False
        return not (
            table is not None and token.table_name is not None and token.table_name != table
        )

    def _audit_access(self, request, token) -> None:
        """WAREHOUSE_SHARE_ACCESSED per request (IP + user-agent),
        best-effort — an audit outage never blocks the response (the
        Phase 273 contract)."""
        try:
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="ASSET",
                action=WAREHOUSE_SHARE_ACCESSED,
                tenant=token.tenant,
                resource_id=str(token.id),
                details={
                    "ip": request.META.get("REMOTE_ADDR", ""),
                    "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                    "path": request.path,
                },
            )
        except Exception:
            logger.warning(
                "delta_share_access_audit_failed",
                extra={"token_id": str(getattr(token, "id", ""))},
            )


def _emit_auth_failed(request) -> None:
    """WAREHOUSE_SHARE_AUTH_FAILED on the 401 path (the UC-DB-012
    contract), best-effort — an unresolvable token has no tenant, so the
    row carries none."""
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="ASSET",
            action=WAREHOUSE_SHARE_AUTH_FAILED,
            tenant=None,
            details={
                "ip": request.META.get("REMOTE_ADDR", ""),
                "path": request.path,
            },
        )
    except Exception:
        logger.warning("delta_share_auth_failed_audit_failed")
