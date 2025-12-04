"""
DQ URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DQRunViewSet

router = DefaultRouter()
router.register(r"dq-runs", DQRunViewSet, basename="dq-run")

# Create a second router for "runs" to match existing test URLs
runs_router = DefaultRouter()
runs_router.register(r"runs", DQRunViewSet, basename="dq-run-runs")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(runs_router.urls)),  # Also support /api/v1/dq/runs/
]

