"""
API Views

Views for API documentation and OpenAPI schema generation.
"""

import drf_spectacular.renderers
import yaml
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response


class OpenAPISchemaView(SpectacularAPIView):
    """
    OpenAPI 3.0 schema generation endpoint.

    GET /api-docs/openapi.json
    GET /api/v1/openapi.json
    GET /api/v1/openapi.yaml

    Uses OpenApiJsonRenderer2 so Accept: application/json (e.g. from browser/axios)
    is satisfied; OpenApiJsonRenderer uses application/vnd.oai.openapi+json and
    causes 406 when clients send application/json.
    """

    # Prefer renderer that declares application/json so browser/axios Accept works
    _json_renderer = getattr(
        drf_spectacular.renderers,
        "OpenApiJsonRenderer2",
        drf_spectacular.renderers.OpenApiJsonRenderer,
    )
    renderer_classes = [_json_renderer]
    urlconf = "hub.urls"

    def perform_content_negotiation(self, request, force=False):
        """Accept application/json so browser/axios requests get 200, not 406."""
        accept = request.META.get("HTTP_ACCEPT", "") or ""
        if "application/json" in accept and self.renderer_classes:
            renderer = self.renderer_classes[0]()
            return (renderer, renderer.media_type)
        return super().perform_content_negotiation(request, force=force)

    def get(self, request, *args, **kwargs):
        """Return JSON format schema with validation and enhancement"""
        import structlog

        from drf_spectacular.generators import SchemaGenerator

        from .openapi_enhancement import OpenAPISpecEnhancer
        from .openapi_validation import OpenAPISpecValidator

        logger = structlog.get_logger(__name__)

        # Generate schema using the generator
        try:
            generator = SchemaGenerator(urlconf=self.urlconf)
            schema = generator.get_schema(request=request, public=True)
        except Exception as e:
            logger.warning("openapi_schema_generation_failed", error=str(e), exc_info=True)
            # Return minimal schema so capabilities/register/password-reset can load
            schema = {
                "openapi": "3.0.0",
                "info": {"title": "Data Interoperability Hub", "version": "1.0"},
                "paths": {
                    "/api/v1/auth/register/": {"post": {"operationId": "auth_register_create"}},
                    "/api/v1/auth/password-reset/": {"post": {"operationId": "auth_password_reset_create"}},
                    "/api/v1/auth/password-reset/confirm/": {
                        "post": {"operationId": "auth_password_reset_confirm_create"}
                    },
                },
            }

        # Validate schema
        is_valid, errors = OpenAPISpecValidator.validate_spec(schema)
        if not is_valid:
            logger.warning("openapi_spec_validation_errors", errors=errors)

        # Enhance schema with validation and additional documentation
        schema = OpenAPISpecValidator.enhance_spec(schema)
        try:
            schema = OpenAPISpecEnhancer.enhance_spec(schema)
        except Exception as enh_err:
            logger.warning(
                "openapi_enhancement_failed",
                error=str(enh_err),
                exc_info=True,
            )
            # Return schema without enhancement so capabilities can load

        # Check if YAML format requested
        format_type = request.query_params.get("format", "json")
        if format_type.lower() == "yaml":
            yaml_content = OpenAPISpecValidator.export_spec(schema, format="yaml")
            return Response(yaml_content, content_type="application/x-yaml")

        # Return JSON schema
        return Response(schema, content_type="application/json")


