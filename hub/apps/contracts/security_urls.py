"""
Security URL Configuration

URL patterns for security incident management endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SecurityIncidentViewSet, SecurityAuditLogViewSet

# Security router (for /api/v1/security/)
router = DefaultRouter()
router.register(r"incidents", SecurityIncidentViewSet, basename="security-incident")
router.register(r"audit-logs", SecurityAuditLogViewSet, basename="security-audit-log")

urlpatterns = [
    path("", include(router.urls)),
]

