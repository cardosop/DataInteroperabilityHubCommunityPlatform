"""
Transformation URLs

URL routing for transformation app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TransformationPipelineViewSet,
    PipelineExecutionViewSet,
    PreviewResultViewSet,
    WranglingSessionViewSet
)

router = DefaultRouter()
router.register(r'pipelines', TransformationPipelineViewSet, basename='transformation-pipeline')
router.register(r'executions', PipelineExecutionViewSet, basename='transformation-execution')
router.register(r'previews', PreviewResultViewSet, basename='transformation-preview')
router.register(r'wrangling', WranglingSessionViewSet, basename='transformation-wrangling')

urlpatterns = [
    path('', include(router.urls)),
]


