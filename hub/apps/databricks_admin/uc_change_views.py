"""U4 approval UX endpoints (openspec add-databricks-uc-write task 2.8).

The change-request API surface nested under the workspace registry
(`/api/v1/databricks/workspaces/{id}/uc/changes/`) plus the
cross-workspace approver inbox. The endpoints are THIN: validation and
state transitions delegate to the 2.2 lifecycle service functions
(`uc_changes`) and the 2.4 guards — the views never mutate rows
directly. The DDL preview and the timeline come from `uc_change_ux`.

Gated by the control-plane flag + kill switch (the 0.12 gate) and
throttled per the Phase 273 contract.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.viewsets import ViewSet

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.databricks_admin.models import (
    UCChangeAction,
    UCChangeRequest,
    UCObjectType,
)
from hub.apps.databricks_admin.uc_change_ux import (
    add_comment,
    approval_inbox,
    preview_change,
    timeline_for,
)
from hub.apps.databricks_admin.views import _gate_control_plane

_SERIALIZED_FIELDS = (
    "id",
    "change_type",
    "securable_type",
    "full_name",
    "status",
    "reason",
    "requires_approval",
    "created_at",
    "execution_error",
    "rejection_reason",
)


def _serialize(request: UCChangeRequest, *, with_preview: bool = False) -> dict:
    payload = {field: getattr(request, field) for field in _SERIALIZED_FIELDS}
    payload["workspace_id"] = str(request.workspace_id)
    if with_preview:
        payload["preview"] = preview_change(request)
    return payload


def _request_for(request, workspace_id, pk) -> UCChangeRequest:
    row = (
        UCChangeRequest.objects.filter(
            tenant=getattr(request, "tenant", None) or request.user.tenant,
            workspace_id=workspace_id,
            id=pk,
        )
        .select_related("workspace")
        .first()
    )
    if row is None:
        raise NotFound()
    return row


class UCChangeRequestViewSet(ViewSet):
    """Nested change-request endpoints (flag-gated, throttled)."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "databricks_uc_changes"

    def get_permissions(self):
        return [IsAuthenticated()]

    def initial(self, request, *args, **kwargs):
        _gate_control_plane(self)
        return super().initial(request, *args, **kwargs)

    # ── list / create ──────────────────────────────────────────────

    def list(self, request, workspace_id):
        from hub.apps.databricks_admin.models import DatabricksWorkspace

        workspace = DatabricksWorkspace.objects.filter(
            tenant=request.user.tenant, id=workspace_id
        ).first()
        if workspace is None:
            raise NotFound()
        queryset = UCChangeRequest.objects.filter(workspace=workspace).order_by("-created_at")
        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            [_serialize(row, with_preview=True) for row in page]
        )

    def create(self, request, workspace_id):
        from hub.apps.databricks_admin.models import DatabricksWorkspace
        from hub.apps.databricks_admin.uc_change_executor import UCDdlPayload
        from hub.apps.databricks_admin.uc_change_guards import (
            UCDdlSafetyError,
            coerce_payload,
            validate_uc_identifiers,
        )
        from hub.apps.databricks_admin.uc_changes import create_change_request

        workspace = DatabricksWorkspace.objects.filter(
            tenant=request.user.tenant, id=workspace_id
        ).first()
        if workspace is None:
            raise NotFound()

        definition = request.data.get("definition") or {}
        change_type = request.data.get("change_type")
        securable_type = request.data.get("securable_type")
        if not change_type or not securable_type:
            return Response(
                {"detail": "change_type and securable_type are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            # The 2.4 guards run at the boundary: the denylist refuses a
            # destructive request on a flag-off tenant, the identifier
            # regex rejects malformed identifiers — both ZERO network.
            payload = coerce_payload(
                UCDdlPayload(
                    object_type=securable_type,
                    action=change_type,
                    identifiers=tuple(definition.get("identifiers") or ()),
                    options=definition.get("options") or {},
                )
            )
            from hub.apps.databricks_admin.uc_change_guards import assert_not_denylisted

            assert_not_denylisted(payload, tenant=request.user.tenant)
            validate_uc_identifiers(payload)
        except UCDdlSafetyError as exc:
            # The classified envelope (the browse's masked-failure shape).
            http_status = (
                status.HTTP_403_FORBIDDEN
                if exc.code == "DATABRICKS_DDL_DENYLISTED"
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({"code": exc.code, "message": str(exc)}, status=http_status)

        change_request = create_change_request(
            tenant=request.user.tenant,
            workspace=workspace,
            requested_by=request.user,
            change_type=UCChangeAction(change_type),
            securable_type=UCObjectType(securable_type),
            full_name=".".join(definition.get("identifiers") or []),
            definition=definition,
            reason=request.data.get("reason", ""),
            required_approval_chain=request.data.get("required_approval_chain"),
            requires_approval=request.data.get("requires_approval", True),
        )
        return Response(_serialize(change_request, with_preview=True), status=201)

    # ── detail + lifecycle actions ─────────────────────────────────

    def retrieve(self, request, workspace_id, pk):
        return Response(_serialize(_request_for(request, workspace_id, pk), with_preview=True))

    def _action(self, request, workspace_id, pk, name):
        from hub.apps.core.services.base import ValidationError as CoreValidationError
        from hub.apps.databricks_admin import uc_changes

        change_request = _request_for(request, workspace_id, pk)
        try:
            if name == "submit":
                result = uc_changes.submit_change_request(change_request=change_request)
            elif name == "approve":
                result = uc_changes.approve_change_request(
                    change_request=change_request, approver=request.user
                )
            else:
                reason = (request.data or {}).get("reason")
                result = uc_changes.reject_change_request(
                    change_request=change_request, approver=request.user, reason=reason
                )
        except (ValidationError, CoreValidationError) as exc:
            # The lifecycle raises the repo's CORE ValidationError (not
            # DRF's) — both must surface as clean 400s, never a 500.
            detail = getattr(exc, "detail", None)
            if isinstance(detail, str):
                message = detail
            elif detail:
                message = str(detail)
            else:
                message = str(exc)
            return Response({"detail": message}, status=400)
        return Response(_serialize(result, with_preview=True))

    def submit(self, request, workspace_id, pk):
        return self._action(request, workspace_id, pk, "submit")

    def approve(self, request, workspace_id, pk):
        return self._action(request, workspace_id, pk, "approve")

    def reject(self, request, workspace_id, pk):
        return self._action(request, workspace_id, pk, "reject")

    # ── timeline + comments ────────────────────────────────────────

    def timeline(self, request, workspace_id, pk):
        change_request = _request_for(request, workspace_id, pk)
        return Response(timeline_for(change_request))

    def comments(self, request, workspace_id, pk):
        change_request = _request_for(request, workspace_id, pk)
        if request.method == "POST":
            body = (request.data or {}).get("body")
            try:
                comment = add_comment(change_request, request.user, body or "")
            except ValidationError as exc:
                return Response({"detail": str(exc)}, status=400)
            return Response(
                {
                    "id": str(comment.id),
                    "body": comment.body,
                    "author": getattr(comment.author, "email", None),
                    "created_at": comment.created_at.isoformat(),
                },
                status=201,
            )
        return Response(
            [
                {
                    "id": str(comment.id),
                    "body": comment.body,
                    "author": getattr(comment.author, "email", None),
                    "created_at": comment.created_at.isoformat(),
                }
                for comment in change_request.comments.select_related("author").all()
            ]
        )


class UCApprovalInboxViewSet(ViewSet):
    """The cross-workspace approver inbox (flag-gated, throttled)."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "databricks_uc_changes"

    def get_permissions(self):
        return [IsAuthenticated()]

    def initial(self, request, *args, **kwargs):
        _gate_control_plane(self)
        return super().initial(request, *args, **kwargs)

    def list(self, request):
        queryset = approval_inbox(request.user)
        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        return paginator.get_paginated_response(
            [_serialize(row, with_preview=True) for row in page]
        )
