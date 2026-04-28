"""
Tenant URL Configuration
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .ephemeral_views import ephemeral_tenant
from .views import TenantConfigViewSet, TenantViewSet

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
    # Phase 226 OQ4 — test-only ephemeral-tenant provisioning. Gated by
    # ENVIRONMENT + E2E_TEST_SECRET; production 404s. Cleanup runs via
    # the staging-prefix-purge cron (slug starts with `e2e-ephemeral-`).
    path("ephemeral/", ephemeral_tenant, name="tenant-ephemeral"),
    path(
        "<uuid:tenant_id>/config/",
        TenantConfigViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="tenant-config-detail",
    ),
    path("", include(router.urls)),
]
