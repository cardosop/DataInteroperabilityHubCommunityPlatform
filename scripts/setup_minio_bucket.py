#!/usr/bin/env python3
"""
Setup MinIO bucket for development and testing.

Creates the hub-files bucket if it doesn't exist.
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_minio_bucket():
    """Create hub-files bucket in MinIO if it doesn't exist"""
    # Try to get settings from Django if available
    try:
        import django

        django.setup()
        from django.conf import settings

        endpoint_url = getattr(
            settings,
            "AWS_S3_ENDPOINT_URL",
            os.environ.get("AWS_S3_ENDPOINT_URL", "http://localhost:9000"),
        )
        access_key = getattr(
            settings, "AWS_ACCESS_KEY_ID", os.environ.get("AWS_ACCESS_KEY_ID", "minio")
        )
        secret_key = getattr(
            settings, "AWS_SECRET_ACCESS_KEY", os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123")
        )
        bucket_name = getattr(
            settings,
            "AWS_STORAGE_BUCKET_NAME",
            os.environ.get("AWS_STORAGE_BUCKET_NAME", "hub-files"),
        )
    except Exception:
        # Fallback to environment variables
        endpoint_url = os.environ.get("AWS_S3_ENDPOINT_URL", "http://localhost:9000")
        access_key = os.environ.get("AWS_ACCESS_KEY_ID", "minio")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123")
        bucket_name = os.environ.get("AWS_STORAGE_BUCKET_NAME", "hub-files")

    print(f"Connecting to MinIO at {endpoint_url}...")

    try:
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

        # Check if bucket exists
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✅ Bucket '{bucket_name}' already exists")
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code in ["404", "403"]:
                # Bucket doesn't exist (404) or forbidden (403 - might mean bucket doesn't exist)
                # Try to create it
                print(f"Bucket '{bucket_name}' not found or access denied. Attempting to create...")
                try:
                    s3_client.create_bucket(Bucket=bucket_name)
                    print(f"✅ Bucket '{bucket_name}' created successfully")
                    return True
                except ClientError as create_error:
                    # If bucket already exists (race condition) or other error
                    create_error_code = create_error.response.get("Error", {}).get(
                        "Code", "Unknown"
                    )
                    if create_error_code == "BucketAlreadyOwnedByYou":
                        print(
                            f"✅ Bucket '{bucket_name}' already exists (created by another process)"
                        )
                        return True
                    else:
                        print(f"❌ Error creating bucket: {create_error}")
                        return False
            else:
                print(f"❌ Error checking bucket: {e}")
                return False

    except Exception as e:
        print(f"❌ Failed to connect to MinIO: {e}")
        print(f"   Make sure MinIO is running at {endpoint_url}")
        return False


if __name__ == "__main__":
    success = setup_minio_bucket()
    sys.exit(0 if success else 1)
