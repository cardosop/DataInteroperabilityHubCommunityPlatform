"""DLT pipeline management views (openspec add-databricks-dlt-pipelines
task 10.7) — the SAME API surface the DLT page (U5) and the `dlt` CLI
ride (design D7).

- **list** — the 10.2 mirror rows with each pipeline's latest update
  state (mirror-first: ZERO network reads).
- **create** — the REGISTERED `databricks.dlt.create` chain (the 10.4
  registry: TenantScoping → SettingsAllowlist → ClusterPolicy →
  Channel) inside `transaction.atomic()` (the Phase 274 contract); a
  refusal surfaces the chain's classified code with ZERO pipelines API
  calls; a PASS ships the settings EXACTLY through the 10.3 client,
  emits `DATABRICKS_DLT_PIPELINE_CREATED` (the 10.8 chokepoint), and
  returns the pipeline id (the mirror reflects it on the next sync).
- **update** — the SAME chain-gated edit (the D3 contract); a PASS
  ships the new settings through the 10.3 client and emits
  `DATABRICKS_DLT_PIPELINE_UPDATED`.
- **destroy** — the client's delete + `DATABRICKS_DLT_PIPELINE_DELETED`
  (the mirror reconciles on the next sync).
- **start** — the conflict gate fail-fast: a non-terminal update on the
  mirror → HTTP 409 `DATABRICKS_DLT_UPDATE_CONFLICT` with ZERO API
  calls (the D4 discipline, wired ahead of the 10.8 registration); else
  the refresh semantics (`full_refresh` / `refresh_selection` —
  the API's documented `{tables, files}` object) ship VERBATIM through
  the 10.3 client, `DATABRICKS_DLT_UPDATE_STARTED` emits, and the
  update id is returned.
- **stop** — a no-op with ZERO API calls when the mirror reports IDLE
  (the D4 discipline); else the stop endpoint.

Both surfaces sit behind the 0.12 flag gate
`databricks_dlt_pipelines_enabled` (design D7) on top of the master
control-plane gate + kill switch (`_gate_control_plane`). The client
factory seam (`_build_dlt_client`) is the 0.8 `_build_probe_client`
convention — tests redirect it to a local transport, the client itself
is the production client.
"""

from __future__ import annotations

from typing import ClassVar

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.databricks_admin.models import (
    DatabricksDltPipeline,
    DatabricksDltPipelineState,
    DatabricksDltPipelineUpdate,
    DatabricksDltPipelineUpdateState,
    DatabricksWorkspace,
)
from hub.apps.databricks_admin.views import _gate_control_plane

# The terminal quartet — a non-terminal update blocks a second start.
_NON_TERMINAL_UPDATE_STATES = set(DatabricksDltPipelineUpdateState.values) - {
    "COMPLETED",
    "FAILED",
    "CANCELED",
    "TIMED_OUT",
}


class _DltPipelinesDisabled(APIException):
    """The D7 surface gate — the flag is off for this tenant."""

    status_code = status.HTTP_403_FORBIDDEN
    code: ClassVar[str] = "DATABRICKS_DLT_PIPELINES_DISABLED"
    default_detail: ClassVar[dict[str, str]] = {
        "code": "DATABRICKS_DLT_PIPELINES_DISABLED",
        "message": "The DLT pipeline management surface is disabled for this tenant",
    }


class _DltUpdateConflict(APIException):
    """An update is already active — the fail-fast conflict gate (the
    D4 discipline; the 10.8 error-code registration rides this class)."""

    status_code = status.HTTP_409_CONFLICT
    code: ClassVar[str] = "DATABRICKS_DLT_UPDATE_CONFLICT"
    default_detail: ClassVar[dict[str, str]] = {
        "code": "DATABRICKS_DLT_UPDATE_CONFLICT",
        "message": "An update is already active for this pipeline",
    }


