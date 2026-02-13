"""
User URL Configuration
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from hub.apps.gdpr.views import DataExportJobViewSet, ErasureRequestViewSet

from .views import RoleViewSet, UserViewSet

router = DefaultRouter()
router.register(r"", UserViewSet, basename="user")
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"me/export-jobs", DataExportJobViewSet, basename="data-export-job")
router.register(r"me/erasure-requests", ErasureRequestViewSet, basename="erasure-request")

urlpatterns = [
    path("", include(router.urls)),
]
