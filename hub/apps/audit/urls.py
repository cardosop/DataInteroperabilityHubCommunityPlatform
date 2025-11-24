"""
Audit URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuditEventViewSet

router = DefaultRouter()
router.register(r"audit-events", AuditEventViewSet, basename="audit-event")

urlpatterns = [
    path("", include(router.urls)),
]

