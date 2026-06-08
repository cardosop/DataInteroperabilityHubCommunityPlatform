"""Serializers for warehouse connections and ACLs (Phase 275)."""
from rest_framework import serializers

from .models import WarehouseConnection, WarehouseConnectionACL, WarehouseType


class WarehouseConnectionSerializer(serializers.ModelSerializer):
    """Read/write serializer. ``config`` is write-only for security."""
    warehouse_type_display = serializers.CharField(
        source="get_warehouse_type_display", read_only=True,
    )

    class Meta:
        model = WarehouseConnection
        fields = [
            "id", "tenant", "name", "warehouse_type",
            "warehouse_type_display", "config", "region",
            "private_endpoint_url", "is_active",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]
        extra_kwargs = {
            "config": {"write_only": True},
        }


class WarehouseConnectionCreateSerializer(serializers.ModelSerializer):
    """Creation-only serializer with explicit warehouse_type validation."""
    class Meta:
        model = WarehouseConnection
        fields = [
            "name", "warehouse_type", "config", "region",
            "private_endpoint_url", "is_active",
        ]

    def validate_warehouse_type(self, value):
        valid = [c[0] for c in WarehouseType.choices]
        if value not in valid:
            raise serializers.ValidationError(
                f"Invalid warehouse type '{value}'. Valid: {valid}"
            )
        return value


class WarehouseConnectionTestResultSerializer(serializers.Serializer):
    """Response shape for the connection-test endpoint."""
    success = serializers.BooleanField()
    latency_ms = serializers.FloatField(required=False)
    warehouse_type = serializers.CharField()
    error = serializers.CharField(required=False)
    tested_at = serializers.DateTimeField(required=False)


class WarehouseConnectionACLSerializer(serializers.ModelSerializer):
    class Meta:
        model = WarehouseConnectionACL
        fields = ["id", "tenant", "connection", "user", "role", "created_at"]
        read_only_fields = ["id", "tenant", "created_at"]
