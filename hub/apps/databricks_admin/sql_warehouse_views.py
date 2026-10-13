"""Phase 3 (openspec add-databricks-sql-warehouses task 3.7) — the SQL
warehouse lifecycle endpoints (the API surface the U5 lifecycle page and
the CLI consume).

- LIST — mirror-first (the 3.2 rows, ZERO network), workspace-scoped +
  tenant-scoped (RLS), paginated (the browse convention).
- START/STOP — drive the PRODUCTION 3.3 compute client under the D12
  INTERACTIVE identity (purpose ``warehouse_lifecycle``, OBO via the
  browse's provider builder, fail-closed without a binding — never a
  service-credential fallback on interactive paths). After the action
  the mirror refreshes through the 3.2 delta-diff (the U5 non-blocking
  semantics — the row reports STARTING/STOPPING as the compute API
  reports them, never an invented state).
- Errors — state refusals propagate the classified
  ``DATABRICKS_WAREHOUSE_STATE_ERROR`` (409, ZERO mutation calls);
  workspace rejections are MASKED (``DATABRICKS_AUTH_FAILED`` 502 —
  never the token or the raw exception); identity failures are
  classified like the browse.

Nested under the workspace registry; gated by the workspace-registry
flag + kill switch (the 0.12 ``_gate_control_plane``); throttled per
the Phase 273 contract (tenant-scoped scope).
"""

from __future__ import annotations

import contextlib
import logging

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.databricks_admin.client import (
    DatabricksApiError,
    DatabricksOBOError,
)
from hub.apps.databricks_admin.identity import HybridIdentityError, resolve_execution_identity
from hub.apps.databricks_admin.models import DatabricksSqlWarehouse, DatabricksWorkspace
from hub.apps.databricks_admin.sql_warehouse_client import (
    DatabricksComputeClient,
    DatabricksWarehouseStateError,
)
from hub.apps.databricks_admin.sql_warehouse_lifecycle import (
    start_sql_warehouse,
    stop_sql_warehouse,
)
from hub.apps.databricks_admin.uc_views import _build_uc_client, _build_uc_obo_provider
from hub.apps.databricks_admin.views import _gate_control_plane

logger = logging.getLogger(__name__)

_WAREHOUSE_FIELDS = (
    "warehouse_id",
    "name",
    "state",
    "serverless",
    "size",
    "auto_stop_mins",
    "synced_at",
)

# 3.7 review — the explicit action dispatch: an unknown action_name
# must NEVER silently map to a real action (a future delete endpoint
# routed through _run_action would otherwise stop the warehouse).
_WAREHOUSE_ACTION_SERVICES = {
    "start": start_sql_warehouse,
    "stop": stop_sql_warehouse,
}


def _to_dict(row: DatabricksSqlWarehouse) -> dict:
    return {field: getattr(row, field) for field in _WAREHOUSE_FIELDS}


class SqlWarehouseViewSet(viewsets.ViewSet):
    """SQL-warehouse lifecycle (authenticated users, flag-gated)."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "databricks_sql_warehouses"

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

    def _warehouse(
        self, workspace: DatabricksWorkspace, warehouse_id: str
    ) -> DatabricksSqlWarehouse:
        row = DatabricksSqlWarehouse.objects.filter(
            workspace=workspace, warehouse_id=warehouse_id
        ).first()
        if row is None:
            raise NotFound()
        return row

    # ── listings (mirror-first) ──────────────────────────────────────

    def list(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(
            DatabricksSqlWarehouse.objects.filter(workspace=workspace), request
        )
        return paginator.get_paginated_response(
            [_to_dict(row) for row in (page if page is not None else [])]
        )

    # ── lifecycle actions ────────────────────────────────────────────

    def _run_action(self, request, workspace_id, warehouse_id, action_name):
        """The shared start/stop spine: mirror row → D12 identity →
        real client action → mirror refresh → the row's NEW state."""
        workspace = self._workspace(request, workspace_id)
        warehouse = self._warehouse(workspace, warehouse_id)
        try:
            action_service = _WAREHOUSE_ACTION_SERVICES[action_name]
        except KeyError:
            # Fail loud at development time (the review pin) — before any
            # identity or network work.
            raise ValueError(f"unknown warehouse lifecycle action '{action_name}'") from None

        # D12 INTERACTIVE identity: OBO required; no binding → fail-closed.
        obo_provider = _build_uc_obo_provider(workspace, request.user)
        try:
            identity = resolve_execution_identity(
                purpose="warehouse_lifecycle",
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
        action_error: DatabricksApiError | None = None
        try:
            try:
                # 3.8 — the lifecycle chokepoint: the action runs through
                # the audit-emitting service (a performed action emits its
                # DATABRICKS_WAREHOUSE_* row; a no-op emits nothing; a
                # failure propagates with no fabricated row).
                action_service(
                    workspace,
                    warehouse_id,
                    client=DatabricksComputeClient(client),
                    actor_user=request.user,
                )
            except DatabricksApiError as exc:  # includes the StateError subclass
                action_error = exc
            if action_error is None:
                # The U5 non-blocking contract: after a SUCCESSFUL action
                # the mirror follows the compute API (delta-diff refresh),
                # while the client is still OPEN. The refresh is
                # BEST-EFFORT — a malformed follow-up LIST must never turn
                # a succeeded action into a 500 (the row keeps its
                # last-known state; the next refresh reconciles).
                try:
                    from hub.apps.databricks_admin.sql_warehouses import (
                        refresh_sql_warehouse_mirror,
                    )

                    refresh_sql_warehouse_mirror(workspace, client=client)
                except Exception:
                    logger.warning(
                        "databricks_sql_warehouse_refresh_failed",
                        extra={
                            "workspace_id": str(workspace.id),
                            "warehouse_id": warehouse_id,
                            "action": action_name,
                        },
                        exc_info=True,
                    )
        finally:
            client.close()

        if isinstance(action_error, DatabricksWarehouseStateError):
            return Response(
                {"code": action_error.code, "message": str(action_error)},
                status=status.HTTP_409_CONFLICT,
            )
        if action_error is not None:
            logger.warning(
                "databricks_sql_warehouse_action_failed",
                extra={
                    "workspace_id": str(workspace.id),
                    "warehouse_id": warehouse_id,
                    "action": action_name,
                    "error_code": action_error.code,
                },
            )
            return Response(
                {
                    "code": "DATABRICKS_AUTH_FAILED",
                    "message": f"Warehouse {action_name} failed",
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # The refresh may have removed the row (the compute API no longer
        # reports it — the 3.2 delta-diff contract). The action SUCCEEDED:
        # return the last-known state (the DB-005 freshness-marker
        # semantics), never a 500.
        with contextlib.suppress(DatabricksSqlWarehouse.DoesNotExist):
            warehouse.refresh_from_db()
        return Response(_to_dict(warehouse), status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="(?P<warehouse_id>[^/.]+)/start")
    def start(self, request, workspace_id, warehouse_id):
        return self._run_action(request, workspace_id, warehouse_id, "start")

    @action(detail=False, methods=["post"], url_path="(?P<warehouse_id>[^/.]+)/stop")
    def stop(self, request, workspace_id, warehouse_id):
        return self._run_action(request, workspace_id, warehouse_id, "stop")
