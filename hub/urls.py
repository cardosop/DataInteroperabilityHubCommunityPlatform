"""
URL configuration for hub project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from hub.apps.api.views import OpenAPISchemaView, ReDocView, SwaggerUIView


def _is_graphene_django_available() -> bool:
    """
    Check if graphene_django is available.

    Returns:
        True if graphene_django is installed and can be imported, False otherwise.
    """
    try:
        import graphene_django  # noqa: F401

        return True
    except ImportError:
        return False


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("hub.apps.api.urls")),
    path("graphql/", include("hub.apps.graphql.urls")),
    path("health/", include("hub.apps.health.urls")),
    # Observability
    path("metrics/", include("hub.apps.observability.urls")),
    # API Documentation
    path("api-docs/openapi.json", OpenAPISchemaView.as_view(), name="openapi-schema"),
    path("api-docs/", SwaggerUIView.as_view(url_name="openapi-schema"), name="swagger-ui"),
    path("api-docs/redoc/", ReDocView.as_view(url_name="openapi-schema"), name="redoc"),
]

# Conditionally include graphql_graphene URLs if available
# This prevents import errors if graphene_django is not installed
if _is_graphene_django_available():
    try:
        from hub.apps.graphql_graphene import urls as graphql_graphene_urls

        # Insert graphql_graphene URLs after graphql URLs
        # Find graphql path by checking pattern strings
        for i, url_pattern in enumerate(urlpatterns):
            # Check if this is the graphql path by examining its string representation
            pattern_str = str(url_pattern)
            if "graphql" in pattern_str and "graphql-graphene" not in pattern_str:
                urlpatterns.insert(i + 1, path("graphql-graphene/", include(graphql_graphene_urls)))
                break
    except (ImportError, ValueError, AttributeError):
        # If graphql_graphene.urls can't be imported, skip it
        pass

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
