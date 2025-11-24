"""
S3-Compatible Storage Utilities

Utilities for interacting with S3-compatible storage (MinIO, S3, GCS, Azure).
"""
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
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
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        self.endpoint_url = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)
        self.use_ssl = getattr(settings, 'AWS_S3_USE_SSL', True)
        
        # Create S3 client
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
    
    def generate_presigned_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in: int = 3600,
        max_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate pre-signed URL for file upload.
        
        Args:
            key: S3 object key (path)
            content_type: MIME type of the file
            expires_in: URL expiration time in seconds (default: 1 hour)
            max_size: Maximum file size in bytes (optional, for validation)
        
        Returns:
            Dictionary with upload_url and fields for POST request
        """
        try:
            conditions = [
                {'Content-Type': content_type}
            ]
            if max_size:
                conditions.append(['content-length-range', 1, max_size])
            
            presigned_post = self.client.generate_presigned_post(
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
        """
        try:
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
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

