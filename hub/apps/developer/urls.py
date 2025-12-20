"""
Developer Experience URLs

URL routing for developer experience API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PluginViewSet, SDKDocumentationViewSet

router = DefaultRouter()
router.register(r'plugins', PluginViewSet, basename='plugin')
router.register(r'sdk', SDKDocumentationViewSet, basename='sdk-documentation')

urlpatterns = [
    path('', include(router.urls)),
]

