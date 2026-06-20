"""
URL configuration for hub project.
"""

from importlib import import_module

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from hub.apps.api.views import OpenAPISchemaView, ReDocView, SwaggerUIView
from hub.apps.security.views import csp_report_view


class _LazyURLConf:
    """Defer importing a URLconf module until the first request to its prefix.

    Using this wrapper with ``include()`` prevents eager imports of expensive
    schemas (e.g. graphql-graphene) from blocking URL resolution for unrelated
    routes during Django startup or test runs.
    """

    def __init__(self, module_path: str):
        self._module_path = module_path
        self._urlconf = None

    @property
    def urlpatterns(self):
        if self._urlconf is None:
            self._urlconf = import_module(self._module_path)
        return self._urlconf.urlpatterns


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


def _build_urlpatterns() -> list:
    """
    Build the root URL patterns list.

    Extracted into a function so that Phase 221.2.1 production guards and
    their tests can evaluate the conditional admin registration without
    module-reload tricks.

    Returns:
        Complete list of URL patterns for ROOT_URLCONF.
    """
    patterns = [
        path("api/v1/", include("hub.apps.api.urls")),
        # Phase 18.3 — unified FTS endpoint querying Asset/Contract search_vector
        path("api/search/", include("hub.apps.search.search_urls")),
        path("graphql/", include("hub.apps.graphql.urls")),
    ]

    # Phase 221.2.1 + Track A PR 1 — Django admin is only available outside
    # production AND staging. Staging is publicly reachable, so exposing
    # /admin/ there is the same attack surface as prod. Dev / test keep it
    # for local debugging; access staging admin via `kubectl port-forward`
    # if needed.
    if settings.ENVIRONMENT not in ("production", "staging"):
        patterns.insert(0, path("admin/", admin.site.urls))

    # Conditionally include graphql_graphene URLs if available.
    # Uses _LazyURLConf to defer the expensive schema import until the
    # first request to /graphql-graphene/ — avoids blocking unrelated
    # URL resolution during startup and test runs (pytest-timeout).
    if _is_graphene_django_available():
        patterns.append(
            path(
                "graphql-graphene/",
                include(_LazyURLConf("hub.apps.graphql_graphene.urls")),
            )
        )

    # Add remaining URL patterns
    patterns.extend(
        [
            path("health/", include("hub.apps.health.urls")),
            # Metrics endpoint (trailing slash canonical; Django APPEND_SLASH handles redirect)
            path("metrics/", include("hub.apps.observability.urls")),
            # CSP violation reports — unauthenticated; browsers send before scripts run.
            path("api/csp-report/", csp_report_view, name="csp-report"),
        ]
    )

    # Phase 221.4.1 + Track A PR 1 — API documentation endpoints are only
    # available outside production AND staging. Swagger UI, ReDoc, and the
    # /api-docs/-scoped OpenAPI schema expose the full API surface
    # interactively, which aids reconnaissance on any public host.
    #
    # NOTE: /api/v1/openapi.json is NOT gated — it lives in the API app's
    # URL conf and is required pre-auth by the frontend's capability
    # discovery service (capabilitiesService.ts).
    if settings.ENVIRONMENT not in ("production", "staging"):
        patterns.extend(
            [
                path(
                    "api-docs/openapi.json",
                    OpenAPISchemaView.as_view(),
                    name="openapi-schema",
                ),
                path(
                    "api-docs/",
                    SwaggerUIView.as_view(url_name="openapi-schema"),
                    name="swagger-ui",
                ),
                path(
                    "api-docs/redoc/",
                    ReDocView.as_view(url_name="openapi-schema"),
                    name="redoc",
                ),
            ]
        )

    return patterns


# Build urlpatterns at import time (standard Django contract).
urlpatterns = _build_urlpatterns()

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
