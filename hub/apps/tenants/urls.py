"""
Tenant URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantViewSet, TenantConfigViewSet

router = DefaultRouter()
router.register(r"tenants", TenantViewSet, basename="tenant")

# Manually register TenantConfigViewSet routes to avoid URL pattern conflicts
# The router would try to add detail routes which conflict with our custom pattern
urlpatterns = [
    path("", include(router.urls)),
    path(
        "tenants/<uuid:tenant_id>/config/",
        TenantConfigViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="tenant-config-detail"
    ),
]

