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

# Manually register TenantConfigViewSet routes to avoid URL pattern conflicts
# The router would try to add detail routes which conflict with our custom pattern
urlpatterns = [
    path("", include(router.urls)),
    path(
        "tenants/<uuid:tenant_id>/config/",
        TenantConfigViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="tenant-config-detail",
    ),
    path("me/usage/", TenantConfigViewSet.as_view({"get": "usage"}), name="tenant-usage"),
]
