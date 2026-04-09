"""
S3-Compatible Storage Utilities

Utilities for interacting with S3-compatible storage (MinIO, S3, GCS, Azure).
"""
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError
from django.conf import settings
from typing import Optional, Dict, Any
from datetime import timedelta


class S3StorageClient:
    """
    Client for S3-compatible storage operations.

    Supports MinIO (dev) and AWS S3, GCS, Azure (prod).
    """

    def __init__(self):
        """Initialize S3 client with configuration from settings"""
        import os
        import sys

        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        # Check environment variable first (highest priority)
        env_endpoint = os.getenv('AWS_S3_ENDPOINT_URL')
        if env_endpoint:
            self.endpoint_url = env_endpoint
        else:
            # Use settings value (may be None when running against native AWS S3
            # in staging/production — settings.py deliberately leaves it unset
            # so boto3 signs URLs against `<bucket>.s3.<region>.amazonaws.com`,
            # which is browser-reachable and IRSA-authenticated).
            self.endpoint_url = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)

            # If endpoint from settings doesn't work, try to detect correct one.
            # Skip the localhost-fallback chain when endpoint_url is None: that
            # is the explicit "use native AWS S3" signal, and falling back to
            # http://localhost:9000 here is exactly what broke staging uploads
            # before — the api pod has no MinIO on loopback, and even if it did,
            # the resulting presigned URL is unreachable from browsers.
            if self.endpoint_url:
                # Try to verify the endpoint hostname is resolvable
                import socket
                from urllib.parse import urlparse
                hostname_resolved = True
                try:
                    parsed = urlparse(self.endpoint_url)
                    host = parsed.hostname
                    if host and host != 'localhost':
                        # Try to resolve hostname
                        socket.gethostbyname(host)
                except (socket.gaierror, Exception):
                    hostname_resolved = False

                if not hostname_resolved:
                    # Hostname doesn't resolve, try alternatives.
                    # NOTE: previously the `is_in_docker` / `is_test_env` definitions lived
                    # inside the except block but the `if is_in_docker:` branch lived OUTSIDE
                    # it at the same indent as try/except. When DNS resolved successfully the
                    # code still hit the `if is_in_docker:` line and raised UnboundLocalError,
                    # which surfaced in production as:
                    #   "cannot access local variable 'is_in_docker' where it is not associated with a value"
                    # in the file-upload code path on staging. Fixed by gating the entire
                    # alternative-endpoint resolution on `not hostname_resolved` so the
                    # variables are only read when they are actually defined.
                    is_in_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER') == 'true'
                    is_test_env = (
                        'pytest' in sys.modules or
                        'unittest' in sys.modules or
                        os.getenv('PYTEST_CURRENT_TEST') or
                        'test' in sys.argv or
                        os.getenv('ENVIRONMENT') == 'test'
                    )

                    if is_in_docker:
                        # In Docker, use service name first (works within Docker network)
                        try:
                            socket.gethostbyname('minio')
                            # Service name resolves, use it
                            self.endpoint_url = 'http://minio:9000'
                        except (socket.gaierror, Exception):
                            # Service name doesn't resolve, use localhost
                            if is_test_env:
                                self.endpoint_url = 'http://localhost:9010'  # Test port
                            else:
                                self.endpoint_url = 'http://localhost:9000'  # Dev port
                    else:
                        # Outside Docker, use localhost
                        self.endpoint_url = 'http://localhost:9000'
            else:
                # No endpoint set, use defaults
                is_in_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER') == 'true'
                is_test_env = (
                    'pytest' in sys.modules or
                    'unittest' in sys.modules or
                    os.getenv('PYTEST_CURRENT_TEST') or
                    'test' in sys.argv
                )

                if is_in_docker:
                    # In Docker, use service name first (works within Docker network)
                    try:
                        import socket
                        socket.gethostbyname('minio')
                        # Service name resolves, use it
                        self.endpoint_url = 'http://minio:9000'  # Use service name in Docker
                    except (socket.gaierror, Exception):
                        # Service name doesn't resolve, use localhost
                        if is_test_env:
                            self.endpoint_url = 'http://localhost:9010'  # Test port
                        else:
                            self.endpoint_url = 'http://localhost:9000'  # Dev port
                else:
                    # Outside Docker, use localhost
                    self.endpoint_url = 'http://localhost:9000'

        self.use_ssl = getattr(settings, 'AWS_S3_USE_SSL', True)

        # Create S3 client. In test, use timeouts that allow slow MinIO (e.g. Docker/CI)
        # without hanging indefinitely; in prod use standard values.
        import os as _os
        _is_test = (
            'pytest' in sys.modules or
            'unittest' in sys.modules or
            _os.getenv('PYTEST_CURRENT_TEST') or
            'test' in sys.argv or
            getattr(settings, 'TESTING', False)
        )
        _connect_timeout = 10 if _is_test else 60
        _read_timeout = 30 if _is_test else 60
        s3_config = Config(
            signature_version='s3v4',
            retries={'max_attempts': 2 if _is_test else 3, 'mode': 'standard'},
            connect_timeout=_connect_timeout,
            read_timeout=_read_timeout,
        )

        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            use_ssl=self.use_ssl,
            verify=getattr(settings, 'AWS_S3_VERIFY', True),
            config=s3_config
        )

        # Don't check bucket in __init__ - check lazily when needed
        self._bucket_checked = False
        self._original_endpoint = self.endpoint_url  # Store original for fallback

    def _ensure_bucket_exists(self):
        """Ensure the bucket exists, create it if it doesn't."""
        import os
        import sys

        try:
            # Try to check if bucket exists
            self.client.head_bucket(Bucket=self.bucket_name)
        except (ClientError, EndpointConnectionError, Exception) as e:
            # If connection fails due to hostname resolution, try alternative endpoints
            error_str = str(e).lower()
            is_connection_error = (
                isinstance(e, EndpointConnectionError) or
                'name resolution' in error_str or
                'could not connect' in error_str or
                'gaierror' in error_str
            )
            if is_connection_error:
                # Hostname doesn't resolve, try alternative endpoints
                is_in_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER') == 'true'
                is_test_env = (
                    'pytest' in sys.modules or
                    'unittest' in sys.modules or
                    os.getenv('PYTEST_CURRENT_TEST') or
                    'test' in sys.argv
                )

                if is_in_docker:
                    # Try alternative endpoints in order: test service name, then dev, then localhost
                    alternative_endpoints = []
                    if is_test_env:
                        # In test environment (docker-compose.test: minio-test), try both names and ports
                        alternative_endpoints = [
                            'http://minio-test:9000',
                            'http://minio:9000',
                            'http://localhost:9010',
                            'http://localhost:9000',
                        ]
                    else:
                        # In dev environment, try service name first, then localhost
                        alternative_endpoints = ['http://minio:9000', 'http://localhost:9000']

                    for alt_endpoint in alternative_endpoints:
                        if self.endpoint_url == alt_endpoint:
                            continue  # Already tried this endpoint
                        try:
                            self.endpoint_url = alt_endpoint
                            # Recreate client with new endpoint
                            s3_config = Config(
                                signature_version='s3v4',
                                retries={'max_attempts': 3, 'mode': 'standard'}
                            )
                            self.client = boto3.client(
                                's3',
                                endpoint_url=self.endpoint_url,
                                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                use_ssl=self.use_ssl,
                                verify=getattr(settings, 'AWS_S3_VERIFY', True),
                                config=s3_config
                            )
                            # Retry bucket check with new endpoint
                            try:
                                self.client.head_bucket(Bucket=self.bucket_name)
                                # Successfully connected, return
                                return
                            except (ClientError, EndpointConnectionError) as retry_error:
                                # Try to create bucket
                                try:
                                    self.client.create_bucket(Bucket=self.bucket_name)
                                    # Successfully created bucket, return
                                    return
                                except (ClientError, EndpointConnectionError):
                                    # This endpoint also failed, try next one
                                    continue
                        except Exception:
                            # Failed to create client with this endpoint, try next
                            continue
                    # All endpoints failed, keep original endpoint (will fail with clear error)
                    self.endpoint_url = self._original_endpoint

            # Handle bucket creation for other errors
            error_code = ''
            if isinstance(e, ClientError):
                error_code = e.response.get('Error', {}).get('Code', '')

            if error_code == '404' or error_code == 'NoSuchBucket':
                # Bucket doesn't exist, try to create it
                try:
                    if self.endpoint_url:
                        # MinIO or S3-compatible storage
                        self.client.create_bucket(Bucket=self.bucket_name)
                    else:
                        # AWS S3 - may need region
                        region = getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
                        self.client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': region}
                        )
                except ClientError as create_error:
                    # Bucket might already exist (race condition) or we don't have permissions
                    # Try to verify it exists now
                    try:
                        self.client.head_bucket(Bucket=self.bucket_name)
                    except ClientError:
                        # Still doesn't exist and we can't create it
                        # This is OK - operations will fail with clear error messages
                        pass
            # Other errors (403, etc.) are OK - we'll get clear error messages when using the bucket

    def generate_presigned_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in: int = 3600,
        max_size: Optional[int] = None,
        use_put: bool = True,
        for_browser: bool = False
    ) -> Dict[str, Any]:
        """
        Generate pre-signed URL for file upload.

        Args:
            key: S3 object key (path)
            content_type: MIME type of the file
            expires_in: URL expiration time in seconds (default: 1 hour)
            max_size: Maximum file size in bytes (optional, for validation)
            use_put: If True, generate PUT URL (simpler, for direct uploads). If False, generate POST URL with fields.
            for_browser: If True, use localhost endpoint (browser can't resolve Docker service names)

        Returns:
            Dictionary with upload_url and fields (empty dict for PUT, populated for POST)
        """
        try:
            # Ensure bucket exists before generating URL (avoids 404 on PUT from browser)
            if not self._bucket_checked:
                self._ensure_bucket_exists()
                self._bucket_checked = True

            # For browser uploads, create a temporary client with localhost endpoint
            # This ensures the presigned URL is signed with the correct host
            # (browser runs on host; can't resolve Docker service names like minio/minio-test)
            client_to_use = self.client
            browser_endpoint = None
            if for_browser and self.endpoint_url:
                import os
                if 'minio-test:9000' in self.endpoint_url:
                    # Test stack: minio-test exposed on host as localhost:9010
                    port = os.getenv('MINIO_TEST_API_PORT', '9010')
                    browser_endpoint = self.endpoint_url.replace('minio-test:9000', f'localhost:{port}')
                elif 'minio:9000' in self.endpoint_url:
                    browser_endpoint = self.endpoint_url.replace('minio:9000', 'localhost:9000')
            if browser_endpoint:
                import boto3
                from botocore.config import Config
                s3_config = Config(
                    signature_version='s3v4',
                    s3={'addressing_style': 'path'},
                    retries={'max_attempts': 3, 'mode': 'standard'}
                )
                browser_client = boto3.client(
                    's3',
                    endpoint_url=browser_endpoint,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    use_ssl=self.use_ssl,
                    verify=getattr(settings, 'AWS_S3_VERIFY', True),
                    config=s3_config
                )
                client_to_use = browser_client
            
            if use_put:
                # Generate presigned PUT URL (simpler, for direct browser uploads)
                upload_url = client_to_use.generate_presigned_url(
                    'put_object',
                    Params={
                        'Bucket': self.bucket_name,
                        'Key': key,
                        'ContentType': content_type,
                    },
                    ExpiresIn=expires_in
                )
                return {
                    'upload_url': upload_url,
                    'fields': {},  # Not used for PUT
                    'key': key
                }
            else:
                # Generate presigned POST URL (with fields, for form-based uploads)
                conditions = [
                    {'Content-Type': content_type}
                ]
                if max_size:
                    conditions.append(['content-length-range', 1, max_size])

                presigned_post = client_to_use.generate_presigned_post(
                    Bucket=self.bucket_name,
                    Key=key,
                    Fields={'Content-Type': content_type},
                    Conditions=conditions,
                    ExpiresIn=expires_in
                )

                return {
                    'upload_url': presigned_post['url'],
                    'fields': presigned_post['fields'],
                    'key': key
                }
        except ClientError as e:
            raise Exception(f"Failed to generate presigned upload URL: {str(e)}")

    def generate_presigned_download_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: Optional[str] = None
    ) -> str:
        """
        Generate pre-signed URL for file download.

        Args:
            key: S3 object key (path)
            expires_in: URL expiration time in seconds (default: 1 hour)
            filename: Optional filename for Content-Disposition header

        Returns:
            Pre-signed download URL
        """
        try:
            params = {
                'Bucket': self.bucket_name,
                'Key': key
            }

            if filename:
                params['ResponseContentDisposition'] = f'attachment; filename="{filename}"'

            url = self.client.generate_presigned_url(
                'get_object',
                Params=params,
                ExpiresIn=expires_in
            )

            return url
        except ClientError as e:
            raise Exception(f"Failed to generate presigned download URL: {str(e)}")

    def initiate_multipart_upload(
        self,
        key: str,
        content_type: str
    ) -> str:
        """
        Initiate a multipart upload for chunked uploads.

        Args:
            key: S3 object key (path)
            content_type: MIME type of the file

        Returns:
            Upload ID for the multipart upload
        """
        try:
            response = self.client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=key,
                ContentType=content_type
            )
            return response['UploadId']
        except ClientError as e:
            raise Exception(f"Failed to initiate multipart upload: {str(e)}")

    def generate_presigned_part_url(
        self,
        key: str,
        upload_id: str,
        part_number: int,
        expires_in: int = 3600
    ) -> str:
        """
        Generate pre-signed URL for uploading a single part in multipart upload.

        Args:
            key: S3 object key (path)
            upload_id: Multipart upload ID
            part_number: Part number (1-indexed)
            expires_in: URL expiration time in seconds

        Returns:
            Pre-signed URL for part upload
        """
        try:
            url = self.client.generate_presigned_url(
                'upload_part',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key,
                    'UploadId': upload_id,
                    'PartNumber': part_number
                },
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            raise Exception(f"Failed to generate presigned part URL: {str(e)}")

    def complete_multipart_upload(
        self,
        key: str,
        upload_id: str,
        parts: list
    ) -> Dict[str, Any]:
        """
        Complete a multipart upload.

        Args:
            key: S3 object key (path)
            upload_id: Multipart upload ID
            parts: List of part dictionaries with 'ETag' and 'PartNumber'

        Returns:
            Response from S3 with ETag and location
        """
        try:
            response = self.client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            return response
        except ClientError as e:
            raise Exception(f"Failed to complete multipart upload: {str(e)}")

    def abort_multipart_upload(
        self,
        key: str,
        upload_id: str
    ):
        """
        Abort a multipart upload.

        Args:
            key: S3 object key (path)
            upload_id: Multipart upload ID
        """
        try:
            self.client.abort_multipart_upload(
                Bucket=self.bucket_name,
                Key=key,
                UploadId=upload_id
            )
        except ClientError as e:
            raise Exception(f"Failed to abort multipart upload: {str(e)}")

    def delete_file(self, key: str):
        """
        Delete a file from S3.

        Args:
            key: S3 object key (path)
        """
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
        except ClientError as e:
            raise Exception(f"Failed to delete file: {str(e)}")

    def file_exists(self, key: str) -> bool:
        """
        Check if a file exists in S3.

        Args:
            key: S3 object key (path)

        Returns:
            True if file exists, False otherwise

        Raises:
            Exception: If storage is unreachable or a non-404 error occurs.
        """
        try:
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except EndpointConnectionError as e:
            raise Exception(
                f"Storage unavailable: {str(e)}"
            ) from e
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise Exception(f"Failed to check file existence: {str(e)}")

    def get_file_size(self, key: str) -> int:
        """
        Get file size from S3.

        Args:
            key: S3 object key (path)

        Returns:
            File size in bytes
        """
        try:
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return response['ContentLength']
        except ClientError as e:
            raise Exception(f"Failed to get file size: {str(e)}")

    def get_file_content(self, key: str) -> bytes:
        # Ensure bucket exists (lazy check)
        if not self._bucket_checked:
            self._ensure_bucket_exists()
            self._bucket_checked = True
        """
        Download file content from S3.

        Args:
            key: S3 object key (path)

        Returns:
            File content as bytes
        """
        try:
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return response['Body'].read()
        except ClientError as e:
            raise Exception(f"Failed to download file: {str(e)}")

    def download_file(self, key: str) -> bytes:
        """
        Download file content from S3 (alias for get_file_content for API consistency).

        Args:
            key: S3 object key (storage path)

        Returns:
            File content as bytes
        """
        return self.get_file_content(key)

    def upload_file(
        self,
        file_path: str,
        file_content: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """
        Upload file content to S3 at the given key (storage path).

        Args:
            file_path: S3 object key (storage path)
            file_content: Raw bytes to upload
            content_type: MIME type for the object
        """
        if not self._bucket_checked:
            self._ensure_bucket_exists()
            self._bucket_checked = True
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=file_path,
            Body=file_content,
            ContentType=content_type,
        )

    def save_file(
        self,
        tenant_id: str,
        file_id: str,
        file_content,
        file_name: str | None = None,
    ) -> str:
        """
        Save file to S3 storage.

        Args:
            tenant_id: Tenant ID
            file_id: File ID
            file_content: File content (file-like object or ContentFile)
            file_name: Optional logical file name. When set, the key matches
                ``File.storage_path`` from ``FileService.create_file``:
                ``{tenant_id}/{file_id}/{file_name}``. When omitted, legacy key
                ``{tenant_id}/{file_id}`` is used (older tests / tooling).

        Returns:
            S3 object key (storage path)
        """
        # Ensure bucket exists (lazy check)
        if not self._bucket_checked:
            self._ensure_bucket_exists()
            self._bucket_checked = True

        key = (
            f"{tenant_id}/{file_id}/{file_name}"
            if file_name
            else f"{tenant_id}/{file_id}"
        )

        try:
            # Get content type from file_content if available
            content_type = getattr(file_content, 'content_type', 'application/octet-stream')

            # Read content if it's a file-like object
            if hasattr(file_content, 'read'):
                content = file_content.read()
                # Reset file pointer if possible
                if hasattr(file_content, 'seek'):
                    file_content.seek(0)
            else:
                content = file_content

            put_kwargs = {
                "Bucket": self.bucket_name,
                "Key": key,
                "Body": content,
                "ContentType": content_type,
            }
            # Explicitly set ContentLength for bytes/memoryview to avoid
            # IncompleteBody errors with some S3-compatible stores (e.g. MinIO).
            if isinstance(content, (bytes, bytearray, memoryview)):
                put_kwargs["ContentLength"] = len(content)
            self.client.put_object(**put_kwargs)

            return key
        except (ClientError, Exception) as e:
            # If connection error, try alternative endpoint (handled in _ensure_bucket_exists)
            error_str = str(e).lower()
            conn_issue = (
                "name resolution" in error_str
                or "could not connect" in error_str
                or "gaierror" in error_str
            )
            if conn_issue and not self._bucket_checked:
                # Retry with bucket check (which will try alternative endpoints)
                self._bucket_checked = False
                self._ensure_bucket_exists()
                self._bucket_checked = True
                # Retry the operation
                try:
                    self.client.put_object(**put_kwargs)
                    return key
                except (ClientError, Exception) as retry_error:
                    raise Exception(f"Failed to save file after retry: {str(retry_error)}")
            raise Exception(f"Failed to save file: {str(e)}")

