"""P0 (openspec add-databricks-control-plane task 0.8) — Workspace ViewSet.

Tenant-scoped CRUD (TENANT_ADMIN) with:

- connection test (``POST {id}/test/``) — probes the workspace through the
  REAL ``DatabricksApiClient`` in workspace mode (dispatch-time DNS
  re-validation + breaker); failures are ALWAYS masked (never echo the
  exception or any credential material); success drives
  ``transition_to(ACTIVE)``.
- delete → 409 ``DATABRICKS_WORKSPACE_HAS_DEPENDENTS`` with dependent ids
  when children exist; otherwise a soft-disable (``transition_to(DISABLED)``
  per the workspace-registry spec — the row is kept for audit).
"""

from __future__ import annotations

import logging
import time
from typing import ClassVar

from django.db import IntegrityError
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from hub.apps.auth.permissions import HasRole
from hub.apps.databricks_admin.client import DatabricksApiClient, DatabricksApiError
from hub.apps.databricks_admin.models import (
    DatabricksCredentialAuthMode,
    DatabricksWorkspace,
    DatabricksWorkspaceStatus,
)
from hub.apps.databricks_admin.serializers import (
    CredentialSerializer,
    RotateCredentialSerializer,
    WorkspaceSerializer,
)

logger = logging.getLogger(__name__)

_MASKED_PROBE_FAILURE = {
    "code": "DATABRICKS_AUTH_FAILED",
    "message": "Credentials rejected by workspace",
}


class _ControlPlaneDisabled(APIException):
    """Feature flag off — 403 DATABRICKS_CONTROL_PLANE_DISABLED."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "DATABRICKS_CONTROL_PLANE_DISABLED"
    default_detail: ClassVar[dict[str, str]] = {
        "code": "DATABRICKS_CONTROL_PLANE_DISABLED",
        "message": "The Databricks control plane is not enabled for this tenant",
    }


def _gate_control_plane(view) -> None:
    """P0 (task 0.12) — flag gate + emergency kill switch, run from initial()."""
    request = view.request
    tenant = getattr(request, "tenant", None)
    if tenant is None and hasattr(request, "user") and hasattr(request.user, "tenant"):
        tenant = request.user.tenant
    # Kill switch FIRST — an emergency kill must win even when the flag is off.
    from hub.apps.tenants.kill_switch_gates import ensure_tenant_databricks_workspaces_allowed

    ensure_tenant_databricks_workspaces_allowed(request)
    if tenant is not None and not getattr(tenant, "databricks_control_plane_enabled", False):
        raise _ControlPlaneDisabled()


class _WorkspaceNameConflict(APIException):
    """(tenant, name) uniqueness — clean 400, never a raw IntegrityError."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail: ClassVar[dict[str, str]] = {
        "code": "DATABRICKS_WORKSPACE_NAME_CONFLICT",
        "message": "A workspace with this name already exists for this tenant",
    }


def _emit_audit(
    workspace: DatabricksWorkspace,
    action: str,
    result: str = "SUCCESS",
    details: dict | None = None,
    resource_type: str = "DATABRICKS_WORKSPACE",
) -> None:
    """Best-effort audit emission — an audit-DB outage never blocks the API."""
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type=resource_type,
            action=action,
            tenant=workspace.tenant,
            resource_id=str(workspace.id),
            result=result,
            details=details or {},
        )
    except Exception:
        logger.warning("databricks_workspace_audit_failed", extra={"action": action})


def _build_probe_client(workspace: DatabricksWorkspace, credential) -> DatabricksApiClient:
    """Build the REAL probe client in workspace mode.

    Workspace mode runs ``validate_for_dispatch()`` (0.4 rebinding guard)
    before every request. Tests redirect this factory to a local transport —
    the client itself is the production client.
    """
    return DatabricksApiClient(
        workspace=workspace,
        tenant_id=str(workspace.tenant_id),
        credential_config=credential.get_config(),
        auth_mode=credential.auth_mode,
    )


