"""In-app notification views (Phase 223.1).

Thin, tenant-scoped endpoints exposing `UserNotification` rows for the
currently authenticated user. Writes are intentionally limited to the
``read``/``read-all`` actions — notifications are produced by backend
flows (governance, marketplace, jobs, contracts) via
`utils.create_user_notification`, never by clients.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from hub.apps.api.standards.pagination import StandardPageNumberPagination

from .models import UserNotification
from .serializers import UserNotificationSerializer


class UserNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """List & mark-as-read endpoints for the current user's inbox."""

    serializer_class = UserNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPageNumberPagination
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        queryset = UserNotification.objects.filter(user=user)

        # Tenant isolation: if the user has a tenant, constrain the row
        # set — protects against stale notifications from a prior tenant
        # if the same user had one. Platform admins see only their own
        # notifications too (this is a personal inbox, not an audit tool).
        tenant = getattr(user, "tenant", None)
        if tenant is not None:
            queryset = queryset.filter(tenant=tenant)

        # Optional filters — both kept narrow to avoid accidental leakage.
        read_param = self.request.query_params.get("read")
        if read_param in ("true", "false"):
            queryset = queryset.filter(read=read_param == "true")

        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category.upper())

        return queryset

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """Return the unread count for the badge.

        GET /api/v1/notifications/user-notifications/unread-count/
        """
        count = self.get_queryset().filter(read=False).count()
        return Response({"count": count}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, id=None):
        """Mark a single notification as read.

        POST /api/v1/notifications/user-notifications/{id}/read/
        Idempotent — marking an already-read row is a no-op.
        """
        notification = self.get_object()
        notification.mark_read()
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        """Mark every unread notification for this user as read.

        POST /api/v1/notifications/user-notifications/read-all/
        Returns the number of rows flipped.
        """
        with transaction.atomic():
            updated = (
                self.get_queryset()
                .filter(read=False)
                .update(read=True, read_at=timezone.now())
            )
        return Response({"updated": updated}, status=status.HTTP_200_OK)
