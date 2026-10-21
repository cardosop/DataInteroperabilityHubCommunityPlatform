"""
Security URL Configuration

URL patterns for security incident management endpoints.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_security import SecurityAuditLogViewSet, SecurityIncidentViewSet

# Security router (for /api/v1/security/)
router = DefaultRouter()
router.register(r"incidents", SecurityIncidentViewSet, basename="security-incident")
router.register(r"audit-logs", SecurityAuditLogViewSet, basename="security-audit-log")

urlpatterns = [
    path("", include(router.urls)),
]
