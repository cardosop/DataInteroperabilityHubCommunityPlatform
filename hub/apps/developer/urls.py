"""
Developer Experience URLs

URL routing for developer experience API endpoints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    APIKeysViewSet,
    APIUsageViewSet,
    DocumentationViewSet,
    PluginViewSet,
    PortalViewSet,
    SDKDocumentationViewSet,
)

router = DefaultRouter()
router.register(r"plugins", PluginViewSet, basename="plugin")
router.register(r"sdk", SDKDocumentationViewSet, basename="sdk-documentation")
router.register(r"documentation", DocumentationViewSet, basename="documentation")
router.register(r"portal", PortalViewSet, basename="portal")
router.register(r"api-keys", APIKeysViewSet, basename="api-keys")
router.register(r"api-usage", APIUsageViewSet, basename="api-usage")

urlpatterns = [
    path("", include(router.urls)),
]
