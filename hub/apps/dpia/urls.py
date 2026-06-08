"""API routes for DPIA register — Phase 232.5."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from hub.apps.dpia.views import DpiaViewSet

router = DefaultRouter()
router.register(r"records", DpiaViewSet, basename="dpia-record")

urlpatterns = [
    path("", include(router.urls)),
]
