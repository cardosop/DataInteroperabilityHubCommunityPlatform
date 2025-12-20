"""
File Storage Serializers
"""
from rest_framework import serializers
from .models import File, FileStatus
from .validators import validate_file_size, validate_file_type, get_chunk_size, calculate_chunk_count


class FileInitSerializer(serializers.Serializer):
    """Serializer for file upload initialization"""
    name = serializers.CharField(max_length=255, help_text="Original filename")
    content_type = serializers.CharField(max_length=100, help_text="MIME type")
    size = serializers.IntegerField(min_value=0, help_text="File size in bytes (0 for empty files)")
    upload_method = serializers.ChoiceField(
        choices=["browser", "sdk"],
        default="browser",
        help_text="Upload method: browser or sdk"
    )

    def validate(self, data):
        """Validate file size and type"""
        size = data['size']
        upload_method = data.get('upload_method', 'browser')
        name = data['name']
        content_type = data.get('content_type')

        # Validate file size
        validate_file_size(size, upload_method)

        # Validate file type
        validate_file_type(name, content_type)

        return data


class FileInitResponseSerializer(serializers.Serializer):
    """Serializer for file upload initialization response"""
    file_id = serializers.UUIDField()
    upload_url = serializers.URLField()
    fields = serializers.DictField()
    chunk_size = serializers.IntegerField(required=False, help_text="Recommended chunk size for multipart upload")
    chunk_count = serializers.IntegerField(required=False, help_text="Number of chunks for multipart upload")
    requires_multipart = serializers.BooleanField(help_text="Whether multipart upload is required")
    upload_id = serializers.CharField(required=False, help_text="Multipart upload ID (for multipart uploads only)")


class FileCompleteSerializer(serializers.Serializer):
    """Serializer for file upload completion"""
    content_sha256 = serializers.CharField(
        max_length=64,
        help_text="SHA-256 hash of uploaded file content (for verification)"
    )
    parts = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        help_text="List of parts for multipart upload (ETag and PartNumber)"
    )


class FileSerializer(serializers.ModelSerializer):
    """Serializer for File model"""

    class Meta:
        model = File
        fields = [
            'id',
            'name',
            'content_type',
            'size',
            'content_sha256',
            'status',
            'metadata_json',
            'created_by',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'content_sha256',
            'status',
            'metadata_json',
            'created_by',
            'created_at',
            'updated_at'
        ]


class FileDownloadResponseSerializer(serializers.Serializer):
    """Serializer for file download response"""
    download_url = serializers.URLField()
    expires_in = serializers.IntegerField(help_text="URL expiration time in seconds")
    filename = serializers.CharField()


class ChunkUploadInitSerializer(serializers.Serializer):
    """Serializer for chunked upload initialization"""
    # file_id is not required here - it's in the URL path
    chunk_number = serializers.IntegerField(min_value=1)
    chunk_size = serializers.IntegerField(min_value=1)


class ChunkUploadResponseSerializer(serializers.Serializer):
    """Serializer for chunk upload response"""
    upload_url = serializers.URLField()
    expires_in = serializers.IntegerField()

