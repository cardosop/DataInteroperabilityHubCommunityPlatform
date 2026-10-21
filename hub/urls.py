"""
URL configuration for hub project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from hub.apps.api.views import OpenAPISchemaView, ReDocView, SwaggerUIView
from hub.apps.security.views import csp_report_view


def _build_urlpatterns() -> list:
    """
    Build the root URL patterns list.

    Extracted into a function so that Phase 221.2.1 production guards and
    their tests can evaluate the conditional admin registration without
    module-reload tricks.

    Returns:
        Complete list of URL patterns for ROOT_URLCONF.
    """
    patterns = []

    # Phase 313.1 — paid-layer prefixes (semantic, marketplace, billing, baas,
    # ai, ml, social, graphql, graphql-graphene) register from their
    # AppConfig.ready() into hub.apps.api.paid_urls. Absent in core-only mode.
    # Mounted FIRST (before the api/v1 catch-all) so paid paths resolve before
    # api_not_found in the core URLconf.
    if not settings.HUB_CORE_ONLY:
        patterns.append(path("", include("hub.apps.api.paid_urls")))

    patterns.extend(
        [
            path("api/v1/", include("hub.apps.api.urls")),
            # Phase 18.3 — unified FTS endpoint querying Asset/Contract search_vector
            path("api/search/", include("hub.apps.search.search_urls")),
        ]
    )

    # Phase 221.2.1 + Track A PR 1 — Django admin is only available outside
    # production AND staging. Staging is publicly reachable, so exposing
    # /admin/ there is the same attack surface as prod. Dev / test keep it
    # for local debugging; access staging admin via `kubectl port-forward`
    # if needed.
    if settings.ENVIRONMENT not in ("production", "staging"):
        patterns.insert(0, path("admin/", admin.site.urls))

    # graphql_graphene (paid) registers "graphql-graphene/" itself in
    # AppConfig.ready() via hub.apps.api.paid_urls — Phase 313.1. The
    # LazyURLConf wrapper (also moved to paid_urls) keeps the deferred
    # schema import behaviour.

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