def _parse_create_pat_payload(payload) -> tuple[str, str]:
    """Extract (token_value, token_id) from a token-management 2xx body.

    Raises outside the rotation try-block (TRY301): a malformed body is a
    classified control-flow signal, not a transport error — the rotation
    view catches it and returns the masked 502.
    """
    if not isinstance(payload, dict):
        raise TypeError("token-management response is not a JSON object")
    new_token = payload.get("token_value", "")
    token_info = payload.get("token_info") or {}
    new_token_id = token_info.get("token_id", "") if isinstance(token_info, dict) else ""
    if not new_token:
        raise ValueError("token-management response carried no token_value")
    return new_token, new_token_id


def _cleanup_orphan_token(client: DatabricksApiClient, token_id: str) -> None:
    """Best-effort deletion of a JUST-CREATED replacement PAT.

    When rotation fails AFTER the token-management create succeeded (the
    delete-old call failed, the response could not be parsed, or the local
    persist failed), the replacement token would otherwise stay alive at
    Databricks while being recorded nowhere — an unrecorded VALID
    credential. The cleanup uses the old credential's bearer, which is
    still valid when the failure happened downstream of the create.
    """
    if not token_id:
        return
    try:
        client.request("DELETE", "token_management.delete", path_params={"token_id": token_id})
    except Exception as exc:
        logger.warning(
            "databricks_credential_orphan_cleanup_failed",
            extra={"token_id": token_id, "error_type": type(exc).__name__},
        )


