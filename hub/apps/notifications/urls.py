"""Notification inbox URL routing (Phase 223.1)."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .stream_views import NotificationStreamView
from .views import UserNotificationViewSet, marketing_unsubscribe

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
    # Phase 277.B.097 — 1-click marketing unsubscribe.
    # The empty-token catch-all ensures short / missing tokens still
    # reach the view (always-200 contract prevents enumeration).
    path(
        "unsubscribe/<str:token>/",
        marketing_unsubscribe,
        name="marketing-unsubscribe",
    ),
    # Catch empty token with trailing slash (// → token="")
    path(
        "unsubscribe//",
        marketing_unsubscribe,
        kwargs={"token": ""},
        name="marketing-unsubscribe-empty-token",
    ),
]
