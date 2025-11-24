"""
API Views

Views for API documentation and OpenAPI schema generation.
"""
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView
)
from drf_spectacular.utils import extend_schema, OpenApiResponse
import drf_spectacular.renderers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound


class OpenAPISchemaView(SpectacularAPIView):
    """
    OpenAPI 3.0 schema generation endpoint.
    
    GET /api-docs/openapi.json
    """
    renderer_classes = [drf_spectacular.renderers.OpenApiJsonRenderer]
    
    def get(self, request, *args, **kwargs):
        """Return JSON format schema"""
        return super().get(request, *args, **kwargs)


class SwaggerUIView(SpectacularSwaggerView):
    """
    Swagger UI documentation endpoint.
    
    GET /api-docs/
    """
    pass


class ReDocView(SpectacularRedocView):
    """
    ReDoc documentation endpoint.
    
    GET /api-docs/redoc/
    """
    pass


@extend_schema(
    responses={200: {
        'type': 'object',
        'properties': {
            'name': {'type': 'string'},
            'version': {'type': 'string'},
            'base_url': {'type': 'string'},
            'documentation': {'type': 'object'},
            'endpoints': {'type': 'object'}
        }
    }},
    tags=['API']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def api_info(request):
    """
    API information endpoint.
    
    GET /api/v1/
    Returns basic API information and available endpoints.
    """
    return Response({
        'name': 'Interoperable Data Hub API',
        'version': '1.0.0',
        'base_url': '/api/v1',
        'documentation': {
            'openapi': '/api-docs/openapi.json',
            'swagger': '/api-docs/',
            'redoc': '/api-docs/redoc/'
        },
        'endpoints': {
            'auth': '/api/v1/auth/',
            'tenants': '/api/v1/tenants/',
            'users': '/api/v1/users/',
            'files': '/api/v1/files/',
            'datasets': '/api/v1/datasets/',
            'assets': '/api/v1/assets/',
            'contracts': '/api/v1/contracts/',
            'jobs': '/api/v1/jobs/',
            'dq': '/api/v1/dq/',
            'compliance': '/api/v1/compliance/',
            'semantic': '/api/v1/semantic/',
            'marketplace': '/api/v1/marketplace/',
            'audit': '/api/v1/audit/',
        }
    })


@extend_schema(
    responses={404: OpenApiResponse(description='Resource not found')},
    tags=['API']
)
@api_view(['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([AllowAny])
def api_not_found(request):
    """
    Catch-all handler for non-existent API endpoints.
    
    This ensures all 404s within /api/v1/ return standardized error format.
    """
    raise NotFound('Resource not found')

