from django.urls import include, path, re_path

from .views import (
    OpenAPISchemaView,
    OpenAPIYAMLView,
    ReDocView,
    SwaggerUIView,
    api_info,
    api_not_found,
    ensure_e2e_subscription,
)

urlpatterns = [
    # API info endpoint
    path("", api_info, name="api-info"),
    # OpenAPI schema endpoints
    path("openapi.json", OpenAPISchemaView.as_view(), name="openapi-schema-v1"),
    path("openapi.yaml", OpenAPIYAMLView.as_view(), name="openapi-schema-yaml"),
    # API v1 endpoints
    path("auth/", include("hub.apps.auth.urls")),
    path("tenants/", include("hub.apps.tenants.urls")),
    path("users/", include("hub.apps.users.urls")),
    path("audit/", include("hub.apps.audit.urls")),
    path("files/", include("hub.apps.files.urls")),
    path("datasets/", include("hub.apps.datasets.urls")),
    path("jobs/", include("hub.apps.jobs.urls")),
    path("contracts/", include("hub.apps.contracts.urls")),
    path("security/", include("hub.apps.contracts.security_urls")),
    path("assets/", include("hub.apps.assets.urls")),
    path("dq/", include("hub.apps.dq.urls")),
    path("compliance/", include("hub.apps.compliance.urls")),
    path("semantic/", include("hub.apps.semantic.urls")),
    path("marketplace/", include("hub.apps.marketplace.urls")),
    path("scheduled-ingestions/", include("hub.apps.scheduled_ingestion.urls")),
    path("scheduled-exports/", include("hub.apps.scheduled_export.urls")),
    path("search/", include("hub.apps.search.urls")),
    path("developer/", include("hub.apps.developer.urls")),
    path("webhooks/", include("hub.apps.webhooks.urls")),
    path("events/", include("hub.apps.core.events.urls")),
    path("", include("hub.apps.api.analytics.urls")),
    path("governance/", include("hub.apps.governance.urls")),
    # Note: observability.urls includes /metrics/ endpoint, but metrics endpoint should NOT be under /api/v1/
    # because it needs to bypass DRF authentication for Prometheus scraping
    # Import the API v1 specific URL patterns (without metrics endpoint)
    path("", include("hub.apps.observability.urls_api_v1")),
    path("ai/", include("hub.apps.ai.urls")),
    path("", include("hub.apps.social.urls")),
    path("mesh/", include("hub.apps.mesh.urls")),
    path("virtualization/", include("hub.apps.virtualization.urls")),
    path("integrations/", include("hub.apps.integrations.urls")),
    path("baas/", include("hub.apps.baas.urls")),
    path("ml/", include("hub.apps.ml.urls")),
    path("billing/", include("hub.apps.billing.urls")),
    path("platform/", include("hub.apps.platform.urls")),
    path("versioning/", include("hub.apps.versioning.urls")),
    path("workflows/", include("hub.apps.orchestration.urls")),
    path("transformation/", include("hub.apps.api.transformation_urls")),
    path("test/ensure-e2e-subscription/", ensure_e2e_subscription, name="ensure-e2e-subscription"),
    # Catch-all for non-existent API endpoints (must be last)
    # This will only match if none of the above patterns matched
    # Use a more specific pattern that doesn't interfere with router actions
    re_path(
        r"^(?!auth/|tenants/|users/|audit/|files/|datasets/|jobs/|contracts/|assets/|dq/|compliance/|semantic/|marketplace/|scheduled-ingestions/|scheduled-exports/|search/|developer/|webhooks/|events/|mesh/|virtualization/|integrations/|baas/|ml/|billing/|platform/|versioning/|workflows/|transformation/|test/).*$",
        api_not_found,
        name="api-not-found",
    ),
]
