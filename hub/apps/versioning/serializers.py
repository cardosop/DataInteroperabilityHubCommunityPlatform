"""
Versioning API serializers.

Read-only representations for list version, get version, and compare.
"""

from rest_framework import serializers


class VersionListEntrySerializer(serializers.Serializer):
    """One entry in the list versions response."""

    id = serializers.UUIDField(read_only=True)
    resource_type = serializers.ChoiceField(choices=["contract", "dataset"], read_only=True)
    version = serializers.IntegerField(read_only=True)
    semantic_version = serializers.CharField(allow_null=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    is_current = serializers.BooleanField(allow_null=True, read_only=True)


class VersionDetailSerializer(serializers.Serializer):
    """Single version detail (get version by id)."""

    id = serializers.UUIDField(read_only=True)
    resource_type = serializers.ChoiceField(choices=["contract", "dataset"], read_only=True)
    version = serializers.IntegerField(read_only=True)
    semantic_version = serializers.CharField(allow_null=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    is_current = serializers.BooleanField(allow_null=True, read_only=True)
    # Optional extra for contracts
    status = serializers.CharField(allow_null=True, read_only=True)
    original_spec_version = serializers.CharField(allow_null=True, read_only=True)


class VersionCompareSerializer(serializers.Serializer):
    """Compare two versions response."""

    id_a = serializers.UUIDField(read_only=True)
    id_b = serializers.UUIDField(read_only=True)
    resource_type = serializers.ChoiceField(choices=["contract", "dataset"], read_only=True)
    version_a = serializers.IntegerField(read_only=True)
    version_b = serializers.IntegerField(read_only=True)
    created_at_a = serializers.DateTimeField(read_only=True)
    created_at_b = serializers.DateTimeField(read_only=True)
