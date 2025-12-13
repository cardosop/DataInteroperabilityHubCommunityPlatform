"""
API Analytics URLs

URL configuration for API analytics endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import APIAnalyticsViewSet

router = DefaultRouter()
router.register(r'api', APIAnalyticsViewSet, basename='api-analytics')

urlpatterns = [
    path('analytics/', include(router.urls)),
]

