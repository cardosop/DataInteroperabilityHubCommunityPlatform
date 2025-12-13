"""
SSO Views

REST API views for SSO authentication.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

from .sso import SSOService
from .jwt_utils import JWTTokenGenerator


class SSOViewSet(viewsets.ViewSet):
    """
    ViewSet for SSO authentication.
    """
    permission_classes = [AllowAny]  # SSO endpoints are public
    
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
        
        login_url = SSOService.get_sso_login_url(tenant_id, "SAML", redirect_uri)
        
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
        tenant_id = self._get_tenant_id(request) or request.data.get('tenant_id')
        saml_response = request.data.get('SAMLResponse')
        
        if not tenant_id:
            raise ValidationError("tenant_id is required")
        
        if not saml_response:
            raise ValidationError("SAMLResponse is required")
        
        user, attributes = SSOService.authenticate_saml(tenant_id, saml_response)
        
        if not user:
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
                'id': str(user.id),
                'email': user.email
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
        
        login_url = SSOService.get_sso_login_url(tenant_id, "OIDC", redirect_uri)
        
        if not login_url:
            return Response(
                {"error": "OIDC SSO not configured for this tenant"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({"login_url": login_url}, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="OIDC authentication callback",
        description="Handle OIDC authentication callback",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'id_token': {'type': 'string'},
                    'access_token': {'type': 'string'},
                    'tenant_id': {'type': 'string', 'format': 'uuid'}
                },
                'required': ['id_token', 'tenant_id']
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
        tenant_id = self._get_tenant_id(request) or request.data.get('tenant_id')
        id_token = request.data.get('id_token')
        access_token = request.data.get('access_token')
        
        if not tenant_id:
            raise ValidationError("tenant_id is required")
        
        if not id_token:
            raise ValidationError("id_token is required")
        
        user, claims = SSOService.authenticate_oidc(tenant_id, id_token, access_token)
        
        if not user:
            return Response(
                {"error": "OIDC authentication failed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate JWT token
        access_token_jwt = JWTTokenGenerator.generate_access_token(user)
        
        return Response({
            'access_token': access_token_jwt,
            'token_type': 'Bearer',
            'user': {
                'id': str(user.id),
                'email': user.email
            }
        }, status=status.HTTP_200_OK)

