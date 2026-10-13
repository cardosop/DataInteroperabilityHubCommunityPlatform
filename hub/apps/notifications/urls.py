"""Notification inbox URL routing (Phase 223.1)."""

from django.urls import include, path, re_path
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
    # A single regex route covers both normal and empty tokens
    # ("unsubscribe//" → token="") so the always-200 contract holds
    # without a double-slash literal in the URLconf (the URL standards
    # gate rejects consecutive slashes).
    re_path(
        r"^unsubscribe/(?P<token>[^/]*)/$",
        marketing_unsubscribe,
        name="marketing-unsubscribe",
    ),
]
