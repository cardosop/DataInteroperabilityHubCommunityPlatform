"""
SSO Views

REST API views for SSO authentication (OIDC only — the SAML endpoints
are DELETED, oss-release-remediation W1.5/D4).

The OIDC callback verifies the ID token via JWKS (signature + iss + aud
+ exp) before any user lookup — see ``hub.apps.auth.oidc_verifier``.
Tenant resolution trusts ONLY the signed one-time ``state`` payload
(``hub.apps.auth.sso_state``): a missing/invalid state fails closed with
SSO_STATE_* — there is no unverified-claims fallback path.
"""

import os
import sys

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from hub.apps.observability.cross_tenant_metrics import cross_tenant_denied

from . import sso_state
from .jwt_utils import JWTTokenGenerator
from .sso import SSOService
from .throttles import SSOThrottle


class SSOViewSet(viewsets.ViewSet):
    """
    ViewSet for SSO authentication (OIDC).
    """

    permission_classes = [AllowAny]  # SSO endpoints are public
    throttle_classes = (SSOThrottle,)  # W1.5 — SSO endpoints throttled per IP

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

    def _resolve_callback_tenant_id(
        self,
        *,
        request,
        state_param: str | None,
    ) -> str:
        # D4/W1.5: the tenant comes ONLY from the signed one-time state.
        # A missing state fails closed (SSO_STATE_MISSING) — the old
        # single-membership email fallback relied on UNVERIFIED claims
        # and is deleted. Every SSOStateError maps to a 400 ValidationError.
        request_ip_class = self._ip_class(request)
        try:
            state_tenant_id = sso_state.consume_state(state_param, request_ip_class)
        except sso_state.SSOStateError as exc:
            raise ValidationError({"error": exc.code}) from exc

        body_tenant_id = request.data.get("tenant_id")
        if body_tenant_id and str(body_tenant_id) != str(state_tenant_id):
            cross_tenant_denied(
                endpoint="auth.sso_callback",
                reason="body_tenant_mismatch",
                request=request,
                requested_tenant_id=body_tenant_id,
                actual_tenant_id=state_tenant_id,
            )
            raise ValidationError({"error": "SSO_STATE_TENANT_MISMATCH"})

        return str(state_tenant_id)

    def _get_tenant_id(self, request):
        """Get tenant ID from request"""
        # For SSO, tenant might be in query params or subdomain
        tenant_id = request.query_params.get("tenant_id")
        if tenant_id:
            return tenant_id

        # Try to get from request
        if hasattr(request, "tenant_id") and request.tenant_id:
            return str(request.tenant_id)

        tenant = getattr(request, "tenant", None)
        if tenant and hasattr(tenant, "id"):
            return str(tenant.id)

        return None

    @extend_schema(
        summary="Get OIDC login URL",
        description="Get OIDC SSO login URL for redirect",
        parameters=[
            OpenApiParameter(
                name="tenant_id",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description="Tenant UUID",
                required=True,
            ),
            OpenApiParameter(
                name="redirect_uri",
                type=OpenApiTypes.URI,
                location=OpenApiParameter.QUERY,
                description="Redirect URI after authentication",
                required=True,
            ),
        ],
        responses={
            200: OpenApiResponse(description="OIDC login URL"),
            400: OpenApiResponse(description="Invalid request or SSO not configured"),
        },
        tags=["SSO"],
    )
    @action(detail=False, methods=["get"], url_path="oidc/login-url")
    def oidc_login_url(self, request):
        """
        Get OIDC login URL.

        GET /api/v1/auth/sso/oidc/login-url/
        """
        tenant_id = self._get_tenant_id(request)
        redirect_uri = request.query_params.get("redirect_uri")

        if not tenant_id:
            raise ValidationError("tenant_id is required")

        if not redirect_uri:
            raise ValidationError("redirect_uri is required")

        state = sso_state.issue_state(tenant_id, self._ip_class(request))
        login_url = SSOService.get_sso_login_url(
            tenant_id,
            "OIDC",
            redirect_uri,
            state=state,
        )

        if not login_url:
            return Response(
                {"error": "OIDC SSO not configured for this tenant"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"login_url": login_url}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="OIDC authentication callback",
        description=(
            "Handle OIDC authentication callback. The ID token is verified "
            "via the tenant IdP's JWKS (signature, issuer, audience, "
            "expiry) before any user lookup; the tenant is resolved from "
            "the signed one-time `state` payload. A missing/invalid state "
            "or an invalid token fails closed with 400."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "id_token": {"type": "string"},
                    "access_token": {"type": "string"},
                    "state": {"type": "string"},
                },
                "required": ["id_token", "state"],
            }
        },
        responses={
            200: OpenApiResponse(description="Authentication successful"),
            400: OpenApiResponse(description="Authentication failed"),
            429: OpenApiResponse(description="Rate limit exceeded"),
        },
        tags=["SSO"],
    )
    @action(detail=False, methods=["post"], url_path="oidc/callback")
    def oidc_callback(self, request):
        """
        Handle OIDC callback.

        POST /api/v1/auth/sso/oidc/callback/
        """
        id_token = request.data.get("id_token")
        access_token = request.data.get("access_token")

        if not id_token:
            raise ValidationError("id_token is required")

        # D4/W1.5: tenant from the signed one-time state ONLY — no
        # unverified-claims fallback (a forged token cannot pick its
        # tenant either).
        tenant_id = self._resolve_callback_tenant_id(
            request=request,
            state_param=request.data.get("state"),
        )

        user, attributes = SSOService.authenticate_oidc(tenant_id, id_token, access_token)

        if user is None:
            verification_error = (attributes or {}).get("verification_error")
            return Response(
                {"error": verification_error or "OIDC authentication failed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate JWT token
        access_token_jwt = JWTTokenGenerator.generate_access_token(user)

        # Warm cache for tenant on login (async to avoid blocking login response).
        # Skip during tests: background threads opened by the in-process test
        # client are blocked by pytest-django's database access guard.
        _is_test = (
            "pytest" in sys.modules
            or os.environ.get("PYTEST_CURRENT_TEST")
            or os.environ.get("TESTING")
        )
        if getattr(user, "tenant_id", None) and not _is_test:
            try:
                import threading

                from hub.apps.core.caching.warming import warm_tenant_cache

                # Warm cache in background thread to avoid blocking login
                def warm_cache_async():
                    try:
                        user_tenant_id = str(getattr(user, "tenant_id", ""))
                        warm_tenant_cache(user_tenant_id)
                    except Exception as e:
                        # Log error but don't fail login
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"Failed to warm cache on SSO login: {e}",
                            exc_info=True,
                        )

                # Start background thread for cache warming
                thread = threading.Thread(target=warm_cache_async, daemon=True)
                thread.start()
            except (ImportError, RuntimeError) as e:
                # Log error but don't fail login
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to start cache warming on SSO login: {e}",
                    exc_info=True,
                )

        return Response(
            {
                "access_token": access_token_jwt,
                "token_type": "Bearer",
                "user": {
                    "id": str(getattr(user, "id", "")),
                    "email": getattr(user, "email", ""),
                },
            },
            status=status.HTTP_200_OK,
        )
