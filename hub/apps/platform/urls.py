"""
Platform Admin URL Configuration
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from hub.apps.platform import views

router = DefaultRouter()
router.register(r"tenants", views.PlatformTenantViewSet, basename="platform-tenant")
router.register(r"users", views.PlatformUserViewSet, basename="platform-user")

urlpatterns = [
    path("", include(router.urls)),
]
