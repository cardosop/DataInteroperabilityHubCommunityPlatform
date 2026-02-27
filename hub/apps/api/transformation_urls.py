"""Transformation pipelines placeholder URLs."""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .transformation_views import (
    TransformationAuditViewSet,
    TransformationExecutionViewSet,
    TransformationPipelineViewSet,
)

router = DefaultRouter()
router.register(r"pipelines", TransformationPipelineViewSet, basename="transformation-pipeline")
router.register(r"executions", TransformationExecutionViewSet, basename="transformation-execution")
router.register(r"audit", TransformationAuditViewSet, basename="transformation-audit")

urlpatterns = [
    path("", include(router.urls)),
]
