"""Databricks SSO API surface (openspec add-databricks-control-plane
task 0b.12 — the backend the login button / chooser / countdown consume).

- ``GET /workspaces/`` — the sign-in chooser: the tenant's ACTIVE
  non-GCP workspaces.
- ``GET /login-url/`` — the authorize URL (PKCE S256 + signed state)
  for a chosen workspace; GCP → 400 ``DATABRICKS_SSO_UNAVAILABLE``.
- ``POST /callback/`` — state consumed BEFORE the exchange; id_token
  claims provision the Hub user + binding; tokens land in the vault;
  a Hub JWT is issued.
- ``GET /session/`` — the countdown state + hub re-auth deadline for
  the authenticated user's bindings (the countdown banner's source).

The endpoints are AllowAny where the flow is pre-login (workspaces /
login-url / callback resolve the tenant from the signed state / query
param, matching the existing SSOViewSet convention) and gated by the
0b.10 flags + kill switches on the RESOLVED tenant.
"""

from __future__ import annotations

import logging

import jwt
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from hub.apps.auth import sso_state
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.databricks_admin.bindings import (
    DatabricksBindingConflict,
    provision_binding,
    sso_workspace_options,
)
from hub.apps.databricks_admin.models import DatabricksWorkspace
from hub.apps.databricks_admin.obo_tokens import store_tokens
from hub.apps.databricks_admin.oidc_provider import (
    DatabricksSSOUnavailableError,
    ensure_sso_supported,
)
from hub.apps.databricks_admin.session_policy import (
    countdown_state,
    hub_session_deadline,
)
from hub.apps.tenants.kill_switch_gates import (
    DatabricksSSODisabledAPIException,
    ensure_databricks_sso_allowed,
)

logger = logging.getLogger(__name__)


def _build_oidc_provider(tenant, workspace, redirect_uri: str = ""):
    """Construct the U2M provider from the workspace's SSO config.

    Module-level seam: the callback tests redirect this to a real local
    HTTP transport (the repo's own factory-seam pattern).
    """
    from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCProvider
    from hub.apps.tenants.models import TenantConfig

    config_row = TenantConfig.objects.filter(tenant=tenant).first()
    sso = (config_row.get_sso_config() if config_row else {}).get("databricks", {})
    if not sso.get("client_id"):
        raise DatabricksSSOUnavailableError(workspace.name)
    return DatabricksOIDCProvider(
        str(tenant.id),
        {
            "host": workspace.host,
            "client_id": sso["client_id"],
            "redirect_uri": redirect_uri
            or sso.get("redirect_uri", "")
            or f"https://{workspace.host}",
        },
    )


