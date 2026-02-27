"""
API Analytics URLs

URL configuration for API analytics endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import APIAnalyticsViewSet, CostsViewSet

router = DefaultRouter()
router.register(r'api', APIAnalyticsViewSet, basename='api-analytics')
router.register(r'costs', CostsViewSet, basename='costs')

urlpatterns = [
    path('analytics/', include(router.urls)),
]

