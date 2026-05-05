"""
SSO Views

REST API views for SSO authentication.
"""
import ipaddress

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from drf_spectacular.types import OpenApiTypes

from hub.apps.observability.cross_tenant_metrics import cross_tenant_denied
from hub.apps.users.models import UserTenantMembership

from .sso import SSOService
from .jwt_utils import JWTTokenGenerator
from . import sso_state


class SSOViewSet(viewsets.ViewSet):
    """
    ViewSet for SSO authentication.
    """
    permission_classes = [AllowAny]  # SSO endpoints are public

    @staticmethod
    def _ip_class(request) -> str:
        forwarded = (
            (request.META.get("HTTP_X_FORWARDED_FOR") or "")
            .split(",")[0]
            .strip()
        )
        remote_addr = forwarded or (request.META.get("REMOTE_ADDR") or "")
        try:
            ip = ipaddress.ip_address(remote_addr)
        except ValueError:
            return "unknown"
        return "private" if ip.is_private else "public"

    @staticmethod
    def _single_membership_tenant_id(email: str | None) -> str | None:
        if not email:
            return None
        memberships = (
            UserTenantMembership.objects.filter(user__email=email)
            .values_list("tenant_id", flat=True)
            .distinct()
        )
        tenant_ids = [str(tid) for tid in memberships]
        if len(tenant_ids) == 1:
            return tenant_ids[0]
        if len(tenant_ids) > 1:
            raise ValidationError({"error": "SSO_TENANT_AMBIGUOUS"})
        return None

    def _resolve_callback_tenant_id(
        self,
        *,
        request,
        state_param: str | None,
        asserted_email: str | None,
    ) -> str:
        request_ip_class = self._ip_class(request)
        try:
            state_tenant_id = sso_state.consume_state(state_param, request_ip_class)
        except sso_state.SSOStateError as exc:
            if exc.code == "SSO_STATE_MISSING":
                fallback_tenant_id = self._single_membership_tenant_id(asserted_email)
                if fallback_tenant_id:
                    return fallback_tenant_id
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
        tenant_id = request.query_params.get('tenant_id')
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
        summary="Get SAML login URL",
        description="Get SAML SSO login URL for redirect",
        parameters=[
            OpenApiParameter(
                name='tenant_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Tenant UUID',
                required=True
            ),
            OpenApiParameter(
                name='redirect_uri',
                type=OpenApiTypes.URI,
                location=OpenApiParameter.QUERY,
                description='Redirect URI after authentication',
                required=True
            ),
        ],
        responses={
            200: OpenApiResponse(description="SAML login URL"),
            400: OpenApiResponse(description="Invalid request or SSO not configured"),
        },
        tags=['SSO']
    )
    @action(detail=False, methods=['get'], url_path='saml/login-url')
    def saml_login_url(self, request):
        """
        Get SAML login URL.

        GET /api/v1/auth/sso/saml/login-url/
        """
        tenant_id = self._get_tenant_id(request)
        redirect_uri = request.query_params.get('redirect_uri')

        if not tenant_id:
            raise ValidationError("tenant_id is required")

        if not redirect_uri:
            raise ValidationError("redirect_uri is required")

        relay_state = sso_state.issue_state(tenant_id, self._ip_class(request))
        login_url = SSOService.get_sso_login_url(
            tenant_id,
            "SAML",
            redirect_uri,
            state=relay_state,
        )

        if not login_url:
            return Response(
                {"error": "SAML SSO not configured for this tenant"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"login_url": login_url}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="SAML authentication callback",
        description="Handle SAML authentication callback",
        request={
            'application/x-www-form-urlencoded': {
                'type': 'object',
                'properties': {
                    'SAMLResponse': {'type': 'string'},
                    'RelayState': {'type': 'string'}
                }
            }
        },
        responses={
            200: OpenApiResponse(description="Authentication successful"),
            400: OpenApiResponse(description="Authentication failed"),
        },
        tags=['SSO']
    )
    @action(detail=False, methods=['post'], url_path='saml/callback')
    def saml_callback(self, request):
        """
        Handle SAML callback.

        POST /api/v1/auth/sso/saml/callback/
        """
        saml_response = request.data.get('SAMLResponse')

        if not saml_response:
            raise ValidationError("SAMLResponse is required")

        asserted_identity = SSOService._extract_unverified_saml_identity(
            saml_response
        )
        tenant_id = self._resolve_callback_tenant_id(
            request=request,
            state_param=request.data.get("RelayState"),
            asserted_email=asserted_identity,
        )

        user, attributes = SSOService.authenticate_saml(tenant_id, saml_response)

        if user is None:
            return Response(
                {"error": "SAML authentication failed"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate JWT token
        access_token = JWTTokenGenerator.generate_access_token(user)

        return Response({
            'access_token': access_token,
            'token_type': 'Bearer',
            'user': {
                'id': str(getattr(user, "id", "")),
                'email': getattr(user, "email", ""),
            }
        }, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Get OIDC login URL",
        description="Get OIDC SSO login URL for redirect",
        parameters=[
            OpenApiParameter(
                name='tenant_id',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Tenant UUID',
                required=True
            ),
            OpenApiParameter(
                name='redirect_uri',
                type=OpenApiTypes.URI,
                location=OpenApiParameter.QUERY,
                description='Redirect URI after authentication',
                required=True
            ),
        ],
        responses={
            200: OpenApiResponse(description="OIDC login URL"),
            400: OpenApiResponse(description="Invalid request or SSO not configured"),
        },
        tags=['SSO']
    )
    @action(detail=False, methods=['get'], url_path='oidc/login-url')
    def oidc_login_url(self, request):
        """
        Get OIDC login URL.

        GET /api/v1/auth/sso/oidc/login-url/
        """
        tenant_id = self._get_tenant_id(request)
        redirect_uri = request.query_params.get('redirect_uri')

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
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"login_url": login_url}, status=status.HTTP_200_OK)

    @extend_schema(
        summary="OIDC authentication callback",
        description=(
            "Handle OIDC authentication callback. Tenant is resolved from "
            "signed `state` payload; request-body `tenant_id` is deprecated "
            "and ignored when matching state (mismatch is rejected)."
        ),
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'id_token': {'type': 'string'},
                    'access_token': {'type': 'string'},
                    'state': {'type': 'string'},
                },
                'required': ['id_token', 'state']
            }
        },
        responses={
            200: OpenApiResponse(description="Authentication successful"),
            400: OpenApiResponse(description="Authentication failed"),
        },
        tags=['SSO']
    )
    @action(detail=False, methods=['post'], url_path='oidc/callback')
    def oidc_callback(self, request):
        """
        Handle OIDC callback.

        POST /api/v1/auth/sso/oidc/callback/
        """
        id_token = request.data.get('id_token')
        access_token = request.data.get('access_token')

        if not id_token:
            raise ValidationError("id_token is required")

        claims = SSOService._extract_unverified_oidc_claims(id_token)
        tenant_id = self._resolve_callback_tenant_id(
            request=request,
            state_param=request.data.get("state"),
            asserted_email=(
                claims.get("email")
                if isinstance(claims, dict)
                else None
            ),
        )

        user, claims = SSOService.authenticate_oidc(tenant_id, id_token, access_token)

        if user is None:
            return Response(
                {"error": "OIDC authentication failed"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate JWT token
        access_token_jwt = JWTTokenGenerator.generate_access_token(user)

        # Warm cache for tenant on login (async to avoid blocking login response)
        if getattr(user, "tenant_id", None):
            try:
                from hub.apps.core.caching.warming import warm_tenant_cache
                import threading

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
            except Exception as e:
                # Log error but don't fail login
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed to start cache warming on SSO login: {e}",
                    exc_info=True,
                )

        return Response({
            'access_token': access_token_jwt,
            'token_type': 'Bearer',
            'user': {
                'id': str(getattr(user, "id", "")),
                'email': getattr(user, "email", ""),
            }
        }, status=status.HTTP_200_OK)
