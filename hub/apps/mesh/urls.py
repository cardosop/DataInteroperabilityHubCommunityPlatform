"""
Data Mesh URLs

URL routing for data mesh app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DomainViewSet, TopologyViewSet

router = DefaultRouter()
router.register(r'domains', DomainViewSet, basename='domain')
router.register(r'topology', TopologyViewSet, basename='topology')

urlpatterns = [
    path('', include(router.urls)),
]


