"""
Data Mesh URLs

URL routing for data mesh app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DomainViewSet, MeshGovernanceViewSet, TopologyViewSet

router = DefaultRouter()
router.register(r'domains', DomainViewSet, basename='domain')
router.register(r'topology', TopologyViewSet, basename='topology')
router.register(r'governance', MeshGovernanceViewSet, basename='mesh-governance')

urlpatterns = [
    path('', include(router.urls)),
]


