"""
Observability URLs

Note: The metrics endpoint is included at root level (/metrics/) in hub/urls.py
to bypass DRF authentication for Prometheus scraping. This file is included in
both root level and /api/v1/ for other observability endpoints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .otel_metrics import metrics_view
from .views import ObservabilityViewSet

router = DefaultRouter()
router.register(r"observability", ObservabilityViewSet, basename="observability")

# URL patterns for root level - includes metrics endpoint without auth
# When included via path("metrics/", include(...)), the metrics/ path is already matched
# so we just need to provide an empty string pattern to match the root of the included URLs
urlpatterns = [
    path(
        "", metrics_view, name="prometheus-metrics"
    ),  # Empty string because parent path already has 'metrics/'
    path("", include(router.urls)),
]