class OpenAPIYAMLView(SpectacularAPIView):
    """
    OpenAPI 3.0 schema generation endpoint (YAML format).

    GET /api/v1/openapi.yaml
    """

    renderer_classes = [drf_spectacular.renderers.OpenApiYamlRenderer]
    urlconf = "hub.urls"

    def get(self, request, *args, **kwargs):
        """Return YAML format schema with validation and enhancement"""
        import structlog

        from drf_spectacular.generators import SchemaGenerator

        from .openapi_enhancement import OpenAPISpecEnhancer
        from .openapi_validation import OpenAPISpecValidator

        logger = structlog.get_logger(__name__)

        # Generate schema using the generator
        try:
            generator = SchemaGenerator(urlconf=self.urlconf)
            schema = generator.get_schema(request=request, public=True)
        except Exception as e:
            logger.warning("openapi_schema_generation_failed", error=str(e), exc_info=True)
            schema = {
                "openapi": "3.0.0",
                "info": {"title": "Data Interoperability Hub", "version": "1.0"},
                "paths": {
                    "/api/v1/auth/register/": {"post": {"operationId": "auth_register_create"}},
                    "/api/v1/auth/password-reset/": {"post": {"operationId": "auth_password_reset_create"}},
                    "/api/v1/auth/password-reset/confirm/": {
                        "post": {"operationId": "auth_password_reset_confirm_create"}
                    },
                },
            }

        # Validate schema
        is_valid, errors = OpenAPISpecValidator.validate_spec(schema)
        if not is_valid:
            logger.warning("openapi_spec_validation_errors", errors=errors)

        # Enhance schema with validation and additional documentation
        schema = OpenAPISpecValidator.enhance_spec(schema)
        try:
            schema = OpenAPISpecEnhancer.enhance_spec(schema)
        except Exception as enh_err:
            logger.warning(
                "openapi_enhancement_failed",
                error=str(enh_err),
                exc_info=True,
            )

        # Export as YAML
        yaml_content = OpenAPISpecValidator.export_spec(schema, format="yaml")
        return Response(yaml_content, content_type="application/x-yaml")


class SwaggerUIView(SpectacularSwaggerView):
    """
    Enhanced Swagger UI documentation endpoint with comprehensive examples.

    GET /api-docs/

    Provides interactive API documentation using Swagger UI.
    """

    urlconf = "hub.urls"

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

    urlconf = "hub.urls"

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


@extend_schema(responses={200: APIInfoSerializer}, tags=["API"])
@api_view(["GET"])
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

    return Response(
        {
            "name": "Interoperable Data Hub API",
            "version": str(api_version),
            "base_url": "/api/v1",
            "documentation": {
                "openapi": "/api-docs/openapi.json",
                "openapi_yaml": "/api/v1/openapi.yaml",
                "swagger": "/api-docs/",
                "redoc": "/api-docs/redoc/",
            },
            "endpoints": {
                "auth": "/api/v1/auth/",
                "tenants": "/api/v1/tenants/",
                "users": "/api/v1/users/",
                "files": "/api/v1/files/",
                "datasets": "/api/v1/datasets/",
                "assets": "/api/v1/assets/",
                "contracts": "/api/v1/contracts/",
                "jobs": "/api/v1/jobs/",
                "dq": "/api/v1/dq/",
                "compliance": "/api/v1/compliance/",
                "semantic": "/api/v1/semantic/",
                "marketplace": "/api/v1/marketplace/",
                "audit": "/api/v1/audit/",
                "webhooks": "/api/v1/webhooks/",
                "analytics": "/api/v1/analytics/",
                "scheduled-ingestions": "/api/v1/scheduled-ingestions/",
                "scheduled-exports": "/api/v1/scheduled-exports/",
            },
        }
    )


@extend_schema(exclude=True, tags=["API"])  # Exclude from OpenAPI schema
@api_view(["GET", "POST", "PUT", "PATCH", "DELETE"])
@permission_classes([AllowAny])
def api_not_found(request):
    """
    Catch-all handler for non-existent API endpoints.

    This ensures all 404s within /api/v1/ return standardized error format.
    """
    raise NotFound("Resource not found")


# Must match ensure_e2e_user_roles.E2E_USERS and ensure_e2e_subscription.E2E_EMAILS
E2E_EMAILS = (
    "e2e_test@example.com",
    "e2e_consumer@example.com",
    "e2e_admin@example.com",
    "e2e_platform@example.com",
    "e2e_auditor@example.com",
    "e2e_cpo@example.com",
    "e2e_developer@example.com",
    "e2e_dmo@example.com",
)


@extend_schema(exclude=True, tags=["API"])
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ensure_e2e_subscription(request):
    """
    Ensure E2E test user's tenant has active subscription and VERIFIED KYC.

    Subscription enables writes; KYC enables marketplace publish. Only available
    when ENVIRONMENT=test or DEBUG=True. Only for E2E test user emails.
    """
    from django.conf import settings

    if not (getattr(settings, "ENVIRONMENT", "") == "test" or settings.DEBUG):
        raise NotFound("Resource not found")
    if request.user.email not in E2E_EMAILS:
        raise NotFound("Resource not found")
    if not request.user.tenant_id:
        return Response({"ok": False, "error": "no tenant"}, status=400)
    from hub.apps.testing.billing_support import ensure_e2e_tenant_ready

    ensure_e2e_tenant_ready(request.user.tenant)
    return Response({"ok": True})
