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


# Build urlpatterns list
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("hub.apps.api.urls")),
    path("graphql/", include("hub.apps.graphql.urls")),
]

# Conditionally include graphql_graphene URLs if available
# This prevents import errors if graphene_django is not installed
if _is_graphene_django_available():
    try:
        from hub.apps.graphql_graphene import urls as graphql_graphene_urls
        # Add graphql_graphene URLs directly after graphql URLs
        urlpatterns.append(path("graphql-graphene/", include(graphql_graphene_urls)))
    except (ImportError, ValueError, AttributeError) as e:
        # If graphql_graphene.urls can't be imported, skip it
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to import graphql_graphene URLs: {e}")
        pass

# Add remaining URL patterns
urlpatterns.extend([
    path("health/", include("hub.apps.health.urls")),
    # Metrics at /metrics and /metrics/ for Prometheus (no trailing slash) and tools
    path("metrics", include("hub.apps.observability.urls")),
    path("metrics/", include("hub.apps.observability.urls")),
    # API Documentation
    path("api-docs/openapi.json", OpenAPISchemaView.as_view(), name="openapi-schema"),
    path("api-docs/", SwaggerUIView.as_view(url_name="openapi-schema"), name="swagger-ui"),
    path("api-docs/redoc/", ReDocView.as_view(url_name="openapi-schema"), name="redoc"),
])

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
