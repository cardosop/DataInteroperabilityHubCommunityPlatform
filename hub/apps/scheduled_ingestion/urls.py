"""
Scheduled Ingestion URLs

URL routing for scheduled ingestion API endpoints.
Internal worker API under internal/ (worker-only auth).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ScheduledIngestionRunViewSet, ScheduledIngestionViewSet

router = DefaultRouter()
# Register without prefix since it's already included at 'scheduled-ingestions/' in api/urls.py
router.register(r"", ScheduledIngestionViewSet, basename="scheduled-ingestion")
router.register(r"runs", ScheduledIngestionRunViewSet, basename="scheduled-ingestion-run")

urlpatterns = [
    path("internal/", include("hub.apps.scheduled_ingestion.internal_urls")),
    path("", include(router.urls)),
]
