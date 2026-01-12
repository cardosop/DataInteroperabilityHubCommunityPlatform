"""
API Views

Views for API documentation and OpenAPI schema generation.
"""
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView
)
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from drf_spectacular.types import OpenApiTypes
import drf_spectacular.renderers
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
import yaml


class OpenAPISchemaView(SpectacularAPIView):
    """
    OpenAPI 3.0 schema generation endpoint.

    GET /api-docs/openapi.json
    GET /api/v1/openapi.json
    GET /api/v1/openapi.yaml
    """
    renderer_classes = [drf_spectacular.renderers.OpenApiJsonRenderer]
    urlconf = 'hub.urls'

    def get(self, request, *args, **kwargs):
        """Return JSON format schema with validation and enhancement"""
        from .openapi_validation import OpenAPISpecValidator
        from .openapi_enhancement import OpenAPISpecEnhancer
        from drf_spectacular.generators import SchemaGenerator

        # Generate schema using the generator
        generator = SchemaGenerator(urlconf=self.urlconf)
        schema = generator.get_schema(request=request, public=True)

        # Validate schema
        is_valid, errors = OpenAPISpecValidator.validate_spec(schema)
        if not is_valid:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "openapi_spec_validation_errors",
                errors=errors
            )

        # Enhance schema with validation and additional documentation
        schema = OpenAPISpecValidator.enhance_spec(schema)
        schema = OpenAPISpecEnhancer.enhance_spec(schema)

        # Check if YAML format requested
        format_type = request.query_params.get('format', 'json')
        if format_type.lower() == 'yaml':
            yaml_content = OpenAPISpecValidator.export_spec(schema, format='yaml')
            return Response(yaml_content, content_type='application/x-yaml')

        # Return JSON schema
        return Response(schema, content_type='application/json')


class OpenAPIYAMLView(SpectacularAPIView):
    """
    OpenAPI 3.0 schema generation endpoint (YAML format).

    GET /api/v1/openapi.yaml
    """
    renderer_classes = [drf_spectacular.renderers.OpenApiYamlRenderer]
    urlconf = 'hub.urls'

    def get(self, request, *args, **kwargs):
        """Return YAML format schema with validation and enhancement"""
        from .openapi_validation import OpenAPISpecValidator
        from .openapi_enhancement import OpenAPISpecEnhancer
        from drf_spectacular.generators import SchemaGenerator

        # Generate schema using the generator
        generator = SchemaGenerator(urlconf=self.urlconf)
        schema = generator.get_schema(request=request, public=True)

        # Validate schema
        is_valid, errors = OpenAPISpecValidator.validate_spec(schema)
        if not is_valid:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning(
                "openapi_spec_validation_errors",
                errors=errors
            )

        # Enhance schema with validation and additional documentation
        schema = OpenAPISpecValidator.enhance_spec(schema)
        schema = OpenAPISpecEnhancer.enhance_spec(schema)

        # Export as YAML
        yaml_content = OpenAPISpecValidator.export_spec(schema, format='yaml')
        return Response(yaml_content, content_type='application/x-yaml')


class SwaggerUIView(SpectacularSwaggerView):
    """
    Enhanced Swagger UI documentation endpoint with comprehensive examples.

    GET /api-docs/

    Provides interactive API documentation using Swagger UI.
    """
    urlconf = 'hub.urls'

    def get(self, request, *args, **kwargs):
        """
        Return Swagger UI with enhanced configuration.

        The Swagger UI automatically loads the OpenAPI schema from the
        openapi-schema endpoint and provides interactive API exploration.
        """
        response = super().get(request, *args, **kwargs)
        return response


class ReDocView(SpectacularRedocView):
    """
    ReDoc documentation endpoint.

    GET /api-docs/redoc/

    Provides alternative API documentation using ReDoc.
    ReDoc offers a clean, three-panel documentation layout.
    """
    urlconf = 'hub.urls'

    def get(self, request, *args, **kwargs):
        """
        Return ReDoc documentation.

        ReDoc automatically loads the OpenAPI schema and provides
        a clean, readable documentation interface.
        """
        response = super().get(request, *args, **kwargs)
        return response


class APIInfoSerializer(serializers.Serializer):
    """Serializer for API info endpoint"""
    name = serializers.CharField()
    version = serializers.CharField()
    base_url = serializers.CharField()
    documentation = serializers.DictField()
    endpoints = serializers.DictField()


@extend_schema(
    responses={200: APIInfoSerializer},
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
    from .versioning import APIVersionManager

    # Get API version from request
    api_version = APIVersionManager.get_request_version(request)

    return Response({
        'name': 'Interoperable Data Hub API',
        'version': str(api_version),
        'base_url': '/api/v1',
        'documentation': {
            'openapi': '/api-docs/openapi.json',
            'openapi_yaml': '/api/v1/openapi.yaml',
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
            'webhooks': '/api/v1/webhooks/',
            'analytics': '/api/v1/analytics/',
        }
    })


@extend_schema(
    exclude=True,  # Exclude from OpenAPI schema
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
