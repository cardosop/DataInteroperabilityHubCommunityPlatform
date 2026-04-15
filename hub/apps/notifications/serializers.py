"""Serializers for the in-app notification inbox (Phase 223.1)."""
from rest_framework import serializers

from .models import UserNotification


class UserNotificationSerializer(serializers.ModelSerializer):
    """Read-optimised serializer for list + detail endpoints."""

    class Meta:
        model = UserNotification
        fields = [
            "id",
            "tenant",
            "user",
            "audit_event",
            "title",
            "message",
            "notification_type",
            "category",
            "resource_type",
            "resource_id",
            "read",
            "read_at",
            "created_at",
        ]
        read_only_fields = fields
