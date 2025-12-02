#!/usr/bin/env python3
"""
Setup MinIO bucket for development and testing.

Creates the hub-files bucket if it doesn't exist.
"""
import boto3
from botocore.exceptions import ClientError
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def setup_minio_bucket():
    """Create hub-files bucket in MinIO if it doesn't exist"""
    endpoint_url = os.environ.get('AWS_S3_ENDPOINT_URL', 'http://localhost:9000')
    access_key = os.environ.get('AWS_ACCESS_KEY_ID', 'minio')
    secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY', 'minio123')
    bucket_name = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'hub-files')
    
    print(f"Connecting to MinIO at {endpoint_url}...")
    
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        # Check if bucket exists
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✅ Bucket '{bucket_name}' already exists")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                print(f"Creating bucket '{bucket_name}'...")
                s3_client.create_bucket(Bucket=bucket_name)
                print(f"✅ Bucket '{bucket_name}' created successfully")
                return True
            else:
                print(f"❌ Error checking bucket: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Failed to connect to MinIO: {e}")
        print(f"   Make sure MinIO is running at {endpoint_url}")
        return False


if __name__ == '__main__':
    success = setup_minio_bucket()
    sys.exit(0 if success else 1)

