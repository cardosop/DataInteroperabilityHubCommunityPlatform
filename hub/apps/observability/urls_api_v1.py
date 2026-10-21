"""
Observability URLs for API v1

This file provides URL patterns for API v1 that exclude the metrics endpoint.
The metrics endpoint should be accessed via root /metrics/ to bypass DRF authentication.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ObservabilityViewSet

router = DefaultRouter()
router.register(r"observability", ObservabilityViewSet, basename="observability")

urlpatterns = [
    # Only include router URLs, not metrics endpoint
    # Metrics endpoint should be accessed via root /metrics/ to bypass DRF auth
    path("", include(router.urls)),
]
