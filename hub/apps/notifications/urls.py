"""Notification inbox URL routing (Phase 223.1)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import UserNotificationViewSet

router = DefaultRouter()
router.register(
    r"user-notifications",
    UserNotificationViewSet,
    basename="user-notification",
)

urlpatterns = [
    path("", include(router.urls)),
]
