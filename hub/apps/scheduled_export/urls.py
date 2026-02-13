"""
Scheduled Export URLs

URL routing for scheduled export API endpoints.
Internal worker API under internal/ (worker-only auth).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ScheduledExportRunViewSet, ScheduledExportViewSet

router = DefaultRouter()
# Register without prefix since it's already included at 'scheduled-exports/' in api/urls.py
router.register(r"", ScheduledExportViewSet, basename="scheduled-export")
router.register(r"runs", ScheduledExportRunViewSet, basename="scheduled-export-run")

urlpatterns = [
    path("internal/", include("hub.apps.scheduled_export.internal_urls")),
    path("", include(router.urls)),
]
