"""
Tenant URL Configuration
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

# Phase 313.1 — per-tenant SPARQL allowlist routes are a paid feature:
# the semantic app registers the ViewSet via commercial hooks; core-only
# mode has no hook and the routes do not exist.
from hub.apps.core.commercial_hooks import get_tenant_sparql_view

from .ephemeral_views import ephemeral_tenant
from .views import RateLimitConfigView, TenantConfigViewSet, TenantViewSet

router = DefaultRouter()
router.register(r"", TenantViewSet, basename="tenant")
# Register TenantConfigViewSet with router to enable @action decorators
router.register(r"config", TenantConfigViewSet, basename="tenant-config")

# Manually register TenantConfigViewSet routes to avoid URL pattern
# conflicts. IMPORTANT: me/usage/, me/config/, ephemeral/, and onboarding
# must come BEFORE include(router.urls) so they match before the router's
# <id>/ pattern (which would otherwise match "me"/"ephemeral" as a tenant id).
urlpatterns = [
    path(
        "onboarding/",
        TenantConfigViewSet.as_view({"post": "onboarding"}),
        name="tenant-onboarding",
    ),
    path("me/usage/", TenantConfigViewSet.as_view({"get": "usage"}), name="tenant-usage"),
    path(
        "me/config/",
        TenantConfigViewSet.as_view({"get": "me_config", "patch": "me_config"}),
        name="tenant-me-config",
    ),
    # Phase 250.6.E.1 — per-tenant feature-flags admin surface.
    # Manually registered (matches the convention for other
    # `me/*` routes) so the URL pattern wins over the router's
    # `<id>/` pattern that would otherwise match `me` as a UUID.
    path(
        "me/feature-flags/",
        TenantConfigViewSet.as_view({"get": "me_feature_flags", "patch": "me_feature_flags"}),
        name="tenant-me-feature-flags",
    ),
    path(
        "me/feature-flag-history/",
        TenantConfigViewSet.as_view({"get": "me_feature_flag_history"}),
        name="tenant-me-feature-flag-history",
    ),
    # Phase 270.D.3 — Tax & Billing Identity surface. Manually
    # registered (same reason as the other ``me/*`` routes — the
    # router's ``<id>/`` pattern below would otherwise try to
    # match ``me`` as a tenant UUID).
    path(
        "me/tax-id/",
        TenantConfigViewSet.as_view({"get": "me_tax_id", "post": "me_tax_id"}),
        name="tenant-me-tax-id",
    ),
    # Phase 278.B.2 — seed sample data for activation
    path(
        "me/seed-sample/",
        TenantConfigViewSet.as_view({"post": "seed_sample"}),
        name="tenant-me-seed-sample",
    ),
    # Phase 285.13.8 — self-serve plan management
    path(
        "me/plan/",
        TenantConfigViewSet.as_view({"get": "me_plan"}),
        name="tenant-me-plan",
    ),
    path(
        "me/plan/available-upgrades/",
        TenantConfigViewSet.as_view({"get": "me_plan_available_upgrades"}),
        name="tenant-me-plan-available-upgrades",
    ),
    path(
        "me/plan/upgrade/",
        TenantConfigViewSet.as_view({"post": "me_plan_upgrade"}),
        name="tenant-me-plan-upgrade",
    ),
    path(
        "me/plan/downgrade/",
        TenantConfigViewSet.as_view({"post": "me_plan_downgrade"}),
        name="tenant-me-plan-downgrade",
    ),
    path(
        "me/plan/available-ml-addons/",
        TenantConfigViewSet.as_view({"get": "me_plan_available_ml_addons"}),
        name="tenant-me-plan-available-ml-addons",
    ),
    # Phase 226 OQ4 — test-only ephemeral-tenant provisioning. Gated by
    # ENVIRONMENT + E2E_TEST_SECRET; production 404s. Cleanup runs via
    # the staging-prefix-purge cron (slug starts with `e2e-ephemeral-`).
    path("ephemeral/", ephemeral_tenant, name="tenant-ephemeral"),
    # Phase 277.B.070 — per-tenant rate limit admin
    path(
        "<uuid:tenant_id>/rate-limits/",
        RateLimitConfigView.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="tenant-rate-limits",
    ),
    path(
        "<uuid:tenant_id>/config/",
        TenantConfigViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="tenant-config-detail",
    ),
    path("", include(router.urls)),
]

# Phase 230.8 (REQ-SEM-FED-001) — per-tenant SPARQL allowlist CRUD.
# Mounted under tenants/ rather than semantic/ because the route is
# nested under <tenant_id>; the implementation lives in semantic/
# so the model + view + serializer travel together.
# Phase 313.1 — registered only when the paid semantic app provides the
# view (commercial hook). Appended AFTER the router include keeps the
# <uuid> patterns resolvable: Django resolves in order and these are more
# specific than nothing else at this level; the pre-split URLconf had them
# before the router include, and the router's terminal '' pattern only
# matches the empty remainder, so order relative to it is preserved by
# keeping these entries ahead of any catch-all.
_sparql_view = get_tenant_sparql_view()
if _sparql_view is not None:
    urlpatterns = [
        path(
            "<uuid:tenant_id>/sparql-endpoints/",
            _sparql_view.as_view(
                {"get": "list", "post": "create"},
            ),
            name="tenant-sparql-endpoint-list",
        ),
        path(
            "<uuid:tenant_id>/sparql-endpoints/<uuid:pk>/",
            _sparql_view.as_view(
                {
                    "get": "retrieve",
                    "patch": "partial_update",
                    "put": "update",
                    "delete": "destroy",
                },
            ),
            name="tenant-sparql-endpoint-detail",
        ),
    ] + urlpatterns
