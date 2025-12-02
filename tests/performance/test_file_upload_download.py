"""
T.15: Load test file upload/download

Tests file upload and download performance under load.
Targets from Testing_Strategy.md §8.1.4:
- 20 concurrent file uploads
- Sustained ingress throughput of at least 50 MB/s aggregate
- P95 latency ≤ 500ms for init/complete endpoints
"""
import os
import time
import random
import requests
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
from tests.performance.helpers import PerformanceTestHelper


class FileUploadDownloadUser(FastHttpUser):
    """Locust user for file upload/download load testing"""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    weight = 1
    
    def on_start(self):
        """Set up test user and authentication"""
        self.helper = PerformanceTestHelper(base_url=self.host)
        self.test_data = self.helper.create_test_tenant_and_user(
            tenant_name=f"perf-tenant-{random.randint(1000, 9999)}",
            user_email=f"perf-user-{random.randint(1000, 9999)}@example.com"
        )
        self.headers = self.test_data['headers']
        self.access_token = self.test_data['access_token']
        self.uploaded_files = []
        
        # Initialize S3 client for direct uploads
        self._init_s3_client()
    
    def _init_s3_client(self):
        """Initialize S3 client for direct uploads"""
        try:
            # Get S3 settings from environment or use defaults
            s3_endpoint = os.getenv('S3_ENDPOINT_URL', 'http://localhost:9000')
            s3_access_key = os.getenv('AWS_ACCESS_KEY_ID', 'minio')
            s3_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', 'minio123')
            
            self.s3_client = boto3.client(
                's3',
                endpoint_url=s3_endpoint,
                aws_access_key_id=s3_access_key,
                aws_secret_access_key=s3_secret_key,
                config=Config(signature_version='s3v4')
            )
            self.s3_bucket = os.getenv('S3_BUCKET_NAME', 'hub-files')
        except Exception as e:
            print(f"Warning: Could not initialize S3 client: {e}")
            self.s3_client = None
    
    @task(3)
    def test_file_upload_small(self):
        """Test small file upload (10-100 MB)"""
        self._upload_file(size_mb=random.randint(10, 100))
    
    @task(2)
    def test_file_upload_medium(self):
        """Test medium file upload (100-500 MB)"""
        self._upload_file(size_mb=random.randint(100, 500))
    
    @task(1)
    def test_file_upload_large(self):
        """Test large file upload (0.5-2 GB) - chunked"""
        self._upload_file(size_mb=random.randint(500, 2000), use_chunked=True)
    
    @task(5)
    def test_file_download(self):
        """Test file download"""
        if not self.uploaded_files:
            return
        
        file_id = random.choice(self.uploaded_files)
        with self.client.get(
            f"/api/v1/files/{file_id}/download",
            headers=self.headers,
            name="/api/v1/files/{id}/download",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                download_url = data.get('download_url')
                if download_url:
                    # Download the file
                    download_start = time.time()
                    download_response = requests.get(download_url, timeout=300)
                    download_time = (time.time() - download_start) * 1000  # ms
                    
                    if download_response.status_code == 200:
                        response.success()
                        # Track download metrics
                        events.request.fire(
                            request_type="download",
                            name="file_download_transfer",
                            response_time=download_time,
                            response_length=len(download_response.content),
                            exception=None
                        )
                    else:
                        response.failure(f"Download failed: {download_response.status_code}")
                else:
                    response.failure("No download URL in response")
            elif response.status_code == 404:
                # File might have been deleted, remove from list
                if file_id in self.uploaded_files:
                    self.uploaded_files.remove(file_id)
                response.failure("File not found")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    def _upload_file(self, size_mb: int, use_chunked: bool = False):
        """Upload a file of specified size"""
        file_name = f"perf-test-{int(time.time())}-{random.randint(1000, 9999)}.csv"
        
        # Step 1: Initialize upload
        init_start = time.time()
        init_data = {
            'name': file_name,
            'content_type': 'text/csv',
            'size_bytes': size_mb * 1024 * 1024
        }
        
        if use_chunked:
            init_data['chunk_count'] = max(1, (size_mb * 1024 * 1024) // (10 * 1024 * 1024))  # 10MB chunks
        
        with self.client.post(
            "/api/v1/files/init",
            json=init_data,
            headers=self.headers,
            name="/api/v1/files/init",
            catch_response=True
        ) as init_response:
            init_time = (time.time() - init_start) * 1000  # ms
            
            if init_response.status_code != 201:
                init_response.failure(f"Init failed: {init_response.status_code}")
                return
            
            init_data_resp = init_response.json()
            file_id = init_data_resp.get('id')
            upload_url = init_data_resp.get('upload_url')
            
            if not upload_url:
                init_response.failure("No upload URL in response")
                return
            
            init_response.success()
            
            # Track init latency
            if init_time > 500:
                events.request.fire(
                    request_type="upload_init",
                    name="file_upload_init_slow",
                    response_time=init_time,
                    response_length=0,
                    exception=None
                )
        
        # Step 2: Upload file data directly to S3
        upload_start = time.time()
        test_data = self.helper.create_test_file_data(size_mb)
        
        try:
            if self.s3_client:
                # Extract key from upload URL or use file_id
                key = f"files/{file_id}/{file_name}"
                self.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=key,
                    Body=test_data,
                    ContentType='text/csv'
                )
            else:
                # Fallback: use pre-signed URL
                upload_response = requests.put(
                    upload_url,
                    data=test_data,
                    headers={'Content-Type': 'text/csv'},
                    timeout=300
                )
                if upload_response.status_code not in [200, 204]:
                    raise Exception(f"Upload failed: {upload_response.status_code}")
            
            upload_time = (time.time() - upload_start) * 1000  # ms
            upload_throughput_mbps = (size_mb * 8) / (upload_time / 1000) if upload_time > 0 else 0
            
            # Track upload throughput
            events.request.fire(
                request_type="upload",
                name="file_upload_transfer",
                response_time=upload_time,
                response_length=len(test_data),
                exception=None
            )
            
        except Exception as e:
            events.request.fire(
                request_type="upload",
                name="file_upload_transfer",
                response_time=0,
                response_length=0,
                exception=e
            )
            return
        
        # Step 3: Complete upload
        complete_start = time.time()
        with self.client.post(
            f"/api/v1/files/{file_id}/complete",
            json={},
            headers=self.headers,
            name="/api/v1/files/{id}/complete",
            catch_response=True
        ) as complete_response:
            complete_time = (time.time() - complete_start) * 1000  # ms
            
            if complete_response.status_code == 200:
                complete_response.success()
                self.uploaded_files.append(file_id)
                
                # Track complete latency
                if complete_time > 500:
                    events.request.fire(
                        request_type="upload_complete",
                        name="file_upload_complete_slow",
                        response_time=complete_time,
                        response_length=0,
                        exception=None
                    )
            else:
                complete_response.failure(f"Complete failed: {complete_response.status_code}")

