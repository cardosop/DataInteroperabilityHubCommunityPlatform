"""
DQ URL Configuration

Standardized to use 'runs' pattern for consistency with API naming standards.
This follows the plural resources rule and avoids duplication (no 'dq/dq-runs').
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DQRunViewSet

router = DefaultRouter()
router.register(r"runs", DQRunViewSet, basename="dq-run")

urlpatterns = [
    path("", include(router.urls)),
]

