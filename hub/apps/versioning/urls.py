"""
Versioning API URL configuration.

Mounted at /api/v1/versioning/ in hub.apps.api.urls.
Endpoints: GET /versioning/versions/, GET /versioning/versions/<id>/, GET /versioning/compare/.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import VersioningViewSet

router = DefaultRouter()
router.register(r"versions", VersioningViewSet, basename="versioning-version")

urlpatterns = [
    path(
        "compare/", VersioningViewSet.as_view(actions={"get": "compare"}), name="versioning-compare"
    ),
    path("", include(router.urls)),
]
