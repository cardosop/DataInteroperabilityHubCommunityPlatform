"""
Virtualization URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VirtualDatasetViewSet, QueryExecutionViewSet, VirtualizationTopologyViewSet

router = DefaultRouter()
router.register(r"datasets", VirtualDatasetViewSet, basename="virtual-dataset")
router.register(r"queries", QueryExecutionViewSet, basename="query-execution")
router.register(r"topology", VirtualizationTopologyViewSet, basename="virtualization-topology")

urlpatterns = [
    path("", include(router.urls)),
]

