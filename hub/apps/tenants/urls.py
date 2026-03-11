"""
Tenant URL Configuration
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TenantConfigViewSet, TenantViewSet

router = DefaultRouter()
router.register(r"", TenantViewSet, basename="tenant")
# Register TenantConfigViewSet with router to enable @action decorators
router.register(r"config", TenantConfigViewSet, basename="tenant-config")

# Manually register TenantConfigViewSet routes to avoid URL pattern conflicts.
# IMPORTANT: me/usage/, me/config/, and onboarding must come BEFORE include(router.urls)
# so they match before the router's <id>/ pattern (which would otherwise match "me" as tenant id).
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
    path(
        "<uuid:tenant_id>/config/",
        TenantConfigViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="tenant-config-detail",
    ),
    path("", include(router.urls)),
]
