"""
Virtualization URL Configuration
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import QueryExecutionViewSet, VirtualDatasetViewSet, VirtualizationTopologyViewSet

router = DefaultRouter()
router.register(r"datasets", VirtualDatasetViewSet, basename="virtual-dataset")
router.register(r"queries", QueryExecutionViewSet, basename="query-execution")
router.register(r"topology", VirtualizationTopologyViewSet, basename="virtualization-topology")

urlpatterns = [
    path("", include(router.urls)),
]
