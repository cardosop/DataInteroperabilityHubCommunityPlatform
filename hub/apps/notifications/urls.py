"""Notification inbox URL routing (Phase 223.1)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .stream_views import NotificationStreamView
from .views import UserNotificationViewSet

router = DefaultRouter()
router.register(
    r"user-notifications",
    UserNotificationViewSet,
    basename="user-notification",
)

urlpatterns = [
    path("", include(router.urls)),
    # Phase 228.F3.16 (REQ-LIN-F3-006) — Server-Sent Events.
    path(
        "stream/",
        NotificationStreamView.as_view(),
        name="notification-stream",
    ),
]
