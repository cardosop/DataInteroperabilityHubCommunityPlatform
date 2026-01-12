"""
Compliance URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ComplianceRunViewSet

router = DefaultRouter()
router.register(r"runs", ComplianceRunViewSet, basename="compliance-run")

urlpatterns = [
    path("", include(router.urls)),
]

