"""
OpenAPI Extensions for Custom Authentication

Provides OpenAPI schema extensions for custom authentication classes.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    OpenAPI extension for JWT Authentication.
    """

    target_class = "hub.apps.auth.authentication.JWTAuthentication"
    name = "BearerAuth"  # Standard name for Bearer token authentication in OpenAPI

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token authentication. Include token in Authorization header as: Bearer <token>",
        }


class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    OpenAPI extension for API Key Authentication.
    """

    target_class = "hub.apps.auth.authentication.APIKeyAuthentication"
    name = "APIKeyAuthentication"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key authentication. Include API key in X-API-Key header.",
        }
