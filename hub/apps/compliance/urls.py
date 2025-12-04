"""
Compliance URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ComplianceRunViewSet

router = DefaultRouter()
router.register(r"compliance-runs", ComplianceRunViewSet, basename="compliance-run")

urlpatterns = [
    path("", include(router.urls)),
    # Also register as "runs" for backward compatibility with existing tests
    # This allows both /api/v1/compliance/compliance-runs/ and /api/v1/compliance/runs/ to work
    path("runs/", ComplianceRunViewSet.as_view({"get": "list", "post": "create"}), name="compliance-run-list"),
    path("runs/<uuid:id>/", ComplianceRunViewSet.as_view({"get": "retrieve"}), name="compliance-run-detail"),
]