class WorkspaceViewSet(viewsets.ModelViewSet):
    """Tenant-scoped Databricks workspace registry (TENANT_ADMIN)."""

    queryset = DatabricksWorkspace.objects.all()
    serializer_class = WorkspaceSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "databricks_workspaces"
    lookup_field = "id"
    http_method_names = ("get", "post", "patch", "delete", "head", "options")

    def get_permissions(self):
        # HasRole takes its argument at construction — pre-instantiated
        # entries in ``permission_classes`` break DRF's re-invocation
        # (see the HasRole docstring).
        return [permissions.IsAuthenticated(), HasRole("TENANT_ADMIN")]

    def initial(self, request, *args, **kwargs):
        _gate_control_plane(self)
        return super().initial(request, *args, **kwargs)

    def _request_tenant(self):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            user = self.request.user
            if hasattr(user, "tenant"):
                tenant = user.tenant
        return tenant

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "is_platform_admin", False):
            return DatabricksWorkspace.objects.all()
        tenant = self._request_tenant()
        if tenant is None:
            return DatabricksWorkspace.objects.none()
        return DatabricksWorkspace.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        tenant = self._request_tenant()
        name = serializer.validated_data.get("name")
        if DatabricksWorkspace.objects.filter(tenant=tenant, name=name).exists():
            raise _WorkspaceNameConflict()
        try:
            workspace = serializer.save(tenant=tenant)
        except IntegrityError as exc:
            # Belt-and-braces: a concurrent create racing the pre-check.
            raise _WorkspaceNameConflict() from exc
        _emit_audit(workspace, "REGISTERED")

    def perform_update(self, serializer):
        workspace = serializer.save()
        _emit_audit(workspace, "UPDATED")

    def destroy(self, _request, *_args, **_kwargs):
        workspace = self.get_object()

        dependent_ids = list(workspace.credentials.values_list("id", flat=True))
        if dependent_ids:
            return Response(
                {
                    "code": "DATABRICKS_WORKSPACE_HAS_DEPENDENTS",
                    "dependent_object_ids": [str(dep) for dep in dependent_ids],
                    "message": (
                        f"Cannot delete workspace '{workspace.name}': "
                        f"{len(dependent_ids)} credential(s) still reference it."
                    ),
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Soft-delete per spec: keep the row, mark it DISABLED (terminal).
        workspace.transition_to(DatabricksWorkspaceStatus.DISABLED)
        workspace.save(update_fields=["status", "updated_at"])
        _emit_audit(workspace, "DELETED", details={"soft_delete": True})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="test")
    def test(self, _request, **_kwargs):
        workspace = self.get_object()
        credential = workspace.credentials.order_by("-created_at").first()
        if credential is None:
            _emit_audit(
                workspace, "TEST_FAILED", result="FAILURE", details={"reason": "no_credential"}
            )
            return Response(_MASKED_PROBE_FAILURE, status=status.HTTP_502_BAD_GATEWAY)

        started = time.monotonic()
        try:
            client = _build_probe_client(workspace, credential)
            try:
                client.test_connection()
            finally:
                client.close()
        except DatabricksApiError as exc:
            # Log the failure CLASS + status only — never the message,
            # which may embed host/credential context.
            logger.warning(
                "databricks_workspace_probe_failed",
                extra={"workspace_id": str(workspace.id), "error_code": exc.code},
            )
            _emit_audit(
                workspace, "TEST_FAILED", result="FAILURE", details={"error_code": exc.code}
            )
            return Response(_MASKED_PROBE_FAILURE, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            logger.warning(
                "databricks_workspace_probe_failed",
                extra={"workspace_id": str(workspace.id), "error_type": type(exc).__name__},
            )
            _emit_audit(
                workspace,
                "TEST_FAILED",
                result="FAILURE",
                details={"error_type": type(exc).__name__},
            )
            return Response(_MASKED_PROBE_FAILURE, status=status.HTTP_502_BAD_GATEWAY)

        latency_ms = round((time.monotonic() - started) * 1000, 1)
        workspace.transition_to(DatabricksWorkspaceStatus.ACTIVE)
        workspace.save(update_fields=["status", "updated_at"])
        _emit_audit(workspace, "TEST_PASSED", details={"latency_ms": latency_ms})
        return Response({"status": "ok", "latency_ms": latency_ms})


class CredentialViewSet(viewsets.ViewSet):
    """Nested credential endpoints under a workspace (TENANT_ADMIN).

    create  — encrypts via the model's real encryption chain; the response
              never carries ``config``.
    rotate  — PAT: creates a replacement via the Databricks token-management
              on-behalf-of API, deletes the PREVIOUS token when its id is
              known (stored from the prior rotation — an externally created
              PAT's id is unknowable, documented limitation), rewrites the
              ciphertext, stamps ``last_rotated_at``, and audits. M2M:
              rewrites the stored secret from the payload — no API call
              (Databricks has no M2M secret-rotation endpoint; the operator
              re-issues in the console). Failure is atomic — the stored
              config is untouched.
    """

    # NOTE: no ``permission_classes`` attribute — get_permissions() is the
    # single source of truth (pre-instantiated HasRole entries break DRF's
    # re-invocation; see the HasRole docstring).
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "databricks_credentials"

    def get_permissions(self):
        return [permissions.IsAuthenticated(), HasRole("TENANT_ADMIN")]

    def initial(self, request, *args, **kwargs):
        _gate_control_plane(self)
        return super().initial(request, *args, **kwargs)

    def _workspace(self, request, workspace_id):
        user = request.user
        if getattr(user, "is_platform_admin", False):
            queryset = DatabricksWorkspace.objects.all()
        else:
            tenant = getattr(request, "tenant", None)
            if tenant is None and hasattr(user, "tenant"):
                tenant = user.tenant
            if tenant is None:
                return None
            queryset = DatabricksWorkspace.objects.filter(tenant=tenant)
        return queryset.filter(id=workspace_id).first()

    def list(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        if workspace is None:
            raise NotFound()
        serializer = CredentialSerializer(workspace.credentials.all(), many=True)
        return Response(serializer.data)

    def create(self, request, workspace_id):
        workspace = self._workspace(request, workspace_id)
        if workspace is None:
            raise NotFound()
        serializer = CredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.save(workspace=workspace)
        _emit_audit(
            workspace,
            "STORED",
            details={"auth_mode": credential.auth_mode},
            resource_type="DATABRICKS_CREDENTIAL",
        )
        return Response(CredentialSerializer(credential).data, status=status.HTTP_201_CREATED)

    def rotate(self, request, workspace_id, pk):
        workspace = self._workspace(request, workspace_id)
        if workspace is None:
            raise NotFound()
        credential = workspace.credentials.filter(id=pk).first()
        if credential is None:
            raise NotFound()

        payload = RotateCredentialSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        if credential.auth_mode == DatabricksCredentialAuthMode.PAT:
            return self._rotate_pat(workspace, credential)

        new_secret = payload.validated_data.get("client_secret")
        if not new_secret:
            return Response(
                {
                    "code": "DATABRICKS_CLIENT_SECRET_REQUIRED",
                    "message": "client_secret is required for M2M re-issue",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        new_config = {**credential.get_config(), "client_secret": new_secret}
        credential.set_config(new_config)
        credential.last_rotated_at = timezone.now()
        credential.save(update_fields=["config", "last_rotated_at", "updated_at"])
        _emit_audit(
            workspace,
            "ROTATED",
            details={"auth_mode": credential.auth_mode},
            resource_type="DATABRICKS_CREDENTIAL",
        )
        return Response(CredentialSerializer(credential).data)

    def _rotate_pat(self, workspace, credential):
        """PAT rotation — on-behalf-of create, then delete-old.

        The persist happens INSIDE the guarded block: any failure after the
        remote create (delete-old failure, unparseable response, local
        persist failure) triggers a best-effort cleanup of the replacement
        token so no live, unrecorded PAT is left behind at Databricks.
        """
        client = _build_probe_client(workspace, credential)
        new_token_id = ""
        try:
            response = client.request(
                "POST",
                "token_management.create_pat",
                json={
                    "comment": f"meshant rotation {credential.id}",
                    "lifetime_seconds": 7776000,
                },
            )
            token_payload = response.json()
            new_token, new_token_id = _parse_create_pat_payload(token_payload)
            old_token_id = credential.get_config().get("token_id")
            if old_token_id:
                client.request(
                    "DELETE",
                    "token_management.delete",
                    path_params={"token_id": old_token_id},
                )
            new_config = {**credential.get_config(), "token": new_token, "token_id": new_token_id}
            credential.set_config(new_config)
            credential.last_rotated_at = timezone.now()
            credential.save(update_fields=["config", "last_rotated_at", "updated_at"])
        except DatabricksApiError as exc:
            _cleanup_orphan_token(client, new_token_id)
            logger.warning(
                "databricks_credential_rotate_failed",
                extra={"credential_id": str(credential.id), "error_code": exc.code},
            )
            _emit_audit(
                workspace,
                "ROTATED",
                result="FAILURE",
                details={"error_code": exc.code},
                resource_type="DATABRICKS_CREDENTIAL",
            )
            return Response(_MASKED_PROBE_FAILURE, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as exc:
            _cleanup_orphan_token(client, new_token_id)
            logger.warning(
                "databricks_credential_rotate_failed",
                extra={"credential_id": str(credential.id), "error_type": type(exc).__name__},
            )
            _emit_audit(
                workspace,
                "ROTATED",
                result="FAILURE",
                details={"error_type": type(exc).__name__},
                resource_type="DATABRICKS_CREDENTIAL",
            )
            return Response(_MASKED_PROBE_FAILURE, status=status.HTTP_502_BAD_GATEWAY)
        finally:
            client.close()

        _emit_audit(
            workspace,
            "ROTATED",
            details={"auth_mode": credential.auth_mode},
            resource_type="DATABRICKS_CREDENTIAL",
        )
        return Response(CredentialSerializer(credential).data)
