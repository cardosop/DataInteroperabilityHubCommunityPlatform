"""
Job URL Configuration
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FailedJobDLQViewSet, JobViewSet

router = DefaultRouter()
router.register(r"dlq", FailedJobDLQViewSet, basename="dlq")
router.register(r"", JobViewSet, basename="job")

urlpatterns = [
    path("", include(router.urls)),
]
