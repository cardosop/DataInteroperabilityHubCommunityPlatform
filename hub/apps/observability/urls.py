"""
Observability URLs
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ObservabilityViewSet
from .otel_metrics import metrics_view

router = DefaultRouter()
router.register(r'observability', ObservabilityViewSet, basename='observability')

urlpatterns = [
    path('metrics/', metrics_view, name='prometheus-metrics'),
    path('', include(router.urls)),
]