class DatabricksSSOViewSet(viewsets.ViewSet):
    """Sign-in with Databricks (U2M) endpoints."""

    permission_classes = (AllowAny,)

    @staticmethod
    def _ip_class(request) -> str:
        import ipaddress

        forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
        remote_addr = forwarded or (request.META.get("REMOTE_ADDR") or "")
        try:
            ip = ipaddress.ip_address(remote_addr)
        except ValueError:
            return "unknown"
        return "private" if ip.is_private else "public"

    def _gate_for_tenant(self, tenant) -> None:
        """Run the 0b.10 SSO flag + kill-switch gate for a RESOLVED tenant
        (the AllowAny flow has no request.tenant)."""
        from types import SimpleNamespace

        shim = SimpleNamespace(tenant=tenant, user=None)
        ensure_databricks_sso_allowed(shim)

    @action(detail=False, methods=["get"], url_path="workspaces")
    def workspaces(self, request):
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.filter(id=request.query_params.get("tenant_id")).first()
        if tenant is None:
            return Response(
                {"error": "Tenant context required", "code": "NO_TENANT"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            self._gate_for_tenant(tenant)
        except DatabricksSSODisabledAPIException as exc:
            return Response(
                {
                    "error": {
                        "code": exc.code,
                        "message": exc.detail.get("error", "SSO disabled"),
                    }
                },
                status=exc.status_code,
            )
        options = sso_workspace_options(tenant)
        return Response(
            {
                "workspaces": [
                    {
                        "id": str(w.id),
                        "name": w.name,
                        "host": w.host,
                        "cloud": w.cloud,
                    }
                    for w in options
                ]
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="login-url")
    def login_url(self, request):
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.filter(id=request.query_params.get("tenant_id")).first()
        workspace_id = request.query_params.get("workspace_id")
        if tenant is None or not workspace_id:
            return Response(
                {"error": "tenant_id and workspace_id are required", "code": "NO_TENANT"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            self._gate_for_tenant(tenant)
        except DatabricksSSODisabledAPIException as exc:
            return Response(
                {
                    "error": {
                        "code": exc.code,
                        "message": exc.detail.get("error", "SSO disabled"),
                    }
                },
                status=exc.status_code,
            )

        workspace = DatabricksWorkspace.objects.filter(tenant=tenant, id=workspace_id).first()
        if workspace is None:
            return Response(
                {"error": "Workspace not found", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            ensure_sso_supported(workspace)
            redirect_uri = request.query_params.get("redirect_uri") or ""
            provider = _build_oidc_provider(tenant, workspace, redirect_uri)
        except DatabricksSSOUnavailableError as exc:
            return Response(
                {
                    "error": {
                        "code": exc.code,
                        "message": str(exc),
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        state = sso_state.issue_state(str(tenant.id), self._ip_class(request))
        return Response(provider.build_authorize_url(state=state), status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="callback")
    def callback(self, request):
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User, UserStatus

        state_param = request.data.get("state")
        try:
            tenant_id = sso_state.peek_state(state_param)
        except sso_state.SSOStateError as exc:
            from hub.apps.databricks_admin.oidc_provider import classify_sso_state_error

            return Response(
                {"error": "State mismatch", "code": classify_sso_state_error(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant = Tenant.objects.filter(id=tenant_id).first()
        if tenant is None:
            return Response(
                {"error": "Tenant not found", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            self._gate_for_tenant(tenant)
        except DatabricksSSODisabledAPIException as exc:
            return Response(
                {
                    "error": {
                        "code": exc.code,
                        "message": exc.detail.get("error", "SSO disabled"),
                    }
                },
                status=exc.status_code,
            )

        workspace = DatabricksWorkspace.objects.filter(
            tenant=tenant, id=request.data.get("workspace_id")
        ).first()
        if workspace is None:
            return Response(
                {"error": "Workspace not found", "code": "NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND,
            )
        provider = _build_oidc_provider(tenant, workspace, request.data.get("redirect_uri") or "")
        try:
            tokens = provider.exchange_auth_code(
                code=request.data.get("code") or "",
                state=state_param,
                ip_class=self._ip_class(request),
            )
        except Exception as exc:
            from hub.apps.databricks_admin.oidc_provider import DatabricksOIDCTokenError

            code = getattr(exc, "code", "DATABRICKS_SSO_STATE_MISMATCH")
            if isinstance(exc, DatabricksOIDCTokenError):
                code = "DATABRICKS_AUTH_FAILED"
            return Response(
                {"error": "Databricks sign-in failed", "code": code},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Claims → Hub user (unverified decode — the repo's OIDC convention;
        # the workspace's token endpoint is the trust anchor).
        id_token = tokens.get("id_token") or ""
        claims = {}
        if id_token:
            try:
                claims = jwt.decode(
                    id_token, options={"verify_signature": False}, algorithms=["HS256"]
                )
            except jwt.exceptions.InvalidTokenError:
                claims = {}
        email = claims.get("email") or ""
        if not email:
            return Response(
                {"error": "Databricks id_token carried no email", "code": "DATABRICKS_AUTH_FAILED"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        user = User.objects.filter(email=email, tenant=tenant).first()
        if user is None:
            user = User.objects.create_user(
                email=email, tenant=tenant, password=None, status=UserStatus.ACTIVE
            )
        try:
            binding = provision_binding(
                tenant=tenant,
                user=user,
                workspace=workspace,
                databricks_sub=claims.get("sub") or f"sub-{email}",
                databricks_email=email,
            )
        except DatabricksBindingConflict as exc:
            return Response(
                {"error": str(exc), "code": "DATABRICKS_PRINCIPAL_ALREADY_BOUND"},
                status=status.HTTP_409_CONFLICT,
            )
        store_tokens(
            binding=binding,
            access_token=tokens.get("access_token") or "",
            access_expires_in=int(tokens.get("expires_in") or 300),
            refresh_token=tokens.get("refresh_token"),
        )

        access_token = JWTTokenGenerator.generate_access_token(user)
        return Response(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "user": {"id": str(user.id), "email": user.email},
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="session")
    def session(self, request):
        from datetime import UTC, datetime

        from hub.apps.databricks_admin.models import DatabricksOBOToken
        from hub.apps.databricks_admin.session_policy import (
            DEFAULT_COUNTDOWN_SECONDS,
        )

        user = request.user
        if not getattr(user, "is_authenticated", False):
            return Response(
                {"error": "Authentication required", "code": "AUTH_REQUIRED"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        bindings = user.databricks_user_bindings.all()
        now = datetime.now(UTC)
        # 0b.7 contract: the deadline is issued-at + hub lifetime — the
        # issued-at is the SESSION token's iat (falling back to now when no
        # token payload is present, e.g. non-JWT session auth).
        issued_ts = getattr(request, "token_payload", None) or {}
        issued_at = datetime.fromtimestamp(float(issued_ts.get("iat", now.timestamp())), UTC)
        countdown = {"active": False, "seconds_remaining": None}
        for binding in bindings:
            vault = DatabricksOBOToken.objects.filter(binding=binding).first()
            absolute_end = (
                vault.refresh_token_expires_at if vault and vault.refresh_token_expires_at else None
            )
            if absolute_end is not None:
                state = countdown_state(
                    binding_absolute_expires_at=absolute_end,
                    now=now,
                    countdown_seconds=DEFAULT_COUNTDOWN_SECONDS,
                )
                if state["active"]:
                    countdown = state
                    break
        return Response(
            {
                "countdown": countdown,
                "hub_reauth_deadline": hub_session_deadline(
                    session_issued_at=issued_at
                ).isoformat(),
            },
            status=status.HTTP_200_OK,
        )
