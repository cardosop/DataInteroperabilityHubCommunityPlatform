"""
Developer Experience Serializers

DRF serializers for developer experience API endpoints.
"""

from rest_framework import serializers

from .models import Plugin, SDKDocumentation


class PluginSerializer(serializers.ModelSerializer):
    """Serializer for Plugin model"""

    class Meta:
        model = Plugin
        fields = [
            "id",
            "name",
            "description",
            "version",
            "author",
            "category",
            "status",
            "download_count",
            "rating",
            "metadata_json",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "download_count", "created_at", "updated_at"]


class SDKDocumentationSerializer(serializers.ModelSerializer):
    """Serializer for SDK Documentation model"""

    class Meta:
        model = SDKDocumentation
        fields = [
            "id",
            "language",
            "version",
            "documentation",
            "installation",
            "quick_start",
            "examples_json",
            "api_reference_json",
            "documentation_url",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
