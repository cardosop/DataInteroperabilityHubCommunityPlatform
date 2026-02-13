"""
GDPR URL Configuration
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from hub.apps.gdpr import views

router = DefaultRouter()
router.register(r"export-jobs", views.DataExportJobViewSet, basename="data-export-job")
router.register(r"erasure-requests", views.ErasureRequestViewSet, basename="erasure-request")

urlpatterns = [
    path("", include(router.urls)),
]