class _DltChainRefused(APIException):
    """The `databricks.dlt.create` chain refused the settings — the
    chain's classified code rides through (never a raw 500)."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(detail={"code": code, "message": message})


def _gate_dlt_pipelines(view) -> None:
    request = view.request
    tenant = getattr(request, "tenant", None)
    if tenant is None and hasattr(request, "user") and hasattr(request.user, "tenant"):
        tenant = request.user.tenant
    if tenant is not None and not getattr(tenant, "databricks_dlt_pipelines_enabled", False):
        raise _DltPipelinesDisabled()


def _build_dlt_client(workspace: DatabricksWorkspace, credential=None):
    """The REAL pipelines client in workspace mode (the 0.8
    `_build_probe_client` convention). Tests redirect this factory to a
    local transport — the client itself is the production client.

    A workspace with NO stored credential passes through with no auth
    kwargs (the 1.3 UC convention) — the workspace's own 401 surfaces
    as the classified `DATABRICKS_AUTH_FAILED`, never a misclassified
    flag-gate 403."""
    from hub.apps.databricks_admin.client import DatabricksApiClient
    from hub.apps.databricks_admin.pipelines_client import DatabricksPipelinesClient

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
    return DatabricksPipelinesClient(
        DatabricksApiClient(
            workspace=workspace,
            tenant_id=str(workspace.tenant_id),
            **kwargs,
        )
    )


def _pipeline_to_dict(row: DatabricksDltPipeline) -> dict:
    latest = (
        DatabricksDltPipelineUpdate.objects.filter(pipeline=row)
        .order_by("-synced_at", "-update_id")
        .first()
    )
    return {
        "id": str(row.id),
        "pipeline_id": row.pipeline_id,
        "name": row.name,
        "state": row.state,
        "channel": row.channel,
        "settings": row.settings,
        "synced_at": row.synced_at.isoformat(),
        "latest_update_id": latest.update_id if latest else None,
        "latest_update_state": latest.state if latest else None,
    }


class DatabricksDltPipelineViewSet(viewsets.ViewSet):
    """DLT pipeline management (authenticated users, flag-gated)."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "databricks_dlt"

    def get_permissions(self):
        return [IsAuthenticated()]

    def initial(self, request, *args, **kwargs):
        _gate_control_plane(self)
        _gate_dlt_pipelines(self)
        return super().initial(request, *args, **kwargs)

    def _workspace(self, request, workspace_id) -> DatabricksWorkspace:
        workspace = DatabricksWorkspace.objects.filter(
            tenant=getattr(request, "tenant", None) or getattr(request.user, "tenant", None),
            id=workspace_id,
        ).first()
        if workspace is None:
            raise NotFound()
        return workspace

    def _pipeline(self, workspace: DatabricksWorkspace, pipeline_id: str) -> DatabricksDltPipeline:
        row = DatabricksDltPipeline.objects.filter(
            workspace=workspace, pipeline_id=pipeline_id
        ).first()
        if row is None:
            raise NotFound()
        return row

    # ── list (mirror-first) ────────────────────────────────────────────

    def list(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(
            DatabricksDltPipeline.objects.filter(workspace=workspace), request
        )
        return paginator.get_paginated_response(
            [_pipeline_to_dict(row) for row in (page if page is not None else [])]
        )

    # ── create (chain-gated) ───────────────────────────────────────────

    def _chain_or_refuse(self, request, workspace, settings) -> None:
        """The ONE chain invocation (create + update share it) — a
        refusal surfaces the chain's classified code with ZERO
        pipelines API calls."""
        from hub.apps.core.business_rules.chains import execute_chain

        if not isinstance(settings, dict):
            raise _DltChainRefused("DATABRICKS_DLT_INVALID_CONFIG", "the payload must be an object")
        tenant = getattr(request, "tenant", None) or getattr(request.user, "tenant", None)
        # The Phase 274 contract: the chain runner requires an active
        # transaction.
        with transaction.atomic():
            result = execute_chain(
                "databricks.dlt.create",
                tenant_id=str(tenant.id) if tenant else None,
                user_id=str(request.user.id),
                tenant=tenant,
                workspace=workspace,
                payload=settings,
            )
        if result.get("outcome") != "PASS":
            errors = result.get("errors") or []
            message = errors[0] if errors else "the DLT create chain refused the settings"
            code = "DATABRICKS_DLT_SETTING_FORBIDDEN"
            # The chain's step refusals carry their code in the error
            # string (the `_fail(code, message)` convention) — surface
            # the first code when it is one of the chain's own.
            for known in (
                "DATABRICKS_DLT_INVALID_CONFIG",
                "DATABRICKS_DLT_SETTING_FORBIDDEN",
                "DATABRICKS_DLT_CLUSTER_POLICY_REQUIRED",
                "DATABRICKS_DLT_CHANNEL_INVALID",
            ):
                if message.startswith(known) or known in message:
                    code = known
                    break
            raise _DltChainRefused(code, message)

    def create(self, request, workspace_id):
        from hub.apps.databricks_admin.dlt_lifecycle import emit_dlt_pipeline_audit

        workspace = self._workspace(request, workspace_id)
        settings = request.data
        self._chain_or_refuse(request, workspace, settings)
        client = _build_dlt_client(workspace)
        pipeline_id = client.create_pipeline(settings)
        emit_dlt_pipeline_audit(
            "DATABRICKS_DLT_PIPELINE_CREATED",
            workspace,
            pipeline_id,
            actor_user=request.user,
        )
        return Response({"pipeline_id": pipeline_id}, status=status.HTTP_201_CREATED)

    # ── update (the same chain-gated edit, the D3 contract) ────────────

    def update(self, request, workspace_id, pipeline_id):
        from hub.apps.databricks_admin.dlt_lifecycle import emit_dlt_pipeline_audit

        workspace = self._workspace(request, workspace_id)
        self._pipeline(workspace, pipeline_id)  # 404 on an unknown id
        settings = request.data
        self._chain_or_refuse(request, workspace, settings)
        client = _build_dlt_client(workspace)
        client.update_pipeline(pipeline_id, settings)
        emit_dlt_pipeline_audit(
            "DATABRICKS_DLT_PIPELINE_UPDATED",
            workspace,
            pipeline_id,
            actor_user=request.user,
        )
        return Response({"pipeline_id": pipeline_id})

    # ── destroy ────────────────────────────────────────────────────────

    def destroy(self, request, workspace_id, pipeline_id):
        from hub.apps.databricks_admin.dlt_lifecycle import emit_dlt_pipeline_audit

        workspace = self._workspace(request, workspace_id)
        self._pipeline(workspace, pipeline_id)  # 404 on an unknown id
        client = _build_dlt_client(workspace)
        client.delete_pipeline(pipeline_id)
        emit_dlt_pipeline_audit(
            "DATABRICKS_DLT_PIPELINE_DELETED",
            workspace,
            pipeline_id,
            actor_user=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── start (conflict gate + verbatim refresh semantics) ─────────────

    def start(self, request, workspace_id, pipeline_id):
        from hub.apps.databricks_admin.dlt_lifecycle import emit_dlt_update_started

        workspace = self._workspace(request, workspace_id)
        pipeline = self._pipeline(workspace, pipeline_id)
        active = (
            DatabricksDltPipelineUpdate.objects.filter(
                pipeline=pipeline, state__in=sorted(_NON_TERMINAL_UPDATE_STATES)
            )
            .order_by("-synced_at")
            .first()
        )
        if active is not None:
            raise _DltUpdateConflict()
        full_refresh = request.data.get("full_refresh", False)
        if not isinstance(full_refresh, bool):
            full_refresh = False
        refresh_selection = request.data.get("refresh_selection")
        client = _build_dlt_client(workspace)
        update_id = client.start_update(
            pipeline.pipeline_id,
            full_refresh=full_refresh,
            refresh_selection=refresh_selection,
        )
        emit_dlt_update_started(workspace, pipeline, update_id, actor_user=request.user)
        return Response({"update_id": update_id}, status=status.HTTP_202_ACCEPTED)

    # ── stop (IDLE no-op) ──────────────────────────────────────────────

    def stop(self, request, workspace_id, pipeline_id):
        workspace = self._workspace(request, workspace_id)
        pipeline = self._pipeline(workspace, pipeline_id)
        if pipeline.state == DatabricksDltPipelineState.IDLE:
            return Response({"stopped": False, "reason": "idle"})
        client = _build_dlt_client(workspace)
        client.stop_pipeline(pipeline.pipeline_id)
        return Response({"stopped": True})
