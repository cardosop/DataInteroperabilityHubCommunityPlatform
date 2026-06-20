"""
File Storage Serializers
"""

from rest_framework import serializers

from .models import File
from .validators import validate_filename

from .metadata_validators import validate_metadata_json_size


class FileInitSerializer(serializers.Serializer):
    """Serializer for file upload initialization.

    Validates only field presence and format. Domain validation (file size,
    file type, storage quota) is done in FileService via FilesBusinessRules
    so that REST and workflows share the same rules and return 400 with
    code BUSINESS_RULES_VALIDATION on invalid.
    """

    name = serializers.CharField(max_length=255, help_text="Original filename")
    content_type = serializers.CharField(max_length=100, help_text="MIME type")
    size = serializers.IntegerField(min_value=0, help_text="File size in bytes (0 for empty files)")
    upload_method = serializers.ChoiceField(
        choices=["browser", "sdk"], default="browser", help_text="Upload method: browser or sdk"
    )

    def validate(self, data):
        """Structural validation only; domain rules run in FileService."""
        # 14.7: path traversal prevention – sanitise and validate the filename.
        if "name" in data:
            data["name"] = validate_filename(data["name"])
        return data


class FileInitResponseSerializer(serializers.Serializer):
    """Serializer for file upload initialization response"""

    file_id = serializers.UUIDField()
    upload_url = serializers.URLField()
    fields = serializers.DictField()
    chunk_size = serializers.IntegerField(
        required=False, help_text="Recommended chunk size for multipart upload"
    )
    chunk_count = serializers.IntegerField(
        required=False, help_text="Number of chunks for multipart upload"
    )
    requires_multipart = serializers.BooleanField(help_text="Whether multipart upload is required")
    upload_id = serializers.CharField(
        required=False, help_text="Multipart upload ID (for multipart uploads only)"
    )


class FileCompleteSerializer(serializers.Serializer):
    """Serializer for file upload completion"""

    content_sha256 = serializers.CharField(
        max_length=64, help_text="SHA-256 hash of uploaded file content (for verification)"
    )
    parts = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        help_text="List of parts for multipart upload (ETag and PartNumber)",
    )


class FileSerializer(serializers.ModelSerializer):
    """Serializer for File model"""

    class Meta:
        model = File
        fields = [
            "id",
            "name",
            "content_type",
            "size",
            "content_sha256",
            "status",
            "scan_status",
            "scanned_at",
            "metadata_json",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "content_sha256",
            "status",
            "scan_status",
            "scanned_at",
            "metadata_json",
            "created_by",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "metadata_json": {
                "validators": [validate_metadata_json_size],
            },
        }

    def validate(self, data):
        # 14.7: path traversal prevention – sanitise and validate the filename.
        if "name" in data:
            data["name"] = validate_filename(data["name"])
        return data


class FileDownloadResponseSerializer(serializers.Serializer):
    """Serializer for file download response"""

    download_url = serializers.URLField()
    expires_in = serializers.IntegerField(help_text="URL expiration time in seconds")
    filename = serializers.CharField()
    content_sha256 = serializers.CharField(
        required=False, allow_null=True, help_text="SHA-256 hash of file content"
    )


class ChunkUploadInitSerializer(serializers.Serializer):
    """Serializer for chunked upload initialization"""

    # file_id is not required here - it's in the URL path
    chunk_number = serializers.IntegerField(min_value=1)
    chunk_size = serializers.IntegerField(min_value=1)


class ChunkUploadResponseSerializer(serializers.Serializer):
    """Serializer for chunk upload response"""

    upload_url = serializers.URLField()
    expires_in = serializers.IntegerField()


class ChecksumMismatchSerializer(serializers.Serializer):
    """Serializer for the download checksum-mismatch audit endpoint."""

    actual_sha256 = serializers.CharField(max_length=64, min_length=64)


class FileRenameSerializer(serializers.Serializer):
    """Serializer for file rename endpoint."""

    name = serializers.CharField(max_length=255)
