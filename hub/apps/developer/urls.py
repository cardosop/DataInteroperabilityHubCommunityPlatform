"""
Developer Experience URLs

URL routing for developer experience API endpoints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    APIKeysViewSet,
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
# NOTE: ``api-usage`` is intentionally NOT registered here (Phase 313 D2).
# The real APIUsageViewSet lives in the paid BaaS app; registering the
# placeholder under the same basename shadowed it and made
# ``reverse("api-usage-list")`` resolve to a stub.

urlpatterns = [
    path("", include(router.urls)),
]
